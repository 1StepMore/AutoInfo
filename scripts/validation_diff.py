#!/usr/bin/env python3
"""Diff two validation runs to expose pass/fail regression trends (fixes #129 P0-3).

Compares the scenario statuses of two persisted runs and prints a human
readable regression summary. When run with no arguments it diffs the two most
recent runs from ``validation-runs/``.

Usage:
    python3 scripts/validation_diff.py [--base RUN_ID] [--head RUN_ID]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "validation-runs"


def _run_dirs() -> list[Path]:
    if not RUNS.is_dir():
        raise SystemExit(f"No validation-runs directory at {RUNS}; run scenarios with save_results first.")
    return sorted(
        (p for p in RUNS.iterdir() if p.is_dir() and (p / "scenarios.json").exists()),
        key=lambda p: p.name,
        reverse=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Diff two validation runs")
    parser.add_argument("--base", default="", help="Older run ID (default: second-newest)")
    parser.add_argument("--head", default="", help="Newer run ID (default: newest)")
    args = parser.parse_args()

    dirs = _run_dirs()
    if len(dirs) < 2:
        raise SystemExit(f"Need at least 2 runs to diff; found {len(dirs)}.")
    head = next((d for d in dirs if d.name == args.head), None) if args.head else dirs[0]
    base = next((d for d in dirs if d.name == args.base), None) if args.base else dirs[1]
    if head is None or base is None:
        raise SystemExit(f"Unknown run id. Available: {[d.name for d in dirs]}")

    sys.path.insert(0, str(ROOT / "src"))
    from autoinfo.mcp.validation import diff_scenario_runs

    diff = diff_scenario_runs(base, head)
    print(f"BASE {diff['base']} -> HEAD {diff['head']}")
    print(f"  head passed:  {diff['head_passed']}/{diff['head_total']}")
    print(f"  head failed:  {diff['head_failed']}")
    print(f"  new passes:   {diff['new_passes'] or '(none)'}")
    print(f"  new failures: {diff['new_failures'] or '(none)'}")
    print(f"  regressed:    {diff['regressed'] or '(none)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
