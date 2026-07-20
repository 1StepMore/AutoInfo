"""System status and collection overview.

Provides ``show_status()`` used by ``autoinfo status`` to present a
domain-level summary of collected items and source health.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from autoinfo.config import (
    Config,
    get_config_path,
    load_config,
)
from autoinfo.kb import SQLiteIndex

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
        # Entry counts
        total_entries = index.count_entries(d.name) if index else 0
        items_today = index.count_entries_today(d.name) if index else 0

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
