"""AX verification metrics — instrument + gate M-01..M-06 (plan §6, Todo 21).

Agent-experience (AX) quality is pinned to six metrics, each mapped to a
pillar and an axis (``agent-oriented-gap-register.md`` §6) and each with a
target that CI enforces:

=========  ==========================  ===================  ==========================
ID         Metric                      Target               Live source
=========  ==========================  ===================  ==========================
M-01       Task completion rate        > 95%                ``validation-runs/``
                                                             ``category-pyramid-history.json``
                                                             (newest recorded suite run)
M-02       Tool-call accuracy          > 98%                ``TOOL_SELECTION_OK`` marker in a
                                                             persisted validation run trace
M-03       Recovery success rate       > 99%                ``recover-*`` scenario results +
                                                             step ``recovery``/``recovered`` flags
M-04       Documentation freshness     100%                 ``scripts/doc_inventory.py --check``
M-05       Token efficiency            <= 10% regression    deterministic token count of real
                                                             generated product text (keyless) vs a
                                                             tracked pinned baseline; plus
                                                             ``llm_meta.tokens`` when present
M-06       Error recovery time         < 30s                duration of failed steps that returned
                                                             an actionable error envelope
=========  ==========================  ===================  ==========================

Design rules
------------
- **Live, never faked.** Every value is read from a live artifact: the run
  ledger, persisted scenario result envelopes, the doc-inventory checker, or
  token metadata carried in step traces.  A metric with no captured data is
  reported ``UNMEASURED`` — it is never silently treated as a pass.
- **No hard-coded result values.** Only the *targets* are pinned (they come
  from plan §6); every measured value is derived from the sources above.
- **Gate on breach.** ``main`` returns non-zero when any metric is ``FAIL``.
  ``UNMEASURED`` does not fail the gate (the data source is absent in a fresh
  checkout), but it is always printed and counted.
- **M-05 signal (no LLM key required).** Keyless environments carry no
  ``llm_meta.tokens``, so M-05's gated value is the *deterministic token count
  of generated product text*: a fixed benchmark of real products rendered
  through the **real** output pipeline (Jinja2 templates + product-template
  families) with the LLM synthesis seam pinned to a deterministic synthesis.
  The rendered text is byte-stable run-to-run, so the count is reproducible on
  any machine.  When a persisted run *does* carry ``llm_meta.tokens``, the mean
  tokens per LLM task is measured alongside and gated too — but only if the
  pinned baseline carries an LLM reference, keeping the baseline channel
  consistent.
- **M-05 baseline is tracked.** The pinned baseline lives at
  ``scripts/ax_token_baseline.json`` — a committed path, never under the
  gitignored ``validation-runs/`` — so a fresh CI checkout can always measure
  and gate M-05.  Refresh it deliberately with ``--update-token-baseline``
  (never automatically: CI must not move the goalposts it is gating against).
- **Never fake a pass.** An M-05 benchmark that cannot render (import/runtime
  failure) is reported ``UNMEASURED`` with the reason; it is never counted as a
  pass and never silently substituted with a constant.

Sources are overridable (``--runs-dir``, ``--history-file``,
``--token-baseline``) so the gate itself can be proven against a planted
breach without touching product code.

``--record`` runs the deterministic, LLM-free scenario subset that feeds
M-01/M-02/M-03/M-06 and persists it as one ``suite`` run, so CI has fresh live
evidence to gate on.  M-05 is measured independently of ``--record`` from the
keyless deterministic product benchmark, so it is live in CI as well.

Run from the project root::

    python3 scripts/ax_metrics.py            # measure + gate
    python3 scripts/ax_metrics.py --record   # seed deterministic evidence, then measure
    python3 scripts/ax_metrics.py --json     # machine-readable report
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import re
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUNS_DIR = ROOT / "validation-runs"
DEFAULT_HISTORY_FILE = "category-pyramid-history.json"
#: M-05's pinned baseline — a **tracked** path (never the gitignored
#: ``validation-runs/``), so a fresh CI checkout can always measure + gate M-05.
DEFAULT_TOKEN_BASELINE = ROOT / "scripts" / "ax_token_baseline.json"
DOC_INVENTORY = ROOT / "scripts" / "doc_inventory.py"
LATEST_POINTER = "latest.txt"

#: The deterministic, LLM-free scenarios that feed the AX metrics.  Each one
#: runs through the real MCP/scenario surface; none needs an LLM key, a live
#: REST server, or a configured domain.  Kept as the single seed definition so
#: CI (``--record``) and tests share it.
SEED_SCENARIOS: tuple[str, ...] = (
    "agent-tool-selection",
    "error-boundary",
    "recover-pipeline-resume",
    "recover-rollback",
    "recover-idempotent-retry",
    "recover-cli-resume-from",
    "perf-token-budget",
)

#: ``(id, metric, pillar, axis, operator, threshold, unit, target_text)``.
#: Targets are from plan §6; operators are the strict reading of its wording
#: ("> 95%" fails at exactly 95%; "< 30s" fails at exactly 30s).
SPEC: tuple[tuple[str, str, str, str, str, float, str, str], ...] = (
    ("M-01", "Task completion rate", "Toolability", "B", ">", 0.95, "ratio", ">95%"),
    ("M-02", "Tool-call accuracy", "Toolability", "B", ">", 0.98, "ratio", ">98%"),
    ("M-03", "Recovery success rate", "Recoverability", "B", ">", 0.99, "ratio", ">99%"),
    ("M-04", "Documentation freshness", "All", "All", "==", 1.0, "ratio", "100%"),
    (
        "M-05",
        "Token efficiency",
        "Recoverability",
        "B",
        "<=",
        0.10,
        "regression",
        "<=10% regression",
    ),
    ("M-06", "Error recovery time", "Recoverability", "A", "<", 30.0, "seconds", "<30s"),
)

#: M-05 deterministic benchmark.  The *inputs* are pinned (fixed entry set +
#: fixed synthesis) so the rendered product text is byte-stable run-to-run; the
#: product text itself is produced live by the real output pipeline.
_BENCH_DOMAIN = "medical-research"
_BENCH_PRODUCTS: tuple[str, ...] = (
    "digest",
    "premium-briefing",
    "enterprise-briefing",
    "magazine-digest",
)
_BENCH_ENTRY_TITLES: tuple[str, ...] = (
    "Time-lapse imaging improves IVF outcomes",
    "AI embryo selection systematic review",
    "IVF clinic workflows",
)
_BENCH_SYNTHESIS: dict[str, Any] = {
    "executive_summary": ("IVF technology advanced with time-lapse imaging and AI selection."),
    "key_findings": [
        {
            "topic": "Time-lapse imaging",
            "detail": "Significant improvement in live birth rates (48.2% vs 39.5%).",
        },
        {
            "topic": "AI embryo selection",
            "detail": "Promising but lacks prospective validation.",
        },
    ],
    "trends": ["Growing evidence for time-lapse imaging benefits."],
    "recommendations": ["Support prospective AI validation trials."],
    "implications": ["Clinics should evaluate time-lapse imaging adoption."],
    "risks": [
        {
            "title": "Validation lag",
            "likelihood": "high",
            "impact": "medium",
            "mitigation": "Run prospective trials.",
        }
    ],
    "action_required": ["Fund prospective AI validation trials."],
}

#: Dependency-free deterministic tokenizer: word runs plus individual
#: punctuation units.  No vendor/model tokenizer is imported, so the count is
#: identical on every machine and needs no API key — which is the entire point
#: of measuring token efficiency without an LLM key.
_DETERMINISTIC_TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)

_TOKEN_SELECTION_RE = re.compile(r"TOOL_SELECTION_OK\s+(\d+)\s*/\s*(\d+)\s+accuracy=([0-9.]+)")


# ---------------------------------------------------------------------------
# Source helpers
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> Any:
    """Load JSON, returning ``None`` on any read/parse failure (never raise)."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _run_dirs(runs_dir: Path) -> list[Path]:
    """Run directories holding ``scenarios.json``, newest-first by name."""
    if not runs_dir.is_dir():
        return []
    return sorted(
        (p for p in runs_dir.iterdir() if p.is_dir() and (p / "scenarios.json").is_file()),
        key=lambda p: p.name,
        reverse=True,
    )


def _step_stdout(step: dict[str, Any]) -> str:
    """Return a step's captured stdout, or ``""`` when absent."""
    detail = step.get("detail")
    if not isinstance(detail, dict):
        return ""
    data = detail.get("data")
    if not isinstance(data, dict):
        return ""
    stdout = data.get("stdout")
    return stdout if isinstance(stdout, str) else ""


def _newest_run_with(
    runs_dir: Path, predicate: Callable[[dict[str, Any]], bool]
) -> tuple[Path, dict[str, Any]] | None:
    """Return ``(run_dir, payload)`` for the newest run satisfying *predicate*."""
    for run in _run_dirs(runs_dir):
        payload = _load_json(run / "scenarios.json")
        if isinstance(payload, dict) and predicate(payload):
            return run, payload
    return None


# ---------------------------------------------------------------------------
# Measure helpers
# ---------------------------------------------------------------------------


def _unmeasured(
    spec: tuple[str, str, str, str, str, float, str, str],
    reason: str,
    *,
    source: str,
    sample: str = "0",
    detail: str = "",
) -> dict[str, Any]:
    mid, metric, pillar, axis, op, threshold, unit, target_text = spec
    return {
        "id": mid,
        "metric": metric,
        "pillar": pillar,
        "axis": axis,
        "operator": op,
        "threshold": threshold,
        "unit": unit,
        "target": target_text,
        "value": None,
        "display": "UNMEASURED",
        "sample": sample,
        "verdict": "UNMEASURED",
        "source": source,
        "detail": f"{reason} {detail}".strip(),
    }


def _measured(
    spec: tuple[str, str, str, str, str, float, str, str],
    value: float,
    *,
    source: str,
    sample: str,
    detail: str = "",
    display: str | None = None,
) -> dict[str, Any]:
    mid, metric, pillar, axis, op, threshold, unit, target_text = spec
    if display is None:
        if unit == "ratio":
            display = f"{value * 100:.1f}%"
        elif unit == "seconds":
            display = f"{value:.1f}s"
        else:  # regression
            display = f"{value * 100:+.1f}%"
    return {
        "id": mid,
        "metric": metric,
        "pillar": pillar,
        "axis": axis,
        "operator": op,
        "threshold": threshold,
        "unit": unit,
        "target": target_text,
        "value": value,
        "display": display,
        "sample": sample,
        "verdict": _verdict(op, threshold, value),
        "source": source,
        "detail": detail,
    }


def _verdict(op: str, threshold: float, value: float) -> str:
    if op == ">":
        return "PASS" if value > threshold else "FAIL"
    if op == "<":
        return "PASS" if value < threshold else "FAIL"
    if op == "==":
        return "PASS" if value == threshold else "FAIL"
    if op == "<=":
        return "PASS" if value <= threshold else "FAIL"
    raise ValueError(f"unknown operator: {op!r}")


# ---------------------------------------------------------------------------
# M-01 Task completion rate (scenario pass rate over the newest suite run)
# ---------------------------------------------------------------------------


def measure_m01(runs_dir: Path, history_file: Path | None = None) -> dict[str, Any]:
    """Task completion rate from the newest recorded suite run's cells.

    Value = passed scenarios / (passed + failed) over every populated cell of
    the newest ``run_type="suite"`` ledger entry.  ``unconfigured`` scenarios
    are env-gated (never attempted), so they are reported separately and
    excluded from the denominator — they are neither completed nor failed.
    """
    spec = SPEC[0]
    source = f"{_history_path(runs_dir, history_file).name} (newest suite run)"
    ledger = _load_json(_history_path(runs_dir, history_file))
    if not isinstance(ledger, dict) or not isinstance(ledger.get("runs"), list):
        return _unmeasured(spec, "no category-pyramid ledger found", source=source)
    suite_runs = [
        r
        for r in ledger["runs"]
        if isinstance(r, dict) and str(r.get("run_type", "suite")) == "suite"
    ]
    if not suite_runs:
        return _unmeasured(spec, "no suite run recorded in ledger", source=source)
    latest = suite_runs[-1]
    cells = latest.get("cells")
    if not isinstance(cells, dict) or not cells:
        return _unmeasured(spec, "newest suite run has no cells", source=source)

    passed = failed = unconfigured = 0
    per_cell: list[dict[str, Any]] = []
    for key, cell in sorted(cells.items()):
        if not isinstance(cell, dict):
            continue
        p = int(cell.get("passed", 0) or 0)
        f = int(cell.get("failed", 0) or 0)
        u = int(cell.get("unconfigured", 0) or 0)
        passed += p
        failed += f
        unconfigured += u
        denom = p + f
        per_cell.append(
            {
                "cell": key,
                "passed": p,
                "failed": f,
                "unconfigured": u,
                "rate": (p / denom) if denom else None,
            }
        )
    denom = passed + failed
    if denom == 0:
        return _unmeasured(
            spec,
            "newest suite run has no attempted (passed/failed) scenarios",
            source=source,
        )
    value = passed / denom
    detail = " | ".join(
        f"{c['cell']}={c['passed']}/{c['passed'] + c['failed']}"
        for c in per_cell
        if (c["passed"] + c["failed"])
    )
    return _measured(
        spec,
        value,
        source=source,
        sample=f"{passed}/{denom} scenarios (run {latest.get('run_id')})",
        detail=f"unconfigured excluded: {unconfigured}; cells: {detail}",
    )


def _history_path(runs_dir: Path, history_file: Path | None) -> Path:
    if history_file is not None:
        return history_file
    return runs_dir / DEFAULT_HISTORY_FILE


# ---------------------------------------------------------------------------
# M-02 Tool-call accuracy
# ---------------------------------------------------------------------------


def measure_m02(runs_dir: Path) -> dict[str, Any]:
    """Tool-call accuracy parsed from the newest ``TOOL_SELECTION_OK`` marker.

    The ``agent-tool-selection`` scenario emits
    ``TOOL_SELECTION_OK <hits>/<total> accuracy=<ratio>`` after selecting the
    correct live MCP tool + valid params for each canonical request.  Only the
    real emitted marker is read — the value is never recomputed or assumed.
    """
    spec = SPEC[1]
    source = "validation run trace: TOOL_SELECTION_OK marker"
    for run in _run_dirs(runs_dir):
        payload = _load_json(run / "scenarios.json")
        if not isinstance(payload, dict):
            continue
        for scenario in payload.get("scenarios", []) or []:
            if not isinstance(scenario, dict):
                continue
            for step in scenario.get("steps", []) or []:
                if not isinstance(step, dict):
                    continue
                match = _TOKEN_SELECTION_RE.search(_step_stdout(step))
                if match:
                    hits, total, accuracy = match.groups()
                    return _measured(
                        spec,
                        float(accuracy),
                        source=source,
                        sample=f"{hits}/{total} requests (run {run.name})",
                        detail=f"scenario={scenario.get('scenario')}",
                    )
    return _unmeasured(spec, "no TOOL_SELECTION_OK marker in any persisted run", source=source)


# ---------------------------------------------------------------------------
# M-03 Recovery success rate
# ---------------------------------------------------------------------------


def measure_m03(runs_dir: Path) -> dict[str, Any]:
    """Recovery success rate across persisted runs.

    Two real recovery mechanisms are counted as attempts:
    (a) a ``recover-*`` scenario that actually ran (``passed``/``failed``);
    (b) a step that executed a ``recovery`` block.  A recovery attempt succeeds
    when the scenario passed (a) or the step ``recovered`` flag is true (b).
    """
    spec = SPEC[2]
    source = "validation runs: recover-* scenarios + step recovery flags"
    attempts = 0
    successes = 0
    scenario_hits = 0
    step_hits = 0
    for run in _run_dirs(runs_dir):
        payload = _load_json(run / "scenarios.json")
        if not isinstance(payload, dict):
            continue
        for scenario in payload.get("scenarios", []) or []:
            if not isinstance(scenario, dict):
                continue
            name = str(scenario.get("scenario", ""))
            status = scenario.get("status")
            if name.startswith("recover-") and status in ("passed", "failed"):
                attempts += 1
                scenario_hits += 1
                if status == "passed":
                    successes += 1
            for step in scenario.get("steps", []) or []:
                if isinstance(step, dict) and "recovery" in step:
                    attempts += 1
                    step_hits += 1
                    if step.get("recovered"):
                        successes += 1
    if attempts == 0:
        return _unmeasured(
            spec,
            "no recovery attempt recorded (no recover-* scenario result and no step recovery flag)",
            source=source,
        )
    return _measured(
        spec,
        successes / attempts,
        source=source,
        sample=f"{successes}/{attempts} attempts (scenarios={scenario_hits}, steps={step_hits})",
    )


# ---------------------------------------------------------------------------
# M-04 Documentation freshness
# ---------------------------------------------------------------------------


def _default_doc_check() -> tuple[int, str]:
    """Run ``scripts/doc_inventory.py --check``; return ``(exit_code, output)``."""
    try:
        proc = subprocess.run(
            [sys.executable, str(DOC_INVENTORY), "--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=600,
        )
    except (OSError, subprocess.SubprocessError) as exc:  # pragma: no cover - env
        return 1, f"doc_inventory.py could not run: {exc}"
    return proc.returncode, f"{proc.stdout}\n{proc.stderr}"


def measure_m04(doc_check: Callable[[], tuple[int, str]] | None = None) -> dict[str, Any]:
    """Documentation freshness from the ``doc_inventory.py --check`` verdict.

    100% when the consistency checker exits 0; 0% when it fails.  This metric
    is always measured (the checker reads the live README/AGENTS/skill/tool/
    scenario/pytest surfaces).
    """
    spec = SPEC[3]
    runner = doc_check or _default_doc_check
    exit_code, output = runner()
    source = "scripts/doc_inventory.py --check"
    value = 1.0 if exit_code == 0 else 0.0
    tail = [ln.strip() for ln in output.splitlines() if ln.strip()]
    failures = [ln for ln in tail if ln.startswith("- ")]
    detail = "clean" if exit_code == 0 else f"{len(failures)} issue(s): " + "; ".join(failures[:3])
    return _measured(
        spec,
        value,
        source=source,
        sample=f"exit {exit_code}",
        detail=detail,
    )


# ---------------------------------------------------------------------------
# M-05 Token efficiency
# ---------------------------------------------------------------------------


def _token_tasks(payload: dict[str, Any]) -> list[int]:
    """Per-scenario token totals from ``llm_meta.tokens`` in a run payload."""
    tasks: list[int] = []
    for scenario in payload.get("scenarios", []) or []:
        if not isinstance(scenario, dict):
            continue
        total = 0
        found = False
        for step in scenario.get("steps", []) or []:
            if not isinstance(step, dict):
                continue
            meta = step.get("llm_meta")
            if not isinstance(meta, dict):
                continue
            tokens = meta.get("tokens")
            if not isinstance(tokens, dict):
                continue
            count = tokens.get("total_tokens")
            if isinstance(count, (int, float)) and count > 0:
                total += int(count)
                found = True
        if found:
            tasks.append(total)
    return tasks


def deterministic_token_count(text: str) -> int:
    """Dependency-free deterministic token count (word runs + punctuation units)."""
    return len(_DETERMINISTIC_TOKEN_RE.findall(text))


class _BenchKB:
    """Minimal KB facade for the M-05 benchmark: returns the pinned entries."""

    def __init__(self, entries: list[dict[str, Any]]) -> None:
        self._entries = entries

    def list_entries(
        self, domain: Any = None, date_from: Any = None, limit: int = 200, **kw: Any
    ) -> list[dict[str, Any]]:
        return list(self._entries)

    def list_kb_tier(self, *args: Any, **kw: Any) -> list[Any]:
        return []

    def update_entry_metadata(self, *args: Any, **kw: Any) -> None:
        return None

    def get_entry_by_source_url(self, *args: Any, **kw: Any) -> None:
        return None


def _bench_entries() -> list[dict[str, Any]]:
    now = datetime.datetime.now(datetime.timezone.utc)
    collected = (now - datetime.timedelta(days=2)).isoformat()
    return [
        {
            "entry_id": f"ax-bench-{i}",
            "title": title,
            "language": "en",
            "domain": _BENCH_DOMAIN,
            "tier": "01-Raw",
            "source_url": f"https://example.com/ax-bench-{i}",
            "source_type": "api",
            "source_platform": "pubmed",
            "collected_at": collected,
            "summary": f"{title}. Relevant content for the briefing.",
            "tags": '["IVF"]',
            "quality_tier": 1,
            "relevance_score": 92.0,
            "dedup_status": "unique",
            "file_path": "",
        }
        for i, title in enumerate(_BENCH_ENTRY_TITLES)
    ]


def deterministic_product_tokens() -> list[int]:
    """Per-product token counts of real generated product text (keyless).

    Renders ``_BENCH_PRODUCTS`` through the real ``generate_digest`` output
    pipeline with the KB facade and the LLM synthesis seam pinned to
    ``_BENCH_SYNTHESIS``, plus the agent-notification hook disabled (no network,
    no background outbox thread).  The rendered text is byte-stable, so the
    returned counts are reproducible on any machine with no API key.
    """
    from unittest.mock import patch

    from autoinfo.output import PRODUCT_TEMPLATES, generate_digest

    templates = {row["name"]: row["template"] for row in PRODUCT_TEMPLATES}

    def _render(name: str) -> str:
        return str(
            generate_digest(
                domain=_BENCH_DOMAIN,
                period="weekly",
                format="markdown",
                product_template=templates[name],
            )
        )

    with (
        patch("autoinfo.output.KBStore", return_value=_BenchKB(_bench_entries())),
        patch("autoinfo.output._call_llm_for_digest", return_value=_BENCH_SYNTHESIS),
        patch("autoinfo.output._fire_agent_notification", lambda *a, **kw: None),
    ):
        return [deterministic_token_count(_render(name)) for name in _BENCH_PRODUCTS]


def _llm_tokens_per_task(runs_dir: Path) -> tuple[float, int, str] | None:
    """Newest run's mean ``llm_meta.tokens`` per LLM task, when present."""
    found = _newest_run_with(runs_dir, lambda payload: bool(_token_tasks(payload)))
    if found is None:
        return None
    run, payload = found
    tasks = _token_tasks(payload)
    return sum(tasks) / len(tasks), len(tasks), run.name


def measure_m05(runs_dir: Path, baseline_file: Path | None = None) -> dict[str, Any]:
    """Token efficiency vs a pinned baseline.

    Primary (gated, keyless) channel: the deterministic token count of real
    generated product text (``deterministic_product_tokens``).  Additional
    channel (when present): mean ``llm_meta.tokens`` per LLM task in the newest
    trace, gated only when the pinned baseline carries an ``llm_tokens_per_task``
    reference (a keyless CI baseline does not).  Value = the worst regression
    across the available channels; a benchmark that cannot render, or a missing
    baseline, means ``UNMEASURED`` — never a faked pass.
    """
    spec = SPEC[4]
    baseline_path = baseline_file or DEFAULT_TOKEN_BASELINE
    source = (
        f"deterministic product-text tokens ({len(_BENCH_PRODUCTS)} products, "
        f"real output pipeline) vs {baseline_path.name}"
    )
    try:
        tokens = deterministic_product_tokens()
    except Exception as exc:  # benchmark failure must never masquerade as a pass
        return _unmeasured(spec, f"deterministic product benchmark failed: {exc}", source=source)
    if not tokens:
        return _unmeasured(spec, "deterministic product benchmark produced no text", source=source)
    current = sum(tokens) / len(tokens)

    baseline_data = _load_json(baseline_path)
    baseline = None
    llm_baseline = None
    if isinstance(baseline_data, dict):
        raw = baseline_data.get("baseline_tokens_per_task")
        baseline = float(raw) if isinstance(raw, (int, float)) and raw > 0 else None
        raw_llm = baseline_data.get("llm_tokens_per_task")
        llm_baseline = float(raw_llm) if isinstance(raw_llm, (int, float)) and raw_llm > 0 else None
    if baseline is None:
        return _unmeasured(
            spec,
            f"no positive baseline_tokens_per_task in {baseline_path.name}",
            source=source,
            sample=f"{len(tokens)} products, current {current:.0f} tokens/product",
        )

    regressions = [(current - baseline) / baseline]
    parts = [f"deterministic: current {current:.0f} vs baseline {baseline:.0f} tokens/product"]
    llm = _llm_tokens_per_task(runs_dir)
    if llm is not None:
        llm_mean, llm_n, llm_run = llm
        parts.append(
            f"llm_meta: {llm_mean:.0f} tokens/task over {llm_n} LLM task(s) (run {llm_run})"
        )
        if llm_baseline is not None:
            regressions.append((llm_mean - llm_baseline) / llm_baseline)
            parts.append(f"llm baseline {llm_baseline:.0f} tokens/task")
        else:
            parts.append("llm channel reported, not pinned in baseline")
    return _measured(
        spec,
        max(regressions),
        source=source,
        sample=f"{len(tokens)} products (mean {current:.0f} tokens/product)",
        detail="; ".join(parts),
    )


def update_token_baseline(runs_dir: Path, baseline_file: Path | None = None) -> Path | None:
    """Pin the live benchmark (+ optional llm trace mean) as the baseline.

    Returns the written path, or ``None`` when the benchmark cannot render.
    """
    try:
        tokens = deterministic_product_tokens()
    except Exception:
        return None
    if not tokens:
        return None
    baseline_path = baseline_file or DEFAULT_TOKEN_BASELINE
    payload: dict[str, Any] = {
        "version": 2,
        "signal": "deterministic_product_text_tokens_per_task",
        "baseline_tokens_per_task": round(sum(tokens) / len(tokens), 2),
        "sample_tasks": len(tokens),
        "products": list(_BENCH_PRODUCTS),
        "tokenizer": "word+punct regex (deterministic, keyless)",
        "llm_tokens_per_task": None,
        "captured_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    llm = _llm_tokens_per_task(runs_dir)
    if llm is not None:
        llm_mean, llm_n, llm_run = llm
        payload["llm_tokens_per_task"] = round(llm_mean, 2)
        payload["llm_sample_tasks"] = llm_n
        payload["llm_source_run"] = llm_run
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return baseline_path


# ---------------------------------------------------------------------------
# M-06 Error recovery time
# ---------------------------------------------------------------------------


def measure_m06(runs_dir: Path) -> dict[str, Any]:
    """Worst observed failure→actionable-envelope latency across persisted runs.

    A step counts when its envelope is ``success: false`` with an actionable
    ``error`` (``actionable: true``) and it carries a ``duration``.  The value
    is the maximum such duration — the worst real recovery round-trip an agent
    had to wait for an actionable error.
    """
    spec = SPEC[5]
    source = "validation run traces: failed steps with actionable error envelope"
    samples: list[tuple[float, str, str, str]] = []
    for run in _run_dirs(runs_dir):
        payload = _load_json(run / "scenarios.json")
        if not isinstance(payload, dict):
            continue
        for scenario in payload.get("scenarios", []) or []:
            if not isinstance(scenario, dict):
                continue
            for step in scenario.get("steps", []) or []:
                if not isinstance(step, dict):
                    continue
                detail = step.get("detail")
                if not isinstance(detail, dict) or detail.get("success") is not False:
                    continue
                error = detail.get("error")
                if not isinstance(error, dict) or error.get("actionable") is not True:
                    continue
                duration = step.get("duration")
                if isinstance(duration, (int, float)):
                    samples.append(
                        (
                            float(duration),
                            run.name,
                            str(scenario.get("scenario")),
                            str(step.get("name")),
                        )
                    )
    if not samples:
        return _unmeasured(spec, "no actionable error envelope in any persisted run", source=source)
    duration, run_name, scenario_name, step_name = max(samples, key=lambda s: s[0])
    return _measured(
        spec,
        duration,
        source=source,
        sample=f"{len(samples)} envelopes (worst in run {run_name})",
        detail=f"{scenario_name}: {step_name}",
    )


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def collect_metrics(
    runs_dir: Path,
    *,
    history_file: Path | None = None,
    token_baseline: Path | None = None,
    doc_check: Callable[[], tuple[int, str]] | None = None,
) -> list[dict[str, Any]]:
    """Measure all six AX metrics against the given live sources."""
    return [
        measure_m01(runs_dir, history_file),
        measure_m02(runs_dir),
        measure_m03(runs_dir),
        measure_m04(doc_check),
        measure_m05(runs_dir, token_baseline),
        measure_m06(runs_dir),
    ]


def render_report(metrics: list[dict[str, Any]], runs_dir: Path) -> str:
    """Render the human-readable AX metrics report."""
    lines: list[str] = []
    lines.append("AX Metrics — agent-oriented quality gate (plan §6, Todo 21)")
    lines.append("=" * 96)
    lines.append(f"Generated : {datetime.datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"Runs dir  : {runs_dir}")
    lines.append("")
    header = (
        f"{'ID':<5} {'Metric':<24} {'Pillar/axis':<18} {'Target':<18} "
        f"{'Value':<16} {'Sample':<42} {'Verdict'}"
    )
    lines.append(header)
    lines.append("-" * 96)
    for m in metrics:
        lines.append(
            f"{m['id']:<5} {m['metric']:<24} {m['pillar'] + '/' + m['axis']:<18} "
            f"{m['target']:<18} {m['display']:<16} {m['sample']:<42} {m['verdict']}"
        )
    lines.append("-" * 96)
    measured = [m for m in metrics if m["verdict"] != "UNMEASURED"]
    breached = [m for m in metrics if m["verdict"] == "FAIL"]
    unmeasured = [m for m in metrics if m["verdict"] == "UNMEASURED"]
    lines.append(
        f"Gate: {len(measured)}/{len(metrics)} measured, "
        f"{len(breached)} breached, {len(unmeasured)} unmeasured"
    )
    if unmeasured:
        lines.append(
            "Unmeasured (data not yet captured — never counted as a pass): "
            + ", ".join(m["id"] for m in unmeasured)
        )
    lines.append("")
    lines.append("Detail:")
    for m in metrics:
        lines.append(f"  {m['id']} [{m['verdict']}] source={m['source']}")
        if m["detail"]:
            lines.append(f"        {m['detail']}")
    lines.append("")
    if breached:
        lines.append(
            "GATE FAILED — breached: "
            + ", ".join(f"{m['id']} ({m['display']} vs {m['target']})" for m in breached)
        )
    else:
        lines.append("GATE PASSED")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Deterministic evidence recording (--record)
# ---------------------------------------------------------------------------


async def _record_async(runs_dir: Path) -> Path:
    """Run the deterministic seed set and persist ONE ``suite`` run."""
    from autoinfo.mcp.server import call_tool
    from autoinfo.mcp.validation import run_scenario, save_scenario_results

    async def dispatch(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        texts = await call_tool(name, arguments)
        return json.loads(texts[0][0].text)

    results = [await run_scenario(name, dispatch=dispatch) for name in SEED_SCENARIOS]
    return save_scenario_results(
        results,
        runs_dir=runs_dir,
        run_type="suite",
        session_id=str(uuid.uuid4()),
    )


def record_deterministic_evidence(runs_dir: Path) -> Path:
    """Synchronously run + persist the deterministic AX evidence suite."""
    return asyncio.run(_record_async(runs_dir))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Measure and gate the six AX verification metrics (plan §6)."
    )
    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=DEFAULT_RUNS_DIR,
        help="Base directory holding validation runs + the history ledger.",
    )
    parser.add_argument(
        "--history-file",
        type=Path,
        default=None,
        help="Category-pyramid ledger (default <runs-dir>/category-pyramid-history.json).",
    )
    parser.add_argument(
        "--token-baseline",
        type=Path,
        default=None,
        help="Pinned token baseline (default scripts/ax_token_baseline.json).",
    )
    parser.add_argument(
        "--record",
        action="store_true",
        help=(
            "Run the deterministic LLM-free seed scenarios and persist them as one suite run first."
        ),
    )
    parser.add_argument(
        "--update-token-baseline",
        action="store_true",
        help=(
            "Pin the live deterministic product benchmark (and the llm_meta "
            "mean when present) as the baseline, then exit."
        ),
    )
    parser.add_argument(
        "--no-gate",
        action="store_true",
        help="Report only; never exit non-zero on a breach.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the machine-readable JSON report instead of the table.",
    )
    args = parser.parse_args(argv)

    runs_dir: Path = args.runs_dir
    if args.update_token_baseline:
        path = update_token_baseline(runs_dir, args.token_baseline)
        if path is None:
            print(
                "Deterministic product benchmark produced no text — baseline not written.",
                file=sys.stderr,
            )
            return 1
        print(f"Wrote token baseline {path}")
        return 0

    if args.record:
        run_dir = record_deterministic_evidence(runs_dir)
        print(f"Recorded deterministic AX evidence: {run_dir}")

    metrics = collect_metrics(
        runs_dir,
        history_file=args.history_file,
        token_baseline=args.token_baseline,
    )

    if args.json:
        print(json.dumps({"metrics": metrics}, indent=2, ensure_ascii=False))
    else:
        print(render_report(metrics, runs_dir))

    breached = [m for m in metrics if m["verdict"] == "FAIL"]
    if breached and not args.no_gate:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
