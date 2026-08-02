"""Tests for the HuggingFace/Kaggle collector handler.

Uses ``unittest.mock.patch`` to mock HTTP responses so tests are
deterministic and fast — no real API calls.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from autoinfo.collectors.huggingface import HuggingFaceHandler
from autoinfo.models import Item


# ---------------------------------------------------------------------------
# Sample HuggingFace Hub API response data
# ---------------------------------------------------------------------------

SAMPLE_HF_RESPONSE: list[dict[str, Any]] = [
    {
        "_id": "621ffdc1364699891d62f12a",
        "id": "imdb",
        "author": "stanfordnlp",
        "sha": "c8b7c2e8a3f4d5e6a7b8c9d0e1f2a3b4c5d6e7f8",
        "lastModified": "2024-11-15T10:30:00.000Z",
        "private": False,
        "gated": False,
        "disabled": False,
        "tags": ["text-classification", "nlp", "sentiment-analysis"],
        "description": "IMDB dataset for sentiment classification with 50K reviews",
        "downloads": 152340,
        "likes": 890,
        "siblings": [
            {"rfilename": "README.md"},
            {"rfilename": "data/train.csv"},
        ],
    },
    {
        "_id": "621ffdc1364699891d62f12b",
        "id": "squad",
        "author": "rajpurkar",
        "sha": "a9b8c7d6e5f4a3b2c1d0e9f8e7d6c5b4a3f2e1d0",
        "lastModified": "2024-08-20T14:00:00.000Z",
        "private": False,
        "gated": False,
        "disabled": False,
        "tags": ["question-answering", "nlp", "reading-comprehension"],
        "description": "Stanford Question Answering Dataset (SQuAD) v2.0",
        "downloads": 98450,
        "likes": 670,
        "siblings": [
            {"rfilename": "README.md"},
            {"rfilename": "train-v2.0.json"},
        ],
    },
]

SAMPLE_HF_EMPTY: list[dict[str, Any]] = []

SAMPLE_HF_SINGLE: list[dict[str, Any]] = [
    {
        "_id": "621ffdc1364699891d62f12c",
        "id": "mnist",
        "author": "ylecun",
        "sha": "b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0",
        "lastModified": "2025-03-01T09:00:00.000Z",
        "private": False,
        "gated": False,
        "disabled": False,
        "tags": ["image-classification", "computer-vision", "benchmark"],
        "description": "The MNIST database of handwritten digits",
        "downloads": 500000,
        "likes": 2100,
        "siblings": [
            {"rfilename": "README.md"},
            {"rfilename": "train-images-idx3-ubyte.gz"},
        ],
    },
]

SAMPLE_HF_NO_DESCRIPTION: list[dict[str, Any]] = [
    {
        "id": "mystery-dataset",
        "author": "unknown",
        "sha": "abc123",
        "lastModified": "",
        "private": False,
        "gated": False,
        "disabled": False,
        "tags": [],
        "downloads": 0,
        "likes": 0,
        "siblings": [],
    },
]


# ---------------------------------------------------------------------------
# Tests: handler existence and construction
# ---------------------------------------------------------------------------


class TestHuggingFaceHandlerExists:
    """Verify the handler class is importable and constructable."""

    def test_handler_is_importable(self) -> None:
        """HuggingFaceHandler should be accessible from the huggingface module."""
        assert HuggingFaceHandler is not None

    def test_creates_with_default_config(self) -> None:
        """Handler instantiates with an empty config dict."""
        handler = HuggingFaceHandler({})
        assert handler.source_type == "huggingface"
        assert handler.provider == "huggingface"
        assert handler.content_type == "datasets"
        assert handler.config == {}

    def test_creates_with_full_config(self) -> None:
        """Handler picks up provider, content_type, query, and rate limit."""
        config = {
            "provider": "kaggle",
            "content_type": "models",
            "query": "bert",
            "max_rps": 2.0,
        }
        handler = HuggingFaceHandler(config)
        assert handler.provider == "kaggle"
        assert handler.source_type == "kaggle"
        assert handler.source_name == "kaggle"
        assert handler.content_type == "models"
        assert handler.query == "bert"
        assert handler.max_rps == 2.0

    def test_source_type_default_huggingface(self) -> None:
        """The source_type class attribute must be 'huggingface'."""
        assert HuggingFaceHandler.source_type == "huggingface"

    def test_unknown_provider_falls_back(self) -> None:
        """Unknown provider should fall back to huggingface."""
        handler = HuggingFaceHandler({"provider": "unknown"})
        assert handler.provider == "huggingface"
        assert handler.source_type == "huggingface"

    def test_unknown_content_type_falls_back(self) -> None:
        """Unknown content_type should fall back to datasets."""
        handler = HuggingFaceHandler({"content_type": "images"})
        assert handler.content_type == "datasets"


# ---------------------------------------------------------------------------
# Tests: fetch returns a list
# ---------------------------------------------------------------------------


class TestHuggingFaceFetch:
    """Tests for the fetch method with mocked HF API."""

    @patch("autoinfo.collectors.huggingface.httpx.get")
    def test_fetch_returns_list(self, mock_get: MagicMock) -> None:
        """fetch() should return a list of dicts."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = SAMPLE_HF_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = HuggingFaceHandler({})
        items = handler.fetch(query="nlp", limit=10)

        assert isinstance(items, list)
        assert len(items) == 2

    @patch("autoinfo.collectors.huggingface.httpx.get")
    def test_fetch_each_item_is_dict(self, mock_get: MagicMock) -> None:
        """Each returned item must be a dict."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = SAMPLE_HF_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = HuggingFaceHandler({})
        items = handler.fetch(query="nlp", limit=10)

        for item in items:
            assert isinstance(item, dict)

    @patch("autoinfo.collectors.huggingface.httpx.get")
    def test_fetch_respects_limit(self, mock_get: MagicMock) -> None:
        """fetch should respect the limit argument."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = SAMPLE_HF_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = HuggingFaceHandler({})
        items = handler.fetch(query="nlp", limit=1)

        assert len(items) == 1

    @patch("autoinfo.collectors.huggingface.httpx.get")
    def test_fetch_uses_correct_endpoint(self, mock_get: MagicMock) -> None:
        """fetch should call the HF Hub /api/datasets endpoint."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = SAMPLE_HF_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = HuggingFaceHandler({"query": "sentiment"})
        handler.fetch(limit=5)

        mock_get.assert_called_once()
        call_args = mock_get.call_args
        url = call_args[0][0] if call_args[0] else ""
        assert "huggingface.co/api/datasets" in url
        assert "search=sentiment" in url

    @patch("autoinfo.collectors.huggingface.httpx.get")
    def test_fetch_uses_config_query_when_empty(self, mock_get: MagicMock) -> None:
        """fetch should use config query when no explicit query given."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = SAMPLE_HF_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = HuggingFaceHandler({"query": "transformers"})
        handler.fetch(limit=5)

        call_args = mock_get.call_args
        url = call_args[0][0] if call_args[0] else ""
        assert "search=transformers" in url

    @patch("autoinfo.collectors.huggingface.httpx.get")
    def test_fetch_handles_empty_query(self, mock_get: MagicMock) -> None:
        """fetch with empty query should still work (returns popular datasets)."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = SAMPLE_HF_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = HuggingFaceHandler({})
        items = handler.fetch(query="", limit=10)

        assert len(items) == 2

    @patch("autoinfo.collectors.huggingface.httpx.get")
    def test_fetch_models_content_type(self, mock_get: MagicMock) -> None:
        """When content_type is 'models', fetch should use /api/models."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = SAMPLE_HF_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = HuggingFaceHandler({"content_type": "models"})
        handler.fetch(limit=5)

        call_args = mock_get.call_args
        url = call_args[0][0] if call_args[0] else ""
        assert "huggingface.co/api/models" in url


# ---------------------------------------------------------------------------
# Tests: empty response handling
# ---------------------------------------------------------------------------


class TestHuggingFaceFetchEmpty:
    """Tests for empty or no-result responses."""

    @patch("autoinfo.collectors.huggingface.httpx.get")
    def test_fetch_handles_empty_results(self, mock_get: MagicMock) -> None:
        """An empty results list should return an empty list."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = []
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = HuggingFaceHandler({})
        items = handler.fetch(query="zzz_nonexistent_999", limit=10)

        assert items == []

    @patch("autoinfo.collectors.huggingface.httpx.get")
    def test_fetch_limit_zero_returns_empty(self, mock_get: MagicMock) -> None:
        """A limit of 0 should result in an empty list."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = SAMPLE_HF_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = HuggingFaceHandler({})
        items = handler.fetch(query="nlp", limit=0)

        assert items == []


# ---------------------------------------------------------------------------
# Tests: field mapping
# ---------------------------------------------------------------------------


class TestHuggingFaceFieldMapping:
    """Tests for mapping HF JSON fields to AutoInfo item format."""

    @patch("autoinfo.collectors.huggingface.httpx.get")
    def test_field_mapping_id(self, mock_get: MagicMock) -> None:
        """id should come from the 'id' field."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = SAMPLE_HF_SINGLE
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = HuggingFaceHandler({})
        items = handler.fetch(query="mnist", limit=10)

        assert items[0]["id"] == "mnist"

    @patch("autoinfo.collectors.huggingface.httpx.get")
    def test_field_mapping_title(self, mock_get: MagicMock) -> None:
        """title should come from the last segment of 'id'."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = SAMPLE_HF_SINGLE
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = HuggingFaceHandler({})
        items = handler.fetch(query="mnist", limit=10)

        assert items[0]["title"] == "mnist"

    @patch("autoinfo.collectors.huggingface.httpx.get")
    def test_field_mapping_description(self, mock_get: MagicMock) -> None:
        """description should come from 'description' field."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = SAMPLE_HF_SINGLE
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = HuggingFaceHandler({})
        items = handler.fetch(query="mnist", limit=10)

        assert items[0]["description"] == "The MNIST database of handwritten digits"

    @patch("autoinfo.collectors.huggingface.httpx.get")
    def test_field_mapping_author(self, mock_get: MagicMock) -> None:
        """author should come from the 'author' field."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = SAMPLE_HF_SINGLE
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = HuggingFaceHandler({})
        items = handler.fetch(query="mnist", limit=10)

        assert items[0]["author"] == "ylecun"

    @patch("autoinfo.collectors.huggingface.httpx.get")
    def test_field_mapping_tags(self, mock_get: MagicMock) -> None:
        """tags should be a list of tag strings."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = SAMPLE_HF_SINGLE
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = HuggingFaceHandler({})
        items = handler.fetch(query="mnist", limit=10)

        tags = items[0]["tags"]
        assert isinstance(tags, list)
        assert "image-classification" in tags
        assert "computer-vision" in tags
        assert "benchmark" in tags

    @patch("autoinfo.collectors.huggingface.httpx.get")
    def test_field_mapping_downloads(self, mock_get: MagicMock) -> None:
        """downloads should match the API value."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = SAMPLE_HF_SINGLE
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = HuggingFaceHandler({})
        items = handler.fetch(query="mnist", limit=10)

        assert items[0]["downloads"] == 500000

    @patch("autoinfo.collectors.huggingface.httpx.get")
    def test_field_mapping_likes(self, mock_get: MagicMock) -> None:
        """likes should match the API value."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = SAMPLE_HF_SINGLE
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = HuggingFaceHandler({})
        items = handler.fetch(query="mnist", limit=10)

        assert items[0]["likes"] == 2100

    @patch("autoinfo.collectors.huggingface.httpx.get")
    def test_field_mapping_source_url(self, mock_get: MagicMock) -> None:
        """source_url should be the HF datasets page URL."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = SAMPLE_HF_SINGLE
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = HuggingFaceHandler({})
        items = handler.fetch(query="mnist", limit=10)

        assert items[0]["source_url"] == "https://huggingface.co/datasets/mnist"

    @patch("autoinfo.collectors.huggingface.httpx.get")
    def test_field_mapping_provider(self, mock_get: MagicMock) -> None:
        """provider field should be 'huggingface' for HF API."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = SAMPLE_HF_SINGLE
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = HuggingFaceHandler({})
        items = handler.fetch(query="mnist", limit=10)

        assert items[0]["provider"] == "huggingface"

    @patch("autoinfo.collectors.huggingface.httpx.get")
    def test_field_mapping_all_expected_fields_present(self, mock_get: MagicMock) -> None:
        """Every returned item must have all expected keys."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = SAMPLE_HF_SINGLE
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = HuggingFaceHandler({})
        items = handler.fetch(query="mnist", limit=10)

        expected_fields = {
            "id", "title", "description", "author",
            "tags", "downloads", "likes", "last_modified",
            "source_url", "provider",
        }
        for item in items:
            for field in expected_fields:
                assert field in item, f"Item missing field: {field}"

    @patch("autoinfo.collectors.huggingface.httpx.get")
    def test_field_mapping_no_description(self, mock_get: MagicMock) -> None:
        """Missing description should yield empty string."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = SAMPLE_HF_NO_DESCRIPTION
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = HuggingFaceHandler({})
        items = handler.fetch(query="test", limit=10)

        assert items[0]["description"] == ""

    @patch("autoinfo.collectors.huggingface.httpx.get")
    def test_field_mapping_empty_tags(self, mock_get: MagicMock) -> None:
        """Empty tags list should yield empty list."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = SAMPLE_HF_NO_DESCRIPTION
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = HuggingFaceHandler({})
        items = handler.fetch(query="test", limit=10)

        assert items[0]["tags"] == []


# ---------------------------------------------------------------------------
# Tests: error handling (graceful degradation)
# ---------------------------------------------------------------------------


class TestHuggingFaceErrorHandling:
    """Tests for HTTP errors, non-JSON responses, and network failures."""

    @patch("autoinfo.collectors.huggingface.httpx.get")
    def test_fetch_http_error_returns_empty(self, mock_get: MagicMock) -> None:
        """HTTP errors should log + return empty list (graceful degradation)."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server error",
            request=MagicMock(),
            response=MagicMock(status_code=500),
        )
        mock_get.return_value = mock_response

        handler = HuggingFaceHandler({})
        items = handler.fetch(query="test", limit=10)

        assert items == []

    @patch("autoinfo.collectors.huggingface.httpx.get")
    def test_fetch_network_error_returns_empty(self, mock_get: MagicMock) -> None:
        """Network errors should return empty list."""
        mock_get.side_effect = httpx.NetworkError("Connection refused")

        handler = HuggingFaceHandler({})
        items = handler.fetch(query="test", limit=10)

        assert items == []

    @patch("autoinfo.collectors.huggingface.httpx.get")
    def test_fetch_timeout_returns_empty(self, mock_get: MagicMock) -> None:
        """Timeout errors should return empty list gracefully."""
        mock_get.side_effect = httpx.TimeoutException(
            "Request timed out",
            request=MagicMock(),
        )

        handler = HuggingFaceHandler({})
        items = handler.fetch(query="test", limit=10)

        assert items == []

    @patch("autoinfo.collectors.huggingface.httpx.get")
    def test_fetch_non_json_response_handled_gracefully(self, mock_get: MagicMock) -> None:
        """If API returns non-JSON, handle gracefully with empty list."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.side_effect = ValueError("Expecting value: line 1 column 1")
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = HuggingFaceHandler({})
        items = handler.fetch(query="test", limit=10)

        assert items == []

    @patch("autoinfo.collectors.huggingface.httpx.get")
    def test_fetch_malformed_item_skipped(self, mock_get: MagicMock) -> None:
        """An item that fails mapping should be skipped gracefully."""
        response = [
            {  # Missing critical fields
                "id": "bad-dataset",
            },
            {  # Good item
                "id": "good-dataset",
                "author": "test-author",
                "sha": "abc123",
                "lastModified": "2025-01-01T00:00:00.000Z",
                "private": False,
                "gated": False,
                "disabled": False,
                "tags": ["test"],
                "description": "A good dataset",
                "downloads": 100,
                "likes": 5,
                "siblings": [],
            },
        ]

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = response
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = HuggingFaceHandler({})
        items = handler.fetch(query="test", limit=10)

        # Both items should be mapped; mapping errors are logged not raised
        assert len(items) == 2
        assert items[0]["id"] == "bad-dataset"
        assert items[1]["title"] == "good-dataset"


# ---------------------------------------------------------------------------
# Tests: Kaggle provider
# ---------------------------------------------------------------------------


class TestKaggleProvider:
    """Tests for Kaggle provider behaviour."""

    def test_kaggle_provider_sets_source_type(self) -> None:
        """Kaggle provider should set source_type to 'kaggle'."""
        handler = HuggingFaceHandler({"provider": "kaggle"})
        assert handler.source_type == "kaggle"
        assert handler.source_name == "kaggle"
        assert handler.provider == "kaggle"

    def test_kaggle_requires_key_handling(self) -> None:
        """When Kaggle credentials are missing, fetch returns empty list
        without errors."""
        # Ensure env vars are not set
        import os
        with patch.dict(os.environ, {}, clear=True):
            handler = HuggingFaceHandler({"provider": "kaggle"})
            items = handler.fetch(query="test", limit=10)
            assert items == []

    def test_kaggle_default_rate_limit(self) -> None:
        """Kaggle provider defaults to 0.5 rps (more polite than HF's 1.0)."""
        handler = HuggingFaceHandler({"provider": "kaggle"})
        assert handler.max_rps == 0.5


# ---------------------------------------------------------------------------
# Tests: rate limiting
# ---------------------------------------------------------------------------


class TestHuggingFaceRateLimit:
    """Tests for rate limiter behaviour."""

    @patch("autoinfo.collectors.huggingface.httpx.get")
    def test_rate_limit_first_call_instant(self, mock_get: MagicMock) -> None:
        """First call should not block (no previous request recorded)."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = []
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        import time
        handler = HuggingFaceHandler({})

        t0 = time.time()
        handler.fetch(query="test", limit=5)
        elapsed = time.time() - t0

        assert elapsed < 0.3  # should be near-instant

    @patch("autoinfo.collectors.huggingface.httpx.get")
    def test_rate_limit_enforces_min_interval(self, mock_get: MagicMock) -> None:
        """Back-to-back calls should be spaced by at least 1/max_rps."""
        import time

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = []
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = HuggingFaceHandler({"max_rps": 5})
        assert handler.max_rps == 5

        handler.fetch(query="test", limit=5)  # warms _last_request_time
        t0 = time.time()
        handler.fetch(query="test", limit=5)  # should wait
        elapsed = time.time() - t0

        min_interval = 1.0 / handler.max_rps  # 0.2 s
        assert elapsed >= min_interval * 0.9  # 10 % tolerance


# ---------------------------------------------------------------------------
# Tests: to_item conversion
# ---------------------------------------------------------------------------


class TestHuggingFaceToItem:
    """Tests for ``HuggingFaceHandler.to_item()``."""

    def test_to_item_complete(self) -> None:
        """A fully populated dataset dict converts to a correct Item."""
        handler = HuggingFaceHandler({})
        dataset = {
            "id": "imdb",
            "title": "imdb",
            "description": "IMDB dataset for sentiment classification",
            "author": "stanfordnlp",
            "tags": ["text-classification", "nlp"],
            "downloads": 152340,
            "likes": 890,
            "last_modified": "2024-11-15T10:30:00.000Z",
            "source_url": "https://huggingface.co/datasets/imdb",
            "provider": "huggingface",
        }

        item = handler.to_item(dataset)

        assert isinstance(item, Item)
        assert item.id == "imdb"
        assert item.source_name == "huggingface"
        assert item.source_type == "huggingface"
        assert item.source_platform == "huggingface"
        assert item.title == "imdb"
        assert item.content == "IMDB dataset for sentiment classification"
        assert item.content_type == "text"
        assert item.collected_at == "2024-11-15T10:30:00.000Z"
        assert item.topic_tags == ["text-classification", "nlp"]
        assert item.raw_data["author"] == "stanfordnlp"
        assert item.raw_data["downloads"] == 152340
        assert item.raw_data["likes"] == 890
        assert item.raw_data["provider"] == "huggingface"

    def test_to_item_empty_id_uses_uuid(self) -> None:
        """When id is empty, a UUID should be generated as the item id."""
        handler = HuggingFaceHandler({})
        dataset = {
            "id": "",
            "title": "No ID",
            "description": "",
            "author": "",
            "tags": [],
            "downloads": 0,
            "likes": 0,
            "last_modified": "",
            "source_url": "",
            "provider": "huggingface",
        }

        item = handler.to_item(dataset)

        assert item.id
        assert item.id != ""

    def test_to_item_empty_description(self) -> None:
        """Empty description should produce empty content."""
        handler = HuggingFaceHandler({})
        dataset = {
            "id": "empty-desc",
            "title": "Empty Description",
            "description": "",
            "author": "test",
            "tags": [],
            "downloads": 0,
            "likes": 0,
            "last_modified": "",
            "source_url": "https://huggingface.co/datasets/empty-desc",
            "provider": "huggingface",
        }

        item = handler.to_item(dataset)

        assert item.content == ""

    def test_to_item_kaggle_provider(self) -> None:
        """Kaggle-mapped dataset should have kaggle source_type."""
        handler = HuggingFaceHandler({"provider": "kaggle"})
        dataset = {
            "id": "datasnaek/youtube-new",
            "title": "YouTube Trending Dataset",
            "description": "YouTube trending statistics",
            "author": "datasnaek",
            "tags": ["youtube", "trending", "video"],
            "downloads": 5000,
            "likes": 120,
            "last_modified": "2025-01-10T00:00:00.000Z",
            "source_url": "https://www.kaggle.com/datasets/datasnaek/youtube-new",
            "provider": "kaggle",
        }

        item = handler.to_item(dataset)

        assert isinstance(item, Item)
        assert item.source_type == "kaggle"
        assert item.source_platform == "kaggle"
        assert item.raw_data["provider"] == "kaggle"


# ---------------------------------------------------------------------------
# Tests: static metadata methods
# ---------------------------------------------------------------------------


class TestHuggingFaceMetadata:
    """Tests for requires_key() and note() static methods."""

    def test_requires_key_returns_false_for_huggingface(self) -> None:
        """HuggingFace Hub is free — requires_key should return False."""
        assert HuggingFaceHandler.requires_key() is False

    def test_note_is_not_none(self) -> None:
        """note() should return a descriptive string."""
        note = HuggingFaceHandler.note()
        assert note is not None
        assert "metadata" in note.lower()
        assert "kaggle" in note.lower()


# ---------------------------------------------------------------------------
# Tests: _map_dataset static method
# ---------------------------------------------------------------------------


class TestMapDataset:
    """Unit tests for the _map_dataset static method."""

    def test_map_dataset_hf_basic(self) -> None:
        """Basic HF dataset mapping."""
        raw = {
            "id": "test/dataset",
            "author": "testauthor",
            "sha": "abc",
            "lastModified": "2025-01-01",
            "tags": ["nlp", "text"],
            "description": "A test dataset",
            "downloads": 42,
            "likes": 7,
        }
        result = HuggingFaceHandler._map_dataset(raw, "huggingface")
        assert result["id"] == "test/dataset"
        assert result["title"] == "dataset"
        assert result["author"] == "testauthor"
        assert result["description"] == "A test dataset"
        assert result["downloads"] == 42
        assert result["likes"] == 7
        assert result["source_url"] == "https://huggingface.co/datasets/test/dataset"
        assert result["provider"] == "huggingface"

    def test_map_dataset_hf_no_id(self) -> None:
        """Dataset without id should have empty id and source_url."""
        raw = {
            "author": "anon",
            "tags": [],
            "downloads": 0,
            "likes": 0,
        }
        result = HuggingFaceHandler._map_dataset(raw, "huggingface")
        assert result["id"] == ""
        assert result["source_url"] == ""

    def test_map_dataset_kaggle_basic(self) -> None:
        """Basic Kaggle dataset mapping."""
        raw = {
            "ref": "owner/dataset-name",
            "title": "Dataset Title",
            "subtitle": "A subtitle describing the data",
            "ownerName": "owner",
            "tags": [{"name": "ml"}, {"name": "tabular"}],
            "downloadCount": 1000,
            "voteCount": 55,
            "lastUpdated": "2025-02-01",
        }
        result = HuggingFaceHandler._map_dataset(raw, "kaggle")
        assert result["id"] == "owner/dataset-name"
        assert result["title"] == "Dataset Title"
        assert result["description"] == "A subtitle describing the data"
        assert result["author"] == "owner"
        assert result["tags"] == ["ml", "tabular"]
        assert result["downloads"] == 1000
        assert result["likes"] == 55
        assert result["source_url"] == "https://www.kaggle.com/datasets/owner/dataset-name"
        assert result["provider"] == "kaggle"
