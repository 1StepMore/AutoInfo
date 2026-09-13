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
