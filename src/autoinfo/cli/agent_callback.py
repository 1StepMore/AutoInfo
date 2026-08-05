"""Agent callback CLI — mirror of the MCP agent callback tools.

Usage::

    autoinfo agent-callback add --agent-url http://localhost:9999/hook \
        --events new_digest
    autoinfo agent-callback list
    autoinfo agent-callback remove --id ab12cd34

Mirrors ``set_agent_callback`` / ``list_agent_callbacks`` /
``remove_agent_callback``. Parameter names are identical (agent_url, events,
callback_id). Persistence stays SQLite (durable outbox system from M4T36).
"""

from __future__ import annotations

import json

import typer

app = typer.Typer(
    name="agent-callback",
    help="Manage agent push callbacks — mirrors MCP set/list/remove_agent_callback",
)

_VALID_EVENTS = ("new_digest", "new_report", "new_tutorial")


def _fail(message: str) -> None:
    typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(code=1)


@app.command()
def add(
    agent_url: str = typer.Option(
        "",
        "--agent-url",
        help="Callback URL (must start with http:// or https://)",
    ),
    url: str = typer.Option(
        "", "--url", help="Alias for --agent-url (shorthand used in plan QA)"
    ),
    events: list[str] = typer.Option(
        [],
        "--events",
        help="Events to subscribe to (repeatable): new_digest, new_report, new_tutorial",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Register an agent callback URL for push events (mirrors MCP set_agent_callback)."""
    if agent_url and url and agent_url != url:
        _fail("--agent-url and --url disagree; pass only one.")
    resolved = agent_url or url
    if not resolved:
        _fail("Provide a callback URL via --agent-url (or --url).")

    invalid = [e for e in events if e not in _VALID_EVENTS]
    if invalid:
        _fail(
            f"Invalid events: {invalid}. Valid events: {', '.join(_VALID_EVENTS)}"
        )
    if not events:
        _fail("At least one --events value is required (new_digest, new_report, new_tutorial)")

    # Deferred import — mirrors the MCP handler
    from autoinfo.agent_callback import register_agent_callback

    try:
        callback_id = register_agent_callback(agent_url=resolved, events=events)
    except ValueError as exc:
        # Mirrors the MCP handler's ValueError → VALIDATION_ERROR mapping
        _fail(str(exc))

    if json_output:
        typer.echo(
            json.dumps(
                {
                    "callback_id": callback_id,
                    "agent_url": resolved,
                    "events": events,
                    "created": True,
                },
                indent=2,
            )
        )
    else:
        typer.echo(
            f"Registered agent callback '{callback_id}' for {resolved} "
            f"(events: {', '.join(events)})"
        )


@app.command("list")
def list_cmd(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """List all registered agent callbacks (mirrors MCP list_agent_callbacks)."""
    # Deferred import — mirrors the MCP handler
    from autoinfo.agent_callback import list_agent_callbacks

    callbacks = list_agent_callbacks()

    if json_output:
        typer.echo(json.dumps(callbacks, indent=2, ensure_ascii=False))
        return

    if not callbacks:
        typer.echo("No agent callbacks registered")
        return

    for cb in callbacks:
        typer.echo(
            f"{cb['callback_id']}  {cb['agent_url']}  events={','.join(cb['events'])}"
        )


@app.command()
def remove(
    callback_id: str = typer.Option(
        "", "--id", help="Callback ID returned by add (alias: --callback-id)"
    ),
    callback_id_long: str = typer.Option(
        "", "--callback-id", help="Full option name (alias of --id)"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Remove a registered agent callback (mirrors MCP remove_agent_callback)."""
    if callback_id and callback_id_long and callback_id != callback_id_long:
        _fail("--id and --callback-id disagree; pass only one.")
    resolved = callback_id_long or callback_id
    if not resolved:
        _fail("Provide a callback ID via --id (or --callback-id).")

    # Deferred import — mirrors the MCP handler
    from autoinfo.agent_callback import remove_agent_callback

    removed = remove_agent_callback(resolved)

    if not removed:
        # Mirrors the MCP handler's NOT_FOUND response
        if json_output:
            typer.echo(
                json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "NotFound",
                            "message": f"Callback '{resolved}' not found",
                            "actionable": True,
                        },
                    },
                    indent=2,
                )
            )
        else:
            typer.echo(f"Error: Callback '{resolved}' not found", err=True)
        raise typer.Exit(code=1)

    if json_output:
        typer.echo(json.dumps({"callback_id": resolved, "removed": True}, indent=2))
    else:
        typer.echo(f"Removed agent callback '{resolved}'")
