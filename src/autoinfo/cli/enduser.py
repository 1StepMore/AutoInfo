from __future__ import annotations

"""End-user CLI — manage end-user profiles.

End users are paying customers, not director/operator users.

Usage::

    autoinfo enduser create --user-id alice --name "Alice Smith" --email alice@example.com
    autoinfo enduser get --user-id alice
    autoinfo enduser update --user-id alice --tier pro
    autoinfo enduser delete --user-id alice
    autoinfo enduser list
"""


import json
from typing import Any

import typer

from autoinfo.user_store import (
    create_profile,
    delete_profile,
    get_profile,
    list_profiles,
    update_profile,
)

app = typer.Typer(help="Manage end-user profiles")


@app.command()
def create(
    user_id: str = typer.Option(..., "--user-id", help="Unique user identifier"),
    name: str = typer.Option(..., "--name", help="User display name"),
    email: str = typer.Option("", "--email", help="Email address"),
    delivery_prefs: str = typer.Option(
        "{}", "--delivery-prefs", help="Delivery preferences as JSON"
    ),
    status: str = typer.Option(
        "trial", "--status", help="Account status (trial/active/suspended/cancelled)"
    ),
    tier: str = typer.Option(
        "free", "--tier", help="Account tier (free/pro/enterprise)"
    ),
) -> None:
    """Create a new end-user profile."""
    try:
        prefs = json.loads(delivery_prefs) if delivery_prefs else {}
    except json.JSONDecodeError as exc:
        typer.echo(f"Error: invalid JSON for --delivery-prefs: {exc}", err=True)
        raise typer.Exit(code=1)

    try:
        profile = create_profile(
            user_id=user_id,
            name=name,
            email=email,
            delivery_prefs=prefs,
            status=status,
            tier=tier,
        )
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Created end-user: {profile.user_id} ({profile.name})")


@app.command()
def get(
    user_id: str = typer.Option(..., "--user-id", help="User identifier to look up"),
) -> None:
    """Get an end-user profile by user ID."""
    try:
        profile = get_profile(user_id)
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)

    if profile is None:
        typer.echo(f"End-user '{user_id}' not found")
        raise typer.Exit(code=1)

    typer.echo(json.dumps(profile.to_dict(), indent=2, ensure_ascii=False))


@app.command()
def update(
    user_id: str = typer.Option(..., "--user-id", help="User identifier to update"),
    name: str = typer.Option(None, "--name", help="New display name"),
    email: str = typer.Option(None, "--email", help="New email address"),
    delivery_prefs: str = typer.Option(
        None, "--delivery-prefs", help="New delivery preferences as JSON"
    ),
    status: str = typer.Option(
        None, "--status", help="New account status (trial/active/suspended/cancelled)"
    ),
    tier: str = typer.Option(
        None, "--tier", help="New account tier (free/pro/enterprise)"
    ),
) -> None:
    """Update an end-user profile (partial update)."""
    kwargs: dict[str, Any] = {}
    if name is not None:
        kwargs["name"] = name
    if email is not None:
        kwargs["email"] = email
    if delivery_prefs is not None:
        try:
            kwargs["delivery_prefs"] = json.loads(delivery_prefs)
        except json.JSONDecodeError as exc:
            typer.echo(f"Error: invalid JSON for --delivery-prefs: {exc}", err=True)
            raise typer.Exit(code=1)
    if status is not None:
        kwargs["status"] = status
    if tier is not None:
        kwargs["tier"] = tier

    try:
        profile = update_profile(user_id=user_id, **kwargs)
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)

    if profile is None:
        typer.echo(f"End-user '{user_id}' not found")
        raise typer.Exit(code=1)

    typer.echo(f"Updated end-user: {profile.user_id}")
    typer.echo(json.dumps(profile.to_dict(), indent=2, ensure_ascii=False))


@app.command()
def delete(
    user_id: str = typer.Option(..., "--user-id", help="User identifier to delete"),
) -> None:
    """Delete an end-user profile and associated subscriptions."""
    try:
        ok = delete_profile(user_id)
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)

    if not ok:
        typer.echo(f"End-user '{user_id}' not found")
        raise typer.Exit(code=1)

    typer.echo(f"Deleted end-user: {user_id}")


@app.command()
def list(
    json_output: bool = typer.Option(
        False, "--json", help="Output as JSON array (default: table)"
    ),
) -> None:
    """List all end-user profiles."""
    try:
        profiles = list_profiles()
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)

    if not profiles:
        typer.echo("No end-users found")
        return

    if json_output:
        typer.echo(
            json.dumps({"items": [p.to_dict() for p in profiles], "count": len(profiles)}, indent=2, ensure_ascii=False)
        )
        return

    # Pretty table
    header = f"{'User ID':<24} {'Name':<24} {'Email':<32} {'Status':<12} {'Tier':<12}"
    sep = "-" * len(header)
    typer.echo(header)
    typer.echo(sep)
    for p in profiles:
        typer.echo(
            f"{p.user_id:<24} {p.name:<24} {p.email:<32} {p.status:<12} {p.tier:<12}"
        )
    typer.echo(f"\nTotal: {len(profiles)} end-user(s)")
