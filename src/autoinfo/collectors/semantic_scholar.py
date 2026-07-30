"""Semantic Scholar Academic Graph API handler.

Searches and fetches academic papers via the Semantic Scholar API using
the ``/graph/v1/paper/search`` endpoint.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any
from urllib.parse import quote

import httpx

from autoinfo.collectors.base import BaseHandler
from autoinfo.models import Item

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "https://api.semanticscholar.org/graph/v1"
DEFAULT_TIMEOUT = 30  # seconds
MAX_RETRIES = 3
RETRY_DELAYS = [2, 4, 8]  # exponential backoff in seconds
RATE_LIMIT_DEFAULT = 1  # requests / second (no API key)
RATE_LIMIT_WITH_KEY = 100  # requests / second (with API key)

# Fields requested from the API for each paper
DEFAULT_FIELDS = "title,abstract,authors,citationCount,publicationDate"


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


class SemanticScholarHandler(BaseHandler):
    """Fetch academic papers using the Semantic Scholar Academic Graph API.

    Usage::

        handler = SemanticScholarHandler()
        items = handler.fetch("machine learning", limit=10)
        for item in items:
            print(item.title, item.raw_data.get("cited_by_count"))

    The API works without an API key at a lower rate limit (1 req/s).
    Supplying an API key raises the rate limit to 100 req/s.
    """

    source_name: str = "semantic_scholar"

    def __init__(self, api_key: str | None = None, source_config=None) -> None:
        """Initialise handler.

        Args:
            api_key: Optional Semantic Scholar API key for higher rate
                limits (100 req/s instead of 1). Falls back to the
                ``AUTOINFO_S2_API_KEY`` environment variable.
            source_config: Optional :class:`SourceConfig` for per-source
                settings (e.g. fetch_depth, rate_limit).
        """
        self.api_key = api_key or os.environ.get("AUTOINFO_S2_API_KEY", "")
        self.source_config = source_config
        self.max_rps = RATE_LIMIT_WITH_KEY if self.api_key else RATE_LIMIT_DEFAULT
        self._last_request_time = 0.0

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    def _wait_for_rate_limit(self) -> None:
        """Block until the next request is allowed under the rate limit."""
        if self._last_request_time == 0.0:
            self._last_request_time = time.time()
            return

        elapsed = time.time() - self._last_request_time
        min_interval = 1.0 / self.max_rps
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
            headers: Optional HTTP headers.

        Returns:
            HTTP response object.

        Raises:
            httpx.TimeoutException: After 3 retries all timed out.
            httpx.NetworkError: After 3 retries all failed.
            httpx.HTTPStatusError: On 4xx/5xx response (not retried).
        """
        last_exc: Exception | None = None

        for attempt in range(MAX_RETRIES):
            self._wait_for_rate_limit()
            try:
                response = httpx.get(
                    url,
                    headers=headers,
                    timeout=DEFAULT_TIMEOUT,
                )
                response.raise_for_status()
                return response
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_exc = exc
                if attempt == MAX_RETRIES - 1:
                    raise
                time.sleep(RETRY_DELAYS[attempt])

        # Unreachable — the loop always returns or raises on the last attempt.
        raise RuntimeError("Unexpected: all retries exhausted") from last_exc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search Semantic Scholar and return parsed paper dicts.

        Args:
            query: Search term (e.g. ``"machine learning"``).
            limit: Maximum number of papers to return (default 10,
                max 100 per API).

        Returns:
            List of parsed paper dictionaries, each with mapped fields.
        """
        limit = max(1, min(limit, 100))
        url = (
            f"{BASE_URL}/paper/search"
            f"?query={quote(query)}&limit={limit}"
            f"&fields={DEFAULT_FIELDS}"
        )

        headers: dict[str, str] = {}
        if self.api_key:
            headers["x-api-key"] = self.api_key

        resp = self._request(url, headers=headers)
        data = resp.json()
        papers = data.get("data", [])

        return [self._map_paper(p) for p in papers]

    # ------------------------------------------------------------------
    # Field mapping
    # ------------------------------------------------------------------

    @staticmethod
    def _map_paper(paper: dict[str, Any]) -> dict[str, Any]:
        """Map raw Semantic Scholar API paper dict to standardised fields.

        Args:
            paper: Raw paper dict from the API response.

        Returns:
            Parsed dict with standardised field names.
        """
        # Extract author names as a flat list of strings
        authors_raw = paper.get("authors") or []
        authors: list[str] = [
            a["name"] for a in authors_raw if isinstance(a, dict) and "name" in a
        ]

        return {
            "id": paper.get("paperId") or "",
            "title": paper.get("title") or "",
            "abstract": paper.get("abstract") or "",
            "authors": authors,
            "cited_by_count": paper.get("citationCount") or 0,
            "published_date": paper.get("publicationDate") or "",
        }

    # ------------------------------------------------------------------
    # Conversion to Item
    # ------------------------------------------------------------------

    def to_item(self, paper: dict[str, Any]) -> Item:
        """Convert a parsed paper dict to an :class:`Item` dataclass.

        Args:
            paper: Parsed paper dict as returned by :meth:`fetch`
                (already mapped by :meth:`_map_paper`).

        Returns:
            An :class:`Item` instance populated from the paper data.
        """
        paper_id: str = paper.get("id") or ""
        title: str = paper.get("title") or ""

        return Item(
            id=paper_id or str(uuid.uuid4()),
            source_name=self.source_name,
            source_type="api",
            source_platform="semantic_scholar",
            source_url=(
                f"https://api.semanticscholar.org/paper/{paper_id}"
                if paper_id
                else ""
            ),
            title=title,
            content=paper.get("abstract") or "",
            content_type="text",
            collected_at=paper.get("published_date") or "",
            domain="medical-research",
            topic_tags=[],
            raw_data={
                "paper_id": paper_id,
                "authors": paper.get("authors") or [],
                "cited_by_count": paper.get("cited_by_count") or 0,
                "published_date": paper.get("published_date") or "",
            },
        )
