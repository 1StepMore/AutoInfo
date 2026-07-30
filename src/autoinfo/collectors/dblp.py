"""DBLP Computer Science Bibliography handler.

Searches and fetches academic publications from the DBLP API
(https://dblp.org/search/publ/api) using the JSON output format.
DBLP indexes 6M+ computer science conference and journal papers.
"""

from __future__ import annotations

import logging
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

BASE_URL = "https://dblp.org/search/publ/api"
DEFAULT_TIMEOUT = 30  # seconds
MAX_RETRIES = 3
RETRY_DELAYS = [2, 4, 8]  # exponential backoff in seconds
RATE_LIMIT = 1  # requests / second — be polite


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


class DBLPHandler(BaseHandler):
    """Fetch CS publications from the DBLP Computer Science Bibliography API.

    Usage::

        handler = DBLPHandler()
        items = handler.fetch("machine learning", limit=10)
        for item in items:
            print(item.title, item.raw_data.get("venue"))
    """

    source_name: str = "dblp"

    def __init__(self, source_config: Any = None) -> None:
        """Initialise handler.

        Args:
            source_config: Optional :class:`SourceConfig` for per-source
                settings (e.g. rate_limit, query).
        """
        self.source_config = source_config
        self.max_rps = RATE_LIMIT
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

    def _request(self, url: str) -> httpx.Response:
        """Issue a GET request with rate limiting and exponential-backoff retry.

        Args:
            url: Fully qualified URL to fetch.

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
                response = httpx.get(url, timeout=DEFAULT_TIMEOUT)
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
        """Search DBLP and return parsed publication dicts.

        Args:
            query: Search term (e.g. ``"machine learning"``).
            limit: Maximum number of publications to return (default 10,
                max 1000 per API).

        Returns:
            List of parsed publication dictionaries, each with mapped
            fields (``id``, ``title``, ``authors``, ``published_date``,
            ``source_type``).  Returns an empty list on error.
        """
        limit = max(1, min(limit, 1000))
        url = (
            f"{BASE_URL}"
            f"?q={quote(query)}&format=json&h={limit}"
        )

        try:
            resp = self._request(url)
            data = resp.json()
        except (ValueError, httpx.HTTPStatusError, httpx.TimeoutException,
                httpx.NetworkError) as exc:
            logger.warning(
                "DBLP API request failed for query '%s': %s",
                query,
                exc,
            )
            return []

        return self._parse_response(data)

    def _parse_response(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        """Parse the DBLP API JSON response into mapped publication dicts.

        DBLP JSON structure::

            {
              "result": {
                "hits": {
                  "@total": "...",
                  "hit": [
                    {
                      "@score": "...",
                      "@id": "...",
                      "info": {
                        "title": "...",
                        "doi": "...",
                        "authors": {
                          "author": "..." or ["...", "..."]
                        },
                        "year": "...",
                        "venue": "..."
                      }
                    }
                  ]
                }
              }
            }

        Args:
            data: Raw parsed JSON from the DBLP API.

        Returns:
            List of mapped publication dicts.  Empty list if no hits.
        """
        result = data.get("result", {})
        hits = result.get("hits", {})
        hit_list = hits.get("hit", [])

        if not hit_list:
            return []

        publications: list[dict[str, Any]] = []
        for hit in hit_list:
            pub = self._map_hit(hit)
            publications.append(pub)

        return publications

    @staticmethod
    def _map_hit(hit: dict[str, Any]) -> dict[str, Any]:
        """Map a single DBLP hit to a standardised publication dict.

        Args:
            hit: A single ``hit`` dict from the ``hits.hit`` list.

        Returns:
            Parsed dict with standardised field names: ``id``, ``title``,
            ``authors``, ``published_date``, ``source_type``, ``venue``,
            ``dblp_url``.
        """
        info = hit.get("info") or {}

        # -- id: use DOI if available, fall back to DBLP @id --
        doi = info.get("doi", "")
        dblp_id = hit.get("@id", "")
        pub_id = doi if doi else dblp_id

        # -- title --
        title = info.get("title", "")

        # -- authors: DBLP returns "author" as a single string or list --
        authors_raw = info.get("authors", {})
        author_data = authors_raw.get("author", []) if isinstance(authors_raw, dict) else []

        authors: list[str] = []
        if isinstance(author_data, str):
            authors = [author_data]
        elif isinstance(author_data, list):
            authors = [
                a.get("text", a) if isinstance(a, dict) else str(a)
                for a in author_data
            ]

        # -- year → published_date --
        year = info.get("year", "")
        published_date = str(year) if year else ""

        # -- venue → source_type --
        venue = info.get("venue", "")
        source_type = venue if venue else "conference"

        return {
            "id": pub_id,
            "title": title,
            "authors": authors,
            "published_date": published_date,
            "source_type": source_type,
            "venue": venue,
            "dblp_url": dblp_id if dblp_id else "",
        }

    # ------------------------------------------------------------------
    # Conversion to Item
    # ------------------------------------------------------------------

    def to_item(self, publication: dict[str, Any]) -> Item:
        """Convert a parsed publication dict to an :class:`Item` dataclass.

        Args:
            publication: Parsed publication dict as returned by
                :meth:`fetch`.

        Returns:
            An :class:`Item` instance populated from the publication data.
        """
        pub_id = publication.get("id", "")
        title = publication.get("title", "")

        return Item(
            id=pub_id or str(uuid.uuid4()),
            source_name=self.source_name,
            source_type="api",
            source_platform="dblp",
            source_url=(
                publication.get("dblp_url", "")
                if publication.get("dblp_url")
                else ""
            ),
            title=title,
            content="",  # DBLP doesn't provide abstracts
            content_type="text",
            collected_at=publication.get("published_date", ""),
            domain="medical-research",
            topic_tags=[],
            raw_data={
                "dblp_id": publication.get("dblp_url", ""),
                "authors": publication.get("authors", []),
                "venue": publication.get("venue", ""),
                "published_date": publication.get("published_date", ""),
            },
        )
