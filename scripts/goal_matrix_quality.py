#!/usr/bin/env python3
"""Goal checker for the P2 goal (docs/dev/goals.md).

矩阵覆盖率 100%，且每个格子产出的东西质量合格；质量结论必须来自真模型。
三条判据同时满足才 exit 0；口径比驱动器退出码更严，见 docstring 与 checks。

Exit codes: 0 = achieved, 1 = gap remains, 2 = usage/environment error.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "docs" / "dev" / "validation-reports" / "capability-27x3"
MATRIX_JSON = REPORT_DIR / "matrix.json"
DOMAINS = ("ai-commercial", "language-learning", "medical-research")
MEDIA_FORMATS = frozenset({"audio", "audiobook", "video"})
LLM_FED_FORMATS = frozenset({"markdown", "html", "json", "agent", "epub"})
QUALITY_VERDICT_DOC = REPORT_DIR / "quality-verdict-2026-11-20.md"
BATTERY_FRESH_DAYS = 7

_SCRIPTS = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "capability_matrix", _SCRIPTS / "capability_matrix.py"
)
assert _spec is not None and _spec.loader is not None
_cm = importlib.util.module_from_spec(_spec)
sys.modules["capability_matrix"] = _cm
_spec.loader.exec_module(_cm)
_combinations, _gated, _spec_products = _cm.load_spec(
    ROOT / "docs" / "dev" / "specs" / "end-user-matrix.yaml"
)

_BATTERY_TS = re.compile(r"l1-battery-(?P<domain>[a-z-]+)-(?P<date>\d{4}-\d{2}-\d{2})\.json$")


def _check_matrix(messages: list[str]) -> list[dict]:
    """Checks 1-3: full grid, all L3, keyed discipline. Returns rows for reuse."""
    data = json.loads(MATRIX_JSON.read_text(encoding="utf-8"))
    rows = data["rows"]
    expected = {(d, c.product, c.format) for d in DOMAINS for c in _combinations}
    recorded = {(r["domain"], r["product"], r["format"]) for r in rows}
    missing = sorted(f"{d}/{p}:{f}" for d, p, f in expected - recorded)
    if missing:
        messages.append(f"matrix missing {len(missing)} cell row(s): {', '.join(missing[:6])}…")
    pending = sorted(
        f"{r['domain']}/{r['product']}:{r['format']}" for r in rows if r.get("reached") == "pending"
    )
    if pending:
        messages.append(f"matrix has pending rows: {', '.join(pending[:6])}")
    non_l3 = sorted(
        f"{r['domain']}/{r['product']}:{r['format']}={r.get('reached')}"
        for r in rows
        if r.get("reached") != "L3"
    )
    if non_l3:
        messages.append(
            f"matrix has non-L3 rows (honest blocks do not count): {', '.join(non_l3[:6])}"
        )
    unkeyed = sorted(
        f"{r['domain']}/{r['product']}:{r['format']}"
        for r in rows
        if r.get("keyed") != "keyed" and r["format"] in LLM_FED_FORMATS
    )
    if unkeyed:
        messages.append(
            "LLM-fed products recorded unkeyed (KB-fallback L3 does not satisfy this goal): "
            + ", ".join(unkeyed[:6])
        )
    media_unkeyed = [r for r in rows if r.get("keyed") != "keyed" and r["format"] in MEDIA_FORMATS]
    if media_unkeyed:
        print(
            f"note: {len(media_unkeyed)} unkeyed media row(s) tolerated (structural acceptance; "
            "document in the quality verdict)"
        )
    return rows


def _check_l0(messages: list[str]) -> None:
    """Check 4: L0 quality gate over the three domain product dirs."""
    directories = [
        str(ROOT / "outputs" / "capability-matrix" / "ai-commercial"),
        str(ROOT / "outputs" / "capability-matrix" / "language-learning"),
        str(ROOT / "outputs" / "capability-matrix" / "medical-research"),
    ]
    result = subprocess.run(
        [sys.executable, str(_SCRIPTS / "quality_gate.py"), *directories],
        capture_output=True,
        text=True,
        shell=False,
    )
    if result.returncode != 0:
        tail = (result.stdout or result.stderr or "").strip().splitlines()[-2:]
        messages.append("L0 quality gate failed: " + " | ".join(tail))


def _check_l1(messages: list[str]) -> list[Path]:
    """Check 5: L1 battery reports — fresh, all-PASS, evidence-bearing, no mock."""
    battery_paths: list[Path] = []
    now = time.time()
    for domain in DOMAINS:
        matches = sorted(REPORT_DIR.glob(f"logs/l1-battery-{domain}-*.json"))
        if not matches:
            missing_note = f"no L1 battery report for {domain} under {REPORT_DIR / 'logs'}"
            messages.append(missing_note)
            continue
        latest = matches[-1]
        battery_paths.append(latest)
        if now - latest.stat().st_mtime > BATTERY_FRESH_DAYS * 86400:
            when = time.strftime("%Y-%m-%d", time.localtime(latest.stat().st_mtime))
            messages.append(f"L1 battery report for {domain} is stale (latest {when})")
            continue
        text = latest.read_text(encoding="utf-8")
        report = json.loads(text)
        summary = report.get("summary", {})
        worklist = len(report.get("worklist", []))
        verdicts = report.get("verdicts", [])
        if summary.get("l0_failed") or summary.get("flagged") or summary.get("escalated"):
            messages.append(f"L1 battery for {domain}: not all-PASS (summary={summary})")
            continue
        if worklist and not verdicts:
            messages.append(f"L1 battery for {domain}: worklist={worklist} but zero verdicts")
            continue
        for v in verdicts:
            if v.get("verdict") != "PASS":
                messages.append(f"L1 battery for {domain}: non-PASS verdict {v.get('blind_spot')}")
            elif not (v.get("note") or "").strip():
                messages.append(f"L1 battery for {domain}: PASS verdict without note/evidence")
        if "confidence=mock" in text:
            messages.append(f"L1 battery for {domain}: mock marker present (fake not allowed)")
    return battery_paths


def _check_evidence(messages: list[str], battery_paths: list[Path]) -> None:
    """Check 6: evidence tracked by git (no local-only evidence)."""
    required = [
        MATRIX_JSON,
        REPORT_DIR / "matrix.md",
        REPORT_DIR / "evidence-pack.md",
        QUALITY_VERDICT_DOC,
        REPORT_DIR / "logs" / "artifact-residue-cleanup-2026-11-20.md",
        REPORT_DIR / "logs" / "kb-purge-2026-11-20.md",
        *battery_paths,
    ]
    for path in required:
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        probe = subprocess.run(
            ["git", "ls-files", "--error-unmatch", rel],
            capture_output=True,
            text=True,
            shell=False,
            cwd=ROOT,
        )
        if probe.returncode != 0:
            messages.append(f"evidence not committed: {rel}")


def main() -> int:
    messages: list[str] = []
    if not MATRIX_JSON.is_file():
        print(f"ERROR: {MATRIX_JSON} not found (run scripts/capability_matrix.py first)")
        return 2
    _check_matrix(messages)
    _check_l0(messages)
    battery_paths = _check_l1(messages)
    _check_evidence(messages, battery_paths)
    if messages:
        for m in messages:
            print(f"GAP: {m}")
        print(f"goal_matrix_quality: NOT ACHIEVED ({len(messages)} gap(s))")
        return 1
    print(
        "goal_matrix_quality: ACHIEVED — matrix full grid, 0 missing, all L3 keyed-disciplined; "
        "L0 gate exit 0; L1 battery all-PASS (real model, no mock marker); evidence committed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
