"""Integration tests for the ContentBasedEngine recommendation pipeline.

Tests the full FTS5 + vector dual search, weighted scoring, dedup,
and edge-case handling (empty query, short query, no KB entries).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from autoinfo.recommend import ContentBasedEngine, ScoredItem


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entry(
    entry_id: str,
    title: str = "",
    domain: str = "medical-research",
    collected_at: str = "2026-07-30T00:00:00+00:00",
    source_url: str = "",
    **kwargs,
) -> dict:
    """Build a mock KB entry dict with sensible defaults."""
    entry = {
        "entry_id": entry_id,
        "title": title or entry_id,
        "domain": domain,
        "collected_at": collected_at,
        "source_url": source_url or f"https://example.com/{entry_id}",
    }
    entry.update(kwargs)
    return entry


def _make_search_result(entries: list[dict]) -> dict:
    """Wrap mock entries in the search_knowledge_base return shape."""
    return {"entries": entries, "total_count": len(entries), "method": "fts5"}


def _score_above(engine: ContentBasedEngine, entry: dict, domain: str, threshold: float) -> bool:
    """Check that a scored item exceeds a threshold when scored manually."""
    fresh = engine._freshness_score(entry)
    dom_score = 1.0 if (domain and entry.get("domain", "") == domain) else 0.0
    # Assume both FTS5+vector found (max score path)
    kw = 1.0  # found via FTS5
    vec = 1.0  # found via vector
    composite = (
        kw * engine.WEIGHT_KEYWORD * 100
        + vec * engine.WEIGHT_VECTOR * 100
        + fresh * engine.WEIGHT_FRESHNESS * 100
        + dom_score * engine.WEIGHT_DOMAIN * 100
    )
    return min(composite, 100.0) > threshold


# ---------------------------------------------------------------------------
# FTS5 + vector dual search
# ---------------------------------------------------------------------------


class TestDualSearchPipeline:
    """Recommend() with FTS5 + vector dual search."""

    def test_items_from_both_search_paths_are_merged(self):
        """Items from FTS5 and vector results are merged with dedup."""
        engine = ContentBasedEngine()
        mock_kb = MagicMock()
        mock_kb.search_knowledge_base.side_effect = [
            _make_search_result([
                _make_entry("e1", "FTS5 Article"),
                _make_entry("e2", "FTS5 Only"),
            ]),
            _make_search_result([
                _make_entry("e1", "Vector Article"),  # overlap
                _make_entry("e3", "Vector Only"),
            ]),
        ]
        engine._get_kb = MagicMock(return_value=mock_kb)

        results = engine.recommend(user_id="u1", query="cancer research", limit=10)

        ids = {r.entry_id for r in results}
        assert len(ids) == 3, f"Expected 3 unique entries, got {len(ids)}: {ids}"
        assert "e1" in ids
        assert "e2" in ids
        assert "e3" in ids

    def test_dedup_same_entry_appears_once(self):
        """An item found in both FTS5 and vector appears exactly once."""
        engine = ContentBasedEngine()
        mock_kb = MagicMock()
        mock_kb.search_knowledge_base.side_effect = [
            _make_search_result([_make_entry("dup")]),
            _make_search_result([_make_entry("dup")]),
        ]
        engine._get_kb = MagicMock(return_value=mock_kb)

        results = engine.recommend(user_id="u1", query="test", limit=10)
        assert len(results) == 1
        assert results[0].entry_id == "dup"

    def test_dual_found_gets_both_keyword_and_vector_weights(self):
        """Entry found via both FTS5 and vector gets 0.4+0.3 base = 70%."""
        engine = ContentBasedEngine()
        mock_kb = MagicMock()
        entry = _make_entry("dual", "Dual Hit")
        mock_kb.search_knowledge_base.side_effect = [
            _make_search_result([entry]),
            _make_search_result([entry]),
        ]
        engine._get_kb = MagicMock(return_value=mock_kb)

        results = engine.recommend(user_id="u1", query="test", limit=10)
        assert len(results) == 1
        # Base keyword+vector = 0.4*100 + 0.3*100 = 70, plus freshness
        assert results[0].score >= 70.0, f"Expected >=70, got {results[0].score}"

    def test_fts5_only_gets_keyword_weight(self):
        """Entry found only via FTS5 gets keyword weight (0.4) but no vector (0.3)."""
        engine = ContentBasedEngine()
        mock_kb = MagicMock()
        entry = _make_entry("fts5_only", "Only FTS5")
        mock_kb.search_knowledge_base.side_effect = [
            _make_search_result([entry]),
            _make_search_result([]),  # empty vector results
        ]
        engine._get_kb = MagicMock(return_value=mock_kb)

        results = engine.recommend(user_id="u1", query="test", limit=10)
        assert len(results) == 1
        # Base keyword = 0.4*100 = 40, plus freshness
        assert 40.0 <= results[0].score < 70.0, f"Expected 40-70, got {results[0].score}"

    def test_vector_only_gets_vector_weight(self):
        """Entry found only via vector gets vector weight (0.3) but no keyword (0.4)."""
        engine = ContentBasedEngine()
        mock_kb = MagicMock()
        entry = _make_entry("vec_only", "Only Vector")
        mock_kb.search_knowledge_base.side_effect = [
            _make_search_result([]),  # empty FTS5 results
            _make_search_result([entry]),
        ]
        engine._get_kb = MagicMock(return_value=mock_kb)

        results = engine.recommend(user_id="u1", query="test", limit=10)
        assert len(results) == 1
        # Base vector = 0.3*100 = 30, plus freshness
        assert 30.0 <= results[0].score < 60.0, f"Expected 30-60, got {results[0].score}"

    def test_found_via_both_scored_higher_than_single_path(self):
        """Entry found in both FTS5 and vector scores higher than single-path entries."""
        engine = ContentBasedEngine()
        mock_kb = MagicMock()

        dual = _make_entry("dual", "Dual Hit")
        fts5_only = _make_entry("fts5", "FTS5 Only")
        vec_only = _make_entry("vec", "Vector Only")

        mock_kb.search_knowledge_base.side_effect = [
            _make_search_result([dual, fts5_only]),
            _make_search_result([dual, vec_only]),
        ]
        engine._get_kb = MagicMock(return_value=mock_kb)

        results = engine.recommend(user_id="u1", query="test", limit=10)
        scores = {r.entry_id: r.score for r in results}

        assert scores["dual"] > scores["fts5"], f"dual ({scores['dual']}) should beat fts5 ({scores['fts5']})"
        assert scores["dual"] > scores["vec"], f"dual ({scores['dual']}) should beat vec ({scores['vec']})"

    def test_scores_always_normalized_to_100(self):
        """All scores should be in [0, 100] range, capped at 100."""
        engine = ContentBasedEngine()
        mock_kb = MagicMock()
        entry = _make_entry("e1", "Score Check",
                            collected_at="2026-07-31T00:00:00+00:00",
                            domain="medical-research")
        mock_kb.search_knowledge_base.side_effect = [
            _make_search_result([entry]),
            _make_search_result([entry]),
        ]
        engine._get_kb = MagicMock(return_value=mock_kb)

        results = engine.recommend(user_id="u1", query="test", domain="medical-research", limit=10)
        for r in results:
            assert 0.0 <= r.score <= 100.0, f"Score {r.score} out of range for {r.entry_id}"


# ---------------------------------------------------------------------------
# Domain match bonus
# ---------------------------------------------------------------------------


class TestDomainScoring:
    """Domain match contributes weight 0.1 to scoring."""

    def test_domain_match_adds_bonus(self):
        engine = ContentBasedEngine()
        mock_kb = MagicMock()
        matching = _make_entry("e1", "Domain Match", domain="medical-research")
        non_matching = _make_entry("e2", "Other Domain", domain="ai-commercial")

        mock_kb.search_knowledge_base.side_effect = [
            _make_search_result([matching]),
            _make_search_result([non_matching]),
        ]
        engine._get_kb = MagicMock(return_value=mock_kb)

        results = engine.recommend(user_id="u1", query="test", domain="medical-research", limit=10)
        scores = {r.entry_id: r.score for r in results}
        assert scores["e1"] > scores["e2"], f"Domain match ({scores['e1']}) should beat non-match ({scores['e2']})"

    def test_no_domain_filter_equal_scores(self):
        """Without a domain filter, domain bonus applies to none.

        When both entries are found via the same search path and have the same
        freshness, their scores should be equal (no domain bonus differential).
        """
        engine = ContentBasedEngine()
        mock_kb = MagicMock()
        e1 = _make_entry("e1", "A", domain="medical-research")
        e2 = _make_entry("e2", "B", domain="ai-commercial")

        # Both found via FTS5 only (same path, same weight)
        mock_kb.search_knowledge_base.side_effect = [
            _make_search_result([e1, e2]),
            _make_search_result([]),  # empty vector
        ]
        engine._get_kb = MagicMock(return_value=mock_kb)

        results = engine.recommend(user_id="u1", query="test", domain=None, limit=10)
        scores = {r.entry_id: r.score for r in results}
        assert abs(scores["e1"] - scores["e2"]) < 2.0, f"Scores {scores} should be nearly equal"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Handle empty query, short query, no KB, no entries."""

    def test_empty_query_returns_recent(self):
        """Empty query falls back to _recommend_recent."""
        engine = ContentBasedEngine()
        mock_kb = MagicMock()
        mock_kb.search_knowledge_base.return_value = _make_search_result([
            _make_entry("r1", "Recent Paper"),
            _make_entry("r2", "Old Paper"),
        ])
        engine._get_kb = MagicMock(return_value=mock_kb)

        results = engine.recommend(user_id="u1", query="", limit=5)
        assert len(results) == 2
        for r in results:
            assert isinstance(r, ScoredItem)

    def test_whitespace_only_query_returns_recent(self):
        """Whitespace-only query falls back to recent items."""
        engine = ContentBasedEngine()
        mock_kb = MagicMock()
        mock_kb.search_knowledge_base.return_value = _make_search_result([
            _make_entry("r1", "Recent"),
        ])
        engine._get_kb = MagicMock(return_value=mock_kb)

        results = engine.recommend(user_id="u1", query="   ", limit=5)
        assert len(results) == 1

    def test_short_query_returns_recent(self):
        """Short query (<3 chars) falls back to recent items."""
        engine = ContentBasedEngine()
        mock_kb = MagicMock()
        mock_kb.search_knowledge_base.return_value = _make_search_result([
            _make_entry("r1", "Recent"),
        ])
        engine._get_kb = MagicMock(return_value=mock_kb)

        results = engine.recommend(user_id="u1", query="ab", limit=5)
        assert len(results) == 1

    def test_query_exactly_3_chars_triggers_search(self):
        """A query with exactly 3 chars triggers the search path (not recent fallback)."""
        engine = ContentBasedEngine()
        mock_kb = MagicMock()
        mock_kb.search_knowledge_base.side_effect = [
            _make_search_result([_make_entry("e1")]),
            _make_search_result([_make_entry("e1")]),
        ]
        engine._get_kb = MagicMock(return_value=mock_kb)

        results = engine.recommend(user_id="u1", query="abc", limit=5)
        assert len(results) == 1
        # Should have called search_knowledge_base twice (FTS5 + vector)
        assert mock_kb.search_knowledge_base.call_count == 2

    def test_no_kb_available_returns_empty(self):
        """When KBStore is unavailable, returns empty list."""
        engine = ContentBasedEngine()
        engine._get_kb = MagicMock(return_value=None)

        results = engine.recommend(user_id="u1", query="cancer", limit=5)
        assert results == []

    def test_no_entries_in_either_search_returns_empty(self):
        """When both FTS5 and vector return no entries, results are empty."""
        engine = ContentBasedEngine()
        mock_kb = MagicMock()
        mock_kb.search_knowledge_base.side_effect = [
            _make_search_result([]),
            _make_search_result([]),
        ]
        engine._get_kb = MagicMock(return_value=mock_kb)

        results = engine.recommend(user_id="u1", query="nonexistent", limit=5)
        assert results == []

    def test_recent_with_no_entries_returns_empty(self):
        """When recent fallback also has no entries, returns empty."""
        engine = ContentBasedEngine()
        mock_kb = MagicMock()
        mock_kb.search_knowledge_base.return_value = _make_search_result([])
        engine._get_kb = MagicMock(return_value=mock_kb)

        results = engine.recommend(user_id="u1", query="", limit=5)
        assert results == []

    def test_limit_respected(self):
        """Only up to `limit` items are returned."""
        engine = ContentBasedEngine()
        mock_kb = MagicMock()
        entries = [_make_entry(f"e{i}") for i in range(20)]
        mock_kb.search_knowledge_base.side_effect = [
            _make_search_result(entries[:10]),
            _make_search_result(entries[10:20]),
        ]
        engine._get_kb = MagicMock(return_value=mock_kb)

        results = engine.recommend(user_id="u1", query="test", limit=3)
        assert len(results) <= 3

    def test_exception_returns_empty(self):
        """When search_knowledge_base raises, returns empty gracefully."""
        engine = ContentBasedEngine()
        mock_kb = MagicMock()
        mock_kb.search_knowledge_base.side_effect = RuntimeError("DB error")
        engine._get_kb = MagicMock(return_value=mock_kb)

        results = engine.recommend(user_id="u1", query="test", limit=5)
        assert results == []


# ---------------------------------------------------------------------------
# Scoring weights are used
# ---------------------------------------------------------------------------


class TestWeightConstants:
    """Verify the scoring weight constants exist and sum to 1.0."""

    def test_weights_sum_to_one(self):
        engine = ContentBasedEngine()
        total = (
            engine.WEIGHT_KEYWORD
            + engine.WEIGHT_VECTOR
            + engine.WEIGHT_FRESHNESS
            + engine.WEIGHT_DOMAIN
        )
        assert total == pytest.approx(1.0), f"Weights sum to {total}, expected 1.0"

    def test_weights_are_positive(self):
        engine = ContentBasedEngine()
        assert engine.WEIGHT_KEYWORD > 0
        assert engine.WEIGHT_VECTOR > 0
        assert engine.WEIGHT_FRESHNESS > 0
        assert engine.WEIGHT_DOMAIN > 0


# ---------------------------------------------------------------------------
# ScoredItem integrity
# ---------------------------------------------------------------------------


class TestScoredItemIntegration:
    """ScoredItem fields populated correctly from the pipeline."""

    def test_all_fields_populated(self):
        engine = ContentBasedEngine()
        mock_kb = MagicMock()
        entry = _make_entry(
            "full",
            "Full Entry",
            domain="medical-research",
            source_url="https://example.com/full",
        )
        mock_kb.search_knowledge_base.side_effect = [
            _make_search_result([entry]),
            _make_search_result([entry]),
        ]
        engine._get_kb = MagicMock(return_value=mock_kb)

        results = engine.recommend(user_id="u1", query="test", domain="medical-research", limit=5)
        assert len(results) == 1
        item = results[0]
        assert item.entry_id == "full"
        assert item.title == "Full Entry"
        assert item.score > 0
        assert item.reason
        assert item.source_url == "https://example.com/full"
        assert item.domain == "medical-research"

    def test_reason_varied_by_score(self):
        engine = ContentBasedEngine()
        mock_kb = MagicMock()

        high = _make_entry("high", "High Score", collected_at="2026-07-31T00:00:00+00:00")
        low = _make_entry("low", "Low Score", collected_at="2020-01-01T00:00:00+00:00")

        mock_kb.search_knowledge_base.side_effect = [
            _make_search_result([high]),
            _make_search_result([low]),
        ]
        engine._get_kb = MagicMock(return_value=mock_kb)

        results = engine.recommend(user_id="u1", query="test", limit=10)
        reasons = {r.entry_id: r.reason for r in results}
        # High-scoring item should have "Highly relevant" or "Related"
        assert reasons["high"] != reasons["low"], f"Reasons should differ: {reasons}"
