#!/usr/bin/env python3
"""Stage×user coverage report (register T-A-02, T-A-03, T-A-07).

Enumerates the **126** stage×user cells (7 pipeline stages ``A1``–``A7`` × 18
user-lifecycle stages ``B1.1``–``B1.7``, ``B2.1``–``B2.6``, ``B3.1``–``B3.5``)
plus the **72** founder-expectation rows (``F01``–``F72``) and classifies every
item as exactly one of:

- ``validated`` — a loaded validation scenario carries the matching
  ``pipeline_stage`` / ``user_level`` tag.
- ``implemented-unvalidated`` — recorded as delivered in the keystone catalog
  (or, for expectation rows, marked ✅/🟡) but not exercised by a scenario.
- ``out-of-scope`` / ``blocked-with-record`` / ``documented-limit`` — the
  committed disposition recorded by Todo 23 (T-A-06) in ``expectations.md``,
  ``cross-dimensional-catalog.md`` and ``multi-tenancy-auth.md``.

Everything is derived at run time from the live sources — the scenario loader,
the three disposition tables, and the catalog matrix — never hard-coded.  The
report exits non-zero if ANY item is unclassified, if the catalog is missing a
lifecycle column (e.g. B1.7), if the root spec does not define all 18 stages, or
if the disposition tables disagree.

Run from the project root::

    python3 scripts/stage_user_coverage.py          # human summary
    python3 scripts/stage_user_coverage.py --json   # machine-readable report

The same ``build_report`` function backs the ``get_coverage_report`` MCP tool.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

CATALOG = ROOT / "docs" / "dev" / "cross-dimensional-catalog.md"
EXPECTATIONS = ROOT / "docs" / "dev" / "specs" / "expectations.md"
TENANCY = ROOT / "docs" / "dev" / "specs" / "multi-tenancy-auth.md"
LIFECYCLE_DOC = ROOT / "docs" / "dev" / "specs" / "user-lifecycle-definition.md"

#: The 7 pipeline (A) stages of the value chain.
PIPELINE_STAGES: tuple[str, ...] = ("A1", "A2", "A3", "A4", "A5", "A6", "A7")

#: The 18 user-lifecycle (B) stages — the spine union (T-A-07).
LIFECYCLE_STAGES: tuple[str, ...] = (
    "B1.1",
    "B1.2",
    "B1.3",
    "B1.4",
    "B1.5",
    "B1.6",
    "B1.7",
    "B2.1",
    "B2.2",
    "B2.3",
    "B2.4",
    "B2.5",
    "B2.6",
    "B3.1",
    "B3.2",
    "B3.3",
    "B3.4",
    "B3.5",
)

#: The 72 founder-expectation IDs are enumerated from the expectation doc;
#: this is only the expected total (the live doc is the source of truth).
EXPECTATION_TOTAL = 72

#: Exactly-one committed disposition states (acceptance-framework §4 AC4).
DISPOSITION_STATES: frozenset[str] = frozenset(
    {"out-of-scope", "blocked-with-record", "documented-limit"}
)

#: Classification values emitted for every item.
CLASS_VALIDATED = "validated"
CLASS_IMPLEMENTED = "implemented-unvalidated"
CLASS_UNCLASSIFIED = "unclassified"

#: Catalog cell status tokens.
KNOWN_STATUS: frozenset[str] = frozenset({"🟢", "🟡", "🔴", "⚪"})

#: Expectation status markers that count as implemented (partial or full).
IMPLEMENTED_MARKERS: frozenset[str] = frozenset({"✅", "🟡", "🟢"})

_DISPOSITION_ROW_RE = re.compile(
    r"^\|\s*`([^`]+)`[^|]*\|\s*`(out-of-scope|blocked-with-record|documented-limit)`\s*\|"
)
_EXPECTATION_HEADING_RE = re.compile(r"^####\s+(F\w+)\s+—\s+(.*)$")
_EXPECTATION_ID_RE = re.compile(r"^F\d+[a-z]?$")
_LEVEL_IN_TITLE_RE = re.compile(r"(B\d\.\d)")
_LIFECYCLE_COLUMN_RE = re.compile(r"^(B\d\.\d)")
_PIPELINE_IN_LABEL_RE = re.compile(r"\*\*(A[1-7])")
_SEPARATOR_ROW_RE = re.compile(r"\|[\s:\-|]+\|")

DISPOSITION_DOCS: tuple[Path, ...] = (EXPECTATIONS, CATALOG, TENANCY)


def _read(path: Path) -> str:
    """Read a UTF-8 file, tolerating legacy bytes."""
    return path.read_text(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Live scenario tags (the only source of ``validated``)
# ---------------------------------------------------------------------------


def _load_scenarios(root: Path) -> list[dict[str, Any]]:
    """Load validation scenarios via the live loader.

    Raises ``RuntimeError`` if the loader cannot be imported or returns no
    scenarios — a report that silently counts zero scenarios would be a
    ``misleading_success_output`` failure mode.
    """
    src = str(root / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    from autoinfo.mcp.validation import load_scenarios

    scenarios = load_scenarios()
    if not scenarios:
        raise RuntimeError("load_scenarios() returned no scenarios — cannot classify cells")
    return scenarios


# ---------------------------------------------------------------------------
# Todo 23 dispositions (T-A-06)
# ---------------------------------------------------------------------------


def load_dispositions(
    doc_paths: tuple[Path, ...],
) -> tuple[dict[str, str], dict[str, int], list[str]]:
    """Parse the committed-disposition tables from the three Todo 23 docs.

    Returns ``(token_to_state, per_doc_counts, conflicts)``.  A token is the
    backticked identifier in the first table cell (``F58``, ``B1.2`` …); the
    state is the backticked disposition token in the second cell.  The same
    token appearing with different states in different documents is a
    ``conflict`` (a stale-disposition guard).
    """
    token_to_state: dict[str, str] = {}
    counts: dict[str, int] = {}
    conflicts: list[str] = []
    for path in doc_paths:
        if not path.exists():
            continue
        n = 0
        for line in _read(path).splitlines():
            m = _DISPOSITION_ROW_RE.match(line)
            if not m:
                continue
            token, state = m.group(1).strip(), m.group(2).strip()
            n += 1
            prior = token_to_state.get(token)
            if prior is not None and prior != state:
                conflicts.append(f"{token}: {prior} (earlier) vs {state} ({path.name})")
            token_to_state.setdefault(token, state)
        counts[path.name] = n
    return token_to_state, counts, conflicts


def _level_dispositions(token_to_state: dict[str, str], expectations: str) -> dict[str, str]:
    """Map lifecycle-level dispositions from the token table.

    A token that is itself a lifecycle stage (``B1.2``, ``B3.4`` …) maps
    directly.  An ``F``-token maps through the lifecycle level named in its
    expectation heading (``F65 → B1.1`` …); ``F``-tokens whose heading names no
    level (the F58–F64 blank-space group) carry no lifecycle-level disposition.
    """
    level_titles: dict[str, str] = {}
    for line in expectations.splitlines():
        m = _EXPECTATION_HEADING_RE.match(line)
        if m:
            level_titles[m.group(1)] = m.group(2)

    level_dispositions: dict[str, str] = {}
    for token, state in token_to_state.items():
        if token in LIFECYCLE_STAGES:
            level_dispositions[token] = state
            continue
        if token.startswith("F"):
            level_match = _LEVEL_IN_TITLE_RE.search(level_titles.get(token, ""))
            if level_match:
                level_dispositions.setdefault(level_match.group(1), state)
    return level_dispositions


# ---------------------------------------------------------------------------
# Live expectation rows (72)
# ---------------------------------------------------------------------------


def parse_expectations(text: str) -> list[dict[str, Any]]:
    """Return one row per ``#### Fxx — … <marker>`` heading in the catalog."""
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        m = _EXPECTATION_HEADING_RE.match(line)
        if not m:
            continue
        fid, title = m.group(1).strip(), m.group(2).strip()
        if not _EXPECTATION_ID_RE.match(fid):
            continue
        marker = next((ch for ch in ("✅", "🟡", "❌", "🟢", "🔴") if ch in title), None)
        level_match = _LEVEL_IN_TITLE_RE.search(title)
        rows.append(
            {
                "id": fid,
                "title": title,
                "status": marker,
                "level": level_match.group(1) if level_match else None,
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Live catalog matrix (status per A×B cell + lifecycle columns)
# ---------------------------------------------------------------------------


def _split_row(line: str) -> list[str]:
    """Split a Markdown table row into stripped cells (no header/edge pipes)."""
    stripped = line.strip()
    if not stripped.startswith("|"):
        return []
    inner = stripped.strip("|")
    return [cell.strip() for cell in inner.split("|")]


def _cell_token(value: str) -> str:
    """Return the catalog status token for a cell, or the raw value if unknown.

    A well-formed cell starts with one of the four status symbols; anything
    else (empty, ``?``, an unrecognised emoji) is returned verbatim so the
    classifier can flag it as unclassified.
    """
    value = value.strip()
    if not value:
        return ""
    first = value[0]
    return first if first in KNOWN_STATUS else value


def parse_catalog(
    text: str,
) -> tuple[dict[tuple[str, str], str], dict[str, set[str]], list[str]]:
    """Parse the catalog matrix.

    Returns ``(cells, stage_columns, errors)`` where ``cells`` maps
    ``(A-stage, lifecycle-level)`` → status token, ``stage_columns`` maps each
    A-stage to the set of lifecycle levels present in its tables, and
    ``errors`` lists structural problems (unparsable rows).
    """
    lines = text.splitlines()
    cells: dict[tuple[str, str], str] = {}
    stage_columns: dict[str, set[str]] = {stage: set() for stage in PIPELINE_STAGES}
    errors: list[str] = []

    i = 0
    while i < len(lines):
        line = lines[i]
        if "Lifecycle" in line and "→" in line and line.lstrip().startswith("|"):
            header = _split_row(line)
            levels = [
                (m.group(1) if (m := _LIFECYCLE_COLUMN_RE.match(cell)) else cell)
                for cell in header[1:]
            ]
            j = i + 1
            while j < len(lines) and (
                not lines[j].strip() or _SEPARATOR_ROW_RE.fullmatch(lines[j].strip())
            ):
                j += 1
            if j >= len(lines) or not lines[j].lstrip().startswith("|"):
                errors.append(f"missing data row after lifecycle header at line {i + 1}")
                i += 1
                continue
            data = _split_row(lines[j])
            stage_match = _PIPELINE_IN_LABEL_RE.search(data[0] if data else "")
            if not stage_match:
                errors.append(f"unparsable stage label at line {j + 1}: {data[:1]!r}")
                i = j + 1
                continue
            stage = stage_match.group(1)
            values = data[1:]
            if len(values) != len(levels):
                errors.append(
                    f"{stage} row at line {j + 1}: {len(values)} values vs "
                    f"{len(levels)} lifecycle columns"
                )
            for level, value in zip(levels, values):
                if level not in LIFECYCLE_STAGES:
                    errors.append(
                        f"{stage} row at line {j + 1}: unknown lifecycle column {level!r}"
                    )
                    continue
                cells[(stage, level)] = _cell_token(value)
                stage_columns[stage].add(level)
            i = j + 1
            continue
        i += 1
    return cells, stage_columns, errors


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def _classify_cells(
    validated: set[tuple[str, str]],
    level_dispositions: dict[str, str],
    cells: dict[tuple[str, str], str],
) -> list[dict[str, str]]:
    """Classify all 126 canonical cells into exactly one state."""
    items: list[dict[str, str]] = []
    for stage in PIPELINE_STAGES:
        for level in LIFECYCLE_STAGES:
            key = (stage, level)
            if key in validated:
                state = CLASS_VALIDATED
            elif key not in cells:
                state = CLASS_UNCLASSIFIED
            elif cells[key] not in KNOWN_STATUS:
                state = CLASS_UNCLASSIFIED
            elif level in level_dispositions:
                state = level_dispositions[level]
            else:
                state = CLASS_IMPLEMENTED
            items.append({"item": f"{stage}×{level}", "kind": "cell", "classification": state})
    return items


def _classify_expectations(
    rows: list[dict[str, Any]], token_to_state: dict[str, str]
) -> list[dict[str, str]]:
    """Classify all 72 expectation rows into exactly one state."""
    items: list[dict[str, str]] = []
    for row in rows:
        if row["id"] in token_to_state:
            state = token_to_state[row["id"]]
        elif row["status"] in IMPLEMENTED_MARKERS:
            state = CLASS_IMPLEMENTED
        else:
            state = CLASS_UNCLASSIFIED
        items.append({"item": row["id"], "kind": "expectation", "classification": state})
    return items


def _tally(items: list[dict[str, str]]) -> dict[str, int]:
    tally: dict[str, int] = {}
    for item in items:
        tally[item["classification"]] = tally.get(item["classification"], 0) + 1
    return dict(sorted(tally.items()))


def build_report(root: Path | None = None) -> dict[str, Any]:
    """Build the full stage×user coverage report (pure function of live files)."""
    root = root or ROOT
    catalog_path = root / "docs" / "dev" / "cross-dimensional-catalog.md"
    expectations_path = root / "docs" / "dev" / "specs" / "expectations.md"
    tenancy_path = root / "docs" / "dev" / "specs" / "multi-tenancy-auth.md"
    lifecycle_path = root / "docs" / "dev" / "specs" / "user-lifecycle-definition.md"

    scenarios = _load_scenarios(root)
    validated = {(s["pipeline_stage"], s["user_level"]) for s in scenarios}

    token_to_state, doc_counts, conflicts = load_dispositions(
        (expectations_path, catalog_path, tenancy_path)
    )
    expectations_text = _read(expectations_path)
    level_dispositions = _level_dispositions(token_to_state, expectations_text)

    rows = parse_expectations(expectations_text)
    catalog_text = _read(catalog_path)
    cells, stage_columns, catalog_errors = parse_catalog(catalog_text)

    cell_items = _classify_cells(validated, level_dispositions, cells)
    exp_items = _classify_expectations(rows, token_to_state)

    unclassified = [
        item["item"]
        for item in cell_items + exp_items
        if item["classification"] == CLASS_UNCLASSIFIED
    ]

    # Structural spine checks: catalog has all 18 lifecycle columns per stage,
    # and the root spec defines all 18 stages (B1.7, B3.4, B3.5 included).
    missing_catalog: dict[str, list[str]] = {}
    for stage, present in stage_columns.items():
        missing = sorted(set(LIFECYCLE_STAGES) - present)
        if missing:
            missing_catalog[stage] = missing
    catalog_lifecycle_columns = len(
        {level for levels in stage_columns.values() for level in levels}
    )

    lifecycle_text = _read(lifecycle_path)
    lifecycle_missing = [
        level
        for level in LIFECYCLE_STAGES
        if not re.search(rf"(?<![0-9]){re.escape(level)}(?![0-9])", lifecycle_text)
    ]

    structural_failures: list[str] = []
    if missing_catalog:
        for stage, missing in sorted(missing_catalog.items()):
            structural_failures.append(
                f"catalog matrix {stage}: missing lifecycle column(s) {missing}"
            )
    if lifecycle_missing:
        structural_failures.append(
            f"root spec {lifecycle_path.name}: missing lifecycle stage(s) {lifecycle_missing}"
        )
    if len(rows) != EXPECTATION_TOTAL:
        structural_failures.append(
            f"expectations: found {len(rows)} rows, expected {EXPECTATION_TOTAL}"
        )
    if catalog_errors:
        structural_failures.extend(catalog_errors)
    if conflicts:
        structural_failures.extend(f"disposition conflict: {c}" for c in conflicts)

    ok = not unclassified and not structural_failures

    return {
        "status": "ok" if ok else "fail",
        "unclassified": unclassified,
        "structural_failures": structural_failures,
        "cells": {
            "total": len(cell_items),
            "classified": len(cell_items)
            - len([i for i in cell_items if i["classification"] == CLASS_UNCLASSIFIED]),
            "by_classification": _tally(cell_items),
            "validated_keys": sorted(f"{a}×{b}" for a, b in validated),
        },
        "expectations": {
            "total": len(exp_items),
            "classified": len(exp_items)
            - len([i for i in exp_items if i["classification"] == CLASS_UNCLASSIFIED]),
            "by_classification": _tally(exp_items),
        },
        "dispositions": {
            "by_state": _tally([{"classification": state} for state in token_to_state.values()]),
            "levels": sorted(level_dispositions),
            "sources": doc_counts,
        },
        "spine": {
            "pipeline_stages": len(PIPELINE_STAGES),
            "lifecycle_stages": len(LIFECYCLE_STAGES),
            "cells": len(PIPELINE_STAGES) * len(LIFECYCLE_STAGES),
            "expectations": len(rows),
            "catalog_lifecycle_columns": catalog_lifecycle_columns,
            "catalog_missing_columns": missing_catalog,
            "lifecycle_doc_missing": lifecycle_missing,
        },
        "scenario_count": len(scenarios),
    }


def _print_human(report: dict[str, Any]) -> None:
    cells = report["cells"]
    exps = report["expectations"]
    spine = report["spine"]
    print("Stage×user coverage report")
    print(
        f"  cells:        {cells['total']} total / {cells['classified']} classified"
        f" / {cells['total'] - cells['classified']} unclassified"
    )
    print(
        f"  expectations: {exps['total']} total / {exps['classified']} classified"
        f" / {exps['total'] - exps['classified']} unclassified"
    )
    print(f"  cells by classification:        {cells['by_classification']}")
    print(f"  expectations by classification: {exps['by_classification']}")
    print(
        f"  spine: {spine['pipeline_stages']} pipeline stages × "
        f"{spine['lifecycle_stages']} lifecycle stages = {spine['cells']} cells; "
        f"catalog columns={spine['catalog_lifecycle_columns']}; "
        f"scenarios={report['scenario_count']}"
    )
    print(f"  dispositions: {report['dispositions']['by_state']}")
    if report["unclassified"]:
        print(f"  UNCLASSIFIED ({len(report['unclassified'])}): {report['unclassified']}")
    for failure in report["structural_failures"]:
        print(f"  STRUCTURAL FAILURE: {failure}")
    print(
        f"STATUS: {'OK' if report['status'] == 'ok' else 'FAIL'} "
        f"(exit {'0' if report['status'] == 'ok' else '1'})"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Stage×user coverage report (126 cells + 72 expectations, "
        "zero-unclassified enforcement)."
    )
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args(argv)

    try:
        report = build_report()
    except Exception as exc:  # noqa: BLE001 - a failed read must never look green
        print(f"stage_user_coverage: ERROR — {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_human(report)
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
