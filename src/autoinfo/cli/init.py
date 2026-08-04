from __future__ import annotations

"""`autoinfo init` — project skeleton generator.

Creates the `.autoinfo/` directory structure, default config, and
optionally populates it with a demo domain definition.
"""


import os
import sys
from pathlib import Path
from typing import Optional, List

import typer
import yaml

app = typer.Typer(help="Initialize AutoInfo project skeleton.")

# Paths to bundled data files (relative to this source file)
_HERE = Path(__file__).resolve().parent
_DATA_DIR = _HERE.parent / "data"
_DEFAULT_CONFIG = _DATA_DIR / "default_config.yaml"
_DEMO_DOMAINS_DIR = _DATA_DIR / "domains"

# Runtime directories created at project root (data dirs; config stays in .autoinfo/)
_REQUIRED_SUBDIRS = [
    "knowledge/00-Inbox",
    "knowledge/01-Raw",
    "knowledge/02-Draft",
    "knowledge/03-Wiki",
    "collections",
    "outputs",
]


def _list_demo_domains() -> list[str]:
    """Return sorted list of available demo domain names (directory names)."""
    if not _DEMO_DOMAINS_DIR.is_dir():
        return []
    return sorted(
        d.name
        for d in _DEMO_DOMAINS_DIR.iterdir()
        if d.is_dir() and (d / "sources.yaml").is_file()
    )


def _print_demo_domains() -> None:
    """Print available demo domains to stdout."""
    domains = _list_demo_domains()
    if not domains:
        typer.echo("No demo domains found.")
        return

    typer.echo("Available demo domains:")
    for d in domains:
        typer.echo(f"  - {d}")
    typer.echo()
    typer.echo("Usage:  autoinfo init --demo <domain>")


def _ensure_dir(path: Path) -> bool:
    """Create directory if it doesn't exist. Returns True if created."""
    if path.exists():
        return False
    path.mkdir(parents=True, exist_ok=True)
    return True


def _generate_config(
    domain_names: list[str],
    dst: Path,
    project_name: str = "",
) -> bool:
    """Generate .autoinfo/config.yaml from default_config.yaml + domain names.

    When *project_name* is non-empty it is stored under both
    ``project.name`` and ``project.project_name`` in the generated YAML
    (the latter for backward compatibility).

    Can accept one or more *domain_names* to configure multiple demo
    domains in a single config file.

    Returns True if the file was written, False if skipped (already exists).
    """
    if dst.exists():
        typer.echo(f"  SKIP  {dst}  (already exists)")
        return False

    if not _DEFAULT_CONFIG.is_file():
        typer.echo(f"  ERROR  default config template missing: {_DEFAULT_CONFIG}", err=True)
        raise typer.Exit(code=1)

    with open(_DEFAULT_CONFIG, "r") as f:
        config = yaml.safe_load(f)

    config["domains"] = []
    for domain_name in domain_names:
        demo_sources_path = _DEMO_DOMAINS_DIR / domain_name / "sources.yaml"
        if demo_sources_path.is_file():
            with open(demo_sources_path) as f:
                domain_data = yaml.safe_load(f)
            config["domains"].append({
                "name": domain_name,
                "active": True,
                "sources": domain_data.get("sources", []),
                "topics": domain_data.get("topics", []),
            })
        else:
            config["domains"].append({
                "name": domain_name,
                "active": True,
                "sources": [],
                "topics": [],
            })

    if project_name:
        proj = config.setdefault("project", {})
        proj["name"] = project_name
        proj["project_name"] = project_name

    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    typer.echo(f"  CREATE  {dst}")
    return True


def _run_init(domains: list[str], autoinfo_dir: Path, project_name: str = "") -> None:
    """Core init logic: generate config, create subdirs, print next steps."""
    config_dst = autoinfo_dir / "config.yaml"
    _generate_config(domains, config_dst, project_name=project_name)

    for sub in _REQUIRED_SUBDIRS:
        d = autoinfo_dir.parent / sub
        if _ensure_dir(d):
            typer.echo(f"  CREATE  {d}/")
        else:
            typer.echo(f"  SKIP  {d}/  (already exists)")

    first_topic = None
    first_domain = domains[0] if domains else ""
    demo_sources = _DEMO_DOMAINS_DIR / first_domain / "sources.yaml"
    if demo_sources.is_file():
        with open(demo_sources) as f:
            domain_data = yaml.safe_load(f)
        topics = domain_data.get("topics", [])
        if topics:
            first_topic = topics[0].get("name")

    typer.echo()
    if len(domains) == 1:
        typer.echo(f"✅ AutoInfo initialized for '{first_domain}'.")
    else:
        typer.echo(f"✅ AutoInfo initialized for {len(domains)} domains: {', '.join(domains)}.")
    typer.echo()
    typer.echo("Next steps:")
    typer.echo("  1. Set your LLM API key:")
    typer.echo("     export AUTOINFO_LLM_API_KEY='sk-...'")
    typer.echo()
    typer.echo("  2. Collect from sources:")
    if first_topic:
        typer.echo(f"     autoinfo collect --domain {first_domain} --topic \"{first_topic}\" --limit 5")
    else:
        typer.echo(f"     autoinfo collect --domain {first_domain} --limit 5")
    typer.echo()
    typer.echo("  3. Process collected items:")
    typer.echo(f"     autoinfo process --domain {first_domain}")


@app.command()
def init(
    demo: Optional[List[str]] = typer.Option(
        None,
        "--demo",
        "-d",
        help="Demo domain to initialize (omit to enter interactive mode). May be repeated for multiple domains.",
        show_default=False,
    ),
    name: Optional[str] = typer.Option(
        None,
        "--name",
        "-n",
        help="Optional human-friendly project name stored as project.name (and project.project_name for backward compat) in config.",
        show_default=False,
    ),
    interactive: bool = typer.Option(
        True,
        "--interactive/--no-interactive",
        "-i",
        help="Run in interactive mode (prompt for domain, LLM provider, API key).",
    ),
    list_domains: bool = typer.Option(
        False,
        "--list-domains",
        help="Show available demo domains and exit.",
    ),
) -> None:
    """Initialize AutoInfo project skeleton.

    Creates the .autoinfo/ directory structure with default configuration
    and (optionally) one or more demo domain definitions.

    Without --demo, the interactive wizard guides you through domain
    selection, LLM provider setup, and optional API key configuration.

    Use --name to give your project a human-friendly name (stored in config
    under ``project.name`` and ``project.project_name``).
    """
    if list_domains:
        _print_demo_domains()
        return

    if demo:
        autoinfo_dir = Path.cwd() / ".autoinfo"
        _ensure_dir(autoinfo_dir)

        validated: list[str] = []
        for d in demo:
            d = d.strip()
            demo_sources = _DEMO_DOMAINS_DIR / d / "sources.yaml"
            if not demo_sources.is_file():
                typer.echo(
                    f"  ERROR  unknown demo domain: '{d}'. "
                    f"Run `autoinfo init --list-domains` to see available domains.",
                    err=True,
                )
                raise typer.Exit(code=1)
            validated.append(d)

        _run_init(validated, autoinfo_dir, project_name=name or "")
        return

    if not interactive:
        _print_demo_domains()
        typer.echo()
        typer.echo(
            "Tip: Use --demo <domain> to initialize non-interactively.\n"
            "  Examples:\n"
            "    autoinfo init --demo medical-research\n"
            "    autoinfo init --demo medical-research --demo ai-commercial --name MyProject\n"
            "    autoinfo init --list-domains  (to see available domains)"
        )
        return

    # Interactive mode — ensure a real terminal is available
    if not sys.stdin.isatty():
        typer.echo(
            "No interactive terminal available. Use --demo <domain> to initialize\n"
            "non-interactively, or --list-domains to see available domains.",
            err=True,
        )
        raise typer.Exit(code=1)

    domains = _list_demo_domains()
    if not domains:
        typer.echo("No demo domains found. Cannot initialize interactively.", err=True)
        raise typer.Exit(code=1)

    try:
        project_name = typer.prompt("Project name (optional)", default="")
    except (EOFError, KeyboardInterrupt):
        typer.echo("")
        raise typer.Exit(code=0)

    typer.echo("Available demo domains:")
    for i, d in enumerate(domains, 1):
        typer.echo(f"  [{i}] {d}")

    try:
        choice = typer.prompt("Select a demo domain", type=int)
    except (EOFError, KeyboardInterrupt):
        typer.echo("")
        raise typer.Exit(code=0)
    if choice < 1 or choice > len(domains):
        typer.echo(f"  ERROR  invalid choice: {choice}", err=True)
        raise typer.Exit(code=1)

    selected_domain = domains[choice - 1]

    try:
        provider = typer.prompt("LLM provider", default="openrouter")
    except (EOFError, KeyboardInterrupt):
        typer.echo("")
        raise typer.Exit(code=0)
    typer.echo(f"  Using provider: {provider}")

    try:
        api_key = typer.prompt("Set AUTOINFO_LLM_API_KEY (optional)", default="")
    except (EOFError, KeyboardInterrupt):
        typer.echo("")
        raise typer.Exit(code=0)
    if api_key:
        os.environ["AUTOINFO_LLM_API_KEY"] = api_key
        typer.echo("  AUTOINFO_LLM_API_KEY set for this session.")
    else:
        typer.echo("  SKIP  LLM API key not set (use export AUTOINFO_LLM_API_KEY=... later)")

    autoinfo_dir = Path.cwd() / ".autoinfo"
    _ensure_dir(autoinfo_dir)

    _run_init([selected_domain], autoinfo_dir, project_name=project_name)
