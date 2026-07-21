from __future__ import annotations

"""`autoinfo init` — project skeleton generator.

Creates the `.autoinfo/` directory structure, default config, and
optionally populates it with a demo domain definition.
"""


import os
import shutil
from pathlib import Path
from typing import Optional

import typer
import yaml

app = typer.Typer(help="Initialize AutoInfo project skeleton.")

# Paths to bundled data files (relative to this source file)
_HERE = Path(__file__).resolve().parent
_DATA_DIR = _HERE.parent / "data"
_DEFAULT_CONFIG = _DATA_DIR / "default_config.yaml"
_DEMO_DOMAINS_DIR = _DATA_DIR / "domains"

# Directory structure created inside .autoinfo/
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


def _copy_template(
    src: Path,
    dst: Path,
    dry_run: bool = False,
) -> bool:
    """Copy a template file from src to dst. Returns True if copied.

    Skips if dst already exists.  Handles missing src gracefully.
    """
    if dst.exists():
        typer.echo(f"  SKIP  {dst}  (already exists)")
        return False

    if not src.is_file():
        typer.echo(f"  WARN  template not found: {src}", err=True)
        return False

    if dry_run:
        return True

    shutil.copy2(src, dst)
    typer.echo(f"  CREATE  {dst}")
    return True


def _generate_config(
    domain_name: str,
    dst: Path,
    project_name: str = "",
) -> bool:
    """Generate .autoinfo/config.yaml from default_config.yaml + domain name.

    When *project_name* is non-empty it is stored under
    ``project.project_name`` in the generated YAML.

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

    # Load sources.yaml to build proper domain config structure
    demo_sources_path = _DEMO_DOMAINS_DIR / domain_name / "sources.yaml"
    if demo_sources_path.is_file():
        with open(demo_sources_path) as f:
            domain_data = yaml.safe_load(f)
        config["domains"] = [{
            "name": domain_name,
            "active": True,
            "sources": domain_data.get("sources", []),
            "topics": domain_data.get("topics", []),
        }]
    else:
        config["domains"] = [{"name": domain_name, "active": True, "sources": [], "topics": []}]

    if project_name:
        config.setdefault("project", {})["project_name"] = project_name

    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    typer.echo(f"  CREATE  {dst}")
    return True


def _run_init(domain: str, autoinfo_dir: Path, project_name: str = "") -> None:
    """Core init logic: generate config, copy sources, create subdirs, print next steps."""
    config_dst = autoinfo_dir / "config.yaml"
    _generate_config(domain, config_dst, project_name=project_name)

    demo_sources = _DEMO_DOMAINS_DIR / domain / "sources.yaml"
    sources_dst = autoinfo_dir / "sources.yaml"
    _copy_template(demo_sources, sources_dst)

    for sub in _REQUIRED_SUBDIRS:
        d = autoinfo_dir / sub
        if _ensure_dir(d):
            typer.echo(f"  CREATE  {d}/")
        else:
            typer.echo(f"  SKIP  {d}/  (already exists)")

    first_topic = None
    if demo_sources.is_file():
        with open(demo_sources) as f:
            domain_data = yaml.safe_load(f)
        topics = domain_data.get("topics", [])
        if topics:
            first_topic = topics[0].get("name")

    typer.echo()
    typer.echo(f"✅ AutoInfo initialized for '{domain}'.")
    typer.echo()
    typer.echo("Next steps:")
    typer.echo("  1. Set your LLM API key:")
    typer.echo("     export AUTOINFO_LLM_API_KEY='sk-...'")
    typer.echo()
    typer.echo("  2. Collect from sources:")
    if first_topic:
        typer.echo(f"     autoinfo collect --domain {domain} --topic \"{first_topic}\" --limit 5")
    else:
        typer.echo(f"     autoinfo collect --domain {domain} --limit 5")
    typer.echo()
    typer.echo("  3. Process collected items:")
    typer.echo(f"     autoinfo process --domain {domain}")


@app.command()
def init(
    demo: Optional[str] = typer.Option(
        None,
        "--demo",
        "-d",
        help="Demo domain to initialize (omit to enter interactive mode).",
        show_default=False,
    ),
    name: Optional[str] = typer.Option(
        None,
        "--name",
        "-n",
        help="Optional human-friendly project name stored as project.project_name in config.",
        show_default=False,
    ),
    interactive: bool = typer.Option(
        True,
        "--interactive/--no-interactive",
        "-i",
        help="Run in interactive mode (prompt for domain, LLM provider, API key).",
    ),
) -> None:
    """Initialize AutoInfo project skeleton.

    Creates the .autoinfo/ directory structure with default configuration
    and (optionally) a demo domain definition.

    Without --demo, the interactive wizard guides you through domain
    selection, LLM provider setup, and optional API key configuration.

    Use --name to give your project a human-friendly name (stored in config
    under ``project.project_name``).
    """
    if demo:
        demo = demo.strip()

        demo_sources = _DEMO_DOMAINS_DIR / demo / "sources.yaml"
        if not demo_sources.is_file():
            typer.echo(
                f"  ERROR  unknown demo domain: '{demo}'. "
                f"Run `autoinfo init --no-interactive` to see available domains.",
                err=True,
            )
            raise typer.Exit(code=1)

        autoinfo_dir = Path.cwd() / ".autoinfo"
        _ensure_dir(autoinfo_dir)

        _run_init(demo, autoinfo_dir, project_name=name or "")
        return

    if not interactive:
        _print_demo_domains()
        return

    domains = _list_demo_domains()
    if not domains:
        typer.echo("No demo domains found. Cannot initialize interactively.", err=True)
        raise typer.Exit(code=1)

    project_name = typer.prompt("Project name (optional)", default="")

    typer.echo("Available demo domains:")
    for i, d in enumerate(domains, 1):
        typer.echo(f"  [{i}] {d}")

    choice = typer.prompt("Select a demo domain", type=int)
    if choice < 1 or choice > len(domains):
        typer.echo(f"  ERROR  invalid choice: {choice}", err=True)
        raise typer.Exit(code=1)

    selected_domain = domains[choice - 1]

    provider = typer.prompt("LLM provider", default="openrouter")
    typer.echo(f"  Using provider: {provider}")

    api_key = typer.prompt("Set AUTOINFO_LLM_API_KEY (optional)", default="")
    if api_key:
        os.environ["AUTOINFO_LLM_API_KEY"] = api_key
        typer.echo("  AUTOINFO_LLM_API_KEY set for this session.")
    else:
        typer.echo("  SKIP  LLM API key not set (use export AUTOINFO_LLM_API_KEY=... later)")

    autoinfo_dir = Path.cwd() / ".autoinfo"
    _ensure_dir(autoinfo_dir)

    _run_init(selected_domain, autoinfo_dir, project_name=project_name)
