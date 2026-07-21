from __future__ import annotations
"""Cron CLI — manage scheduled collection jobs.

Usage::

    autoinfo cron run
    autoinfo cron list-schedules
    autoinfo cron add-schedule --name nightly --expression "0 2 * * *" --domain medical
    autoinfo cron remove-schedule --name nightly
"""


import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer
import yaml

logger = logging.getLogger(__name__)

app = typer.Typer(help="Manage scheduled collection jobs")

# ---------------------------------------------------------------------------
# Schedule data model
# ---------------------------------------------------------------------------

SCHEDULES_PATH = Path(".autoinfo/schedules.yaml")


@dataclass
class Schedule:
    name: str = ""
    expression: str = ""
    domain: str = ""
    enabled: bool = True
    last_run: str | None = None  # ISO-8601 datetime, or None if never run
    created_at: str = ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Schedule storage
# ---------------------------------------------------------------------------


def _schedules_path() -> Path:
    return Path.cwd() / SCHEDULES_PATH


def _load_schedules_raw() -> dict[str, Any]:
    """Load the schedules YAML file, returning a dict with a 'schedules' key."""
    path = _schedules_path()
    if not path.is_file():
        return {"schedules": {}}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {"schedules": {}}
    except yaml.YAMLError:
        logger.warning("Failed to parse schedules file at %s", path)
        return {"schedules": {}}


def _dump_schedules_raw(data: dict[str, Any]) -> None:
    """Write the schedules YAML file."""
    path = _schedules_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        yaml.dump(data, fh, default_flow_style=False, sort_keys=False, allow_unicode=True)


def load_schedules() -> dict[str, Schedule]:
    """Load all schedules from disk as Schedule objects."""
    raw = _load_schedules_raw()
    schedules: dict[str, Schedule] = {}
    for name, s in raw.get("schedules", {}).items():
        schedules[name] = Schedule(
            name=name,
            expression=s.get("expression", ""),
            domain=s.get("domain", ""),
            enabled=s.get("enabled", True),
            last_run=s.get("last_run"),
            created_at=s.get("created_at", ""),
        )
    return schedules


def save_schedules(schedules: dict[str, Schedule]) -> None:
    """Persist schedules to disk."""
    raw: dict[str, Any] = {"schedules": {}}
    for name, s in schedules.items():
        raw["schedules"][name] = {
            "expression": s.expression,
            "domain": s.domain,
            "enabled": s.enabled,
            "last_run": s.last_run,
            "created_at": s.created_at,
        }
    _dump_schedules_raw(raw)


def get_schedule(name: str) -> Schedule | None:
    """Return a single schedule by name, or None."""
    return load_schedules().get(name)


# ---------------------------------------------------------------------------
# Cron check logic
# ---------------------------------------------------------------------------


def _is_due(
    expression: str,
    last_run: str | None,
    now: datetime | None = None,
) -> bool:
    """Check whether a schedule is due to run.

    A schedule is due when:

    * It has never run (``last_run is None``), **or**
    * The next occurrence of the cron expression after *last_run* is
      at or before *now*.
    """
    from croniter import croniter

    if now is None:
        now = datetime.now(timezone.utc)

    if last_run is None:
        return True

    last_dt = datetime.fromisoformat(last_run)
    cron = croniter(expression, last_dt)
    next_time = cron.get_next(datetime)
    return next_time <= now


def run_due_schedules(
    dry_run: bool = False,
    schedule_filter: str | None = None,
    json_output: bool = False,
) -> list:  # list of result dicts
    """Run all due schedules, returning a list of result dicts.

    Parameters
    ----------
    dry_run : bool
        If True, only report which schedules *would* run without executing.
    schedule_filter : str | None
        Optional single schedule name to check instead of all.
    json_output : bool
        If True, include full collection results as JSON in the output.

    Returns
    -------
    list[dict]
        One dict per schedule that was due, each with keys:
        ``name``, ``domain``, ``expression``, ``ran`` (bool),
        ``collection_result`` (dict, only when ``ran=True``),
        ``error`` (str, only on failure).
    """
    from croniter import croniter

    schedules = load_schedules()
    now = datetime.now(timezone.utc)
    results = []

    for name, sched in schedules.items():
        if schedule_filter and name != schedule_filter:
            continue
        if not sched.enabled:
            continue

        due = _is_due(sched.expression, sched.last_run, now)

        entry: dict[str, Any] = {
            "name": name,
            "domain": sched.domain,
            "expression": sched.expression,
            "due": due,
        }

        if not due:
            entry["ran"] = False
            results.append(entry)
            continue

        if dry_run:
            entry["ran"] = False
            entry["dry_run"] = True
            results.append(entry)
            continue

        # Execute collection
        try:
            from autoinfo.collect import run_collection

            coll_result = run_collection(domain=sched.domain)
            # Update last_run
            sched.last_run = now.isoformat()
            save_schedules(schedules)
            entry["ran"] = True
            if json_output:
                entry["collection_result"] = coll_result
            else:
                entry["collection_result"] = {
                    "collection_id": coll_result.get("collection_id"),
                    "total_new": coll_result.get("total_new", 0),
                    "total_found": coll_result.get("total_found", 0),
                }
            entry["last_run"] = sched.last_run
        except Exception as exc:
            logger.exception("Schedule '%s' failed", name)
            entry["ran"] = False
            entry["error"] = str(exc)

        results.append(entry)

    return results


# ---------------------------------------------------------------------------
# CLI Commands
# ---------------------------------------------------------------------------


@app.command()
def run(
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Report which schedules would run without executing",
    ),
    name: str | None = typer.Option(
        None, "--name", help="Run only a specific schedule by name",
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Output full results as JSON",
    ),
) -> None:
    """Run pending scheduled collections."""
    try:
        results = run_due_schedules(
            dry_run=dry_run,
            schedule_filter=name,
            json_output=json_output,
        )
    except ImportError:
        typer.echo(
            "Error: croniter is required for scheduled collection.\n"
            "Install it with: pip install croniter",
            err=True,
        )
        raise typer.Exit(code=1)

    if json_output:
        typer.echo(json.dumps(results, ensure_ascii=False, indent=2))
        return

    due = [r for r in results if r.get("due")]
    ran = [r for r in results if r.get("ran")]

    if not due:
        typer.echo("No schedules are due.")
        return

    for entry in due:
        if entry.get("dry_run"):
            typer.echo(
                f"  🔄 {entry['name']} ({entry['domain']}) — "
                f"[{entry['expression']}] — would run"
            )
        elif entry.get("ran"):
            cr = entry.get("collection_result", {})
            typer.echo(
                f"  ✓ {entry['name']} ({entry['domain']}) — "
                f"{cr.get('total_new', 0)} new / {cr.get('total_found', 0)} found"
            )
        elif "error" in entry:
            typer.echo(
                f"  ✗ {entry['name']} ({entry['domain']}) — FAILED: {entry['error']}",
                err=True,
            )
        else:
            typer.echo(
                f"  – {entry['name']} ({entry['domain']}) — skipped"
            )

    due_count = len(due)
    ran_count = len(ran)
    typer.echo("")
    typer.echo(f"{ran_count} of {due_count} due schedule(s) executed.")


@app.command(name="list-schedules")
def list_schedules(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """List all configured schedules."""
    schedules = load_schedules()

    if json_output:
        data = []
        for name, s in schedules.items():
            data.append(asdict(s))
        typer.echo(json.dumps(data, ensure_ascii=False, indent=2))
        return

    if not schedules:
        typer.echo("No schedules configured.")
        return

    typer.echo(f"{'Name':<20} {'Expression':<18} {'Domain':<22} {'Enabled':<8} {'Last Run':<30}")
    typer.echo("-" * 100)
    for name, s in schedules.items():
        last = s.last_run or "—"
        enabled = "yes" if s.enabled else "no"
        typer.echo(
            f"{name:<20} {s.expression:<18} {s.domain:<22} {enabled:<8} {last:<30}"
        )


@app.command(name="add-schedule")
def add_schedule(
    name: str = typer.Option(..., "--name", help="Schedule name"),
    expression: str = typer.Option(
        ..., "--expression", help="Cron expression (e.g. '0 2 * * *')",
    ),
    domain: str = typer.Option(
        ..., "--domain", help="Domain to collect on this schedule",
    ),
) -> None:
    """Add a new collection schedule."""
    # Validate cron expression
    try:
        from croniter import croniter

        if not croniter.is_valid(expression):
            typer.echo(
                f"Error: '{expression}' is not a valid cron expression.",
                err=True,
            )
            raise typer.Exit(code=1)
    except ImportError:
        typer.echo(
            "Error: croniter is required for scheduled collection.\n"
            "Install it with: pip install croniter",
            err=True,
        )
        raise typer.Exit(code=1)

    schedules = load_schedules()
    if name in schedules:
        typer.echo(f"Error: A schedule named '{name}' already exists.", err=True)
        raise typer.Exit(code=1)

    new_schedule = Schedule(
        name=name,
        expression=expression,
        domain=domain,
        enabled=True,
        last_run=None,
        created_at=_now_iso(),
    )
    schedules[name] = new_schedule
    save_schedules(schedules)

    typer.echo(f"Schedule '{name}' added: {expression} → domain '{domain}'")


@app.command(name="remove-schedule")
def remove_schedule(
    name: str = typer.Option(..., "--name", help="Schedule name to remove"),
) -> None:
    """Remove a collection schedule."""
    schedules = load_schedules()
    if name not in schedules:
        typer.echo(f"Error: Schedule '{name}' not found.", err=True)
        raise typer.Exit(code=1)

    removed = schedules.pop(name)
    save_schedules(schedules)
    typer.echo(
        f"Schedule '{name}' removed (was: {removed.expression} → domain '{removed.domain}')."
    )
