"""Tests for the Quandl / Nasdaq Data Link API collector handler.

Uses ``unittest.mock.patch`` to mock HTTP responses so tests are
deterministic and fast — no real API calls.
"""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from autoinfo.collectors.quandl import QuandlHandler
from autoinfo.config import SourceConfig

# ---------------------------------------------------------------------------
# Sample Quandl API response data
# ---------------------------------------------------------------------------

SAMPLE_QUANDL_RESPONSE: dict[str, Any] = {
    "dataset": {
        "dataset_code": "AAPL",
        "database_code": "WIKI",
        "name": "Apple Inc (AAPL) Stock Prices",
        "description": "End of day stock prices for Apple Inc from 1980.",
        "column_names": ["Date", "Open", "High", "Low", "Close", "Volume"],
        "start_date": "1980-12-12",
        "end_date": "2026-07-30",
        "frequency": "daily",
        "data": [
            ["2026-07-30", 245.0, 248.5, 244.0, 247.0, 52000000],
            ["2026-07-29", 244.0, 246.0, 242.5, 245.0, 48000000],
            ["2026-07-28", 243.0, 245.0, 241.0, 244.0, 45000000],
        ],
    }
}

SAMPLE_QUANDL_MISSING_DATASET: dict[str, Any] = {
    "error": "Dataset not found",
}

SAMPLE_QUANDL_EMPTY_DATASET: dict[str, Any] = {
    "dataset": None,
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


class TestQuandlHandlerExists:
    """Verify the handler class is importable and constructable."""

    def test_handler_is_importable(self) -> None:
        """QuandlHandler should be accessible from quandl module."""
        assert QuandlHandler is not None

    def test_creates_with_config(self) -> None:
        """Handler instantiates with a SourceConfig."""
        config = SourceConfig(
            name="quandl-test",
            type="quandl",
            url="https://data.nasdaq.com/api/v3/datasets/WIKI/AAPL.json",
        )
        handler = QuandlHandler(config)
        assert handler.source_name == "quandl-test"
        assert handler.source_config is config
        assert handler._handler_type == "QuandlHandler"

    def test_handler_type_marker(self) -> None:
        """The _handler_type marker should be 'QuandlHandler'."""
        config = SourceConfig(
            name="quandl-test",
            type="quandl",
            url="https://data.nasdaq.com/api/v3/datasets/WIKI/AAPL.json",
        )
        handler = QuandlHandler(config)
        assert getattr(handler, "_handler_type", "") == "QuandlHandler"


# ---------------------------------------------------------------------------
# Tests: fetch basic behaviour
# ---------------------------------------------------------------------------


class TestQuandlFetch:
    """Tests for the fetch method."""

    @patch("autoinfo.collectors.quandl.httpx.get")
    def test_fetch_returns_items(self, mock_get: MagicMock) -> None:
        """fetch() should return a list of Item objects."""
        mock_get.return_value = _mock_response(SAMPLE_QUANDL_RESPONSE)

        config = SourceConfig(
            name="quandl-test",
            type="quandl",
            url="https://data.nasdaq.com/api/v3/datasets/WIKI/AAPL.json",
        )
        handler = QuandlHandler(config)
        from autoinfo.models import Item

        with patch.dict(os.environ, {"AUTOINFO_QUANDL_API_KEY": "test-key"}):
            items = handler.fetch(config.url, query="", limit=5)

        assert isinstance(items, list)
        assert len(items) == 1
        assert isinstance(items[0], Item)

    @patch("autoinfo.collectors.quandl.httpx.get")
    def test_fetch_field_mapping(self, mock_get: MagicMock) -> None:
        """Fields should be mapped correctly from Quandl response."""
        mock_get.return_value = _mock_response(SAMPLE_QUANDL_RESPONSE)

        config = SourceConfig(
            name="quandl-test",
            type="quandl",
            url="https://data.nasdaq.com/api/v3/datasets/WIKI/AAPL.json",
        )
        handler = QuandlHandler(config)
        with patch.dict(os.environ, {"AUTOINFO_QUANDL_API_KEY": "test-key"}):
            items = handler.fetch(config.url, limit=5)

        assert len(items) == 1
        item = items[0]
        assert item.id == "AAPL"
        assert item.title == "Apple Inc (AAPL) Stock Prices"
        assert "End of day stock prices" in item.content
        assert item.source_type == "quandl"
        assert item.source_name == "quandl-test"

    @patch("autoinfo.collectors.quandl.httpx.get")
    def test_fetch_api_key_in_params(self, mock_get: MagicMock) -> None:
        """API key should be passed as query parameter."""
        mock_get.return_value = _mock_response(SAMPLE_QUANDL_RESPONSE)

        config = SourceConfig(
            name="quandl-test",
            type="quandl",
            url="https://data.nasdaq.com/api/v3/datasets/WIKI/AAPL.json",
        )
        handler = QuandlHandler(config)

        with patch.dict(os.environ, {"AUTOINFO_QUANDL_API_KEY": "test-key-123"}):
            handler.fetch(config.url, limit=5)

        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args.kwargs
        assert call_kwargs["params"]["api_key"] == "test-key-123"

    @patch("autoinfo.collectors.quandl.httpx.get")
    def test_fetch_rows_param(self, mock_get: MagicMock) -> None:
        """rows parameter should be included when limit > 0."""
        mock_get.return_value = _mock_response(SAMPLE_QUANDL_RESPONSE)

        config = SourceConfig(
            name="quandl-test",
            type="quandl",
            url="https://data.nasdaq.com/api/v3/datasets/WIKI/AAPL.json",
        )
        handler = QuandlHandler(config)

        with patch.dict(os.environ, {"AUTOINFO_QUANDL_API_KEY": "test-key"}):
            handler.fetch(config.url, limit=3)

        call_kwargs = mock_get.call_args.kwargs
        assert call_kwargs["params"]["rows"] == 3


# ---------------------------------------------------------------------------
# Tests: raw_data contains full dataset metadata
# ---------------------------------------------------------------------------


class TestQuandlRawData:
    """Tests for raw_data in the returned items."""

    @patch("autoinfo.collectors.quandl.httpx.get")
    def test_raw_data_contains_all_fields(self, mock_get: MagicMock) -> None:
        """raw_data should contain all dataset fields from the API response."""
        mock_get.return_value = _mock_response(SAMPLE_QUANDL_RESPONSE)

        config = SourceConfig(
            name="quandl-test",
            type="quandl",
            url="https://data.nasdaq.com/api/v3/datasets/WIKI/AAPL.json",
        )
        handler = QuandlHandler(config)
        with patch.dict(os.environ, {"AUTOINFO_QUANDL_API_KEY": "test-key"}):
            items = handler.fetch(config.url, limit=5)

        raw = items[0].raw_data
        assert raw["dataset_code"] == "AAPL"
        assert raw["database_code"] == "WIKI"
        assert raw["frequency"] == "daily"
        assert raw["start_date"] == "1980-12-12"
        assert "column_names" in raw
        assert "data" in raw
        assert len(raw["data"]) == 3  # latest 3 rows


# ---------------------------------------------------------------------------
# Tests: error handling
# ---------------------------------------------------------------------------


class TestQuandlErrorHandling:
    """Tests for error handling (empty list on failure)."""

    @patch("autoinfo.collectors.quandl.httpx.get")
    def test_fetch_missing_api_key(self, mock_get: MagicMock) -> None:
        """When no API key is set, fetch returns empty list without making a request."""
        config = SourceConfig(
            name="quandl-test",
            type="quandl",
            url="https://data.nasdaq.com/api/v3/datasets/WIKI/AAPL.json",
        )
        handler = QuandlHandler(config)

        with patch.dict(os.environ, clear=True):
            items = handler.fetch(config.url, limit=5)

        assert items == []
        mock_get.assert_not_called()

    @patch("autoinfo.collectors.quandl.httpx.get")
    def test_fetch_http_error_returns_empty(self, mock_get: MagicMock) -> None:
        """HTTP errors should return empty list."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found",
            request=MagicMock(),
            response=MagicMock(status_code=404),
        )
        mock_get.return_value = mock_response

        config = SourceConfig(
            name="quandl-test",
            type="quandl",
            url="https://data.nasdaq.com/api/v3/datasets/WIKI/INVALID.json",
        )
        handler = QuandlHandler(config)

        with patch.dict(os.environ, {"AUTOINFO_QUANDL_API_KEY": "test-key"}):
            items = handler.fetch(config.url, limit=5)

        assert items == []

    @patch("autoinfo.collectors.quandl.httpx.get")
    def test_fetch_network_error_returns_empty(self, mock_get: MagicMock) -> None:
        """Network errors should return empty list."""
        mock_get.side_effect = httpx.NetworkError("Connection refused")

        config = SourceConfig(
            name="quandl-test",
            type="quandl",
            url="https://data.nasdaq.com/api/v3/datasets/WIKI/AAPL.json",
        )
        handler = QuandlHandler(config)

        with patch.dict(os.environ, {"AUTOINFO_QUANDL_API_KEY": "test-key"}):
            items = handler.fetch(config.url, limit=5)

        assert items == []

    @patch("autoinfo.collectors.quandl.httpx.get")
    def test_fetch_timeout_returns_empty(self, mock_get: MagicMock) -> None:
        """Timeout errors should return empty list."""
        mock_get.side_effect = httpx.TimeoutException(
            "Request timed out",
            request=MagicMock(),
        )

        config = SourceConfig(
            name="quandl-test",
            type="quandl",
            url="https://data.nasdaq.com/api/v3/datasets/WIKI/AAPL.json",
        )
        handler = QuandlHandler(config)

        with patch.dict(os.environ, {"AUTOINFO_QUANDL_API_KEY": "test-key"}):
            items = handler.fetch(config.url, limit=5)

        assert items == []

    @patch("autoinfo.collectors.quandl.httpx.get")
    def test_fetch_missing_dataset_returns_empty(self, mock_get: MagicMock) -> None:
        """Response without 'dataset' key should return empty list."""
        mock_get.return_value = _mock_response(SAMPLE_QUANDL_MISSING_DATASET)

        config = SourceConfig(
            name="quandl-test",
            type="quandl",
            url="https://data.nasdaq.com/api/v3/datasets/WIKI/INVALID.json",
        )
        handler = QuandlHandler(config)

        with patch.dict(os.environ, {"AUTOINFO_QUANDL_API_KEY": "test-key"}):
            items = handler.fetch(config.url, limit=5)

        assert items == []

    @patch("autoinfo.collectors.quandl.httpx.get")
    def test_fetch_null_dataset_returns_empty(self, mock_get: MagicMock) -> None:
        """Response with null dataset should return empty list."""
        mock_get.return_value = _mock_response(SAMPLE_QUANDL_EMPTY_DATASET)

        config = SourceConfig(
            name="quandl-test",
            type="quandl",
            url="https://data.nasdaq.com/api/v3/datasets/WIKI/INVALID.json",
        )
        handler = QuandlHandler(config)

        with patch.dict(os.environ, {"AUTOINFO_QUANDL_API_KEY": "test-key"}):
            items = handler.fetch(config.url, limit=5)

        assert items == []

    @patch("autoinfo.collectors.quandl.httpx.get")
    def test_fetch_non_json_response_returns_empty(self, mock_get: MagicMock) -> None:
        """Non-JSON response should return empty list."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.side_effect = ValueError("Expecting value")
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        config = SourceConfig(
            name="quandl-test",
            type="quandl",
            url="https://data.nasdaq.com/api/v3/datasets/WIKI/AAPL.json",
        )
        handler = QuandlHandler(config)

        with patch.dict(os.environ, {"AUTOINFO_QUANDL_API_KEY": "test-key"}):
            items = handler.fetch(config.url, limit=5)

        assert items == []


# ---------------------------------------------------------------------------
# Tests: dispatch in _build_handler
# ---------------------------------------------------------------------------


class TestQuandlDispatch:
    """Tests that Quandl sources dispatch correctly."""

    def test_quandl_dispatches_to_quandl_handler(self) -> None:
        """Source with type='quandl' should dispatch to QuandlHandler."""
        from autoinfo.collect import _build_handler

        config = SourceConfig(
            name="quandl-test",
            type="quandl",
            url="https://data.nasdaq.com/api/v3/datasets/WIKI/AAPL.json",
        )
        handler = _build_handler(config)
        assert isinstance(handler, QuandlHandler)
        assert handler.source_name == "quandl-test"

    def test_quandl_handler_not_dispatched_for_other_types(self) -> None:
        """Non-quandl source types should not create QuandlHandler."""
        from autoinfo.collect import _build_handler

        config = SourceConfig(
            name="test-rss",
            type="rss",
            url="https://example.com/feed.xml",
        )
        handler = _build_handler(config)
        assert not isinstance(handler, QuandlHandler)


# ---------------------------------------------------------------------------
# Tests: source_url in items
# ---------------------------------------------------------------------------


class TestQuandlSourceUrl:
    """Tests that source_url is correctly set in items."""

    @patch("autoinfo.collectors.quandl.httpx.get")
    def test_source_url_matches_config_url(self, mock_get: MagicMock) -> None:
        """The source_url on the item should match the config URL."""
        mock_get.return_value = _mock_response(SAMPLE_QUANDL_RESPONSE)

        api_url = "https://data.nasdaq.com/api/v3/datasets/WIKI/AAPL.json"
        config = SourceConfig(
            name="quandl-test",
            type="quandl",
            url=api_url,
        )
        handler = QuandlHandler(config)
        with patch.dict(os.environ, {"AUTOINFO_QUANDL_API_KEY": "test-key"}):
            items = handler.fetch(config.url, limit=5)

        assert items[0].source_url == api_url
