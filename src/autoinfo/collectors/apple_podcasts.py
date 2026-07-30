"""Apple Podcasts / iTunes Search API handler.

Searches for podcast shows via the free iTunes Search API
(``https://itunes.apple.com/search``).  No authentication required.

.. caution::

    This API returns podcast **shows** (collections), not individual
    episodes.  The ``description`` field is the show-level summary;
    ``longDescription`` is not available at the collection level in the
    iTunes Search API.  For per-episode data a separate RSS/Atom feed
    fetch of the show's ``feedUrl`` is required.

Usage::

    handler = ApplePodcastsHandler()
    shows = handler.fetch(term="machine learning", limit=10)
    items = [handler.to_item(show) for show in shows]
"""

from __future__ import annotations

import logging
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

BASE_URL: str = "https://itunes.apple.com/search"
DEFAULT_TIMEOUT: int = 30  # seconds
DEFAULT_LIMIT: int = 10
MAX_LIMIT: int = 200  # iTunes API hard cap
MAX_RETRIES: int = 3
RETRY_DELAYS: list[int] = [2, 4, 8]  # exponential backoff in seconds

# Polite rate limiting: 1 request per second
MIN_REQUEST_INTERVAL: float = 1.0


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


class ApplePodcastsHandler(BaseHandler):
    """Fetch podcast shows from the iTunes Search API.

    The iTunes Search API is free, no authentication required.
    Returns podcast **shows** (collections), not individual episodes.

    Usage::

        handler = ApplePodcastsHandler()
        shows = handler.fetch(term="machine learning", limit=10)
    """

    source_type: str = "apple_podcasts"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialise handler.

        Args:
            config: Dictionary with optional keys:
                - ``term``: default search term (default ``""``)
                - ``country``: ISO 3166-1 alpha-2 country code
                  (default ``"US"``)
                - ``entity``: podcast entity type (default ``"podcast"``)
                - ``max_rps``: requests per second rate limit
                  (default ``1.0``)
        """
        if config is None:
            config = {}
        self.config: dict[str, Any] = config
        self.term: str = config.get("term", "")
        self.country: str = config.get("country", "US")
        self.entity: str = config.get("entity", "podcast")
        self.max_rps: float = float(config.get("max_rps", 1.0))
        self._last_request_time: float = 0.0

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    def _wait_for_rate_limit(self) -> None:
        """Block until the next request is allowed (polite: 1 rps default)."""
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

    def _request(self, url: str) -> httpx.Response:
        """Issue a GET request with rate limiting and exponential-backoff retry.

        Args:
            url: Fully qualified URL to fetch.

        Returns:
            HTTP response object.

        Raises:
            httpx.TimeoutException: After retries exhausted.
            httpx.NetworkError: After retries exhausted.
            httpx.HTTPStatusError: On 4xx/5xx (not retried).
        """
        last_exc: Exception | None = None

        for attempt in range(MAX_RETRIES):
            self._wait_for_rate_limit()
            try:
                response = httpx.get(url, timeout=DEFAULT_TIMEOUT)
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
    # Field mapping
    # ------------------------------------------------------------------

    @staticmethod
    def _map_show(item: dict[str, Any]) -> dict[str, Any]:
        """Map a raw iTunes Search API result to standardised fields.

        Args:
            item: Raw JSON result from the iTunes API ``results`` list.
                Each item represents a podcast show (collection).

        Returns:
            Parsed dict with standardised field names: ``id``, ``title``,
            ``content``, ``author``, ``feed_url``, ``published_date``,
            ``source_url``, ``genre``, ``artwork_url``,
            ``track_count``, ``country``.
        """
        # Primary fields from the API
        track_id: str = str(item.get("trackId", ""))
        title: str = item.get("trackName") or item.get("collectionName") or ""
        content: str = item.get("description") or ""
        author: str = item.get("artistName") or ""
        feed_url: str = item.get("feedUrl") or ""
        published_date: str = item.get("releaseDate") or ""
        source_url: str = (
            item.get("collectionViewUrl")
            or item.get("trackViewUrl")
            or ""
        )
        genre: str = item.get("primaryGenreName") or ""
        artwork_url: str = (
            item.get("artworkUrl600")
            or item.get("artworkUrl100")
            or item.get("artworkUrl60")
            or item.get("artworkUrl30")
            or ""
        )
        track_count: int = item.get("trackCount", 0)
        country: str = item.get("country", "")
        genres: list[str] = item.get("genres") or []

        return {
            "id": track_id,
            "title": title,
            "content": content,
            "author": author,
            "feed_url": feed_url,
            "published_date": published_date,
            "source_url": source_url,
            "genre": genre,
            "genres": genres,
            "artwork_url": artwork_url,
            "track_count": track_count,
            "country": country,
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch(
        self,
        term: str = "",
        limit: int = DEFAULT_LIMIT,
    ) -> list[dict[str, Any]]:
        """Fetch podcast shows from the iTunes Search API.

        Args:
            term: Search query string (e.g. ``"machine learning"``).
                Falls back to ``self.term`` if empty.
            limit: Maximum number of shows to return (default 10,
                max 200).

        Returns:
            List of parsed show dicts, each with standardised fields.
            Returns an empty list on error or if *limit* ≤ 0.

        Note:
            The iTunes Search API returns podcast **shows** (collections),
            not individual episodes.  Use ``feed_url`` in the result to
            fetch per-episode data via RSS.
        """
        if limit <= 0:
            return []

        query = (term or self.term).strip()
        if not query:
            logger.warning(
                "Apple Podcasts fetch called with empty term; returning empty list."
            )
            return []

        page_size = min(limit, MAX_LIMIT)

        params: dict[str, Any] = {
            "term": query,
            "media": "podcast",
            "entity": self.entity,
            "limit": page_size,
            "country": self.country,
        }
        url = f"{BASE_URL}?{urlencode(params)}"

        all_shows: list[dict[str, Any]] = []

        try:
            resp = self._request(url)
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code if exc.response else "?"
            logger.warning(
                "iTunes Search API HTTP error %s for term '%s': %s",
                status,
                query,
                exc,
            )
            return []
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            logger.warning(
                "iTunes Search API network error for term '%s': %s",
                query,
                exc,
            )
            return []

        # Parse JSON response
        try:
            data = resp.json()
        except ValueError as exc:
            logger.warning(
                "iTunes Search API returned non-JSON for term '%s': %s",
                query,
                exc,
            )
            return []

        results: list[dict[str, Any]] = data.get("results") or []
        for item in results:
            try:
                show = self._map_show(item)
                all_shows.append(show)
            except Exception as exc:
                logger.debug(
                    "Failed to map Apple Podcasts item: %s",
                    exc,
                    exc_info=True,
                )
                continue

        return all_shows[:limit]

    # ------------------------------------------------------------------
    # Conversion to Item
    # ------------------------------------------------------------------

    def to_item(self, show: dict[str, Any]) -> Item:
        """Convert a parsed show dict to an :class:`Item` dataclass.

        Args:
            show: Parsed show dict as returned by :meth:`fetch`.

        Returns:
            An :class:`Item` instance populated from the show data.
        """
        show_id: str = show.get("id") or ""
        title: str = show.get("title") or ""

        return Item(
            id=show_id or str(uuid.uuid4()),
            source_name="apple_podcasts",
            source_type="apple_podcasts",
            source_platform="apple_podcasts",
            source_url=show.get("source_url") or "",
            title=title,
            content=show.get("content") or "",
            content_type="text",
            collected_at=show.get("published_date") or "",
            language="",
            domain="",
            topic_tags=[],
            raw_data={
                "apple_track_id": show_id,
                "author": show.get("author") or "",
                "feed_url": show.get("feed_url") or "",
                "published_date": show.get("published_date") or "",
                "genre": show.get("genre") or "",
                "genres": show.get("genres") or [],
                "artwork_url": show.get("artwork_url") or "",
                "track_count": show.get("track_count") or 0,
                "country": show.get("country") or "",
            },
        )

    # ------------------------------------------------------------------
    # Source metadata
    # ------------------------------------------------------------------

    @staticmethod
    def requires_key() -> bool:
        """Return ``False`` — the iTunes Search API requires no auth."""
        return False

    @staticmethod
    def note() -> str | None:
        """Return a note about the API's collection-level limitation."""
        return (
            "iTunes Search API returns podcast SHOWS (collections), "
            "not individual episodes. Use feed_url for per-episode RSS."
        )
