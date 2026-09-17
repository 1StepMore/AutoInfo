"""Regression locks for the CLI dataclass ``.to_dict()`` → ``asdict()`` fixes.

Three CLI commands called ``.to_dict()`` on pure dataclasses
(``UserProfile`` / ``AuditLog`` / ``DeliveryLog``), which have no such
method — an ``AttributeError`` on every non-empty path.  Each test patches
the command's real seam so it returns REAL dataclass instances and asserts
the ``--json`` envelope carries their fields.  Restoring ``.to_dict()``
makes the command raise ``AttributeError`` and the CLI exit non-zero.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from autoinfo.cli import _output, app
from autoinfo.models import AuditLog, DeliveryLog, Subscription, UserProfile

runner = CliRunner()


@pytest.fixture(autouse=True)
def _reset_global_json() -> None:
    """Reset the global-json ContextVar so one test cannot leak into the next."""
    yield
    _output.set_global_json(False)


def _envelope_data(stdout: str) -> dict[str, Any]:
    """Parse the canonical ``--json`` success envelope and return its ``data``."""
    payload = json.loads(stdout)
    assert payload["success"] is True, payload
    return payload["data"]


def test_enduser_create_real_dataclass_serializes() -> None:
    """``enduser create`` serializes a real ``UserProfile`` (was ``.to_dict()``).

    The ``asdict(profile)`` call sits outside the command's ``try`` block, so
    the old ``profile.to_dict()`` raised ``AttributeError`` and the CLI exited
    non-zero instead of emitting the profile fields.
    """
    profile = UserProfile(user_id="cli-user", name="CLI User", email="cli@example.com")
    with patch("autoinfo.cli.enduser.create_profile", return_value=profile):
        result = runner.invoke(
            app,
            ["--json", "enduser", "create", "--user-id", "cli-user", "--name", "CLI User"],
        )

    assert result.exit_code == 0, result.output
    data = _envelope_data(result.stdout)
    assert data["user_id"] == "cli-user"
    assert data["name"] == "CLI User"


def test_enduser_get_real_dataclass_serializes() -> None:
    """``enduser get`` serializes a real ``UserProfile`` (seam: ``get_profile``).

    Both the envelope branch and the human ``json.dumps`` branch call
    ``asdict(profile)``; the old ``.to_dict()`` raised ``AttributeError``
    before either could emit the fields.
    """
    profile = UserProfile(user_id="cli-user", name="CLI User")
    with patch("autoinfo.cli.enduser.get_profile", return_value=profile):
        result = runner.invoke(app, ["--json", "enduser", "get", "--user-id", "cli-user"])

    assert result.exit_code == 0, result.output
    data = _envelope_data(result.stdout)
    assert data["user_id"] == "cli-user"
    assert data["name"] == "CLI User"


def test_audit_query_real_dataclass_serializes() -> None:
    """``audit query`` serializes real ``AuditLog`` rows (seam: ``query_audit_log``).

    The list comprehension used ``e.to_dict()``; the old code raised
    ``AttributeError`` on the first entry, so the envelope never rendered.
    """
    entry = AuditLog(
        log_id="audit-1",
        timestamp="2026-01-01T00:00:00+00:00",
        actor="cli",
        action="test",
        resource_type="kb",
        resource_id="kb-1",
    )
    with patch("autoinfo.audit.query_audit_log", return_value=[entry]):
        result = runner.invoke(app, ["--json", "audit", "query"])

    assert result.exit_code == 0, result.output
    data = _envelope_data(result.stdout)
    assert data["count"] == 1
    assert data["entries"][0]["log_id"] == "audit-1"
    assert data["entries"][0]["actor"] == "cli"


def test_portal_history_real_dataclasses_serialize() -> None:
    """``portal history`` serializes real ``DeliveryLog`` rows (was ``.to_dict()``).

    Patches the module-level seams bound in ``autoinfo.cli.portal``: the
    command imports ``get_profile`` / ``list_subscriptions`` at module import
    time and aliases ``query_delivery_log`` as ``_query_log``.
    """
    profile = UserProfile(user_id="cli-user", name="CLI User")
    subscription = Subscription(subscription_id="sub-1", user_id="cli-user")
    entries = [
        DeliveryLog(
            log_id="log-1",
            subscription_id="sub-1",
            channel="smtp",
            message_type="digest",
            status="delivered",
            attempt_count=1,
            last_attempt="2026-01-01T00:00:00+00:00",
        )
    ]
    with (
        patch("autoinfo.cli.portal.get_profile", return_value=profile),
        patch("autoinfo.cli.portal.list_subscriptions", return_value=[subscription]),
        patch("autoinfo.cli.portal._query_log", return_value=entries),
    ):
        result = runner.invoke(app, ["--json", "portal", "history", "--user", "cli-user"])

    assert result.exit_code == 0, result.output
    data = _envelope_data(result.stdout)
    assert data["count"] == 1
    assert data["items"][0]["log_id"] == "log-1"
    assert data["items"][0]["channel"] == "smtp"
