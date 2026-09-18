"""Coverage for the billing CLI additions: ``create-free`` error/idempotency
envelope paths and the ``summary`` failure branch (T-S-07 error envelopes).

Complements ``test_billing_create_free.py`` (happy paths against the real
user store) with the error branches that only trigger when the user store
or the cost meter raises.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from autoinfo.cli import _output
from autoinfo.cli import app as main_app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _hermetic(tmp_path, monkeypatch):
    """Isolate cwd + HOME so no real config or user DB leaks in."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    yield
    _output.set_global_json(False)


def _subscription(**overrides: Any) -> MagicMock:
    """A persisted-subscription stand-in with free-tier defaults."""
    sub = MagicMock()
    sub.plan = "free"
    sub.domain_limit = 1
    sub.max_products = 1
    sub.max_frequency = "weekly"
    sub.allow_custom = False
    for key, value in overrides.items():
        setattr(sub, key, value)
    return sub


class TestCreateFreeErrorBranches:
    """``create-free`` must fail loudly (exit 1) when the user store errors."""

    @patch("autoinfo.user_store.create_subscription")
    @patch("autoinfo.user_store.create_profile")
    @patch("autoinfo.user_store.get_profile", side_effect=RuntimeError("db locked"))
    def test_profile_lookup_failure_exits_nonzero(
        self,
        mock_get_profile: MagicMock,
        mock_create_profile: MagicMock,
        mock_create_subscription: MagicMock,
    ) -> None:
        result = runner.invoke(main_app, ["billing", "create-free", "--user-id", "alice"])

        assert result.exit_code == 1, result.output
        assert "Error: db locked" in result.output
        mock_get_profile.assert_called_once_with("alice")
        mock_create_profile.assert_not_called()
        mock_create_subscription.assert_not_called()

    @patch("autoinfo.user_store.create_subscription")
    @patch("autoinfo.user_store.create_profile")
    @patch("autoinfo.user_store.get_profile", return_value=None)
    @patch("autoinfo.user_store.list_subscriptions", side_effect=RuntimeError("io error"))
    def test_subscription_lookup_failure_exits_nonzero(
        self,
        mock_list_subs: MagicMock,
        mock_get_profile: MagicMock,
        mock_create_profile: MagicMock,
        mock_create_subscription: MagicMock,
    ) -> None:
        result = runner.invoke(main_app, ["billing", "create-free", "--user-id", "alice"])

        assert result.exit_code == 1, result.output
        assert "Error: io error" in result.output
        mock_create_profile.assert_called_once_with(user_id="alice", name="alice", status="active")
        mock_create_subscription.assert_not_called()


class TestCreateFreeGlobalJsonEnvelope:
    """Global ``--json`` wraps the provisioning result in the canonical envelope."""

    @patch("autoinfo.user_store.get_profile", return_value=None)
    @patch("autoinfo.user_store.create_profile")
    @patch("autoinfo.user_store.list_subscriptions", return_value=[])
    @patch("autoinfo.user_store.create_subscription", return_value=_subscription())
    def test_created_emits_success_envelope(
        self, mock_create_sub: MagicMock, mock_list_subs: MagicMock, *_: MagicMock
    ) -> None:
        result = runner.invoke(main_app, ["--json", "billing", "create-free", "--user-id", "gina"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert payload["success"] is True
        data = payload["data"]
        assert data["user_id"] == "gina"
        assert data["plan"] == "free"
        assert data["created"] is True
        assert data["limits"] == {
            "max_domains": 1,
            "max_products": 1,
            "max_frequency": "weekly",
            "allow_custom": False,
        }
        mock_create_sub.assert_called_once_with(
            user_id="gina",
            plan="free",
            status="active",
            tier="free",
            platform_limit=1,
            domain_limit=1,
            max_products=1,
            max_frequency="weekly",
            allow_custom=False,
        )
        assert "Created free subscription" not in result.stdout

    @patch("autoinfo.user_store.get_profile")
    @patch("autoinfo.user_store.list_subscriptions", return_value=[_subscription(plan="premium")])
    @patch("autoinfo.user_store.create_subscription")
    def test_existing_subscription_envelope_reports_untouched(
        self, mock_create_sub: MagicMock, _mock_list_subs: MagicMock, _mock_get_profile: MagicMock
    ) -> None:
        result = runner.invoke(main_app, ["--json", "billing", "create-free", "--user-id", "hank"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert payload["success"] is True
        assert payload["data"]["created"] is False
        assert payload["data"]["plan"] == "free"
        mock_create_sub.assert_not_called()


class TestSummaryErrorBranch:
    """``billing summary`` reports cost-meter failures with exit 1."""

    @patch("autoinfo.cost.CostMeter.get_enduser_usage", side_effect=RuntimeError("usage boom"))
    def test_usage_failure_exits_nonzero(self, mock_usage: MagicMock) -> None:
        result = runner.invoke(main_app, ["billing", "summary", "--user-id", "iris"])

        assert result.exit_code == 1, result.output
        assert "Error: usage boom" in result.output
        mock_usage.assert_called_once_with(end_user_id="iris", period="month")
