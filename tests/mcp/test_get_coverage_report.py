"""get_coverage_report MCP tool (register T-A-02/T-A-03/T-A-07).

Locks the behavior of the stage×user coverage report so the spine guarantee
stays machine-measurable:

1. The ``get_coverage_report`` tool is declared in ``_full_tool_list()``.
2. The handler returns a live report classifying all 126 cells + 72
   expectations with zero unclassified (reads the real repo docs + the live
   scenario loader — never a cached classification).
3. An unclassified cell is the only failing state: a cell missing from the
   catalog, or carrying an unknown status token, is reported unclassified.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "stage_user_coverage.py"


@pytest.fixture(scope="module")
def coverage() -> Any:
    spec = importlib.util.spec_from_file_location("stage_user_coverage", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_tool_declared_in_full_tool_list() -> None:
    from autoinfo.mcp.server import _full_tool_list

    names = [t.name for t in _full_tool_list()]
    assert "get_coverage_report" in names


def test_handler_returns_live_report_zero_unclassified() -> None:
    from autoinfo.mcp.server import _handle_get_coverage_report

    report = _handle_get_coverage_report()
    assert report["status"] == "ok", report
    assert report["cells"]["total"] == 126
    assert report["cells"]["classified"] == 126
    assert report["expectations"]["total"] == 72
    assert report["expectations"]["classified"] == 72
    assert report["unclassified"] == []
    assert report["spine"]["catalog_lifecycle_columns"] == 18
    assert report["spine"]["lifecycle_doc_missing"] == []


def test_validated_cell_requires_scenario_match(coverage: Any) -> None:
    validated = {("A1", "B1.4")}
    cells = {
        ("A1", "B1.4"): "🟢",
        ("A1", "B1.6"): "⚪",
        ("A1", "B1.1"): "⚪",
    }
    items = coverage._classify_cells(validated, {"B1.1": "out-of-scope"}, cells)
    by_key = {i["item"]: i["classification"] for i in items}
    assert by_key["A1×B1.4"] == "validated"
    assert by_key["A1×B1.6"] == "implemented-unvalidated"
    assert by_key["A1×B1.1"] == "out-of-scope"


def test_missing_cell_is_unclassified(coverage: Any) -> None:
    items = coverage._classify_cells(set(), {}, {})
    assert len(items) == 126
    assert all(i["classification"] == "unclassified" for i in items)


def test_unknown_token_cell_is_unclassified(coverage: Any) -> None:
    items = coverage._classify_cells(set(), {}, {("A1", "B1.4"): "🤷"})
    by_key = {i["item"]: i["classification"] for i in items}
    assert by_key["A1×B1.4"] == "unclassified"


def test_level_disposition_applies_when_catalog_token_known(coverage: Any) -> None:
    level_dispositions = {"B1.7": "out-of-scope"}
    items = coverage._classify_cells(set(), level_dispositions, {("A1", "B1.7"): "🔴"})
    by_key = {i["item"]: i["classification"] for i in items}
    assert by_key["A1×B1.7"] == "out-of-scope"


def test_expectation_rows_all_classified(coverage: Any) -> None:
    text = coverage._read(ROOT / "docs" / "dev" / "specs" / "expectations.md")
    rows = coverage.parse_expectations(text)
    assert len(rows) == 72
    token_to_state, _, _ = coverage.load_dispositions(
        (
            ROOT / "docs" / "dev" / "specs" / "expectations.md",
            ROOT / "docs" / "dev" / "cross-dimensional-catalog.md",
            ROOT / "docs" / "dev" / "specs" / "multi-tenancy-auth.md",
        )
    )
    items = coverage._classify_expectations(rows, token_to_state)
    assert len(items) == 72
    assert all(i["classification"] != "unclassified" for i in items)
    by_id = {i["item"]: i["classification"] for i in items}
    assert by_id["F58"] == "blocked-with-record"
    assert by_id["F68"] == "out-of-scope"
