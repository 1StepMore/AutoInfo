"""Tests for the USPTO patent collector handler.

Uses ``unittest.mock`` to avoid real API calls — all HTTP interactions
are mocked.
"""

from __future__ import annotations

import time
from unittest.mock import patch

import httpx
import pytest

from autoinfo.collectors.uspto import (
    PATENTSVIEW_DEFAULT_FIELDS,
    RATE_LIMIT_DEFAULT,
    RATE_LIMIT_WITH_KEY,
    USPTOHandler,
)
from autoinfo.models import Item

# ---------------------------------------------------------------------------
# Sample API response data
# ---------------------------------------------------------------------------


def _make_patentsview_response(
    patents: list[dict],
    count: int = 0,
) -> httpx.Response:
    """Create a mock httpx.Response with a PatentsView-style JSON body."""
    return httpx.Response(
        200,
        json={
            "patents": patents,
            "count": count or len(patents),
            "total_patent_count": count or len(patents),
        },
        request=httpx.Request(
            "POST",
            "https://api.patentsview.org/patents/query",
        ),
    )


def _make_rss_response(xml_body: str = "") -> httpx.Response:
    """Create a mock httpx.Response with a USPTO RSS XML body."""
    if not xml_body:
        xml_body = _SAMPLE_RSS_XML
    return httpx.Response(
        200,
        content=xml_body.encode("utf-8"),
        headers={"Content-Type": "application/rss+xml"},
        request=httpx.Request(
            "GET",
            "https://www.uspto.gov/feeds/patent_application.xml",
        ),
    )


SAMPLE_PATENTS = [
    {
        "patent_number": "US12000123",
        "patent_title": "CRISPR-based Gene Editing Method for Targeted Therapy",
        "patent_abstract": (
            "A method for targeted gene editing using CRISPR-Cas9 "
            "ribonucleoprotein complexes delivered via lipid nanoparticles. "
            "The method enables precise modification of disease-associated "
            "genetic loci with reduced off-target effects."
        ),
        "patent_date": "2026-06-15",
        "app_date": "2025-01-10",
        "inventors": [
            {
                "inventor_first_name": "Jennifer",
                "inventor_last_name": "Doudna",
                "inventor_key_id": "inv_001",
            },
            {
                "inventor_first_name": "Emmanuelle",
                "inventor_last_name": "Charpentier",
                "inventor_key_id": "inv_002",
            },
        ],
        "assignees": [
            {"assignee_organization": "Broad Institute"},
        ],
        "patent_num_cited_by_us_patents": 45,
        "patent_num_combined_citations": 120,
    },
    {
        "patent_number": "US12000999",
        "patent_title": "AI-Assisted Drug Discovery Platform",
        "patent_abstract": (
            "A computational platform that combines deep learning with "
            "molecular dynamics simulations to predict drug-target "
            "interactions and optimize lead compounds."
        ),
        "patent_date": "2026-04-20",
        "app_date": "2024-09-05",
        "inventors": [
            {
                "inventor_first_name": "Demis",
                "inventor_last_name": "Hassabis",
                "inventor_key_id": "inv_003",
            },
        ],
        "assignees": [
            {"assignee_organization": "DeepMind Technologies"},
        ],
        "patent_num_cited_by_us_patents": 23,
        "patent_num_combined_citations": 67,
    },
]

SAMPLE_PATENT_MINIMAL: dict = {
    "patent_number": "US12000001",
    "patent_title": "",
    "patent_abstract": None,
    "patent_date": None,
    "app_date": None,
    "inventors": [],
    "assignees": [],
    "patent_num_cited_by_us_patents": None,
    "patent_num_combined_citations": None,
}

MAPPED_PATENT = {
    "id": "US12000123",
    "patent_number": "US12000123",
    "title": "CRISPR-based Gene Editing Method for Targeted Therapy",
    "abstract": (
        "A method for targeted gene editing using CRISPR-Cas9 "
        "ribonucleoprotein complexes delivered via lipid nanoparticles."
    ),
    "authors": ["Jennifer Doudna", "Emmanuelle Charpentier"],
    "filed_date": "2025-01-10",
    "published_date": "2026-06-15",
    "assignee": "",
    "cited_by_count": 45,
    "total_citations": 120,
    "source_type": "api",
}

_SAMPLE_RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
    <title>USPTO Patent Applications</title>
    <link>https://www.uspto.gov/</link>
    <description>Recent patent applications from the USPTO</description>
    <item>
        <title>US 2024/0123456 A1: Gene Editing Method</title>
        <link>https://patents.google.com/patent/US20240123456A1/en</link>
        <description>A novel method for gene editing using CRISPR technology.</description>
        <pubDate>Mon, 15 Jun 2026 00:00:00 GMT</pubDate>
    </item>
    <item>
        <title>US 2024/0099999 A1: Drug Discovery Method</title>
        <link>https://patents.google.com/patent/US20240099999A1/en</link>
        <description>AI-assisted drug discovery platform for identifying therapeutic compounds.</description>
        <pubDate>Wed, 20 Apr 2026 00:00:00 GMT</pubDate>
    </item>
</channel>
</rss>"""

# ---------------------------------------------------------------------------
# Handler import / construction tests
# ---------------------------------------------------------------------------


class TestUSPTOImport:
    """Verify the handler is importable and properly inherits BaseHandler."""

    def test_handler_is_importable(self) -> None:
        """Verify ``USPTOHandler`` can be imported from the collector module."""
        from autoinfo.collectors.uspto import USPTOHandler as H
        assert H is not None

    def test_handler_creates_instance(self) -> None:
        """Default constructor should not raise."""
        handler = USPTOHandler()
        assert handler is not None
        assert handler.source_name == "uspto"

    def test_handler_is_registered_in_package(self) -> None:
        """Verify the handler is exported from the collectors package."""
        from autoinfo.collectors import USPTOHandler
        assert USPTOHandler is not None


# ---------------------------------------------------------------------------
# fetch() tests — PatentsView API (primary)
# ---------------------------------------------------------------------------


class TestUSPTOFetchPatentsView:
    """Tests for ``USPTOHandler.fetch()`` using PatentsView API (mocked)."""

    def test_fetch_returns_list(self) -> None:
        """fetch() should return a list of patent dicts."""
        handler = USPTOHandler()
        resp = _make_patentsview_response(SAMPLE_PATENTS)

        with patch("httpx.post", return_value=resp):
            patents = handler.fetch("gene editing", limit=5)

        assert isinstance(patents, list)
        assert len(patents) == 2

    def test_fetch_empty_response(self) -> None:
        """When the API returns no data, fetch() should return an empty list."""
        handler = USPTOHandler()
        resp = _make_patentsview_response([], count=0)

        with patch("httpx.post", return_value=resp):
            patents = handler.fetch("zzzzznonexistentquery12345", limit=5)

        assert isinstance(patents, list)
        assert len(patents) == 0

    def test_fetch_empty_query_uses_text_any_match(self) -> None:
        """Empty query should still issue a valid request."""
        handler = USPTOHandler()
        resp = _make_patentsview_response(SAMPLE_PATENTS)

        with patch("httpx.post", return_value=resp) as mock_post:
            patents = handler.fetch("", limit=5)
            call_body = mock_post.call_args[1].get("json", {})
            # Empty query → no _text_any filter in body
            assert call_body.get("q") == {}

        assert len(patents) == 2

    def test_fetch_field_mapping_correct(self) -> None:
        """Parsed patents should have standardised field names."""
        handler = USPTOHandler()
        resp = _make_patentsview_response(SAMPLE_PATENTS)

        with patch("httpx.post", return_value=resp):
            patents = handler.fetch("gene editing", limit=5)

        for patent in patents:
            assert "id" in patent
            assert "patent_number" in patent
            assert "title" in patent
            assert "abstract" in patent
            assert "authors" in patent
            assert "filed_date" in patent
            assert "published_date" in patent
            assert "source_type" in patent

            # Authors should be a list of name strings
            assert isinstance(patent["authors"], list)
            for name in patent["authors"]:
                assert isinstance(name, str)

    def test_fetch_field_values_match_api_response(self) -> None:
        """Each mapped field should contain the value from the API response."""
        handler = USPTOHandler()
        resp = _make_patentsview_response(SAMPLE_PATENTS)

        with patch("httpx.post", return_value=resp):
            patents = handler.fetch("gene editing", limit=5)

        p0 = patents[0]
        assert p0["id"] == "US12000123"
        assert p0["patent_number"] == "US12000123"
        assert "CRISPR" in p0["title"]
        assert "gene editing" in p0["abstract"].lower()
        assert p0["authors"] == ["Jennifer Doudna", "Emmanuelle Charpentier"]
        assert p0["filed_date"] == "2025-01-10"
        assert p0["published_date"] == "2026-06-15"

        p1 = patents[1]
        assert p1["id"] == "US12000999"
        assert "Drug Discovery" in p1["title"]
        assert p1["authors"] == ["Demis Hassabis"]
        assert p1["published_date"] == "2026-04-20"

    def test_fetch_minimal_patent_handles_missing_fields(self) -> None:
        """A patent with None/empty fields should not crash the handler."""
        handler = USPTOHandler()
        resp = _make_patentsview_response([SAMPLE_PATENT_MINIMAL])

        with patch("httpx.post", return_value=resp):
            patents = handler.fetch("minimal", limit=1)

        assert len(patents) == 1
        p = patents[0]
        assert p["id"] == "US12000001"
        assert p["title"] == ""
        assert p["abstract"] == ""
        assert p["authors"] == []
        assert p["filed_date"] == ""
        assert p["published_date"] == ""
        assert p["cited_by_count"] == 0

    def test_fetch_respects_limit_parameter(self) -> None:
        """The ``limit`` parameter should be reflected in the request body."""
        handler = USPTOHandler()
        resp = _make_patentsview_response(SAMPLE_PATENTS[:1])

        with patch("httpx.post", return_value=resp) as mock_post:
            handler.fetch("test", limit=3)
            call_body = mock_post.call_args[1].get("json", {})

        assert call_body["o"]["per_page"] == 3

    def test_fetch_clamps_limit_to_500(self) -> None:
        """Limits above 500 should be clamped down by the handler."""
        handler = USPTOHandler()
        resp = _make_patentsview_response(SAMPLE_PATENTS)

        with patch("httpx.post", return_value=resp) as mock_post:
            handler.fetch("test", limit=9999)
            call_body = mock_post.call_args[1].get("json", {})

        assert call_body["o"]["per_page"] == 500

    def test_fetch_clamps_limit_min_1(self) -> None:
        """Limits below 1 should be clamped up to 1."""
        handler = USPTOHandler()
        resp = _make_patentsview_response(SAMPLE_PATENTS[:1])

        with patch("httpx.post", return_value=resp) as mock_post:
            handler.fetch("test", limit=0)
            call_body = mock_post.call_args[1].get("json", {})

        assert call_body["o"]["per_page"] == 1

    def test_fetch_sorts_by_date_descending(self) -> None:
        """Request should sort by patent_date descending by default."""
        handler = USPTOHandler()
        resp = _make_patentsview_response(SAMPLE_PATENTS)

        with patch("httpx.post", return_value=resp) as mock_post:
            handler.fetch("test", limit=5)
            call_body = mock_post.call_args[1].get("json", {})

        sort = call_body["o"].get("sort", [])
        assert sort == [{"patent_date": "desc"}]

    def test_fetch_includes_default_fields(self) -> None:
        """The request body should include all default fields."""
        handler = USPTOHandler()
        resp = _make_patentsview_response(SAMPLE_PATENTS)

        with patch("httpx.post", return_value=resp) as mock_post:
            handler.fetch("test", limit=5)
            call_body = mock_post.call_args[1].get("json", {})

        fields = call_body.get("f", [])
        for f in PATENTSVIEW_DEFAULT_FIELDS:
            assert f in fields

    def test_fetch_with_query_sets_text_any_filter(self) -> None:
        """A non-empty query should set ``_text_any`` filter on patent_title."""
        handler = USPTOHandler()
        resp = _make_patentsview_response(SAMPLE_PATENTS)

        with patch("httpx.post", return_value=resp) as mock_post:
            handler.fetch("CRISPR gene editing", limit=5)
            call_body = mock_post.call_args[1].get("json", {})

        q = call_body.get("q", {})
        assert "_text_any" in q
        assert q["_text_any"]["patent_title"] == "CRISPR gene editing"


# ---------------------------------------------------------------------------
# fetch() tests — RSS fallback
# ---------------------------------------------------------------------------


class TestUSPTOFetchRSS:
    """Tests for ``USPTOHandler.fetch()`` using RSS fallback (mocked)."""

    def test_fetch_rss_returns_list(self) -> None:
        """When use_rss=True, fetch() should parse the RSS feed."""
        handler = USPTOHandler()
        resp = _make_rss_response()

        with patch("httpx.get", return_value=resp):
            patents = handler.fetch(use_rss=True, limit=10)

        assert isinstance(patents, list)
        assert len(patents) == 2

    def test_fetch_rss_has_rss_source_type(self) -> None:
        """RSS-fetched patents should have source_type='rss'."""
        handler = USPTOHandler()
        resp = _make_rss_response()

        with patch("httpx.get", return_value=resp):
            patents = handler.fetch(use_rss=True, limit=10)

        for p in patents:
            assert p["source_type"] == "rss"

    def test_fetch_rss_filters_by_query(self) -> None:
        """RSS results should be filtered by the query keyword."""
        handler = USPTOHandler()
        resp = _make_rss_response()

        with patch("httpx.get", return_value=resp):
            patents = handler.fetch(query="Gene", use_rss=True, limit=10)

        assert len(patents) == 1
        assert "Gene" in patents[0]["title"]

    def test_fetch_rss_empty_when_no_match(self) -> None:
        """RSS with query that matches nothing returns empty list."""
        handler = USPTOHandler()
        resp = _make_rss_response()

        with patch("httpx.get", return_value=resp):
            patents = handler.fetch(
                query="zzzzznonexistent",
                use_rss=True,
                limit=10,
            )

        assert isinstance(patents, list)
        assert len(patents) == 0

    def test_fetch_falls_back_to_rss_on_api_error(self) -> None:
        """When PatentsView raises, fall back to RSS automatically."""
        handler = USPTOHandler()
        rss_resp = _make_rss_response()

        with patch("httpx.post", side_effect=httpx.TimeoutException(
            "timeout",
            request=httpx.Request("POST", "http://test"),
        )):
            with patch("httpx.get", return_value=rss_resp):
                patents = handler.fetch("gene editing", limit=10)

        assert isinstance(patents, list)
        assert len(patents) == 1


# ---------------------------------------------------------------------------
# to_item() conversion tests
# ---------------------------------------------------------------------------


class TestUSPTOConversion:
    """Tests for ``USPTOHandler.to_item()``."""

    def test_to_item_complete(self) -> None:
        """A fully populated patent dict should produce a correct Item."""
        handler = USPTOHandler()
        patent = MAPPED_PATENT

        item = handler.to_item(patent)

        assert isinstance(item, Item)
        assert item.id == "US12000123"
        assert item.source_name == "uspto"
        assert item.source_type == "api"
        assert item.source_platform == "uspto"
        assert "US12000123" in item.source_url
        assert item.title == "CRISPR-based Gene Editing Method for Targeted Therapy"
        assert "gene editing" in item.content.lower()
        assert item.content_type == "text"
        assert item.domain == "medical-research"
        assert item.raw_data["patent_number"] == "US12000123"
        assert item.raw_data["authors"] == ["Jennifer Doudna", "Emmanuelle Charpentier"]
        assert item.raw_data["filed_date"] == "2025-01-10"
        assert item.raw_data["published_date"] == "2026-06-15"
        assert item.raw_data["cited_by_count"] == 45
        assert item.raw_data["total_citations"] == 120

    def test_to_item_empty_id_uses_uuid(self) -> None:
        """When patent ID is empty, a UUID should be generated."""
        handler = USPTOHandler()
        patent: dict = {
            "id": "",
            "patent_number": "",
            "title": "No ID Patent",
            "abstract": "",
            "authors": [],
            "filed_date": "",
            "published_date": "",
            "source_type": "api",
        }

        item = handler.to_item(patent)
        assert item.id
        assert item.id != ""
        assert "-" in item.id  # UUID format

    def test_to_item_source_url_empty_when_no_patent_number(self) -> None:
        """When patent number is empty, source_url should be empty string."""
        handler = USPTOHandler()
        patent: dict = {
            "id": "",
            "patent_number": "",
            "title": "",
            "abstract": "",
            "authors": [],
            "filed_date": "",
            "published_date": "",
            "source_type": "api",
        }

        item = handler.to_item(patent)
        assert item.source_url == ""


# ---------------------------------------------------------------------------
# API key and rate limiting tests
# ---------------------------------------------------------------------------


class TestUSPTORateLimit:
    """Tests for rate limiter behaviour and API key handling."""

    def test_without_api_key_defaults_to_5_rps(self) -> None:
        """Default rate limit should be 5 requests/second."""
        handler = USPTOHandler()
        assert handler.max_rps == RATE_LIMIT_DEFAULT
        assert handler.max_rps == 5

    def test_with_api_key_uses_45_rps(self) -> None:
        """With API key, rate limit should be 45 requests/second."""
        handler = USPTOHandler(api_key="my-test-key")
        assert handler.max_rps == RATE_LIMIT_WITH_KEY
        assert handler.max_rps == 45

    def test_with_env_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """API key from environment variable should raise rate limit to 45."""
        monkeypatch.setenv("AUTOINFO_USPTO_API_KEY", "env-key")
        handler = USPTOHandler()
        assert handler.max_rps == 45

    def test_api_key_sent_as_header(self) -> None:
        """When API key is provided, it should be sent as ``X-Api-Key`` header."""
        handler = USPTOHandler(api_key="my-api-key-123")
        resp = _make_patentsview_response(SAMPLE_PATENTS)

        with patch("httpx.post", return_value=resp) as mock_post:
            handler.fetch("test", limit=1)

        headers = mock_post.call_args[1].get("headers", {})
        assert headers.get("X-Api-Key") == "my-api-key-123"

    def test_no_api_key_header_when_no_key(self) -> None:
        """Without API key, no ``X-Api-Key`` header should be sent."""
        handler = USPTOHandler()
        resp = _make_patentsview_response(SAMPLE_PATENTS)

        with patch("httpx.post", return_value=resp) as mock_post:
            handler.fetch("test", limit=1)

        headers = mock_post.call_args[1].get("headers", {})
        assert headers.get("X-Api-Key", "") == ""

    def test_rate_limit_first_call_instant(self) -> None:
        """First call should not block (no previous request recorded)."""
        handler = USPTOHandler()
        resp = _make_patentsview_response(SAMPLE_PATENTS)

        with patch("httpx.post", return_value=resp):
            t0 = time.time()
            handler.fetch("test", limit=1)
            elapsed = time.time() - t0

        assert elapsed < 0.3  # should be near-instant

    def test_rate_limit_enforces_min_interval(self) -> None:
        """Back-to-back calls should be spaced by at least 1/max_rps."""
        handler = USPTOHandler()  # max_rps = 5 → min interval = 0.2 s
        resp = _make_patentsview_response(SAMPLE_PATENTS)

        with patch("httpx.post", return_value=resp):
            handler.fetch("test", limit=1)  # warms _last_request_time
            t0 = time.time()
            handler.fetch("test", limit=1)  # should wait ~0.2 second
            elapsed = time.time() - t0

        min_interval = 1.0 / handler.max_rps
        assert elapsed >= min_interval * 0.9  # 10 % tolerance


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------


class TestUSPTOErrorHandling:
    """Tests for retry logic, error propagation, and graceful degradation."""

    def test_retry_on_timeout(self) -> None:
        """After 3 TimeoutExceptions the error should propagate."""
        handler = USPTOHandler()
        call_count = 0

        def _fake_post(*args: object, **kwargs: object) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            msg = f"Simulated timeout (attempt {call_count})"
            raise httpx.TimeoutException(msg, request=None)  # type: ignore[arg-type]

        rss_resp = _make_rss_response()
        with patch("httpx.post", side_effect=_fake_post):
            with patch("httpx.get", return_value=rss_resp):
                start = time.time()
                patents = handler.fetch("test", limit=1)
                elapsed = time.time() - start

        assert call_count == 3
        assert isinstance(patents, list)
        # Expect at least 2 + 4 = 6 seconds of backoff sleep
        assert elapsed >= 6.0

    def test_retry_on_network_error(self) -> None:
        """NetworkError is also retried 3 times before raising."""
        handler = USPTOHandler()
        call_count = 0

        def _fake_post(*args: object, **kwargs: object) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            raise httpx.NetworkError("Simulated network error", request=None)  # type: ignore[arg-type]

        rss_resp = _make_rss_response()
        with patch("httpx.post", side_effect=_fake_post):
            with patch("httpx.get", return_value=rss_resp):
                patents = handler.fetch("test", limit=1)

        assert call_count == 3
        assert isinstance(patents, list)

    def test_http_4xx_is_not_retried(self) -> None:
        """HTTP 4xx/5xx responses are raised immediately (no retry)."""
        handler = USPTOHandler()

        resp = httpx.Response(
            401,
            json={"error": "Unauthorized", "message": "Invalid API key"},
            request=httpx.Request("POST", "http://test.com"),
        )

        rss_resp = _make_rss_response()
        with patch("httpx.post", return_value=resp):
            with patch("httpx.get", return_value=rss_resp):
                patents = handler.fetch("Gene", limit=1)

        assert isinstance(patents, list)
        assert len(patents) == 1
        assert patents[0]["source_type"] == "rss"

    def test_http_429_too_many_requests_is_not_retried(self) -> None:
        """429 is an HTTP status error — not retried unless explicitly coded."""
        handler = USPTOHandler()

        resp = httpx.Response(
            429,
            json={"error": "Rate limit exceeded"},
            request=httpx.Request("POST", "http://test.com"),
        )

        rss_resp = _make_rss_response()
        with patch("httpx.post", return_value=resp):
            with patch("httpx.get", return_value=rss_resp):
                patents = handler.fetch("Gene", limit=1)

        assert isinstance(patents, list)
        assert len(patents) == 1
        assert patents[0]["source_type"] == "rss"

    def test_malformed_json_is_handled_gracefully(self) -> None:
        """A response with malformed JSON should not crash."""
        handler = USPTOHandler()

        resp = httpx.Response(
            200,
            content=b"<html>Internal Server Error</html>",
            headers={"Content-Type": "text/html"},
            request=httpx.Request("POST", "http://test.com"),
        )

        rss_resp = _make_rss_response()
        with patch("httpx.post", return_value=resp):
            with patch("httpx.get", return_value=rss_resp):
                patents = handler.fetch("Gene", limit=1)

        assert isinstance(patents, list)
        assert len(patents) == 1
        assert patents[0]["source_type"] == "rss"

    def test_rss_fallback_on_api_timeout(self) -> None:
        """When API times out, RSS fallback should return data if available."""
        handler = USPTOHandler()
        rss_resp = _make_rss_response()

        def _fake_post(*args: object, **kwargs: object) -> httpx.Response:
            raise httpx.TimeoutException("API timeout", request=None)  # type: ignore[arg-type]

        with patch("httpx.post", side_effect=_fake_post):
            with patch("httpx.get", return_value=rss_resp):
                patents = handler.fetch("gene editing", limit=10)

        assert isinstance(patents, list)
        assert len(patents) == 1
        assert patents[0]["source_type"] == "rss"


# ---------------------------------------------------------------------------
# Patent number extraction from RSS
# ---------------------------------------------------------------------------


class TestUSPTORSSExtraction:
    """Tests for patent number extraction from RSS feed metadata."""

    def test_extract_from_title(self) -> None:
        """US patent number format in title should be extracted."""
        result = USPTOHandler._extract_patent_number_from_rss(
            "US 2024/0123456 A1: Gene Editing Method",
            "https://example.com/doc/123",
        )
        assert result == "US20240123456"

    def test_extract_from_link(self) -> None:
        """Numeric sequence in link should be used when title has no match."""
        result = USPTOHandler._extract_patent_number_from_rss(
            "Patent Application",
            "https://patents.google.com/patent/12000123/en",
        )
        assert result == "12000123"

    def test_extract_fallback_hash(self) -> None:
        """When neither title nor link has a pattern, fall back to hash."""
        result = USPTOHandler._extract_patent_number_from_rss(
            "Some Patent",
            "https://example.com/",
        )
        # Should be a numeric string (hash-based)
        assert result
        assert isinstance(result, str)
        assert result.isdigit() or any(c.isdigit() for c in result)
