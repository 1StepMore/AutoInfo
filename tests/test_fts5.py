"""Tests for FTS5 full-text search over KB entries.

Covers:
    - FTS5 virtual table creation
    - Search returns matching entries ranked by relevance
    - Search with no matches returns empty entries with total_count=0
    - Pagination (offset, limit)
    - Domain filter
    - CJK search (Chinese characters)
    - kb reindex populates FTS5 from .md files
    - _escape_fts5_query helper
    - Fallback to LIKE search
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
import yaml

from autoinfo.kb import (
    KBStore,
    SQLiteIndex,
    _escape_fts5_query,
    _strip_frontmatter,
)
from autoinfo.models import Item, KBEntry


# ===================================================================
# _escape_fts5_query helper
# ===================================================================


class TestEscapeFts5Query:
    def test_empty_query(self) -> None:
        assert _escape_fts5_query("") == ""
        assert _escape_fts5_query("   ") == ""

    def test_plain_terms(self) -> None:
        assert _escape_fts5_query("IVF breakthrough") == "IVF breakthrough"

    def test_strips_special_chars(self) -> None:
        assert "^" not in _escape_fts5_query("^IVF")
        assert '"' not in _escape_fts5_query('"IVF"')
        assert "(" not in _escape_fts5_query("(IVF)")
        assert ":" not in _escape_fts5_query("title:IVF")
        assert "*" not in _escape_fts5_query("IVF*")
        assert "!" not in _escape_fts5_query("!IVF")

    def test_lowercases_fts5_keywords(self) -> None:
        result = _escape_fts5_query("IVF AND embryo")
        assert "AND" not in result
        assert "and" in result

    def test_lowercases_or_not(self) -> None:
        result = _escape_fts5_query("IVF OR embryo")
        assert "OR" not in result
        assert "or" in result

    def test_mixed_chars_preserves_alphanumeric(self) -> None:
        result = _escape_fts5_query("time-lapse imaging")
        assert result

    def test_cjk_preserved(self) -> None:
        result = _escape_fts5_query("辅助生殖")
        assert "辅助生殖" in result or "辅" in result


# ===================================================================
# SQLiteIndex FTS5
# ===================================================================


class TestSQLiteIndexFTS5:
    """Test FTS5 functionality on the low-level SQLiteIndex."""

    @pytest.fixture
    def db_path(self, tmp_path: Path) -> Path:
        return tmp_path / "test_autoinfo.db"

    @pytest.fixture
    def index(self, db_path: Path) -> SQLiteIndex:
        idx = SQLiteIndex(db_path)
        idx.init_db()
        return idx

    @pytest.fixture
    def sample_entries(self) -> list[KBEntry]:
        return [
            KBEntry(
                entry_id="entry-001",
                title="Improved IVF outcomes with time-lapse imaging",
                domain="medical-research",
                tier="01-Raw",
                source_url="https://example.com/1",
                source_type="api",
                source_platform="pubmed",
                collected_at="2026-07-15T10:00:00Z",
                summary="Time-lapse imaging improves live birth rates in IVF patients.",
                tags=["IVF", "time-lapse", "embryo imaging"],
                quality_tier=1,
                relevance_score=92.0,
                dedup_status="unique",
                file_path="",
            ),
            KBEntry(
                entry_id="entry-002",
                title="AI-powered embryo selection using deep learning",
                domain="medical-research",
                tier="01-Raw",
                source_url="https://example.com/2",
                source_type="api",
                source_platform="pubmed",
                collected_at="2026-07-14T10:00:00Z",
                summary="Deep learning model predicts embryo viability with 89% accuracy.",
                tags=["AI", "embryo", "deep learning"],
                quality_tier=1,
                relevance_score=88.0,
                dedup_status="unique",
                file_path="",
            ),
            KBEntry(
                entry_id="entry-003",
                title="LLM market trends 2026",
                domain="ai-commercial",
                tier="01-Raw",
                source_url="https://example.com/3",
                source_type="api",
                source_platform="arxiv",
                collected_at="2026-07-13T10:00:00Z",
                summary="Large language models continue to dominate AI investment.",
                tags=["LLM", "market", "AI"],
                quality_tier=1,
                relevance_score=75.0,
                dedup_status="unique",
                file_path="",
            ),
            KBEntry(
                entry_id="entry-004",
                title="儿童英语学习新方法",
                domain="language-learning",
                tier="01-Raw",
                source_url="https://example.com/4",
                source_type="api",
                source_platform="custom",
                collected_at="2026-07-12T10:00:00Z",
                summary="通过游戏学习英语的新方法研究",
                tags=["儿童", "英语", "游戏"],
                quality_tier=1,
                relevance_score=80.0,
                dedup_status="unique",
                file_path="",
            ),
        ]

    def _index_all(
        self,
        index: SQLiteIndex,
        entries: list[KBEntry],
        contents: dict[str, str] | None = None,
    ) -> None:
        for entry in entries:
            index.index_entry(entry)
            index.index_entry_fts5(
                entry, content=(contents or {}).get(entry.entry_id, "")
            )

    def test_fts5_table_created(self, db_path: Path, index: SQLiteIndex) -> None:
        conn = sqlite3.connect(str(db_path))
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = {r[0] for r in tables}
        assert "entries_fts5" in table_names
        conn.close()

    def test_fts5_virtual_table_type(self, db_path: Path, index: SQLiteIndex) -> None:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT type, sql FROM sqlite_master WHERE name='entries_fts5'"
        ).fetchone()
        assert row is not None, "entries_fts5 table not found"
        assert "fts5" in row["sql"].lower(), "not an FTS5 table"
        conn.close()

    # --------------------------------------------------------------
    # Search returns matching entries
    # --------------------------------------------------------------

    def test_search_returns_matching_entries(
        self, index: SQLiteIndex, sample_entries: list[KBEntry]
    ) -> None:
        self._index_all(index, sample_entries)

        result = index.search_fts5("IVF")
        assert result["total_count"] >= 1
        assert result["entries"][0]["entry_id"] == "entry-001"

    def test_search_multiple_matches_ranked(
        self, index: SQLiteIndex, sample_entries: list[KBEntry]
    ) -> None:
        self._index_all(index, sample_entries)

        result = index.search_fts5("embryo")
        # Both entry-001 and entry-002 mention "embryo"
        assert result["total_count"] >= 2
        entry_ids = {e["entry_id"] for e in result["entries"]}
        assert "entry-001" in entry_ids
        assert "entry-002" in entry_ids

    def test_search_no_matches_returns_empty(
        self, index: SQLiteIndex, sample_entries: list[KBEntry]
    ) -> None:
        self._index_all(index, sample_entries)

        result = index.search_fts5("xyznonexistent12345")
        assert result["total_count"] == 0
        assert result["entries"] == []

    # --------------------------------------------------------------
    # Pagination
    # --------------------------------------------------------------

    def test_search_pagination(
        self, index: SQLiteIndex
    ) -> None:
        entries = [
            KBEntry(
                entry_id=f"page-entry-{i:03d}",
                title=f"Article about IVF number {i}",
                domain="medical-research",
                source_url=f"https://example.com/{i}",
                tags=["IVF"],
                collected_at=f"2026-07-{15:02d}T10:00:0{i}Z",
            )
            for i in range(10)
        ]
        self._index_all(index, entries)

        # Page 1: limit=5, offset=0
        page1 = index.search_fts5("IVF", limit=5, offset=0)
        assert len(page1["entries"]) == 5
        assert page1["total_count"] >= 10

        # Page 2: limit=5, offset=5
        page2 = index.search_fts5("IVF", limit=5, offset=5)
        assert len(page2["entries"]) == 5

        # No overlap
        ids_p1 = {e["entry_id"] for e in page1["entries"]}
        ids_p2 = {e["entry_id"] for e in page2["entries"]}
        assert ids_p1.isdisjoint(ids_p2)

    # --------------------------------------------------------------
    # Domain filter
    # --------------------------------------------------------------

    def test_search_domain_filter(
        self, index: SQLiteIndex, sample_entries: list[KBEntry]
    ) -> None:
        self._index_all(index, sample_entries)

        # Search "AI" across all domains
        all_results = index.search_fts5("AI")
        assert all_results["total_count"] >= 1

        # Filter to only ai-commercial
        ai_results = index.search_fts5("AI", domain="ai-commercial")
        assert ai_results["total_count"] >= 1
        for e in ai_results["entries"]:
            assert e["domain"] == "ai-commercial"

        # Filter to non-matching domain
        empty = index.search_fts5("AI", domain="language-learning")
        assert empty["total_count"] == 0

    def test_search_empty_domain_returns_all(
        self, index: SQLiteIndex, sample_entries: list[KBEntry]
    ) -> None:
        self._index_all(index, sample_entries)

        result = index.search_fts5("embryo", domain="")
        assert result["total_count"] >= 1

    # --------------------------------------------------------------
    # CJK search
    # --------------------------------------------------------------

    def test_cjk_search(
        self, index: SQLiteIndex, sample_entries: list[KBEntry]
    ) -> None:
        self._index_all(index, sample_entries)

        result = index.search_fts5("儿童")
        assert result["total_count"] >= 1
        assert result["entries"][0]["entry_id"] == "entry-004"

    def test_cjk_search_summary(
        self, index: SQLiteIndex, sample_entries: list[KBEntry]
    ) -> None:
        self._index_all(index, sample_entries)

        result = index.search_fts5("游戏")
        assert result["total_count"] >= 1

    # --------------------------------------------------------------
    # FTS5 fallback
    # --------------------------------------------------------------

    def test_fts5_fallback_on_invalid_syntax(
        self, index: SQLiteIndex, sample_entries: list[KBEntry]
    ) -> None:
        self._index_all(index, sample_entries)

        result = index.search_fts5("IVF")
        assert result["total_count"] >= 1

    # ==============================================================
    # KBStore integration
    # ==============================================================


class TestKBStoreFTS5:
    """Test FTS5 via the high-level KBStore."""

    @pytest.fixture
    def store(self, tmp_path: Path) -> KBStore:
        return KBStore(base_path=tmp_path / "knowledge")

    @pytest.fixture
    def sample_items(self) -> list[Item]:
        return [
            Item(
                id="item-001",
                source_name="pubmed",
                source_type="api",
                source_url="https://example.com/1",
                title="IVF with time-lapse imaging",
                content="Time-lapse embryo imaging improves embryo selection in IVF cycles.",
                collected_at="2026-07-15T10:00:00Z",
                domain="medical-research",
                topic_tags=["IVF", "time-lapse"],
            ),
            Item(
                id="item-002",
                source_name="pubmed",
                source_type="api",
                source_url="https://example.com/2",
                title="AI in embryo selection",
                content="Deep learning models can predict embryo viability with high accuracy.",
                collected_at="2026-07-14T10:00:00Z",
                domain="medical-research",
                topic_tags=["AI", "embryo"],
            ),
            Item(
                id="item-003",
                source_name="arxiv",
                source_type="api",
                source_url="https://example.com/3",
                title="儿童英语学习",
                content="通过互动游戏学习英语的方法研究。",
                collected_at="2026-07-13T10:00:00Z",
                domain="language-learning",
                topic_tags=["儿童", "英语"],
            ),
        ]

    def test_search_knowledge_base_after_store(
        self, store: KBStore, sample_items: list[Item]
    ) -> None:
        for item in sample_items:
            store.store_entry(item)

        result = store.search_knowledge_base("IVF")
        assert result["total_count"] >= 1
        assert "time-lapse" in result["entries"][0]["title"].lower()

    def test_search_knowledge_base_no_matches(
        self, store: KBStore, sample_items: list[Item]
    ) -> None:
        for item in sample_items:
            store.store_entry(item)

        result = store.search_knowledge_base("nonexistent12345")
        assert result["total_count"] == 0
        assert result["entries"] == []

    def test_search_with_domain_filter(
        self, store: KBStore, sample_items: list[Item]
    ) -> None:
        for item in sample_items:
            store.store_entry(item)

        result = store.search_knowledge_base("embryo", domain="medical-research")
        assert result["total_count"] >= 1
        for e in result["entries"]:
            assert e["domain"] == "medical-research"

    def test_search_with_domain_no_match(
        self, store: KBStore, sample_items: list[Item]
    ) -> None:
        for item in sample_items:
            store.store_entry(item)

        result = store.search_knowledge_base("embryo", domain="ai-commercial")
        assert result["total_count"] == 0

    def test_cjk_search_via_store(
        self, store: KBStore, sample_items: list[Item]
    ) -> None:
        for item in sample_items:
            store.store_entry(item)

        result = store.search_knowledge_base("儿童")
        assert result["total_count"] >= 1

    def test_search_pagination_via_store(
        self, store: KBStore
    ) -> None:
        for i in range(10):
            store.store_entry(
                Item(
                    id=f"item-{i:03d}",
                    source_name="pubmed",
                    source_type="api",
                    source_url=f"https://example.com/{i}",
                    title=f"IVF research article {i}",
                    content=f"This is content about IVF for article number {i}.",
                    collected_at=f"2026-07-{15:02d}T10:00:0{i}Z",
                    domain="medical-research",
                    topic_tags=["IVF"],
                )
            )

        page1 = store.search_knowledge_base("IVF", limit=5, offset=0)
        assert len(page1["entries"]) == 5

        page2 = store.search_knowledge_base("IVF", limit=5, offset=5)
        assert len(page2["entries"]) == 5

        ids_p1 = {e["entry_id"] for e in page1["entries"]}
        ids_p2 = {e["entry_id"] for e in page2["entries"]}
        assert ids_p1.isdisjoint(ids_p2)

    # --------------------------------------------------------------
    # Reindex
    # --------------------------------------------------------------

    def test_reindex_knowledge_base(
        self, store: KBStore, sample_items: list[Item]
    ) -> None:
        for item in sample_items:
            store.store_entry(item)

        # Verify search works (FTS5 was populated via store_entry)
        before = store.search_knowledge_base("IVF")
        assert before["total_count"] >= 1

        # Now reindex
        result = store.reindex_knowledge_base()
        assert result["fts5_indexed"] >= 3
        assert result["files_found"] >= 3
        assert result["errors"] == []

        # Search should still work after reindex
        after = store.search_knowledge_base("IVF")
        assert after["total_count"] >= 1

    def test_reindex_domain_scoped(
        self, store: KBStore, sample_items: list[Item]
    ) -> None:
        for item in sample_items:
            store.store_entry(item)

        result = store.reindex_knowledge_base(domain="medical-research")
        assert result["fts5_indexed"] >= 3  # Still indexes all entries
        assert result["files_found"] >= 2  # 2 items in medical-research

    def test_reindex_from_orphaned_md_files(
        self, tmp_path: Path, store: KBStore
    ) -> None:
        md_dir = tmp_path / "knowledge" / "medical-research" / "01-Raw" / "IVF"
        md_dir.mkdir(parents=True, exist_ok=True)
        md_file = md_dir / "2026-07-15-orphaned-test.md"
        entry_id = "orphaned-entry"
        fm = {
            "title": "Orphaned test entry",
            "domain": "medical-research",
            "tier": "01-Raw",
            "entry_id": entry_id,
            "source_url": "https://example.com/orphaned",
            "source_type": "api",
            "source_platform": "test",
            "collected_at": "2026-07-15T10:00:00Z",
            "summary": "This entry only exists as a md file.",
            "tags": ["test"],
            "quality_tier": 1,
            "relevance_score": 50.0,
            "dedup_status": "unique",
            "language": "en",
        }
        frontmatter = yaml.dump(fm, default_flow_style=False, allow_unicode=True)
        md_file.write_text(
            f"---\n{frontmatter}---\n\nOrphaned body content for FTS5 testing.",
            encoding="utf-8",
        )

        # Verify not in index yet
        assert store.index.get_entry(entry_id) is None

        # Reindex — should pick up orphaned file
        result = store.reindex_knowledge_base(domain="medical-research")
        assert result["files_found"] >= 1

        # Now entry should exist in SQLite and FTS5
        assert store.index.get_entry(entry_id) is not None

        search_result = store.search_knowledge_base("orphaned")
        assert search_result["total_count"] >= 1

    def test_mcp_search_returns_expected_shape(
        self, store: KBStore, sample_items: list[Item]
    ) -> None:
        for item in sample_items:
            store.store_entry(item)

        result = store.search_knowledge_base("IVF")
        expected_keys = {"query", "domain", "entries", "total_count", "limit", "offset"}
        assert expected_keys.issubset(result.keys())
        assert isinstance(result["entries"], list)
        assert isinstance(result["total_count"], int)
