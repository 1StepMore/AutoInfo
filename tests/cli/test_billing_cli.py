"""Tests for billing CLI — user-id optional with fallback (GH #107)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from autoinfo.cli import app as main_app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestBillingSummaryUserIdFallback:
    """`autoinfo billing summary` should work without --user-id,
    falling back to the configured multi_user.default_user_id ("default")."""

    def test_summary_without_user_id_falls_back_to_default(
        self, runner, tmp_path, monkeypatch
    ):
        """No config → fallback "default". --user-id is optional."""
        monkeypatch.chdir(tmp_path)

        with patch(
            "autoinfo.cost.CostMeter.get_enduser_usage",
            return_value={"llm_units": 42, "storage_mb": 1.5, "api_call_units": 3},
        ), patch(
            "autoinfo.billing.get_subscription_status",
            return_value={
                "profile_status": "active",
                "plan": "free",
                "stripe_status": "none",
                "customer_id": "",
            },
        ):
            result = runner.invoke(main_app, ["billing", "summary"])

        assert result.exit_code == 0, f"STDERR: {result.output}"
        assert "default" in result.output, (
            f"Expected 'default' in output, got: {result.output}"
        )

    def test_summary_with_explicit_user_id_works(
        self, runner, tmp_path, monkeypatch
    ):
        """Explicit --user-id alice → output shows 'alice'."""
        monkeypatch.chdir(tmp_path)

        with patch(
            "autoinfo.cost.CostMeter.get_enduser_usage",
            return_value={"llm_units": 10, "storage_mb": 0.5, "api_call_units": 1},
        ), patch(
            "autoinfo.billing.get_subscription_status",
            return_value={
                "profile_status": "trial",
                "plan": "premium",
                "stripe_status": "active",
                "customer_id": "cus_test",
            },
        ):
            result = runner.invoke(
                main_app, ["billing", "summary", "--user-id", "alice"]
            )

        assert result.exit_code == 0, f"STDERR: {result.output}"
        assert "alice" in result.output, (
            f"Expected 'alice' in output, got: {result.output}"
        )

    def test_summary_json_output_without_user_id(
        self, runner, tmp_path, monkeypatch
    ):
        """JSON output also works without --user-id."""
        monkeypatch.chdir(tmp_path)

        with patch(
            "autoinfo.cost.CostMeter.get_enduser_usage",
            return_value={"llm_units": 7, "storage_mb": 0.0, "api_call_units": 0},
        ), patch(
            "autoinfo.billing.get_subscription_status",
            return_value={
                "profile_status": "unknown",
                "plan": "free",
                "stripe_status": "none",
                "customer_id": "",
            },
        ):
            result = runner.invoke(
                main_app, ["billing", "summary", "--json"]
            )

        assert result.exit_code == 0
        assert '"user_id": "default"' in result.output, (
            f"JSON should contain default user_id, got: {result.output}"
        )
