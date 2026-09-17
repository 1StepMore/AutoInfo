"""Portal CLI — end-user self-service for preferences and delivery history.

Usage::

    autoinfo portal preferences show --user-id alice
    autoinfo portal preferences update --user-id alice --delivery-prefs '{"digest":true}'
    autoinfo portal history --user alice
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

import typer

from autoinfo.delivery_log import query_delivery_log as _query_log
from autoinfo.user_store import (
    get_profile,
    list_subscriptions,
    update_profile,
)

from ._output import emit_if_global, fail_if_global  # noqa: E402

app = typer.Typer(help="End-user self-service portal")

# ---------------------------------------------------------------------------
# preferences subcommand group  (autoinfo portal preferences show|update)
# ---------------------------------------------------------------------------

preferences_app = typer.Typer(help="View or update delivery preferences")
app.add_typer(preferences_app, name="preferences")


@preferences_app.command("show")
def preferences_show(
    user_id: str = typer.Option(..., "--user-id", help="End-user ID"),
    json_output: bool = typer.Option(
        False, "--json", help="Output as raw JSON (default: human-readable)"
    ),
) -> None:
    """Show delivery preferences for an end-user."""
    profile = get_profile(user_id)
    if profile is None:
        fail_if_global("NotFound", f"End-user '{user_id}' not found")
        typer.echo(f"Error: End-user '{user_id}' not found", err=True)
        raise typer.Exit(code=1)

    data = {
        "user_id": profile.user_id,
        "name": profile.name,
        "email": profile.email,
        "tier": profile.tier,
        "status": profile.status,
        "delivery_preferences": profile.delivery_preferences,
    }
    if emit_if_global(data):
        return

    if json_output:
        typer.echo(json.dumps(profile.delivery_preferences, indent=2, ensure_ascii=False))
        return

    typer.echo(f"User:        {profile.user_id}")
    typer.echo(f"Name:        {profile.name}")
    typer.echo(f"Email:       {profile.email}")
    typer.echo(f"Tier:        {profile.tier}")
    typer.echo(f"Status:      {profile.status}")
    typer.echo("Preferences:")
    prefs: dict[str, Any] = profile.delivery_preferences or {}
    if prefs:
        for k, v in prefs.items():
            typer.echo(f"  {k}: {v}")
    else:
        typer.echo("  (none)")


@preferences_app.command("update")
def preferences_update(
    user_id: str = typer.Option(..., "--user-id", help="End-user ID"),
    delivery_prefs: str = typer.Option(
        ..., "--delivery-prefs", help="Delivery preferences as JSON"
    ),
    email: str = typer.Option(None, "--email", help="Optional new email address"),
) -> None:
    """Update delivery preferences for an end-user."""
    try:
        prefs: dict[str, Any] = json.loads(delivery_prefs)
    except json.JSONDecodeError as exc:
        fail_if_global("ValidationError", f"invalid JSON for --delivery-prefs: {exc}")
        typer.echo(f"Error: invalid JSON for --delivery-prefs: {exc}", err=True)
        raise typer.Exit(code=1)

    kwargs: dict[str, Any] = {"delivery_prefs": prefs}
    if email is not None:
        kwargs["email"] = email

    profile = update_profile(user_id=user_id, **kwargs)
    if profile is None:
        fail_if_global("NotFound", f"End-user '{user_id}' not found")
        typer.echo(f"Error: End-user '{user_id}' not found", err=True)
        raise typer.Exit(code=1)

    if emit_if_global(
        {"user_id": profile.user_id, "delivery_preferences": profile.delivery_preferences}
    ):
        return

    typer.echo(f"Updated preferences for end-user: {profile.user_id}")
    typer.echo(json.dumps(profile.delivery_preferences, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# history command  (autoinfo portal history --user <id>)
# ---------------------------------------------------------------------------


@app.command()
def history(
    user_id: str = typer.Option(..., "--user", help="End-user ID"),
    limit: int = typer.Option(50, "--limit", help="Max entries to return"),
    channel: str = typer.Option(None, "--channel", help="Filter by channel (smtp, webhook, ...)"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON array (default: table)"),
) -> None:
    """Show delivery history for an end-user."""
    profile = get_profile(user_id)
    if profile is None:
        fail_if_global("NotFound", f"End-user '{user_id}' not found")
        typer.echo(f"Error: End-user '{user_id}' not found", err=True)
        raise typer.Exit(code=1)

    subscriptions = list_subscriptions(user_id=user_id)
    sub_ids = [s.subscription_id for s in subscriptions if s.subscription_id]

    if not sub_ids:
        if emit_if_global({"user_id": user_id, "items": [], "count": 0}):
            return
        typer.echo(f"No subscriptions found for end-user '{user_id}'")
        return

    all_entries: list[dict[str, Any]] = []
    for sid in sub_ids:
        raw = _query_log(
            subscription_id=sid,
            channel=channel,
            limit=limit,
        )
        for entry in raw:
            all_entries.append(asdict(entry))

    all_entries.sort(key=lambda e: e.get("last_attempt", ""), reverse=True)
    page = all_entries[:limit]

    if not page:
        if emit_if_global({"user_id": user_id, "items": [], "count": 0}):
            return
        typer.echo(f"No delivery history for end-user '{user_id}'")
        return

    if emit_if_global({"user_id": user_id, "items": page, "count": len(page)}):
        return

    if json_output:
        typer.echo(json.dumps({"items": page, "count": len(page)}, indent=2, ensure_ascii=False))
        return

    # Pretty table
    header = (
        f"{'Log ID':<40} {'Channel':<12} {'Type':<12} "
        f"{'Status':<10} {'Attempt':<8} {'Last Attempt':<30}"
    )
    sep = "-" * len(header)
    typer.echo(f"Delivery history for '{user_id}' ({len(page)} entries):")
    typer.echo(header)
    typer.echo(sep)
    for row in page:
        typer.echo(
            f"{row.get('log_id', ''):<40} "
            f"{row.get('channel', ''):<12} "
            f"{row.get('message_type', ''):<12} "
            f"{row.get('status', ''):<10} "
            f"{row.get('attempt_count', 0):<8} "
            f"{row.get('last_attempt', ''):<30}"
        )
    typer.echo(sep)
    typer.echo(f"Total: {len(page)} entries across {len(sub_ids)} subscription(s)")
