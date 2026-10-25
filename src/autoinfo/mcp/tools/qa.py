"""MCP tool schemas — Q&A + source health (3 tools).

Phase 1 of #581: schemas extracted from ``mcp/server.py::_full_tool_list``
verbatim.  ``build_tools()`` returns FRESH ``Tool`` objects on every call,
so ``_decorate_tools`` mutation never leaks across calls.
"""

from __future__ import annotations

from typing import Any

from mcp.types import Tool

from autoinfo.mcp import context as mcp_context


def build_tools() -> list[Tool]:
    """Return the 3 schemas for this module, in registration order."""
    return [
        # -- Q&A (1) ---------------------------------------------------------
        Tool(
            name="query_collected",
            description=(
                "Search collected content via FTS5 and synthesise an answer "
                "using the LLM.  Provide a natural-language question; the "
                "tool returns an answer with source citations."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural-language question to answer",
                    },
                    "domain": {
                        "type": "string",
                        "description": "Domain to scope the search to (e.g. medical-research)",
                    },
                    "content_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Optional explicit list of entry IDs to use instead of FTS5 search"
                        ),
                    },
                },
                "required": ["query", "domain"],
            },
        ),
        # -- Source Health / Feedback (2) ------------------------------------
        Tool(
            name="get_source_health",
            description=(
                "Return health status for a single source. "
                "Status values: healthy, degraded, error, paused, unknown."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "source_id": {
                        "type": "string",
                        "description": "Source identifier in 'domain:name' format (e.g. 'medical-research:pubmed'). Returned by add_source in the response.",
                    },
                },
                "required": ["source_id"],
            },
        ),
        Tool(
            name="rate_item",
            description=(
                "Store a user rating and optional feedback for a "
                "collected item or KB entry.  Rating must be 1-5."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "item_id": {
                        "type": "string",
                        "description": "Collected item or KB entry ID to rate",
                    },
                    "rating": {
                        "type": "integer",
                        "description": "Rating value 1 (worst) to 5 (best)",
                    },
                    "feedback": {
                        "type": "string",
                        "description": "Optional free-text feedback",
                    },
                },
                "required": ["item_id", "rating"],
            },
        ),
    ]


def _handle_get_source_health(source_id: str) -> dict[str, Any]:
    """Return health status for a single source."""
    from autoinfo.status import get_source_health

    return mcp_context._canonicalize(get_source_health(source_id=source_id))


def _handle_rate_item(
    item_id: str,
    rating: int,
    feedback: str = "",
) -> dict[str, Any]:
    """Store user rating/feedback for a collected item."""
    from autoinfo.status import rate_item

    return mcp_context._canonicalize(rate_item(item_id=item_id, rating=rating, feedback=feedback))


def _handle_query_collected(
    query: str,
    domain: str,
    content_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Q&A on collected content via FTS5 + LLM synthesis.

    Dispatches to ``autoinfo.qa.query_collected``.
    """
    from autoinfo.qa import query_collected as _qa

    return mcp_context._canonicalize(_qa(query=query, domain=domain, content_ids=content_ids))
