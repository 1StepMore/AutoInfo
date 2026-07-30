"""Tests for the Reuters MCP collector handler.

Uses ``unittest.mock.patch`` to mock HTTP responses — no real API calls.
"""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import patch

import httpx
import pytest

from autoinfo.collectors.reuters_mcp import (
    DEFAULT_FIELD_MAPPING,
    ReutersMCPHandler,
    _extract_items,
)
from autoinfo.config import SourceConfig
from autoinfo.models import Item


# -- Helpers ---------------------------------------------------------------


def _make_response(data: dict[str, Any] | list[Any]) -> httpx.Response:
    """Create a mock httpx.Response with Reuters-style JSON body."""
    return httpx.Response(
        200,
        json=data,
        request=httpx.Request("POST", "https://api.reuters.com/content/v1/search"),
    )


def _make_error_response(status_code: int) -> httpx.Response:
    """Create a mock error response."""
    return httpx.Response(
        status_code,
        request=httpx.Request("POST", "https://api.reuters.com/content/v1/search"),
    )


def _make_source_config(**settings: Any) -> SourceConfig:
    """Create a SourceConfig with default Reuters settings."""
    defaults: dict[str, Any] = {
        "endpoint_url": "https://api.reuters.com/content/v1/search",
        "api_key": "test-reuters-key",
    }
    defaults.update(settings)
    return SourceConfig(
        name="reuters_mcp",
        type="reuters_mcp",
        url="https://api.reuters.com/content/v1/search",
        settings=defaults,
    )


# -- Sample data -----------------------------------------------------------


SAMPLE_ARTICLE = {
    "id": "reuters-news-001",
    "headline": "Global Markets Rally on Rate Cut Hopes",
    "body": "Stock markets surged worldwide as central banks signaled...",
    "byline": "By JANE DOE, Reuters",
    "published": "2026-07-29T14:30:00Z",
    "section": "Business",
    "language": "en",
    "source": "Reuters",
    "url": "https://www.reuters.com/markets/article-001",
}

SAMPLE_ARTICLE_2 = {
    "id": "reuters-news-002",
    "headline": "Oil Prices Drop Amid Supply Surplus",
    "body": "Crude oil prices fell sharply on Thursday...",
    "byline": "By JOHN SMITH, Reuters",
    "published": "2026-07-29T10:15:00Z",
    "section": "Commodities",
    "language": "en",
    "source": "Reuters",
    "url": "https://www.reuters.com/commodities/article-002",
}

SAMPLE_RESPONSE = {
    "data": {
        "items": [SAMPLE_ARTICLE, SAMPLE_ARTICLE_2],
    }
}

SAMPLE_RESPONSE_EMPTY = {
    "data": {
        "items": [],
    }
}


# -- Handler import / construction -----------------------------------------


class TestReutersMCPImport:
    """Verify the handler is importable and properly inherits BaseHandler."""

    def test_handler_is_importable(self) -> None:
        from autoinfo.collectors.reuters_mcp import ReutersMCPHandler as H

        assert H is not None

    def test_handler_creates_instance_with_config(self) -> None:
        config = _make_source_config()
        handler = ReutersMCPHandler(config)
        assert handler is not None
        assert handler.source_name == "reuters_mcp"
        assert handler.source_type == "reuters_mcp"

    def test_handler_creates_instance_no_config(self) -> None:
        handler = ReutersMCPHandler()
        assert handler is not None
        assert handler.api_key == ""

    def test_handler_is_registered_in_package(self) -> None:
        from autoinfo.collectors import ReutersMCPHandler

        assert ReutersMCPHandler is not None

    def test_requires_key_returns_true(self) -> None:
        assert ReutersMCPHandler.requires_key() is True

    def test_default_field_mapping_has_expected_keys(self) -> None:
        expected_keys = {"id", "title", "content", "author", "published_date",
                         "section", "language", "source", "source_url"}
        assert set(DEFAULT_FIELD_MAPPING.keys()) == expected_keys


# -- fetch() tests ---------------------------------------------------------


class TestReutersMCPFetch:
    """Tests for ``ReutersMCPHandler.fetch()`` with mocked HTTP."""

    def test_fetch_returns_list(self) -> None:
        config = _make_source_config()
        handler = ReutersMCPHandler(config)
        resp = _make_response(SAMPLE_RESPONSE)

        with patch("httpx.post", return_value=resp):
            articles = handler.fetch(limit=10)

        assert isinstance(articles, list)
        assert len(articles) == 2

    def test_fetch_empty_response(self) -> None:
        config = _make_source_config()
        handler = ReutersMCPHandler(config)
        resp = _make_response(SAMPLE_RESPONSE_EMPTY)

        with patch("httpx.post", return_value=resp):
            articles = handler.fetch(limit=10)

        assert isinstance(articles, list)
        assert len(articles) == 0

    def test_fetch_no_api_key_returns_empty(self, caplog: pytest.LogCaptureFixture) -> None:
        """Without api_key, fetch should log info and return empty list."""
        caplog.set_level(logging.INFO)
        config = _make_source_config(api_key="")
        handler = ReutersMCPHandler(config)

        with patch("httpx.post") as mock_post:
            articles = handler.fetch(limit=10)

        mock_post.assert_not_called()
        assert articles == []
        assert "api key not configured" in caplog.text.lower()

    def test_fetch_no_endpoint_url_returns_empty(self, caplog: pytest.LogCaptureFixture) -> None:
        """Without endpoint_url, fetch should log info and return empty list."""
        caplog.set_level(logging.INFO)
        config = _make_source_config(endpoint_url="")
        handler = ReutersMCPHandler(config)

        with patch("httpx.post") as mock_post:
            articles = handler.fetch(limit=10)

        mock_post.assert_not_called()
        assert articles == []
        assert "endpoint not configured" in caplog.text.lower()

    def test_fetch_field_values_match(self) -> None:
        config = _make_source_config()
        handler = ReutersMCPHandler(config)
        resp = _make_response(SAMPLE_RESPONSE)

        with patch("httpx.post", return_value=resp):
            articles = handler.fetch(limit=10)

        a0 = articles[0]
        assert a0["id"] == "reuters-news-001"
        assert a0["title"] == "Global Markets Rally on Rate Cut Hopes"
        assert "stock markets" in a0["content"].lower()
        assert a0["author"] == "By JANE DOE, Reuters"
        assert a0["published_date"] == "2026-07-29T14:30:00Z"
        assert a0["section"] == "Business"
        assert a0["language"] == "en"
        assert a0["source"] == "Reuters"
        assert a0["source_url"] == "https://www.reuters.com/markets/article-001"

    def test_fetch_respects_limit(self) -> None:
        config = _make_source_config()
        handler = ReutersMCPHandler(config)
        resp = _make_response(SAMPLE_RESPONSE)

        with patch("httpx.post", return_value=resp) as mock_post:
            handler.fetch(limit=5)

        json_body = mock_post.call_args[1].get("json", {})
        assert json_body["limit"] == 5

    def test_fetch_clamps_limit_max_100(self) -> None:
        config = _make_source_config()
        handler = ReutersMCPHandler(config)
        resp = _make_response(SAMPLE_RESPONSE)

        with patch("httpx.post", return_value=resp) as mock_post:
            handler.fetch(limit=999)

        json_body = mock_post.call_args[1].get("json", {})
        assert json_body["limit"] == 100

    def test_fetch_limit_zero_returns_empty(self) -> None:
        config = _make_source_config()
        handler = ReutersMCPHandler(config)

        with patch("httpx.post") as mock_post:
            articles = handler.fetch(limit=0)

        mock_post.assert_not_called()
        assert articles == []

    def test_fetch_includes_query_when_configured(self) -> None:
        config = _make_source_config(query="technology")
        handler = ReutersMCPHandler(config)
        resp = _make_response(SAMPLE_RESPONSE)

        with patch("httpx.post", return_value=resp) as mock_post:
            handler.fetch(limit=10)

        json_body = mock_post.call_args[1].get("json", {})
        assert json_body["q"] == "technology"

    def test_fetch_no_query_when_not_configured(self) -> None:
        config = _make_source_config()
        handler = ReutersMCPHandler(config)
        resp = _make_response(SAMPLE_RESPONSE)

        with patch("httpx.post", return_value=resp) as mock_post:
            handler.fetch(limit=10)

        json_body = mock_post.call_args[1].get("json", {})
        assert "q" not in json_body

    def test_fetch_maps_minimal_article(self) -> None:
        """An article with minimal fields should not crash."""
        minimal_response = {
            "data": {
                "items": [
                    {
                        "id": "reuters-min-001",
                        "headline": "Breaking News",
                    },
                ],
            },
        }
        config = _make_source_config()
        handler = ReutersMCPHandler(config)
        resp = _make_response(minimal_response)

        with patch("httpx.post", return_value=resp):
            articles = handler.fetch(limit=10)

        assert len(articles) == 1
        a = articles[0]
        assert a["id"] == "reuters-min-001"
        assert a["title"] == "Breaking News"
        assert a["content"] == ""
        assert a["author"] == ""

    def test_fetch_skips_items_without_id_and_title(self) -> None:
        """Items with no id and no title should be skipped."""
        response = {
            "data": {
                "items": [
                    {"id": "", "headline": ""},
                    SAMPLE_ARTICLE,
                ],
            },
        }
        config = _make_source_config()
        handler = ReutersMCPHandler(config)
        resp = _make_response(response)

        with patch("httpx.post", return_value=resp):
            articles = handler.fetch(limit=10)

        assert len(articles) == 1
        assert articles[0]["id"] == SAMPLE_ARTICLE["id"]

    def test_fetch_custom_field_mapping(self) -> None:
        """Custom field_mapping in settings should override defaults."""
        config = _make_source_config(
            field_mapping={
                "title": "alt_headline",
                "content": "full_text",
            },
        )
        handler = ReutersMCPHandler(config)
        assert handler.field_mapping["title"] == "alt_headline"
        assert handler.field_mapping["content"] == "full_text"
        # Unchanged defaults.
        assert handler.field_mapping["id"] == "id"
        assert handler.field_mapping["source"] == "source"

        custom_article = {
            "id": "custom-001",
            "alt_headline": "Custom Title",
            "full_text": "Custom content text.",
        }
        response = {"data": {"items": [custom_article]}}
        config2 = _make_source_config(
            field_mapping={
                "title": "alt_headline",
                "content": "full_text",
            },
        )
        handler2 = ReutersMCPHandler(config2)
        resp = _make_response(response)

        with patch("httpx.post", return_value=resp):
            articles = handler2.fetch(limit=10)

        assert len(articles) == 1
        assert articles[0]["title"] == "Custom Title"
        assert articles[0]["content"] == "Custom content text."

    def test_fetch_handles_results_shape(self) -> None:
        """Response with 'results' key should work."""
        response = {"results": [SAMPLE_ARTICLE]}
        config = _make_source_config()
        handler = ReutersMCPHandler(config)
        resp = _make_response(response)

        with patch("httpx.post", return_value=resp):
            articles = handler.fetch(limit=10)

        assert len(articles) == 1

    def test_fetch_handles_top_level_list(self) -> None:
        """Response that is a top-level list should work."""
        config = _make_source_config()
        handler = ReutersMCPHandler(config)
        resp = _make_response([SAMPLE_ARTICLE, SAMPLE_ARTICLE_2])

        with patch("httpx.post", return_value=resp):
            articles = handler.fetch(limit=10)

        assert len(articles) == 2

    def test_fetch_handles_items_at_top_level(self) -> None:
        """Response with items at top level."""
        response = {"items": [SAMPLE_ARTICLE]}
        config = _make_source_config()
        handler = ReutersMCPHandler(config)
        resp = _make_response(response)

        with patch("httpx.post", return_value=resp):
            articles = handler.fetch(limit=10)

        assert len(articles) == 1


# -- to_item() conversion tests ---------------------------------------------


class TestReutersMCPConversion:
    """Tests for ``ReutersMCPHandler.to_item()``."""

    def test_to_item_complete(self) -> None:
        config = _make_source_config()
        handler = ReutersMCPHandler(config)
        mapped = handler._map_article(SAMPLE_ARTICLE)
        item = handler.to_item(mapped)

        assert isinstance(item, Item)
        assert item.id == "reuters-news-001"
        assert item.source_name == "reuters_mcp"
        assert item.source_type == "reuters_mcp"
        assert item.source_platform == "reuters_mcp"
        assert item.title == "Global Markets Rally on Rate Cut Hopes"
        assert "stock markets" in item.content.lower()
        assert item.content_type == "text"
        assert item.source_url == "https://www.reuters.com/markets/article-001"
        assert item.raw_data["author"] == "By JANE DOE, Reuters"
        assert item.raw_data["section"] == "Business"

    def test_to_item_empty_id_uses_uuid(self) -> None:
        config = _make_source_config()
        handler = ReutersMCPHandler(config)
        article = {
            "id": "",
            "title": "No ID Article",
            "content": "",
            "author": "",
            "published_date": "",
            "section": "",
            "language": "",
            "source": "",
            "source_url": "",
        }
        item = handler.to_item(article)
        assert item.id
        assert item.id != ""
        assert "-" in item.id

    def test_to_item_source_url_falls_back_to_id(self) -> None:
        config = _make_source_config()
        handler = ReutersMCPHandler(config)
        article = {
            "id": "reuters-news-001",
            "title": "Test",
            "content": "",
            "author": "",
            "published_date": "",
            "section": "",
            "language": "",
            "source": "",
            "source_url": "",
        }
        item = handler.to_item(article)
        assert item.source_url == "reuters-news-001"

    def test_map_article_falls_back_to_reuters_source(self) -> None:
        config = _make_source_config()
        handler = ReutersMCPHandler(config)
        mapped = handler._map_article({"id": "x", "headline": "Y"})
        assert mapped["source"] == "Reuters"


# -- Auth & headers tests --------------------------------------------------


class TestReutersMCPAuth:
    """Tests for API key handling and HTTP headers."""

    def test_api_key_sent_as_bearer_header(self) -> None:
        config = _make_source_config(api_key="reuters-key-123")
        handler = ReutersMCPHandler(config)
        resp = _make_response(SAMPLE_RESPONSE)

        with patch("httpx.post", return_value=resp) as mock_post:
            handler.fetch(limit=5)

        headers = mock_post.call_args[1].get("headers", {})
        assert headers.get("Authorization") == "Bearer reuters-key-123"

    def test_no_bearer_header_when_key_empty(self) -> None:
        """When api_key is empty, fetch returns early without HTTP call."""
        config = _make_source_config(api_key="")
        handler = ReutersMCPHandler(config)

        with patch("httpx.post", return_value=_make_response(SAMPLE_RESPONSE)) as mock_post:
            articles = handler.fetch(limit=5)

        mock_post.assert_not_called()
        assert articles == []

    def test_with_env_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AUTOINFO_REUTERS_API_KEY", "env-reuters-key")
        config = SourceConfig(
            name="reuters_mcp",
            type="reuters_mcp",
            url="https://api.reuters.com/content/v1/search",
            settings={},
        )
        handler = ReutersMCPHandler(config)
        assert handler.api_key == "env-reuters-key"

    def test_settings_key_takes_precedence_over_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AUTOINFO_REUTERS_API_KEY", "env-reuters-key")
        config = _make_source_config(api_key="settings-reuters-key")
        handler = ReutersMCPHandler(config)
        assert handler.api_key == "settings-reuters-key"

    def test_accept_header_present(self) -> None:
        config = _make_source_config()
        handler = ReutersMCPHandler(config)
        resp = _make_response(SAMPLE_RESPONSE)

        with patch("httpx.post", return_value=resp) as mock_post:
            handler.fetch(limit=5)

        headers = mock_post.call_args[1].get("headers", {})
        assert headers.get("Accept") == "application/json"
        assert headers.get("Content-Type") == "application/json"


# -- Error handling tests --------------------------------------------------


class TestReutersMCPErrors:
    """Tests for error handling and graceful degradation."""

    def test_401_returns_empty_and_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO)
        config = _make_source_config()
        handler = ReutersMCPHandler(config)
        resp = _make_error_response(401)

        with patch("httpx.post", return_value=resp):
            articles = handler.fetch(limit=10)

        assert articles == []
        assert "enterprise" in caplog.text.lower() or "401" in caplog.text.lower()

    def test_403_returns_empty(self) -> None:
        config = _make_source_config()
        handler = ReutersMCPHandler(config)
        resp = _make_error_response(403)

        with patch("httpx.post", return_value=resp):
            articles = handler.fetch(limit=10)

        assert articles == []

    def test_429_rate_limit_returns_empty(self) -> None:
        config = _make_source_config()
        handler = ReutersMCPHandler(config)
        resp = _make_error_response(429)

        with patch("httpx.post", return_value=resp):
            articles = handler.fetch(limit=10)

        assert articles == []

    def test_500_returns_empty(self) -> None:
        config = _make_source_config()
        handler = ReutersMCPHandler(config)
        resp = _make_error_response(500)

        with patch("httpx.post", return_value=resp):
            articles = handler.fetch(limit=10)

        assert articles == []

    def test_non_json_response_returns_empty(self) -> None:
        config = _make_source_config()
        handler = ReutersMCPHandler(config)
        resp = httpx.Response(
            200,
            content=b"<html>Not JSON</html>",
            request=httpx.Request("POST", "https://api.reuters.com/"),
        )

        with patch("httpx.post", return_value=resp):
            articles = handler.fetch(limit=10)

        assert articles == []

    def test_unexpected_response_structure_returns_empty(self) -> None:
        config = _make_source_config()
        handler = ReutersMCPHandler(config)
        resp = _make_response({"unexpected": "structure"})

        with patch("httpx.post", return_value=resp):
            articles = handler.fetch(limit=10)

        assert articles == []

    def test_handler_without_config_returns_empty_on_fetch(self) -> None:
        handler = ReutersMCPHandler()

        with patch("httpx.post") as mock_post:
            articles = handler.fetch(limit=10)

        mock_post.assert_not_called()
        assert articles == []


# -- _extract_items helper tests -------------------------------------------


class TestExtractItems:
    """Tests for the ``_extract_items`` helper."""

    def test_data_items_shape(self) -> None:
        result = _extract_items({"data": {"items": [{"a": 1}, {"b": 2}]}})
        assert result == [{"a": 1}, {"b": 2}]

    def test_items_top_level(self) -> None:
        result = _extract_items({"items": [{"a": 1}]})
        assert result == [{"a": 1}]

    def test_results_shape(self) -> None:
        result = _extract_items({"results": [{"a": 1}]})
        assert result == [{"a": 1}]

    def test_top_level_list(self) -> None:
        result = _extract_items([{"a": 1}, {"b": 2}])
        assert result == [{"a": 1}, {"b": 2}]

    def test_wrap_single_dict_in_data(self) -> None:
        result = _extract_items({"data": {"a": 1}})
        assert result == [{"a": 1}]

    def test_non_dict_none(self) -> None:
        assert _extract_items("nope") is None
        assert _extract_items(42) is None

    def test_empty_dict_returns_none(self) -> None:
        assert _extract_items({}) is None


# -- Rate limiting tests ---------------------------------------------------


class TestReutersMCPRateLimit:
    """Tests for rate limiter behaviour."""

    def test_default_rps(self) -> None:
        config = _make_source_config()
        handler = ReutersMCPHandler(config)
        assert handler._rate_limit == 1.0

    def test_rate_limit_first_call_instant(self) -> None:
        import time

        config = _make_source_config()
        handler = ReutersMCPHandler(config)
        resp = _make_response(SAMPLE_RESPONSE)

        with patch("httpx.post", return_value=resp):
            t0 = time.time()
            handler.fetch(limit=5)
            elapsed = time.time() - t0

        assert elapsed < 0.3

    def test_custom_rate_limit(self) -> None:
        config = _make_source_config(rate_limit=3.0)
        handler = ReutersMCPHandler(config)
        assert handler._rate_limit == 3.0
