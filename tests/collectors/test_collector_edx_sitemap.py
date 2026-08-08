"""Tests for the edX Sitemap handler (A27 — edX course discovery).

Verifies: sitemap-index parse → course sub-sitemaps → JSON-LD course
metadata extraction, robots.txt politeness (disallowed paths are skipped),
per-request throttling, ``to_item`` conversion, and the never-raises
contract (network/parse errors return ``[]``).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from autoinfo.collect import _build_handler
from autoinfo.collectors.edx_sitemap import EdxSitemapHandler
from autoinfo.config import SourceConfig

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SITEMAP_INDEX_XML = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap>
    <loc>https://www.edx.org/sitemap/sitemap-course-0.xml</loc>
  </sitemap>
  <sitemap>
    <loc>https://www.edx.org/sitemap/sitemap-page-0.xml</loc>
  </sitemap>
</sitemapindex>
"""

COURSE_SITEMAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://www.edx.org/course/introduction-to-python</loc>
  </url>
  <url>
    <loc>https://www.edx.org/course/linear-algebra-foundations</loc>
  </url>
</urlset>
"""

PAGE_SITEMAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://www.edx.org/about</loc>
  </url>
</urlset>
"""

COURSE_PAGE_PYTHON = """<!DOCTYPE html>
<html>
<head>
  <title>Introduction to Python</title>
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "Course",
    "name": "Introduction to Python",
    "description": "Learn Python programming from scratch.",
    "provider": {"@type": "Organization", "name": "edX"}
  }
  </script>
</head>
<body><h1>Introduction to Python</h1></body>
</html>
"""

COURSE_PAGE_LINEAR = """<!DOCTYPE html>
<html>
<head>
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "Course",
    "name": "Linear Algebra Foundations",
    "description": "Master vectors, matrices and eigenvalues.",
    "provider": {"@type": "Organization", "name": "edX"}
  }
  </script>
</head>
<body></body>
</html>
"""

ROBOTS_ALLOW = """User-agent: *
Disallow: /admin/
Allow: /
"""

ROBOTS_DISALLOW_COURSE = """User-agent: *
Disallow: /course/
"""


@pytest.fixture
def edx_config() -> dict[str, object]:
    """Config matching the M2T18 dispatch branch (``config=settings``)."""
    return {"sitemap_url": "https://www.edx.org/sitemap.xml", "rate_limit": 0}


def _fake_response(text: str) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.text = text
    resp.raise_for_status.return_value = None
    return resp


def _side_effect_for(robots_text: str = ROBOTS_ALLOW) -> "object":
    """Build an ``httpx.get`` side_effect serving the fixture set."""

    def side_effect(url: str, **kwargs: object) -> MagicMock:
        if "sitemap.xml" in url:
            return _fake_response(SITEMAP_INDEX_XML)
        if "sitemap-course" in url:
            return _fake_response(COURSE_SITEMAP_XML)
        if "sitemap-page" in url:
            return _fake_response(PAGE_SITEMAP_XML)
        if "robots.txt" in url:
            return _fake_response(robots_text)
        if "introduction-to-python" in url:
            return _fake_response(COURSE_PAGE_PYTHON)
        if "linear-algebra" in url:
            return _fake_response(COURSE_PAGE_LINEAR)
        return _fake_response("<html><body></body></html>")

    return side_effect


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEdxSitemapHandler:
    def test_source_type_attribute(self, edx_config: dict[str, object]) -> None:
        handler = EdxSitemapHandler(config=edx_config)
        assert handler.source_type == "edx_sitemap"

    @patch("autoinfo.collectors.edx_sitemap.httpx.get")
    def test_fetch_follows_index_to_course_pages(
        self, mock_get: MagicMock, edx_config: dict[str, object]
    ) -> None:
        mock_get.side_effect = _side_effect_for()

        handler = EdxSitemapHandler(config=edx_config)
        raw_items = handler.fetch(limit=5)

        # Course sitemap has 2 course URLs; the /about page sitemap yields none.
        assert len(raw_items) == 2

        titles = {p["title"] for p in raw_items}
        assert titles == {"Introduction to Python", "Linear Algebra Foundations"}
        urls = {p["url"] for p in raw_items}
        assert "https://www.edx.org/course/introduction-to-python" in urls
        # JSON-LD provider extracted into the payload
        assert {p.get("provider") for p in raw_items} == {"edX"}

    @patch("autoinfo.collectors.edx_sitemap.httpx.get")
    def test_fetch_limit_respected(
        self, mock_get: MagicMock, edx_config: dict[str, object]
    ) -> None:
        mock_get.side_effect = _side_effect_for()

        handler = EdxSitemapHandler(config=edx_config)
        raw_items = handler.fetch(limit=1)
        assert len(raw_items) == 1

    @patch("autoinfo.collectors.edx_sitemap.httpx.get")
    def test_robots_disallowed_course_path_skips(
        self, mock_get: MagicMock, edx_config: dict[str, object]
    ) -> None:
        mock_get.side_effect = _side_effect_for(ROBOTS_DISALLOW_COURSE)

        handler = EdxSitemapHandler(config=edx_config)
        raw_items = handler.fetch(limit=5)

        assert raw_items == []
        # No course page may be fetched when robots.txt forbids /course/
        course_calls = [
            c.args[0]
            for c in mock_get.call_args_list
            if "course" in c.args[0] and "sitemap" not in c.args[0]
        ]
        assert course_calls == []

    @patch("autoinfo.collectors.edx_sitemap.httpx.get")
    def test_robots_allows_other_paths(
        self, mock_get: MagicMock, edx_config: dict[str, object]
    ) -> None:
        mock_get.side_effect = _side_effect_for(ROBOTS_ALLOW)

        handler = EdxSitemapHandler(config=edx_config)
        raw_items = handler.fetch(limit=5)
        assert len(raw_items) == 2

    @patch("autoinfo.collectors.edx_sitemap.time.sleep")
    @patch("autoinfo.collectors.edx_sitemap.httpx.get")
    def test_fetch_throttles_requests(
        self,
        mock_get: MagicMock,
        mock_sleep: MagicMock,
    ) -> None:
        mock_get.side_effect = _side_effect_for()

        handler = EdxSitemapHandler(config={"rate_limit": 5})
        handler.fetch(limit=5)

        # index + course sitemap + page sitemap + robots + 2 course pages
        assert mock_get.call_count == 6
        # every request after the first sleeps up to the rate limit
        assert mock_sleep.call_count >= 3

    def test_to_item(self, edx_config: dict[str, object]) -> None:
        handler = EdxSitemapHandler(config=edx_config)
        payload = {
            "title": "Introduction to Python",
            "description": "Learn Python programming from scratch.",
            "provider": "edX",
            "url": "https://www.edx.org/course/introduction-to-python",
        }
        item = handler.to_item(payload)
        assert item.title == "Introduction to Python"
        assert item.content == "Learn Python programming from scratch."
        assert item.source_url == "https://www.edx.org/course/introduction-to-python"
        assert item.source_type == "edx_sitemap"
        assert item.source_platform == "edx_sitemap"
        assert item.raw_data == payload

    def test_to_item_fallback_fields(self, edx_config: dict[str, object]) -> None:
        handler = EdxSitemapHandler(config=edx_config)
        item = handler.to_item({"url": "https://www.edx.org/course/some-course"})
        assert item.title  # never empty
        assert item.source_url == "https://www.edx.org/course/some-course"

    @patch("autoinfo.collectors.edx_sitemap.httpx.get")
    def test_fetch_network_error_returns_empty(
        self, mock_get: MagicMock, edx_config: dict[str, object]
    ) -> None:
        mock_get.side_effect = httpx.NetworkError("Connection refused")
        handler = EdxSitemapHandler(config=edx_config)
        assert handler.fetch(limit=5) == []

    @patch("autoinfo.collectors.edx_sitemap.httpx.get")
    def test_fetch_malformed_xml_returns_empty(
        self, mock_get: MagicMock, edx_config: dict[str, object]
    ) -> None:
        mock_get.return_value = _fake_response("<not-xml>")
        handler = EdxSitemapHandler(config=edx_config)
        assert handler.fetch(limit=5) == []

    @patch("autoinfo.collectors.edx_sitemap.httpx.get")
    def test_fetch_zero_limit_returns_empty(
        self, mock_get: MagicMock, edx_config: dict[str, object]
    ) -> None:
        handler = EdxSitemapHandler(config=edx_config)
        assert handler.fetch(limit=0) == []
        mock_get.assert_not_called()


class TestEdxSitemapDispatch:
    def test_build_handler_routes_to_edx(self) -> None:
        cfg = SourceConfig(name="t", type="edx_sitemap", url="", settings={})
        handler = _build_handler(cfg)
        assert isinstance(handler, EdxSitemapHandler)
        assert handler.source_type == "edx_sitemap"
