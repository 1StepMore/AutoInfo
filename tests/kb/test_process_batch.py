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

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

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
        mock_write.assert_called_once_with(
            "medical-research", 2, 3, processed_ids=["item-001", "item-002"]
        )

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
                return_value={"last_processed_index": 2, "total_items": 3},
            ),
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

        # Track progress writes to simulate persistence between calls
        progress_store: dict = {}

        def mock_read(domain: str) -> dict:
            return progress_store.get(
                domain, {"last_processed_index": 0, "total_items": len(three_items)}
            )

        def mock_write(domain: str, index: int, total: int, processed_ids=None) -> None:
            progress_store[domain] = {
                "last_processed_index": index,
                "total_items": total,
                "processed_ids": sorted(processed_ids or []),
            }

        patches = [
            patch("autoinfo.process.load_cached_items", return_value=three_items),
            patch("autoinfo.process._read_progress", side_effect=mock_read),
            patch("autoinfo.process._write_progress", side_effect=mock_write),
            patch.object(LLMExtractor, "extract", mock_ext),
            patch("autoinfo.process.run_quality_gates", mock_quality),
            patch("autoinfo.process.KBStore", return_value=mock_store),
        ]

        # First batch: process 2 items
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            r1 = run_processing("medical-research", batch_size=2)

        assert r1.processed_count == 2
        assert r1.remaining_count == 1
        assert r1.is_complete is False
        # Parallel processing does not guarantee extraction call order
        assert sorted(processed_ids) == ["item-001", "item-002"]
        first_batch_ids = list(processed_ids)
        processed_ids.clear()

        # Second batch: process remaining 1 item
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            r2 = run_processing("medical-research", batch_size=2)

        assert r2.processed_count == 1
        assert r2.remaining_count == 0
        assert r2.is_complete is True
        assert sorted(processed_ids) == ["item-003"]

        # Verify no overlap
        all_ids = first_batch_ids + processed_ids
        assert len(all_ids) == 3
        assert len(set(all_ids)) == 3  # all unique

    def test_no_duplicates_on_restart(
        self,
        three_items: list[Item],
        mock_extraction: ExtractionResult,
    ) -> None:
        """A shrunk cache must not reprocess the items the legacy cursor covered."""
        processed_ids: list[str] = []

        def track_extraction(item: Item, **kwargs: Any) -> ExtractionResult:
            processed_ids.append(item.id)
            return mock_extraction

        mock_ext = MagicMock(side_effect=track_extraction)
        mock_quality = MagicMock(return_value=_all_pass_gates())
        mock_store = _mock_kb_store()

        # Legacy state: cursor covered 2 items, but the cache now holds 2 items.
        with (
            patch("autoinfo.process.load_cached_items", return_value=three_items[:2]),
            patch(
                "autoinfo.process._read_progress",
                return_value={
                    "last_processed_index": 2,
                    "total_items": 3,
                    "processed_ids": [],
                },
            ),
            patch("autoinfo.process._write_progress") as mock_write,
            patch.object(LLMExtractor, "extract", mock_ext),
            patch("autoinfo.process.run_quality_gates", mock_quality),
            patch("autoinfo.process.KBStore", return_value=mock_store),
        ):
            result = run_processing("medical-research", batch_size=5)

        assert result.total_items == 2
        assert result.processed_count == 0
        assert processed_ids == []
        mock_write.assert_not_called()

    def test_cache_growth_processes_only_the_new_items(
        self,
        three_items: list[Item],
        mock_extraction: ExtractionResult,
    ) -> None:
        """The regression: a collect that changes the item count must not reset
        progress. The recorded ids are skipped; only the new item is extracted."""
        processed_ids: list[str] = []

        def track_extraction(item: Item, **kwargs: Any) -> ExtractionResult:
            processed_ids.append(item.id)
            return mock_extraction

        mock_ext = MagicMock(side_effect=track_extraction)
        mock_quality = MagicMock(return_value=_all_pass_gates())
        mock_store = _mock_kb_store()

        # 3 items cached now; the first two were recorded on previous nights.
        with (
            patch("autoinfo.process.load_cached_items", return_value=three_items),
            patch(
                "autoinfo.process._read_progress",
                return_value={
                    "last_processed_index": 2,
                    "total_items": 2,
                    "processed_ids": ["item-001", "item-002"],
                },
            ),
            patch("autoinfo.process._write_progress") as mock_write,
            patch.object(LLMExtractor, "extract", mock_ext),
            patch("autoinfo.process.run_quality_gates", mock_quality),
            patch("autoinfo.process.KBStore", return_value=mock_store),
        ):
            result = run_processing("medical-research", batch_size=5)

        assert sorted(processed_ids) == ["item-003"]
        assert result.processed_count == 1
        assert result.remaining_count == 0
        mock_write.assert_called_once_with("medical-research", 3, 3, processed_ids=["item-003"])

    def test_newest_first_prioritises_the_latest_items(
        self,
        three_items: list[Item],
        mock_extraction: ExtractionResult,
    ) -> None:
        """With newest_first and a batch of 1, the most recent item is chosen."""
        processed_ids: list[str] = []

        def track_extraction(item: Item, **kwargs: Any) -> ExtractionResult:
            processed_ids.append(item.id)
            return mock_extraction

        mock_ext = MagicMock(side_effect=track_extraction)
        mock_quality = MagicMock(return_value=_all_pass_gates())
        mock_store = _mock_kb_store()

        with (
            patch("autoinfo.process.load_cached_items", return_value=three_items),
            patch(
                "autoinfo.process._read_progress",
                return_value={
                    "last_processed_index": 0,
                    "total_items": 3,
                    "processed_ids": [],
                },
            ),
            patch("autoinfo.process._write_progress"),
            patch.object(LLMExtractor, "extract", mock_ext),
            patch("autoinfo.process.run_quality_gates", mock_quality),
            patch("autoinfo.process.KBStore", return_value=mock_store),
        ):
            result = run_processing("medical-research", batch_size=1, newest_first=True)

        assert processed_ids == ["item-003"]
        assert result.processed_count == 1

    def test_resume_from_start_records_ids(
        self,
        three_items: list[Item],
        mock_extraction: ExtractionResult,
    ) -> None:
        """A full re-run must record ids, so a later auto run does not repeat it."""
        mock_ext = MagicMock(return_value=mock_extraction)
        mock_quality = MagicMock(return_value=_all_pass_gates())
        mock_store = _mock_kb_store()

        with (
            patch("autoinfo.process.load_cached_items", return_value=three_items),
            patch("autoinfo.process._reset_progress") as mock_reset,
            patch("autoinfo.process._write_progress") as mock_write,
            patch.object(LLMExtractor, "extract", mock_ext),
            patch("autoinfo.process.run_quality_gates", mock_quality),
            patch("autoinfo.process.KBStore", return_value=mock_store),
        ):
            result = run_processing("medical-research", resume_from="start")

        mock_reset.assert_called_once_with("medical-research")
        assert result.processed_count == 3
        mock_write.assert_called_once_with(
            "medical-research",
            3,
            3,
            processed_ids=["item-001", "item-002", "item-003"],
        )

    def test_legacy_cursor_migration_is_persisted(
        self,
        three_items: list[Item],
        mock_extraction: ExtractionResult,
    ) -> None:
        """The seeded prefix must be written back, not just used in memory:
        otherwise the next run sees a non-empty table, skips the migration, and
        reprocesses the whole legacy prefix."""
        mock_ext = MagicMock(return_value=mock_extraction)
        mock_quality = MagicMock(return_value=_all_pass_gates())
        mock_store = _mock_kb_store()

        with (
            patch("autoinfo.process.load_cached_items", return_value=three_items),
            patch(
                "autoinfo.process._read_progress",
                return_value={
                    "last_processed_index": 2,
                    "total_items": 2,
                    "processed_ids": [],
                },
            ),
            patch("autoinfo.process._write_progress") as mock_write,
            patch.object(LLMExtractor, "extract", mock_ext),
            patch("autoinfo.process.run_quality_gates", mock_quality),
            patch("autoinfo.process.KBStore", return_value=mock_store),
        ):
            run_processing("medical-research", batch_size=5)

        mock_write.assert_called_once_with(
            "medical-research",
            3,
            3,
            processed_ids=["item-001", "item-002", "item-003"],
        )

    def test_cache_change_resets_progress(self, three_items: list[Item]) -> None:
        """A legacy cursor past the current cache means the prefix is processed;
        a different persisted total alone must not trigger a re-run."""
        mock_ext = MagicMock()
        mock_quality = MagicMock()
        mock_store = _mock_kb_store()

        with (
            patch("autoinfo.process.load_cached_items", return_value=three_items),
            patch(
                "autoinfo.process._read_progress",
                return_value={
                    "last_processed_index": 3,
                    "total_items": 5,
                    "processed_ids": [],
                },
            ),
            patch("autoinfo.process._write_progress") as mock_write,
            patch.object(LLMExtractor, "extract", mock_ext),
            patch("autoinfo.process.run_quality_gates", mock_quality),
            patch("autoinfo.process.KBStore", return_value=mock_store),
        ):
            result = run_processing("medical-research", batch_size=2)

        # The legacy cursor covered all three cached items -> nothing to do.
        assert result.processed_count == 0
        mock_ext.assert_not_called()
        mock_write.assert_not_called()


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
