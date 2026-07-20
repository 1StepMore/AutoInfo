"""MCP server — exposes AutoInfo capabilities as MCP tools over stdio.

This is the primary agent-facing interface for AutoInfo.  All 35+ capabilities
are planned; v0.1 exposes the 6 core tools:

* ``health_check``        — Quick status ping
* ``diagnose_system``     — Comprehensive system health
* ``collect_sources``     — Execute a collection run
* ``process_collection``  — Execute a processing (LLM extraction) run
* ``list_summaries``      — Browse KB entries
* ``get_kb_entry``        — Fetch a single KB entry

Usage::

    python -m autoinfo.mcp.server

The server listens on stdio (JSON-RPC 2.0) and responds to
``CallToolRequest`` messages.  Connect with any MCP client::

    async with stdio_client(["python", "-m", "autoinfo.mcp.server"]) as (read, write):
        async with ClientSession(read, write) as session:
            result = await session.call_tool("health_check", {})
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from autoinfo import __version__

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool implementations
#
# These are plain (sync) functions so they can be tested without an async
# test harness.  The ``call_tool`` handler wraps them in ``TextContent``.
# ---------------------------------------------------------------------------


def _handle_health_check() -> dict[str, Any]:
    """Quick status ping."""
    return {
        "status": "ok",
        "version": __version__,
        "tools_count": 6,
    }


def _handle_diagnose_system() -> dict[str, Any]:
    """Comprehensive system diagnostics — llm, sources, disk, db."""
    result: dict[str, Any] = {
        "llm": {"configured": False},
        "sources": {"count": 0},
        "disk": {},
        "db": {"exists": False},
    }

    # -- Config -----------------------------------------------------------
    try:
        from autoinfo.config import get_config_path, load_config

        config_path = get_config_path()
        if config_path:
            config = load_config(config_path)
            result["llm"] = {
                "configured": True,
                "provider": config.llm.provider,
                "model": config.llm.model,
                "key_configured": bool(
                    config.llm.api_key
                    or os.environ.get("AUTOINFO_LLM_API_KEY")
                ),
            }
            sources = []
            for d in config.domains:
                if d.active:
                    for s in d.sources:
                        sources.append({
                            "name": s.name,
                            "type": s.type,
                            "domain": d.name,
                            "quality_tier": s.quality_tier,
                        })
            result["sources"] = {"count": len(sources), "items": sources}
    except Exception as exc:
        result["config_error"] = str(exc)

    # -- Disk -------------------------------------------------------------
    collections_dir = Path("collections")
    knowledge_dir = Path("knowledge")
    result["disk"] = {
        "collections_dir_exists": collections_dir.is_dir(),
        "knowledge_dir_exists": knowledge_dir.is_dir(),
    }

    # -- DB ---------------------------------------------------------------
    db_path = knowledge_dir.parent / "autoinfo.db"
    result["db"] = {"exists": db_path.is_file()}

    return result


def _handle_collect_sources(**kwargs: Any) -> dict[str, Any]:
    """Execute a collection run via ``autoinfo.collect.run_collection``."""
    from autoinfo.collect import run_collection

    return run_collection(**kwargs)


def _handle_process_collection(**kwargs: Any) -> dict[str, Any]:
    """Execute a processing run via ``autoinfo.process.run_processing``."""
    from autoinfo.process import run_processing

    result = run_processing(**kwargs)
    return asdict(result)


def _handle_list_summaries(**kwargs: Any) -> dict[str, Any]:
    """List KB entries for a domain via ``KBStore.list_entries``.

    Expects ``domain`` in ``**kwargs`` (popped before passing the rest).
    """
    from autoinfo.kb import KBStore

    domain = kwargs.pop("domain")
    store = KBStore()
    entries = store.list_entries(domain, **kwargs)
    return {"domain": domain, "entries": entries, "count": len(entries)}


def _handle_get_kb_entry(entry_id: str) -> dict[str, Any]:
    """Fetch a single KB entry by ID via ``KBStore.get_entry``."""
    from autoinfo.kb import KBStore

    store = KBStore()
    entry = store.get_entry(entry_id)
    if entry is None:
        return {
            "error_code": "NotFound",
            "message": f"Entry '{entry_id}' not found",
            "actionable": True,
        }
    return entry


# ---------------------------------------------------------------------------
# Error response helper
# ---------------------------------------------------------------------------


def _error_response(exc: Exception) -> list[TextContent]:
    """Build a standardised error response.

    Every error response includes three fields so agents can decide how
    to react:

    * ``error_code``  — Python exception type name
    * ``message``     — Human-readable description
    * ``actionable``  — Whether the agent can retry the operation
    """
    return [
        TextContent(
            type="text",
            text=json.dumps({
                "error_code": type(exc).__name__,
                "message": str(exc),
                "actionable": True,
            }),
        )
    ]


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

app = Server("autoinfo")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """Declare the 6 available tools with their input schemas."""
    return [
        Tool(
            name="health_check",
            description="Check server health status",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="diagnose_system",
            description=(
                "Comprehensive system diagnostics — LLM config, "
                "sources, disk, and database"
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="collect_sources",
            description="Execute a collection run for a domain",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                    "topic": {
                        "type": "string",
                        "description": "Optional topic / keyword filter",
                    },
                    "sources": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Optional list of source names to restrict to"
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max items per source",
                        "default": 20,
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": (
                            "If true, preview only — no storage"
                        ),
                        "default": False,
                    },
                },
                "required": ["domain"],
            },
        ),
        Tool(
            name="process_collection",
            description=(
                "Execute a processing (LLM extraction) run for a domain"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                    "model": {
                        "type": "string",
                        "description": (
                            "Optional LLM model override "
                            "(e.g. deepseek/deepseek-chat)"
                        ),
                    },
                },
                "required": ["domain"],
            },
        ),
        Tool(
            name="list_summaries",
            description="Browse KB entries for a domain, newest first",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                    "date_from": {
                        "type": "string",
                        "description": (
                            "ISO date filter — only entries from "
                            "this date onward"
                        ),
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
            description="Fetch a single KB entry by its entry ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "entry_id": {
                        "type": "string",
                        "description": "Unique entry identifier",
                    },
                },
                "required": ["entry_id"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Dispatch tool calls to the appropriate implementation."""
    try:
        if name == "health_check":
            result = _handle_health_check()
        elif name == "diagnose_system":
            result = _handle_diagnose_system()
        elif name == "collect_sources":
            result = _handle_collect_sources(**arguments)
        elif name == "process_collection":
            result = _handle_process_collection(**arguments)
        elif name == "list_summaries":
            result = _handle_list_summaries(**arguments)
        elif name == "get_kb_entry":
            result = _handle_get_kb_entry(**arguments)
        else:
            return [
                TextContent(
                    type="text",
                    text=json.dumps({
                        "error_code": "UnknownTool",
                        "message": f"Unknown tool: {name}",
                        "actionable": False,
                    }),
                )
            ]

        return [TextContent(type="text", text=json.dumps(result))]
    except Exception as exc:
        logger.exception("Tool '%s' failed", name)
        return _error_response(exc)


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


async def main() -> None:
    """Run the MCP server over stdio transport.

    Opens the stdio read/write streams and enters the server's main loop.
    The server processes incoming JSON-RPC messages until the client
    disconnects.
    """
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


def run() -> None:
    """Synchronous entry point (used by ``python -m autoinfo.mcp.server``)."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
