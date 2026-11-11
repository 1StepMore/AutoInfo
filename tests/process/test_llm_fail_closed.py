"""#750 regression: an empty LLM extraction fails the run instead of passing.

``LLMExtractor.extract`` deliberately swallows credential/transport errors and
returns an empty ``ExtractionResult``. The pipeline used to store that entry
with an empty summary and still exit 0, so a missing API key looked like a
successful nightly run. The item still gets stored and still counts as
processed (retrying cannot repair a missing credential), but the run now
reports an ``ExtractionFailed`` error and the CLI exits 2.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from autoinfo.cli.process import app as process_app
from autoinfo.kb import KBStore
from autoinfo.llm import LLMExtractor
from autoinfo.models import ExtractionResult, Item, KBEntry
from autoinfo.process import ProcessResult, run_processing
from autoinfo.quality import QualityResult

runner = CliRunner()


@pytest.fixture
def item() -> Item:
    return Item(
        id="llm-fail-1",
        source_name="pubmed",
        source_type="api",
        source_platform="pubmed",
        source_url="https://example.com/llm-fail-1",
        title="A valid item whose extraction fails",
        content="Body text long enough for the minimum KB content length.",
        domain="medical-research",
        collected_at="2026-07-20T00:00:00Z",
    )


def _all_pass_gates() -> dict[str, QualityResult]:
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


def _mock_store() -> MagicMock:
    store = MagicMock(spec=KBStore)
    store.store_entry.return_value = KBEntry(
        entry_id="llm-fail-1",
        title="A valid item whose extraction fails",
        domain="medical-research",
    )
    store.list_entries.return_value = []
    return store


def _run(
    item: Item,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    batch_size: int = 0,
) -> tuple[ProcessResult, MagicMock, MagicMock]:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AUTOINFO_PROCESS_WORKERS", "1")
    store = _mock_store()
    mark = MagicMock()

    with (
        patch("autoinfo.process.load_cached_items", return_value=[item]),
        patch(
            "autoinfo.process._read_progress",
            return_value={"last_processed_index": 0, "total_items": 1},
        ),
        patch("autoinfo.process._read_processed_ids", return_value=set()),
        patch("autoinfo.process._mark_processed", mark),
        patch("autoinfo.process._write_progress"),
        patch("autoinfo.process.run_quality_gates", return_value=_all_pass_gates()),
        patch("autoinfo.process.KBStore", return_value=store),
    ):
        result = run_processing("medical-research", batch_size=batch_size)
    return result, store, mark


def test_empty_extraction_is_reported_as_an_error(
    item: Item,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with patch(
        "autoinfo.llm.call_with_fallback",
        side_effect=RuntimeError("Missing credentials"),
    ):
        result, store, mark = _run(item, tmp_path, monkeypatch, batch_size=1)

    assert result.extraction_failed == 1
    assert len(result.errors) == 1
    assert result.errors[0]["item_id"] == "llm-fail-1"
    assert result.errors[0]["error_type"] == "ExtractionFailed"

    # The entry is still stored and the ledger still marks it processed.
    assert result.kb_entries_created == 1
    assert store.store_entry.call_count == 1
    assert result.per_item_logs[0]["status"] == "ok"
    assert result.per_item_logs[0]["extraction_failed"] is True
    mark.assert_called_once_with("medical-research", ["llm-fail-1"])


def test_non_empty_extraction_does_not_fail_the_run(
    item: Item,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    extraction = ExtractionResult(
        item_id=item.id,
        title=item.title,
        tl_dr="A real summary.",
        key_points=["A point"],
        relevance_score=80.0,
    )
    with patch.object(LLMExtractor, "extract", return_value=extraction):
        result, store, _ = _run(item, tmp_path, monkeypatch)

    assert result.extraction_failed == 0
    assert result.errors == []
    assert result.kb_entries_created == 1
    assert store.store_entry.call_count == 1


def test_cli_json_reports_extraction_failed_and_exits_2() -> None:
    result = ProcessResult(
        domain="medical-research",
        total_items=1,
        processed_count=1,
        kb_entries_created=1,
        extraction_failed=1,
        errors=[
            {
                "item_id": "llm-fail-1",
                "error": "LLM extraction returned an empty result",
                "error_type": "ExtractionFailed",
            }
        ],
    )
    with patch("autoinfo.cli.process.run_processing", return_value=result):
        res = runner.invoke(process_app, ["--domain", "medical-research", "--json"])

    assert res.exit_code == 2, res.output
    payload = json.loads(res.stdout)
    assert payload["extraction_failed"] == 1
    assert payload["errors"][0]["error_type"] == "ExtractionFailed"


def test_cli_human_output_reports_failed_items() -> None:
    result = ProcessResult(
        domain="medical-research",
        total_items=1,
        processed_count=1,
        kb_entries_created=1,
        extraction_failed=1,
        errors=[
            {
                "item_id": "llm-fail-1",
                "error": "LLM extraction returned an empty result",
                "error_type": "ExtractionFailed",
            }
        ],
    )
    with patch("autoinfo.cli.process.run_processing", return_value=result):
        res = runner.invoke(process_app, ["--domain", "medical-research"])

    assert res.exit_code == 2, res.output
    assert "1 item(s) failed processing" in res.output
