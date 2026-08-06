"""Tests for the Semantic Scholar Academic Graph API handler.

Uses ``unittest.mock`` to avoid real API calls — all HTTP interactions are
mocked.
"""

from __future__ import annotations

import time
from unittest.mock import patch

import httpx
import pytest

from autoinfo.collectors.semantic_scholar import (
    DEFAULT_FIELDS,
    RATE_LIMIT_DEFAULT,
    RATE_LIMIT_WITH_KEY,
    SemanticScholarHandler,
)
from autoinfo.models import Item

# ---------------------------------------------------------------------------
# Sample API response data
# ---------------------------------------------------------------------------


def _make_response(data: list[dict], total: int = 0) -> httpx.Response:
    """Create a mock httpx.Response with a Semantic Scholar-style JSON body."""
    return httpx.Response(
        200,
        json={"total": total or len(data), "offset": 0, "data": data},
        request=httpx.Request("GET", "https://api.semanticscholar.org/graph/v1/paper/search?query=test&limit=10"),
    )


SAMPLE_PAPERS = [
    {
        "paperId": "abc123def456",
        "externalIds": {"DOI": "10.1000/test.2026.001", "ArXiv": "2601.00001"},
        "title": "Deep Learning for Medical Image Analysis",
        "abstract": "We present a comprehensive survey of deep learning methods applied to medical image analysis, covering segmentation, classification, and detection tasks.",
        "authors": [
            {"authorId": "a1", "name": "Jane Smith"},
            {"authorId": "a2", "name": "John Doe"},
            {"authorId": "a3", "name": "Wei Zhang"},
        ],
        "citationCount": 42,
        "publicationDate": "2026-03-15",
    },
    {
        "paperId": "xyz789ghi012",
        "externalIds": {"DOI": "10.1000/test.2026.002"},
        "title": "Transformers for Protein Structure Prediction",
        "abstract": "We adapt transformer architectures to predict protein 3D structures from amino acid sequences, achieving state-of-the-art accuracy.",
        "authors": [
            {"authorId": "b1", "name": "Alice Johnson"},
            {"authorId": "b2", "name": "Bob Wilson"},
        ],
        "citationCount": 128,
        "publicationDate": "2026-01-20",
    },
]

SAMPLE_PAPER_MINIMAL = {
    "paperId": "min001",
    "title": "A Minimal Paper",
    "abstract": None,
    "authors": [],
    "citationCount": 0,
    "publicationDate": None,
}

MAPPED_PAPER = {
    "id": "abc123def456",
    "title": "Deep Learning for Medical Image Analysis",
    "abstract": "We present a comprehensive survey of deep learning methods applied to medical image analysis.",
    "authors": ["Jane Smith", "John Doe", "Wei Zhang"],
    "cited_by_count": 42,
    "published_date": "2026-03-15",
}


# ---------------------------------------------------------------------------
# Handler import / construction tests
# ---------------------------------------------------------------------------


class TestSemanticScholarImport:
    """Verify the handler is importable and properly inherits BaseHandler."""

    def test_handler_is_importable(self) -> None:
        """Verify ``SemanticScholarHandler`` can be imported from the collector module."""
        from autoinfo.collectors.semantic_scholar import SemanticScholarHandler as H
        assert H is not None

    def test_handler_creates_instance(self) -> None:
        """Default constructor should not raise."""
        handler = SemanticScholarHandler()
        assert handler is not None
        assert handler.source_name == "semantic_scholar"

    def test_handler_is_registered_in_package(self) -> None:
        """Verify the handler is exported from the collectors package."""
        from autoinfo.collectors import SemanticScholarHandler
        assert SemanticScholarHandler is not None


# ---------------------------------------------------------------------------
# fetch() tests
# ---------------------------------------------------------------------------


class TestSemanticScholarFetch:
    """Tests for ``SemanticScholarHandler.fetch()`` with mocked HTTP."""

    def test_fetch_returns_list(self) -> None:
        """fetch() should return a list of paper dicts."""
        handler = SemanticScholarHandler()
        resp = _make_response(SAMPLE_PAPERS)

        with patch("httpx.get", return_value=resp):
            papers = handler.fetch("deep learning", limit=5)

        assert isinstance(papers, list)
        assert len(papers) == 2

    def test_fetch_empty_response(self) -> None:
        """When the API returns no data, fetch() should return an empty list."""
        handler = SemanticScholarHandler()
        resp = _make_response([], total=0)

        with patch("httpx.get", return_value=resp):
            papers = handler.fetch("zzzzznonexistentquery12345", limit=5)

        assert isinstance(papers, list)
        assert len(papers) == 0

    def test_fetch_field_mapping_correct(self) -> None:
        """Parsed papers should have standardised field names and correct values."""
        handler = SemanticScholarHandler()
        resp = _make_response(SAMPLE_PAPERS)

        with patch("httpx.get", return_value=resp):
            papers = handler.fetch("deep learning", limit=5)

        for paper in papers:
            # Check standardised field names exist
            assert "id" in paper
            assert "title" in paper
            assert "abstract" in paper
            assert "authors" in paper
            assert "cited_by_count" in paper
            assert "published_date" in paper

            # Authors should be a list of name strings
            assert isinstance(paper["authors"], list)
            for name in paper["authors"]:
                assert isinstance(name, str)

            # cited_by_count should be an int
            assert isinstance(paper["cited_by_count"], int)

    def test_fetch_field_values_match_api_response(self) -> None:
        """Each mapped field should contain the value from the API response."""
        handler = SemanticScholarHandler()
        resp = _make_response(SAMPLE_PAPERS)

        with patch("httpx.get", return_value=resp):
            papers = handler.fetch("deep learning", limit=5)

        # First paper checks
        p0 = papers[0]
        assert p0["id"] == "abc123def456"
        assert p0["title"] == "Deep Learning for Medical Image Analysis"
        assert "deep learning" in p0["abstract"].lower()
        assert p0["authors"] == ["Jane Smith", "John Doe", "Wei Zhang"]
        assert p0["cited_by_count"] == 42
        assert p0["published_date"] == "2026-03-15"

        # Second paper checks
        p1 = papers[1]
        assert p1["id"] == "xyz789ghi012"
        assert "Transformers" in p1["title"]
        assert p1["authors"] == ["Alice Johnson", "Bob Wilson"]
        assert p1["cited_by_count"] == 128
        assert p1["published_date"] == "2026-01-20"

    def test_fetch_minimal_paper_handles_missing_fields(self) -> None:
        """A paper with None/empty fields should not crash the handler."""
        handler = SemanticScholarHandler()
        resp = _make_response([SAMPLE_PAPER_MINIMAL])

        with patch("httpx.get", return_value=resp):
            papers = handler.fetch("minimal", limit=1)

        assert len(papers) == 1
        p = papers[0]
        assert p["id"] == "min001"
        assert p["title"] == "A Minimal Paper"
        assert p["abstract"] == ""
        assert p["authors"] == []
        assert p["cited_by_count"] == 0
        assert p["published_date"] == ""

    def test_fetch_respects_limit_parameter(self) -> None:
        """The ``limit`` parameter should be clamped to [1, 100]."""
        handler = SemanticScholarHandler()
        resp = _make_response(SAMPLE_PAPERS[:1])

        with patch("httpx.get", return_value=resp) as mock_get:
            handler.fetch("test", limit=1)

        # Check the URL includes limit=1
        call_url = mock_get.call_args[0][0]
        assert "limit=1" in call_url

    def test_fetch_clamps_limit_to_100(self) -> None:
        """Limits above 100 should be clamped down by the handler."""
        handler = SemanticScholarHandler()
        resp = _make_response(SAMPLE_PAPERS)

        with patch("httpx.get", return_value=resp) as mock_get:
            handler.fetch("test", limit=999)

        call_url = mock_get.call_args[0][0]
        assert "limit=100" in call_url

    def test_fetch_clamps_limit_min_1(self) -> None:
        """Limits below 1 should be clamped up to 1."""
        handler = SemanticScholarHandler()
        resp = _make_response(SAMPLE_PAPERS[:1])

        with patch("httpx.get", return_value=resp) as mock_get:
            handler.fetch("test", limit=0)

        call_url = mock_get.call_args[0][0]
        assert "limit=1" in call_url

    def test_fetch_includes_default_fields(self) -> None:
        """The request URL should include the required fields parameter."""
        handler = SemanticScholarHandler()
        resp = _make_response(SAMPLE_PAPERS)

        with patch("httpx.get", return_value=resp) as mock_get:
            handler.fetch("test", limit=5)

        call_url = mock_get.call_args[0][0]
        assert f"fields={DEFAULT_FIELDS}" in call_url


# ---------------------------------------------------------------------------
# to_item() conversion tests
# ---------------------------------------------------------------------------


class TestSemanticScholarConversion:
    """Tests for ``SemanticScholarHandler.to_item()``."""

    def test_to_item_complete(self) -> None:
        """A fully populated paper dict should produce a correct Item."""
        handler = SemanticScholarHandler()
        paper = MAPPED_PAPER

        item = handler.to_item(paper)

        assert isinstance(item, Item)
        assert item.id == "abc123def456"
        assert item.source_name == "semantic_scholar"
        assert item.source_type == "api"
        assert item.source_platform == "semantic_scholar"
        assert "abc123def456" in item.source_url
        assert item.title == "Deep Learning for Medical Image Analysis"
        assert "deep learning" in item.content.lower()
        assert item.content_type == "text"
        assert item.domain == "medical-research"
        assert item.raw_data["paper_id"] == "abc123def456"
        assert item.raw_data["authors"] == ["Jane Smith", "John Doe", "Wei Zhang"]
        assert item.raw_data["cited_by_count"] == 42
        assert item.raw_data["published_date"] == "2026-03-15"

    def test_to_item_empty_id_uses_uuid(self) -> None:
        """When paper ID is empty, a UUID should be generated."""
        handler = SemanticScholarHandler()
        paper = {
            "id": "",
            "title": "No ID Paper",
            "abstract": "",
            "authors": [],
            "cited_by_count": 0,
            "published_date": "",
        }

        item = handler.to_item(paper)

        assert item.id
        assert item.id != ""
        assert "-" in item.id  # UUID format

    def test_to_item_source_url_empty_when_no_id(self) -> None:
        """When paper ID is empty, source_url should be empty string."""
        handler = SemanticScholarHandler()
        paper = {
            "id": "",
            "title": "",
            "abstract": "",
            "authors": [],
            "cited_by_count": 0,
            "published_date": "",
        }

        item = handler.to_item(paper)
        assert item.source_url == ""


# ---------------------------------------------------------------------------
# API key and rate limiting tests
# ---------------------------------------------------------------------------


class TestSemanticScholarRateLimit:
    """Tests for rate limiter behaviour and API key handling."""

    def test_without_api_key_defaults_to_1_rps(self) -> None:
        """Default rate limit should be 1 request/second."""
        handler = SemanticScholarHandler()
        assert handler.max_rps == RATE_LIMIT_DEFAULT
        assert handler.max_rps == 1

    def test_with_api_key_uses_100_rps(self) -> None:
        """With API key, rate limit should be 100 requests/second."""
        handler = SemanticScholarHandler(api_key="my-test-key")
        assert handler.max_rps == RATE_LIMIT_WITH_KEY
        assert handler.max_rps == 100

    def test_with_env_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """API key from environment variable should raise rate limit to 100."""
        monkeypatch.setenv("AUTOINFO_S2_API_KEY", "env-key")
        handler = SemanticScholarHandler()
        assert handler.max_rps == 100

    def test_api_key_sent_as_header(self) -> None:
        """When API key is provided, it should be sent as ``x-api-key`` header."""
        handler = SemanticScholarHandler(api_key="my-api-key-123")
        resp = _make_response(SAMPLE_PAPERS)

        with patch("httpx.get", return_value=resp) as mock_get:
            handler.fetch("test", limit=1)

        headers = mock_get.call_args[1].get("headers", {})
        assert headers.get("x-api-key") == "my-api-key-123"

    def test_no_api_key_header_when_no_key(self) -> None:
        """Without API key, no ``x-api-key`` header should be sent."""
        handler = SemanticScholarHandler()
        resp = _make_response(SAMPLE_PAPERS)

        with patch("httpx.get", return_value=resp) as mock_get:
            handler.fetch("test", limit=1)

        headers = mock_get.call_args[1].get("headers", {})
        assert "x-api-key" not in headers or headers.get("x-api-key") == ""

    def test_rate_limit_first_call_instant(self) -> None:
        """First call should not block (no previous request recorded)."""
        handler = SemanticScholarHandler()
        resp = _make_response(SAMPLE_PAPERS)

        with patch("httpx.get", return_value=resp):
            t0 = time.time()
            handler.fetch("test", limit=1)
            elapsed = time.time() - t0

        assert elapsed < 0.2  # should be near-instant

    def test_rate_limit_enforces_min_interval(self) -> None:
        """Back-to-back calls should be spaced by at least 1/max_rps."""
        handler = SemanticScholarHandler()  # max_rps = 1
        resp = _make_response(SAMPLE_PAPERS)

        with patch("httpx.get", return_value=resp):
            handler.fetch("test", limit=1)  # warms _last_request_time
            t0 = time.time()
            handler.fetch("test", limit=1)  # should wait ~1 second
            elapsed = time.time() - t0

        min_interval = 1.0 / handler.max_rps  # exactly 1.0 s
        assert elapsed >= min_interval * 0.9  # 10 % tolerance


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------


class TestSemanticScholarErrorHandling:
    """Tests for retry logic and error propagation."""

    def test_retry_on_timeout(self) -> None:
        """After 3 TimeoutExceptions the error should propagate."""
        handler = SemanticScholarHandler()
        call_count = 0

        def _fake_get(*args: object, **kwargs: object) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            msg = f"Simulated timeout (attempt {call_count})"
            raise httpx.TimeoutException(msg, request=None)  # type: ignore[arg-type]

        with patch("httpx.get", side_effect=_fake_get):
            start = time.time()
            with pytest.raises(httpx.TimeoutException):
                handler.fetch("test", limit=1)
            elapsed = time.time() - start

        assert call_count == 3
        # Expect at least 2 + 4 = 6 seconds of backoff sleep
        assert elapsed >= 6.0

    def test_retry_on_network_error(self) -> None:
        """NetworkError is also retried 3 times before raising."""
        handler = SemanticScholarHandler()
        call_count = 0

        def _fake_get(*args: object, **kwargs: object) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            raise httpx.NetworkError("Simulated network error", request=None)  # type: ignore[arg-type]

        with patch("httpx.get", side_effect=_fake_get):
            with pytest.raises(httpx.NetworkError):
                handler.fetch("test", limit=1)

        assert call_count == 3

    def test_http_4xx_is_not_retried(self) -> None:
        """HTTP 4xx/5xx responses are raised immediately (no retry)."""
        handler = SemanticScholarHandler()

        resp = httpx.Response(
            404,
            request=httpx.Request("GET", "http://test.com"),
        )

        with patch("httpx.get", return_value=resp):
            with pytest.raises(httpx.HTTPStatusError):
                handler.fetch("test", limit=1)

    def test_http_429_too_many_requests(self) -> None:
        """429 without an API key raises an explicit SourceFailure (issue #135)."""
        from autoinfo.collectors.base import SourceFailure

        handler = SemanticScholarHandler()

        resp = httpx.Response(
            429,
            request=httpx.Request("GET", "http://test.com"),
        )

        with patch("httpx.get", return_value=resp):
            with pytest.raises(SourceFailure) as exc_info:
                handler.fetch("test", limit=1)

        assert "429" in exc_info.value.reason
        assert "AUTOINFO_S2_API_KEY" in exc_info.value.reason


# ---------------------------------------------------------------------------
# URL construction tests
# ---------------------------------------------------------------------------


class TestSemanticScholarUrlConstruction:
    """Verify that the handler builds correct API URLs."""

    def test_query_is_url_encoded(self) -> None:
        """Spaces and special characters in the query should be URL-encoded."""
        handler = SemanticScholarHandler()
        resp = _make_response(SAMPLE_PAPERS)

        with patch("httpx.get", return_value=resp) as mock_get:
            handler.fetch("machine learning & AI", limit=5)

        call_url = mock_get.call_args[0][0]
        # "machine learning & AI" → "machine%20learning%20%26%20AI"
        assert "machine%20learning" in call_url or "machine+learning" in call_url
        assert "%26" in call_url or "&" not in call_url.split("?")[1]
