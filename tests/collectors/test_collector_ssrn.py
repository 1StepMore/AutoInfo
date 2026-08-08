"""Tests for the SSRN working paper handler.

Uses ``unittest.mock.patch`` to mock HTTP responses so tests are
deterministic and fast — no real API calls.

SSRN does not have a public REST API; this handler performs
best-effort HTML parsing of abstract-level metadata.

Test categories:
- Handler construction and config parsing
- Fetch with mock HTTP responses
- Field mapping correctness
- Error handling (HTTP errors, network errors, empty body)
- Rate limiting
- to_item conversion
- requires_key check
- Empty / edge-case handling
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import httpx

from autoinfo.collectors.ssrn import SSRNHandler
from autoinfo.models import Item

# ---------------------------------------------------------------------------
# Sample SSRN search result HTML
# ---------------------------------------------------------------------------

SAMPLE_SSRN_HTML: str = (
    """<!DOCTYPE html>
<html>
<head><title>SSRN Search Results</title></head>
<body>
<div class="results">
  <div class="result">
    <h3><a href="/sol3/papers.cfm?abstract_id=3542186">"""
    """The Impact of Minimum Wage on Employment: Evidence from the Fast-Food Industry</a></h3>
    <p class="authors">by David Card, Alan B. Krueger</p>
    <p class="abstract">This paper examines the effect of minimum wage increases on employment """
    """in the fast-food industry using a difference-in-differences approach. We find no evidence """
    """that minimum wage increases reduce employment.</p>
    <p class="date">Posted: 15 Jan 2022</p>
  </div>
  <div class="result">
    <h3><a href="/sol3/papers.cfm?abstract_id=1234567">"""
    """Behavioral Economics and Public Policy</a></h3>
    <p class="authors">by Richard H. Thaler, Cass R. Sunstein</p>
    <p class="abstract">This paper explores how insights from behavioral economics can improve """
    """the design and implementation of public policies, with applications to retirement """
    """savings, health care, and environmental regulation.</p>
    <p class="date">Posted: March 3, 2021</p>
  </div>
</div>
</body>
</html>"""
)

SAMPLE_SSRN_HTML_EMPTY: str = """<!DOCTYPE html>
<html>
<head><title>SSRN Search Results</title></head>
<body>
<div class="results">
  <p>No results found for your query.</p>
</div>
</body>
</html>"""

SAMPLE_SSRN_HTML_SINGLE: str = """<!DOCTYPE html>
<html>
<body>
<a href="/sol3/papers.cfm?abstract_id=999888">Single Paper: A Test of Market Efficiency</a>
by Eugene F. Fama
Post: 5 Jun 2023
This paper tests the efficient market hypothesis using daily stock return data from 1963 to 2022.
</body>
</html>"""

SAMPLE_SSRN_HTML_MISSING_FIELDS: str = """<!DOCTYPE html>
<html>
<body>
<a href="/sol3/papers.cfm?abstract_id=111222">Untitled Paper</a>
</body>
</html>"""

SAMPLE_SSRN_HTML_MALFORMED: str = "<html><body>Not a valid search results page</body></html>"


# ---------------------------------------------------------------------------
# Helper: create a mock httpx.Response
# ---------------------------------------------------------------------------


def _mock_response(html: str, status_code: int = 200) -> MagicMock:
    """Create a mock httpx.Response that returns the given HTML body."""
    mock = MagicMock(spec=httpx.Response)
    mock.text = html
    mock.status_code = status_code
    mock.raise_for_status.return_value = None
    return mock


# ---------------------------------------------------------------------------
# Tests: handler existence and construction
# ---------------------------------------------------------------------------


class TestSSRNHandlerExists:
    """Verify the handler class is importable and constructable."""

    def test_handler_is_importable(self) -> None:
        """SSRNHandler should be accessible from the module."""
        assert SSRNHandler is not None

    def test_creates_with_default_config(self) -> None:
        """Handler instantiates with empty config dict."""
        handler = SSRNHandler({})
        assert handler.source_type == "ssrn"
        assert handler.config == {}
        assert handler.query == ""
        assert handler.max_rps == 0.5

    def test_creates_with_full_config(self) -> None:
        """Handler picks up all config keys correctly."""
        config = {
            "query": "behavioral economics",
            "max_rps": 1.0,
        }
        handler = SSRNHandler(config)
        assert handler.config == config
        assert handler.query == "behavioral economics"
        assert handler.max_rps == 1.0

    def test_source_type_is_ssrn(self) -> None:
        """The source_type class attribute must be 'ssrn'."""
        assert SSRNHandler.source_type == "ssrn"

    def test_subclass_of_base_handler(self) -> None:
        """SSRNHandler should be a subclass of BaseHandler."""
        from autoinfo.collectors.base import BaseHandler

        assert issubclass(SSRNHandler, BaseHandler)

    def test_creates_with_none_config(self) -> None:
        """Handler instantiates with None config (uses empty dict)."""
        handler = SSRNHandler(None)  # type: ignore[arg-type]
        assert handler.config == {}
        assert handler.query == ""


# ---------------------------------------------------------------------------
# Tests: fetch returns a list
# ---------------------------------------------------------------------------


class TestSSRNFetch:
    """Tests for the fetch method."""

    @patch("autoinfo.collectors.ssrn.httpx.get")
    def test_fetch_returns_list(self, mock_get: MagicMock) -> None:
        """fetch() should return a list of dicts."""
        mock_get.return_value = _mock_response(SAMPLE_SSRN_HTML)

        handler = SSRNHandler()
        items = handler.fetch(query="minimum wage", limit=10)

        assert isinstance(items, list)
        assert len(items) == 2

    @patch("autoinfo.collectors.ssrn.httpx.get")
    def test_fetch_each_item_is_dict(self, mock_get: MagicMock) -> None:
        """Each returned item must be a dict."""
        mock_get.return_value = _mock_response(SAMPLE_SSRN_HTML)

        handler = SSRNHandler()
        items = handler.fetch(query="minimum wage", limit=10)

        for item in items:
            assert isinstance(item, dict)

    @patch("autoinfo.collectors.ssrn.httpx.get")
    def test_fetch_respects_limit(self, mock_get: MagicMock) -> None:
        """fetch should respect the limit argument."""
        mock_get.return_value = _mock_response(SAMPLE_SSRN_HTML)

        handler = SSRNHandler()
        items = handler.fetch(query="minimum wage", limit=1)

        assert len(items) == 1

    @patch("autoinfo.collectors.ssrn.httpx.get")
    def test_fetch_uses_correct_endpoint(self, mock_get: MagicMock) -> None:
        """fetch should call the SSRN search page with correct params."""
        mock_get.return_value = _mock_response(SAMPLE_SSRN_HTML)

        handler = SSRNHandler()
        handler.fetch(query="behavioral economics", limit=5)

        mock_get.assert_called_once()
        call_args = mock_get.call_args
        url = call_args[0][0] if call_args[0] else ""
        assert "papers.ssrn.com/sol3/results.cfm" in url
        assert "txtKeywords=behavioral+economics" in url

    @patch("autoinfo.collectors.ssrn.httpx.get")
    def test_fetch_uses_configured_query(self, mock_get: MagicMock) -> None:
        """When no query argument is passed, uses self.query."""
        mock_get.return_value = _mock_response(SAMPLE_SSRN_HTML)

        handler = SSRNHandler({"query": "configured query"})
        handler.fetch(limit=5)

        call_args = mock_get.call_args
        url = call_args[0][0] if call_args[0] else ""
        assert "txtKeywords=configured+query" in url

    @patch("autoinfo.collectors.ssrn.httpx.get")
    def test_fetch_query_argument_overrides_config(self, mock_get: MagicMock) -> None:
        """Passing query as argument should override config.query."""
        mock_get.return_value = _mock_response(SAMPLE_SSRN_HTML)

        handler = SSRNHandler({"query": "configured query"})
        handler.fetch(query="overridden query", limit=5)

        call_args = mock_get.call_args
        url = call_args[0][0] if call_args[0] else ""
        assert "txtKeywords=overridden+query" in url


# ---------------------------------------------------------------------------
# Tests: empty response / edge cases
# ---------------------------------------------------------------------------


class TestSSRNFetchEmpty:
    """Tests for empty or no-result responses."""

    @patch("autoinfo.collectors.ssrn.httpx.get")
    def test_fetch_handles_empty_results(self, mock_get: MagicMock) -> None:
        """An empty results HTML should return an empty list."""
        mock_get.return_value = _mock_response(SAMPLE_SSRN_HTML_EMPTY)

        handler = SSRNHandler()
        items = handler.fetch(query="NONEXISTENT_QUERY_99999", limit=10)

        assert items == []

    @patch("autoinfo.collectors.ssrn.httpx.get")
    def test_fetch_handles_malformed_html(self, mock_get: MagicMock) -> None:
        """Malformed HTML without abstract links should return empty list."""
        mock_get.return_value = _mock_response(SAMPLE_SSRN_HTML_MALFORMED)

        handler = SSRNHandler()
        items = handler.fetch(query="test", limit=10)

        assert items == []

    def test_fetch_limit_zero_returns_empty(self) -> None:
        """A limit of 0 should result in an empty list without API call."""
        handler = SSRNHandler({"query": "test"})
        items = handler.fetch(query="test", limit=0)

        assert items == []

    def test_fetch_empty_query_returns_empty(self) -> None:
        """With an empty query, fetch should return empty list and log warning."""
        handler = SSRNHandler()
        items = handler.fetch(query="", limit=10)

        assert items == []

    def test_fetch_empty_query_no_config_returns_empty(self) -> None:
        """With no query passed and no config query, return empty."""
        handler = SSRNHandler({})
        items = handler.fetch(limit=10)

        assert items == []


# ---------------------------------------------------------------------------
# Tests: field mapping
# ---------------------------------------------------------------------------


class TestSSRNFieldMapping:
    """Tests for parsing SSRN HTML into standardised item format."""

    @patch("autoinfo.collectors.ssrn.httpx.get")
    def test_field_mapping_id(self, mock_get: MagicMock) -> None:
        """id should come from abstract_id in the URL."""
        mock_get.return_value = _mock_response(SAMPLE_SSRN_HTML_SINGLE)

        handler = SSRNHandler()
        items = handler.fetch(query="test", limit=10)

        assert items[0]["id"] == "999888"

    @patch("autoinfo.collectors.ssrn.httpx.get")
    def test_field_mapping_title(self, mock_get: MagicMock) -> None:
        """title should be extracted from link text."""
        mock_get.return_value = _mock_response(SAMPLE_SSRN_HTML_SINGLE)

        handler = SSRNHandler()
        items = handler.fetch(query="test", limit=10)

        assert "Market Efficiency" in items[0]["title"]

    @patch("autoinfo.collectors.ssrn.httpx.get")
    def test_field_mapping_source_url(self, mock_get: MagicMock) -> None:
        """source_url should be the SSRN paper page."""
        mock_get.return_value = _mock_response(SAMPLE_SSRN_HTML_SINGLE)

        handler = SSRNHandler()
        items = handler.fetch(query="test", limit=10)

        assert items[0]["source_url"] == "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=999888"

    @patch("autoinfo.collectors.ssrn.httpx.get")
    def test_field_mapping_abstract_id(self, mock_get: MagicMock) -> None:
        """abstract_id should match the URL parameter."""
        mock_get.return_value = _mock_response(SAMPLE_SSRN_HTML_SINGLE)

        handler = SSRNHandler()
        items = handler.fetch(query="test", limit=10)

        assert items[0]["abstract_id"] == "999888"

    @patch("autoinfo.collectors.ssrn.httpx.get")
    def test_field_mapping_authors(self, mock_get: MagicMock) -> None:
        """authors should be extracted when present."""
        mock_get.return_value = _mock_response(SAMPLE_SSRN_HTML)

        handler = SSRNHandler()
        items = handler.fetch(query="minimum wage", limit=10)

        assert len(items[0].get("authors", [])) > 0

    @patch("autoinfo.collectors.ssrn.httpx.get")
    def test_field_mapping_all_expected_fields_present(self, mock_get: MagicMock) -> None:
        """Every returned item must have all expected keys."""
        mock_get.return_value = _mock_response(SAMPLE_SSRN_HTML)

        handler = SSRNHandler()
        items = handler.fetch(query="minimum wage", limit=10)

        expected_fields = {
            "id", "title", "content", "authors",
            "published_date", "source_url", "abstract_id",
        }
        for item in items:
            for field in expected_fields:
                assert field in item, f"Item missing field: {field}"

    @patch("autoinfo.collectors.ssrn.httpx.get")
    def test_field_mapping_missing_fields(self, mock_get: MagicMock) -> None:
        """When fields are missing, they should default to empty values."""
        mock_get.return_value = _mock_response(SAMPLE_SSRN_HTML_MISSING_FIELDS)

        handler = SSRNHandler()
        items = handler.fetch(query="test", limit=10)

        assert len(items) >= 1
        assert items[0]["content"] == ""
        assert items[0]["authors"] == []

    @patch("autoinfo.collectors.ssrn.httpx.get")
    def test_field_mapping_multiple_papers(self, mock_get: MagicMock) -> None:
        """Multiple papers should all be extracted with unique IDs."""
        mock_get.return_value = _mock_response(SAMPLE_SSRN_HTML)

        handler = SSRNHandler()
        items = handler.fetch(query="minimum wage", limit=10)

        assert len(items) == 2
        ids = {item["id"] for item in items}
        assert len(ids) == 2  # no duplicates
        assert "3542186" in ids
        assert "1234567" in ids

    @patch("autoinfo.collectors.ssrn.httpx.get")
    def test_field_mapping_deduplicates_abstract_ids(self, mock_get: MagicMock) -> None:
        """Duplicate abstract IDs in HTML should be deduped."""
        dup_html = """<html><body>
<a href="/sol3/papers.cfm?abstract_id=111">Paper One</a>
<a href="/sol3/papers.cfm?abstract_id=111">Paper One Again</a>
<a href="/sol3/papers.cfm?abstract_id=222">Paper Two</a>
</body></html>"""
        mock_get.return_value = _mock_response(dup_html)

        handler = SSRNHandler()
        items = handler.fetch(query="test", limit=10)

        assert len(items) == 2


# ---------------------------------------------------------------------------
# Tests: error handling (graceful degradation)
# ---------------------------------------------------------------------------


class TestSSRNErrorHandling:
    """Tests for HTTP errors, empty body, and network failures."""

    @patch("autoinfo.collectors.ssrn.httpx.get")
    def test_fetch_http_error_returns_empty(self, mock_get: MagicMock) -> None:
        """HTTP errors should return empty list."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server error",
            request=MagicMock(),
            response=MagicMock(status_code=500),
        )
        mock_get.return_value = mock_response

        handler = SSRNHandler()
        items = handler.fetch(query="test", limit=10)

        assert items == []

    @patch("autoinfo.collectors.ssrn.httpx.get")
    def test_fetch_network_error_returns_empty(self, mock_get: MagicMock) -> None:
        """Network errors should return empty list."""
        mock_get.side_effect = httpx.NetworkError("Connection refused")

        handler = SSRNHandler()
        items = handler.fetch(query="test", limit=10)

        assert items == []

    @patch("autoinfo.collectors.ssrn.httpx.get")
    def test_fetch_timeout_returns_empty(self, mock_get: MagicMock) -> None:
        """Timeout errors should return empty list gracefully."""
        mock_get.side_effect = httpx.TimeoutException(
            "Request timed out",
            request=MagicMock(),
        )

        handler = SSRNHandler()
        items = handler.fetch(query="test", limit=10)

        assert items == []

    @patch("autoinfo.collectors.ssrn.httpx.get")
    def test_fetch_empty_html_handled_gracefully(self, mock_get: MagicMock) -> None:
        """If SSRN returns empty HTML, handle gracefully with empty list."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.text = ""
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = SSRNHandler()
        items = handler.fetch(query="test", limit=10)

        assert items == []

    @patch("autoinfo.collectors.ssrn.httpx.get")
    def test_fetch_malformed_item_gets_empty_defaults(self, mock_get: MagicMock) -> None:
        """A malformed item with missing fields gets empty string defaults."""
        response = _mock_response(SAMPLE_SSRN_HTML_MALFORMED)
        mock_get.return_value = response

        handler = SSRNHandler()
        items = handler.fetch(query="test", limit=10)

        # Malformed HTML with no abstract links → empty list
        assert items == []


# ---------------------------------------------------------------------------
# Tests: rate limiting
# ---------------------------------------------------------------------------


class TestSSRNRateLimit:
    """Tests for rate limiter behaviour."""

    @patch("autoinfo.collectors.ssrn.httpx.get")
    def test_rate_limit_first_call_instant(self, mock_get: MagicMock) -> None:
        """First call should not block (no previous request recorded)."""
        mock_get.return_value = _mock_response(SAMPLE_SSRN_HTML_EMPTY)

        handler = SSRNHandler()

        t0 = time.time()
        handler.fetch(query="test", limit=5)
        elapsed = time.time() - t0

        assert elapsed < 0.3  # should be near-instant

    @patch("autoinfo.collectors.ssrn.httpx.get")
    def test_rate_limit_enforces_min_interval(self, mock_get: MagicMock) -> None:
        """Back-to-back calls should be spaced by at least 1/max_rps."""
        mock_get.return_value = _mock_response(SAMPLE_SSRN_HTML_EMPTY)

        handler = SSRNHandler({"max_rps": 5})
        assert handler.max_rps == 5.0

        handler.fetch(query="test", limit=5)  # warms _last_request_time
        t0 = time.time()
        handler.fetch(query="test", limit=5)  # should wait
        elapsed = time.time() - t0

        min_interval = 1.0 / handler.max_rps  # 0.2 s
        assert elapsed >= min_interval * 0.9  # 10% tolerance


# ---------------------------------------------------------------------------
# Tests: to_item conversion
# ---------------------------------------------------------------------------


class TestSSRNToItem:
    """Tests for ``SSRNHandler.to_item()``."""

    def test_to_item_complete(self) -> None:
        """A fully populated paper dict converts to a correct Item."""
        handler = SSRNHandler()
        paper = {
            "id": "3542186",
            "title": "The Impact of Minimum Wage on Employment",
            "content": "This paper examines the effect of minimum wage increases.",
            "authors": ["David Card", "Alan B. Krueger"],
            "published_date": "15 Jan 2022",
            "source_url": "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3542186",
            "abstract_id": "3542186",
        }

        item = handler.to_item(paper)

        assert isinstance(item, Item)
        assert item.id == "3542186"
        assert item.source_name == "ssrn"
        assert item.source_type == "ssrn"
        assert item.source_platform == "ssrn"
        assert item.source_url == "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3542186"
        assert item.title == "The Impact of Minimum Wage on Employment"
        assert item.content == "This paper examines the effect of minimum wage increases."
        assert item.content_type == "text"
        assert item.collected_at == "15 Jan 2022"
        assert "ssrn_abstract_id" in item.raw_data
        assert item.raw_data["ssrn_abstract_id"] == "3542186"
        assert item.raw_data["authors"] == ["David Card", "Alan B. Krueger"]
        assert item.raw_data["published_date"] == "15 Jan 2022"

    def test_to_item_empty_id_uses_uuid(self) -> None:
        """When id is empty, a UUID should be generated as the item id."""
        handler = SSRNHandler()
        paper = {
            "id": "",
            "title": "No ID",
            "content": "",
            "authors": [],
            "published_date": "",
            "source_url": "",
            "abstract_id": "",
        }

        item = handler.to_item(paper)

        assert item.id
        assert item.id != ""
        assert "-" in item.id  # UUID contains hyphens

    def test_to_item_empty_source_url_handled(self) -> None:
        """When source_url is empty, it defaults to empty string."""
        handler = SSRNHandler()
        paper = {
            "id": "123",
            "title": "No URL",
            "content": "",
            "authors": [],
            "published_date": "",
            "source_url": "",
            "abstract_id": "123",
        }

        item = handler.to_item(paper)

        assert item.source_url == ""

    def test_to_item_minimal_paper(self) -> None:
        """A paper dict with only id and title converts correctly."""
        handler = SSRNHandler()
        paper = {
            "id": "42",
            "title": "Minimal",
            "content": "",
            "authors": [],
            "published_date": "",
            "source_url": "",
            "abstract_id": "42",
        }

        item = handler.to_item(paper)

        assert item.id == "42"
        assert item.title == "Minimal"
        assert item.source_type == "ssrn"


# ---------------------------------------------------------------------------
# Tests: requires_key
# ---------------------------------------------------------------------------


class TestSSRNRequiresKey:
    """Tests for requires_key static method."""

    def test_requires_key_returns_false(self) -> None:
        """SSRN search is public — requires_key should return False."""
        assert SSRNHandler.requires_key() is False


# ---------------------------------------------------------------------------
# Tests: note method
# ---------------------------------------------------------------------------


class TestSSRNNote:
    """Tests for the note static method."""

    def test_note_returns_api_limitation_warning(self) -> None:
        """note() should mention SSRN's lack of a public API."""
        note = SSRNHandler.note()
        assert note is not None
        assert "public" in note.lower() or "API" in note

    def test_note_mentions_html_parsing(self) -> None:
        """note() should mention best-effort HTML parsing."""
        note = SSRNHandler.note()
        assert note is not None
        assert "HTML" in note or "best-effort" in note.lower() or "abstract" in note.lower()
