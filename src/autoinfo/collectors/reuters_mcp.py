"""Reuters MCP handler for enterprise news collection.

Provides :class:`ReutersMCPHandler` — a REST client that connects to a
configurable Reuters news endpoint.  This is an **enterprise-only** source
requiring a valid API key.  Without credentials all operations return an
empty list gracefully.

.. warning::

    Reuters MCP (Managed Content Provider) is an **enterprise / paid**
    service.  Authentication requires a valid API key.  The handler
    degrades gracefully — if the endpoint or key is missing it logs an
    informational message and returns ``[]``.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

from autoinfo.collectors.base import BaseHandler
from autoinfo.config import SourceConfig
from autoinfo.models import Item

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_ENDPOINT = "https://api.reuters.com/content/v1/search"
DEFAULT_TIMEOUT = 30  # seconds
MAX_RETRIES = 3
RETRY_DELAYS = [2, 4, 8]  # exponential backoff in seconds

# Default field mapping: Reuters response field → AutoInfo standard field.
# Overridable via ``field_mapping`` in the source's ``settings`` dict.
DEFAULT_FIELD_MAPPING: dict[str, str] = {
    "id": "id",
    "title": "headline",
    "content": "body",
    "author": "byline",
    "published_date": "published",
    "section": "section",
    "language": "language",
    "source": "source",
    "source_url": "url",
}


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


class ReutersMCPHandler(BaseHandler):
    """Fetch news content from the Reuters MCP endpoint.

    **Enterprise / paid source** — a valid Reuters API key is required.
    Set the ``AUTOINFO_REUTERS_API_KEY`` environment variable or provide
    an ``api_key`` in the source configuration ``settings`` dict.

    Configuration is read from ``SourceConfig.settings``:

    +----------------------+-------------------------------------------------+
    | Setting              | Description                                     |
    +======================+=================================================+
    | ``endpoint_url``     | Reuters MCP API endpoint URL.  Defaults to      |
    |                      | ``https://api.reuters.com/content/v1/search``.  |
    +----------------------+-------------------------------------------------+
    | ``api_key``          | Reuters API key.  Falls back to the             |
    |                      | ``AUTOINFO_REUTERS_API_KEY`` environment var.   |
    +----------------------+-------------------------------------------------+
    | ``query``            | Optional search query to include in the         |
    |                      | request payload.                                |
    +----------------------+-------------------------------------------------+
    | ``field_mapping``    | Dict mapping standard AutoInfo field names to   |
    |                      | Reuters response keys.  Merged on top of        |
    |                      | :data:`DEFAULT_FIELD_MAPPING`.                  |
    +----------------------+-------------------------------------------------+
    | ``rate_limit``       | Requests per second (default: ``1.0``).         |
    +----------------------+-------------------------------------------------+
    | ``timeout``          | Request timeout in seconds (default: ``30``).   |
    +----------------------+-------------------------------------------------+

    Usage::

        config = SourceConfig(
            name="reuters_mcp",
            type="reuters_mcp",
            url="https://api.reuters.com/content/v1/search",
            settings={
                "api_key": "sk-reuters-xxxx",
                "query": "technology",
            },
        )
        handler = ReutersMCPHandler(config)
        articles = handler.fetch(limit=10)
        items = [handler.to_item(article) for article in articles]
    """

    source_type: str = "reuters_mcp"
    source_name: str = "reuters_mcp"

    # Sentinel for handler-type dispatch in collect.py without an import.
    _handler_type: str = "ReutersMCPHandler"

    @staticmethod
    def requires_key() -> bool:
        """Return ``True`` — Reuters MCP always requires an API key."""
        return True

    def __init__(self, source_config: SourceConfig | None = None) -> None:
        """Initialise handler from a :class:`SourceConfig`.

        Args:
            source_config: Source configuration providing settings
                (endpoint_url, api_key, query, field_mapping, etc.).
        """
        self.source_config = source_config
        self._settings: dict[str, Any] = (
            source_config.settings if source_config is not None else {}
        )

        # Resolve API key: settings dict first, then environment variable.
        self.api_key: str = self._settings.get("api_key") or os.environ.get(
            "AUTOINFO_REUTERS_API_KEY", ""
        )

        # Resolve endpoint URL.
        self.endpoint_url: str = self._settings.get(
            "endpoint_url", DEFAULT_ENDPOINT
        )

        # Build field mapping: defaults merged with per-source overrides.
        self.field_mapping: dict[str, str] = dict(DEFAULT_FIELD_MAPPING)
        custom_mapping: dict[str, str] = self._settings.get("field_mapping", {})
        self.field_mapping.update(custom_mapping)

        self._rate_limit: float = float(self._settings.get("rate_limit", 1.0))
        self._timeout: float = float(self._settings.get("timeout", DEFAULT_TIMEOUT))
        self._last_request_time: float = 0.0

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    def _wait_for_rate_limit(self) -> None:
        """Block until the next request is allowed under the rate limit."""
        if self._last_request_time == 0.0:
            self._last_request_time = time.time()
            return

        if self._rate_limit <= 0:
            return

        elapsed = time.time() - self._last_request_time
        min_interval = 1.0 / self._rate_limit
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_request_time = time.time()

    # ------------------------------------------------------------------
    # HTTP request with retry
    # ------------------------------------------------------------------

    def _request(
        self, url: str, headers: dict[str, str] | None = None, json_body: dict[str, Any] | None = None
    ) -> httpx.Response:
        """Issue an HTTP request with rate limiting and exponential-backoff retry.

        Args:
            url: Fully qualified URL to POST to.
            headers: Optional HTTP headers (merged with auth header).
            json_body: Optional JSON payload for the POST body.

        Returns:
            HTTP response object.

        Raises:
            httpx.HTTPStatusError: On 4xx/5xx response (not retried).
            httpx.TimeoutException: After 3 retries all timed out.
            httpx.NetworkError: After 3 retries all failed.
        """
        last_exc: Exception | None = None

        for attempt in range(MAX_RETRIES):
            self._wait_for_rate_limit()
            try:
                response = httpx.post(
                    url,
                    headers=headers,
                    json=json_body,
                    timeout=self._timeout,
                )
                response.raise_for_status()
                return response
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_exc = exc
                if attempt == MAX_RETRIES - 1:
                    raise
                time.sleep(RETRY_DELAYS[attempt])

        # Unreachable.
        raise RuntimeError("Unexpected: all retries exhausted") from last_exc

    # ------------------------------------------------------------------
    # Header construction
    # ------------------------------------------------------------------

    def _build_headers(self) -> dict[str, str]:
        """Build HTTP headers including API key authentication.

        Returns:
            Dict with ``Accept``, ``Content-Type``, and ``Authorization``
            (if an API key is available).
        """
        headers: dict[str, str] = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch(self, limit: int = 10) -> list[dict[str, Any]]:
        """Fetch articles from the Reuters MCP endpoint.

        Args:
            limit: Maximum number of articles to return (default 10).

        Returns:
            List of mapped article dicts.  Returns an empty list on error
            or when the endpoint / API key is not configured.
        """
        if limit <= 0:
            return []

        # Validate prerequisites — enterprise source, graceful degradation.
        if not self.api_key:
            logger.info(
                "Reuters MCP API key not configured (set "
                "AUTOINFO_REUTERS_API_KEY or provide api_key in source "
                "settings). Reuters MCP is an enterprise/paid service."
            )
            return []

        if not self.endpoint_url:
            logger.info(
                "Reuters MCP endpoint not configured. "
                "Set endpoint_url in source settings."
            )
            return []

        # Clamp limit to a reasonable max.
        limit = min(limit, 100)

        # Build request body.
        payload: dict[str, Any] = {"limit": limit}
        query = self._settings.get("query", "")
        if query:
            payload["q"] = query

        headers = self._build_headers()

        try:
            response = self._request(
                self.endpoint_url, headers=headers, json_body=payload
            )
        except httpx.HTTPStatusError as exc:
            status: int = exc.response.status_code if exc.response else 0
            if status == 401:
                logger.info(
                    "Reuters MCP returned 401 Unauthorized. "
                    "Reuters MCP is an enterprise/paid service — "
                    "valid credentials are required."
                )
            elif status == 403:
                logger.info(
                    "Reuters MCP returned 403 Forbidden. "
                    "Your API key may not have access to the requested "
                    "endpoint or your subscription tier may be insufficient."
                )
            elif status == 429:
                logger.info(
                    "Reuters MCP rate limit exceeded (429). "
                    "Backing off before the next collection cycle."
                )
            else:
                logger.info(
                    "Reuters MCP HTTP error %d from %s: %s",
                    status,
                    self.endpoint_url,
                    exc,
                )
            return []
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            logger.info(
                "Reuters MCP network error for %s: %s",
                self.endpoint_url,
                exc,
            )
            return []
        except Exception as exc:
            logger.info(
                "Reuters MCP unexpected error for %s: %s",
                self.endpoint_url,
                exc,
                exc_info=True,
            )
            return []

        # Parse JSON.
        try:
            data = response.json()
        except ValueError as exc:
            logger.info(
                "Reuters MCP returned non-JSON response from %s: %s",
                self.endpoint_url,
                exc,
            )
            return []

        # Extract the articles array.
        items_raw = _extract_items(data)
        if items_raw is None or not isinstance(items_raw, list):
            logger.info(
                "Unexpected Reuters MCP response structure from %s",
                self.endpoint_url,
            )
            return []

        # Map each raw article to a standardised dict.
        articles: list[dict[str, Any]] = []
        for raw in items_raw:
            if not isinstance(raw, dict):
                continue
            article = self._map_article(raw)
            if article.get("id") or article.get("title"):
                articles.append(article)

        return articles[:limit]

    # ------------------------------------------------------------------
    # Field mapping
    # ------------------------------------------------------------------

    def _map_article(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Map a raw article dict to standard AutoInfo fields.

        Uses ``self.field_mapping`` to translate Reuters field names to
        AutoInfo standard field names.  The mapping is initialised from
        :data:`DEFAULT_FIELD_MAPPING` and can be extended via the
        ``field_mapping`` source setting.

        Args:
            raw: Raw article dict from the Reuters API response.

        Returns:
            Dict with standardised AutoInfo field names.
        """
        mapped: dict[str, Any] = {}
        for auto_field, reuters_key in self.field_mapping.items():
            mapped[auto_field] = raw.get(reuters_key, "")
        # Ensure 'source' has a fallback.
        if not mapped.get("source"):
            mapped["source"] = "Reuters"
        return mapped

    # ------------------------------------------------------------------
    # Conversion to Item
    # ------------------------------------------------------------------

    def to_item(self, article: dict[str, Any]) -> Item:
        """Convert a mapped article dict to an :class:`Item` dataclass.

        Args:
            article: Parsed article dict as returned by :meth:`fetch`
                (already mapped by :meth:`_map_article`).

        Returns:
            An :class:`Item` instance populated from the article data.
        """
        article_id: str = article.get("id") or ""
        title: str = article.get("title") or ""
        content: str = article.get("content") or ""
        published_date: str = article.get("published_date") or ""
        language: str = article.get("language") or ""
        author: str = article.get("author") or ""
        section: str = article.get("section") or ""

        return Item(
            id=article_id or str(uuid.uuid4()),
            source_name=self.source_name,
            source_type=self.source_type,
            source_platform="reuters_mcp",
            source_url=article.get("source_url") or article_id or "",
            title=title,
            content=content,
            content_type="text",
            collected_at=published_date or datetime.now(timezone.utc).isoformat(),
            language=language,
            domain="",
            topic_tags=[],
            raw_data={
                "author": author,
                "section": section,
                "published_date": published_date,
                "language": language,
                "source": article.get("source", "Reuters"),
            },
        )


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _extract_items(data: Any) -> list[dict[str, Any]] | None:
    """Extract the articles array from the Reuters API response.

    Tries common response shapes in order:
    1. ``{"data": {"items": [...]}}``  (Reuters standard)
    2. ``{"items": [...]}``
    3. ``{"results": [...]}``
    4. Top-level list: ``[...]``
    5. Wrap single dict: ``{"data": {...}}``

    Args:
        data: Parsed JSON response.

    Returns:
        List of raw article dicts, or ``None`` if unrecognised.
    """
    if isinstance(data, list):
        return data

    if not isinstance(data, dict):
        return None

    # Shape 1: data.items
    data_obj = data.get("data")
    if isinstance(data_obj, dict):
        items = data_obj.get("items")
        if isinstance(items, list):
            return items
        # Shape 5: wrap single dict
        if isinstance(data_obj, dict) and data_obj:
            return [data_obj]

    # Shape 2: items
    items = data.get("items")
    if isinstance(items, list):
        return items

    # Shape 3: results
    results = data.get("results")
    if isinstance(results, list):
        return results

    return None
