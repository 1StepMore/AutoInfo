"""Tests for scripts/check_kb_provenance.py — the T19 (a) provenance check."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import check_kb_provenance  # noqa: E402


def _seed(tmp_path: Path, entries: list[tuple[str, str]], collected: list[str]) -> None:
    cache = tmp_path / "collections" / "medical-research" / "pubmed"
    cache.mkdir(parents=True)
    for index, url in enumerate(collected):
        (cache / f"item-{index}.json").write_text(json.dumps({"source_url": url, "title": "t"}))
    conn = sqlite3.connect(tmp_path / "autoinfo.db")
    conn.execute(
        "create table entries (entry_id text primary key, domain text, source_url text, tier text, deleted integer)"
    )
    conn.executemany(
        "insert into entries values (?, ?, ?, '01-Raw', 0)",
        [(f"e{i}", domain, url) for i, (domain, url) in enumerate(entries)],
    )
    conn.commit()
    conn.close()


def test_exact_url_match_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    _seed(tmp_path, [("medical-research", "https://example.org/a")], ["https://example.org/a"])
    monkeypatch.chdir(tmp_path)

    assert check_kb_provenance.main() == 0
    out = capsys.readouterr().out
    assert "exact: 1" in out
    assert "unmatched: 0" in out


def test_query_string_drift_is_counted_but_not_fatal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    _seed(tmp_path, [("medical-research", "https://example.org/a")], ["https://example.org/a?f=rss"])
    monkeypatch.chdir(tmp_path)

    assert check_kb_provenance.main() == 0
    assert "query-string drift: 1" in capsys.readouterr().out


def test_unmatched_url_fails_the_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    _seed(tmp_path, [("medical-research", "https://api.openalex.org/works/https://openalex.org/W1")], [])
    monkeypatch.chdir(tmp_path)

    assert check_kb_provenance.main() == 1
    assert "UNMATCHED medical-research" in capsys.readouterr().out


def test_unreadable_collection_file_is_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed(tmp_path, [("medical-research", "https://example.org/a")], ["https://example.org/a"])
    (tmp_path / "collections" / "medical-research" / "pubmed" / "broken.json").write_text("{not json")
    monkeypatch.chdir(tmp_path)

    assert check_kb_provenance.main() == 0
