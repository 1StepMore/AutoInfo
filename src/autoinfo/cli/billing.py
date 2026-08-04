from __future__ import annotations

"""Billing CLI — read-only billing summary for end-users.

Combines usage data from CostMeter with subscription status from Stripe.

Usage::

    autoinfo billing --user-id alice --period month
    autoinfo billing --user-id alice --period month --json
"""

import json

import typer

app = typer.Typer(help="Read-only billing summary (usage + subscription)")


@app.command()
def summary(
    user_id: str = typer.Option("", "--user-id", help="End-user ID (defaults to config multi_user.default_user_id)"),
    period: str = typer.Option("month", "--period", help="Time period (today/week/month/all)"),
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
) -> None:
    """Show combined billing summary — usage + subscription status."""
    from autoinfo.billing import resolve_user_id

    user_id = resolve_user_id(user_id or None)

    try:
        from autoinfo.billing import get_subscription_status
        from autoinfo.cost import CostMeter

        meter = CostMeter()
        usage = meter.get_enduser_usage(end_user_id=user_id, period=period)
        subscription = get_subscription_status(end_user_id=user_id)
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)

    result = {
        "user_id": user_id,
        "period": period,
        "usage": {
            "llm_units": usage.get("llm_units", 0),
            "storage_mb": usage.get("storage_mb", 0.0),
            "api_call_units": usage.get("api_call_units", 0),
        },
        "subscription": {
            "status": subscription.get("profile_status", "unknown"),
            "plan": subscription.get("plan", "free"),
            "stripe_status": subscription.get("stripe_status", "none"),
            "customer_id": subscription.get("customer_id", ""),
        },
    }

    if json_output:
        typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_summary(result)


def _print_summary(result: dict) -> None:
    typer.echo("")
    typer.echo(f"  Billing Summary — {result['user_id']} ({result['period']})")
    typer.echo(f"  {'=' * 50}")
    typer.echo("")
    typer.echo("  Usage:")
    usage = result["usage"]
    typer.echo(f"    LLM tokens:        {usage['llm_units']:>12,}")
    typer.echo(f"    Storage (MB):      {usage['storage_mb']:>12.4f}")
    typer.echo(f"    API calls:         {usage['api_call_units']:>12,}")
    typer.echo("")
    typer.echo("  Subscription:")
    sub = result["subscription"]
    typer.echo(f"    Status:            {sub['status']}")
    typer.echo(f"    Plan:              {sub['plan']}")
    typer.echo(f"    Stripe status:     {sub['stripe_status']}")
    if sub.get("customer_id"):
        typer.echo(f"    Customer ID:       {sub['customer_id']}")
    typer.echo("")
