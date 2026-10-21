"""Tests for the backlog-triggered nightly process stage (#554)."""

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


def test_below_threshold_skips(tmp_path: Path) -> None:
    _seed_domain(tmp_path, count=6)
    calls: list[str] = []

    def runner(domain: str, repo: Path, timeout: int) -> tuple[int, float]:
        calls.append(domain)
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
    calls: list[tuple[str, Path, int]] = []

    def runner(domain: str, repo: Path, timeout: int) -> tuple[int, float]:
        calls.append((domain, repo, timeout))
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
    assert calls == [("alpha", tmp_path, 30)]
    report = _read_report(tmp_path)
    assert report["domains"][0]["action"] == "run"
    assert report["domains"][0]["exit_code"] == 0
    assert report["summary"] == {
        "domains": 1,
        "selected": 1,
        "executed": 1,
        "failed": 0,
        "skipped": 0,
    }
    assert "| alpha | 10 | 0 | 10 | run | 0 | 1.5 |" in (tmp_path / "report.md").read_text(
        encoding="utf-8"
    )


def test_progress_reduces_backlog(tmp_path: Path) -> None:
    _seed_domain(tmp_path, count=30)
    _seed_progress(tmp_path, last=25, total=30)
    calls: list[str] = []

    def runner(domain: str, repo: Path, timeout: int) -> tuple[int, float]:
        calls.append(domain)
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

    def runner(domain: str, repo: Path, timeout: int) -> tuple[int, float]:
        calls.append(domain)
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

    def runner(domain: str, repo: Path, timeout: int) -> tuple[int, float]:
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

    def runner(domain: str, repo: Path, timeout: int) -> tuple[int, float]:
        calls.append(domain)
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
