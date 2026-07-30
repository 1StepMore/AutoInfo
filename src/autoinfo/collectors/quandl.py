"""Quandl / Nasdaq Data Link API collector.

Provides :class:`QuandlHandler` — a handler that fetches financial and
economic datasets from the Nasdaq Data Link (formerly Quandl) API.

Maps the JSON API response to :class:`Item` instances with standard fields
(dataset_code as id, name as title, description as content) and includes
the full dataset metadata as ``raw_data``.

API documentation: https://docs.data.nasdaq.com/
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx

from autoinfo.collectors.base import BaseHandler
from autoinfo.config import SourceConfig
from autoinfo.models import Item

logger = logging.getLogger(__name__)

# Sentinel to allow dispatch in collect.py to recognise this handler type
# without importing the class (avoids circular imports).
_HANDLER_MARKER = "QuandlHandler"


class QuandlHandler(BaseHandler):
    """Handler for the Nasdaq Data Link (Quandl) API.

    Fetches dataset metadata and the latest data rows from
    ``https://data.nasdaq.com/api/v3/datasets/{db}/{code}.json``.

    API key is read from the ``AUTOINFO_QUANDL_API_KEY`` environment
    variable and passed as the ``api_key`` query parameter.

    Usage::

        config = SourceConfig(
            name="quandl-test",
            type="quandl",
            url="https://data.nasdaq.com/api/v3/datasets/WIKI/AAPL.json",
        )
        handler = QuandlHandler(config)
        items = handler.fetch(config.url, query="", limit=5)
    """

    _handler_type: str = _HANDLER_MARKER
    source_type: str = "quandl"

    def __init__(self, source_config: SourceConfig) -> None:
        """Initialise the handler from a :class:`SourceConfig`."""
        self.source_config = source_config
        self.source_name = source_config.name
        self._settings = source_config.settings or {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch(self, url: str, query: str = "", limit: int = 20) -> list[Item]:
        """Fetch items from the Quandl API.

        Parameters
        ----------
        url : str
            The API endpoint URL (e.g. ``.../datasets/WIKI/AAPL.json``).
        query : str
            Ignored for Quandl datasets (the dataset is identified by the
            URL).  Kept for API compatibility with the dispatch layer.
        limit : int
            Maximum number of data rows to include in ``raw_data``
            (default 20).  The actual number of returned items is always
            1 per API call (one dataset per request), but the data rows
            within are trimmed to this limit.

        Returns
        -------
        list[Item]
            A list with zero or one :class:`Item` per API call.
            Returns an empty list on any error — this method **never**
            raises.
        """
        api_key = self._get_api_key()
        if not api_key:
            logger.warning(
                "No Quandl API key configured for source '%s'. "
                "Set AUTOINFO_QUANDL_API_KEY environment variable.",
                self.source_name,
            )
            return []

        params: dict[str, Any] = {"api_key": api_key}
        if limit and limit > 0:
            params["rows"] = limit

        timeout = float(self._settings.get("timeout", 30))

        try:
            response = httpx.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            data = response.json()
        except httpx.TimeoutException:
            logger.error("Quandl request timed out for %s", url)
            return []
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Quandl HTTP error for %s: %s",
                url,
                exc.response.status_code if exc.response else exc,
            )
            return []
        except httpx.NetworkError as exc:
            logger.error("Quandl network error for %s: %s", url, exc)
            return []
        except Exception as exc:
            logger.error(
                "Quandl fetch failed for %s (source: %s): %s",
                url,
                self.source_name,
                exc,
            )
            return []

        return self._map_to_items(data)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_api_key(self) -> str:
        """Resolve the Quandl API key from the environment variable."""
        return os.environ.get("AUTOINFO_QUANDL_API_KEY", "")

    def _map_to_items(self, data: dict[str, Any]) -> list[Item]:
        """Map the Quandl JSON response to a list of :class:`Item`.

        The Quandl API wraps the dataset in a top-level ``"dataset"`` key.
        Fields are extracted as follows:

        =================  ============================
        ``Item`` field     Quandl JSON field
        =================  ============================
        ``id``             ``dataset.dataset_code``
        ``title``          ``dataset.name``
        ``content``        ``dataset.description``
        ``source_url``     The original API request URL
        =================  ============================

        The entire dataset dict is stored in ``raw_data``.
        """
        dataset = data.get("dataset")
        if not dataset or not isinstance(dataset, dict):
            logger.warning(
                "Quandl response missing 'dataset' key (source: %s)",
                self.source_name,
            )
            return []

        collected_at = datetime.now(timezone.utc).isoformat()
        dataset_code = dataset.get("dataset_code", "") or ""

        item = Item(
            id=str(dataset_code),
            source_name=self.source_name,
            source_type="quandl",
            source_url=self.source_config.url,
            title=str(dataset.get("name", "") or ""),
            content=str(dataset.get("description", "") or ""),
            content_type="text",
            source_platform=self.source_config.name,
            collected_at=collected_at,
            raw_data=dataset,
        )

        return [item]
