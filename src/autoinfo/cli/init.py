"""`autoinfo init` — project skeleton generator.

Creates the `.autoinfo/` directory structure, default config, and
optionally populates it with a demo domain definition.
"""

from __future__ import annotations

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
_REQUIRED_SUBDIRS = ["knowledge/01-Raw", "collections", "outputs"]


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
) -> bool:
    """Generate .autoinfo/config.yaml from default_config.yaml + domain name.

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

    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    typer.echo(f"  CREATE  {dst}")
    return True


@app.command()
def init(
    demo: Optional[str] = typer.Option(
        None,
        "--demo",
        "-d",
        help="Demo domain to initialize (omit to list available domains).",
        show_default=False,
    ),
) -> None:
    """Initialize AutoInfo project skeleton.

    Creates the .autoinfo/ directory structure with default configuration
    and (optionally) a demo domain definition.
    """
    # --- No --demo flag: list available domains ---
    if not demo:
        _print_demo_domains()
        return

    demo = demo.strip()

    # --- Validate demo domain exists ---
    demo_sources = _DEMO_DOMAINS_DIR / demo / "sources.yaml"
    if not demo_sources.is_file():
        typer.echo(
            f"  ERROR  unknown demo domain: '{demo}'. "
            f"Run `autoinfo init` without --demo to see available domains.",
            err=True,
        )
        raise typer.Exit(code=1)

    # --- Create .autoinfo/ at current working directory ---
    autoinfo_dir = Path.cwd() / ".autoinfo"
    _ensure_dir(autoinfo_dir)

    # --- Generate config.yaml ---
    config_dst = autoinfo_dir / "config.yaml"
    _generate_config(demo, config_dst)

    # --- Copy sources.yaml ---
    sources_dst = autoinfo_dir / "sources.yaml"
    _copy_template(demo_sources, sources_dst)

    # --- Create required sub-directories ---
    for sub in _REQUIRED_SUBDIRS:
        d = autoinfo_dir / sub
        if _ensure_dir(d):
            typer.echo(f"  CREATE  {d}/")
        else:
            typer.echo(f"  SKIP  {d}/  (already exists)")

    # --- Success message with next steps ---
    typer.echo()
    typer.echo(f"✅ AutoInfo initialized for '{demo}'.")
    typer.echo()
    typer.echo("Next steps:")
    typer.echo("  1. Set your LLM API key:")
    typer.echo("     export AUTOINFO_LLM_API_KEY='sk-...'")
    typer.echo()
    typer.echo("  2. Collect from sources:")
    typer.echo(f"     autoinfo collect --domain {demo} --topic \"IVF breakthroughs\" --limit 5")
    typer.echo()
    typer.echo("  3. Process collected items:")
    typer.echo(f"     autoinfo process --domain {demo}")
