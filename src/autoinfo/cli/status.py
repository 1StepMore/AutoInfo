from __future__ import annotations
"""Status CLI — system and collection status.

Usage::

    autoinfo status [--domain medical-research] [--json]
"""


import json

import typer

app = typer.Typer()


@app.callback(invoke_without_command=True)
def status(
    domain: str = typer.Option(None, "--domain", help="Domain filter"),
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
) -> None:
    """Show collection overview and system status."""
    try:
        from autoinfo.status import show_status

        result = show_status(domain=domain)
    except FileNotFoundError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)
    except ImportError as exc:
        typer.echo(f"Error: status module not available: {exc}", err=True)
        raise typer.Exit(code=1)

    if json_output:
        typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_human(result)


def _print_human(result: dict) -> None:
    """Print a human-readable status overview."""
    domains = result.get("domains", [])
    if not domains:
        typer.echo("No domains found.")
        return

    for d in domains:
        typer.echo(f"Domain: {d['name']}")
        typer.echo(f"  Items today:    {d['items_today']}")
        typer.echo(f"  Total entries:  {d['total_entries']}")
        typer.echo("  Source health:")
        for sh in d.get("source_health", []):
            icon = {"healthy": "✓", "stale": "⚠", "unknown": "–", "error": "✗"}.get(
                sh["status"], "?"
            )
            typer.echo(f"    {icon} {sh['name']}: {sh['status']}")
        typer.echo("")
