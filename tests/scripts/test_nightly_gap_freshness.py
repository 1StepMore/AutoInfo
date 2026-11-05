"""entries_freshness 口径回归（目标 2026-11-06 #1：新增 = 首次入库 + 窗口内发布）。

scripts/ is not a package — load it via sys.path like the sibling test files.
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

import nightly_gap  # noqa: E402  (sys.path insert above)

NOW = datetime(2026, 11, 5, 12, 0, 0, tzinfo=timezone.utc)


def _make_db(tmp_path: Path) -> Path:
    """Five rows exercising every bucket of the new caliber."""
    db = tmp_path / "autoinfo.db"
    con = sqlite3.connect(str(db))
    con.execute(
        "CREATE TABLE entries ("
        " entry_id TEXT PRIMARY KEY, domain TEXT, created_at TEXT,"
        " collected_at TEXT, dedup_status TEXT, deleted INTEGER DEFAULT 0)"
    )
    rows = [
        # (entry_id, created_at, collected_at, dedup_status, deleted)
        ("fresh-1", "2026-11-03T00:00:00", "2026-11-03T00:00:00", "unique", 0),
        ("stale-1", "2026-11-02T00:00:00", "2026-09-01T00:00:00", "unique", 0),
        ("dup-1", "2026-11-01T00:00:00", "2026-09-01T00:00:00", "duplicate", 0),
        ("old-1", "2026-09-01T00:00:00", "2026-09-01T00:00:00", "unique", 0),
        ("deleted-1", "2026-11-04T00:00:00", "2026-11-04T00:00:00", "unique", 1),
    ]
    con.executemany(
        "INSERT INTO entries (entry_id, domain, created_at, collected_at,"
        " dedup_status, deleted) VALUES (?, 'ai-commercial', ?, ?, ?, ?)",
        rows,
    )
    con.commit()
    con.close()
    return db


class TestEntriesFreshnessCaliber:
    def test_new_requires_first_ingest_and_recent_publication(self, tmp_path):
        db = _make_db(tmp_path)
        result = nightly_gap.entries_freshness(db, ["ai-commercial"], now=NOW)

        b = result["ai-commercial"]
        # 入库动作：fresh/stale/dup 三行（old 在窗口外，deleted 软删不计）
        assert b["entries_ingested_7d"] == 3
        # 真新增：只有 fresh-1
        assert b["entries_new_7d"] == 1
        # 旧文重采：stale-1（unique 但发布早于窗口）
        assert b["entries_new_7d_stale_content"] == 1
        # 重复入库：dup-1
        assert b["entries_dup_reingested_7d"] == 1

    def test_missing_collected_at_counts_as_new(self, tmp_path):
        """collected_at 缺失 → 无法证明陈旧 → 保守计入真新增。"""
        db = tmp_path / "autoinfo.db"
        con = sqlite3.connect(str(db))
        con.execute(
            "CREATE TABLE entries (entry_id TEXT PRIMARY KEY, domain TEXT,"
            " created_at TEXT, collected_at TEXT, dedup_status TEXT,"
            " deleted INTEGER DEFAULT 0)"
        )
        con.execute(
            "INSERT INTO entries (entry_id, domain, created_at, collected_at,"
            " dedup_status, deleted)"
            " VALUES ('no-date', 'ai-commercial', '2026-11-03T00:00:00',"
            " NULL, 'unique', 0)"
        )
        con.commit()
        con.close()

        result = nightly_gap.entries_freshness(db, ["ai-commercial"], now=NOW)
        b = result["ai-commercial"]
        assert b["entries_ingested_7d"] == 1
        assert b["entries_new_7d"] == 1
        assert b["entries_new_7d_stale_content"] == 0

    def test_new_caliber_beats_the_old_one_on_reingested_old_content(self, tmp_path):
        """守护口径本身：旧口径（created_at 计新增、不筛 duplicate）会把
        stale-1/dup-1 全算「新增」——这正是目标文档 603/555 现象的统计来源。"""
        db = _make_db(tmp_path)
        con = sqlite3.connect(str(db))
        old_caliber = con.execute(
            "SELECT COUNT(*) FROM entries"
            " WHERE created_at >= ? AND (deleted IS NULL OR deleted = 0)",
            ((NOW - timedelta(days=7)).isoformat(),),
        ).fetchone()[0]
        con.close()

        assert old_caliber == 3  # 旧口径的「近7天新增」
        result = nightly_gap.entries_freshness(db, ["ai-commercial"], now=NOW)
        assert result["ai-commercial"]["entries_new_7d"] == 1  # 新口径的真新增
