"""Tests for the living-doc count gate (issue #621)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


def _load_inventory() -> Any:
    path = Path(__file__).resolve().parents[2] / "scripts" / "doc_inventory.py"
    spec = importlib.util.spec_from_file_location("doc_inventory", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


inventory = _load_inventory()

EXPECTED = {"tools": 149, "scenarios": 182, "functional": 86, "regression": 96, "cli_groups": 31}


def test_stale_tool_count_is_flagged() -> None:
    text = "see MCP tools (146 tools, 35 categories) for the catalog"
    assert inventory.find_count_violations(text, EXPECTED) == [
        "line 1: tool count 146 != 149 (tools)"
    ]


def test_correct_tool_count_is_not_flagged() -> None:
    assert inventory.find_count_violations("MCP tools (149 tools, 35 categories)", EXPECTED) == []


def test_identifier_prefixed_number_is_not_a_claim() -> None:
    assert inventory.find_count_violations("A1 arXiv, B1 digest, E1 MCP tools", EXPECTED) == []


def test_small_subset_count_is_not_the_total() -> None:
    assert inventory.find_count_violations("15 scenarios need keys", EXPECTED) == []


def test_stale_scenario_split_is_flagged_per_fact() -> None:
    text = "list_validation_scenarios() → 166 scenarios (86 functional + 80 regression)"
    violations = inventory.find_count_violations(text, EXPECTED)
    assert "line 1: scenario total 166 != 182 (scenarios)" in violations
    assert "line 1: scenario split 80 != 96 (regression)" in violations


def test_multiline_claim_is_flagged() -> None:
    text = "the catalog (146\n   tools) is generated"
    assert inventory.find_count_violations(text, EXPECTED) == [
        "line 1: tool count 146 != 149 (tools)"
    ]


def test_counts_ignore_line_is_skipped() -> None:
    text = "history: 116 scenarios, 65 functional + 51 regression <!-- counts-ignore -->"
    assert inventory.find_count_violations(text, EXPECTED) == []


def test_stale_cli_group_count_is_flagged() -> None:
    assert inventory.find_count_violations("cli/ (30 groups mirroring MCP)", EXPECTED) == [
        "line 1: CLI group count 30 != 31 (cli_groups)"
    ]
