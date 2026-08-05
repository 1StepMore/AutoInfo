"""Alert rules CLI — mirror of the MCP alert rule tools.

Usage::

    autoinfo alert-rules add --domain medical-research --topic-keywords IVF --topic-keywords embryo
    autoinfo alert-rules list --domain medical-research
    autoinfo alert-rules remove --id alert-ab12cd34

Mirrors ``add_alert_rule`` / ``get_alert_rules`` / ``remove_alert_rule``.
Parameter names are identical (domain, topic_keywords, relevance_threshold,
channel, enabled, id). Storage stays YAML (``.autoinfo/alerts.yaml``).
"""

from __future__ import annotations

import json
from dataclasses import asdict

import typer

app = typer.Typer(
    name="alert-rules",
    help="Manage alert rules — mirrors MCP add_alert_rule/get_alert_rules/remove_alert_rule",
)

_VALID_CHANNELS = ("email", "webhook")


def _fail(message: str) -> None:
    typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(code=1)


@app.command()
def add(
    domain: str = typer.Option(
        ..., "--domain", help="Domain name this rule applies to (e.g. medical-research)"
    ),
    topic_keywords: list[str] = typer.Option(
        [],
        "--topic-keywords",
        help="Keywords to match against item title and content (repeatable). "
        "Empty list matches all items",
    ),
    relevance_threshold: float = typer.Option(
        0.0, "--relevance-threshold", help="Minimum relevance score (0-100) to trigger"
    ),
    channel: str = typer.Option(
        "email", "--channel", help="Delivery channel: email or webhook"
    ),
    enabled: bool = typer.Option(
        True, "--enabled/--no-enabled", help="Whether the rule is active"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Create a new alert rule for a domain (mirrors MCP add_alert_rule)."""
    if channel not in _VALID_CHANNELS:
        _fail(f"Invalid channel '{channel}'. Valid channels: email, webhook")

    # Deferred import — mirrors the MCP handler
    from autoinfo.alerts import add_alert_rule

    rule = add_alert_rule(
        domain=domain,
        topic_keywords=topic_keywords,
        relevance_threshold=relevance_threshold,
        channel=channel,  # type: ignore[arg-type]
        enabled=enabled,
    )

    if json_output:
        typer.echo(json.dumps({"alert_rule": asdict(rule), "created": True}, indent=2))
    else:
        typer.echo(
            f"Added alert rule '{rule.id}' for domain '{domain}' "
            f"(channel={channel}, threshold={relevance_threshold}, enabled={enabled})"
        )


@app.command("list")
def list_cmd(
    domain: str | None = typer.Option(
        None,
        "--domain",
        help="Filter by domain (e.g. medical-research). Omit to list all rules "
        "(superset of MCP get_alert_rules, which requires a domain)",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """List alert rules, optionally filtered by domain (mirrors MCP get_alert_rules)."""
    # Deferred import — mirrors the MCP handler
    from autoinfo.alerts import list_alert_rules

    rules = list_alert_rules(domain=domain)

    if json_output:
        typer.echo(
            json.dumps(
                {
                    "domain": domain or "*",
                    "alert_rules": [asdict(r) for r in rules],
                    "count": len(rules),
                },
                indent=2,
            )
        )
        return

    if not rules:
        if domain:
            typer.echo(f"No alert rules found for domain '{domain}'")
        else:
            typer.echo("No alert rules found")
        return

    for rule in rules:
        typer.echo(
            f"{rule.id}  domain={rule.domain}  channel={rule.channel}  "
            f"threshold={rule.relevance_threshold}  enabled={rule.enabled}  "
            f"keywords={','.join(rule.topic_keywords) or '-'}"
        )


@app.command()
def remove(
    id: str = typer.Option(  # noqa: A002 — mirrors the MCP tool param name
        ..., "--id", help="Alert rule ID to remove (returned by add)"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Remove an alert rule by its ID (mirrors MCP remove_alert_rule)."""
    # Deferred import — mirrors the MCP handler
    from autoinfo.alerts import remove_alert_rule

    removed = remove_alert_rule(id)

    if not removed:
        # Mirrors the MCP handler's AlertRuleNotFound response
        if json_output:
            typer.echo(
                json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "AlertRuleNotFound",
                            "message": f"Alert rule '{id}' not found",
                            "actionable": True,
                        },
                    },
                    indent=2,
                )
            )
        else:
            typer.echo(f"Error: Alert rule '{id}' not found", err=True)
        raise typer.Exit(code=1)

    if json_output:
        typer.echo(json.dumps({"removed": True, "alert_rule_id": id}, indent=2))
    else:
        typer.echo(f"Removed alert rule '{id}'")
