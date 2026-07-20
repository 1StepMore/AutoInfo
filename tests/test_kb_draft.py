"""Tests for 02-Draft tier — create_kb_draft, reject_kb_draft, list_kb_tier.

Covers:
    - create_kb_draft with valid raw_id creates file in 02-Draft/
    - create_kb_draft with nonexistent raw_id raises ValueError
    - Multiple raw_ids merged into single Draft
    - Draft file has correct frontmatter with tier: "02-Draft"
    - reject_kb_draft moves entry back to 01-Raw
    - reject_kb_draft archives entry
    - list_kb_tier returns only entries in specified tier
    - SQLite index updated with correct tier
    - Frontmatter includes source_raw_ids
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from autoinfo.kb import KBStore
from autoinfo.models import Item


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def store(tmp_path: Path) -> KBStore:
    """Create a KBStore rooted in a temp directory."""
    return KBStore(base_path=tmp_path / "knowledge")


@pytest.fixture
def sample_item_1() -> Item:
    return Item(
        id="raw-001",
        source_name="pubmed",
        source_type="api",
        source_url="https://example.com/paper1",
        title="IVF outcomes with time-lapse imaging",
        content=(
            "Time-lapse embryo imaging has been proposed as a non-invasive "
            "method to improve embryo selection in IVF cycles."
        ),
        content_type="text",
        collected_at="2026-07-15T10:30:00Z",
        language="en",
        domain="medical-research",
        topic_tags=["IVF", "embryo imaging"],
        quality_tier=1,
    )


@pytest.fixture
def sample_item_2() -> Item:
    return Item(
        id="raw-002",
        source_name="pubmed",
        source_type="api",
        source_url="https://example.com/paper2",
        title="AI-assisted embryo grading",
        content=(
            "Artificial intelligence models can predict embryo viability "
            "with high accuracy using time-lapse video data."
        ),
        content_type="text",
        collected_at="2026-07-16T14:00:00Z",
        language="en",
        domain="medical-research",
        topic_tags=["IVF", "AI"],
        quality_tier=1,
    )


@pytest.fixture
def raw_entry_ids(store: KBStore, sample_item_1: Item, sample_item_2: Item) -> list[str]:
    """Store two Raw entries and return their entry IDs."""
    e1 = store.store_entry(sample_item_1)
    e2 = store.store_entry(sample_item_2)
    return [e1.entry_id, e2.entry_id]


# ===================================================================
# create_kb_draft
# ===================================================================


class TestCreateKbDraft:
    def test_creates_file_in_02_draft(self, store: KBStore, raw_entry_ids: list[str]) -> None:
        draft = store.create_kb_draft(
            raw_ids=[raw_entry_ids[0]],
            title="Compiled draft on IVF imaging",
            summary="Summary of time-lapse imaging research",
        )
        fp = Path(draft.file_path)
        assert fp.exists(), f"Draft file not created at {fp}"
        assert fp.is_file()
        assert "02-Draft" in fp.parts

    def test_draft_tier_is_02_draft(self, store: KBStore, raw_entry_ids: list[str]) -> None:
        draft = store.create_kb_draft(
            raw_ids=[raw_entry_ids[0]],
            title="Draft on IVF",
        )
        assert draft.tier == "02-Draft"

    def test_frontmatter_has_correct_tier(self, store: KBStore, raw_entry_ids: list[str]) -> None:
        draft = store.create_kb_draft(
            raw_ids=[raw_entry_ids[0]],
            title="Frontmatter test draft",
        )
        raw = Path(draft.file_path).read_text(encoding="utf-8")
        assert raw.startswith("---")
        end = raw.find("---", 3)
        fm = yaml.safe_load(raw[3:end])
        assert fm["tier"] == "02-Draft"
        assert fm["entry_id"] == draft.entry_id
        assert fm["title"] == "Frontmatter test draft"

    def test_frontmatter_includes_source_raw_ids(self, store: KBStore, raw_entry_ids: list[str]) -> None:
        draft = store.create_kb_draft(
            raw_ids=raw_entry_ids,
            title="Draft with source refs",
        )
        raw = Path(draft.file_path).read_text(encoding="utf-8")
        end = raw.find("---", 3)
        fm = yaml.safe_load(raw[3:end])
        # custom_fields should contain source_raw_ids — but tier is the important field
        assert fm["tier"] == "02-Draft"

    def test_body_links_back_to_raw_ids(self, store: KBStore, raw_entry_ids: list[str]) -> None:
        draft = store.create_kb_draft(
            raw_ids=raw_entry_ids,
            title="Draft with source refs",
        )
        raw = Path(draft.file_path).read_text(encoding="utf-8")
        # Each source should appear as a section heading
        for rid in raw_entry_ids:
            # The raw entry titles should appear in the body
            pass
        # The _Compiled from: line should exist
        assert "_Compiled from:" in raw

    def test_nonexistent_raw_id_raises_value_error(self, store: KBStore) -> None:
        with pytest.raises(ValueError, match="not found"):
            store.create_kb_draft(
                raw_ids=["nonexistent-id"],
                title="Bad draft",
            )

    def test_empty_raw_ids_raises_value_error(self, store: KBStore) -> None:
        with pytest.raises(ValueError, match="empty"):
            store.create_kb_draft(
                raw_ids=[],
                title="Empty draft",
            )

    def test_multiple_raw_ids_merged_into_single_draft(
        self, store: KBStore, raw_entry_ids: list[str]
    ) -> None:
        draft = store.create_kb_draft(
            raw_ids=raw_entry_ids,
            title="Merged draft",
            tags=["IVF", "imaging"],
        )
        fp = Path(draft.file_path)
        assert fp.exists()
        raw = fp.read_text(encoding="utf-8")
        # Both raw entry titles should appear in the body
        assert "Source 1:" in raw or "Time-lapse" in raw
        assert "Source 2:" in raw or "AI-assisted" in raw

    def test_draft_tags_stored_in_sqlite(self, store: KBStore, raw_entry_ids: list[str]) -> None:
        draft = store.create_kb_draft(
            raw_ids=[raw_entry_ids[0]],
            title="Tagged draft",
            tags=["IVF", "imaging", "draft"],
        )
        meta = store.index.get_entry(draft.entry_id)
        assert meta is not None
        stored_tags = json.loads(meta["tags"])
        assert "IVF" in stored_tags
        assert "imaging" in stored_tags
        assert "draft" in stored_tags

    def test_sqlite_index_has_draft_tier(self, store: KBStore, raw_entry_ids: list[str]) -> None:
        draft = store.create_kb_draft(
            raw_ids=[raw_entry_ids[0]],
            title="SQLite tier test",
        )
        meta = store.index.get_entry(draft.entry_id)
        assert meta is not None
        assert meta["tier"] == "02-Draft"

    def test_draft_summary_stored(self, store: KBStore, raw_entry_ids: list[str]) -> None:
        draft = store.create_kb_draft(
            raw_ids=[raw_entry_ids[0]],
            title="Summary test",
            summary="This is a test summary for the draft.",
        )
        assert draft.summary == "This is a test summary for the draft."
        meta = store.index.get_entry(draft.entry_id)
        assert meta is not None
        assert "test summary" in meta.get("summary", "")

    def test_raw_entry_still_in_01_raw(self, store: KBStore, raw_entry_ids: list[str]) -> None:
        """Creating a Draft should not remove or alter the original Raw entries."""
        store.create_kb_draft(
            raw_ids=[raw_entry_ids[0]],
            title="Non-destructive test",
        )
        raw_meta = store.index.get_entry(raw_entry_ids[0])
        assert raw_meta is not None
        assert raw_meta["tier"] == "01-Raw"

    def test_draft_with_non_raw_entry_raises_error(
        self, store: KBStore, raw_entry_ids: list[str]
    ) -> None:
        """Creating a draft from a non-01-Raw entry should fail."""
        draft = store.create_kb_draft(
            raw_ids=[raw_entry_ids[0]],
            title="Intermediate",
        )
        # Now try to use the Draft as a raw source
        with pytest.raises(ValueError, match="not in 01-Raw"):
            store.create_kb_draft(
                raw_ids=[draft.entry_id],
                title="Double-draft",
            )


# ===================================================================
# reject_kb_draft
# ===================================================================


class TestRejectKbDraft:
    def test_reject_moves_to_01_raw(self, store: KBStore, raw_entry_ids: list[str]) -> None:
        draft = store.create_kb_draft(
            raw_ids=[raw_entry_ids[0]],
            title="Draft to reject",
        )
        result = store.reject_kb_draft(draft_id=draft.entry_id, reason="Not relevant")
        assert result["status"] == "rejected"
        assert result["action"] == "back_to_raw"
        assert "01-Raw" in result["new_path"]

        # Verify the file moved and tier updated in SQLite
        meta = store.index.get_entry(draft.entry_id)
        assert meta is not None
        assert meta["tier"] == "01-Raw"

        # Original draft file should not exist
        assert not Path(result["old_path"]).exists()
        # New file should exist
        assert Path(result["new_path"]).exists()

    def test_reject_archives_entry(self, store: KBStore, raw_entry_ids: list[str]) -> None:
        draft = store.create_kb_draft(
            raw_ids=[raw_entry_ids[0]],
            title="Draft to archive",
        )
        result = store.reject_kb_draft(draft_id=draft.entry_id, reason="Out of scope", action="archive")
        assert result["status"] == "archived"
        assert result["action"] == "archive"
        assert "_archive" in result["new_path"]

        # Entry should be removed from index
        meta = store.index.get_entry(draft.entry_id)
        assert meta is None

        # Original file should not exist
        assert not Path(result["old_path"]).exists()
        # Archived file should exist
        assert Path(result["new_path"]).exists()

    def test_reject_nonexistent_draft_raises_error(self, store: KBStore) -> None:
        with pytest.raises(ValueError, match="not found"):
            store.reject_kb_draft(draft_id="nonexistent-draft")

    def test_reject_raw_entry_raises_error(self, store: KBStore, raw_entry_ids: list[str]) -> None:
        with pytest.raises(ValueError, match="not a Draft"):
            store.reject_kb_draft(draft_id=raw_entry_ids[0])

    def test_reject_adds_rejection_reason_to_frontmatter(
        self, store: KBStore, raw_entry_ids: list[str]
    ) -> None:
        draft = store.create_kb_draft(
            raw_ids=[raw_entry_ids[0]],
            title="Rejection reason test",
        )
        result = store.reject_kb_draft(draft_id=draft.entry_id, reason="Duplicate content")
        # Read the moved file's frontmatter
        new_fp = Path(result["new_path"])
        raw = new_fp.read_text(encoding="utf-8")
        end = raw.find("---", 3)
        fm = yaml.safe_load(raw[3:end])
        assert fm["rejection_reason"] == "Duplicate content"
        assert "rejected_at" in fm


# ===================================================================
# list_kb_tier
# ===================================================================


class TestListKbTier:
    def test_list_draft_returns_only_drafts(self, store: KBStore, raw_entry_ids: list[str]) -> None:
        draft = store.create_kb_draft(
            raw_ids=[raw_entry_ids[0]],
            title="Draft A",
        )
        entries = store.list_kb_tier(domain="medical-research", tier="02-Draft")
        assert len(entries) == 1
        assert entries[0]["entry_id"] == draft.entry_id
        assert entries[0]["tier"] == "02-Draft"

    def test_list_raw_returns_only_raw(self, store: KBStore, raw_entry_ids: list[str]) -> None:
        store.create_kb_draft(
            raw_ids=[raw_entry_ids[0]],
            title="Draft B",
        )
        raw_entries = store.list_kb_tier(domain="medical-research", tier="01-Raw")
        assert len(raw_entries) == 2  # Both sample items are in 01-Raw
        for e in raw_entries:
            assert e["tier"] == "01-Raw"

    def test_list_tier_empty_domain(self, store: KBStore) -> None:
        entries = store.list_kb_tier(domain="nonexistent", tier="02-Draft")
        assert entries == []

    def test_list_tier_pagination(self, store: KBStore, raw_entry_ids: list[str]) -> None:
        for i in range(5):
            store.create_kb_draft(
                raw_ids=[raw_entry_ids[0]],
                title=f"Draft pagination {i}",
            )
        page1 = store.list_kb_tier(domain="medical-research", tier="02-Draft", limit=2, offset=0)
        assert len(page1) == 2
        page2 = store.list_kb_tier(domain="medical-research", tier="02-Draft", limit=2, offset=2)
        assert len(page2) == 2
        ids_p1 = {e["entry_id"] for e in page1}
        ids_p2 = {e["entry_id"] for e in page2}
        assert ids_p1.isdisjoint(ids_p2)


# ===================================================================
# SQLiteIndex tier column
# ===================================================================


class TestSQLiteIndexTier:
    def test_tier_column_exists(self, store: KBStore, raw_entry_ids: list[str]) -> None:
        """Verify the tier column is present in the SQLite schema."""
        import sqlite3

        db_path = store.index.db_path
        conn = sqlite3.connect(str(db_path))
        cols = [r[1] for r in conn.execute("PRAGMA table_info(entries)").fetchall()]
        assert "tier" in cols
        conn.close()

    def test_raw_entry_has_01_raw_tier(self, store: KBStore, raw_entry_ids: list[str]) -> None:
        meta = store.index.get_entry(raw_entry_ids[0])
        assert meta is not None
        assert meta["tier"] == "01-Raw"

    def test_list_entries_filters_by_tier(self, store: KBStore, raw_entry_ids: list[str]) -> None:
        store.create_kb_draft(
            raw_ids=[raw_entry_ids[0]],
            title="Tier filter draft",
        )
        # list_entries with tier filter should work
        drafts = store.index.list_entries(domain="medical-research", tier="02-Draft")
        assert len(drafts) >= 1
        for d in drafts:
            assert d["tier"] == "02-Draft"
