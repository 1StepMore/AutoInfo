#!/usr/bin/env python3
"""Deterministic acceptance-report generator (AC1-AC9).

Renders ``docs/dev/validation-reports/acceptance-<version>-<date>.md`` from real
artifacts instead of hand-authoring the verdict table — the hand-written table
already rotted once (a stale ``1.14.0`` version row survived ``1.14.1``). Every
mechanical row is derived from an artifact on disk and carries an evidence
pointer (artifact path + decisive value); a row with no pointer is a bug.

The three human-reserved rows — ``AC3-human``, ``AC5-director`` and the overall
verdict — must **never** carry a machine ``PASS``. This is enforced
structurally, not by convention:

- :data:`HUMAN_RESERVED` + :func:`_machine_row` refuse a human-reserved id.
- :func:`_human_rows` is the only producer of reserved rows.
- :func:`render_report` asserts the overall verdict is the reserved token.

This module contains **no LLM**: it is purely deterministic (subprocess for
pytest / doc_inventory / git / CLI cost dashboard; JSON reads for artifacts).

Usage:
    python3 scripts/acceptance_report.py --version 1.14.1 --date 2026-09-30
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "validation-runs"
REPORTS = ROOT / "docs" / "dev" / "validation-reports"
SCRIPTS = ROOT / "scripts"
TESTS = ROOT / "tests"

# --- The verdict vocabulary is fixed by acceptance-framework.md §7.3 ---------

MACHINE_VERDICTS = frozenset({"PASS", "FAIL", "RISK", "unconfigured"})
HUMAN_RESERVED = frozenset({"AC3-human", "AC5-director", "overall"})
RESERVED_TOKEN = {
    "AC3-human": "PENDING HUMAN",
    "AC5-director": "PENDING HUMAN",
    "overall": "PENDING DIRECTOR SIGN-OFF",
}

_DIM_LABELS = {
    "AC1": "AC1 User model integrity",
    "AC2": "AC2 Data-layer integrity",
    "AC3-agent": "AC3 Dual orientation (agent)",
    "AC3-human": "AC3 Dual orientation (human)",
    "AC4": "AC4 Coverage commitment",
    "AC5-gates": "AC5 Quality (automated gates)",
    "AC5-director": "AC5 Quality (director review)",
    "AC6": "AC6 Commercial viability",
    "AC7": "AC7 Process & governance",
    "AC8": "AC8 Documentation health",
    "AC9": "AC9 Test & validation health",
    "overall": "**Overall verdict**",
}

# AC1 requires these three scenarios present and not failed.
_AC1_REQUIRED = ("enduser-journey", "regression-b1-content-preference", "error-boundary")
# The provenance scenario AC2 gates on.
_AC2_PROVENANCE = "promotion-provenance"

_CONVENTIONAL_RE = re.compile(
    r"^(?:feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(?:\([^)]+\))?!?:\s+\S"
)
_SIGNOFF_RE = re.compile(r"(?m)^Signed-off-by:\s+.+<[^>]+>\s*$")
_COLLECTED_RE = re.compile(r"(\d+)\s+tests?\s+collected")
_FORMS_READ_RE = re.compile(r"forms read: 0/(\d+)")


@dataclasses.dataclass(frozen=True)
class DimensionRow:
    """One row of the §10 per-dimension verdict table."""

    dim_id: str
    verdict: str
    blockers: str = ""
    evidence: str = ""
    notes: str = ""


@dataclasses.dataclass(frozen=True)
class AcceptanceInputs:
    """Everything :func:`compute_dimensions` grades, already gathered."""

    run_id: str
    scenarios: dict[str, Any]
    coverage: dict[str, Any] | None
    delivery: dict[str, Any]
    pytest_kb_rc: int | None
    pytest_collected: int | None
    bug_test_count: int
    doc_inventory_rc: int | None
    cost_dashboard: dict[str, Any] | None
    pr_range: str | None = None
    commit_violations: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# The anti-fabrication guard
# ---------------------------------------------------------------------------


def _machine_row(
    dim_id: str,
    verdict: str,
    *,
    evidence: str,
    notes: str = "",
    blockers: str = "",
) -> DimensionRow:
    """Build a machine-derived row.

    Refuses a human-reserved ``dim_id`` and any verdict outside the fixed
    vocabulary; refuses an empty evidence pointer.
    """
    assert dim_id not in HUMAN_RESERVED, f"{dim_id} is human-reserved"
    assert verdict in MACHINE_VERDICTS, verdict
    assert evidence.strip(), f"{dim_id} must carry an evidence pointer"
    return DimensionRow(
        dim_id=dim_id, verdict=verdict, blockers=blockers, evidence=evidence, notes=notes
    )


def _human_rows(forms_total: int) -> list[DimensionRow]:
    """The ONLY producer of reserved rows; accepts no computed verdict.

    *forms_total* is the count of PROCESSED product forms (the ``M`` in the
    ``forms read: 0/M`` counter) — never a verdict.
    """
    assert forms_total >= 0, forms_total
    return [
        DimensionRow(
            dim_id="AC3-human",
            verdict=RESERVED_TOKEN["AC3-human"],
            evidence="human review required — acceptance-framework.md §0.4 / §3.3",
            notes="Requires a human reviewer. Not self-certified.",
        ),
        DimensionRow(
            dim_id="AC5-director",
            verdict=RESERVED_TOKEN["AC5-director"],
            evidence="director sampling review — acceptance-framework.md §5.2",
            notes=f"forms read: 0/{forms_total}; the four-concern table below is (pending)",
        ),
        DimensionRow(
            dim_id="overall",
            verdict=RESERVED_TOKEN["overall"],
            evidence="director sign-off — acceptance-framework.md §7.5",
            notes=(
                "The acceptance lens is human-first; agent evidence alone is never "
                "sufficient. Requires a named director signature."
            ),
        ),
    ]


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _rel(path: Path) -> str:
    """Repo-relative POSIX path when possible, else the absolute string."""
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def _run_label(inp: AcceptanceInputs) -> str:
    return inp.scenarios.get("_path") or f"validation-runs/{inp.run_id}/scenarios.json"


def _status_index(inp: AcceptanceInputs) -> dict[str, str]:
    return {
        str(s.get("scenario")): str(s.get("status", "unknown"))
        for s in inp.scenarios.get("scenarios", [])
    }


def _manifest_files(inp: AcceptanceInputs, kind: str) -> list[dict[str, Any]]:
    manifest = inp.delivery.get("manifest") or {}
    return [f for f in manifest.get("files", []) if f.get("kind") == kind]


def _processed_files(inp: AcceptanceInputs) -> list[dict[str, Any]]:
    return _manifest_files(inp, "PROCESSED")


def _fmt_rc(rc: int | None) -> str:
    return "not-run" if rc is None else str(rc)


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


# ---------------------------------------------------------------------------
# Per-dimension producers
# ---------------------------------------------------------------------------


def _ac1_row(inp: AcceptanceInputs) -> DimensionRow:
    idx = _status_index(inp)
    states = {name: idx.get(name, "MISSING") for name in _AC1_REQUIRED}
    evidence = f"{_run_label(inp)}: " + ", ".join(f"{n}={states[n]}" for n in _AC1_REQUIRED)
    failed = [n for n in _AC1_REQUIRED if states[n] == "failed"]
    missing = [n for n in _AC1_REQUIRED if states[n] == "MISSING"]
    unconf = [n for n in _AC1_REQUIRED if states[n] == "unconfigured"]
    if failed:
        return _machine_row("AC1", "FAIL", evidence=evidence, notes=f"failed: {', '.join(failed)}")
    if missing:
        note = f"missing: {', '.join(missing)}"
        return _machine_row("AC1", "RISK", evidence=evidence, notes=note)
    if unconf:
        return _machine_row(
            "AC1",
            "RISK",
            evidence=evidence,
            notes=f"unconfigured (never a pass): {', '.join(unconf)}",
        )
    return _machine_row("AC1", "PASS", evidence=evidence)


def _ac2_row(inp: AcceptanceInputs) -> DimensionRow:
    idx = _status_index(inp)
    prov = idx.get(_AC2_PROVENANCE, "MISSING")
    raw = _manifest_files(inp, "RAW")
    manifest = inp.delivery.get("manifest_path") or "manifest.json"
    evidence = (
        f"python3 -m pytest tests/kb: rc={_fmt_rc(inp.pytest_kb_rc)}; "
        f"{_run_label(inp)}: {_AC2_PROVENANCE}={prov}; {manifest}: RAW files={len(raw)}"
    )
    if inp.pytest_kb_rc is None:
        return _machine_row("AC2", "unconfigured", evidence=evidence, notes="tests/kb did not run")
    if inp.pytest_kb_rc != 0:
        return _machine_row(
            "AC2", "FAIL", evidence=evidence, notes=f"tests/kb rc={inp.pytest_kb_rc}"
        )
    if prov == "failed":
        return _machine_row("AC2", "FAIL", evidence=evidence, notes="provenance scenario failed")
    if prov == "MISSING":
        return _machine_row(
            "AC2", "RISK", evidence=evidence, notes=f"{_AC2_PROVENANCE} scenario absent"
        )
    if not raw:
        return _machine_row("AC2", "FAIL", evidence=evidence, notes="no RAW manifest file")
    return _machine_row("AC2", "PASS", evidence=evidence)


def _ac3_agent_row(inp: AcceptanceInputs) -> DimensionRow:
    cov = inp.coverage
    if cov is None:
        return _machine_row(
            "AC3-agent",
            "unconfigured",
            evidence="validation-runs/coverage/: no coverage json present",
            notes="run scripts/coverage_audit.py",
        )
    missing = cov.get("missing_tools", [])
    path = cov.get("_path", "validation-runs/coverage/coverage-<newest>.json")
    evidence = f"{path}: missing_tools={missing}"
    if missing:
        return _machine_row(
            "AC3-agent", "FAIL", evidence=evidence, notes=f"{len(missing)} uncovered tool(s)"
        )
    return _machine_row("AC3-agent", "PASS", evidence=evidence)


def _ac4_row(inp: AcceptanceInputs) -> DimensionRow:
    gaps = inp.delivery.get("coverage_gaps")
    path = inp.delivery.get("gaps_path") or "04-MATRIX/coverage-gaps.json"
    if gaps is None:
        return _machine_row(
            "AC4",
            "unconfigured",
            evidence=f"{path}: absent",
            notes="run scripts/validation_delivery.py to build 04-MATRIX",
        )
    summary = gaps.get("summary", {})
    gap = int(summary.get("gap", 0) or 0)
    unconf = int(summary.get("unconfigured", 0) or 0)
    evidence = f"{path}: summary.gap={gap}, summary.unconfigured={unconf}"
    if gap:
        return _machine_row("AC4", "FAIL", evidence=evidence, notes=f"unclassified gaps: {gap}")
    return _machine_row(
        "AC4",
        "PASS",
        evidence=evidence,
        notes=f"unclassified: {gap}; unconfigured={unconf} (never a pass)",
    )


def _ac5_gates_row(inp: AcceptanceInputs) -> DimensionRow:
    processed = _processed_files(inp)
    manifest = inp.delivery.get("manifest_path") or "manifest.json"
    if not processed:
        return _machine_row(
            "AC5-gates",
            "unconfigured",
            evidence=f"{manifest}: PROCESSED=0",
            notes="no PROCESSED product delivered this run",
        )
    bad = [
        e
        for e in processed
        if e.get("quality") != "PASS"
        or ((e.get("gates") or {}).get("authenticity") or {}).get("authenticity") != "pass"
    ]
    evidence = f"{manifest}: PROCESSED={len(processed)}, failing={len(bad)}"
    if bad:
        names = ", ".join(str(e.get("file")) for e in bad)
        return _machine_row("AC5-gates", "FAIL", evidence=evidence, notes=f"failed: {names}")
    return _machine_row("AC5-gates", "PASS", evidence=evidence)


def _ac6_row(inp: AcceptanceInputs) -> DimensionRow:
    cmd = "python3 -m autoinfo.cli cost dashboard --json"
    if inp.cost_dashboard is None:
        return _machine_row(
            "AC6",
            "unconfigured",
            evidence=f"{cmd}: unavailable (rc!=0 or empty summary)",
            notes="never a pass",
        )
    keys = sorted((inp.cost_dashboard.get("summary") or {}).keys())
    return _machine_row("AC6", "PASS", evidence=f"{cmd}: rc=0, summary keys={keys}")


def _ac7_row(inp: AcceptanceInputs) -> DimensionRow:
    if not inp.pr_range:
        return _machine_row(
            "AC7",
            "unconfigured",
            evidence="no --pr-range supplied; acceptance-framework.md §7.2",
            notes="never PASS without a PR range",
        )
    evidence = f"git log {inp.pr_range}: {len(inp.commit_violations)} violating commit(s)"
    if inp.commit_violations:
        return _machine_row(
            "AC7", "FAIL", evidence=evidence, notes="; ".join(inp.commit_violations[:3])
        )
    return _machine_row("AC7", "PASS", evidence=evidence)


def _ac8_row(inp: AcceptanceInputs) -> DimensionRow:
    cmd = "python3 scripts/doc_inventory.py --check"
    if inp.doc_inventory_rc is None:
        return _machine_row("AC8", "unconfigured", evidence=f"{cmd}: did not run")
    evidence = f"{cmd}: rc={inp.doc_inventory_rc}"
    if inp.doc_inventory_rc != 0:
        return _machine_row("AC8", "FAIL", evidence=evidence)
    return _machine_row("AC8", "PASS", evidence=evidence)


def _ac9_row(inp: AcceptanceInputs) -> DimensionRow:
    reg = [
        s
        for s in inp.scenarios.get("scenarios", [])
        if s.get("regression") and s.get("status") == "failed"
    ]
    collected = "not-run" if inp.pytest_collected is None else str(inp.pytest_collected)
    evidence = (
        f"python3 -m pytest --collect-only -q: {collected} tests; "
        f"tests/test_bug_* files={inp.bug_test_count}; "
        f"{_run_label(inp)}: regression failures={len(reg)}"
    )
    if inp.bug_test_count > 0:
        return _machine_row(
            "AC9",
            "FAIL",
            evidence=evidence,
            notes=f"{inp.bug_test_count} bug-named test file(s)",
        )
    if inp.pytest_collected is None:
        return _machine_row("AC9", "unconfigured", evidence=evidence, notes="pytest collect failed")
    if reg:
        names = ", ".join(str(s.get("scenario")) for s in reg)
        return _machine_row("AC9", "RISK", evidence=evidence, notes=f"regression failures: {names}")
    return _machine_row("AC9", "PASS", evidence=evidence)


def compute_dimensions(inp: AcceptanceInputs) -> list[DimensionRow]:
    """Grade AC1-AC9 into the §10 row order, with human rows reserved."""
    forms_total = len(_processed_files(inp))
    human = {r.dim_id: r for r in _human_rows(forms_total)}
    return [
        _ac1_row(inp),
        _ac2_row(inp),
        _ac3_agent_row(inp),
        human["AC3-human"],
        _ac4_row(inp),
        _ac5_gates_row(inp),
        human["AC5-director"],
        _ac6_row(inp),
        _ac7_row(inp),
        _ac8_row(inp),
        _ac9_row(inp),
        human["overall"],
    ]


# ---------------------------------------------------------------------------
# Report rendering (§10 skeleton)
# ---------------------------------------------------------------------------


def _executive_summary(rows: list[DimensionRow]) -> list[str]:
    machine = [r for r in rows if r.dim_id not in HUMAN_RESERVED]
    counts: dict[str, int] = {}
    for row in machine:
        counts[row.verdict] = counts.get(row.verdict, 0) + 1
    failed = [r.dim_id for r in machine if r.verdict == "FAIL"]
    risk = [r.dim_id for r in machine if r.verdict == "RISK"]
    unconf = [r.dim_id for r in machine if r.verdict == "unconfigured"]
    out = [
        f"Of {len(machine)} machine-derived dimensions: "
        f"{counts.get('PASS', 0)} PASS, {counts.get('FAIL', 0)} FAIL, "
        f"{counts.get('RISK', 0)} RISK, {counts.get('unconfigured', 0)} unconfigured."
    ]
    if failed:
        out.append(f"Blocking FAIL: {', '.join(failed)}.")
    if unconf:
        out.append(f"Unconfigured (never a pass): {', '.join(unconf)}.")
    if risk:
        out.append(f"RISK (partial/indirect evidence): {', '.join(risk)}.")
    out.append(
        "The AC3-human and AC5-director rows and the overall verdict are human-reserved; "
        "they remain PENDING and block sign-off until a named director records a verdict "
        "(acceptance-framework.md §0.4, §0.6 P5, §3.3)."
    )
    return out


def _forms_total(rows: list[DimensionRow]) -> int:
    row = next((r for r in rows if r.dim_id == "AC5-director"), None)
    if row is None:
        return 0
    match = _FORMS_READ_RE.search(row.notes)
    return int(match.group(1)) if match else 0


def _director_review_section(forms_total: int) -> list[str]:
    return [
        "## AC5 Director sampling review (pending)",
        "",
        f"Forms read: **0/{forms_total}** — a human reviewer must read at least one real "
        "sample per PROCESSED product form and record a verdict against the four quality "
        "concerns (acceptance-framework.md §5.2).",
        "",
        "| Quality concern | RAW product lens | PROCESSED product lens | Director verdict |",
        "|-----------------|------------------|------------------------|------------------|",
        "| Completeness / accuracy | Coverage of the domain's sources; no key items missing "
        "| Factual accuracy: no errors, hallucination, or misattribution | (pending) |",
        "| Depth / freshness | Data is current per domain TTL "
        "| Analysis depth; timeliness of the briefing | (pending) |",
        "| Traceability / presentation | Source provenance visible "
        "| Presentation quality: renders cleanly, reads well for a human | (pending) |",
    ]


def _blocker_lines(rows: list[DimensionRow]) -> list[str]:
    out = [
        "| # | Dimension | Verdict | Finding | Evidence |",
        "|---|-----------|:---:|---------|----------|",
    ]
    count = 0
    for row in rows:
        if row.dim_id in HUMAN_RESERVED:
            count += 1
            out.append(
                f"| B-{count:03d} | {_DIM_LABELS.get(row.dim_id, row.dim_id)} | {row.verdict} "
                f"| Human-reserved — not self-certified | {_cell(row.evidence)} |"
            )
        elif row.verdict in ("FAIL", "RISK", "unconfigured"):
            count += 1
            finding = row.notes or row.verdict
            out.append(
                f"| B-{count:03d} | {_DIM_LABELS.get(row.dim_id, row.dim_id)} | {row.verdict} "
                f"| {_cell(finding)} | {_cell(row.evidence)} |"
            )
    if count == 0:
        out.append("| — | — | — | No machine blockers | — |")
    return out


def _chinese_summary(rows: list[DimensionRow]) -> list[str]:
    out = ["## 中文摘要（Director）", "", "| 维度 | 判定 | 说明 |", "|------|------|------|"]
    for row in rows:
        label = _DIM_LABELS.get(row.dim_id, row.dim_id)
        note = row.notes or row.evidence
        out.append(f"| {label} | {row.verdict} | {_cell(note)} |")
    machine = [r for r in rows if r.dim_id not in HUMAN_RESERVED]
    passes = sum(1 for r in machine if r.verdict == "PASS")
    out.append("")
    out.append(
        f"机器判定维度共 {len(machine)} 项，其中 PASS {passes} 项；"
        "三项人工保留判定（AC3-human、AC5-director、总体判定）始终为 PENDING，"
        "本报告不自证，须由具名 Director 签署。"
    )
    return out


def render_report(version: str, date: str, rows: list[DimensionRow]) -> str:
    """Render the §10 report; refuses any overall verdict but the reserved token."""
    by_id = {r.dim_id: r for r in rows}
    overall = by_id.get("overall")
    assert overall is not None, "report must contain an overall row"
    assert overall.verdict == RESERVED_TOKEN["overall"], (
        f"overall verdict must be {RESERVED_TOKEN['overall']!r}, got {overall.verdict!r}"
    )
    for row in rows:
        if row.dim_id in HUMAN_RESERVED:
            assert row.verdict not in MACHINE_VERDICTS, (
                f"{row.dim_id} is human-reserved and must not carry a machine verdict"
            )

    lines: list[str] = []
    lines.append(f"# Acceptance Run Report {version} ({date})")
    lines.append("")
    lines.append(
        "Machine-derived rows are produced by `scripts/acceptance_report.py` from real "
        "artifacts; the three human-reserved rows are emitted as non-PASS tokens and cannot "
        "be fabricated by this generator. Template: `docs/dev/acceptance-framework.md` §10."
    )
    lines.append("")
    lines.append(
        "Run by: B2 agent-as-tester (`scripts/acceptance_report.py`) | "
        "Reviewed by: B3 director (pending)"
    )
    lines.append("")

    lines.append("## Verdicts")
    lines.append("")
    for row in rows:
        lines.append(f"- {row.dim_id}: {row.verdict}")
    lines.append("")
    lines.append("> `unconfigured` is never a pass (acceptance-framework.md §7.3).")
    lines.append("")

    lines.append("## Per-dimension verdict table")
    lines.append("")
    lines.append("| Dimension | Verdict | Blockers | Evidence artifacts | Notes |")
    lines.append("|-----------|:---:|----------|--------------------|-------|")
    for row in rows:
        label = _DIM_LABELS.get(row.dim_id, row.dim_id)
        lines.append(
            f"| {label} | {row.verdict} | {_cell(row.blockers)} | "
            f"{_cell(row.evidence)} | {_cell(row.notes)} |"
        )
    lines.append("")

    lines.append("## Executive summary")
    lines.append("")
    lines.extend(_executive_summary(rows))
    lines.append("")

    lines.extend(_director_review_section(_forms_total(rows)))
    lines.append("")

    lines.append("## Blockers")
    lines.append("")
    lines.extend(_blocker_lines(rows))
    lines.append("")

    lines.append("## Director sign-off")
    lines.append("")
    lines.append(
        "This report is evidence-complete but **not self-certified**. The overall verdict "
        "and the two human-reserved rows require a human."
    )
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("|-------|-------|")
    lines.append("| Director | _(unsigned)_ |")
    lines.append("| Date | _(unsigned)_ |")
    lines.append("| Verdict | **PENDING DIRECTOR SIGN-OFF** |")
    lines.append("")

    lines.extend(_chinese_summary(rows))
    lines.append("")
    lines.append("Generated by `python3 scripts/acceptance_report.py`.")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Artifact loaders
# ---------------------------------------------------------------------------


def _latest_run(base: Path | None = None) -> str:
    base = base or RUNS
    pointer = base / "latest.txt"
    if pointer.exists():
        text = pointer.read_text(encoding="utf-8").strip()
        if text:
            return text
    raise SystemExit(f"No validation run pointer at {pointer}; pass --run explicitly.")


def load_run_scenarios(
    run_id: str | None = None, *, runs_dir: Path | None = None
) -> dict[str, Any]:
    """Load ``validation-runs/<run>/scenarios.json`` (newest when *run_id* is None)."""
    base = runs_dir or RUNS
    rid = run_id or _latest_run(base)
    path = base / rid / "scenarios.json"
    if not path.exists():
        raise FileNotFoundError(f"scenarios.json not found: {path}")
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    payload.setdefault("run_id", rid)
    payload["_path"] = _rel(path)
    return payload


def load_coverage(*, coverage_dir: Path | None = None) -> dict[str, Any] | None:
    """Load the newest ``validation-runs/coverage/coverage-*.json`` (or None)."""
    base = coverage_dir or (RUNS / "coverage")
    if not base.is_dir():
        return None
    candidates = sorted(base.glob("coverage-*.json"))
    if not candidates:
        return None
    path = candidates[-1]  # lexicographic order == chronological for the stamp format
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    payload["_path"] = _rel(path)
    return payload


def _default_delivery_dir() -> Path | None:
    base = ROOT / "validation-deliveries"
    if not base.is_dir():
        return None
    dirs = sorted((p for p in base.iterdir() if p.is_dir()), reverse=True)
    with_manifest = [p for p in dirs if (p / "manifest.json").is_file()]
    if with_manifest:
        return with_manifest[0]
    return dirs[0] if dirs else None


def load_delivery(delivery_dir: Path | None = None) -> dict[str, Any]:
    """Load a delivery package's manifest, coverage gaps, and QA gate index."""
    base = delivery_dir if delivery_dir is not None else _default_delivery_dir()
    result: dict[str, Any] = {
        "dir": _rel(base) if base is not None else "",
        "manifest": None,
        "manifest_path": "",
        "coverage_gaps": None,
        "gaps_path": "",
        "gate_reports": None,
        "gate_index_path": "",
    }
    if base is None or not base.is_dir():
        return result
    manifest_path = base / "manifest.json"
    if manifest_path.is_file():
        result["manifest"] = json.loads(manifest_path.read_text(encoding="utf-8"))
        result["manifest_path"] = _rel(manifest_path)
    gaps_path = base / "04-MATRIX" / "coverage-gaps.json"
    if gaps_path.is_file():
        result["coverage_gaps"] = json.loads(gaps_path.read_text(encoding="utf-8"))
        result["gaps_path"] = _rel(gaps_path)
    index_path = base / "01-QA-GATES" / "gate-reports-index.json"
    if index_path.is_file():
        result["gate_reports"] = json.loads(index_path.read_text(encoding="utf-8"))
        result["gate_index_path"] = _rel(index_path)
    return result


# ---------------------------------------------------------------------------
# Subprocess probes
# ---------------------------------------------------------------------------


def _parse_collected(text: str) -> int | None:
    match = _COLLECTED_RE.search(text)
    return int(match.group(1)) if match else None


def run_pytest(args: list[str], *, cwd: Path | None = None, timeout: int = 900) -> dict[str, Any]:
    """Run pytest with *args*; return ``{rc, stdout, stderr, collected}``."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *args],
        cwd=str(cwd) if cwd is not None else None,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return {
        "rc": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "collected": _parse_collected(proc.stdout),
    }


def _run_doc_inventory() -> int | None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "doc_inventory.py"), "--check"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=300,
    )
    return proc.returncode


def _load_cost_dashboard() -> dict[str, Any] | None:
    proc = subprocess.run(
        [sys.executable, "-m", "autoinfo.cli", "cost", "dashboard", "--json"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=300,
    )
    if proc.returncode != 0:
        return None
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or not data.get("summary"):
        return None
    return data


def _count_bug_tests(tests_dir: Path | None = None) -> int:
    base = tests_dir or TESTS
    return sum(1 for _ in base.rglob("test_bug_*.py"))


def _commit_violations(commits: list[tuple[str, str]]) -> list[str]:
    """Flag non-Conventional-Commits subjects and missing ``Signed-off-by`` trailers."""
    violations: list[str] = []
    for subject, body in commits:
        if not _CONVENTIONAL_RE.match(subject.strip()):
            violations.append(f"non-Conventional-Commit subject: {subject!r}")
        if not _SIGNOFF_RE.search(body or ""):
            violations.append(f"missing Signed-off-by trailer: {subject!r}")
    return violations


def _git_commit_violations(pr_range: str) -> list[str]:
    proc = subprocess.run(
        ["git", "log", "--format=%s%x1f%B%x1e", pr_range],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0:
        return [f"git log failed for {pr_range!r}: {proc.stderr.strip()}"]
    commits: list[tuple[str, str]] = []
    for record in proc.stdout.split("\x1e"):
        record = record.strip("\n")
        if not record.strip():
            continue
        parts = record.split("\x1f", 1)
        subject = parts[0].strip()
        body = parts[1] if len(parts) > 1 else ""
        commits.append((subject, body))
    return _commit_violations(commits)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _version_default() -> str:
    try:
        from autoinfo._version import __version__

        return __version__
    except Exception:  # noqa: BLE001 - report must degrade, never crash on import
        return "unreleased"


def _gather_inputs(args: argparse.Namespace) -> AcceptanceInputs:
    run_id = args.run or _latest_run()
    scenarios = load_run_scenarios(run_id)
    coverage = load_coverage()
    delivery_dir = Path(args.delivery_dir) if args.delivery_dir else None
    delivery = load_delivery(delivery_dir)
    kb = run_pytest(["tests/kb", "-q"])
    collect = run_pytest(["--collect-only", "-q"])
    violations = tuple(_git_commit_violations(args.pr_range)) if args.pr_range else ()
    return AcceptanceInputs(
        run_id=run_id,
        scenarios=scenarios,
        coverage=coverage,
        delivery=delivery,
        pytest_kb_rc=kb["rc"],
        pytest_collected=collect["collected"],
        bug_test_count=_count_bug_tests(),
        doc_inventory_rc=_run_doc_inventory(),
        cost_dashboard=_load_cost_dashboard(),
        pr_range=args.pr_range,
        commit_violations=violations,
    )


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the deterministic AC1-AC9 acceptance run report"
    )
    parser.add_argument("--version", default=_version_default(), help="Release version label")
    parser.add_argument(
        "--date",
        default=datetime.date.today().isoformat(),
        help="Report date (default: today, ISO)",
    )
    parser.add_argument(
        "--run", default="", help="Run ID (default: newest from validation-runs/latest.txt)"
    )
    parser.add_argument(
        "--delivery-dir", default="", help="Delivery package dir (default: newest with manifest)"
    )
    parser.add_argument(
        "--pr-range", default="", help="Git range for AC7 governance check (e.g. origin/main..HEAD)"
    )
    parser.add_argument(
        "--out", default="", help="Output path (default: validation-reports/acceptance-<v>-<d>.md)"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    inputs = _gather_inputs(args)
    rows = compute_dimensions(inputs)
    text = render_report(args.version, args.date, rows)
    out = Path(args.out) if args.out else REPORTS / f"acceptance-{args.version}-{args.date}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"REPORT: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
