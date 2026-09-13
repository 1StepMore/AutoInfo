"""Regression tests for T-S-03 param-alias normalization.

Generic ``(name, arguments)`` handlers declare neither ``user_id`` nor
``end_user_id``.  The resolver must not collapse a provider ``user_id``
onto the alias spelling, or the handler raises ``KeyError`` and the call
surfaces a spurious ``ValidationError`` (``export_user_data`` /
``delete_user_data``).
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from autoinfo.mcp import server
from autoinfo.mcp.server import call_tool


def _body(result: Any) -> dict[str, Any]:
    return json.loads(result[0][0].text)


class TestGenericHandlerUserIds:
    """Handlers taking ``(name, arguments)`` must see the canonical key."""

    def test_user_id_is_preserved(self) -> None:
        assert server._normalize_param_aliases("export_user_data", {"user_id": "u1"}) == {
            "user_id": "u1"
        }

    def test_end_user_id_resolves_to_canonical(self) -> None:
        assert server._normalize_param_aliases("export_user_data", {"end_user_id": "u1"}) == {
            "user_id": "u1"
        }

    def test_both_spellings_collapse_to_canonical(self) -> None:
        assert server._normalize_param_aliases(
            "delete_user_data", {"user_id": "u1", "end_user_id": "u2"}
        ) == {"user_id": "u1"}

    def test_handler_declares_rejects_generic_and_kwargs_signatures(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _handle_fake_generic(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
            return arguments

        def _handle_fake_kwargs(**kwargs: Any) -> dict[str, Any]:
            return kwargs

        monkeypatch.setitem(server.__dict__, "_handle_fake_generic", _handle_fake_generic)
        monkeypatch.setitem(server.__dict__, "_handle_fake_kwargs", _handle_fake_kwargs)

        assert server._handler_declares("fake_generic", "user_id") is False
        assert server._handler_declares("fake_kwargs", "user_id") is False
        assert server._handler_declares("export_user_data", "user_id") is False


class TestExplicitHandlerUserIds:
    """Explicit signatures keep resolving to the spelling they declare."""

    def test_end_user_id_handler_resolves_both_spellings_to_end_user_id(self) -> None:
        assert server._normalize_param_aliases("get_preferences", {"user_id": "u1"}) == {
            "end_user_id": "u1"
        }
        assert server._normalize_param_aliases("get_preferences", {"end_user_id": "u1"}) == {
            "end_user_id": "u1"
        }

    def test_user_id_handler_resolves_both_spellings_to_user_id(self) -> None:
        assert server._normalize_param_aliases("enduser_get", {"end_user_id": "u1"}) == {
            "user_id": "u1"
        }
        assert server._normalize_param_aliases("enduser_get", {"user_id": "u1"}) == {
            "user_id": "u1"
        }


class TestDomainAliases:
    """The ``domain``/``name`` block follows the same signature rule."""

    def test_explicit_name_handler_resolves_domain_to_name(self) -> None:
        assert server._normalize_param_aliases(
            "activate_domain", {"domain": "medical-research"}
        ) == {"name": "medical-research"}
        assert server._normalize_param_aliases("activate_domain", {"name": "medical-research"}) == {
            "name": "medical-research"
        }

    def test_generic_identity_handler_defaults_to_canonical_name(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _handle_fake_identity(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
            return arguments

        monkeypatch.setitem(server.__dict__, "_handle_fake_identity", _handle_fake_identity)
        monkeypatch.setattr(
            server,
            "_DOMAIN_IDENTITY_TOOLS",
            server._DOMAIN_IDENTITY_TOOLS | {"fake_identity"},
        )

        assert server._normalize_param_aliases("fake_identity", {"domain": "d1"}) == {"name": "d1"}

    def test_non_identity_tool_leaves_domain_untouched(self) -> None:
        assert server._normalize_param_aliases("export_user_data", {"domain": "d1"}) == {
            "domain": "d1"
        }


class TestGenericHandlerDispatch:
    """Dispatch-level regression: both spellings must reach the handler."""

    async def test_export_user_data_accepts_both_spellings(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen: list[str] = []

        def _fake_get_profile(user_id: str) -> dict[str, Any]:
            seen.append(user_id)
            return {"user_id": user_id}

        monkeypatch.setattr("autoinfo.user_store.get_profile", _fake_get_profile)

        for spelling in ("user_id", "end_user_id"):
            seen.clear()
            body = _body(await call_tool("export_user_data", {spelling: "u1"}))
            assert body["success"] is True, (spelling, body)
            assert body["data"]["user_id"] == "u1"
            assert seen == ["u1"]

    async def test_delete_user_data_accepts_both_spellings_with_purge(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen: list[str] = []

        class _FakeStore:
            def delete_user_data(self, user_id: str) -> dict[str, Any]:
                seen.append(user_id)
                return {"user_id": user_id, "deleted_count": 0}

        monkeypatch.setattr("autoinfo.kb.KBStore", _FakeStore)

        for spelling in ("user_id", "end_user_id"):
            seen.clear()
            body = _body(await call_tool("delete_user_data", {spelling: "u1", "purge": True}))
            assert body["success"] is True, (spelling, body)
            assert body["data"]["user_id"] == "u1"
            assert seen == ["u1"]

    async def test_delete_user_data_still_rejects_missing_purge(self) -> None:
        body = _body(await call_tool("delete_user_data", {"user_id": "u1"}))
        assert body["success"] is False
        assert body["error"]["code"] == "ValidationError"
