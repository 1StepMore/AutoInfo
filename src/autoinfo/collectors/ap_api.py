"""Associated Press (AP) Content API handler.

Fetches news articles, photos, and videos from the AP Content API
(enterprise/paid endpoint).  Requires valid AP enterprise credentials.

.. warning::

    The AP Content API is a **paid / enterprise** service.  A valid API
    key is required for authentication.  Unauthorised requests (HTTP 401)
    are handled gracefully with an explanatory log message.

Documentation: https://developer.ap.org/
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

BASE_URL = "https://api.ap.org/media/v/content/search"
DEFAULT_TIMEOUT = 30  # seconds
MAX_RETRIES = 3
RETRY_DELAYS = [2, 4, 8]  # exponential backoff in seconds

# AP enterprise tier: documented at 100 requests / minute (≈1.67 req/s).
# We use a conservative default of 30 req/min (0.5 req/s) to stay safely
# under the limit.
RATE_LIMIT_DEFAULT = 0.5  # requests / second
RATE_LIMIT_WITH_KEY = 1.0  # requests / second (enterprise tier)

# Fields requested from the AP Content API per article
DEFAULT_FIELDS = "uri,headline,body,byline,published,section,language,source"


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


class APAPIHandler(BaseHandler):
    """Fetch news content from the Associated Press Content API.

    **Paid / enterprise source** — a valid AP API key is required.
    Set the ``AUTOINFO_AP_API_KEY`` environment variable or pass
    ``api_key`` directly to the constructor.

    Usage::

        handler = APAPIHandler(api_key="ap-xxxx")
        articles = handler.fetch(limit=10)
        items = [handler.to_item(a) for a in articles]
    """

    source_type: str = "ap_api"
    source_name: str = "ap_api"

    @staticmethod
    def requires_key() -> bool:
        """Return ``True`` — the AP Content API always requires a key."""
        return True

    def __init__(
        self,
        api_key: str | None = None,
        source_config: Any = None,
    ) -> None:
        """Initialise handler.

        Args:
            api_key: Optional AP API key.  Falls back to the
                ``AUTOINFO_AP_API_KEY`` environment variable.
            source_config: Optional :class:`SourceConfig` for per-source
                settings (e.g. query, rate_limit).
        """
        self.api_key = api_key or os.environ.get("AUTOINFO_AP_API_KEY", "")
        self.source_config = source_config
        self._rps = RATE_LIMIT_WITH_KEY if self.api_key else RATE_LIMIT_DEFAULT
        self._last_request_time: float = 0.0

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    def _wait_for_rate_limit(self) -> None:
        """Block until the next request is allowed under the rate limit."""
        if self._last_request_time == 0.0:
            self._last_request_time = time.time()
            return

        if self._rps <= 0:
            return

        elapsed = time.time() - self._last_request_time
        min_interval = 1.0 / self._rps
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_request_time = time.time()

    # ------------------------------------------------------------------
    # HTTP request with retry
    # ------------------------------------------------------------------

    def _request(
        self, url: str, headers: dict[str, str] | None = None
    ) -> httpx.Response:
        """Issue a GET request with rate limiting and exponential-backoff retry.

        Args:
            url: Fully qualified URL to fetch.
            headers: Optional HTTP headers (merged with auth header).

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

    def _build_headers(self) -> dict[str, str]:
        """Build HTTP headers including API key authentication.

        Headers:
            ``x-api-key``
                AP API key (if available).
            ``Accept``
                Always ``"application/json"``.
        """
        headers: dict[str, str] = {
            "Accept": "application/json",
        }
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch(self, limit: int = 10) -> list[dict[str, Any]]:
        """Fetch articles from the AP Content API.

        Args:
            limit: Maximum number of articles to return (default 10).

        Returns:
            List of parsed article dictionaries, each with keys:
            ``id``, ``title``, ``content``, ``author``,
            ``published_date``, ``section``, ``language``, ``source``.
            Returns an empty list on error or when no API key is configured
            (with a log message for 401).
        """
        if limit <= 0:
            return []

        # Warn early if no credentials are available — the API is paid.
        if not self.api_key:
            logger.warning(
                "AP API key not configured (set AUTOINFO_AP_API_KEY). "
                "AP Content API is a paid/enterprise service and requires "
                "valid credentials."
            )
            return []

        limit = min(limit, 100)  # AP max items per request

        # -- Build query parameters ------------------------------------------
        params: dict[str, Any] = {
            "limit": limit,
            "fields": DEFAULT_FIELDS,
        }

        # Optional search query from source_config
        if self.source_config is not None:
            settings = getattr(self.source_config, "settings", {}) or {}
            query = settings.get("query", "")
            if query:
                params["q"] = query

        # -- Build URL with query string -------------------------------------
        query_parts: list[str] = []
        for key, value in params.items():
            query_parts.append(f"{key}={quote(str(value))}")
        url = BASE_URL + "?" + "&".join(query_parts)

        # -- Make HTTP request -----------------------------------------------
        headers = self._build_headers()

        try:
            response = self._request(url, headers=headers)
        except httpx.HTTPStatusError as exc:
            status: int = exc.response.status_code if exc.response else 0
            if status == 401:
                logger.warning(
                    "AP API returned 401 Unauthorized. "
                    "The AP Content API is a paid/enterprise service — "
                    "valid credentials are required. "
                    "Please set AUTOINFO_AP_API_KEY or contact your AP "
                    "account manager.",
                )
            elif status == 403:
                logger.warning(
                    "AP API returned 403 Forbidden. "
                    "Your API key may not have access to the requested "
                    "resource or your subscription tier may be insufficient."
                )
            elif status == 429:
                logger.warning(
                    "AP API rate limit exceeded (429). "
                    "Backing off before the next collection cycle."
                )
            else:
                logger.warning(
                    "AP API HTTP error %d for URL %s",
                    status,
                    url,
                    exc_info=True,
                )
            return []
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            logger.warning(
                "AP API network error for URL %s: %s",
                url,
                exc,
            )
            return []
        except Exception as exc:
            logger.warning(
                "AP API unexpected error for URL %s: %s",
                url,
                exc,
                exc_info=True,
            )
            return []

        # -- Parse JSON response ---------------------------------------------
        try:
            data = response.json()
        except ValueError as exc:
            logger.warning(
                "AP API returned non-JSON response for URL %s: %s",
                url,
                exc,
            )
            return []

        # AP API response shape: {"data": {"items": [...]}}
        items = _traverse_json(data, "data.items")
        if items is None or not isinstance(items, list):
            logger.warning(
                "Unexpected AP API response structure (missing data.items) "
                "for URL %s",
                url,
            )
            return []

        # -- Map each article to standardised dict ---------------------------
        articles: list[dict[str, Any]] = []
        for raw in items:
            if not isinstance(raw, dict):
                continue
            article = self._map_article(raw)
            if article.get("id") or article.get("title"):
                articles.append(article)

        return articles[:limit]

    # ------------------------------------------------------------------
    # Field mapping
    # ------------------------------------------------------------------

    @staticmethod
    def _map_article(raw: dict[str, Any]) -> dict[str, Any]:
        """Map a raw AP API article dict to standardised AutoInfo fields.

        Field mapping (AP → AutoInfo):

        ====================== =============== ===========================
        AP field               AutoInfo field  Notes
        ====================== =============== ===========================
        ``uri``                ``id``          AP content URI (unique)
        ``headline``           ``title``       Article headline
        ``body``               ``content``     Full article body text
        ``byline``             ``author``      Author byline string
        ``published``          ``published``   ISO 8601 datetime
        ``section``            ``section``     Content section/category
        ``language``           ``language``    ISO language code
        ``source``             ``source``      Source attribution
        ====================== =============== ===========================

        Args:
            raw: Raw article dict from the AP API response.

        Returns:
            Parsed dict with standardised field names.
        """
        return {
            "id": raw.get("uri") or "",
            "title": raw.get("headline") or "",
            "content": raw.get("body") or "",
            "author": raw.get("byline") or "",
            "published_date": raw.get("published") or "",
            "section": raw.get("section") or "",
            "language": raw.get("language") or "",
            "source": raw.get("source") or "Associated Press",
        }

    # ------------------------------------------------------------------
    # Conversion to Item
    # ------------------------------------------------------------------

    def to_item(self, article: dict[str, Any]) -> Item:
        """Convert a parsed article dict to an :class:`Item` dataclass.

        Args:
            article: Parsed article dict as returned by :meth:`fetch`
                (already mapped by :meth:`_map_article`).

        Returns:
            An :class:`Item` instance populated from the article data.
        """
        article_id: str = article.get("id") or ""
        title: str = article.get("title") or ""

        return Item(
            id=article_id or str(uuid.uuid4()),
            source_name=self.source_name,
            source_type=self.source_type,
            source_platform="ap_api",
            source_url=article_id if article_id else "",
            title=title,
            content=article.get("content") or "",
            content_type="text",
            collected_at=article.get("published_date") or "",
            language=article.get("language") or "",
            domain="",
            topic_tags=[],
            raw_data={
                "ap_uri": article_id,
                "author": article.get("author") or "",
                "section": article.get("section") or "",
                "published_date": article.get("published_date") or "",
                "language": article.get("language") or "",
                "source": article.get("source") or "Associated Press",
            },
        )


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _traverse_json(data: dict[str, Any], dot_path: str) -> Any:
    """Traverse a nested dict/list by dot-separated path.

    Parameters
    ----------
    data : dict
        The JSON response dict.
    dot_path : str
        Dot-separated path, e.g. ``"data.items"``.

    Returns
    -------
    Any
        The value at the path, or ``None`` if any segment is missing.
    """
    current: Any = data
    for key in dot_path.split("."):
        if isinstance(current, dict):
            current = current.get(key)
            if current is None:
                return None
        elif isinstance(current, list):
            return None
        else:
            return None
    return current
