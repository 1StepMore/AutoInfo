"""Topics CLI — manage tracked topics.

Usage::

    autoinfo topics add --domain medical --name "IVF breakthroughs" --keywords IVF,embryo
    autoinfo topics list --domain medical
    autoinfo topics remove --domain medical --topic-id "IVF breakthroughs"
    autoinfo topic-group add --domain medical --group fertility --topic IVF
    autoinfo topic-group remove --domain medical --group fertility --topic IVF
"""

from __future__ import annotations

import builtins

import typer

from autoinfo.config import (
    DomainConfig,
    TopicConfig,
    ensure_config_exists,
    get_config_path,
    load_config,
    save_config,
)

app = typer.Typer(help="Manage tracked topics")

_NO_CONFIG_MSG = (
    "Error: No configuration file found. Run 'autoinfo init' first. "
    "See docs/dev/required-api-keys.md for API key setup."
)


@app.command()
def add(
    domain: str = typer.Option(..., "--domain", help="Domain to add topic to"),
    name: str = typer.Option(..., "--name", help="Topic name"),
    keywords: str = typer.Option(
        ..., "--keywords", help="Comma-separated topic keywords"
    ),
) -> None:
    """Add a new topic to a domain (idempotent by name+domain)."""
    ensure_config_exists()
    config_path = get_config_path()
    if config_path is None:
        typer.echo("Error: No configuration file found. Run 'autoinfo init' first. See docs/dev/required-api-keys.md for API key setup.", err=True)
        raise typer.Exit(code=1)

    config = load_config(config_path)

    domain_cfg = _find_domain(config, domain)
    if domain_cfg is None:
        typer.echo(f"Error: Domain '{domain}' is not configured", err=True)
        raise typer.Exit(code=1)

    # Idempotency check: same name + domain
    for existing in domain_cfg.topics:
        if existing.name == name:
            kw_str = ", ".join(existing.keywords)
            typer.echo(f"Topic '{name}' already exists in domain '{domain}' (keywords: {kw_str})")
            return

    kw_list = [k.strip() for k in keywords.split(",") if k.strip()]
    if not kw_list:
        typer.echo("Error: At least one keyword is required.", err=True)
        raise typer.Exit(code=1)
    new_topic = TopicConfig(name=name, keywords=kw_list)
    domain_cfg.topics.append(new_topic)
    save_config(config, config_path)

    kw_str = ", ".join(kw_list)
    typer.echo(f"Added topic '{name}' to domain '{domain}' (keywords: {kw_str})")


@app.command()
def list(  # noqa: A001 — shadowing built-in list is intentional for CLI
    domain: str = typer.Option(..., "--domain", help="Domain to list topics for"),
) -> None:
    """List topics for a domain."""
    ensure_config_exists()
    config_path = get_config_path()
    if config_path is None:
        typer.echo("Error: No configuration file found. Run 'autoinfo init' first. See docs/dev/required-api-keys.md for API key setup.", err=True)
        raise typer.Exit(code=1)

    config = load_config(config_path)

    domain_cfg = _find_domain(config, domain)
    if domain_cfg is None:
        typer.echo(f"Error: Domain '{domain}' is not configured", err=True)
        raise typer.Exit(code=1)

    if not domain_cfg.topics:
        typer.echo(f"No topics configured for domain '{domain}'")
        return

    typer.echo(f"Topics for domain '{domain}':")
    for topic in domain_cfg.topics:
        kw_str = ", ".join(topic.keywords) if topic.keywords else "(none)"
        typer.echo(f"  - {topic.name} (keywords: {kw_str})")


@app.command()
def remove(
    domain: str = typer.Option(..., "--domain", help="Domain the topic belongs to"),
    topic_id: str = typer.Option(
        ..., "--topic-id", help="ID or name of the topic to remove"
    ),
) -> None:
    """Remove a topic from a domain."""
    ensure_config_exists()
    config_path = get_config_path()
    if config_path is None:
        typer.echo("Error: No configuration file found. Run 'autoinfo init' first. See docs/dev/required-api-keys.md for API key setup.", err=True)
        raise typer.Exit(code=1)

    config = load_config(config_path)

    domain_cfg = _find_domain(config, domain)
    if domain_cfg is None:
        typer.echo(f"Error: Domain '{domain}' is not configured", err=True)
        raise typer.Exit(code=1)

    for i, existing in enumerate(domain_cfg.topics):
        if existing.name == topic_id:
            domain_cfg.topics.pop(i)
            save_config(config, config_path)
            typer.echo(f"Removed topic '{topic_id}' from domain '{domain}'")
            return

    typer.echo(f"Error: Topic '{topic_id}' not found in domain '{domain}'", err=True)
    raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# topic-group subcommand (autoinfo topic-group add|remove)
#
# Mirrors the MCP tools topic_group_add / topic_group_remove
# (src/autoinfo/mcp/server.py:_handle_topic_group_add / _handle_topic_group_remove).
# Parameter mapping: domain -> --domain, group_name -> --group,
# topic_names -> --topic (repeatable).  --domain defaults to the first
# configured domain when omitted.
# ---------------------------------------------------------------------------


topic_group_app = typer.Typer(
    help="Manage topic groups (mirrors MCP topic_group_add/topic_group_remove)"
)
app.add_typer(topic_group_app, name="topic-group")


@topic_group_app.command("add")
def topic_group_add(
    domain: str | None = typer.Option(
        None,
        "--domain",
        help="Domain the topics belong to (default: first configured domain)",
    ),
    group: str = typer.Option(..., "--group", help="Group name to assign (MCP group_name)"),
    topic: builtins.list[str] = typer.Option(
        ..., "--topic", help="Topic name to assign to the group (repeatable; MCP topic_names)"
    ),
) -> None:
    """Assign a group to one or more topics (mirrors MCP topic_group_add)."""
    ensure_config_exists()
    config_path = get_config_path()
    if config_path is None:
        typer.echo(_NO_CONFIG_MSG, err=True)
        raise typer.Exit(code=1)

    config = load_config(config_path)
    domain_cfg = _resolve_domain(config, domain)
    if domain_cfg is None:
        typer.echo(f"Error: Domain '{domain}' is not configured", err=True)
        raise typer.Exit(code=1)

    assigned: builtins.list[str] = []
    not_found: builtins.list[str] = []
    for name in topic:
        found = False
        for t in domain_cfg.topics:
            if t.name == name:
                t.group = group
                assigned.append(name)
                found = True
                break
        if not found:
            not_found.append(name)

    if assigned:
        save_config(config, config_path)

    for name in assigned:
        typer.echo(f"Assigned topic '{name}' to group '{group}' in domain '{domain_cfg.name}'")
    for name in not_found:
        typer.echo(f"Topic '{name}' not found in domain '{domain_cfg.name}' (skipped)")
    if not assigned:
        typer.echo(
            f"No topics assigned to group '{group}' in domain '{domain_cfg.name}'"
        )


@topic_group_app.command("remove")
def topic_group_remove(
    domain: str | None = typer.Option(
        None,
        "--domain",
        help="Domain the topics belong to (default: first configured domain)",
    ),
    group: str = typer.Option(..., "--group", help="Group name to clear (MCP group_name)"),
    topic: builtins.list[str] = typer.Option(
        [],
        "--topic",
        help=(
            "Optional topic filter (repeatable). When omitted, clears the "
            "group from every topic (MCP topic_group_remove behavior)"
        ),
    ),
) -> None:
    """Remove a group assignment from topics (mirrors MCP topic_group_remove)."""
    ensure_config_exists()
    config_path = get_config_path()
    if config_path is None:
        typer.echo(_NO_CONFIG_MSG, err=True)
        raise typer.Exit(code=1)

    config = load_config(config_path)
    domain_cfg = _resolve_domain(config, domain)
    if domain_cfg is None:
        typer.echo(f"Error: Domain '{domain}' is not configured", err=True)
        raise typer.Exit(code=1)

    cleared: builtins.list[str] = []
    skipped: builtins.list[str] = []

    if topic:
        # Filtered remove: only clear the named topics, and only when they
        # actually carry the group.
        for name in topic:
            target = None
            for t in domain_cfg.topics:
                if t.name == name:
                    target = t
                    break
            if target is None:
                skipped.append(f"topic '{name}' not found")
            elif target.group != group:
                skipped.append(f"topic '{name}' is not in group '{group}'")
            else:
                target.group = ""
                cleared.append(name)
    else:
        # Unfiltered remove: clear the group from every topic carrying it.
        for t in domain_cfg.topics:
            if t.group == group:
                t.group = ""
                cleared.append(t.name)

    if cleared:
        save_config(config, config_path)

    for name in cleared:
        typer.echo(f"Removed group '{group}' from topic '{name}' in domain '{domain_cfg.name}'")
    for note in skipped:
        typer.echo(f"Skipped {note} in domain '{domain_cfg.name}'")
    if not cleared:
        if topic:
            typer.echo(
                f"No topics in group '{group}' were removed in domain '{domain_cfg.name}'"
            )
        else:
            typer.echo(
                f"No topics are assigned to group '{group}' in domain '{domain_cfg.name}'"
            )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


@app.command()
def keywords(
    domain: str = typer.Option(..., "--domain", help="Domain to list keywords for"),
    topic: str = typer.Option(None, "--topic", help="Optional topic name filter"),
) -> None:
    """List keywords with topic grouping and scoring info."""
    ensure_config_exists()
    config_path = get_config_path()
    if config_path is None:
        typer.echo("Error: No configuration file found. Run 'autoinfo init' first. See docs/dev/required-api-keys.md for API key setup.", err=True)
        raise typer.Exit(code=1)

    config = load_config(config_path)

    domain_cfg = _find_domain(config, domain)
    if domain_cfg is None:
        typer.echo(f"Error: Domain '{domain}' is not configured", err=True)
        raise typer.Exit(code=1)

    found = False
    for t in domain_cfg.topics:
        if topic and t.name != topic:
            continue
        found = True
        kw_display = t.keywords if t.keywords else "(none)"
        group_info = f" [group: {t.group}]" if t.group else ""
        threshold_info = f" [threshold: {t.relevance_threshold}]"
        typer.echo(f"  - {t.name}{group_info}{threshold_info}")
        typer.echo(f"    keywords: {kw_display}")
    if not found:
        if topic:
            typer.echo(f"No topic '{topic}' found in domain '{domain}'")
        else:
            typer.echo(f"No topics configured for domain '{domain}'")


# ---------------------------------------------------------------------------
# group subcommand (autoinfo topics group add|remove)
# ---------------------------------------------------------------------------


group_app = typer.Typer(help="Manage topic groups")
app.add_typer(group_app, name="group")


@group_app.command("add")
def group_add(
    domain: str = typer.Option(..., "--domain", help="Domain the topic belongs to"),
    topic: str = typer.Argument(..., help="Topic name"),
    group: str = typer.Option(..., "--group", help="Group name to assign"),
) -> None:
    """Assign a group to a topic."""
    ensure_config_exists()
    config_path = get_config_path()
    if config_path is None:
        typer.echo("Error: No configuration file found. Run 'autoinfo init' first. See docs/dev/required-api-keys.md for API key setup.", err=True)
        raise typer.Exit(code=1)

    config = load_config(config_path)
    domain_cfg = _find_domain(config, domain)
    if domain_cfg is None:
        typer.echo(f"Error: Domain '{domain}' is not configured", err=True)
        raise typer.Exit(code=1)

    for t in domain_cfg.topics:
        if t.name == topic:
            t.group = group
            save_config(config, config_path)
            typer.echo(f"Set group '{group}' on topic '{topic}' in domain '{domain}'")
            return

    typer.echo(f"Error: Topic '{topic}' not found in domain '{domain}'", err=True)
    raise typer.Exit(code=1)


@group_app.command("remove")
def group_remove(
    domain: str = typer.Option(..., "--domain", help="Domain the topic belongs to"),
    topic: str = typer.Argument(..., help="Topic name"),
) -> None:
    """Remove group assignment from a topic."""
    ensure_config_exists()
    config_path = get_config_path()
    if config_path is None:
        typer.echo("Error: No configuration file found. Run 'autoinfo init' first. See docs/dev/required-api-keys.md for API key setup.", err=True)
        raise typer.Exit(code=1)

    config = load_config(config_path)
    domain_cfg = _find_domain(config, domain)
    if domain_cfg is None:
        typer.echo(f"Error: Domain '{domain}' is not configured", err=True)
        raise typer.Exit(code=1)

    for t in domain_cfg.topics:
        if t.name == topic:
            if not t.group:
                typer.echo(f"Topic '{topic}' in domain '{domain}' has no group set")
                return
            old_group = t.group
            t.group = ""
            save_config(config, config_path)
            typer.echo(f"Removed group '{old_group}' from topic '{topic}' in domain '{domain}'")
            return

    typer.echo(f"Error: Topic '{topic}' not found in domain '{domain}'", err=True)
    raise typer.Exit(code=1)


def _find_domain(config: object, name: str) -> DomainConfig | None:
    """Return the domain config for *name*, or ``None``."""
    from autoinfo.config import Config

    if isinstance(config, Config):
        for d in config.domains:
            if d.name == name:
                return d
    return None


def _resolve_domain(config: object, name: str | None) -> DomainConfig | None:
    """Return the domain config for *name*; when *name* is None, the first
    configured domain; or ``None`` if no match/no domains."""
    from autoinfo.config import Config

    if not isinstance(config, Config):
        return None
    if name:
        for d in config.domains:
            if d.name == name:
                return d
        return None
    if config.domains:
        return config.domains[0]
    return None
