from __future__ import annotations
"""Knowledge Base CLI — search, list, and manage KB entries.

Usage::

    autoinfo kb search --query "IVF" --domain medical --limit 10 --offset 0
    autoinfo kb list --domain medical --tier raw
    autoinfo kb reindex --domain medical
    autoinfo kb promote --entry-id kb-001
"""


import json
from pathlib import Path

import typer

from autoinfo.kb import KBStore

app = typer.Typer(help="Knowledge base operations")


@app.command()
def search(
    query: str = typer.Option(..., "--query", help="Search query"),
    domain: str = typer.Option("", "--domain", help="Domain to search in"),
    limit: int = typer.Option(20, "--limit", help="Max results"),
    offset: int = typer.Option(0, "--offset", help="Result offset"),
) -> None:
    """Search the knowledge base using FTS5 full-text search."""
    store = KBStore()
    result = store.search_knowledge_base(
        query=query, domain=domain, limit=limit, offset=offset
    )
    typer.echo(json.dumps(result, indent=2, ensure_ascii=False))


@app.command()
def list(
    domain: str = typer.Option(..., "--domain", help="Domain to list entries for"),
    tier: str = typer.Option(
        "01-Raw", "--tier", help="KB tier (01-Raw, 02-Draft, 03-Wiki)"
    ),
    limit: int = typer.Option(20, "--limit", help="Max entries"),
    offset: int = typer.Option(0, "--offset", help="Pagination offset"),
) -> None:
    """List KB entries by domain and tier."""
    store = KBStore()
    entries = store.list_kb_tier(
        domain=domain, tier=tier, limit=limit, offset=offset
    )
    typer.echo(json.dumps(entries, indent=2, ensure_ascii=False))


@app.command()
def reindex(
    domain: str = typer.Option(
        "", "--domain", help="Domain to reindex (empty = all)"
    ),
) -> None:
    """Rebuild the FTS5 search index from knowledge/ files."""
    store = KBStore()
    result = store.reindex_knowledge_base(domain=domain or None)
    typer.echo(json.dumps(result, indent=2, ensure_ascii=False))


@app.command(name="create-draft")
def create_draft(
    raw_ids = typer.Option(
        ..., "--raw-id", help="Raw entry ID(s) to compile into a Draft (repeatable)"
    ),
    title: str = typer.Option(..., "--title", help="Title for the new Draft entry"),
    summary: str = typer.Option("", "--summary", help="Optional summary text"),
    tags = typer.Option(
        [], "--tag", help="Optional tag (repeatable)"
    ),
) -> None:
    """Create a Draft entry from one or more Raw entries."""
    store = KBStore()
    try:
        entry = store.create_kb_draft(
            raw_ids=raw_ids, title=title, summary=summary, tags=tags
        )
        typer.echo(json.dumps(entry.to_dict(), indent=2, ensure_ascii=False))
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)


@app.command(name="reject-draft")
def reject_draft(
    draft_id: str = typer.Argument(..., help="Entry ID of the Draft to reject"),
    reason: str = typer.Option("", "--reason", help="Rejection reason"),
    action: str = typer.Option(
        "back_to_raw", "--action", help="'back_to_raw' (default) or 'archive'"
    ),
) -> None:
    """Reject a Draft, moving it back to 01-Raw or archiving."""
    store = KBStore()
    try:
        result = store.reject_kb_draft(
            draft_id=draft_id, reason=reason, action=action
        )
        typer.echo(json.dumps(result, indent=2, ensure_ascii=False))
    except (ValueError, FileNotFoundError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)


@app.command(name="list-tiers")
def list_tiers(
    domain: str = typer.Option(
        ..., "--domain", help="Domain to list tiers for"
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Output as JSON"
    ),
) -> None:
    """List available KB tiers with entry counts for a domain."""
    store = KBStore()
    tiers = ["01-Raw", "02-Draft", "03-Wiki"]
    tier_info = []
    for tier in tiers:
        entries = store.list_kb_tier(
            domain=domain, tier=tier, limit=0, offset=0
        )
        tier_info.append({
            "tier": tier,
            "description": {
                "01-Raw": "Sole entry point for collected content",
                "02-Draft": "Agent-created drafts from Raw entries",
                "03-Wiki": "Human-promoted, reviewed entries (append-only)",
            }.get(tier, ""),
            "entry_count": len(entries),
        })

    if json_output:
        typer.echo(json.dumps(tier_info, indent=2, ensure_ascii=False))
        return

    typer.echo(f"KB tiers for domain '{domain}':")
    typer.echo("")
    for t in tier_info:
        desc = t["description"]
        typer.echo(
            f"  {t['tier']:<12} ({t['entry_count']:>4} entries)  {desc}"
        )


@app.command()
def promote(
    entry_id: str = typer.Option(
        ..., "--entry-id", help="Entry ID of the Draft to promote to 03-Wiki"
    ),
) -> None:
    """Promote a Draft entry to 03-Wiki (human-only, append-only)."""
    store = KBStore()
    try:
        result = store.promote_kb_draft(draft_id=entry_id)
        typer.echo(json.dumps(result, indent=2, ensure_ascii=False))
    except (ValueError, FileNotFoundError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
