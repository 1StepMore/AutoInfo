"""MCP tool schemas — Trace, merge, similarity, KB freshness (4 tools).

Phase 1 of #581: schemas extracted from ``mcp/server.py::_full_tool_list``
verbatim.  ``build_tools()`` returns FRESH ``Tool`` objects on every call,
so ``_decorate_tools`` mutation never leaks across calls.
"""

from __future__ import annotations

from mcp.types import Tool

from autoinfo.config import DEFAULT_TTL_DAYS


def build_tools() -> list[Tool]:
    """Return the 4 schemas for this module, in registration order."""
    return [
        # -- Trace (1) -------------------------------------------------------
        Tool(
            name="trace_item",
            description="Trace the full pipeline history for a trace_id. Reconstructs the item journey from collection through gates, KB storage, and delivery using the structured logs. Use to diagnose why a specific item was dropped or delayed.",
            inputSchema={
                "type": "object",
                "properties": {
                    "trace_id": {
                        "type": "string",
                        "description": "UUID trace identifier from collection",
                    },
                },
                "required": ["trace_id"],
            },
        ),
        # -- Merge (1) -------------------------------------------------------
        Tool(
            name="merge_items",
            description="Merge multiple KB entries into one (cross-collection dedup). Combines the content, sources, and metadata of 2+ entries into a single entry. Use after find_similar_items flags duplicates; strategy selects simple concatenation or title-first merging.",
            inputSchema={
                "type": "object",
                "properties": {
                    "item_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of KB entry IDs to merge",
                    },
                    "strategy": {
                        "type": "string",
                        "description": "Merge strategy: 'simple' or 'title_first'",
                        "default": "simple",
                        "enum": ["simple", "title_first"],
                    },
                },
                "required": ["item_ids"],
            },
        ),
        # -- Find Similar (1) ------------------------------------------------
        Tool(
            name="find_similar_items",
            description="Find items similar to a query using text similarity. Accepts a query string and ranks KB entries by lexical/semantic closeness. Use for dedup triage before merge_items or to locate related content across the collection.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "threshold": {
                        "type": "number",
                        "description": "Minimum similarity ratio (0.0–1.0)",
                        "default": 0.8,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results to return",
                        "default": 20,
                    },
                },
                "required": ["query"],
            },
        ),
        # -- KB Freshness (1) ------------------------------------------------
        Tool(
            name="calculate_freshness_score",
            description="Calculate freshness score (0.0–1.0) for a KB entry based on age and TTL",
            inputSchema={
                "type": "object",
                "properties": {
                    "entry_id": {
                        "type": "string",
                        "description": "KB entry ID to calculate freshness for",
                    },
                    "ttl_days": {
                        "type": "integer",
                        "description": f"Time-to-live in days (default: {DEFAULT_TTL_DAYS})",
                        "default": DEFAULT_TTL_DAYS,
                    },
                },
                "required": ["entry_id"],
            },
        ),
    ]
