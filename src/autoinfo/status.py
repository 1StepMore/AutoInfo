"""System status, per-source health monitoring (F18), and user feedback (F29).

Provides:

* ``show_status()`` — domain-level summary used by ``autoinfo status``.
* ``get_source_health()`` — per-source health from ``_runs.json``.
* ``rate_item()`` — store user ratings/feedback in SQLite.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

from autoinfo.config import (
    Config,
    get_config_path,
    load_config,
)
from autoinfo.kb import SQLiteIndex
from autoinfo.models import SourceHealth

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def show_status(domain: str | None = None) -> dict[str, Any]:
    """Return a structured status overview for one or all domains.

    Reads the SQLite index for entry counts and collection run logs for
    per-source health information.

    Parameters
    ----------
    domain : str | None
        If given, only status for this domain is returned.  When ``None``,
        every configured domain is included.

    Returns
    -------
    dict
        ``{domains: [{name, items_today, total_entries, source_health: [{name, status}]}]}``

    Raises
    ------
    FileNotFoundError
        If no configuration file is found.
    ValueError
        If *domain* is specified but not in configuration.
    """
    config_path = get_config_path()
    if config_path is None:
        raise FileNotFoundError(
            "No configuration found. Run 'autoinfo init' first."
        )
    config = load_config(config_path)

    # -- Resolve which domains to report on ---------------------------------
    target_domains = _resolve_domains(config, domain)
    if not target_domains:
        raise ValueError(
            f"Domain '{domain}' not found in configuration."
            if domain
            else "No active domains configured."
        )

    # -- Locate the SQLite index --------------------------------------------
    autoinfo_dir = config_path.parent
    db_path = autoinfo_dir / "autoinfo.db"
    index = SQLiteIndex(db_path) if db_path.exists() else None

    domains_status: list[dict[str, Any]] = []
    for d in target_domains:
        # Entry counts (with filesystem fallback when SQLite is empty)
        total_entries = index.count_entries(d.name) if index else 0
        items_today = index.count_entries_today(d.name) if index else 0

        # If SQLite returned 0 but files exist on disk, count from filesystem
        if total_entries == 0:
            kb_base = config_path.parent.parent / "knowledge"
            domain_path = kb_base / d.name
            if domain_path.is_dir():
                fs_files = list(domain_path.rglob("*.md"))
                total_entries = len(fs_files)
                # Estimate today: count files whose path contains today's date
                from datetime import date
                today_str = date.today().isoformat()
                items_today = sum(1 for f in fs_files if today_str in f.name)

        # Per-source health from collection run logs
        source_health = _collect_source_health(config_path.parent, d.name, d.sources)

        domains_status.append(
            {
                "name": d.name,
                "items_today": items_today,
                "total_entries": total_entries,
                "source_health": source_health,
            }
        )

    return {"domains": domains_status}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_domains(config: Config, domain: str | None) -> list[Any]:
    """Return the list of domain configs to report on."""
    if domain:
        for d in config.domains:
            if d.name == domain:
                return [d]
        return []
    # All active domains
    return [d for d in config.domains if d.active]


def _collect_source_health(
    autoinfo_dir: Path,
    domain_name: str,
    source_configs: list[Any],
) -> list[dict[str, Any]]:
    """Check the health of each source based on its collection run log.

    Reads ``collections/<domain>/<source>/_runs.json`` to determine the
    status of each source.  A source is considered *healthy* if it has at
    least one successful run and the most recent run is within the last
    7 days.  Otherwise it is *stale* or *unknown*.
    """
    health: list[dict[str, Any]] = []

    for src in source_configs:
        runs_file = (
            autoinfo_dir.parent
            / "collections"
            / domain_name
            / src.name
            / "_runs.json"
        )

        status: str
        last_run: str = ""
        total_runs: int = 0

        if runs_file.is_file():
            try:
                runs = json.loads(runs_file.read_text(encoding="utf-8"))
                total_runs = len(runs)
                if total_runs > 0:
                    last_run = runs[-1].get("timestamp", "")
                    if _is_recent(last_run, days=7):
                        status = "healthy"
                    else:
                        status = "stale"
                else:
                    status = "unknown"
            except (json.JSONDecodeError, OSError):
                status = "error"
        else:
            status = "unknown"

        health.append(
            {
                "name": src.name,
                "status": status,
                "last_run": last_run,
                "total_runs": total_runs,
            }
        )

    return health


def _is_recent(timestamp: str, days: int = 7) -> bool:
    """Check whether an ISO timestamp falls within the last *days* days."""
    if not timestamp:
        return False
    try:
        from datetime import datetime

        ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        delta = date.today() - ts.date()
        return delta.days <= days
    except (ValueError, TypeError):
        return False


# ===================================================================
# F18 — Per-source health monitoring
# ===================================================================


def get_source_health(source_id: str) -> dict[str, Any]:
    """Return health status for a single source.

    Reads ``collections/<domain>/<source>/_runs.json`` and computes
    the source health based on run history.

    Parameters
    ----------
    source_id:
        Source identifier in ``domain:name`` format.

    Returns
    -------
    dict
        ``SourceHealth`` fields plus an ``error_code`` on failure::

            {source_id, status, last_success, error_count,
             avg_response_time_ms}

    Health statuses
    ---------------
    * ``healthy`` — last run succeeded, <3 consecutive failures
    * ``degraded`` — last run failed (<3 consecutively) or slow
    * ``error`` — 3+ consecutive failures
    * ``paused`` — ``_paused`` marker file exists
    * ``unknown`` — no runs recorded
    """
    # -- Parse source_id -------------------------------------------------
    parts = source_id.split(":", 1)
    if len(parts) != 2:
        return {
            "error_code": "InvalidSourceId",
            "message": "source_id must be in 'domain:name' format",
        }

    domain, source_name = parts
    health = SourceHealth(source_id=source_id)

    # -- Check for paused marker -----------------------------------------
    paused_path = Path("collections") / domain / source_name / "_paused"
    if paused_path.is_file():
        health.status = "paused"
        return health.to_dict()

    # -- Read runs -------------------------------------------------------
    runs_path = Path("collections") / domain / source_name / "_runs.json"
    if not runs_path.is_file():
        health.status = "unknown"
        return health.to_dict()

    try:
        runs: list[dict[str, Any]] = json.loads(
            runs_path.read_text(encoding="utf-8")
        )
    except (json.JSONDecodeError, OSError):
        health.status = "error"
        return health.to_dict()

    if not runs:
        health.status = "unknown"
        return health.to_dict()

    # -- Analyse run history ---------------------------------------------
    last_success = ""
    error_count = 0
    consecutive_errors = 0
    total_duration_ms = 0.0
    duration_count = 0

    for run in reversed(runs):
        run_status = run.get("status", "success")  # legacy: missing == success
        if run_status == "success":
            if not last_success:
                last_success = run.get("timestamp", "")
            consecutive_errors = 0
        else:
            error_count += 1
            consecutive_errors += 1

        dur = run.get("duration_ms", 0)
        if dur:
            total_duration_ms += dur
            duration_count += 1

    avg_rt = round(total_duration_ms / duration_count, 1) if duration_count > 0 else 0.0

    health.last_success = last_success
    health.error_count = error_count
    health.avg_response_time_ms = avg_rt

    # -- Determine status -------------------------------------------------
    last_run = runs[-1]
    last_status = last_run.get("status", "success")

    if consecutive_errors >= 3:
        health.status = "error"
    elif last_status != "success":
        health.status = "degraded"
    elif avg_rt > 5000:
        health.status = "degraded"
    else:
        health.status = "healthy"

    return health.to_dict()


# ===================================================================
# F29 — User feedback / rating
# ===================================================================


def rate_item(
    item_id: str,
    rating: int,
    feedback: str = "",
) -> dict[str, Any]:
    """Store a user rating and optional feedback for a collected item.

    Ratings are persisted in a ``feedback`` table in the project's
    ``autoinfo.db`` SQLite database.

    Parameters
    ----------
    item_id:
        The collected item or KB entry ID to rate.
    rating:
        Rating value (1-5).
    feedback:
        Optional free-text feedback.

    Returns
    -------
    dict
        ``{recorded: bool, item_id, rating, feedback}`` on success,
        or an ``error_code`` dict if validation fails.
    """
    if not 1 <= rating <= 5:
        return {
            "error_code": "InvalidRating",
            "message": "Rating must be between 1 and 5",
        }

    # Use same DB path as KBStore
    autoinfo_dir = _find_autoinfo_dir()
    db_path = autoinfo_dir / "autoinfo.db"

    try:
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id     TEXT NOT NULL,
                rating      INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
                feedback    TEXT DEFAULT '',
                created_at  TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute(
            "INSERT INTO feedback (item_id, rating, feedback) VALUES (?, ?, ?)",
            (item_id, rating, feedback),
        )
        conn.commit()
        conn.close()
    except sqlite3.Error as exc:
        return {
            "error_code": "DatabaseError",
            "message": f"Failed to store rating: {exc}",
        }

    return {
        "recorded": True,
        "item_id": item_id,
        "rating": rating,
        "feedback": feedback,
    }


def _find_autoinfo_dir() -> Path:
    """Locate the project's ``.autoinfo`` directory (config parent)."""
    config_path = get_config_path()
    if config_path:
        return config_path.parent
    # Fallback: look for autoinfo.db in CWD
    return Path.cwd()


# ===================================================================
# Collection stats / diff (tasks 24+25)
# ===================================================================


def get_collection_stats(period: str = "daily") -> dict[str, Any]:
    """Aggregated collection statistics across domains.

    Parameters
    ----------
    period:
        ``"daily"`` (default), ``"weekly"``, or ``"monthly"``.

    Returns
    -------
    dict
        ``{period, date_from, date_to, total_items, new_items,
        duplicate_items, domains, sources}``
    """
    from autoinfo.kb import KBStore

    store = KBStore()
    return store.get_collection_stats(period=period)


def get_collection_diff(since_collection_id: str) -> dict[str, Any]:
    """Return entries collected since a previous collection ID.

    Parameters
    ----------
    since_collection_id:
        A collection ID (timestamp) to compare against.

    Returns
    -------
    dict
        ``{since_id, new_entries, count, domains}``
    """
    from autoinfo.kb import KBStore

    store = KBStore()
    return store.get_collection_diff(since_collection_id=since_collection_id)
