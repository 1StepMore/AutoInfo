"""SSRN (Social Science Research Network) handler.

Fetches social science working papers from SSRN's search page
(``https://papers.ssrn.com/sol3/results.cfm``) and parses
abstract-level information from the HTML response.

.. caution::

    SSRN does **not** provide a public REST API or Atom/RSS feed.
    This handler performs a best-effort parse of the search results
    HTML page.  Only publicly available abstract-level data is
    collected (title, authors, abstract snippet, date, SSRN abstract
    URL).  Full-text downloads are behind Elsevier's authentication
    wall and are intentionally out of scope.

    The HTML structure of SSRN's search results page may change
    without notice.  This handler falls back gracefully — returning
    an empty list rather than raising — when parsing fails.

Usage::

    handler = SSRNHandler({"query": "behavioral economics"})
    papers = handler.fetch(limit=10)
    items = [handler.to_item(p) for p in papers]
"""

from __future__ import annotations

import logging
import re
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

BASE_URL: str = "https://papers.ssrn.com/sol3/results.cfm"
DEFAULT_TIMEOUT: int = 30  # seconds
DEFAULT_LIMIT: int = 10
MAX_RETRIES: int = 3
RETRY_DELAYS: list[int] = [2, 4, 8]  # exponential backoff in seconds

# Polite rate limiting: 1 request per 2 seconds (SSRN is not an API server)
MIN_REQUEST_INTERVAL: float = 2.0


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


class SSRNHandler(BaseHandler):
    """Fetch social science working papers from SSRN search.

    SSRN does not expose a public API.  This handler fetches the
    HTML search results page and parses abstract-level metadata
    (title, authors, abstract snippet, date, SSRN URL).

    Usage::

        handler = SSRNHandler({"query": "cryptocurrency regulation"})
        papers = handler.fetch(limit=10)
    """

    source_type: str = "ssrn"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialise handler.

        Args:
            config: Dictionary with optional keys:
                - ``query``: default search query string (default ``""``)
                - ``max_rps``: requests per second rate limit
                  (default ``0.5``, i.e. one request every 2 seconds)
        """
        if config is None:
            config = {}
        self.config: dict[str, Any] = config
        self.query: str = config.get("query", "")
        self.max_rps: float = float(config.get("max_rps", 0.5))
        self._last_request_time: float = 0.0

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    def _wait_for_rate_limit(self) -> None:
        """Block until the next request is allowed (polite: 0.5 rps default)."""
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
    # HTML parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_search_results(html: str) -> list[dict[str, Any]]:
        """Parse SSRN search results HTML into structured paper dicts.

        Extracts abstract-level metadata from the HTML search results
        page.  This is a best-effort parser that looks for common
        patterns in SSRN's result layout:

        - Paper title from headline / link text
        - Authors from the metadata line
        - Abstract snippet from the description paragraph
        - Date from the publication metadata
        - Abstract ID from the URL (``abstract_id=...``)

        Args:
            html: Raw HTML of the SSRN search results page.

        Returns:
            List of parsed paper dicts.  Empty list if no results found
            or parsing fails completely.
        """
        if not html or not html.strip():
            return []

        papers: list[dict[str, Any]] = []

        # -- Pattern 1: Look for abstract ID links ----------------------------
        # SSRN links typically look like:
        #   /sol3/papers.cfm?abstract_id=1234567
        # or
        #   https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3542186
        abstract_url_pattern = re.compile(
            r'(?:https?://papers\.ssrn\.com)?/sol3/papers\.cfm\?abstract_id=(\d+)',
            re.IGNORECASE,
        )

        # Find all unique abstract IDs in order
        seen_ids: set[str] = set()
        for match in abstract_url_pattern.finditer(html):
            abstract_id = match.group(1)
            if abstract_id in seen_ids:
                continue
            seen_ids.add(abstract_id)

            paper_url = f"https://papers.ssrn.com/sol3/papers.cfm?abstract_id={abstract_id}"

            # Try to find title near the link (within ~2000 chars)
            # Extend context backward to capture the opening <a> tag
            link_start = match.start()
            ctx_start = max(0, link_start - 150)
            context_window = html[ctx_start : link_start + 2000]

            # Extract title: look for text between link and next tag boundary
            # Simple approach: title is typically the link text or nearby heading
            title = ""
            title_match = re.search(
                r'<a[^>]*abstract_id=' + re.escape(abstract_id) + r'[^>]*>([^<]+)',
                context_window,
                re.IGNORECASE,
            )
            if title_match:
                title = title_match.group(1).strip()
                # Clean HTML entities (necessary: SSRN encodes quotes/amps)
                title = (
                    title.replace("&amp;", "&")
                    .replace("&lt;", "<")
                    .replace("&gt;", ">")
                    .replace("&quot;", '"')
                    .replace("&#39;", "'")
                )

            # Try alt title extraction from meta/heading tags near the link
            if not title:
                alt_title = re.search(
                    r'<h\d[^>]*>([^<]+)</h\d>',
                    context_window,
                    re.IGNORECASE,
                )
                if alt_title:
                    title = alt_title.group(1).strip()

            # Extract authors (comma-separated names near the link)
            authors: list[str] = []
            author_match = re.search(
                r'(?:by|authors?)[:\s]*([^<]+)',
                context_window,
                re.IGNORECASE,
            )
            if author_match:
                author_text = author_match.group(1).strip()
                authors = [a.strip() for a in author_text.split(",") if a.strip()]

            # Extract abstract snippet
            content = ""
            abstract_match = re.search(
                r'(?:abstract|description)[:\s]*<[^>]*>?\s*([^<]{50,500})',
                context_window,
                re.IGNORECASE | re.DOTALL,
            )
            if abstract_match:
                content = abstract_match.group(1).strip()
                # Clean leading HTML tags
                content = re.sub(r'<[^>]+>', '', content).strip()

            # Extract date
            published_date = ""
            date_match = re.search(
                r'(?:posted|published|date)[:\s]*(\d{1,2}\s\w+\s\d{4}|\d{4}-\d{2}-\d{2}|\w+\s\d{1,2},?\s\d{4})',
                context_window,
                re.IGNORECASE,
            )
            if date_match:
                published_date = date_match.group(1).strip()

            papers.append({
                "id": abstract_id,
                "title": title,
                "content": content,
                "authors": authors,
                "published_date": published_date,
                "source_url": paper_url,
                "abstract_id": abstract_id,
            })

        return papers

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch(
        self,
        query: str = "",
        limit: int = DEFAULT_LIMIT,
    ) -> list[dict[str, Any]]:
        """Fetch working papers from SSRN search.

        Args:
            query: Search query string (e.g. ``"labor economics minimum wage"``).
                Falls back to ``self.query`` if empty.
            limit: Maximum number of papers to return (default 10).

        Returns:
            List of parsed paper dicts, each with standardised fields:
            ``id``, ``title``, ``content``, ``authors``,
            ``published_date``, ``source_url``, ``abstract_id``.
            Returns an empty list on error or if *limit* ≤ 0.

        Note:
            SSRN has no public API.  This method fetches the HTML search
            results page and performs best-effort parsing of abstract-level
            metadata.  The HTML structure may change; this handler degrades
            gracefully (empty list on parse failure).
        """
        if limit <= 0:
            return []

        search_query = (query or self.query).strip()
        if not search_query:
            logger.warning(
                "SSRN fetch called with empty query; returning empty list."
            )
            return []

        # Build SSRN search URL
        params: dict[str, Any] = {
            "txtKeywords": search_query,
        }
        url = f"{BASE_URL}?{urlencode(params)}"

        all_papers: list[dict[str, Any]] = []

        try:
            resp = self._request(url)
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code if exc.response else "?"
            logger.warning(
                "SSRN search HTTP error %s for query '%s': %s",
                status,
                search_query,
                exc,
            )
            return []
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            logger.warning(
                "SSRN search network error for query '%s': %s",
                search_query,
                exc,
            )
            return []

        # Parse HTML response
        try:
            html = resp.text
        except Exception as exc:
            logger.warning(
                "SSRN search response could not be read for query '%s': %s",
                search_query,
                exc,
            )
            return []

        if not html:
            logger.warning(
                "SSRN search returned empty body for query '%s'",
                search_query,
            )
            return []

        try:
            papers = self._parse_search_results(html)
            all_papers.extend(papers)
        except Exception as exc:
            logger.debug(
                "SSRN HTML parsing failed for query '%s': %s",
                search_query,
                exc,
                exc_info=True,
            )
            return []

        return all_papers[:limit]

    # ------------------------------------------------------------------
    # Conversion to Item
    # ------------------------------------------------------------------

    def to_item(self, paper: dict[str, Any]) -> Item:
        """Convert a parsed paper dict to an :class:`Item` dataclass.

        Args:
            paper: Parsed paper dict as returned by :meth:`fetch`.

        Returns:
            An :class:`Item` instance populated from the paper data.
        """
        paper_id: str = paper.get("id") or ""
        title: str = paper.get("title") or ""

        return Item(
            id=paper_id or str(uuid.uuid4()),
            source_name="ssrn",
            source_type="ssrn",
            source_platform="ssrn",
            source_url=paper.get("source_url") or "",
            title=title,
            content=paper.get("content") or "",
            content_type="text",
            collected_at=paper.get("published_date") or "",
            language="",
            domain="",
            topic_tags=[],
            raw_data={
                "ssrn_abstract_id": paper.get("abstract_id") or paper_id,
                "authors": paper.get("authors") or [],
                "published_date": paper.get("published_date") or "",
            },
        )

    # ------------------------------------------------------------------
    # Source metadata
    # ------------------------------------------------------------------

    @staticmethod
    def requires_key() -> bool:
        """Return ``False`` — SSRN search requires no API key."""
        return False

    @staticmethod
    def note() -> str | None:
        """Return a note about SSRN's lack of a public API."""
        return (
            "SSRN does not provide a public REST API or RSS feed. "
            "This handler performs best-effort HTML parsing of "
            "abstract-level metadata from the search results page. "
            "Full-text downloads and paywalled content are out of scope."
        )
