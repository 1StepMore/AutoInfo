"""`autoinfo audit` — Query the immutable audit log.

Usage::

    autoinfo audit query
    autoinfo audit query --actor system
    autoinfo audit query --action collect_sources --limit 20
    autoinfo audit query --date-from 2025-01-01 --date-to 2025-06-30
"""

from __future__ import annotations

import json

import typer

from autoinfo.models import AuditLog

app = typer.Typer(help="Query the immutable audit log (append-only).")


@app.command(name="query")
def query_audit(
    actor: str | None = typer.Option(None, "--actor", help="Filter by actor name"),
    action: str | None = typer.Option(None, "--action", help="Filter by action name"),
    resource_type: str | None = typer.Option(
        None, "--resource-type", help="Filter by resource type"
    ),
    date_from: str | None = typer.Option(
        None, "--date-from", help="Only entries with timestamp >= this ISO-8601 value"
    ),
    date_to: str | None = typer.Option(
        None, "--date-to", help="Only entries with timestamp <= this ISO-8601 value"
    ),
    limit: int = typer.Option(100, "--limit", help="Max entries to return"),
    offset: int = typer.Option(0, "--offset", help="Pagination offset"),
    json_output: bool = typer.Option(
        False, "--json", help="Output as JSON instead of a human-readable table"
    ),
) -> None:
    """Query the immutable audit log with optional filters.

    All filters are optional and combined with AND logic.
    Results are returned newest-first.
    """
    try:
        from autoinfo.audit import query_audit_log as _query

        entries = _query(
            actor=actor,
            action=action,
            resource_type=resource_type,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        typer.echo(f"Error: audit log query failed: {exc}", err=True)
        raise typer.Exit(code=1)

    if json_output:
        typer.echo(
            json.dumps(
                {
                    "entries": [e.to_dict() for e in entries],
                    "count": len(entries),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        if not entries:
            typer.echo("No audit log entries found.")
            return

        _print_table(entries)


def _print_table(entries: list[AuditLog]) -> None:
    """Print audit log entries as a human-readable table."""
    header = f"{'LOG ID':<38} {'TIMESTAMP':<26} {'ACTOR':<20} {'ACTION':<30} {'RESOURCE TYPE':<18} {'RESOURCE ID':<22}"
    typer.echo(header)
    typer.echo("-" * len(header))
    for e in entries:
        log_id = e.log_id[:36]
        ts = e.timestamp[:24]
        actor = e.actor[:18]
        action = e.action[:28]
        rtype = e.resource_type[:16]
        rid = e.resource_id[:20]
        typer.echo(f"{log_id:<38} {ts:<26} {actor:<20} {action:<30} {rtype:<18} {rid:<22}")
    typer.echo(f"\nTotal: {len(entries)} entries")
