"""Tests for the Yahoo Finance RSS feed handler.

Uses ``unittest.mock.patch`` to mock feedparser responses — no real network calls.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from autoinfo.collectors.yahoo_finance import YahooFinanceHandler
from autoinfo.models import Item

# ---------------------------------------------------------------------------
# Sample feed entries
# ---------------------------------------------------------------------------

SAMPLE_ENTRIES: list[dict[str, str]] = [
    {
        "title": "AAPL Up 5% After Strong Earnings",
        "link": "https://finance.yahoo.com/news/aapl-up-5-20260101.html",
        "summary": "Apple stock rises 5% after reporting better-than-expected quarterly earnings.",
        "published": "Mon, 01 Jan 2026 10:00:00 GMT",
    },
    {
        "title": "Market Report: S&P 500 Hits New High",
        "link": "https://finance.yahoo.com/news/sp500-new-high-20260101.html",
        "summary": "The S&P 500 reached a new all-time high driven by tech sector gains.",
        "published": "Mon, 01 Jan 2026 11:00:00 GMT",
    },
]

MINIMAL_ENTRY: dict[str, str] = {
    "title": "Minimal Headline",
    "link": "https://finance.yahoo.com/news/minimal",
    "summary": "",
    "published": "",
}


# ---------------------------------------------------------------------------
# Tests: handler existence and construction
# ---------------------------------------------------------------------------


class TestYahooFinanceHandlerExists:
    """Verify the handler class is importable and constructable."""

    def test_handler_is_importable(self) -> None:
        """YahooFinanceHandler should be accessible from its module."""
        from autoinfo.collectors.yahoo_finance import YahooFinanceHandler as H
        assert H is not None

    def test_inherits_from_base_handler(self) -> None:
        """YahooFinanceHandler should inherit from BaseHandler."""
        from autoinfo.collectors.base import BaseHandler
        assert issubclass(YahooFinanceHandler, BaseHandler)

    def test_creates_with_default_name(self) -> None:
        """Handler instantiates with default source_name."""
        handler = YahooFinanceHandler()
        assert handler.source_name == "yahoo_finance"
        assert handler.source_type == "yahoo_finance"
        assert handler._handler_type == "YahooFinanceHandler"

    def test_creates_with_custom_name(self) -> None:
        """Handler instantiates with a custom source_name."""
        handler = YahooFinanceHandler(source_name="my-yahoo-finance")
        assert handler.source_name == "my-yahoo-finance"

    def test_source_type_class_attribute(self) -> None:
        """The source_type class attribute must be 'yahoo_finance'."""
        assert YahooFinanceHandler.source_type == "yahoo_finance"

    def test_handler_type_class_attribute(self) -> None:
        """The _handler_type class attribute must be 'YahooFinanceHandler'."""
        assert YahooFinanceHandler._handler_type == "YahooFinanceHandler"


# ---------------------------------------------------------------------------
# Tests: fetch returns valid items
# ---------------------------------------------------------------------------


class TestYahooFinanceFetch:
    """Tests for the fetch method with mocked feedparser."""

    @patch("autoinfo.collectors.yahoo_finance.feedparser.parse")
    def test_fetch_returns_items(self, mock_parse: MagicMock) -> None:
        """fetch() should return a list of Items."""
        mock_parse.return_value = MagicMock(
            bozo=False,
            entries=SAMPLE_ENTRIES,
        )

        handler = YahooFinanceHandler(source_name="yahoo-finance")
        items = handler.fetch("https://finance.yahoo.com/news/rssindex")

        assert isinstance(items, list)
        assert len(items) == 2

    @patch("autoinfo.collectors.yahoo_finance.feedparser.parse")
    def test_fetch_each_item_is_item_instance(self, mock_parse: MagicMock) -> None:
        """Each returned item must be an Item instance."""
        mock_parse.return_value = MagicMock(
            bozo=False,
            entries=SAMPLE_ENTRIES,
        )

        handler = YahooFinanceHandler()
        items = handler.fetch("https://finance.yahoo.com/news/rssindex")

        for item in items:
            assert isinstance(item, Item)

    @patch("autoinfo.collectors.yahoo_finance.feedparser.parse")
    def test_fetch_default_url(self, mock_parse: MagicMock) -> None:
        """Calling fetch() without URL should use the default feed URL."""
        mock_parse.return_value = MagicMock(
            bozo=False,
            entries=SAMPLE_ENTRIES,
        )

        handler = YahooFinanceHandler()
        items = handler.fetch()

        assert len(items) == 2
        # Should have used default URL
        call_args = mock_parse.call_args
        assert call_args is not None
        assert "finance.yahoo.com/news/rssindex" in str(call_args[0][0])

    @patch("autoinfo.collectors.yahoo_finance.feedparser.parse")
    def test_fetch_with_topic_url(self, mock_parse: MagicMock) -> None:
        """Passing a topic-specific URL should use that URL."""
        mock_parse.return_value = MagicMock(
            bozo=False,
            entries=[SAMPLE_ENTRIES[0]],
        )

        handler = YahooFinanceHandler()
        topic_url = "https://finance.yahoo.com/rss/headline?s=AAPL"
        items = handler.fetch(topic_url)

        assert len(items) == 1
        call_url = mock_parse.call_args[0][0] if mock_parse.call_args else ""
        assert call_url == topic_url


# ---------------------------------------------------------------------------
# Tests: field mapping
# ---------------------------------------------------------------------------


class TestYahooFinanceFieldMapping:
    """Verify correct mapping of RSS fields to Item attributes."""

    @patch("autoinfo.collectors.yahoo_finance.feedparser.parse")
    def test_title_mapping(self, mock_parse: MagicMock) -> None:
        """title should come from entry.title."""
        mock_parse.return_value = MagicMock(
            bozo=False,
            entries=[SAMPLE_ENTRIES[0]],
        )

        handler = YahooFinanceHandler()
        items = handler.fetch()
        assert items[0].title == "AAPL Up 5% After Strong Earnings"

    @patch("autoinfo.collectors.yahoo_finance.feedparser.parse")
    def test_source_url_mapping(self, mock_parse: MagicMock) -> None:
        """source_url should come from entry.link."""
        mock_parse.return_value = MagicMock(
            bozo=False,
            entries=[SAMPLE_ENTRIES[0]],
        )

        handler = YahooFinanceHandler()
        items = handler.fetch()
        assert "aapl-up-5-20260101" in items[0].source_url

    @patch("autoinfo.collectors.yahoo_finance.feedparser.parse")
    def test_content_mapping(self, mock_parse: MagicMock) -> None:
        """content should come from entry.summary."""
        mock_parse.return_value = MagicMock(
            bozo=False,
            entries=[SAMPLE_ENTRIES[0]],
        )

        handler = YahooFinanceHandler()
        items = handler.fetch()
        assert "Apple stock rises" in items[0].content

    @patch("autoinfo.collectors.yahoo_finance.feedparser.parse")
    def test_collected_at_mapping(self, mock_parse: MagicMock) -> None:
        """collected_at should be parsed from entry.published into ISO-8601."""
        mock_parse.return_value = MagicMock(
            bozo=False,
            entries=[SAMPLE_ENTRIES[0]],
        )

        handler = YahooFinanceHandler()
        items = handler.fetch()
        assert "2026" in items[0].collected_at
        assert "T" in items[0].collected_at

    @patch("autoinfo.collectors.yahoo_finance.feedparser.parse")
    def test_source_type_fields(self, mock_parse: MagicMock) -> None:
        """Items should have correct source metadata."""
        mock_parse.return_value = MagicMock(
            bozo=False,
            entries=[SAMPLE_ENTRIES[0]],
        )

        handler = YahooFinanceHandler()
        items = handler.fetch()

        assert items[0].source_name == "yahoo_finance"
        assert items[0].source_type == "yahoo_finance"
        assert items[0].source_platform == "yahoo_finance"
        assert items[0].content_type == "text"

    @patch("autoinfo.collectors.yahoo_finance.feedparser.parse")
    def test_item_has_all_required_fields(self, mock_parse: MagicMock) -> None:
        """All required Item fields must be populated."""
        mock_parse.return_value = MagicMock(
            bozo=False,
            entries=[SAMPLE_ENTRIES[0]],
        )

        handler = YahooFinanceHandler()
        items = handler.fetch()

        item = items[0]
        assert item.id
        assert item.title
        assert item.source_url
        assert item.content is not None
        assert item.collected_at
        assert item.source_name
        assert item.source_type
        assert item.source_platform
        assert item.content_type
        assert item.raw_data is not None


# ---------------------------------------------------------------------------
# Tests: description fallback
# ---------------------------------------------------------------------------


class TestYahooFinanceContentFallback:
    """Verify content fallback when summary is empty."""

    @patch("autoinfo.collectors.yahoo_finance.feedparser.parse")
    def test_content_fallback_to_description(self, mock_parse: MagicMock) -> None:
        """When summary is absent, content should come from description."""
        mock_parse.return_value = MagicMock(
            bozo=False,
            entries=[{
                "title": "Test",
                "link": "https://test.com",
                "description": "Description fallback content",
            }],
        )

        handler = YahooFinanceHandler()
        items = handler.fetch()
        assert items[0].content == "Description fallback content"

    @patch("autoinfo.collectors.yahoo_finance.feedparser.parse")
    def test_content_fallback_to_content_value(self, mock_parse: MagicMock) -> None:
        """When summary and description are absent, fall back to content[0].value."""
        mock_parse.return_value = MagicMock(
            bozo=False,
            entries=[{
                "title": "Test",
                "link": "https://test.com",
                "content": [{"value": "Content list value"}],
            }],
        )

        handler = YahooFinanceHandler()
        items = handler.fetch()
        assert items[0].content == "Content list value"

    @patch("autoinfo.collectors.yahoo_finance.feedparser.parse")
    def test_content_empty_string_when_all_absent(self, mock_parse: MagicMock) -> None:
        """When all content fields are absent, content should be empty string."""
        mock_parse.return_value = MagicMock(
            bozo=False,
            entries=[{
                "title": "Test",
                "link": "https://test.com",
            }],
        )

        handler = YahooFinanceHandler()
        items = handler.fetch()
        assert items[0].content == ""


# ---------------------------------------------------------------------------
# Tests: date parsing
# ---------------------------------------------------------------------------


class TestYahooFinanceDateParsing:
    """Verify date parsing edge cases."""

    @patch("autoinfo.collectors.yahoo_finance.feedparser.parse")
    def test_published_date_parsed(self, mock_parse: MagicMock) -> None:
        """A valid RFC 2822 date should be parsed to ISO-8601."""
        mock_parse.return_value = MagicMock(
            bozo=False,
            entries=[{
                "title": "Test",
                "link": "https://test.com",
                "published": "Mon, 15 Jan 2026 14:30:00 GMT",
            }],
        )

        handler = YahooFinanceHandler()
        items = handler.fetch()
        assert items[0].collected_at == "2026-01-15T14:30:00+00:00"

    @patch("autoinfo.collectors.yahoo_finance.feedparser.parse")
    def test_fallback_to_updated(self, mock_parse: MagicMock) -> None:
        """When published is absent, fall back to updated."""
        mock_parse.return_value = MagicMock(
            bozo=False,
            entries=[{
                "title": "Test",
                "link": "https://test.com",
                "updated": "Tue, 20 Jan 2026 08:00:00 GMT",
            }],
        )

        handler = YahooFinanceHandler()
        items = handler.fetch()
        assert "2026-01-20" in items[0].collected_at

    @patch("autoinfo.collectors.yahoo_finance.feedparser.parse")
    def test_empty_date_returns_empty_string(self, mock_parse: MagicMock) -> None:
        """When no date is present, collected_at should be empty string."""
        mock_parse.return_value = MagicMock(
            bozo=False,
            entries=[{
                "title": "Test",
                "link": "https://test.com",
            }],
        )

        handler = YahooFinanceHandler()
        items = handler.fetch()
        assert items[0].collected_at == ""


# ---------------------------------------------------------------------------
# Tests: error handling
# ---------------------------------------------------------------------------


class TestYahooFinanceErrorHandling:
    """Verify the handler fails gracefully under error conditions."""

    @patch("autoinfo.collectors.yahoo_finance.feedparser.parse")
    def test_bozo_no_entries_returns_empty(self, mock_parse: MagicMock) -> None:
        """A bozo feed with no entries should return an empty list."""
        mock_parse.return_value = MagicMock(
            bozo=True,
            entries=[],
            bozo_exception="Malformed XML",
        )

        handler = YahooFinanceHandler()
        items = handler.fetch()
        assert items == []

    @patch("autoinfo.collectors.yahoo_finance.feedparser.parse")
    def test_bozo_with_entries_still_returns_items(self, mock_parse: MagicMock) -> None:
        """A bozo feed that still has entries should still be processed."""
        mock_parse.return_value = MagicMock(
            bozo=True,
            entries=SAMPLE_ENTRIES,
        )

        handler = YahooFinanceHandler()
        items = handler.fetch()
        assert len(items) == 2

    @patch("autoinfo.collectors.yahoo_finance.feedparser.parse")
    def test_empty_entries_returns_empty(self, mock_parse: MagicMock) -> None:
        """A valid feed with zero entries should return an empty list."""
        mock_parse.return_value = MagicMock(
            bozo=False,
            entries=[],
        )

        handler = YahooFinanceHandler()
        items = handler.fetch()
        assert items == []

    @patch("autoinfo.collectors.yahoo_finance.feedparser.parse")
    def test_parse_exception_returns_empty(self, mock_parse: MagicMock) -> None:
        """When feedparser.parse raises, should return empty list."""
        mock_parse.side_effect = ConnectionError("Network unreachable")

        handler = YahooFinanceHandler()
        items = handler.fetch()
        assert items == []

    @patch("autoinfo.collectors.yahoo_finance.feedparser.parse")
    def test_malformed_entry_skipped(self, mock_parse: MagicMock) -> None:
        """An entry causing an exception during mapping should be skipped."""
        # entry without any dict methods will cause error during field access
        mock_parse.return_value = MagicMock(
            bozo=False,
            entries=[None, SAMPLE_ENTRIES[0]],
        )

        handler = YahooFinanceHandler()
        items = handler.fetch()
        assert len(items) == 1  # only the valid entry returned
        assert items[0].title == "AAPL Up 5% After Strong Earnings"


# ---------------------------------------------------------------------------
# Tests: item ID stability
# ---------------------------------------------------------------------------


class TestYahooFinanceItemId:
    """Verify item IDs are deterministic and stable."""

    def test_make_item_id_is_deterministic(self) -> None:
        """Same feed URL + link should produce the same ID."""
        from autoinfo.collectors.yahoo_finance import _make_item_id

        id1 = _make_item_id("https://finance.yahoo.com/news/rssindex", "https://finance.yahoo.com/news/1")
        id2 = _make_item_id("https://finance.yahoo.com/news/rssindex", "https://finance.yahoo.com/news/1")
        assert id1 == id2

    def test_different_links_produce_different_ids(self) -> None:
        """Different links should produce different IDs."""
        from autoinfo.collectors.yahoo_finance import _make_item_id

        id1 = _make_item_id("https://finance.yahoo.com/news/rssindex", "https://finance.yahoo.com/news/1")
        id2 = _make_item_id("https://finance.yahoo.com/news/rssindex", "https://finance.yahoo.com/news/2")
        assert id1 != id2

    @patch("autoinfo.collectors.yahoo_finance.feedparser.parse")
    def test_item_id_is_16_char_hex(self, mock_parse: MagicMock) -> None:
        """Item IDs should be 16-character hex strings."""
        mock_parse.return_value = MagicMock(
            bozo=False,
            entries=[SAMPLE_ENTRIES[0]],
        )

        handler = YahooFinanceHandler()
        items = handler.fetch()
        assert len(items[0].id) == 16
        int(items[0].id, 16)  # should not raise


# ---------------------------------------------------------------------------
# Tests: multiple items
# ---------------------------------------------------------------------------


class TestYahooFinanceMultiItem:
    """Tests involving multiple items from the feed."""

    @patch("autoinfo.collectors.yahoo_finance.feedparser.parse")
    def test_all_items_have_unique_ids(self, mock_parse: MagicMock) -> None:
        """Each item in a batch should have a unique ID."""
        mock_parse.return_value = MagicMock(
            bozo=False,
            entries=SAMPLE_ENTRIES,
        )

        handler = YahooFinanceHandler()
        items = handler.fetch()
        ids = {item.id for item in items}
        assert len(ids) == len(items)

    @patch("autoinfo.collectors.yahoo_finance.feedparser.parse")
    def test_raw_data_contains_feed_url(self, mock_parse: MagicMock) -> None:
        """raw_data should include the feed_url for provenance."""
        mock_parse.return_value = MagicMock(
            bozo=False,
            entries=[SAMPLE_ENTRIES[0]],
        )

        handler = YahooFinanceHandler()
        feed_url = "https://finance.yahoo.com/news/rssindex"
        items = handler.fetch(feed_url)
        assert items[0].raw_data.get("feed_url") == feed_url
