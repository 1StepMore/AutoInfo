"""Tests for v1.5 MCP tools: gate config, product management, alert rules (Task 15).

Covers: get_gate_config, set_gate_config, get_product, list_products,
get_alert_rules, add_alert_rule, remove_alert_rule handlers and tool manifest.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import yaml

from autoinfo.mcp.errors import ErrorCode, success_response
from autoinfo.mcp.server import (
    _handle_get_gate_config,
    _handle_set_gate_config,
    _handle_get_product,
    _handle_list_products,
    _handle_get_alert_rules,
    _handle_add_alert_rule,
    _handle_remove_alert_rule,
)


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------


def _make_config_yaml(project_dir: Path, overrides: dict | None = None) -> None:
    """Write a minimal config.yaml with optional overrides into *project_dir*."""
    config: dict[str, Any] = {
        "project": {"name": "Test Project", "created_at": "2026-07-01"},
        "llm": {"provider": "openrouter", "model": "deepseek/deepseek-chat", "api_key": "test-key"},
        "domains": [
            {
                "name": "medical-research",
                "active": True,
                "sources": [{"name": "pubmed", "type": "api", "url": "https://example.com/api", "quality_tier": 1}],
                "topics": [{"name": "IVF", "keywords": ["IVF", "embryo"]}],
                "quality_gates": {
                    "G0": {"category": "hard", "retries": 2, "action": "block"},
                    "G1": {"category": "soft", "action": "flag"},
                },
                "delivery_gates": {
                    "D1": {"enabled": True, "action_on_failure": "block"},
                },
            }
        ],
        "quality_gates": {
            "G3": {"category": "soft", "action": "archive", "threshold": 30},
        },
    }
    if overrides:
        _deep_merge(config, overrides)
    config_dir = project_dir / ".autoinfo"
    config_dir.mkdir(parents=True, exist_ok=True)
    with open(config_dir / "config.yaml", "w", encoding="utf-8") as fh:
        yaml.dump(config, fh, default_flow_style=False)


def _deep_merge(base: dict, overrides: dict) -> None:
    """Recursively merge *overrides* into *base*."""
    for key, value in overrides.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


@pytest.fixture
def cwd_patch(tmp_path: Path):
    """Patch Path.cwd to return a temp dir with config.yaml."""
    _make_config_yaml(tmp_path)
    with patch("pathlib.Path.cwd", return_value=tmp_path):
        yield tmp_path


@pytest.fixture
def cwd_patch_no_domain(tmp_path: Path):
    """Patch Path.cwd with config that has no domains."""
    _make_config_yaml(tmp_path, {"domains": []})
    with patch("pathlib.Path.cwd", return_value=tmp_path):
        yield tmp_path


# ===================================================================
# 1. get_gate_config
# ===================================================================


class TestGetGateConfig:
    """get_gate_config returns gate config for a domain."""

    def test_get_quality_gate_from_domain(self, cwd_patch: Path) -> None:
        """Domain-level quality gate config is returned."""
        result = _handle_get_gate_config(domain="medical-research", gate="G0")
        assert "error_code" not in result, f"Unexpected error: {result}"
        assert result["domain"] == "medical-research"
        assert result["gate"] == "G0"
        assert result["gate_type"] == "quality"
        assert result["config"]["action"] == "block"
        assert result["config"]["retries"] == 2

    def test_get_delivery_gate_from_domain(self, cwd_patch: Path) -> None:
        """Domain-level delivery gate config is returned."""
        result = _handle_get_gate_config(domain="medical-research", gate="D1")
        assert "error_code" not in result
        assert result["gate"] == "D1"
        assert result["gate_type"] == "delivery"
        assert result["config"]["enabled"] is True
        assert result["config"]["action_on_failure"] == "block"

    def test_get_global_fallback_gate(self, cwd_patch: Path) -> None:
        """When gate is not set at domain level, global default is returned."""
        result = _handle_get_gate_config(domain="medical-research", gate="G3")
        assert "error_code" not in result
        assert result["gate"] == "G3"
        assert result["gate_type"] == "quality"
        # Global default action is "archive" with threshold 30
        assert result["config"]["action"] == "archive"

    def test_get_nonexistent_gate(self, cwd_patch: Path) -> None:
        """Non-existent gate returns error."""
        result = _handle_get_gate_config(domain="medical-research", gate="NONEXISTENT")
        assert "error_code" in result

    def test_get_nonexistent_domain(self, cwd_patch_no_domain: Path) -> None:
        """Non-existent domain returns error."""
        result = _handle_get_gate_config(domain="missing-domain", gate="G0")
        assert result.get("error_code") == ErrorCode.DOMAIN_NOT_FOUND.value


# ===================================================================
# 2. set_gate_config
# ===================================================================


class TestSetGateConfig:
    """set_gate_config updates gate config for a domain."""

    def test_set_quality_gate(self, cwd_patch: Path) -> None:
        """Updating a quality gate persists the new config."""
        result = _handle_set_gate_config(
            domain="medical-research",
            gate="G0",
            config={"action": "retry", "retries": 5, "category": "hard"},
        )
        assert "error_code" not in result, f"Unexpected error: {result}"
        assert result["updated"] is True
        assert result["config"]["action"] == "retry"
        assert result["config"]["retries"] == 5

    def test_set_delivery_gate(self, cwd_patch: Path) -> None:
        """Updating a delivery gate persists the new config."""
        result = _handle_set_gate_config(
            domain="medical-research",
            gate="D1",
            config={"enabled": False, "action_on_failure": "flag"},
        )
        assert "error_code" not in result
        assert result["updated"] is True
        assert result["config"]["enabled"] is False
        assert result["config"]["action_on_failure"] == "flag"

    def test_set_creates_new_gate(self, cwd_patch: Path) -> None:
        """Setting a gate that doesn't exist creates it."""
        result = _handle_set_gate_config(
            domain="medical-research",
            gate="G4",
            config={"action": "block", "retries": 3, "category": "hard"},
        )
        assert "error_code" not in result
        assert result["updated"] is True

        # Verify it was persisted
        readback = _handle_get_gate_config(domain="medical-research", gate="G4")
        assert readback["config"]["action"] == "block"
        assert readback["config"]["retries"] == 3

    def test_set_nonexistent_domain(self, cwd_patch_no_domain: Path) -> None:
        """Setting gate on non-existent domain returns error."""
        result = _handle_set_gate_config(
            domain="missing-domain",
            gate="G0",
            config={"action": "block"},
        )
        assert result.get("error_code") == ErrorCode.DOMAIN_NOT_FOUND.value


# ===================================================================
# 3. get_product / list_products
# ===================================================================


class TestProductTools:
    """Product MCP tools return derived product config."""

    def test_get_raw_product(self, cwd_patch: Path) -> None:
        """get_product with RAW type returns raw product."""
        result = _handle_get_product(domain="medical-research", product_type="RAW")
        assert "error_code" not in result, f"Unexpected error: {result}"
        product = result["product"]
        assert product["type"] == "raw"
        assert product["domain"] == "medical-research"
        assert len(product["config"]["sources"]) == 1
        assert product["config"]["sources"][0]["name"] == "pubmed"

    def test_get_processed_product(self, cwd_patch: Path) -> None:
        """get_product with PROCESSED type returns processed product."""
        result = _handle_get_product(domain="medical-research", product_type="PROCESSED")
        assert "error_code" not in result
        product = result["product"]
        assert product["type"] == "processed"
        assert len(product["delivery_channels"]) > 0
        assert "digest" in product["templates"]

    def test_get_product_invalid_type(self, cwd_patch: Path) -> None:
        """Invalid product_type returns validation error."""
        result = _handle_get_product(domain="medical-research", product_type="INVALID")
        assert "error_code" in result

    def test_list_products(self, cwd_patch: Path) -> None:
        """list_products returns both RAW and PROCESSED products."""
        result = _handle_list_products(domain="medical-research")
        assert "error_code" not in result
        assert result["count"] == 2
        types = {p["type"] for p in result["products"]}
        assert types == {"raw", "processed"}

    def test_list_products_nonexistent_domain(self, cwd_patch_no_domain: Path) -> None:
        """list_products on missing domain returns error."""
        result = _handle_list_products(domain="missing-domain")
        assert result.get("error_code") == ErrorCode.DOMAIN_NOT_FOUND.value


# ===================================================================
# 4. Alert Rule handlers
# ===================================================================


class TestAlertRuleMCPHandlers:
    """Alert rule MCP handlers delegate to the alerts module."""

    def test_get_alert_rules_empty(self, cwd_patch: Path, tmp_path: Path) -> None:
        """get_alert_rules returns empty list when no rules exist."""
        alerts_path = tmp_path / ".autoinfo" / "alerts.yaml"
        with patch("autoinfo.alerts._alerts_path", return_value=alerts_path):
            result = _handle_get_alert_rules(domain="medical-research")
            assert "error_code" not in result
            assert result["count"] == 0
            assert result["alert_rules"] == []

    def test_add_and_list_alert_rules(self, cwd_patch: Path, tmp_path: Path) -> None:
        """Add a rule, then list it."""
        alerts_path = tmp_path / ".autoinfo" / "alerts.yaml"
        with patch("autoinfo.alerts._alerts_path", return_value=alerts_path):
            add_result = _handle_add_alert_rule(
                domain="medical-research",
                topic_keywords=["IVF", "embryo"],
                relevance_threshold=50.0,
                channel="email",
                enabled=True,
            )
            assert "error_code" not in add_result
            assert add_result["created"] is True
            rule = add_result["alert_rule"]
            assert rule["domain"] == "medical-research"
            assert rule["topic_keywords"] == ["IVF", "embryo"]

            # List and verify
            list_result = _handle_get_alert_rules(domain="medical-research")
            assert list_result["count"] == 1
            assert list_result["alert_rules"][0]["id"] == rule["id"]

    def test_remove_alert_rule(self, cwd_patch: Path, tmp_path: Path) -> None:
        """Remove an alert rule by ID."""
        alerts_path = tmp_path / ".autoinfo" / "alerts.yaml"
        with patch("autoinfo.alerts._alerts_path", return_value=alerts_path):
            add_result = _handle_add_alert_rule(
                domain="medical-research",
                topic_keywords=["test"],
            )
            rule_id = add_result["alert_rule"]["id"]

            remove_result = _handle_remove_alert_rule(id=rule_id)
            assert "error_code" not in remove_result
            assert remove_result["removed"] is True

            # Verify gone
            list_result = _handle_get_alert_rules(domain="medical-research")
            assert list_result["count"] == 0

    def test_remove_nonexistent_rule(self, cwd_patch: Path) -> None:
        """Removing a non-existent rule returns error."""
        with patch("autoinfo.alerts._alerts_path", return_value=Path("/nonexistent/alerts.yaml")):
            # The alerts module handles missing file gracefully
            result = _handle_remove_alert_rule(id="non-existent-id")
            # Should get an error since the rule doesn't exist
            assert "error_code" in result or result.get("removed") is False


# ===================================================================
# 5. Tool manifest verification
# ===================================================================


class TestToolManifest:
    """All new tools are registered in the MCP tool manifest."""

    def test_new_tools_in_health_check_count(self) -> None:
        """Number of tools reported by health_check should be >= 75 (68 existing + 7 new)."""
        from autoinfo.mcp.server import _handle_health_check
        result = _handle_health_check()
        # 68 existing + 7 new = 75 minimum
        assert result["tools_count"] >= 75, f"Expected >=75 tools, got {result['tools_count']}"

    def test_new_tools_listed(self) -> None:
        """Verify all 7 new tools are returned by list_tools."""
        import anyio
        from autoinfo.mcp.server import list_tools
        tools = anyio.run(list_tools)
        tool_names = {t.name for t in tools}
        expected = {
            "get_gate_config",
            "set_gate_config",
            "get_product",
            "list_products",
            "get_alert_rules",
            "add_alert_rule",
            "remove_alert_rule",
        }
        missing = expected - tool_names
        assert not missing, f"Tools missing from manifest: {missing}"
