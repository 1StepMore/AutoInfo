from __future__ import annotations

"""Cost CLI — cost tracking, allocation, and dashboard.

Usage::

    autoinfo cost allocation [--domain medical-research] [--user-id u1] [--period week] [--json]
    autoinfo cost dashboard [--period week]
"""

import json

import typer

app = typer.Typer()


@app.command()
def dashboard(
    period: str = typer.Option("week", "--period", help="Time period (today/week/month/all)"),
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
) -> None:
    """Show cost dashboard — totals by domain, daily trend, top models/sources, budget status."""
    try:
        from autoinfo.cost import CostMeter

        meter = CostMeter()
        result = meter.get_cost_dashboard(period=period)
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)

    if json_output:
        typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_dashboard(result)


def _print_dashboard(result: dict) -> None:
    typer.echo("")
    typer.echo(f"  Cost Dashboard — period: {result['period']}")
    typer.echo(f"  {'=' * 50}")
    typer.echo(f"  Total cost:  ${result['total_cost']:.6f}")
    typer.echo(f"  Log count:   {result['log_count']}")
    typer.echo("")

    # Breakdown by domain
    by_domain = result.get("by_domain", [])
    if by_domain:
        typer.echo("  Costs by domain:")
        typer.echo(f"    {'Domain':<25} {'Cost':>12} {'%':>8} {'Logs':>6}")
        typer.echo(f"    {'-'*25} {'-'*12} {'-'*8} {'-'*6}")
        for d in by_domain:
            typer.echo(
                f"    {d['domain']:<25} ${d['cost']:>10.6f} {d['pct_of_total']:>7.2f}% {d['log_count']:>6}"
            )
        typer.echo("")

    # Daily trend
    daily_trend = result.get("daily_trend", [])
    if daily_trend:
        typer.echo("  Daily cost trend:")
        typer.echo(f"    {'Day':<15} {'Cost':>12} {'Logs':>6}")
        typer.echo(f"    {'-'*15} {'-'*12} {'-'*6}")
        for d in daily_trend:
            typer.echo(
                f"    {d['day']:<15} ${d['cost']:>10.6f} {d['log_count']:>6}"
            )
        typer.echo("")

    # Top 5 models
    top_models = result.get("top_models", [])
    if top_models:
        typer.echo("  Top 5 most expensive models:")
        typer.echo(f"    {'Model':<35} {'Cost':>12} {'Tokens':>12} {'Calls':>8}")
        typer.echo(f"    {'-'*35} {'-'*12} {'-'*12} {'-'*8}")
        for m in top_models:
            typer.echo(
                f"    {m['model']:<35} ${m['cost']:>10.6f} {m['total_tokens']:>12,} {m['call_count']:>8}"
            )
        typer.echo("")

    # Top 5 sources
    top_sources = result.get("top_sources", [])
    if top_sources:
        typer.echo("  Top 5 most expensive API sources:")
        typer.echo(f"    {'Source':<25} {'Cost':>12} {'Calls':>8}")
        typer.echo(f"    {'-'*25} {'-'*12} {'-'*8}")
        for s in top_sources:
            typer.echo(
                f"    {s['source_type']:<25} ${s['cost']:>10.6f} {s['call_count']:>8}"
            )
        typer.echo("")

    # Budget status
    budget_status = result.get("budget_status", [])
    if budget_status:
        typer.echo("  Budget status:")
        typer.echo(f"    {'Domain':<25} {'Cost':>12} {'Budget':>10} {'Used':>8} {'Status':>10}")
        typer.echo(f"    {'-'*25} {'-'*12} {'-'*10} {'-'*8} {'-'*10}")
        for b in budget_status:
            typer.echo(
                f"    {b['domain']:<25} ${b['cost']:>10.6f} ${b['budget']:>8.2f} {b['pct_used']:>7.1f}% {b['status']:>10}"
            )
        typer.echo("")


@app.command()
def allocation(
    domain: str = typer.Option("", "--domain", help="Domain filter"),
    user_id: str = typer.Option("", "--user-id", help="User ID filter"),
    period: str = typer.Option("all", "--period", help="Time period (all/today/week/month)"),
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
) -> None:
    """Show cost allocation broken down by domain and user."""
    try:
        from autoinfo.cost import CostMeter

        meter = CostMeter()
        result = meter.get_cost_allocation(
            domain=domain, user_id=user_id, period=period
        )
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)

    if json_output:
        typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_human(result)


def _print_human(result: dict) -> None:
    typer.echo(f"Period:      {result['period']}")
    typer.echo(f"Domain:      {result['domain_filter'] or '(all)'}")
    typer.echo(f"User ID:     {result['user_id_filter'] or '(all)'}")
    typer.echo(f"Total cost:  ${result['total_cost']:.6f}")
    typer.echo(f"Log count:   {result['log_count']}")
    typer.echo("")

    by_domain = result.get("by_domain", [])
    if by_domain:
        typer.echo("Breakdown by domain:")
        typer.echo(f"  {'Domain':<25} {'Cost':>12} {'%':>8} {'Logs':>6}")
        typer.echo(f"  {'-'*25} {'-'*12} {'-'*8} {'-'*6}")
        for d in by_domain:
            typer.echo(
                f"  {d['domain']:<25} ${d['cost']:>10.6f} {d['pct_of_total']:>7.2f}% {d['log_count']:>6}"
            )
        typer.echo("")

    by_user = result.get("by_user", [])
    if by_user:
        typer.echo("Breakdown by user:")
        typer.echo(f"  {'User ID':<20} {'Domain':<25} {'Cost':>12} {'%':>8} {'Logs':>6}")
        typer.echo(f"  {'-'*20} {'-'*25} {'-'*12} {'-'*8} {'-'*6}")
        for u in by_user:
            typer.echo(
                f"  {u['user_id']:<20} {u['domain']:<25} ${u['cost']:>10.6f} {u['pct_of_total']:>7.2f}% {u['log_count']:>6}"
            )
