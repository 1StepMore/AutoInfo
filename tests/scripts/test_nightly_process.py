"""Tests for the backlog-triggered nightly process stage (#554, #596)."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import nightly_process as np  # noqa: E402


def _seed_domain(tmp_path: Path, domain: str = "alpha", count: int = 10) -> None:
    domain_dir = tmp_path / "domains" / domain
    domain_dir.mkdir(parents=True)
    (domain_dir / "sources.yaml").write_text("sources: []\n", encoding="utf-8")

    cache_dir = tmp_path / "collections" / domain / "source" / "2026-10-21"
    cache_dir.mkdir(parents=True)
    for index in range(count):
        (cache_dir / f"{index:03d}.json").write_text(json.dumps({"id": index}), encoding="utf-8")
    # Bookkeeping files must not count as backlog.
    (cache_dir / "_runs.json").write_text("{}", encoding="utf-8")
    failed = cache_dir / "_failed"
    failed.mkdir()
    (failed / "broken.json").write_text("{}", encoding="utf-8")


def _seed_progress(tmp_path: Path, domain: str = "alpha", last: int = 0, total: int = 0) -> None:
    conn = sqlite3.connect(tmp_path / "autoinfo.db")
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS processing_progress ("
            "domain TEXT PRIMARY KEY, "
            "last_processed_index INTEGER NOT NULL DEFAULT 0, "
            "total_items INTEGER NOT NULL DEFAULT 0)"
        )
        conn.execute(
            "INSERT OR REPLACE INTO processing_progress "
            "(domain, last_processed_index, total_items) VALUES (?, ?, ?)",
            (domain, last, total),
        )
        conn.commit()
    finally:
        conn.close()


def _args(tmp_path: Path, *extra: str) -> list[str]:
    return [
        "--domains-dir",
        str(tmp_path / "domains"),
        "--collections",
        str(tmp_path / "collections"),
        "--db",
        str(tmp_path / "autoinfo.db"),
        "--repo",
        str(tmp_path),
        *extra,
    ]


def _read_report(tmp_path: Path) -> dict:
    report_path = tmp_path / "report.json"
    return json.loads(report_path.read_text(encoding="utf-8"))


class _FakeClock:
    """Monotonic stand-in so budget arithmetic is deterministic in tests."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_below_threshold_skips(tmp_path: Path) -> None:
    _seed_domain(tmp_path, count=6)
    calls: list[str] = []

    def runner(request: np.ProcessRequest) -> tuple[int, float]:
        calls.append(request.domain)
        return 0, 0.1

    rc = np.main(
        _args(
            tmp_path,
            "--min-backlog",
            "10",
            "--json-out",
            str(tmp_path / "report.json"),
        ),
        runner=runner,
    )

    assert rc == 0
    assert calls == []
    report = _read_report(tmp_path)
    assert report["domains"][0]["backlog"] == 6
    assert report["domains"][0]["action"] == "skip"
    assert report["summary"]["selected"] == 0


def test_at_threshold_runs_and_writes_reports(tmp_path: Path) -> None:
    _seed_domain(tmp_path, count=10)
    calls: list[np.ProcessRequest] = []

    def runner(request: np.ProcessRequest) -> tuple[int, float]:
        calls.append(request)
        return 0, 1.5

    rc = np.main(
        _args(
            tmp_path,
            "--min-backlog",
            "10",
            "--timeout",
            "30",
            "--json-out",
            str(tmp_path / "report.json"),
            "--md-out",
            str(tmp_path / "report.md"),
        ),
        runner=runner,
    )

    assert rc == 0
    assert calls == [np.ProcessRequest("alpha", tmp_path, 30, 10)]
    report = _read_report(tmp_path)
    assert report["domains"][0]["action"] == "run"
    assert report["domains"][0]["exit_code"] == 0
    assert report["domains"][0]["budget_s"] == 30.0
    assert report["domains"][0]["batch_size"] == 10
    assert report["summary"] == {
        "domains": 1,
        "selected": 1,
        "executed": 1,
        "failed": 0,
        "skipped": 0,
        "skipped_budget": 0,
        "budget_exhausted": False,
    }
    assert "| alpha | 10 | 0 | 10 | run | 30.0 | 10 | 0 | 1.5 |" in (
        tmp_path / "report.md"
    ).read_text(encoding="utf-8")


def test_progress_reduces_backlog(tmp_path: Path) -> None:
    _seed_domain(tmp_path, count=30)
    _seed_progress(tmp_path, last=25, total=30)
    calls: list[str] = []

    def runner(request: np.ProcessRequest) -> tuple[int, float]:
        calls.append(request.domain)
        return 0, 0.1

    rc = np.main(
        _args(
            tmp_path,
            "--min-backlog",
            "10",
            "--json-out",
            str(tmp_path / "report.json"),
        ),
        runner=runner,
    )

    assert rc == 0
    assert calls == []
    report = _read_report(tmp_path)
    assert report["domains"][0]["processed_count"] == 25
    assert report["domains"][0]["backlog"] == 5
    assert report["domains"][0]["action"] == "skip"


def test_missing_progress_table_means_full_backlog(tmp_path: Path) -> None:
    _seed_domain(tmp_path, count=12)
    conn = sqlite3.connect(tmp_path / "autoinfo.db")
    try:
        conn.execute("CREATE TABLE unrelated (id INTEGER)")
        conn.commit()
    finally:
        conn.close()

    calls: list[str] = []

    def runner(request: np.ProcessRequest) -> tuple[int, float]:
        calls.append(request.domain)
        return 0, 0.1

    rc = np.main(
        _args(
            tmp_path,
            "--min-backlog",
            "10",
            "--json-out",
            str(tmp_path / "report.json"),
        ),
        runner=runner,
    )

    assert rc == 0
    assert calls == ["alpha"]
    assert _read_report(tmp_path)["domains"][0]["processed_count"] == 0


def test_process_failure_returns_1(tmp_path: Path) -> None:
    _seed_domain(tmp_path, count=10)

    def runner(request: np.ProcessRequest) -> tuple[int, float]:
        return 1, 2.0

    rc = np.main(
        _args(
            tmp_path,
            "--min-backlog",
            "10",
            "--json-out",
            str(tmp_path / "report.json"),
        ),
        runner=runner,
    )

    assert rc == 1
    report = _read_report(tmp_path)
    assert report["domains"][0]["exit_code"] == 1
    assert report["summary"]["failed"] == 1


def test_dry_run_does_not_execute(tmp_path: Path) -> None:
    _seed_domain(tmp_path, count=10)
    calls: list[str] = []

    def runner(request: np.ProcessRequest) -> tuple[int, float]:
        calls.append(request.domain)
        return 0, 0.1

    rc = np.main(
        _args(
            tmp_path,
            "--min-backlog",
            "10",
            "--dry-run",
            "--json-out",
            str(tmp_path / "report.json"),
        ),
        runner=runner,
    )

    assert rc == 0
    assert calls == []
    report = _read_report(tmp_path)
    assert report["domains"][0]["action"] == "would_run"
    assert report["summary"]["executed"] == 0


def test_fair_share_derives_batch_and_timeout(tmp_path: Path) -> None:
    _seed_domain(tmp_path, domain="alpha", count=10)
    _seed_domain(tmp_path, domain="beta", count=10)
    clock = _FakeClock()
    calls: list[np.ProcessRequest] = []

    def runner(request: np.ProcessRequest) -> tuple[int, float]:
        calls.append(request)
        clock.advance(10)
        return 0, 10.0

    rc = np.main(
        _args(
            tmp_path,
            "--min-backlog",
            "10",
            "--max-seconds",
            "240",
            "--seconds-per-item",
            "40",
            "--json-out",
            str(tmp_path / "report.json"),
        ),
        runner=runner,
        clock=clock,
    )

    assert rc == 0
    # 240 s shared by two due domains -> 120 s each, 120 // 40 = 3 items.
    assert calls[0] == np.ProcessRequest("alpha", tmp_path, 120, 3)
    # The second domain gets the remainder (230 s) as the only pending domain.
    assert calls[1].domain == "beta"
    assert calls[1].timeout_s == 230
    assert calls[1].batch_size == 5


def test_budget_defers_domain_then_runs_last(tmp_path: Path) -> None:
    _seed_domain(tmp_path, domain="alpha", count=10)
    _seed_domain(tmp_path, domain="beta", count=10)
    clock = _FakeClock()
    calls: list[np.ProcessRequest] = []

    def runner(request: np.ProcessRequest) -> tuple[int, float]:
        calls.append(request)
        clock.advance(60)
        return 0, 60.0

    rc = np.main(
        _args(
            tmp_path,
            "--min-backlog",
            "10",
            "--max-seconds",
            "60",
            "--seconds-per-item",
            "40",
            "--json-out",
            str(tmp_path / "report.json"),
        ),
        runner=runner,
        clock=clock,
    )

    assert rc == 0
    report = _read_report(tmp_path)
    actions = [row["action"] for row in report["domains"]]
    # alpha's 30 s share cannot fit one 40 s item, so it is deferred; beta then
    # gets the full budget as the only pending domain.
    assert actions == ["skipped_budget", "run"]
    assert calls == [np.ProcessRequest("beta", tmp_path, 60, 1)]
    assert report["summary"]["skipped_budget"] == 1
    assert report["summary"]["budget_exhausted"] is True


def test_budget_exhausted_skips_everything(tmp_path: Path) -> None:
    _seed_domain(tmp_path, domain="alpha", count=10)
    _seed_domain(tmp_path, domain="beta", count=10)

    def runner(request: np.ProcessRequest) -> tuple[int, float]:
        raise AssertionError("no domain should run under an exhausted budget")

    rc = np.main(
        _args(
            tmp_path,
            "--min-backlog",
            "10",
            "--max-seconds",
            "30",
            "--seconds-per-item",
            "40",
            "--json-out",
            str(tmp_path / "report.json"),
        ),
        runner=runner,
        clock=_FakeClock(),
    )

    assert rc == 0
    report = _read_report(tmp_path)
    assert [row["action"] for row in report["domains"]] == [
        "skipped_budget",
        "skipped_budget",
    ]
    assert report["summary"]["selected"] == 0
    assert report["summary"]["skipped_budget"] == 2
    assert report["summary"]["budget_exhausted"] is True


def test_explicit_batch_size_passes_through(tmp_path: Path) -> None:
    _seed_domain(tmp_path, count=10)
    calls: list[np.ProcessRequest] = []

    def runner(request: np.ProcessRequest) -> tuple[int, float]:
        calls.append(request)
        return 0, 1.0

    rc = np.main(
        _args(tmp_path, "--min-backlog", "10", "--batch-size", "7"),
        runner=runner,
        clock=_FakeClock(),
    )

    assert rc == 0
    assert calls == [np.ProcessRequest("alpha", tmp_path, 2400, 7)]


def test_unlimited_budget_disables_batching(tmp_path: Path) -> None:
    _seed_domain(tmp_path, count=10)
    calls: list[np.ProcessRequest] = []

    def runner(request: np.ProcessRequest) -> tuple[int, float]:
        calls.append(request)
        return 0, 1.0

    rc = np.main(
        _args(tmp_path, "--min-backlog", "10", "--max-seconds", "0", "--timeout", "30"),
        runner=runner,
        clock=_FakeClock(),
    )

    assert rc == 0
    # 0 disables the budget: no derived batch cap, legacy per-domain timeout.
    assert calls == [np.ProcessRequest("alpha", tmp_path, 30, 0)]


def test_dry_run_reports_budget_and_batch(tmp_path: Path) -> None:
    _seed_domain(tmp_path, domain="alpha", count=10)
    _seed_domain(tmp_path, domain="beta", count=10)
    calls: list[np.ProcessRequest] = []

    def runner(request: np.ProcessRequest) -> tuple[int, float]:
        calls.append(request)
        return 0, 0.1

    rc = np.main(
        _args(
            tmp_path,
            "--dry-run",
            "--min-backlog",
            "10",
            "--max-seconds",
            "240",
            "--seconds-per-item",
            "40",
            "--json-out",
            str(tmp_path / "report.json"),
        ),
        runner=runner,
        clock=_FakeClock(),
    )

    assert rc == 0
    assert calls == []
    report = _read_report(tmp_path)
    assert [row["action"] for row in report["domains"]] == ["would_run", "would_run"]
    assert [(row["budget_s"], row["batch_size"]) for row in report["domains"]] == [
        (120.0, 3),
        (120.0, 3),
    ]
    assert report["summary"]["executed"] == 0


def test_derived_batch_capped_by_backlog(tmp_path: Path) -> None:
    _seed_domain(tmp_path, count=10)
    calls: list[np.ProcessRequest] = []

    def runner(request: np.ProcessRequest) -> tuple[int, float]:
        calls.append(request)
        return 0, 1.0

    rc = np.main(
        _args(tmp_path, "--min-backlog", "10", "--max-seconds", "2000", "--seconds-per-item", "40"),
        runner=runner,
        clock=_FakeClock(),
    )

    assert rc == 0
    # The budget would allow 50 items; the backlog is the real cap.
    assert calls[0].batch_size == 10


# ===================================================================
# AutoInfo#596 / BACKLOG B7 — item-id cursor
# ===================================================================


def _seed_id_cache(tmp_path: Path, ids: list[str], domain: str = "alpha") -> None:
    """Seed ``collections/<domain>/source/<date>/<id>.json`` cache files."""
    cache_dir = tmp_path / "collections" / domain / "source" / "2026-10-21"
    cache_dir.mkdir(parents=True, exist_ok=True)
    for item_id in ids:
        (cache_dir / f"{item_id}.json").write_text(
            json.dumps(
                {
                    "id": item_id,
                    "source_name": "source",
                    "source_type": "api",
                    "source_platform": "source",
                    "source_url": f"https://example.com/{item_id}",
                    "title": f"Title {item_id}",
                    "content": f"Content for {item_id}.",
                    "content_type": "text",
                    "collected_at": "2026-10-21T10:00:00Z",
                    "language": "en",
                    "domain": domain,
                    "topic_tags": [],
                    "quality_tier": 1,
                    "raw_data": {},
                }
            ),
            encoding="utf-8",
        )


def _all_pass_gates() -> dict:
    from autoinfo.quality import QualityResult

    return {
        "G1-SourceAuthority": QualityResult(
            gate_name="G1-SourceAuthority",
            passed=True,
            score=1.0,
            details={"quality_tier": 1, "source_name": "source"},
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


def test_cursor_survives_item_count_change(tmp_path: Path, monkeypatch) -> None:
    """Growing the cache no longer resets the cursor (AutoInfo#596 / B7).

    Seed 10 cached items and run a batch that consumes all of them; then add
    3 more (10 → 13) and run again.  The second run must process exactly the
    3 new ids, never re-process the 10 already-done ones, and complete.
    """
    from unittest.mock import MagicMock

    from autoinfo import process as proc
    from autoinfo.kb import KBStore
    from autoinfo.llm import LLMExtractor
    from autoinfo.models import ExtractionResult, KBEntry

    # Isolate the progress DB inside tmp_path (process resolves it from cwd).
    monkeypatch.setattr(proc, "_get_progress_db_path", lambda: tmp_path / "autoinfo.db")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AUTOINFO_CONFIG", raising=False)

    domain = "alpha"
    first_ids = [f"item-{i:03d}" for i in range(10)]
    _seed_id_cache(tmp_path, first_ids, domain=domain)

    processed: list[str] = []

    def track(item, **kwargs):
        processed.append(item.id)
        return ExtractionResult(
            item_id=item.id,
            title=item.title,
            tl_dr="summary",
            key_points=["p"],
            entities=[],
            relevance_score=80.0,
        )

    entry = KBEntry(entry_id="e", title="t", domain=domain)
    store = MagicMock(spec=KBStore)
    store.store_entry.return_value = entry
    store.list_entries.return_value = []

    monkeypatch.setattr(LLMExtractor, "extract", MagicMock(side_effect=track))
    monkeypatch.setattr(proc, "run_quality_gates", MagicMock(return_value=_all_pass_gates()))
    monkeypatch.setattr(proc, "KBStore", MagicMock(return_value=store))

    # Round 1 — the whole 10-item cache.
    r1 = proc.run_processing(domain, batch_size=100)
    assert r1.total_items == 10
    assert r1.processed_count == 10
    assert r1.is_complete is True
    assert sorted(processed) == sorted(first_ids)

    # The ledger is the anchor: 10 ids recorded.
    assert proc._read_processed_ids(domain) == set(first_ids)
    assert np.read_processed_count(tmp_path / "autoinfo.db", domain) == 10

    # Round 2 — collect adds 3 new items (total 10 → 13).
    new_ids = [f"item-{i:03d}" for i in range(10, 13)]
    _seed_id_cache(tmp_path, new_ids, domain=domain)
    processed.clear()

    r2 = proc.run_processing(domain, batch_size=100)
    assert r2.total_items == 13
    # ... but the cursor does NOT reset: only the 3 new ids are processed.
    assert r2.processed_count == 3
    assert r2.is_complete is True
    assert sorted(processed) == sorted(new_ids)
    assert proc._read_processed_ids(domain) == set(first_ids) | set(new_ids)
    assert np.read_processed_count(tmp_path / "autoinfo.db", domain) == 13


def test_cursor_read_processed_count_prefers_ledger(tmp_path: Path) -> None:
    """``read_processed_count`` reads the id ledger, not the legacy column."""
    db_path = tmp_path / "autoinfo.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "CREATE TABLE processing_progress ("
            "domain TEXT PRIMARY KEY, last_processed_index INTEGER NOT NULL DEFAULT 0, "
            "total_items INTEGER NOT NULL DEFAULT 0)"
        )
        conn.execute(
            "INSERT INTO processing_progress (domain, last_processed_index, total_items) "
            "VALUES ('alpha', 3, 3)"
        )
        conn.execute(
            "CREATE TABLE processing_items ("
            "domain TEXT NOT NULL, item_id TEXT NOT NULL, processed_at TEXT NOT NULL, "
            "PRIMARY KEY (domain, item_id))"
        )
        conn.executemany(
            "INSERT INTO processing_items (domain, item_id, processed_at) VALUES ('alpha', ?, ?)",
            [(f"i{n}", "2026-10-21T00:00:00+00:00") for n in range(7)],
        )

        conn.commit()
    finally:
        conn.close()

    # The ledger wins over the stale legacy column.
    assert np.read_processed_count(db_path, "alpha") == 7
    # Unknown domains fall back to 0 (original "unavailable => 0" contract).
    assert np.read_processed_count(db_path, "beta") == 0


# ===================================================================
# AutoInfo#596 root cause 3 — freshness window + newest-first
# ===================================================================


def _seed_dated_cache(
    tmp_path: Path, date_name: str, ids: list[str], domain: str = "alpha"
) -> None:
    """Seed ``collections/<domain>/source/<date_name>/<id>.json`` cache files."""
    cache_dir = tmp_path / "collections" / domain / "source" / date_name
    cache_dir.mkdir(parents=True, exist_ok=True)
    for item_id in ids:
        (cache_dir / f"{item_id}.json").write_text(json.dumps({"id": item_id}), encoding="utf-8")


def test_since_days_and_newest_first_reach_request(tmp_path: Path) -> None:
    from tests._freshness import fresh_date

    _seed_domain(tmp_path)
    _seed_dated_cache(tmp_path, fresh_date(1), [f"new-{i:03d}" for i in range(10)])
    calls: list[np.ProcessRequest] = []

    def runner(request: np.ProcessRequest) -> tuple[int, float]:
        calls.append(request)
        return 0, 1.0

    rc = np.main(
        _args(
            tmp_path,
            "--min-backlog",
            "10",
            "--since-days",
            "7",
            "--newest-first",
            "--json-out",
            str(tmp_path / "report.json"),
        ),
        runner=runner,
        clock=_FakeClock(),
    )

    assert rc == 0
    assert calls == [np.ProcessRequest("alpha", tmp_path, 2400, 10, 7, True)]
    row = _read_report(tmp_path)["domains"][0]
    assert row["since_days"] == 7
    assert row["newest_first"] is True


def test_run_process_forwards_window_flags(tmp_path: Path) -> None:
    recorded: list[list[str]] = []

    class _Completed:
        returncode = 0

    def fake_run(cmd: list[str], **kwargs: object) -> _Completed:
        recorded.append(cmd)
        return _Completed()

    original = np.subprocess.run
    np.subprocess.run = fake_run  # type: ignore[assignment]
    try:
        np._run_process(np.ProcessRequest("alpha", tmp_path, 30, 0, 7, True))
        np._run_process(np.ProcessRequest("alpha", tmp_path, 30, 0))
    finally:
        np.subprocess.run = original  # type: ignore[assignment]

    assert recorded[0][-3:] == ["--since-days", "7", "--newest-first"]
    assert "--since-days" not in recorded[1]
    assert "--newest-first" not in recorded[1]


def test_count_cached_items_applies_window_to_date_dirs(tmp_path: Path) -> None:
    from tests._freshness import fresh_date

    _seed_dated_cache(tmp_path, "2020-01-01", ["old-a", "old-b"])
    _seed_dated_cache(tmp_path, fresh_date(1), ["new-a", "new-b", "new-c"])
    _seed_dated_cache(tmp_path, "not-a-date", ["misc-a"])
    collections = tmp_path / "collections"

    assert np.count_cached_items(collections, "alpha") == 6
    assert np.count_cached_items(collections, "alpha", since_days=7) == 4
