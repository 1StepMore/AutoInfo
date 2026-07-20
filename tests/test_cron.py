"""Tests for the scheduled collection (cron) subsystem.

Covers:
    - ``_is_due`` logic with various cron expressions and last_run values
    - Schedule CRUD: add, list, remove via CLI and storage functions
    - ``run_due_schedules`` with mocked collection
    - CLI command output formatting
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from autoinfo.cli.cron import app as cron_app
from autoinfo.cli.cron import (
    Schedule,
    _is_due,
    _now_iso,
    load_schedules,
    run_due_schedules,
    save_schedules,
)


def _make_tzaware(
    year: int, month: int, day: int, hour: int = 0, minute: int = 0
) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


@contextmanager
def _with_schedules_path(tmp_path: Path):
    sched_path = tmp_path / ".autoinfo" / "schedules.yaml"
    sched_path.parent.mkdir(parents=True, exist_ok=True)
    with patch("autoinfo.cli.cron._schedules_path", return_value=sched_path):
        yield sched_path


def _save_test_schedule(tmp_path: Path, **overrides) -> None:
    with _with_schedules_path(tmp_path):
        save_schedules({
            "nightly": Schedule(
                name=overrides.get("name", "nightly"),
                expression=overrides.get("expression", "0 2 * * *"),
                domain=overrides.get("domain", "medical-research"),
                enabled=overrides.get("enabled", True),
                last_run=overrides.get("last_run"),
                created_at=overrides.get("created_at", "2026-07-19T00:00:00+00:00"),
            ),
        })


# ======================================================================
# _now_iso
# ======================================================================


class TestNowIso:
    def test_returns_utc_iso_string(self) -> None:
        result = _now_iso()
        assert isinstance(result, str)
        parsed = datetime.fromisoformat(result)
        assert parsed.tzinfo is not None


# ======================================================================
# _is_due
# ======================================================================


class TestIsDue:
    def test_never_run_is_due(self) -> None:
        assert _is_due("0 2 * * *", last_run=None)

    def test_recent_run_not_due(self) -> None:
        last_run = _make_tzaware(2026, 7, 20, 10, 30).isoformat()
        now = _make_tzaware(2026, 7, 20, 10, 35)
        assert not _is_due("0 * * * *", last_run, now)

    def test_exact_next_match_is_due(self) -> None:
        last_run = _make_tzaware(2026, 7, 20, 10, 30).isoformat()
        now = _make_tzaware(2026, 7, 20, 11, 0)
        assert _is_due("0 * * * *", last_run, now)

    def test_past_next_match_is_due(self) -> None:
        last_run = _make_tzaware(2026, 7, 20, 8, 0).isoformat()
        now = _make_tzaware(2026, 7, 20, 14, 30)
        assert _is_due("0 9 * * *", last_run, now)

    def test_daily_expression(self) -> None:
        last_run = _make_tzaware(2026, 7, 19, 2, 0).isoformat()
        now = _make_tzaware(2026, 7, 20, 10, 0)
        assert _is_due("0 2 * * *", last_run, now)

    def test_daily_expression_same_day_not_due(self) -> None:
        last_run = _make_tzaware(2026, 7, 20, 2, 0).isoformat()
        now = _make_tzaware(2026, 7, 20, 2, 30)
        assert not _is_due("0 2 * * *", last_run, now)

    def test_invalid_expression_raises(self) -> None:
        last_run = _make_tzaware(2026, 7, 20, 10, 0).isoformat()
        from croniter import CroniterBadCronError
        with pytest.raises(CroniterBadCronError):
            _is_due("not-a-cron", last_run)


# ======================================================================
# Schedule storage
# ======================================================================


class TestScheduleStorage:
    def test_round_trip(self, tmp_path: Path) -> None:
        with _with_schedules_path(tmp_path):
            schedules = {
                "nightly": Schedule(
                    name="nightly",
                    expression="0 2 * * *",
                    domain="medical-research",
                    enabled=True,
                    last_run=None,
                    created_at="2026-07-20T00:00:00+00:00",
                ),
            }
            save_schedules(schedules)
            loaded = load_schedules()
        assert "nightly" in loaded
        s = loaded["nightly"]
        assert s.name == "nightly"
        assert s.expression == "0 2 * * *"
        assert s.domain == "medical-research"
        assert s.enabled is True
        assert s.last_run is None
        assert s.created_at == "2026-07-20T00:00:00+00:00"

    def test_load_empty(self, tmp_path: Path) -> None:
        with _with_schedules_path(tmp_path):
            schedules = load_schedules()
        assert schedules == {}

    def test_load_malformed(self, tmp_path: Path) -> None:
        with _with_schedules_path(tmp_path) as sched_path:
            sched_path.write_text("invalid: [yaml: broken\n")
            schedules = load_schedules()
        assert isinstance(schedules, dict)


# ======================================================================
# CLI: add-schedule
# ======================================================================


class TestCliAddSchedule:
    def test_adds_schedule(self, tmp_path: Path, cli_runner: CliRunner) -> None:
        with _with_schedules_path(tmp_path):
            result = cli_runner.invoke(
                cron_app,
                ["add-schedule", "--name", "daily",
                 "--expression", "0 6 * * *",
                 "--domain", "medical-research"],
            )
        assert result.exit_code == 0
        assert "Schedule 'daily' added" in result.stdout

    def test_duplicate_name_fails(
        self, tmp_path: Path, cli_runner: CliRunner
    ) -> None:
        with _with_schedules_path(tmp_path):
            cli_runner.invoke(
                cron_app,
                ["add-schedule", "--name", "daily",
                 "--expression", "0 6 * * *",
                 "--domain", "medical-research"],
            )
            result = cli_runner.invoke(
                cron_app,
                ["add-schedule", "--name", "daily",
                 "--expression", "0 8 * * *",
                 "--domain", "medical-research"],
            )
        assert result.exit_code != 0
        assert "already exists" in result.output

    def test_invalid_expression_fails(
        self, tmp_path: Path, cli_runner: CliRunner
    ) -> None:
        with _with_schedules_path(tmp_path):
            result = cli_runner.invoke(
                cron_app,
                ["add-schedule", "--name", "bad",
                 "--expression", "not-a-cron",
                 "--domain", "medical-research"],
            )
        assert result.exit_code != 0
        assert "not a valid cron expression" in result.output


# ======================================================================
# CLI: list-schedules
# ======================================================================


class TestCliListSchedules:
    def test_list_empty(self, tmp_path: Path, cli_runner: CliRunner) -> None:
        with _with_schedules_path(tmp_path):
            result = cli_runner.invoke(cron_app, ["list-schedules"])
        assert result.exit_code == 0
        assert "No schedules configured" in result.stdout

    def test_list_with_schedules(
        self, tmp_path: Path, cli_runner: CliRunner
    ) -> None:
        with _with_schedules_path(tmp_path):
            save_schedules({
                "nightly": Schedule(
                    name="nightly",
                    expression="0 2 * * *",
                    domain="medical-research",
                    enabled=True,
                    last_run="2026-07-20T02:00:00+00:00",
                    created_at="2026-07-19T00:00:00+00:00",
                ),
            })
            result = cli_runner.invoke(cron_app, ["list-schedules"])
        assert result.exit_code == 0
        assert "nightly" in result.stdout
        assert "0 2 * * *" in result.stdout
        assert "medical-research" in result.stdout

    def test_list_json(self, tmp_path: Path, cli_runner: CliRunner) -> None:
        with _with_schedules_path(tmp_path):
            save_schedules({
                "weekly": Schedule(
                    name="weekly",
                    expression="0 8 * * 1",
                    domain="medical-research",
                    enabled=True,
                    last_run=None,
                    created_at="2026-07-20T00:00:00+00:00",
                ),
            })
            result = cli_runner.invoke(cron_app, ["list-schedules", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "weekly"


# ======================================================================
# CLI: remove-schedule
# ======================================================================


class TestCliRemoveSchedule:
    def test_removes_schedule(
        self, tmp_path: Path, cli_runner: CliRunner
    ) -> None:
        with _with_schedules_path(tmp_path):
            cli_runner.invoke(
                cron_app,
                ["add-schedule", "--name", "toremove",
                 "--expression", "0 2 * * *",
                 "--domain", "medical-research"],
            )
            result = cli_runner.invoke(
                cron_app, ["remove-schedule", "--name", "toremove"]
            )
        assert result.exit_code == 0
        assert "removed" in result.stdout

    def test_remove_nonexistent_fails(
        self, tmp_path: Path, cli_runner: CliRunner
    ) -> None:
        with _with_schedules_path(tmp_path):
            result = cli_runner.invoke(
                cron_app, ["remove-schedule", "--name", "nonexistent"]
            )
        assert result.exit_code != 0
        assert "not found" in result.output


# ======================================================================
# CLI: cron run
# ======================================================================


class TestCliRun:
    def test_no_due_schedules(self, tmp_path: Path, cli_runner: CliRunner) -> None:
        with _with_schedules_path(tmp_path):
            result = cli_runner.invoke(cron_app, ["run"])
        assert result.exit_code == 0
        assert "No schedules are due" in result.stdout

    def test_dry_run_reports_due(
        self, tmp_path: Path, cli_runner: CliRunner
    ) -> None:
        with _with_schedules_path(tmp_path):
            _save_test_schedule(tmp_path)
            result = cli_runner.invoke(cron_app, ["run", "--dry-run"])
        assert result.exit_code == 0
        assert "would run" in result.stdout

    @patch("autoinfo.collect.run_collection")
    def test_runs_due_schedule(
        self,
        mock_run_collection,
        tmp_path: Path,
        cli_runner: CliRunner,
    ) -> None:
        mock_run_collection.return_value = {
            "collection_id": "col-001",
            "domain": "medical-research",
            "total_new": 5,
            "total_found": 10,
            "per_source": [],
            "duration_s": 1.5,
        }
        with _with_schedules_path(tmp_path):
            _save_test_schedule(tmp_path)
            result = cli_runner.invoke(cron_app, ["run"])
        assert result.exit_code == 0
        assert "5 new / 10 found" in result.stdout
        assert "1 of 1" in result.stdout
        mock_run_collection.assert_called_once_with(domain="medical-research")

    @patch("autoinfo.collect.run_collection")
    def test_runs_updates_last_run(
        self,
        mock_run_collection,
        tmp_path: Path,
        cli_runner: CliRunner,
    ) -> None:
        mock_run_collection.return_value = {
            "collection_id": "col-002",
            "domain": "medical-research",
            "total_new": 3,
            "total_found": 7,
            "per_source": [],
            "duration_s": 0.8,
        }
        with _with_schedules_path(tmp_path):
            _save_test_schedule(tmp_path)
            cli_runner.invoke(cron_app, ["run"])
            schedules = load_schedules()
        assert schedules["nightly"].last_run is not None

    @patch("autoinfo.collect.run_collection")
    def test_named_schedule_only(
        self,
        mock_run_collection,
        tmp_path: Path,
        cli_runner: CliRunner,
    ) -> None:
        mock_run_collection.return_value = {
            "collection_id": "col-003",
            "domain": "medical-research",
            "total_new": 2,
            "total_found": 4,
            "per_source": [],
            "duration_s": 0.5,
        }
        with _with_schedules_path(tmp_path):
            save_schedules({
                "a": Schedule(
                    name="a", expression="0 2 * * *",
                    domain="medical-research",
                    enabled=True, last_run=None,
                    created_at="2026-07-19T00:00:00+00:00",
                ),
                "b": Schedule(
                    name="b", expression="0 4 * * *",
                    domain="medical-research",
                    enabled=True, last_run=None,
                    created_at="2026-07-19T00:00:00+00:00",
                ),
            })
            result = cli_runner.invoke(cron_app, ["run", "--name", "a"])
        assert result.exit_code == 0
        mock_run_collection.assert_called_once_with(domain="medical-research")


# ======================================================================
# run_due_schedules (programmatic API)
# ======================================================================


class TestRunDueSchedules:
    @patch("autoinfo.collect.run_collection")
    def test_returns_result_dicts(
        self, mock_run_collection, tmp_path: Path
    ) -> None:
        mock_run_collection.return_value = {
            "collection_id": "col-004",
            "domain": "medical-research",
            "total_new": 5,
            "total_found": 10,
            "per_source": [],
            "duration_s": 1.2,
        }
        with _with_schedules_path(tmp_path):
            _save_test_schedule(tmp_path)
            results = run_due_schedules()
        assert len(results) == 1
        r = results[0]
        assert r["name"] == "nightly"
        assert r["domain"] == "medical-research"
        assert r["ran"] is True

    @patch("autoinfo.collect.run_collection")
    def test_dry_run_skips_collection(
        self, mock_run_collection, tmp_path: Path
    ) -> None:
        with _with_schedules_path(tmp_path):
            _save_test_schedule(tmp_path)
            results = run_due_schedules(dry_run=True)
        assert len(results) == 1
        assert results[0]["dry_run"] is True
        mock_run_collection.assert_not_called()

    @patch("autoinfo.collect.run_collection")
    def test_disabled_schedule_skipped(
        self, mock_run_collection, tmp_path: Path
    ) -> None:
        with _with_schedules_path(tmp_path):
            save_schedules({
                "disabled-sched": Schedule(
                    name="disabled-sched",
                    expression="0 2 * * *",
                    domain="medical-research",
                    enabled=False,
                    last_run=None,
                    created_at="2026-07-19T00:00:00+00:00",
                ),
            })
            results = run_due_schedules()
        assert len(results) == 0
        mock_run_collection.assert_not_called()

    @patch("autoinfo.collect.run_collection")
    def test_schedule_filter(
        self, mock_run_collection, tmp_path: Path
    ) -> None:
        mock_run_collection.return_value = {
            "collection_id": "col-005",
            "domain": "ai-commercial",
            "total_new": 1,
            "total_found": 3,
            "per_source": [],
            "duration_s": 0.6,
        }
        with _with_schedules_path(tmp_path):
            save_schedules({
                "nightly": Schedule(
                    name="nightly",
                    expression="0 2 * * *",
                    domain="medical-research",
                    enabled=True,
                    last_run=None,
                    created_at="2026-07-19T00:00:00+00:00",
                ),
                "weekly": Schedule(
                    name="weekly",
                    expression="0 8 * * 1",
                    domain="ai-commercial",
                    enabled=True,
                    last_run=None,
                    created_at="2026-07-19T00:00:00+00:00",
                ),
            })
            results = run_due_schedules(schedule_filter="weekly")
        assert len(results) == 1
        assert results[0]["name"] == "weekly"
        mock_run_collection.assert_called_once_with(domain="ai-commercial")
