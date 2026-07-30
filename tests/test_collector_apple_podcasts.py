"""Tests for the Apple Podcasts / iTunes Search API handler.

Uses ``unittest.mock.patch`` to mock HTTP responses so tests are
deterministic and fast — no real API calls.

Test categories:
- Handler construction and config parsing
- Fetch with mock HTTP responses
- Field mapping correctness
- Error handling (HTTP errors, network errors, non-JSON)
- Rate limiting
- to_item conversion
- requires_key check
- Empty / edge-case handling
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from autoinfo.collectors.apple_podcasts import ApplePodcastsHandler
from autoinfo.models import Item

# ---------------------------------------------------------------------------
# Sample iTunes Search API response (podcast shows)
# ---------------------------------------------------------------------------

SAMPLE_ITUNES_RESPONSE: dict[str, Any] = {
    "resultCount": 2,
    "results": [
        {
            "wrapperType": "track",
            "kind": "podcast",
            "collectionId": 890468527,
            "trackId": 890468527,
            "artistName": "Lex Fridman",
            "collectionName": "Lex Fridman Podcast",
            "trackName": "Lex Fridman Podcast",
            "collectionCensoredName": "Lex Fridman Podcast",
            "trackCensoredName": "Lex Fridman Podcast",
            "collectionViewUrl": "https://podcasts.apple.com/us/podcast/lex-fridman-podcast/id890468527",
            "feedUrl": "https://lexfridman.com/feed/podcast/",
            "trackViewUrl": "https://podcasts.apple.com/us/podcast/lex-fridman-podcast/id890468527",
            "artworkUrl30": "https://is1-ssl.mzstatic.com/image/thumb/artwork30.jpg",
            "artworkUrl60": "https://is1-ssl.mzstatic.com/image/thumb/artwork60.jpg",
            "artworkUrl100": "https://is1-ssl.mzstatic.com/image/thumb/artwork100.jpg",
            "artworkUrl600": "https://is1-ssl.mzstatic.com/image/thumb/artwork600.jpg",
            "releaseDate": "2024-01-15T00:00:00Z",
            "collectionExplicitness": "notExplicit",
            "trackExplicitness": "notExplicit",
            "trackCount": 300,
            "country": "USA",
            "primaryGenreName": "Technology",
            "contentAdvisoryRating": "Clean",
            "genres": ["Technology", "Podcasts"],
            "genreIds": ["1318", "26"],
            "description": "Conversations about the nature of intelligence, consciousness, love, and power.",
        },
        {
            "wrapperType": "track",
            "kind": "podcast",
            "collectionId": 1384884517,
            "trackId": 1384884517,
            "artistName": "Sam Harris",
            "collectionName": "Making Sense with Sam Harris",
            "trackName": "Making Sense with Sam Harris",
            "collectionCensoredName": "Making Sense with Sam Harris",
            "trackCensoredName": "Making Sense with Sam Harris",
            "collectionViewUrl": "https://podcasts.apple.com/us/podcast/making-sense-with-sam-harris/id1384884517",
            "feedUrl": "https://samharris.org/subscribe",
            "trackViewUrl": "https://podcasts.apple.com/us/podcast/making-sense-with-sam-harris/id1384884517",
            "artworkUrl600": "https://is1-ssl.mzstatic.com/image/thumb/artwork2_600.jpg",
            "releaseDate": "2023-06-10T00:00:00Z",
            "collectionExplicitness": "notExplicit",
            "trackExplicitness": "notExplicit",
            "trackCount": 250,
            "country": "USA",
            "primaryGenreName": "Science",
            "genres": ["Science", "Society & Culture"],
            "description": "Exploring the most important questions about the mind, society, and current events.",
        },
    ],
}

SAMPLE_EMPTY_RESPONSE: dict[str, Any] = {
    "resultCount": 0,
    "results": [],
}

SAMPLE_SINGLE_RESPONSE: dict[str, Any] = {
    "resultCount": 1,
    "results": [
        {
            "wrapperType": "track",
            "kind": "podcast",
            "trackId": 123456,
            "artistName": "Test Author",
            "collectionName": "Test Podcast",
            "trackName": "Test Podcast",
            "collectionViewUrl": "https://podcasts.apple.com/us/podcast/test-podcast/id123456",
            "feedUrl": "https://feeds.example.com/test.xml",
            "releaseDate": "2025-01-01T00:00:00Z",
            "artworkUrl600": "https://example.com/artwork600.jpg",
            "primaryGenreName": "Education",
            "genres": ["Education"],
            "description": "A test podcast about testing.",
            "trackCount": 42,
            "country": "USA",
        },
    ],
}

SAMPLE_RESPONSE_NO_DESCRIPTION: dict[str, Any] = {
    "resultCount": 1,
    "results": [
        {
            "wrapperType": "track",
            "kind": "podcast",
            "trackId": 789012,
            "artistName": "NoDesc Author",
            "trackName": "No Description Podcast",
            "collectionViewUrl": "https://podcasts.apple.com/us/podcast/nodesc/id789012",
            "feedUrl": "https://feeds.example.com/nodesc.xml",
            "releaseDate": "2024-06-15T00:00:00Z",
            "primaryGenreName": "Comedy",
            "genres": ["Comedy"],
            "trackCount": 10,
            "country": "USA",
        },
    ],
}

SAMPLE_RESPONSE_MISSING_FEED_URL: dict[str, Any] = {
    "resultCount": 1,
    "results": [
        {
            "wrapperType": "track",
            "kind": "podcast",
            "trackId": 345678,
            "artistName": "NoFeed Author",
            "trackName": "No Feed URL Podcast",
            "collectionViewUrl": "https://podcasts.apple.com/us/podcast/nofeed/id345678",
            "releaseDate": "2024-03-20T00:00:00Z",
            "primaryGenreName": "News",
            "genres": ["News"],
            "description": "A podcast without a feed URL.",
            "trackCount": 5,
            "country": "GBR",
        },
    ],
}


# ---------------------------------------------------------------------------
# Helper: create a mock httpx.Response
# ---------------------------------------------------------------------------


def _mock_response(data: dict[str, Any]) -> MagicMock:
    """Create a mock httpx.Response that returns the given JSON data."""
    mock = MagicMock(spec=httpx.Response)
    mock.json.return_value = data
    mock.raise_for_status.return_value = None
    return mock


# ---------------------------------------------------------------------------
# Tests: handler existence and construction
# ---------------------------------------------------------------------------


class TestApplePodcastsHandlerExists:
    """Verify the handler class is importable and constructable."""

    def test_handler_is_importable(self) -> None:
        """ApplePodcastsHandler should be accessible from the module."""
        assert ApplePodcastsHandler is not None

    def test_creates_with_default_config(self) -> None:
        """Handler instantiates with empty config dict."""
        handler = ApplePodcastsHandler({})
        assert handler.source_type == "apple_podcasts"
        assert handler.config == {}
        assert handler.term == ""
        assert handler.country == "US"
        assert handler.entity == "podcast"
        assert handler.max_rps == 1.0

    def test_creates_with_full_config(self) -> None:
        """Handler picks up all config keys correctly."""
        config = {
            "term": "machine learning",
            "country": "GB",
            "entity": "podcast",
            "max_rps": 2.0,
        }
        handler = ApplePodcastsHandler(config)
        assert handler.config == config
        assert handler.term == "machine learning"
        assert handler.country == "GB"
        assert handler.entity == "podcast"
        assert handler.max_rps == 2.0

    def test_source_type_is_apple_podcasts(self) -> None:
        """The source_type class attribute must be 'apple_podcasts'."""
        assert ApplePodcastsHandler.source_type == "apple_podcasts"

    def test_subclass_of_base_handler(self) -> None:
        """ApplePodcastsHandler should be a subclass of BaseHandler."""
        from autoinfo.collectors.base import BaseHandler

        assert issubclass(ApplePodcastsHandler, BaseHandler)

    def test_creates_with_none_config(self) -> None:
        """Handler instantiates with None config (uses empty dict)."""
        handler = ApplePodcastsHandler(None)  # type: ignore[arg-type]
        assert handler.config == {}
        assert handler.term == ""


# ---------------------------------------------------------------------------
# Tests: fetch returns a list
# ---------------------------------------------------------------------------


class TestApplePodcastsFetch:
    """Tests for the fetch method."""

    @patch("autoinfo.collectors.apple_podcasts.httpx.get")
    def test_fetch_returns_list(self, mock_get: MagicMock) -> None:
        """fetch() should return a list of dicts."""
        mock_get.return_value = _mock_response(SAMPLE_ITUNES_RESPONSE)

        handler = ApplePodcastsHandler()
        items = handler.fetch(term="technology", limit=10)

        assert isinstance(items, list)
        assert len(items) == 2

    @patch("autoinfo.collectors.apple_podcasts.httpx.get")
    def test_fetch_each_item_is_dict(self, mock_get: MagicMock) -> None:
        """Each returned item must be a dict."""
        mock_get.return_value = _mock_response(SAMPLE_ITUNES_RESPONSE)

        handler = ApplePodcastsHandler()
        items = handler.fetch(term="technology", limit=10)

        for item in items:
            assert isinstance(item, dict)

    @patch("autoinfo.collectors.apple_podcasts.httpx.get")
    def test_fetch_respects_limit(self, mock_get: MagicMock) -> None:
        """fetch should respect the limit argument."""
        mock_get.return_value = _mock_response(SAMPLE_ITUNES_RESPONSE)

        handler = ApplePodcastsHandler()
        items = handler.fetch(term="technology", limit=1)

        assert len(items) == 1

    @patch("autoinfo.collectors.apple_podcasts.httpx.get")
    def test_fetch_uses_correct_endpoint(self, mock_get: MagicMock) -> None:
        """fetch should call the iTunes Search API with correct params."""
        mock_get.return_value = _mock_response(SAMPLE_ITUNES_RESPONSE)

        handler = ApplePodcastsHandler({"country": "GB"})
        handler.fetch(term="machine learning", limit=5)

        mock_get.assert_called_once()
        call_args = mock_get.call_args
        url = call_args[0][0] if call_args[0] else ""
        assert "itunes.apple.com/search" in url
        assert "term=machine+learning" in url
        assert "media=podcast" in url
        assert "entity=podcast" in url
        assert "country=GB" in url
        assert "limit=5" in url

    @patch("autoinfo.collectors.apple_podcasts.httpx.get")
    def test_fetch_uses_configured_term(self, mock_get: MagicMock) -> None:
        """When no term argument is passed, uses self.term."""
        mock_get.return_value = _mock_response(SAMPLE_ITUNES_RESPONSE)

        handler = ApplePodcastsHandler({"term": "configured term"})
        handler.fetch(limit=5)

        call_args = mock_get.call_args
        url = call_args[0][0] if call_args[0] else ""
        assert "term=configured+term" in url

    @patch("autoinfo.collectors.apple_podcasts.httpx.get")
    def test_fetch_term_argument_overrides_config(self, mock_get: MagicMock) -> None:
        """Passing term as argument should override config.term."""
        mock_get.return_value = _mock_response(SAMPLE_ITUNES_RESPONSE)

        handler = ApplePodcastsHandler({"term": "configured term"})
        handler.fetch(term="overridden term", limit=5)

        call_args = mock_get.call_args
        url = call_args[0][0] if call_args[0] else ""
        assert "term=overridden+term" in url


# ---------------------------------------------------------------------------
# Tests: empty response / edge cases
# ---------------------------------------------------------------------------


class TestApplePodcastsFetchEmpty:
    """Tests for empty or no-result responses."""

    @patch("autoinfo.collectors.apple_podcasts.httpx.get")
    def test_fetch_handles_empty_results(self, mock_get: MagicMock) -> None:
        """An empty results list should return an empty list."""
        mock_get.return_value = _mock_response(SAMPLE_EMPTY_RESPONSE)

        handler = ApplePodcastsHandler()
        items = handler.fetch(term="NONEXISTENT_QUERY_99999", limit=10)

        assert items == []

    @patch("autoinfo.collectors.apple_podcasts.httpx.get")
    def test_fetch_handles_missing_results_key(self, mock_get: MagicMock) -> None:
        """Response without a 'results' key should return empty list."""
        mock_get.return_value = _mock_response({"resultCount": 0})

        handler = ApplePodcastsHandler()
        items = handler.fetch(term="test", limit=10)

        assert items == []

    def test_fetch_limit_zero_returns_empty(self) -> None:
        """A limit of 0 should result in an empty list without API call."""
        handler = ApplePodcastsHandler({"term": "test"})
        items = handler.fetch(term="test", limit=0)

        assert items == []

    def test_fetch_empty_term_returns_empty(self) -> None:
        """With an empty term, fetch should return empty list and log warning."""
        handler = ApplePodcastsHandler()
        items = handler.fetch(term="", limit=10)

        assert items == []

    def test_fetch_empty_term_no_config_returns_empty(self) -> None:
        """With no term passed and no config term, return empty."""
        handler = ApplePodcastsHandler({})
        items = handler.fetch(limit=10)

        assert items == []


# ---------------------------------------------------------------------------
# Tests: field mapping
# ---------------------------------------------------------------------------


class TestApplePodcastsFieldMapping:
    """Tests for mapping iTunes JSON fields to standardised item format."""

    @patch("autoinfo.collectors.apple_podcasts.httpx.get")
    def test_field_mapping_id(self, mock_get: MagicMock) -> None:
        """id should come from trackId field."""
        mock_get.return_value = _mock_response(SAMPLE_SINGLE_RESPONSE)

        handler = ApplePodcastsHandler()
        items = handler.fetch(term="test", limit=10)

        assert items[0]["id"] == "123456"

    @patch("autoinfo.collectors.apple_podcasts.httpx.get")
    def test_field_mapping_title(self, mock_get: MagicMock) -> None:
        """title should come from trackName."""
        mock_get.return_value = _mock_response(SAMPLE_SINGLE_RESPONSE)

        handler = ApplePodcastsHandler()
        items = handler.fetch(term="test", limit=10)

        assert items[0]["title"] == "Test Podcast"

    @patch("autoinfo.collectors.apple_podcasts.httpx.get")
    def test_field_mapping_content(self, mock_get: MagicMock) -> None:
        """content should come from description field."""
        mock_get.return_value = _mock_response(SAMPLE_SINGLE_RESPONSE)

        handler = ApplePodcastsHandler()
        items = handler.fetch(term="test", limit=10)

        assert items[0]["content"] == "A test podcast about testing."

    @patch("autoinfo.collectors.apple_podcasts.httpx.get")
    def test_field_mapping_author(self, mock_get: MagicMock) -> None:
        """author should come from artistName."""
        mock_get.return_value = _mock_response(SAMPLE_SINGLE_RESPONSE)

        handler = ApplePodcastsHandler()
        items = handler.fetch(term="test", limit=10)

        assert items[0]["author"] == "Test Author"

    @patch("autoinfo.collectors.apple_podcasts.httpx.get")
    def test_field_mapping_feed_url(self, mock_get: MagicMock) -> None:
        """feed_url should come from feedUrl."""
        mock_get.return_value = _mock_response(SAMPLE_SINGLE_RESPONSE)

        handler = ApplePodcastsHandler()
        items = handler.fetch(term="test", limit=10)

        assert items[0]["feed_url"] == "https://feeds.example.com/test.xml"

    @patch("autoinfo.collectors.apple_podcasts.httpx.get")
    def test_field_mapping_published_date(self, mock_get: MagicMock) -> None:
        """published_date should come from releaseDate."""
        mock_get.return_value = _mock_response(SAMPLE_SINGLE_RESPONSE)

        handler = ApplePodcastsHandler()
        items = handler.fetch(term="test", limit=10)

        assert items[0]["published_date"] == "2025-01-01T00:00:00Z"

    @patch("autoinfo.collectors.apple_podcasts.httpx.get")
    def test_field_mapping_source_url(self, mock_get: MagicMock) -> None:
        """source_url should come from collectionViewUrl."""
        mock_get.return_value = _mock_response(SAMPLE_SINGLE_RESPONSE)

        handler = ApplePodcastsHandler()
        items = handler.fetch(term="test", limit=10)

        assert "podcasts.apple.com" in items[0]["source_url"]
        assert "id123456" in items[0]["source_url"]

    @patch("autoinfo.collectors.apple_podcasts.httpx.get")
    def test_field_mapping_genre(self, mock_get: MagicMock) -> None:
        """genre should come from primaryGenreName."""
        mock_get.return_value = _mock_response(SAMPLE_SINGLE_RESPONSE)

        handler = ApplePodcastsHandler()
        items = handler.fetch(term="test", limit=10)

        assert items[0]["genre"] == "Education"

    @patch("autoinfo.collectors.apple_podcasts.httpx.get")
    def test_field_mapping_artwork_url(self, mock_get: MagicMock) -> None:
        """artwork_url should come from artworkUrl600."""
        mock_get.return_value = _mock_response(SAMPLE_SINGLE_RESPONSE)

        handler = ApplePodcastsHandler()
        items = handler.fetch(term="test", limit=10)

        assert "artwork600.jpg" in items[0]["artwork_url"]

    @patch("autoinfo.collectors.apple_podcasts.httpx.get")
    def test_field_mapping_track_count(self, mock_get: MagicMock) -> None:
        """track_count should come from trackCount."""
        mock_get.return_value = _mock_response(SAMPLE_SINGLE_RESPONSE)

        handler = ApplePodcastsHandler()
        items = handler.fetch(term="test", limit=10)

        assert items[0]["track_count"] == 42

    @patch("autoinfo.collectors.apple_podcasts.httpx.get")
    def test_field_mapping_country(self, mock_get: MagicMock) -> None:
        """country should come from country."""
        mock_get.return_value = _mock_response(SAMPLE_SINGLE_RESPONSE)

        handler = ApplePodcastsHandler()
        items = handler.fetch(term="test", limit=10)

        assert items[0]["country"] == "USA"

    @patch("autoinfo.collectors.apple_podcasts.httpx.get")
    def test_field_mapping_all_expected_fields_present(self, mock_get: MagicMock) -> None:
        """Every returned item must have all expected keys."""
        mock_get.return_value = _mock_response(SAMPLE_SINGLE_RESPONSE)

        handler = ApplePodcastsHandler()
        items = handler.fetch(term="test", limit=10)

        expected_fields = {
            "id", "title", "content", "author", "feed_url",
            "published_date", "source_url", "genre", "genres",
            "artwork_url", "track_count", "country",
        }
        for item in items:
            for field in expected_fields:
                assert field in item, f"Item missing field: {field}"

    @patch("autoinfo.collectors.apple_podcasts.httpx.get")
    def test_field_mapping_missing_description(self, mock_get: MagicMock) -> None:
        """When description is missing, content should be empty string."""
        mock_get.return_value = _mock_response(SAMPLE_RESPONSE_NO_DESCRIPTION)

        handler = ApplePodcastsHandler()
        items = handler.fetch(term="test", limit=10)

        assert items[0]["content"] == ""

    @patch("autoinfo.collectors.apple_podcasts.httpx.get")
    def test_field_mapping_missing_feed_url(self, mock_get: MagicMock) -> None:
        """When feedUrl is missing, feed_url should be empty string."""
        mock_get.return_value = _mock_response(SAMPLE_RESPONSE_MISSING_FEED_URL)

        handler = ApplePodcastsHandler()
        items = handler.fetch(term="test", limit=10)

        assert items[0]["feed_url"] == ""
        assert items[0]["id"] == "345678"

    @patch("autoinfo.collectors.apple_podcasts.httpx.get")
    def test_field_mapping_falls_back_to_collection_name(self, mock_get: MagicMock) -> None:
        """If trackName is missing, fall back to collectionName."""
        resp = {
            "resultCount": 1,
            "results": [
                {
                    "wrapperType": "track",
                    "kind": "podcast",
                    "trackId": 999,
                    "artistName": "Fallback Author",
                    "collectionName": "Fallback Collection Name",
                    "collectionViewUrl": "https://example.com/fallback",
                    "feedUrl": "https://feeds.example.com/fallback.xml",
                    "releaseDate": "2024-01-01T00:00:00Z",
                    "primaryGenreName": "Tech",
                    "genres": ["Tech"],
                    "description": "Fallback description.",
                    "trackCount": 1,
                    "country": "USA",
                },
            ],
        }
        mock_get.return_value = _mock_response(resp)

        handler = ApplePodcastsHandler()
        items = handler.fetch(term="test", limit=10)

        assert items[0]["title"] == "Fallback Collection Name"


# ---------------------------------------------------------------------------
# Tests: error handling (graceful degradation)
# ---------------------------------------------------------------------------


class TestApplePodcastsErrorHandling:
    """Tests for HTTP errors, non-JSON responses, and network failures."""

    @patch("autoinfo.collectors.apple_podcasts.httpx.get")
    def test_fetch_http_error_returns_empty(self, mock_get: MagicMock) -> None:
        """HTTP errors should return empty list."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server error",
            request=MagicMock(),
            response=MagicMock(status_code=500),
        )
        mock_get.return_value = mock_response

        handler = ApplePodcastsHandler()
        items = handler.fetch(term="test", limit=10)

        assert items == []

    @patch("autoinfo.collectors.apple_podcasts.httpx.get")
    def test_fetch_network_error_returns_empty(self, mock_get: MagicMock) -> None:
        """Network errors should return empty list."""
        mock_get.side_effect = httpx.NetworkError("Connection refused")

        handler = ApplePodcastsHandler()
        items = handler.fetch(term="test", limit=10)

        assert items == []

    @patch("autoinfo.collectors.apple_podcasts.httpx.get")
    def test_fetch_timeout_returns_empty(self, mock_get: MagicMock) -> None:
        """Timeout errors should return empty list gracefully."""
        mock_get.side_effect = httpx.TimeoutException(
            "Request timed out",
            request=MagicMock(),
        )

        handler = ApplePodcastsHandler()
        items = handler.fetch(term="test", limit=10)

        assert items == []

    @patch("autoinfo.collectors.apple_podcasts.httpx.get")
    def test_fetch_non_json_response_handled_gracefully(self, mock_get: MagicMock) -> None:
        """If API returns non-JSON, handle gracefully with empty list."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.side_effect = ValueError("Expecting value: line 1 column 1")
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = ApplePodcastsHandler()
        items = handler.fetch(term="test", limit=10)

        assert items == []

    @patch("autoinfo.collectors.apple_podcasts.httpx.get")
    def test_fetch_malformed_item_gets_empty_defaults(self, mock_get: MagicMock) -> None:
        """A malformed item with missing fields gets empty string defaults."""
        response = {
            "resultCount": 2,
            "results": [
                {
                    # Missing trackId, trackName, etc. — gets empty defaults
                    "wrapperType": "track",
                    "kind": "podcast",
                },
                {  # Good item
                    "wrapperType": "track",
                    "kind": "podcast",
                    "trackId": 111222,
                    "artistName": "Good Author",
                    "trackName": "Good Podcast",
                    "collectionViewUrl": "https://example.com/good",
                    "feedUrl": "https://feeds.example.com/good.xml",
                    "releaseDate": "2024-01-01T00:00:00Z",
                    "primaryGenreName": "Good Genre",
                    "genres": ["Good Genre"],
                    "description": "A good podcast.",
                    "trackCount": 1,
                    "country": "USA",
                },
            ],
        }

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = response
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = ApplePodcastsHandler()
        items = handler.fetch(term="test", limit=10)

        assert len(items) == 2
        assert items[0]["id"] == ""
        assert items[0]["title"] == ""
        assert items[0]["author"] == ""
        assert items[1]["id"] == "111222"
        assert items[1]["title"] == "Good Podcast"


# ---------------------------------------------------------------------------
# Tests: rate limiting
# ---------------------------------------------------------------------------


class TestApplePodcastsRateLimit:
    """Tests for rate limiter behaviour."""

    @patch("autoinfo.collectors.apple_podcasts.httpx.get")
    def test_rate_limit_first_call_instant(self, mock_get: MagicMock) -> None:
        """First call should not block (no previous request recorded)."""
        mock_get.return_value = _mock_response(SAMPLE_EMPTY_RESPONSE)

        handler = ApplePodcastsHandler()

        t0 = time.time()
        handler.fetch(term="test", limit=5)
        elapsed = time.time() - t0

        assert elapsed < 0.3  # should be near-instant

    @patch("autoinfo.collectors.apple_podcasts.httpx.get")
    def test_rate_limit_enforces_min_interval(self, mock_get: MagicMock) -> None:
        """Back-to-back calls should be spaced by at least 1/max_rps."""
        mock_get.return_value = _mock_response(SAMPLE_EMPTY_RESPONSE)

        handler = ApplePodcastsHandler({"max_rps": 5})
        assert handler.max_rps == 5.0

        handler.fetch(term="test", limit=5)  # warms _last_request_time
        t0 = time.time()
        handler.fetch(term="test", limit=5)  # should wait
        elapsed = time.time() - t0

        min_interval = 1.0 / handler.max_rps  # 0.2 s
        assert elapsed >= min_interval * 0.9  # 10 % tolerance


# ---------------------------------------------------------------------------
# Tests: to_item conversion
# ---------------------------------------------------------------------------


class TestApplePodcastsToItem:
    """Tests for ``ApplePodcastsHandler.to_item()``."""

    def test_to_item_complete(self) -> None:
        """A fully populated show dict converts to a correct Item."""
        handler = ApplePodcastsHandler()
        show = {
            "id": "890468527",
            "title": "Lex Fridman Podcast",
            "content": "Conversations about the nature of intelligence.",
            "author": "Lex Fridman",
            "feed_url": "https://lexfridman.com/feed/podcast/",
            "published_date": "2024-01-15T00:00:00Z",
            "source_url": "https://podcasts.apple.com/us/podcast/lex-fridman-podcast/id890468527",
            "genre": "Technology",
            "genres": ["Technology", "Podcasts"],
            "artwork_url": "https://example.com/artwork600.jpg",
            "track_count": 300,
            "country": "USA",
        }

        item = handler.to_item(show)

        assert isinstance(item, Item)
        assert item.id == "890468527"
        assert item.source_name == "apple_podcasts"
        assert item.source_type == "apple_podcasts"
        assert item.source_platform == "apple_podcasts"
        assert item.source_url == "https://podcasts.apple.com/us/podcast/lex-fridman-podcast/id890468527"
        assert item.title == "Lex Fridman Podcast"
        assert item.content == "Conversations about the nature of intelligence."
        assert item.content_type == "text"
        assert item.collected_at == "2024-01-15T00:00:00Z"
        assert "apple_track_id" in item.raw_data
        assert item.raw_data["apple_track_id"] == "890468527"
        assert item.raw_data["author"] == "Lex Fridman"
        assert item.raw_data["feed_url"] == "https://lexfridman.com/feed/podcast/"
        assert item.raw_data["genre"] == "Technology"
        assert item.raw_data["genres"] == ["Technology", "Podcasts"]
        assert item.raw_data["artwork_url"] == "https://example.com/artwork600.jpg"
        assert item.raw_data["track_count"] == 300
        assert item.raw_data["country"] == "USA"

    def test_to_item_empty_id_uses_uuid(self) -> None:
        """When id is empty, a UUID should be generated as the item id."""
        handler = ApplePodcastsHandler()
        show = {
            "id": "",
            "title": "No ID",
            "content": "",
            "author": "",
            "feed_url": "",
            "published_date": "",
            "source_url": "",
            "genre": "",
            "genres": [],
            "artwork_url": "",
            "track_count": 0,
            "country": "",
        }

        item = handler.to_item(show)

        assert item.id
        assert item.id != ""
        assert "-" in item.id  # UUID contains hyphens

    def test_to_item_empty_source_url_handled(self) -> None:
        """When source_url is empty, it defaults to empty string."""
        handler = ApplePodcastsHandler()
        show = {
            "id": "123",
            "title": "No URL",
            "content": "",
            "author": "",
            "feed_url": "",
            "published_date": "",
            "source_url": "",
            "genre": "",
            "genres": [],
            "artwork_url": "",
            "track_count": 0,
            "country": "",
        }

        item = handler.to_item(show)

        assert item.source_url == ""

    def test_to_item_minimal_show(self) -> None:
        """A show dict with only id and title converts correctly."""
        handler = ApplePodcastsHandler()
        show = {
            "id": "42",
            "title": "Minimal",
            "content": "",
            "author": "",
            "feed_url": "",
            "published_date": "",
            "source_url": "",
            "genre": "",
            "genres": [],
            "artwork_url": "",
            "track_count": 0,
            "country": "",
        }

        item = handler.to_item(show)

        assert item.id == "42"
        assert item.title == "Minimal"
        assert item.source_type == "apple_podcasts"


# ---------------------------------------------------------------------------
# Tests: requires_key
# ---------------------------------------------------------------------------


class TestApplePodcastsRequiresKey:
    """Tests for requires_key static method."""

    def test_requires_key_returns_false(self) -> None:
        """iTunes Search API is free — requires_key should return False."""
        assert ApplePodcastsHandler.requires_key() is False


# ---------------------------------------------------------------------------
# Tests: note method
# ---------------------------------------------------------------------------


class TestApplePodcastsNote:
    """Tests for the note static method."""

    def test_note_returns_collection_level_warning(self) -> None:
        """note() should mention the collection-level limitation."""
        note = ApplePodcastsHandler.note()
        assert note is not None
        assert "SHOWS" in note
        assert "episodes" in note.lower()

    def test_note_mentions_feed_url(self) -> None:
        """note() should suggest using feed_url for episodes."""
        note = ApplePodcastsHandler.note()
        assert note is not None
        assert "feed_url" in note or "feedUrl" in note or "feed" in note.lower()
