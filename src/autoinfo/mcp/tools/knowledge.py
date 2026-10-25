"""MCP tool schemas — Knowledge base + graph + draft tools (24 tools).

Phase 1 of #581: schemas extracted from ``mcp/server.py::_full_tool_list``
verbatim.  ``build_tools()`` returns FRESH ``Tool`` objects on every call,
so ``_decorate_tools`` mutation never leaks across calls.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from mcp.types import Tool

from autoinfo.config import DEFAULT_TTL_DAYS
from autoinfo.kb import DirectorOnlyError
from autoinfo.mcp import context as mcp_context
from autoinfo.mcp.errors import ErrorCode, error_response, success_response


def build_tools() -> list[Tool]:
    """Return the 24 schemas for this module, in registration order."""
    return [
        # -- Knowledge Base (4) ----------------------------------------------
        Tool(
            name="list_summaries",
            description="Browse KB entries for a domain, newest first. Returns summary cards (title, summary, tier, source) with pagination. Use to scan what the KB currently holds before choosing entries to flag, promote, or synthesize into a digest.",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                    "date_from": {
                        "type": "string",
                        "description": ("ISO date filter — only entries from this date onward"),
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max entries to return",
                        "default": 20,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Pagination offset",
                        "default": 0,
                    },
                },
                "required": ["domain"],
            },
        ),
        Tool(
            name="get_kb_entry",
            description="Fetch a single KB entry by its entry ID. Returns the full tier metadata, content, source provenance, quality scores and custom fields. Use to inspect one item before promoting it or to retrieve the raw payload for downstream processing.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entry_id": {
                        "type": "string",
                        "description": "Unique entry identifier",
                    },
                    "user_id": {
                        "type": "string",
                        "description": "Optional user_id filter (accepted for multi-user compatibility; direct ID lookup is user-independent)",
                    },
                },
                "required": ["entry_id"],
            },
        ),
        Tool(
            name="search_knowledge_base",
            description=(
                "Search the knowledge base using FTS5 full-text, vector, "
                "or hybrid (FTS5 + vector) search. "
                "Supports simple term queries with optional domain and "
                "faceted filters (tags, date range, quality tier, "
                "content type, language)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                    },
                    "domain": {
                        "type": "string",
                        "description": "Optional domain filter. When omitted or None, searches across all domains.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results",
                        "default": 20,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Pagination offset",
                        "default": 0,
                    },
                    "mode": {
                        "type": "string",
                        "description": "Search mode: 'fts5' (default, full-text only), 'hybrid' (FTS5 + vector fusion), or 'vector' (vector-only). Falls back to FTS5 when vector search is unavailable.",
                        "default": "fts5",
                        "enum": ["fts5", "hybrid", "vector"],
                    },
                    "filter_tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Only include entries whose tags contain ANY of the given values",
                    },
                    "filter_date_from": {
                        "type": "string",
                        "description": "Only entries with collected_at >= this ISO date (e.g. 2025-01-01)",
                    },
                    "filter_date_to": {
                        "type": "string",
                        "description": "Only entries with collected_at <= this ISO date (e.g. 2025-06-30)",
                    },
                    "filter_quality_tier_min": {
                        "type": "integer",
                        "description": "Only entries with quality_tier >= this value",
                    },
                    "filter_quality_tier_max": {
                        "type": "integer",
                        "description": "Only entries with quality_tier <= this value",
                    },
                    "filter_content_type": {
                        "type": "string",
                        "description": "Only entries with this exact content_type",
                    },
                    "filter_language": {
                        "type": "string",
                        "description": "Only entries with this exact language",
                    },
                    "user_id": {
                        "type": "string",
                        "description": "Optional user_id filter — only entries belonging to this user",
                    },
                    "filter_custom_fields": {
                        "type": "object",
                        "additionalProperties": {"type": "string"},
                        "description": "Faceted filter over the custom_fields JSON column (product-analysis metadata). Each key is a dot-path into custom_fields (e.g. 'product_analysis.action_required'); an empty-string value matches entries where the field exists and is non-empty, any other value matches entries where the field's JSON value equals that text.",
                    },
                    "include_stale": {
                        "type": "boolean",
                        "description": "If false (default), stale entries are demoted to the bottom of search results. If true, stale entries are mixed normally with fresh results.",
                        "default": False,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="query_knowledge_graph",
            description=(
                "Query the knowledge graph for entities related to a given "
                "entity.  Returns related entities with relation type and "
                "co-occurrence strength."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {
                        "type": "string",
                        "description": "Entity name to query (case-insensitive partial match)",
                    },
                    "relation": {
                        "type": "string",
                        "description": (
                            "Entity-graph relation type to filter by. Empty "
                            "string matches all relation types."
                        ),
                        "default": "related_to",
                        "enum": [
                            "",
                            "child_of",
                            "duplicate_of",
                            "parent_of",
                            "referenced_by",
                            "references",
                            "related",
                            "related_to",
                            "similar_to",
                            "superseded_by",
                            "supersedes",
                            "version_of",
                        ],
                    },
                    "domain": {
                        "type": "string",
                        "description": "Optional domain scope filter",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results",
                        "default": 20,
                    },
                },
                "required": ["entity"],
            },
        ),
        # -- Knowledge Graph Export (2) --------------------------------------
        Tool(
            name="knowledge_graph_export",
            description=(
                "Export the knowledge graph for a domain. "
                "Supports json, graphml, and csv formats. "
                "Returns entity and relation counts."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                    "format": {
                        "type": "string",
                        "description": "Export format: json, graphml, csv",
                        "default": "json",
                        "enum": ["json", "graphml", "csv"],
                    },
                    "output": {
                        "type": "string",
                        "description": "Optional output file path (auto-generated if omitted)",
                        "default": "",
                    },
                },
                "required": ["domain"],
            },
        ),
        Tool(
            name="flag_for_knowledge_base",
            description=(
                "Flag a summary entry for KB inclusion — tags it in the "
                "SQLite index with importance rating.  Does NOT create a "
                "Draft; call create_kb_draft separately."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "summary_id": {
                        "type": "string",
                        "description": "Summary entry ID",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tags to apply (merged with existing, no duplicates)",
                    },
                    "importance": {
                        "type": "integer",
                        "description": "Importance rating 1-5",
                        "default": 3,
                    },
                },
                "required": ["summary_id"],
            },
        ),
        # -- KB: get_summary (1) ---------------------------------------------
        Tool(
            name="get_summary",
            description=(
                "Return full detail for a summary entry including key "
                "points parsed from the body, quality scores, tags, "
                "importance, and source provenance."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "summary_id": {
                        "type": "string",
                        "description": "Summary entry ID",
                    },
                },
                "required": ["summary_id"],
            },
        ),
        # -- KB: Relations (2) -----------------------------------------------
        Tool(
            name="link_items",
            description=(
                "Create a link between two KB entries. Idempotent — "
                "calling with the same (item_a, item_b, relation_type) "
                "returns the existing relation."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "item_a_id": {
                        "type": "string",
                        "description": "First entry ID",
                    },
                    "item_b_id": {
                        "type": "string",
                        "description": "Second entry ID",
                    },
                    "relation_type": {
                        "type": "string",
                        "description": "Relation type (e.g. related, references)",
                        "default": "related",
                        "enum": ["related", "references"],
                    },
                    "metadata": {
                        "type": "object",
                        "description": "Optional metadata dict (e.g. matched_tags)",
                    },
                },
                "required": ["item_a_id", "item_b_id"],
            },
        ),
        Tool(
            name="get_item_relations",
            description=(
                "Return all relations where an item participates. "
                "Optionally filtered by relation_type."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "item_id": {
                        "type": "string",
                        "description": "Entry ID to query",
                    },
                    "relation_type": {
                        "type": "string",
                        "description": "Optional relation type filter",
                        "enum": ["related", "references"],
                    },
                },
                "required": ["item_id"],
            },
        ),
        # -- KB: Versioning (3) ----------------------------------------------
        Tool(
            name="get_entry_history",
            description=(
                "Return all saved backup versions for an entry, "
                "newest first. Up to 5 versions are retained."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "entry_id": {
                        "type": "string",
                        "description": "Entry ID to query",
                    },
                },
                "required": ["entry_id"],
            },
        ),
        Tool(
            name="restore_entry_version",
            description=(
                "Restore an entry from a saved version backup. "
                "Copies the .bak file back over the original."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "version_id": {
                        "type": "string",
                        "description": "Version ID to restore",
                    },
                },
                "required": ["version_id"],
            },
        ),
        Tool(
            name="compare_versions",
            description=(
                "Compare two versions of a KB entry and return a "
                "structured diff showing which fields changed, their "
                "old and new values, and a summary of changes."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "entry_id": {
                        "type": "string",
                        "description": "KB entry ID whose versions to compare",
                    },
                    "version_a": {
                        "type": "string",
                        "description": (
                            "First version identifier (version_id like "
                            "'entry_abc--v1' or version number string like '1')"
                        ),
                    },
                    "version_b": {
                        "type": "string",
                        "description": (
                            "Second version identifier (version_id like "
                            "'entry_abc--v2' or version number string like '2')"
                        ),
                    },
                },
                "required": ["entry_id", "version_a", "version_b"],
            },
        ),
        # -- KB: Monitor (3) -------------------------------------------------
        Tool(
            name="get_collection_stats",
            description=(
                "Aggregated collection statistics across all domains "
                "for daily, weekly, or monthly periods."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "description": "Period: daily (default), weekly, monthly",
                        "default": "daily",
                        "enum": ["daily", "weekly", "monthly"],
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="get_collection_diff",
            description=(
                "Return entries collected since a previous collection ID, "
                "showing new entries grouped by domain."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "since_collection_id": {
                        "type": "string",
                        "description": "Collection ID (timestamp) to compare against",
                    },
                },
                "required": ["since_collection_id"],
            },
        ),
        Tool(
            name="get_domain_decay",
            description=(
                "Compute decay / staleness metrics for a domain. "
                "Returns staleness ratio, average TTL remaining, "
                "decay grade (GREEN/YELLOW/RED), and re-collection suggestions."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name to compute decay metrics for",
                    },
                    "ttl_days": {
                        "type": "integer",
                        "description": (
                            "Days before an entry is considered fully stale "
                            f"(default: {DEFAULT_TTL_DAYS})"
                        ),
                        "default": DEFAULT_TTL_DAYS,
                    },
                },
                "required": ["domain"],
            },
        ),
        # -- KB: Draft tools (9) ---------------------------------------------
        Tool(
            name="create_kb_draft",
            description=(
                "Create a Draft entry from one or more Raw entries. "
                "Validates all raw_ids exist in 01-Raw, merges content, "
                "and creates a file in 02-Draft/."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "raw_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "One or more 01-Raw entry IDs to compile into a Draft",
                    },
                    "title": {
                        "type": "string",
                        "description": "Title for the new Draft entry",
                    },
                    "summary": {
                        "type": "string",
                        "description": "Optional summary text",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional tags for the Draft entry",
                    },
                },
                "required": ["raw_ids", "title"],
            },
        ),
        Tool(
            name="reject_kb_draft",
            description=(
                "Reject a Draft entry, moving it back to 01-Raw or "
                "archiving it.  Adds rejection_reason to frontmatter."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "draft_id": {
                        "type": "string",
                        "description": "Entry ID of the Draft to reject",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Optional rejection reason",
                    },
                    "action": {
                        "type": "string",
                        "description": (
                            "'back_to_raw' (default) moves to 01-Raw; 'archive' moves to _archive/"
                        ),
                        "default": "back_to_raw",
                        "enum": ["back_to_raw", "archive"],
                    },
                },
                "required": ["draft_id"],
            },
        ),
        Tool(
            name="list_kb_tier",
            description=(
                "List all entries in a specific KB tier (01-Raw, 02-Draft, 03-Wiki) for a domain."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                    "tier": {
                        "type": "string",
                        "description": "Tier to list (01-Raw, 02-Draft, 03-Wiki)",
                        "enum": ["01-Raw", "02-Draft", "03-Wiki"],
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max entries to return",
                        "default": 50,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Pagination offset",
                        "default": 0,
                    },
                    "user_id": {
                        "type": "string",
                        "description": "Optional user_id filter — only entries belonging to this user",
                    },
                },
                "required": ["domain", "tier"],
            },
        ),
        Tool(
            name="promote_kb_draft",
            description=(
                "Promote a Draft KB entry (02-Draft) to the 03-Wiki tier. "
                "Admission-gated agent promotion: the draft must satisfy "
                "the curation gate (source provenance, G1/G3 thresholds, "
                "G4 factual consistency) or the promotion is rejected and "
                "a _failed/ marker is written while the draft stays in "
                "02-Draft. Once promoted, entries are append-only and "
                "cannot be demoted. The entry must already exist in 02-Draft."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "entry_id": {
                        "type": "string",
                        "description": "ID of the Draft KB entry to promote (e.g. medical-research-draft-some-title)",
                    },
                    "user_id": {
                        "type": "string",
                        "description": "Optional user ID for audit trail",
                        "default": "",
                    },
                },
                "required": ["entry_id"],
            },
        ),
        Tool(
            name="demote_kb_wiki",
            description=(
                "Demote a 03-Wiki entry back to 02-Draft (director-only backdoor). "
                "Content is preserved: the file moves to 02-Draft with a "
                "demoted_at marker; the original promotion provenance is kept. "
                "The actor must be whitelisted in AUTOINFO_DIRECTOR_ACTORS "
                "(default 'director') or the call is refused with DIRECTOR_ONLY."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "entry_id": {
                        "type": "string",
                        "description": "ID of the 03-Wiki entry to demote",
                    },
                    "actor": {
                        "type": "string",
                        "description": "Required. Acting director (must be whitelisted in AUTOINFO_DIRECTOR_ACTORS)",
                    },
                },
                "required": ["entry_id", "actor"],
            },
        ),
        Tool(
            name="force_promote",
            description=(
                "Force-promote a 02-Draft entry to 03-Wiki, skipping the "
                "admission gate (director-only backdoor). Records "
                "promotion_source: director. The actor must be whitelisted "
                "in AUTOINFO_DIRECTOR_ACTORS (default 'director') or the "
                "call is refused with DIRECTOR_ONLY."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "draft_id": {
                        "type": "string",
                        "description": "ID of the 02-Draft entry to force-promote",
                    },
                    "actor": {
                        "type": "string",
                        "description": "Required. Acting director (must be whitelisted in AUTOINFO_DIRECTOR_ACTORS)",
                    },
                },
                "required": ["draft_id", "actor"],
            },
        ),
        Tool(
            name="promote_pending",
            description=(
                "Batch-promote all eligible 02-Draft entries for a domain "
                "(promotion sweep). Each draft is admission-checked via the "
                "curation gate (source provenance, G1/G3 thresholds, G4 "
                "factual consistency); drafts previously rejected (carrying "
                "a _failed/ marker) are skipped and never retried. "
                "Idempotent: already-promoted entries are naturally skipped. "
                "Returns a summary with promoted/rejected/failed per entry "
                "and per-entry failure reasons."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                    "actor": {
                        "type": "string",
                        "description": "Acting agent recorded in promoted_by (default 'agent')",
                        "default": "agent",
                    },
                },
                "required": ["domain"],
            },
        ),
        Tool(
            name="reindex_kb",
            description="Rebuild SQLite FTS5 search index from disk frontmatter. Re-reads every KB markdown file and refreshes the full-text index and vector embeddings. Use after manual file edits or when search results look stale versus the files on disk.",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain to reindex (empty = all domains)",
                    },
                },
                "required": ["domain"],
            },
        ),
        Tool(
            name="create_kb_entry",
            description=(
                "Create a KB entry from scratch in 01-Raw tier. "
                "Architecture: 01-Raw is the sole entry point — "
                "all content enters the KB pipeline here. "
                "No quality gates are applied (matching REST behavior)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Target domain name (e.g. medical-research)",
                    },
                    "title": {
                        "type": "string",
                        "description": "Entry title",
                    },
                    "content": {
                        "type": "string",
                        "description": "Full text / Markdown content of the entry",
                    },
                    "source_url": {
                        "type": "string",
                        "description": "Source URL (mandatory provenance)",
                    },
                    "source_type": {
                        "type": "string",
                        "description": "Source type (e.g. web, api, manual)",
                    },
                    "topics": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of topic tags",
                    },
                    "author": {
                        "type": "string",
                        "description": "Optional author name",
                    },
                },
                "required": [
                    "domain",
                    "title",
                    "content",
                    "source_url",
                    "source_type",
                ],
            },
        ),
    ]


def _handle_list_summaries(**kwargs: Any) -> dict[str, Any]:
    """List KB entries for a domain via ``KBStore.list_entries``.

    Expects ``domain`` in ``**kwargs`` (popped before passing the rest).
    """
    from autoinfo.kb import KBStore

    domain = kwargs.pop("domain")

    kb_status = mcp_context._detect_kb_status()
    if kb_status == "uninitialized":
        return error_response(
            ErrorCode.EMPTY_RESULT,
            "Knowledge base not initialized. Run collect_sources() + process_collection() first.",
        )
    if kb_status == "empty":
        return {
            "domain": domain,
            "entries": [],
            "count": 0,
            "message": "Knowledge base initialized but has no entries yet. Run collect_sources() + process_collection() to populate.",
        }

    store = KBStore()
    entries = store.list_entries(domain, **kwargs)
    return {"domain": domain, "entries": entries, "count": len(entries)}


def _handle_get_kb_entry(entry_id: str, user_id: str | None = None) -> dict[str, Any]:
    """Fetch a single KB entry by ID via ``KBStore.get_entry``.

    Parameters
    ----------
    entry_id:
        Unique entry identifier.
    user_id:
        Optional user_id filter (accepted for multi-user compatibility;
        direct ID lookup is user-independent).
    """
    from autoinfo.kb import KBStore

    store = KBStore()
    entry = store.get_entry(entry_id)
    if entry is None:
        return error_response(
            code=ErrorCode.NOT_FOUND,
            message=f"Entry '{entry_id}' not found",
            actionable=True,
        )
    return mcp_context._canonicalize(entry)


def _handle_search_knowledge_base(
    query: str,
    domain: str | None = None,
    limit: int = 20,
    offset: int = 0,
    mode: str = "fts5",
    filter_tags: list[str] | None = None,
    filter_date_from: str | None = None,
    filter_date_to: str | None = None,
    filter_quality_tier_min: int | None = None,
    filter_quality_tier_max: int | None = None,
    filter_content_type: str | None = None,
    filter_language: str | None = None,
    user_id: str | None = None,
    include_stale: bool = False,
    filter_custom_fields: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Search the knowledge base using FTS5 full-text search.

    Parameters
    ----------
    domain:
        Optional domain filter. When ``None`` (default), searches across
        all domains. When an empty string or a specific domain name is
        passed, results are filtered to that domain.
    mode:
        Search mode: ``"fts5"`` (default), ``"hybrid"`` (FTS5 + vector),
        or ``"vector"``.  Falls back to FTS5 when vector search is
        unavailable.
    include_stale:
        If False (default), stale entries are demoted to the bottom
        of search results.
    filter_custom_fields:
        Faceted filter over the ``custom_fields`` JSON column (todo 25,
        output-quality-mega — product-analysis metadata search).  Each
        key is a dot-path into ``custom_fields`` (e.g.
        ``"product_analysis.action_required"``); an empty-string value
        matches entries where the field exists and is non-empty, any
        other value matches entries where the field's JSON value equals
        that text.
    """
    from autoinfo.kb import KBStore

    kb_status = mcp_context._detect_kb_status()
    if kb_status == "uninitialized":
        return error_response(
            ErrorCode.EMPTY_RESULT,
            "Knowledge base not initialized. Run collect_sources() + process_collection() first.",
        )
    if kb_status == "empty":
        return {
            "entries": [],
            "count": 0,
            "message": "Knowledge base initialized but has no entries yet. Run collect_sources() + process_collection() to populate.",
        }

    store = KBStore()
    return mcp_context._canonicalize(
        store.search_knowledge_base(
            query=query,
            domain=domain or "",
            limit=limit,
            offset=offset,
            mode=mode,
            filter_tags=filter_tags,
            filter_date_from=filter_date_from,
            filter_date_to=filter_date_to,
            filter_quality_tier_min=filter_quality_tier_min,
            filter_quality_tier_max=filter_quality_tier_max,
            filter_content_type=filter_content_type,
            filter_language=filter_language,
            filter_user_id=user_id,
            include_stale=include_stale,
            filter_custom_fields=filter_custom_fields,
        )
    )


def _handle_query_knowledge_graph(
    entity: str,
    relation: str = "related_to",
    domain: str = "",
    limit: int = 20,
) -> dict[str, Any]:
    """Query the knowledge graph for entities related to *entity*."""
    from autoinfo.kb import KBStore

    store = KBStore()
    return mcp_context._canonicalize(
        store.query_knowledge_graph(
            entity=entity,
            relation=relation,
            domain=domain,
            limit=limit,
        )
    )


def _handle_knowledge_graph_export(
    domain: str,
    format: str = "json",
    output: str = "",
) -> dict[str, Any]:
    """Export the knowledge graph for a domain.

    Parameters
    ----------
    domain:
        Domain name (e.g. medical-research).
    format:
        Export format: ``"json"``, ``"graphml"``, or ``"csv"``.
    output:
        Optional output file path (auto-generated if omitted).

    Returns
    -------
    dict
        ``{domain, format, output_path, entity_count, relation_count}``.
    """
    valid_formats = {"json", "graphml", "csv"}
    if format not in valid_formats:
        return error_response(
            code=ErrorCode.VALIDATION_ERROR,
            message=f"Unsupported format '{format}'. Supported: {', '.join(sorted(valid_formats))}",
            actionable=True,
        )

    from autoinfo.kb import KBStore

    store = KBStore()

    try:
        data = store.export_knowledge_graph(domain=domain)
    except Exception as exc:
        mcp_context.logger.exception("Knowledge graph export failed for domain '%s'", domain)
        return mcp_context._error_from_exc(exc, "Knowledge graph export failed")

    out_path = Path(output) if output else Path(f"knowledge_graph_export.{format}")

    try:
        if format == "json":
            content = json.dumps(data, ensure_ascii=False, indent=2)
            out_path.write_text(content, encoding="utf-8")
        elif format == "graphml":
            from autoinfo.cli.knowledge import _build_graphml

            xml_content = _build_graphml(data)
            out_path.write_text(xml_content, encoding="utf-8")
        elif format == "csv":
            from autoinfo.cli.knowledge import _write_csv

            stem = str(out_path.with_suffix(""))
            _write_csv(data, stem)
    except OSError as exc:
        mcp_context.logger.exception("Error writing knowledge graph export file")
        return mcp_context._error_from_exc(exc, "Error writing knowledge graph export file")

    return {
        "domain": domain,
        "format": format,
        "output_path": str(out_path),
        "entity_count": len(data.get("entities", [])),
        "relation_count": len(data.get("relations", [])),
    }


def _handle_flag_for_knowledge_base(
    summary_id: str,
    tags: list[str] | None = None,
    importance: int = 3,
) -> dict[str, Any]:
    """Flag a summary for KB inclusion.

    Dispatches to ``KBStore.flag_for_knowledge_base``.
    """
    from autoinfo.kb import KBStore

    store = KBStore()
    return mcp_context._canonicalize(
        store.flag_for_knowledge_base(summary_id=summary_id, tags=tags, importance=importance)
    )


def _handle_get_summary(summary_id: str) -> dict[str, Any]:
    """Return full detail for a summary entry.

    Dispatches to ``KBStore.get_summary``.
    """
    from autoinfo.kb import KBStore

    store = KBStore()
    return mcp_context._canonicalize(store.get_summary(summary_id=summary_id))


def _handle_link_items(
    item_a_id: str,
    item_b_id: str,
    relation_type: str = "related",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a link between two KB entries."""
    from autoinfo.kb import KBStore

    store = KBStore()
    return mcp_context._canonicalize(
        store.link_items(
            item_a_id=item_a_id,
            item_b_id=item_b_id,
            relation_type=relation_type,
            metadata=metadata,
        )
    )


def _handle_get_item_relations(
    item_id: str,
    relation_type: str | None = None,
) -> dict[str, Any]:
    """Return all relations where an item participates."""
    from autoinfo.kb import KBStore

    store = KBStore()
    relations = store.get_item_relations(item_id=item_id, relation_type=relation_type)
    return {"item_id": item_id, "relations": relations, "count": len(relations)}


def _handle_get_entry_history(entry_id: str) -> dict[str, Any]:
    """Return all saved backup versions for an entry."""
    from autoinfo.kb import KBStore

    store = KBStore()
    versions = store.get_entry_history(entry_id=entry_id)
    return {"entry_id": entry_id, "versions": versions, "count": len(versions)}


def _handle_restore_entry_version(version_id: str) -> dict[str, Any]:
    """Restore an entry from a saved version backup."""
    from autoinfo.kb import KBStore

    store = KBStore()
    return mcp_context._canonicalize(store.restore_entry_version(version_id=version_id))


def _handle_compare_versions(entry_id: str, version_a: str, version_b: str) -> dict[str, Any]:
    """Compare two versions of a KB entry and return a structured diff."""
    from autoinfo.kb import KBStore

    store = KBStore()
    return mcp_context._canonicalize(
        store.compare_versions(entry_id=entry_id, version_a=version_a, version_b=version_b)
    )


def _handle_get_collection_stats(period: str = "daily") -> dict[str, Any]:
    """Aggregated collection statistics for the given period."""
    from autoinfo.kb import KBStore

    store = KBStore()
    return mcp_context._canonicalize(store.get_collection_stats(period=period))


def _handle_get_collection_diff(since_collection_id: str) -> dict[str, Any]:
    """Return entries collected since a previous collection ID."""
    from autoinfo.kb import KBStore

    store = KBStore()
    return mcp_context._canonicalize(
        store.get_collection_diff(since_collection_id=since_collection_id)
    )


def _handle_get_domain_decay(domain: str, ttl_days: int = DEFAULT_TTL_DAYS) -> dict[str, Any]:
    """Compute decay / staleness metrics for a domain."""
    from autoinfo.kb import KBStore

    store = KBStore()
    return mcp_context._canonicalize(store.get_domain_decay(domain=domain, ttl_days=ttl_days))


def _handle_create_kb_draft(
    raw_ids: list[str],
    title: str,
    summary: str = "",
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Create a Draft entry from one or more Raw entries."""
    from autoinfo.kb import MIN_KB_CONTENT_CHARS, KBStore

    # Enforce the same 50-char content floor at the Draft boundary: a
    # Draft compiled from below-min raw content is an empty shell (#279).
    store = KBStore(min_content_chars=MIN_KB_CONTENT_CHARS)
    try:
        entry = store.create_kb_draft(raw_ids=raw_ids, title=title, summary=summary, tags=tags)
        return mcp_context._canonicalize(entry.to_dict())
    except ValueError as exc:
        return mcp_context._error_from_exc(
            exc, "Failed to create the KB draft", code=ErrorCode.VALIDATION_ERROR
        )


def _handle_reject_kb_draft(
    draft_id: str,
    reason: str = "",
    action: str = "back_to_raw",
) -> dict[str, Any]:
    """Reject a Draft, moving it back to 01-Raw or archiving."""
    from autoinfo.kb import KBStore

    store = KBStore()
    try:
        return mcp_context._canonicalize(
            store.reject_kb_draft(draft_id=draft_id, reason=reason, action=action)
        )
    except (ValueError, FileNotFoundError) as exc:
        return mcp_context._error_from_exc(exc, "Failed to reject the KB draft")


def _handle_list_kb_tier(
    domain: str,
    tier: str,
    limit: int = 50,
    offset: int = 0,
    user_id: str | None = None,
) -> dict[str, Any]:
    """List entries in a specific KB tier.

    Parameters
    ----------
    user_id:
        Optional user_id filter — only entries belonging to this user
        are returned. When ``None``, no user filter is applied.
    """
    from autoinfo.kb import KBStore

    kb_status = mcp_context._detect_kb_status()
    if kb_status == "uninitialized":
        return error_response(
            ErrorCode.EMPTY_RESULT,
            "Knowledge base not initialized. Run collect_sources() + process_collection() first.",
        )
    if kb_status == "empty":
        return {
            "domain": domain,
            "tier": tier,
            "entries": [],
            "count": 0,
            "message": "Knowledge base initialized but has no entries yet. Run collect_sources() + process_collection() to populate.",
        }

    store = KBStore()
    entries = store.list_kb_tier(
        domain=domain, tier=tier, limit=limit, offset=offset, user_id=user_id
    )
    return {
        "domain": domain,
        "tier": tier,
        "entries": entries,
        "count": len(entries),
    }


def _handle_promote_kb_draft(
    entry_id: str,
    user_id: str = "",
) -> dict[str, Any]:
    """Promote a Draft KB entry to the 03-Wiki tier.

    Admission-gated agent promotion: the draft must pass the curation gate
    (source provenance, G0, G1/G3 thresholds, G4 factual consistency) or
    the promotion is rejected and a ``_failed/<domain>/<entry_id>.md``
    marker is written while the draft stays in 02-Draft. The draft must be
    in 02-Draft tier. Returns the promoted entry path and metadata.
    """
    from autoinfo.kb import KBStore

    try:
        store = KBStore()
        result = store.promote_kb_draft(draft_id=entry_id)
        return mcp_context._canonicalize(result)
    except FileNotFoundError as exc:
        return mcp_context._error_from_exc(
            exc, "Failed to promote the KB draft", code=ErrorCode.NOT_FOUND
        )
    except PermissionError as exc:
        return mcp_context._error_from_exc(
            exc, "Failed to promote the KB draft", code=ErrorCode.VALIDATION_ERROR
        )
    except Exception as exc:
        mcp_context.logger.exception("promote_kb_draft failed for '%s'", entry_id)
        return mcp_context._error_from_exc(exc, "promote_kb_draft failed")


def _handle_demote_kb_wiki(entry_id: str, actor: str = "agent") -> dict[str, Any]:
    """Demote a 03-Wiki entry back to 02-Draft (director-only backdoor).

    Content is preserved: the file moves from ``03-Wiki/`` to ``02-Draft/``
    under the same domain and topic, frontmatter ``tier`` is rewritten to
    ``02-Draft`` and a ``demoted_at`` timestamp is appended; the original
    promotion provenance is kept.  The actor must be whitelisted in
    ``AUTOINFO_DIRECTOR_ACTORS`` (default ``director``) or the call is
    refused with a ``DIRECTOR_ONLY`` error envelope.
    """
    from autoinfo.kb import KBStore

    store = KBStore()
    try:
        return mcp_context._canonicalize(store.demote_entry(entry_id=entry_id, caller=actor))
    except DirectorOnlyError as exc:
        return mcp_context._error_from_exc(
            exc, "demote_kb_wiki refused", code=ErrorCode.DIRECTOR_ONLY
        )


def _handle_force_promote(draft_id: str, actor: str = "agent") -> dict[str, Any]:
    """Force-promote a 02-Draft entry to 03-Wiki, skipping the admission gate.

    Director-only backdoor: provenance / G0 / G1 / G3 / G4 checks are not
    evaluated; the frontmatter records ``promotion_source: director``.  The
    actor must be whitelisted in ``AUTOINFO_DIRECTOR_ACTORS`` (default
    ``director``) or the call is refused with a ``DIRECTOR_ONLY`` error
    envelope.
    """
    from autoinfo.kb import KBStore

    store = KBStore()
    try:
        return mcp_context._canonicalize(
            store.force_promote_kb_draft(draft_id=draft_id, caller=actor)
        )
    except DirectorOnlyError as exc:
        return mcp_context._error_from_exc(
            exc, "force_promote refused", code=ErrorCode.DIRECTOR_ONLY
        )


def _handle_promote_pending(domain: str, actor: str = "agent") -> dict[str, Any]:
    """Promote all eligible 02-Draft entries for *domain* (batch sweep).

    Each 02-Draft entry is admission-checked via the existing promote path;
    entries previously rejected (carrying a ``_failed/<domain>/<entry_id>.md``
    marker) are skipped and never retried.  Returns a summary with
    promoted/rejected/failed per entry and per-entry failure reasons; the
    sweep never raises (per-entry failures are collected in the summary).
    """
    from autoinfo.kb import KBStore

    store = KBStore()
    config = None
    try:
        config = mcp_context._load_config()
    except Exception:
        config = None
    try:
        return mcp_context._canonicalize(
            store.promote_pending_drafts(domain=domain, config=config, caller=actor)
        )
    except Exception as exc:
        mcp_context.logger.exception("promote_pending failed for domain '%s'", domain)
        return mcp_context._error_from_exc(exc, "promote_pending failed")


def _handle_reindex_kb(domain: str) -> dict[str, Any]:
    """Rebuild SQLite index from disk frontmatter.

    Dispatches to ``KBStore.reindex_knowledge_base``.
    """
    from autoinfo.kb import KBStore

    store = KBStore()
    return mcp_context._canonicalize(store.reindex_knowledge_base(domain=domain))


def _handle_create_kb_entry(
    domain: str,
    title: str,
    content: str,
    source_url: str,
    source_type: str,
    topics: list[str] | None = None,
    author: str = "",
) -> dict[str, Any]:
    """Create a KB entry from scratch in the 01-Raw tier.

    Architecture rule: 01-Raw is the sole entry point for all
    collected and manually-created content.  This tool writes to
    01-Raw only — 02-Draft and 03-Wiki are reached through separate
    promotion steps.

    Parameters
    ----------
    domain:
        Target domain name (e.g. medical-research).
    title:
        Entry title.
    content:
        Full text / Markdown content of the entry.
    source_url:
        Source URL (mandatory provenance).
    source_type:
        Source type (e.g. web, api, manual).
    topics:
        Optional list of topic tags.
    author:
        Optional author name (stored in KBEntry frontmatter).

    Returns
    -------
    dict
        ``{entry_id, tier, source_url, created_at, title, domain}``
        wrapped in ``success_response()`` envelope.
    """
    from datetime import timezone
    from uuid import uuid4

    from autoinfo.kb import MIN_KB_CONTENT_CHARS, KBStore
    from autoinfo.models import Item

    try:
        if not domain or not title or not content or not source_url:
            return error_response(
                code=ErrorCode.VALIDATION_ERROR,
                message="domain, title, content, and source_url are required. Provide all four fields to create the KB entry.",
                actionable=True,
            )

        if len(content.strip()) < MIN_KB_CONTENT_CHARS:
            return error_response(
                ErrorCode.VALIDATION_ERROR,
                f"content must be at least {MIN_KB_CONTENT_CHARS} characters",
                actionable=True,
            )

        topic_tags = topics or []

        item = Item(
            id=str(uuid4()),
            source_name=source_type,
            source_type=source_type,
            source_url=source_url,
            source_platform=source_type,
            title=title,
            content=content,
            domain=domain,
            topic_tags=topic_tags,
            collected_at=datetime.now(timezone.utc).isoformat(),
            content_type="text",
            quality_tier=1,
        )

        store = KBStore(min_content_chars=MIN_KB_CONTENT_CHARS)
        entry = store.store_entry(item=item, tier="01-Raw")

        if entry is None:
            # Issue #182: rejected (content too short) — clean error response
            return error_response(
                code=ErrorCode.VALIDATION_ERROR,
                message="entry rejected by KB store (content too short or unparseable)",
                actionable=True,
            )

        return success_response(
            {
                "entry_id": entry.entry_id,
                "tier": entry.tier,
                "source_url": entry.source_url,
                "created_at": entry.collected_at,
                "title": entry.title,
                "domain": entry.domain,
            }
        )
    except ValueError as exc:
        return mcp_context._error_from_exc(
            exc,
            "Failed to create the KB entry",
            code=ErrorCode.VALIDATION_ERROR,
        )
    except Exception as exc:
        mcp_context.logger.exception("create_kb_entry failed")
        return mcp_context._error_from_exc(exc, "create_kb_entry failed")
