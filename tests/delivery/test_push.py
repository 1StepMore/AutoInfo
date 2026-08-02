"""Tests for PushDeliveryChannel — generic push notification adapter.

Covers PushDeliveryChannel lifecycle, registry integration, and
health_check graceful degradation.  All HTTP calls are mocked
via httpx.Client patch — zero network requests.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import httpx
import pytest

from autoinfo.delivery.push import PushDeliveryChannel, _resolve_token
from autoinfo.models import DeliveryResult, Product, ProductType


# ============================================================================
# Helpers
# ============================================================================


def _make_product(
    product_id: str = "prod-001",
    domain: str = "test-domain",
    **config: object,
) -> Product:
    """Create a minimal Product for testing."""
    return Product(
        id=product_id,
        domain=domain,
        type=ProductType.PROCESSED,
        name="test-digest",
        config={k: v for k, v in config.items()},
    )


def _make_mock_httpx(
    status_code: int = 200,
    json_data: dict | None = None,
) -> MagicMock:
    """Create a mock httpx.Client response."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.text = "OK"
    if json_data is not None:
        mock_resp.json.return_value = json_data
    return mock_resp


# ============================================================================
# Token resolution
# ============================================================================


class TestResolveToken:
    """Tests for _resolve_token helper."""

    def test_resolve_literal_token(self) -> None:
        config = {"push_token": "abc123"}
        assert _resolve_token(config) == "abc123"

    def test_resolve_env_var_reference(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MY_PUSH_TOKEN", "env-token-456")
        config = {"push_token": "${MY_PUSH_TOKEN}"}
        assert _resolve_token(config) == "env-token-456"

    def test_resolve_env_var_missing_falls_back_to_raw(self) -> None:
        config = {"push_token": "${MISSING_ENV}"}
        result = _resolve_token(config)
        # Falls back to the raw "${MISSING_ENV}" string
        assert result == "${MISSING_ENV}"

    def test_resolve_no_token(self) -> None:
        assert _resolve_token({}) is None
        assert _resolve_token({"other": "value"}) is None


# ============================================================================
# Channel name
# ============================================================================


class TestPushChannelName:
    def test_name_is_push(self) -> None:
        channel = PushDeliveryChannel()
        assert channel.name == "push"


# ============================================================================
# validate_config
# ============================================================================


class TestValidateConfig:
    def test_valid_config(self) -> None:
        channel = PushDeliveryChannel()
        assert channel.validate_config({"push_endpoint": "https://example.com/push"}) is True

    def test_missing_endpoint(self) -> None:
        channel = PushDeliveryChannel()
        assert channel.validate_config({}) is False

    def test_empty_endpoint(self) -> None:
        channel = PushDeliveryChannel()
        assert channel.validate_config({"push_endpoint": ""}) is False

    def test_whitespace_only_endpoint(self) -> None:
        channel = PushDeliveryChannel()
        assert channel.validate_config({"push_endpoint": "   "}) is False

    def test_none_endpoint(self) -> None:
        channel = PushDeliveryChannel()
        # None is not a truthy string
        assert channel.validate_config({"push_endpoint": None}) is False  # type: ignore[dict-item]

    def test_never_raises(self) -> None:
        channel = PushDeliveryChannel()
        # Should never raise for any input
        assert channel.validate_config({}) is False
        assert channel.validate_config({"push_endpoint": 123}) is False  # type: ignore[dict-item]


# ============================================================================
# health_check
# ============================================================================


class TestHealthCheck:
    def test_missing_endpoint_returns_unhealthy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """health_check with no PUSH_ENDPOINT returns healthy=False, no raise."""
        monkeypatch.delenv("PUSH_ENDPOINT", raising=False)
        monkeypatch.delenv("PUSH_TOKEN", raising=False)
        channel = PushDeliveryChannel()
        result = channel.health_check()
        assert result["healthy"] is False
        assert "error" in result
        assert result["channel"] == "push"
        assert isinstance(result["latency_ms"], float)

    def test_endpoint_set_without_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """health_check with PUSH_ENDPOINT but no PUSH_TOKEN — still checks connectivity."""
        monkeypatch.setenv("PUSH_ENDPOINT", "https://example.com/push")
        monkeypatch.delenv("PUSH_TOKEN", raising=False)
        channel = PushDeliveryChannel()
        with patch("httpx.Client.head") as mock_head:
            mock_resp = _make_mock_httpx(200)
            mock_head.return_value = mock_resp
            result = channel.health_check()
            assert result["healthy"] is True
            assert result["channel"] == "push"

    def test_endpoint_unreachable_handles_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PUSH_ENDPOINT", "https://example.com/push")
        monkeypatch.delenv("PUSH_TOKEN", raising=False)
        channel = PushDeliveryChannel()
        with patch("httpx.Client.head", side_effect=httpx.ConnectError("Connection refused")):
            result = channel.health_check()
            assert result["healthy"] is False
            assert result["channel"] == "push"
            assert "Connection refused" in result["error"]


# ============================================================================
# send
# ============================================================================


class TestSend:
    def test_send_no_endpoint_returns_failed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """send() with no endpoint gracefully returns failed — never raises."""
        monkeypatch.delenv("PUSH_ENDPOINT", raising=False)
        channel = PushDeliveryChannel()
        product = _make_product()
        payload: dict[str, str] = {"title": "Test", "content": "Hello"}
        result = channel.send(product, payload, [])
        assert result.status == "failed"
        assert result.channel == "push"
        assert "No push endpoint" in (result.error or "")

    def test_send_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """send() with endpoint configured POSTs and succeeds."""
        monkeypatch.setenv("PUSH_ENDPOINT", "https://example.com/push")
        channel = PushDeliveryChannel()
        product = _make_product(
            push_endpoint="https://example.com/push",
        )
        payload: dict[str, str] = {"title": "Test", "content": "Hello"}
        with patch("httpx.Client.post") as mock_post:
            mock_resp = _make_mock_httpx(200)
            mock_post.return_value.__enter__ = MagicMock(return_value=mock_resp)
            mock_post.return_value.__exit__ = MagicMock(return_value=False)
            # Use the internal _post_push via send
            with patch.object(channel, "_post_push") as mock_push:
                result = channel.send(product, payload, [])
                mock_push.assert_called_once()
                assert result.status == "success"

    def test_send_with_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """send() with push_token includes Bearer auth header."""
        monkeypatch.setenv("PUSH_ENDPOINT", "https://example.com/push")
        channel = PushDeliveryChannel()
        product = _make_product(
            push_endpoint="https://example.com/push",
            push_token="my-secret-token",
        )
        payload: dict[str, str] = {"title": "Test", "content": "Hello"}
        with patch.object(channel, "_post_push") as mock_push:
            result = channel.send(product, payload, [])
            mock_push.assert_called_once()
            args, _kwargs = mock_push.call_args
            headers = args[2]
            assert "Authorization" in headers
            assert headers["Authorization"] == "Bearer my-secret-token"
            assert result.status == "success"

    def test_send_with_recipients(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """send() with recipients list POSTs to each."""
        channel = PushDeliveryChannel()
        product = _make_product()
        payload: dict[str, str] = {"title": "Test", "content": "Hello"}
        with patch.object(channel, "_post_push") as mock_push:
            result = channel.send(
                product,
                payload,
                ["https://ep1.example.com", "https://ep2.example.com"],
            )
            assert mock_push.call_count == 2
            assert result.status == "success"

    def test_send_partial_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """send() with partial failures returns partial status."""
        channel = PushDeliveryChannel()
        product = _make_product()
        payload: dict[str, str] = {"title": "Test", "content": "Hello"}
        recipients = ["https://ok.example.com", "https://fail.example.com"]

        call_count = 0

        def mock_post_push(url, body, headers, timeout=30, retries=3):
            nonlocal call_count
            call_count += 1
            if "fail" in url:
                raise httpx.ConnectError("Connection refused")

        with patch.object(channel, "_post_push", side_effect=mock_post_push):
            result = channel.send(product, payload, recipients)
            assert result.status == "partial"
            assert result.recipient_count == 1


# ============================================================================
# Channel registry integration
# ============================================================================


class TestRegistryIntegration:
    """Tests that the channel is properly registered."""

    def test_channel_in_registry(self) -> None:
        from autoinfo.delivery import _CHANNEL_REGISTRY, get_channel
        assert "push" in _CHANNEL_REGISTRY
        channel = get_channel("push")
        assert isinstance(channel, PushDeliveryChannel)
        assert channel.name == "push"

    def test_list_channels_includes_push(self) -> None:
        from autoinfo.delivery import list_channels
        channels = list_channels()
        assert "push" in channels

    def test_get_available_channels_includes_push(self) -> None:
        from autoinfo.delivery import get_available_channels
        channels = get_available_channels()
        assert "push" in channels

    def test_health_check_graceful_no_endpoint(self) -> None:
        """health_check() returns healthy=False without raising when no endpoint."""
        from autoinfo.delivery import get_channel
        channel = get_channel("push")
        with patch.dict(os.environ, {}, clear=True):
            result = channel.health_check()
            assert result["healthy"] is False
            assert result["channel"] == "push"
            assert "error" in result
