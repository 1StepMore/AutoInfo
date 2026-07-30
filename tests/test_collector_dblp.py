"""Tests for the DBLP Computer Science Bibliography handler.

Uses ``unittest.mock`` to avoid real API calls — all HTTP interactions are
mocked.
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from autoinfo.collectors.dblp import DBLPHandler, RATE_LIMIT
from autoinfo.models import Item


# ---------------------------------------------------------------------------
# Sample DBLP API response data
# ---------------------------------------------------------------------------


def _make_response(data: dict[str, Any]) -> httpx.Response:
    """Create a mock httpx.Response with a DBLP-style JSON body."""
    return httpx.Response(
        200,
        json=data,
        request=httpx.Request("GET", "https://dblp.org/search/publ/api?q=test&format=json&h=10"),
    )


def _make_hit(
    title: str = "Test Paper",
    doi: str = "",
    dblp_id: str = "https://dblp.org/rec/conf/test/2026",
    authors: Any | None = None,
    year: str = "2026",
    venue: str = "ICML",
) -> dict[str, Any]:
    """Build a single DBLP hit dict."""
    if authors is None:
        authors_data: dict[str, Any] = {"author": ["Jane Smith", "John Doe"]}
    elif isinstance(authors, dict):
        authors_data = authors
    elif isinstance(authors, list):
        authors_data = {"author": authors}
    else:
        authors_data = {"author": str(authors)}

    return {
        "@score": "42",
        "@id": dblp_id,
        "info": {
            "title": title,
            "doi": doi,
            "authors": authors_data,
            "year": year,
            "venue": venue,
        },
    }


def _make_hit_response(hits: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a full DBLP response dict from a list of hits."""
    total = str(len(hits))
    return {
        "result": {
            "hits": {
                "@total": total,
                "@sent": total,
                "@first": "1",
                "hit": hits,
            },
        },
    }


SAMPLE_HITS = [
    _make_hit(
        title="Deep Learning for Medical Image Analysis",
        doi="10.1000/test.2026.001",
        dblp_id="https://dblp.org/rec/conf/icml/2026dl",
        authors=["Jane Smith", "John Doe", "Wei Zhang"],
        year="2026",
        venue="ICML",
    ),
    _make_hit(
        title="Transformers for Protein Structure Prediction",
        doi="10.1000/test.2026.002",
        dblp_id="https://dblp.org/rec/conf/neurips/2026tp",
        authors=["Alice Johnson", "Bob Wilson"],
        year="2026",
        venue="NeurIPS",
    ),
]

SAMPLE_HIT_NO_DOI = _make_hit(
    title="Paper Without DOI",
    doi="",
    dblp_id="https://dblp.org/rec/conf/nodoi/2026",
    authors=["Test Author"],
    year="2025",
    venue="CVPR",
)

SAMPLE_HIT_STRING_AUTHOR = _make_hit(
    title="Single Author Paper",
    doi="10.1000/single.2026",
    dblp_id="https://dblp.org/rec/conf/single/2026",
    authors="Single Author Name",
    year="2026",
    venue="ECCV",
)

SAMPLE_HIT_MINIMAL = _make_hit(
    title="",
    doi="",
    dblp_id="",
    authors=[],
    year="",
    venue="",
)


# ---------------------------------------------------------------------------
# Handler import / construction tests
# ---------------------------------------------------------------------------


class TestDBLPImport:
    """Verify the handler is importable and properly inherits BaseHandler."""

    def test_handler_is_importable(self) -> None:
        """Verify ``DBLPHandler`` can be imported from the collector module."""
        from autoinfo.collectors.dblp import DBLPHandler as H
        assert H is not None

    def test_handler_creates_instance(self) -> None:
        """Default constructor should not raise."""
        handler = DBLPHandler()
        assert handler is not None
        assert handler.source_name == "dblp"

    def test_handler_is_registered_in_package(self) -> None:
        """Verify the handler is exported from the collectors package."""
        from autoinfo.collectors import DBLPHandler
        assert DBLPHandler is not None


# ---------------------------------------------------------------------------
# fetch() tests
# ---------------------------------------------------------------------------


class TestDBLPFetch:
    """Tests for ``DBLPHandler.fetch()`` with mocked HTTP."""

    def test_fetch_returns_list(self) -> None:
        """fetch() should return a list of publication dicts."""
        handler = DBLPHandler()
        resp = _make_response(_make_hit_response(SAMPLE_HITS))

        with patch("httpx.get", return_value=resp):
            pubs = handler.fetch("deep learning", limit=5)

        assert isinstance(pubs, list)
        assert len(pubs) == 2

    def test_fetch_empty_response(self) -> None:
        """When the API returns no hits, fetch() should return an empty list."""
        handler = DBLPHandler()
        resp = _make_response(_make_hit_response([]))

        with patch("httpx.get", return_value=resp):
            pubs = handler.fetch("zzzzznonexistentquery12345", limit=5)

        assert isinstance(pubs, list)
        assert len(pubs) == 0

    def test_fetch_empty_result(self) -> None:
        """Response with no 'hit' key should return empty list."""
        handler = DBLPHandler()
        resp = _make_response({"result": {"hits": {}}})

        with patch("httpx.get", return_value=resp):
            pubs = handler.fetch("test", limit=5)

        assert pubs == []

    def test_fetch_respects_limit_parameter(self) -> None:
        """The ``limit`` parameter should be passed as ``h`` in the URL."""
        handler = DBLPHandler()
        resp = _make_response(_make_hit_response(SAMPLE_HITS[:1]))

        with patch("httpx.get", return_value=resp) as mock_get:
            handler.fetch("test", limit=5)

        call_url = mock_get.call_args[0][0]
        assert "h=5" in call_url

    def test_fetch_clamps_limit_to_1000(self) -> None:
        """Limits above 1000 should be clamped down."""
        handler = DBLPHandler()
        resp = _make_response(_make_hit_response(SAMPLE_HITS))

        with patch("httpx.get", return_value=resp) as mock_get:
            handler.fetch("test", limit=9999)

        call_url = mock_get.call_args[0][0]
        assert "h=1000" in call_url

    def test_fetch_clamps_limit_min_1(self) -> None:
        """Limits below 1 should be clamped up to 1."""
        handler = DBLPHandler()
        resp = _make_response(_make_hit_response(SAMPLE_HITS[:1]))

        with patch("httpx.get", return_value=resp) as mock_get:
            handler.fetch("test", limit=0)

        call_url = mock_get.call_args[0][0]
        assert "h=1" in call_url

    def test_fetch_uses_json_format(self) -> None:
        """Request URL must include ``format=json``."""
        handler = DBLPHandler()
        resp = _make_response(_make_hit_response(SAMPLE_HITS))

        with patch("httpx.get", return_value=resp) as mock_get:
            handler.fetch("test", limit=5)

        call_url = mock_get.call_args[0][0]
        assert "format=json" in call_url


# ---------------------------------------------------------------------------
# Field mapping tests
# ---------------------------------------------------------------------------


class TestDBLPFieldMapping:
    """Tests for mapping DBLP JSON fields to standardised dicts."""

    def test_field_mapping_all_expected_fields_present(self) -> None:
        """Every returned item must have all expected keys."""
        handler = DBLPHandler()
        resp = _make_response(_make_hit_response(SAMPLE_HITS))

        with patch("httpx.get", return_value=resp):
            pubs = handler.fetch("deep learning", limit=5)

        expected_fields = {
            "id", "title", "authors", "published_date",
            "source_type", "venue", "dblp_url",
        }
        for pub in pubs:
            for field in expected_fields:
                assert field in pub, f"Item missing field: {field}"

    def test_field_mapping_id_from_doi(self) -> None:
        """When DOI is present, id should use it."""
        handler = DBLPHandler()
        resp = _make_response(_make_hit_response(SAMPLE_HITS))

        with patch("httpx.get", return_value=resp):
            pubs = handler.fetch("deep learning", limit=5)

        assert pubs[0]["id"] == "10.1000/test.2026.001"
        assert pubs[1]["id"] == "10.1000/test.2026.002"

    def test_field_mapping_id_fallback_to_dblp_id(self) -> None:
        """When DOI is absent, id should fall back to DBLP @id."""
        handler = DBLPHandler()
        resp = _make_response(_make_hit_response([SAMPLE_HIT_NO_DOI]))

        with patch("httpx.get", return_value=resp):
            pubs = handler.fetch("test", limit=1)

        assert pubs[0]["id"] == "https://dblp.org/rec/conf/nodoi/2026"

    def test_field_mapping_id_empty_when_all_absent(self) -> None:
        """When both DOI and @id are empty, id should be empty string."""
        handler = DBLPHandler()
        resp = _make_response(_make_hit_response([SAMPLE_HIT_MINIMAL]))

        with patch("httpx.get", return_value=resp):
            pubs = handler.fetch("test", limit=1)

        assert pubs[0]["id"] == ""

    def test_field_mapping_title(self) -> None:
        """Title should come from info.title."""
        handler = DBLPHandler()
        resp = _make_response(_make_hit_response(SAMPLE_HITS))

        with patch("httpx.get", return_value=resp):
            pubs = handler.fetch("deep learning", limit=5)

        assert pubs[0]["title"] == "Deep Learning for Medical Image Analysis"
        assert pubs[1]["title"] == "Transformers for Protein Structure Prediction"

    def test_field_mapping_authors_list(self) -> None:
        """Authors should be extracted as a list of strings."""
        handler = DBLPHandler()
        resp = _make_response(_make_hit_response(SAMPLE_HITS))

        with patch("httpx.get", return_value=resp):
            pubs = handler.fetch("deep learning", limit=5)

        assert isinstance(pubs[0]["authors"], list)
        assert pubs[0]["authors"] == ["Jane Smith", "John Doe", "Wei Zhang"]
        assert pubs[1]["authors"] == ["Alice Johnson", "Bob Wilson"]

    def test_field_mapping_authors_string(self) -> None:
        """When DBLP returns a single string author, wrap it in a list."""
        handler = DBLPHandler()
        resp = _make_response(_make_hit_response([SAMPLE_HIT_STRING_AUTHOR]))

        with patch("httpx.get", return_value=resp):
            pubs = handler.fetch("test", limit=1)

        assert pubs[0]["authors"] == ["Single Author Name"]

    def test_field_mapping_authors_empty(self) -> None:
        """Empty author list should remain empty."""
        handler = DBLPHandler()
        resp = _make_response(_make_hit_response([SAMPLE_HIT_MINIMAL]))

        with patch("httpx.get", return_value=resp):
            pubs = handler.fetch("test", limit=1)

        assert pubs[0]["authors"] == []

    def test_field_mapping_year_to_published_date(self) -> None:
        """info.year should map to published_date."""
        handler = DBLPHandler()
        resp = _make_response(_make_hit_response(SAMPLE_HITS))

        with patch("httpx.get", return_value=resp):
            pubs = handler.fetch("deep learning", limit=5)

        assert pubs[0]["published_date"] == "2026"
        assert pubs[1]["published_date"] == "2026"

    def test_field_mapping_venue_to_source_type(self) -> None:
        """info.venue should map to source_type."""
        handler = DBLPHandler()
        resp = _make_response(_make_hit_response(SAMPLE_HITS))

        with patch("httpx.get", return_value=resp):
            pubs = handler.fetch("deep learning", limit=5)

        assert pubs[0]["source_type"] == "ICML"
        assert pubs[1]["source_type"] == "NeurIPS"

    def test_field_mapping_venue_empty_defaults(self) -> None:
        """Empty venue should default to 'conference'."""
        handler = DBLPHandler()
        hit = _make_hit(
            title="No Venue Paper",
            dblp_id="https://dblp.org/rec/conf/nv/2026",
            authors=["Author"],
            year="2026",
            venue="",
        )
        resp = _make_response(_make_hit_response([hit]))

        with patch("httpx.get", return_value=resp):
            pubs = handler.fetch("test", limit=1)

        assert pubs[0]["source_type"] == "conference"
        assert pubs[0]["venue"] == ""

    def test_field_mapping_dblp_url(self) -> None:
        """dblp_url should match the @id field."""
        handler = DBLPHandler()
        resp = _make_response(_make_hit_response(SAMPLE_HITS))

        with patch("httpx.get", return_value=resp):
            pubs = handler.fetch("deep learning", limit=5)

        assert pubs[0]["dblp_url"] == "https://dblp.org/rec/conf/icml/2026dl"

    def test_field_mapping_minimal_handles_missing_fields(self) -> None:
        """A hit with empty fields should not crash the handler."""
        handler = DBLPHandler()
        resp = _make_response(_make_hit_response([SAMPLE_HIT_MINIMAL]))

        with patch("httpx.get", return_value=resp):
            pubs = handler.fetch("test", limit=1)

        assert len(pubs) == 1
        p = pubs[0]
        assert p["id"] == ""
        assert p["title"] == ""
        assert p["authors"] == []
        assert p["published_date"] == ""
        assert p["source_type"] == "conference"
        assert p["venue"] == ""
        assert p["dblp_url"] == ""

    def test_field_mapping_dict_author_with_text(self) -> None:
        """When DBLP returns author objects with a 'text' key, extract text."""
        handler = DBLPHandler()
        hit = _make_hit(
            title="Dict Authors Paper",
            dblp_id="https://dblp.org/rec/conf/da/2026",
            authors=[
                {"text": "Zhang Wei", "@pid": "123"},
                {"text": "Li Ming", "@pid": "456"},
            ],
            year="2026",
            venue="AAAI",
        )
        resp = _make_response(_make_hit_response([hit]))

        with patch("httpx.get", return_value=resp):
            pubs = handler.fetch("test", limit=1)

        assert pubs[0]["authors"] == ["Zhang Wei", "Li Ming"]


# ---------------------------------------------------------------------------
# to_item() conversion tests
# ---------------------------------------------------------------------------


class TestDBLPConversion:
    """Tests for ``DBLPHandler.to_item()``."""

    def test_to_item_complete(self) -> None:
        """A fully populated publication dict should produce a correct Item."""
        handler = DBLPHandler()
        publication = {
            "id": "10.1000/test.2026.001",
            "title": "Deep Learning for Medical Image Analysis",
            "authors": ["Jane Smith", "John Doe", "Wei Zhang"],
            "published_date": "2026",
            "source_type": "ICML",
            "venue": "ICML",
            "dblp_url": "https://dblp.org/rec/conf/icml/2026dl",
        }

        item = handler.to_item(publication)

        assert isinstance(item, Item)
        assert item.id == "10.1000/test.2026.001"
        assert item.source_name == "dblp"
        assert item.source_type == "api"
        assert item.source_platform == "dblp"
        assert item.source_url == "https://dblp.org/rec/conf/icml/2026dl"
        assert item.title == "Deep Learning for Medical Image Analysis"
        assert item.content_type == "text"
        assert item.domain == "medical-research"
        assert item.raw_data["dblp_id"] == "https://dblp.org/rec/conf/icml/2026dl"
        assert item.raw_data["authors"] == ["Jane Smith", "John Doe", "Wei Zhang"]
        assert item.raw_data["venue"] == "ICML"
        assert item.raw_data["published_date"] == "2026"

    def test_to_item_empty_id_uses_uuid(self) -> None:
        """When id is empty, a UUID should be generated."""
        handler = DBLPHandler()
        publication = {
            "id": "",
            "title": "No ID Paper",
            "authors": [],
            "published_date": "",
            "source_type": "conference",
            "venue": "",
            "dblp_url": "",
        }

        item = handler.to_item(publication)

        assert item.id
        assert item.id != ""
        assert "-" in item.id  # UUID format

    def test_to_item_source_url_empty_when_no_dblp_url(self) -> None:
        """When dblp_url is empty, source_url should be empty string."""
        handler = DBLPHandler()
        publication = {
            "id": "10.1000/test.2026",
            "title": "Test",
            "authors": [],
            "published_date": "",
            "source_type": "conference",
            "venue": "",
            "dblp_url": "",
        }

        item = handler.to_item(publication)
        assert item.source_url == ""

    def test_to_item_content_is_empty(self) -> None:
        """DBLP doesn't provide abstracts — content should be empty string."""
        handler = DBLPHandler()
        publication = {
            "id": "10.1000/test.2026",
            "title": "Test",
            "authors": ["Author"],
            "published_date": "2026",
            "source_type": "ICML",
            "venue": "ICML",
            "dblp_url": "https://dblp.org/rec/conf/test",
        }

        item = handler.to_item(publication)
        assert item.content == ""


# ---------------------------------------------------------------------------
# Rate limiting tests
# ---------------------------------------------------------------------------


class TestDBLPRateLimit:
    """Tests for rate limiter behaviour."""

    def test_default_rate_limit_is_1_rps(self) -> None:
        """Default rate limit should be 1 request/second."""
        handler = DBLPHandler()
        assert handler.max_rps == RATE_LIMIT
        assert handler.max_rps == 1

    def test_rate_limit_first_call_instant(self) -> None:
        """First call should not block (no previous request recorded)."""
        handler = DBLPHandler()
        resp = _make_response(_make_hit_response(SAMPLE_HITS))

        with patch("httpx.get", return_value=resp):
            t0 = time.time()
            handler.fetch("test", limit=1)
            elapsed = time.time() - t0

        assert elapsed < 0.3  # should be near-instant

    def test_rate_limit_enforces_min_interval(self) -> None:
        """Back-to-back calls should be spaced by at least 1/max_rps."""
        handler = DBLPHandler()
        resp = _make_response(_make_hit_response(SAMPLE_HITS))

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


class TestDBLPErrorHandling:
    """Tests for retry logic and error propagation."""

    def test_retry_on_timeout(self) -> None:
        """After repeated TimeoutExceptions, fetch should return empty list."""
        handler = DBLPHandler()
        call_count = 0

        def _fake_get(*args: object, **kwargs: object) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            msg = f"Simulated timeout (attempt {call_count})"
            raise httpx.TimeoutException(msg, request=None)  # type: ignore[arg-type]

        with patch("httpx.get", side_effect=_fake_get):
            start = time.time()
            pubs = handler.fetch("test", limit=1)
            elapsed = time.time() - start

        assert pubs == []
        assert call_count == 3
        # Expect at least 2 + 4 = 6 seconds of backoff sleep
        assert elapsed >= 6.0

    def test_retry_on_network_error(self) -> None:
        """NetworkError is retried 3 times then returns empty list."""
        handler = DBLPHandler()
        call_count = 0

        def _fake_get(*args: object, **kwargs: object) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            raise httpx.NetworkError("Simulated network error", request=None)  # type: ignore[arg-type]

        with patch("httpx.get", side_effect=_fake_get):
            pubs = handler.fetch("test", limit=1)

        assert pubs == []
        assert call_count == 3

    def test_http_error_returns_empty(self) -> None:
        """HTTP error responses should return empty list gracefully."""
        handler = DBLPHandler()

        resp = httpx.Response(
            404,
            request=httpx.Request("GET", "http://test.com"),
        )

        with patch("httpx.get", return_value=resp):
            pubs = handler.fetch("test", limit=1)

        assert pubs == []

    def test_fetch_handles_non_json_response(self) -> None:
        """Non-JSON response should return empty list gracefully."""
        handler = DBLPHandler()
        resp = MagicMock(spec=httpx.Response)
        resp.json.side_effect = ValueError("Expecting value: line 1 column 1")
        resp.raise_for_status.return_value = None

        with patch("httpx.get", return_value=resp):
            pubs = handler.fetch("test", limit=1)

        assert pubs == []

    def test_fetch_handles_missing_result_key(self) -> None:
        """Response missing 'result' key should return empty list."""
        handler = DBLPHandler()
        resp = _make_response({"unexpected": "format"})

        with patch("httpx.get", return_value=resp):
            pubs = handler.fetch("test", limit=1)

        assert pubs == []

    def test_fetch_handles_missing_info_key(self) -> None:
        """Hits without 'info' key should not crash."""
        handler = DBLPHandler()
        resp = _make_response({
            "result": {
                "hits": {
                    "hit": [
                        {"@score": "1", "@id": "urn:x", "info": None},
                    ],
                },
            },
        })

        with patch("httpx.get", return_value=resp):
            pubs = handler.fetch("test", limit=1)

        assert len(pubs) == 1
        assert pubs[0]["title"] == ""


# ---------------------------------------------------------------------------
# URL construction tests
# ---------------------------------------------------------------------------


class TestDBLPUrlConstruction:
    """Verify that the handler builds correct API URLs."""

    def test_query_is_url_encoded(self) -> None:
        """Spaces and special characters in the query should be URL-encoded."""
        handler = DBLPHandler()
        resp = _make_response(_make_hit_response(SAMPLE_HITS))

        with patch("httpx.get", return_value=resp) as mock_get:
            handler.fetch("machine learning & AI", limit=5)

        call_url = mock_get.call_args[0][0]
        assert "machine%20learning" in call_url or "machine+learning" in call_url
        assert "%26" in call_url or "&AI" not in call_url.split("?")[1]

    def test_fetch_uses_correct_base_url(self) -> None:
        """fetch should call the DBLP search/publ/api endpoint."""
        handler = DBLPHandler()
        resp = _make_response(_make_hit_response(SAMPLE_HITS))

        with patch("httpx.get", return_value=resp) as mock_get:
            handler.fetch("machine learning", limit=5)

        call_url = mock_get.call_args[0][0]
        assert "dblp.org/search/publ/api" in call_url
