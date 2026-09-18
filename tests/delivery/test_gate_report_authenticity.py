"""Tests for autoinfo.delivery.gate_report.check_authenticity.

The authenticity pre-check is field-presence only (Oracle R3):

- md/html text products pass as N/A (frontmatter reported informationally)
- JSON/JSONL payloads: every structured source entry must carry non-empty
  ``source_url`` (no example.com placeholders), ``source_type`` and
  ``source_platform``
- agent JSON-LD payloads (@type: KnowledgeDigest/KnowledgePresentation/
  KnowledgeTutorial) follow the agent-native provenance contract (#217)
- payloads without structured entries have nothing to verify and pass
"""

from __future__ import annotations

import json
from pathlib import Path

from autoinfo.delivery.gate_report import check_authenticity

# ---------------------------------------------------------------------------
# Text products (md/html)
# ---------------------------------------------------------------------------


class TestTextProducts:
    def test_markdown_passes_as_not_applicable(self, tmp_path: Path) -> None:
        p = tmp_path / "digest.md"
        p.write_text("# Digest\n\nBody.\n", encoding="utf-8")
        result = check_authenticity(p)
        assert result["authenticity"] == "pass"
        assert "N/A" in result["reason"]
        assert "text content file" in result["reason"]

    def test_markdown_frontmatter_reported_informationally(self, tmp_path: Path) -> None:
        p = tmp_path / "report.md"
        p.write_text(
            "---\ntitle: Report\ndomain: medical-research\n---\n\nBody.\n",
            encoding="utf-8",
        )
        result = check_authenticity(p)
        assert result["authenticity"] == "pass"
        assert "frontmatter fields:" in result["reason"]
        assert "domain" in result["reason"] and "title" in result["reason"]

    def test_html_passes_as_not_applicable(self, tmp_path: Path) -> None:
        p = tmp_path / "report.html"
        p.write_text("<h1>Report</h1>", encoding="utf-8")
        result = check_authenticity(p)
        assert result["authenticity"] == "pass"


# ---------------------------------------------------------------------------
# Structured JSON payloads (non-agent)
# ---------------------------------------------------------------------------


def _json_file(tmp_path: Path, name: str, payload: object) -> Path:
    p = tmp_path / name
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def _complete_entry(title: str = "e1") -> dict:
    return {
        "title": title,
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/42",
        "source_type": "api",
        "source_platform": "pubmed",
    }


class TestStructuredJsonPayloads:
    def test_payload_without_entries_passes(self, tmp_path: Path) -> None:
        p = _json_file(tmp_path, "x.json", {"note": "nothing structured"})
        result = check_authenticity(p)
        assert result["authenticity"] == "pass"
        assert "nothing to verify" in result["reason"]

    def test_complete_entries_pass_with_count(self, tmp_path: Path) -> None:
        payload = {"entries": [_complete_entry("a"), _complete_entry("b")]}
        result = check_authenticity(_json_file(tmp_path, "ok.json", payload))
        assert result["authenticity"] == "pass"
        assert "2 structured entries" in result["reason"]

    def test_single_entry_singular_wording(self, tmp_path: Path) -> None:
        result = check_authenticity(_json_file(tmp_path, "one.json", [_complete_entry()]))
        assert result["authenticity"] == "pass"
        assert "1 structured entry with complete source fields" in result["reason"]

    def test_missing_source_url_fails(self, tmp_path: Path) -> None:
        entry = _complete_entry()
        entry["source_url"] = "  "
        result = check_authenticity(_json_file(tmp_path, "bad.json", [entry]))
        assert result["authenticity"] == "fail"
        assert "entry[0] missing source_url" in result["reason"]

    def test_non_string_source_url_fails(self, tmp_path: Path) -> None:
        entry = _complete_entry()
        entry["source_url"] = 12345
        result = check_authenticity(_json_file(tmp_path, "bad.json", [entry]))
        assert result["authenticity"] == "fail"
        assert "missing source_url" in result["reason"]

    def test_example_com_placeholder_fails(self, tmp_path: Path) -> None:
        entry = _complete_entry()
        entry["source_url"] = "https://example.com/article"
        result = check_authenticity(_json_file(tmp_path, "placeholder.json", [entry]))
        assert result["authenticity"] == "fail"
        assert "placeholder source_url" in result["reason"]

    def test_missing_source_type_and_platform_both_reported(self, tmp_path: Path) -> None:
        entry = {"title": "x", "source_url": "https://real.test/a"}
        result = check_authenticity(_json_file(tmp_path, "bad.json", [entry]))
        assert result["authenticity"] == "fail"
        assert "entry[0] missing source_type" in result["reason"]
        assert "entry[0] missing source_platform" in result["reason"]


# ---------------------------------------------------------------------------
# Agent JSON-LD payloads (#217)
# ---------------------------------------------------------------------------


class TestAgentJsonLd:
    def test_agent_entry_requires_source_platform_not_source_type(self, tmp_path: Path) -> None:
        entry = {
            "title": "digest entry",
            "source_url": "https://real.test/a",
            "source_platform": "pubmed",
        }
        payload = {"@type": "KnowledgeDigest", "title": "Digest", "entries": [entry]}
        result = check_authenticity(_json_file(tmp_path, "agent.json", payload))
        assert result["authenticity"] == "pass"

    def test_agent_entry_missing_platform_fails(self, tmp_path: Path) -> None:
        entry = {"title": "digest entry", "source_url": "https://real.test/a"}
        payload = {"@type": "KnowledgeDigest", "title": "Digest", "entries": [entry]}
        result = check_authenticity(_json_file(tmp_path, "agent.json", payload))
        assert result["authenticity"] == "fail"
        assert "entry[0] missing source_platform" in result["reason"]
        assert "source_type" not in result["reason"]

    def test_presentation_with_valid_sources_passes(self, tmp_path: Path) -> None:
        payload = {
            "@type": "KnowledgePresentation",
            "title": "Quarterly deck",
            "sources": [
                {"source_url": "https://real.test/1"},
                {"source_url": "https://real.test/2"},
            ],
        }
        result = check_authenticity(_json_file(tmp_path, "deck.json", payload))
        assert result["authenticity"] == "pass"

    def test_presentation_source_missing_url_fails(self, tmp_path: Path) -> None:
        payload = {
            "@type": "KnowledgePresentation",
            "title": "Quarterly deck",
            "sources": [{"source_url": ""}, "not-a-dict"],
        }
        result = check_authenticity(_json_file(tmp_path, "deck.json", payload))
        assert result["authenticity"] == "fail"
        assert "sources[0] missing source_url" in result["reason"]

    def test_presentation_without_sources_passes(self, tmp_path: Path) -> None:
        payload = {"@type": "KnowledgePresentation", "title": "Quarterly deck"}
        result = check_authenticity(_json_file(tmp_path, "deck.json", payload))
        assert result["authenticity"] == "pass"
        assert "presentation has no provenance sources" in result["reason"]

    def test_tutorial_missing_url_and_platform_fails(self, tmp_path: Path) -> None:
        payload = {
            "@type": "KnowledgeTutorial",
            "title": "How-to",
            "source_entries": [{"title": "step source"}],
        }
        result = check_authenticity(_json_file(tmp_path, "tutorial.json", payload))
        assert result["authenticity"] == "fail"
        assert "source_entries[0] missing source_url" in result["reason"]
        assert "source_entries[0] missing source_platform" in result["reason"]

    def test_tutorial_without_source_entries_passes(self, tmp_path: Path) -> None:
        payload = {"@type": "KnowledgeTutorial", "title": "How-to", "steps": ["do thing"]}
        result = check_authenticity(_json_file(tmp_path, "tutorial.json", payload))
        assert result["authenticity"] == "pass"
        assert "tutorial has no provenance source_entries" in result["reason"]

    def test_tutorial_non_dict_source_entries_are_skipped(self, tmp_path: Path) -> None:
        payload = {
            "@type": "KnowledgeTutorial",
            "title": "How-to",
            "source_entries": ["not-a-dict", {"title": "step source"}],
        }
        result = check_authenticity(_json_file(tmp_path, "tutorial.json", payload))
        assert result["authenticity"] == "fail"
        assert "source_entries[1] missing source_url" in result["reason"]
        assert "source_entries[1] missing source_platform" in result["reason"]

    def test_tutorial_complete_source_entries_pass(self, tmp_path: Path) -> None:
        payload = {
            "@type": "KnowledgeTutorial",
            "title": "How-to",
            "source_entries": [{"source_url": "https://real.test/a", "source_platform": "web"}],
        }
        result = check_authenticity(_json_file(tmp_path, "tutorial.json", payload))
        assert result["authenticity"] == "pass"

    def test_more_than_six_problems_are_truncated(self, tmp_path: Path) -> None:
        entries = [
            {
                "title": f"e{i}",
                "source_type": "api",
                "source_platform": "pubmed",
            }
            for i in range(8)
        ]
        result = check_authenticity(_json_file(tmp_path, "many.json", entries))
        assert result["authenticity"] == "fail"
        assert result["reason"].endswith(" ...")
        assert result["reason"].count("missing source_url") == 6
