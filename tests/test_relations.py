"""Tests for item linking / relations (task 22)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from autoinfo.kb import KBStore, SQLiteIndex
from autoinfo.models import Item, KBEntry


def _make_entry(
    entry_id: str,
    domain: str = "test-domain",
    tags: list[str] | None = None,
    title: str = "",
    tier: str = "01-Raw",
) -> KBEntry:
    return KBEntry(
        entry_id=entry_id,
        title=title or entry_id,
        domain=domain,
        tier=tier,
        source_url="https://example.com",
        source_type="api",
        source_platform="test",
        collected_at="2026-07-20T00:00:00Z",
        summary="",
        tags=tags or [],
        quality_tier=1,
        relevance_score=50.0,
        dedup_status="unique",
        file_path="",
    )


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_relations.db"


@pytest.fixture
def index(db_path: Path) -> SQLiteIndex:
    idx = SQLiteIndex(db_path)
    idx.init_db()
    return idx


class TestSQLiteIndexRelations:
    """Direct SQLiteIndex-level relation tests."""

    def test_link_items_creates_relation(self, index: SQLiteIndex) -> None:
        # Seed two entries
        a = _make_entry("entry-a", tags=["tag1"])
        b = _make_entry("entry-b", tags=["tag2"])
        index.index_entry(a)
        index.index_entry(b)

        result = index.link_items("entry-a", "entry-b", "related")
        assert "relation_id" in result
        assert result.get("linked") is True or "relation_id" in result

    def test_link_items_idempotent(self, index: SQLiteIndex) -> None:
        a = _make_entry("entry-a-idem")
        b = _make_entry("entry-b-idem")
        index.index_entry(a)
        index.index_entry(b)

        r1 = index.link_items("entry-a-idem", "entry-b-idem", "related")
        r2 = index.link_items("entry-a-idem", "entry-b-idem", "related")
        # Same relation_id means no duplicate created
        assert r1.get("relation_id") == r2.get("relation_id")

    def test_link_items_foreign_key_fails(self, index: SQLiteIndex) -> None:
        result = index.link_items("nonexistent-a", "nonexistent-b")
        assert result.get("linked") is False
        assert "error" in result

    def test_get_item_relations_returns_linked(self, index: SQLiteIndex) -> None:
        a = _make_entry("entry-rel-a")
        b = _make_entry("entry-rel-b")
        c = _make_entry("entry-rel-c")
        index.index_entry(a)
        index.index_entry(b)
        index.index_entry(c)

        index.link_items("entry-rel-a", "entry-rel-b")
        index.link_items("entry-rel-a", "entry-rel-c")

        rels = index.get_item_relations("entry-rel-a")
        assert len(rels) == 2

    def test_get_item_relations_filter_by_type(self, index: SQLiteIndex) -> None:
        a = _make_entry("entry-ft-a")
        b = _make_entry("entry-ft-b")
        c = _make_entry("entry-ft-c")
        index.index_entry(a)
        index.index_entry(b)
        index.index_entry(c)

        index.link_items("entry-ft-a", "entry-ft-b", "related")
        index.link_items("entry-ft-a", "entry-ft-c", "references")

        related = index.get_item_relations("entry-ft-a", "related")
        assert len(related) == 1
        assert related[0]["relation_type"] == "related"

    def test_no_relations_returns_empty(self, index: SQLiteIndex) -> None:
        rels = index.get_item_relations("ghost-entry")
        assert rels == []


class TestKBStoreRelations:
    """KBStore-level relation tests including auto-linking."""

    @pytest.fixture
    def store(self, tmp_path: Path) -> KBStore:
        kb_path = tmp_path / "knowledge"
        kb_path.mkdir(parents=True, exist_ok=True)
        return KBStore(base_path=kb_path)

    @pytest.fixture
    def sample_item_a(self) -> Item:
        return Item(
            id="item-a",
            source_name="test",
            source_type="api",
            source_url="https://example.com/a",
            title="Entry A about IVF",
            content="Content about IVF treatment.",
            collected_at="2026-07-20T00:00:00Z",
            domain="test-domain",
            topic_tags=["IVF", "embryo"],
        )

    @pytest.fixture
    def sample_item_b(self) -> Item:
        return Item(
            id="item-b",
            source_name="test",
            source_type="api",
            source_url="https://example.com/b",
            title="Entry B about embryo imaging",
            content="Content about embryo imaging.",
            collected_at="2026-07-20T01:00:00Z",
            domain="test-domain",
            topic_tags=["embryo", "imaging"],
        )

    @pytest.fixture
    def sample_item_c(self) -> Item:
        return Item(
            id="item-c",
            source_name="test",
            source_type="api",
            source_url="https://example.com/c",
            title="Entry C about AI",
            content="Content about artificial intelligence.",
            collected_at="2026-07-20T02:00:00Z",
            domain="test-domain",
            topic_tags=["AI", "machine learning"],
        )

    def test_link_items_public(self, store: KBStore) -> None:
        entry_a = _make_entry("pub-link-a")
        entry_b = _make_entry("pub-link-b")
        store.index.index_entry(entry_a)
        store.index.index_entry(entry_b)

        result = store.link_items("pub-link-a", "pub-link-b")
        assert result.get("linked") is True or "relation_id" in result

    def test_get_item_relations_public(self, store: KBStore) -> None:
        entry_a = _make_entry("pub-rel-a")
        entry_b = _make_entry("pub-rel-b")
        store.index.index_entry(entry_a)
        store.index.index_entry(entry_b)
        store.link_items("pub-rel-a", "pub-rel-b")

        rels = store.get_item_relations("pub-rel-a")
        assert len(rels) == 1

    def test_auto_linking_on_store_entry(
        self, store: KBStore, sample_item_a: Item, sample_item_b: Item
    ) -> None:
        # Store first item — no existing entries to link to
        entry_a = store.store_entry(sample_item_a)
        assert entry_a is not None

        # Store second item with overlapping tag "embryo" — auto-links
        entry_b = store.store_entry(sample_item_b)
        assert entry_b is not None

        rels = store.get_item_relations(entry_b.entry_id)
        assert len(rels) >= 1
        # Should be linked to entry_a via overlapping "embryo" tag
        related_ids = {r["item_a_id"] for r in rels} | {r["item_b_id"] for r in rels}
        assert entry_a.entry_id in related_ids

    def test_auto_linking_no_overlap(
        self, store: KBStore, sample_item_a: Item, sample_item_c: Item
    ) -> None:
        entry_a = store.store_entry(sample_item_a)
        entry_c = store.store_entry(sample_item_c)

        rels = store.get_item_relations(entry_c.entry_id)
        # No overlapping tags between IVF/embryo and AI/machine learning
        assert len(rels) == 0

    def test_auto_linking_different_domain(
        self, store: KBStore, sample_item_a: Item
    ) -> None:
        item_other = Item(
            id="item-other",
            source_name="test",
            source_type="api",
            source_url="https://example.com/other",
            title="Other",
            content="Other content.",
            collected_at="2026-07-20T00:00:00Z",
            domain="other-domain",
            topic_tags=["IVF"],
        )
        entry_a = store.store_entry(sample_item_a)
        entry_other = store.store_entry(item_other)

        rels = store.get_item_relations(entry_other.entry_id)
        # Different domain, so no auto-link despite tag overlap
        assert len(rels) == 0
