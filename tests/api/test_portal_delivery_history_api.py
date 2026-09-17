# mypy: ignore-errors
"""REST artifact: ``GET /api/v1/portal/delivery-history`` (T-S-10).

The REST surface-parity audit (``scripts/surface_parity.py``) points the
delivery-history route at this file as its real artifact — it was the only
``/api/v1`` route without an existing test or scenario step.  Keeping this
test green keeps the REST surface 100% accounted for (scenario, artifact or
documented disposition).

The route reads the user profile and the user's subscriptions via lazy
imports inside the handler, so ``autoinfo.user_store`` is patched at the
module seam (not the route module).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from autoinfo.models import DeliveryLog, Subscription, UserProfile


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    """Isolated ``TestClient`` with a minimal config and a temp CWD."""
    from autoinfo.api.server import app

    config_dir = tmp_path / ".autoinfo"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text("rest_api:\n  host: 127.0.0.1\n  port: 8741\n", encoding="utf-8")

    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        with patch("autoinfo.config.get_config_path", return_value=config_path):
            yield TestClient(app, raise_server_exceptions=False)
    finally:
        os.chdir(old_cwd)


def test_delivery_history_existing_user_empty(client: TestClient) -> None:
    """A user with no subscriptions gets an empty, enveloped history."""
    profile = SimpleNamespace(user_id="surface-user")
    with (
        patch("autoinfo.user_store.get_profile", return_value=profile),
        patch("autoinfo.user_store.list_subscriptions", return_value=[]),
    ):
        response = client.get("/api/v1/portal/delivery-history", params={"user_id": "surface-user"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["data"]["user_id"] == "surface-user"
    assert body["data"]["entries"] == []
    assert body["data"]["total"] == 0


def test_delivery_history_unknown_user_404(client: TestClient) -> None:
    """An unknown user is a 404 in the canonical error envelope."""
    with patch("autoinfo.user_store.get_profile", return_value=None):
        response = client.get("/api/v1/portal/delivery-history", params={"user_id": "ghost"})

    assert response.status_code == 404, response.text
    body = response.json()
    assert body["success"] is False
    assert "error" in body


def test_delivery_history_populated_serializes_real_dataclasses(client: TestClient) -> None:
    """Regression lock: the handler serializes real ``DeliveryLog``/``Subscription``.

    The route used to call ``entry.to_dict()`` and ``s.to_dict()`` on pure
    dataclasses (no such method — it was masked by a ``# type: ignore``).
    This path was never exercised because the only other test returns an
    empty subscription list, so the loop body and the subscriptions leg
    never ran.  With ``.to_dict()`` restored, the ``AttributeError`` hits
    the catch-all 500 handler and the ``status_code == 200`` assertion
    (plus the field assertions) fail.
    """
    profile = UserProfile(user_id="hist-user", name="Hist User")
    subscription = Subscription(
        subscription_id="sub_hist",
        user_id="hist-user",
        plan="premium",
        status="active",
    )
    older = DeliveryLog(
        log_id="log-old",
        subscription_id="sub_hist",
        channel="smtp",
        message_type="digest",
        status="delivered",
        attempt_count=1,
        last_attempt="2026-01-01T00:00:00+00:00",
    )
    newer = DeliveryLog(
        log_id="log-new",
        subscription_id="sub_hist",
        channel="webhook",
        message_type="report",
        status="delivered",
        attempt_count=2,
        last_attempt="2026-01-02T00:00:00+00:00",
    )

    with (
        patch("autoinfo.user_store.get_profile", return_value=profile),
        patch("autoinfo.user_store.list_subscriptions", return_value=[subscription]),
        patch("autoinfo.delivery_log.query_delivery_log", return_value=[older, newer]),
    ):
        response = client.get(
            "/api/v1/portal/delivery-history",
            params={"user_id": "hist-user"},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    data = body["data"]
    assert data["total"] == 2
    assert [e["log_id"] for e in data["entries"]] == ["log-new", "log-old"]
    entry = data["entries"][0]
    assert entry["channel"] == "webhook"
    assert entry["status"] == "delivered"
    assert data["subscriptions"][0]["subscription_id"] == "sub_hist"
    assert data["subscriptions"][0]["plan"] == "premium"
