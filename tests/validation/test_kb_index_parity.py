# mypy: ignore-errors
"""Two-sided parity between the live KB tree and its SQLite index (T9).

A row without a file inflates tier counts; a file without a row is invisible to
search and to `kb list-tiers`. Both make the capability matrix lie, so the
guard compares both directions plus the verification domains end to end.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE = ROOT / "knowledge"
DB = ROOT / "autoinfo.db"
TIERS = ("01-Raw", "02-Draft", "03-Wiki")
VERIFICATION_DOMAINS = ("medical-research", "language-learning", "ai-commercial")

needs_runtime = pytest.mark.skipif(
    not (KNOWLEDGE.is_dir() and DB.is_file()),
    reason="runtime KB tree/index absent (clean checkout)",
)


def _files_by_domain_tier() -> dict[tuple[str, str], int]:
    counts: dict[tuple[str, str], int] = {}
    for path in KNOWLEDGE.rglob("*.md"):
        rel = path.relative_to(KNOWLEDGE)
        if len(rel.parts) >= 3 and rel.parts[1] in TIERS:
            key = (rel.parts[0], rel.parts[1])
            counts[key] = counts.get(key, 0) + 1
    return counts


def _rows_by_domain_tier() -> dict[tuple[str, str], int]:
    with sqlite3.connect(DB) as conn:
        rows = conn.execute("SELECT domain, tier, count(*) FROM entries GROUP BY domain, tier")
        return {(domain, tier): count for domain, tier, count in rows}


@needs_runtime
def test_index_rows_match_files_per_domain_and_tier() -> None:
    assert _rows_by_domain_tier() == _files_by_domain_tier()


@needs_runtime
def test_no_index_row_points_at_missing_or_non_tier_file() -> None:
    with sqlite3.connect(DB) as conn:
        rows = conn.execute("SELECT entry_id, file_path FROM entries").fetchall()
    offenders = []
    for entry_id, file_path in rows:
        path = Path(file_path) if file_path else None
        if path is None or not path.is_file():
            offenders.append(f"{entry_id}: file missing ({file_path!r})")
            continue
        rel = path.resolve().relative_to(KNOWLEDGE.resolve())
        if len(rel.parts) < 3 or rel.parts[1] not in TIERS:
            offenders.append(f"{entry_id}: outside the four tiers ({rel})")
    assert offenders == []


@needs_runtime
@pytest.mark.parametrize("domain", VERIFICATION_DOMAINS)
def test_verification_domain_tier_counts_match(domain: str) -> None:
    files = {tier: _files_by_domain_tier().get((domain, tier), 0) for tier in TIERS}
    rows = {tier: _rows_by_domain_tier().get((domain, tier), 0) for tier in TIERS}
    assert rows == files
    assert sum(files.values()) > 0
