#!/usr/bin/env python3
"""Generate a versioned validation run report (fixes #129 P0-2).

Reads the persisted scenario results from ``validation-runs/<run>/scenarios.json``
(the newest run by default) and emits an executive report to
``docs/dev/validation-reports/launch-validation-<version>-<runid>.md``.

The report uses the framework ``§6`` executive-summary skeleton: verdict counts,
scenario status table, and an appendix pointer back to the framework template
and evidence catalog.  Since issue #139 it also renders a root-cause
``## Blockers`` section — every failing step of every failed scenario, with its
``llm_reason`` / ``llm_meta`` when present — and a ``## Per-step trace``
appendix with the full per-step trace table (scenario | step_index | name |
tool | status | duration | trace_id).

Usage:
    python3 scripts/validation_report.py [--version VERSION] [--run RUN_ID]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "validation-runs"
REPORTS = ROOT / "docs" / "dev" / "validation-reports"
FRAMEWORK = "docs/dev/acceptance-framework.md"
TEMPLATE = "docs/archive/launch-validation-framework.md"


def _latest_run() -> str:
    pointer = RUNS / "latest.txt"
    if pointer.exists():
        return pointer.read_text().strip()
    raise SystemExit(
        f"No validation runs found under {RUNS}; run scenarios with save_results first."
    )


def _status_counts(scenarios: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for sc in scenarios:
        status = sc.get("status", "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts


def _truncate_detail(detail: Any, limit: int = 200) -> str:
    """Render a step detail for the blockers list, truncated to ~*limit* chars.

    Non-string details (e.g. the envelope dict on passed steps) are
    serialised to JSON first so the truncation applies to the text.
    """
    if not isinstance(detail, str):
        detail = json.dumps(detail, ensure_ascii=False)
    if len(detail) > limit:
        return detail[:limit] + "…"
    return detail


def _escape_cell(value: str) -> str:
    """Escape pipe/newline characters so a value fits a markdown table cell."""
    return value.replace("|", "\\|").replace("\n", " ")


def _iter_steps(
    scenarios: list[dict[str, Any]],
) -> list[tuple[str, dict[str, Any]]]:
    """Flatten every step of every scenario for the per-step trace table.

    Yields ``(scenario_name, step)`` pairs covering the main steps, their
    nested recovery steps (issue #138), and the cleanup steps — in that
    order — so the appendix renders the full execution trace of the run.
    """
    rows: list[tuple[str, dict[str, Any]]] = []
    for sc in scenarios:
        sc_name = sc.get("scenario", "?")
        for step in sc.get("steps", []):
            rows.append((sc_name, step))
            for rec in step.get("recovery", []):
                rows.append((sc_name, rec))
        for step in sc.get("cleanup", {}).get("steps", []):
            rows.append((sc_name, step))
    return rows


# --- Causal report (TR-S-02) ---------------------------------------------
# The historic ``## Blockers`` list merely echoed failing steps with truncated
# detail, so an agent could not tell a flaky assertion from an environment
# precondition.  The functions below classify every failure into a cause class,
# deduplicate repeated failure signatures, and surface a first-cause candidate.

CAUSE_CLASSES = (
    "unconfigured-env",
    "timeout",
    "error-envelope",
    "llm-parse",
    "assertion-failed",
    "unknown",
)

# Lower rank == more causally upstream.  An unmet environment precondition or a
# timeout can explain a later assertion failure; the reverse is unlikely.
_CAUSE_PRIORITY = {
    "unconfigured-env": 0,
    "timeout": 1,
    "error-envelope": 2,
    "llm-parse": 3,
    "assertion-failed": 4,
    "unknown": 5,
}

_UNCONFIGURED_MARKERS = (
    "missing required env",
    "missing required domain",
    "not reachable",
    "requires a real llm api key",
    "llm_not_configured",
    "must configure",
    "not configured",
)
_TIMEOUT_MARKERS = ("timed out", "timeout")
_LLM_PARSE_MARKERS = (
    "llm_assert error",
    "llm judge returned",
    "non-json",
    "empty content",
    "unexpected llm verdict",
    "expecting value",
    "jsondecodeerror",
)
_ENVELOPE_MARKERS = ("expected success=", "success=false")
_ASSERTION_MARKERS = (
    "data_has",
    "stdout_has",
    "stderr_has",
    "exit_code",
    "status_code",
    "json_has",
    "llm_assert failed",
    "expected ",
)


def _detail_text(step: dict[str, Any]) -> str:
    detail = step.get("detail")
    if not isinstance(detail, str):
        detail = json.dumps(detail, ensure_ascii=False)
    return detail


def _classify_failure(step: dict[str, Any]) -> str:
    """Map a failing step to one of :data:`CAUSE_CLASSES` (TR-S-02).

    Ordered most-specific first: an ``unconfigured`` status (or an explicit
    environment-precondition message) wins; then a timeout; then an LLM judge
    parse failure; then a tool error envelope; then a generic assertion
    mismatch; anything else is ``unknown``.
    """
    if str(step.get("status", "")) == "unconfigured":
        return "unconfigured-env"
    text = _detail_text(step).lower()
    if any(m in text for m in _UNCONFIGURED_MARKERS):
        return "unconfigured-env"
    if any(m in text for m in _TIMEOUT_MARKERS):
        return "timeout"
    if any(m in text for m in _LLM_PARSE_MARKERS):
        return "llm-parse"
    if any(m in text for m in _ENVELOPE_MARKERS):
        return "error-envelope"
    if any(m in text for m in _ASSERTION_MARKERS):
        return "assertion-failed"
    return "unknown"


def _normalize_detail(detail: Any) -> str:
    """Collapse whitespace and cap length so equal failures dedup together."""
    text = detail if isinstance(detail, str) else json.dumps(detail, ensure_ascii=False)
    return " ".join(text.split())[:240]


def _failure_key(failure: dict[str, Any]) -> tuple[str, str, str]:
    return (failure["cause"], str(failure.get("tool", "?")), _normalize_detail(failure["detail"]))


def _iter_step_and_recovery(step: dict[str, Any]):
    yield step
    for rec in step.get("recovery", []) or []:
        yield rec


def _collect_failures(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collect every failed/unconfigured step of failed scenarios, in order.

    Walks each failed scenario's main steps (and their recovery steps) plus
    its cleanup steps; only steps whose status is ``failed`` or
    ``unconfigured`` become records, so the report classifies residual
    problems, not clean passes.
    """
    failures: list[dict[str, Any]] = []
    order = 0
    for sc in scenarios:
        if sc.get("status") != "failed":
            continue
        sc_name = sc.get("scenario", "?")
        sources = (
            ("primary", sc.get("steps", [])),
            ("cleanup", sc.get("cleanup", {}).get("steps", [])),
        )
        for base_location, steps in sources:
            for step in steps:
                for sub in _iter_step_and_recovery(step):
                    if sub.get("status") not in ("failed", "unconfigured"):
                        continue
                    order += 1
                    location = base_location if sub is step else f"{base_location}-recovery"
                    failures.append(
                        {
                            "scenario": sc_name,
                            "location": location,
                            "name": sub.get("name", "?"),
                            "tool": sub.get("tool", "?"),
                            "status": sub.get("status"),
                            "detail": sub.get("detail"),
                            "step_id": sub.get("step_id", sub.get("step_index", "?")),
                            "step_index": sub.get("step_index"),
                            "llm_reason": sub.get("llm_reason"),
                            "llm_meta": sub.get("llm_meta"),
                            "recovered": bool(sub.get("recovered")),
                            "cause": _classify_failure(sub),
                            "order": order,
                        }
                    )
    return failures


def _first_cause(failures: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Pick the most causally-upstream residual failure, or ``None``.

    Recovered failures are never the first cause (they were already fixed).
    Among the rest, environment/timeout causes outrank downstream assertion
    failures; ties break on execution order.
    """
    candidates = [f for f in failures if not f["recovered"]] or failures
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda f: (_CAUSE_PRIORITY.get(f["cause"], 99), f["order"]),
    )


def _causal_lines(failures: list[dict[str, Any]]) -> list[str]:
    if not failures:
        return ["(no failing scenarios in this run)", ""]

    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for failure in failures:
        groups.setdefault(_failure_key(failure), []).append(failure)

    lines: list[str] = []
    lines.append("### Cause classification")
    lines.append("")
    lines.append("| Cause class | Occurrences | Distinct groups |")
    lines.append("|-------------|-------------|-----------------|")
    for cause in CAUSE_CLASSES:
        members = [f for f in failures if f["cause"] == cause]
        if not members:
            continue
        distinct = sum(1 for group in groups.values() if group[0]["cause"] == cause)
        lines.append(f"| {cause} | {len(members)} | {distinct} |")
    lines.append("")

    first = _first_cause(failures)
    lines.append("### First-cause candidate")
    lines.append("")
    if first is None:
        lines.append("(none)")
    else:
        lines.append(
            f"`{first['scenario']}` step {first['step_id']} {first['name']} "
            f"({first['tool']}) — `{first['cause']}`: "
            f"{_truncate_detail(first['detail'])}"
        )
        lines.append("")
        lines.append(
            "Most causally-upstream residual failure (environment/timeout causes "
            "outrank downstream assertion failures; ties break on execution order; "
            "recovered failures are never chosen)."
        )
    lines.append("")

    lines.append("### Failure groups (deduplicated)")
    lines.append("")
    for group in groups.values():
        head = group[0]
        scenarios_in_group = sorted({m["scenario"] for m in group})
        scenario_label = ", ".join(f"`{s}`" for s in scenarios_in_group)
        lines.append(
            f"- `[{head['cause']}]` ×{len(group)} — {scenario_label} step "
            f"{head['step_id']} {head['name']} ({head['tool']}): "
            f"{_truncate_detail(head['detail'])}"
        )
    lines.append("")

    lines.append("### Failing steps")
    lines.append("")
    for failure in failures:
        recovered = " (recovered)" if failure["recovered"] else ""
        lines.append(
            f"- `{failure['scenario']}` step {failure['step_id']} {failure['name']} "
            f"({failure['tool']}) — {_truncate_detail(failure['detail'])} "
            f"[{failure['cause']}]{recovered}"
        )
        if failure["llm_reason"]:
            lines.append(f"  - llm_reason: {failure['llm_reason']}")
        if failure["llm_meta"]:
            lines.append(f"  - llm_meta: {json.dumps(failure['llm_meta'], ensure_ascii=False)}")
    lines.append("")
    return lines


def _history_token(status: Any) -> str:
    """Compact per-run status token for the history column."""
    return {
        "passed": "P",
        "failed": "F",
        "unconfigured": "U",
        "partial": "~",
    }.get(str(status), "?")


def _category_pyramid_section(runs_dir: Path) -> list[str]:
    """Render per-category×pyramid N-run pass history (TR-B-01/TR-B-02).

    Consumes the ledger persisted by ``autoinfo.mcp.validation``.  The gate
    rule is the methodology's "hard 5/5, soft 4/5": a cell passes the hard rule
    when every recorded run passed and the soft rule when its rate is >= 0.8.
    An unmeasured cell renders ``-`` (never a pass) — the report must not fake
    a verdict.
    """
    lines = ["## Category × pyramid pass history", ""]
    try:
        from autoinfo.mcp.validation import category_pyramid_history_report
    except Exception as exc:  # noqa: BLE001 - report must degrade, not crash
        lines.append(f"(history unavailable: {exc})")
        lines.append("")
        return lines
    history = category_pyramid_history_report(runs_dir=runs_dir)
    if not history["runs"]:
        lines.append(
            "(no suite-run history recorded yet — call "
            "`run_all_validation_scenarios` to accumulate N-run history)"
        )
        lines.append("")
        return lines
    window = history.get("window")
    header = f"Suite runs recorded: {history['total_runs']}"
    if window:
        header += f" (window: last {window})"
    lines.append(header)
    lines.append("")
    lines.append(
        "Gate rule: **hard 5/5** = every recorded run passed; "
        "**soft 4/5** = pass rate ≥ 0.8. An unmeasured cell reports `-`."
    )
    lines.append("")
    lines.append(
        "| Category | Pyramid | Runs | Passes | Rate | Hard (5/5) | Soft (4/5) | History |"
    )
    lines.append(
        "|----------|---------|------|--------|------|------------|------------|---------|"
    )
    for cell in history["cells"].values():
        rate = cell["rate"]
        rate_cell = f"{rate:.0%}" if isinstance(rate, (int, float)) else "-"
        measured = bool(cell["runs"])
        hard = "PASS" if cell["meets_hard"] else ("FAIL" if measured else "-")
        soft = "PASS" if cell["meets_soft"] else ("FAIL" if measured else "-")
        hist_cell = " ".join(_history_token(h["status"]) for h in cell["history"]) or "-"
        lines.append(
            f"| {cell['category']} | {cell['pyramid_layer']} | {cell['runs']} "
            f"| {cell['passes']} | {rate_cell} | {hard} | {soft} | {hist_cell} |"
        )
    lines.append("")
    failed_hard = sum(1 for c in history["cells"].values() if c["runs"] and not c["meets_hard"])
    failed_soft = sum(1 for c in history["cells"].values() if c["runs"] and not c["meets_soft"])
    lines.append(f"Cells failing hard rule: {failed_hard}; cells failing soft rule: {failed_soft}.")
    if history.get("unclassified"):
        lines.append("")
        lines.append(
            f"Unclassified scenarios in history: "
            f"{len(history['unclassified'])} (no category/pyramid — "
            "not counted in any cell)."
        )
    lines.append("")
    return lines


def generate(version: str, run_id: str) -> Path:
    run_dir = RUNS / run_id
    payload_path = run_dir / "scenarios.json"
    if not payload_path.exists():
        raise SystemExit(f"scenarios.json not found in {run_dir}")
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    scenarios: list[dict[str, Any]] = payload.get("scenarios", [])
    run_type = payload.get("run_type", "single")
    counts = _status_counts(scenarios)
    passed = counts.get("passed", 0)
    failed = counts.get("failed", 0)
    unconfigured = counts.get("unconfigured", 0)

    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / f"launch-validation-{version}-{run_id}.md"

    lines: list[str] = []
    lines.append(f"# Launch Validation Run Report {version} ({run_id})")
    lines.append("")
    lines.append(
        f"> Run: {run_id} | Type: {run_type} | Scenarios: {len(scenarios)} "
        f"(passed={passed}, failed={failed}, unconfigured={unconfigured})"
    )
    lines.append(">")
    lines.append(
        f"> Template: `{FRAMEWORK}` | Skeleton: `§6` | Evidence catalog: appendix of the template"
    )
    lines.append("")
    lines.append("## Verdicts")
    lines.append("")
    lines.append("| Scenario | Status | Passed/Total |")
    lines.append("|----------|--------|---|")
    for sc in sorted(scenarios, key=lambda x: x.get("scenario", "")):
        summary = sc.get("summary", {})
        status_str = sc.get("status", "?")
        if sc.get("regression"):
            status_str = f"{status_str} (regression)"
        lines.append(
            f"| {sc.get('scenario', '?')} | {status_str} "
            f"| {summary.get('passed', 0)}/{summary.get('total', 0)} |"
        )
    lines.append("")
    lines.append("## Executive summary")
    lines.append("")
    regression_failed = sum(
        1 for sc in scenarios if sc.get("regression") and sc.get("status") == "failed"
    )
    if failed or unconfigured:
        lines.append(
            f"{failed} scenario(s) failed and {unconfigured} were unconfigured; "
            f"{passed} passed. See the per-scenario status table and the evidence "
            f"files under `{run_dir}` for details."
        )
        if regression_failed:
            lines.append(
                f"Includes {regression_failed} regression failure(s) "
                f"(see Regression failures section)."
            )
    else:
        lines.append(f"All {passed} scenario(s) passed. Evidence available under `{run_dir}`.")
    lines.append("")

    # --- Regression failures section (issue #140 P1-3) -----------------------
    regression_failures = [
        sc for sc in scenarios if sc.get("regression") and sc.get("status") == "failed"
    ]
    lines.append("## Regression failures")
    lines.append("")
    if not regression_failures:
        lines.append("(no regression failures in this run)")
    else:
        for sc in regression_failures:
            sc_name = sc.get("scenario", "?")
            issue_ref = sc.get("regression_issue", "?")
            issue_paren = f"({issue_ref})" if issue_ref.startswith("#") else f"(#{issue_ref})"
            summary = sc.get("summary", {})
            lines.append(
                f"- `REG RGRESSION {sc_name} {issue_paren}` — "
                f"failed {summary.get('passed', 0)}/{summary.get('total', 0)} passed "
                f"({summary.get('failed', 0)} failed, "
                f"{summary.get('unconfigured', 0)} unconfigured)"
            )
    lines.append("")
    # --- Scenario leak warnings (B-03) ---
    # A leak is a hygiene failure even on a passing scenario: fixtures that
    # should have been cleaned up still live in the user's KB.  Surface them
    # regardless of scenario status.
    leak_warnings = [
        w for sc in scenarios for w in sc.get("warnings", []) if w.startswith("SCENARIO_LEAK")
    ]
    if leak_warnings:
        lines.append("### Scenario leak warnings (B-03)")
        lines.append("")
        for w in leak_warnings:
            lines.append(f"- {w}")
        lines.append("")
    lines.append("## Blockers")
    lines.append("")
    lines.extend(_causal_lines(_collect_failures(scenarios)))
    lines.append("## Per-step trace")
    lines.append("")
    lines.append(
        "Full per-step execution trace for every scenario — "
        "step identity (run-unique ``step_id``, falling back to "
        "``step_index``), duration (wall-clock seconds, incl. "
        "recovery), and the run trace_id (issues #139, TR-S-03)."
    )
    lines.append("")
    lines.append("| Scenario | Step | Name | Tool | Status | Duration (s) | Trace ID |")
    lines.append("|----------|------|------|------|--------|--------------|----------|")
    for sc_name, step in _iter_steps(scenarios):
        dur = step.get("duration")
        dur_cell = f"{dur:.3f}" if isinstance(dur, (int, float)) else "-"
        identity = step.get("step_id", step.get("step_index", "-"))
        lines.append(
            f"| {_escape_cell(sc_name)} | {identity} "
            f"| {_escape_cell(str(step.get('name', '?')))} "
            f"| {_escape_cell(str(step.get('tool', '?')))} "
            f"| {step.get('status', '?')} | {dur_cell} "
            f"| {step.get('trace_id', '-')} |"
        )
    lines.append("")
    lines.append("## Appendix pointer")
    lines.append("")
    ev = run_dir / "evidence"
    if ev.is_dir():
        for f in sorted(ev.rglob("*")):
            if f.is_file():
                lines.append(f"- `{f.relative_to(ROOT)}`")
    else:
        lines.append(f"(no evidence subdir yet — artifacts appear under `{run_dir}` on collect)")
    lines.append("")
    lines.extend(_category_pyramid_section(RUNS))
    lines.append("Generated by `python3 scripts/validation_report.py`.")
    lines.append("")

    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a versioned validation run report")
    parser.add_argument("--version", default="unreleased", help="Release/feature version label")
    parser.add_argument("--run", default="", help="Run ID (default: newest from latest.txt)")
    args = parser.parse_args()

    run_id = args.run or _latest_run()
    import os

    version = args.version or os.environ.get("AUTOINFO_VERSION", "unreleased")
    out = generate(version, run_id)
    print(f"REPORT: {out}")


if __name__ == "__main__":
    sys.exit(main())
