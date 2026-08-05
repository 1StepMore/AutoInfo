"""Import content into the KB CLI — mirror of the MCP ``import_kb`` tool.

Usage::

    autoinfo import-kb --format markdown --file entry.md --domain medical-research
    autoinfo import-kb --format json --file entries.json --domain ai-commercial --json
    autoinfo import-kb --format markdown --data '<yaml-frontmatter>...' --domain tech-ai-developer

All entry imports land in 01-Raw (the sole entry point of the KB pipeline).
Parameter names mirror the MCP tool (``domain`` / ``format`` / ``data``);
``--file`` reads the raw content from disk and passes it through as ``data``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

app = typer.Typer(
    name="import-kb",
    help="Import entries into the KB (01-Raw) — mirrors MCP import_kb",
)


def _fail(message: str) -> None:
    """Print an error and exit non-zero (mirrors MCP error envelopes)."""
    typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(code=1)


@app.callback(invoke_without_command=True)
def import_kb(  # noqa: A001 — mirrors the MCP tool name
    domain: str = typer.Option(
        ..., "--domain", help="Target domain name (e.g. medical-research)"
    ),
    format: str = typer.Option(  # noqa: A002 — mirrors the MCP tool param name
        ...,
        "--format",
        help="Import format: markdown (YAML+Markdown), json, csv, opml",
    ),
    file: list[Path] = typer.Option(
        [],
        "--file",
        help="File(s) to import (repeatable). Content is read and passed as the "
        "'data' parameter of the MCP import_kb tool.",
    ),
    data: str | None = typer.Option(
        None,
        "--data",
        help="Raw content string to import (alternative to --file; mirrors the "
        "MCP import_kb 'data' parameter)",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Import entries or source suggestions into the KB (01-Raw).

    Mirrors the MCP ``import_kb`` tool: supports 4 formats (markdown, json,
    csv, opml). Entry imports land in 01-Raw; opml returns source suggestions
    only and does NOT auto-add sources.
    """
    # Deferred import — mirrors the MCP handler (avoids circular imports)
    from autoinfo.importer import import_kb as _import_kb

    if file and data is not None:
        _fail("Use either --file or --data, not both.")

    if not file and data is None:
        _fail("Provide content to import via --file or --data.")

    # Build the payload list: (label, raw content) pairs, one per import call.
    payloads: list[tuple[str, str]] = []
    if data is not None:
        payloads.append(("<data>", data))
    for path in file:
        if not path.is_file():
            _fail(f"File not found: {path}")
        try:
            payloads.append((str(path), path.read_text(encoding="utf-8")))
        except OSError as exc:
            _fail(f"Cannot read file {path}: {exc}")

    results: list[dict[str, Any]] = []
    for label, raw in payloads:
        try:
            result = _import_kb(domain=domain, format=format, data=raw)
        except ValueError as exc:
            # Mirrors the MCP handler's ValueError → VALIDATION_ERROR mapping
            result = {
                "source": label,
                "error": str(exc),
                "entries_imported": 0,
                "entries_failed": 0,
                "errors": [str(exc)],
            }
        except Exception as exc:  # noqa: BLE001 — CLI boundary, never crash
            result = {
                "source": label,
                "error": str(exc),
                "entries_imported": 0,
                "entries_failed": 0,
                "errors": [str(exc)],
            }
        result["source"] = label
        result["domain"] = domain
        result["format"] = format
        results.append(result)

    total_imported = sum(int(r.get("entries_imported", 0)) for r in results)
    total_failed = sum(int(r.get("entries_failed", 0)) for r in results)

    if json_output:
        typer.echo(
            json.dumps(
                {
                    "domain": domain,
                    "format": format,
                    "imports": results,
                    "total_imported": total_imported,
                    "total_failed": total_failed,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        for result in results:
            imported = result.get("entries_imported", 0)
            failed = result.get("entries_failed", 0)
            errors = result.get("errors") or []
            entry_id = result.get("entry_id")
            line = (
                f"{result['source']}: {imported} imported, {failed} failed"
                + (f" (entry_id={entry_id})" if entry_id else "")
            )
            typer.echo(line)
            for error in errors:
                typer.echo(f"  error: {error}")
        typer.echo(f"Total: {total_imported} imported, {total_failed} failed")

    # Mirrors the MCP behavior: a fully-failed import is still a valid response,
    # but the CLI surfaces it with a non-zero exit for script consumers.
    if total_failed > 0:
        raise typer.Exit(code=1)
