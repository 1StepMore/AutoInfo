from __future__ import annotations

"""Domain CLI — manage domain configurations.

Usage::

    autoinfo domain add --name test --description "Test domain"
    autoinfo domain list
    autoinfo domain show --name test
    autoinfo domain remove --name test
    autoinfo domain activate --name test
    autoinfo domain deactivate --name test
"""


import json
from pathlib import Path

import typer
import yaml

from autoinfo.config import (
    Config,
    DomainConfig,
    SourceConfig,
    TopicConfig,
    get_config_path,
    load_config,
    save_config,
)

# Directory containing bundled demo domain definitions
_HERE = Path(__file__).resolve().parent
_DEMO_DOMAINS_DIR = _HERE.parent / "data" / "domains"

app = typer.Typer(help="Manage domain configurations")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load() -> tuple[Path, Config]:
    """Load the config and return ``(config_path, config)``.

    Exits with code 1 when no project config exists.
    """
    cfg_path = get_config_path()
    if cfg_path is None:
        typer.echo("Error: No configuration found. Run 'autoinfo init' first.", err=True)
        raise typer.Exit(1)
    config = load_config(cfg_path)
    return cfg_path, config


def _find_domain(config: Config, name: str) -> DomainConfig | None:
    """Return the domain config for *name*, or ``None``."""
    for d in config.domains:
        if d.name == name:
            return d
    return None


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command()
def add(
    name: str = typer.Option(..., "--name", help="Domain name"),
    description: str = typer.Option("", "--description", help="Domain description"),
) -> None:
    """Add a new domain configuration (idempotent)."""
    cfg_path, config = _load()

    domain_cfg = _find_domain(config, name)
    if domain_cfg is not None:
        typer.echo(f"Domain '{name}' already exists (active={domain_cfg.active}), skipped.")
        return

    new_domain = DomainConfig(name=name, description=description, active=True)
    config.domains.append(new_domain)
    save_config(config, cfg_path)
    typer.echo(f"Domain '{name}' added.")


@app.command(name="list")
def list_domains(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """List all configured domains."""
    _, config = _load()

    if json_output:
        domains_data = [
            {
                "name": d.name,
                "active": d.active,
                "source_count": len(d.sources),
                "topic_count": len(d.topics),
                "description": d.description,
            }
            for d in config.domains
        ]
        typer.echo(json.dumps({"domains": domains_data, "count": len(domains_data)}, indent=2))
        return

    if not config.domains:
        typer.echo("No domains configured.")
        return

    typer.echo(f"{'Name':<30} {'Active':<8} {'Sources':<10} {'Topics':<10} Description")
    typer.echo("-" * 100)
    for d in config.domains:
        active_str = "yes" if d.active else "no"
        typer.echo(
            f"{d.name:<30} {active_str:<8} {len(d.sources):<10} {len(d.topics):<10} {d.description}"
        )


@app.command()
def show(
    name: str = typer.Option(..., "--name", help="Domain name"),
) -> None:
    """Show full domain configuration."""
    _, config = _load()

    domain_cfg = _find_domain(config, name)
    if domain_cfg is None:
        typer.echo(f"Error: Domain '{name}' is not configured", err=True)
        raise typer.Exit(1)

    typer.echo(f"Domain:        {domain_cfg.name}")
    typer.echo(f"Description:   {domain_cfg.description}")
    typer.echo(f"Active:        {'yes' if domain_cfg.active else 'no'}")
    typer.echo(f"Search mode:   {domain_cfg.search_mode}")
    typer.echo(f"Sources:       {len(domain_cfg.sources)}")
    for s in domain_cfg.sources:
        typer.echo(f"  - {s.name} ({s.type}, tier={s.quality_tier}, tos={s.tos_classification}): {s.url}")
    typer.echo(f"Topics:        {len(domain_cfg.topics)}")
    for t in domain_cfg.topics:
        kw_str = ", ".join(t.keywords) if t.keywords else "(none)"
        typer.echo(f"  - {t.name} (keywords: {kw_str})")
    if domain_cfg.extract_fields:
        typer.echo(f"Extract fields: {', '.join(domain_cfg.extract_fields)}")


@app.command()
def remove(
    name: str = typer.Option(..., "--name", help="Domain name to remove"),
) -> None:
    """Remove a domain configuration (keeps collected data intact)."""
    cfg_path, config = _load()

    domain_cfg = _find_domain(config, name)
    if domain_cfg is None:
        typer.echo(f"Error: Domain '{name}' is not configured", err=True)
        raise typer.Exit(1)

    config.domains.remove(domain_cfg)
    save_config(config, cfg_path)
    typer.echo(f"Domain '{name}' removed (collected data preserved).")


@app.command()
def activate(
    name: str = typer.Option(..., "--name", help="Domain name to activate"),
) -> None:
    """Activate a domain."""
    cfg_path, config = _load()

    domain_cfg = _find_domain(config, name)
    if domain_cfg is None:
        typer.echo(f"Error: Domain '{name}' is not configured", err=True)
        raise typer.Exit(1)

    if domain_cfg.active:
        typer.echo(f"Domain '{name}' is already active.")
        return

    domain_cfg.active = True
    save_config(config, cfg_path)
    typer.echo(f"Domain '{name}' activated.")


@app.command()
def deactivate(
    name: str = typer.Option(..., "--name", help="Domain name to deactivate"),
) -> None:
    """Deactivate a domain."""
    cfg_path, config = _load()

    domain_cfg = _find_domain(config, name)
    if domain_cfg is None:
        typer.echo(f"Error: Domain '{name}' is not configured", err=True)
        raise typer.Exit(1)

    if not domain_cfg.active:
        typer.echo(f"Domain '{name}' is already inactive.")
        return

    domain_cfg.active = False
    save_config(config, cfg_path)
    typer.echo(f"Domain '{name}' deactivated.")


@app.command(name="import")
def import_cmd(
    from_demo: str = typer.Option(
        ..., "--from-demo", help="Name of the demo domain to import"
    ),
) -> None:
    """Import a demo domain into the current project configuration (idempotent)."""
    _SOURCE_CORE_KEYS = frozenset({"name", "type", "url", "quality_tier", "tos_classification"})
    _TIER_TOS_MAP = {1: "open", 2: "licensed", 3: "restricted", 4: "sensitive"}

    demo_yaml = _DEMO_DOMAINS_DIR / from_demo / "sources.yaml"
    if not demo_yaml.is_file():
        typer.echo(
            f"Unknown demo domain '{from_demo}'. "
            f"Available: {', '.join(sorted(d.name for d in _DEMO_DOMAINS_DIR.iterdir() if d.is_dir() and (d / 'sources.yaml').is_file()))}",
            err=True,
        )
        raise typer.Exit(1)

    cfg_path, config = _load()
    if _find_domain(config, from_demo) is not None:
        typer.echo(f"Domain '{from_demo}' already exists")
        return

    with open(demo_yaml) as f:
        domain_data = yaml.safe_load(f)

    sources = []
    for s in domain_data.get("sources", []):
        tier = s.get("quality_tier", 1)
        tos = s.get("tos_classification")
        if not tos:
            tos = _TIER_TOS_MAP.get(tier, "open")
        sources.append(
            SourceConfig(
                name=s.get("name", ""),
                type=s.get("type", "api"),
                url=s.get("url", ""),
                quality_tier=tier,
                tos_classification=tos,
                settings={k: v for k, v in s.items() if k not in _SOURCE_CORE_KEYS},
            )
        )

    topics = [
        TopicConfig(
            name=t.get("name", ""),
            keywords=t.get("keywords", []),
            group=t.get("group", ""),
            relevance_threshold=int(t.get("relevance_threshold", 30)),
        )
        for t in domain_data.get("topics", [])
    ]

    new_domain = DomainConfig(
        name=from_demo,
        description=domain_data.get("description", ""),
        active=True,
        sources=sources,
        topics=topics,
        extract_fields=domain_data.get("extract_fields", []),
    )
    config.domains.append(new_domain)
    save_config(config, cfg_path)
    typer.echo(f"Domain '{from_demo}' imported.")
