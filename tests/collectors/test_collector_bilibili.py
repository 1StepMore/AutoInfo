"""Tests for the Bilibili (B站) search handler.

Uses ``unittest.mock.patch`` to mock HTTP responses so tests are
deterministic and fast — no real API calls.

Test categories:
- Handler construction and config parsing
- Fetch with mock HTTP responses (search/all/v2 primary endpoint)
- Fetch with fallback (search/v2) when primary fails
- Field mapping correctness (both endpoints)
- Error handling (HTTP errors, network errors, non-JSON, Bilibili error codes)
- Anti-scraping blocking (403 response) — graceful empty list return
- to_item conversion
- requires_app_review check
- Empty query / limit=0 edge cases
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from autoinfo.collectors.bilibili import BilibiliHandler
from autoinfo.models import Item

# ---------------------------------------------------------------------------
# Sample Bilibili search/all/v2 API response (primary endpoint)
# ---------------------------------------------------------------------------

SAMPLE_SEARCH_ALL_RESPONSE: dict[str, Any] = {
    "code": 0,
    "message": "0",
    "data": {
        "seid": "abc123",
        "page": 1,
        "pagesize": 20,
        "numResults": 2,
        "numPages": 1,
        "result": {
            "video": [
                {
                    "type": "video",
                    "aid": 170001,
                    "bvid": "BV1xx411c7mD",
                    "title": "大模型入门教程",
                    "description": "从零开始学习大语言模型的基础知识。",
                    "author": "AI研习社",
                    "mid": 10001,
                    "pic": "https://i0.hdslb.com/bfs/archive/abc123.jpg",
                    "created": 1700000000,
                    "stat": {
                        "view": 50000,
                        "danmaku": 300,
                        "reply": 120,
                        "favorite": 2000,
                        "coin": 1500,
                        "share": 500,
                        "like": 3000,
                    },
                },
                {
                    "type": "video",
                    "aid": 170002,
                    "bvid": "BV1yy422c8nE",
                    "title": "深度学习实战",
                    "description": "动手实践深度学习项目。",
                    "author": "码农日记",
                    "mid": 20002,
                    "pic": "https://i0.hdslb.com/bfs/archive/def456.jpg",
                    "created": 1699999999,
                    "stat": {"view": 30000, "danmaku": 150, "reply": 80, "favorite": 1000},
                },
            ],
        },
    },
}

SAMPLE_SEARCH_ALL_RESPONSE_FLAT: dict[str, Any] = {
    "code": 0,
    "message": "0",
    "data": {
        "result": [
            {
                "type": "video",
                "aid": 170003,
                "bvid": "BV1zz333d9oF",
                "title": "AI最新进展",
                "description": "2024年AI领域最新研究进展。",
                "author": "科技观察",
                "mid": 30003,
                "pic": "https://i0.hdslb.com/bfs/archive/ghi789.jpg",
                "created": 1700000100,
                "stat": {"view": 15000},
            },
            {
                "type": "article",
                "aid": 170004,
                "title": "Not a video",
                "description": "This should be filtered out",
                "author": "Writer",
            },
        ],
    },
}

SAMPLE_SEARCH_ALL_SINGLE: dict[str, Any] = {
    "code": 0,
    "message": "0",
    "data": {
        "result": {
            "video": [
                {
                    "type": "video",
                    "aid": 100001,
                    "bvid": "BV1aa111c7aA",
                    "title": "Python教程",
                    "description": "Python编程入门。",
                    "author": "Python之禅",
                    "mid": 40004,
                    "pic": "https://i0.hdslb.com/bfs/archive/jkl012.jpg",
                    "created": 1699999999,
                    "stat": {"view": 80000},
                },
            ],
        },
    },
}

SAMPLE_SEARCH_ALL_EMPTY: dict[str, Any] = {
    "code": 0,
    "message": "0",
    "data": {
        "numResults": 0,
        "numPages": 0,
        "result": {},
    },
}

SAMPLE_SEARCH_ALL_NO_DESCRIPTION: dict[str, Any] = {
    "code": 0,
    "data": {
        "result": {
            "video": [
                {
                    "type": "video",
                    "aid": 200001,
                    "bvid": "BV1bb222d8bB",
                    "title": "No Description Video",
                    "author": "Test UP",
                    "mid": 50005,
                    "pic": "",
                    "created": 1700000000,
                    "stat": {},
                },
            ],
        },
    },
}

SAMPLE_SEARCH_ALL_MISSING_STAT: dict[str, Any] = {
    "code": 0,
    "data": {
        "result": {
            "video": [
                {
                    "type": "video",
                    "aid": 200002,
                    "bvid": "BV1cc333e9cC",
                    "title": "No Stats Video",
                    "description": "Video without stat dict.",
                    "author": "NoStats",
                    "mid": 60006,
                    "pic": "https://example.com/thumb.jpg",
                    "created": 1700000100,
                },
            ],
        },
    },
}

# ---------------------------------------------------------------------------
# Sample Bilibili search/v2 API response (fallback endpoint)
# ---------------------------------------------------------------------------

SAMPLE_SEARCH_V2_RESPONSE: dict[str, Any] = {
    "code": 0,
    "data": {
        "page": 1,
        "pagesize": 20,
        "numResults": 1,
        "numPages": 1,
        "result": [
            {
                "type": "video",
                "aid": 300001,
                "bvid": "BV1dd444f0dD",
                "title": "Kubernetes实战",
                "description": "K8s从入门到精通。",
                "author": "云原生之路",
                "mid": 70007,
                "pic": "https://i0.hdslb.com/bfs/archive/mno345.jpg",
                "pubdate": 1700000000,
                "play": 25000,
            },
        ],
    },
}

SAMPLE_SEARCH_V2_EMPTY: dict[str, Any] = {
    "code": 0,
    "data": {
        "numResults": 0,
        "result": [],
    },
}

# ---------------------------------------------------------------------------
# Bilibili error responses
# ---------------------------------------------------------------------------

SAMPLE_BILIBILI_ERROR: dict[str, Any] = {
    "code": -400,
    "message": "请求错误",
    "data": None,
}

SAMPLE_BILIBILI_RATE_LIMIT: dict[str, Any] = {
    "code": -412,
    "message": "请求被拦截",
    "data": None,
}

# ---------------------------------------------------------------------------
# Helper: create a mock httpx.Response
# ---------------------------------------------------------------------------


def _mock_response(data: dict[str, Any], status_code: int = 200) -> MagicMock:
    """Create a mock httpx.Response that returns the given JSON data."""
    mock = MagicMock(spec=httpx.Response)
    mock.json.return_value = data
    mock.raise_for_status.return_value = None
    return mock


# ---------------------------------------------------------------------------
# Tests: handler existence and construction
# ---------------------------------------------------------------------------


class TestBilibiliHandlerExists:
    """Verify the handler class is importable and constructable."""

    def test_handler_is_importable(self) -> None:
        """BilibiliHandler should be accessible from bilibili module."""
        assert BilibiliHandler is not None

    def test_creates_with_default_config(self) -> None:
        """Handler instantiates with empty config dict."""
        handler = BilibiliHandler({})
        assert handler.source_type == "bilibili"
        assert handler.config == {}
        assert handler.query == ""

    def test_creates_with_full_config(self) -> None:
        """Handler picks up config keys correctly."""
        config = {
            "query": "大模型",
            "user_agent": "MyCustomAgent/1.0",
        }
        handler = BilibiliHandler(config)
        assert handler.config == config
        assert handler.query == "大模型"

    def test_source_type_is_bilibili(self) -> None:
        """The source_type class attribute must be 'bilibili'."""
        assert BilibiliHandler.source_type == "bilibili"

    def test_subclass_of_base_handler(self) -> None:
        """BilibiliHandler should be a subclass of BaseHandler."""
        from autoinfo.collectors.base import BaseHandler

        assert issubclass(BilibiliHandler, BaseHandler)

    def test_requires_app_review_returns_true(self) -> None:
        """Bilibili's anti-scraping measures require app review."""
        assert BilibiliHandler.requires_app_review() is True


# ---------------------------------------------------------------------------
# Tests: fetch returns a list (primary endpoint)
# ---------------------------------------------------------------------------


class TestBilibiliFetch:
    """Tests for the fetch method with search/all/v2 (primary endpoint)."""

    @patch("autoinfo.collectors.bilibili.httpx.get")
    def test_fetch_returns_list(self, mock_get: MagicMock) -> None:
        """fetch() should return a list of dicts."""
        mock_get.return_value = _mock_response(SAMPLE_SEARCH_ALL_RESPONSE)

        handler = BilibiliHandler({"query": "大模型"})
        items = handler.fetch(limit=10)

        assert isinstance(items, list)
        assert len(items) == 2

    @patch("autoinfo.collectors.bilibili.httpx.get")
    def test_fetch_each_item_is_dict(self, mock_get: MagicMock) -> None:
        """Each returned item must be a dict."""
        mock_get.return_value = _mock_response(SAMPLE_SEARCH_ALL_RESPONSE)

        handler = BilibiliHandler({"query": "大模型"})
        items = handler.fetch(limit=10)

        for item in items:
            assert isinstance(item, dict)

    @patch("autoinfo.collectors.bilibili.httpx.get")
    def test_fetch_respects_limit(self, mock_get: MagicMock) -> None:
        """fetch should respect the limit argument."""
        mock_get.return_value = _mock_response(SAMPLE_SEARCH_ALL_RESPONSE)

        handler = BilibiliHandler({"query": "大模型"})
        items = handler.fetch(limit=1)

        assert len(items) == 1

    @patch("autoinfo.collectors.bilibili.httpx.get")
    def test_fetch_uses_correct_endpoint(self, mock_get: MagicMock) -> None:
        """fetch should call the search/all/v2 endpoint with correct params."""
        mock_get.return_value = _mock_response(SAMPLE_SEARCH_ALL_RESPONSE)

        handler = BilibiliHandler({"query": "大模型"})
        handler.fetch(limit=5)

        mock_get.assert_called()
        call_args = mock_get.call_args
        url = call_args[0][0] if call_args[0] else ""
        assert "api.bilibili.com/x/web-interface/search/all/v2" in url
        assert "keyword" in str(call_args.kwargs.get("params", {}))

    @patch("autoinfo.collectors.bilibili.httpx.get")
    def test_fetch_uses_user_agent(self, mock_get: MagicMock) -> None:
        """fetch should include a Chrome User-Agent header."""
        mock_get.return_value = _mock_response(SAMPLE_SEARCH_ALL_RESPONSE)

        handler = BilibiliHandler({"query": "大模型"})
        handler.fetch(limit=5)

        call_kwargs = mock_get.call_args.kwargs
        headers = call_kwargs.get("headers", {})
        assert "User-Agent" in headers
        assert "Chrome" in headers["User-Agent"]

    @patch("autoinfo.collectors.bilibili.httpx.get")
    def test_fetch_accepts_custom_user_agent(self, mock_get: MagicMock) -> None:
        """When user_agent is in config, use it instead of default."""
        mock_get.return_value = _mock_response(SAMPLE_SEARCH_ALL_RESPONSE)

        handler = BilibiliHandler({"query": "test", "user_agent": "MyBot/2.0"})
        handler.fetch(limit=5)

        headers = mock_get.call_args.kwargs.get("headers", {})
        assert headers["User-Agent"] == "MyBot/2.0"

    @patch("autoinfo.collectors.bilibili.httpx.get")
    def test_fetch_filters_non_video_types_flat(self, mock_get: MagicMock) -> None:
        """When response uses flat list, only video-type items are returned."""
        mock_get.return_value = _mock_response(SAMPLE_SEARCH_ALL_RESPONSE_FLAT)

        handler = BilibiliHandler({"query": "AI"})
        items = handler.fetch(limit=10)

        # Should only contain the video item, not the article
        assert len(items) == 1
        assert items[0]["id"] == "170003"


# ---------------------------------------------------------------------------
# Tests: fetch via fallback endpoint
# ---------------------------------------------------------------------------


class TestBilibiliFetchFallback:
    """Tests for fallback to search/v2 when primary fails."""

    @patch("autoinfo.collectors.bilibili.httpx.get")
    def test_fallback_on_primary_http_error(self, mock_get: MagicMock) -> None:
        """When search/all/v2 returns 500, fall back to search/v2."""
        # First call (search/all/v2) fails with 500
        error_response = MagicMock(spec=httpx.Response)
        error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server error",
            request=MagicMock(),
            response=MagicMock(status_code=500),
        )
        # Second call (search/v2 fallback) succeeds
        success_response = _mock_response(SAMPLE_SEARCH_V2_RESPONSE)

        mock_get.side_effect = [error_response, success_response]

        handler = BilibiliHandler({"query": "Kubernetes"})
        items = handler.fetch(limit=10)

        assert len(items) == 1
        assert items[0]["title"] == "Kubernetes实战"
        assert mock_get.call_count == 2

    @patch("autoinfo.collectors.bilibili.httpx.get")
    def test_fallback_on_primary_network_error(self, mock_get: MagicMock) -> None:
        """When search/all/v2 times out, fall back to search/v2."""
        mock_get.side_effect = [
            httpx.NetworkError("Connection refused"),
            _mock_response(SAMPLE_SEARCH_V2_RESPONSE),
        ]

        handler = BilibiliHandler({"query": "Kubernetes"})
        items = handler.fetch(limit=10)

        assert len(items) == 1
        assert items[0]["title"] == "Kubernetes实战"

    @patch("autoinfo.collectors.bilibili.httpx.get")
    def test_empty_list_when_both_endpoints_fail(self, mock_get: MagicMock) -> None:
        """When both primary and fallback fail, return empty list."""
        mock_get.side_effect = httpx.NetworkError("Connection refused")

        handler = BilibiliHandler({"query": "大模型"})
        items = handler.fetch(limit=10)

        assert items == []

    @patch("autoinfo.collectors.bilibili.httpx.get")
    def test_empty_list_when_both_return_errors(self, mock_get: MagicMock) -> None:
        """When primary and fallback both return Bilibili errors, return empty."""
        mock_get.side_effect = [
            _mock_response(SAMPLE_BILIBILI_ERROR),
            _mock_response(SAMPLE_BILIBILI_ERROR),
        ]

        handler = BilibiliHandler({"query": "test"})
        items = handler.fetch(limit=10)

        assert items == []


# ---------------------------------------------------------------------------
# Tests: empty response / missing query
# ---------------------------------------------------------------------------


class TestBilibiliFetchEmpty:
    """Tests for empty or no-result responses."""

    @patch("autoinfo.collectors.bilibili.httpx.get")
    def test_fetch_handles_empty_results(self, mock_get: MagicMock) -> None:
        """An empty result dict should return an empty list."""
        mock_get.return_value = _mock_response(SAMPLE_SEARCH_ALL_EMPTY)

        handler = BilibiliHandler({"query": "NONEXISTENT_QUERY_99999"})
        items = handler.fetch(limit=10)

        assert items == []

    @patch("autoinfo.collectors.bilibili.httpx.get")
    def test_fetch_handles_missing_result_key(self, mock_get: MagicMock) -> None:
        """Response without a 'result' key should return empty list."""
        mock_get.return_value = _mock_response({
            "code": 0,
            "data": {"seid": "abc", "numResults": 0},
        })

        handler = BilibiliHandler({"query": "test"})
        items = handler.fetch(limit=10)

        assert items == []

    def test_fetch_limit_zero_returns_empty(self) -> None:
        """A limit of 0 should result in an empty list without API call."""
        handler = BilibiliHandler({"query": "test"})
        items = handler.fetch(limit=0)

        assert items == []

    def test_fetch_empty_query_returns_empty(self) -> None:
        """With an empty query, fetch should return empty list and log warning."""
        handler = BilibiliHandler({"query": ""})
        items = handler.fetch(limit=10)

        assert items == []


# ---------------------------------------------------------------------------
# Tests: field mapping (search/all/v2 primary endpoint)
# ---------------------------------------------------------------------------


class TestBilibiliFieldMapping:
    """Tests for mapping Bilibili JSON fields to AutoInfo item format."""

    @patch("autoinfo.collectors.bilibili.httpx.get")
    def test_field_mapping_id(self, mock_get: MagicMock) -> None:
        """id should come from the aid field."""
        mock_get.return_value = _mock_response(SAMPLE_SEARCH_ALL_SINGLE)

        handler = BilibiliHandler({"query": "Python"})
        items = handler.fetch(limit=10)

        assert items[0]["id"] == "100001"

    @patch("autoinfo.collectors.bilibili.httpx.get")
    def test_field_mapping_title(self, mock_get: MagicMock) -> None:
        """title should come from the title field."""
        mock_get.return_value = _mock_response(SAMPLE_SEARCH_ALL_SINGLE)

        handler = BilibiliHandler({"query": "Python"})
        items = handler.fetch(limit=10)

        assert items[0]["title"] == "Python教程"

    @patch("autoinfo.collectors.bilibili.httpx.get")
    def test_field_mapping_content(self, mock_get: MagicMock) -> None:
        """content should come from the description field."""
        mock_get.return_value = _mock_response(SAMPLE_SEARCH_ALL_SINGLE)

        handler = BilibiliHandler({"query": "Python"})
        items = handler.fetch(limit=10)

        assert items[0]["content"] == "Python编程入门。"

    @patch("autoinfo.collectors.bilibili.httpx.get")
    def test_field_mapping_author(self, mock_get: MagicMock) -> None:
        """author should come from the author field."""
        mock_get.return_value = _mock_response(SAMPLE_SEARCH_ALL_SINGLE)

        handler = BilibiliHandler({"query": "Python"})
        items = handler.fetch(limit=10)

        assert items[0]["author"] == "Python之禅"

    @patch("autoinfo.collectors.bilibili.httpx.get")
    def test_field_mapping_published_date(self, mock_get: MagicMock) -> None:
        """published_date should be an ISO format timestamp from created field."""
        mock_get.return_value = _mock_response(SAMPLE_SEARCH_ALL_SINGLE)

        handler = BilibiliHandler({"query": "Python"})
        items = handler.fetch(limit=10)

        # Unix timestamp 1699999999 → ISO 8601
        assert items[0]["published_date"] is not None
        assert "2023" in items[0]["published_date"]

    @patch("autoinfo.collectors.bilibili.httpx.get")
    def test_field_mapping_source_url(self, mock_get: MagicMock) -> None:
        """source_url should be https://www.bilibili.com/video/av{aid}."""
        mock_get.return_value = _mock_response(SAMPLE_SEARCH_ALL_SINGLE)

        handler = BilibiliHandler({"query": "Python"})
        items = handler.fetch(limit=10)

        assert items[0]["source_url"] == "https://www.bilibili.com/video/av100001"

    @patch("autoinfo.collectors.bilibili.httpx.get")
    def test_field_mapping_view_count(self, mock_get: MagicMock) -> None:
        """view_count should come from stat.view."""
        mock_get.return_value = _mock_response(SAMPLE_SEARCH_ALL_SINGLE)

        handler = BilibiliHandler({"query": "Python"})
        items = handler.fetch(limit=10)

        assert items[0]["view_count"] == 80000

    @patch("autoinfo.collectors.bilibili.httpx.get")
    def test_field_mapping_image_url(self, mock_get: MagicMock) -> None:
        """image_url should come from the pic field."""
        mock_get.return_value = _mock_response(SAMPLE_SEARCH_ALL_SINGLE)

        handler = BilibiliHandler({"query": "Python"})
        items = handler.fetch(limit=10)

        assert items[0]["image_url"] == "https://i0.hdslb.com/bfs/archive/jkl012.jpg"

    @patch("autoinfo.collectors.bilibili.httpx.get")
    def test_field_mapping_bvid(self, mock_get: MagicMock) -> None:
        """bvid should come from the bvid field."""
        mock_get.return_value = _mock_response(SAMPLE_SEARCH_ALL_SINGLE)

        handler = BilibiliHandler({"query": "Python"})
        items = handler.fetch(limit=10)

        assert items[0]["bvid"] == "BV1aa111c7aA"

    @patch("autoinfo.collectors.bilibili.httpx.get")
    def test_field_mapping_missing_description(self, mock_get: MagicMock) -> None:
        """When description is missing, content should be empty string."""
        mock_get.return_value = _mock_response(SAMPLE_SEARCH_ALL_NO_DESCRIPTION)

        handler = BilibiliHandler({"query": "test"})
        items = handler.fetch(limit=10)

        assert items[0]["content"] == ""

    @patch("autoinfo.collectors.bilibili.httpx.get")
    def test_field_mapping_missing_stat(self, mock_get: MagicMock) -> None:
        """When stat dict is missing, view_count should be 0."""
        mock_get.return_value = _mock_response(SAMPLE_SEARCH_ALL_MISSING_STAT)

        handler = BilibiliHandler({"query": "test"})
        items = handler.fetch(limit=10)

        assert items[0]["view_count"] == 0

    @patch("autoinfo.collectors.bilibili.httpx.get")
    def test_field_mapping_all_expected_fields_present(self, mock_get: MagicMock) -> None:
        """Every returned item must have all expected keys."""
        mock_get.return_value = _mock_response(SAMPLE_SEARCH_ALL_SINGLE)

        handler = BilibiliHandler({"query": "Python"})
        items = handler.fetch(limit=10)

        expected_fields = {
            "id", "bvid", "title", "content", "author",
            "published_date", "source_url", "view_count", "image_url",
        }
        for item in items:
            for field in expected_fields:
                assert field in item, f"Item missing field: {field}"


# ---------------------------------------------------------------------------
# Tests: field mapping (search/v2 fallback endpoint)
# ---------------------------------------------------------------------------


class TestBilibiliFieldMappingV2:
    """Tests for mapped fields from the search/v2 fallback endpoint."""

    @patch("autoinfo.collectors.bilibili.httpx.get")
    def test_v2_field_mapping_play_count(self, mock_get: MagicMock) -> None:
        """view_count should come from the 'play' field in search/v2."""
        # Primary fails, fallback succeeds
        error_resp = MagicMock(spec=httpx.Response)
        error_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server error", request=MagicMock(), response=MagicMock(status_code=500),
        )
        success_resp = _mock_response(SAMPLE_SEARCH_V2_RESPONSE)
        mock_get.side_effect = [error_resp, success_resp]

        handler = BilibiliHandler({"query": "Kubernetes"})
        items = handler.fetch(limit=10)

        assert items[0]["view_count"] == 25000

    @patch("autoinfo.collectors.bilibili.httpx.get")
    def test_v2_field_mapping_all_fields(self, mock_get: MagicMock) -> None:
        """All expected fields should be present in search/v2 results."""
        error_resp = MagicMock(spec=httpx.Response)
        error_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server error", request=MagicMock(), response=MagicMock(status_code=500),
        )
        success_resp = _mock_response(SAMPLE_SEARCH_V2_RESPONSE)
        mock_get.side_effect = [error_resp, success_resp]

        handler = BilibiliHandler({"query": "Kubernetes"})
        items = handler.fetch(limit=10)

        assert items[0]["id"] == "300001"
        assert items[0]["bvid"] == "BV1dd444f0dD"
        assert items[0]["title"] == "Kubernetes实战"
        assert items[0]["content"] == "K8s从入门到精通。"
        assert items[0]["author"] == "云原生之路"
        assert items[0]["source_url"] == "https://www.bilibili.com/video/av300001"
        assert items[0]["view_count"] == 25000


# ---------------------------------------------------------------------------
# Tests: error handling (graceful degradation)
# ---------------------------------------------------------------------------


class TestBilibiliErrorHandling:
    """Tests for HTTP errors, anti-scraping blocking, and non-JSON responses."""

    @patch("autoinfo.collectors.bilibili.httpx.get")
    def test_bilibili_error_code_returns_empty(self, mock_get: MagicMock) -> None:
        """When Bilibili returns a non-zero code, treat as error."""
        mock_get.return_value = _mock_response(SAMPLE_BILIBILI_ERROR)

        handler = BilibiliHandler({"query": "test"})
        items = handler.fetch(limit=10)

        assert items == []

    @patch("autoinfo.collectors.bilibili.httpx.get")
    def test_bilibili_rate_limit_returns_empty(self, mock_get: MagicMock) -> None:
        """When Bilibili returns -412 (rate limit/block), return empty."""
        mock_get.return_value = _mock_response(SAMPLE_BILIBILI_RATE_LIMIT)

        handler = BilibiliHandler({"query": "test"})
        items = handler.fetch(limit=10)

        assert items == []

    @patch("autoinfo.collectors.bilibili.httpx.get")
    def test_http_403_blocking_returns_empty(self, mock_get: MagicMock) -> None:
        """Anti-scraping 403 should return empty list gracefully."""
        error_response = MagicMock(spec=httpx.Response)
        error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Forbidden",
            request=MagicMock(),
            response=MagicMock(status_code=403),
        )
        mock_get.return_value = error_response

        handler = BilibiliHandler({"query": "test"})
        items = handler.fetch(limit=10)

        assert items == []

    @patch("autoinfo.collectors.bilibili.httpx.get")
    def test_network_error_returns_empty(self, mock_get: MagicMock) -> None:
        """Network errors should return empty list."""
        mock_get.side_effect = httpx.NetworkError("Connection refused")

        handler = BilibiliHandler({"query": "test"})
        items = handler.fetch(limit=10)

        assert items == []

    @patch("autoinfo.collectors.bilibili.httpx.get")
    def test_timeout_returns_empty(self, mock_get: MagicMock) -> None:
        """Timeout errors should return empty list gracefully."""
        mock_get.side_effect = httpx.TimeoutException(
            "Request timed out",
            request=MagicMock(),
        )

        handler = BilibiliHandler({"query": "test"})
        items = handler.fetch(limit=10)

        assert items == []

    @patch("autoinfo.collectors.bilibili.httpx.get")
    def test_non_json_response_handled_gracefully(self, mock_get: MagicMock) -> None:
        """If API returns non-JSON, handle gracefully with empty list."""
        error_response = MagicMock(spec=httpx.Response)
        error_response.json.side_effect = ValueError("Expecting value: line 1 column 1")
        error_response.raise_for_status.return_value = None
        mock_get.return_value = error_response

        handler = BilibiliHandler({"query": "test"})
        items = handler.fetch(limit=10)

        assert items == []

    @patch("autoinfo.collectors.bilibili.httpx.get")
    def test_malformed_item_gets_empty_defaults(self, mock_get: MagicMock) -> None:
        """A malformed item with missing fields gets empty string/zero defaults."""
        response = {
            "code": 0,
            "data": {
                "result": {
                    "video": [
                        {
                            "type": "video",
                        },
                        {
                            "type": "video",
                            "aid": 999,
                            "bvid": "BV1good",
                            "title": "Good Item",
                            "description": "This one is fine.",
                            "author": "Good Author",
                            "mid": 100,
                            "pic": "https://example.com/good.jpg",
                            "created": 1700000000,
                            "stat": {"view": 42},
                        },
                    ],
                },
            },
        }

        mock = _mock_response(response)
        mock_get.return_value = mock

        handler = BilibiliHandler({"query": "test"})
        items = handler.fetch(limit=10)

        assert len(items) == 2
        assert items[0]["id"] == ""
        assert items[0]["title"] == ""
        assert items[0]["content"] == ""
        assert items[0]["view_count"] == 0
        assert items[1]["id"] == "999"
        assert items[1]["title"] == "Good Item"


# ---------------------------------------------------------------------------
# Tests: to_item conversion
# ---------------------------------------------------------------------------


class TestBilibiliToItem:
    """Tests for ``BilibiliHandler.to_item()``."""

    def test_to_item_complete(self) -> None:
        """A fully populated video dict converts to a correct Item."""
        handler = BilibiliHandler({"query": "dummy"})
        video = {
            "id": "170001",
            "bvid": "BV1xx411c7mD",
            "title": "大模型入门教程",
            "content": "从零开始学习大语言模型的基础知识。",
            "author": "AI研习社",
            "published_date": "2023-11-15T00:00:00+00:00",
            "source_url": "https://www.bilibili.com/video/av170001",
            "view_count": 50000,
            "image_url": "https://i0.hdslb.com/bfs/archive/abc123.jpg",
        }

        item = handler.to_item(video)

        assert isinstance(item, Item)
        assert item.id == "170001"
        assert item.source_name == "bilibili"
        assert item.source_type == "bilibili"
        assert item.source_platform == "bilibili"
        assert item.source_url == "https://www.bilibili.com/video/av170001"
        assert item.title == "大模型入门教程"
        assert item.content == "从零开始学习大语言模型的基础知识。"
        assert item.content_type == "text"
        assert item.collected_at == "2023-11-15T00:00:00+00:00"
        assert "video_id" in item.raw_data
        assert item.raw_data["video_id"] == "170001"
        assert item.raw_data["bvid"] == "BV1xx411c7mD"
        assert item.raw_data["author"] == "AI研习社"
        assert item.raw_data["view_count"] == 50000
        assert item.raw_data["image_url"] == "https://i0.hdslb.com/bfs/archive/abc123.jpg"

    def test_to_item_empty_id_uses_uuid(self) -> None:
        """When id is empty, a UUID should be generated as the item id."""
        handler = BilibiliHandler({"query": "dummy"})
        video = {
            "id": "",
            "bvid": "",
            "title": "No ID",
            "content": "",
            "author": "",
            "published_date": "",
            "source_url": "",
            "view_count": 0,
            "image_url": "",
        }

        item = handler.to_item(video)

        assert item.id
        assert item.id != ""
        assert "-" in item.id  # UUID contains hyphens

    def test_to_item_constructs_source_url_from_id(self) -> None:
        """When source_url is empty but id is present, construct it."""
        handler = BilibiliHandler({"query": "dummy"})
        video = {
            "id": "100001",
            "bvid": "BV1aa111c7aA",
            "title": "Test",
            "content": "",
            "author": "",
            "published_date": "",
            "source_url": "",
            "view_count": 0,
            "image_url": "",
        }

        item = handler.to_item(video)

        assert item.source_url == "https://www.bilibili.com/video/av100001"


# ---------------------------------------------------------------------------
# Tests: _map_video_all static method
# ---------------------------------------------------------------------------


class TestBilibiliMapVideoAll:
    """Tests for the _map_video_all static method."""

    def test_map_video_all_handles_empty_item(self) -> None:
        """An empty item should fall back to sensible defaults."""
        item: dict[str, Any] = {}
        result = BilibiliHandler._map_video_all(item)
        assert result["id"] == ""
        assert result["title"] == ""
        assert result["content"] == ""
        assert result["author"] == ""
        assert result["source_url"] == ""
        assert result["view_count"] == 0

    def test_map_video_all_handles_invalid_timestamp(self) -> None:
        """An invalid created timestamp should result in empty published_date."""
        item = {
            "type": "video",
            "aid": 123,
            "title": "Test",
            "created": "not_a_number",
        }
        result = BilibiliHandler._map_video_all(item)
        assert result["published_date"] == ""

    def test_map_video_all_uses_id_fallback_when_aid_missing(self) -> None:
        """When aid is missing but id is present, use id."""
        item = {
            "type": "video",
            "id": 99999,
            "title": "Test",
        }
        result = BilibiliHandler._map_video_all(item)
        assert result["id"] == "99999"
        assert result["source_url"] == "https://www.bilibili.com/video/av99999"


# ---------------------------------------------------------------------------
# Tests: _map_video static method (fallback endpoint)
# ---------------------------------------------------------------------------


class TestBilibiliMapVideo:
    """Tests for the _map_video static method."""

    def test_map_video_handles_empty_item(self) -> None:
        """An empty item should fall back to sensible defaults."""
        item: dict[str, Any] = {}
        result = BilibiliHandler._map_video(item)
        assert result["id"] == ""
        assert result["title"] == ""

    def test_map_video_uses_pubdate_field(self) -> None:
        """search/v2 uses 'pubdate' instead of 'created'."""
        item = {
            "type": "video",
            "aid": 456,
            "title": "Test V2",
            "pubdate": 1700000000,
        }
        result = BilibiliHandler._map_video(item)
        assert result["published_date"] is not None
        assert "2023" in result["published_date"]

    def test_map_video_uses_play_field_for_view_count(self) -> None:
        """search/v2 uses 'play' field for view count."""
        item = {
            "type": "video",
            "aid": 456,
            "title": "Test V2",
            "play": 15000,
        }
        result = BilibiliHandler._map_video(item)
        assert result["view_count"] == 15000

    def test_map_video_falls_back_to_stat_view(self) -> None:
        """When 'play' is missing, fall back to stat.view."""
        item = {
            "type": "video",
            "aid": 456,
            "title": "Test V2",
            "stat": {"view": 9999},
        }
        result = BilibiliHandler._map_video(item)
        assert result["view_count"] == 9999
