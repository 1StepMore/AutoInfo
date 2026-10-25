"""MCP tool schemas — Trace, merge, similarity, KB freshness (4 tools).

Phase 1 of #581: schemas extracted from ``mcp/server.py::_full_tool_list``
verbatim.  ``build_tools()`` returns FRESH ``Tool`` objects on every call,
so ``_decorate_tools`` mutation never leaks across calls.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcp.types import Tool

from autoinfo.config import DEFAULT_TTL_DAYS
from autoinfo.mcp import context as mcp_context
from autoinfo.mcp.errors import ErrorCode, error_response


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


def _handle_trace_item(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Trace the full pipeline history for a trace_id.

    Searches pipeline logs (``logs/pipeline-*.log``) and KB frontmatter
    for all events associated with the trace_id.
    """
    trace_id = arguments["trace_id"]

    # -- Search pipeline logs ---------------------------------------------
    pipeline_events: list[dict[str, Any]] = []
    log_dir = Path("logs")
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

    # -- Search KB frontmatter for the entry ----------------------------
    kb_entries: list[dict[str, Any]] = []
    knowledge_dir = Path("knowledge")
    if knowledge_dir.is_dir():
        import yaml as _yaml

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
                fm = _yaml.safe_load(parts[1])
            except Exception:
                continue
            if isinstance(fm, dict) and fm.get("trace_id") == trace_id:
                kb_entries.append(
                    {
                        "entry_id": fm.get("entry_id", ""),
                        "title": fm.get("title", ""),
                        "domain": fm.get("domain", ""),
                        "tier": fm.get("tier", ""),
                        "file_path": str(md_file),
                        "collected_at": fm.get("collected_at", ""),
                        "language": fm.get("language", ""),
                        "dedup_status": fm.get("dedup_status", ""),
                    }
                )

    # -- Timeline from pipeline events -----------------------------------
    timeline: list[dict[str, Any]] = []
    for evt in pipeline_events:
        timeline.append(
            {
                "stage": evt.get("module", "?"),
                "timestamp": evt.get("timestamp", ""),
                "status": evt.get("level", "?"),
                "message": evt.get("message", ""),
                "item_id": evt.get("item_id", ""),
            }
        )

    return {
        "trace_id": trace_id,
        "pipeline_events": pipeline_events,
        "timeline": timeline,
        "kb_entries": kb_entries,
        "event_count": len(pipeline_events),
        "kb_entry_count": len(kb_entries),
    }


def _handle_merge_items(
    item_ids: list[str],
    strategy: str = "simple",
) -> dict[str, Any]:
    """Merge multiple KB entries into one.

    Parameters
    ----------
    item_ids:
        List of KB entry IDs to merge (min 2).
    strategy:
        ``"simple"`` (default) or ``"title_first"``.

    Returns
    -------
    dict
        Merged result from :func:`autoinfo.quality.merge_items`.
    """
    from autoinfo.quality import merge_items

    try:
        result = merge_items(item_ids=item_ids, strategy=strategy)
        return mcp_context._canonicalize(result)
    except Exception as exc:
        mcp_context.logger.exception("merge_items failed")
        return mcp_context._error_from_exc(exc, "merge_items failed")


def _handle_find_similar_items(
    query: str,
    threshold: float = 0.8,
    limit: int | None = None,
) -> dict[str, Any]:
    """Find items similar to *query* using text similarity.

    Parameters
    ----------
    query:
        Text to match against KB entries.
    threshold:
        Minimum similarity ratio (0.0–1.0). Default 0.8.
    limit:
        Maximum number of results to return. Default (None) returns
        up to 20.

    Returns
    -------
    dict
        ``{"entries": [...]}`` from :func:`autoinfo.quality.find_similar_items`.
    """
    from autoinfo.quality import find_similar_items

    try:
        result = find_similar_items(query=query, threshold=threshold)
        if limit is not None:
            result = result[:limit]
        return {"entries": result}
    except Exception as exc:
        mcp_context.logger.exception("find_similar_items failed")
        return mcp_context._error_from_exc(exc, "find_similar_items failed")


def _handle_calculate_freshness_score(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle calculate_freshness_score — fetch entry, compute freshness."""
    entry_id = arguments["entry_id"]
    ttl_days = arguments.get("ttl_days", DEFAULT_TTL_DAYS)
    from autoinfo.kb import KBStore, calculate_freshness_score

    store = KBStore()
    entry = store.get_entry(entry_id)
    if entry is None:
        return error_response(
            code=ErrorCode.NOT_FOUND,
            message=f"Entry not found: {entry_id}",
            actionable=True,
        )
    score = calculate_freshness_score(entry, ttl_days)
    return {"entry_id": entry_id, "freshness_score": score, "ttl_days": ttl_days}
