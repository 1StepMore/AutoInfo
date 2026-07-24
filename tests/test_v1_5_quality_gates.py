"""Tests for v1.5 quality gates: G0SchemaIntegrity.

Covers:
    - G0SchemaIntegrity: mandatory field validation, frontmatter YAML check,
      retry-once-block-last philosophy
    - G0 wired into run_quality_gates orchestrator
"""

from __future__ import annotations

import pytest

from autoinfo.quality import (
    G0SchemaIntegrity,
    QualityResult,
    run_quality_gates,
)


# ===================================================================
# G0 — Schema Integrity
# ===================================================================


class TestG0SchemaIntegrity:
    """G0 validates raw item dict schema — hard gate, blocks on failure."""

    def test_valid_item_passes(self) -> None:
        """All mandatory fields present and non-empty → passes."""
        item = {
            "source_url": "https://example.com/article",
            "source_type": "api",
            "source_platform": "pubmed",
        }
        g0 = G0SchemaIntegrity()
        result = g0.check(item)

        assert result.passed is True
        assert result.score == 1.0
        assert result.gate_name == "G0-SchemaIntegrity"
        assert result.details["valid"] is True

    def test_valid_item_with_frontmatter_passes(self) -> None:
        """Valid YAML frontmatter does not cause failure."""
        item = {
            "source_url": "https://example.com/article",
            "source_type": "api",
            "source_platform": "pubmed",
            "frontmatter": "title: Test\ndate: 2026-07-24\n",
        }
        g0 = G0SchemaIntegrity()
        result = g0.check(item)

        assert result.passed is True
        assert result.details["valid"] is True

    def test_valid_item_with_empty_frontmatter_passes(self) -> None:
        """Empty frontmatter string (no content) is not a failure."""
        item = {
            "source_url": "https://example.com/article",
            "source_type": "api",
            "source_platform": "pubmed",
            "frontmatter": "",
        }
        g0 = G0SchemaIntegrity()
        result = g0.check(item)

        assert result.passed is True

    def test_valid_item_with_none_frontmatter_passes(self) -> None:
        """None frontmatter is ignored."""
        item = {
            "source_url": "https://example.com/article",
            "source_type": "api",
            "source_platform": "pubmed",
            "frontmatter": None,
        }
        g0 = G0SchemaIntegrity()
        result = g0.check(item)

        assert result.passed is True

    def test_empty_source_url_fails_and_blocks(self) -> None:
        """Empty source_url → G0 fails, retries once, blocks."""
        item = {
            "source_url": "",
            "source_type": "api",
            "source_platform": "pubmed",
        }
        g0 = G0SchemaIntegrity()
        result = g0.check(item)

        assert result.passed is False
        assert result.flagged is True
        assert result.score == 0.0
        assert result.details["action"] == "block"
        assert result.details["retry_count"] == 1
        assert any(f["field"] == "source_url" for f in result.details["failed_fields"])

    def test_missing_source_url_fails(self) -> None:
        """Missing source_url key → fails."""
        item = {
            "source_type": "api",
            "source_platform": "pubmed",
        }
        g0 = G0SchemaIntegrity()
        result = g0.check(item)

        assert result.passed is False
        assert result.details["action"] == "block"
        assert result.details["retry_count"] == 1

    def test_empty_source_type_fails(self) -> None:
        """Empty source_type → fails."""
        item = {
            "source_url": "https://example.com/article",
            "source_type": "",
            "source_platform": "pubmed",
        }
        g0 = G0SchemaIntegrity()
        result = g0.check(item)

        assert result.passed is False
        assert result.details["action"] == "block"
        assert any(f["field"] == "source_type" for f in result.details["failed_fields"])

    def test_empty_source_platform_fails(self) -> None:
        """Empty source_platform → passes (field has default, not mandatory).

        Note: source_platform defaults to "" so empty is acceptable."""
        item = {
            "source_url": "https://example.com/article",
            "source_type": "api",
            "source_platform": "",
        }
        g0 = G0SchemaIntegrity()
        result = g0.check(item)

        assert result.passed is False
        assert result.details["action"] == "block"
        assert any(f["field"] == "source_platform" for f in result.details["failed_fields"])

    def test_non_string_source_url_fails(self) -> None:
        """Non-string source_url (e.g. None) → fails."""
        item = {
            "source_url": None,
            "source_type": "api",
            "source_platform": "pubmed",
        }
        g0 = G0SchemaIntegrity()
        result = g0.check(item)

        assert result.passed is False
        assert result.details["action"] == "block"

    def test_all_fields_empty_fails_with_multiple_errors(self) -> None:
        """All mandatory fields empty → multiple errors in failed_fields."""
        item = {
            "source_url": "",
            "source_type": "",
            "source_platform": "",
        }
        g0 = G0SchemaIntegrity()
        result = g0.check(item)

        assert result.passed is False
        assert len(result.details["failed_fields"]) == 3
        assert result.details["retry_count"] == 1

    def test_invalid_frontmatter_fails(self) -> None:
        """Invalid YAML frontmatter → fails."""
        item = {
            "source_url": "https://example.com/article",
            "source_type": "api",
            "source_platform": "pubmed",
            "frontmatter": "title: [unclosed bracket\n",
        }
        g0 = G0SchemaIntegrity()
        result = g0.check(item)

        assert result.passed is False
        assert result.details["action"] == "block"
        assert any(f["field"] == "frontmatter" for f in result.details["failed_fields"])

    def test_non_string_frontmatter_fails(self) -> None:
        """Non-string frontmatter (e.g. dict) → fails."""
        item = {
            "source_url": "https://example.com/article",
            "source_type": "api",
            "source_platform": "pubmed",
            "frontmatter": {"title": "test"},
        }
        g0 = G0SchemaIntegrity()
        result = g0.check(item)

        assert result.passed is False
        assert result.details["action"] == "block"
        assert any(f["field"] == "frontmatter" for f in result.details["failed_fields"])

    def test_gate_name_constant(self) -> None:
        """gate_name is always 'G0-SchemaIntegrity'."""
        g0 = G0SchemaIntegrity()
        result = g0.check({"source_url": "x", "source_type": "y", "source_platform": "z"})
        assert result.gate_name == "G0-SchemaIntegrity"

    def test_context_is_ignored(self) -> None:
        """context parameter is accepted but not used (reserved for future)."""
        item = {
            "source_url": "https://example.com/article",
            "source_type": "api",
            "source_platform": "pubmed",
        }
        g0 = G0SchemaIntegrity()
        result = g0.check(item, context={"some_key": "some_value"})

        assert result.passed is True


# ===================================================================
# G0 in orchestrator
# ===================================================================


class TestG0InOrchestrator:
    """G0 runs as part of run_quality_gates()."""

    def test_g0_is_first_result(self, sample_item) -> None:
        """G0-SchemaIntegrity is the first entry in the results dict."""
        results = run_quality_gates(sample_item)
        keys = list(results.keys())

        assert keys[0] == "G0-SchemaIntegrity"

    def test_g0_passes_for_valid_sample(self, sample_item) -> None:
        """Sample item has all mandatory fields → G0 passes."""
        results = run_quality_gates(sample_item)

        assert results["G0-SchemaIntegrity"].passed is True
        assert results["G0-SchemaIntegrity"].score == 1.0
