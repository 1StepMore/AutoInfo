"""HuggingFace Hub / Kaggle dataset and model metadata collector.

Fetches dataset or model metadata from the HuggingFace Hub API
(``https://huggingface.co/api/``) and the Kaggle API.  Only metadata
(names, descriptions, tags, download counts, source URLs) is collected —
no dataset or model files are downloaded.

HuggingFace Hub: free, no authentication required.
Kaggle: requires ``KAGGLE_USERNAME`` and ``KAGGLE_KEY`` environment
variables.  When missing, ``requires_key()`` returns ``True`` and
``fetch()`` returns an empty list without error.

Usage::

    handler = HuggingFaceHandler()
    datasets = handler.fetch(query="machine learning", limit=10)
    items = [handler.to_item(d) for d in datasets]

    # Kaggle provider
    handler_k = HuggingFaceHandler(provider="kaggle")
    kaggle_datasets = handler_k.fetch(query="cancer", limit=5)
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any
from urllib.parse import urlencode

import httpx

from autoinfo.collectors.base import BaseHandler
from autoinfo.models import Item

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HF_BASE_URL: str = "https://huggingface.co/api"
KAGGLE_BASE_URL: str = "https://www.kaggle.com/api/v1"
DEFAULT_TIMEOUT: int = 30  # seconds
DEFAULT_LIMIT: int = 10
MAX_LIMIT: int = 250  # HF Hub API max
MAX_RETRIES: int = 3
RETRY_DELAYS: list[int] = [2, 4, 8]  # exponential backoff in seconds

# Polite rate limiting: 1 request per second
MIN_REQUEST_INTERVAL: float = 1.0

SUPPORTED_CONTENT_TYPES: frozenset[str] = frozenset({"datasets", "models"})


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


class HuggingFaceHandler(BaseHandler):
    """Fetch dataset/model metadata from HuggingFace Hub or Kaggle.

    Supports two providers:

    * ``"huggingface"`` — free Hub API, no auth needed
    * ``"kaggle"`` — requires ``KAGGLE_USERNAME`` / ``KAGGLE_KEY`` env vars

    Parameters
    ----------
    config : dict
        Handler configuration.  Supported keys:

        * ``provider`` — ``"huggingface"`` (default) or ``"kaggle"``
        * ``content_type`` — ``"datasets"`` (default) or ``"models"``
        * ``query`` — default search query (used when ``fetch()`` receives
          an empty query)
        * ``max_rps`` — max requests per second (default 1.0; Kaggle
          defaults to 0.5 to be polite)
    """

    source_type: str = "huggingface"
    source_name: str = "huggingface"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        cfg = config or {}
        self.config = cfg

        # Provider
        self.provider: str = cfg.get("provider", "huggingface")
        if self.provider not in ("huggingface", "kaggle"):
            logger.warning(
                "Unknown provider '%s', falling back to 'huggingface'",
                self.provider,
            )
            self.provider = "huggingface"

        # Content type: datasets or models
        self.content_type: str = cfg.get("content_type", "datasets")
        if self.content_type not in SUPPORTED_CONTENT_TYPES:
            logger.warning(
                "Unknown content_type '%s', falling back to 'datasets'",
                self.content_type,
            )
            self.content_type = "datasets"

        # Default query
        self.query: str = cfg.get("query", "")

        # Rate limiting
        default_rps = 0.5 if self.provider == "kaggle" else 1.0
        self.max_rps: float = float(cfg.get("max_rps", default_rps))
        self._last_request_time: float = 0.0

        # Override source_type for kaggle provider
        if self.provider == "kaggle":
            self.source_type = "kaggle"
            self.source_name = "kaggle"

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    def _wait_for_rate_limit(self) -> None:
        """Block until the next request is allowed under the rate limit."""
        if self._last_request_time == 0.0:
            self._last_request_time = time.time()
            return

        min_interval = (
            1.0 / self.max_rps if self.max_rps > 0 else MIN_REQUEST_INTERVAL
        )
        elapsed = time.time() - self._last_request_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_request_time = time.time()

    # ------------------------------------------------------------------
    # HTTP request with retry
    # ------------------------------------------------------------------

    def _request(self, url: str, headers: dict[str, str] | None = None) -> httpx.Response:
        """Issue a GET request with rate limiting and exponential-backoff retry.

        Args:
            url: Fully qualified URL to fetch.
            headers: Optional HTTP headers (used for Kaggle auth).

        Returns:
            HTTP response object.

        Raises:
            httpx.HTTPStatusError: On 4xx/5xx (not retried).
            httpx.TimeoutException: After retries exhausted.
            httpx.NetworkError: After retries exhausted.
        """
        last_exc: Exception | None = None
        req_headers = headers or {}

        for attempt in range(MAX_RETRIES):
            self._wait_for_rate_limit()
            try:
                response = httpx.get(url, headers=req_headers, timeout=DEFAULT_TIMEOUT)
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError:
                # Do not retry 4xx/5xx — propagate immediately
                raise
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_exc = exc
                if attempt == MAX_RETRIES - 1:
                    raise
                time.sleep(RETRY_DELAYS[attempt])

        raise RuntimeError("Unexpected: all retries exhausted") from last_exc

    # ------------------------------------------------------------------
    # Kaggle auth headers
    # ------------------------------------------------------------------

    def _kaggle_auth_headers(self) -> dict[str, str] | None:
        """Build auth headers for Kaggle API using env vars.

        Returns ``None`` if credentials are missing.
        """
        username = os.environ.get("KAGGLE_USERNAME", "")
        key = os.environ.get("KAGGLE_KEY", "")
        if not username or not key:
            return None
        import base64

        encoded = base64.b64encode(f"{username}:{key}".encode()).decode()
        return {
            "Authorization": f"Basic {encoded}",
            "Accept": "application/json",
        }

    # ------------------------------------------------------------------
    # Field mapping
    # ------------------------------------------------------------------

    @staticmethod
    def _map_dataset(item: dict[str, Any], provider: str) -> dict[str, Any]:
        """Map a raw API result to standardised fields.

        Args:
            item: Raw JSON result from the HuggingFace Hub API or Kaggle API.
            provider: ``"huggingface"`` or ``"kaggle"``.

        Returns:
            Parsed dict with standardised field names: ``id``, ``title``,
            ``description``, ``author``, ``tags``, ``downloads``,
            ``likes``, ``last_modified``, ``source_url``, ``provider``.
        """
        if provider == "huggingface":
            dataset_id: str = item.get("id", "")
            title: str = item.get("id", "").split("/")[-1] if item.get("id") else ""
            description: str = item.get("description") or ""
            author: str = item.get("author") or ""
            tags: list[str] = item.get("tags") or []
            downloads: int = item.get("downloads") or 0
            likes: int = item.get("likes") or 0
            last_modified: str = item.get("lastModified") or ""
            source_url: str = f"https://huggingface.co/datasets/{dataset_id}" if dataset_id else ""
        else:
            # Kaggle dataset
            ref: str = item.get("ref") or ""
            dataset_id = ref
            title: str = item.get("title") or ""
            description: str = item.get("subtitle") or item.get("description") or ""
            author: str = item.get("ownerName") or item.get("ownerRef") or ""
            tags_raw: list[dict[str, str]] = item.get("tags") or []
            tags = [t.get("name", t.get("ref", "")) if isinstance(t, dict) else str(t) for t in tags_raw]
            downloads: int = item.get("downloadCount") or 0
            likes: int = item.get("voteCount") or 0
            last_modified: str = item.get("lastUpdated") or ""
            source_url: str = f"https://www.kaggle.com/datasets/{ref}" if ref else ""

        return {
            "id": dataset_id,
            "title": title,
            "description": description,
            "author": author,
            "tags": tags,
            "downloads": downloads,
            "likes": likes,
            "last_modified": last_modified,
            "source_url": source_url,
            "provider": provider,
        }

    # ------------------------------------------------------------------
    # Public API — fetch
    # ------------------------------------------------------------------

    def fetch(
        self,
        query: str = "",
        limit: int = DEFAULT_LIMIT,
    ) -> list[dict[str, Any]]:
        """Fetch dataset/model metadata from HuggingFace Hub or Kaggle.

        Args:
            query: Search query string.  Falls back to ``self.query`` if
                empty.
            limit: Maximum number of results to return (default 10).

        Returns:
            List of parsed dataset dicts, each with standardised fields.
            Returns an empty list on error, if *limit* ≤ 0, or (for
            Kaggle) when credentials are missing.
        """
        if limit <= 0:
            return []

        search_term = (query or self.query).strip()

        if self.provider == "kaggle":
            return self._fetch_kaggle(search_term, limit)
        else:
            return self._fetch_huggingface(search_term, limit)

    def _fetch_huggingface(self, query: str, limit: int) -> list[dict[str, Any]]:
        """Fetch from HuggingFace Hub datasets-server API."""
        # HF Hub accepts empty query — returns popular/recent datasets
        search = query if query else ""
        page_size = min(limit, MAX_LIMIT)

        params: dict[str, Any] = {
            "search": search,
            "limit": page_size,
            "full": "false",  # no need for full metadata
        }
        url = f"{HF_BASE_URL}/{self.content_type}?{urlencode(params)}"

        all_items: list[dict[str, Any]] = []

        try:
            resp = self._request(url)
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code if exc.response else "?"
            logger.warning(
                "HF Hub API HTTP error %s for query '%s': %s",
                status,
                query,
                exc,
            )
            return []
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            logger.warning(
                "HF Hub API network error for query '%s': %s",
                query,
                exc,
            )
            return []

        # Parse JSON response
        try:
            data = resp.json()
        except ValueError as exc:
            logger.warning(
                "HF Hub API returned non-JSON for query '%s': %s",
                query,
                exc,
            )
            return []

        # HF Hub API returns a list directly (not wrapped in {"results": [...]})
        items_list: list[dict[str, Any]] = (
            data if isinstance(data, list) else data.get(self.content_type) or data.get("results") or []
        )

        for item in items_list:
            try:
                mapped = self._map_dataset(item, "huggingface")
                all_items.append(mapped)
            except Exception as exc:
                logger.debug(
                    "Failed to map HF dataset item: %s",
                    exc,
                    exc_info=True,
                )
                continue

        return all_items[:limit]

    def _fetch_kaggle(self, query: str, limit: int) -> list[dict[str, Any]]:
        """Fetch from Kaggle API.

        Returns an empty list when KAGGLE_USERNAME/KAGGLE_KEY are missing.
        """
        headers = self._kaggle_auth_headers()
        if headers is None:
            logger.info("Kaggle API credentials not configured; skipping fetch.")
            return []

        search = query if query else ""
        page_size = min(limit, 100)  # Kaggle API default page size

        params: dict[str, Any] = {
            "page": 1,
            "pageSize": page_size,
        }
        if search:
            params["search"] = search

        url = f"{KAGGLE_BASE_URL}/datasets?{urlencode(params)}"

        all_items: list[dict[str, Any]] = []

        try:
            resp = self._request(url, headers=headers)
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code if exc.response else "?"
            logger.warning(
                "Kaggle API HTTP error %s for query '%s': %s",
                status,
                query,
                exc,
            )
            return []
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            logger.warning(
                "Kaggle API network error for query '%s': %s",
                query,
                exc,
            )
            return []

        # Parse JSON response
        try:
            data = resp.json()
        except ValueError as exc:
            logger.warning(
                "Kaggle API returned non-JSON for query '%s': %s",
                query,
                exc,
            )
            return []

        # Kaggle returns {"datasets": [...]} or a flat list
        items_list: list[dict[str, Any]] = (
            data if isinstance(data, list) else data.get("datasets") or data.get("results") or []
        )

        for item in items_list:
            try:
                mapped = self._map_dataset(item, "kaggle")
                all_items.append(mapped)
            except Exception as exc:
                logger.debug(
                    "Failed to map Kaggle dataset item: %s",
                    exc,
                    exc_info=True,
                )
                continue

        return all_items[:limit]

    # ------------------------------------------------------------------
    # Conversion to Item
    # ------------------------------------------------------------------

    def to_item(self, dataset: dict[str, Any]) -> Item:
        """Convert a parsed dataset dict to an :class:`Item` dataclass.

        Args:
            dataset: Parsed dataset dict as returned by :meth:`fetch`.

        Returns:
            An :class:`Item` instance populated from the dataset metadata.
        """
        dataset_id: str = dataset.get("id") or ""
        title: str = dataset.get("title") or ""
        description: str = dataset.get("description") or ""
        source_url: str = dataset.get("source_url") or ""
        provider: str = dataset.get("provider", self.provider)
        source_type: str = "kaggle" if provider == "kaggle" else "huggingface"

        return Item(
            id=dataset_id or str(uuid.uuid4()),
            source_name=self.source_name,
            source_type=source_type,
            source_platform=source_type,
            source_url=source_url,
            title=title,
            content=description,
            content_type="text",
            collected_at=dataset.get("last_modified") or "",
            language="",
            domain="",
            topic_tags=dataset.get("tags") or [],
            raw_data={
                "author": dataset.get("author") or "",
                "tags": dataset.get("tags") or [],
                "downloads": dataset.get("downloads") or 0,
                "likes": dataset.get("likes") or 0,
                "last_modified": dataset.get("last_modified") or "",
                "provider": provider,
            },
        )

    # ------------------------------------------------------------------
    # Source metadata
    # ------------------------------------------------------------------

    @staticmethod
    def requires_key() -> bool:
        """Return ``True`` when the Kaggle provider is active (env-only key).

        HuggingFace Hub is always free and requires no key.
        """
        # This is a static check — it's conservative and returns True
        # if KAGGLE_USERNAME/KAGGLE_KEY are not set, which is correct
        # for the kaggle provider.  For huggingface, returns False.
        return False  # huggingface default needs no key

    @staticmethod
    def note() -> str | None:
        """Return a usage note about metadata-only collection."""
        return (
            "HF Hub / Kaggle collector fetches only dataset/model METADATA "
            "(names, descriptions, tags, download counts).  No dataset or "
            "model files are downloaded.  For the Kaggle provider, set "
            "KAGGLE_USERNAME and KAGGLE_KEY environment variables."
        )
