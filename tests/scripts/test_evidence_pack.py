"""Consistency tests for the 27x3 capability evidence pack.

Hermetic: the tests read the committed evidence files only; no network, no LLM.
They prove the Markdown table in ``evidence-pack.md`` is a projection of
``matrix.json`` rather than a hand-maintained copy.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

_EVIDENCE_DIR = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "dev"
    / "validation-reports"
    / "capability-27x3"
)
_PACK = _EVIDENCE_DIR / "evidence-pack.md"
_MATRIX = _EVIDENCE_DIR / "matrix.json"

_REACHED_INDEX = 4
_COUNTS_RE = re.compile(r"([A-Za-z][A-Za-z0-9-]*)=(\d+)")


def _read(path: Path) -> str:
    if not path.exists():
        pytest.fail(f"missing evidence file: {path}")
    return path.read_text(encoding="utf-8")


def _matrix_rows() -> list[dict[str, Any]]:
    return json.loads(_read(_MATRIX))["rows"]


def _cell_key(row: dict[str, Any]) -> tuple[str, str]:
    return row["domain"], f'{row["product"]}:{row["format"]}'


def _capability_section() -> str:
    text = _read(_PACK)
    marker = "## Capability matrix"
    assert marker in text, "evidence pack lost its Capability matrix section"
    section = text.split(marker, 1)[1]
    next_heading = section.find("\n## ")
    return section if next_heading == -1 else section[:next_heading]


def _capability_rows() -> list[list[str]]:
    lines = [
        line for line in _capability_section().splitlines() if line.startswith("| ")
    ]
    header = next(
        (
            index
            for index, line in enumerate(lines)
            if line.split("|")[1].strip() == "Domain"
        ),
        None,
    )
    assert header is not None, "Capability matrix table header is missing"
    return [
        [cell.strip() for cell in line.strip().strip("|").split("|")]
        for line in lines[header + 1 :]
    ]


def test_capability_table_has_one_row_per_matrix_cell() -> None:
    rows = _capability_rows()
    matrix = _matrix_rows()
    assert len(rows) == 81
    assert len(rows) == len(matrix)


def test_cell_set_matches_matrix_json() -> None:
    parsed = {(row[0], row[1]) for row in _capability_rows()}
    expected = {_cell_key(row) for row in _matrix_rows()}
    assert len(parsed) == 81
    assert parsed == expected


def test_reached_column_matches_matrix_json() -> None:
    rows = _capability_rows()
    expected = {_cell_key(row): row["reached"] for row in _matrix_rows()}
    seen: dict[tuple[str, str], str] = {}
    for row in rows:
        seen[(row[0], row[1])] = row[_REACHED_INDEX]
    assert len(seen) == len(rows), "duplicate (domain, cell) rows in the table"
    assert seen == expected


def test_counts_line_matches_matrix_counter() -> None:
    counts_line = next(
        (
            line
            for line in _read(_PACK).splitlines()
            if line.startswith("Counts: ")
        ),
        None,
    )
    assert counts_line is not None, "evidence pack lost its counts line"
    announced = {
        match.group(1): int(match.group(2))
        for match in _COUNTS_RE.finditer(counts_line)
    }

    rows = _matrix_rows()
    reached = Counter(row["reached"] for row in rows)
    expected = {
        "rows": len(rows),
        "L3": reached["L3"],
        "blocked-no-llm-key": reached["blocked-no-llm-key"],
        "blocked-no-browser": reached["blocked-no-browser"],
        "blocked-stale-sources": reached["blocked-stale-sources"],
        "gated": sum(1 for row in rows if row["gated"]),
        "non-gated": sum(1 for row in rows if not row["gated"]),
        "keyed": sum(1 for row in rows if row["keyed"] == "keyed"),
        "unkeyed": sum(1 for row in rows if row["keyed"] == "unkeyed"),
    }
    assert announced == expected
