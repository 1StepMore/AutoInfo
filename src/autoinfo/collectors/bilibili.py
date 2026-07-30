"""Bilibili (B站) search handler.

Fetches video search results from Bilibili's public search API.
Uses Chrome User-Agent to mitigate anti-scraping measures.

.. note::

   Bilibili employs anti-scraping countermeasures.  This handler uses
   a Chrome User-Agent header and graceful error handling.  Marked as
   ``requires_app_review: true`` for production use.

API endpoints
-------------
* Primary: ``GET https://api.bilibili.com/x/web-interface/search/all/v2?keyword=QUERY&page=1``
* Fallback: ``GET https://api.bilibili.com/x/web-interface/search/v2?keyword=QUERY&page_size=N``
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

from autoinfo.collectors.base import BaseHandler
from autoinfo.models import Item

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SEARCH_ALL_URL = "https://api.bilibili.com/x/web-interface/search/all/v2"
SEARCH_URL = "https://api.bilibili.com/x/web-interface/search/v2"

DEFAULT_TIMEOUT = 15  # seconds
MAX_RETRIES = 3
RETRY_DELAYS = [2, 4, 8]  # exponential backoff in seconds

# Chrome 120 on Linux — common UA to reduce blocking risk
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


class BilibiliHandler(BaseHandler):
    """Fetch Bilibili video search results via the public search API.

    Usage::

        handler = BilibiliHandler({"query": "大模型"})
        videos = handler.fetch(limit=10)
        for video in videos:
            print(video["title"], video["author"])

        # Convert to Item for KB storage
        items = [handler.to_item(v) for v in videos]

    No API key is required for the public search endpoint, but
    Bilibili's anti-scraping measures may block requests.  This
    handler is marked ``requires_app_review: true``.
    """

    source_type: str = "bilibili"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialise handler.

        Args:
            config: Dictionary with optional keys:
                - ``query``: search query string (default ``""``)
                - ``user_agent``: override the default User-Agent header
        """
        if config is None:
            config = {}
        self.config: dict[str, Any] = config
        self.query: str = config.get("query", "")
        self._ua: str = config.get("user_agent") or USER_AGENT

    # ------------------------------------------------------------------
    # HTTP request with retry
    # ------------------------------------------------------------------

    def _request(self, url: str, params: dict[str, Any]) -> httpx.Response:
        """Issue a GET request with exponential-backoff retry.

        Args:
            url: Fully qualified URL to fetch.
            params: Query-string parameters.

        Returns:
            HTTP response object.

        Raises:
            httpx.TimeoutException: After 3 retries all timed out.
            httpx.NetworkError: After 3 retries all failed.
            httpx.HTTPStatusError: On 4xx/5xx response (not retried).
        """
        headers = {
            "User-Agent": self._ua,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.bilibili.com/",
        }

        last_exc: Exception | None = None

        for attempt in range(MAX_RETRIES):
            try:
                response = httpx.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=DEFAULT_TIMEOUT,
                )
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError:
                # Do not retry 4xx/5xx — propagate immediately
                raise
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_exc = exc
                if attempt == MAX_RETRIES - 1:
                    raise
                import time

                time.sleep(RETRY_DELAYS[attempt])

        raise RuntimeError("Unexpected: all retries exhausted") from last_exc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch(self, limit: int = 10) -> list[dict[str, Any]]:
        """Search Bilibili and return parsed video dicts.

        Args:
            limit: Maximum number of videos to return (default 10).

        Returns:
            List of parsed video dictionaries, each with mapped fields:
            ``id``, ``title``, ``content``, ``author``, ``published_date``,
            ``source_url``, ``view_count``, ``image_url``, ``bvid``.
            Returns an empty list on error.
        """
        if limit <= 0:
            return []

        query = self.query.strip()
        if not query:
            logger.warning("Bilibili fetch called with empty query; returning empty list.")
            return []

        # -- Try primary endpoint first, then fallback ----------------------
        all_videos: list[dict[str, Any]] = []

        try:
            all_videos = self._fetch_from_search_all(query, limit)
        except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.NetworkError) as exc:
            logger.warning(
                "Bilibili search/all/v2 failed for query '%s': %s. Trying fallback.",
                query,
                exc,
            )
            try:
                all_videos = self._fetch_from_search(query, limit)
            except Exception as fallback_exc:
                logger.warning(
                    "Bilibili search/v2 fallback also failed for query '%s': %s",
                    query,
                    fallback_exc,
                )
                return []

        return all_videos[:limit]

    def _fetch_from_search_all(
        self,
        query: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Fetch using the primary search/all/v2 endpoint.

        This endpoint returns results grouped by type (video, article, etc.).
        We extract only video-type results.
        """
        all_videos: list[dict[str, Any]] = []
        page = 1

        while len(all_videos) < limit:
            params: dict[str, Any] = {
                "keyword": query,
                "page": page,
            }
            resp = self._request(SEARCH_ALL_URL, params)
            data = self._parse_response(resp, "search/all/v2")
            if data is None:
                break

            # Results are grouped by type — grab the "video" group
            result_groups = data.get("result") or []
            video_items: list[dict[str, Any]] = []

            if isinstance(result_groups, list):
                # Some responses return a flat list
                video_items = [r for r in result_groups if r.get("type") == "video"]
            elif isinstance(result_groups, dict):
                video_items = result_groups.get("video") or []

            if not video_items:
                break

            for item in video_items:
                try:
                    video = self._map_video_all(item)
                    all_videos.append(video)
                except Exception as exc:
                    logger.debug(
                        "Failed to map Bilibili search/all item: %s",
                        exc,
                        exc_info=True,
                    )
                    continue

            # Check if more pages are available
            if len(video_items) < 20 or page >= 10:
                # Bilibili caps at ~20 items per page, 10 pages max
                break
            page += 1

        return all_videos

    def _fetch_from_search(
        self,
        query: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Fetch using the fallback search/v2 endpoint."""
        params: dict[str, Any] = {
            "keyword": query,
            "search_type": "video",
            "page_size": min(limit, 50),
            "page": 1,
        }
        resp = self._request(SEARCH_URL, params)
        data = self._parse_response(resp, "search/v2")
        if data is None:
            return []

        result_items = data.get("result") or []
        if not isinstance(result_items, list):
            # Some API versions wrap in a dict
            result_items = []

        all_videos: list[dict[str, Any]] = []
        for item in result_items:
            try:
                video = self._map_video(item)
                all_videos.append(video)
            except Exception as exc:
                logger.debug(
                    "Failed to map Bilibili search/v2 item: %s",
                    exc,
                    exc_info=True,
                )
                continue

        return all_videos

    @staticmethod
    def requires_app_review() -> bool:
        """Return ``True`` — Bilibili has anti-scraping measures."""
        return True

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_response(
        resp: httpx.Response,
        endpoint: str,
    ) -> dict[str, Any] | None:
        """Parse Bilibili JSON response and validate the status code.

        Bilibili returns ``{"code": 0, "data": {...}}`` on success.
        Any non-zero code is treated as an error.

        Returns:
            The ``data`` dict on success, ``None`` on Bilibili-level error
            or parse failure.
        """
        try:
            body = resp.json()
        except ValueError as exc:
            logger.warning(
                "Bilibili %s returned non-JSON response: %s",
                endpoint,
                exc,
            )
            return None

        code = body.get("code", -1)
        if code != 0:
            message = body.get("message", "unknown error")
            logger.warning(
                "Bilibili %s returned error code %s: %s",
                endpoint,
                code,
                message,
            )
            return None

        return body.get("data")

    # ------------------------------------------------------------------
    # Field mapping
    # ------------------------------------------------------------------

    @staticmethod
    def _map_video_all(item: dict[str, Any]) -> dict[str, Any]:
        """Map a raw item from ``search/all/v2`` to standardised fields.

        Args:
            item: Raw video item from the ``result.video`` list.

        Returns:
            Parsed dict with standardised field names.
        """
        aid = item.get("aid") or item.get("id") or ""
        bvid = item.get("bvid") or ""
        author = item.get("author") or ""
        pic = item.get("pic") or ""
        title = item.get("title", "") or ""
        description = item.get("description", "") or ""

        # Handle publish timestamp (Unix timestamp in seconds)
        created = item.get("created") or item.get("pubdate") or 0
        published_date = ""
        if created:
            try:
                published_date = datetime.fromtimestamp(
                    int(created), tz=timezone.utc
                ).isoformat()
            except (ValueError, OSError):
                published_date = ""

        # Extract view count from stat dict
        stat = item.get("stat") or {}
        view_count = stat.get("view", 0)

        return {
            "id": str(aid),
            "bvid": bvid,
            "title": title,
            "content": description,
            "author": author,
            "published_date": published_date,
            "source_url": f"https://www.bilibili.com/video/av{aid}" if aid else "",
            "view_count": view_count,
            "image_url": pic,
        }

    @staticmethod
    def _map_video(item: dict[str, Any]) -> dict[str, Any]:
        """Map a raw item from ``search/v2`` (fallback) to standardised fields.

        Args:
            item: Raw video item from the ``result`` list.

        Returns:
            Parsed dict with standardised field names.
        """
        aid = item.get("aid") or item.get("id") or ""
        bvid = item.get("bvid") or ""
        author = item.get("author") or ""
        pic = item.get("pic") or ""
        title = item.get("title", "") or ""
        description = item.get("description", "") or ""

        # Handle publish timestamp
        created = item.get("pubdate") or item.get("created") or 0
        published_date = ""
        if created:
            try:
                published_date = datetime.fromtimestamp(
                    int(created), tz=timezone.utc
                ).isoformat()
            except (ValueError, OSError):
                published_date = ""

        # View count — direct field in search/v2
        play = item.get("play") or 0
        # Also try stat dict for robustness
        stat = item.get("stat") or {}
        view_count = play or stat.get("view", 0)

        return {
            "id": str(aid),
            "bvid": bvid,
            "title": title,
            "content": description,
            "author": author,
            "published_date": published_date,
            "source_url": f"https://www.bilibili.com/video/av{aid}" if aid else "",
            "view_count": view_count,
            "image_url": pic,
        }

    # ------------------------------------------------------------------
    # Conversion to Item
    # ------------------------------------------------------------------

    def to_item(self, video: dict[str, Any]) -> Item:
        """Convert a parsed video dict to an :class:`Item` dataclass.

        Args:
            video: Parsed video dict as returned by :meth:`fetch`
                (already mapped by ``_map_video_all`` or ``_map_video``).

        Returns:
            An :class:`Item` instance populated from the video data.
        """
        video_id: str = video.get("id") or ""
        title: str = video.get("title") or ""

        return Item(
            id=video_id or str(uuid.uuid4()),
            source_name="bilibili",
            source_type="bilibili",
            source_platform="bilibili",
            source_url=video.get("source_url") or (
                f"https://www.bilibili.com/video/av{video_id}" if video_id else ""
            ),
            title=title,
            content=video.get("content") or "",
            content_type="text",
            collected_at=video.get("published_date") or "",
            domain="",
            topic_tags=[],
            raw_data={
                "video_id": video_id,
                "bvid": video.get("bvid") or "",
                "author": video.get("author") or "",
                "published_date": video.get("published_date") or "",
                "view_count": video.get("view_count") or 0,
                "image_url": video.get("image_url") or "",
            },
        )
