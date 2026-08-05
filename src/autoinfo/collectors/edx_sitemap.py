"""edX course discovery via the public sitemap.

Fetches ``https://www.edx.org/sitemap.xml`` (a sitemap index), follows the
course sub-sitemaps, and extracts course metadata from the JSON-LD
``<script type="application/ld+json">`` blocks embedded in each course page.

Politeness contract (A27):

* robots.txt — ``/course/`` paths are only crawled when
  ``https://www.edx.org/robots.txt`` allows them (RFC 9309 subset).
* Throttle — a configurable delay (default 1s) is applied between
  consecutive requests.

``fetch`` never raises: any network or parse error returns ``[]``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

import httpx

from autoinfo.collectors.base import BaseHandler
from autoinfo.models import Item

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_TIMEOUT: int = 15  # seconds
DEFAULT_LIMIT: int = 20
DEFAULT_RATE_LIMIT: float = 1.0  # seconds between requests (polite)
DEFAULT_SITEMAP_URL: str = "https://www.edx.org/sitemap.xml"
ROBOTS_URL: str = "https://www.edx.org/robots.txt"
COURSE_PATH: str = "/course/"
_NAMESPACES: tuple[str, ...] = (
    "{http://www.sitemaps.org/schemas/sitemap/0.9}loc",
    "{http://www.sitemaps.org/schemas/sitemap/0.9}url",
    "{http://www.sitemaps.org/schemas/sitemap/0.9}sitemap",
    "loc",
)
_JSONLD_SCRIPT_RE = re.compile(
    r"<script[^>]*type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
    re.DOTALL | re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


class EdxSitemapHandler(BaseHandler):
    """Discover edX courses through the public sitemap index.

    Usage::

        handler = EdxSitemapHandler(config={
            "sitemap_url": "https://www.edx.org/sitemap.xml",
            "rate_limit": 1,
        })
        payloads = handler.fetch(limit=10)
        items = [handler.to_item(p) for p in payloads]
    """

    source_type: str = "edx_sitemap"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialise from a settings dict (``config=source_config.settings``).

        Args:
            config: Optional settings dict with ``sitemap_url``
                (default the live edX sitemap index), ``limit``,
                ``rate_limit`` (seconds between requests) and ``timeout``.
        """
        settings: dict[str, Any] = config or {}
        self.config: dict[str, Any] = settings
        self.source_name: str = str(settings.get("name", "edX Sitemap"))
        self.sitemap_url: str = str(
            settings.get("sitemap_url", DEFAULT_SITEMAP_URL)
        ).rstrip("/")
        self.robots_url: str = ROBOTS_URL
        self.limit: int = int(settings.get("limit", DEFAULT_LIMIT))
        self.rate_limit: float = float(settings.get("rate_limit", DEFAULT_RATE_LIMIT))
        self.timeout: int = int(settings.get("timeout", DEFAULT_TIMEOUT))
        self._last_request_time: float = 0.0

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    def _wait_for_rate_limit(self) -> None:
        """Sleep so consecutive requests are at least ``rate_limit`` seconds apart."""
        if self.rate_limit <= 0:
            return
        if self._last_request_time == 0.0:
            self._last_request_time = time.time()
            return
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self._last_request_time = time.time()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch(self, limit: int = DEFAULT_LIMIT) -> list[dict[str, Any]]:  # type: ignore[override]
        """Fetch course metadata from the edX sitemap.

        Args:
            limit: Maximum number of courses to return (default 20).

        Returns:
            List of course payload dicts with ``title``, ``description``,
            ``provider`` and ``url`` keys.  Returns ``[]`` on any network
            or parse error — this method **never** raises.
        """
        if limit <= 0:
            return []

        xml_text = self._fetch_sitemap_index()
        if xml_text is None:
            return []

        course_urls = self._resolve_course_urls(xml_text, limit)
        if not course_urls:
            return []

        # Politeness gate: only crawl /course/ pages robots.txt allows.
        if not self._robots_allows_course():
            logger.warning("robots.txt disallows %s — skipping edX crawl", COURSE_PATH)
            return []

        payloads: list[dict[str, Any]] = []
        for url in course_urls[:limit]:
            payload = self._fetch_course_page(url)
            if payload is not None:
                payloads.append(payload)
        return payloads

    # ------------------------------------------------------------------
    # Conversion to Item
    # ------------------------------------------------------------------

    def to_item(self, payload: dict[str, Any]) -> Item:
        """Convert a course payload dict to an :class:`Item`."""
        source_url: str = payload.get("url") or ""
        sid: str = ""
        if source_url:
            sid = hashlib.sha256(source_url.encode()).hexdigest()[:16]
        title: str = payload.get("title") or "edX course"
        description: str = payload.get("description") or ""

        return Item(
            id=sid,
            source_name=self.source_name,
            source_type="edx_sitemap",
            source_url=source_url,
            title=title,
            content=description,
            content_type="text",
            source_platform="edx_sitemap",
            collected_at=datetime.now(timezone.utc).isoformat(),
            raw_data=payload,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_sitemap_index(self) -> str | None:
        """GET the sitemap index; returns XML text or ``None`` on failure."""
        try:
            self._wait_for_rate_limit()
            resp = httpx.get(self.sitemap_url, timeout=self.timeout)
            resp.raise_for_status()
            return resp.text
        except Exception as exc:
            logger.error("edX sitemap index fetch failed: %s", exc)
            return None

    def _resolve_course_urls(self, xml_text: str, limit: int) -> list[str]:
        """Extract course URLs from the sitemap index (following sub-sitemaps)."""
        root = self._parse_sitemap_xml(xml_text)
        if root is None:
            return []

        locs = [el.text.strip() for el in root.iter() if _is_loc_element(el) and el.text]
        if not locs:
            return []

        course_urls: list[str] = []
        for loc in locs:
            if COURSE_PATH in loc:
                course_urls.append(loc)
            elif "sitemap" in loc:
                # Sub-sitemap reference — resolve it and keep course URLs.
                sub_locs = self._fetch_sitemap_locs(loc)
                course_urls.extend(u for u in sub_locs if COURSE_PATH in u)
            if len(course_urls) >= limit:
                break
        return course_urls[:limit]

    def _fetch_sitemap_locs(self, sitemap_url: str) -> list[str]:
        """Fetch a sub-sitemap and return its ``<loc>`` entries."""
        try:
            self._wait_for_rate_limit()
            resp = httpx.get(sitemap_url, timeout=self.timeout)
            resp.raise_for_status()
            root = self._parse_sitemap_xml(resp.text)
        except Exception as exc:
            logger.warning("edX sub-sitemap fetch failed for %s: %s", sitemap_url, exc)
            return []
        if root is None:
            return []
        return [el.text.strip() for el in root.iter() if _is_loc_element(el) and el.text]

    @staticmethod
    def _parse_sitemap_xml(xml_text: str) -> ET.Element | None:
        """Parse sitemap XML; returns ``None`` on malformed input."""
        try:
            return ET.fromstring(xml_text)
        except ET.ParseError as exc:
            logger.error("edX sitemap XML parse error: %s", exc)
            return None

    def _robots_allows_course(self) -> bool:
        """Check robots.txt allows ``/course/`` paths (RFC 9309 subset).

        If robots.txt cannot be fetched the crawl is allowed to proceed
        (RFC 9309 §2.3.1: an unreachable robots.txt implies no rules) but
        the failure is logged.
        """
        try:
            self._wait_for_rate_limit()
            resp = httpx.get(self.robots_url, timeout=self.timeout)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning(
                "robots.txt fetch failed (%s) — proceeding with course crawl", exc
            )
            return True
        return robots_allows(resp.text, COURSE_PATH, user_agent="*")

    def _fetch_course_page(self, url: str) -> dict[str, Any] | None:
        """Fetch a course page and extract its JSON-LD metadata."""
        try:
            self._wait_for_rate_limit()
            resp = httpx.get(url, timeout=self.timeout)
            resp.raise_for_status()
            return self._extract_course_metadata(resp.text, url)
        except Exception as exc:
            logger.warning("edX course page fetch failed for %s: %s", url, exc)
            return None

    @staticmethod
    def _extract_course_metadata(html_text: str, url: str) -> dict[str, Any]:
        """Extract course name/description/provider from JSON-LD.

        Falls back to a URL-derived title when no JSON-LD ``Course`` node
        is found, so a page without structured data still yields an item.
        """
        for match in _JSONLD_SCRIPT_RE.finditer(html_text):
            try:
                data: Any = json.loads(match.group(1).strip())
            except (json.JSONDecodeError, ValueError):
                continue
            node = _find_course_node(data)
            if node is None:
                continue
            provider = node.get("provider") or {}
            if not isinstance(provider, dict):
                provider = {}
            return {
                "title": str(node.get("name") or ""),
                "description": str(node.get("description") or ""),
                "provider": str(provider.get("name") or ""),
                "url": url,
            }

        slug = url.rstrip("/").rsplit("/", 1)[-1].replace("-", " ").replace("_", " ")
        title = slug.strip().title() or "edX course"
        return {"title": title, "description": "", "provider": "", "url": url}


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _is_loc_element(el: ET.Element) -> bool:
    """True for ``<loc>`` elements regardless of sitemap namespace."""
    return el.tag in _NAMESPACES or el.tag.endswith("}loc")


def _find_course_node(data: Any) -> dict[str, Any] | None:
    """Walk JSON-LD (dict / list / @graph) looking for a ``Course`` node."""
    if isinstance(data, list):
        for item in data:
            node = _find_course_node(item)
            if node is not None:
                return node
        return None
    if not isinstance(data, dict):
        return None
    node_type = str(data.get("@type") or "")
    if "Course" in node_type:
        return data
    graph = data.get("@graph")
    if isinstance(graph, (list, dict)):
        return _find_course_node(graph)
    return None


def _parse_robots_rules(robots_text: str, user_agent: str) -> list[tuple[str, str]]:
    """Parse robots.txt into ``(type, path)`` rules for *user_agent*.

    Only the group whose ``User-agent`` line matches *user_agent* (case
    insensitive, ``*`` wildcard) contributes rules; the last matching
    group wins, per RFC 9309 §2.2.1.
    """
    rules: list[tuple[str, str]] = []
    group_active = False
    for raw_line in robots_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        field, _, value = line.partition(":")
        field = field.strip().lower()
        value = value.strip()
        if field == "user-agent":
            group_active = value.lower() == user_agent.lower()
        elif group_active and field in ("allow", "disallow"):
            rules.append((field, value))
    return rules


def robots_allows(robots_text: str, url_path: str, user_agent: str = "*") -> bool:
    """Decide whether *url_path* may be crawled under *robots_text*.

    Longest-matching rule wins; an ``Allow`` and ``Disallow`` of equal
    length prefer ``Allow`` (RFC 9309 §2.2.2).  Empty ``Disallow`` means
    "allow all".  No matching rule → allowed.
    """
    rules = _parse_robots_rules(robots_text, user_agent)
    best: tuple[int, str] | None = None
    for rule_type, rule_path in rules:
        if rule_type == "disallow" and rule_path == "":
            continue  # empty Disallow is a no-op
        if not url_path.startswith(rule_path):
            continue
        if best is None or len(rule_path) > best[0]:
            best = (len(rule_path), rule_type)
        elif len(rule_path) == best[0] and rule_type == "allow":
            best = (len(rule_path), rule_type)
    if best is None:
        return True
    return best[1] == "allow"
