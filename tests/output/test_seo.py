"""Tests for SEO output module."""

import json
import pytest
from autoinfo.output.seo import generate_sitemap, generate_structured_data


class TestGenerateSitemap:
    def test_sitemap_has_urlset_root(self):
        xml = generate_sitemap(base_url="https://example.com")
        assert "<urlset" in xml
        assert "</urlset>" in xml
        assert "sitemaps.org" in xml

    def test_sitemap_includes_entries(self):
        entries = [
            {"url": "https://example.com/page1", "lastmod": "2026-07-30", "changefreq": "weekly", "priority": 0.8},
            {"url": "https://example.com/page2", "lastmod": "2026-07-29", "changefreq": "monthly", "priority": 0.5},
        ]
        xml = generate_sitemap(entries=entries, base_url="https://example.com")
        assert "<loc>https://example.com/page1</loc>" in xml
        assert "<loc>https://example.com/page2</loc>" in xml
        assert "0.8" in xml
        assert "weekly" in xml

    def test_sitemap_handles_empty_entries(self):
        xml = generate_sitemap(entries=[])
        assert "<urlset" in xml
        assert "</urlset>" in xml


class TestGenerateStructuredData:
    def test_valid_json_ld(self):
        ld = generate_structured_data(title="Test Article", description="A test")
        parsed = json.loads(ld)
        assert parsed["@context"] == "https://schema.org"
        assert parsed["@type"] == "Article"

    def test_includes_dates(self):
        ld = generate_structured_data(title="T", date_published="2026-07-30")
        parsed = json.loads(ld)
        assert "datePublished" in parsed
        assert parsed["datePublished"] == "2026-07-30"

    def test_custom_type(self):
        ld = generate_structured_data(title="T", article_type="NewsArticle")
        parsed = json.loads(ld)
        assert parsed["@type"] == "NewsArticle"

    def test_includes_url(self):
        ld = generate_structured_data(title="T", url="https://example.com/article")
        parsed = json.loads(ld)
        assert parsed["url"] == "https://example.com/article"
