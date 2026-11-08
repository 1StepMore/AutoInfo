"""Collision-free KB entry ids and the legacy-id migration (issue #695)."""

from __future__ import annotations

import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from typing import Any

import yaml

from autoinfo.kb import KBStore, _source_fingerprint
from autoinfo.models import Item, KBEntry

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import migrate_entry_ids as migration  # noqa: E402


def _item(**overrides: Any) -> Item:
    data: dict[str, Any] = {
        "id": "item-1",
        "source_name": "test",
        "source_type": "api",
        "source_platform": "api",
        "source_url": "https://example.com/a",
        "title": "Same title",
        "content": "Body long enough to be stored as a real entry.",
        "content_type": "text",
        "collected_at": "2026-07-20T00:00:00Z",
        "language": "en",
        "domain": "medical-research",
        "topic_tags": ["general"],
    }
    data.update(overrides)
    return Item(**data)


def _write_entry(
    path: Path,
    entry_id: str,
    *,
    source_url: str,
    title: str = "Duplicate title",
    tier: str = "01-Raw",
    domain: str = "medical-research",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frontmatter = {
        "entry_id": entry_id,
        "domain": domain,
        "tier": tier,
        "source_url": source_url,
        "source_type": "api",
        "source_platform": "api",
        "collected_at": "2026-07-20T00:00:00Z",
        "title": title,
        "summary": "summary",
    }
    path.write_text(
        f"---\n{yaml.dump(frontmatter, sort_keys=False)}---\n\nBody text.\n",
        encoding="utf-8",
    )


class TestStoreEntryIdentity:
    def test_same_title_different_source_keeps_both_files_and_rows(self, tmp_path: Path) -> None:
        store = KBStore(base_path=tmp_path / "knowledge", min_content_chars=0)
        first = store.store_entry(_item())
        second = store.store_entry(_item(id="item-2", source_url="https://example.com/b"))

        assert first is not None and second is not None
        assert first.entry_id != second.entry_id
        assert first.file_path != second.file_path
        assert Path(first.file_path).is_file()
        assert Path(second.file_path).is_file()
        first_row = store.index.get_entry(first.entry_id)
        second_row = store.index.get_entry(second.entry_id)
        assert first_row is not None and second_row is not None
        assert first_row["file_path"] == first.file_path
        assert second_row["file_path"] == second.file_path

    def test_same_source_and_day_updates_one_entry(self, tmp_path: Path) -> None:
        store = KBStore(base_path=tmp_path / "knowledge", min_content_chars=0)
        first = store.store_entry(_item())
        again = store.store_entry(_item(id="item-1b", content="Updated body."))

        assert first is not None and again is not None
        assert again.entry_id == first.entry_id
        assert again.file_path == first.file_path
        assert store.index.get_entry(first.entry_id) is not None

    def test_empty_title_still_gets_a_distinct_id(self, tmp_path: Path) -> None:
        store = KBStore(base_path=tmp_path / "knowledge", min_content_chars=0)
        first = store.store_entry(_item(title=""))
        second = store.store_entry(_item(id="item-2", title="", source_url="https://example.com/b"))

        assert first is not None and second is not None
        assert first.entry_id != second.entry_id
        assert "medical-research-general-" not in first.entry_id
        assert "-entry-" in Path(first.file_path).name

    def test_fingerprint_is_stable_for_the_same_source(self) -> None:
        assert _source_fingerprint("https://example.com/a") == _source_fingerprint(
            "https://example.com/a"
        )
        assert _source_fingerprint("https://example.com/a") != _source_fingerprint(
            "https://example.com/b"
        )


class TestReindexCollisions:
    def test_duplicate_entry_ids_are_reported(self, tmp_path: Path) -> None:
        kb = tmp_path / "knowledge"
        store = KBStore(base_path=kb, min_content_chars=0)
        _write_entry(
            kb / "medical-research" / "01-Raw" / "general" / "a.md",
            "legacy-id",
            source_url="https://example.com/a",
        )
        _write_entry(
            kb / "medical-research" / "01-Raw" / "general" / "b.md",
            "legacy-id",
            source_url="https://example.com/b",
        )

        result = store.reindex_knowledge_base()

        assert any("duplicate entry_id" in error["error"] for error in result["errors"])
        assert result["files_found"] == 1

    def test_index_row_pointing_at_another_file_is_reported(self, tmp_path: Path) -> None:
        kb = tmp_path / "knowledge"
        store = KBStore(base_path=kb, min_content_chars=0)
        entry_file = kb / "medical-research" / "01-Raw" / "general" / "a.md"
        _write_entry(entry_file, "id-a", source_url="https://example.com/a")
        store.index.index_entry(
            KBEntry(
                entry_id="id-a",
                title="Duplicate title",
                domain="medical-research",
                tier="01-Raw",
                file_path=str(tmp_path / "elsewhere.md"),
            )
        )

        result = store.reindex_knowledge_base()

        assert any("indexed at" in error["error"] for error in result["errors"])


class TestEntryIdMigration:
    def _legacy_pair(self, kb: Path) -> tuple[Path, Path]:
        first = kb / "medical-research" / "01-Raw" / "general" / "2026-07-20-dup.md"
        second = kb / "medical-research" / "01-Raw" / "general" / "2026-07-20-dup-2.md"
        old_id = "medical-research-general-duplicate-title"
        _write_entry(first, old_id, source_url="https://example.com/a")
        _write_entry(second, old_id, source_url="https://example.com/b")
        return first, second

    def test_dry_run_apply_and_idempotency(self, tmp_path: Path) -> None:
        kb = tmp_path / "knowledge"
        first, second = self._legacy_pair(kb)
        store = KBStore(base_path=kb, min_content_chars=0)
        store.index.index_entry(
            KBEntry(
                entry_id="medical-research-general-duplicate-title",
                title="Duplicate title",
                domain="medical-research",
                tier="01-Raw",
                file_path=str(first),
            )
        )

        changes, errors, skipped = migration.plan_migration(kb)

        assert errors == []
        assert skipped == []
        assert len(changes) == 2
        assert first.is_file() and second.is_file()

        assert migration.apply_changes(changes) == []
        assert not first.exists()
        assert not second.exists()
        for change in changes:
            new_path = Path(change.new_path)
            assert new_path.is_file()
            assert "medical-research-2026-07-20-" in change.new_id
            frontmatter = yaml.safe_load(new_path.read_text(encoding="utf-8").split("---")[1])
            assert frontmatter["entry_id"] == change.new_id

        assert migration.rekey_index(tmp_path / "autoinfo.db", changes) == []
        reindexed = migration.rebuild_index(kb)
        assert reindexed["errors"] == []

        with closing(sqlite3.connect(tmp_path / "autoinfo.db")) as conn:
            ids = {row[0] for row in conn.execute("SELECT entry_id FROM entries")}
        assert "medical-research-general-duplicate-title" not in ids
        assert {change.new_id for change in changes} <= ids

        again, again_errors, _ = migration.plan_migration(kb)
        assert again_errors == []
        assert again == []

    def test_wiki_is_skipped_without_explicit_flag(self, tmp_path: Path) -> None:
        kb = tmp_path / "knowledge"
        wiki = kb / "medical-research" / "03-Wiki" / "general" / "2026-07-20-wiki.md"
        _write_entry(
            wiki,
            "medical-research-general-wiki",
            source_url="https://example.com/wiki",
            tier="03-Wiki",
        )

        changes, errors, skipped = migration.plan_migration(kb)
        assert changes == []
        assert errors == []
        assert len(skipped) == 1
        assert "append-only" in skipped[0]["reason"]
        assert wiki.is_file()

        included, included_errors, included_skipped = migration.plan_migration(
            kb, include_wiki=True
        )
        assert included_errors == []
        assert included_skipped == []
        assert len(included) == 1
