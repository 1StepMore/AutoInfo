"""Default-ON whole-repo drift scan (T03, principle P3).

Every git-tracked ``*.md`` is scanned with the contract's fact patterns; a
line restating a derived fact with a different number is a violation unless
the line carries the ignore marker or the file is excluded (each exclusion in
the contract carries a written reason). Historical values are never edited —
they opt out per-line or per-file, keeping dated records honest.
"""

from __future__ import annotations

import fnmatch
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from autoinfo.gov.contract import Contract


@dataclass(frozen=True)
class ScanResult:
    violations: tuple[str, ...]
    files_scanned: int
    excluded_files: int


def tracked_markdown(root: Path) -> list[str]:
    """Git-tracked ``*.md`` paths (posix, unquoted) — the scan universe.

    ``core.quotepath=false`` keeps non-ASCII filenames raw so exclusion
    matching works on Chinese-named docs; ``-z`` is newline-safe.
    """
    proc = subprocess.run(
        ["git", "-c", "core.quotepath=false", "ls-files", "-z", "--", "*.md"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git ls-files failed (exit {proc.returncode}): {proc.stderr.strip()}")
    return sorted(f for f in proc.stdout.split("\0") if f)


def exclusion_reason(rel_posix: str, contract: Contract) -> str | None:
    """Return the written reason when a path is excluded, else None."""
    for exc in contract.excludes:
        if fnmatch.fnmatch(rel_posix, exc.path):
            return exc.reason
    return None


def _match_line(
    line: str,
    contract: Contract,
    expected: dict[str, int],
    violations: list[str],
    where: str,
) -> None:
    if contract.ignore_marker and contract.ignore_marker in line:
        return
    for fact in contract.facts.values():
        for match_spec in fact.matches:
            for match in match_spec.pattern.finditer(line):
                seen = [g for g in match.groups() if g is not None]
                for expect_path, raw in zip(match_spec.expects, seen, strict=False):
                    want = expected.get(expect_path)
                    if want is not None and int(raw) != want:
                        violations.append(f"{where}: {expect_path} {raw} != {want}")


def scan_markdown(contract: Contract, facts: dict[str, Any]) -> ScanResult:
    """Scan every tracked markdown file against the derived facts."""
    from autoinfo.gov.facts import flatten

    expected = flatten(facts)
    files = tracked_markdown(contract.root)
    violations: list[str] = []
    scanned = 0
    excluded = 0
    for rel in files:
        posix = rel.replace("\\", "/")
        if exclusion_reason(posix, contract) is not None:
            excluded += 1
            continue
        path = contract.root / rel
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue  # unreadable working copy: skip, never crash the scan
        scanned += 1
        for lineno, line in enumerate(text.splitlines(), 1):
            _match_line(line, contract, expected, violations, f"{posix}:{lineno}")
    return ScanResult(violations=tuple(violations), files_scanned=scanned, excluded_files=excluded)
