"""Freshness window + newest-first ordering for ``load_cached_items`` (#596).

The processing pipeline walks ``collections/<domain>/<source>/<date>/`` oldest
first, so a bounded nightly run only ever reaches stale entries.  These tests
cover the ``since_days`` window and the ``newest_first`` ordering, including the
date-directory fallback for items with no parseable ``collected_at``.
"""

from __future__ import annotations

import json
from pathlib import Path

from autoinfo.process import load_cached_items
from tests._freshness import fresh_date, fresh_iso

OLD_ISO = "2020-01-01T00:00:00+00:00"


def _write_item(date_dir: Path, item_id: str, collected_at: str) -> None:
    """Write ``<date_dir>/<item_id>.json`` in the collector cache layout."""
    date_dir.mkdir(parents=True, exist_ok=True)
    (date_dir / f"{item_id}.json").write_text(
        json.dumps(
            {
                "id": item_id,
                "source_name": "pubmed",
                "source_type": "api",
                "source_url": f"https://example.com/{item_id}",
                "title": f"Title {item_id}",
                "content": f"Content for {item_id}.",
                "collected_at": collected_at,
            }
        ),
        encoding="utf-8",
    )


def _base(tmp_path: Path) -> Path:
    return tmp_path / "collections"


def test_window_keeps_fresh_and_drops_old(tmp_path: Path) -> None:
    source_dir = _base(tmp_path) / "test-domain" / "pubmed"
    _write_item(source_dir / fresh_date(1), "fresh", fresh_iso())
    _write_item(source_dir / "2020-01-01", "old", OLD_ISO)

    items = load_cached_items("test-domain", base_path=_base(tmp_path), since_days=7)

    assert [item.id for item in items] == ["fresh"]


def test_newest_first_reverses_walk_order(tmp_path: Path) -> None:
    source_dir = _base(tmp_path) / "test-domain" / "pubmed"
    _write_item(source_dir / "2020-01-01", "a", OLD_ISO)
    _write_item(source_dir / "2021-01-01", "b", "2021-01-01T00:00:00+00:00")
    _write_item(source_dir / fresh_date(1), "c", fresh_iso())

    oldest_first = load_cached_items("test-domain", base_path=_base(tmp_path))
    newest_first = load_cached_items("test-domain", base_path=_base(tmp_path), newest_first=True)

    assert [item.id for item in oldest_first] == ["a", "b", "c"]
    assert [item.id for item in newest_first] == ["c", "b", "a"]


def test_undated_item_in_nondate_dir_survives_window(tmp_path: Path) -> None:
    source_dir = _base(tmp_path) / "test-domain" / "pubmed"
    _write_item(source_dir / "unknown", "u", "")

    items = load_cached_items("test-domain", base_path=_base(tmp_path), since_days=7)

    assert [item.id for item in items] == ["u"]


def test_undated_item_kept_by_fresh_date_dir(tmp_path: Path) -> None:
    source_dir = _base(tmp_path) / "test-domain" / "pubmed"
    _write_item(source_dir / fresh_date(1), "u", "")

    items = load_cached_items("test-domain", base_path=_base(tmp_path), since_days=7)

    assert [item.id for item in items] == ["u"]


def test_undated_item_dropped_by_old_date_dir(tmp_path: Path) -> None:
    source_dir = _base(tmp_path) / "test-domain" / "pubmed"
    _write_item(source_dir / "2020-01-01", "u", "")

    items = load_cached_items("test-domain", base_path=_base(tmp_path), since_days=7)

    assert items == []


def test_since_days_zero_returns_everything(tmp_path: Path) -> None:
    source_dir = _base(tmp_path) / "test-domain" / "pubmed"
    _write_item(source_dir / fresh_date(1), "fresh", fresh_iso())
    _write_item(source_dir / "2020-01-01", "old", OLD_ISO)

    items = load_cached_items("test-domain", base_path=_base(tmp_path), since_days=0)

    assert [item.id for item in items] == ["old", "fresh"]


def test_cli_threads_window_flags(cli_runner) -> None:
    from unittest.mock import MagicMock, patch

    from autoinfo.cli import app
    from autoinfo.process import ProcessResult

    mock_proc = MagicMock(return_value=ProcessResult(domain="d", total_items=1, processed_count=1))

    with patch("autoinfo.cli.process.run_processing", mock_proc):
        result = cli_runner.invoke(
            app,
            ["process", "--domain", "d", "--since-days", "7", "--newest-first"],
        )

    assert result.exit_code == 0
    kwargs = mock_proc.call_args.kwargs
    assert kwargs["since_days"] == 7
    assert kwargs["newest_first"] is True
