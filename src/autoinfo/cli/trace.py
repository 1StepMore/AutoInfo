"""Trace CLI — query the full pipeline history for a trace_id.

Usage::

    autoinfo trace <trace_id>
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
import yaml

app = typer.Typer(help="Query pipeline history for a trace_id")


@app.callback(invoke_without_command=True)
def trace(
    trace_id: str = typer.Argument(..., help="UUID trace_id assigned at collection time"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Return the full pipeline history for a given trace_id.

    Searches pipeline logs (``logs/pipeline-*.log``) and KB frontmatter
    for all events associated with the trace_id.
    """
    # -- Search pipeline logs ---------------------------------------------
    log_dir = Path("logs")
    pipeline_events: list[dict] = []

    if log_dir.is_dir():
        for log_file in sorted(log_dir.glob("pipeline-*.log"), reverse=True):
            try:
                lines = log_file.read_text(encoding="utf-8").splitlines()
            except Exception:
                continue
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                if entry.get("trace_id") == trace_id or (
                    isinstance(entry.get("extra"), dict)
                    and entry["extra"].get("trace_ids")
                    and trace_id in entry["extra"]["trace_ids"]
                ):
                    pipeline_events.append(entry)
            if pipeline_events:
                break

    # -- Search KB frontmatter for the entry ------------------------------
    kb_entries: list[dict] = []
    knowledge_dir = Path("knowledge")
    if knowledge_dir.is_dir():
        for md_file in knowledge_dir.rglob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8")
            except Exception:
                continue
            if not content.startswith("---"):
                continue
            parts = content.split("---", 2)
            if len(parts) < 3:
                continue
            try:
                fm = yaml.safe_load(parts[1])
            except Exception:
                continue
            if isinstance(fm, dict) and fm.get("trace_id") == trace_id:
                kb_entries.append({
                    "entry_id": fm.get("entry_id", ""),
                    "title": fm.get("title", ""),
                    "domain": fm.get("domain", ""),
                    "tier": fm.get("tier", ""),
                    "file_path": str(md_file),
                    "collected_at": fm.get("collected_at", ""),
                    "language": fm.get("language", ""),
                    "dedup_status": fm.get("dedup_status", ""),
                })

    # -- Output -----------------------------------------------------------
    if json_output:
        typer.echo(json.dumps({
            "trace_id": trace_id,
            "pipeline_events": pipeline_events,
            "kb_entries": kb_entries,
            "event_count": len(pipeline_events),
            "kb_entry_count": len(kb_entries),
        }, ensure_ascii=False, indent=2))
        return

    # Human-readable output
    typer.echo(f"Trace: {trace_id}")
    typer.echo("")

    if pipeline_events:
        typer.echo(f"Pipeline Events ({len(pipeline_events)}):")
        typer.echo("\u2500" * 60)
        for evt in pipeline_events:
            ts = evt.get("timestamp", "")[:19]
            level = evt.get("level", "")
            module = evt.get("module", "")
            msg = evt.get("message", "")
            item_id = evt.get("item_id", "")
            extra = evt.get("extra", {})
            extra_str = ""
            if isinstance(extra, dict):
                parts_str = []
                for k in ("source_name", "domain", "gate", "source"):
                    if k in extra:
                        parts_str.append(f"{k}={extra[k]}")
                if parts_str:
                    extra_str = f" ({', '.join(parts_str)})"
            typer.echo(f"  [{ts}] {level:7s} {module:8s} {msg}{extra_str}")
            if item_id:
                typer.echo(f"          item_id={item_id}")
        typer.echo("")
    else:
        typer.echo("No pipeline events found.")
        typer.echo("")

    if kb_entries:
        typer.echo(f"KB Entries ({len(kb_entries)}):")
        typer.echo("\u2500" * 60)
        for entry in kb_entries:
            typer.echo(f"  Entry ID: {entry['entry_id']}")
            typer.echo(f"  Title:    {entry['title']}")
            typer.echo(f"  Domain:   {entry['domain']}")
            typer.echo(f"  Tier:     {entry['tier']}")
            typer.echo(f"  File:     {entry['file_path']}")
            typer.echo("")
    else:
        typer.echo("No KB entries found for this trace_id.")
