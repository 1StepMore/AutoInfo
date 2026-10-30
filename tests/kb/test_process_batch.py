"""Tests for batch processing support — ``autoinfo.process``.

Covers:

- ``run_processing`` with ``batch_size > 0`` returns partial results
- ``get_processing_progress`` reflects current progress correctly
- Backward compatibility: ``batch_size=0`` processes all items
- Multiple batch calls process distinct slices without loss/duplication
- CLI ``--batch-size`` flag wiring
- MCP ``get_processing_progress`` tool wiring
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import ExitStack
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from autoinfo import process as process_module
from autoinfo.kb import KBStore
from autoinfo.llm import LLMExtractor
from autoinfo.models import ExtractionResult, Item, KBEntry
from autoinfo.process import (
    ProcessResult,
    get_processing_progress,
    run_processing,
)
from autoinfo.quality import QualityResult
from tests._ansi import strip_ansi
from tests._freshness import fresh_iso

# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def three_items() -> list[Item]:
    """Return three synthetic items for batch tests."""
    items = []
    for i in range(1, 4):
        items.append(
            Item(
                id=f"item-{i:03d}",
                source_name="pubmed",
                source_type="api",
                source_platform="pubmed",
                source_url=f"https://example.com/{i}",
                title=f"Test article {i}",
                content=f"Content of test article {i}.",
                content_type="text",
                collected_at=f"2026-07-{15 + i:02d}T10:00:00Z",
                language="en",
                domain="medical-research",
                topic_tags=["IVF"],
                quality_tier=1,
                raw_data={},
            )
        )
    return items


@pytest.fixture
def mock_extraction() -> ExtractionResult:
    """Standard mock extraction result."""
    return ExtractionResult(
        item_id="mock",
        title="Mock",
        tl_dr="A mock extraction.",
        key_points=["Point 1"],
        entities=[],
        relevance_score=80.0,
    )


def _all_pass_gates() -> dict[str, QualityResult]:
    """Quality gate results where all three gates pass."""
    return {
        "G1-SourceAuthority": QualityResult(
            gate_name="G1-SourceAuthority",
            passed=True,
            score=1.0,
            details={"quality_tier": 1, "source_name": "pubmed"},
        ),
        "G2-Dedup": QualityResult(
            gate_name="G2-Dedup",
            passed=True,
            score=1.0,
            details={"is_duplicate": False, "matched_by": None},
        ),
        "G3-RelevanceScoring": QualityResult(
            gate_name="G3-RelevanceScoring",
            passed=True,
            score=80.0,
            details={"hidden": False},
        ),
    }


def _mock_kb_store() -> MagicMock:
    """Return a mocked KBStore."""
    entry = KBEntry(entry_id="test", title="test", domain="test")
    store = MagicMock(spec=KBStore)
    store.store_entry.return_value = entry
    store.list_entries.return_value = []
    return store


# ===================================================================
# Test: run_processing with batch_size
# ===================================================================


class TestBatchProcessing:
    """``run_processing()`` with ``batch_size``."""

    def test_batch_returns_partial_results(
        self,
        three_items: list[Item],
        mock_extraction: ExtractionResult,
    ) -> None:
        """With batch_size=2, only 2 of 3 items are processed."""
        mock_ext = MagicMock(return_value=mock_extraction)
        mock_quality = MagicMock(return_value=_all_pass_gates())
        mock_store = _mock_kb_store()

        with (
            patch("autoinfo.process.load_cached_items", return_value=three_items),
            patch(
                "autoinfo.process._read_progress",
                return_value={"last_processed_index": 0, "total_items": 3},
            ),
            patch("autoinfo.process._read_processed_ids", return_value=set()),
            patch("autoinfo.process._mark_processed"),
            patch("autoinfo.process._write_progress") as mock_write,
            patch.object(LLMExtractor, "extract", mock_ext),
            patch("autoinfo.process.run_quality_gates", mock_quality),
            patch("autoinfo.process.KBStore", return_value=mock_store),
        ):
            result = run_processing("medical-research", batch_size=2)

        assert result.total_items == 3
        assert result.processed_count == 2
        assert result.remaining_count == 1
        assert result.is_complete is False
        assert result.kb_entries_created == 2
        assert len(result.per_item_logs) == 2

        # Progress was persisted
        mock_write.assert_called_once_with("medical-research", 2, 3)

    def test_batch_completes_when_batch_exceeds_remaining(
        self,
        three_items: list[Item],
        mock_extraction: ExtractionResult,
    ) -> None:
        """batch_size larger than remaining items sets is_complete=True."""
        mock_ext = MagicMock(return_value=mock_extraction)
        mock_quality = MagicMock(return_value=_all_pass_gates())
        mock_store = _mock_kb_store()

        # Start from index 2 (1 item remaining), batch=5 should get it all
        with (
            patch("autoinfo.process.load_cached_items", return_value=three_items),
            patch(
                "autoinfo.process._read_progress",
                return_value={"last_processed_index": 0, "total_items": 3},
            ),
            patch(
                "autoinfo.process._read_processed_ids",
                return_value={"item-001", "item-002"},
            ),
            patch("autoinfo.process._mark_processed"),
            patch("autoinfo.process._write_progress"),
            patch.object(LLMExtractor, "extract", mock_ext),
            patch("autoinfo.process.run_quality_gates", mock_quality),
            patch("autoinfo.process.KBStore", return_value=mock_store),
        ):
            result = run_processing("medical-research", batch_size=5)

        assert result.total_items == 3
        assert result.processed_count == 1
        assert result.remaining_count == 0
        assert result.is_complete is True

    def test_sequential_batches_no_loss_no_duplication(
        self,
        three_items: list[Item],
        mock_extraction: ExtractionResult,
    ) -> None:
        """Two sequential batch calls process items without overlap."""
        processed_ids: list[str] = []

        def track_extraction(item: Item, **kwargs: Any) -> ExtractionResult:
            processed_ids.append(item.id)
            return mock_extraction

        mock_ext = MagicMock(side_effect=track_extraction)
        mock_quality = MagicMock(return_value=_all_pass_gates())
        mock_store = _mock_kb_store()

        # Track the item-id ledger to simulate persistence between calls
        # (AutoInfo#596: the cursor is the set of processed ids).
        ledger: set[str] = set()

        def mock_read_ids(domain: str) -> set[str]:
            return set(ledger)

        def mock_mark(domain: str, item_ids: Any) -> None:
            ledger.update(str(i) for i in item_ids)

        def _run() -> ProcessResult:
            with ExitStack() as stack:
                stack.enter_context(
                    patch("autoinfo.process.load_cached_items", return_value=three_items)
                )
                stack.enter_context(
                    patch(
                        "autoinfo.process._read_processed_ids",
                        side_effect=mock_read_ids,
                    )
                )
                stack.enter_context(
                    patch("autoinfo.process._mark_processed", side_effect=mock_mark)
                )
                stack.enter_context(
                    patch(
                        "autoinfo.process._read_progress",
                        return_value={"last_processed_index": 0, "total_items": 3},
                    )
                )
                stack.enter_context(patch("autoinfo.process._write_progress"))
                stack.enter_context(patch.object(LLMExtractor, "extract", mock_ext))
                stack.enter_context(patch("autoinfo.process.run_quality_gates", mock_quality))
                stack.enter_context(patch("autoinfo.process.KBStore", return_value=mock_store))
                return run_processing("medical-research", batch_size=2)

        # First batch: process 2 items
        r1 = _run()

        assert r1.processed_count == 2
        assert r1.remaining_count == 1
        assert r1.is_complete is False
        # Parallel processing does not guarantee extraction call order
        assert sorted(processed_ids) == ["item-001", "item-002"]
        first_batch_ids = list(processed_ids)
        processed_ids.clear()
        assert ledger == {"item-001", "item-002"}

        # Second batch: process remaining 1 item
        r2 = _run()

        assert r2.processed_count == 1
        assert r2.remaining_count == 0
        assert r2.is_complete is True
        assert sorted(processed_ids) == ["item-003"]

        # Verify no overlap
        all_ids = first_batch_ids + processed_ids
        assert len(all_ids) == 3
        assert len(set(all_ids)) == 3  # all unique
        assert ledger == {"item-001", "item-002", "item-003"}

    def test_no_duplicates_on_restart(
        self,
        three_items: list[Item],
        mock_extraction: ExtractionResult,
    ) -> None:
        """Processed ids are skipped even when the cache shrank between runs."""
        processed_ids: list[str] = []

        def track_extraction(item: Item, **kwargs: Any) -> ExtractionResult:
            processed_ids.append(item.id)
            return mock_extraction

        mock_ext = MagicMock(side_effect=track_extraction)
        mock_quality = MagicMock(return_value=_all_pass_gates())
        mock_store = _mock_kb_store()

        # Simulate: the ledger says item-003 was processed, but only the
        # first two items are still in the cache.
        with (
            patch("autoinfo.process.load_cached_items", return_value=three_items[:2]),
            patch(
                "autoinfo.process._read_processed_ids",
                return_value={"item-001", "item-002", "item-003"},
            ),
            patch("autoinfo.process._write_progress"),
            patch.object(LLMExtractor, "extract", mock_ext),
            patch("autoinfo.process.run_quality_gates", mock_quality),
            patch("autoinfo.process.KBStore", return_value=mock_store),
        ):
            result = run_processing("medical-research", batch_size=5)

        # Every cached item was already processed => nothing to do, and
        # specifically nothing is reprocessed just because the cache shrank.
        assert result.total_items == 2
        assert result.processed_count == 0
        assert result.remaining_count == 0
        assert result.is_complete is True
        assert processed_ids == []

    def test_cache_change_does_not_reset_progress(
        self,
        three_items: list[Item],
        mock_extraction: ExtractionResult,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """A changed cache total no longer resets the id cursor.

        AutoInfo#596 regression: the old position cursor reset to 0 whenever
        ``persisted_total != total_items``.  With an id ledger the first two
        ids are already processed, so ``batch_size=2`` picks up exactly the
        one remaining item instead of reprocessing the whole cache.
        """
        processed_ids: list[str] = []

        def track_extraction(item: Item, **kwargs: Any) -> ExtractionResult:
            processed_ids.append(item.id)
            return mock_extraction

        mock_ext = MagicMock(side_effect=track_extraction)
        mock_quality = MagicMock(return_value=_all_pass_gates())
        mock_store = _mock_kb_store()

        # Keep the ledger write inside tmp_path — never touch the repo DB.
        monkeypatch.setattr(
            "autoinfo.process._get_progress_db_path", lambda: tmp_path / "autoinfo.db"
        )

        # Legacy row says total_items=5 while the cache holds 3 — the old code
        # treated that mismatch as "cache changed, start over".
        with (
            patch("autoinfo.process.load_cached_items", return_value=three_items),
            patch(
                "autoinfo.process._read_progress",
                return_value={"last_processed_index": 2, "total_items": 5},
            ),
            patch(
                "autoinfo.process._read_processed_ids",
                return_value={"item-001", "item-002"},
            ),
            patch("autoinfo.process._write_progress") as mock_write,
            patch.object(LLMExtractor, "extract", mock_ext),
            patch("autoinfo.process.run_quality_gates", mock_quality),
            patch("autoinfo.process.KBStore", return_value=mock_store),
        ):
            result = run_processing("medical-research", batch_size=2)

        # Only the pending id is processed; the two already-done ids are skipped.
        assert sorted(processed_ids) == ["item-003"]
        assert result.total_items == 3
        assert result.processed_count == 1
        assert result.remaining_count == 0
        assert result.is_complete is True
        mock_write.assert_called_once_with("medical-research", 3, 3)


class TestBatchBackwardCompatibility:
    """``batch_size=0`` processes all items (existing behaviour)."""

    def test_batch_size_zero_processes_all(
        self,
        three_items: list[Item],
        mock_extraction: ExtractionResult,
    ) -> None:
        """batch_size=0 (default) processes all items."""
        mock_ext = MagicMock(return_value=mock_extraction)
        mock_quality = MagicMock(return_value=_all_pass_gates())
        mock_store = _mock_kb_store()

        with (
            patch("autoinfo.process.load_cached_items", return_value=three_items),
            patch.object(LLMExtractor, "extract", mock_ext),
            patch("autoinfo.process.run_quality_gates", mock_quality),
            patch("autoinfo.process.KBStore", return_value=mock_store),
        ):
            result = run_processing("medical-research")

        assert result.total_items == 3
        assert result.processed_count == 3
        assert result.remaining_count == 0
        assert result.is_complete is True
        assert result.kb_entries_created == 3
        assert len(result.per_item_logs) == 3

    def test_batch_size_zero_no_progress_writes(
        self,
        three_items: list[Item],
        mock_extraction: ExtractionResult,
    ) -> None:
        """With batch_size=0, no progress is persisted."""
        mock_ext = MagicMock(return_value=mock_extraction)
        mock_quality = MagicMock(return_value=_all_pass_gates())
        mock_store = _mock_kb_store()

        with (
            patch("autoinfo.process.load_cached_items", return_value=three_items),
            patch("autoinfo.process._write_progress") as mock_write,
            patch.object(LLMExtractor, "extract", mock_ext),
            patch("autoinfo.process.run_quality_gates", mock_quality),
            patch("autoinfo.process.KBStore", return_value=mock_store),
        ):
            run_processing("medical-research")

        mock_write.assert_not_called()

    def test_empty_cache_with_batch(self, mock_extraction: ExtractionResult) -> None:
        """Empty cache with batch_size returns zero counts."""
        mock_ext = MagicMock(return_value=mock_extraction)
        mock_quality = MagicMock()
        mock_store = _mock_kb_store()

        with (
            patch("autoinfo.process.load_cached_items", return_value=[]),
            patch(
                "autoinfo.process._read_progress",
                return_value={"last_processed_index": 0, "total_items": 0},
            ),
            patch.object(LLMExtractor, "extract", mock_ext),
            patch("autoinfo.process.run_quality_gates", mock_quality),
            patch("autoinfo.process.KBStore", return_value=mock_store),
        ):
            result = run_processing("medical-research", batch_size=5)

        assert result.total_items == 0
        assert result.processed_count == 0
        assert result.remaining_count == 0
        assert result.is_complete is True


# ===================================================================
# Test: migration seed ordering (AutoInfo#663)
# ===================================================================


def _seed_item(item_id: str, collected_at: str) -> Item:
    return Item(
        id=item_id,
        source_name="pubmed",
        source_type="api",
        source_platform="pubmed",
        source_url=f"https://example.com/{item_id}",
        title=f"Article {item_id}",
        content=f"Content of {item_id}.",
        content_type="text",
        collected_at=collected_at,
        language="en",
        domain="medical-research",
        topic_tags=["IVF"],
        quality_tier=1,
        raw_data={},
    )


class TestMigrationSeedOrdering:
    """The one-shot ledger seed must follow the DEFAULT cache walk (#663).

    A pre-#596 domain has a legacy position cursor but an empty id ledger.
    The legacy semantics were "the first N items in default cache order were
    processed", so the seed prefix is defined against the default
    oldest-first walk of the FULL cache.  Deriving it from the list a run is
    about to process marks fresh content as already done under
    ``--newest-first`` (newest items first in the list) and under
    ``--since-days`` (the seed swallows the whole fresh window).
    """

    OLD1_COLLECTED = "2020-01-01T00:00:00Z"
    OLD2_COLLECTED = "2020-06-01T00:00:00Z"

    @staticmethod
    def _cache() -> tuple[list[Item], list[Item], list[Item]]:
        """Return (default walk, newest-first order, 7-day window)."""
        old1 = _seed_item("old-1", TestMigrationSeedOrdering.OLD1_COLLECTED)
        old2 = _seed_item("old-2", TestMigrationSeedOrdering.OLD2_COLLECTED)
        new1 = _seed_item("new-1", fresh_iso(1))
        new2 = _seed_item("new-2", fresh_iso(0))
        default_walk = [old1, old2, new1, new2]  # date dirs ascending
        newest_first = [new2, new1, old2, old1]
        window = [new1, new2]  # since_days=7 drops the 2020 items
        return default_walk, newest_first, window

    @staticmethod
    def _fake_loader(calls: list[tuple[int, bool]]):
        default_walk, newest_first_order, window = TestMigrationSeedOrdering._cache()

        def fake_load(
            domain: str,
            base_path: Any = "collections",
            *,
            since_days: int = 0,
            newest_first: bool = False,
        ) -> list[Item]:
            calls.append((since_days, newest_first))
            if since_days > 0:
                return list(window)
            if newest_first:
                return list(newest_first_order)
            return list(default_walk)

        return fake_load

    @pytest.fixture
    def isolated_db(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
        """Point the real progress DB at tmp_path — never the repo DB."""
        db_path = tmp_path / "autoinfo.db"
        monkeypatch.setattr("autoinfo.process._get_progress_db_path", lambda: db_path)
        monkeypatch.setattr("autoinfo.process.get_config_path", lambda: None)
        return db_path

    def _run(
        self,
        loader: Any,
        extracted: list[str],
        mock_extraction: ExtractionResult,
        **kwargs: Any,
    ) -> ProcessResult:
        def track_extraction(item: Item, **_: Any) -> ExtractionResult:
            extracted.append(item.id)
            return mock_extraction

        with (
            patch("autoinfo.process.load_cached_items", side_effect=loader),
            patch.object(LLMExtractor, "extract", side_effect=track_extraction),
            patch("autoinfo.process.run_quality_gates", MagicMock(return_value=_all_pass_gates())),
            patch("autoinfo.process.KBStore", return_value=_mock_kb_store()),
        ):
            return run_processing("medical-research", **kwargs)

    def test_newest_first_seed_marks_oldest_not_newest(
        self,
        mock_extraction: ExtractionResult,
        isolated_db: Path,
    ) -> None:
        """Under --newest-first the seed consumes the OLDEST prefix; the fresh items are processed."""
        calls: list[tuple[int, bool]] = []
        loader = self._fake_loader(calls)
        extracted: list[str] = []

        # Pre-#596 state: legacy cursor says the first 2 items are done, ledger empty.
        process_module._write_progress("medical-research", 2, 4)

        result = self._run(
            loader,
            extracted,
            mock_extraction,
            batch_size=2,
            resume_from="auto",
            newest_first=True,
        )

        assert sorted(extracted) == ["new-1", "new-2"]
        assert result.processed_count == 2
        # The seed re-derived its prefix from a default-order walk, not from
        # the newest-first list this run handed to the workers.
        assert (0, False) in calls
        assert (0, True) in calls
        assert process_module._read_processed_ids("medical-research") == {
            "old-1",
            "old-2",
            "new-1",
            "new-2",
        }

    def test_since_days_seed_spares_the_fresh_window(
        self,
        mock_extraction: ExtractionResult,
        isolated_db: Path,
    ) -> None:
        """Under --since-days the seed never consumes the fresh window itself."""
        calls: list[tuple[int, bool]] = []
        loader = self._fake_loader(calls)
        extracted: list[str] = []

        process_module._write_progress("medical-research", 2, 4)

        result = self._run(
            loader,
            extracted,
            mock_extraction,
            batch_size=4,
            resume_from="auto",
            since_days=7,
        )

        # Bug behaviour was: seed took windowed[:2] == the whole fresh window,
        # pending emptied out, and the run processed NOTHING.
        assert sorted(extracted) == ["new-1", "new-2"]
        assert result.processed_count == 2
        assert (7, False) in calls
        assert (0, False) in calls  # seed reload, no window
        assert process_module._read_processed_ids("medical-research") == {
            "old-1",
            "old-2",
            "new-1",
            "new-2",
        }

    def test_second_run_continues_from_persisted_ledger(
        self,
        mock_extraction: ExtractionResult,
        isolated_db: Path,
    ) -> None:
        """Ledger rows survive the run: the second batch picks up the rest.

        Mirrors the nightly shape — a backlog larger than one ``batch_size``:
        run 1 takes the two newest pending items, run 2 must continue with the
        next two instead of resetting to zero or re-seeding.
        """
        # 6-item cache: legacy prefix (old-1, old-2) + four fresh items.
        # Default walk (date dirs ascending): old-1, old-2, new-4 … new-1.
        default_walk = [
            _seed_item("old-1", self.OLD1_COLLECTED),
            _seed_item("old-2", self.OLD2_COLLECTED),
            _seed_item("new-4", fresh_iso(4)),
            _seed_item("new-3", fresh_iso(3)),
            _seed_item("new-2", fresh_iso(2)),
            _seed_item("new-1", fresh_iso(1)),
        ]
        newest_order = list(reversed(default_walk))

        def fake_load(
            domain: str,
            base_path: Any = "collections",
            *,
            since_days: int = 0,
            newest_first: bool = False,
        ) -> list[Item]:
            return list(newest_order) if newest_first else list(default_walk)

        extracted: list[str] = []

        process_module._write_progress("medical-research", 2, 6)
        self._run(
            fake_load,
            extracted,
            mock_extraction,
            batch_size=2,
            resume_from="auto",
            newest_first=True,
        )
        assert sorted(extracted) == ["new-1", "new-2"]

        extracted.clear()
        result = self._run(
            fake_load,
            extracted,
            mock_extraction,
            batch_size=2,
            resume_from="auto",
            newest_first=True,
        )

        # The next pending slice — not a reset to zero, not a re-seed.
        assert sorted(extracted) == ["new-3", "new-4"]
        assert result.processed_count == 2
        assert result.is_complete is True
        assert process_module._read_processed_ids("medical-research") == {
            "old-1",
            "old-2",
            "new-1",
            "new-2",
            "new-3",
            "new-4",
        }


# ===================================================================
# Test: ledger write resilience (AutoInfo#663)
# ===================================================================


class TestLedgerWriteResilience:
    """Cursor/ledger writes retry SQLite contention, then fail LOUD."""

    @pytest.fixture
    def isolated_db(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(
            "autoinfo.process._get_progress_db_path", lambda: tmp_path / "autoinfo.db"
        )
        monkeypatch.setattr("autoinfo.process._LEDGER_RETRY_SLEEP_S", 0.0)

    def test_mark_processed_retries_on_lock(self, isolated_db: None) -> None:
        real_connect = process_module._connect_progress_db
        attempts = {"n": 0}

        def flaky_connect() -> sqlite3.Connection:
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise sqlite3.OperationalError("database is locked")
            return real_connect()

        with patch("autoinfo.process._connect_progress_db", side_effect=flaky_connect):
            process_module._mark_processed("d-resilience", ["a", "b"])

        assert attempts["n"] == 2
        assert process_module._read_processed_ids("d-resilience") == {"a", "b"}

    def test_mark_processed_exhaustion_is_loud_not_fatal(
        self, isolated_db: None, caplog: pytest.LogCaptureFixture
    ) -> None:
        def locked_connect() -> sqlite3.Connection:
            raise sqlite3.OperationalError("database is locked")

        with (
            patch("autoinfo.process._connect_progress_db", side_effect=locked_connect),
            caplog.at_level(logging.ERROR, logger="autoinfo.process"),
        ):
            process_module._mark_processed("d-resilience", ["a"])  # must not raise

        assert any(
            "ledger" in rec.getMessage() or "processed" in rec.getMessage()
            for rec in caplog.records
            if rec.levelno == logging.ERROR
        )
        assert process_module._read_processed_ids("d-resilience") == set()

    def test_write_progress_retries_on_lock(self, isolated_db: None) -> None:
        real_connect = process_module._connect_progress_db
        attempts = {"n": 0}

        def flaky_connect() -> sqlite3.Connection:
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise sqlite3.OperationalError("database is locked")
            return real_connect()

        with patch("autoinfo.process._connect_progress_db", side_effect=flaky_connect):
            process_module._write_progress("d-resilience", 7, 10)

        assert attempts["n"] == 2
        assert process_module._read_progress("d-resilience") == {
            "last_processed_index": 7,
            "total_items": 10,
        }


# ===================================================================
# Test: get_processing_progress
# ===================================================================


class TestGetProcessingProgress:
    """``get_processing_progress()``."""

    def test_returns_partial_progress(self) -> None:
        """Partial processing is reflected correctly."""
        with patch(
            "autoinfo.process._read_progress",
            return_value={"last_processed_index": 3, "total_items": 10},
        ):
            progress = get_processing_progress(domain="medical-research")

        assert progress["total_items"] == 10
        assert progress["processed_count"] == 3
        assert progress["remaining_count"] == 7
        assert progress["is_complete"] is False

    def test_returns_complete(self) -> None:
        """All items processed shows is_complete=True."""
        with patch(
            "autoinfo.process._read_progress",
            return_value={"last_processed_index": 10, "total_items": 10},
        ):
            progress = get_processing_progress(domain="medical-research")

        assert progress["processed_count"] == 10
        assert progress["remaining_count"] == 0
        assert progress["is_complete"] is True

    def test_returns_no_progress(self) -> None:
        """No progress recorded shows zeroes and is_complete=True."""
        with patch(
            "autoinfo.process._read_progress",
            return_value={"last_processed_index": 0, "total_items": 0},
        ):
            progress = get_processing_progress(domain="medical-research")

        assert progress["total_items"] == 0
        assert progress["processed_count"] == 0
        assert progress["remaining_count"] == 0
        assert progress["is_complete"] is True

    def test_returns_full_before_any_batch(self) -> None:
        """Before any batch call, progress shows zero processed."""
        with patch(
            "autoinfo.process._read_progress",
            return_value={"last_processed_index": 0, "total_items": 10},
        ):
            progress = get_processing_progress(domain="medical-research")

        assert progress["total_items"] == 10
        assert progress["processed_count"] == 0
        assert progress["remaining_count"] == 10
        assert progress["is_complete"] is False


# ===================================================================
# Test: CLI batch-size flag
# ===================================================================


class TestBatchCli:
    """``autoinfo process --batch-size`` CLI flag."""

    def test_batch_size_in_help(self, cli_runner) -> None:
        """--help shows --batch-size flag."""
        from autoinfo.cli import app

        result = cli_runner.invoke(app, ["process", "--help"])
        assert result.exit_code == 0
        assert "--batch-size" in strip_ansi(result.stdout)

    def test_batch_size_passed_to_run_processing(self, cli_runner) -> None:
        """--batch-size 2 is passed to run_processing()."""
        from autoinfo.cli import app

        mock_proc = MagicMock(
            return_value=ProcessResult(
                domain="test-domain",
                total_items=5,
                processed_count=2,
                remaining_count=3,
                is_complete=False,
            )
        )

        with patch("autoinfo.cli.process.run_processing", mock_proc):
            result = cli_runner.invoke(
                app,
                [
                    "process",
                    "--domain",
                    "test-domain",
                    "--batch-size",
                    "2",
                ],
            )

        assert result.exit_code == 0
        mock_proc.assert_called_once_with(
            domain="test-domain",
            topic=None,
            model=None,
            batch_size=2,
            check_factual=False,
            check_translation=False,
            resume_from=None,
            since_days=0,
            newest_first=False,
        )

    def test_batch_progress_shown_in_human_output(self, cli_runner) -> None:
        """Incomplete batch shows progress message."""
        from autoinfo.cli import app

        mock_proc = MagicMock(
            return_value=ProcessResult(
                domain="test-domain",
                total_items=5,
                processed_count=2,
                remaining_count=3,
                is_complete=False,
            )
        )

        with patch("autoinfo.cli.process.run_processing", mock_proc):
            result = cli_runner.invoke(
                app,
                [
                    "process",
                    "--domain",
                    "test-domain",
                ],
            )

        assert result.exit_code == 0
        assert "incomplete" in strip_ansi(result.stdout)
        assert "2 processed" in strip_ansi(result.stdout)
        assert "3 remaining" in strip_ansi(result.stdout)

    def test_batch_progress_hidden_when_complete(self, cli_runner) -> None:
        """Complete batch hides the progress message."""
        from autoinfo.cli import app

        mock_proc = MagicMock(
            return_value=ProcessResult(
                domain="test-domain",
                total_items=3,
                processed_count=3,
                remaining_count=0,
                is_complete=True,
            )
        )

        with patch("autoinfo.cli.process.run_processing", mock_proc):
            result = cli_runner.invoke(
                app,
                [
                    "process",
                    "--domain",
                    "test-domain",
                ],
            )

        assert result.exit_code == 0
        assert "incomplete" not in result.stdout


# ===================================================================
# Test: MCP tool wiring
# ===================================================================


class TestBatchMCP:
    """MCP server dispatches batch_size to run_processing."""

    @patch("autoinfo.process.run_processing")
    def test_mcp_passes_batch_size(self, mock_proc: MagicMock) -> None:
        """MCP process_collection passes batch_size kwarg."""
        from autoinfo.mcp.server import _handle_process_collection

        mock_proc.return_value = ProcessResult(
            domain="med",
            total_items=10,
            processed_count=3,
            is_complete=False,
        )

        result = _handle_process_collection(domain="med", batch_size=3)

        mock_proc.assert_called_once_with(domain="med", batch_size=3)
        assert result["is_complete"] is False
        assert result["processed_count"] == 3

    @patch("autoinfo.process.get_processing_progress")
    def test_mcp_get_progress(self, mock_progress: MagicMock) -> None:
        """MCP get_processing_progress returns progress data."""
        from autoinfo.mcp.server import _handle_get_processing_progress

        mock_progress.return_value = {
            "total_items": 10,
            "processed_count": 3,
            "remaining_count": 7,
            "is_complete": False,
        }

        result = _handle_get_processing_progress(domain="med")

        assert result["total_items"] == 10
        assert result["remaining_count"] == 7
