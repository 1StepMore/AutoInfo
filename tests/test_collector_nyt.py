"""Tests for the NYT Article Search API collector handler.

Uses ``unittest.mock.patch`` to mock HTTP responses so tests are
deterministic and fast — no real API calls.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from autoinfo.collectors.nyt import NYTHandler

# ---------------------------------------------------------------------------
# Sample NYT API response data
# ---------------------------------------------------------------------------

SAMPLE_NYT_RESPONSE: dict[str, Any] = {
    "status": "OK",
    "copyright": "Copyright (c) 2026 The New York Times Company.",
    "response": {
        "docs": [
            {
                "_id": "nyt://article/abc-123-def",
                "abstract": "The Federal Reserve raised interest rates by 0.25 percentage points on Wednesday, continuing its campaign to cool inflation.",
                "web_url": "https://www.nytimes.com/2026/03/15/business/fed-interest-rates.html",
                "headline": {
                    "main": "Fed Raises Rates Again as Inflation Fight Continues",
                    "kicker": None,
                    "print_headline": "Fed Raises Rates Again",
                },
                "pub_date": "2026-03-15T10:00:00+0000",
                "section_name": "Business",
                "subsection_name": "Economy",
                "byline": {
                    "original": "By John Smith and Jane Doe",
                    "person": [
                        {"firstname": "John", "lastname": "Smith"},
                        {"firstname": "Jane", "lastname": "Doe"},
                    ],
                },
                "document_type": "article",
                "word_count": 850,
                "source": "The New York Times",
            },
            {
                "_id": "nyt://article/def-456-ghi",
                "abstract": None,
                "web_url": "https://www.nytimes.com/2026/03/14/science/mars-rover-discovery.html",
                "headline": {
                    "main": "Mars Rover Discovers New Evidence of Ancient Water",
                },
                "pub_date": "2026-03-14T08:30:00+0000",
                "section_name": "Science",
                "subsection_name": "",
                "byline": {"original": None},
                "document_type": "article",
                "word_count": 1200,
            },
        ],
        "meta": {
            "hits": 2,
            "offset": 0,
            "time": 15,
        },
    },
}

SAMPLE_NYT_SINGLE: dict[str, Any] = {
    "status": "OK",
    "response": {
        "docs": [
            {
                "_id": "nyt://article/single-001",
                "abstract": "A breakthrough in quantum computing promises to revolutionize the field.",
                "web_url": "https://www.nytimes.com/2026/07/01/technology/quantum-breakthrough.html",
                "headline": {
                    "main": "Quantum Computing Breakthrough Stuns Researchers",
                    "print_headline": "Quantum Leap",
                },
                "pub_date": "2026-07-01T12:00:00+0000",
                "section_name": "Technology",
                "subsection_name": "Quantum Computing",
                "byline": {"original": "By Alice Wang"},
                "document_type": "article",
                "word_count": 650,
            },
        ],
        "meta": {"hits": 1, "offset": 0, "time": 8},
    },
}

SAMPLE_NYT_EMPTY: dict[str, Any] = {
    "status": "OK",
    "response": {
        "docs": [],
        "meta": {"hits": 0, "offset": 0, "time": 3},
    },
}

SAMPLE_NYT_MISSING_RESPONSE_KEY: dict[str, Any] = {
    "status": "OK",
    "copyright": "...",
}

SAMPLE_NYT_MINIMAL: dict[str, Any] = {
    "status": "OK",
    "response": {
        "docs": [
            {
                "_id": "nyt://article/min-001",
                "headline": {},
                "web_url": "",
                "pub_date": "",
            },
        ],
        "meta": {"hits": 1},
    },
}


# ---------------------------------------------------------------------------
# Helper to build a mock response
# ---------------------------------------------------------------------------


def _mock_response(data: dict[str, Any], status_code: int = 200) -> MagicMock:
    """Build a mock httpx.Response with the given JSON body."""
    mock = MagicMock(spec=httpx.Response)
    mock.json.return_value = data
    mock.raise_for_status.return_value = None
    mock.status_code = status_code
    return mock


# ---------------------------------------------------------------------------
# Tests: handler existence and construction
# ---------------------------------------------------------------------------


class TestNYTHandlerExists:
    """Verify the handler class is importable and constructable."""

    def test_handler_is_importable(self) -> None:
        """NYTHandler should be accessible from nyt module."""
        assert NYTHandler is not None

    def test_creates_with_default_config(self) -> None:
        """Handler instantiates with an empty config dict."""
        handler = NYTHandler({})
        assert handler.source_type == "nyt"
        assert handler.config == {}
        assert handler.api_key == ""

    def test_creates_with_full_config(self) -> None:
        """Handler picks up query, api_key, date filters, and sort."""
        config = {
            "query": "climate change",
            "api_key": "test-key-123",
            "begin_date": "20260101",
            "end_date": "20260730",
            "sort": "relevance",
        }
        handler = NYTHandler(config)
        assert handler.config == config
        assert handler.config["query"] == "climate change"
        assert handler.api_key == "test-key-123"
        assert handler.config["begin_date"] == "20260101"
        assert handler.config["end_date"] == "20260730"
        assert handler.config["sort"] == "relevance"

    def test_source_type_is_nyt(self) -> None:
        """The source_type class attribute must be 'nyt'."""
        assert NYTHandler.source_type == "nyt"


# ---------------------------------------------------------------------------
# Tests: fetch basic behaviour
# ---------------------------------------------------------------------------


class TestNYTFetch:
    """Tests for the fetch method."""

    @patch("autoinfo.collectors.nyt.httpx.get")
    def test_fetch_returns_list(self, mock_get: MagicMock) -> None:
        """fetch() should return a list of dicts."""
        mock_get.return_value = _mock_response(SAMPLE_NYT_RESPONSE)

        handler = NYTHandler({"api_key": "test-key"})
        items = handler.fetch(limit=10)

        assert isinstance(items, list)
        assert len(items) == 2

    @patch("autoinfo.collectors.nyt.httpx.get")
    def test_fetch_each_item_is_dict(self, mock_get: MagicMock) -> None:
        """Each returned item must be a dict."""
        mock_get.return_value = _mock_response(SAMPLE_NYT_RESPONSE)

        handler = NYTHandler({"api_key": "test-key"})
        items = handler.fetch(limit=10)

        for item in items:
            assert isinstance(item, dict)

    @patch("autoinfo.collectors.nyt.httpx.get")
    def test_fetch_respects_limit(self, mock_get: MagicMock) -> None:
        """fetch should respect the limit argument."""
        mock_get.return_value = _mock_response(SAMPLE_NYT_RESPONSE)

        handler = NYTHandler({"api_key": "test-key"})
        items = handler.fetch(limit=1)

        assert len(items) == 1

    @patch("autoinfo.collectors.nyt.httpx.get")
    def test_fetch_uses_correct_endpoint(self, mock_get: MagicMock) -> None:
        """fetch should call the NYT Article Search endpoint."""
        mock_get.return_value = _mock_response(SAMPLE_NYT_RESPONSE)

        handler = NYTHandler({"query": "interest rates", "api_key": "test-key"})
        handler.fetch(limit=5)

        mock_get.assert_called_once()
        call_args = mock_get.call_args
        url = call_args[0][0] if call_args[0] else ""
        assert "api.nytimes.com/svc/search/v2/articlesearch.json" in url
        assert "q=interest+rates" in url or "interest%20rates" in url
        assert "api-key=test-key" in url

    @patch("autoinfo.collectors.nyt.httpx.get")
    def test_fetch_limit_zero_returns_empty(self, mock_get: MagicMock) -> None:
        """A limit of 0 should result in an empty list."""
        handler = NYTHandler({"api_key": "test-key"})
        items = handler.fetch(limit=0)

        assert items == []

    @patch("autoinfo.collectors.nyt.httpx.get")
    def test_fetch_limit_negative_returns_empty(self, mock_get: MagicMock) -> None:
        """A negative limit should result in an empty list."""
        handler = NYTHandler({"api_key": "test-key"})
        items = handler.fetch(limit=-5)

        assert items == []


# ---------------------------------------------------------------------------
# Tests: missing API key
# ---------------------------------------------------------------------------


class TestNYTNoApiKey:
    """Tests for behaviour when no API key is configured."""

    @patch("autoinfo.collectors.nyt.httpx.get")
    def test_fetch_no_api_key_returns_empty(self, mock_get: MagicMock) -> None:
        """When no API key is set, fetch returns empty list and logs warning."""
        handler = NYTHandler({})
        items = handler.fetch(limit=10)
        assert items == []

    @patch("autoinfo.collectors.nyt.httpx.get")
    def test_fetch_no_api_key_does_not_make_request(self, mock_get: MagicMock) -> None:
        """When no API key, no HTTP request should be made."""
        handler = NYTHandler({})
        handler.fetch(limit=10)
        mock_get.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: empty response handling
# ---------------------------------------------------------------------------


class TestNYTFetchEmpty:
    """Tests for empty or no-result responses."""

    @patch("autoinfo.collectors.nyt.httpx.get")
    def test_fetch_handles_empty_docs(self, mock_get: MagicMock) -> None:
        """An empty docs list should return an empty list."""
        mock_get.return_value = _mock_response(SAMPLE_NYT_EMPTY)

        handler = NYTHandler({"api_key": "test-key", "query": "NONEXISTENT"})
        items = handler.fetch(limit=10)

        assert items == []

    @patch("autoinfo.collectors.nyt.httpx.get")
    def test_fetch_handles_missing_response_key(self, mock_get: MagicMock) -> None:
        """Response without 'response' key should return empty list."""
        mock_get.return_value = _mock_response(SAMPLE_NYT_MISSING_RESPONSE_KEY)

        handler = NYTHandler({"api_key": "test-key"})
        items = handler.fetch(limit=10)

        assert items == []


# ---------------------------------------------------------------------------
# Tests: field mapping
# ---------------------------------------------------------------------------


class TestNYTFieldMapping:
    """Tests for mapping NYT JSON fields to AutoInfo item format."""

    @patch("autoinfo.collectors.nyt.httpx.get")
    def test_field_mapping_id(self, mock_get: MagicMock) -> None:
        """id should come from the '_id' field."""
        mock_get.return_value = _mock_response(SAMPLE_NYT_SINGLE)

        handler = NYTHandler({"api_key": "test-key"})
        items = handler.fetch(limit=10)

        assert items[0]["id"] == "nyt://article/single-001"

    @patch("autoinfo.collectors.nyt.httpx.get")
    def test_field_mapping_title(self, mock_get: MagicMock) -> None:
        """title should come from headline.main."""
        mock_get.return_value = _mock_response(SAMPLE_NYT_SINGLE)

        handler = NYTHandler({"api_key": "test-key"})
        items = handler.fetch(limit=10)

        assert items[0]["title"] == "Quantum Computing Breakthrough Stuns Researchers"

    @patch("autoinfo.collectors.nyt.httpx.get")
    def test_field_mapping_content_from_abstract(self, mock_get: MagicMock) -> None:
        """content should come from the 'abstract' field."""
        mock_get.return_value = _mock_response(SAMPLE_NYT_SINGLE)

        handler = NYTHandler({"api_key": "test-key"})
        items = handler.fetch(limit=10)

        assert items[0]["content"] == "A breakthrough in quantum computing promises to revolutionize the field."

    @patch("autoinfo.collectors.nyt.httpx.get")
    def test_field_mapping_none_abstract_becomes_empty(self, mock_get: MagicMock) -> None:
        """None abstract should become empty string."""
        mock_get.return_value = _mock_response(SAMPLE_NYT_RESPONSE)

        handler = NYTHandler({"api_key": "test-key"})
        items = handler.fetch(limit=10)

        # Second item has abstract: None
        assert items[1]["content"] == ""

    @patch("autoinfo.collectors.nyt.httpx.get")
    def test_field_mapping_section(self, mock_get: MagicMock) -> None:
        """section should come from section_name."""
        mock_get.return_value = _mock_response(SAMPLE_NYT_SINGLE)

        handler = NYTHandler({"api_key": "test-key"})
        items = handler.fetch(limit=10)

        assert items[0]["section"] == "Technology"
        assert items[0]["subsection"] == "Quantum Computing"

    @patch("autoinfo.collectors.nyt.httpx.get")
    def test_field_mapping_empty_subsection(self, mock_get: MagicMock) -> None:
        """Empty subsection_name should map to empty string."""
        mock_get.return_value = _mock_response(SAMPLE_NYT_RESPONSE)

        handler = NYTHandler({"api_key": "test-key"})
        items = handler.fetch(limit=10)

        assert items[1]["subsection"] == ""

    @patch("autoinfo.collectors.nyt.httpx.get")
    def test_field_mapping_published_date(self, mock_get: MagicMock) -> None:
        """published_date should match pub_date."""
        mock_get.return_value = _mock_response(SAMPLE_NYT_SINGLE)

        handler = NYTHandler({"api_key": "test-key"})
        items = handler.fetch(limit=10)

        assert items[0]["published_date"] == "2026-07-01T12:00:00+0000"

    @patch("autoinfo.collectors.nyt.httpx.get")
    def test_field_mapping_source_url(self, mock_get: MagicMock) -> None:
        """source_url should come from web_url."""
        mock_get.return_value = _mock_response(SAMPLE_NYT_SINGLE)

        handler = NYTHandler({"api_key": "test-key"})
        items = handler.fetch(limit=10)

        assert items[0]["source_url"] == "https://www.nytimes.com/2026/07/01/technology/quantum-breakthrough.html"

    @patch("autoinfo.collectors.nyt.httpx.get")
    def test_field_mapping_byline(self, mock_get: MagicMock) -> None:
        """byline should come from byline.original."""
        mock_get.return_value = _mock_response(SAMPLE_NYT_SINGLE)

        handler = NYTHandler({"api_key": "test-key"})
        items = handler.fetch(limit=10)

        assert items[0]["byline"] == "By Alice Wang"

    @patch("autoinfo.collectors.nyt.httpx.get")
    def test_field_mapping_word_count(self, mock_get: MagicMock) -> None:
        """word_count should match the API value."""
        mock_get.return_value = _mock_response(SAMPLE_NYT_SINGLE)

        handler = NYTHandler({"api_key": "test-key"})
        items = handler.fetch(limit=10)

        assert items[0]["word_count"] == 650

    @patch("autoinfo.collectors.nyt.httpx.get")
    def test_field_mapping_document_type(self, mock_get: MagicMock) -> None:
        """document_type should match the API value."""
        mock_get.return_value = _mock_response(SAMPLE_NYT_SINGLE)

        handler = NYTHandler({"api_key": "test-key"})
        items = handler.fetch(limit=10)

        assert items[0]["document_type"] == "article"

    @patch("autoinfo.collectors.nyt.httpx.get")
    def test_field_mapping_all_expected_fields_present(self, mock_get: MagicMock) -> None:
        """Every returned item must have all expected keys."""
        mock_get.return_value = _mock_response(SAMPLE_NYT_SINGLE)

        handler = NYTHandler({"api_key": "test-key"})
        items = handler.fetch(limit=10)

        expected_fields = {
            "id", "title", "content", "section", "subsection",
            "published_date", "source_url", "byline",
            "word_count", "document_type",
        }
        for item in items:
            for field in expected_fields:
                assert field in item, f"Item missing field: {field}"

    @patch("autoinfo.collectors.nyt.httpx.get")
    def test_field_mapping_minimal_item(self, mock_get: MagicMock) -> None:
        """Minimal API doc with missing optional fields should not crash."""
        mock_get.return_value = _mock_response(SAMPLE_NYT_MINIMAL)

        handler = NYTHandler({"api_key": "test-key"})
        items = handler.fetch(limit=10)

        assert len(items) == 1
        assert items[0]["id"] == "nyt://article/min-001"
        assert items[0]["title"] == ""
        assert items[0]["content"] == ""


# ---------------------------------------------------------------------------
# Tests: error handling (graceful degradation)
# ---------------------------------------------------------------------------


class TestNYTErrorHandling:
    """Tests for HTTP errors, non-JSON responses, and network failures."""

    @patch("autoinfo.collectors.nyt.httpx.get")
    def test_fetch_http_error_returns_empty(self, mock_get: MagicMock) -> None:
        """HTTP errors should log + return empty list."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Too Many Requests",
            request=MagicMock(),
            response=MagicMock(status_code=429),
        )
        mock_get.return_value = mock_response

        handler = NYTHandler({"api_key": "test-key"})
        items = handler.fetch(limit=10)

        assert items == []

    @patch("autoinfo.collectors.nyt.httpx.get")
    def test_fetch_network_error_returns_empty(self, mock_get: MagicMock) -> None:
        """Network errors should return empty list."""
        mock_get.side_effect = httpx.NetworkError("Connection refused")

        handler = NYTHandler({"api_key": "test-key"})
        items = handler.fetch(limit=10)

        assert items == []

    @patch("autoinfo.collectors.nyt.httpx.get")
    def test_fetch_timeout_returns_empty(self, mock_get: MagicMock) -> None:
        """Timeout errors should return empty list gracefully."""
        mock_get.side_effect = httpx.TimeoutException(
            "Request timed out",
            request=MagicMock(),
        )

        handler = NYTHandler({"api_key": "test-key"})
        items = handler.fetch(limit=10)

        assert items == []

    @patch("autoinfo.collectors.nyt.httpx.get")
    def test_fetch_non_json_response_handled_gracefully(self, mock_get: MagicMock) -> None:
        """If API returns non-JSON, handle gracefully with empty list."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.side_effect = ValueError("Expecting value: line 1 column 1")
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = NYTHandler({"api_key": "test-key"})
        items = handler.fetch(limit=10)

        assert items == []

    @patch("autoinfo.collectors.nyt.httpx.get")
    def test_fetch_unexpected_error_returns_empty(self, mock_get: MagicMock) -> None:
        """Unexpected exceptions should return empty list."""
        mock_get.side_effect = RuntimeError("Something went terribly wrong")

        handler = NYTHandler({"api_key": "test-key"})
        items = handler.fetch(limit=10)

        assert items == []

    @patch("autoinfo.collectors.nyt.httpx.get")
    def test_fetch_unauthorized_error_returns_empty(self, mock_get: MagicMock) -> None:
        """401 Unauthorized should return empty list."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unauthorized",
            request=MagicMock(),
            response=MagicMock(status_code=401),
        )
        mock_get.return_value = mock_response

        handler = NYTHandler({"api_key": "test-key"})
        items = handler.fetch(limit=10)

        assert items == []


# ---------------------------------------------------------------------------
# Tests: rate limiting
# ---------------------------------------------------------------------------


class TestNYTRateLimit:
    """Tests for rate limiter behaviour."""

    @patch("autoinfo.collectors.nyt.httpx.get")
    def test_rate_limit_first_call_instant(self, mock_get: MagicMock) -> None:
        """First call should not block (no previous request recorded)."""
        mock_get.return_value = _mock_response(SAMPLE_NYT_EMPTY)

        import time
        handler = NYTHandler({"api_key": "test-key"})

        t0 = time.time()
        handler.fetch(limit=5)
        elapsed = time.time() - t0

        assert elapsed < 0.3  # should be near-instant

    @patch("autoinfo.collectors.nyt.httpx.get")
    def test_rate_limit_enforces_min_interval(self, mock_get: MagicMock) -> None:
        """Back-to-back calls should be spaced by free tier limit (~6s)."""
        import time

        mock_get.return_value = _mock_response(SAMPLE_NYT_EMPTY)

        handler = NYTHandler({"api_key": "test-key"})
        handler.fetch(limit=5)  # warms _last_request_time
        t0 = time.time()
        handler.fetch(limit=5)  # should wait ~6s
        elapsed = time.time() - t0

        # Free tier: 10 req/min → 1/0.167 ≈ 6.0 s. Allow ± std tolerance.
        assert elapsed >= 5.4  # 10% tolerance on 6s


# ---------------------------------------------------------------------------
# Tests: date and sort parameters
# ---------------------------------------------------------------------------


class TestNYTDateFilters:
    """Tests for date range and sort parameters in API requests."""

    @patch("autoinfo.collectors.nyt.httpx.get")
    def test_fetch_includes_begin_date(self, mock_get: MagicMock) -> None:
        """begin_date config should appear in URL query params."""
        mock_get.return_value = _mock_response(SAMPLE_NYT_EMPTY)

        handler = NYTHandler({
            "api_key": "test-key",
            "query": "elections",
            "begin_date": "20260101",
        })
        handler.fetch(limit=10)

        call_url = mock_get.call_args[0][0]
        assert "begin_date=20260101" in call_url

    @patch("autoinfo.collectors.nyt.httpx.get")
    def test_fetch_includes_end_date(self, mock_get: MagicMock) -> None:
        """end_date config should appear in URL query params."""
        mock_get.return_value = _mock_response(SAMPLE_NYT_EMPTY)

        handler = NYTHandler({
            "api_key": "test-key",
            "query": "elections",
            "end_date": "20260730",
        })
        handler.fetch(limit=10)

        call_url = mock_get.call_args[0][0]
        assert "end_date=20260730" in call_url

    @patch("autoinfo.collectors.nyt.httpx.get")
    def test_fetch_includes_sort_param(self, mock_get: MagicMock) -> None:
        """sort config should appear in URL query params."""
        mock_get.return_value = _mock_response(SAMPLE_NYT_EMPTY)

        handler = NYTHandler({
            "api_key": "test-key",
            "query": "technology",
            "sort": "relevance",
        })
        handler.fetch(limit=10)

        call_url = mock_get.call_args[0][0]
        assert "sort=relevance" in call_url

    @patch("autoinfo.collectors.nyt.httpx.get")
    def test_fetch_default_sort_is_newest(self, mock_get: MagicMock) -> None:
        """Default sort should be 'newest'."""
        mock_get.return_value = _mock_response(SAMPLE_NYT_EMPTY)

        handler = NYTHandler({"api_key": "test-key", "query": "news"})
        handler.fetch(limit=10)

        call_url = mock_get.call_args[0][0]
        assert "sort=newest" in call_url


# ---------------------------------------------------------------------------
# Tests: to_item conversion
# ---------------------------------------------------------------------------


class TestNYTToItem:
    """Tests for ``NYTHandler.to_item()``."""

    def test_to_item_complete(self) -> None:
        """A fully populated article dict converts to a correct Item."""
        from autoinfo.models import Item

        handler = NYTHandler({"api_key": "test-key"})
        article = {
            "id": "nyt://article/single-001",
            "title": "Quantum Computing Breakthrough Stuns Researchers",
            "content": "A breakthrough in quantum computing.",
            "section": "Technology",
            "subsection": "Quantum Computing",
            "published_date": "2026-07-01T12:00:00+0000",
            "source_url": "https://www.nytimes.com/2026/07/01/technology/quantum-breakthrough.html",
            "byline": "By Alice Wang",
            "word_count": 650,
            "document_type": "article",
        }

        item = handler.to_item(article)

        assert isinstance(item, Item)
        assert item.id == "nyt://article/single-001"
        assert item.source_name == "nyt"
        assert item.source_type == "api"
        assert item.source_platform == "nyt"
        assert item.title == "Quantum Computing Breakthrough Stuns Researchers"
        assert item.content == "A breakthrough in quantum computing."
        assert item.content_type == "text"
        assert item.collected_at == "2026-07-01T12:00:00+0000"
        assert item.source_url == "https://www.nytimes.com/2026/07/01/technology/quantum-breakthrough.html"
        assert "section" in item.raw_data
        assert item.raw_data["section"] == "Technology"
        assert item.raw_data["subsection"] == "Quantum Computing"
        assert item.raw_data["byline"] == "By Alice Wang"
        assert item.raw_data["word_count"] == 650
        assert item.raw_data["document_type"] == "article"

    def test_to_item_empty_id_uses_uuid(self) -> None:
        """When id is empty, a UUID should be generated as the item id."""
        from autoinfo.models import Item

        handler = NYTHandler({"api_key": "test-key"})
        article = {
            "id": "",
            "title": "No ID Article",
            "content": "",
            "section": "",
            "subsection": "",
            "published_date": "",
            "source_url": "",
            "byline": "",
            "word_count": 0,
            "document_type": "",
        }

        item = handler.to_item(article)

        assert item.id
        assert item.id != ""
        assert "-" in item.id  # UUID contains hyphens

    def test_to_item_missing_fields_default_to_empty(self) -> None:
        """Missing fields in article dict should become empty defaults."""
        handler = NYTHandler({"api_key": "test-key"})
        article: dict[str, Any] = {}

        item = handler.to_item(article)

        assert item.title == ""
        assert item.content == ""
        assert item.source_url == ""
        assert isinstance(item.raw_data, dict)
