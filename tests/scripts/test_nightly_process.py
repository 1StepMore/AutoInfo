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
