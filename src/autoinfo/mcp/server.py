"""MCP server — exposes AutoInfo capabilities as MCP tools over stdio.

This is the primary agent-facing interface for AutoInfo. It exposes 149 tools
across 35 categories — the full catalog lives in the README "MCP Tools" table
and is discoverable at runtime via ``list_tools()``.  ``get_tool_count()``
returns the live count.

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
import base64
import concurrent.futures
import json
import os
import sqlite3
import uuid
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, cast

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from autoinfo import __version__
from autoinfo.cli.doctor import calculate_health_score
from autoinfo.config import (
    SOURCE_KEY_ENV_VARS,
    ConfigNotFoundError,
)
from autoinfo.kb import is_director
from autoinfo.keywords import keyword_suggestion_system_prompt
from autoinfo.llm import call_with_fallback
from autoinfo.mcp import context as mcp_context
from autoinfo.mcp.errors import ErrorCode, error_response, success_response

# ---------------------------------------------------------------------------
# Config I/O helpers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Job state persistence (SQLite-backed, survives server restarts)
# ---------------------------------------------------------------------------

# Reuse the same autoinfo.db that KBStore uses.
# KBStore places it at ``Path("knowledge").resolve().parent / "autoinfo.db"``,
# which resolves to ``<cwd>/autoinfo.db`` when running from the project root.


# ---------------------------------------------------------------------------
# Tool implementations
#
# These are plain (sync) functions so they can be tested without an async
# test harness.  The ``call_tool`` handler wraps them in ``TextContent``.
# ---------------------------------------------------------------------------


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
    return success_response(
        {
            "status": "ok",
            "version": __version__,
            "tools_count": len([name for name in globals() if name.startswith("_handle_")]),
        }
    )


def _handle_get_tool_count() -> dict[str, Any]:
    """Return the number of registered MCP tools."""
    return {
        "tools_count": len([name for name in globals() if name.startswith("_handle_")]),
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
    result["phase"] = _detect_phase(result, config_path, collections_dir, knowledge_dir)

    return _canonicalize(result)


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
            _save_job_state(
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
                total_found = result.get("total_found", 0) if isinstance(result, dict) else 0
                errors = result.get("errors", 0) if isinstance(result, dict) else 0
                _save_job_state(
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
                _save_job_state(
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
    if _find_domain(cfg, domain) is None:
        return error_response(
            ErrorCode.DOMAIN_NOT_FOUND,
            f"Domain '{domain}' is not configured. Use add_domain(name='{domain}') to create it.",
            actionable=True,
        )

    job_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc).isoformat()
    _save_job_state(
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
        total_found = result.get("total_found", 0) if isinstance(result, dict) else 0
        errors = result.get("errors", 0) if isinstance(result, dict) else 0
        _save_job_state(
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
        return _canonicalize(result)
    except Exception as exc:
        _save_job_state(
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
        return _error_from_exc(exc, "Collection failed", code=ErrorCode.COLLECTION_FAILED)


def _handle_get_collection_progress(domain: str = "", job_id: str = "") -> dict[str, Any]:
    """Return current collection progress. Supports lookup by domain or job_id."""
    if job_id:
        state = _load_job_state(job_id)
        if state:
            is_complete = state.get("status") in ("completed", "error")
            return {"job_id": job_id, **state, "is_complete": is_complete}
        return {"job_id": job_id, "status": "not_found", "is_complete": False}
    if domain:
        state = _load_latest_domain_state(domain, "collection")
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
                meta = _safe_json_load(latest["metadata"])
                results[dom] = {
                    "status": latest["status"],
                    "progress_pct": latest["progress_pct"],
                    "created_at": latest["created_at"],
                    "updated_at": latest["updated_at"],
                    **meta,
                }
        return {"domains": results, "count": len(results)}

    return _canonicalize(_with_job_db(_read_all))


def _handle_get_collection_status(domain: str) -> dict[str, Any]:
    """Return full collection results for *domain* (last run)."""
    state = _load_latest_domain_state(domain, "collection")
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
    _save_job_state(
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
            _save_job_state(
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
        _save_job_state(
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
        return _canonicalize(result_dict)
    except Exception as exc:
        _save_job_state(
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
        return _error_from_exc(exc, "Processing failed", code=ErrorCode.PROCESSING_FAILED)


def _handle_get_processing_progress(domain: str = "", job_id: str = "") -> dict[str, Any]:
    """Return processing progress. Supports lookup by domain or job_id."""
    if job_id:
        state = _load_job_state(job_id)
        if state:
            is_complete = state.get("status") in ("completed", "error")
            return {"job_id": job_id, **state, "is_complete": is_complete}
        return {"job_id": job_id, "status": "not_found", "is_complete": False}
    if domain:
        from autoinfo.process import get_processing_progress

        return _canonicalize(get_processing_progress(domain=domain))
    return {"status": "idle", "is_complete": True}


# ---------------------------------------------------------------------------
# Discovery tools
# ---------------------------------------------------------------------------


def _handle_list_domains() -> dict[str, Any]:
    """List all configured domains with source/topic counts."""
    try:
        config = mcp_context._load_config()
    except Exception as exc:
        return _error_from_exc(exc, "Failed to load the project configuration")

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


# -- Platform metadata (static) -------------------------------------------

# Curated metadata for well-known source types; anything missing from this
# map still gets advertised via ``list_available_platforms`` with a default
# entry so PLATFORMS always mirrors VALID_SOURCE_TYPES.


# ---------------------------------------------------------------------------
# Source key requirements (D4: requirement awareness at onboarding)
# ---------------------------------------------------------------------------

# Canonical env vars per source type live in
# ``autoinfo.config.SOURCE_KEY_ENV_VARS`` — the single source of truth
# shared with ``alerts.py`` (B3 credential-missing detection) so the two
# key-maps can never drift apart.  Mirrors the collector contract:
# handlers with ``requires_key() -> True`` (ap_api, reuters_mcp, unpaywall,
# youtube) plus the collect-time key guards (nyt, spotify, quandl, kaggle,
# core, email, email_imap).  Drives the missing-key detection behind
# ``init_project`` next_steps and the ``test_source`` key warning.

# Source settings keys that carry a credential directly, satisfying the
# requirement without any env var.


def _handle_list_available_platforms() -> dict[str, Any]:
    """List all supported source platform types with descriptions."""
    return {"platforms": PLATFORMS}


def _handle_activate_domain(name: str) -> dict[str, Any]:
    """Activate a domain (set domain.active = True)."""
    try:
        config = mcp_context._load_config()
    except Exception as exc:
        return _error_from_exc(exc, "Failed to load the project configuration")

    domain_cfg = _find_domain(config, name)
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
        return _error_from_exc(exc, "Failed to load the project configuration")

    domain_cfg = _find_domain(config, name)
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
        return _error_from_exc(exc, "Failed to load the project configuration")

    domain_cfg = _find_domain(config, name)
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
        return _error_from_exc(exc, "Failed to load the project configuration")

    domain_cfg = _find_domain(config, name)
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


def _handle_add_domain(name: str, description: str = "") -> dict[str, Any]:
    """Create a new domain configuration (idempotent — returns existing config if domain already exists)."""
    try:
        config = mcp_context._load_config()
    except Exception as exc:
        return _error_from_exc(exc, "Failed to load the project configuration")

    domain_cfg = _find_domain(config, name)
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


def _handle_get_domain_schema(domain: str) -> dict[str, Any]:
    """Return the schema / structure for a given domain."""
    try:
        config = mcp_context._load_config()
    except Exception as exc:
        return _error_from_exc(exc, "Failed to load the project configuration")

    domain_cfg = _find_domain(config, domain)
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
        return _error_from_exc(exc, "Failed to load the project configuration")

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
        return _canonicalize(get_effective_llm_config(task=task))
    except Exception as exc:
        return _error_from_exc(exc, "Failed to resolve the effective LLM configuration")


# ---------------------------------------------------------------------------
# Source management tools
# ---------------------------------------------------------------------------


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
    type_error = _validate_source_type(type)
    if type_error:
        return error_response(
            code=ErrorCode.VALIDATION_ERROR,
            message=type_error,
            actionable=True,
        )

    url_error = _validate_url(url, source_type=type)
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
        return _error_from_exc(exc, "Failed to load the project configuration")

    domain_cfg = _find_domain(config, domain)
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
            return _canonicalize(dup_result)

    # Determine next quality_tier based on type
    quality_tier = 1 if type in ("api", "rss") else 2
    _TIER_TOS_MAP = {1: "open", 2: "licensed", 3: "restricted", 4: "sensitive"}
    tos_classification = _TIER_TOS_MAP.get(quality_tier, "open")

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

    return _canonicalize(result)


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
                    **_error_from_exc(exc, "Failed to add sources"),
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
        return _error_from_exc(exc, "Failed to load the project configuration")

    parts = source_id.split(":", 1)
    if len(parts) != 2:
        return error_response(
            code=ErrorCode.INVALID_SOURCE_ID,
            message="source_id must be in format 'domain:name'",
            actionable=True,
        )
    domain_name, source_name = parts

    domain_cfg = _find_domain(config, domain_name)
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
    type_error = _validate_source_type(type)
    if type_error:
        return error_response(
            code=ErrorCode.VALIDATION_ERROR,
            message=type_error,
            actionable=True,
        )
    url_error = _validate_url(url, source_type=type)
    if url_error:
        return error_response(
            code=ErrorCode.VALIDATION_ERROR,
            message=url_error,
            actionable=True,
        )
    key_status = _source_key_status(type)
    key_missing_hint = ""
    if key_status["key_required"] and not key_status["key_configured"]:
        key_missing_hint = (
            f" Source type '{type}' requires an API key ({', '.join(key_status['missing_env_vars'])}), "
            f"which is not configured; collection may return no items. See {_REQUIRED_KEYS_DOCS_REF}."
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
        suggested_fields = _suggest_extract_fields(type)

        result: dict[str, Any] = {
            "reachable": resp.status_code < 500,
            "status_code": resp.status_code,
            "content_type": content_type_header,
            "content_preview": content_preview,
            "size_kb": round(size_kb, 1),
            "format": _infer_format(content_type_header, content_preview),
            "suggested_extract_fields": suggested_fields,
            "key_required": key_status["key_required"],
            "key_configured": key_status["key_configured"],
        }
        if key_missing_hint:
            result["warning"] = key_missing_hint.strip()
        return _canonicalize(result)
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
        return _error_from_exc(exc, "Failed to load the project configuration")

    domain_cfg = _find_domain(config, domain)
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


# ---------------------------------------------------------------------------
# Topic management tools
# ---------------------------------------------------------------------------


def _handle_add_topic(
    domain: str,
    name: str,
    keywords: list[str] | None = None,
) -> dict[str, Any]:
    """Add a topic to a domain."""
    try:
        config = mcp_context._load_config()
    except Exception as exc:
        return _error_from_exc(exc, "Failed to load the project configuration")

    domain_cfg = _find_domain(config, domain)
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
        return _error_from_exc(exc, "Failed to load the project configuration")

    domain_cfg = _find_domain(config, domain)
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
        return _error_from_exc(exc, "Failed to load the project configuration")

    domain_cfg = _find_domain(config, domain)
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
        return _error_from_exc(exc, "Failed to load the project configuration")

    domain_cfg = _find_domain(config, domain)
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


# ---------------------------------------------------------------------------
# Topic group management tools
# ---------------------------------------------------------------------------


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
        return _error_from_exc(exc, "Failed to load the project configuration")

    domain_cfg = _find_domain(config, domain)
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
        return _error_from_exc(exc, "Failed to load the project configuration")

    domain_cfg = _find_domain(config, domain)
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


# ---------------------------------------------------------------------------
# Keywords management tools (approve / reject / suggest)
# ---------------------------------------------------------------------------


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
        logger.exception("Keyword suggestion failed")
        return _error_from_exc(exc, "Keyword suggestion failed")


# ---------------------------------------------------------------------------
# Custom extraction tools
# ---------------------------------------------------------------------------


def _handle_extract_fields(content_id: str, schema: list[str]) -> dict[str, Any]:
    """On-demand re-extraction with custom schema.

    Retrieves the KB entry for *content_id*, reconstructs an :class:`Item`
    from its stored content, and runs LLM extraction with the given *schema*.
    This does **not** persist the result — it is a one-off re-extraction.
    """
    from autoinfo.kb import KBStore
    from autoinfo.llm import LLMExtractor
    from autoinfo.models import Item

    store = KBStore()
    entry = store.get_entry(content_id)
    if entry is None:
        return error_response(
            code=ErrorCode.NOT_FOUND,
            message=f"Entry '{content_id}' not found",
            actionable=True,
        )

    # Reconstruct a minimal Item from the KB entry's stored content
    item = Item(
        id=content_id,
        source_name=entry.get("source_platform", ""),
        source_type=entry.get("source_type", ""),
        source_url=entry.get("source_url", ""),
        title=entry.get("title", ""),
        content=entry.get("content", ""),
        collected_at=entry.get("collected_at", ""),
        domain=entry.get("domain", ""),
    )

    extractor = LLMExtractor()
    result = extractor.extract(item, schema=schema)

    return {
        "content_id": content_id,
        "tl_dr": result.tl_dr,
        "key_points": result.key_points,
        "entities": result.entities,
        "relevance_score": result.relevance_score,
        "custom_fields": result.custom_fields,
    }


def _handle_get_extraction(content_id: str) -> dict[str, Any]:
    """Return what was extracted for a KB entry.

    Reads the Markdown frontmatter to retrieve ``extracted_fields`` (populated
    when custom extraction fields were used during processing).
    """
    from autoinfo.kb import KBStore

    store = KBStore()
    entry = store.get_entry(content_id)
    if entry is None:
        return error_response(
            code=ErrorCode.NOT_FOUND,
            message=f"Entry '{content_id}' not found",
            actionable=True,
        )

    # Parse the Markdown frontmatter for extracted_fields
    file_path = entry.get("file_path", "")
    extracted_fields: dict[str, Any] = {}
    if file_path:
        fp = Path(file_path)
        if fp.is_file():
            raw = fp.read_text(encoding="utf-8")
            if raw.startswith("---"):
                end_idx = raw.find("---", 3)
                if end_idx != -1:
                    fm_raw = raw[3:end_idx]
                    import yaml  # noqa: PLC0415 — deferred import

                    fm = yaml.safe_load(fm_raw) or {}
                    extracted_fields = fm.get("extracted_fields", {})

    return {
        "content_id": content_id,
        "title": entry.get("title", ""),
        "summary": entry.get("summary", ""),
        "relevance_score": entry.get("relevance_score", 0),
        "dedup_status": entry.get("dedup_status", "unknown"),
        "quality_tier": entry.get("quality_tier", 1),
        "extracted_fields": extracted_fields,
    }


def _handle_list_output_templates(domain: str = "", user_id: str | None = None) -> dict[str, Any]:
    """List available output templates for a domain, optionally filtered by user tier.

    When *user_id* is provided, templates are filtered so that only those
    whose ``access_level`` is accessible to the user are returned.
    When *user_id* is ``None``, all templates are returned (backward compatible).
    """
    from autoinfo.billing import check_access
    from autoinfo.output import list_output_templates as _list_output_templates

    result = _list_output_templates(domain=domain)
    templates: list[dict[str, Any]] = result["templates"]

    if user_id is not None:
        filtered: list[dict[str, Any]] = []
        for t in templates:
            access = check_access(user_id, t["access_level"])
            if access["allowed"]:
                filtered.append(t)
        result["templates"] = filtered
        result["count"] = len(filtered)

    return _canonicalize(result)


def _handle_generate_digest(
    domain: str,
    period: str = "weekly",
    format: str = "markdown",
    custom_instructions: str = "",
    target_audience: str = "",
    include_stale: bool = False,
    recipients: list[str] | None = None,
    user_id: str = "",
    max_items: int = 0,
    product: str = "",
    language: str = "",
    ref_limit: int | None = None,
    persist: bool = False,
) -> dict[str, Any]:
    """Generate a digest of KB entries for *domain* over the given *period*.

    Dispatches to :func:`autoinfo.output.generate_digest`.
    """
    from datetime import date, timedelta

    from autoinfo.kb import KBStore
    from autoinfo.output import generate_digest as _generate_digest
    from autoinfo.output.free_tier import FreeTierLimitError

    product_template = None
    if product:
        from autoinfo.output import PRODUCT_TEMPLATES

        _product_row = next(
            (row for row in PRODUCT_TEMPLATES if row["name"] == product),
            None,
        )
        if _product_row is None:
            _valid = ", ".join(sorted(row["name"] for row in PRODUCT_TEMPLATES))
            return error_response(
                code=ErrorCode.VALIDATION_ERROR,
                message=f"Unknown product '{product}'. Valid products: {_valid}",
                actionable=True,
            )
        product_template = _product_row["template"]

    _period_days = {"daily": 1, "weekly": 7, "monthly": 30}
    _days = _period_days.get(period, 7)
    _date_from = (date.today() - timedelta(days=_days)).isoformat()
    _store = KBStore()
    _preview = _store.list_entries(domain=domain, date_from=_date_from, limit=1)
    if not _preview:
        # generate_digest relaxes the date filter to the full domain set when
        # no entries fall in the window (data-staleness fallback).  Match that
        # so the preview gate never suppresses content the generator would
        # produce (issue #10).
        _preview = _store.list_entries(domain=domain, limit=1)
    if not _preview:
        return success_response(
            {
                "domain": domain,
                "format": format,
                "period": period,
                "status": "noop",
                "content": "",
                "message": f"No entries found for domain '{domain}' in the requested period. Run collect_sources() + process_collection() first.",
            }
        )

    try:
        result = _generate_digest(
            domain=domain,
            period=period,
            format=format,
            custom_instructions=custom_instructions,
            target_audience=target_audience,
            include_stale=include_stale,
            recipients=recipients,
            user_id=user_id,
            max_items=max_items,
            product_template=product_template,
            language=language,
            ref_limit=ref_limit,
        )
        if format in ("json", "agent"):
            # Parse JSON string back to dict for structured MCP response
            import json as _json

            _parsed = _json.loads(_output_text(result))
            return _maybe_persist_output(
                {"success": True, "format": format, "content": _parsed},
                persist,
                domain,
                "digest",
                format,
                _parsed,
            )
        if format == "audio":
            return _maybe_persist_output(
                {
                    "success": True,
                    "format": "audio",
                    "content_type": "audio/mp3",
                    "encoding": "base64",
                    "content": result,
                },
                persist,
                domain,
                "digest",
                "audio",
                result,
            )
        if format == "video":
            # _render_video_scaffold returns a JSON status blob with video_path.
            import json as _json2

            try:
                parsed = _json2.loads(_output_text(result))
            except (ValueError, TypeError):
                parsed = {"status": "ok", "video_path": result}
            return _maybe_persist_output(
                {"success": True, "format": "video", **parsed},
                persist,
                domain,
                "digest",
                "video",
                result,
            )
        if format in ("epub", "audiobook"):
            return _maybe_persist_output(
                {
                    "success": True,
                    "format": format,
                    "content_type": ("application/epub+zip" if format == "epub" else "audio/mpeg"),
                    "encoding": "base64",
                    "content": result,
                },
                persist,
                domain,
                "digest",
                format,
                result,
            )
        return _maybe_persist_output(
            {"success": True, "format": format, "content": result},
            persist,
            domain,
            "digest",
            format,
            result,
        )
    except FreeTierLimitError as exc:
        # Named free-tier user over quota — unified FREE_TIER_LIMIT envelope.
        error_detail = exc.to_envelope()["error"]
        return error_response(
            code=error_detail["code"],
            message=error_detail["message"],
            actionable=error_detail["actionable"],
        )
    except ValueError as exc:
        return _error_from_exc(exc, "Digest generation failed", code=ErrorCode.VALIDATION_ERROR)
    except Exception as exc:
        logger.exception("Digest generation failed for domain '%s'", domain)
        return _error_from_exc(exc, "Digest generation failed")


def _handle_generate_report(
    domain: str,
    format: str = "markdown",
    period: str = "monthly",
    custom_instructions: str = "",
    target_audience: str = "",
    user_id: str = "",
    report_type: str = "standard",
    product: str = "",
    language: str = "",
    ref_limit: int | None = None,
    persist: bool = False,
) -> dict[str, Any]:
    """Generate a structured report for *domain* over the given *period*.

    Dispatches to :func:`autoinfo.output.generate_report`.
    """
    from datetime import date, timedelta

    from autoinfo.kb import KBStore
    from autoinfo.output import generate_report as _generate_report
    from autoinfo.output import is_no_data_product as _is_no_data_product
    from autoinfo.output.free_tier import FreeTierLimitError

    product_template = None
    if product:
        from autoinfo.output import PRODUCT_TEMPLATES

        _product_row = next(
            (row for row in PRODUCT_TEMPLATES if row["name"] == product),
            None,
        )
        if _product_row is None:
            _valid = ", ".join(sorted(row["name"] for row in PRODUCT_TEMPLATES))
            return error_response(
                code=ErrorCode.VALIDATION_ERROR,
                message=f"Unknown product '{product}'. Valid products: {_valid}",
                actionable=True,
            )
        product_template = _product_row["template"]
    elif report_type == "column":
        from autoinfo.output import PRODUCT_TEMPLATES

        product_template = next(
            (row["template"] for row in PRODUCT_TEMPLATES if row["name"] == "column"),
            None,
        )
    _period_days = {"daily": 1, "weekly": 7, "monthly": 30}
    _days = _period_days.get(period, 7)
    _date_from = (date.today() - timedelta(days=_days)).isoformat()
    _store = KBStore()
    _preview = _store.list_entries(domain=domain, date_from=_date_from, limit=1)
    if not _preview:
        # generate_report relaxes the date filter to the full domain set when
        # no entries fall in the window.  Match that so the preview gate never
        # suppresses content the generator would produce (issue #10).
        _preview = _store.list_entries(domain=domain, limit=1)
    if not _preview:
        return success_response(
            {
                "domain": domain,
                "format": format,
                "period": period,
                "status": "noop",
                "content": "",
                "message": f"No entries found for domain '{domain}' in the requested period. Run collect_sources() + process_collection() first.",
            }
        )

    try:
        # Persist under the spec product name so matrix evidence resolves
        # (column was persisted as report-markdown-* and never counted for
        # the column:markdown cell — issue #229).
        _persist_product = "column" if report_type == "column" else "report"
        result = _generate_report(
            domain=domain,
            format=format,
            period=period,
            custom_instructions=custom_instructions,
            target_audience=target_audience,
            user_id=user_id,
            report_type=report_type,
            product_template=product_template,
            language=language,
            ref_limit=ref_limit,
        )
        if _is_no_data_product(result, format):
            return success_response(
                {
                    "domain": domain,
                    "format": format,
                    "period": period,
                    "status": "noop",
                    "content": "",
                    "message": (
                        f"No curated entries for domain '{domain}' produced a "
                        "deliverable report; nothing was written. Run "
                        "collect_sources() + process_collection() first."
                    ),
                }
            )
        if format in ("json", "agent"):
            import json as _json

            parsed = _json.loads(_output_text(result))
            return _maybe_persist_output(
                {
                    "success": True,
                    "domain": domain,
                    "format": format,
                    "period": period,
                    "content": parsed,
                },
                persist,
                domain,
                _persist_product,
                format,
                parsed,
            )
        if format == "audio":
            return _maybe_persist_output(
                {
                    "success": True,
                    "domain": domain,
                    "format": "audio",
                    "period": period,
                    "content_type": "audio/mp3",
                    "encoding": "base64",
                    "content": result,
                },
                persist,
                domain,
                _persist_product,
                "audio",
                result,
            )
        if format == "video":
            import json as _json3

            try:
                parsed = _json3.loads(_output_text(result))
            except (ValueError, TypeError):
                parsed = {"status": "ok", "video_path": result}
            content = result
            if isinstance(result, str) and os.path.isfile(result):
                # generate_video returns an MP4 file path; persist expects
                # the same base64 payload shape as audio (#254).
                content = base64.b64encode(Path(result).read_bytes()).decode("ascii")
                parsed.setdefault("encoding", "base64")
            return _maybe_persist_output(
                {
                    "success": True,
                    "domain": domain,
                    "format": "video",
                    "period": period,
                    **parsed,
                },
                persist,
                domain,
                _persist_product,
                "video",
                content,
            )
        if format in ("epub", "audiobook"):
            return _maybe_persist_output(
                {
                    "success": True,
                    "domain": domain,
                    "format": format,
                    "period": period,
                    "content_type": ("application/epub+zip" if format == "epub" else "audio/mpeg"),
                    "encoding": "base64",
                    "content": result,
                },
                persist,
                domain,
                _persist_product,
                format,
                result,
            )
        return _maybe_persist_output(
            {
                "success": True,
                "domain": domain,
                "format": format,
                "period": period,
                "content": result,
            },
            persist,
            domain,
            _persist_product,
            format,
            result,
        )
    except FreeTierLimitError as exc:
        error_detail = exc.to_envelope()["error"]
        return error_response(
            code=error_detail["code"],
            message=error_detail["message"],
            actionable=error_detail["actionable"],
        )
    except ValueError as exc:
        return _error_from_exc(exc, "Report generation failed", code=ErrorCode.VALIDATION_ERROR)
    except Exception as exc:
        logger.exception("Report generation failed for domain '%s'", domain)
        return _error_from_exc(exc, "Report generation failed")


def _handle_generate_cross_domain_report(
    domains: list[str],
    format: str = "markdown",
    period: str = "monthly",
    target_audience: str = "",
    report_type: str = "standard",
    user_id: str = "",
    language: str = "",
    persist: bool = False,
) -> dict[str, Any]:
    """Generate a synthesis report across multiple domains.

    Delegates to :func:`autoinfo.output.generate_report` with the
    ``domains`` parameter, using the first domain as primary for
    backward-compatible metadata.

    Parameters
    ----------
    user_id:
        Optional end-user ID forwarded to ``generate_report`` so the
        user's stored ``content_preference`` is honored.  Empty by
        default (no preference lookup).
    """
    from autoinfo.output import generate_report as _generate_report
    from autoinfo.output.free_tier import FreeTierLimitError

    # Validate at least 2 domains
    if not isinstance(domains, list) or len(domains) < 2:
        return error_response(
            code=ErrorCode.VALIDATION_ERROR,
            message="At least 2 domains are required for cross-domain report generation. Provide a list of two or more active domain names.",
            actionable=True,
        )

    # Validate all domains exist
    try:
        config = mcp_context._load_config()
    except FileNotFoundError:
        return error_response(
            code=ErrorCode.VALIDATION_ERROR,
            message="No project configuration found.  Run `init_project` first to set up at least one domain. See docs/dev/director-user-guide.md for setup instructions.",
            actionable=True,
        )
    except Exception as exc:
        return _error_from_exc(exc, "Cross-domain report generation failed")
    valid_names = {d.name for d in config.domains}
    invalid = [d for d in domains if d not in valid_names]
    if invalid:
        return error_response(
            code=ErrorCode.VALIDATION_ERROR,
            message=f"Unknown domain(s): {', '.join(invalid)}. Valid domains: {', '.join(sorted(valid_names))}",
            actionable=True,
        )

    try:
        result = _generate_report(
            domain=domains[0],
            domains=domains,
            format=format,
            period=period,
            target_audience=target_audience,
            report_type=report_type,
            user_id=user_id,
            language=language,
        )
        if format in ("json", "agent"):
            import json as _json

            parsed = _json.loads(_output_text(result))
            return _maybe_persist_output(
                {
                    "success": True,
                    "domain": domains[0],
                    "domains": domains,
                    "format": format,
                    "period": period,
                    "content": parsed,
                },
                persist,
                domains[0],
                "report",
                format,
                parsed,
            )
        if format == "audio":
            return _maybe_persist_output(
                {
                    "success": True,
                    "domain": domains[0],
                    "domains": domains,
                    "format": "audio",
                    "period": period,
                    "content_type": "audio/mp3",
                    "encoding": "base64",
                    "content": result,
                },
                persist,
                domains[0],
                "report",
                "audio",
                result,
            )
        if format == "video":
            import json as _json4

            try:
                parsed = _json4.loads(_output_text(result))
            except (ValueError, TypeError):
                parsed = {"status": "ok", "video_path": result}
            return _maybe_persist_output(
                {
                    "success": True,
                    "domain": domains[0],
                    "domains": domains,
                    "format": "video",
                    "period": period,
                    **parsed,
                },
                persist,
                domains[0],
                "report",
                "video",
                result,
            )
        if format in ("epub", "audiobook"):
            return _maybe_persist_output(
                {
                    "success": True,
                    "domain": domains[0],
                    "domains": domains,
                    "format": format,
                    "period": period,
                    "content_type": ("application/epub+zip" if format == "epub" else "audio/mpeg"),
                    "encoding": "base64",
                    "content": result,
                },
                persist,
                domains[0],
                "report",
                format,
                result,
            )
        return _maybe_persist_output(
            {
                "success": True,
                "domain": domains[0],
                "domains": domains,
                "format": format,
                "period": period,
                "content": result,
            },
            persist,
            domains[0],
            "report",
            format,
            result,
        )
    except FreeTierLimitError as exc:
        error_detail = exc.to_envelope()["error"]
        return error_response(
            code=error_detail["code"],
            message=error_detail["message"],
            actionable=error_detail["actionable"],
        )
    except ValueError as exc:
        return _error_from_exc(
            exc, "Cross-domain report generation failed", code=ErrorCode.VALIDATION_ERROR
        )
    except Exception as exc:
        logger.exception(
            "Cross-domain report generation failed for domains %s",
            domains,
        )
        return _error_from_exc(exc, "Cross-domain report generation failed")


def _handle_generate_tutorial(
    domain: str,
    topic: str | None = None,
    format: str = "markdown",
    custom_instructions: str = "",
    user_id: str = "",
    persist: bool = False,
) -> dict[str, Any]:
    """Generate a structured tutorial for *domain*.

    Thin wrapper around :func:`autoinfo.output.generate_tutorial`.

    Parameters
    ----------
    user_id:
        Optional end-user ID forwarded to ``generate_tutorial`` so the
        user's stored ``content_preference`` is honored.  Empty by
        default (no preference lookup).
    """
    from autoinfo.output import generate_tutorial as _generate_tutorial

    try:
        result = _generate_tutorial(
            domain=domain, format=format, custom_instructions=custom_instructions, user_id=user_id
        )
        if format == "agent":
            import json as _json

            return _maybe_persist_output(
                {
                    "success": True,
                    "format": format,
                    "domain": domain,
                    "topic": topic,
                    "content": _json.loads(_output_text(result)),
                },
                persist,
                domain,
                "tutorial",
                format,
                _json.loads(_output_text(result)),
            )
        return _maybe_persist_output(
            {
                "success": True,
                "format": format,
                "domain": domain,
                "topic": topic,
                "content": result,
            },
            persist,
            domain,
            "tutorial",
            format,
            result,
        )
    except ValueError as exc:
        return _error_from_exc(exc, "Tutorial generation failed", code=ErrorCode.VALIDATION_ERROR)
    except Exception as exc:
        logger.exception("Tutorial generation failed for domain '%s'", domain)
        return _error_from_exc(exc, "Tutorial generation failed")


def _handle_generate_presentation(
    domain: str,
    topic: str | None = None,
    slides: int = 10,
    format: str = "markdown",
    custom_instructions: str = "",
    user_id: str = "",
    persist: bool = False,
) -> dict[str, Any]:
    """Generate a slide-based presentation for *topic* within *domain*.

    Thin wrapper around :func:`autoinfo.output.generate_presentation`.

    Parameters
    ----------
    user_id:
        Optional end-user ID forwarded to ``generate_presentation`` so
        the user's stored ``content_preference`` is honored.  Empty by
        default (no preference lookup).
    """
    from autoinfo.output import generate_presentation as _generate_presentation

    try:
        topic_str = topic or ""
        result = _generate_presentation(
            domain=domain,
            topic=topic_str,
            slide_count=slides,
            format=format,
            custom_instructions=custom_instructions,
            user_id=user_id,
        )
        if format == "agent":
            import json as _json

            return _maybe_persist_output(
                {
                    "success": True,
                    "domain": domain,
                    "topic": topic,
                    "slides": slides,
                    "format": format,
                    "content": _json.loads(_output_text(result)),
                },
                persist,
                domain,
                "presentation",
                format,
                _json.loads(_output_text(result)),
            )
        return _maybe_persist_output(
            {
                "success": True,
                "domain": domain,
                "topic": topic,
                "slides": slides,
                "format": format,
                "content": result,
            },
            persist,
            domain,
            "presentation",
            format,
            result,
        )
    except ValueError as exc:
        return _error_from_exc(
            exc,
            "Presentation generation failed",
            code=ErrorCode.VALIDATION_ERROR,
        )
    except Exception as exc:
        logger.exception("Presentation generation failed for domain '%s'", domain)
        return _error_from_exc(exc, "Presentation generation failed")


def _handle_send_email_digest(
    domain: str,
    period: str = "weekly",
    user_id: str = "",
) -> dict[str, Any]:
    """Generate and send a digest via SMTP email.

    Dispatches to :func:`autoinfo.email_sender.send_digest`.
    Only sends when ``config.email.enabled == True``.

    Parameters
    ----------
    domain:
        Domain to generate the digest for.
    period:
        Digest period: ``"daily"``, ``"weekly"``, ``"monthly"``.
        Defaults to ``"weekly"``.
    user_id:
        Optional end-user ID forwarded to the email sender so the
        user's stored ``content_preference`` is honored.  Empty by
        default (no preference lookup).

    Returns
    -------
    dict
        ``{success, message, recipients, domain, period}``.
    """
    from autoinfo.email_sender import send_digest as _send_email

    try:
        config = mcp_context._load_config()
    except Exception as exc:
        return _error_from_exc(exc, "Failed to load the project configuration")

    if not config.email.enabled:
        return error_response(
            code=ErrorCode.EMAIL_NOT_ENABLED,
            message=(
                "Email delivery is not enabled. "
                "Set 'email.enabled: true' in .autoinfo/config.yaml "
                "and configure email.smtp_host, email.from_addr, "
                "and email.to_addrs."
            ),
            actionable=True,
        )

    try:
        result = _send_email(domain=domain, period=period, config=config, user_id=user_id)
        return _canonicalize(result)
    except RuntimeError as exc:
        return _error_from_exc(exc, "Email digest send failed", code=ErrorCode.EMAIL_SEND_FAILED)
    except Exception as exc:
        logger.exception("Email digest send failed for domain '%s'", domain)
        return _error_from_exc(exc, "Email digest send failed")


def _handle_localize_content(**kwargs: Any) -> dict[str, Any]:
    """Translate a KB entry or raw text via LLM.

    Dispatches to :func:`autoinfo.output.localize_content`.
    Supports both content_id mode (reads from KB, stores translation)
    and direct content mode (returns translated text only).

    Parameters match :func:`autoinfo.output.localize_content`.
    """
    from autoinfo.output import localize_content as _localize

    try:
        result = _localize(**kwargs)
        return _canonicalize(result)
    except ValueError as exc:
        return _error_from_exc(exc, "Localization failed", code=ErrorCode.VALIDATION_ERROR)
    except Exception as exc:
        logger.exception("Localization failed")
        return _error_from_exc(exc, "Localization failed")


# ---------------------------------------------------------------------------
# Export / Import (2)
# ---------------------------------------------------------------------------


def _handle_export_kb(
    domain: str,
    format: str = "markdown",
    scope: str = "domain",
    entry_ids: list[str] | None = None,
    output_path: str | None = None,
    base_url: str | None = None,
) -> dict[str, Any]:
    """Export knowledge base entries to specified format.

    Dispatches to :func:`autoinfo.output.export_kb`.

    Parameters
    ----------
    domain:
        Domain name (e.g. medical-research).
    format:
        Output format: ``"markdown"``, ``"json"``, ``"sqlite"``, ``"csv"``,
        ``"pdf"``, or ``"graphml"``.  Defaults to ``"markdown"``.
    scope:
        Export scope: ``"domain"`` (all entries in domain), ``"entry"``
        (specific entries by ID), or ``"collection"`` (collection-scoped).
        Defaults to ``"domain"``.
    entry_ids:
        Specific entry IDs to export (used when scope == ``"entry"``).
    output_path:
        Optional explicit output path.  When omitted, the file is written
        to the ``exports/`` directory with an auto-generated name.
    base_url:
        Site base URL required when ``format`` is ``"sitemap"`` (e.g.
        ``"https://your-site.example"``).  Ignored for other formats.

    Returns
    -------
    dict
        ``{format, path, entries_count, file_size_bytes, domain, success}``.
    """
    from autoinfo.output import export_kb as _export_kb

    try:
        collection_id: str | None = None
        if scope == "entry" and entry_ids:
            collection_id = entry_ids[0]
        elif scope == "collection":
            collection_id = "__all__"

        result = _export_kb(
            domain=domain,
            format=format,
            collection_id=collection_id,
            base_url=base_url,
        )

        file_path = result.get("path", "")
        if file_path and os.path.isfile(file_path):
            result["file_size_bytes"] = os.path.getsize(file_path)
        else:
            result["file_size_bytes"] = 0

        return _canonicalize(result)
    except ValueError as exc:
        return _error_from_exc(exc, "Export KB failed", code=ErrorCode.VALIDATION_ERROR)
    except Exception as exc:
        logger.exception("Export KB failed for domain '%s'", domain)
        return _error_from_exc(exc, "Export KB failed")


def _handle_import_kb(
    domain: str,
    format: str,
    data: str,
) -> dict[str, Any]:
    """Import entries or source suggestions into the KB.

    Dispatches to the appropriate handler in :mod:`autoinfo.importer`
    based on *format*.

    Parameters
    ----------
    domain:
        Target domain name (e.g. medical-research).
    format:
        Import format: ``"markdown"``, ``"json"``, ``"csv"``, or ``"opml"``.
    data:
        Raw content string to import (YAML+Markdown, JSON, CSV, or OPML XML).

    Returns
    -------
    dict
        For ``markdown`` / ``json`` / ``csv``::
            ``{domain, format, entries_imported, entries_failed, errors}``
        For ``opml``::
            ``{type: "source_list", suggestions, action_required, domain, format}``
    """
    from autoinfo.importer import import_kb as _import_kb

    try:
        result = _import_kb(domain=domain, format=format, data=data)
        return _canonicalize(result)
    except ValueError as exc:
        return _error_from_exc(exc, "Import KB failed", code=ErrorCode.VALIDATION_ERROR)
    except Exception as exc:
        logger.exception("Import KB failed for domain '%s'", domain)
        return _error_from_exc(exc, "Import KB failed")


# ---------------------------------------------------------------------------
# CEFR classification tool
# ---------------------------------------------------------------------------


def _handle_classify_cefr(text: str, lang: str = "en") -> dict[str, Any]:
    """Classify text into a CEFR level (A1-C2) using the configured LLM.

    Dispatches to :func:`autoinfo.cefr.classify_text`.

    Parameters
    ----------
    text:
        Text to classify.
    lang:
        Language code: ``"en"``, ``"zh"``, or ``"ja"`` (default ``"en"``).

    Returns
    -------
    dict
        ``{cefr_level, confidence, text_preview}``.
    """
    try:
        config = mcp_context._load_config()
        model_config: dict[str, Any] = {}
        if config.cefr.model:
            model_config["model"] = config.cefr.model
        elif config.llm.provider and config.llm.model:
            llm_model = config.llm.model
            if "/" not in llm_model:
                llm_model = f"{config.llm.provider}/{llm_model}"
            model_config["model"] = llm_model
        if config.llm.api_key:
            model_config["api_key"] = config.llm.api_key
        if config.llm.base_url:
            model_config["base_url"] = config.llm.base_url
    except Exception:
        model_config = {}

    from autoinfo.cefr import classify_text

    result = classify_text(text=text, lang=lang, model_config=model_config)
    text_preview = text[:200] + "..." if len(text) > 200 else text
    return {
        "cefr_level": result["cefr_level"],
        "confidence": result["confidence"],
        "text_preview": text_preview,
    }


def _handle_list_projects(status: str = "") -> dict[str, Any]:
    """List all configured projects with domain/source summaries."""
    try:
        config = mcp_context._load_config()
    except Exception as exc:
        return _error_from_exc(exc, "Failed to list projects")

    from autoinfo.config import get_config_path

    cfg_path = get_config_path()
    projects = [
        {
            "name": config.project.name if hasattr(config, "project") else "default",
            "config_path": str(cfg_path) if cfg_path else "",
            "domain_count": len([d for d in config.domains if d.active]),
            "total_sources": sum(len(d.sources) for d in config.domains if d.active),
            "total_topics": sum(len(d.topics) for d in config.domains if d.active),
            "created_at": (
                config.project.created_at
                if hasattr(config, "project") and hasattr(config.project, "created_at")
                else ""
            ),
            "llm_provider": config.llm.provider if hasattr(config, "llm") else "",
            "llm_model": config.llm.model if hasattr(config, "llm") else "",
            "status": "active",
        }
    ]

    if status:
        projects = [p for p in projects if p.get("status") == status]

    return {"projects": projects, "count": len(projects)}


def _handle_get_project_assets(type: str = "") -> dict[str, Any]:
    """Return project assets info — directories, db, exports."""
    assets: dict[str, Any] = {
        "collections_dir": {"exists": False, "path": ""},
        "knowledge_dir": {"exists": False, "path": ""},
        "database": {"exists": False, "path": ""},
        "exports_dir": {"exists": False, "path": ""},
        "config_dir": {"exists": False, "path": ""},
    }

    cwd = Path.cwd()
    collections_dir = cwd / "collections"
    knowledge_dir = cwd / "knowledge"
    db_path = cwd / "autoinfo.db"
    exports_dir = cwd / "exports"
    config_dir = cwd / ".autoinfo"

    assets["collections_dir"] = {
        "exists": collections_dir.is_dir(),
        "path": str(collections_dir),
        "item_count": len(list(collections_dir.rglob("*.json"))) if collections_dir.is_dir() else 0,
    }
    assets["knowledge_dir"] = {
        "exists": knowledge_dir.is_dir(),
        "path": str(knowledge_dir),
        "entry_count": len(list(knowledge_dir.rglob("*.md"))) if knowledge_dir.is_dir() else 0,
    }
    assets["database"] = {
        "exists": db_path.is_file(),
        "path": str(db_path),
        "size_bytes": db_path.stat().st_size if db_path.is_file() else 0,
    }
    assets["exports_dir"] = {
        "exists": exports_dir.is_dir(),
        "path": str(exports_dir),
        "file_count": len(list(exports_dir.iterdir())) if exports_dir.is_dir() else 0,
    }
    assets["config_dir"] = {
        "exists": config_dir.is_dir(),
        "path": str(config_dir),
    }

    if type:
        asset_types_map = {
            "collections": "collections_dir",
            "knowledge": "knowledge_dir",
            "database": "database",
            "exports": "exports_dir",
            "config": "config_dir",
        }
        key = asset_types_map.get(type)
        if key:
            return {key: assets[key]}

    return _canonicalize(assets)


def _handle_archive_project(reason: str = "", confirm: bool = False) -> dict[str, Any]:
    """Archive the current project (refuses unless published to 03-Wiki)."""
    if not confirm:
        return error_response(
            code=ErrorCode.CONFIRMATION_REQUIRED,
            message=(
                "This operation is destructive and requires confirmation. "
                "Pass confirm=True to proceed."
            ),
            actionable=True,
        )
    try:
        from autoinfo.kb import KBStore

        store = KBStore()
        wiki_count = store.index.count_entries()
        wiki_entries = store.index.list_entries_by_tier(
            domain="", tier="03-Wiki", limit=1, offset=0
        )
        has_published = len(wiki_entries) > 0
    except Exception:
        has_published = False

    if not has_published:
        return error_response(
            code=ErrorCode.NOT_PUBLISHED,
            message=(
                "Cannot archive project: no entries have been promoted to "
                "03-Wiki. Publish at least one Draft entry before archiving. "
                "Use create_kb_draft raw_ids=[...] title=... to create a Draft, "
                "then the human director can promote it to 03-Wiki."
            ),
            actionable=True,
        )

    return {
        "status": "refused_by_design",
        "message": (
            "Archive is a human-only operation. The agent can prepare a "
            "summary of the project but cannot perform the archive. "
            f"Reason provided: {reason or 'not specified'}"
        ),
        "actionable": False,
    }


def _handle_batch_run(
    domain: str,
    topic: str = "",
    limit: int = 20,
    model: str = "",
    resume_from: str = "",
) -> dict[str, Any]:
    """Run collect + process in sequence for a domain. Returns per-phase results.

    ``resume_from`` (R-A-01) resumes each phase from its persisted
    checkpoint: ``"auto"`` skips already-completed collection sources and
    already-processed items; ``"start"`` checkpoints a fresh run;
    ``"<source>"`` starts collection at that source.  Omitted → legacy run.
    """
    from datetime import timezone

    from autoinfo.collect import run_collection
    from autoinfo.process import ProcessResult, run_processing

    start_time = datetime.now(timezone.utc)
    phases: list[dict[str, Any]] = []

    collect_args: dict[str, Any] = {"domain": domain, "limit": limit}
    if topic:
        collect_args["topic"] = topic
    if resume_from:
        collect_args["resume_from"] = resume_from

    phase_start = datetime.now(timezone.utc)
    try:
        collected = run_collection(**collect_args)
        phase_duration = (datetime.now(timezone.utc) - phase_start).total_seconds()
        phases.append(
            {
                "phase": "collection",
                "status": "completed",
                "result": collected,
                "duration_s": round(phase_duration, 2),
            }
        )
    except Exception as exc:
        phase_duration = (datetime.now(timezone.utc) - phase_start).total_seconds()
        phases.append(
            {
                "phase": "collection",
                "status": "failed",
                "error": str(exc),
                "duration_s": round(phase_duration, 2),
            }
        )

    if phases[-1]["status"] == "completed":
        process_args: dict[str, Any] = {"domain": domain}
        if model:
            process_args["model"] = model
        if resume_from:
            process_args["resume_from"] = resume_from

        phase_start = datetime.now(timezone.utc)
        try:
            processed: ProcessResult = run_processing(**process_args)
            processed_dict = asdict(processed)
            phase_duration = (datetime.now(timezone.utc) - phase_start).total_seconds()
            phases.append(
                {
                    "phase": "processing",
                    "status": "completed",
                    "result": processed_dict,
                    "duration_s": round(phase_duration, 2),
                }
            )
        except Exception as exc:
            phase_duration = (datetime.now(timezone.utc) - phase_start).total_seconds()
            phases.append(
                {
                    "phase": "processing",
                    "status": "failed",
                    "error": str(exc),
                    "duration_s": round(phase_duration, 2),
                }
            )
    else:
        phases.append(
            {
                "phase": "processing",
                "status": "skipped",
                "reason": "collection failed",
            }
        )

    total_duration = (datetime.now(timezone.utc) - start_time).total_seconds()
    overall_success = all(p["status"] == "completed" for p in phases)

    return {
        "domain": domain,
        "topic": topic or "*",
        "phases": phases,
        "overall_success": overall_success,
        "total_duration_s": round(total_duration, 2),
    }


def _handle_get_feeds(
    domain: str,
    topic: str | None = None,
    source_type: str | None = None,
    since: str | None = None,
    limit: int = 50,
    offset: int = 0,
    format: str = "json",
) -> dict[str, Any]:
    """Return a paginated feed of KB entries for *domain*.

    Parameters
    ----------
    domain:
        Domain to query (required).
    topic:
        Optional filter by topic tag.
    source_type:
        Optional filter by source type (e.g. rss, api).
    since:
        Optional ISO date filter (collected_at >=).
    limit:
        Max items to return (default 50, max 200).
    offset:
        Number of items to skip for pagination (default 0).
    format:
        Output format: ``"json"`` (default) or ``"rss"``.
        ``"json"`` returns a paginated JSON envelope with ``{items, pagination}``.
        ``"rss"`` returns an RSS 2.0 XML feed.

    Returns
    -------
    dict
        For ``format="json"``: ``{domain, format, items, pagination}`` —
        structured JSON, not an opaque text payload.
        For ``format="rss"``: ``{domain, format, content, content_type,
        encoding, length, bytes, pagination}``.  ``content`` is the RSS 2.0
        XML string and the surrounding keys are its machine-readable metadata
        (T-S-09); ``content_type`` is ``application/rss+xml``.
    """
    from autoinfo.kb import KBStore

    limit = max(1, min(limit, 200))
    store = KBStore()

    # Fetch all entries for the domain with since filter at the DB level
    all_raw = store.list_all_entries(
        domain=domain,
        date_from=since,
        limit=10000,
        offset=0,
    )

    # Apply topic filter (tags are a JSON string in the DB)
    if topic:
        topic_lower = topic.strip().lower()
        filtered: list[dict[str, Any]] = []
        for entry in all_raw:
            tags = _parse_tags(entry)
            if any(t.lower() == topic_lower for t in tags):
                filtered.append(entry)
        all_raw = filtered

    # Apply source_type filter
    if source_type:
        st = source_type.strip().lower()
        all_raw = [e for e in all_raw if e.get("source_type", "").lower() == st]

    # Sort by collected_at DESC (newest first)
    all_raw.sort(key=lambda e: e.get("collected_at", "") or "", reverse=True)

    total = len(all_raw)

    # Slice for pagination
    page = all_raw[offset : offset + limit]

    # Determine next offset
    next_offset: int | None = offset + limit if offset + limit < total else None

    items = []
    for entry in page:
        items.append(
            {
                "id": entry.get("entry_id", ""),
                "title": entry.get("title", ""),
                "url": entry.get("source_url", ""),
                "source_type": entry.get("source_type", ""),
                "source_platform": entry.get("source_platform", ""),
                "collected_at": entry.get("collected_at", ""),
                "summary": entry.get("summary", ""),
                "relevance_score": entry.get("relevance_score", 0.0),
            }
        )

    if format == "rss":
        import xml.etree.ElementTree as ET  # noqa: PLC0415 — deferred import

        rss = ET.Element("rss", {"version": "2.0"})
        channel = ET.SubElement(rss, "channel")
        ET.SubElement(channel, "title").text = f"AutoInfo Feed — {domain}"
        ET.SubElement(channel, "description").text = f"Knowledge base feed for domain: {domain}"
        ET.SubElement(channel, "link").text = "https://autoinfo.local"
        ET.SubElement(channel, "lastBuildDate").text = items[0]["collected_at"] if items else ""

        for item in items:
            xml_item = ET.SubElement(channel, "item")
            ET.SubElement(xml_item, "guid", {"isPermaLink": "false"}).text = item["id"]
            ET.SubElement(xml_item, "title").text = item["title"] or "(untitled)"
            ET.SubElement(xml_item, "link").text = item["url"] or ""
            ET.SubElement(xml_item, "description").text = item["summary"] or ""
            if item["collected_at"]:
                ET.SubElement(xml_item, "pubDate").text = item["collected_at"]
            ET.SubElement(xml_item, "source", {"url": item["url"] or ""}).text = (
                item["source_type"] or ""
            )

        ET.indent(rss, space="  ")
        rss_content = ET.tostring(rss, encoding="unicode", xml_declaration=True)
        return {
            "domain": domain,
            **_text_payload_metadata(
                rss_content,
                format="rss",
                content_type="application/rss+xml; charset=utf-8",
            ),
            "content": rss_content,
            "pagination": {
                "total": total,
                "limit": limit,
                "offset": offset,
                "next": next_offset,
            },
        }

    return {
        "domain": domain,
        "format": "json",
        "items": items,
        "pagination": {
            "total": total,
            "limit": limit,
            "offset": offset,
            "next": next_offset,
        },
    }


def _handle_list_active_collections(domain: str = "") -> dict[str, Any]:
    """List active / in-progress collection runs."""
    from autoinfo.collect import list_active_collections as _list_active

    try:
        active = _list_active()
    except Exception as exc:
        return _error_from_exc(exc, "Failed to list active collections")

    if domain:
        active = [c for c in active if c.get("domain") == domain]

    return {
        "active_collections": active,
        "count": len(active),
    }


def _handle_get_config(section: str = "") -> dict[str, Any]:
    """Return the current configuration as a structured dict.

    Supports optional *section* filter: 'project', 'llm', 'domains'.
    Returns the full config when *section* is empty.
    """
    try:
        config = mcp_context._load_config()
    except Exception as exc:
        return _error_from_exc(exc, "Failed to load the project configuration")

    config_dict: dict[str, Any] = {}

    if section in ("", "project"):
        if hasattr(config, "project"):
            prj = config.project
            config_dict["project"] = {
                "name": prj.name if hasattr(prj, "name") else "",
                "created_at": prj.created_at if hasattr(prj, "created_at") else "",
            }

    if section in ("", "llm"):
        if hasattr(config, "llm"):
            llm = config.llm
            config_dict["llm"] = {
                "provider": llm.provider if hasattr(llm, "provider") else "",
                "model": llm.model if hasattr(llm, "model") else "",
                "api_key_configured": bool(
                    (llm.api_key if hasattr(llm, "api_key") else "")
                    or os.environ.get("AUTOINFO_LLM_API_KEY")
                ),
            }

    if section in ("", "domains"):
        domains_list = []
        if hasattr(config, "domains"):
            for d in config.domains:
                domains_list.append(
                    {
                        "name": d.name,
                        "active": d.active if hasattr(d, "active") else False,
                        "source_count": len(d.sources) if hasattr(d, "sources") else 0,
                        "topic_count": len(d.topics) if hasattr(d, "topics") else 0,
                    }
                )
        config_dict["domains"] = domains_list

    if section and section not in ("project", "llm", "domains"):
        return error_response(
            code=ErrorCode.INVALID_SECTION,
            message=f"Unknown config section '{section}'. Valid: project, llm, domains",
            actionable=True,
        )

    config_dict["config_path"] = str(mcp_context._config_path())

    return {"config": config_dict}


def _handle_get_channel_health(
    channel_name: str | None = None,
) -> list[dict[str, Any]]:
    """Return health status for all or a specific delivery channel."""
    from autoinfo.delivery import _CHANNEL_REGISTRY

    results: list[dict[str, Any]] = []
    if channel_name is not None:
        channel_cls = _CHANNEL_REGISTRY.get(channel_name)
        if channel_cls is None:
            return [
                {
                    "healthy": False,
                    "latency_ms": 0.0,
                    "error": f"unknown channel: {channel_name}",
                    "channel": channel_name,
                }
            ]
        instance = channel_cls()
        results.append(instance.health_check())
    else:
        for name, channel_cls in _CHANNEL_REGISTRY.items():
            try:
                instance = channel_cls()
                results.append(instance.health_check())
            except Exception as exc:
                results.append(
                    {"healthy": False, "latency_ms": 0.0, "error": str(exc), "channel": name}
                )
    return _canonicalize(results)


# ---------------------------------------------------------------------------
# Error response helper
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Agent Callback handlers (3)


# ---------------------------------------------------------------------------
# Agent Callback handlers (3)
# ---------------------------------------------------------------------------


def _handle_set_agent_callback(
    agent_url: str,
    events: list[str],
) -> dict[str, Any]:
    """Register a new agent callback URL for specified events."""
    from autoinfo.agent_callback import register_agent_callback

    try:
        callback_id = register_agent_callback(agent_url=agent_url, events=events)
        return {
            "callback_id": callback_id,
            "agent_url": agent_url,
            "events": events,
            "created": True,
        }
    except ValueError as exc:
        return _error_from_exc(exc, "set_agent_callback failed", code=ErrorCode.VALIDATION_ERROR)
    except Exception as exc:
        logger.exception("set_agent_callback failed")
        return _error_from_exc(exc, "set_agent_callback failed")


def _handle_list_agent_callbacks() -> dict[str, Any] | list[dict[str, Any]]:
    """List all registered agent callbacks."""
    from autoinfo.agent_callback import list_agent_callbacks

    try:
        return _canonicalize(list_agent_callbacks())
    except Exception as exc:
        logger.exception("list_agent_callbacks failed")
        return _error_from_exc(exc, "list_agent_callbacks failed")


def _handle_remove_agent_callback(callback_id: str) -> dict[str, Any]:
    """Remove a registered agent callback."""
    from autoinfo.agent_callback import remove_agent_callback

    try:
        removed = remove_agent_callback(callback_id)
        if removed:
            return {"callback_id": callback_id, "removed": True}
        return error_response(
            code=ErrorCode.NOT_FOUND,
            message=f"Callback '{callback_id}' not found",
            actionable=True,
        )
    except Exception as exc:
        logger.exception("remove_agent_callback failed")
        return _error_from_exc(exc, "remove_agent_callback failed")


# ---------------------------------------------------------------------------
# Recommendation (1)
# ---------------------------------------------------------------------------


def _handle_simplify_content(
    content: str,
    target_level: str,
    language: str = "en",
) -> dict[str, Any]:
    """Handle simplify_content MCP tool."""
    from autoinfo.output import simplify_text

    result = simplify_text(content, target_level, language)

    if target_level not in (frozenset({"A1", "A2", "B1", "B2", "C1"})):
        return error_response(
            code=ErrorCode.VALIDATION_ERROR,
            message=(f"Invalid target_level: '{target_level}'. Must be one of A1, A2, B1, B2, C1."),
            actionable=True,
        )

    error_msg = result.get("error")
    if error_msg and not result["verified"]:
        return success_response({**result, "warning": error_msg})

    return success_response(result)


# ---------------------------------------------------------------------------
# Validation (4)
# ---------------------------------------------------------------------------


def _handle_list_validation_scenarios() -> dict[str, Any]:
    """Handle list_validation_scenarios MCP tool."""
    from autoinfo.mcp.validation import list_scenarios

    return _canonicalize(list_scenarios())


async def _handle_run_validation_scenario(
    scenario: str,
    steps: list[int] | None = None,
    save_results: bool = False,
    timeout: float = 180.0,
) -> dict[str, Any]:
    """Handle run_validation_scenario MCP tool."""
    from autoinfo.mcp.validation import run_scenario, save_scenario_results

    async def _validation_dispatch(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        texts = await call_tool(name, arguments)
        return cast(dict[str, Any], json.loads(texts[0][0].text))

    try:
        result = await run_scenario(
            scenario,
            dispatch=_validation_dispatch,
            steps=steps,
            timeout=timeout,
        )
        if save_results:
            from autoinfo.output.run_report import (
                build_run_report,
                persist_run_report,
            )

            # ``or ""`` keeps this a ``str``: both consumers only test truthiness
            # (``save_scenario_results`` skips a falsy id; ``build_run_report``
            # raises on one), so an absent id behaved as "" already.
            session_id = result.get("session_id") or result.get("trace_id") or ""
            run_dir = save_scenario_results([result], session_id=session_id)
            result["saved_run"] = str(run_dir)
            report = build_run_report(session_id, [result], kind="single")
            result["report_path"] = str(persist_run_report(report))
        return result
    except ValueError as exc:
        return _error_from_exc(
            exc,
            "run_validation_scenario failed",
            code=ErrorCode.VALIDATION_ERROR,
        )


async def _handle_run_all_validation_scenarios(
    save_results: bool = True,
    timeout: float = 180.0,
) -> dict[str, Any]:
    """Handle run_all_validation_scenarios MCP tool (R-S-05).

    Runs the full live scenario library once and persists a single aggregate
    run (``run_type="suite"``) whose ``scenarios[]`` array carries every
    per-scenario result, so ``scripts/validation_report.py`` renders the whole
    suite from one run without external aggregation scripting.
    """
    from autoinfo.mcp.validation import run_all_scenarios

    async def _validation_dispatch(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        texts = await call_tool(name, arguments)
        return cast(dict[str, Any], json.loads(texts[0][0].text))

    try:
        return await run_all_scenarios(
            dispatch=_validation_dispatch,
            timeout=timeout,
            save=save_results,
        )
    except Exception as exc:  # noqa: BLE001 - typed envelope, never a silent pass
        return _error_from_exc(
            exc,
            "run_all_validation_scenarios failed",
            code=ErrorCode.VALIDATION_ERROR,
        )


def _handle_get_coverage_report() -> dict[str, Any]:
    """Handle get_coverage_report MCP tool (register T-A-02/T-A-03/T-A-07).

    Delegates to ``scripts/stage_user_coverage.py::build_report`` so the MCP
    surface and the CLI report are the same classification (one source of
    truth).  The script reads live scenario tags, the Todo 23 disposition
    tables and the catalog matrix at call time — no cached classification.
    """
    import importlib.util
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    script = root / "scripts" / "stage_user_coverage.py"
    try:
        spec = importlib.util.spec_from_file_location("_autoinfo_stage_user_coverage", script)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load coverage script at {script}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # The script is loaded dynamically, so its ``build_report`` return
        # type is invisible to mypy; the report is a plain JSON-able dict.
        report: dict[str, Any] = module.build_report(root=root)
        return _canonicalize(report)
    except Exception as exc:  # noqa: BLE001 - surface a typed error, never a silent pass
        return _error_from_exc(
            exc,
            "get_coverage_report failed",
            code=ErrorCode.VALIDATION_ERROR,
        )


def _handle_get_run_decisions(session_id: str) -> dict[str, Any]:
    """Handle get_run_decisions MCP tool (TR-A-01/TR-A-02, B2.6/F69).

    Return the structured decision trail for one run/session correlation id:
    every scenario verdict, every step decision in execution order, and the
    anomaly list (failures, timeouts, unconfigured/recovered steps, warnings).
    Reads the persisted report under ``validation-runs/sessions/<id>.json``;
    when no separate report exists it falls back to scanning saved runs, so an
    already-persisted run is still queryable.  Use after
    ``run_validation_scenario(save_results=true)`` or
    ``run_all_validation_scenarios()`` to reconstruct what happened without
    re-running anything.
    """
    from autoinfo.output.run_report import load_run_report

    report = load_run_report(session_id)
    if report is None:
        return error_response(
            code=ErrorCode.NOT_FOUND,
            message=(
                f"No run report found for session_id '{session_id}'. Run "
                "run_validation_scenario(save_results=true) or "
                "run_all_validation_scenarios() first, then query the "
                "returned session_id."
            ),
            actionable=True,
        )
    return success_response(report)


def _handle_recommend_content(
    user_id: str,
    query: str = "",
    domain: str = "",
    limit: int = 10,
) -> dict[str, Any]:
    """Handle recommend_content MCP tool."""
    try:
        from autoinfo.recommend import ContentBasedEngine

        engine = ContentBasedEngine()
        items = engine.recommend(
            user_id=user_id,
            query=query,
            domain=domain or None,
            limit=limit,
        )
        return {
            "user_id": user_id,
            "query": query,
            "items": [
                {
                    "entry_id": item.entry_id,
                    "title": item.title,
                    "score": item.score,
                    "reason": item.reason,
                    "source_url": item.source_url,
                    "domain": item.domain,
                }
                for item in items
            ],
            "count": len(items),
        }
    except Exception as exc:
        logger.error("recommend_content failed: %s", exc)
        return _error_from_exc(exc, "recommend_content failed")


# ---------------------------------------------------------------------------
# T15: Audit Log Query
# ---------------------------------------------------------------------------


def _handle_query_audit_log(
    actor: str | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """Query the immutable audit log with optional filters.

    Parameters
    ----------
    actor:
        Filter by actor name.
    action:
        Filter by action name.
    resource_type:
        Filter by resource type.
    date_from:
        ISO-8601 lower bound on timestamp.
    date_to:
        ISO-8601 upper bound on timestamp.
    limit:
        Max entries to return (default 100).
    offset:
        Pagination offset (default 0).

    Returns
    -------
    dict
        ``{entries, count}``.
    """
    try:
        from autoinfo.audit import query_audit_log

        entries = query_audit_log(
            actor=actor,
            action=action,
            resource_type=resource_type,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
        )
        return {
            "entries": [asdict(e) for e in entries],
            "count": len(entries),
        }
    except Exception as exc:
        logger.exception("Audit log query failed")
        return _error_from_exc(exc, "Audit log query failed")


# ---------------------------------------------------------------------------
# T16: CEFR Batch Classification
# ---------------------------------------------------------------------------


def _handle_cefr_batch(
    texts: list[str],
    lang: str = "en",
) -> dict[str, Any]:
    """Batch classify multiple texts into CEFR levels (A1-C2).

    Parameters
    ----------
    texts:
        List of texts to classify.
    lang:
        Language code: ``"en"``, ``"zh"``, or ``"ja"`` (default ``"en"``).

    Returns
    -------
    dict
        ``{results, total, errors}`` where each result is
        ``{text, cefr_level, confidence}`` or ``{text, error}``.
    """
    try:
        config = mcp_context._load_config()
        model_config: dict[str, Any] = {}
        if hasattr(config, "cefr") and config.cefr.model:
            model_config["model"] = config.cefr.model
        elif config.llm.provider and config.llm.model:
            llm_model = config.llm.model
            if "/" not in llm_model:
                llm_model = f"{config.llm.provider}/{llm_model}"
            model_config["model"] = llm_model
        if config.llm.api_key:
            model_config["api_key"] = config.llm.api_key
        if config.llm.base_url:
            model_config["base_url"] = config.llm.base_url
    except Exception:
        model_config = {}

    from autoinfo.cefr import classify_text

    if not texts:
        return error_response(
            code=ErrorCode.VALIDATION_ERROR,
            message="texts must be a non-empty list",
            actionable=True,
        )

    results: list[dict[str, Any]] = []
    errors = 0

    # Bounded fan-out: at most 8 concurrent classifications (env override
    # AUTOINFO_CEFR_BATCH_WORKERS), never more than the number of texts.
    # Each per-text task runs through classify_text -> call_with_fallback,
    # which acquires the shared per-provider semaphore (llm.py) so the
    # fan-out stays rate-limited.  Futures are keyed by original index and
    # collected in insertion order, preserving the sequential response order.
    max_workers = min(len(texts), 8)
    raw_workers = os.environ.get("AUTOINFO_CEFR_BATCH_WORKERS", "")
    if raw_workers.isdigit():
        max_workers = min(len(texts), max(1, int(raw_workers)))

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=max_workers,
        thread_name_prefix="cefr-batch",
    ) as pool:
        futures = {
            i: pool.submit(classify_text, text=t, lang=lang, model_config=model_config)
            for i, t in enumerate(texts)
        }
        for i, future in futures.items():
            try:
                result = future.result()
                results.append(
                    {
                        "text": texts[i],
                        "cefr_level": result["cefr_level"],
                        "confidence": result["confidence"],
                    }
                )
            except Exception as exc:
                results.append({"text": texts[i], "error": str(exc)})
                errors += 1

    return {
        "results": results,
        "total": len(texts),
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# T17: Email SMTP Config
# ---------------------------------------------------------------------------


def _handle_email_config(
    smtp_server: str = "",
    smtp_port: int = 0,
    username: str = "",
    password: str = "",
    enable: bool = False,
    disable: bool = False,
    test: bool = False,
) -> dict[str, Any]:
    """View or update email SMTP configuration.

    Parameters
    ----------
    smtp_server:
        SMTP server hostname.
    smtp_port:
        SMTP server port.
    username:
        SMTP username.
    password:
        SMTP password.
    enable:
        Enable email sending.
    disable:
        Disable email sending.
    test:
        Send a test email using current config.

    Returns
    -------
    dict
        ``{config: {smtp_host, smtp_port, enabled, ...}, updated, test_result}``.
    """
    import smtplib
    from email.mime.text import MIMEText

    try:
        cfg = mcp_context._load_config()
    except Exception as exc:
        return _error_from_exc(exc, "Failed to load the project configuration")

    email_cfg = cfg.email

    if enable and disable:
        return error_response(
            code=ErrorCode.VALIDATION_ERROR,
            message="Cannot use both enable and disable.",
            actionable=True,
        )

    changed = False
    if smtp_server:
        email_cfg.smtp_host = smtp_server
        changed = True
    if smtp_port > 0:
        email_cfg.smtp_port = smtp_port
        changed = True
    if username:
        email_cfg.smtp_user = username
        changed = True
    if password:
        email_cfg.smtp_pass = password
        changed = True
    if enable:
        email_cfg.enabled = True
        changed = True
    if disable:
        email_cfg.enabled = False
        changed = True

    if changed:
        mcp_context._save_config(cfg)

    config_summary: dict[str, Any] = {
        "smtp_host": email_cfg.smtp_host or "(not set)",
        "smtp_port": email_cfg.smtp_port,
        "smtp_user": email_cfg.smtp_user or "(not set)",
        "smtp_pass": "****" if email_cfg.smtp_pass else "(not set)",
        "from_addr": email_cfg.from_addr or "(not set)",
        "to_addrs": email_cfg.to_addrs or [],
        "enabled": email_cfg.enabled,
    }

    response: dict[str, Any] = {
        "config": config_summary,
        "updated": changed,
        "test_result": None,
    }

    if test:
        if not email_cfg.smtp_host:
            response["test_result"] = "skipped: SMTP server not configured"
        elif not email_cfg.from_addr and not email_cfg.smtp_user:
            response["test_result"] = "skipped: no from address configured"
        elif not email_cfg.to_addrs:
            response["test_result"] = "skipped: no recipients configured"
        else:
            from_addr = email_cfg.from_addr or email_cfg.smtp_user
            to_addrs = email_cfg.to_addrs

            msg = MIMEText(
                "This is a test email from AutoInfo.\n\n"
                "If you received this, SMTP configuration is working correctly."
            )
            msg["Subject"] = "[AutoInfo] Test Email"
            msg["From"] = from_addr
            msg["To"] = ", ".join(to_addrs)

            server = None
            try:
                server = smtplib.SMTP(email_cfg.smtp_host, email_cfg.smtp_port, timeout=30)
                server.ehlo()
                if server.has_extn("STARTTLS"):
                    server.starttls()
                    server.ehlo()
                if email_cfg.smtp_user and email_cfg.smtp_pass:
                    server.login(email_cfg.smtp_user, email_cfg.smtp_pass)
                server.sendmail(from_addr, to_addrs, msg.as_string())
                response["test_result"] = f"success: sent to {', '.join(to_addrs)}"
            except (smtplib.SMTPException, OSError) as exc:
                response["test_result"] = f"failed: {exc}"
            finally:
                if server is not None:
                    try:
                        server.quit()
                    except Exception:
                        pass

    return _canonicalize(response)


# ---------------------------------------------------------------------------
# T19: Clean Cache
# ---------------------------------------------------------------------------


def _handle_clean_cache(
    collections: bool = False,
    outputs: bool = False,
    everything: bool = False,
    dry_run: bool = False,
    confirm: bool = False,
    actor: str = "agent",
) -> dict[str, Any]:
    """Remove cached artifacts and temporary files.

    Parameters
    ----------
    collections:
        Remove cached collections/ contents.
    outputs:
        Remove outputs/ contents.
    everything:
        Remove ALL cached data (collections + outputs + knowledge + DB).
    dry_run:
        Show what would be deleted without deleting (default False).

    Returns
    -------
    dict
        ``{items_removed, dry_run, targets}``.
    """
    if everything and not confirm and not dry_run:
        return error_response(
            code=ErrorCode.CONFIRMATION_REQUIRED,
            message="clean_cache(everything=True) requires confirm=true — this deletes the entire knowledge/ directory and database",
            actionable=True,
        )
    import shutil

    targets: list[str] = []
    total = 0

    if collections or everything:
        path = Path("collections")
        if path.is_dir():
            if dry_run:
                cnt = sum(1 for _ in path.iterdir())
            else:
                cnt = 0
                for child in path.iterdir():
                    if child.is_dir():
                        shutil.rmtree(child)
                    else:
                        child.unlink()
                    cnt += 1
            total += cnt
            targets.append(f"collections ({cnt} items)")
    if outputs or everything:
        path = Path("outputs")
        if path.is_dir():
            if dry_run:
                cnt = sum(1 for _ in path.iterdir())
            else:
                cnt = 0
                for child in path.iterdir():
                    if child.is_dir():
                        shutil.rmtree(child)
                    else:
                        child.unlink()
                    cnt += 1
            total += cnt
            targets.append(f"outputs ({cnt} items)")
    if everything:
        path = Path("knowledge")
        if path.is_dir():
            if dry_run:
                cnt = sum(1 for _ in path.iterdir())
            else:
                cnt = 0
                for child in path.iterdir():
                    if child.is_dir():
                        shutil.rmtree(child)
                    else:
                        child.unlink()
                    cnt += 1
            total += cnt
            targets.append(f"knowledge ({cnt} items)")

        db_path = Path("autoinfo.db")
        if db_path.is_file():
            if not dry_run:
                db_path.unlink()
            total += 1
            targets.append("autoinfo.db")

    return {
        "items_removed": total,
        "dry_run": dry_run,
        "targets": targets,
    }


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

app = Server("autoinfo")

# Director-only operations (T-S-08 / AC1.3).  These are reserved for the
# human director and are gated at the CODE level, not merely documented: a
# default agent neither discovers them in ``list_tools()`` nor can invoke
# them (the dispatch guard below refuses with ``DIRECTOR_ONLY``).  Keeping
# the single source of truth here means discovery, the machine-readable
# per-tool marker, and the dispatch guard can never drift apart.
_DIRECTOR_ONLY_TOOLS: frozenset[str] = frozenset(
    {
        "demote_kb_wiki",  # 03-Wiki is append-only: director-only demotion
        "force_promote",  # skip the curation/admission gate: director-only
        "remove_domain",  # destructive config removal: human/director decides
    }
)

# JSON Schema extension keyword marking a tool as director-only.  Unknown
# keywords are ignored by standard JSON Schema consumers, so this rides
# alongside the normal schema while staying machine-readable to an agent.
DIRECTOR_ONLY_MARKER = "x-autoinfo-director-only"


def _caller_actor_for_discovery() -> str:
    """Resolve the actor identity used to decide director-surface visibility.

    The MCP stdio transport carries no per-request caller identity, so the
    server identity is taken from ``AUTOINFO_ACTOR`` (the same variable the
    audit trail uses).  When that is unset but ``AUTOINFO_DIRECTOR_ACTORS``
    is explicitly configured, the server adopts the first whitelisted actor
    as its identity — i.e. a director-operated server.  A default agent
    (neither variable set) resolves to ``"agent:mcp"``, which the default
    ``"director"`` whitelist never matches, so director tools stay hidden.
    """
    actor = os.environ.get("AUTOINFO_ACTOR")
    if actor and actor.strip():
        return actor.strip()
    raw = os.environ.get("AUTOINFO_DIRECTOR_ACTORS")
    if raw and raw.strip():
        first = next((a.strip() for a in raw.split(",") if a.strip()), "")
        if first:
            return first
    return "agent:mcp"


def _caller_is_director() -> bool:
    """Return whether the current server identity is a whitelisted director."""
    if _is_readonly():
        return False
    return is_director(_caller_actor_for_discovery())


@app.list_tools()  # type: ignore[untyped-decorator,no-untyped-call]
async def list_tools() -> list[Tool]:
    """Declare the available MCP tools with their input schemas.

    Read-only mode (gate 1): exposes ONLY the ``_READONLY_TOOLS`` whitelist.

    Director gating (T-S-08): a default agent never sees the
    ``_DIRECTOR_ONLY_TOOLS`` surface — an operation it cannot invoke is not
    advertised.  A server whose identity resolves to a whitelisted
    ``AUTOINFO_DIRECTOR_ACTORS`` entry sees the full declaration; those
    tools also carry the machine-readable ``DIRECTOR_ONLY_MARKER``.
    """
    tools = _full_tool_list()
    if _is_readonly():
        return [t for t in tools if t.name in _READONLY_TOOLS]
    if not _caller_is_director():
        return [t for t in tools if t.name not in _DIRECTOR_ONLY_TOOLS]
    return tools


# Canonical param spellings with their legacy alias (T-S-03). The alias is
# accepted at dispatch and exposed as an optional schema property; it is then
# normalized to whichever spelling the handler signature expects.
_USER_ID_ALIASES = ("user_id", "end_user_id")
_DOMAIN_ALIASES = ("name", "domain")
_DOMAIN_IDENTITY_TOOLS = frozenset(
    {
        "activate_domain",
        "deactivate_domain",
        "add_domain",
        "remove_domain",
        "get_domain_config",
    }
)


def _inject_param_alias(
    schema: dict[str, Any],
    canonical: str,
    alias: str,
    alias_description: str,
) -> None:
    """Expose ``alias`` as an optional spelling of ``canonical``.

    ``canonical`` stays required alongside the alias so the contract still
    demands the value while either spelling satisfies it (JSON Schema
    ``required`` is presence-only — dispatch collapses the alias).
    """
    props = schema.setdefault("properties", {})
    if canonical not in props or alias in props:
        return
    props[alias] = {
        "type": props[canonical].get("type", "string"),
        "description": alias_description,
        "deprecated": True,
    }


def _inject_param_aliases(tool: Tool) -> None:
    """Expose legacy param spellings as optional aliases (T-S-03).

    ``user_id``/``end_user_id`` and ``domain``/``name`` are the same entity
    spelled two ways across the surface.  Both spellings remain callable;
    dispatch normalizes to whichever spelling the handler expects.  The
    canonical spelling stays in ``required`` when the handler needs it; the
    alias is optional so existing required-param contracts don't break.
    """
    schema = tool.inputSchema
    if not isinstance(schema, dict):
        return
    props = schema.get("properties", {})
    if "user_id" in props:
        _inject_param_alias(
            schema,
            "user_id",
            "end_user_id",
            "Alias of user_id (deprecated spelling; both are accepted).",
        )
    elif "end_user_id" in props:
        _inject_param_alias(
            schema,
            "end_user_id",
            "user_id",
            "Alias of end_user_id (canonical spelling; both are accepted).",
        )
    if tool.name in _DOMAIN_IDENTITY_TOOLS and "name" in props:
        _inject_param_alias(
            schema,
            "name",
            "domain",
            "Alias of name (domain identity; both are accepted).",
        )


def _decorate_tools(tools: list[Tool]) -> list[Tool]:
    """Inject legacy param aliases and the director-only marker.

    ``outputSchema`` is deliberately not attached: the canonical envelope is
    documented once (ADR 0010, ``docs/dev/specs/mcp-tools.md``) instead of
    being repeated on all 149 tools.  Per-tool schemas are a follow-up (#581).
    """
    for tool in tools:
        _inject_param_aliases(tool)
        if tool.name in _DIRECTOR_ONLY_TOOLS and isinstance(tool.inputSchema, dict):
            tool.inputSchema[DIRECTOR_ONLY_MARKER] = True
    return tools


def _full_tool_list() -> list[Tool]:
    """Return the MCP tool schemas in their stable registration order.

    Schemas live in :mod:`autoinfo.mcp.tools` (one module per domain; #581
    phase 1).  Every call builds fresh ``Tool`` objects before decoration, so
    ``_decorate_tools`` mutations never leak across calls.
    """
    from autoinfo.mcp.tools import build_all_tools

    return _decorate_tools(build_all_tools())


# -- LLM-required tools (16) ------------------------------------------------
# Tools in this set require LLM configuration to function.  When the LLM
# is not configured (no api_key), call_tool will block them with a clear
# error response before dispatching to the handler.
_LLM_REQUIRED_TOOLS: frozenset[str] = frozenset(
    {
        "suggest_keywords",
        "classify_cefr",
        "cefr_batch",
        "extract_fields",
        "generate_digest",
        "generate_report",
        "generate_cross_domain_report",
        "generate_tutorial",
        "generate_presentation",
        "localize_content",
        "query_collected",
        "process_collection",
        "recommend_content",
        "simplify_content",
        "promote_kb_draft",
        "batch_run",
    }
)


# -- Read-only server mode (``autoinfo serve --agent``) ----------------------
# SECURITY: double gate — list_tools() lists ONLY whitelisted tools;
# call_tool() returns an explicit READ_ONLY_SERVER error envelope for any
# non-whitelisted name (never silent).  ``run_validation_scenario`` is
# EXPLICITLY EXCLUDED (its steps contain write ops: collect/promote/delete).
# ``export_kb`` / ``search_knowledge_base`` are not in _LLM_REQUIRED_TOOLS,
# and export_kb(format="agent") is served by the pure-function path
# (_export_agent_json — no LLM, no disk), so readonly mode works keyless.
_READONLY_TOOLS: frozenset[str] = frozenset(
    {
        "search_knowledge_base",
        "get_kb_entry",
        "export_kb",
        "list_validation_scenarios",
    }
)

# Mode is decided at startup (--readonly / serve --agent), never mid-session.
_READONLY_MODE = False


def set_readonly_mode(enabled: bool) -> None:
    """Enable/disable read-only server mode (process-wide)."""
    global _READONLY_MODE
    _READONLY_MODE = bool(enabled)


def _is_readonly() -> bool:
    """Return ``True`` when the server runs in read-only mode."""
    return _READONLY_MODE


def _is_llm_configured() -> bool:
    """Return ``True`` if an LLM API key has been configured.

    Mirrors the logic in ``_handle_diagnose_system`` — reads the config
    and checks both the config field and the ``AUTOINFO_LLM_API_KEY``
    environment variable.  Fails closed (``False``) on error.
    """
    try:
        from autoinfo.config import get_config_path, load_config

        config_path = get_config_path()
        if config_path:
            config = load_config(config_path)
            return bool(config.llm.api_key or os.environ.get("AUTOINFO_LLM_API_KEY"))
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------------
# Dispatch-level audit hook (M1T15)
#
# Every MCP tool call is recorded in the append-only audit log with the
# whitelisted fields ONLY: actor, action, tool, resource, result_code,
# trace_id.  Tool inputs and response data are NEVER written here — the
# privacy grep (`grep -rn "api_key\|arguments\|payload" server.py |
# grep -i audit`) must stay empty.
# ---------------------------------------------------------------------------

# Explicit exclusion list (volume control): high-frequency read probes.
#  * ``health_check``  — entry-point health probe
#  * ``get_tool_count`` — static introspection
#  * every ``list_*`` tool (list_domains, list_sources, list_topics,
#    list_summaries, ...) — read-only discovery probes that fire in tight
#    agent loops and would otherwise dominate the log.
# All other tools (mutations + parameterised reads) are audited.
_AUDIT_EXCLUDED_TOOLS: frozenset[str] = frozenset(
    {
        "health_check",
        "get_tool_count",
    }
)

_AUDIT_WRITE_FAILURES = 0  # in-process counter surfaced via pipeline logs


def _audit_excluded(tool_name: str) -> bool:
    """Return ``True`` when *tool_name* is on the audit exclusion list.

    Exclusion list (documented, explicit):
      * ``health_check``
      * ``get_tool_count``
      * every tool whose name starts with ``list_``
    """
    return tool_name in _AUDIT_EXCLUDED_TOOLS or tool_name.startswith("list_")


def _handler_declares(tool_name: str, param: str) -> bool:
    """Return whether the handler *explicitly* declares ``param`` (T-S-03).

    Unlike :func:`_handler_accepts`, this ignores ``**kwargs`` absorption:
    a handler that only takes ``(name, arguments)`` — or a ``**kwargs``
    catch-all — does *not* declare either spelling, and the alias resolver
    must not assume the handler reads a specific key just because its
    signature can absorb one.
    """
    import inspect

    handler = globals().get(f"_handle_{tool_name}")
    if handler is None:
        return False
    try:
        sig = inspect.signature(handler)
    except (TypeError, ValueError):
        return False
    return param in sig.parameters


def _handler_accepts(tool_name: str, param: str) -> bool:
    """Return whether the tool's handler accepts ``param`` at dispatch time."""
    import inspect

    handler = globals().get(f"_handle_{tool_name}")
    if handler is None:
        return False
    try:
        sig = inspect.signature(handler)
    except (TypeError, ValueError):
        return False
    if param in sig.parameters:
        return True
    return any(p.kind is inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())


def _normalize_param_aliases(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Normalize legacy param spellings to what the handler expects (T-S-03).

    The surface exposes ``user_id``/``end_user_id`` and
    ``domain``/``name`` as the same entity.  Both spellings are accepted;
    here the alias is collapsed onto whichever spelling the handler
    signature *explicitly declares*, so explicit-signature handlers never
    see an unexpected keyword and callers keep working with either
    spelling.

    Generic handlers — ``(name, arguments)`` or ``**kwargs`` collectors —
    declare neither spelling, so their signature cannot tell us which key
    they read.  Collapsing to the alias would break a handler that reads
    ``arguments["user_id"]`` (the canonical spelling); therefore the
    canonical spelling is used as the fallback target.
    """
    args = dict(arguments)
    for canonical, alias in (_USER_ID_ALIASES,):
        present = [p for p in (canonical, alias) if p in args]
        if not present:
            continue
        value = args[present[0]]
        if _handler_declares(tool_name, alias) and not _handler_declares(tool_name, canonical):
            target = alias
        else:
            target = canonical
        for p in (canonical, alias):
            args.pop(p, None)
        args[target] = value
    if tool_name in _DOMAIN_IDENTITY_TOOLS:
        present = [p for p in _DOMAIN_ALIASES if p in args]
        if present:
            value = args[present[0]]
            if _handler_declares(tool_name, "domain") and not _handler_declares(tool_name, "name"):
                target = "domain"
            else:
                target = "name"
            for p in _DOMAIN_ALIASES:
                args.pop(p, None)
            args[target] = value
    return args


def _current_actor() -> str:
    """Resolve a stable actor id for dispatch-level audit entries.

    Taxonomy: ``"agent:<session>"`` (interactive MCP agent client),
    ``"cli"`` (command-line driven), ``"cron"`` (scheduled job),
    ``"system"`` (internal / server-originated).

    The MCP dispatch does not carry caller identity in its handler
    signature, so the actor is taken from the ``AUTOINFO_ACTOR``
    environment variable when a launcher (cron wrapper, CLI shim) sets
    it, defaulting to ``"agent:mcp"`` for the stdio/SSE agent surface.
    """
    return os.environ.get("AUTOINFO_ACTOR") or "agent:mcp"


def _safe_resource(args: dict[str, Any]) -> str:
    """Extract a single low-sensitivity resource identifier for audit rows.

    Returns the ``domain`` (then ``topic``, then ``name``) argument when
    present, else ``""``.  Only configuration-level identifiers (domain /
    topic / entity names) are ever used — never URLs, credentials, or
    free-form content — so the audit row's resource field cannot carry
    secrets.
    """
    for key in ("domain", "topic", "name"):
        value = args.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _audit_tool_call(tool_name: str, code: str, resource: str = "") -> None:
    """Append one dispatch-level row to the audit log (fire-and-forget).

    Writes exactly the whitelisted fields: ``actor``, ``action``,
    ``tool``, ``resource``, ``result_code``, ``trace_id`` — nothing else
    (no tool inputs, no response data).

    Best-effort by design: the write is wrapped in try/except so an audit
    failure can never fail the tool call itself; failures are logged and
    counted (``_AUDIT_WRITE_FAILURES``) instead.
    """
    global _AUDIT_WRITE_FAILURES
    if _audit_excluded(tool_name):
        return
    try:
        from autoinfo.audit import append_audit_log

        append_audit_log(
            actor=_current_actor(),
            action="tool_call",
            tool=tool_name,
            resource_id=resource,
            details={
                "result_code": code,
                "trace_id": str(uuid.uuid4()),
            },
        )
    except Exception:
        _AUDIT_WRITE_FAILURES += 1
        logger.warning(
            "Audit write failed for tool '%s' (code=%s) — call result unaffected",
            tool_name,
            code,
            exc_info=True,
        )
        from autoinfo.logging import get_pipeline_logger

        get_pipeline_logger("mcp.dispatch").warning(
            "Audit write failure",
            extra={"tool": tool_name, "result_code": code, "failures": _AUDIT_WRITE_FAILURES},
        )


def _envelope_result(
    envelope: dict[str, Any],
) -> tuple[list[TextContent], dict[str, Any]]:
    """Pack an envelope as ``(text_content, structured_content)``.

    Returning the tuple form lets clients read the same JSON either as text
    or as structured data, both carrying the canonical envelope.
    """
    return (
        [TextContent(type="text", text=json.dumps(envelope))],
        envelope,
    )


# #581 phase 2: data-driven dispatch.  Handler + invocation mode, in the
# same category order as the former if/elif chain (149 tools).  Keep this
# table in lock-step with ``_full_tool_list`` (enforced by
# tests/mcp/test_tool_dispatch_registry.py).
_TOOL_DISPATCH: dict[str, tuple[str, str]] = {
    # -- System (3) ---------------------------------------------------
    "health_check": ("_handle_health_check", "noargs"),
    "get_tool_count": ("_handle_get_tool_count", "noargs"),
    "diagnose_system": ("_handle_diagnose_system", "noargs"),
    # -- Discovery (7) ------------------------------------------------
    "list_domains": ("_handle_list_domains", "noargs"),
    "list_available_platforms": ("_handle_list_available_platforms", "noargs"),
    "get_domain_schema": ("_handle_get_domain_schema", "kwargs"),
    "list_available_models": ("_handle_list_available_models", "noargs"),
    "get_effective_llm_config": ("_handle_get_effective_llm_config", "kwargs"),
    "activate_domain": ("_handle_activate_domain", "kwargs"),
    "deactivate_domain": ("_handle_deactivate_domain", "kwargs"),
    "add_domain": ("_handle_add_domain", "kwargs"),
    "remove_domain": ("_handle_remove_domain", "kwargs"),
    "get_domain_config": ("_handle_get_domain_config", "kwargs"),
    # -- Source Management (5) ----------------------------------------
    "add_source": ("_handle_add_source", "kwargs"),
    "add_sources": ("_handle_add_sources", "kwargs"),
    "remove_source": ("_handle_remove_source", "kwargs"),
    "test_source": ("_handle_test_source", "kwargs"),
    "list_sources": ("_handle_list_sources", "kwargs"),
    # -- Topic Management (6) -----------------------------------------
    "add_topic": ("_handle_add_topic", "kwargs"),
    "remove_topic": ("_handle_remove_topic", "kwargs"),
    "list_topics": ("_handle_list_topics", "kwargs"),
    "list_keywords": ("_handle_list_keywords", "kwargs"),
    "topic_group_add": ("_handle_topic_group_add", "kwargs"),
    "topic_group_remove": ("_handle_topic_group_remove", "kwargs"),
    # -- Keywords Management (3) --------------------------------------
    "approve_keyword": ("_handle_approve_keyword", "kwargs"),
    "reject_keyword": ("_handle_reject_keyword", "kwargs"),
    "suggest_keywords": ("_handle_suggest_keywords", "thread"),
    # -- Collection / Processing (5) ----------------------------------
    # collect/process/batch_run are long-running sync handlers; offload
    # them so the asyncio event loop stays responsive and the progress
    # tools (get_collection_progress / get_processing_progress) keep
    # answering while a run is in flight (issue #136).
    "collect_sources": ("_handle_collect_sources", "thread"),
    "get_collection_progress": ("_handle_get_collection_progress", "kwargs"),
    "get_collection_status": ("_handle_get_collection_status", "kwargs"),
    "process_collection": ("_handle_process_collection", "thread"),
    "get_processing_progress": ("_handle_get_processing_progress", "kwargs"),
    # -- Knowledge Base (4) -------------------------------------------
    "list_summaries": ("_handle_list_summaries", "kwargs"),
    "get_kb_entry": ("_handle_get_kb_entry", "kwargs"),
    "search_knowledge_base": ("_handle_search_knowledge_base", "kwargs"),
    "query_knowledge_graph": ("_handle_query_knowledge_graph", "kwargs"),
    "knowledge_graph_export": ("_handle_knowledge_graph_export", "kwargs"),
    "flag_for_knowledge_base": ("_handle_flag_for_knowledge_base", "kwargs"),
    "get_summary": ("_handle_get_summary", "kwargs"),
    "link_items": ("_handle_link_items", "kwargs"),
    "get_item_relations": ("_handle_get_item_relations", "kwargs"),
    "get_entry_history": ("_handle_get_entry_history", "kwargs"),
    "restore_entry_version": ("_handle_restore_entry_version", "kwargs"),
    "compare_versions": ("_handle_compare_versions", "kwargs"),
    "get_collection_stats": ("_handle_get_collection_stats", "kwargs"),
    "get_collection_diff": ("_handle_get_collection_diff", "kwargs"),
    "get_domain_decay": ("_handle_get_domain_decay", "kwargs"),
    # -- KB: Draft tools (4) ------------------------------------------
    "create_kb_draft": ("_handle_create_kb_draft", "kwargs"),
    "reject_kb_draft": ("_handle_reject_kb_draft", "kwargs"),
    "list_kb_tier": ("_handle_list_kb_tier", "kwargs"),
    "promote_kb_draft": ("_handle_promote_kb_draft", "thread"),
    "demote_kb_wiki": ("_handle_demote_kb_wiki", "kwargs"),
    "force_promote": ("_handle_force_promote", "kwargs"),
    "promote_pending": ("_handle_promote_pending", "kwargs"),
    "reindex_kb": ("_handle_reindex_kb", "kwargs"),
    "create_kb_entry": ("_handle_create_kb_entry", "kwargs"),
    # -- Audit (1) -------------------------------------------------------
    "query_audit_log": ("_handle_query_audit_log", "kwargs"),
    # -- CEFR Classification (1) ----------------------------------------
    "classify_cefr": ("_handle_classify_cefr", "thread"),
    "cefr_batch": ("_handle_cefr_batch", "thread"),
    # -- Output (6) ---------------------------------------------------
    "list_output_templates": ("_handle_list_output_templates", "kwargs"),
    "generate_digest": ("_handle_generate_digest", "thread"),
    "generate_report": ("_handle_generate_report", "thread"),
    "generate_cross_domain_report": ("_handle_generate_cross_domain_report", "thread"),
    "generate_tutorial": ("_handle_generate_tutorial", "thread"),
    "generate_presentation": ("_handle_generate_presentation", "thread"),
    "localize_content": ("_handle_localize_content", "thread"),
    # -- Export / Import (2) -----------------------------------------------
    "export_kb": ("_handle_export_kb", "kwargs"),
    "import_kb": ("_handle_import_kb", "kwargs"),
    # -- Email (1) --------------------------------------------------------
    "send_email_digest": ("_handle_send_email_digest", "kwargs"),
    "email_config": ("_handle_email_config", "kwargs"),
    # -- Custom Extraction (2) ----------------------------------------
    "extract_fields": ("_handle_extract_fields", "thread"),
    "get_extraction": ("_handle_get_extraction", "kwargs"),
    # -- Schedule Management (5) ---------------------------------------
    "list_schedules": ("_handle_list_schedules", "noargs"),
    "add_schedule": ("_handle_add_schedule", "kwargs"),
    "remove_schedule": ("_handle_remove_schedule", "kwargs"),
    "run_schedules": ("_handle_run_schedules", "kwargs"),
    "get_schedule_status": ("_handle_get_schedule_status", "kwargs"),
    # -- Delivery Schedule Management (3) --------------------------------
    "add_delivery_schedule": ("_handle_add_delivery_schedule", "kwargs"),
    "list_delivery_schedules": ("_handle_list_delivery_schedules", "noargs"),
    "remove_delivery_schedule": ("_handle_remove_delivery_schedule", "kwargs"),
    # -- Q&A (1) -------------------------------------------------------
    "query_collected": ("_handle_query_collected", "thread"),
    # -- Source Health / Feedback (2) ----------------------------------
    "get_source_health": ("_handle_get_source_health", "kwargs"),
    "rate_item": ("_handle_rate_item", "kwargs"),
    # -- Webhooks (2) -------------------------------------------------
    "set_domain_webhooks": ("_handle_set_domain_webhooks", "kwargs"),
    "get_domain_webhooks": ("_handle_get_domain_webhooks", "kwargs"),
    # -- Init / Project / Batch / Config (8) --------------------------
    "init_project": ("_handle_init_project", "kwargs"),
    "configure_llm": ("_handle_configure_llm", "kwargs"),
    "test_llm_connection": ("_handle_test_llm_connection", "thread"),
    "list_projects": ("_handle_list_projects", "noargs"),
    "get_project_assets": ("_handle_get_project_assets", "noargs"),
    "archive_project": ("_handle_archive_project", "kwargs"),
    "batch_run": ("_handle_batch_run", "thread"),
    "get_feeds": ("_handle_get_feeds", "kwargs"),
    "list_active_collections": ("_handle_list_active_collections", "noargs"),
    "get_config": ("_handle_get_config", "kwargs"),
    # -- Gate Config (2) ------------------------------------------------
    "get_gate_config": ("_handle_get_gate_config", "kwargs"),
    "set_gate_config": ("_handle_set_gate_config", "kwargs"),
    # -- Product (2) ----------------------------------------------------
    "get_product": ("_handle_get_product", "kwargs"),
    "list_products": ("_handle_list_products", "kwargs"),
    # -- End User Delivery (1) -------------------------------------------
    "send_to_enduser": ("_handle_send_to_enduser", "kwargs"),
    # -- Alert Rules (3) ------------------------------------------------
    "get_alert_rules": ("_handle_get_alert_rules", "kwargs"),
    "add_alert_rule": ("_handle_add_alert_rule", "kwargs"),
    "remove_alert_rule": ("_handle_remove_alert_rule", "kwargs"),
    # -- Budget Thresholds (2) -------------------------------------------
    "get_budget_thresholds": ("_handle_get_budget_thresholds", "noargs"),
    "set_budget_thresholds": ("_handle_set_budget_thresholds", "kwargs"),
    "cost_dashboard": ("_handle_cost_dashboard", "kwargs"),
    "cost_allocation": ("_handle_cost_allocation", "kwargs"),
    # -- Metrics (2) --------------------------------------------------
    "get_metrics": ("_handle_get_metrics", "raw"),
    "get_prometheus_metrics": ("_handle_get_prometheus_metrics", "raw"),
    # -- Trace (1) ----------------------------------------------------
    "trace_item": ("_handle_trace_item", "raw"),
    # -- Soft-delete & GDPR (4) -----------------------------------------
    "soft_delete_entry": ("_handle_soft_delete_entry", "raw"),
    "mark_stale": ("_handle_mark_stale", "raw"),
    "restore_entry": ("_handle_restore_entry", "raw"),
    "export_user_data": ("_handle_export_user_data", "raw"),
    "delete_user_data": ("_handle_delete_user_data", "raw"),
    # -- Portal / End-user Self-service (2) ------------------------------
    "get_enduser_history": ("_handle_get_enduser_history", "kwargs"),
    "get_enduser_products": ("_handle_get_enduser_products", "kwargs"),
    # -- Delivery Log (1) ------------------------------------------------
    "query_delivery_log": ("_handle_query_delivery_log", "raw"),
    # -- Delivery Monitor (2) ------------------------------------------
    "list_active_deliveries": ("_handle_list_active_deliveries", "noargs"),
    "get_delivery_log": ("_handle_get_delivery_log", "kwargs"),
    # -- Clean Cache (1) -------------------------------------------------
    "clean_cache": ("_handle_clean_cache", "kwargs"),
    # -- Channel Health (1) ------------------------------------------
    "get_channel_health": ("_handle_get_channel_health", "kwargs"),
    # -- Merge / Find Similar (2) ---------------------------------
    "merge_items": ("_handle_merge_items", "kwargs"),
    "find_similar_items": ("_handle_find_similar_items", "kwargs"),
    # -- KB Freshness (1) ---------------------------------------------
    "calculate_freshness_score": ("_handle_calculate_freshness_score", "raw"),
    # -- End-User Trial (2) ----------------------------------------------
    "activate_trial": ("_handle_activate_trial", "kwargs"),
    "check_trial_expiry": ("_handle_check_trial_expiry", "kwargs"),
    # -- End-User Preferences (2) ----------------------------------------
    "update_preferences": ("_handle_update_preferences", "kwargs"),
    "get_preferences": ("_handle_get_preferences", "kwargs"),
    # -- End-User CRUD (5) --------------------------------------------------
    "enduser_create": ("_handle_enduser_create", "kwargs"),
    "enduser_get": ("_handle_enduser_get", "kwargs"),
    "enduser_update": ("_handle_enduser_update", "kwargs"),
    "enduser_delete": ("_handle_enduser_delete", "kwargs"),
    "enduser_list": ("_handle_enduser_list", "noargs"),
    # -- Stripe Billing (3) ------------------------------------------------
    "create_checkout_session": ("_handle_create_checkout_session", "kwargs"),
    "get_subscription_status": ("_handle_get_subscription_status", "kwargs"),
    "get_billing_summary": ("_handle_get_billing_summary", "kwargs"),
    # -- Usage-based Billing (G16 — 2) -----------------------------------
    "get_enduser_usage": ("_handle_get_enduser_usage", "kwargs"),
    "get_enduser_invoice": ("_handle_get_enduser_invoice", "kwargs"),
    # -- Agent Callbacks (3) --------------------------------------------
    "set_agent_callback": ("_handle_set_agent_callback", "kwargs"),
    "list_agent_callbacks": ("_handle_list_agent_callbacks", "noargs"),
    "remove_agent_callback": ("_handle_remove_agent_callback", "kwargs"),
    # -- Recommendation (1) --------------------------------------------
    "recommend_content": ("_handle_recommend_content", "thread"),
    # -- Simplification (1) --------------------------------------------
    "simplify_content": ("_handle_simplify_content", "thread"),
    # -- Validation (5) ------------------------------------------------
    "list_validation_scenarios": ("_handle_list_validation_scenarios", "noargs"),
    "run_validation_scenario": ("_handle_run_validation_scenario", "async"),
    "run_all_validation_scenarios": ("_handle_run_all_validation_scenarios", "async"),
    "get_coverage_report": ("_handle_get_coverage_report", "thread_noargs"),
    "get_run_decisions": ("_handle_get_run_decisions", "thread"),
}


async def _invoke_tool(
    spec: tuple[str, str],
    name: str,
    arguments: dict[str, Any],
) -> dict[str, Any] | list[dict[str, Any]]:
    """Invoke one dispatched handler using its registered call shape.

    The registry stores the handler *name*, resolved through module globals at
    call time: tests monkeypatch ``autoinfo.mcp.server._handle_*`` and that
    seam must keep working after the dispatch chain became a table.
    """
    handler_name, mode = spec
    handler = cast(Callable[..., Any], globals()[handler_name])
    result: dict[str, Any] | list[dict[str, Any]]
    if mode == "kwargs":
        result = handler(**arguments)
    elif mode == "thread":
        result = await asyncio.to_thread(handler, **arguments)
    elif mode == "noargs":
        result = handler()
    elif mode == "raw":
        result = handler(name, arguments)
    elif mode == "thread_noargs":
        result = await asyncio.to_thread(handler)
    elif mode == "async":
        result = await handler(**arguments)
    else:
        raise RuntimeError(f"unknown dispatch mode {mode!r} for tool {name!r}")
    return result


@app.call_tool()  # type: ignore[untyped-decorator]
async def call_tool(
    name: str, arguments: dict[str, Any]
) -> tuple[list[TextContent], dict[str, Any]]:
    """Dispatch tool calls to the appropriate implementation."""
    _dispatch_audit: dict[str, str] = {"code": "success"}
    result: dict[str, Any] | list[dict[str, Any]]
    arguments = _normalize_param_aliases(name, arguments)
    try:
        # -- Read-only gate (gate 2): whitelist enforcement ---------------
        # Explicit error envelope for non-whitelisted names — never silent.
        if _is_readonly() and name not in _READONLY_TOOLS:
            _dispatch_audit["code"] = "read_only"
            return _envelope_result(
                error_response(
                    code=ErrorCode.READ_ONLY_SERVER,
                    message=(
                        f"Tool '{name}' is not available in read-only "
                        "server mode (autoinfo serve --agent). "
                        f"Allowed tools: {', '.join(sorted(_READONLY_TOOLS))}. "
                        "Restart the server without --readonly for full access."
                    ),
                    actionable=True,
                )
            )

        # -- LLM guard: block LLM-required tools when not configured ------
        if name in _LLM_REQUIRED_TOOLS and not _is_llm_configured():
            _dispatch_audit["code"] = "blocked"
            return _envelope_result(
                error_response(
                    code=ErrorCode.LLM_NOT_CONFIGURED,
                    message="LLM is not configured. Use configure_llm() to set up your API key. See docs/dev/required-api-keys.md for the full list of API keys and environment variables.",
                    actionable=True,
                )
            )

        # -- Director-only guard: demote / force-promote / remove-domain --
        # Enforced at dispatch against the AUTOINFO_DIRECTOR_ACTORS
        # whitelist so a non-director actor is refused before anything is
        # mutated; an omitted actor defaults to the non-privileged "agent",
        # never to a privileged role.  demote_kb_wiki / force_promote repeat
        # the check in the store; soft_delete_entry enforces the same
        # whitelist at the store for 03-Wiki targets.
        if name in _DIRECTOR_ONLY_TOOLS:
            actor = arguments.get("actor") or "agent"
            if not is_director(actor):
                _dispatch_audit["code"] = "director_only"
                return _envelope_result(
                    error_response(
                        code=ErrorCode.DIRECTOR_ONLY,
                        message=(f"actor '{actor}' not whitelisted in AUTOINFO_DIRECTOR_ACTORS"),
                        actionable=True,
                    )
                )

        spec = _TOOL_DISPATCH.get(name)
        if spec is None:
            _dispatch_audit["code"] = "unknown_tool"
            return _envelope_result(
                error_response(
                    code=ErrorCode.UNKNOWN_TOOL,
                    message=f"Unknown tool: {name}",
                    actionable=False,
                )
            )
        result = await _invoke_tool(spec, name, arguments)

        # Canonical envelope only: handlers return either the success envelope
        # or the error envelope; flat success payloads are wrapped here.
        if isinstance(result, dict) and "success" in result:
            wrapped = result
        else:
            wrapped = success_response(result)
        return _envelope_result(wrapped)
    except NotImplementedError:
        # Stub tools return a graceful error response using canonical envelope
        _dispatch_audit["code"] = "not_implemented"
        return _envelope_result(
            error_response(
                code=ErrorCode.INTERNAL_ERROR,
                message=str(arguments.get("message", "Not implemented in v0.1")),
                actionable=True,
            )
        )
    except TypeError as exc:
        # Missing required arguments — client-side call error, not a server bug
        _dispatch_audit["code"] = "validation_error"
        return _envelope_result(
            _error_from_exc(
                exc,
                f"Tool '{name}' call failed",
                code=ErrorCode.VALIDATION_ERROR,
            )
        )
    except Exception as exc:
        _dispatch_audit["code"] = "error"
        logger.exception("Tool '%s' failed", name)
        return _envelope_result(_error_response(exc))
    finally:
        resource = _safe_resource(arguments)
        _audit_tool_call(name, _dispatch_audit["code"], resource)


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


async def main(readonly: bool = False) -> None:
    """Run the MCP server over stdio transport.

    Opens the stdio read/write streams and enters the server's main loop.
    The server processes incoming JSON-RPC messages until the client
    disconnects.

    Parameters
    ----------
    readonly:
        When ``True``, expose ONLY the ``_READONLY_TOOLS`` whitelist
        (read-only server mode — ``autoinfo serve --agent`` /
        ``python -m autoinfo.mcp.server --readonly``).
    """
    set_readonly_mode(readonly)
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


def run(readonly: bool = False) -> None:
    """Synchronous entry point (used by ``python -m autoinfo.mcp.server``)."""
    asyncio.run(main(readonly=readonly))


# Re-export surface for the shared helper tier (#581 phase 3): handler code
# and external imports keep these names without importing context directly.
from autoinfo.mcp.context import _PERSIST_EXT_BY_FORMAT as _PERSIST_EXT_BY_FORMAT
from autoinfo.mcp.context import _PLATFORM_INFO as _PLATFORM_INFO
from autoinfo.mcp.context import _REQUIRED_KEYS_DOCS_REF as _REQUIRED_KEYS_DOCS_REF
from autoinfo.mcp.context import _SOURCE_SETTINGS_KEY_KEYS as _SOURCE_SETTINGS_KEY_KEYS
from autoinfo.mcp.context import _VALID_SOURCE_TYPES as _VALID_SOURCE_TYPES
from autoinfo.mcp.context import OUTPUTS_DIR as OUTPUTS_DIR
from autoinfo.mcp.context import PLATFORMS as PLATFORMS
from autoinfo.mcp.context import T as T
from autoinfo.mcp.context import _canonicalize as _canonicalize
from autoinfo.mcp.context import _chain_contains_timeout as _chain_contains_timeout
from autoinfo.mcp.context import _classify_exception as _classify_exception
from autoinfo.mcp.context import _config_path as _config_path
from autoinfo.mcp.context import _default_platform_info as _default_platform_info
from autoinfo.mcp.context import _demo_sources_defs as _demo_sources_defs
from autoinfo.mcp.context import _detect_kb_status as _detect_kb_status
from autoinfo.mcp.context import _detect_missing_source_keys as _detect_missing_source_keys
from autoinfo.mcp.context import _detect_phase as _detect_phase
from autoinfo.mcp.context import _error_from_exc as _error_from_exc
from autoinfo.mcp.context import _error_response as _error_response
from autoinfo.mcp.context import _find_domain as _find_domain
from autoinfo.mcp.context import _gate_to_dict as _gate_to_dict
from autoinfo.mcp.context import _infer_format as _infer_format
from autoinfo.mcp.context import _init_job_state_table as _init_job_state_table
from autoinfo.mcp.context import _job_db_path as _job_db_path
from autoinfo.mcp.context import _load_config as _load_config
from autoinfo.mcp.context import _load_job_state as _load_job_state
from autoinfo.mcp.context import _load_latest_domain_state as _load_latest_domain_state
from autoinfo.mcp.context import _maybe_persist_output as _maybe_persist_output
from autoinfo.mcp.context import _merge_fallback_entries as _merge_fallback_entries
from autoinfo.mcp.context import _output_text as _output_text
from autoinfo.mcp.context import _parse_tags as _parse_tags
from autoinfo.mcp.context import _persist_output as _persist_output
from autoinfo.mcp.context import _safe_json_load as _safe_json_load
from autoinfo.mcp.context import _save_config as _save_config
from autoinfo.mcp.context import _save_job_state as _save_job_state
from autoinfo.mcp.context import _source_key_status as _source_key_status
from autoinfo.mcp.context import _suggest_extract_fields as _suggest_extract_fields
from autoinfo.mcp.context import _text_payload_metadata as _text_payload_metadata
from autoinfo.mcp.context import _validate_llm_pool_params as _validate_llm_pool_params
from autoinfo.mcp.context import _validate_source_type as _validate_source_type
from autoinfo.mcp.context import _validate_url as _validate_url
from autoinfo.mcp.context import _with_job_db as _with_job_db
from autoinfo.mcp.context import logger as logger
from autoinfo.mcp.tools.config_admin import (
    _handle_get_domain_webhooks as _handle_get_domain_webhooks,
)
from autoinfo.mcp.tools.config_admin import _handle_get_gate_config as _handle_get_gate_config
from autoinfo.mcp.tools.config_admin import _handle_get_product as _handle_get_product
from autoinfo.mcp.tools.config_admin import _handle_list_products as _handle_list_products
from autoinfo.mcp.tools.config_admin import (
    _handle_set_domain_webhooks as _handle_set_domain_webhooks,
)
from autoinfo.mcp.tools.config_admin import _handle_set_gate_config as _handle_set_gate_config
from autoinfo.mcp.tools.enduser import _handle_add_alert_rule as _handle_add_alert_rule
from autoinfo.mcp.tools.enduser import _handle_cost_allocation as _handle_cost_allocation
from autoinfo.mcp.tools.enduser import _handle_cost_dashboard as _handle_cost_dashboard
from autoinfo.mcp.tools.enduser import _handle_get_alert_rules as _handle_get_alert_rules
from autoinfo.mcp.tools.enduser import (
    _handle_get_budget_thresholds as _handle_get_budget_thresholds,
)
from autoinfo.mcp.tools.enduser import _handle_remove_alert_rule as _handle_remove_alert_rule
from autoinfo.mcp.tools.enduser import _handle_send_to_enduser as _handle_send_to_enduser
from autoinfo.mcp.tools.enduser import (
    _handle_set_budget_thresholds as _handle_set_budget_thresholds,
)
from autoinfo.mcp.tools.enduser_billing import _handle_activate_trial as _handle_activate_trial
from autoinfo.mcp.tools.enduser_billing import (
    _handle_check_trial_expiry as _handle_check_trial_expiry,
)
from autoinfo.mcp.tools.enduser_billing import (
    _handle_create_checkout_session as _handle_create_checkout_session,
)
from autoinfo.mcp.tools.enduser_billing import _handle_enduser_create as _handle_enduser_create
from autoinfo.mcp.tools.enduser_billing import _handle_enduser_delete as _handle_enduser_delete
from autoinfo.mcp.tools.enduser_billing import _handle_enduser_get as _handle_enduser_get
from autoinfo.mcp.tools.enduser_billing import _handle_enduser_list as _handle_enduser_list
from autoinfo.mcp.tools.enduser_billing import _handle_enduser_update as _handle_enduser_update
from autoinfo.mcp.tools.enduser_billing import (
    _handle_get_billing_summary as _handle_get_billing_summary,
)
from autoinfo.mcp.tools.enduser_billing import _handle_get_delivery_log as _handle_get_delivery_log
from autoinfo.mcp.tools.enduser_billing import (
    _handle_get_enduser_history as _handle_get_enduser_history,
)
from autoinfo.mcp.tools.enduser_billing import (
    _handle_get_enduser_invoice as _handle_get_enduser_invoice,
)
from autoinfo.mcp.tools.enduser_billing import (
    _handle_get_enduser_products as _handle_get_enduser_products,
)
from autoinfo.mcp.tools.enduser_billing import (
    _handle_get_enduser_usage as _handle_get_enduser_usage,
)
from autoinfo.mcp.tools.enduser_billing import _handle_get_preferences as _handle_get_preferences
from autoinfo.mcp.tools.enduser_billing import (
    _handle_get_subscription_status as _handle_get_subscription_status,
)
from autoinfo.mcp.tools.enduser_billing import (
    _handle_list_active_deliveries as _handle_list_active_deliveries,
)
from autoinfo.mcp.tools.enduser_billing import (
    _handle_query_delivery_log as _handle_query_delivery_log,
)
from autoinfo.mcp.tools.enduser_billing import (
    _handle_update_preferences as _handle_update_preferences,
)
from autoinfo.mcp.tools.kb_lifecycle import (
    _handle_calculate_freshness_score as _handle_calculate_freshness_score,
)
from autoinfo.mcp.tools.kb_lifecycle import _handle_find_similar_items as _handle_find_similar_items
from autoinfo.mcp.tools.kb_lifecycle import _handle_merge_items as _handle_merge_items
from autoinfo.mcp.tools.kb_lifecycle import _handle_trace_item as _handle_trace_item
from autoinfo.mcp.tools.knowledge import _handle_compare_versions as _handle_compare_versions
from autoinfo.mcp.tools.knowledge import _handle_create_kb_draft as _handle_create_kb_draft
from autoinfo.mcp.tools.knowledge import _handle_create_kb_entry as _handle_create_kb_entry
from autoinfo.mcp.tools.knowledge import _handle_demote_kb_wiki as _handle_demote_kb_wiki
from autoinfo.mcp.tools.knowledge import (
    _handle_flag_for_knowledge_base as _handle_flag_for_knowledge_base,
)
from autoinfo.mcp.tools.knowledge import _handle_force_promote as _handle_force_promote
from autoinfo.mcp.tools.knowledge import _handle_get_collection_diff as _handle_get_collection_diff
from autoinfo.mcp.tools.knowledge import (
    _handle_get_collection_stats as _handle_get_collection_stats,
)
from autoinfo.mcp.tools.knowledge import _handle_get_domain_decay as _handle_get_domain_decay
from autoinfo.mcp.tools.knowledge import _handle_get_entry_history as _handle_get_entry_history
from autoinfo.mcp.tools.knowledge import _handle_get_item_relations as _handle_get_item_relations
from autoinfo.mcp.tools.knowledge import _handle_get_kb_entry as _handle_get_kb_entry
from autoinfo.mcp.tools.knowledge import _handle_get_summary as _handle_get_summary
from autoinfo.mcp.tools.knowledge import (
    _handle_knowledge_graph_export as _handle_knowledge_graph_export,
)
from autoinfo.mcp.tools.knowledge import _handle_link_items as _handle_link_items
from autoinfo.mcp.tools.knowledge import _handle_list_kb_tier as _handle_list_kb_tier
from autoinfo.mcp.tools.knowledge import _handle_list_summaries as _handle_list_summaries
from autoinfo.mcp.tools.knowledge import _handle_promote_kb_draft as _handle_promote_kb_draft
from autoinfo.mcp.tools.knowledge import _handle_promote_pending as _handle_promote_pending
from autoinfo.mcp.tools.knowledge import (
    _handle_query_knowledge_graph as _handle_query_knowledge_graph,
)
from autoinfo.mcp.tools.knowledge import _handle_reindex_kb as _handle_reindex_kb
from autoinfo.mcp.tools.knowledge import _handle_reject_kb_draft as _handle_reject_kb_draft
from autoinfo.mcp.tools.knowledge import (
    _handle_restore_entry_version as _handle_restore_entry_version,
)
from autoinfo.mcp.tools.knowledge import (
    _handle_search_knowledge_base as _handle_search_knowledge_base,
)
from autoinfo.mcp.tools.qa import _handle_get_source_health as _handle_get_source_health
from autoinfo.mcp.tools.qa import _handle_query_collected as _handle_query_collected
from autoinfo.mcp.tools.qa import _handle_rate_item as _handle_rate_item
from autoinfo.mcp.tools.runtime import _handle_configure_llm as _handle_configure_llm
from autoinfo.mcp.tools.runtime import _handle_delete_user_data as _handle_delete_user_data
from autoinfo.mcp.tools.runtime import _handle_export_user_data as _handle_export_user_data
from autoinfo.mcp.tools.runtime import _handle_get_metrics as _handle_get_metrics
from autoinfo.mcp.tools.runtime import (
    _handle_get_prometheus_metrics as _handle_get_prometheus_metrics,
)
from autoinfo.mcp.tools.runtime import _handle_init_project as _handle_init_project
from autoinfo.mcp.tools.runtime import _handle_mark_stale as _handle_mark_stale
from autoinfo.mcp.tools.runtime import _handle_restore_entry as _handle_restore_entry
from autoinfo.mcp.tools.runtime import _handle_soft_delete_entry as _handle_soft_delete_entry
from autoinfo.mcp.tools.runtime import _handle_test_llm_connection as _handle_test_llm_connection
from autoinfo.mcp.tools.scheduling import (
    _handle_add_delivery_schedule as _handle_add_delivery_schedule,
)
from autoinfo.mcp.tools.scheduling import _handle_add_schedule as _handle_add_schedule
from autoinfo.mcp.tools.scheduling import _handle_get_schedule_status as _handle_get_schedule_status
from autoinfo.mcp.tools.scheduling import (
    _handle_list_delivery_schedules as _handle_list_delivery_schedules,
)
from autoinfo.mcp.tools.scheduling import _handle_list_schedules as _handle_list_schedules
from autoinfo.mcp.tools.scheduling import (
    _handle_remove_delivery_schedule as _handle_remove_delivery_schedule,
)
from autoinfo.mcp.tools.scheduling import _handle_remove_schedule as _handle_remove_schedule
from autoinfo.mcp.tools.scheduling import _handle_run_schedules as _handle_run_schedules

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Run the AutoInfo MCP server (stdio transport).",
    )
    parser.add_argument(
        "--readonly",
        action="store_true",
        help="Read-only mode: expose only the 4 read-only tools "
        "(search_knowledge_base, get_kb_entry, export_kb(format=agent), "
        "list_validation_scenarios). Equivalent to 'autoinfo serve --agent'.",
    )
    args = parser.parse_args()
    run(readonly=args.readonly)
