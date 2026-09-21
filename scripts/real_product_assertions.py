#!/usr/bin/env python3
"""Deterministic, network-free real-product assertion scanner (issue #356).

Issue #356 (验证闭环 / closure verification): after a fix merges, a
real-product validation run must show the issue's flagged assertion cleared
before the issue is closed.  Until now there was no tool that ran *a chosen
assertion* over arbitrary real-product roots — the maintainer hand-scanned
``outputs/`` + ``demo-packages/`` (hundreds of files) with an ad-hoc Python
snippet each time.

This script is that missing tool.  It walks one or more product roots, runs the
formalized assertion set from :mod:`autoinfo.validation_matrix` (reused
verbatim — the assertion logic is never re-implemented here) over every
``*.md`` / ``*.html`` / ``*.txt`` file, and emits machine-readable + human
evidence for the close decision:

* ``--json-out`` → ``{schema_version, tool, generated_at, commit, issue, roots,
  assertions, files_scanned, totals, failures}`` (agent-consumable);
* ``--md-out``  → the same evidence rendered as a markdown close artifact.

Exit codes (usable directly as a close gate):

* ``0`` — no P0/P1 failure (the flagged assertion is cleared);
* ``1`` — at least one P0/P1 failure (keep the issue open, label
  ``needs-real-verification``);
* ``2`` — usage error (unknown assertion name, bad arguments).

Strictly deterministic and offline: no LLM, no network.  The opt-in network
link-reachability assertion (``SLOW_ASSERTION_FUNCS``) is never reachable from
here because the default set is ``validation_matrix.assertion_names`` (the fast
set only).

Usage (from repo root):

    python3 scripts/real_product_assertions.py \\
        --assertions _no_year_hallucination --issue 351

    python3 scripts/real_product_assertions.py \\
        --roots outputs,demo-packages --exclude '*/draft/*' \\
        --assertions _source_labels_specific \\
        --json-out /tmp/rp.json --md-out /tmp/rp.md
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from autoinfo.validation_matrix import (  # noqa: E402
    _current_commit,
    assertion_names,
    run_assertions,
)

SCHEMA_VERSION = 1
TOOL = "scripts/real_product_assertions.py"
DEFAULT_ROOTS = "outputs,demo-packages"
_SCAN_SUFFIXES = (".md", ".html", ".txt")

# Filename keyword -> product name, mirroring the established product-type
# inference in scripts/validation_delivery.py (order matters).  An unknown
# filename yields "" so product-conditional assertions pass informationally
# rather than false-firing on a mis-detected product.
_PRODUCT_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("enterprise-briefing", "enterprise-briefing"),
    ("premium-briefing", "premium-briefing"),
    ("magazine-digest", "magazine-digest"),
    ("presentation", "presentation"),
    ("tutorial", "tutorial"),
    ("magazine", "magazine"),
    ("digest", "digest"),
    ("column", "column"),
)

_SEVERITIES = ("P0", "P1", "P2")


@dataclass(frozen=True)
class Failure:
    """One failing assertion for one product file."""

    path: str
    assertion: str
    severity: str
    details: str

    def to_dict(self) -> dict[str, str]:
        return {
            "path": self.path,
            "assertion": self.assertion,
            "severity": self.severity,
            "details": self.details,
        }


def parse_csv(value: str) -> list[str]:
    """Split a comma-separated CLI value, dropping blanks."""
    return [item.strip() for item in value.split(",") if item.strip()]


def default_assertions() -> list[str]:
    """All fast assertions (``SLOW_ASSERTION_FUNCS`` are excluded by design)."""
    return list(assertion_names)


def _product_from_name(name: str) -> str:
    lowered = name.lower()
    for keyword, product in _PRODUCT_KEYWORDS:
        if keyword in lowered:
            return product
    return ""


def _domain_from_path(path: Path, root: Path) -> str:
    """First path segment below *root* (``<root>/<domain>/...``), else ""."""
    try:
        rel = path.relative_to(root)
    except ValueError:
        return ""
    parts = rel.parts
    return parts[0] if len(parts) >= 2 else ""


def _matches_exclude(path: Path, root: Path, patterns: Sequence[str]) -> bool:
    """True when *path* matches any exclude glob (full / root-relative / name)."""
    if not patterns:
        return False
    posix = path.as_posix()
    try:
        rel = path.relative_to(root).as_posix()
    except ValueError:
        rel = posix
    name = path.name
    return any(
        fnmatch.fnmatch(posix, pattern)
        or fnmatch.fnmatch(rel, pattern)
        or fnmatch.fnmatch(name, pattern)
        for pattern in patterns
    )


def _collect_files(roots: Sequence[str], excludes: Sequence[str]) -> list[tuple[Path, Path]]:
    """Deterministically collect ``(path, owning_root)`` for every product file.

    Missing roots are skipped.  Results are de-duplicated by resolved path
    (overlapping roots) and sorted by POSIX path so a scan is reproducible.
    """
    found: list[tuple[Path, Path]] = []
    for root_str in roots:
        root = Path(root_str)
        if not root.is_dir():
            continue
        for candidate in sorted(root.rglob("*")):
            if not candidate.is_file():
                continue
            if candidate.suffix.lower() not in _SCAN_SUFFIXES:
                continue
            if _matches_exclude(candidate, root, excludes):
                continue
            found.append((candidate, root))
    unique: list[tuple[Path, Path]] = []
    seen: set[Path] = set()
    for path, root in found:
        key = path.resolve()
        if key in seen:
            continue
        seen.add(key)
        unique.append((path, root))
    unique.sort(key=lambda item: item[0].as_posix())
    return unique


def scan(
    roots: Sequence[str],
    assertions: Sequence[str],
    *,
    excludes: Sequence[str] = (),
    issue: str = "",
) -> dict[str, Any]:
    """Run the selected assertions over every file under *roots*.

    Returns the evidence dict (the ``--json-out`` payload).  Unknown assertion
    names are silently ignored here — :func:`main` validates and reports them.
    """
    selected = list(assertions)
    files = _collect_files(roots, excludes)
    failures: list[Failure] = []
    for path, root in files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        results = run_assertions(
            text,
            domain=_domain_from_path(path, root),
            product=_product_from_name(path.name),
        )
        by_name = {result.name: result for result in results}
        for name in selected:
            result = by_name.get(name)
            if result is None or result.passed:
                continue
            failures.append(Failure(path.as_posix(), result.name, result.severity, result.details))
    failures.sort(key=lambda f: (f.path, f.assertion, f.severity, f.details))

    by_severity = {severity: 0 for severity in _SEVERITIES}
    by_assertion: dict[str, int] = {}
    for failure in failures:
        by_severity[failure.severity] = by_severity.get(failure.severity, 0) + 1
        by_assertion[failure.assertion] = by_assertion.get(failure.assertion, 0) + 1

    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commit": _current_commit(),
        "issue": issue or None,
        "roots": list(roots),
        "assertions": selected,
        "files_scanned": len(files),
        "totals": {
            "by_severity": by_severity,
            "total_failures": len(failures),
            "by_assertion": dict(sorted(by_assertion.items())),
        },
        "failures": [failure.to_dict() for failure in failures],
    }


def exit_code(evidence: dict[str, Any]) -> int:
    """1 when any P0/P1 failure is recorded, else 0 (P2 is advisory)."""
    blocking = [failure for failure in evidence["failures"] if failure["severity"] in ("P0", "P1")]
    return 1 if blocking else 0


def render_markdown(evidence: dict[str, Any]) -> str:
    """Render the evidence dict as the markdown close artifact."""
    issue = evidence["issue"]
    roots = ", ".join(evidence["roots"]) or "—"
    assertions = ", ".join(evidence["assertions"]) or "—"
    totals = evidence["totals"]
    by_severity = totals["by_severity"]
    by_assertion = totals["by_assertion"]

    lines: list[str] = [
        "# Real-Product Assertion Evidence",
        "",
        f"- Tool: `{evidence['tool']}`",
        f"- Schema: {evidence['schema_version']}",
        f"- Generated: {evidence['generated_at']}",
        f"- Commit: `{evidence['commit']}`",
        f"- Issue: {'# ' + str(issue) if issue else '—'}",
        f"- Roots: {roots}",
        f"- Assertions: {assertions}",
        f"- Files scanned: {evidence['files_scanned']}",
        "",
        "## Totals",
        "",
        "| Severity | Failures |",
        "|----------|----------|",
    ]
    for severity in _SEVERITIES:
        lines.append(f"| {severity} | {by_severity.get(severity, 0)} |")
    lines.append(f"| **Total** | {totals['total_failures']} |")

    lines += ["", "## Failures by assertion", ""]
    if by_assertion:
        lines += ["| Assertion | Failures |", "|-----------|----------|"]
        for name, count in by_assertion.items():
            lines.append(f"| {name} | {count} |")
    else:
        lines.append("No failures.")

    lines += ["", "## Failure details", ""]
    if evidence["failures"]:
        lines += [
            "| Path | Assertion | Severity | Details |",
            "|------|-----------|----------|---------|",
        ]
        for failure in evidence["failures"]:
            details = str(failure["details"]).replace("|", "\\|").replace("\n", " ")
            lines.append(
                f"| {failure['path']} | {failure['assertion']} | "
                f"{failure['severity']} | {details} |"
            )
    else:
        lines.append("No failures.")
    lines.append("")
    return "\n".join(lines)


def _print_summary(evidence: dict[str, Any]) -> None:
    totals = evidence["totals"]
    by_severity = totals["by_severity"]
    by_assertion = totals["by_assertion"]
    print(f"files scanned: {evidence['files_scanned']}")
    print(
        f"failures: {totals['total_failures']} "
        f"(P0={by_severity.get('P0', 0)}, "
        f"P1={by_severity.get('P1', 0)}, "
        f"P2={by_severity.get('P2', 0)})"
    )
    if by_assertion:
        print("failures by assertion:")
        for name, count in by_assertion.items():
            print(f"  {name}: {count}")
    else:
        print("failures by assertion: none")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="real_product_assertions.py",
        description=(
            "Run chosen autoinfo.validation_matrix assertions over real product "
            "roots and emit close evidence (deterministic, offline)."
        ),
    )
    parser.add_argument(
        "--roots",
        default=DEFAULT_ROOTS,
        help=f"comma-separated roots to walk (default: {DEFAULT_ROOTS})",
    )
    parser.add_argument(
        "--assertions",
        default="",
        help="comma-separated assertion names (default: all fast assertions)",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="GLOB",
        help="skip paths matching GLOB (repeatable / comma-separated)",
    )
    parser.add_argument(
        "--issue",
        default="",
        help="GitHub issue number/reference embedded in the evidence (e.g. 351)",
    )
    parser.add_argument("--json-out", default="", help="write evidence JSON here")
    parser.add_argument("--md-out", default="", help="write evidence markdown here")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    requested = parse_csv(args.assertions) or default_assertions()
    valid = set(assertion_names)
    unknown = [name for name in requested if name not in valid]
    if unknown:
        print(
            f"error: unknown assertion name(s): {', '.join(unknown)}",
            file=sys.stderr,
        )
        print("valid assertion names:", file=sys.stderr)
        for name in assertion_names:
            print(f"  {name}", file=sys.stderr)
        return 2

    roots = parse_csv(args.roots)
    if not roots:
        print("error: --roots is empty", file=sys.stderr)
        return 2
    excludes: list[str] = []
    for chunk in args.exclude:
        excludes.extend(parse_csv(chunk))

    for root_str in roots:
        if not Path(root_str).is_dir():
            print(f"warning: root not found, skipping: {root_str}", file=sys.stderr)

    evidence = scan(roots, requested, excludes=excludes, issue=args.issue)

    if args.json_out:
        json_path = Path(args.json_out)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if args.md_out:
        md_path = Path(args.md_out)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(render_markdown(evidence), encoding="utf-8")

    _print_summary(evidence)
    return exit_code(evidence)


if __name__ == "__main__":
    raise SystemExit(main())
