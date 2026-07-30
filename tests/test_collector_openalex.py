"""Tests for the OpenAlex academic collector handler.

Uses ``unittest.mock.patch`` to mock HTTP responses so tests are
deterministic and fast — no real API calls.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from autoinfo.collectors.openalex import OpenAlexHandler


# ---------------------------------------------------------------------------
# Sample OpenAlex API response data
# ---------------------------------------------------------------------------

SAMPLE_OPENALEX_RESPONSE: dict[str, Any] = {
    "meta": {"count": 2, "db_response_time_ms": 45, "page": 1, "per_page": 25},
    "results": [
        {
            "id": "https://openalex.org/W2741809807",
            "doi": "https://doi.org/10.1038/nature21369",
            "title": "Microenvironmental regulation of tumour angiogenesis",
            "display_name": "Microenvironmental regulation of tumour angiogenesis",
            "publication_date": "2017-02-16",
            "abstract_inverted_index": {
                "Tumour": [0],
                "angiogenesis": [1],
                "is": [2],
                "regulated": [3],
                "by": [4],
                "the": [5],
                "microenvironment.": [6],
            },
            "cited_by_count": 245,
            "authorships": [
                {
                    "author_position": "first",
                    "author": {
                        "id": "https://openalex.org/A5061435288",
                        "display_name": "Michele De Palma",
                        "orcid": "https://orcid.org/0000-0002-2016-3921",
                    },
                },
                {
                    "author_position": "last",
                    "author": {
                        "id": "https://openalex.org/A5026349996",
                        "display_name": "Luigi Naldini",
                        "orcid": "https://orcid.org/0000-0001-9088-8458",
                    },
                },
            ],
        },
        {
            "id": "https://openalex.org/W3123456789",
            "doi": "https://doi.org/10.1126/science.aam8992",
            "title": "A second title about embryo development",
            "display_name": "A second title about embryo development",
            "publication_date": "2018-05-10",
            "abstract_inverted_index": {},
            "cited_by_count": 89,
            "authorships": [],
        },
    ],
}

SAMPLE_EMPTY_RESPONSE: dict[str, Any] = {
    "meta": {"count": 0, "db_response_time_ms": 12, "page": 1, "per_page": 25},
    "results": [],
}

SAMPLE_OPENALEX_SINGLE: dict[str, Any] = {
    "meta": {"count": 1, "db_response_time_ms": 30, "page": 1, "per_page": 25},
    "results": [
        {
            "id": "https://openalex.org/W1111111111",
            "doi": "https://doi.org/10.1000/test.2026",
            "title": "Test Paper with Complete Metadata",
            "display_name": "Test Paper with Complete Metadata",
            "publication_date": "2026-01-15",
            "abstract_inverted_index": {
                "Background:": [0],
                "This": [1],
                "study": [2],
                "examines": [3],
                "important": [4],
                "findings.": [5],
                "Methods:": [6],
                "We": [7],
                "used": [8],
                "novel": [9],
                "techniques.": [10],
                "Results:": [11],
                "The": [12],
                "data": [13],
                "shows": [14],
                "significance.": [15],
            },
            "cited_by_count": 42,
            "authorships": [
                {
                    "author_position": "first",
                    "author": {
                        "id": "https://openalex.org/A5000000001",
                        "display_name": "John Smith",
                        "orcid": "https://orcid.org/0000-0000-0000-0001",
                    },
                },
                {
                    "author_position": "middle",
                    "author": {
                        "id": "https://openalex.org/A5000000002",
                        "display_name": "Jane Doe",
                        "orcid": "https://orcid.org/0000-0000-0000-0002",
                    },
                },
            ],
        },
    ],
}

SAMPLE_NO_ABSTRACT_INDEX: dict[str, Any] = {
    "meta": {"count": 1, "db_response_time_ms": 20, "page": 1, "per_page": 25},
    "results": [
        {
            "id": "https://openalex.org/W9999999999",
            "doi": "https://doi.org/10.1000/noabstract.2026",
            "title": "Paper Without Abstract Index",
            "display_name": "Paper Without Abstract Index",
            "publication_date": "2026-06-01",
            "cited_by_count": 5,
            "authorships": [],
        },
    ],
}

SAMPLE_OPENALEX_NO_DOI: dict[str, Any] = {
    "meta": {"count": 1, "db_response_time_ms": 20, "page": 1, "per_page": 25},
    "results": [
        {
            "id": "https://openalex.org/W8888888888",
            "title": "Paper With No DOI",
            "display_name": "Paper With No DOI",
            "publication_date": "2025-12-01",
            "abstract_inverted_index": {
                "Simple": [0],
                "abstract": [1],
                "text.": [2],
            },
            "cited_by_count": 3,
            "authorships": [
                {
                    "author_position": "first",
                    "author": {
                        "id": "https://openalex.org/A5000000003",
                        "display_name": "Alice Wang",
                        "orcid": None,
                    },
                },
            ],
        },
    ],
}


# ---------------------------------------------------------------------------
# Tests: handler existence and construction
# ---------------------------------------------------------------------------


class TestOpenAlexHandlerExists:
    """Verify the handler class is importable and constructable."""

    def test_handler_is_importable(self) -> None:
        """OpenAlexHandler should be accessible from openalex module."""
        assert OpenAlexHandler is not None

    def test_creates_with_default_config(self) -> None:
        """Handler instantiates with an empty config dict."""
        handler = OpenAlexHandler({})
        assert handler.source_type == "openalex"
        assert handler.config == {}
        assert handler.rate_limit == 10

    def test_creates_with_full_config(self) -> None:
        """Handler picks up query, filters, and custom rate limit."""
        config = {
            "query": "CRISPR",
            "filters": "publication_year:2024",
            "rate_limit_per_second": 5,
        }
        handler = OpenAlexHandler(config)
        assert handler.config == config
        assert handler.config["query"] == "CRISPR"
        assert handler.config["filters"] == "publication_year:2024"
        assert handler.rate_limit == 5

    def test_source_type_is_openalex(self) -> None:
        """The source_type class attribute must be 'openalex'."""
        assert OpenAlexHandler.source_type == "openalex"


# ---------------------------------------------------------------------------
# Tests: fetch returns a list
# ---------------------------------------------------------------------------


class TestOpenAlexFetch:
    """Tests for the fetch method."""

    @patch("autoinfo.collectors.openalex.httpx.get")
    def test_fetch_returns_list(self, mock_get: MagicMock) -> None:
        """fetch() should return a list of dicts."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = SAMPLE_OPENALEX_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = OpenAlexHandler({})
        items = handler.fetch(limit=10)

        assert isinstance(items, list)
        assert len(items) == 2

    @patch("autoinfo.collectors.openalex.httpx.get")
    def test_fetch_each_item_is_dict(self, mock_get: MagicMock) -> None:
        """Each returned item must be a dict."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = SAMPLE_OPENALEX_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = OpenAlexHandler({})
        items = handler.fetch(limit=10)

        for item in items:
            assert isinstance(item, dict)

    @patch("autoinfo.collectors.openalex.httpx.get")
    def test_fetch_respects_limit(self, mock_get: MagicMock) -> None:
        """fetch should respect the limit argument."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = SAMPLE_OPENALEX_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = OpenAlexHandler({})
        items = handler.fetch(limit=1)

        assert len(items) == 1

    @patch("autoinfo.collectors.openalex.httpx.get")
    def test_fetch_uses_correct_endpoint(self, mock_get: MagicMock) -> None:
        """fetch should call the OpenAlex /works endpoint."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = SAMPLE_OPENALEX_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = OpenAlexHandler({"query": "embryo development"})
        handler.fetch(limit=5)

        mock_get.assert_called_once()
        call_args = mock_get.call_args
        url = call_args[0][0] if call_args[0] else ""
        assert "api.openalex.org/works" in url
        assert "search=embryo+development" in url or "embryo%20development" in url


# ---------------------------------------------------------------------------
# Tests: empty response handling
# ---------------------------------------------------------------------------


class TestOpenAlexFetchEmpty:
    """Tests for empty or no-result responses."""

    @patch("autoinfo.collectors.openalex.httpx.get")
    def test_fetch_handles_empty_results(self, mock_get: MagicMock) -> None:
        """An empty results list should return an empty list."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = SAMPLE_EMPTY_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = OpenAlexHandler({"query": "NONEXISTENTQUERY999999"})
        items = handler.fetch(limit=10)

        assert items == []

    @patch("autoinfo.collectors.openalex.httpx.get")
    def test_fetch_handles_missing_results_key(self, mock_get: MagicMock) -> None:
        """Response without a 'results' key should return empty list."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = {"meta": {"count": 0}}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = OpenAlexHandler({})
        items = handler.fetch(limit=10)

        assert items == []

    @patch("autoinfo.collectors.openalex.httpx.get")
    def test_fetch_limit_zero_returns_empty(self, mock_get: MagicMock) -> None:
        """A limit of 0 should result in an empty list."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = SAMPLE_OPENALEX_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = OpenAlexHandler({})
        items = handler.fetch(limit=0)

        assert items == []


# ---------------------------------------------------------------------------
# Tests: field mapping
# ---------------------------------------------------------------------------


class TestOpenAlexFieldMapping:
    """Tests for mapping OpenAlex JSON fields to AutoInfo item format."""

    @patch("autoinfo.collectors.openalex.httpx.get")
    def test_field_mapping_id(self, mock_get: MagicMock) -> None:
        """id should come from the 'id' field (OpenAlex URL ID)."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = SAMPLE_OPENALEX_SINGLE
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = OpenAlexHandler({})
        items = handler.fetch(limit=10)

        assert items[0]["id"] == "https://openalex.org/W1111111111"

    @patch("autoinfo.collectors.openalex.httpx.get")
    def test_field_mapping_title(self, mock_get: MagicMock) -> None:
        """title should come from the 'title' field."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = SAMPLE_OPENALEX_SINGLE
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = OpenAlexHandler({})
        items = handler.fetch(limit=10)

        assert items[0]["title"] == "Test Paper with Complete Metadata"

    @patch("autoinfo.collectors.openalex.httpx.get")
    def test_field_mapping_abstract_reconstructed(self, mock_get: MagicMock) -> None:
        """Abstract should be reconstructed from abstract_inverted_index."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = SAMPLE_OPENALEX_SINGLE
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = OpenAlexHandler({})
        items = handler.fetch(limit=10)

        abstract = items[0]["abstract"]
        assert "Background:" in abstract
        assert "This study examines important findings." in abstract
        assert "Methods:" in abstract
        assert "We used novel techniques." in abstract
        assert "Results:" in abstract
        assert "The data shows significance." in abstract

    @patch("autoinfo.collectors.openalex.httpx.get")
    def test_field_mapping_empty_abstract(self, mock_get: MagicMock) -> None:
        """Empty abstract_inverted_index should yield empty abstract string."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = SAMPLE_OPENALEX_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = OpenAlexHandler({})
        items = handler.fetch(limit=10)

        # Second item has empty abstract_inverted_index
        assert items[1]["abstract"] == ""

    @patch("autoinfo.collectors.openalex.httpx.get")
    def test_field_mapping_no_abstract_index_key(self, mock_get: MagicMock) -> None:
        """If abstract_inverted_index is missing entirely, abstract is empty."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = SAMPLE_NO_ABSTRACT_INDEX
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = OpenAlexHandler({})
        items = handler.fetch(limit=10)

        assert items[0]["abstract"] == ""

    @patch("autoinfo.collectors.openalex.httpx.get")
    def test_field_mapping_authors(self, mock_get: MagicMock) -> None:
        """Authors should be a list of author display names."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = SAMPLE_OPENALEX_SINGLE
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = OpenAlexHandler({})
        items = handler.fetch(limit=10)

        authors = items[0]["authors"]
        assert isinstance(authors, list)
        assert len(authors) == 2
        assert "John Smith" in authors
        assert "Jane Doe" in authors

    @patch("autoinfo.collectors.openalex.httpx.get")
    def test_field_mapping_empty_authors(self, mock_get: MagicMock) -> None:
        """Empty authorships list should yield empty authors list."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = SAMPLE_OPENALEX_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = OpenAlexHandler({})
        items = handler.fetch(limit=10)

        assert items[1]["authors"] == []

    @patch("autoinfo.collectors.openalex.httpx.get")
    def test_field_mapping_cited_by_count(self, mock_get: MagicMock) -> None:
        """cited_by_count should match the API value."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = SAMPLE_OPENALEX_SINGLE
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = OpenAlexHandler({})
        items = handler.fetch(limit=10)

        assert items[0]["cited_by_count"] == 42

    @patch("autoinfo.collectors.openalex.httpx.get")
    def test_field_mapping_published_date(self, mock_get: MagicMock) -> None:
        """published_date should match the API publication_date."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = SAMPLE_OPENALEX_SINGLE
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = OpenAlexHandler({})
        items = handler.fetch(limit=10)

        assert items[0]["published_date"] == "2026-01-15"

    @patch("autoinfo.collectors.openalex.httpx.get")
    def test_field_mapping_all_expected_fields_present(self, mock_get: MagicMock) -> None:
        """Every returned item must have all expected keys."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = SAMPLE_OPENALEX_SINGLE
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = OpenAlexHandler({})
        items = handler.fetch(limit=10)

        expected_fields = {
            "id", "title", "abstract", "authors",
            "cited_by_count", "published_date",
        }
        for item in items:
            for field in expected_fields:
                assert field in item, f"Item missing field: {field}"

    @patch("autoinfo.collectors.openalex.httpx.get")
    def test_field_mapping_no_doi_falls_back_to_id(self, mock_get: MagicMock) -> None:
        """When DOI is missing, id should use the OpenAlex work ID."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = SAMPLE_OPENALEX_NO_DOI
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = OpenAlexHandler({})
        items = handler.fetch(limit=10)

        assert items[0]["id"] == "https://openalex.org/W8888888888"


# ---------------------------------------------------------------------------
# Tests: error handling (graceful degradation)
# ---------------------------------------------------------------------------


class TestOpenAlexErrorHandling:
    """Tests for HTTP errors, non-JSON responses, and network failures."""

    @patch("autoinfo.collectors.openalex.httpx.get")
    def test_fetch_http_error_returns_empty(self, mock_get: MagicMock) -> None:
        """HTTP errors should log + return empty list (graceful degradation)."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server error",
            request=MagicMock(),
            response=MagicMock(status_code=500),
        )
        mock_get.return_value = mock_response

        handler = OpenAlexHandler({})
        items = handler.fetch(limit=10)

        assert items == []

    @patch("autoinfo.collectors.openalex.httpx.get")
    def test_fetch_network_error_returns_empty(self, mock_get: MagicMock) -> None:
        """Network errors should return empty list."""
        mock_get.side_effect = httpx.NetworkError("Connection refused")

        handler = OpenAlexHandler({})
        items = handler.fetch(limit=10)

        assert items == []

    @patch("autoinfo.collectors.openalex.httpx.get")
    def test_fetch_timeout_returns_empty(self, mock_get: MagicMock) -> None:
        """Timeout errors should return empty list gracefully."""
        mock_get.side_effect = httpx.TimeoutException(
            "Request timed out",
            request=MagicMock(),
        )

        handler = OpenAlexHandler({})
        items = handler.fetch(limit=10)

        assert items == []

    @patch("autoinfo.collectors.openalex.httpx.get")
    def test_fetch_non_json_response_handled_gracefully(self, mock_get: MagicMock) -> None:
        """If API returns non-JSON, handle gracefully with empty list."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.side_effect = ValueError("Expecting value: line 1 column 1")
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = OpenAlexHandler({})
        items = handler.fetch(limit=10)

        assert items == []

    @patch("autoinfo.collectors.openalex.httpx.get")
    def test_fetch_malformed_item_skipped(self, mock_get: MagicMock) -> None:
        """An item that fails mapping should be skipped gracefully."""
        response = {
            "meta": {"count": 2},
            "results": [
                {  # Missing required fields entirely
                    "id": "https://openalex.org/W123",
                },
                {  # Good item
                    "id": "https://openalex.org/W456",
                    "title": "Good Paper",
                    "publication_date": "2026-01-01",
                    "abstract_inverted_index": {
                        "Hello": [0],
                        "world.": [1],
                    },
                    "cited_by_count": 10,
                    "authorships": [
                        {
                            "author": {
                                "id": "https://openalex.org/A1",
                                "display_name": "Test Author",
                            },
                        },
                    ],
                },
            ],
        }

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = response
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = OpenAlexHandler({})
        items = handler.fetch(limit=10)

        # Both items should be returned; bad item gets empty strings
        assert len(items) == 2
        assert items[0]["title"] == ""  # no title in first item
        assert items[1]["title"] == "Good Paper"


# ---------------------------------------------------------------------------
# Tests: rate limiting
# ---------------------------------------------------------------------------


class TestOpenAlexRateLimit:
    """Tests for rate limiter behaviour."""

    @patch("autoinfo.collectors.openalex.httpx.get")
    def test_rate_limit_first_call_instant(self, mock_get: MagicMock) -> None:
        """First call should not block (no previous request recorded)."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = SAMPLE_EMPTY_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        import time
        handler = OpenAlexHandler({})

        t0 = time.time()
        handler.fetch(limit=5)
        elapsed = time.time() - t0

        assert elapsed < 0.3  # should be near-instant

    @patch("autoinfo.collectors.openalex.httpx.get")
    def test_rate_limit_enforces_min_interval(self, mock_get: MagicMock) -> None:
        """Back-to-back calls should be spaced by at least 1/max_rps."""
        import time

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = SAMPLE_EMPTY_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = OpenAlexHandler({"rate_limit_per_second": 5})
        # Ensure the handler rate limit is 5 rps
        assert handler.rate_limit == 5

        handler.fetch(limit=5)  # warms _last_request_time
        t0 = time.time()
        handler.fetch(limit=5)  # should wait
        elapsed = time.time() - t0

        min_interval = 1.0 / handler.rate_limit  # 0.2 s
        assert elapsed >= min_interval * 0.9  # 10 % tolerance


# ---------------------------------------------------------------------------
# Tests: abstract reconstruction helper
# ---------------------------------------------------------------------------


class TestAbstractReconstruction:
    """Unit tests for _reconstruct_abstract static/helper method."""

    def test_empty_index_returns_empty(self) -> None:
        """Empty dict or None should return empty string."""
        from autoinfo.collectors.openalex import OpenAlexHandler
        assert OpenAlexHandler._reconstruct_abstract({}) == ""
        assert OpenAlexHandler._reconstruct_abstract(None) == ""

    def test_simple_reconstruction(self) -> None:
        """Words should be ordered by position index."""
        from autoinfo.collectors.openalex import OpenAlexHandler
        inverted = {
            "first": [0],
            "second": [1],
            "third": [2],
        }
        result = OpenAlexHandler._reconstruct_abstract(inverted)
        assert result == "first second third"

    def test_multi_position_words(self) -> None:
        """A word appearing at multiple positions should appear at each."""
        from autoinfo.collectors.openalex import OpenAlexHandler
        inverted = {
            "the": [0, 3],
            "cat": [1],
            "sat": [2],
            "mat": [4],
        }
        result = OpenAlexHandler._reconstruct_abstract(inverted)
        assert result == "the cat sat the mat"

    def test_unordered_positions(self) -> None:
        """Input words can be in any order; output must be sorted by position."""
        from autoinfo.collectors.openalex import OpenAlexHandler
        inverted = {
            "zebra": [2],
            "alpha": [0],
            "beta": [1],
        }
        result = OpenAlexHandler._reconstruct_abstract(inverted)
        assert result == "alpha beta zebra"


# ---------------------------------------------------------------------------
# Tests: to_item conversion
# ---------------------------------------------------------------------------


class TestOpenAlexToItem:
    """Tests for ``OpenAlexHandler.to_item()``."""

    def test_to_item_complete(self) -> None:
        """A fully populated article dict converts to a correct Item."""
        from autoinfo.models import Item

        handler = OpenAlexHandler({})
        article = {
            "id": "https://openalex.org/W1111111111",
            "title": "Test Article Title",
            "abstract": "This is the abstract of the test article.",
            "authors": ["John Smith", "Jane Doe"],
            "cited_by_count": 42,
            "published_date": "2026-01-15",
        }

        item = handler.to_item(article)

        assert isinstance(item, Item)
        assert item.id == "https://openalex.org/W1111111111"
        assert item.source_name == "openalex"
        assert item.source_type == "api"
        assert item.source_platform == "openalex"
        assert item.title == "Test Article Title"
        assert item.content == "This is the abstract of the test article."
        assert item.content_type == "text"
        assert item.domain == "medical-research"
        assert item.collected_at == "2026-01-15"
        assert "authors" in item.raw_data
        assert item.raw_data["authors"] == ["John Smith", "Jane Doe"]
        assert item.raw_data["cited_by_count"] == 42

    def test_to_item_empty_id_uses_uuid(self) -> None:
        """When id is empty, a UUID should be generated as the item id."""
        from autoinfo.models import Item

        handler = OpenAlexHandler({})
        article = {
            "id": "",
            "title": "No ID",
            "abstract": "",
            "authors": [],
            "cited_by_count": 0,
            "published_date": "",
        }

        item = handler.to_item(article)

        assert item.id
        assert item.id != ""
        assert "-" in item.id  # UUID contains hyphens
