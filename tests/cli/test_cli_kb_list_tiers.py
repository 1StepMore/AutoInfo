"""Regression test for Bug #42.

Bug: In ``list_tiers()`` (``src/autoinfo/cli/kb.py:124``), the call
``store.list_kb_tier(domain=domain, tier=tier, limit=0, offset=0)``
passes ``limit=0`` to SQLite as ``LIMIT 0``, which returns 0 rows
regardless of how many entries exist — so every tier always shows
"0 entries".

Fix: Added ``count_entries_by_tier(domain, tier)`` to ``SQLiteIndex``
that uses ``SELECT COUNT(*)`` instead of ``SELECT * ... LIMIT 0``.
``KBStore`` delegates to the index. ``list_tiers()`` uses the new
count method.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from autoinfo.kb import KBStore, SQLiteIndex
from autoinfo.models import KBEntry


class TestCountEntriesByTier:
    """Verify ``count_entries_by_tier`` returns correct counts."""

    @pytest.fixture
    def db_path(self, tmp_path: Path) -> Path:
        return tmp_path / "test_autoinfo.db"

    @pytest.fixture
    def index(self, db_path: Path) -> SQLiteIndex:
        idx = SQLiteIndex(db_path)
        idx.init_db()
        return idx

    @pytest.fixture
    def store(self, db_path: Path) -> KBStore:
        return KBStore(db_path)

    def _insert(
        self, index: SQLiteIndex, entry_id: str, domain: str, tier: str
    ) -> None:
        index.index_entry(
            KBEntry(
                entry_id=entry_id,
                title=f"Title for {entry_id}",
                domain=domain,
                tier=tier,
                source_url=f"https://example.com/{entry_id}",
                source_type="api",
                source_platform="pubmed",
                collected_at="2026-07-20T10:00:00Z",
                tags=[],
            )
        )

    def test_count_returns_zero_for_empty_domain(self, index: SQLiteIndex) -> None:
        """No entries in domain → count is 0."""
        assert index.count_entries_by_tier("medical-research", "01-Raw") == 0

    def test_count_matches_inserted_entries(self, index: SQLiteIndex) -> None:
        """Insert 3 entries in 01-Raw → count returns 3."""
        for i in range(3):
            self._insert(index, f"raw-{i}", "medical-research", "01-Raw")
        assert index.count_entries_by_tier("medical-research", "01-Raw") == 3

    def test_count_respects_tier_filter(self, index: SQLiteIndex) -> None:
        """Entries in different tiers are counted independently."""
        self._insert(index, "raw-1", "medical-research", "01-Raw")
        self._insert(index, "raw-2", "medical-research", "01-Raw")
        self._insert(index, "draft-1", "medical-research", "02-Draft")
        assert index.count_entries_by_tier("medical-research", "01-Raw") == 2
        assert index.count_entries_by_tier("medical-research", "02-Draft") == 1
        assert index.count_entries_by_tier("medical-research", "03-Wiki") == 0

    def test_count_respects_domain_filter(self, index: SQLiteIndex) -> None:
        """Entries in different domains are counted independently."""
        self._insert(index, "med-1", "medical-research", "01-Raw")
        self._insert(index, "med-2", "medical-research", "01-Raw")
        self._insert(index, "ai-1", "ai-commercial", "01-Raw")
        assert index.count_entries_by_tier("medical-research", "01-Raw") == 2
        assert index.count_entries_by_tier("ai-commercial", "01-Raw") == 1

    # --- Bug regression: LIMIT 0 returns 0 rows ---

    def test_list_entries_limit_zero_returns_empty(self, index: SQLiteIndex) -> None:
        """Prove the bug: ``list_entries(limit=0)`` returns [].

        This is what the original ``list_tiers()`` was doing — the
        count method exists precisely to avoid this.
        """
        for i in range(3):
            self._insert(index, f"raw-{i}", "medical-research", "01-Raw")
        entries = index.list_entries_by_tier(
            "medical-research", "01-Raw", limit=0, offset=0
        )
        assert entries == [], (
            f"LIMIT 0 should return [], not {entries!r} — this is the bug!"
        )
        # Meanwhile count must return the real number
        assert index.count_entries_by_tier("medical-research", "01-Raw") == 3

    # --- KBStore delegation ---

    def test_store_delegates_count(self, store: KBStore) -> None:
        """KBStore.count_entries_by_tier delegates to the index correctly."""
        idx: SQLiteIndex = store.index  # type: ignore[assignment]
        for i in range(5):
            self._insert(idx, f"raw-{i}", "medical-research", "01-Raw")
        assert (
            store.count_entries_by_tier("medical-research", "01-Raw") == 5
        )
