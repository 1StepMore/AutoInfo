from __future__ import annotations
"""Doctor CLI — checks system health and configuration.

Usage::

    autoinfo doctor [--json]
"""


import json

import typer

app = typer.Typer()


@app.callback(invoke_without_command=True)
def doctor(
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
) -> None:
    """Check system health and configuration."""
    try:
        from autoinfo.doctor import run_doctor

        result = run_doctor()
    except ImportError as exc:
        typer.echo(f"Error: doctor module not available: {exc}", err=True)
        raise typer.Exit(code=1)

    if json_output:
        typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_human(result)

    # Exit with error if any critical check failed
    if result.get("python", {}).get("status") == "error":
        raise typer.Exit(code=1)
    if result.get("config", {}).get("status") == "error":
        raise typer.Exit(code=1)


def _print_human(result: dict) -> None:
    """Print a human-readable health report with ✅/❌ indicators."""

    # --- Python ---
    py = result.get("python", {})
    icon = "✅" if py.get("status") == "ok" else "❌"
    typer.echo(f"  {icon} Python {py.get('version', '?')}")

    # --- Config ---
    cfg = result.get("config", {})
    if cfg.get("status") == "ok":
        typer.echo(f"  ✅ Config: {cfg.get('path', '?')}")
    else:
        typer.echo(f"  ❌ Config: {cfg.get('path', '(not found)')}")
        for err in cfg.get("errors", []):
            typer.echo(f"       ↳ {err}")

    # --- LLM ---
    llm = result.get("llm", {})
    if llm.get("status") == "ok":
        typer.echo(
            f"  ✅ LLM: {llm.get('provider', '?')} / {llm.get('model', '?')} "
            f"(key {'✓' if llm.get('key_configured') else '✗'})"
        )
    else:
        typer.echo(
            "  ❌ LLM: no API key configured "
            "(set AUTOINFO_LLM_API_KEY or configure llm.api_key)"
        )

    # --- Sources ---
    sources = result.get("sources", [])
    if sources:
        typer.echo("  Sources:")
        for src in sources:
            icon = "✅" if src.get("status") == "ok" else "❌"
            if src.get("status") == "skipped":
                icon = "–"
            latency = src.get("latency_ms", 0)
            detail = src.get("detail", "")
            line = f"    {icon} {src['name']} ({latency:.0f}ms)"
            if detail:
                line += f" — {detail}"
            typer.echo(line)
    else:
        typer.echo("  Sources: (none configured)")
