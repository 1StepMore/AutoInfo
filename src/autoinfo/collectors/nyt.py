"""New York Times Article Search API collector handler.

Fetches articles from the NYT Article Search API
(https://api.nytimes.com/svc/search/v2/articlesearch.json) and maps them
to AutoInfo's internal item format.

API key required.  Free tier: 10 requests/minute, 5,000 requests/day.
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

BASE_URL = "https://api.nytimes.com/svc/search/v2/articlesearch.json"
DEFAULT_TIMEOUT = 30  # seconds
DEFAULT_LIMIT = 10
# Free tier: 10 req/min = 1 req / 6 seconds
RATE_LIMIT_RPS = 10.0 / 60.0  # ~0.167 req/s
ENV_API_KEY = "AUTOINFO_NYT_API_KEY"


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


class NYTHandler(BaseHandler):
    """Fetch articles from the New York Times Article Search API.

    Usage::

        handler = NYTHandler({"query": "climate change", "api_key": "..."})
        articles = handler.fetch(limit=10)
        items = [handler.to_item(a) for a in articles]
    """

    source_type: str = "nyt"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialise handler.

        Args:
            config: Dictionary with optional keys:
                - ``query``: search query string (default ``""``)
                - ``api_key``: NYT API key (falls back to
                  ``AUTOINFO_NYT_API_KEY`` environment variable)
                - ``begin_date``: start date filter ``YYYYMMDD``
                - ``end_date``: end date filter ``YYYYMMDD``
                - ``sort``: ``"newest"`` (default), ``"oldest"``, or
                  ``"relevance"``
        """
        if config is None:
            config = {}
        self.config: dict[str, Any] = config
        self.api_key: str = config.get("api_key", "") or os.environ.get(
            ENV_API_KEY, ""
        )
        self._last_request_time: float = 0.0

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    def _wait_for_rate_limit(self) -> None:
        """Block until the next request is allowed under the rate limit.

        Free tier: 10 requests/minute.
        """
        if self._last_request_time == 0.0:
            self._last_request_time = time.time()
            return

        elapsed = time.time() - self._last_request_time
        min_interval = 1.0 / RATE_LIMIT_RPS  # ~6.0 seconds
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_request_time = time.time()

    # ------------------------------------------------------------------
    # Field mapping
    # ------------------------------------------------------------------

    @staticmethod
    def _map_doc_to_article(doc: dict[str, Any]) -> dict[str, Any]:
        """Map a single NYT Article Search API doc to AutoInfo article dict.

        Args:
            doc: Raw document object from the ``response.docs`` list.

        Returns:
            Dict with keys: ``id``, ``title``, ``content``, ``section``,
            ``subsection``, ``published_date``, ``source_url``,
            ``byline``, ``word_count``, ``document_type``.
        """
        headline = doc.get("headline") or {}
        byline = doc.get("byline") or {}

        return {
            "id": doc.get("_id", ""),
            "title": headline.get("main", ""),
            "content": doc.get("abstract", "") or "",
            "section": doc.get("section_name", "") or "",
            "subsection": doc.get("subsection_name", "") or "",
            "published_date": doc.get("pub_date", ""),
            "source_url": doc.get("web_url", ""),
            "byline": byline.get("original", ""),
            "word_count": doc.get("word_count", 0),
            "document_type": doc.get("document_type", ""),
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch(self, limit: int = 10) -> list[dict[str, Any]]:
        """Fetch articles from the NYT Article Search API.

        Args:
            limit: Maximum number of results to return (default 10,
                max 200 at a time from the NYT API).

        Returns:
            List of article dicts, each with mapped fields.  Returns
            an empty list on error.
        """
        if limit <= 0:
            return []

        if not self.api_key:
            logger.warning(
                "NYT API key not set. Set AUTOINFO_NYT_API_KEY env var "
                "or pass api_key in config."
            )
            return []

        # -- Build query parameters --
        params: dict[str, Any] = {
            "api-key": self.api_key,
        }

        query = self.config.get("query", "")
        if query:
            params["q"] = query

        begin_date = self.config.get("begin_date", "")
        if begin_date:
            params["begin_date"] = begin_date

        end_date = self.config.get("end_date", "")
        if end_date:
            params["end_date"] = end_date

        sort = self.config.get("sort", "newest")
        if sort:
            params["sort"] = sort

        # -- Build URL --
        query_parts: list[str] = []
        for key, value in params.items():
            query_parts.append(f"{key}={quote(str(value))}")
        url = BASE_URL + "?" + "&".join(query_parts)

        # -- Make HTTP request --
        self._wait_for_rate_limit()

        try:
            response = httpx.get(
                url,
                timeout=DEFAULT_TIMEOUT,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "NYT HTTP error %s for URL %s",
                exc.response.status_code if exc.response else "?",
                url[:120],
                exc_info=True,
            )
            return []
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            logger.warning(
                "NYT network error for URL %s: %s",
                url[:120],
                exc,
            )
            return []
        except Exception as exc:
            logger.warning(
                "NYT unexpected error for URL %s: %s",
                url[:120],
                exc,
                exc_info=True,
            )
            return []

        # -- Parse JSON response --
        try:
            data = response.json()
        except ValueError as exc:
            logger.warning(
                "NYT returned non-JSON response for URL %s: %s",
                url[:120],
                exc,
            )
            return []

        response_data = data.get("response") or {}
        docs = response_data.get("docs", [])
        if not docs:
            return []

        # -- Map each doc to article dict --
        articles: list[dict[str, Any]] = []
        for doc in docs:
            article = self._map_doc_to_article(doc)
            articles.append(article)

        return articles[:limit]

    # ------------------------------------------------------------------
    # Conversion to Item
    # ------------------------------------------------------------------

    def to_item(self, article: dict[str, Any]) -> Item:
        """Convert a parsed article dict to an :class:`Item` dataclass.

        Args:
            article: Parsed article dict as returned by :meth:`fetch`.

        Returns:
            An :class:`Item` instance populated from the article data.
        """
        article_id = article.get("id", "")
        source_url = article.get("source_url", "")

        return Item(
            id=article_id or str(uuid.uuid4()),
            source_name="nyt",
            source_type="api",
            source_platform="nyt",
            source_url=source_url,
            title=article.get("title", ""),
            content=article.get("content", ""),
            content_type="text",
            collected_at=article.get("published_date", ""),
            domain="",
            topic_tags=[],
            raw_data={
                "section": article.get("section", ""),
                "subsection": article.get("subsection", ""),
                "byline": article.get("byline", ""),
                "word_count": article.get("word_count", 0),
                "document_type": article.get("document_type", ""),
                "published_date": article.get("published_date", ""),
            },
        )
