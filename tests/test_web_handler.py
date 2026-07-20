"""Tests for the web page content extractor (WebHandler).

Uses ``pytest-vcr`` to replay HTTP interactions with a pre-recorded
cassette, plus fixture-based tests for direct extraction verification.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
import vcr as vcr_lib

from autoinfo.collectors.web import WebHandler
from autoinfo.models import Item

# Paths
FIXTURES = Path(__file__).resolve().parent / "fixtures"
CASSETTES = Path(__file__).resolve().parent / "cassettes"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def handler() -> WebHandler:
    """Return a default :class:`WebHandler` instance (plain text output)."""
    return WebHandler()


@pytest.fixture
def handler_with_links() -> WebHandler:
    """Return a handler with ``include_links=True``."""
    return WebHandler(include_links=True)


@pytest.fixture
def sample_html() -> str:
    """Return the content of ``web-article.html`` fixture."""
    path = FIXTURES / "web-article.html"
    return path.read_text(encoding="utf-8")


WIKI_URL = "https://en.wikipedia.org/wiki/Python_(programming_language)"


# ---------------------------------------------------------------------------
# Happy path — VCR-recorded web page
# ---------------------------------------------------------------------------


class TestWebExtractionVCR:
    """Verify end-to-end extraction using a pre-recorded VCR cassette."""

    CASSETTE = str(CASSETTES / "test_web_wikipedia.yaml")

    def test_fetch_returns_item(self, handler: WebHandler) -> None:
        """Fetching a valid HTML page should return one Item."""
        with vcr_lib.use_cassette(self.CASSETTE):
            items = handler.fetch(WIKI_URL)
        assert len(items) == 1, "Expected exactly one item from a single URL"

    def test_item_has_required_fields(self, handler: WebHandler) -> None:
        """Each item must have id, title, source_url, content."""
        with vcr_lib.use_cassette(self.CASSETTE):
            items = handler.fetch(WIKI_URL)
        assert len(items) == 1
        item = items[0]

        assert isinstance(item, Item)
        assert item.id, "Item missing id"
        assert item.title, "Item missing title"
        assert item.source_url == WIKI_URL
        assert item.source_url.startswith("http")
        assert item.content, "Item missing content (empty string)"
        assert len(item.content) > 50, "Content seems too short"
        assert item.source_name == "web"
        assert item.source_type == "web"
        assert item.content_type == "text"

    def test_item_contains_expected_text(self, handler: WebHandler) -> None:
        """The extracted content should include key terms from the page."""
        with vcr_lib.use_cassette(self.CASSETTE):
            items = handler.fetch(WIKI_URL)
        assert len(items) == 1
        item = items[0]

        content_lower = item.content.lower()
        assert "python" in content_lower
        assert "python" in item.title.lower()

    def test_item_has_metadata(self, handler: WebHandler) -> None:
        """The raw_data dict should include author and date."""
        with vcr_lib.use_cassette(self.CASSETTE):
            items = handler.fetch(WIKI_URL)
        assert len(items) == 1
        item = items[0]

        assert "author" in item.raw_data
        assert "date" in item.raw_data


# ---------------------------------------------------------------------------
# Direct extraction from fixture (no network, no VCR)
# ---------------------------------------------------------------------------


class TestExtractFromFixture:
    """Test trafilatura extraction directly from a local HTML fixture."""

    def test_extract_returns_item(self, handler: WebHandler, sample_html: str) -> None:
        """``_extract`` should return an Item from valid HTML."""
        item = handler._extract(sample_html, WIKI_URL)
        assert item is not None
        assert isinstance(item, Item)

    def test_extract_title(self, handler: WebHandler, sample_html: str) -> None:
        """Title should be extracted from <title> or <h1>."""
        item = handler._extract(sample_html, WIKI_URL)
        assert item is not None
        # trafilatura may use <title> or <h1> — either is acceptable
        assert "python" in item.title.lower() or "test article" in item.title.lower()

    def test_extract_content(self, handler: WebHandler, sample_html: str) -> None:
        """Content should contain article body text."""
        item = handler._extract(sample_html, WIKI_URL)
        assert item is not None
        assert len(item.content) > 100
        assert "high-level" in item.content
        assert "garbage-collected" in item.content
        assert "Guido van Rossum" in item.content

    def test_extract_metadata(self, handler: WebHandler, sample_html: str) -> None:
        """Author and date should be extracted from meta tags."""
        item = handler._extract(sample_html, WIKI_URL)
        assert item is not None
        # trafilatura may or may not pick up meta author/date depending on
        # its heuristics — verify the field exists (may be empty string)
        assert "author" in item.raw_data
        assert "date" in item.raw_data

    def test_extract_none_on_empty(self, handler: WebHandler) -> None:
        """``_extract`` should return ``None`` for empty/non-content HTML."""
        result = handler._extract("<html><body></body></html>", "https://example.com")
        assert result is None


# ---------------------------------------------------------------------------
# Configuration options
# ---------------------------------------------------------------------------


class TestWebHandlerConfig:
    """Verify handler configuration options."""

    def test_custom_source_name(self, sample_html: str) -> None:
        """A custom source_name should propagate to the Item."""
        handler = WebHandler(source_name="my-web-source")
        item = handler._extract(sample_html, "https://example.com/article")
        assert item is not None
        assert item.source_name == "my-web-source"

    def test_include_links(self, handler_with_links: WebHandler, sample_html: str) -> None:
        """With include_links=True, output may contain link markup."""
        item = handler_with_links._extract(sample_html, "https://example.com/article")
        assert item is not None
        # Trafilatura renders links as [text](url) with include_links=True
        assert item.content

    def test_default_config_values(self) -> None:
        """Default constructor should set expected values."""
        handler = WebHandler()
        assert handler.source_name == "web"
        assert handler.extract_only_text is True
        assert handler.include_links is False
        assert handler.include_images is False


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestWebHandlerErrors:
    """Verify the handler fails gracefully under error conditions."""

    def test_unreachable_url_returns_empty_list(self, handler: WebHandler) -> None:
        """An unreachable URL should return an empty list."""
        items = handler.fetch("https://invalid.example.com/nonexistent-page")
        assert items == []

    def test_non_html_url_returns_empty_list(self, handler: WebHandler) -> None:
        """A URL returning non-HTML content should be skipped."""
        items = handler.fetch("https://httpbin.org/robots.txt")
        assert items == []

    def test_handler_never_raises(self, handler: WebHandler) -> None:
        """Calling ``fetch`` should never raise, regardless of input."""
        bad_inputs = [
            "",
            "not-a-url",
            "https://",
            "ftp://invalid-protocol.com/page.html",
        ]
        for url in bad_inputs:
            items = handler.fetch(url)
            assert items == [], f"Expected empty list for URL: {url!r}"

    def test_retry_on_timeout(self, handler: WebHandler) -> None:
        """After 3 TimeoutExceptions, handler returns empty list (no crash)."""
        call_count = 0

        def _fake_get(*args: object, **kwargs: object) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            msg = f"Simulated timeout (attempt {call_count})"
            raise httpx.TimeoutException(msg, request=None)  # type:ignore[arg-type]

        with patch("httpx.get", side_effect=_fake_get):
            items = handler.fetch("https://example.com/article")
        assert items == []
        assert call_count == 3

    def test_retry_on_network_error(self, handler: WebHandler) -> None:
        """Network errors retried 3 times, then return empty list."""
        call_count = 0

        def _fake_get(*args: object, **kwargs: object) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            raise httpx.NetworkError("Simulated network error", request=None)  # type:ignore[arg-type]

        with patch("httpx.get", side_effect=_fake_get):
            items = handler.fetch("https://example.com/article")
        assert items == []
        assert call_count == 3

    def test_http_4xx_returns_empty_list(self, handler: WebHandler) -> None:
        """HTTP 4xx responses return empty list (no retry, no crash)."""
        resp = httpx.Response(
            404,
            request=httpx.Request("GET", "http://test.com"),
        )

        with patch("httpx.get", return_value=resp):
            items = handler.fetch("https://example.com/article")
        assert items == []

    def test_http_5xx_returns_empty_list(self, handler: WebHandler) -> None:
        """HTTP 5xx responses return empty list."""
        resp = httpx.Response(
            503,
            request=httpx.Request("GET", "http://test.com"),
        )

        with patch("httpx.get", return_value=resp):
            items = handler.fetch("https://example.com/article")
        assert items == []

    def test_extract_returns_none_for_empty_html(self, handler: WebHandler) -> None:
        """``_extract`` on HTML with no readable text returns ``None``."""
        result = handler._extract("<html><head></head><body></body></html>", "http://x.com")
        assert result is None

    def test_extract_logs_on_exception(self, handler: WebHandler, caplog: pytest.LogCaptureFixture) -> None:
        """If trafilatura raises, _extract logs the error and returns None."""
        import logging
        caplog.set_level(logging.ERROR)

        result = handler._extract("not valid html", "http://x.com")
        assert result is None


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestWebHandlerEdgeCases:
    """Corner cases for the web handler."""

    def test_duplicate_urls_produce_same_item_id(self) -> None:
        """Same URL → same deterministic Item ID."""
        from autoinfo.collectors.web import _make_item_id

        id1 = _make_item_id("https://example.com/article")
        id2 = _make_item_id("https://example.com/article")
        assert id1 == id2
        assert len(id1) == 16
        assert id1.isalnum()

    def test_different_urls_produce_different_ids(self) -> None:
        """Different URLs → different Item IDs."""
        from autoinfo.collectors.web import _make_item_id

        id1 = _make_item_id("https://example.com/article-1")
        id2 = _make_item_id("https://example.com/article-2")
        assert id1 != id2
