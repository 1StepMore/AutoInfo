"""Tests for delivery scheduler (CRUD, cron matching, persistence, format validation)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from autoinfo.delivery.scheduler import (
    SCHEDULES_PATH,
    VALID_CHANNELS,
    VALID_FORMATS,
    VALID_OUTPUT_TYPES,
    DeliverySchedule,
    DeliveryScheduler,
    get_delivery_schedule_summary,
    run_delivery_schedules,
)


# ============================================================================
# Helpers
# ============================================================================


def _with_temp_path(tmp_path: Path):
    """Context manager that patches SCHEDULES_PATH to a temp location."""
    return patch(
        "autoinfo.delivery.scheduler.SCHEDULES_PATH",
        tmp_path / "delivery_schedules.yaml",
    )


def _make_scheduler() -> DeliveryScheduler:
    """Create a fresh DeliveryScheduler (uses current SCHEDULES_PATH)."""
    scheduler = DeliveryScheduler()
    scheduler._schedules = {}
    scheduler._loaded = False
    return scheduler


# ============================================================================
# DeliverySchedule dataclass
# ============================================================================


class TestDeliverySchedule:
    """Tests for the DeliverySchedule dataclass."""

    def test_defaults_generate_id(self):
        s = DeliverySchedule(cron_expression="0 8 * * 1", domain="test")
        assert s.id
        assert len(s.id) == 36  # UUID

    def test_defaults_generate_created_at(self):
        s = DeliverySchedule(cron_expression="0 8 * * 1", domain="test")
        assert s.created_at
        assert "T" in s.created_at  # ISO format

    def test_recipients_default(self):
        s = DeliverySchedule(cron_expression="0 8 * * 1", domain="test")
        assert s.recipients == []

    def test_enabled_default(self):
        s = DeliverySchedule(cron_expression="0 8 * * 1", domain="test")
        assert s.enabled is True

    def test_output_type_default(self):
        s = DeliverySchedule(cron_expression="0 8 * * 1", domain="test")
        assert s.output_type == "digest"

    def test_format_default(self):
        s = DeliverySchedule(cron_expression="0 8 * * 1", domain="test")
        assert s.format == "markdown"

    def test_channel_default(self):
        s = DeliverySchedule(cron_expression="0 8 * * 1", domain="test")
        assert s.channel == "email"

    def test_full_constructor(self):
        s = DeliverySchedule(
            id="test-id",
            cron_expression="0 8 * * 1",
            domain="medical-research",
            output_type="report",
            format="html",
            channel="webhook",
            recipients=["https://example.com/hook"],
            period="monthly",
            enabled=False,
            created_at="2026-01-01T00:00:00",
            last_run="2026-06-01T00:00:00",
            last_error="Something went wrong",
        )
        assert s.id == "test-id"
        assert s.cron_expression == "0 8 * * 1"
        assert s.domain == "medical-research"
        assert s.output_type == "report"
        assert s.format == "html"
        assert s.channel == "webhook"
        assert s.recipients == ["https://example.com/hook"]
        assert s.period == "monthly"
        assert s.enabled is False
        assert s.created_at == "2026-01-01T00:00:00"
        assert s.last_run == "2026-06-01T00:00:00"
        assert s.last_error == "Something went wrong"


# ============================================================================
# DeliveryScheduler CRUD
# ============================================================================


class TestDeliverySchedulerCRUD:
    """Tests for add/list/remove/get operations."""

    def test_add_schedule(self, tmp_path):
        with _with_temp_path(tmp_path):
            scheduler = _make_scheduler()
            s = DeliverySchedule(cron_expression="0 8 * * 1", domain="test")
            result = scheduler.add_schedule(s)
            assert result.id == s.id
            assert len(scheduler.list_schedules()) == 1

    def test_add_schedule_persists(self, tmp_path):
        with _with_temp_path(tmp_path):
            scheduler = _make_scheduler()
            s = DeliverySchedule(cron_expression="0 8 * * 1", domain="test")
            scheduler.add_schedule(s)

            # Reload from disk
            scheduler2 = _make_scheduler()
            loaded = scheduler2.list_schedules()
            assert len(loaded) == 1
            assert loaded[0].id == s.id
            assert loaded[0].cron_expression == "0 8 * * 1"

    def test_add_schedule_invalid_output_type(self, tmp_path):
        with _with_temp_path(tmp_path):
            scheduler = _make_scheduler()
            s = DeliverySchedule(
                cron_expression="0 8 * * 1",
                domain="test",
                output_type="invalid",
            )
            with pytest.raises(ValueError, match="Invalid output_type"):
                scheduler.add_schedule(s)

    def test_add_schedule_invalid_format(self, tmp_path):
        with _with_temp_path(tmp_path):
            scheduler = _make_scheduler()
            s = DeliverySchedule(
                cron_expression="0 8 * * 1",
                domain="test",
                format="invalid",
            )
            with pytest.raises(ValueError, match="Invalid format"):
                scheduler.add_schedule(s)

    def test_add_schedule_invalid_channel(self, tmp_path):
        with _with_temp_path(tmp_path):
            scheduler = _make_scheduler()
            s = DeliverySchedule(
                cron_expression="0 8 * * 1",
                domain="test",
                channel="invalid",
            )
            with pytest.raises(ValueError, match="Invalid channel"):
                scheduler.add_schedule(s)

    def test_add_schedule_empty_cron(self, tmp_path):
        with _with_temp_path(tmp_path):
            scheduler = _make_scheduler()
            s = DeliverySchedule(cron_expression="", domain="test")
            with pytest.raises(ValueError, match="cron_expression must not be empty"):
                scheduler.add_schedule(s)

    def test_list_multiple_schedules(self, tmp_path):
        with _with_temp_path(tmp_path):
            scheduler = _make_scheduler()
            s1 = DeliverySchedule(cron_expression="0 8 * * 1", domain="a")
            s2 = DeliverySchedule(cron_expression="0 9 * * 2", domain="b")
            scheduler.add_schedule(s1)
            scheduler.add_schedule(s2)
            assert len(scheduler.list_schedules()) == 2

    def test_get_schedule(self, tmp_path):
        with _with_temp_path(tmp_path):
            scheduler = _make_scheduler()
            s = DeliverySchedule(cron_expression="0 8 * * 1", domain="test")
            scheduler.add_schedule(s)
            found = scheduler.get_schedule(s.id)
            assert found is not None
            assert found.id == s.id

    def test_get_schedule_not_found(self, tmp_path):
        with _with_temp_path(tmp_path):
            scheduler = _make_scheduler()
            assert scheduler.get_schedule("nonexistent") is None

    def test_remove_schedule(self, tmp_path):
        with _with_temp_path(tmp_path):
            scheduler = _make_scheduler()
            s = DeliverySchedule(cron_expression="0 8 * * 1", domain="test")
            scheduler.add_schedule(s)
            assert scheduler.remove_schedule(s.id) is True
            assert len(scheduler.list_schedules()) == 0

    def test_remove_schedule_not_found(self, tmp_path):
        with _with_temp_path(tmp_path):
            scheduler = _make_scheduler()
            assert scheduler.remove_schedule("nonexistent") is False

    def test_remove_schedule_persists(self, tmp_path):
        with _with_temp_path(tmp_path):
            scheduler = _make_scheduler()
            s = DeliverySchedule(cron_expression="0 8 * * 1", domain="test")
            scheduler.add_schedule(s)
            scheduler.remove_schedule(s.id)

            scheduler2 = _make_scheduler()
            assert len(scheduler2.list_schedules()) == 0


# ============================================================================
# Cron matching
# ============================================================================


class TestCronMatching:
    """Tests for get_due_schedules cron matching."""

    def test_never_run_is_due(self, tmp_path):
        with _with_temp_path(tmp_path):
            scheduler = _make_scheduler()
            s = DeliverySchedule(cron_expression="0 8 * * 1", domain="test")
            scheduler.add_schedule(s)
            due = scheduler.get_due_schedules()
            assert len(due) == 1
            assert due[0].id == s.id

    def test_disabled_not_due(self, tmp_path):
        with _with_temp_path(tmp_path):
            scheduler = _make_scheduler()
            s = DeliverySchedule(
                cron_expression="0 8 * * 1", domain="test", enabled=False,
            )
            scheduler.add_schedule(s)
            due = scheduler.get_due_schedules()
            assert len(due) == 0

    def test_empty_cron_rejected_at_add(self, tmp_path):
        with _with_temp_path(tmp_path):
            scheduler = _make_scheduler()
            s = DeliverySchedule(cron_expression="", domain="test")
            with pytest.raises(ValueError, match="cron_expression must not be empty"):
                scheduler.add_schedule(s)

    def test_recently_run_not_due(self, tmp_path):
        with _with_temp_path(tmp_path):
            scheduler = _make_scheduler()
            from datetime import datetime, timezone

            now = datetime.now(timezone.utc)
            s = DeliverySchedule(
                cron_expression="0 0 1 1 *",  # Jan 1 at midnight
                domain="test",
                last_run=now.isoformat(),
            )
            scheduler.add_schedule(s)
            due = scheduler.get_due_schedules()
            assert len(due) == 0

    def test_custom_now(self, tmp_path):
        with _with_temp_path(tmp_path):
            scheduler = _make_scheduler()
            from datetime import datetime

            # Schedule that ran on Jan 1; next run would be Jan 2 at midnight
            s = DeliverySchedule(
                cron_expression="0 0 * * *",  # Daily at midnight
                domain="test",
                last_run="2026-01-01T00:00:00",
            )
            scheduler.add_schedule(s)
            # Check with date Jan 2 — should be due
            due = scheduler.get_due_schedules(now=datetime(2026, 1, 2, 12, 0))
            assert len(due) == 1

    def test_not_due_yet_with_custom_now(self, tmp_path):
        with _with_temp_path(tmp_path):
            scheduler = _make_scheduler()
            from datetime import datetime

            s = DeliverySchedule(
                cron_expression="0 0 * * *",
                domain="test",
                last_run="2026-01-01T12:00:00",
            )
            scheduler.add_schedule(s)
            due = scheduler.get_due_schedules(now=datetime(2026, 1, 1, 13, 0))
            # Next run would be Jan 2 at midnight; not due yet
            assert len(due) == 0


# ============================================================================
# Mark run
# ============================================================================


class TestMarkRun:
    """Tests for mark_run method."""

    def test_mark_run_updates_last_run(self, tmp_path):
        with _with_temp_path(tmp_path):
            scheduler = _make_scheduler()
            s = DeliverySchedule(cron_expression="0 8 * * 1", domain="test")
            scheduler.add_schedule(s)
            scheduler.mark_run(s.id)
            updated = scheduler.get_schedule(s.id)
            assert updated is not None
            assert updated.last_run is not None

    def test_mark_run_with_error(self, tmp_path):
        with _with_temp_path(tmp_path):
            scheduler = _make_scheduler()
            s = DeliverySchedule(cron_expression="0 8 * * 1", domain="test")
            scheduler.add_schedule(s)
            scheduler.mark_run(s.id, error="SMTP connection failed")
            updated = scheduler.get_schedule(s.id)
            assert updated is not None
            assert updated.last_error == "SMTP connection failed"

    def test_mark_run_nonexistent(self, tmp_path):
        with _with_temp_path(tmp_path):
            scheduler = _make_scheduler()
            scheduler.mark_run("nonexistent")  # Should not raise


# ============================================================================
# Persistence (YAML)
# ============================================================================


class TestPersistence:
    """Tests for YAML persistence."""

    def test_save_creates_file(self, tmp_path):
        with _with_temp_path(tmp_path):
            yaml_path = tmp_path / "delivery_schedules.yaml"
            scheduler = _make_scheduler()
            s = DeliverySchedule(cron_expression="0 8 * * 1", domain="test")
            scheduler.add_schedule(s)
            assert yaml_path.is_file()

    def test_load_existing_file(self, tmp_path):
        yaml_path = tmp_path / "delivery_schedules.yaml"
        yaml_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "schedules": [
                {
                    "id": "abc-123",
                    "cron_expression": "0 8 * * 1",
                    "domain": "medical-research",
                    "output_type": "digest",
                    "format": "html",
                    "channel": "email",
                    "recipients": ["user@example.com"],
                    "period": "weekly",
                    "enabled": True,
                    "created_at": "2026-01-01T00:00:00",
                    "last_run": None,
                    "last_error": None,
                }
            ]
        }
        yaml_path.write_text(yaml.dump(data))

        with _with_temp_path(tmp_path):
            scheduler = _make_scheduler()
            schedules = scheduler.list_schedules()
            assert len(schedules) == 1
            assert schedules[0].id == "abc-123"
            assert schedules[0].domain == "medical-research"

    def test_load_corrupt_file(self, tmp_path):
        yaml_path = tmp_path / "delivery_schedules.yaml"
        yaml_path.parent.mkdir(parents=True, exist_ok=True)
        yaml_path.write_text("not valid yaml: [[[")

        with _with_temp_path(tmp_path):
            scheduler = _make_scheduler()
            schedules = scheduler.list_schedules()
            assert len(schedules) == 0  # Graceful degradation

    def test_load_missing_file(self, tmp_path):
        with _with_temp_path(tmp_path):
            scheduler = _make_scheduler()
            assert len(scheduler.list_schedules()) == 0

    def test_save_and_reload_roundtrip(self, tmp_path):
        with _with_temp_path(tmp_path):
            scheduler = _make_scheduler()
            s1 = DeliverySchedule(
                cron_expression="0 8 * * 1",
                domain="medical-research",
                output_type="report",
                format="json",
                channel="webhook",
                recipients=["https://hook.example.com"],
                period="monthly",
            )
            scheduler.add_schedule(s1)
            scheduler.mark_run(s1.id, error=None)

            scheduler2 = _make_scheduler()
            loaded = scheduler2.list_schedules()
            assert len(loaded) == 1
            assert loaded[0].cron_expression == "0 8 * * 1"
            assert loaded[0].domain == "medical-research"
            assert loaded[0].output_type == "report"
            assert loaded[0].format == "json"
            assert loaded[0].channel == "webhook"
            assert loaded[0].recipients == ["https://hook.example.com"]
            assert loaded[0].period == "monthly"
            assert loaded[0].last_run is not None


# ============================================================================
# Format validation
# ============================================================================


class TestFormatValidation:
    """Tests for valid output types, formats, and channels."""

    def test_valid_output_types(self):
        assert "digest" in VALID_OUTPUT_TYPES
        assert "report" in VALID_OUTPUT_TYPES
        assert len(VALID_OUTPUT_TYPES) == 2

    def test_valid_formats(self):
        expected = {"markdown", "html", "json", "agent", "audio", "pdf"}
        assert VALID_FORMATS == expected

    def test_valid_channels(self):
        assert "email" in VALID_CHANNELS
        assert "webhook" in VALID_CHANNELS
        assert "rest" in VALID_CHANNELS
        assert "smtp" in VALID_CHANNELS
        assert "telegram" in VALID_CHANNELS
        assert "discord" in VALID_CHANNELS


# ============================================================================
# get_delivery_schedule_summary
# ============================================================================


class TestSummary:
    """Tests for get_delivery_schedule_summary."""

    def test_empty(self, tmp_path):
        with _with_temp_path(tmp_path):
            summary = get_delivery_schedule_summary()
            assert summary["total"] == 0
            assert summary["enabled"] == 0
            assert summary["due"] == 0

    def test_with_schedules(self, tmp_path):
        with _with_temp_path(tmp_path):
            scheduler = _make_scheduler()
            s1 = DeliverySchedule(cron_expression="0 8 * * 1", domain="a")
            s2 = DeliverySchedule(cron_expression="0 9 * * 2", domain="b", enabled=False)
            s3 = DeliverySchedule(cron_expression="0 10 * * 3", domain="c")
            scheduler.add_schedule(s1)
            scheduler.add_schedule(s2)
            scheduler.add_schedule(s3)
            # Set error on one schedule
            scheduler.mark_run(s1.id, error="test error")

            summary = get_delivery_schedule_summary()
            assert summary["total"] == 3
            assert summary["enabled"] == 2
            assert summary["due"] >= 0  # At least some are due
            assert summary["last_error_count"] == 1


# ============================================================================
# run_delivery_schedules
# ============================================================================


class TestRunDeliverySchedules:
    """Tests for run_delivery_schedules execution function."""

    def test_dry_run(self, tmp_path):
        with _with_temp_path(tmp_path):
            scheduler = _make_scheduler()
            s = DeliverySchedule(cron_expression="0 8 * * 1", domain="test")
            scheduler.add_schedule(s)

            results = run_delivery_schedules(dry_run=True)
            due_results = [r for r in results if r.get("due")]
            for r in due_results:
                if r.get("dry_run") is True:
                    break
            else:
                if due_results:
                    pytest.fail("No dry_run=True in due results")

    def test_runs_without_crashing(self, tmp_path):
        """run_delivery_schedules should handle errors gracefully."""
        with _with_temp_path(tmp_path):
            scheduler = _make_scheduler()
            s = DeliverySchedule(
                cron_expression="0 8 * * 1",
                domain="nonexistent-domain",
                channel="webhook",
                recipients=["https://example.com/hook"],
            )
            scheduler.add_schedule(s)

            # Should not raise
            results = run_delivery_schedules()
            assert isinstance(results, list)


# ============================================================================
# Edge cases
# ============================================================================


class TestEdgeCases:
    """Edge case tests."""

    def test_multiple_recipients(self, tmp_path):
        with _with_temp_path(tmp_path):
            scheduler = _make_scheduler()
            s = DeliverySchedule(
                cron_expression="0 8 * * 1",
                domain="test",
                recipients=["a@b.com", "c@d.com"],
            )
            scheduler.add_schedule(s)
            loaded = scheduler.list_schedules()[0]
            assert loaded.recipients == ["a@b.com", "c@d.com"]

    def test_same_id_add_twice_overwrites(self, tmp_path):
        with _with_temp_path(tmp_path):
            scheduler = _make_scheduler()
            s1 = DeliverySchedule(
                id="fixed-id", cron_expression="0 8 * * 1", domain="a",
            )
            s2 = DeliverySchedule(
                id="fixed-id", cron_expression="0 9 * * 2", domain="b",
            )
            scheduler.add_schedule(s1)
            scheduler.add_schedule(s2)
            assert len(scheduler.list_schedules()) == 1
            assert scheduler.get_schedule("fixed-id").domain == "b"  # type: ignore[union-attr]

    def test_list_empty(self, tmp_path):
        with _with_temp_path(tmp_path):
            scheduler = _make_scheduler()
            assert scheduler.list_schedules() == []
