"""Tests for recommendation engine."""

import pytest
from unittest.mock import MagicMock
from autoinfo.recommend import ContentBasedEngine, ScoredItem


class TestScoredItem:
    def test_creation_with_required_fields(self):
        item = ScoredItem(entry_id="id1", title="Test", score=85.0, reason="Highly relevant")
        assert item.entry_id == "id1"
        assert item.score == 85.0
        assert item.title == "Test"
        assert item.reason == "Highly relevant"

    def test_default_values(self):
        item = ScoredItem(entry_id="e2", title="T2", score=50.0, reason="ok")
        assert item.source_url == ""
        assert item.domain == ""
        assert item.metadata == {}

    def test_score_range_valid(self):
        for s in [0.0, 50.0, 100.0]:
            item = ScoredItem(entry_id="x", title="x", score=s, reason="x")
            assert 0 <= item.score <= 100

    def test_metadata_stores_extra_fields(self):
        item = ScoredItem(
            entry_id="e3", title="T3", score=90.0, reason="R",
            metadata={"tags": ["ai"], "author": "Test Author"},
        )
        assert item.metadata["tags"] == ["ai"]
        assert item.metadata["author"] == "Test Author"


class TestContentBasedEngine:
    def test_no_kb_returns_empty(self):
        engine = ContentBasedEngine()
        engine._get_kb = MagicMock(return_value=None)
        result = engine.recommend(user_id="test", query="cancer research")
        assert result == []

    def test_empty_query_returns_empty_when_no_kb(self):
        engine = ContentBasedEngine()
        engine._get_kb = MagicMock(return_value=None)
        result = engine.recommend(user_id="test", query="", limit=5)
        assert result == []

    def test_short_query_returns_empty_when_no_kb(self):
        engine = ContentBasedEngine()
        engine._get_kb = MagicMock(return_value=None)
        result = engine.recommend(user_id="test", query="ab", limit=5)
        assert result == []

    def test_recommend_with_kb_results(self):
        engine = ContentBasedEngine()
        mock_kb = MagicMock()
        mock_kb.search_knowledge_base.return_value = {
            "entries": [
                {
                    "entry_id": "e1",
                    "title": "Test Article",
                    "relevance_score": 0.8,
                    "freshness_score": 0.9,
                    "collected_at": "2026-07-30T00:00:00+00:00",
                    "source_url": "https://example.com",
                    "domain": "medical-research",
                },
            ],
        }
        engine._get_kb = MagicMock(return_value=mock_kb)
        results = engine.recommend(user_id="test", query="cancer research", limit=5)

        assert len(results) > 0
        for r in results:
            assert 0 <= r.score <= 100
            assert r.reason

    def test_scores_are_within_range_mixed_inputs(self):
        engine = ContentBasedEngine()
        # Over-range relevance_score should still produce 0-100 result
        item = {
            "relevance_score": 200.0,
            "freshness_score": None,
            "collected_at": "2026-07-30T00:00:00+00:00",
            "domain": "test",
        }
        score = engine._calculate_score(item, "test", "test")
        assert 0 <= score <= 100, f"Score out of range: {score}"

    def test_scores_are_within_range_no_data(self):
        engine = ContentBasedEngine()
        item: dict = {}
        score = engine._calculate_score(item, "test", "test")
        assert 0 <= score <= 100, f"Score out of range: {score}"

    def test_domain_match_adds_bonus(self):
        engine = ContentBasedEngine()
        item_with_match = {
            "relevance_score": 0.5,
            "freshness_score": 0.5,
            "domain": "medical-research",
        }
        item_no_match = {
            "relevance_score": 0.5,
            "freshness_score": 0.5,
            "domain": "other-domain",
        }
        score_match = engine._calculate_score(item_with_match, "test", "medical-research")
        score_no_match = engine._calculate_score(item_no_match, "test", "medical-research")
        assert score_match > score_no_match

    def test_freshness_score_max_for_future_date(self):
        engine = ContentBasedEngine()
        item = {"collected_at": "2099-01-01T00:00:00+00:00"}
        score = engine._freshness_score(item)
        assert score == 1.0

    def test_freshness_score_mid_for_missing_date(self):
        engine = ContentBasedEngine()
        item: dict = {}
        score = engine._freshness_score(item)
        assert score == 0.5

    def test_freshness_score_recent_date(self):
        from datetime import datetime, timezone, timedelta

        engine = ContentBasedEngine()
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        item = {"collected_at": yesterday.isoformat()}
        score = engine._freshness_score(item)
        assert score > 0.9  # Very recent -> high score

    def test_generate_reason_tiers(self):
        engine = ContentBasedEngine()
        item = {"title": "Important Research Paper on Cancer Treatment"}

        assert "Highly relevant" in engine._generate_reason(item, 85)
        assert "Related content" in engine._generate_reason(item, 65)
        assert "Similar topic" in engine._generate_reason(item, 45)
        assert "Recently added" in engine._generate_reason(item, 20)

    def test_recommend_recent_no_kb_entries(self):
        engine = ContentBasedEngine()
        mock_kb = MagicMock()
        mock_kb.search_knowledge_base.return_value = {"entries": []}
        result = engine._recommend_recent(mock_kb, "medical-research", limit=5)
        assert result == []

    def test_recommend_recent_with_entries(self):
        engine = ContentBasedEngine()
        mock_kb = MagicMock()
        mock_kb.search_knowledge_base.return_value = {
            "entries": [
                {
                    "entry_id": "e1",
                    "title": "Recent Paper",
                    "freshness_score": 0.85,
                    "domain": "medical-research",
                },
                {
                    "entry_id": "e2",
                    "title": "Old Paper",
                    "freshness_score": 0.2,
                    "domain": "ai-commercial",
                },
            ],
        }
        result = engine._recommend_recent(mock_kb, domain=None, limit=2)
        assert len(result) == 2
        assert all(isinstance(r, ScoredItem) for r in result)
        assert result[0].score > result[1].score  # Higher freshness score first
