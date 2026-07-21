from __future__ import annotations
"""Sources CLI — manage collection sources.

Usage::

    autoinfo sources add --name pubmed --url https://... --type api --domain medical
    autoinfo sources list --domain medical
    autoinfo sources remove --source-id medical:pubmed
    autoinfo sources test --url https://... --type api
"""


import json
from pathlib import Path
from typing import Any

import httpx
import typer
import yaml

from autoinfo.config import (
    Config,
    SourceConfig,
    DomainConfig,
    get_config_path,
    load_config,
    save_config,
)

app = typer.Typer(help="Manage collection sources")

_VALID_SOURCE_TYPES = frozenset({"rss", "api", "web"})


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


def _validate_url(url: str) -> str | None:
    """Return an error message if *url* is invalid, or ``None``."""
    if not url or not isinstance(url, str):
        return "URL is required"
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        return "URL must start with http:// or https://"
    parts = url.split("://", 1)
    if len(parts) != 2 or not parts[1]:
        return "URL must have a valid host"
    return None


def _validate_type(type_: str) -> str | None:
    """Return an error message if *type_* is invalid, or ``None``."""
    if type_ not in _VALID_SOURCE_TYPES:
        return (
            f"Invalid source type '{type_}'. "
            f"Must be one of: {', '.join(sorted(_VALID_SOURCE_TYPES))}"
        )
    return None


def _infer_format(content_type: str, content_preview: str) -> str:
    """Infer content format from content-type header and body preview."""
    if "xml" in content_type:
        return "xml"
    if "json" in content_type:
        return "json"
    if "html" in content_type or "xhtml" in content_type:
        return "html"
    if content_preview.strip().startswith(("<rss", "<feed", "<?xml")):
        return "rss"
    if content_preview.strip().startswith("{"):
        return "json"
    return "unknown"


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command()
def add(
    name: str = typer.Option(..., "--name", help="Source name"),
    url: str = typer.Option(..., "--url", help="Source URL"),
    type: str = typer.Option(..., "--type", help="Source type (rss, api, web)"),
    domain: str = typer.Option(..., "--domain", help="Domain to add source to"),
) -> None:
    """Add a new source to a domain (idempotent by url + type + domain)."""
    # --- Validate arguments ---
    url_error = _validate_url(url)
    if url_error:
        typer.echo(f"Error: {url_error}", err=True)
        raise typer.Exit(1)

    type_error = _validate_type(type)
    if type_error:
        typer.echo(f"Error: {type_error}", err=True)
        raise typer.Exit(1)

    # --- Load config ---
    cfg_path, config = _load()

    domain_cfg = _find_domain(config, domain)
    if domain_cfg is None:
        typer.echo(f"Error: Domain '{domain}' is not configured", err=True)
        raise typer.Exit(1)

    # --- Idempotency check ---
    for existing in domain_cfg.sources:
        if existing.url == url and existing.type == type:
            typer.echo(
                f"Source already exists (domain={domain}, url={url}, type={type}), skipped."
            )
            return

    # --- Add source ---
    quality_tier = 1 if type in ("api", "rss") else 2
    new_source = SourceConfig(name=name, type=type, url=url, quality_tier=quality_tier)
    domain_cfg.sources.append(new_source)
    save_config(config, cfg_path)
    typer.echo(f"Source '{name}' added to domain '{domain}'.")


@app.command()
def add_sources(
    filename: str = typer.Option(
        ...,
        "--file",
        help="Path to JSON file containing a list of source objects",
    ),
) -> None:
    """Batch-add sources from a JSON file.

    Each source object must have ``name``, ``url``, ``domain`` and
    optionally ``type`` (default ``api``).  Errors are reported per source
    without aborting the batch.
    """
    src_path = Path(filename)
    if not src_path.is_file():
        typer.echo(f"Error: File not found: {filename}", err=True)
        raise typer.Exit(1)

    with open(src_path, encoding="utf-8") as fh:
        try:
            sources_list = json.load(fh)
        except json.JSONDecodeError as exc:
            typer.echo(f"Error: Invalid JSON in {filename}: {exc}", err=True)
            raise typer.Exit(1)

    if not isinstance(sources_list, list):
        typer.echo("Error: JSON file must contain an array of source objects", err=True)
        raise typer.Exit(1)

    errored = 0
    succeeded = 0

    for idx, src in enumerate(sources_list):
        src_name = src.get("name", f"source-{idx}")
        src_url = src.get("url", "")
        src_type = src.get("type", "api")
        src_domain = src.get("domain", "")

        # Validate
        url_err = _validate_url(src_url)
        if url_err:
            typer.echo(f"  [{idx}] Error: {url_err} (name={src_name})", err=True)
            errored += 1
            continue

        type_err = _validate_type(src_type)
        if type_err:
            typer.echo(f"  [{idx}] Error: {type_err} (name={src_name})", err=True)
            errored += 1
            continue

        # Load config fresh per source to keep state consistent
        cfg_path, config = _load()
        domain_cfg = _find_domain(config, src_domain)
        if domain_cfg is None:
            typer.echo(
                f"  [{idx}] Error: Domain '{src_domain}' not configured (name={src_name})",
                err=True,
            )
            errored += 1
            continue

        # Idempotency check
        existing = any(
            s.url == src_url and s.type == src_type for s in domain_cfg.sources
        )
        if existing:
            typer.echo(f"  [{idx}] Skipped (already exists): {src_name}")
            continue

        quality_tier = 1 if src_type in ("api", "rss") else 2
        domain_cfg.sources.append(
            SourceConfig(name=src_name, type=src_type, url=src_url, quality_tier=quality_tier)
        )
        save_config(config, cfg_path)
        typer.echo(f"  [{idx}] Added: {src_name}")
        succeeded += 1

    typer.echo(f"\nBatch complete: {succeeded} added, {errored} errors")


@app.command(name="list")
def list_sources(
    domain: str = typer.Option(..., "--domain", help="Domain to list sources for"),
    json_output: bool = typer.Option(
        False, "--json", help="Output as JSON"
    ),
) -> None:
    """List sources for a domain."""
    _, config = _load()

    domain_cfg = _find_domain(config, domain)
    if domain_cfg is None:
        typer.echo(f"Error: Domain '{domain}' is not configured", err=True)
        raise typer.Exit(1)

    source_list = [
        {
            "source_id": f"{domain}:{s.name}",
            "name": s.name,
            "type": s.type,
            "url": s.url,
            "quality_tier": s.quality_tier,
        }
        for s in domain_cfg.sources
    ]

    if json_output:
        typer.echo(json.dumps({"domain": domain, "sources": source_list, "count": len(source_list)}, indent=2))
        return

    if not source_list:
        typer.echo(f"No sources configured for domain '{domain}'.")
        return

    typer.echo(f"Sources for domain '{domain}':")
    typer.echo(f"{'Source ID':<40} {'Type':<8} {'Quality':<8} URL")
    typer.echo("-" * 120)
    for s in source_list:
        typer.echo(f"{s['source_id']:<40} {s['type']:<8} {s['quality_tier']:<8} {s['url']}")


@app.command()
def remove(
    source_id: str = typer.Option(
        ..., "--source-id", help="Source identifier in 'domain:name' format"
    ),
) -> None:
    """Remove a source by its source_id (``domain:name``)."""
    parts = source_id.split(":", 1)
    if len(parts) != 2:
        typer.echo("Error: source_id must be in format 'domain:name'", err=True)
        raise typer.Exit(1)

    domain_name, source_name = parts
    cfg_path, config = _load()

    domain_cfg = _find_domain(config, domain_name)
    if domain_cfg is None:
        typer.echo(f"Error: Domain '{domain_name}' is not configured", err=True)
        raise typer.Exit(1)

    for i, existing in enumerate(domain_cfg.sources):
        if existing.name == source_name:
            domain_cfg.sources.pop(i)
            save_config(config, cfg_path)
            typer.echo(f"Source '{source_name}' removed from domain '{domain_name}'.")
            return

    typer.echo(f"Error: Source '{source_name}' not found in domain '{domain_name}'", err=True)
    raise typer.Exit(1)


@app.command()
def health(
    source_id: str = typer.Option(
        ..., "--source-id", help="Source identifier in 'domain:name' format"
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Output as JSON"
    ),
) -> None:
    """Check health status of a single source."""
    try:
        from autoinfo.status import get_source_health

        result = get_source_health(source_id=source_id)
        if json_output:
            typer.echo(json.dumps(result, indent=2, ensure_ascii=False))
            return

        status_val = result.get("status", "unknown")
        typer.echo(f"Source:       {source_id}")
        typer.echo(f"Status:       {status_val}")
        typer.echo(f"Total runs:   {result.get('total_runs', 0)}")
        last_run = result.get("last_run", "")
        if last_run:
            typer.echo(f"Last run:     {last_run}")
        error_msg = result.get("error", "")
        if error_msg:
            typer.echo(f"Error:        {error_msg}", err=True)
        latency = result.get("latency_ms")
        if latency is not None:
            typer.echo(f"Latency:      {latency:.0f} ms")
    except Exception as exc:
        typer.echo(f"Error checking source health: {exc}", err=True)
        raise typer.Exit(1) from exc


@app.command()
def test(
    url: str = typer.Option(..., "--url", help="Source URL to test"),
    type: str = typer.Option("api", "--type", help="Source type (rss, api, web)"),
) -> None:
    """Test a source connection without adding it."""
    # Validate
    url_error = _validate_url(url)
    if url_error:
        typer.echo(f"Error: {url_error}", err=True)
        raise typer.Exit(1)

    type_error = _validate_type(type)
    if type_error:
        typer.echo(f"Error: {type_error}", err=True)
        raise typer.Exit(1)

    try:
        if type == "api":
            resp = httpx.get(url, timeout=10.0, follow_redirects=True)
        else:
            resp = httpx.head(url, timeout=10.0, follow_redirects=True)
            if resp.status_code >= 400:
                resp = httpx.get(url, timeout=10.0, follow_redirects=True)

        content_type_header = resp.headers.get("content-type", "").split(";")[0].strip()
        content_preview = resp.text[:500] if resp.text else ""
        size_kb = len(resp.content) / 1024.0

        typer.echo(f"URL:           {url}")
        typer.echo(f"Status:        {resp.status_code}")
        typer.echo(f"Content-Type:  {content_type_header}")
        typer.echo(f"Size:          {size_kb:.1f} KB")
        typer.echo(f"Format:        {_infer_format(content_type_header, content_preview)}")
        typer.echo(f"Reachable:     {'yes' if resp.status_code < 500 else 'no'}")
    except httpx.TimeoutException:
        typer.echo(f"Error: Request to '{url}' timed out", err=True)
        raise typer.Exit(1)
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
