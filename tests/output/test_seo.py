"""Tests for SEO output module."""

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from autoinfo.kb import KBStore
from autoinfo.models import Item
from autoinfo.output import export_kb
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


# ---------------------------------------------------------------------------
# Fixtures for export_kb integration tests
# ---------------------------------------------------------------------------

_SAMPLE_CONFIG = {
    "project": {"name": "Test Project", "created_at": "2026-07-01"},
    "llm": {
        "provider": "openrouter",
        "model": "deepseek/deepseek-chat",
        "api_key": "test-key",
    },
    "domains": [
        {
            "name": "medical-research",
            "active": True,
            "sources": [],
            "topics": [{"name": "IVF breakthroughs", "keywords": ["IVF"]}],
        },
    ],
}


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """Create a temporary project with config and some KB entries."""
    config_dir = tmp_path / ".autoinfo"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.yaml"
    with open(config_path, "w", encoding="utf-8") as fh:
        yaml.dump(_SAMPLE_CONFIG, fh, default_flow_style=False)

    store = KBStore(base_path=tmp_path / "knowledge")
    store.store_entry(
        Item(
            id="med-1",
            source_name="pubmed",
            source_type="api",
            source_url="https://pubmed.example.com/article/1",
            title="IVF breakthrough study",
            content="Medical content about IVF breakthroughs.",
            collected_at="2026-07-15T10:00:00Z",
            domain="medical-research",
            topic_tags=["IVF"],
        )
    )
    store.store_entry(
        Item(
            id="med-2",
            source_name="pubmed",
            source_type="api",
            source_url="https://pubmed.example.com/article/2",
            title="Embryo selection advances",
            content="New embryo selection techniques.",
            collected_at="2026-07-16T10:00:00Z",
            domain="medical-research",
            topic_tags=["IVF"],
        )
    )
    return tmp_path


# ---------------------------------------------------------------------------
# Tests: export_kb(format="sitemap")
# ---------------------------------------------------------------------------


class TestExportKbSitemap:
    def test_returns_expected_keys(self, project_dir: Path) -> None:
        """export_kb(format='sitemap') returns expected result dict."""
        with patch("autoinfo.output.get_config_path") as mock_cfg:
            mock_cfg.return_value = project_dir / ".autoinfo" / "config.yaml"
            result = export_kb(domain="medical-research", format="sitemap")

        assert result["format"] == "sitemap"
        assert result["success"] is True
        assert result["entries_count"] == 2
        assert result["domain"] == "medical-research"
        assert "path" in result
        assert Path(result["path"]).exists()
        assert Path(result["path"]).name == "sitemap.xml"

    def test_writes_valid_xml(self, project_dir: Path) -> None:
        """Generated sitemap.xml is valid XML with sitemaps.org namespace."""
        with patch("autoinfo.output.get_config_path") as mock_cfg:
            mock_cfg.return_value = project_dir / ".autoinfo" / "config.yaml"
            result = export_kb(domain="medical-research", format="sitemap")

        tree = ET.parse(result["path"])
        root = tree.getroot()
        assert root.tag == "{https://www.sitemaps.org/schemas/sitemap/0.9}urlset"

    def test_contains_entry_urls(self, project_dir: Path) -> None:
        """Sitemap contains real entry URLs, not just the index page."""
        with patch("autoinfo.output.get_config_path") as mock_cfg:
            mock_cfg.return_value = project_dir / ".autoinfo" / "config.yaml"
            result = export_kb(domain="medical-research", format="sitemap")

        tree = ET.parse(result["path"])
        root = tree.getroot()
        ns = {"sm": "https://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = root.findall("sm:url", ns)
        assert len(urls) == 3

        locs = [u.find("sm:loc", ns).text for u in urls if u.find("sm:loc", ns) is not None]
        assert "https://pubmed.example.com/article/1" in locs
        assert "https://pubmed.example.com/article/2" in locs

    def test_empty_entries_handled(self, tmp_path: Path) -> None:
        """Sitemap export with zero entries still produces valid XML."""
        config_dir = tmp_path / ".autoinfo"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / "config.yaml"
        with open(config_path, "w", encoding="utf-8") as fh:
            yaml.dump(_SAMPLE_CONFIG, fh, default_flow_style=False)

        KBStore(base_path=tmp_path / "knowledge")

        with patch("autoinfo.output.get_config_path") as mock_cfg:
            mock_cfg.return_value = config_path
            result = export_kb(domain="medical-research", format="sitemap")

        assert result["format"] == "sitemap"
        assert result["success"] is True
        assert result["entries_count"] == 0
        assert Path(result["path"]).exists()

        tree = ET.parse(result["path"])
        root = tree.getroot()
        ns = {"sm": "https://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = root.findall("sm:url", ns)
        assert len(urls) == 1

    def test_includes_lastmod_from_collected_at(self, project_dir: Path) -> None:
        """Entry lastmod fields are derived from collected_at timestamps."""
        with patch("autoinfo.output.get_config_path") as mock_cfg:
            mock_cfg.return_value = project_dir / ".autoinfo" / "config.yaml"
            result = export_kb(domain="medical-research", format="sitemap")

        tree = ET.parse(result["path"])
        root = tree.getroot()
        ns = {"sm": "https://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = root.findall("sm:url", ns)
        lastmods = [
            u.find("sm:lastmod", ns).text
            for u in urls
            if u.find("sm:lastmod", ns) is not None
        ]
        assert "2026-07-15" in lastmods or "2026-07-16" in lastmods

    def test_invalid_format_raises_value_error(self, project_dir: Path) -> None:
        """Unsupported format raises ValueError."""
        with patch("autoinfo.output.get_config_path") as mock_cfg:
            mock_cfg.return_value = project_dir / ".autoinfo" / "config.yaml"
            with pytest.raises(ValueError, match="Unsupported export format"):
                export_kb(domain="medical-research", format="invalid")


# ---------------------------------------------------------------------------
# Tests: JSON-LD injection in HTML digest output
# ---------------------------------------------------------------------------


class TestJsonLdInjection:
    def test_digest_html_contains_json_ld_script_block(self) -> None:
        """Digest HTML rendered via _render_digest_html contains JSON-LD."""
        from autoinfo.output import _render_digest_html

        context: dict = {
            "title": "Medical Weekly Digest",
            "domain": "medical-research",
            "period": "week",
            "period_label": "This Week",
            "date_from": "2026-07-24",
            "date_to": "2026-07-30",
            "generated_at": "2026-07-31T10:00:00Z",
            "entries": [
                {
                    "title": "IVF Breakthrough",
                    "source_url": "https://pubmed.example.com/1",
                    "summary": "New IVF technique discovered.",
                    "relevance_score": 95,
                },
            ],
            "llm_synthesis": {
                "executive_summary": "Key breakthroughs in IVF research.",
                "key_findings": [],
                "trends": [],
                "recommendations": [],
            },
        }

        html = _render_digest_html(context)

        assert '<script type="application/ld+json">' in html, (
            "Digest HTML must contain JSON-LD script block"
        )
        assert '"@type"' in html, "JSON-LD must contain @type"
        assert '"Medical Weekly Digest"' in html, (
            "JSON-LD must include the title"
        )

    def test_report_html_contains_json_ld_script_block(self) -> None:
        """Report HTML rendered via _render_report_html contains JSON-LD."""
        from autoinfo.output import _render_report_html
        from autoinfo.output import ReportData

        report_data = ReportData(
            title="Medical Research Report",
            domain="medical-research",
            executive_summary="Summary of medical advances.",
            generated_at="2026-07-31T10:00:00Z",
            sections=[],
            references=[],
        )

        html = _render_report_html(report_data, period="month")

        assert '<script type="application/ld+json">' in html, (
            "Report HTML must contain JSON-LD script block"
        )
        assert '"@type"' in html, "JSON-LD must contain @type"
        assert '"Medical Research Report"' in html, (
            "JSON-LD must include the title"
        )


# ---------------------------------------------------------------------------
# Tests: MCP export_kb tool schema includes sitemap
# ---------------------------------------------------------------------------


class TestMcpExportKbEnum:
    def test_export_kb_schema_includes_sitemap(self) -> None:
        """MCP export_kb tool schema enum includes 'sitemap'."""
        import asyncio

        from autoinfo.mcp.server import list_tools

        tools = asyncio.run(list_tools())
        export_kb_tool = next(
            (t for t in tools if t.name == "export_kb"), None
        )
        assert export_kb_tool is not None, "export_kb tool must exist"

        schema = export_kb_tool.inputSchema
        fmt_enum = (
            schema.get("properties", {})
            .get("format", {})
            .get("enum", [])
        )
        assert "sitemap" in fmt_enum, (
            f"MCP export_kb format enum must include 'sitemap', got: {fmt_enum}"
        )
