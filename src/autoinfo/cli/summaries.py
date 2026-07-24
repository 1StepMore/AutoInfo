from __future__ import annotations

"""Summaries CLI — browse, flag, and inspect collected summaries.

Usage::

    autoinfo summaries list --domain medical-research [--date-from 2026-07-01] \
        [--limit 20] [--offset 0] [--json]

    autoinfo summaries flag <entry-id> --tag important --tag ivf [--importance 3]

    autoinfo summaries show <entry-id>
"""


import json
from typing import Any

import typer

from autoinfo.config import get_config_path

app = typer.Typer()


@app.callback()
def summaries_callback() -> None:
    """List and manage collected summaries."""


@app.command("list")
def list_(
    domain: str = typer.Option(..., "--domain", help="Domain to list summaries for"),
    date_from: str = typer.Option(None, "--date-from", help="Start date (ISO 8601)"),
    limit: int = typer.Option(20, "--limit", min=1, help="Max results"),
    offset: int = typer.Option(0, "--offset", help="Result offset"),
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
) -> None:
    """List summaries for a domain."""
    try:
        from autoinfo.kb import KBStore

        config_path = get_config_path()
        if config_path is None:
            typer.echo(
                "Error: No configuration found. Run 'autoinfo init' first.",
                err=True,
            )
            raise typer.Exit(code=1)

        kb_base = config_path.parent.parent / "knowledge"
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


@app.command()
def flag(
    entry_id: str = typer.Argument(..., help="Entry ID to flag for KB inclusion"),
    tag = typer.Option(
        [], "--tag", help="Tags to apply (can be repeated)"
    ),
    importance: int = typer.Option(
        3, "--importance", help="Importance rating 1-5", min=1, max=5
    ),
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
) -> None:
    """Flag a summary for knowledge base inclusion."""
    try:
        from autoinfo.kb import KBStore

        config_path = get_config_path()
        if config_path is None:
            typer.echo(
                "Error: No configuration found. Run 'autoinfo init' first.",
                err=True,
            )
            raise typer.Exit(code=1)

        kb_base = config_path.parent.parent / "knowledge"
        store = KBStore(base_path=kb_base)
        result = store.flag_for_knowledge_base(
            summary_id=entry_id, tags=tag, importance=importance
        )
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)

    if json_output:
        typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if result.get("flagged"):
            typer.echo(
                f"Flagged {result['entry_id']} "
                f"(tags: {result['tags']}, importance: {result['importance']})"
            )
        else:
            typer.echo(
                f"Error: {result.get('error', 'Unknown error')}: {entry_id}",
                err=True,
            )
            raise typer.Exit(code=1)


@app.command()
def show(
    entry_id: str = typer.Argument(..., help="Entry ID to show full detail"),
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
) -> None:
    """Show full detail for a summary entry."""
    try:
        from autoinfo.kb import KBStore

        config_path = get_config_path()
        if config_path is None:
            typer.echo(
                "Error: No configuration found. Run 'autoinfo init' first.",
                err=True,
            )
            raise typer.Exit(code=1)

        kb_base = config_path.parent.parent / "knowledge"
        store = KBStore(base_path=kb_base)
        result = store.get_summary(summary_id=entry_id)
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)

    if "error" in result:
        typer.echo(f"Error: {result['error']}: {entry_id}", err=True)
        raise typer.Exit(code=1)

    if json_output:
        typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_summary_human(result)


def _print_human(entries) -> None:
    """Print entries in a human-readable table."""
    if not entries:
        typer.echo("No entries found.")
        return

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


def _print_summary_human(result: dict[str, Any]) -> None:
    """Print a single summary detail in human-readable format."""
    typer.echo(f"Entry ID:   {result.get('entry_id', '?')}")
    typer.echo(f"Title:      {result.get('title', '?')}")
    typer.echo(f"TL;DR:      {result.get('tl_dr', '')}")
    typer.echo(f"Relevance:  {result.get('relevance_score', 0):.0f}/100")
    typer.echo(f"Importance: {result.get('importance', 3)}/5")
    typer.echo(f"File:       {result.get('file_path', '?')}")

    tags = result.get("tags", [])
    if tags:
        typer.echo(f"Tags:       {', '.join(tags)}")

    sp = result.get("source_provenance", {})
    typer.echo(
        f"Source:     {sp.get('source_platform', '?')} — {sp.get('source_url', '?')}"
    )
    typer.echo(f"Collected:  {sp.get('collected_at', '?')}")

    kp = result.get("key_points", [])
    if kp:
        typer.echo("\nKey Points:")
        for i, pt in enumerate(kp, 1):
            typer.echo(f"  {i}. {pt}")

    qs = result.get("quality_scores", {})
    if qs:
        typer.echo("\nQuality Flags:")
        for gname, flagged in qs.items():
            status = "Flagged" if flagged else "Passed"
            typer.echo(f"  {gname}: {status}")
