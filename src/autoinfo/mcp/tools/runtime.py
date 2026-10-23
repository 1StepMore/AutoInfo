"""MCP tool schemas — Init, metrics, soft-delete/GDPR (10 tools).

Phase 1 of #581: schemas extracted from ``mcp/server.py::_full_tool_list``
verbatim.  ``build_tools()`` returns FRESH ``Tool`` objects on every call,
so ``_decorate_tools`` mutation never leaks across calls.
"""

from __future__ import annotations

from mcp.types import Tool

from autoinfo.cli.init import _list_demo_domains


def build_tools() -> list[Tool]:
    """Return the 10 schemas for this module, in registration order."""
    return [
        # -- Init (3) --------------------------------------------------------
        Tool(
            name="init_project",
            description=(
                "Initialize AutoInfo project skeleton (creates .autoinfo/ "
                "directory, config, demo domain). Idempotent — safe to call "
                "when already initialized."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Demo domain name (e.g. medical-research)",
                        "enum": _list_demo_domains(),
                    },
                    "project_name": {
                        "type": "string",
                        "description": "Optional human-friendly project name",
                        "default": "",
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "Preview what would be created without writing files",
                        "default": False,
                    },
                    "llm_provider": {
                        "type": "string",
                        "description": 'Override default LLM provider (e.g. "openai")',
                        "default": "",
                    },
                    "llm_model": {
                        "type": "string",
                        "description": 'Override default LLM model (e.g. "gpt-4")',
                        "default": "",
                    },
                    "llm_base_url": {
                        "type": "string",
                        "description": 'Override default LLM base URL (e.g. "http://localhost:11434/v1")',
                        "default": "",
                    },
                },
                "required": ["domain"],
            },
        ),
        Tool(
            name="configure_llm",
            description=(
                "Update LLM configuration in .autoinfo/config.yaml. "
                "Incremental: only updates fields explicitly provided. "
                "api_key is stored as env var reference (${AUTOINFO_LLM_API_KEY}), "
                "never the raw key. No-op when no parameters are supplied. "
                "llm_fallback configures the fallback chain (None = unchanged, "
                "[] = clear, entries merge by (provider, model) identity); "
                "llm_tasks configures per-task model routing (None = unchanged, "
                "{} = clear; judgment tasks still resolve to the release-pinned "
                "the effective judgment model at runtime)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "provider": {
                        "type": "string",
                        "description": 'LLM provider name (e.g. "openai", "openrouter")',
                        "default": "",
                    },
                    "model": {
                        "type": "string",
                        "description": 'LLM model name (e.g. "gpt-4", "deepseek/deepseek-chat")',
                        "default": "",
                    },
                    "api_key": {
                        "type": "string",
                        "description": "API key — stored as env var reference (${AUTOINFO_LLM_API_KEY}), not raw key. Set AUTOINFO_LLM_API_KEY env var separately.",
                        "default": "",
                    },
                    "base_url": {
                        "type": "string",
                        "description": 'LLM base URL (e.g. "http://localhost:11434/v1")',
                        "default": "",
                    },
                    "llm_fallback": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "model": {
                                    "type": "string",
                                    "description": "Fallback model name (required)",
                                },
                                "provider": {
                                    "type": "string",
                                    "description": "Fallback provider; empty inherits the primary provider (provider inheritance does not grant the primary API key — key inheritance requires a matching base_url)",
                                },
                                "base_url": {
                                    "type": "string",
                                    "description": "Fallback base URL",
                                },
                                "api_key": {
                                    "type": "string",
                                    "description": "Fallback API key (env var reference ${...}); empty inherits the primary key ONLY when base_url matches the primary gateway — a cross-endpoint fallback must carry its own explicit key",
                                },
                                "json_mode": {
                                    "type": "boolean",
                                    "description": "Force JSON response format for this fallback",
                                },
                                "reasoning_model": {
                                    "type": "boolean",
                                    "description": "Mark this fallback as a reasoning model",
                                },
                                "timeout": {
                                    "type": "number",
                                    "description": "Per-call timeout in seconds",
                                },
                            },
                            "required": ["model"],
                        },
                        "description": "Fallback chain entries. None = leave unchanged; [] = clear; entries merge by (provider, model) identity.",
                    },
                    "llm_tasks": {
                        "type": "object",
                        "description": "Per-task LLM overrides keyed by task name (model/provider/max_tokens). None = leave unchanged; {} = clear. Judgment tasks (g4_factual/g5_translation/llm_judge) still resolve to the effective judgment model (llm.judgment_model/llm.model) at runtime.",
                        "additionalProperties": {
                            "type": "object",
                            "properties": {
                                "model": {
                                    "type": "string",
                                    "description": "Task model override",
                                },
                                "provider": {
                                    "type": "string",
                                    "description": "Task provider override",
                                },
                                "max_tokens": {
                                    "type": "integer",
                                    "description": "Task max_tokens override",
                                },
                            },
                        },
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="test_llm_connection",
            description=(
                "Test LLM connectivity with the current or overridden "
                "configuration. Makes a minimal completion call and reports "
                "connectable, tested_model, latency_ms, and config_source "
                "(params when any override is supplied, else config). "
                "Pass api_key explicitly to test a key without persisting it."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "provider": {
                        "type": "string",
                        "description": 'LLM provider override (e.g. "openai", "openrouter")',
                        "default": "",
                    },
                    "model": {
                        "type": "string",
                        "description": 'LLM model override (e.g. "gpt-4", "deepseek/deepseek-chat")',
                        "default": "",
                    },
                    "base_url": {
                        "type": "string",
                        "description": 'LLM base URL override (e.g. "http://localhost:11434/v1")',
                        "default": "",
                    },
                    "api_key": {
                        "type": "string",
                        "description": "API key override for this test only (never persisted). Empty inherits the config/env key.",
                        "default": "",
                    },
                },
                "required": [],
            },
        ),
        # -- Metrics (2) -----------------------------------------------------
        Tool(
            name="get_metrics",
            description="Get Prometheus-format metrics for monitoring. Exposes counters and gauges for collection, processing, LLM spend and delivery as text exposition format. Use when scraping into a monitoring stack or debugging a live server.",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Optional domain filter",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="get_prometheus_metrics",
            description="Get raw Prometheus exposition-format metrics (same format as /metrics HTTP endpoint)",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        # -- Soft-delete & GDPR (5) ------------------------------------------
        Tool(
            name="soft_delete_entry",
            description="Mark an entry as deleted (soft-delete) or permanently remove it (hard-delete). Set purge=True for permanent deletion. 03-Wiki entries are append-only: only an actor whitelisted in AUTOINFO_DIRECTOR_ACTORS (default 'director') can delete them.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entry_id": {"type": "string"},
                    "purge": {
                        "type": "boolean",
                        "description": "If False (default), performs soft-delete (mark as deleted). If True, permanently deletes the entry from index, FTS5, and disk.",
                        "default": False,
                    },
                    "actor": {
                        "type": "string",
                        "description": "Required. Acting actor. 03-Wiki entries require an actor whitelisted in AUTOINFO_DIRECTOR_ACTORS",
                    },
                },
                "required": ["entry_id", "actor"],
            },
        ),
        Tool(
            name="mark_stale",
            description="Mark a knowledge base entry as stale (demoted in search, excluded from digests)",
            inputSchema={
                "type": "object",
                "properties": {
                    "entry_id": {"type": "string"},
                },
                "required": ["entry_id"],
            },
        ),
        Tool(
            name="restore_entry",
            description="Restore a soft-deleted entry. Reverses soft_delete_entry within the retention window, returning the entry to its previous tier. Use to recover a mistakenly archived item before permanent purge.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entry_id": {"type": "string"},
                    "actor": {
                        "type": "string",
                        "description": "Required. Actor requesting this destructive operation (must be passed explicitly)",
                    },
                },
                "required": ["entry_id", "actor"],
            },
        ),
        Tool(
            name="export_user_data",
            description="Export all data for a user (GDPR compliance). Bundles the profile, subscriptions, preferences, delivery log and audit rows into a single JSON payload. Use to fulfill a data-subject access request.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                },
                "required": ["user_id"],
            },
        ),
        Tool(
            name="delete_user_data",
            description="Delete all user data (GDPR right to be forgotten). Permanently erases the end-user profile, subscriptions, delivery history and derived records. Use only for a verified erasure request; requires actor for audit.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "purge": {"type": "boolean"},
                    "actor": {
                        "type": "string",
                        "description": "Required. Actor requesting this destructive operation (must be passed explicitly)",
                    },
                },
                "required": ["user_id", "actor"],
            },
        ),
    ]
