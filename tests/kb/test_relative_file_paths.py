"""KB index ``file_path`` values are KB-relative and resolve on read (#695)."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import yaml

from autoinfo.kb import KBStore, SQLiteIndex
from autoinfo.models import KBEntry

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import migrate_entry_ids as migration  # noqa: E402


def _write_entry(path: Path, entry_id: str, domain: str = "test-domain") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frontmatter = {
        "entry_id": entry_id,
        "domain": domain,
        "tier": "01-Raw",
        "source_url": "https://example.com/relative",
        "source_type": "api",
        "source_platform": "api",
        "collected_at": "2026-07-20T00:00:00Z",
        "title": "Relative path entry",
        "summary": "summary",
    }
    path.write_text(
        f"---\n{yaml.dump(frontmatter, sort_keys=False)}---\n\nBody text for the entry.\n",
        encoding="utf-8",
    )
    return path


def _raw_file_path(db_path: Path, entry_id: str) -> str:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT file_path FROM entries WHERE entry_id = ?", (entry_id,)
        ).fetchone()
    assert row is not None
    return str(row[0])


def test_sqlite_index_stores_relative_and_reads_absolute(tmp_path: Path) -> None:
    kb = tmp_path / "knowledge"
    entry_file = _write_entry(
        kb / "test-domain" / "01-Raw" / "topic" / "2026-07-20-entry.md",
        "relative-entry",
    )
    db_path = tmp_path / "autoinfo.db"
    index = SQLiteIndex(db_path, base_path=kb)
    index.init_db()

    index.index_entry(
        KBEntry(
            entry_id="relative-entry",
            title="Relative path entry",
            domain="test-domain",
            file_path=str(entry_file),
        )
    )

    assert _raw_file_path(db_path, "relative-entry") == (
        "test-domain/01-Raw/topic/2026-07-20-entry.md"
    )
    meta = index.get_entry("relative-entry")
    assert meta is not None
    assert meta["file_path"] == str(entry_file.resolve())


def test_kbstore_indexes_relative_and_resolves_public_reads(tmp_path: Path) -> None:
    kb = tmp_path / "knowledge"
    entry_file = _write_entry(
        kb / "test-domain" / "01-Raw" / "topic" / "2026-07-20-entry.md",
        "relative-entry",
    )
    store = KBStore(base_path=kb)

    result = store.reindex_knowledge_base()
    assert result["errors"] == []
    assert _raw_file_path(tmp_path / "autoinfo.db", "relative-entry") == (
        "test-domain/01-Raw/topic/2026-07-20-entry.md"
    )

    full = store.get_entry("relative-entry")
    assert full is not None
    assert full["file_path"] == str(entry_file.resolve())
    assert "Body text for the entry." in full["content"]

    by_absolute = store.get_entry_by_path(str(entry_file))
    assert by_absolute is not None
    assert by_absolute["entry_id"] == "relative-entry"
    by_relative = store.get_entry_by_path("test-domain/01-Raw/topic/2026-07-20-entry.md")
    assert by_relative is not None
    assert by_relative["entry_id"] == "relative-entry"

    version = store.index.save_entry_version("relative-entry", str(entry_file), "v1")
    assert version["saved"] is True
    with sqlite3.connect(tmp_path / "autoinfo.db") as conn:
        stored_version = conn.execute(
            "SELECT file_path FROM entry_versions WHERE version_id = ?",
            (version["version_id"],),
        ).fetchone()
    assert stored_version is not None
    assert not Path(stored_version[0]).is_absolute()
    history = store.get_entry_history("relative-entry")
    assert Path(history[0]["file_path"]).is_absolute()


def test_normalize_index_paths_rewrites_legacy_absolute_paths(tmp_path: Path) -> None:
    kb = tmp_path / "knowledge"
    entry_file = _write_entry(
        kb / "test-domain" / "01-Raw" / "topic" / "2026-07-20-entry.md",
        "relative-entry",
    )
    db_path = tmp_path / "autoinfo.db"
    index = SQLiteIndex(db_path, base_path=kb)
    index.init_db()
    index.index_entry(
        KBEntry(
            entry_id="relative-entry",
            title="Relative path entry",
            domain="test-domain",
            file_path=str(entry_file),
        )
    )
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE entries SET file_path = ? WHERE entry_id = ?",
            (str(entry_file), "relative-entry"),
        )

    dry_run = migration.normalize_index_paths(db_path, kb, apply=False)
    assert dry_run == {"entries": 1, "versions": 0}
    assert Path(_raw_file_path(db_path, "relative-entry")).is_absolute()

    applied = migration.normalize_index_paths(db_path, kb, apply=True)
    assert applied == {"entries": 1, "versions": 0}
    assert _raw_file_path(db_path, "relative-entry") == (
        "test-domain/01-Raw/topic/2026-07-20-entry.md"
    )
    assert migration.normalize_index_paths(db_path, kb, apply=False) == {
        "entries": 0,
        "versions": 0,
    }
