"""Tests for SocialDeliveryChannel — social media publishing adapter.

Covers SocialPlatformConfig, _truncate_text, _format_post, and the
full SocialDeliveryChannel lifecycle.  All HTTP calls are mocked
via httpx.Client patch — zero network requests.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import httpx
import pytest

from autoinfo.delivery.social import (
    _PLATFORM_CHAR_LIMITS,
    _format_post,
    _resolve_auth_token,
    _truncate_text,
    SocialDeliveryChannel,
    SocialPlatformConfig,
)
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
        config={k: v for k, v in config.items()},  # type: ignore[misc]
    )


def _make_mock_httpx(
    status_code: int = 200,
    json_data: dict | None = None,
) -> MagicMock:
    """Create an httpx.Client mock that works inside a context manager."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    if json_data is not None:
        mock_response.json.return_value = json_data
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.post.return_value = mock_response
    mock_client.get.return_value = mock_response
    mock_client.head.return_value = mock_response

    return mock_client


# ============================================================================
# SocialPlatformConfig
# ============================================================================


class TestSocialPlatformConfig:
    """Tests for the SocialPlatformConfig dataclass."""

    def test_defaults(self) -> None:
        cfg = SocialPlatformConfig(platform="mastodon")
        assert cfg.platform == "mastodon"
        assert cfg.api_endpoint == ""
        assert cfg.auth_token == ""
        assert cfg.char_limit == 0
        assert cfg.post_format == "plain"
        assert cfg.extra_headers == {}

    def test_effective_char_limit_platform_default(self) -> None:
        cfg = SocialPlatformConfig(platform="mastodon")
        assert cfg.effective_char_limit == 500

    def test_effective_char_limit_custom_override(self) -> None:
        cfg = SocialPlatformConfig(platform="mastodon", char_limit=200)
        assert cfg.effective_char_limit == 200

    def test_effective_char_limit_unknown_platform(self) -> None:
        cfg = SocialPlatformConfig(platform="nonexistent")
        assert cfg.effective_char_limit == _PLATFORM_CHAR_LIMITS["generic"]

    def test_effective_char_limit_x(self) -> None:
        cfg = SocialPlatformConfig(platform="x")
        assert cfg.effective_char_limit == 280

    def test_effective_char_limit_linkedin(self) -> None:
        cfg = SocialPlatformConfig(platform="linkedin")
        assert cfg.effective_char_limit == 3000

    def test_full_config(self) -> None:
        cfg = SocialPlatformConfig(
            platform="bluesky",
            api_endpoint="https://bsky.social/api/v1/post",
            auth_token="token123",
            char_limit=250,
            post_format="markdown",
            extra_headers={"X-Custom": "value"},
        )
        assert cfg.platform == "bluesky"
        assert cfg.api_endpoint == "https://bsky.social/api/v1/post"
        assert cfg.auth_token == "token123"
        assert cfg.char_limit == 250
        assert cfg.effective_char_limit == 250
        assert cfg.post_format == "markdown"
        assert cfg.extra_headers == {"X-Custom": "value"}


# ============================================================================
# _truncate_text
# ============================================================================


class TestTruncateText:
    """Tests for the _truncate_text helper."""

    def test_short_text_unchanged(self) -> None:
        assert _truncate_text("hello", 10) == "hello"

    def test_exact_fit(self) -> None:
        assert _truncate_text("1234567890", 10) == "1234567890"

    def test_long_text_truncated(self) -> None:
        result = _truncate_text("a" * 500, 280)
        assert len(result) == 280  # exactly at max_chars limit
        assert result.endswith("\u2026")

    def test_truncate_at_space(self) -> None:
        result = _truncate_text("hello world this is a test", 22)
        # text[:21] = "hello world this is a" (21 chars), + "…" = 22
        assert result == "hello world this is a\u2026"

    def test_empty_text(self) -> None:
        assert _truncate_text("", 10) == ""

    def test_none_text(self) -> None:
        assert _truncate_text(None, 10) == ""  # type: ignore[arg-type]

    def test_zero_limit(self) -> None:
        result = _truncate_text("hello", 0)
        assert result == "\u2026"


# ============================================================================
# _format_post
# ============================================================================


class TestFormatPost:
    """Tests for the _format_post helper."""

    def _cfg(self, platform: str = "mastodon") -> SocialPlatformConfig:
        return SocialPlatformConfig(platform=platform)

    def test_basic_post(self) -> None:
        body = _format_post(
            {"title": "Breaking News", "content": "Something happened"},
            self._cfg(),
        )
        assert body["platform"] == "mastodon"
        assert body["format"] == "plain"
        assert "Breaking News Something happened" in body["text"]

    def test_title_only(self) -> None:
        body = _format_post({"title": "Hello World"}, self._cfg())
        assert body["text"] == "Hello World"

    def test_content_only(self) -> None:
        body = _format_post({"content": "Just content"}, self._cfg())
        assert body["text"] == "Just content"

    def test_with_url(self) -> None:
        body = _format_post(
            {"title": "Title", "url": "https://example.com"},
            self._cfg(),
        )
        assert "https://example.com" in body["text"]
        assert body["link"] == "https://example.com"

    def test_with_image_urls(self) -> None:
        body = _format_post(
            {"title": "Photo post", "image_urls": ["https://img.example.com/1.jpg"]},
            self._cfg(),
        )
        assert "media" in body
        assert len(body["media"]) == 1
        assert body["media"][0] == {"type": "image", "url": "https://img.example.com/1.jpg"}

    def test_with_video_url(self) -> None:
        body = _format_post(
            {"title": "Video", "video_url": "https://vid.example.com/clip.mp4"},
            self._cfg(),
        )
        assert "media" in body
        assert body["media"][0] == {"type": "video", "url": "https://vid.example.com/clip.mp4"}

    def test_with_both_media_types(self) -> None:
        body = _format_post(
            {
                "title": "Mixed media",
                "image_urls": ["https://img.example.com/1.jpg"],
                "video_url": "https://vid.example.com/clip.mp4",
            },
            self._cfg(),
        )
        assert len(body["media"]) == 2
        assert body["media"][0]["type"] == "image"
        assert body["media"][1]["type"] == "video"

    def test_empty_image_urls_skipped(self) -> None:
        body = _format_post(
            {"title": "Post", "image_urls": ["", "  "]},
            self._cfg(),
        )
        assert "media" not in body

    def test_truncation_with_url_preserved(self) -> None:
        """URL should be preserved even when content is truncated."""
        content = "x" * 500
        cfg = SocialPlatformConfig(platform="mastodon")
        body = _format_post(
            {"title": "T", "content": content, "url": "https://example.com/long-url"},
            cfg,
        )
        assert "https://example.com/long-url" in body["text"]

    def test_markdown_format(self) -> None:
        cfg = SocialPlatformConfig(platform="linkedin", post_format="markdown")
        body = _format_post({"title": "Title", "content": "Content"}, cfg)
        assert body["format"] == "markdown"


# ============================================================================
# _resolve_auth_token
# ============================================================================


class TestResolveAuthToken:
    """Tests for the _resolve_auth_token helper."""

    def test_from_config(self) -> None:
        token = _resolve_auth_token({"auth_token": "abc123"}, {})
        assert token == "abc123"

    def test_from_payload(self) -> None:
        token = _resolve_auth_token({}, {"auth_token": "xyz789"})
        assert token == "xyz789"

    def test_config_takes_precedence(self) -> None:
        token = _resolve_auth_token(
            {"auth_token": "config-token"},
            {"auth_token": "payload-token"},
        )
        assert token == "config-token"

    def test_env_var_reference(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MY_SOCIAL_TOKEN", "env-resolved-token")
        token = _resolve_auth_token({"auth_token": "${MY_SOCIAL_TOKEN}"}, {})
        assert token == "env-resolved-token"

    def test_env_var_not_set(self) -> None:
        """Unresolved env var reference passes through as-is."""
        token = _resolve_auth_token({"auth_token": "${MISSING_VAR}"}, {})
        assert token == "${MISSING_VAR}"  # unchanged — caller handles

    def test_none_token(self) -> None:
        token = _resolve_auth_token({}, {})
        assert token is None

    def test_empty_string_token(self) -> None:
        token = _resolve_auth_token({"auth_token": ""}, {})
        assert token is None


# ============================================================================
# SocialDeliveryChannel
# ============================================================================


class TestSocialDeliveryChannel:
    """Tests for SocialDeliveryChannel ABC implementation."""

    def test_name_property(self) -> None:
        channel = SocialDeliveryChannel()
        assert channel.name == "social_publish"

    def test_validate_config_valid(self) -> None:
        channel = SocialDeliveryChannel()
        assert channel.validate_config({"auth_token": "token-abc"}) is True

    def test_validate_config_env_var_reference(self) -> None:
        channel = SocialDeliveryChannel()
        assert channel.validate_config({"auth_token": "${SOCIAL_TOKEN}"}) is True

    def test_validate_config_missing_token(self) -> None:
        channel = SocialDeliveryChannel()
        assert channel.validate_config({}) is False
        assert channel.validate_config({"other": "value"}) is False

    def test_validate_config_empty_token(self) -> None:
        channel = SocialDeliveryChannel()
        assert channel.validate_config({"auth_token": ""}) is False
        assert channel.validate_config({"auth_token": "  "}) is False


# ============================================================================
# SocialDeliveryChannel.send
# ============================================================================


class TestSocialDeliveryChannelSend:
    """Tests for the send() method with mocked HTTP."""

    def test_send_success_single_endpoint(self) -> None:
        product = _make_product(
            auth_token="test-token",
            platform="mastodon",
        )
        channel = SocialDeliveryChannel()
        payload = {"title": "Hello", "content": "World"}

        mock_http = _make_mock_httpx(200, {"id": "post-1"})
        with patch("autoinfo.delivery.social.httpx.Client", return_value=mock_http):
            result = channel.send(
                product, payload, ["https://mastodon.social/api/v1/statuses"],
            )

        assert result.status == "success"
        assert result.channel == "social_publish"
        assert result.recipient_count == 1
        assert result.error is None

    def test_send_success_multiple_endpoints(self) -> None:
        product = _make_product(auth_token="token", platform="bluesky")
        channel = SocialDeliveryChannel()
        payload = {"title": "Multi", "content": "Post"}

        mock_http = _make_mock_httpx(200, {"id": "ok"})
        with patch("autoinfo.delivery.social.httpx.Client", return_value=mock_http):
            result = channel.send(
                product, payload,
                ["https://bsky1.example.com", "https://bsky2.example.com"],
            )

        assert result.status == "success"
        assert result.recipient_count == 2

    def test_send_missing_auth_token(self) -> None:
        product = _make_product(platform="mastodon")
        channel = SocialDeliveryChannel()
        result = channel.send(product, {}, [])
        assert result.status == "failed"
        assert "auth_token is required" in (result.error or "")

    def test_send_missing_endpoint(self) -> None:
        product = _make_product(auth_token="token", platform="mastodon")
        channel = SocialDeliveryChannel()
        result = channel.send(product, {}, [])
        assert result.status == "failed"
        assert "No platform endpoint" in (result.error or "")

    def test_send_uses_api_endpoint_from_config(self) -> None:
        product = _make_product(
            auth_token="token",
            platform="mastodon",
            api_endpoint="https://custom.example.com/api/post",
        )
        channel = SocialDeliveryChannel()
        payload = {"title": "Test"}

        mock_http = _make_mock_httpx(200, {"id": "ok"})
        with patch("autoinfo.delivery.social.httpx.Client", return_value=mock_http):
            result = channel.send(product, payload, [])

        assert result.status == "success"
        assert result.recipient_count == 1

    def test_send_auth_error_401(self) -> None:
        """Auth error (401) should be caught and reported."""
        product = _make_product(auth_token="bad-token", platform="mastodon")
        channel = SocialDeliveryChannel()
        payload = {"title": "Bad auth"}

        # 401 response
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_response.request = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.post.return_value = mock_response

        with patch("autoinfo.delivery.social.httpx.Client", return_value=mock_client):
            result = channel.send(
                product, payload, ["https://mastodon.social/api/v1/statuses"],
            )

        assert result.status == "partial"
        assert result.recipient_count == 0
        assert "1 platform endpoint(s) failed" in (result.error or "")

    def test_send_auth_error_403(self) -> None:
        """Forbidden error (403) should be caught and reported."""
        product = _make_product(auth_token="token", platform="linkedin")
        channel = SocialDeliveryChannel()
        payload = {"title": "Forbidden"}

        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"
        mock_response.request = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.post.return_value = mock_response

        with patch("autoinfo.delivery.social.httpx.Client", return_value=mock_client):
            result = channel.send(
                product, payload, ["https://api.linkedin.com/posts"],
            )

        assert result.status == "partial"
        assert result.recipient_count == 0

    def test_send_partial_success(self) -> None:
        """One endpoint succeeds, another fails."""
        product = _make_product(auth_token="token", platform="mastodon")
        channel = SocialDeliveryChannel()
        payload = {"title": "Partial"}

        # First call succeeds, second fails
        mock_success = MagicMock()
        mock_success.status_code = 200
        mock_success.request = MagicMock()  # needed for HTTPStatusError constructor
        mock_fail = MagicMock()
        mock_fail.status_code = 401
        mock_fail.text = "Unauthorized"
        mock_fail.request = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.post.side_effect = [mock_success, mock_fail]

        with patch("autoinfo.delivery.social.httpx.Client", return_value=mock_client):
            result = channel.send(
                product, payload,
                ["https://good.example.com", "https://bad.example.com"],
            )

        assert result.status == "partial"
        assert result.recipient_count == 1
        assert "1 platform endpoint(s) failed" in (result.error or "")

    def test_send_network_error(self) -> None:
        """Network errors should be caught and reported."""
        product = _make_product(auth_token="token", platform="mastodon")
        channel = SocialDeliveryChannel()
        payload = {"title": "Network fail"}

        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.post.side_effect = httpx.NetworkError("Connection refused")

        with patch("autoinfo.delivery.social.httpx.Client", return_value=mock_client):
            result = channel.send(
                product, payload, ["https://down.example.com"],
            )

        assert result.status == "partial"
        assert result.recipient_count == 0

    def test_send_includes_media_in_post_body(self) -> None:
        """Verify that image_urls and video_url are included in the POST."""
        product = _make_product(auth_token="token", platform="mastodon")
        channel = SocialDeliveryChannel()
        payload = {
            "title": "Media post",
            "content": "Check this out",
            "image_urls": ["https://img.example.com/photo.jpg"],
            "video_url": "https://vid.example.com/clip.mp4",
        }

        mock_http = _make_mock_httpx(200, {"id": "ok"})
        with patch("autoinfo.delivery.social.httpx.Client", return_value=mock_http):
            result = channel.send(
                product, payload, ["https://mastodon.example.com/api/post"],
            )

        assert result.status == "success"
        # Verify the body sent to the API
        call_args = mock_http.post.call_args
        sent_body = call_args.kwargs.get("json", {})
        assert "media" in sent_body
        assert len(sent_body["media"]) == 2

    def test_send_custom_char_limit(self) -> None:
        """Custom char_limit from config should be used."""
        product = _make_product(
            auth_token="token",
            platform="mastodon",
            char_limit=100,
        )
        channel = SocialDeliveryChannel()
        payload = {"title": "Short"}

        mock_http = _make_mock_httpx(200, {"id": "ok"})
        with patch("autoinfo.delivery.social.httpx.Client", return_value=mock_http):
            result = channel.send(
                product, payload, ["https://mastodon.example.com/api/post"],
            )

        assert result.status == "success"
        call_args = mock_http.post.call_args
        sent_body = call_args.kwargs.get("json", {})
        assert len(sent_body["text"]) <= 100 + 1  # char limit + possible ellipsis

    def test_send_extra_headers(self) -> None:
        """Extra headers from config should be included in POST."""
        product = _make_product(
            auth_token="token",
            platform="mastodon",
            extra_headers={"X-API-Key": "custom-key"},
        )
        channel = SocialDeliveryChannel()
        payload = {"title": "Headers test"}

        mock_http = _make_mock_httpx(200, {"id": "ok"})
        with patch("autoinfo.delivery.social.httpx.Client", return_value=mock_http):
            channel.send(
                product, payload, ["https://mastodon.example.com/api/post"],
            )

        # Check headers were passed
        call_args = mock_http.post.call_args
        sent_headers = call_args.kwargs.get("headers", {})
        assert "X-API-Key" in sent_headers

    def test_send_auth_token_from_payload(self) -> None:
        """Auth token from payload should be used when config lacks it."""
        product = _make_product(platform="mastodon")
        channel = SocialDeliveryChannel()
        payload = {"title": "Test", "auth_token": "payload-token"}

        mock_http = _make_mock_httpx(200, {"id": "ok"})
        with patch("autoinfo.delivery.social.httpx.Client", return_value=mock_http):
            result = channel.send(
                product, payload, ["https://mastodon.example.com/api/post"],
            )

        assert result.status == "success"


# ============================================================================
# SocialDeliveryChannel.health_check
# ============================================================================


class TestHealthCheck:
    """Tests for the health_check method."""

    def test_health_check_missing_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SOCIAL_PUBLISH_TOKEN", raising=False)
        channel = SocialDeliveryChannel()
        result = channel.health_check()
        assert result["healthy"] is False
        assert "SOCIAL_PUBLISH_TOKEN" in (result["error"] or "")
        assert result["channel"] == "social_publish"
        assert "latency_ms" in result

    def test_health_check_missing_endpoint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SOCIAL_PUBLISH_TOKEN", "test-token")
        monkeypatch.delenv("SOCIAL_PUBLISH_ENDPOINT", raising=False)
        channel = SocialDeliveryChannel()
        result = channel.health_check()
        assert result["healthy"] is False
        assert "SOCIAL_PUBLISH_ENDPOINT" in (result["error"] or "")

    def test_health_check_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SOCIAL_PUBLISH_TOKEN", "test-token")
        monkeypatch.setenv("SOCIAL_PUBLISH_ENDPOINT", "https://mastodon.example.com/api")

        mock_http = _make_mock_httpx(200)
        with patch("autoinfo.delivery.social.httpx.Client", return_value=mock_http):
            channel = SocialDeliveryChannel()
            result = channel.health_check()

        assert result["healthy"] is True
        assert result["channel"] == "social_publish"
        assert result["error"] is None

    def test_health_check_5xx(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SOCIAL_PUBLISH_TOKEN", "token")
        monkeypatch.setenv("SOCIAL_PUBLISH_ENDPOINT", "https://down.example.com")

        mock_http = _make_mock_httpx(503)
        with patch("autoinfo.delivery.social.httpx.Client", return_value=mock_http):
            channel = SocialDeliveryChannel()
            result = channel.health_check()

        assert result["healthy"] is False
        assert "HTTP 503" in (result["error"] or "")

    def test_health_check_network_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SOCIAL_PUBLISH_TOKEN", "token")
        monkeypatch.setenv("SOCIAL_PUBLISH_ENDPOINT", "https://unreachable.example.com")

        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.head.side_effect = httpx.NetworkError("No route to host")

        with patch("autoinfo.delivery.social.httpx.Client", return_value=mock_client):
            channel = SocialDeliveryChannel()
            result = channel.health_check()

        assert result["healthy"] is False


# ============================================================================
# Channel registry integration
# ============================================================================


class TestRegistryIntegration:
    """Tests that the channel is properly registered."""

    def test_channel_in_registry(self) -> None:
        from autoinfo.delivery import _CHANNEL_REGISTRY, get_channel
        assert "social_publish" in _CHANNEL_REGISTRY
        channel = get_channel("social_publish")
        assert isinstance(channel, SocialDeliveryChannel)
        assert channel.name == "social_publish"

    def test_list_channels_includes_social_publish(self) -> None:
        from autoinfo.delivery import list_channels
        channels = list_channels()
        assert "social_publish" in channels

    def test_get_available_channels_includes_social_publish(self) -> None:
        from autoinfo.delivery import get_available_channels
        channels = get_available_channels()
        assert "social_publish" in channels
