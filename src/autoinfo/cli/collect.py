"""Collect CLI — runs collection pipeline.

Usage::

    autoinfo collect --domain medical-research [--topic "IVF"] [--source pubmed] \\
        [--limit 20] [--dry-run] [--auto-process] [--json]
"""

from __future__ import annotations

import json
from typing import Any

import typer

app = typer.Typer()


@app.callback(invoke_without_command=True)
def collect(
    domain: str = typer.Option(..., "--domain", help="Domain to collect for"),
    topic: str = typer.Option("", "--topic", help="Topic / search query filter"),
    source: str = typer.Option(
        None, "--source", help="Source name filter (repeatable: --source pubmed --source rss)",
    ),
    limit: int = typer.Option(20, "--limit", help="Max items to collect per source"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without storing"),
    auto_process: bool = typer.Option(
        False, "--auto-process", help="Run processing immediately after collection",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Collect items from configured sources."""
    # -- Parse source filter -----------------------------------------------
    # The `--source` option is repeatable, single-string pass-through is fine
    # because typer collects multiple `--source` flags into a tuple → string.
    # We normalise it into a list here.
    sources: list[str] | None = None
    if source:
        # source is a single string; split by comma or treat as single entry
        sources = [s.strip() for s in source.split(",") if s.strip()]

    try:
        from autoinfo.collect import run_collection

        result = run_collection(
            domain=domain,
            topic=topic,
            sources=sources,
            limit=limit,
            dry_run=dry_run,
        )
    except FileNotFoundError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)
    except ImportError as exc:
        typer.echo(f"Error: collect module not available: {exc}", err=True)
        raise typer.Exit(code=1)

    # -- Output ------------------------------------------------------------
    if json_output:
        typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_human(result)

    # -- Optional: auto-process --------------------------------------------
    if auto_process and not dry_run:
        if result["total_new"] > 0:
            typer.echo("")
            typer.echo("── Running auto-process ──")
            _run_auto_process(domain, topic)
        else:
            typer.echo("")
            typer.echo("No new items — skipping auto-process.")

    if dry_run:
        typer.echo("")
        typer.echo("ℹ Dry-run — no items were stored.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _print_human(result: dict[str, Any]) -> None:
    """Print a human-readable collection summary."""
    typer.echo(
        f"Collection {result['collection_id']} for domain '{result['domain']}'"
    )
    typer.echo("")

    for src in result["per_source"]:
        status_icon = {
            "success": "✓",
            "partial": "⚠",
            "error": "✗",
            "skipped": "–",
        }.get(src["status"], "?")

        typer.echo(
            f"  {status_icon} {src['source']}: "
            f"{src['items_new']} new / {src['items_found']} found "
            f"({src['duration_s']:.1f}s)"
        )

        for err in src.get("errors", []):
            typer.echo(f"      ↳ {err.get('message', 'unknown error')}", err=True)

    typer.echo("")
    typer.echo(
        f"Total: {result['total_new']} new items from {result['total_found']} found "
        f"in {result['duration_s']:.1f}s"
    )


def _run_auto_process(domain: str, topic: str = "") -> None:
    """Call the processing pipeline after collection."""
    try:
        from autoinfo.process import run_processing

        proc_result = run_processing(domain=domain, topic=topic if topic else None)
        typer.echo(
            f"Processing: {proc_result.total_items} items → "
            f"{proc_result.passed_gates} passed G1-G3 → "
            f"{proc_result.kb_entries_created} KB entries created "
            f"({proc_result.duration_s:.1f}s)"
        )
        if proc_result.errors:
            typer.echo(
                f"  {len(proc_result.errors)} item(s) failed", err=True
            )
    except Exception as exc:
        typer.echo(f"Auto-process failed: {exc}", err=True)
