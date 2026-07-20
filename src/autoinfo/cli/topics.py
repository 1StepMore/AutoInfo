"""Topics CLI — manage tracked topics.

Usage::

    autoinfo topics add --domain medical --name "IVF breakthroughs" --keywords IVF,embryo
    autoinfo topics list --domain medical
    autoinfo topics remove --domain medical --topic-id "IVF breakthroughs"
"""

from __future__ import annotations

import typer

from autoinfo.config import (
    DomainConfig,
    TopicConfig,
    get_config_path,
    load_config,
    save_config,
    ensure_config_exists,
)

app = typer.Typer(help="Manage tracked topics")


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
        typer.echo("Error: No configuration file found. Run 'autoinfo init' first.", err=True)
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
        typer.echo("Error: No configuration file found. Run 'autoinfo init' first.", err=True)
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
        typer.echo("Error: No configuration file found. Run 'autoinfo init' first.", err=True)
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
# Internal helpers
# ---------------------------------------------------------------------------


def _find_domain(config: object, name: str) -> DomainConfig | None:
    """Return the domain config for *name*, or ``None``."""
    from autoinfo.config import Config

    if isinstance(config, Config):
        for d in config.domains:
            if d.name == name:
                return d
    return None
