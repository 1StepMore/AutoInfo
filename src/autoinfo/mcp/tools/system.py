"""MCP tool schemas — System + Discovery (13 tools).

Phase 1 of #581: schemas extracted from ``mcp/server.py::_full_tool_list``
verbatim.  ``build_tools()`` returns FRESH ``Tool`` objects on every call,
so ``_decorate_tools`` mutation never leaks across calls.
"""

from __future__ import annotations

from mcp.types import Tool


def build_tools() -> list[Tool]:
    """Return the 13 schemas for this module, in registration order."""
    return [
        # -- System (3) ------------------------------------------------------
        Tool(
            name="health_check",
            description="Check server health status. Returns status, version, and the registered tool count without touching the LLM or disk. Use as the first call when a session starts to confirm the MCP server is alive and correctly versioned.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_tool_count",
            description="Return the number of registered MCP tools. Reads the live _full_tool_list() so the count always matches the declared surface. Use to sanity-check a server's tool inventory after configuration changes.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="diagnose_system",
            description=(
                "Comprehensive system diagnostics — LLM config, "
                "sources, disk, database, health_score (0-100), "
                "and phase detection (uninitialized/llm_unconfigured/"
                "no_sources/ready_to_collect/operational)"
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        # -- Discovery (10) ---------------------------------------------------
        Tool(
            name="list_domains",
            description="List all configured domains with source/topic counts. Each entry shows name, active flag, source count and topic count. Use to orient at session start before deciding which domain to collect, process, or generate output for.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="list_available_platforms",
            description="List all supported source platform types with descriptions. Returns the catalog of collector handlers (rss, api, web, webhook, email, pdf and the platform-specific adapters). Use when choosing a source type for add_source.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_domain_schema",
            description="Return the extraction schema and structure for a domain. Lists the extract_fields, classifier settings and quality-gate configuration that process_collection applies. Use to preview what fields an item will be extracted into.",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                },
                "required": ["domain"],
            },
        ),
        Tool(
            name="list_available_models",
            description="List configured LLM models with provider and task info. Reads the effective config so agents can pick a model id for process_collection or output generation. Use before the first LLM-heavy call to confirm a key is wired.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_effective_llm_config",
            description="Resolve the effective LLM configuration for a task. Merges the base llm config with per-task overrides (model, provider, fallback chain). Use to preview which model process_collection or output generation will actually call for a named task.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": ("Optional task name (e.g. extraction, summarization)"),
                        "default": None,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="activate_domain",
            description="Activate a domain (set domain.active = True). Use after adding a domain to mark it eligible for collection; deactivated domains are skipped by collect_sources. Returns the updated domain configuration.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Domain name to activate",
                    },
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="deactivate_domain",
            description="Deactivate a domain (set domain.active = False). Use to temporarily pause collection for a domain without deleting its configuration or data; collect_sources skips inactive domains. Returns the updated domain configuration.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Domain name to deactivate",
                    },
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="add_domain",
            description="Create a new domain configuration (idempotent — returns existing config if domain already exists)",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Domain name (e.g. my-custom-domain)",
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional description of the domain",
                    },
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="remove_domain",
            description="Remove a domain configuration (director-only). Preserves all collected data on disk. Requires confirm=True and an actor whitelisted in AUTOINFO_DIRECTOR_ACTORS (default 'director') or the call is refused with DirectorOnly.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Domain name to remove",
                    },
                    "confirm": {
                        "type": "boolean",
                        "description": "Must be True to remove a domain (destructive operation)",
                    },
                    "actor": {
                        "type": "string",
                        "description": "Required. Acting director (must be whitelisted in AUTOINFO_DIRECTOR_ACTORS; default 'director') or the call is refused with DirectorOnly.",
                    },
                },
                "required": ["name", "confirm", "actor"],
            },
        ),
        Tool(
            name="get_domain_config",
            description="Return full domain config including sources, topics, extract_fields. Use to inspect a domain's complete configuration before modifying it or before running process_collection. Accepts either the domain name or the legacy name spelling.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                },
                "required": ["name"],
            },
        ),
    ]
