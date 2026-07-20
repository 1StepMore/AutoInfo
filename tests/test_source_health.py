"""Tests for per-source health monitoring (F18) and user feedback (F29).

Covers:
    - ``get_source_health()`` status: healthy, degraded, error, paused, unknown
    - ``rate_item()`` stores rating/feedback in SQLite
    - ``_log_run`` extended format (status, errors, duration_ms)
    - MCP handler wiring for ``get_source_health`` and ``rate_item``
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from autoinfo.collect import _log_run
from autoinfo.status import get_source_health, rate_item


# ======================================================================
# Helpers
# ======================================================================


@pytest.fixture
def proj_dir(tmp_path: Path) -> Path:
    """Create a project skeleton with ``.autoinfo/config.yaml``."""
    config_dir = tmp_path / ".autoinfo"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.yaml").write_text(
        "project:\n  name: Test\n  created_at: 2026-07-01\n"
        "llm:\n  provider: openrouter\n  model: test\n  api_key: sk-test\n"
        "domains:\n"
        "  - name: medical-research\n    active: true\n"
        "    sources:\n"
        "      - name: pubmed\n        type: api\n"
        "        url: https://eutils.ncbi.nlm.nih.gov\n"
        "    topics:\n"
        "      - name: IVF\n        keywords: [IVF]\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def chdir_proj(proj_dir: Path) -> Path:
    """Change to *proj_dir* so relative ``Path('collections')`` resolves there."""
    old_cwd = Path.cwd()
    os.chdir(str(proj_dir))
    yield proj_dir
    os.chdir(str(old_cwd))


def _make_runs(
    path: Path,
    entries: list[dict],
) -> None:
    """Write a ``_runs.json`` file with *entries*."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def _ts(days_ago: int = 0) -> str:
    """Return an ISO timestamp *days_ago* days from now."""
    dt = datetime.now(timezone.utc)
    if days_ago:
        dt = dt.replace(day=dt.day - days_ago)
    return dt.isoformat()


# ======================================================================
# _log_run — extended format
# ======================================================================


class TestLogRunExtended:
    def test_success_run_sets_duration_and_status(self, chdir_proj: Path) -> None:
        """A successful run records duration_ms and status."""
        _log_run(
            domain="test-domain",
            source_name="test-source",
            collection_id="col-001",
            items_found=10,
            items_new=5,
            status="success",
            duration_s=2.5,
        )

        runs_path = chdir_proj / "collections" / "test-domain" / "test-source" / "_runs.json"
        assert runs_path.is_file()
        runs = json.loads(runs_path.read_text(encoding="utf-8"))
        assert len(runs) == 1
        entry = runs[0]
        assert entry["status"] == "success"
        assert entry["duration_ms"] == 2500.0
        assert entry["items_found"] == 10
        assert entry["items_new"] == 5
        assert entry["errors"] == []

    def test_error_run_records_errors(self, chdir_proj: Path) -> None:
        """An error run stores error details and status='error'."""
        _log_run(
            domain="test-domain",
            source_name="test-source",
            collection_id="col-002",
            items_found=0,
            items_new=0,
            status="error",
            errors=[{"message": "Connection refused"}],
            duration_s=1.2,
        )

        runs_path = chdir_proj / "collections" / "test-domain" / "test-source" / "_runs.json"
        runs = json.loads(runs_path.read_text(encoding="utf-8"))
        assert len(runs) == 1
        entry = runs[0]
        assert entry["status"] == "error"
        assert entry["errors"] == [{"message": "Connection refused"}]
        assert entry["duration_ms"] == 1200.0

    def test_skipped_run_has_status_skipped(self, chdir_proj: Path) -> None:
        """A skipped run records status='skipped'."""
        _log_run(
            domain="test-domain",
            source_name="test-source",
            collection_id="col-003",
            items_found=0,
            items_new=0,
            status="skipped",
            errors=[{"message": "Unsupported source type"}],
            duration_s=0.0,
        )

        runs_path = chdir_proj / "collections" / "test-domain" / "test-source" / "_runs.json"
        runs = json.loads(runs_path.read_text(encoding="utf-8"))
        assert runs[-1]["status"] == "skipped"


# ======================================================================
# get_source_health — status determination
# ======================================================================


class TestGetSourceHealth:
    def test_invalid_source_id_format(self) -> None:
        """Missing colon returns an error."""
        result = get_source_health("nosourceid")
        assert "error_code" in result
        assert result["error_code"] == "InvalidSourceId"

    def test_unknown_when_no_runs_file(self, chdir_proj: Path) -> None:
        """No _runs.json yields status 'unknown'."""
        result = get_source_health("test-domain:test-source")
        assert result["status"] == "unknown"

    def test_unknown_when_runs_empty(self, chdir_proj: Path) -> None:
        """Empty _runs.json yields status 'unknown'."""
        runs_path = chdir_proj / "collections" / "test-domain" / "test-source" / "_runs.json"
        _make_runs(runs_path, [])
        result = get_source_health("test-domain:test-source")
        assert result["status"] == "unknown"

    def test_healthy_after_successful_run(self, chdir_proj: Path) -> None:
        """A successful recent run yields status 'healthy'."""
        runs_path = chdir_proj / "collections" / "test-domain" / "test-source" / "_runs.json"
        _make_runs(runs_path, [
            {
                "collection_id": "col-001",
                "timestamp": _ts(),
                "status": "success",
                "items_found": 10,
                "items_new": 5,
                "errors": [],
                "duration_ms": 1200.0,
            },
        ])
        result = get_source_health("test-domain:test-source")
        assert result["status"] == "healthy"
        assert result["error_count"] == 0
        assert result["avg_response_time_ms"] == 1200.0

    @pytest.mark.parametrize("consecutive_fails", [3, 4, 10])
    def test_error_after_three_consecutive_failures(
        self, chdir_proj: Path, consecutive_fails: int,
    ) -> None:
        """3+ consecutive errors yields status 'error'."""
        runs = []
        for i in range(consecutive_fails):
            runs.append({
                "collection_id": f"col-{i:03d}",
                "timestamp": _ts(days_ago=i),
                "status": "error",
                "items_found": 0,
                "items_new": 0,
                "errors": [{"message": "Timeout"}],
                "duration_ms": 5000.0,
            })
        runs_path = chdir_proj / "collections" / "test-domain" / "test-source" / "_runs.json"
        _make_runs(runs_path, runs)
        result = get_source_health("test-domain:test-source")
        assert result["status"] == "error"
        assert result["error_count"] == consecutive_fails

    def test_degraded_after_one_failure(self, chdir_proj: Path) -> None:
        """A single failure with prior success yields status 'degraded'."""
        runs_path = chdir_proj / "collections" / "test-domain" / "test-source" / "_runs.json"
        _make_runs(runs_path, [
            {
                "collection_id": "col-001",
                "timestamp": _ts(days_ago=2),
                "status": "success",
                "items_found": 10,
                "items_new": 5,
                "errors": [],
                "duration_ms": 800.0,
            },
            {
                "collection_id": "col-002",
                "timestamp": _ts(),
                "status": "error",
                "items_found": 0,
                "items_new": 0,
                "errors": [{"message": "Rate limited"}],
                "duration_ms": 3000.0,
            },
        ])
        result = get_source_health("test-domain:test-source")
        assert result["status"] == "degraded"

    def test_degraded_when_slow(self, chdir_proj: Path) -> None:
        """Slow responses (>5s avg) yield 'degraded' even without errors."""
        runs_path = chdir_proj / "collections" / "test-domain" / "test-source" / "_runs.json"
        _make_runs(runs_path, [
            {
                "collection_id": "col-001",
                "timestamp": _ts(),
                "status": "success",
                "items_found": 3,
                "items_new": 1,
                "errors": [],
                "duration_ms": 6000.0,
            },
        ])
        result = get_source_health("test-domain:test-source")
        assert result["status"] == "degraded"

    def test_paused_when_marker_exists(self, chdir_proj: Path) -> None:
        """A _paused file yields status 'paused'."""
        source_dir = chdir_proj / "collections" / "test-domain" / "test-source"
        source_dir.mkdir(parents=True, exist_ok=True)
        (source_dir / "_paused").touch()
        result = get_source_health("test-domain:test-source")
        assert result["status"] == "paused"

    def test_corrupt_runs_json(self, chdir_proj: Path) -> None:
        """Corrupt _runs.json yields status 'error'."""
        runs_path = chdir_proj / "collections" / "test-domain" / "test-source" / "_runs.json"
        runs_path.parent.mkdir(parents=True, exist_ok=True)
        runs_path.write_text("not valid json", encoding="utf-8")
        result = get_source_health("test-domain:test-source")
        assert result["status"] == "error"

    def test_legacy_runs_without_status_field(self, chdir_proj: Path) -> None:
        """Legacy _runs.json entries (no 'status' field) are treated as success."""
        runs_path = chdir_proj / "collections" / "test-domain" / "test-source" / "_runs.json"
        _make_runs(runs_path, [
            {
                "collection_id": "col-001",
                "timestamp": _ts(),
                # no 'status' field — legacy format
                "items_found": 5,
                "items_new": 3,
            },
        ])
        result = get_source_health("test-domain:test-source")
        assert result["status"] == "healthy"
        assert result["error_count"] == 0

    def test_resets_after_success_following_errors(self, chdir_proj: Path) -> None:
        """A success after 2 errors resets consecutive count (healthy)."""
        runs_path = chdir_proj / "collections" / "test-domain" / "test-source" / "_runs.json"
        _make_runs(runs_path, [
            {
                "collection_id": "col-001",
                "timestamp": _ts(days_ago=5),
                "status": "error",
                "items_found": 0,
                "items_new": 0,
                "errors": [{"message": "Timeout"}],
                "duration_ms": 5000.0,
            },
            {
                "collection_id": "col-002",
                "timestamp": _ts(days_ago=3),
                "status": "error",
                "items_found": 0,
                "items_new": 0,
                "errors": [{"message": "Timeout"}],
                "duration_ms": 5000.0,
            },
            {
                "collection_id": "col-003",
                "timestamp": _ts(),
                "status": "success",
                "items_found": 10,
                "items_new": 5,
                "errors": [],
                "duration_ms": 1000.0,
            },
        ])
        result = get_source_health("test-domain:test-source")
        assert result["status"] == "healthy"
        assert result["error_count"] == 2


# ======================================================================
# rate_item — user feedback storage
# ======================================================================


class TestRateItem:
    def test_stores_rating_in_db(self, chdir_proj: Path) -> None:
        """A valid rating is stored and returns recorded=True."""
        result = rate_item(item_id="item-001", rating=4, feedback="Great article!")

        assert result["recorded"] is True
        assert result["item_id"] == "item-001"
        assert result["rating"] == 4
        assert result["feedback"] == "Great article!"

        # Verify in DB (stored in .autoinfo/ next to config)
        db_path = chdir_proj / ".autoinfo" / "autoinfo.db"
        conn = sqlite3.connect(str(db_path))
        rows = conn.execute(
            "SELECT item_id, rating, feedback FROM feedback",
        ).fetchall()
        conn.close()
        assert rows == [("item-001", 4, "Great article!")]

    def test_rejects_invalid_rating(self) -> None:
        """Rating outside 1-5 returns an error."""
        for bad_rating in (0, 6, -1, 100):
            result = rate_item(item_id="item-x", rating=bad_rating)
            assert "error_code" in result
            assert result["error_code"] == "InvalidRating"

    def test_stores_rating_without_feedback(self, chdir_proj: Path) -> None:
        """Feedback is optional — stores empty string when omitted."""
        result = rate_item(item_id="item-002", rating=3)

        assert result["recorded"] is True
        assert result["feedback"] == ""

    def test_multiple_ratings_same_item(self, chdir_proj: Path) -> None:
        """Multiple ratings for the same item are appended (not replaced)."""
        rate_item(item_id="item-003", rating=2)
        result = rate_item(item_id="item-003", rating=5, feedback="Changed my mind")

        assert result["recorded"] is True
        db_path = chdir_proj / ".autoinfo" / "autoinfo.db"
        conn = sqlite3.connect(str(db_path))
        rows = conn.execute(
            "SELECT rating, feedback FROM feedback WHERE item_id = ? ORDER BY id",
            ("item-003",),
        ).fetchall()
        conn.close()
        assert rows == [(2, ""), (5, "Changed my mind")]


# ======================================================================
# MCP handler integration
# ======================================================================


class TestMcpGetSourceHealth:
    def test_handler_delegates_to_status(self, chdir_proj: Path) -> None:
        """_handle_get_source_health calls status.get_source_health."""
        from autoinfo.mcp.server import _handle_get_source_health

        runs_path = chdir_proj / "collections" / "test-domain" / "mcp-source" / "_runs.json"
        _make_runs(runs_path, [
            {
                "collection_id": "col-001",
                "timestamp": _ts(),
                "status": "success",
                "items_found": 5,
                "items_new": 3,
                "errors": [],
                "duration_ms": 500.0,
            },
        ])
        result = _handle_get_source_health(source_id="test-domain:mcp-source")
        assert result["status"] == "healthy"
        assert result["source_id"] == "test-domain:mcp-source"


class TestMcpRateItem:
    def test_handler_delegates_to_status(self, chdir_proj: Path) -> None:
        """_handle_rate_item calls status.rate_item."""
        from autoinfo.mcp.server import _handle_rate_item

        result = _handle_rate_item(item_id="mcp-item", rating=5, feedback="Excellent!")

        assert result["recorded"] is True
        assert result["rating"] == 5
