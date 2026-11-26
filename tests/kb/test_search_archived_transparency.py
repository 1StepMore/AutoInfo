"""Search must not silently hide archived entries (issue #969).

``search_knowledge_base`` excludes ``custom_fields.status`` =
``archived``/``deprecated`` rows by design — but it used to hide them
*silently*: ``kb list-tiers`` reported 12 entries while ``kb search``
found 5, and nothing told the caller the other 7 existed.  Locked here:

1. default search keeps excluding archived rows but reports how many
   hits were hidden in ``excluded_archived``;
2. ``include_archived=True`` disables the status filter entirely;
3. ``kb list-tiers`` reports per-tier active/archived counts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from autoinfo.cli.kb import app as kb_app
from autoinfo.kb import KBStore, SQLiteIndex
from autoinfo.models import KBEntry

DOMAIN = "ai-commercial"


def _entry(entry_id: str, title: str, status: str) -> KBEntry:
    return KBEntry(
        entry_id=entry_id,
        title=title,
        domain=DOMAIN,
        tier="01-Raw",
        source_url=f"https://example.com/{entry_id}",
        source_type="api",
        source_platform="demo",
        collected_at="2026-11-20T10:00:00Z",
        tags=["phone"],
        status=status,
    )


@pytest.fixture()
def store(tmp_path: Path) -> KBStore:
    store = KBStore(base_path=tmp_path / "knowledge")
    idx: SQLiteIndex = store.index
    for i in range(3):
        e = _entry(f"act-{i}", f"OPPO flagship review part {i}", "active")
        idx.index_entry(e)
        idx.index_entry_fts5(e, content=e.title)
    for i in range(2):
        e = _entry(f"arc-{i}", f"OPPO archived review part {i}", "archived")
        idx.index_entry(e)
        idx.index_entry_fts5(e, content=e.title)
    return store


class TestSearchExcludedArchivedCount:
    def test_default_search_reports_hidden_hits(self, store: KBStore) -> None:
        """Default: archived stays excluded, but counted, never silent."""
        result = store.search_knowledge_base("OPPO", domain=DOMAIN)

        assert result["total_count"] == 3
        assert result["excluded_archived"] == 2
        ids = {e["entry_id"] for e in result["entries"]}
        assert not any(i.startswith("arc-") for i in ids)

    def test_include_archived_disables_status_filter(self, store: KBStore) -> None:
        result = store.search_knowledge_base(
            "OPPO", domain=DOMAIN, include_archived=True
        )

        assert result["total_count"] == 5
        assert result["excluded_archived"] == 0
        ids = {e["entry_id"] for e in result["entries"]}
        assert {f"arc-{i}" for i in range(2)} <= ids

    def test_zero_hidden_when_only_active_match(self, store: KBStore) -> None:
        result = store.search_knowledge_base("flagship", domain=DOMAIN)

        assert result["total_count"] == 3
        assert result["excluded_archived"] == 0

    def test_empty_query_still_carries_the_key(self, store: KBStore) -> None:
        """An escaped-to-empty query must not crash on the new field."""
        result = store.search_knowledge_base("NOT", domain=DOMAIN)
        assert result["excluded_archived"] == 0


class TestCliSearchHint:
    def test_stderr_hint_when_hits_were_hidden(
        self, store: KBStore, monkeypatch: Any
    ) -> None:
        monkeypatch.setattr("autoinfo.kb.KBStore", lambda *a, **k: store)

        result = CliRunner().invoke(
            kb_app, ["search", "--query", "OPPO", "--domain", DOMAIN]
        )

        assert result.exit_code == 0
        # stdout stays pure JSON; the hint goes to stderr.
        data = json.loads(result.stdout)
        assert data["excluded_archived"] == 2
        assert "2 条命中但已归档" in result.stderr

    def test_no_hint_when_nothing_hidden(
        self, store: KBStore, monkeypatch: Any
    ) -> None:
        monkeypatch.setattr("autoinfo.kb.KBStore", lambda *a, **k: store)

        result = CliRunner().invoke(
            kb_app, ["search", "--query", "flagship", "--domain", DOMAIN]
        )

        assert result.exit_code == 0
        assert "已归档" not in result.stderr


class TestListTiersStatusCounts:
    def test_json_carries_active_and_archived(
        self, store: KBStore, monkeypatch: Any
    ) -> None:
        monkeypatch.setattr("autoinfo.kb.KBStore", lambda *a, **k: store)

        result = CliRunner().invoke(
            kb_app, ["list-tiers", "--domain", DOMAIN, "--json"]
        )

        assert result.exit_code == 0
        parsed = json.loads(result.stdout)
        raw = next(t for t in parsed["items"] if t["tier"] == "01-Raw")
        assert raw["entry_count"] == 5
        assert raw["active"] == 3
        assert raw["archived"] == 2

    def test_human_output_shows_both_counts(
        self, store: KBStore, monkeypatch: Any
    ) -> None:
        monkeypatch.setattr("autoinfo.kb.KBStore", lambda *a, **k: store)

        result = CliRunner().invoke(kb_app, ["list-tiers", "--domain", DOMAIN])

        assert result.exit_code == 0
        assert "5 entries: 3 active / 2 archived" in result.stdout


class TestCountEntriesByTierStatus:
    def test_counts_split_and_sum(self, store: KBStore) -> None:
        counts = store.count_entries_by_tier_status(DOMAIN, "01-Raw")
        assert counts == {"active": 3, "archived": 2}
        assert (
            counts["active"] + counts["archived"]
            == store.count_entries_by_tier(DOMAIN, "01-Raw")
        )

    def test_empty_domain_is_zeroed(self, store: KBStore) -> None:
        assert store.count_entries_by_tier_status("no-such-domain", "01-Raw") == {
            "active": 0,
            "archived": 0,
        }
