"""Issue #645: the skeleton-placeholder cleaner must not eat real HTML tags.

The product-template render path runs ``_clean_skeleton_placeholders`` over
the rendered document to remove LLM-echoed placeholders such as
``<finding 1>``.  Its regex also matched *bare* HTML tags (``<head>``,
``<title>``, ``<style>``, ``<h1>``…), so every gated product rendered as
``:html`` lost its document structure: no ``<head>``/``<title>`` and zero
headings, which fails the L2 structural check (``format_structure``) and
pinned those cells at L1 forever.
"""

from __future__ import annotations

import re
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest

from autoinfo.llm import LLMExtractor
from autoinfo.models import ExtractionResult
from autoinfo.output import (
    PRODUCT_TEMPLATES,
    ProductTemplate,
    _clean_skeleton_placeholders,
    generate_report,
)
from tests._freshness import fresh_iso

_HTML_DOC = (
    "<!DOCTYPE html>\n"
    "<html lang='en'>\n"
    "<head>\n"
    "<meta charset='utf-8'>\n"
    "<title>Medical Research \u2014 Report</title>\n"
    "<style>\n"
    ":root { --bg: #f7f8fa; }\n"
    "</style>\n"
    "</head>\n"
    "<body>\n"
    "<h1>Report</h1>\n"
    "<h2>Finding one</h2>\n"
    "<h2>Finding two</h2>\n"
    "<ul><li>item</li></ul>\n"
    "</body>\n"
    "</html>\n"
)


class TestSkeletonCleanerPreservesHtml:
    """``_clean_skeleton_placeholders`` is a placeholder cleaner, not a stripper."""

    def test_keeps_document_skeleton_tags(self) -> None:
        cleaned = _clean_skeleton_placeholders(_HTML_DOC)
        for tag in ("<head>", "<title>", "<style>", "<body>", "<h1>", "<h2>", "<ul>", "<li>"):
            assert tag in cleaned, f"{tag} was stripped from the HTML document"

    def test_keeps_title_text_and_heading_count(self) -> None:
        cleaned = _clean_skeleton_placeholders(_HTML_DOC)
        title = re.search(r"<title>(.*?)</title>", cleaned, re.S)
        assert title is not None
        assert title.group(1).strip() == "Medical Research \u2014 Report"
        assert len(re.findall(r"<h[1-6][ >]", cleaned)) >= 3

    def test_still_strips_llm_placeholders(self) -> None:
        text = "## Finding 1\n<finding 1>\nMetric: <metric>\n<section heading 1>\n<objective 2>\n"
        cleaned = _clean_skeleton_placeholders(text)
        assert "<finding 1>" not in cleaned
        assert "<metric>" not in cleaned
        assert "<section heading 1>" not in cleaned
        assert "<objective 2>" not in cleaned

    def test_strips_placeholders_from_html_body(self) -> None:
        cleaned = _clean_skeleton_placeholders(
            "<h2>Key metric</h2>\n<p><metric></p>\n<h2>Next</h2>"
        )
        assert "<metric>" not in cleaned
        assert "<h2>" in cleaned
        assert "Key metric" in cleaned


def _registry_template(name: str) -> ProductTemplate:
    for row in PRODUCT_TEMPLATES:
        if row["name"] == name:
            return cast(ProductTemplate, row["template"])
    raise AssertionError(f"{name} ProductTemplate row missing from PRODUCT_TEMPLATES")


def _grouping_result() -> ExtractionResult:
    return ExtractionResult(
        item_id="_report_llm_call",
        title="Groups",
        custom_fields={
            "groups": [
                {
                    "theme": "IVF & Reproductive Medicine",
                    "description": "Advancements in IVF treatment.",
                    "entry_ids": ["entry-001"],
                },
                {
                    "theme": "Neuroplasticity & Brain Development",
                    "description": "Brain plasticity across development.",
                    "entry_ids": ["entry-002"],
                },
            ],
        },
    )


def _summary_result() -> ExtractionResult:
    return ExtractionResult(
        item_id="_report_llm_call",
        title="Executive Summary",
        custom_fields={
            "executive_summary": (
                "This briefing covers two key themes. IVF treatment continues to "
                "advance with time-lapse imaging improving outcomes."
            ),
        },
    )


@pytest.fixture
def sample_entries() -> list[dict[str, Any]]:
    return [
        {
            "entry_id": "entry-001",
            "title": "Improved IVF outcomes with time-lapse imaging",
            "language": "en",
            "summary": "Time-lapse imaging improves live birth rates in IVF.",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/12345678/",
            "source_type": "api",
            "source_platform": "pubmed",
            "relevance_score": 92.0,
            "tags": '["IVF", "embryo"]',
            "tier": "01-Raw",
            "collected_at": fresh_iso(89),
        },
        {
            "entry_id": "entry-002",
            "title": "Neuroplasticity in early childhood development",
            "language": "en",
            "summary": "Early childhood experiences shape brain plasticity.",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/87654321/",
            "source_type": "rss",
            "source_platform": "feed",
            "relevance_score": 78.0,
            "tags": '["neuroplasticity", "development"]',
            "tier": "01-Raw",
            "collected_at": fresh_iso(88),
        },
    ]


class TestProductTemplateHtmlKeepsStructure:
    """End-to-end: a gated product rendered as ``:html`` keeps its skeleton."""

    def test_enterprise_briefing_html_has_head_title_and_headings(
        self, sample_entries: list[dict[str, Any]]
    ) -> None:
        mock_extract = MagicMock(side_effect=[_grouping_result(), _summary_result()])

        with (
            patch("autoinfo.output.KBStore") as mock_kb_cls,
            patch.object(LLMExtractor, "extract", mock_extract),
            patch(
                "autoinfo.output._call_llm_for_report_synthesis",
                return_value="",
            ),
        ):
            mock_store = MagicMock()
            mock_store.list_entries.return_value = sample_entries
            mock_kb_cls.return_value = mock_store

            result = generate_report(
                domain="medical-research",
                format="html",
                report_type="standard",
                product_template=_registry_template("enterprise-briefing"),
            )

        assert isinstance(result, str)
        assert "<head>" in result
        title = re.search(r"<title>(.*?)</title>", result, re.S)
        assert title is not None and title.group(1).strip()
        assert len(re.findall(r"<h[1-6][ >]", result)) >= 3
