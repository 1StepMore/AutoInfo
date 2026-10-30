"""MCP tool schemas — Sources, topics, keywords, collection (19 tools).

Phase 1 of #581: schemas extracted from ``mcp/server.py::_full_tool_list``
verbatim.  ``build_tools()`` returns FRESH ``Tool`` objects on every call,
so ``_decorate_tools`` mutation never leaks across calls.
"""

from __future__ import annotations

import os
import sqlite3
import uuid
from dataclasses import asdict
from datetime import datetime
from typing import Any

import httpx
from mcp.types import Tool

from autoinfo.config import SOURCE_KEY_ENV_VARS, ConfigNotFoundError
from autoinfo.keywords import keyword_suggestion_system_prompt
from autoinfo.llm import call_with_fallback
from autoinfo.mcp import context as mcp_context
from autoinfo.mcp.errors import ErrorCode, error_response, success_response


def build_tools() -> list[Tool]:
    """Return the 19 schemas for this module, in registration order."""
    return [
        # -- Source Management (5) -------------------------------------------
        Tool(
            name="add_source",
            description=(
                "Add a data source (idempotent — dedup by url + type + domain). "
                "Supports 6 source types: api, rss, web, webhook, email, pdf. "
                "For email sources, pass imap_server/imap_port/imap_username/"
                "imap_password/imap_mailbox convenience params. "
                "For webhook sources, pass webhook_secret for HMAC verification. "
                "All types accept an optional settings dict for arbitrary configuration."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Human-readable source name",
                    },
                    "url": {
                        "type": "string",
                        "description": "Source URL. email: imap(s)://host, pdf: file://path or http(s)://url, others: http(s)://url",
                    },
                    "type": {
                        "type": "string",
                        "description": "Source type (api, rss, web, webhook, email, pdf)",
                        "default": "api",
                        "enum": [
                            "api",
                            "rss",
                            "web",
                            "webhook",
                            "email",
                            "pdf",
                            "akshare",
                            "sec_edgar",
                            "edx_sitemap",
                        ],
                    },
                    "domain": {
                        "type": "string",
                        "description": "Domain to add this source to",
                    },
                    "settings": {
                        "type": "object",
                        "description": "Optional key-value configuration (stored in SourceConfig.settings)",
                    },
                    "requires_key": {
                        "type": "boolean",
                        "description": (
                            "Whether this source requires an API key/credential. "
                            "Defaults to derived from the source type (true for "
                            "known key-requiring types, e.g. nyt, ap_api, "
                            "reuters_mcp, unpaywall, youtube)."
                        ),
                    },
                    "imap_server": {
                        "type": "string",
                        "description": "Email type only: IMAP server hostname (e.g. imap.gmail.com)",
                    },
                    "imap_port": {
                        "type": "integer",
                        "description": "Email type only: IMAP port (default 993)",
                    },
                    "imap_username": {
                        "type": "string",
                        "description": "Email type only: IMAP username",
                    },
                    "imap_password": {
                        "type": "string",
                        "description": "Email type only: IMAP password (or set AUTOINFO_EMAIL_PASSWORD env var)",
                    },
                    "imap_mailbox": {
                        "type": "string",
                        "description": "Email type only: IMAP mailbox name (default INBOX)",
                    },
                    "webhook_secret": {
                        "type": "string",
                        "description": "Webhook type only: HMAC shared secret for payload verification",
                    },
                },
                "required": ["name", "url", "domain"],
            },
        ),
        Tool(
            name="add_sources",
            description="Batch-add sources with per-source error isolation. Each source object supports the same parameters as add_source.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sources": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "description": "Human-readable source name",
                                },
                                "url": {
                                    "type": "string",
                                    "description": "Source URL. email: imap(s)://host, pdf: file://path or http(s)://url, others: http(s)://url",
                                },
                                "type": {
                                    "type": "string",
                                    "default": "api",
                                    "description": "Source type (api, rss, web, webhook, email, pdf)",
                                    "enum": [
                                        "api",
                                        "rss",
                                        "web",
                                        "webhook",
                                        "email",
                                        "pdf",
                                        "akshare",
                                        "sec_edgar",
                                        "edx_sitemap",
                                    ],
                                },
                                "domain": {
                                    "type": "string",
                                    "description": "Domain to add this source to",
                                },
                                "settings": {
                                    "type": "object",
                                    "description": "Optional key-value configuration (stored in SourceConfig.settings)",
                                },
                                "requires_key": {
                                    "type": "boolean",
                                    "description": (
                                        "Whether this source requires an API key/credential. "
                                        "Defaults to derived from the source type (true for "
                                        "known key-requiring types, e.g. nyt, ap_api, "
                                        "reuters_mcp, unpaywall, youtube)."
                                    ),
                                },
                                "imap_server": {
                                    "type": "string",
                                    "description": "Email type only: IMAP server hostname",
                                },
                                "imap_port": {
                                    "type": "integer",
                                    "description": "Email type only: IMAP port (default 993)",
                                },
                                "imap_username": {
                                    "type": "string",
                                    "description": "Email type only: IMAP username",
                                },
                                "imap_password": {
                                    "type": "string",
                                    "description": "Email type only: IMAP password",
                                },
                                "imap_mailbox": {
                                    "type": "string",
                                    "description": "Email type only: IMAP mailbox name (default INBOX)",
                                },
                                "webhook_secret": {
                                    "type": "string",
                                    "description": "Webhook type only: HMAC shared secret",
                                },
                            },
                            "required": ["name", "url", "domain"],
                        },
                        "description": "List of source objects to add",
                    },
                },
                "required": ["sources"],
            },
        ),
        Tool(
            name="remove_source",
            description="Remove a source by its source_id (format: 'domain:name'). Deleting a source stops future collection from it without touching already-collected items. Requires confirm=True and an explicit actor for the audit trail.",
            inputSchema={
                "type": "object",
                "properties": {
                    "source_id": {
                        "type": "string",
                        "description": "Source identifier in 'domain:name' format (e.g. 'medical-research:pubmed'). Returned by add_source in the response.",
                    },
                    "confirm": {
                        "type": "boolean",
                        "description": "Must be True to confirm this destructive operation",
                        "default": False,
                    },
                    "actor": {
                        "type": "string",
                        "description": "Required. Actor requesting this destructive operation (must be passed explicitly)",
                    },
                },
                "required": ["source_id", "actor"],
            },
        ),
        Tool(
            name="test_source",
            description="Test whether a source URL is reachable and return metadata",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Source URL to test",
                    },
                    "type": {
                        "type": "string",
                        "description": "Source type (api, rss, web, webhook, email, pdf)",
                        "default": "api",
                        "enum": [
                            "api",
                            "rss",
                            "web",
                            "webhook",
                            "email",
                            "pdf",
                            "akshare",
                            "sec_edgar",
                            "edx_sitemap",
                        ],
                    },
                },
                "required": ["url"],
            },
        ),
        Tool(
            name="list_sources",
            description=(
                "List all configured collection sources for a domain, with "
                "each source's id, type, and platform. Use to inspect what "
                "feeds a domain before adding or removing sources."
            ),
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
        # -- Topic Management (6) --------------------------------------------
        Tool(
            name="add_topic",
            description="Add a topic to a domain (idempotent by name+domain). Topics focus collection on specific subjects; use before collect_sources so the topic's keywords drive which items get fetched. Returns the new or existing topic.",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name",
                    },
                    "name": {
                        "type": "string",
                        "description": "Topic name",
                    },
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of related keywords",
                        "default": [],
                    },
                },
                "required": ["domain", "name"],
            },
        ),
        Tool(
            name="remove_topic",
            description="Remove a topic from a domain. Stops topic-scoped collection for that name; existing items stay in the KB. Use to narrow collection scope when a research interest ends.",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name",
                    },
                    "topic_id": {
                        "type": "string",
                        "description": "Topic identifier — name or 'domain:name' format (e.g. 'IVF breakthroughs' or 'medical-research:IVF breakthroughs'). Returned by add_topic in the response.",
                    },
                    "confirm": {
                        "type": "boolean",
                        "description": "Must be True to confirm this destructive operation",
                        "default": False,
                    },
                    "actor": {
                        "type": "string",
                        "description": "Required. Actor requesting this destructive operation (must be passed explicitly)",
                    },
                },
                "required": ["domain", "topic_id", "actor"],
            },
        ),
        Tool(
            name="list_topics",
            description=(
                "List all tracked topics and their keywords for a domain. "
                "Topics group collected items by area; use to review "
                "coverage before collecting."
            ),
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
            name="list_keywords",
            description="List keywords with topic grouping, multi-language support, and scoring info",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                    "topic": {
                        "type": "string",
                        "description": "Optional topic name filter",
                    },
                },
                "required": ["domain"],
            },
        ),
        Tool(
            name="topic_group_add",
            description="Assign a group to one or more topics within a domain",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                    "group_name": {
                        "type": "string",
                        "description": "Name of the group to assign topics to",
                    },
                    "topic_names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of topic names to assign to this group",
                    },
                },
                "required": ["domain", "group_name", "topic_names"],
            },
        ),
        Tool(
            name="topic_group_remove",
            description="Remove a group assignment from all topics in that group",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                    "group_name": {
                        "type": "string",
                        "description": "Name of the group whose assignment should be removed from all topics",
                    },
                },
                "required": ["domain", "group_name"],
            },
        ),
        # -- Keywords Management (3) -----------------------------------------
        Tool(
            name="approve_keyword",
            description="Approve a keyword — move from auto_added to verified state",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                    "keyword": {
                        "type": "string",
                        "description": "Keyword to approve",
                    },
                },
                "required": ["domain", "keyword"],
            },
        ),
        Tool(
            name="reject_keyword",
            description="Reject a keyword — move to deprecated state. Marks the keyword so suggest_keywords and extraction no longer propose it. Use to prune noisy terms that keep appearing in collected content.",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                    "keyword": {
                        "type": "string",
                        "description": "Keyword to reject",
                    },
                },
                "required": ["domain", "keyword"],
            },
        ),
        Tool(
            name="suggest_keywords",
            description="Use LLM to suggest relevant keywords from a text input",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name for context",
                    },
                    "text": {
                        "type": "string",
                        "description": "Text to extract keywords from",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of suggestions (default 10)",
                        "default": 10,
                    },
                },
                "required": ["domain", "text"],
            },
        ),
        # -- Collection / Processing (5) -------------------------------------
        Tool(
            name="collect_sources",
            description=(
                "Execute a collection run for a domain. When domain is "
                "omitted, collects from ALL active domains and returns a "
                "{domains: {name: job_id, ...}, collected_count: N} mapping."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": (
                            "Domain name (e.g. medical-research). "
                            "Omit to collect from all active domains."
                        ),
                    },
                    "topic": {
                        "type": "string",
                        "description": "Optional topic / keyword filter",
                    },
                    "sources": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": ("Optional list of source names to restrict to"),
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max items per source",
                        "default": 20,
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": ("If true, preview only — no storage"),
                        "default": False,
                    },
                    "resume_from": {
                        "type": "string",
                        "description": (
                            "Checkpoint/resume mode for a long collection run "
                            "(R-A-01): 'auto' skips sources already completed "
                            "in the checkpoint, 'start' checkpoints a fresh "
                            "run, or a source name to start at that source. "
                            "Omit for a legacy run that writes no checkpoint."
                        ),
                        "default": "",
                    },
                    "force_enable": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Escape valve for the #665 auto-disable gate: source "
                            "names to collect even though their consecutive-failure "
                            "history auto-disabled them. One forced success resets "
                            "the error streak and un-disables the source."
                        ),
                        "default": [],
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="get_collection_progress",
            description="Return current collection progress for a domain (in-memory state). Reports items fetched, remaining, per-source status and an optional job_id lookup. Poll this while collect_sources runs to surface live progress to the user.",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Optional domain name — returns all domains if omitted",
                        "default": "",
                    },
                    "job_id": {
                        "type": "string",
                        "description": "Optional job_id to look up collection progress by job",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="get_collection_status",
            description="Return full collection results for a domain (last run). Summarizes the previous collect_sources execution: total items, per-source counts, failures and the run timestamp. Use after a collection finishes to inspect what was gathered.",
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
            name="process_collection",
            description=(
                "Execute a processing (LLM extraction) run for a domain. "
                "Optionally runs G4 factual consistency gate (check_factual) "
                "and G5 translation accuracy gate (check_translation)."
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
                        "description": (
                            "Optional topic name whose keywords seed the G3 "
                            "relevance gate. When omitted, G3 defaults to the "
                            "union of all the domain's topic keywords."
                        ),
                    },
                    "model": {
                        "type": "string",
                        "description": (
                            "Optional LLM model override (e.g. deepseek/deepseek-chat)"
                        ),
                    },
                    "batch_size": {
                        "type": "integer",
                        "description": (
                            "Max number of items to process per run (0 = all, default 0)"
                        ),
                        "default": 0,
                    },
                    "check_factual": {
                        "type": "boolean",
                        "description": (
                            "Run G4 factual consistency gate "
                            "(LLM-based check of summary vs source). "
                            "Default: False."
                        ),
                        "default": False,
                    },
                    "check_translation": {
                        "type": "boolean",
                        "description": (
                            "Run G5 translation accuracy gate "
                            "(LLM-based check of translation vs source). "
                            "Default: False."
                        ),
                        "default": False,
                    },
                },
                "required": ["domain"],
            },
        ),
        Tool(
            name="get_processing_progress",
            description="Get processing progress for a domain or job_id. Reports items processed, pending, and per-stage gate results during process_collection. Poll this to surface live LLM extraction progress to the operator.",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                    "job_id": {
                        "type": "string",
                        "description": "Optional job_id to look up processing progress by job",
                    },
                },
                "required": [],
            },
        ),
    ]


def _handle_add_source(
    name: str,
    url: str,
    type: str = "api",
    domain: str = "",
    settings: dict[str, Any] | None = None,
    requires_key: bool | None = None,
    imap_server: str | None = None,
    imap_port: int | None = None,
    imap_username: str | None = None,
    imap_password: str | None = None,
    imap_mailbox: str | None = None,
    webhook_secret: str | None = None,
) -> dict[str, Any]:
    """Add a source (idempotent — dedup by url + type + domain).

    Type-specific parameters:
    - *email*: ``imap_server``, ``imap_port``, ``imap_username``,
      ``imap_password``, ``imap_mailbox``
    - *webhook*: ``webhook_secret`` (HMAC shared secret)
    - All types: ``settings`` dict for arbitrary configuration
    - *requires_key*: whether the source needs a credential.  Defaults to
      derived from the source type via ``SOURCE_KEY_ENV_VARS`` (a type with
      canonical env vars is key-requiring).
    """
    # --- Validation -----------------------------------------------------------
    type_error = mcp_context._validate_source_type(type)
    if type_error:
        return error_response(
            code=ErrorCode.VALIDATION_ERROR,
            message=type_error,
            actionable=True,
        )

    url_error = mcp_context._validate_url(url, source_type=type)
    if url_error:
        return error_response(
            code=ErrorCode.VALIDATION_ERROR,
            message=url_error,
            actionable=True,
        )

    # --- Merge convenience params into settings dict ---------------------------
    merged_settings: dict[str, Any] = dict(settings or {})
    if type == "email":
        if imap_server:
            merged_settings["host"] = imap_server
        if imap_port is not None:
            merged_settings["port"] = imap_port
        if imap_username:
            merged_settings["username"] = imap_username
        if imap_password:
            merged_settings["password"] = imap_password
        if imap_mailbox:
            merged_settings["mailbox"] = imap_mailbox
    elif type == "webhook":
        if webhook_secret:
            merged_settings["secret"] = webhook_secret

    try:
        config = mcp_context._load_config()
    except Exception as exc:
        return mcp_context._error_from_exc(exc, "Failed to load the project configuration")

    domain_cfg = mcp_context._find_domain(config, domain)
    if domain_cfg is None:
        return error_response(
            code=ErrorCode.DOMAIN_NOT_FOUND,
            message=f"Domain '{domain}' is not configured. Use add_domain(name='{domain}') to create it.",
            actionable=True,
        )

    # Idempotency check: same url + type + domain
    for existing in domain_cfg.sources:
        if existing.url == url and existing.type == type:
            dup_result: dict[str, Any] = {
                "source": {
                    "name": existing.name,
                    "type": existing.type,
                    "url": existing.url,
                    "domain": domain,
                    "quality_tier": existing.quality_tier,
                    "tos_classification": existing.tos_classification,
                    "requires_key": existing.requires_key,
                },
                "created": False,
                "source_id": f"{domain}:{existing.name}",
            }
            if existing.quality_tier >= 3:
                dup_result["warning"] = "Quality tier 3+ source — content may have lower authority."
            return mcp_context._canonicalize(dup_result)

    # Determine next quality_tier based on type
    quality_tier = 1 if type in ("api", "rss") else 2
    _tier_tos_map = {1: "open", 2: "licensed", 3: "restricted", 4: "sensitive"}
    tos_classification = _tier_tos_map.get(quality_tier, "open")

    # requires_key: explicit param wins; otherwise derive from the source
    # type via the consolidated key map (a type with canonical env vars is
    # key-requiring).
    if requires_key is None:
        requires_key = type in SOURCE_KEY_ENV_VARS

    from autoinfo.config import SourceConfig

    new_source = SourceConfig(
        name=name,
        type=type,
        url=url,
        quality_tier=quality_tier,
        tos_classification=tos_classification,
        requires_key=requires_key,
        settings=merged_settings,
    )
    domain_cfg.sources.append(new_source)
    mcp_context._save_config(config)

    result: dict[str, Any] = {
        "source": {
            "name": name,
            "type": type,
            "url": url,
            "domain": domain,
            "quality_tier": quality_tier,
            "tos_classification": tos_classification,
            "requires_key": requires_key,
        },
        "created": True,
        "source_id": f"{domain}:{name}",
    }

    # Include settings in result if non-empty
    if merged_settings:
        result["source"]["settings"] = merged_settings

    # Advisory warning for tier 3+ sources
    if quality_tier >= 3:
        result["warning"] = "Quality tier 3+ source — content may have lower authority."

    return mcp_context._canonicalize(result)


def _handle_add_sources(sources: list[dict[str, Any]]) -> dict[str, Any]:
    """Batch-add sources with per-source error isolation."""
    results: list[dict[str, Any]] = []
    errored = 0

    for idx, src in enumerate(sources):
        try:
            result = _handle_add_source(
                name=src.get("name", f"source-{idx}"),
                url=src.get("url", ""),
                type=src.get("type", "api"),
                domain=src.get("domain", ""),
                settings=src.get("settings"),
                requires_key=src.get("requires_key"),
            )
            if isinstance(result, dict) and result.get("success") is False:
                errored += 1
            results.append({"index": idx, **result})
        except Exception as exc:
            errored += 1
            results.append(
                {
                    "index": idx,
                    **mcp_context._error_from_exc(exc, "Failed to add sources"),
                }
            )

    return {
        "results": results,
        "total": len(sources),
        "succeeded": len(sources) - errored,
        "errored": errored,
    }


def _handle_remove_source(
    source_id: str, confirm: bool = True, actor: str = "agent"
) -> dict[str, Any]:
    """Remove a source by its source_id (``domain:name``)."""
    if not confirm:
        return error_response(
            code=ErrorCode.CONFIRMATION_REQUIRED,
            message="This operation is destructive and requires confirmation. Pass confirm=True to proceed.",
            actionable=True,
        )
    try:
        config = mcp_context._load_config()
    except Exception as exc:
        return mcp_context._error_from_exc(exc, "Failed to load the project configuration")

    parts = source_id.split(":", 1)
    if len(parts) != 2:
        return error_response(
            code=ErrorCode.INVALID_SOURCE_ID,
            message="source_id must be in format 'domain:name'",
            actionable=True,
        )
    domain_name, source_name = parts

    domain_cfg = mcp_context._find_domain(config, domain_name)
    if domain_cfg is None:
        return error_response(
            code=ErrorCode.DOMAIN_NOT_FOUND,
            message=f"Domain '{domain_name}' is not configured. Use add_domain(name='{domain_name}') to create it.",
            actionable=True,
        )

    for i, existing in enumerate(domain_cfg.sources):
        if existing.name == source_name:
            removed = domain_cfg.sources.pop(i)
            mcp_context._save_config(config)
            return {
                "removed": True,
                "source_id": source_id,
                "source": {
                    "name": removed.name,
                    "type": removed.type,
                    "url": removed.url,
                },
            }

    return error_response(
        code=ErrorCode.SOURCE_NOT_FOUND,
        message=f"Source '{source_name}' not found in domain '{domain_name}'",
        actionable=True,
    )


def _handle_test_source(url: str, type: str = "api") -> dict[str, Any]:
    """Test whether a source URL is reachable."""
    type_error = mcp_context._validate_source_type(type)
    if type_error:
        return error_response(
            code=ErrorCode.VALIDATION_ERROR,
            message=type_error,
            actionable=True,
        )
    url_error = mcp_context._validate_url(url, source_type=type)
    if url_error:
        return error_response(
            code=ErrorCode.VALIDATION_ERROR,
            message=url_error,
            actionable=True,
        )
    key_status = mcp_context._source_key_status(type)
    key_missing_hint = ""
    if key_status["key_required"] and not key_status["key_configured"]:
        key_missing_hint = (
            f" Source type '{type}' requires an API key ({', '.join(key_status['missing_env_vars'])}), "
            f"which is not configured; collection may return no items. See {mcp_context._REQUIRED_KEYS_DOCS_REF}."
        )
    try:
        if type == "api":
            resp = httpx.get(url, timeout=10.0, follow_redirects=True)
        else:
            resp = httpx.head(url, timeout=10.0, follow_redirects=True)
            if resp.status_code >= 400:
                resp = httpx.get(url, timeout=10.0, follow_redirects=True)

        content_type_header = resp.headers.get("content-type", "").split(";")[0].strip()
        content_preview = resp.text[:500] if resp.text else ""
        size_kb = len(resp.content) / 1024.0

        # Suggested extract fields based on source type
        suggested_fields = mcp_context._suggest_extract_fields(type)

        result: dict[str, Any] = {
            "reachable": resp.status_code < 500,
            "status_code": resp.status_code,
            "content_type": content_type_header,
            "content_preview": content_preview,
            "size_kb": round(size_kb, 1),
            "format": mcp_context._infer_format(content_type_header, content_preview),
            "suggested_extract_fields": suggested_fields,
            "key_required": key_status["key_required"],
            "key_configured": key_status["key_configured"],
        }
        if key_missing_hint:
            result["warning"] = key_missing_hint.strip()
        return mcp_context._canonicalize(result)
    except httpx.TimeoutException:
        return error_response(
            code=ErrorCode.TIMEOUT,
            message=f"Request to '{url}' timed out.{key_missing_hint}",
            actionable=True,
        )
    except Exception as exc:
        hint = f" {key_missing_hint.strip()}" if key_missing_hint else ""
        return error_response(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"{exc}{hint}",
            actionable=True,
        )


def _handle_list_sources(domain: str) -> dict[str, Any]:
    """List all sources for a given domain."""
    try:
        config = mcp_context._load_config()
    except Exception as exc:
        return mcp_context._error_from_exc(exc, "Failed to load the project configuration")

    domain_cfg = mcp_context._find_domain(config, domain)
    if domain_cfg is None:
        return error_response(
            code=ErrorCode.DOMAIN_NOT_FOUND,
            message=f"Domain '{domain}' is not configured. Use add_domain(name='{domain}') to create it.",
            actionable=True,
        )

    sources = [
        {
            "source_id": f"{domain}:{s.name}",
            "name": s.name,
            "type": s.type,
            "url": s.url,
            "quality_tier": s.quality_tier,
            "tos_classification": s.tos_classification,
            "requires_key": s.requires_key,
        }
        for s in domain_cfg.sources
    ]
    return {"domain": domain, "sources": sources, "count": len(sources)}


def _handle_add_topic(
    domain: str,
    name: str,
    keywords: list[str] | None = None,
) -> dict[str, Any]:
    """Add a topic to a domain."""
    try:
        config = mcp_context._load_config()
    except Exception as exc:
        return mcp_context._error_from_exc(exc, "Failed to load the project configuration")

    domain_cfg = mcp_context._find_domain(config, domain)
    if domain_cfg is None:
        return error_response(
            code=ErrorCode.DOMAIN_NOT_FOUND,
            message=f"Domain '{domain}' is not configured. Use add_domain(name='{domain}') to create it.",
            actionable=True,
        )

    # Idempotency check: same name
    for existing in domain_cfg.topics:
        if existing.name == name:
            return {
                "topic": {"name": name, "keywords": existing.keywords},
                "created": False,
                "topic_id": f"{domain}:{name}",
            }

    from autoinfo.config import TopicConfig

    new_topic = TopicConfig(name=name, keywords=keywords or [])
    domain_cfg.topics.append(new_topic)
    mcp_context._save_config(config)

    return {
        "topic": {"name": name, "keywords": keywords or []},
        "created": True,
        "topic_id": f"{domain}:{name}",
    }


def _handle_remove_topic(
    domain: str, topic_id: str, confirm: bool = True, actor: str = "agent"
) -> dict[str, Any]:
    """Remove a topic by its topic_id (``domain:name``)."""
    if not confirm:
        return error_response(
            code=ErrorCode.CONFIRMATION_REQUIRED,
            message="This operation is destructive and requires confirmation. Pass confirm=True to proceed.",
            actionable=True,
        )
    try:
        config = mcp_context._load_config()
    except Exception as exc:
        return mcp_context._error_from_exc(exc, "Failed to load the project configuration")

    domain_cfg = mcp_context._find_domain(config, domain)
    if domain_cfg is None:
        return error_response(
            code=ErrorCode.DOMAIN_NOT_FOUND,
            message=f"Domain '{domain}' is not configured. Use add_domain(name='{domain}') to create it.",
            actionable=True,
        )

    topic_name = topic_id.split(":", 1)[-1] if ":" in topic_id else topic_id
    for i, existing in enumerate(domain_cfg.topics):
        if existing.name == topic_name:
            removed = domain_cfg.topics.pop(i)
            mcp_context._save_config(config)
            return {
                "removed": True,
                "topic_id": topic_id,
                "topic": {"name": removed.name, "keywords": removed.keywords},
            }

    return error_response(
        code=ErrorCode.TOPIC_NOT_FOUND,
        message=f"Topic '{topic_name}' not found in domain '{domain}'",
        actionable=True,
    )


def _handle_list_topics(domain: str) -> dict[str, Any]:
    """List all topics for a given domain."""
    try:
        config = mcp_context._load_config()
    except Exception as exc:
        return mcp_context._error_from_exc(exc, "Failed to load the project configuration")

    domain_cfg = mcp_context._find_domain(config, domain)
    if domain_cfg is None:
        return error_response(
            code=ErrorCode.DOMAIN_NOT_FOUND,
            message=f"Domain '{domain}' is not configured. Use add_domain(name='{domain}') to create it.",
            actionable=True,
        )

    topics = [{"name": t.name, "keywords": t.keywords} for t in domain_cfg.topics]
    return {"domain": domain, "topics": topics, "count": len(topics)}


def _handle_list_keywords(
    domain: str,
    topic: str | None = None,
) -> dict[str, Any]:
    """List keywords with topic grouping, multi-language support, and scoring info.

    Returns keywords from two sources:
    1. Topic-level keywords from ``.autoinfo/config.yaml`` (existing behaviour).
    2. Managed keywords from ``knowledge/<domain>/_keywords.yaml``.

    When *topic* is provided, only keywords for that topic are returned
    (from config only — managed keywords are returned separately).
    """
    try:
        config = mcp_context._load_config()
    except Exception as exc:
        return mcp_context._error_from_exc(exc, "Failed to load the project configuration")

    domain_cfg = mcp_context._find_domain(config, domain)
    if domain_cfg is None:
        return error_response(
            code=ErrorCode.DOMAIN_NOT_FOUND,
            message=f"Domain '{domain}' is not configured. Use add_domain(name='{domain}') to create it.",
            actionable=True,
        )

    # --- Topic-level keywords from config (existing behaviour) ---
    results: list[dict[str, Any]] = []
    for t in domain_cfg.topics:
        if topic and t.name != topic:
            continue
        entry: dict[str, Any] = {
            "name": t.name,
            "keywords": t.keywords,
            "group": t.group,
            "relevance_threshold": t.relevance_threshold,
            "keyword_count": len(t.keywords)
            if isinstance(t.keywords, list)
            else sum(len(v) for v in t.keywords.values())
            if isinstance(t.keywords, dict)
            else 0,
        }
        results.append(entry)

    # --- Managed keywords from _keywords.yaml (new) ---
    from autoinfo.keywords import KeywordsFile

    kf = KeywordsFile()
    managed_entries = kf.load(domain)
    managed = [
        {
            "keyword": e.keyword,
            "state": e.state.value,
            "aliases": e.aliases,
            "created_at": e.created_at,
            "updated_at": e.updated_at,
            "source": e.source,
        }
        for e in managed_entries
    ]

    return {
        "domain": domain,
        "topic": topic or "*",
        "topics": results,
        "count": len(results),
        "keywords_file": {
            "path": str(kf._path(domain)),
            "exists": kf._path(domain).is_file(),
            "entries": managed,
            "entry_count": len(managed),
        },
    }


def _handle_topic_group_add(
    domain: str,
    group_name: str,
    topic_names: list[str],
) -> dict[str, Any]:
    """Assign a group to one or more topics.

    For each topic name in *topic_names*, find the matching topic in the
    domain config and set its ``group`` field to *group_name*.  Topics that
    do not exist in the domain are reported in the ``not_found`` list.
    """
    try:
        config = mcp_context._load_config()
    except Exception as exc:
        return mcp_context._error_from_exc(exc, "Failed to load the project configuration")

    domain_cfg = mcp_context._find_domain(config, domain)
    if domain_cfg is None:
        return error_response(
            code=ErrorCode.DOMAIN_NOT_FOUND,
            message=f"Domain '{domain}' is not configured. Use add_domain(name='{domain}') to create it.",
            actionable=True,
        )

    assigned: list[str] = []
    not_found: list[str] = []

    for name in topic_names:
        found = False
        for t in domain_cfg.topics:
            if t.name == name:
                t.group = group_name
                assigned.append(name)
                found = True
                break
        if not found:
            not_found.append(name)

    if assigned:
        mcp_context._save_config(config)

    return {
        "domain": domain,
        "group": group_name,
        "assigned": assigned,
        "not_found": not_found,
    }


def _handle_topic_group_remove(domain: str, group_name: str) -> dict[str, Any]:
    """Remove a group assignment from all topics in that group.

    Clears the ``group`` field (sets to ``""``) on every topic whose
    current group matches *group_name*.
    """
    try:
        config = mcp_context._load_config()
    except Exception as exc:
        return mcp_context._error_from_exc(exc, "Failed to load the project configuration")

    domain_cfg = mcp_context._find_domain(config, domain)
    if domain_cfg is None:
        return error_response(
            code=ErrorCode.DOMAIN_NOT_FOUND,
            message=f"Domain '{domain}' is not configured. Use add_domain(name='{domain}') to create it.",
            actionable=True,
        )

    cleared: list[str] = []
    for t in domain_cfg.topics:
        if t.group == group_name:
            t.group = ""
            cleared.append(t.name)

    if cleared:
        mcp_context._save_config(config)

    return {
        "domain": domain,
        "group": group_name,
        "cleared": cleared,
        "removed": len(cleared) > 0,
    }


def _handle_approve_keyword(domain: str, keyword: str) -> dict[str, Any]:
    """Approve a keyword — move from ``auto_added`` → ``verified``."""
    from autoinfo.keywords import KeywordsFile

    kf = KeywordsFile()
    result = kf.approve_keyword(domain=domain, keyword=keyword)
    if result is None:
        return error_response(
            code=ErrorCode.KEYWORD_NOT_FOUND,
            message=f"Keyword '{keyword}' not found in domain '{domain}'",
            actionable=True,
        )
    return success_response(
        {
            "domain": domain,
            "keyword": keyword,
            "state": result.state.value,
        }
    )


def _handle_reject_keyword(domain: str, keyword: str) -> dict[str, Any]:
    """Reject a keyword — move to ``deprecated``."""
    from autoinfo.keywords import KeywordsFile

    kf = KeywordsFile()
    result = kf.deprecate_keyword(domain=domain, keyword=keyword)
    if result is None:
        return error_response(
            code=ErrorCode.KEYWORD_NOT_FOUND,
            message=f"Keyword '{keyword}' not found in domain '{domain}'",
            actionable=True,
        )
    return success_response(
        {
            "domain": domain,
            "keyword": keyword,
            "state": result.state.value,
        }
    )


def _handle_suggest_keywords(
    domain: str,
    text: str,
    limit: int = 10,
) -> dict[str, Any]:
    """Use LLM to suggest keywords from the given text."""
    import json

    from autoinfo.config import get_config_path, load_config, resolve_llm_model

    timeout: float | None = None
    try:
        config_path = get_config_path()
        if config_path:
            config = load_config(config_path)
            # Issue #195: resolve_llm_model raises when unconfigured — no
            # hardcoded vendor default; the not-api_key guard below is the
            # MCP-level LLM_NOT_CONFIGURED response.
            model = resolve_llm_model(config.llm)
            api_key = config.llm.api_key or os.environ.get("AUTOINFO_LLM_API_KEY", "")
            base_url = config.llm.base_url or None
            json_mode = config.llm.json_mode
            timeout = config.llm.timeout
        else:
            model = ""
            api_key = os.environ.get("AUTOINFO_LLM_API_KEY", "")
            base_url = None
            json_mode = False
    except Exception:
        model = ""
        api_key = os.environ.get("AUTOINFO_LLM_API_KEY", "")
        base_url = None
        json_mode = True

    if not api_key:
        return error_response(
            code=ErrorCode.LLM_NOT_CONFIGURED,
            message="LLM is not configured. Use configure_llm() to set up your API key. See docs/dev/required-api-keys.md for the full list of API keys and environment variables.",
            actionable=True,
        )

    system_prompt = keyword_suggestion_system_prompt(limit)

    user_prompt = f"Extract up to {limit} keywords from this text:\n\n{text}"

    try:
        response = call_with_fallback(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            json_mode=json_mode,
            max_tokens=500,
            temperature=0.3,
            base_url=base_url,
            api_key=api_key or None,
            timeout=timeout,
        )
        content: str = response.choices[0].message.content or ""

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            # LLM returned empty or non-JSON content.  Fall back to a
            # deterministic keyword extraction from the text itself so the
            # tool still returns useful suggestions instead of failing
            # (issue #215; DeepSeek-V4-Flash occasionally returns empty
            # content for longer prompts).
            import re

            from autoinfo.process import _is_valid_discovery_keyword

            words = re.findall(r"[A-Za-z][A-Za-z\-]{3,}", text)
            seen: list[str] = []
            for w in words:
                wl = w.lower()
                if wl not in seen and _is_valid_discovery_keyword(wl):
                    seen.append(wl)
                if len(seen) >= limit:
                    break
            if seen:
                return {
                    "domain": domain,
                    "suggestions": seen,
                    "count": len(seen),
                    "source": "deterministic-fallback",
                }
            return error_response(
                code=ErrorCode.EMPTY_RESULT,
                message=(
                    "Keyword suggestion failed: LLM returned empty or "
                    "non-JSON content and no keywords could be extracted "
                    "from the text. Retry the request."
                ),
                actionable=True,
            )
        if isinstance(parsed, list):
            suggestions = parsed
        elif isinstance(parsed, dict):
            for key in ("keywords", "suggestions", "tags", "items"):
                if key in parsed and isinstance(parsed[key], list):
                    suggestions = parsed[key]
                    break
            else:
                suggestions = list(parsed.values()) if parsed else []
        else:
            suggestions = []

        suggestions = [str(s).strip() for s in suggestions if s]
        suggestions = suggestions[:limit]

        return {
            "domain": domain,
            "suggestions": suggestions,
            "count": len(suggestions),
        }
    except Exception as exc:
        mcp_context.logger.exception("Keyword suggestion failed")
        return mcp_context._error_from_exc(exc, "Keyword suggestion failed")


def _handle_collect_sources(
    domain: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Execute a collection run via ``autoinfo.collect.run_collection``.

    When *domain* is ``None``, collects from all active domains and returns a
    ``{domains: {name: job_id, ...}, collected_count: N}`` mapping.
    """
    from datetime import timezone

    from autoinfo.collect import run_collection

    # -- Domain-less: collect from ALL active domains ------------------------
    if domain is None:
        from autoinfo.config import get_config_path, load_config

        config_path = get_config_path()
        if config_path is None:
            raise ConfigNotFoundError("No configuration found. Run 'autoinfo init' first.")
        config = load_config(config_path)
        active_domains = [d.name for d in config.domains if d.active]

        if not active_domains:
            return {
                "domains": {},
                "collected_count": 0,
                "message": "No active domains found in configuration.",
            }

        domain_results: dict[str, str] = {}
        for dom in active_domains:
            job_id = str(uuid.uuid4())
            started_at = datetime.now(timezone.utc).isoformat()
            mcp_context._save_job_state(
                job_id,
                "collection",
                dom,
                "running",
                0.0,
                {
                    "started_at": started_at,
                    "completed_at": "",
                    "items_collected": 0,
                    "errors": 0,
                    "items_per_source": {},
                    "duration_s": 0.0,
                },
            )

            try:
                result = run_collection(domain=dom, **kwargs)
                total_new = result.get("total_new", 0) if isinstance(result, dict) else 0
                _total_found = result.get("total_found", 0) if isinstance(result, dict) else 0
                errors = result.get("errors", 0) if isinstance(result, dict) else 0
                mcp_context._save_job_state(
                    job_id,
                    "collection",
                    dom,
                    "completed",
                    100.0,
                    {
                        "started_at": started_at,
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                        "items_collected": total_new,
                        "errors": errors,
                        "items_per_source": (
                            result.get("items_per_source", {}) if isinstance(result, dict) else {}
                        ),
                        "duration_s": 0.0,
                    },
                )
                domain_results[dom] = job_id
            except Exception:
                mcp_context._save_job_state(
                    job_id,
                    "collection",
                    dom,
                    "error",
                    0.0,
                    {
                        "started_at": started_at,
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                # Continue to next domain on failure

        return {
            "domains": domain_results,
            "collected_count": len(domain_results),
        }

    # -- Single-domain collection ---------------------------------------------
    cfg = mcp_context._load_config()
    if mcp_context._find_domain(cfg, domain) is None:
        return error_response(
            ErrorCode.DOMAIN_NOT_FOUND,
            f"Domain '{domain}' is not configured. Use add_domain(name='{domain}') to create it.",
            actionable=True,
        )

    job_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc).isoformat()
    mcp_context._save_job_state(
        job_id,
        "collection",
        domain,
        "running",
        0.0,
        {
            "started_at": started_at,
            "completed_at": "",
            "items_collected": 0,
            "errors": 0,
            "items_per_source": {},
            "duration_s": 0.0,
        },
    )

    try:
        result = run_collection(domain=domain, **kwargs)
        # Attempt to extract stats from result
        total_new = result.get("total_new", 0) if isinstance(result, dict) else 0
        _total_found = result.get("total_found", 0) if isinstance(result, dict) else 0
        errors = result.get("errors", 0) if isinstance(result, dict) else 0
        mcp_context._save_job_state(
            job_id,
            "collection",
            domain,
            "completed",
            100.0,
            {
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "items_collected": total_new,
                "errors": errors,
                "items_per_source": result.get("items_per_source", {})
                if isinstance(result, dict)
                else {},
                "duration_s": 0.0,
            },
        )
        if isinstance(result, dict):
            result["job_id"] = job_id
        else:
            result = {"job_id": job_id, "result": result}
        return mcp_context._canonicalize(result)
    except Exception as exc:
        mcp_context._save_job_state(
            job_id,
            "collection",
            domain,
            "error",
            0.0,
            {
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return mcp_context._error_from_exc(
            exc, "Collection failed", code=ErrorCode.COLLECTION_FAILED
        )


def _handle_get_collection_progress(domain: str = "", job_id: str = "") -> dict[str, Any]:
    """Return current collection progress. Supports lookup by domain or job_id."""
    if job_id:
        state = mcp_context._load_job_state(job_id)
        if state:
            is_complete = state.get("status") in ("completed", "error")
            return {"job_id": job_id, **state, "is_complete": is_complete}
        return {"job_id": job_id, "status": "not_found", "is_complete": False}
    if domain:
        state = mcp_context._load_latest_domain_state(domain, "collection")
        if state:
            return {"domain": domain, **state}
        return {
            "domain": domain,
            "status": "idle",
            "started_at": "",
            "completed_at": "",
            "progress_pct": 0.0,
            "items_collected": 0,
            "errors": 0,
            "items_per_source": {},
            "duration_s": 0.0,
        }

    # Return all — query distinct domains with collection entries
    def _read_all(conn: sqlite3.Connection) -> dict[str, Any]:
        rows = conn.execute(
            """SELECT DISTINCT domain FROM job_state
               WHERE state_type = 'collection'
               ORDER BY domain"""
        ).fetchall()
        results: dict[str, Any] = {}
        for row in rows:
            dom = row["domain"]
            latest = conn.execute(
                """SELECT * FROM job_state
                   WHERE domain = ? AND state_type = 'collection'
                   ORDER BY created_at DESC LIMIT 1""",
                (dom,),
            ).fetchone()
            if latest:
                meta = mcp_context._safe_json_load(latest["metadata"])
                results[dom] = {
                    "status": latest["status"],
                    "progress_pct": latest["progress_pct"],
                    "created_at": latest["created_at"],
                    "updated_at": latest["updated_at"],
                    **meta,
                }
        return {"domains": results, "count": len(results)}

    return mcp_context._canonicalize(mcp_context._with_job_db(_read_all))


def _handle_get_collection_status(domain: str) -> dict[str, Any]:
    """Return full collection results for *domain* (last run)."""
    state = mcp_context._load_latest_domain_state(domain, "collection")
    if state is None:
        state = {
            "status": "idle",
            "started_at": "",
            "completed_at": "",
            "progress_pct": 0.0,
            "items_collected": 0,
            "errors": 0,
            "items_per_source": {},
            "duration_s": 0.0,
        }

    # Compute duration if available
    duration = 0.0
    if state.get("started_at") and state.get("completed_at"):
        try:
            from datetime import datetime

            started = datetime.fromisoformat(state["started_at"])
            completed = datetime.fromisoformat(state["completed_at"])
            duration = (completed - started).total_seconds()
        except (ValueError, TypeError):
            duration = 0.0

    return {
        "domain": domain,
        "status": state["status"],
        "last_collection_time": state.get("completed_at", ""),
        "items_per_source": state.get("items_per_source", {}),
        "error_count": state.get("errors", 0),
        "duration_s": round(duration, 2),
        "items_collected": state.get("items_collected", 0),
    }


def _handle_process_collection(**kwargs: Any) -> dict[str, Any]:
    """Execute a processing run via ``autoinfo.process.run_processing``."""
    from datetime import timezone

    from autoinfo.process import run_processing

    domain = kwargs.get("domain", "unknown")
    job_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc).isoformat()
    mcp_context._save_job_state(
        job_id,
        "processing",
        domain,
        "running",
        0.0,
        {
            "started_at": started_at,
            "kb_entries_created": 0,
            "total_items": 0,
        },
    )

    try:
        result = run_processing(**kwargs)
        if result.total_items == 0:
            mcp_context._save_job_state(
                job_id,
                "processing",
                domain,
                "noop",
                100.0,
                {
                    "started_at": started_at,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "total_items": 0,
                },
            )
            return success_response(
                {
                    "status": "noop",
                    "total_items": 0,
                    "message": f"No cached items found for domain '{domain}'. Run collect_sources() first.",
                    "domain": domain,
                }
            )
        result_dict = asdict(result)
        mcp_context._save_job_state(
            job_id,
            "processing",
            domain,
            "completed",
            100.0,
            {
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "kb_entries_created": result_dict.get("kb_entries_created", 0),
                "total_items": result_dict.get("total_items", result_dict.get("total_new", 0)),
            },
        )
        result_dict["job_id"] = job_id
        return mcp_context._canonicalize(result_dict)
    except Exception as exc:
        mcp_context._save_job_state(
            job_id,
            "processing",
            domain,
            "error",
            0.0,
            {
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return mcp_context._error_from_exc(
            exc, "Processing failed", code=ErrorCode.PROCESSING_FAILED
        )


def _handle_get_processing_progress(domain: str = "", job_id: str = "") -> dict[str, Any]:
    """Return processing progress. Supports lookup by domain or job_id."""
    if job_id:
        state = mcp_context._load_job_state(job_id)
        if state:
            is_complete = state.get("status") in ("completed", "error")
            return {"job_id": job_id, **state, "is_complete": is_complete}
        return {"job_id": job_id, "status": "not_found", "is_complete": False}
    if domain:
        from autoinfo.process import get_processing_progress

        return mcp_context._canonicalize(get_processing_progress(domain=domain))
    return {"status": "idle", "is_complete": True}
