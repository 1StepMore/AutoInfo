"""Summaries CLI — browse and manage collected summaries.

Usage::

    autoinfo summaries --domain medical-research [--date-from 2026-07-01] \\
        [--limit 20] [--offset 0] [--json]
"""

from __future__ import annotations

import json

import typer

from autoinfo.config import get_config_path

app = typer.Typer()


@app.callback(invoke_without_command=True)
def summaries(
    domain: str = typer.Option(..., "--domain", help="Domain to list summaries for"),
    date_from: str = typer.Option(None, "--date-from", help="Start date (ISO 8601)"),
    limit: int = typer.Option(20, "--limit", help="Max results"),
    offset: int = typer.Option(0, "--offset", help="Result offset"),
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
) -> None:
    """List and manage collected summaries."""
    try:
        from autoinfo.kb import KBStore

        # Determine knowledge base path from config location
        config_path = get_config_path()
        if config_path is None:
            typer.echo(
                "Error: No configuration found. Run 'autoinfo init' first.",
                err=True,
            )
            raise typer.Exit(code=1)

        kb_base = config_path.parent / "knowledge"
        store = KBStore(base_path=kb_base)
        entries = store.list_entries(
            domain=domain,
            date_from=date_from,
            limit=limit,
            offset=offset,
        )
    except FileNotFoundError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)
    except ImportError as exc:
        typer.echo(f"Error: summaries module not available: {exc}", err=True)
        raise typer.Exit(code=1)
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)

    if json_output:
        typer.echo(json.dumps(entries, ensure_ascii=False, indent=2))
    else:
        _print_human(entries)


def _print_human(entries: list[dict]) -> None:
    """Print entries in a human-readable table."""
    if not entries:
        typer.echo("No entries found.")
        return

    # Header
    typer.echo(
        f"{'ID':<36} {'Title':<50} {'TL;DR':<60} {'Rel':>5}  {'Date':<12}"
    )
    typer.echo("-" * 170)

    for e in entries:
        entry_id = (e.get("entry_id") or "?")[:35]
        title = (e.get("title") or "?")[:49]
        tldr = (e.get("summary") or "")[:59]
        relevance = e.get("relevance_score", 0)
        date_str = (e.get("collected_at") or "?")[:10]

        typer.echo(
            f"{entry_id:<36} {title:<50} {tldr:<60} {relevance:>5.0f}  {date_str:<12}"
        )
