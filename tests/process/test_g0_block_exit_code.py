"""#751 regression: G0-blocked items are graded into CLI exit code 2.

G0 is a deterministic hard gate: a blocked item is written to
``collections/<domain>/_failed/`` and stays marked processed (no retry). It
used to leave ``result.errors`` empty, so an all-G0-blocked domain exited 0
and looked successful to schedulers. The run now reports the count through
``ProcessResult.g0_blocked`` and the CLI grades it as 2 without inventing a
per-item error or changing the ledger rule.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from autoinfo.cli.process import app as process_app
from autoinfo.kb import KBStore
from autoinfo.models import Item
from autoinfo.process import ProcessResult, run_processing

runner = CliRunner()


@pytest.fixture
def g0_blocked_item() -> Item:
    """An item missing G0's mandatory source fields."""
    return Item(
        id="g0-bad-1",
        source_name="test",
        source_type="",
        source_url="",
        title="Malformed item",
        content="Body text long enough to be a real item.",
        domain="medical-research",
        collected_at="2026-07-20T00:00:00Z",
    )


def test_run_processing_counts_g0_blocked_without_an_error(
    g0_blocked_item: Item,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AUTOINFO_PROCESS_WORKERS", "1")
    store = MagicMock(spec=KBStore)
    store.list_entries.return_value = []

    with (
        patch("autoinfo.process.load_cached_items", return_value=[g0_blocked_item]),
        patch("autoinfo.process.KBStore", return_value=store),
    ):
        result = run_processing("medical-research")

    assert result.g0_blocked == 1
    assert result.errors == []
    assert result.kb_entries_created == 0
    # G0-blocked items are diagnostics-only: no per-item log, no storage.
    assert result.per_item_logs == []
    assert store.store_entry.call_count == 0
    failed = tmp_path / "collections" / "medical-research" / "_failed" / "g0-bad-1.json"
    assert failed.is_file()
    assert json.loads(failed.read_text(encoding="utf-8"))["gate"] == "G0"


def test_cli_exits_2_when_g0_blocked_without_result_errors() -> None:
    blocked = ProcessResult(
        domain="medical-research",
        total_items=1,
        processed_count=1,
        remaining_count=0,
        is_complete=True,
        g0_blocked=1,
    )
    with patch("autoinfo.cli.process.run_processing", return_value=blocked):
        res = runner.invoke(process_app, ["--domain", "medical-research"])

    assert res.exit_code == 2, res.output
    assert "blocked by G0" in res.output


def test_cli_json_reports_g0_blocked_and_exits_2() -> None:
    blocked = ProcessResult(
        domain="medical-research",
        total_items=1,
        processed_count=1,
        remaining_count=0,
        is_complete=True,
        g0_blocked=1,
    )
    with patch("autoinfo.cli.process.run_processing", return_value=blocked):
        res = runner.invoke(process_app, ["--domain", "medical-research", "--json"])

    assert res.exit_code == 2, res.output
    payload = json.loads(res.stdout)
    assert payload["g0_blocked"] == 1
    assert payload["errors"] == []


def test_cli_still_exits_0_when_nothing_was_blocked() -> None:
    clean = ProcessResult(
        domain="medical-research",
        total_items=1,
        processed_count=1,
        remaining_count=0,
        is_complete=True,
    )
    with patch("autoinfo.cli.process.run_processing", return_value=clean):
        res = runner.invoke(process_app, ["--domain", "medical-research"])

    assert res.exit_code == 0, res.output
