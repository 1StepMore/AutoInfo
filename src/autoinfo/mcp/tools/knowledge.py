"""MCP tool schemas — Knowledge base + graph + draft tools (24 tools).

Phase 1 of #581: schemas extracted from ``mcp/server.py::_full_tool_list``
verbatim.  ``build_tools()`` returns FRESH ``Tool`` objects on every call,
so ``_decorate_tools`` mutation never leaks across calls.
"""

from __future__ import annotations

from mcp.types import Tool

from autoinfo.config import DEFAULT_TTL_DAYS


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
