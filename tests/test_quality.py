"""Tests for quality gates G1-G3.

Covers:
    - G1SourceAuthority: tier-based advisory warnings
    - G2Dedup: URL, PMID, DOI duplicate detection
    - G3RelevanceScoring: keyword overlap scoring + threshold hiding
    - run_quality_gates: orchestrator runs all three gates
"""

from __future__ import annotations

import pytest

from autoinfo.models import Item, KBEntry
from autoinfo.quality import (
    G1SourceAuthority,
    G2Dedup,
    G3RelevanceScoring,
    QualityResult,
    run_quality_gates,
)


# ===================================================================
# G1 — Source Authority
# ===================================================================


class TestG1SourceAuthority:
    """G1 is advisory — always passes, but flags low-tier sources."""

    def test_tier_1_passes_unflagged(self, sample_item: Item) -> None:
        g1 = G1SourceAuthority()
        result = g1.check(sample_item)

        assert result.passed is True
        assert result.flagged is False
        assert result.gate_name == "G1-SourceAuthority"
        assert "warning" not in result.details

    def test_tier_2_passes_unflagged(self, sample_item: Item) -> None:
        item = Item(**{**sample_item.to_dict(), "quality_tier": 2})
        g1 = G1SourceAuthority()
        result = g1.check(item)

        assert result.passed is True
        assert result.flagged is False
        assert "warning" not in result.details

    def test_tier_3_flagged_advisory(self, sample_item: Item) -> None:
        item = Item(**{**sample_item.to_dict(), "quality_tier": 3})
        g1 = G1SourceAuthority()
        result = g1.check(item)

        assert result.passed is True  # advisory only
        assert result.flagged is True
        assert result.details["warning"] == "low quality source"

    def test_tier_4_flagged_advisory(self, sample_item: Item) -> None:
        item = Item(**{**sample_item.to_dict(), "quality_tier": 4})
        g1 = G1SourceAuthority()
        result = g1.check(item)

        assert result.passed is True
        assert result.flagged is True
        assert result.details["warning"] == "low quality source"

    def test_source_config_overrides_item_tier(self, sample_item: Item) -> None:
        """source_config quality_tier takes precedence over item.quality_tier."""
        item = Item(**{**sample_item.to_dict(), "quality_tier": 1})
        source_config = {"quality_tier": 3, "name": "community-forum"}
        g1 = G1SourceAuthority()
        result = g1.check(item, source_config)

        assert result.flagged is True
        assert result.details["warning"] == "low quality source"

    def test_negative_tier_handling(self, sample_item: Item) -> None:
        """Tier 0 or negative should be treated conservatively (not flagged)."""
        item = Item(**{**sample_item.to_dict(), "quality_tier": 0})
        g1 = G1SourceAuthority()
        result = g1.check(item)

        assert result.passed is True
        assert result.flagged is False  # tier 0 <= 2

    def test_score_reflects_tier(self, sample_item: Item) -> None:
        item = Item(**{**sample_item.to_dict(), "quality_tier": 3})
        g1 = G1SourceAuthority()
        result = g1.check(item)

        assert result.score == 3.0  # score = tier number


# ===================================================================
# G2 — Dedup
# ===================================================================


class TestG2Dedup:
    """G2 detects duplicates by URL, PMID, or DOI."""

    def test_url_duplicate_detected(self, sample_item: Item, sample_kb_entry: KBEntry) -> None:
        existing = [
            KBEntry(**{**sample_kb_entry.to_dict(), "source_url": sample_item.source_url})
        ]
        g2 = G2Dedup()
        result = g2.check(sample_item, existing)

        assert result.passed is False
        assert result.flagged is True
        assert result.details["is_duplicate"] is True
        assert result.details["matched_by"] == "url"

    def test_url_unique_passes(self, sample_item: Item, sample_kb_entry: KBEntry) -> None:
        existing = [
            KBEntry(**{**sample_kb_entry.to_dict(), "source_url": "https://example.com/other"})
        ]
        g2 = G2Dedup()
        result = g2.check(sample_item, existing)

        assert result.passed is True
        assert result.details["is_duplicate"] is False

    def test_pmid_duplicate_detected(self, sample_item: Item, sample_kb_entry: KBEntry) -> None:
        """Use different URLs so URL match doesn't fire before PMID match."""
        item = Item(
            **{
                **sample_item.to_dict(),
                "source_url": "https://example.com/new-item",
                "raw_data": {"pmid": "12345678"},
            }
        )
        existing = [
            KBEntry(
                **{
                    **sample_kb_entry.to_dict(),
                    "source_url": "https://example.com/existing-entry",
                    "custom_fields": {"pmid": "12345678"},
                }
            )
        ]
        g2 = G2Dedup()
        result = g2.check(item, existing)

        assert result.passed is False
        assert result.flagged is True
        assert result.details["is_duplicate"] is True
        assert result.details["matched_by"] == "pmid"

    def test_doi_duplicate_detected(self, sample_item: Item, sample_kb_entry: KBEntry) -> None:
        """Use different URLs so URL match doesn't fire before DOI match."""
        item = Item(
            **{
                **sample_item.to_dict(),
                "source_url": "https://example.com/new-item",
                "raw_data": {"doi": "10.1000/j.jrm.2026.03.004"},
            }
        )
        existing = [
            KBEntry(
                **{
                    **sample_kb_entry.to_dict(),
                    "source_url": "https://example.com/existing-entry",
                    "extracted_fields": {"doi": "10.1000/j.jrm.2026.03.004"},
                }
            )
        ]
        g2 = G2Dedup()
        result = g2.check(item, existing)

        assert result.passed is False
        assert result.flagged is True
        assert result.details["is_duplicate"] is True
        assert result.details["matched_by"] == "doi"

    def test_doi_case_insensitive(self, sample_item: Item, sample_kb_entry: KBEntry) -> None:
        """DOI matching should be case-insensitive."""
        item = Item(
            **{
                **sample_item.to_dict(),
                "source_url": "https://example.com/new-item",
                "raw_data": {"doi": "10.1000/J.JRM.2026.03.004"},
            }
        )
        existing = [
            KBEntry(
                **{
                    **sample_kb_entry.to_dict(),
                    "source_url": "https://example.com/existing-entry",
                    "extracted_fields": {"doi": "10.1000/j.jrm.2026.03.004"},
                }
            )
        ]
        g2 = G2Dedup()
        result = g2.check(item, existing)

        assert result.passed is False
        assert result.details["matched_by"] == "doi"

    def test_empty_existing_entries(self, sample_item: Item) -> None:
        g2 = G2Dedup()
        result = g2.check(sample_item, [])

        assert result.passed is True
        assert result.details["is_duplicate"] is False

    def test_no_match_returns_correct_details(self, sample_item: Item, sample_kb_entry: KBEntry) -> None:
        existing = [
            KBEntry(**{**sample_kb_entry.to_dict(), "source_url": "https://example.com/other"})
        ]
        g2 = G2Dedup()
        result = g2.check(sample_item, existing)

        assert result.details["matched_by"] is None

    def test_url_match_precedes_pmid(self, sample_item: Item, sample_kb_entry: KBEntry) -> None:
        """URL match should be detected before checking PMID/DOI."""
        item = Item(
            **{
                **sample_item.to_dict(),
                "source_url": "https://example.com/dup",
                "raw_data": {"pmid": "12345678"},
            }
        )
        existing = [
            KBEntry(
                **{
                    **sample_kb_entry.to_dict(),
                    "source_url": "https://example.com/dup",
                    "custom_fields": {"pmid": "12345678"},
                }
            )
        ]
        g2 = G2Dedup()
        result = g2.check(item, existing)

        assert result.details["matched_by"] == "url"
        assert result.passed is False

    def test_different_urls_same_pmid_detected(self, sample_item: Item, sample_kb_entry: KBEntry) -> None:
        """Different URLs with same PMID should be caught by PMID match."""
        item = Item(
            **{
                **sample_item.to_dict(),
                "source_url": "https://example.com/via-pubmed",
                "raw_data": {"pmid": "12345678"},
            }
        )
        existing = [
            KBEntry(
                **{
                    **sample_kb_entry.to_dict(),
                    "source_url": "https://example.com/other-url",
                    "custom_fields": {"pmid": "12345678"},
                }
            )
        ]
        g2 = G2Dedup()
        result = g2.check(item, existing)

        assert result.passed is False
        assert result.details["matched_by"] == "pmid"


# ===================================================================
# G3 — Relevance Scoring
# ===================================================================


class TestG3RelevanceScoring:
    """G3 scores keyword overlap and hides low-relevance items."""

    def test_all_keywords_match_gets_full_score(self, sample_item: Item) -> None:
        g3 = G3RelevanceScoring()
        # The sample_item's title and content mention "IVF" and "embryo"
        result = g3.check(sample_item, topic_keywords=["IVF", "embryo"])

        assert result.passed is True
        assert result.score == 100.0  # both keywords found

    def test_partial_keyword_match(self, sample_item: Item) -> None:
        g3 = G3RelevanceScoring()
        # Only "IVF" appears in the item, "quantum" does not
        result = g3.check(sample_item, topic_keywords=["IVF", "quantum"])

        assert result.score == 50.0  # 1/2 matched = 50

    def test_no_keywords_match_returns_zero(self, sample_item: Item) -> None:
        g3 = G3RelevanceScoring()
        result = g3.check(sample_item, topic_keywords=["quantum", "computing"])

        assert result.score == 0.0
        assert result.flagged is True
        assert result.details["hidden"] is True

    def test_empty_keywords_returns_full_score(self, sample_item: Item) -> None:
        g3 = G3RelevanceScoring()
        result = g3.check(sample_item, topic_keywords=[])

        assert result.score == 100.0
        assert result.passed is True
        assert result.flagged is False

    def test_below_threshold_flagged_hidden(self, sample_item: Item) -> None:
        g3 = G3RelevanceScoring()
        result = g3.check(sample_item, topic_keywords=["quantum"], threshold=30)

        assert result.score == 0.0
        assert result.flagged is True
        assert result.details["hidden"] is True
        assert result.details["reason"] == "below relevance threshold"

    def test_above_threshold_not_hidden(self, sample_item: Item) -> None:
        g3 = G3RelevanceScoring()
        result = g3.check(sample_item, topic_keywords=["IVF"], threshold=30)

        assert result.score == 100.0
        assert result.flagged is False
        assert result.details["hidden"] is False

    def test_score_capped_at_100(self, sample_item: Item) -> None:
        g3 = G3RelevanceScoring()
        # Even if more keywords match than total keywords (shouldn't happen, but guard)
        result = g3.check(sample_item, topic_keywords=["IVF"])

        assert result.score == 100.0  # 1/1 * 100 = 100, capped at 100

    def test_case_insensitive_matching(self, sample_item: Item) -> None:
        """Keyword matching is case-insensitive."""
        g3 = G3RelevanceScoring()
        # "ivf" lowercase should match "IVF" in the title
        result = g3.check(sample_item, topic_keywords=["ivf"])

        assert result.score == 100.0

    def test_content_keyword_match(self, sample_item: Item) -> None:
        """Keywords in the content body should also count."""
        g3 = G3RelevanceScoring()
        # "implantation" isn't in title but appears in content as "implantation" (wait let me check)
        # Actually looking at sample_item content, "implantation" is there in "implantation rate"
        # But the sample_item content uses "implantation" — let me use something I know is there
        # "live birth" appears in the content
        result = g3.check(sample_item, topic_keywords=["live birth"])

        assert result.score == 100.0

    def test_keyword_match_count_in_details(self, sample_item: Item) -> None:
        g3 = G3RelevanceScoring()
        result = g3.check(sample_item, topic_keywords=["IVF", "embryo", "quantum"])

        assert result.details["keyword_matches"] == 2
        assert result.details["total_keywords"] == 3

    def test_custom_threshold(self, sample_item: Item) -> None:
        """Custom threshold values are respected."""
        g3 = G3RelevanceScoring()
        # 1/3 match = round((1/3)*100) = 33
        # With threshold=30: 33 >= 30 → passes (not flagged)
        # With threshold=40: 33 < 40 → flagged + hidden
        result_low = g3.check(sample_item, topic_keywords=["IVF", "quantum", "computing"], threshold=30)
        assert result_low.score == 33.0
        assert result_low.passed is True
        assert result_low.flagged is False  # 33 >= 30

        result_high = g3.check(sample_item, topic_keywords=["IVF", "quantum", "computing"], threshold=40)
        assert result_high.score == 33.0
        assert result_high.passed is False
        assert result_high.flagged is True  # 33 < 40
        assert result_high.details["hidden"] is True


# ===================================================================
# Orchestrator — run_quality_gates
# ===================================================================


class TestRunQualityGates:
    """run_quality_gates() orchestrator runs all three gates."""

    def test_runs_all_three_gates(self, sample_item: Item) -> None:
        context = {
            "source_config": {"quality_tier": 1},
            "existing_entries": [],
            "topic_keywords": ["IVF", "embryo"],
            "threshold": 30,
        }
        results = run_quality_gates(sample_item, context)

        assert "G1-SourceAuthority" in results
        assert "G2-Dedup" in results
        assert "G3-RelevanceScoring" in results
        assert len(results) == 3

    def test_all_quality_result_instances(self, sample_item: Item) -> None:
        results = run_quality_gates(sample_item, {"topic_keywords": ["IVF"]})

        for name, result in results.items():
            assert isinstance(result, QualityResult), f"{name} is not a QualityResult"

    def test_context_defaults_when_missing(self, sample_item: Item) -> None:
        """Orchestrator should not crash when context is empty."""
        results = run_quality_gates(sample_item, {})

        assert len(results) == 3
        # G3 with empty keywords = score 100
        assert results["G3-RelevanceScoring"].score == 100.0

    def test_context_none_defaults(self, sample_item: Item) -> None:
        """Orchestrator should not crash when context is None."""
        results = run_quality_gates(sample_item)

        assert len(results) == 3

    def test_g3_triggers_hidden_in_orchestrator(self, sample_item: Item) -> None:
        """Hidden flag propagates through orchestrated G3."""
        context = {
            "topic_keywords": ["quantum", "computing"],
            "threshold": 30,
        }
        results = run_quality_gates(sample_item, context)

        g3 = results["G3-RelevanceScoring"]
        assert g3.flagged is True
        assert g3.details["hidden"] is True

    def test_g1_flagged_in_orchestrator(self, sample_item: Item) -> None:
        context = {
            "source_config": {"quality_tier": 3},
            "topic_keywords": ["IVF"],
        }
        results = run_quality_gates(sample_item, context)

        g1 = results["G1-SourceAuthority"]
        assert g1.flagged is True
        assert g1.details["warning"] == "low quality source"

    def test_g2_detects_duplicate_in_orchestrator(
        self, sample_item: Item, sample_kb_entry: KBEntry
    ) -> None:
        existing = [
            KBEntry(**{**sample_kb_entry.to_dict(), "source_url": sample_item.source_url})
        ]
        context = {
            "existing_entries": existing,
            "topic_keywords": ["IVF"],
        }
        results = run_quality_gates(sample_item, context)

        g2 = results["G2-Dedup"]
        assert g2.passed is False
        assert g2.details["is_duplicate"] is True


# ===================================================================
# QualityResult dataclass
# ===================================================================


class TestQualityResult:
    """Verify QualityResult dataclass fields and defaults."""

    def test_default_values(self) -> None:
        r = QualityResult(gate_name="test", passed=True)

        assert r.score == 0.0
        assert r.details == {}
        assert r.flagged is False

    def test_custom_values(self) -> None:
        r = QualityResult(
            gate_name="G1",
            passed=True,
            score=95.0,
            details={"key": "val"},
            flagged=True,
        )

        assert r.gate_name == "G1"
        assert r.passed is True
        assert r.score == 95.0
        assert r.details == {"key": "val"}
        assert r.flagged is True
