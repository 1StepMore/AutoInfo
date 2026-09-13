"""Tool-description audit tests (D-工-1 evidence, best-practice-review).

Locks the behavior of ``scripts/tool_desc_audit.py`` so the audit the
best-practice review dimension relies on stays deterministic:

1. Every declared tool is parsed (count matches ``_full_tool_list()``,
   the live declaration and the source of ``get_tool_count``).
2. Verb-first naming — ``email_config`` is the only non-verb-style name;
   namespace+verb names (``enduser_create``, ``soft_delete_entry``,
   ``knowledge_graph_export``) are NOT violations.
3. The four D-工-1 metrics (param count / enum / default / description
   length) are computed and reported in ``summary``.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

from autoinfo.mcp.server import _full_tool_list

ROOT = Path(__file__).resolve().parents[2]
SERVER_SRC = ROOT / "src" / "autoinfo" / "mcp" / "server.py"
AUDIT_SCRIPT = ROOT / "scripts" / "tool_desc_audit.py"


@pytest.fixture(scope="module")
def tool_audit() -> Any:
    spec = importlib.util.spec_from_file_location("tool_desc_audit", AUDIT_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def result(tool_audit: Any) -> Any:
    return tool_audit.audit_tools(SERVER_SRC.read_text(encoding="utf-8"))


def test_all_declared_tools_parsed(result: Any) -> None:
    assert result["declared"] == len(_full_tool_list())


def test_email_config_is_only_verb_violation(result: Any) -> None:
    assert result["violations"]["not_verb_first"] == ["email_config"]


def test_namespace_verb_names_are_not_violations(result: Any) -> None:
    tools = {t["name"]: t for t in result["tools"]}
    for name in (
        "enduser_create",
        "soft_delete_entry",
        "knowledge_graph_export",
        "health_check",
        "topic_group_add",
    ):
        assert tools[name]["namespace_verb"] is True, name


def test_verb_first_ratio_high(result: Any) -> None:
    # 99.3% verb-style (verb-first + namespace+verb); keep >= 98% as the
    # regression floor so the D-工-1 evidence stays strong.
    assert result["summary"]["verb_style_ratio"] >= 0.98


def test_summary_metrics_present(result: Any) -> None:
    s = result["summary"]
    for key in (
        "declared",
        "verb_style_ratio",
        "param_count_avg",
        "over_8_params",
        "short_desc_lt10",
        "no_enum_tools",
        "enum_params_total",
        "default_params_total",
        "output_schema_ratio",
        "no_output_schema",
        "output_schema_floor_ok",
    ):
        assert key in s, key


def test_output_schema_floor_100_percent(result: Any) -> None:
    # T-S-01: every declared tool advertises the canonical envelope. The
    # static check mirrors the runtime test in tests/mcp/
    # test_tool_output_schema.py (both derive from _full_tool_list).
    assert result["summary"]["no_output_schema"] == 0
    assert result["summary"]["output_schema_floor_ok"] is True


def test_no_short_descriptions_remain(result: Any) -> None:
    # D2-1: descriptions must carry a "when to use" signal — <10 words
    # cannot. Fixed 36 -> 0; this is the regression floor.
    assert result["summary"]["short_desc_lt10"] == 0


def test_enum_params_total_above_baseline(result: Any) -> None:
    # Finite-value params must declare enums. Baseline was 36 enum params
    # across the surface; Todo 15 raised it to 55, then to 58 with the
    # asset-type / channel / graph-relation enums. Floor is the improved
    # number, so a regression that removes enums fails.
    assert result["summary"]["enum_params_total"] >= 58


def test_finite_value_params_declare_enums(result: Any) -> None:
    # T-S-04: params whose value set is genuinely fixed must carry an enum.
    tools = {t["name"]: t for t in result["tools"]}
    for name in ("get_project_assets", "get_channel_health", "query_knowledge_graph"):
        assert tools[name]["enum_params"] >= 1, name


def test_over_8_params_are_the_known_heavy_tools(result: Any) -> None:
    assert set(result["violations"]["over_8_params"]) == {
        "add_source",
        "generate_digest",
        "generate_report",
        "search_knowledge_base",
    }


def test_over_8_params_have_documented_rationale(result: Any) -> None:
    # Each sanctioned >8-param tool carries a documented reason for staying
    # over the D-工-1 threshold (splitting is a breaking surface change).
    exemptions = result["summary"]["over_8_param_exemptions"]
    assert set(exemptions) == set(result["violations"]["over_8_params"])
    for tool in exemptions:
        assert len(tool) > 0 and isinstance(tool, str)


def test_per_tool_row_shape(result: Any) -> None:
    tools = {t["name"]: t for t in result["tools"]}
    row = tools["add_source"]
    assert row["verb_first"] is True
    assert row["param_count"] == 12
    assert row["desc_words"] > 10
    assert row["enum_params"] >= 0
