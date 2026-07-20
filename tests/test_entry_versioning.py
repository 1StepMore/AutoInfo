"""Tests for entry versioning (task 22 — .bak copies, history, restore)."""

from __future__ import annotations

from pathlib import Path

import pytest

from autoinfo.kb import KBStore, SQLiteIndex
from autoinfo.models import Item


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_versioning.db"


@pytest.fixture
def index(db_path: Path) -> SQLiteIndex:
    idx = SQLiteIndex(db_path)
    idx.init_db()
    return idx


@pytest.fixture
def store(tmp_path: Path) -> KBStore:
    kb_path = tmp_path / "knowledge"
    kb_path.mkdir(parents=True, exist_ok=True)
    return KBStore(base_path=kb_path)


@pytest.fixture
def sample_item() -> Item:
    return Item(
        id="item-v",
        source_name="test",
        source_type="api",
        source_url="https://example.com/v",
        title="Versioned entry",
        content="Original content.",
        collected_at="2026-07-20T00:00:00Z",
        domain="test-domain",
        topic_tags=["test"],
    )


class TestEntryVersioning:
    """Test versioning at the SQLiteIndex and KBStore levels."""

    def test_save_version_creates_bak(self, store: KBStore, sample_item: Item) -> None:
        # Store the entry first
        entry = store.store_entry(sample_item)
        assert entry.file_path

        fp = Path(entry.file_path)
        assert fp.is_file()

        # Save a version manually
        result = store.index.save_entry_version(
            entry_id=entry.entry_id,
            file_path=entry.file_path,
            comment="first backup",
        )
        assert result["saved"] is True
        assert result["version_num"] == 1

        bak_path = Path(result["file_path"])
        assert bak_path.is_file()
        assert bak_path.suffix == ".1"
        assert bak_path.name.endswith(".bak.1")

    def test_auto_version_on_update(self, store: KBStore, sample_item: Item) -> None:
        # First store
        entry = store.store_entry(sample_item)

        # Second store (same item_id triggers versioning in store_entry)
        item2 = Item(
            id="item-v2",
            source_name="test",
            source_type="api",
            source_url="https://example.com/v2",
            title="Versioned entry",
            content="Updated content.",
            collected_at="2026-07-20T01:00:00Z",
            domain="test-domain",
            topic_tags=["test"],
        )
        store.store_entry(item2)

        # Should have created a .bak for the first version
        history = store.get_entry_history(entry.entry_id)
        assert len(history) >= 1

    def test_get_entry_history_returns_versions(
        self, index: SQLiteIndex, tmp_path: Path
    ) -> None:
        from autoinfo.models import KBEntry

        entry = KBEntry(
            entry_id="hist-entry",
            title="History entry",
            domain="test",
            file_path=str(tmp_path / "test_history.md"),
        )
        index.index_entry(entry)

        # Create the file so versioning works
        fp = Path(entry.file_path)
        fp.write_text("---\nentry_id: hist-entry\n---\n\nBody", encoding="utf-8")

        index.save_entry_version("hist-entry", str(fp), "v1")
        index.save_entry_version("hist-entry", str(fp), "v2")

        history = index.get_entry_history("hist-entry")
        assert len(history) == 2
        assert history[0]["version_num"] == 2  # newest first
        assert history[1]["version_num"] == 1

    def test_max_versions_pruned(self, index: SQLiteIndex, tmp_path: Path) -> None:
        from autoinfo.models import KBEntry

        entry = KBEntry(
            entry_id="max-entry",
            title="Max versions entry",
            domain="test",
            file_path=str(tmp_path / "test_max.md"),
        )
        index.index_entry(entry)
        fp = Path(entry.file_path)
        fp.write_text("body", encoding="utf-8")

        # Save 7 versions — only 5 should remain
        for i in range(1, 8):
            index.save_entry_version("max-entry", str(fp), f"v{i}")

        history = index.get_entry_history("max-entry")
        assert len(history) == 5
        # Oldest version_num should be 3 (7 - 5 + 1)
        oldest = history[-1]["version_num"]
        assert oldest == 3

    def test_restore_entry_version(self, index: SQLiteIndex, tmp_path: Path) -> None:
        from autoinfo.models import KBEntry

        entry = KBEntry(
            entry_id="restore-entry",
            title="Restore entry",
            domain="test",
            file_path=str(tmp_path / "test_restore.md"),
        )
        index.index_entry(entry)
        fp = Path(entry.file_path)

        # Write v1 content
        fp.write_text("v1 content", encoding="utf-8")
        v1 = index.save_entry_version("restore-entry", str(fp), "v1 backup")

        # Write v2 content
        fp.write_text("v2 content", encoding="utf-8")
        v2 = index.save_entry_version("restore-entry", str(fp), "v2 backup")

        # Verify current content is v2
        assert fp.read_text(encoding="utf-8") == "v2 content"

        # Restore v1
        result = index.restore_entry_version(v1["version_id"])
        assert result["restored"] is True
        assert result["version_num"] == 1
        # File should now contain v1 content
        assert fp.read_text(encoding="utf-8") == "v1 content"

    def test_restore_nonexistent_version(self, index: SQLiteIndex) -> None:
        result = index.restore_entry_version("nonexistent-v99")
        assert result["restored"] is False
        assert "not found" in result.get("error", "")

    def test_save_version_missing_file(self, index: SQLiteIndex) -> None:
        result = index.save_entry_version("ghost-entry", "/nonexistent/file.md")
        assert result["saved"] is False
        assert "not found" in result.get("error", "")
