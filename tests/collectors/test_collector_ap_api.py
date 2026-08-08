"""Tests for the Associated Press Content API collector handler.

Uses ``unittest.mock.patch`` to mock HTTP responses — no real API calls.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import patch

import httpx
import pytest

from autoinfo.collectors.ap_api import APAPIHandler, DEFAULT_FIELDS
from autoinfo.models import Item


# -- Helpers ---------------------------------------------------------------


def _make_response(data: dict[str, Any]) -> httpx.Response:
    """Create a mock httpx.Response with AP API-style JSON body."""
    return httpx.Response(
        200,
        json=data,
        request=httpx.Request("GET", "https://api.ap.org/media/v/content/search"),
    )


def _make_error_response(status_code: int) -> httpx.Response:
    """Create a mock error response."""
    return httpx.Response(
        status_code,
        request=httpx.Request("GET", "https://api.ap.org/media/v/content/search"),
    )


# -- Sample data -----------------------------------------------------------


SAMPLE_ARTICLES = [
    {
        "uri": "https://api.ap.org/content/abc123",
        "headline": "Global Climate Summit Reaches Landmark Agreement",
        "body": "World leaders gathered in Geneva for the annual climate summit...",
        "byline": "By JOHN DOE, Associated Press",
        "published": "2026-07-29T14:30:00Z",
        "section": "World",
        "language": "en",
        "source": "Associated Press",
    },
    {
        "uri": "https://api.ap.org/content/def456",
        "headline": "Tech Stocks Surge on AI Earnings Reports",
        "body": "Major technology companies reported strong quarterly earnings...",
        "byline": "By JANE SMITH, AP Business Writer",
        "published": "2026-07-29T09:15:00Z",
        "section": "Business",
        "language": "en",
        "source": "Associated Press",
    },
]

SAMPLE_RESPONSE = {
    "data": {
        "total": 2,
        "items": SAMPLE_ARTICLES,
    }
}

SAMPLE_RESPONSE_EMPTY = {
    "data": {
        "total": 0,
        "items": [],
    }
}

MAPPED_ARTICLE = {
    "id": "https://api.ap.org/content/abc123",
    "title": "Global Climate Summit Reaches Landmark Agreement",
    "content": "World leaders gathered in Geneva for the annual climate summit...",
    "author": "By JOHN DOE, Associated Press",
    "published_date": "2026-07-29T14:30:00Z",
    "section": "World",
    "language": "en",
    "source": "Associated Press",
}


# -- Handler import / construction -----------------------------------------


class TestAPAPIImport:
    """Verify the handler is importable and properly inherits BaseHandler."""

    def test_handler_is_importable(self) -> None:
        from autoinfo.collectors.ap_api import APAPIHandler as H
        assert H is not None

    def test_handler_creates_instance(self) -> None:
        handler = APAPIHandler(api_key="test-key")
        assert handler is not None
        assert handler.source_name == "ap_api"
        assert handler.source_type == "ap_api"

    def test_handler_is_registered_in_package(self) -> None:
        from autoinfo.collectors import APAPIHandler
        assert APAPIHandler is not None


# -- fetch() tests ---------------------------------------------------------


class TestAPAPIFetch:
    """Tests for ``APAPIHandler.fetch()`` with mocked HTTP."""

    def test_fetch_returns_list(self) -> None:
        handler = APAPIHandler(api_key="test-key")
        resp = _make_response(SAMPLE_RESPONSE)

        with patch("httpx.get", return_value=resp):
            articles = handler.fetch(limit=10)

        assert isinstance(articles, list)
        assert len(articles) == 2

    def test_fetch_empty_response(self) -> None:
        handler = APAPIHandler(api_key="test-key")
        resp = _make_response(SAMPLE_RESPONSE_EMPTY)

        with patch("httpx.get", return_value=resp):
            articles = handler.fetch(limit=10)

        assert isinstance(articles, list)
        assert len(articles) == 0

    def test_fetch_no_api_key_returns_empty(self) -> None:
        """Without api_key, fetch should log warning and return empty list."""
        handler = APAPIHandler()

        with patch("httpx.get") as mock_get:
            articles = handler.fetch(limit=10)

        mock_get.assert_not_called()
        assert articles == []

    def test_fetch_field_mapping_correct(self) -> None:
        handler = APAPIHandler(api_key="test-key")
        resp = _make_response(SAMPLE_RESPONSE)

        with patch("httpx.get", return_value=resp):
            articles = handler.fetch(limit=10)

        for article in articles:
            assert "id" in article
            assert "title" in article
            assert "content" in article
            assert "author" in article
            assert "published_date" in article
            assert "section" in article
            assert "language" in article
            assert "source" in article

    def test_fetch_field_values_match(self) -> None:
        handler = APAPIHandler(api_key="test-key")
        resp = _make_response(SAMPLE_RESPONSE)

        with patch("httpx.get", return_value=resp):
            articles = handler.fetch(limit=10)

        a0 = articles[0]
        assert a0["id"] == "https://api.ap.org/content/abc123"
        assert a0["title"] == "Global Climate Summit Reaches Landmark Agreement"
        assert "Geneva" in a0["content"]
        assert a0["author"] == "By JOHN DOE, Associated Press"
        assert a0["published_date"] == "2026-07-29T14:30:00Z"
        assert a0["section"] == "World"
        assert a0["language"] == "en"
        assert a0["source"] == "Associated Press"

        a1 = articles[1]
        assert a1["id"] == "https://api.ap.org/content/def456"
        assert "Tech Stocks" in a1["title"]
        assert a1["author"] == "By JANE SMITH, AP Business Writer"
        assert a1["section"] == "Business"

    def test_fetch_respects_limit(self) -> None:
        handler = APAPIHandler(api_key="test-key")
        resp = _make_response(SAMPLE_RESPONSE)

        with patch("httpx.get", return_value=resp) as mock_get:
            handler.fetch(limit=1)

        call_url = mock_get.call_args[0][0]
        assert "limit=1" in call_url

    def test_fetch_clamps_limit_max_100(self) -> None:
        handler = APAPIHandler(api_key="test-key")
        resp = _make_response(SAMPLE_RESPONSE)

        with patch("httpx.get", return_value=resp) as mock_get:
            handler.fetch(limit=999)

        call_url = mock_get.call_args[0][0]
        assert "limit=100" in call_url

    def test_fetch_clamps_limit_min_1(self) -> None:
        handler = APAPIHandler(api_key="test-key")
        resp = _make_response(SAMPLE_RESPONSE)

        with patch("httpx.get", return_value=resp) as mock_get:
            handler.fetch(limit=0)

        mock_get.assert_not_called()

    def test_fetch_includes_default_fields(self) -> None:
        handler = APAPIHandler(api_key="test-key")
        resp = _make_response(SAMPLE_RESPONSE)

        with patch("httpx.get", return_value=resp) as mock_get:
            handler.fetch(limit=10)

        call_url = mock_get.call_args[0][0]
        # Comma is %2C in URL-encoded query string
        assert "fields=" in call_url
        assert "uri%2Cheadline" in call_url

    def test_fetch_maps_minimal_article(self) -> None:
        """An article with minimal fields should not crash."""
        minimal_response = {
            "data": {
                "total": 1,
                "items": [
                    {
                        "uri": "https://api.ap.org/content/min001",
                        "headline": "Breaking News",
                    }
                ],
            }
        }
        handler = APAPIHandler(api_key="test-key")
        resp = _make_response(minimal_response)

        with patch("httpx.get", return_value=resp):
            articles = handler.fetch(limit=10)

        assert len(articles) == 1
        a = articles[0]
        assert a["id"] == "https://api.ap.org/content/min001"
        assert a["title"] == "Breaking News"
        assert a["content"] == ""
        assert a["author"] == ""

    def test_fetch_skips_items_without_id_and_title(self) -> None:
        """Items with no uri and no headline should be skipped."""
        minimal_response = {
            "data": {
                "total": 2,
                "items": [
                    {"uri": "", "headline": ""},
                    SAMPLE_ARTICLES[0],
                ],
            }
        }
        handler = APAPIHandler(api_key="test-key")
        resp = _make_response(minimal_response)

        with patch("httpx.get", return_value=resp):
            articles = handler.fetch(limit=10)

        assert len(articles) == 1
        assert articles[0]["id"] == SAMPLE_ARTICLES[0]["uri"]


# -- to_item() conversion tests ---------------------------------------------


class TestAPAPIConversion:
    """Tests for ``APAPIHandler.to_item()``."""

    def test_to_item_complete(self) -> None:
        handler = APAPIHandler(api_key="test-key")
        item = handler.to_item(MAPPED_ARTICLE)

        assert isinstance(item, Item)
        assert item.id == "https://api.ap.org/content/abc123"
        assert item.source_name == "ap_api"
        assert item.source_type == "ap_api"
        assert item.source_platform == "ap_api"
        assert item.title == "Global Climate Summit Reaches Landmark Agreement"
        assert "Geneva" in item.content
        assert item.content_type == "text"
        assert "ap_uri" in item.raw_data
        assert item.raw_data["author"] == "By JOHN DOE, Associated Press"
        assert item.raw_data["section"] == "World"
        assert item.raw_data["published_date"] == "2026-07-29T14:30:00Z"
        assert item.raw_data["language"] == "en"
        assert item.raw_data["source"] == "Associated Press"

    def test_to_item_empty_id_uses_uuid(self) -> None:
        handler = APAPIHandler(api_key="test-key")
        article = {
            "id": "",
            "title": "No ID Article",
            "content": "",
            "author": "",
            "published_date": "",
            "section": "",
            "language": "",
            "source": "",
        }
        item = handler.to_item(article)
        assert item.id
        assert item.id != ""
        assert "-" in item.id

    def test_to_item_source_url_empty_when_no_id(self) -> None:
        handler = APAPIHandler(api_key="test-key")
        article = {
            "id": "",
            "title": "",
            "content": "",
            "author": "",
            "published_date": "",
            "section": "",
            "language": "",
            "source": "",
        }
        item = handler.to_item(article)
        assert item.source_url == ""


# -- Auth & headers tests --------------------------------------------------


class TestAPAPIAuth:
    """Tests for API key handling and HTTP headers."""

    def test_api_key_sent_as_header(self) -> None:
        handler = APAPIHandler(api_key="my-ap-key-123")
        resp = _make_response(SAMPLE_RESPONSE)

        with patch("httpx.get", return_value=resp) as mock_get:
            handler.fetch(limit=5)

        headers = mock_get.call_args[1].get("headers", {})
        assert headers.get("x-api-key") == "my-ap-key-123"

    def test_no_api_key_header_when_key_empty(self) -> None:
        """When api_key is empty string, ``fetch`` returns early without HTTP call."""
        handler = APAPIHandler(api_key="")
        resp = _make_response(SAMPLE_RESPONSE)

        with patch("httpx.get", return_value=resp) as mock_get:
            articles = handler.fetch(limit=5)

        mock_get.assert_not_called()
        assert articles == []

    def test_with_env_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AUTOINFO_AP_API_KEY", "env-key-123")
        handler = APAPIHandler()
        assert handler.api_key == "env-key-123"

    def test_constructor_key_takes_precedence_over_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AUTOINFO_AP_API_KEY", "env-key")
        handler = APAPIHandler(api_key="explicit-key")
        assert handler.api_key == "explicit-key"

    def test_accept_header_always_present(self) -> None:
        handler = APAPIHandler(api_key="test-key")
        resp = _make_response(SAMPLE_RESPONSE)

        with patch("httpx.get", return_value=resp) as mock_get:
            handler.fetch(limit=5)

        headers = mock_get.call_args[1].get("headers", {})
        assert headers.get("Accept") == "application/json"


# -- Error handling tests --------------------------------------------------


class TestAPAPIErrorHandling:
    """Tests for error handling and graceful degradation."""

    def test_401_returns_empty_and_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        handler = APAPIHandler(api_key="test-key")
        resp = _make_error_response(401)

        with patch("httpx.get", return_value=resp):
            articles = handler.fetch(limit=10)

        assert articles == []
        assert "paid/enterprise" in caplog.text

    def test_403_returns_empty(self) -> None:
        handler = APAPIHandler(api_key="test-key")
        resp = _make_error_response(403)

        with patch("httpx.get", return_value=resp):
            articles = handler.fetch(limit=10)

        assert articles == []

    def test_429_rate_limit_returns_empty(self) -> None:
        handler = APAPIHandler(api_key="test-key")
        resp = _make_error_response(429)

        with patch("httpx.get", return_value=resp):
            articles = handler.fetch(limit=10)

        assert articles == []

    def test_500_returns_empty(self) -> None:
        handler = APAPIHandler(api_key="test-key")
        resp = _make_error_response(500)

        with patch("httpx.get", return_value=resp):
            articles = handler.fetch(limit=10)

        assert articles == []

    def test_non_json_response_returns_empty(self) -> None:
        handler = APAPIHandler(api_key="test-key")
        resp = httpx.Response(
            200,
            content=b"<html>Not JSON</html>",
            request=httpx.Request("GET", "https://api.ap.org/"),
        )

        with patch("httpx.get", return_value=resp):
            articles = handler.fetch(limit=10)

        assert articles == []

    def test_missing_data_items_returns_empty(self) -> None:
        handler = APAPIHandler(api_key="test-key")
        resp = _make_response({"unexpected": "structure"})

        with patch("httpx.get", return_value=resp):
            articles = handler.fetch(limit=10)

        assert articles == []


# -- Rate limiting tests ---------------------------------------------------


class TestAPAPIRateLimit:
    """Tests for rate limiter behaviour."""

    def test_requires_key_returns_true(self) -> None:
        assert APAPIHandler.requires_key() is True

    def test_default_rps(self) -> None:
        handler = APAPIHandler(api_key="test-key")
        assert handler._rps == 1.0

    def test_no_key_rps(self) -> None:
        handler = APAPIHandler()
        assert handler._rps == 0.5

    def test_rate_limit_first_call_instant(self) -> None:
        import time
        handler = APAPIHandler(api_key="test-key")
        resp = _make_response(SAMPLE_RESPONSE)

        with patch("httpx.get", return_value=resp):
            t0 = time.time()
            handler.fetch(limit=5)
            elapsed = time.time() - t0

        assert elapsed < 0.2
