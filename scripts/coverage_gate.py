"""Baseline-aware coverage gate for changed src/autoinfo modules.

Replaces the fixed ``fail-under=60`` check that previously ran
``coverage report --include=<changed modules> --fail-under=60``: that gate
measured the WHOLE changed module against a fixed 60% floor, so any PR
touching a legacy module whose fast-subset coverage is below 60% (e.g.
server.py at 53%) failed even for a one-line, fully-tested change.

New semantics — no-regression vs the merge-base (base SHA):

- For each changed ``src/autoinfo/*.py`` module, measure its coverage on
  the PR head AND on the base SHA (both from the fast subset).
- EXISTING module (present at base SHA): floor = base coverage minus a
  small tolerance (default 2pp, absorbs measurement noise / test-order
  variance between the two runs). A PR must not lower a module's coverage
  below what the base already achieves.
- NEW module (not present at base SHA): floor = threshold (default 60) —
  new code still has to ship with tests.
- RELOCATED module (base version was a near-empty stub, PR version is many
  times larger): per-module percentage is meaningless for code motion. The
  base percentage measures the stub, not the bodies that moved in. Such
  modules are judged by an AGGREGATE no-regression check over every changed
  module instead: total covered statements on the PR head must be >= total
  covered statements at the merge base. A pure move keeps the same covered
  statements (they are counted in the source module at base and in the
  destination module at head), so it passes; deleting covered code fails.

Exit 0 = pass, 1 = fail, 2 = usage/IO error.

Usage (from repo root, after the fast subset has run under pytest-cov on
both the PR head and the base SHA):

    python3 scripts/coverage_gate.py \
        --changed changed-files.txt \
        --pr-data .coverage \
        --base-data .coverage.base \
        --base-sha <merge-base-sha>
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple, Sequence

TOTAL_LINE_RE = re.compile(r"^TOTAL\s+(\d+)\s+(\d+)\s+(\d+)%")

# A module whose base version held at most this many statements is a stub
# (e.g. an extracted schema table). When its PR version is at least
# RELOCATION_RATIO times larger AND gained at least RELOCATION_MIN_GROWTH
# statements, the growth is code motion, not new code.
STUB_MAX_STATEMENTS = 20
RELOCATION_RATIO = 3
RELOCATION_MIN_GROWTH = 10


class ModuleCoverage(NamedTuple):
    """One module's TOTAL row: percentage plus the statement counts behind it."""

    pct: float
    statements: int
    missing: int

    @property
    def covered(self) -> int:
        return self.statements - self.missing


def parse_total_row(report_output: str) -> ModuleCoverage | None:
    """Parse the TOTAL row of a ``coverage report`` output."""
    for line in report_output.splitlines():
        m = TOTAL_LINE_RE.match(line.strip())
        if m:
            statements, missing, pct = (int(m.group(i)) for i in (1, 2, 3))
            return ModuleCoverage(float(pct), statements, missing)
    return None


def parse_total_pct(report_output: str) -> float | None:
    """Extract the TOTAL row percentage from a ``coverage report`` output."""
    row = parse_total_row(report_output)
    return row.pct if row is not None else None


def measure_module_detail(data_file: Path, module: str) -> ModuleCoverage | None:
    """Return the TOTAL row for *module* in *data_file*, or None if not executed.

    ``coverage report --include`` takes fnmatch patterns; try the
    git-relative path first and fall back to a ``*/``-prefixed pattern for
    runners where coverage stores absolute paths (mirrors the original
    workflow's INCLUDE_REL/INCLUDE_ABS retry).
    """
    for pattern in (module, f"*/{module}"):
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "coverage",
                "report",
                "--data-file",
                str(data_file),
                "--include",
                pattern,
                "--skip-empty",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            row = parse_total_row(proc.stdout)
            if row is not None:
                return row
        # "No data to report" (returncode 1/2) or no TOTAL row — try the
        # next pattern; if both miss, the module was never executed.
    return None


def measure_module_coverage(data_file: Path, module: str) -> float | None:
    """Return coverage % of *module* in *data_file*, or None if not executed."""
    row = measure_module_detail(data_file, module)
    return row.pct if row is not None else None


def is_relocated(base: ModuleCoverage | None, pr: ModuleCoverage | None) -> bool:
    """True when the module grew by code motion rather than by new code."""
    if base is None or pr is None:
        return False
    return (
        base.statements <= STUB_MAX_STATEMENTS
        and pr.statements >= base.statements * RELOCATION_RATIO
        and pr.statements - base.statements >= RELOCATION_MIN_GROWTH
    )


def module_exists_at(module: str, sha: str | None) -> bool:
    """Return True if *module* exists in the tree at *sha* (HEAD if None)."""
    if not sha:
        return True  # no base SHA given — treat as existing (conservative)
    proc = subprocess.run(
        ["git", "cat-file", "-e", f"{sha}:{module}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode == 0


def compute_floor(
    is_new: bool,
    base_pct: float | None,
    threshold: float,
    tolerance: float,
) -> float:
    """Per-module pass floor: base minus tolerance, or threshold for new modules."""
    if is_new:
        return threshold
    base = base_pct if base_pct is not None else 0.0
    return max(0.0, base - tolerance)


def gate(
    changed_modules: Sequence[str],
    pr_data: Path,
    base_data: Path,
    base_sha: str | None,
    threshold: float,
    tolerance: float,
) -> int:
    """Evaluate every changed module; return 0 (pass) or 1 (fail)."""
    failures: list[str] = []
    pr_covered_total = 0
    base_covered_total = 0
    relocated_modules: list[str] = []

    for module in sorted(changed_modules):
        pr = measure_module_detail(pr_data, module)
        is_new = not module_exists_at(module, base_sha)
        base = measure_module_detail(base_data, module) if not is_new else None

        pr_covered_total += pr.covered if pr is not None else 0
        base_covered_total += base.covered if base is not None else 0

        if is_relocated(base, pr):
            relocated_modules.append(module)
            assert base is not None and pr is not None
            print(
                f"  [RELOCATED] {module}: {base.statements} -> {pr.statements} "
                f"statements (base stub) — judged by the aggregate no-regression check"
            )
            continue

        floor = compute_floor(is_new, base.pct if base is not None else None, threshold, tolerance)
        pr_pct_val = pr.pct if pr is not None else 0.0
        status = "PASS" if pr_pct_val >= floor else "FAIL"
        new_marker = " (new module)" if is_new else ""
        base_note = f"base {base.pct:.1f}%" if base is not None else "base n/a"
        print(
            f"  [{status}] {module}: pr {pr_pct_val:.1f}% vs floor {floor:.1f}%"
            f"{new_marker} ({base_note})"
        )
        if pr_pct_val < floor:
            failures.append(
                f"{module}: pr {pr_pct_val:.1f}% < floor {floor:.1f}%{new_marker} ({base_note})"
            )

    if relocated_modules:
        status = "PASS" if pr_covered_total >= base_covered_total else "FAIL"
        print(
            f"  [{status}] aggregate covered statements: "
            f"pr {pr_covered_total} vs base {base_covered_total} "
            f"({len(relocated_modules)} relocated module(s))"
        )
        if pr_covered_total < base_covered_total:
            failures.append(
                "relocated code lost test coverage: covered statements "
                f"{pr_covered_total} < base {base_covered_total}"
            )

    if failures:
        print("COVERAGE GATE FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("COVERAGE GATE PASSED")
    return 0


def _read_changed_src_modules(changed_file: Path) -> list[str]:
    """Filter changed-files.txt to src/autoinfo/*.py modules (gate scope)."""
    if not changed_file.is_file():
        return []
    modules: list[str] = []
    for line in changed_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("src/autoinfo/") and line.endswith(".py"):
            modules.append(line)
    return modules


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--changed", required=True, type=Path)
    parser.add_argument("--pr-data", required=True, type=Path)
    parser.add_argument("--base-data", required=True, type=Path)
    parser.add_argument("--base-sha", default=None, help="merge-base SHA of the PR")
    parser.add_argument("--threshold", type=float, default=60.0)
    parser.add_argument("--tolerance", type=float, default=2.0)
    args = parser.parse_args(argv)

    modules = _read_changed_src_modules(args.changed)
    if not modules:
        print("No changed src/autoinfo modules - coverage gate skipped.")
        return 0
    if not args.pr_data.is_file():
        print(f"ERROR: PR coverage data {args.pr_data} not found", file=sys.stderr)
        return 2
    if not args.base_data.is_file():
        print(
            f"ERROR: base coverage data {args.base_data} not found — "
            "did the base-SHA fast subset run?",
            file=sys.stderr,
        )
        return 2

    print(
        f"Coverage gate on {len(modules)} changed module(s) "
        f"(threshold={args.threshold:.0f}%, tolerance={args.tolerance:.1f}pp)"
    )
    return gate(
        modules,
        args.pr_data,
        args.base_data,
        args.base_sha,
        args.threshold,
        args.tolerance,
    )


if __name__ == "__main__":
    sys.exit(main())
