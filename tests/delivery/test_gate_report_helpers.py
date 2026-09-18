"""Tests for autoinfo.delivery.gate_report helper functions.

Covers the structural parsing / detection helpers that adapt an artifact
file into the ``product_output`` dict quality.py's D1-D3 gates expect:

- ``_is_metadata_json`` — run/coverage JSONs are not report products (#169)
- ``_parse_json_payload`` — JSON + JSONL, malformed input toleration
- ``_parse_frontmatter`` — YAML frontmatter extraction
- ``_json_entries`` — structured source-entry extraction
- ``_is_empty_placeholder`` — empty-state placeholders are not content (#172)
- ``_detect_product_type`` — filename keywords + column heading upgrade (#172)
- ``_sections_from_headings`` — alias / slide / numbered-entry / column
  heading matching, HTML conversion, placeholder emptiness
- ``_section_value`` — top-level + llm_synthesis JSON section lookup
- ``_apply_format_sections`` — per-product-type required-section mapping (#172)

All tests are hermetic: real files in tmp_path, no LLM, no network.
"""

from __future__ import annotations

import json
from pathlib import Path

from autoinfo.delivery.gate_report import (
    _apply_format_sections,
    _detect_product_type,
    _is_empty_placeholder,
    _is_metadata_json,
    _json_entries,
    _parse_frontmatter,
    _parse_json_payload,
    _section_value,
    _sections_from_headings,
)

# ---------------------------------------------------------------------------
# _is_metadata_json
# ---------------------------------------------------------------------------


class TestIsMetadataJson:
    def test_metadata_names_are_not_products(self, tmp_path: Path) -> None:
        for name in ("scenarios.json", "manifest.json"):
            p = tmp_path / name
            p.write_text("{}", encoding="utf-8")
            assert _is_metadata_json(p, {}) is True, name

    def test_metadata_prefix_and_suffix_names(self, tmp_path: Path) -> None:
        cov = tmp_path / "coverage-20260904.json"
        cov.write_text("{}", encoding="utf-8")
        runs = tmp_path / "digest_runs.json"
        runs.write_text("{}", encoding="utf-8")
        assert _is_metadata_json(cov, {}) is True
        assert _is_metadata_json(runs, {}) is True

    def test_dict_without_report_markers_is_metadata(self, tmp_path: Path) -> None:
        p = tmp_path / "anything.json"
        p.write_text("{}", encoding="utf-8")
        assert _is_metadata_json(p, {"status": "ok", "count": 3}) is True

    def test_dict_with_report_markers_is_a_product(self, tmp_path: Path) -> None:
        p = tmp_path / "anything.json"
        p.write_text("{}", encoding="utf-8")
        payload = {"title": "Weekly digest", "entries": []}
        assert _is_metadata_json(p, payload) is False

    def test_non_dict_payload_defaults_to_product(self, tmp_path: Path) -> None:
        p = tmp_path / "list.json"
        p.write_text("[]", encoding="utf-8")
        # A list payload is not decided by filename alone here -> not metadata.
        assert _is_metadata_json(p, [{"title": "x"}]) is False


# ---------------------------------------------------------------------------
# _parse_json_payload
# ---------------------------------------------------------------------------


class TestParseJsonPayload:
    def test_valid_json_dict(self, tmp_path: Path) -> None:
        p = tmp_path / "a.json"
        p.write_text(json.dumps({"title": "t"}), encoding="utf-8")
        assert _parse_json_payload(p) == {"title": "t"}

    def test_malformed_json_returns_none(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.json"
        p.write_text("{not json", encoding="utf-8")
        assert _parse_json_payload(p) is None

    def test_unreadable_file_returns_none(self, tmp_path: Path) -> None:
        # A directory with a .json suffix: read_text raises -> None.
        d = tmp_path / "dir.json"
        d.mkdir()
        assert _parse_json_payload(d) is None

    def test_jsonl_lines_are_parsed_individually(self, tmp_path: Path) -> None:
        p = tmp_path / "a.jsonl"
        p.write_text(
            json.dumps({"title": "one"})
            + "\n"
            + "\n"  # blank lines are skipped
            + json.dumps({"title": "two"})
            + "\n"
            + "{broken line}\n",
            encoding="utf-8",
        )
        parsed = _parse_json_payload(p)
        assert isinstance(parsed, list)
        assert [e["title"] for e in parsed] == ["one", "two"]

    def test_jsonl_only_blank_or_broken_lines_returns_none(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.jsonl"
        p.write_text("\n   \n{broken}\n", encoding="utf-8")
        assert _parse_json_payload(p) is None

    def test_jsonl_single_valid_line_returns_list(self, tmp_path: Path) -> None:
        p = tmp_path / "one.jsonl"
        p.write_text(json.dumps({"title": "only"}), encoding="utf-8")
        assert _parse_json_payload(p) == [{"title": "only"}]


# ---------------------------------------------------------------------------
# _parse_frontmatter
# ---------------------------------------------------------------------------


class TestParseFrontmatter:
    def test_extracts_yaml_frontmatter(self, tmp_path: Path) -> None:
        p = tmp_path / "a.md"
        p.write_text(
            "---\ntitle: My report\ntags:\n  - ai\n  - llm\n---\n\n# Body\n",
            encoding="utf-8",
        )
        fm = _parse_frontmatter(p)
        assert fm == {"title": "My report", "tags": ["ai", "llm"]}

    def test_no_frontmatter_returns_empty(self, tmp_path: Path) -> None:
        p = tmp_path / "plain.md"
        p.write_text("# Just a heading\n\nBody.\n", encoding="utf-8")
        assert _parse_frontmatter(p) == {}

    def test_unterminated_frontmatter_returns_empty(self, tmp_path: Path) -> None:
        p = tmp_path / "open.md"
        p.write_text("---\ntitle: never closed\n", encoding="utf-8")
        assert _parse_frontmatter(p) == {}

    def test_non_dict_frontmatter_returns_empty(self, tmp_path: Path) -> None:
        p = tmp_path / "list.md"
        p.write_text("---\n- a\n- b\n---\nbody", encoding="utf-8")
        assert _parse_frontmatter(p) == {}

    def test_malformed_yaml_returns_empty(self, tmp_path: Path) -> None:
        p = tmp_path / "broken.md"
        p.write_text("---\n: :\n  - [\n---\nbody", encoding="utf-8")
        assert _parse_frontmatter(p) == {}

    def test_unreadable_file_returns_empty(self, tmp_path: Path) -> None:
        d = tmp_path / "dir.md"
        d.mkdir()
        assert _parse_frontmatter(d) == {}


# ---------------------------------------------------------------------------
# _json_entries
# ---------------------------------------------------------------------------


def _entry(title: str = "e1", **extra: str) -> dict:
    return {"title": title, "source_url": "https://x.test/a", **extra}


class TestJsonEntries:
    def test_list_payload_filters_entry_dicts(self) -> None:
        parsed = [_entry("a"), {"no": "entry keys"}, _entry("b")]
        found = _json_entries(parsed)
        assert [e["title"] for e in found] == ["a", "b"]

    def test_entries_key_is_extracted(self) -> None:
        parsed = {"entries": [_entry("a"), {"not": "an entry"}]}
        assert [e["title"] for e in _json_entries(parsed)] == ["a"]

    def test_alternative_container_keys_are_extracted(self) -> None:
        for key in ("items", "results", "articles", "payload"):
            parsed = {key: [_entry(f"via-{key}")]}
            found = _json_entries(parsed)
            assert len(found) == 1 and found[0]["title"] == f"via-{key}", key

    def test_top_level_entry_dict_is_returned(self) -> None:
        parsed = _entry("top")
        assert _json_entries(parsed) == [parsed]

    def test_no_entries_returns_empty_list(self) -> None:
        assert _json_entries({"unrelated": True}) == []
        assert _json_entries("scalar") == []
        assert _json_entries(None) == []

    def test_list_of_non_dicts_returns_empty_list(self) -> None:
        assert _json_entries(["a", 1, None]) == []


# ---------------------------------------------------------------------------
# _is_empty_placeholder
# ---------------------------------------------------------------------------


class TestIsEmptyPlaceholder:
    def test_placeholder_templates_are_empty(self) -> None:
        assert _is_empty_placeholder("_No objectives defined._")
        assert _is_empty_placeholder("_No exercises provided._")
        assert _is_empty_placeholder("  _No entries found for this period._\n")

    def test_real_content_is_not_a_placeholder(self) -> None:
        assert not _is_empty_placeholder("AI adoption accelerates.")
        assert not _is_empty_placeholder("- LLM costs dropped 40%.")

    def test_blank_string_is_not_a_placeholder(self) -> None:
        assert not _is_empty_placeholder("")
        assert not _is_empty_placeholder("   \n")


# ---------------------------------------------------------------------------
# _detect_product_type
# ---------------------------------------------------------------------------


class TestDetectProductType:
    def test_filename_keywords_map_to_types(self, tmp_path: Path) -> None:
        cases = {
            "presentation-weekly.pptx.md": "presentation",
            "tutorial-python.md": "tutorial",
            "magazine-2026-09.md": "magazine",
            "digest-2026-09-04.md": "digest",
            "column-health.md": "column",
            "enterprise-briefing.md": "enterprise_briefing",
            "premium-briefing.md": "premium_briefing",
            "magazine-digest-09.md": "magazine_digest",
        }
        for name, expected in cases.items():
            p = tmp_path / name
            assert _detect_product_type(p) == expected, name

    def test_nested_path_keywords_still_match(self) -> None:
        p = Path("outputs/med/reports/digest-2026.md")
        assert _detect_product_type(p) == "digest"

    def test_report_named_file_with_column_headings_upgrades(self, tmp_path: Path) -> None:
        p = tmp_path / "report-2026.md"
        body = "## The Big Idea\n\nBold claim.\n"
        assert _detect_product_type(p, body) == "column"

    def test_plain_report_name_defaults_to_report(self, tmp_path: Path) -> None:
        p = tmp_path / "report-2026.md"
        assert _detect_product_type(p, "## Some section\n") == "report"

    def test_case_insensitive(self, tmp_path: Path) -> None:
        p = tmp_path / "Weekly-DIGEST.md"
        assert _detect_product_type(p) == "digest"


# ---------------------------------------------------------------------------
# _sections_from_headings
# ---------------------------------------------------------------------------


class TestSectionsFromHeadings:
    def test_report_headings_via_aliases(self) -> None:
        md = (
            "# Weekly AI Digest\n\n"
            "## Executive Summary\n\nAI adoption accelerates.\n\n"
            "## Key Findings\n\n- LLM costs dropped 40%.\n\n"
            "## Recommendations\n\n- Adopt agent workflows.\n"
        )
        found = _sections_from_headings(md)
        assert found["summary"] == "AI adoption accelerates."
        assert found["key_findings"] == "- LLM costs dropped 40%."
        assert found["recommendations"] == "- Adopt agent workflows."

    def test_alias_variants_and_alternate_headings(self) -> None:
        md = "## Executive Overview\n\nBody text.\n\n## Next Steps\n\nDo things.\n"
        found = _sections_from_headings(md)
        assert found["summary"] == "Body text."
        assert found["recommendations"] == "Do things."
        # key_findings not present at all.
        assert "key_findings" not in found

    def test_html_headings_are_converted_with_content_kept(self) -> None:
        html = (
            "<h1>Report</h1>"
            "<h2>Key Findings</h2><p>Great <b>content</b> here.</p>"
            "<h2>Recommendations</h2><p>Do X.</p>"
        )
        found = _sections_from_headings(html)
        assert "Great" in found["key_findings"]
        assert "content" in found["key_findings"]
        assert "here." in found["key_findings"]
        assert found["recommendations"] == "Do X."

    def test_slide_headings_map_to_key_findings(self) -> None:
        md = (
            "# Slide 1: Overview\n\nDeck intro points.\n\n# Slide 2: Evidence\n\nSupporting data.\n"
        )
        found = _sections_from_headings(md)
        assert "Deck intro points." in found["key_findings"]
        assert "Supporting data." in found["key_findings"]

    def test_numbered_entry_headings_count_as_summary(self) -> None:
        md = "# 1. First entry\n\nBody one.\n\n# 2) Second entry\n\nBody two.\n"
        found = _sections_from_headings(md, "digest")
        assert found["summary"] == "present"

    def test_placeholder_section_is_kept_empty(self) -> None:
        md = "## Learning Objectives\n\n_No objectives defined._\n"
        found = _sections_from_headings(md, "tutorial")
        assert found["key_findings"] == ""

    def test_horizontal_rules_do_not_mask_placeholder(self) -> None:
        md = "## Entries\n\n---\n\n_No entries found for this period._\n\n---\n"
        found = _sections_from_headings(md, "digest")
        assert found["summary"] == ""

    def test_column_product_uses_first_content_heading(self) -> None:
        md = "## The Big Idea\n\nBold claim.\n\n## Deep Dive\n\nDetails.\n"
        found = _sections_from_headings(md, "column")
        assert found["key_findings"] == "Bold claim."

    def test_magazine_product_uses_first_content_heading(self) -> None:
        md = "## Fresh Angle\n\nStory body.\n"
        found = _sections_from_headings(md, "magazine")
        assert found["key_findings"] == "Story body."

    def test_empty_text_returns_empty_map(self) -> None:
        assert _sections_from_headings("") == {}
        assert _sections_from_headings("No headings at all.\n") == {}


# ---------------------------------------------------------------------------
# _section_value
# ---------------------------------------------------------------------------


class TestSectionValue:
    def test_top_level_value_wins(self) -> None:
        parsed = {"summary": "top", "llm_synthesis": {"summary": "nested"}}
        assert _section_value(parsed, ("summary",)) == "top"

    def test_llm_synthesis_fallback(self) -> None:
        parsed = {"llm_synthesis": {"executive_summary": "nested"}}
        assert _section_value(parsed, ("summary", "executive_summary")) == "nested"

    def test_first_non_empty_alias_wins(self) -> None:
        parsed = {"next_steps": "steps"}
        assert _section_value(parsed, ("recommendations", "next_steps")) == "steps"

    def test_empty_values_are_skipped(self) -> None:
        parsed = {"summary": "", "llm_synthesis": {"summary": None}}
        assert _section_value(parsed, ("summary",)) is None

    def test_non_dict_llm_synthesis_is_ignored(self) -> None:
        parsed = {"llm_synthesis": "not a dict"}
        assert _section_value(parsed, ("summary",)) is None


# ---------------------------------------------------------------------------
# _apply_format_sections
# ---------------------------------------------------------------------------


class TestApplyFormatSections:
    def test_report_keeps_all_detected_sections(self) -> None:
        sections = {
            "key_findings": "kf",
            "summary": "s",
            "recommendations": "r",
        }
        assert _apply_format_sections(sections, "report") == sections

    def test_presentation_non_required_sections_get_marker(self) -> None:
        sections = {"key_findings": "slide content"}
        mapped = _apply_format_sections(sections, "presentation")
        assert mapped["key_findings"] == "slide content"
        assert mapped["summary"] == "present"
        assert mapped["recommendations"] == "present"

    def test_digest_required_summary_stays_empty_when_missing(self) -> None:
        mapped = _apply_format_sections({}, "digest")
        assert mapped["summary"] == ""
        assert mapped["key_findings"] == "present"
        assert mapped["recommendations"] == "present"

    def test_tutorial_required_sections_keep_detected_values(self) -> None:
        sections = {"key_findings": ""}
        mapped = _apply_format_sections(sections, "tutorial")
        assert mapped["key_findings"] == ""
        assert mapped["recommendations"] == ""
        assert mapped["summary"] == "present"

    def test_unknown_type_defaults_to_report_rules(self) -> None:
        mapped = _apply_format_sections({}, "mystery-type")
        assert mapped == {"key_findings": "", "summary": "", "recommendations": ""}
