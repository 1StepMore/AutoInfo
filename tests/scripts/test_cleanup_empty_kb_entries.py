"""Tests for the legacy empty-entry cleanup script (scripts/cleanup_empty_kb_entries.py).

Covers issue #279: entries whose content is shorter than ``MIN_KB_CONTENT_CHARS``
(50) — written before the min-length guard existed — must be scan-able and
removable, while 03-Wiki is NEVER touched (append-only tier).

Behaviour under test:

- ``scan_empty_entries`` flags only <50-char files under 01-Raw/02-Draft
- a >=50-char 01-Raw entry and a <50-char 03-Wiki entry are left alone
- ``main(["--apply", root])`` deletes only the flagged files
- ``main(["--dry-run", root])`` prints a report and a summary line
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# scripts/ is not a package — load it via sys.path like the script itself does.
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

import cleanup_empty_kb_entries as clean  # noqa: E402  (sys.path insert above)

from autoinfo.kb import MIN_KB_CONTENT_CHARS, KBStore  # noqa: E402
from autoinfo.models import KBEntry  # noqa: E402


def _write_entry(root: Path, tier: str, name: str, body: str) -> Path:
    """Create ``knowledge/<domain>/<tier>/<topic>/<name>.md`` and return its path."""
    fp = root / "medical-research" / tier / "general" / name
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(
        "---\ntitle: fixture\ndomain: medical-research\n"
        f"tier: {tier}\nentry_id: fixture-{name}\n---\n\n{body}",
        encoding="utf-8",
    )
    return fp


def _fixture_tree(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    """Build (knowledge_root, short_raw, long_raw, short_wiki) with known content."""
    kb = tmp_path / "knowledge"
    short_raw = _write_entry(kb, "01-Raw", "short-raw.md", "x" * 10)
    long_raw = _write_entry(kb, "01-Raw", "long-raw.md", "y" * MIN_KB_CONTENT_CHARS)
    short_wiki = _write_entry(kb, "03-Wiki", "short-wiki.md", "z" * 10)
    return kb, short_raw, long_raw, short_wiki


def test_scan_returns_only_short_non_wiki(tmp_path: Path) -> None:
    """Only the <50-char 01-Raw entry is flagged; 03-Wiki is never scanned."""
    kb, short_raw, long_raw, short_wiki = _fixture_tree(tmp_path)

    found = clean.scan_empty_entries(kb)

    assert found == [short_raw]
    assert long_raw.exists()
    assert short_wiki.exists()


def test_apply_removes_only_short_non_wiki(tmp_path: Path) -> None:
    """--apply deletes the short 01-Raw entry, keeps the long raw and wiki."""
    kb, short_raw, long_raw, short_wiki = _fixture_tree(tmp_path)

    exit_code = clean.main(["--apply", str(kb)])

    assert exit_code == 0
    assert not short_raw.exists()
    assert long_raw.exists()
    assert short_wiki.exists()


def test_dry_run_prints_report_and_leaves_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """--dry-run prints the report and summary line without deleting."""
    kb, short_raw, long_raw, short_wiki = _fixture_tree(tmp_path)

    exit_code = clean.main(["--dry-run", str(kb)])
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "1 empty" in out
    assert str(short_raw) in out
    assert short_raw.exists()
    assert long_raw.exists()
    assert short_wiki.exists()


# ===================================================================
# --prune-missing (T9: index/file parity)
# ===================================================================


def _index_row(root: Path, entry_id: str, tier: str, file_path: Path) -> None:
    """Index *file_path* directly, bypassing the store's write path."""
    KBStore(base_path=root).index.index_entry(
        KBEntry(
            entry_id=entry_id,
            title="fixture",
            domain="medical-research",
            tier=tier,
            file_path=str(file_path),
        )
    )


def test_prune_missing_dry_run_counts_and_keeps_rows(tmp_path: Path) -> None:
    kb, *_ = _fixture_tree(tmp_path)
    _index_row(kb, "gone", "01-Raw", kb / "medical-research" / "01-Raw" / "gone.md")

    per_domain, total = clean.prune_missing_index_rows(kb, apply=False)

    assert (per_domain, total) == ({"medical-research": [1, 0]}, 1)
    assert KBStore(base_path=kb).index.get_entry("gone") is not None


def test_prune_missing_apply_deletes_only_dangling_rows(tmp_path: Path) -> None:
    kb, short_raw, *_ = _fixture_tree(tmp_path)
    _index_row(kb, "keep", "01-Raw", short_raw)
    _index_row(kb, "gone", "01-Raw", kb / "medical-research" / "01-Raw" / "gone.md")
    store = KBStore(base_path=kb)

    per_domain, total = clean.prune_missing_index_rows(kb, apply=True)

    assert (per_domain, total) == ({"medical-research": [1, 0]}, 1)
    assert store.index.get_entry("gone") is None
    assert store.index.get_entry("keep") is not None
    assert short_raw.exists()


def test_prune_outside_tier_drops_row_but_keeps_file(tmp_path: Path) -> None:
    kb = tmp_path / "knowledge"
    quarantine = kb / "_failed" / "medical-research" / "blocked.md"
    quarantine.parent.mkdir(parents=True)
    quarantine.write_text("---\ntier: 02-Draft\n---\n\nblocked", encoding="utf-8")
    _index_row(kb, "blocked", "02-Draft", quarantine)

    per_domain, total = clean.prune_missing_index_rows(kb, apply=True)

    assert (per_domain, total) == ({"medical-research": [0, 1]}, 1)
    assert KBStore(base_path=kb).index.get_entry("blocked") is None
    assert quarantine.exists()


def test_main_prune_missing_is_dry_run_by_default(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    kb, *_ = _fixture_tree(tmp_path)
    _index_row(kb, "gone", "01-Raw", kb / "medical-research" / "01-Raw" / "gone.md")

    assert clean.main(["--prune-missing", str(kb)]) == 0

    out = capsys.readouterr().out
    assert "1 (stale 1, outside-tier 0)" in out
    assert "1 dangling index rows flagged" in out
    assert KBStore(base_path=kb).index.get_entry("gone") is not None
