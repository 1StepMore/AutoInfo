"""MCP tool schemas — System + Discovery (13 tools).

Phase 1 of #581: schemas extracted from ``mcp/server.py::_full_tool_list``
verbatim.  ``build_tools()`` returns FRESH ``Tool`` objects on every call,
so ``_decorate_tools`` mutation never leaks across calls.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp.types import Tool

from autoinfo import __version__
from autoinfo.cli.doctor import calculate_health_score
from autoinfo.mcp import context as mcp_context
from autoinfo.mcp.errors import ErrorCode, error_response, success_response


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


def _handle_health_check() -> dict[str, Any]:
    """Quick status ping.

    Returns a canonical success envelope whose ``data`` is a **structured**
    object (``status`` / ``version`` / ``tools_count``) — never an opaque
    text blob.  Per ADR-0005 (T-S-09), this is the intentional exception to
    the text-payload metadata rule: there is no text payload to label, so no
    ``content_type``/``length`` metadata is emitted.  Text-format tools
    (``get_prometheus_metrics``, ``get_feeds``) carry the metadata block
    instead.
    """
    from autoinfo.mcp.server import _TOOL_DISPATCH

    return success_response(
        {
            "status": "ok",
            "version": __version__,
            "tools_count": len(_TOOL_DISPATCH),
        }
    )


def _handle_get_tool_count() -> dict[str, Any]:
    """Return the number of registered MCP tools."""
    from autoinfo.mcp.server import _TOOL_DISPATCH

    return {
        "tools_count": len(_TOOL_DISPATCH),
    }


def _handle_diagnose_system() -> dict[str, Any]:
    """Comprehensive system diagnostics — llm, sources, disk, db."""
    result: dict[str, Any] = {
        "llm": {"configured": False},
        "sources": {"count": 0, "items": []},
        "disk": {},
        "db": {"exists": False},
        "fallback_health": {
            "configured": False,
            "count": 0,
            "entries": [],
            "primary": {
                "model": "",
                "provider": "",
                "reasoning_model": False,
                "json_mode": False,
            },
        },
    }

    # -- Config -----------------------------------------------------------
    config_path = None
    try:
        from autoinfo.config import get_config_path, llm_fallback_health, load_config

        config_path = get_config_path()
        if config_path:
            config = load_config(config_path)
            result["llm"] = {
                "configured": True,
                "provider": config.llm.provider,
                "model": config.llm.model,
                "key_configured": bool(
                    config.llm.api_key or os.environ.get("AUTOINFO_LLM_API_KEY")
                ),
            }
            result["fallback_health"] = llm_fallback_health(config)
            sources = []
            for d in config.domains:
                if d.active:
                    for s in d.sources:
                        sources.append(
                            {
                                "name": s.name,
                                "type": s.type,
                                "domain": d.name,
                                "quality_tier": s.quality_tier,
                                "tos_classification": s.tos_classification,
                            }
                        )
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

    # -- Health Score -----------------------------------------------------
    # Adapt MCP result schema to match doctor.py calculate_health_score contract:
    #   llm.status (ok/error) from llm.key_configured
    #   config.status (ok/error) from config_path presence
    #   sources list from sources.items
    llm_cfg = result["llm"]
    llm_status = "ok" if llm_cfg.get("key_configured", False) else "error"
    config_status = "ok" if config_path and "config_error" not in result else "error"
    source_items: Any = result["sources"].get("items", [])
    if not isinstance(source_items, list):
        source_items = []

    health_dict: dict[str, Any] = {
        "python": {"status": "ok"},
        "config": {"status": config_status},
        "llm": {
            "status": llm_status,
            "key_configured": llm_cfg.get("key_configured", False),
        },
        "sources": [{"status": "ok"} for _ in source_items],
    }
    result["health_score"] = calculate_health_score(health_dict)

    # -- Phase Detection --------------------------------------------------
    result["phase"] = mcp_context._detect_phase(result, config_path, collections_dir, knowledge_dir)

    return mcp_context._canonicalize(result)


def _handle_list_domains() -> dict[str, Any]:
    """List all configured domains with source/topic counts."""
    try:
        config = mcp_context._load_config()
    except Exception as exc:
        return mcp_context._error_from_exc(exc, "Failed to load the project configuration")

    domains = []
    for d in config.domains:
        domains.append(
            {
                "name": d.name,
                "active": d.active,
                "source_count": len(d.sources),
                "topic_count": len(d.topics),
            }
        )
    return {"domains": domains, "count": len(domains)}


def _handle_list_available_platforms() -> dict[str, Any]:
    """List all supported source platform types with descriptions."""
    return {"platforms": mcp_context.PLATFORMS}


def _handle_get_domain_schema(domain: str) -> dict[str, Any]:
    """Return the schema / structure for a given domain."""
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
            "name": s.name,
            "type": s.type,
            "url": s.url,
            "quality_tier": s.quality_tier,
            "tos_classification": s.tos_classification,
            "requires_key": s.requires_key,
        }
        for s in domain_cfg.sources
    ]
    topics = [{"name": t.name, "keywords": t.keywords} for t in domain_cfg.topics]

    extract_fields_schema: dict[str, dict[str, str]] = {
        "tl_dr": {"type": "string", "description": "One-sentence summary"},
        "key_points": {"type": "array", "description": "Bullet-point key findings"},
        "entities": {"type": "array", "description": "Extracted entities with types"},
        "relevance_score": {"type": "number", "description": "Relevance 0-100"},
    }

    # Include any custom extract_fields from the domain config
    for field_name in domain_cfg.extract_fields:
        if field_name not in extract_fields_schema:
            extract_fields_schema[field_name] = {
                "type": "string",
                "description": field_name.replace("_", " ").title(),
            }

    return {
        "domain": domain,
        "extract_fields": extract_fields_schema,
        "output_templates": [
            {
                "name": "digest",
                "description": "Scheduled knowledge digests",
                "access_level": "free",
            },
            {
                "name": "report",
                "description": "Thematic structured reports",
                "access_level": "free",
            },
            {"name": "tutorial", "description": "Learning path tutorials", "access_level": "free"},
            {
                "name": "presentation",
                "description": "Slide-based presentations",
                "access_level": "free",
            },
        ],
        "topics": topics,
        "sources": sources,
    }


def _handle_list_available_models() -> dict[str, Any]:
    """List available LLM models from configuration.

    Returns the full model pool: the primary model first, then every
    configured fallback entry (``task: fallback:<model>``), then every
    per-task model override (``task: <task name>``).  The primary entry
    keeps its historical shape (task/provider/model/api_key_configured);
    fallback and task entries are appended with additional fields
    (``inherits_provider``, ``max_tokens``).  ``count`` always equals
    ``len(models)``.
    """
    try:
        config = mcp_context._load_config()
    except Exception as exc:
        return mcp_context._error_from_exc(exc, "Failed to load the project configuration")

    api_key_configured = bool(config.llm.api_key or os.environ.get("AUTOINFO_LLM_API_KEY"))

    models: list[dict[str, Any]] = [
        {
            "task": "default",
            "provider": config.llm.provider,
            "model": config.llm.model,
            "api_key_configured": api_key_configured,
        },
    ]

    # Fallback chain entries — appended after the primary.  An empty
    # provider means the entry inherits the primary provider at call time
    # (call_with_fallback, llm.py:714-727); the key is inherited too.
    for fb in config.llm.fallback:
        models.append(
            {
                "task": f"fallback:{fb.model}",
                "provider": fb.provider,
                "model": fb.model,
                "api_key_configured": bool(
                    fb.api_key or config.llm.api_key or os.environ.get("AUTOINFO_LLM_API_KEY")
                ),
                "inherits_provider": not bool(fb.provider),
            }
        )

    # Per-task model overrides — appended last.  Tasks inherit the
    # primary provider/model/key when their own fields are empty.
    for task_name, tc in config.llm.tasks.items():
        models.append(
            {
                "task": task_name,
                "provider": tc.provider,
                "model": tc.model,
                "api_key_configured": api_key_configured,
                "inherits_provider": not bool(tc.provider),
                "max_tokens": tc.max_tokens,
            }
        )

    return {"models": models, "count": len(models)}


def _handle_get_effective_llm_config(task: str | None = None) -> dict[str, Any]:
    """Resolve effective LLM config for a given task."""
    from autoinfo.config import get_effective_llm_config

    try:
        return mcp_context._canonicalize(get_effective_llm_config(task=task))
    except Exception as exc:
        return mcp_context._error_from_exc(exc, "Failed to resolve the effective LLM configuration")


def _handle_activate_domain(name: str) -> dict[str, Any]:
    """Activate a domain (set domain.active = True)."""
    try:
        config = mcp_context._load_config()
    except Exception as exc:
        return mcp_context._error_from_exc(exc, "Failed to load the project configuration")

    domain_cfg = mcp_context._find_domain(config, name)
    if domain_cfg is None:
        return error_response(
            code=ErrorCode.DOMAIN_NOT_FOUND,
            message=f"Domain '{name}' is not configured. Use add_domain(name='{name}') to create it.",
            actionable=True,
        )

    if domain_cfg.active:
        return {
            "domain": name,
            "active": True,
            "message": f"Domain '{name}' is already active",
        }

    domain_cfg.active = True
    mcp_context._save_config(config)
    return {
        "domain": name,
        "active": True,
        "message": f"Domain '{name}' activated",
    }


def _handle_deactivate_domain(name: str) -> dict[str, Any]:
    """Deactivate a domain (set domain.active = False)."""
    try:
        config = mcp_context._load_config()
    except Exception as exc:
        return mcp_context._error_from_exc(exc, "Failed to load the project configuration")

    domain_cfg = mcp_context._find_domain(config, name)
    if domain_cfg is None:
        return error_response(
            code=ErrorCode.DOMAIN_NOT_FOUND,
            message=f"Domain '{name}' is not configured. Use add_domain(name='{name}') to create it.",
            actionable=True,
        )

    if not domain_cfg.active:
        return {
            "domain": name,
            "active": False,
            "message": f"Domain '{name}' is already inactive",
        }

    domain_cfg.active = False
    mcp_context._save_config(config)
    return {
        "domain": name,
        "active": False,
        "message": f"Domain '{name}' deactivated",
    }


def _handle_add_domain(name: str, description: str = "") -> dict[str, Any]:
    """Create a new domain configuration (idempotent — returns existing config if domain already exists)."""
    try:
        config = mcp_context._load_config()
    except Exception as exc:
        return mcp_context._error_from_exc(exc, "Failed to load the project configuration")

    domain_cfg = mcp_context._find_domain(config, name)
    if domain_cfg is not None:
        return {
            "domain": name,
            "name": name,
            "description": domain_cfg.description,
            "sources": domain_cfg.sources,
            "topics": domain_cfg.topics,
            "active": domain_cfg.active,
            "created": False,
        }

    from autoinfo.config import DomainConfig

    new_domain = DomainConfig(name=name, description=description or "", active=True)
    config.domains.append(new_domain)
    mcp_context._save_config(config)
    return {
        "domain": name,
        "name": name,
        "description": description or "",
        "sources": [],
        "topics": [],
        "active": True,
        "created": True,
    }


def _handle_remove_domain(name: str, confirm: bool = True, actor: str = "agent") -> dict[str, Any]:
    """Remove a domain configuration. Preserves all collected data on disk."""
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

    domain_cfg = mcp_context._find_domain(config, name)
    if domain_cfg is None:
        return error_response(
            code=ErrorCode.DOMAIN_NOT_FOUND,
            message=f"Domain '{name}' is not configured. Use add_domain(name='{name}') to create it.",
            actionable=True,
        )

    config.domains.remove(domain_cfg)
    mcp_context._save_config(config)
    return {"removed": True, "domain": name}


def _handle_get_domain_config(name: str) -> dict[str, Any]:
    """Return full domain config including sources, topics, extract_fields."""
    try:
        config = mcp_context._load_config()
    except Exception as exc:
        return mcp_context._error_from_exc(exc, "Failed to load the project configuration")

    domain_cfg = mcp_context._find_domain(config, name)
    if domain_cfg is None:
        return error_response(
            code=ErrorCode.DOMAIN_NOT_FOUND,
            message=f"Domain '{name}' is not configured. Use add_domain(name='{name}') to create it.",
            actionable=True,
        )

    sources = [
        {
            "name": s.name,
            "type": s.type,
            "url": s.url,
            "quality_tier": s.quality_tier,
            "tos_classification": s.tos_classification,
            "requires_key": s.requires_key,
        }
        for s in domain_cfg.sources
    ]
    topics = [
        {
            "name": t.name,
            "keywords": t.keywords,
            "group": t.group,
            "relevance_threshold": t.relevance_threshold,
        }
        for t in domain_cfg.topics
    ]

    return {
        "domain": domain_cfg.name,
        "active": domain_cfg.active,
        "search_mode": domain_cfg.search_mode,
        "extract_fields": domain_cfg.extract_fields,
        "sources": sources,
        "source_count": len(sources),
        "topics": topics,
        "topic_count": len(topics),
    }
