"""Tests for the webhook payload handler (WebhookHandler).

Tests cover valid payload processing, missing field validation, HMAC
signature verification (valid + invalid + tampered), and rate limiting.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

import pytest

from autoinfo.collectors.webhook import WebhookHandler
from autoinfo.models import Item

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def handler() -> WebhookHandler:
    """Return a default :class:`WebhookHandler` instance."""
    return WebhookHandler()


@pytest.fixture
def valid_payload() -> dict[str, Any]:
    """A payload with all required fields plus an extra field."""
    return {
        "title": "Test Article",
        "content": "This is the article body content.",
        "source_url": "https://example.com/article/1",
        "author": "John Doe",
    }


# ---------------------------------------------------------------------------
# Happy path — valid payload
# ---------------------------------------------------------------------------


class TestValidPayload:
    """Verify that a well-formed payload produces a correct Item."""

    def test_handle_returns_item(
        self, handler: WebhookHandler, valid_payload
    ) -> None:
        item = handler.handle(valid_payload)
        assert isinstance(item, Item)

    def test_handle_sets_required_fields(
        self, handler: WebhookHandler, valid_payload
    ) -> None:
        item = handler.handle(valid_payload)
        assert item.title == "Test Article"
        assert item.content == "This is the article body content."
        assert item.source_url == "https://example.com/article/1"
        assert item.source_type == "webhook"

    def test_handle_sets_source_name(
        self, handler: WebhookHandler, valid_payload
    ) -> None:
        item = handler.handle(valid_payload)
        assert item.source_name == "webhook"

    def test_handle_preserves_extra_fields_in_raw_data(
        self, handler: WebhookHandler, valid_payload
    ) -> None:
        item = handler.handle(valid_payload)
        assert item.raw_data.get("author") == "John Doe"

    def test_handle_excludes_required_fields_from_raw_data(
        self, handler: WebhookHandler, valid_payload
    ) -> None:
        item = handler.handle(valid_payload)
        assert "title" not in item.raw_data
        assert "content" not in item.raw_data
        assert "source_url" not in item.raw_data

    def test_custom_source_name(self, valid_payload) -> None:
        h = WebhookHandler(source_name="my-webhook")
        item = h.handle(valid_payload)
        assert item.source_name == "my-webhook"


# ---------------------------------------------------------------------------
# Validation — missing required fields
# ---------------------------------------------------------------------------


class TestMissingFields:
    """Verify that missing required fields raise ValueError."""

    def test_missing_title_raises_value_error(
        self, handler: WebhookHandler
    ) -> None:
        payload = {"content": "body", "source_url": "https://example.com"}
        with pytest.raises(ValueError, match="title"):
            handler.handle(payload)

    def test_missing_content_raises_value_error(
        self, handler: WebhookHandler
    ) -> None:
        payload = {"title": "Title", "source_url": "https://example.com"}
        with pytest.raises(ValueError, match="content"):
            handler.handle(payload)

    def test_missing_source_url_raises_value_error(
        self, handler: WebhookHandler
    ) -> None:
        payload = {"title": "Title", "content": "body"}
        with pytest.raises(ValueError, match="source_url"):
            handler.handle(payload)

    def test_empty_payload_raises_value_error(
        self, handler: WebhookHandler
    ) -> None:
        with pytest.raises(ValueError, match="Missing required"):
            handler.handle({})


# ---------------------------------------------------------------------------
# HMAC signature verification
# ---------------------------------------------------------------------------


class TestHMACVerification:
    """Verify HMAC-SHA256 signature signing and verification."""

    @staticmethod
    def _sign_payload(payload: dict[str, Any], secret: str) -> str:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hmac.new(
            secret.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def test_valid_signature_succeeds(
        self, handler: WebhookHandler
    ) -> None:
        payload = {
            "title": "Secure Article",
            "content": "Secret content",
            "source_url": "https://example.com/secure",
        }
        secret = "my-shared-secret"
        sig = self._sign_payload(payload, secret)
        payload["signature"] = sig

        item = handler.handle(payload, config={"secret": secret})
        assert isinstance(item, Item)
        assert item.title == "Secure Article"

    def test_valid_signature_with_sha256_prefix_succeeds(
        self, handler: WebhookHandler
    ) -> None:
        payload = {
            "title": "Prefixed Sig",
            "content": "Body",
            "source_url": "https://example.com/prefixed",
        }
        secret = "test-secret"
        sig = "sha256=" + self._sign_payload(payload, secret)
        payload["signature"] = sig

        item = handler.handle(payload, config={"secret": secret})
        assert isinstance(item, Item)

    def test_signature_in_config_instead_of_payload(
        self, handler: WebhookHandler
    ) -> None:
        payload = {
            "title": "Sig in Config",
            "content": "Body",
            "source_url": "https://example.com/sig-in-config",
        }
        secret = "config-secret"
        sig = self._sign_payload(payload, secret)

        item = handler.handle(
            payload, config={"secret": secret, "signature": sig}
        )
        assert isinstance(item, Item)

    def test_invalid_signature_raises_value_error(
        self, handler: WebhookHandler
    ) -> None:
        payload = {
            "title": "Tampered",
            "content": "Body",
            "source_url": "https://example.com/tampered",
        }
        payload["signature"] = "sha256=invalid_signature_value"

        with pytest.raises(ValueError, match="HMAC signature mismatch"):
            handler.handle(payload, config={"secret": "real-secret"})

    def test_missing_signature_with_secret_raises_value_error(
        self, handler: WebhookHandler
    ) -> None:
        payload = {
            "title": "No Sig",
            "content": "Body",
            "source_url": "https://example.com/no-sig",
        }
        with pytest.raises(ValueError, match="no signature"):
            handler.handle(payload, config={"secret": "some-secret"})

    def test_no_secret_skips_hmac(
        self, handler: WebhookHandler, valid_payload
    ) -> None:
        item = handler.handle(valid_payload)
        assert isinstance(item, Item)

    def test_tampered_payload_raises_value_error(
        self, handler: WebhookHandler
    ) -> None:
        payload = {
            "title": "Original",
            "content": "Original content",
            "source_url": "https://example.com/original",
        }
        secret = "my-secret"
        sig = self._sign_payload(payload, secret)
        payload["signature"] = sig

        payload["content"] = "Tampered content"

        with pytest.raises(ValueError, match="HMAC signature mismatch"):
            handler.handle(payload, config={"secret": secret})


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


class TestRateLimiting:
    """Verify in-memory sliding-window rate limiting."""

    def test_rate_limit_exceeded_raises_value_error(
        self, handler: WebhookHandler
    ) -> None:
        payload = {
            "title": "Rate Limited",
            "content": "Body",
            "source_url": "https://example.com/rate",
        }
        config = {"max_requests_per_minute": 2}

        handler.handle(payload, config)
        handler.handle(payload, config)

        with pytest.raises(ValueError, match="Rate limit exceeded"):
            handler.handle(payload, config)

    def test_no_rate_limit_when_config_not_set(
        self, handler: WebhookHandler, valid_payload
    ) -> None:
        for _ in range(100):
            item = handler.handle(valid_payload)
            assert item is not None

    def test_window_expiry_allows_new_requests(
        self, handler: WebhookHandler
    ) -> None:
        payload = {
            "title": "Window Expiry",
            "content": "Body",
            "source_url": "https://example.com/window",
        }
        config = {"max_requests_per_minute": 1}

        handler.handle(payload, config)

        handler._request_timestamps.clear()

        item = handler.handle(payload, config)
        assert isinstance(item, Item)
