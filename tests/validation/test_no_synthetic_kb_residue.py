# mypy: ignore-errors
"""Guard the live KB against synthetic scenario residue.

`kb-tier-matrix` scenario runs had written one synthetic entry per domain into
`01-Raw/`, and six drafts had been filed under `03-Wiki/` while their own
frontmatter still said `tier: 02-Draft`. Both are residue, not knowledge.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE = ROOT / "knowledge"
DB = ROOT / "autoinfo.db"
SYNTHETIC_SOURCE_PREFIX = "https://kb-tier-matrix.autoinfo.dev/"

needs_knowledge = pytest.mark.skipif(
    not KNOWLEDGE.is_dir(), reason="runtime KB tree is absent (clean checkout)"
)
needs_db = pytest.mark.skipif(not DB.is_file(), reason="runtime index is absent (clean checkout)")


def _frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(errors="replace")
    if not text.startswith("---"):
        return {}
    meta: dict[str, str] = {}
    for line in text.split("---", 2)[1].splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()
    return meta


def _kb_files() -> list[Path]:
    if not KNOWLEDGE.is_dir():
        return []
    return [p for p in KNOWLEDGE.rglob("*.md") if "_archive" not in p.parts]


@needs_knowledge
def test_no_synthetic_kb_tier_matrix_source_url() -> None:
    offenders = [
        str(p)
        for p in _kb_files()
        if _frontmatter(p).get("source_url", "").startswith(SYNTHETIC_SOURCE_PREFIX)
    ]
    assert offenders == []


@needs_knowledge
def test_no_unpromoted_draft_under_wiki_tier_dir() -> None:
    offenders = [
        f"{p} (tier={_frontmatter(p).get('tier', '?')})"
        for p in _kb_files()
        if "03-Wiki" in p.parts and _frontmatter(p).get("tier") != "03-Wiki"
    ]
    assert offenders == []


@needs_db
def test_no_kb_tier_matrix_index_rows() -> None:
    with sqlite3.connect(DB) as conn:
        count = conn.execute(
            "SELECT count(*) FROM entries WHERE file_path LIKE '%kb-tier-matrix%'"
        ).fetchone()[0]
    assert count == 0
