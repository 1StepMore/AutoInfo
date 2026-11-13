"""Governance-path CI gate (AutoInfo issue #727).

Port of the e2e-test-suite gate (suite#260 / suite#308), adapted to this
repository's CODEOWNERS layout: AutoInfo's CODEOWNERS is primarily a
review-routing file (it carries a bare ``*`` default-owner catch-all and
per-directory routing entries that must NOT become label gates). The
owner-gated surfaces therefore live in a dedicated, marker-delimited
section, and only the patterns inside that section are enforced.

The repository ruleset intentionally does NOT require code-owner review:
the owner and the automation share one token identity, so a governance PR
could never self-approve and would deadlock. Instead this gate blocks a PR
that touches an owner-gated surface unless the owner has applied the
``governance-approved`` label (applying a label needs write access, which
is equivalent to owner approval).

CODEOWNERS layout expected by this gate::

    # (review-routing entries above — not enforced by this gate)
    # governance-path-gate: begin
    /.agents/expectations/  @1StepMore
    /.agents/roles/         @1StepMore
    # governance-path-gate: end

The CODEOWNERS file itself is always protected (editing it would edit the
gate), regardless of the markers.

Usage::

    check_governance_paths.py --files - --labels governance-approved
    check_governance_paths.py --files /tmp/changed.txt --labels ''

Exit codes: 0 allowed / no protected change / no CODEOWNERS, 1 blocked.
"""

from __future__ import annotations

import argparse
import fnmatch
import sys
from pathlib import Path

DEFAULT_LABEL = "governance-approved"
DEFAULT_CODEOWNERS = ".github/CODEOWNERS"

BEGIN_MARK = "# governance-path-gate: begin"
END_MARK = "# governance-path-gate: end"

_GLOB_CHARS = "*?["


def parse_codeowners(path: Path) -> list[str]:
    """Return the owner-gated globs from the marker-delimited section.

    Lines outside the ``governance-path-gate`` section are review routing
    (including the bare ``*`` default-owner catch-all) and are ignored so
    that ordinary PRs stay label-free.
    """
    patterns: list[str] = []
    in_section = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line == BEGIN_MARK:
            in_section = True
            continue
        if line == END_MARK:
            in_section = False
            continue
        if not in_section or not line or line.startswith("#"):
            continue
        fields = line.split()
        if fields and fields[0] not in patterns:
            patterns.append(fields[0])
    return patterns


def _normalize(pattern: str) -> str:
    """Strip the repo-root marker; CODEOWNERS globs are root-relative."""
    return pattern[1:] if pattern.startswith("/") else pattern


def matches(path: str, pattern: str) -> bool:
    """Match a repo-relative path against one CODEOWNERS glob.

    Supports ``path/**`` prefixes, trailing-slash directory prefixes and
    glob-free prefixes (``docs/dev`` is treated as a directory too) while
    still matching an exact literal file name.
    """
    glob = _normalize(pattern)
    if not glob:
        return False
    if glob.endswith("/"):
        return fnmatch.fnmatchcase(path, glob + "**")
    if not any(ch in glob for ch in _GLOB_CHARS):
        return path == glob or fnmatch.fnmatchcase(path, glob + "/**")
    return fnmatch.fnmatchcase(path, glob)


def _codeowners_relpath(codeowners: Path) -> str | None:
    """Return *codeowners* relative to cwd when it lives inside the tree."""
    try:
        return codeowners.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return None


def is_self_protected(path: str, codeowners: Path, rel: str | None) -> bool:
    """The CODEOWNERS file itself changes the gate, so it is always gated."""
    normalized = path[2:] if path.startswith("./") else path
    if rel is not None and normalized == rel:
        return True
    try:
        return (Path.cwd() / path).resolve() == codeowners.resolve()
    except OSError:
        return False


def _read_changed_files(source: str) -> list[str]:
    if source == "-":
        text = sys.stdin.read()
    else:
        text = Path(source).read_text(encoding="utf-8")
    return [line.strip() for line in text.splitlines() if line.strip()]


def evaluate(
    changed_files: list[str],
    patterns: list[str],
    labels: set[str],
    label_name: str,
    codeowners: Path,
    codeowners_rel: str | None,
) -> tuple[int, list[str]]:
    """Return ``(exit_code, output_lines)`` for the gate decision."""
    out: list[str] = []
    protected: list[tuple[str, str]] = []
    for path in changed_files:
        matched = next((p for p in patterns if matches(path, p)), None)
        if matched is not None:
            protected.append((path, matched))
        elif is_self_protected(path, codeowners, codeowners_rel):
            protected.append((path, codeowners_rel or str(codeowners)))
    for path, pattern in protected:
        out.append(f"PROTECTED: {path} (matched {pattern})")

    if not protected:
        out.append("OK: no unprotected governance changes")
        return 0, out
    if label_name in labels:
        out.append(f"OK: {len(protected)} governance file(s) allowed by '{label_name}'")
        return 0, out
    out.append(
        f"FAIL: {len(protected)} governance path(s) changed without the "
        f"'{label_name}' label. Ask the owner to add it."
    )
    return 1, out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Block governance-path changes without an owner label."
    )
    parser.add_argument(
        "--files",
        default="-",
        help="Changed-file list (one per line); '-' reads stdin (default).",
    )
    parser.add_argument(
        "--labels",
        default="",
        help="Comma-separated PR labels (default: none).",
    )
    parser.add_argument(
        "--label-name",
        default=DEFAULT_LABEL,
        help=f"Required label (default: {DEFAULT_LABEL}).",
    )
    parser.add_argument(
        "--codeowners",
        default=DEFAULT_CODEOWNERS,
        help=f"CODEOWNERS file (default: {DEFAULT_CODEOWNERS}).",
    )
    args = parser.parse_args(argv)

    codeowners = Path(args.codeowners)
    if not codeowners.is_file():
        print("SKIP: no CODEOWNERS file")
        return 0

    labels = {label.strip() for label in args.labels.split(",") if label.strip()}
    changed = _read_changed_files(args.files)
    code, lines = evaluate(
        changed,
        parse_codeowners(codeowners),
        labels,
        args.label_name,
        codeowners,
        _codeowners_relpath(codeowners),
    )
    for line in lines:
        print(line)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
