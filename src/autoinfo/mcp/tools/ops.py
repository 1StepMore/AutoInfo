"""MCP tool schemas — Audit, CEFR, project/batch config (10 tools).

Phase 1 of #581: schemas extracted from ``mcp/server.py::_full_tool_list``
verbatim.  ``build_tools()`` returns FRESH ``Tool`` objects on every call,
so ``_decorate_tools`` mutation never leaks across calls.
"""

from __future__ import annotations

from mcp.types import Tool


def build_tools() -> list[Tool]:
    """Return the 10 schemas for this module, in registration order."""
    return [
        # -- Audit (1) -------------------------------------------------------
        Tool(
            name="query_audit_log",
            description=(
                "Query the immutable audit log with optional filters. "
                "All filters are optional and combined with AND logic. "
                "Results returned newest-first."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "actor": {
                        "type": "string",
                        "description": "Filter by actor name",
                    },
                    "action": {
                        "type": "string",
                        "description": "Filter by action name",
                    },
                    "resource_type": {
                        "type": "string",
                        "description": "Filter by resource type",
                    },
                    "date_from": {
                        "type": "string",
                        "description": "ISO-8601 lower bound on timestamp",
                    },
                    "date_to": {
                        "type": "string",
                        "description": "ISO-8601 upper bound on timestamp",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max entries to return (default 100)",
                        "default": 100,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Pagination offset (default 0)",
                        "default": 0,
                    },
                },
                "required": [],
            },
        ),
        # -- CEFR Classification (1) -----------------------------------------
        Tool(
            name="classify_cefr",
            description=(
                "Classify text into a CEFR level (A1-C2) using the "
                "configured LLM. Supports English (en), Chinese (zh), "
                "and Japanese (ja)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text to classify",
                    },
                    "lang": {
                        "type": "string",
                        "description": "Language code: en, zh, or ja",
                        "default": "en",
                        "enum": ["en", "zh", "ja"],
                    },
                },
                "required": ["text"],
            },
        ),
        # -- CEFR Batch (1) --------------------------------------------------
        Tool(
            name="cefr_batch",
            description=(
                "Batch classify multiple texts into CEFR levels (A1-C2). "
                "Each text is classified independently. Per-text errors are "
                "included with an error key in the results array."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "texts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Texts to classify (non-empty)",
                    },
                    "lang": {
                        "type": "string",
                        "description": "Language code: en, zh, or ja",
                        "default": "en",
                        "enum": ["en", "zh", "ja"],
                    },
                },
                "required": ["texts"],
            },
        ),
        # -- Project / Batch / Config (7) ------------------------------------
        Tool(
            name="list_projects",
            description=(
                "List all configured projects with domain count, source/topic "
                "summaries, and LLM provider info."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Optional status filter (active, archived)",
                        "default": "",
                        "enum": ["active", "archived"],
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="get_project_assets",
            description=(
                "Return project asset paths and sizes — collections, knowledge "
                "directories, database, exports, and config directory."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "description": (
                            "Optional asset-type filter: collections, knowledge, "
                            "database, exports, or config. Omit to return every "
                            "asset group."
                        ),
                        "enum": [
                            "collections",
                            "knowledge",
                            "database",
                            "exports",
                            "config",
                        ],
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="archive_project",
            description=(
                "Archive the current project. Refuses unless at least one "
                "entry has been promoted to 03-Wiki.  Archive itself is a "
                "human-only operation; this tool reports whether prerequisites "
                "are met."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Optional reason for archiving",
                        "default": "",
                    },
                    "confirm": {
                        "type": "boolean",
                        "description": "Must be True to confirm this destructive operation",
                        "default": False,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="batch_run",
            description=(
                "Execute collection and processing in sequence for a domain. "
                "Runs collect_sources then process_collection automatically."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                    "topic": {
                        "type": "string",
                        "description": "Optional topic / keyword filter for collection",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max items per source",
                        "default": 20,
                    },
                    "model": {
                        "type": "string",
                        "description": "Optional LLM model override for processing",
                    },
                    "resume_from": {
                        "type": "string",
                        "description": (
                            "Checkpoint/resume mode for the collect + process "
                            "pipeline (R-A-01): 'auto' resumes both phases from "
                            "their persisted checkpoints, 'start' checkpoints a "
                            "fresh run, or a source name to start collection at "
                            "that source. Omit for a legacy run."
                        ),
                        "default": "",
                    },
                },
                "required": ["domain"],
            },
        ),
        Tool(
            name="get_feeds",
            description=(
                "Return a paginated feed of KB entries for a domain. "
                "Supports optional filters by topic tag, source type, "
                "and collected-at date.  Output format: JSON (default) or RSS 2.0 XML."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain to query (required)",
                    },
                    "topic": {
                        "type": "string",
                        "description": "Optional filter by topic tag",
                    },
                    "source_type": {
                        "type": "string",
                        "description": "Optional filter by source type (e.g. rss, api)",
                    },
                    "since": {
                        "type": "string",
                        "description": "Optional ISO date filter (collected_at >=)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max items to return (1-200)",
                        "default": 50,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Number of items to skip for pagination",
                        "default": 0,
                    },
                    "format": {
                        "type": "string",
                        "description": "Output format: 'json' (paginated JSON envelope) or 'rss' (RSS 2.0 XML feed)",
                        "default": "json",
                        "enum": ["json", "rss"],
                    },
                },
                "required": ["domain"],
            },
        ),
        Tool(
            name="list_active_collections",
            description=(
                "List currently active or in-progress collection runs. Optionally filter by domain."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Optional domain filter (e.g. medical-research)",
                        "default": "",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="get_config",
            description=(
                "Return the current configuration as a structured dict. "
                "Supports optional 'section' filter: project, llm, domains. "
                "Returns the full config when section is omitted."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "section": {
                        "type": "string",
                        "description": "Optional config section: project, llm, domains",
                        "default": "",
                        "enum": ["project", "llm", "domains"],
                    },
                },
                "required": [],
            },
        ),
    ]
