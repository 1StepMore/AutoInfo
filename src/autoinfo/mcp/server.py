"""MCP server — exposes AutoInfo capabilities as MCP tools over stdio.

This is the primary agent-facing interface for AutoInfo.  All 35+ capabilities
are planned; v0.1 exposes 30 tools across 7 categories:

**System** (2):
    health_check, diagnose_system

**Discovery** (7):
    list_domains, get_domain_schema, list_available_models, get_effective_llm_config,
    activate_domain, deactivate_domain, get_domain_config

**Schedule Management** (4):
    list_schedules, add_schedule, remove_schedule, run_schedules

**Source Management** (5):
    add_source, add_sources, remove_source, test_source, list_sources

**Topic Management** (3):
    add_topic, remove_topic, list_keywords

**Collection / Processing** (5):
    collect_sources, get_collection_progress, get_collection_status,
    process_collection, get_processing_progress

**Knowledge Base** (4):
    list_summaries, get_kb_entry, search_knowledge_base, flag_for_knowledge_base

**Output** (3):
    list_output_templates, generate_tutorial, generate_presentation

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
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from autoinfo import __version__
from autoinfo.mcp.errors import ErrorCode, error_dict, error_response, success_response

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config I/O helpers
# ---------------------------------------------------------------------------


def _config_path() -> Path:
    """Return the path to the project's ``.autoinfo/config.yaml``."""
    return Path.cwd() / ".autoinfo" / "config.yaml"


def _load_config() -> Any:
    """Load the AutoInfo configuration."""
    from autoinfo.config import load_config

    return load_config(_config_path())


def _save_config(config: Any) -> None:
    """Write a Config dataclass tree back to ``.autoinfo/config.yaml``."""
    from autoinfo.config import save_config as _public_save

    _public_save(config, _config_path())


def _find_domain(config: Any, name: str) -> Any | None:
    """Return the domain config object for *name*, or ``None``."""
    for d in config.domains:
        if d.name == name:
            return d
    return None

# ---------------------------------------------------------------------------
# Module-level state (in-memory, not persisted)
# ---------------------------------------------------------------------------

_collection_state: dict[str, Any] = {}
"""In-memory state tracking active collection runs, keyed by domain.

Each entry has the shape::

    {
        "status": "running" | "completed" | "idle",
        "started_at": "ISO timestamp" | "",
        "completed_at": "ISO timestamp" | "",
        "progress_pct": 0.0 .. 100.0,
        "items_collected": int,
        "errors": int,
        "items_per_source": dict[str, int],
        "duration_s": float,
    }
"""

# In-memory job state for progress tracking via job_id (collect_sources / process_collection)
_job_state: dict[str, dict[str, Any]] = {}

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
        "tools_count": len(
            [name for name in globals() if name.startswith("_handle_")]
        ),
    }


def _handle_get_tool_count() -> dict[str, Any]:
    """Return the number of registered MCP tools."""
    return {
        "tools_count": len(
            [name for name in globals() if name.startswith("_handle_")]
        ),
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
                            "tos_classification": s.tos_classification,
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
    from datetime import datetime, timezone

    from autoinfo.collect import run_collection

    domain = kwargs.get("domain", "unknown")
    job_id = str(uuid.uuid4())
    _collection_state[domain] = {
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": "",
        "progress_pct": 0.0,
        "items_collected": 0,
        "errors": 0,
        "items_per_source": {},
        "duration_s": 0.0,
        "job_id": job_id,
    }
    _job_state[job_id] = {
        "domain": domain,
        "tool": "collect_sources",
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "items_collected": 0,
        "errors": 0,
        "progress_pct": 0.0,
    }

    try:
        result = run_collection(**kwargs)
        # Attempt to extract stats from result
        total_new = result.get("total_new", 0) if isinstance(result, dict) else 0
        total_found = result.get("total_found", 0) if isinstance(result, dict) else 0
        errors = result.get("errors", 0) if isinstance(result, dict) else 0
        _collection_state[domain].update({
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "progress_pct": 100.0,
            "items_collected": total_new,
            "errors": errors,
            "items_per_source": result.get("items_per_source", {}) if isinstance(result, dict) else {},
        })
        _job_state[job_id].update({
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "items_collected": total_new,
            "errors": errors,
            "progress_pct": 100.0,
        })
        if isinstance(result, dict):
            result["job_id"] = job_id
        else:
            result = {"job_id": job_id, "result": result}
        return result
    except Exception:
        _collection_state[domain].update({
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "progress_pct": 100.0,
        })
        _job_state[job_id].update({
            "status": "error",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })
        raise


def _handle_get_collection_progress(domain: str = "", job_id: str = "") -> dict[str, Any]:
    """Return current collection progress. Supports lookup by domain or job_id."""
    if job_id:
        state = _job_state.get(job_id)
        if state:
            return {"job_id": job_id, **state, "is_complete": state.get("status") in ("completed", "error")}
        return {"job_id": job_id, "status": "not_found", "is_complete": True}
    if domain:
        state = _collection_state.get(domain, {
            "status": "idle",
            "started_at": "",
            "completed_at": "",
            "progress_pct": 0.0,
            "items_collected": 0,
            "errors": 0,
            "items_per_source": {},
            "duration_s": 0.0,
        })
        return {"domain": domain, **state}

    # Return all
    results: dict[str, Any] = {}
    for d in list(_collection_state.keys()):
        results[d] = {k: v for k, v in _collection_state[d].items()}
    return {"domains": results, "count": len(results)}


def _handle_get_collection_status(domain: str) -> dict[str, Any]:
    """Return full collection results for *domain* (last run)."""
    from datetime import datetime

    state = _collection_state.get(domain, {
        "status": "idle",
        "started_at": "",
        "completed_at": "",
        "progress_pct": 0.0,
        "items_collected": 0,
        "errors": 0,
        "items_per_source": {},
        "duration_s": 0.0,
    })

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
    from datetime import datetime, timezone

    from autoinfo.process import run_processing

    job_id = str(uuid.uuid4())
    _job_state[job_id] = {
        "domain": kwargs.get("domain", "unknown"),
        "tool": "process_collection",
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "progress_pct": 0.0,
        "kb_entries_created": 0,
        "total_items": 0,
    }

    try:
        result = run_processing(**kwargs)
        result_dict = asdict(result)
        _job_state[job_id].update({
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "progress_pct": 100.0,
            "kb_entries_created": result_dict.get("kb_entries_created", 0),
            "total_items": result_dict.get("total_items", result_dict.get("total_new", 0)),
        })
        result_dict["job_id"] = job_id
        return result_dict
    except Exception:
        _job_state[job_id].update({
            "status": "error",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })
        raise


def _handle_get_processing_progress(domain: str = "", job_id: str = "") -> dict[str, Any]:
    """Return processing progress. Supports lookup by domain or job_id."""
    if job_id:
        state = _job_state.get(job_id)
        if state:
            return {"job_id": job_id, **state, "is_complete": state.get("status") in ("completed", "error")}
        return {"job_id": job_id, "status": "not_found", "is_complete": True}
    if domain:
        from autoinfo.process import get_processing_progress

        return get_processing_progress(domain=domain)
    return {"status": "idle", "is_complete": True}


def _handle_list_summaries(**kwargs: Any) -> dict[str, Any]:
    """List KB entries for a domain via ``KBStore.list_entries``.

    Expects ``domain`` in ``**kwargs`` (popped before passing the rest).
    """
    from autoinfo.kb import KBStore

    domain = kwargs.pop("domain")
    store = KBStore()
    entries = store.list_entries(domain, **kwargs)
    return {"domain": domain, "entries": entries, "count": len(entries)}


def _handle_get_kb_entry(entry_id: str, user_id: str | None = None) -> dict[str, Any]:
    """Fetch a single KB entry by ID via ``KBStore.get_entry``.

    Parameters
    ----------
    entry_id:
        Unique entry identifier.
    user_id:
        Optional user_id filter (accepted for multi-user compatibility;
        direct ID lookup is user-independent).
    """
    from autoinfo.kb import KBStore

    store = KBStore()
    entry = store.get_entry(entry_id)
    if entry is None:
        return {
            "error_code": ErrorCode.NOT_FOUND.value,
            "message": f"Entry '{entry_id}' not found",
            "actionable": True,
        }
    return entry


# ---------------------------------------------------------------------------
# Discovery tools
# ---------------------------------------------------------------------------


def _handle_list_domains() -> dict[str, Any]:
    """List all configured domains with source/topic counts."""
    try:
        config = _load_config()
    except Exception as exc:
        return {"domains": [], "count": 0, "error_code": ErrorCode.INTERNAL_ERROR.value, "message": str(exc), "actionable": True}

    domains = []
    for d in config.domains:
        domains.append({
            "name": d.name,
            "active": d.active,
            "source_count": len(d.sources),
            "topic_count": len(d.topics),
        })
    return {"domains": domains, "count": len(domains)}


# -- Platform metadata (static) -------------------------------------------

PLATFORMS = [
    {"type": "rss", "name": "RSS/Atom Feed", "description": "Fetch content from RSS or Atom feeds", "output_formats": ["xml", "json"]},
    {"type": "api", "name": "REST API", "description": "Call REST API endpoints that return JSON data", "output_formats": ["json"]},
    {"type": "web", "name": "Web Page", "description": "Extract content from web pages using trafilatura/readability", "output_formats": ["html", "markdown"]},
    {"type": "webhook", "name": "Webhook Receiver", "description": "Receive pushed content via HTTP POST webhooks", "output_formats": ["json"]},
    {"type": "email", "name": "Email (IMAP)", "description": "Collect content from email inboxes via IMAP", "output_formats": ["html", "text"]},
    {"type": "pdf", "name": "PDF Document", "description": "Extract text content from PDF documents", "output_formats": ["text", "markdown"]},
]


def _handle_list_available_platforms() -> dict[str, Any]:
    """List all supported source platform types with descriptions."""
    return {"platforms": PLATFORMS}


def _handle_activate_domain(name: str) -> dict[str, Any]:
    """Activate a domain (set domain.active = True)."""
    try:
        config = _load_config()
    except Exception as exc:
        return _error_dict(exc)

    domain_cfg = _find_domain(config, name)
    if domain_cfg is None:
        return {
            "error_code": ErrorCode.DOMAIN_NOT_FOUND.value,
            "message": f"Domain '{name}' is not configured",
            "actionable": True,
        }

    if domain_cfg.active:
        return {
            "domain": name,
            "active": True,
            "message": f"Domain '{name}' is already active",
        }

    domain_cfg.active = True
    _save_config(config)
    return {
        "domain": name,
        "active": True,
        "message": f"Domain '{name}' activated",
    }


def _handle_deactivate_domain(name: str) -> dict[str, Any]:
    """Deactivate a domain (set domain.active = False)."""
    try:
        config = _load_config()
    except Exception as exc:
        return _error_dict(exc)

    domain_cfg = _find_domain(config, name)
    if domain_cfg is None:
        return {
            "error_code": ErrorCode.DOMAIN_NOT_FOUND.value,
            "message": f"Domain '{name}' is not configured",
            "actionable": True,
        }

    if not domain_cfg.active:
        return {
            "domain": name,
            "active": False,
            "message": f"Domain '{name}' is already inactive",
        }

    domain_cfg.active = False
    _save_config(config)
    return {
        "domain": name,
        "active": False,
        "message": f"Domain '{name}' deactivated",
    }


def _handle_remove_domain(name: str) -> dict[str, Any]:
    """Remove a domain configuration. Preserves all collected data on disk."""
    try:
        config = _load_config()
    except Exception as exc:
        return _error_dict(exc)

    domain_cfg = _find_domain(config, name)
    if domain_cfg is None:
        return {
            "error_code": ErrorCode.DOMAIN_NOT_FOUND.value,
            "message": f"Domain '{name}' is not configured",
            "actionable": True,
        }

    config.domains.remove(domain_cfg)
    _save_config(config)
    return {"removed": True, "domain": name}


def _handle_get_domain_config(name: str) -> dict[str, Any]:
    """Return full domain config including sources, topics, extract_fields."""
    try:
        config = _load_config()
    except Exception as exc:
        return _error_dict(exc)

    domain_cfg = _find_domain(config, name)
    if domain_cfg is None:
        return {
            "error_code": ErrorCode.DOMAIN_NOT_FOUND.value,
            "message": f"Domain '{name}' is not configured",
            "actionable": True,
        }

    sources = [
        {
            "name": s.name,
            "type": s.type,
            "url": s.url,
            "quality_tier": s.quality_tier,
            "tos_classification": s.tos_classification,
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


def _handle_set_domain_webhooks(
    domain: str,
    webhook_urls: list[str],
) -> dict[str, Any]:
    """Set webhook URLs for a domain. Replaces any existing URLs."""
    # -- Validate URLs ----------------------------------------------------
    invalid: list[str] = []
    for url in webhook_urls:
        if not url.startswith(("http://", "https://")):
            invalid.append(url)
    if invalid:
        return {
            "error_code": ErrorCode.VALIDATION_ERROR.value,
            "message": (
                f"Invalid webhook URLs (must start with http:// or https://): "
                f"{invalid}"
            ),
            "actionable": True,
        }

    try:
        config = _load_config()
    except Exception as exc:
        return _error_dict(exc)

    domain_cfg = _find_domain(config, domain)
    if domain_cfg is None:
        return {
            "error_code": ErrorCode.DOMAIN_NOT_FOUND.value,
            "message": f"Domain '{domain}' is not configured",
            "actionable": True,
        }

    domain_cfg.webhook_urls = list(webhook_urls)
    _save_config(config)

    return {
        "domain": domain,
        "webhook_urls": domain_cfg.webhook_urls,
        "updated": True,
    }


def _handle_get_domain_webhooks(domain: str) -> dict[str, Any]:
    """Return the configured webhook URLs for a domain."""
    try:
        config = _load_config()
    except Exception as exc:
        return _error_dict(exc)

    domain_cfg = _find_domain(config, domain)
    if domain_cfg is None:
        return {
            "error_code": ErrorCode.DOMAIN_NOT_FOUND.value,
            "message": f"Domain '{domain}' is not configured",
            "actionable": True,
        }

    return {
        "domain": domain,
        "webhook_urls": list(getattr(domain_cfg, "webhook_urls", [])),
    }


def _handle_add_domain(name: str, description: str = "") -> dict[str, Any]:
    """Create a new domain configuration (idempotent — returns existing config if domain already exists)."""
    try:
        config = _load_config()
    except Exception as exc:
        return _error_dict(exc)

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
    _save_config(config)
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
        config = _load_config()
    except Exception as exc:
        return _error_dict(exc)

    domain_cfg = _find_domain(config, domain)
    if domain_cfg is None:
        return {
            "error_code": ErrorCode.DOMAIN_NOT_FOUND.value,
            "message": f"Domain '{domain}' is not configured",
            "actionable": True,
        }

    sources = [
        {"name": s.name, "type": s.type, "url": s.url, "quality_tier": s.quality_tier, "tos_classification": s.tos_classification}
        for s in domain_cfg.sources
    ]
    topics = [
        {"name": t.name, "keywords": t.keywords}
        for t in domain_cfg.topics
    ]

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
            {"name": "digest", "description": "Scheduled knowledge digests", "access_level": "free"},
            {"name": "report", "description": "Thematic structured reports", "access_level": "free"},
            {"name": "tutorial", "description": "Learning path tutorials", "access_level": "free"},
            {"name": "presentation", "description": "Slide-based presentations", "access_level": "free"},
        ],
        "topics": topics,
        "sources": sources,
    }


def _handle_list_available_models() -> dict[str, Any]:
    """List available LLM models from configuration."""
    try:
        config = _load_config()
    except Exception as exc:
        return {"models": [], "count": 0, "error_code": ErrorCode.INTERNAL_ERROR.value, "message": str(exc), "actionable": True}

    models = [
        {
            "task": "default",
            "provider": config.llm.provider,
            "model": config.llm.model,
            "api_key_configured": bool(
                config.llm.api_key
                or os.environ.get("AUTOINFO_LLM_API_KEY")
            ),
        },
    ]
    return {"models": models, "count": len(models)}


def _handle_get_effective_llm_config(task: str | None = None) -> dict[str, Any]:
    """Resolve effective LLM config for a given task."""
    from autoinfo.config import get_effective_llm_config

    try:
        return get_effective_llm_config(task=task)
    except Exception as exc:
        return _error_dict(exc)


# ---------------------------------------------------------------------------
# Source management tools
# ---------------------------------------------------------------------------

_VALID_SOURCE_TYPES = frozenset({"rss", "api", "web"})


def _validate_url(url: str) -> str | None:
    """Return an error message if *url* is invalid, or ``None``."""
    if not url or not isinstance(url, str):
        return "URL is required"
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        return "URL must start with http:// or https://"
    parts = url.split("://", 1)
    if len(parts) != 2 or not parts[1]:
        return "URL must have a valid host"
    return None


def _validate_source_type(type_: str) -> str | None:
    """Return an error message if *type_* is invalid, or ``None``."""
    if not type_ or not isinstance(type_, str):
        return "Source type is required"
    if type_ not in _VALID_SOURCE_TYPES:
        return (
            f"Invalid source type '{type_}'. "
            f"Must be one of: {', '.join(sorted(_VALID_SOURCE_TYPES))}"
        )
    return None


def _handle_add_source(
    name: str,
    url: str,
    type: str = "api",
    domain: str = "",
) -> dict[str, Any]:
    """Add a source (idempotent — dedup by url + type + domain)."""
    # --- Validation -----------------------------------------------------------
    url_error = _validate_url(url)
    if url_error:
        return {"error_code": ErrorCode.VALIDATION_ERROR.value, "message": url_error, "actionable": True}

    type_error = _validate_source_type(type)
    if type_error:
        return {"error_code": ErrorCode.VALIDATION_ERROR.value, "message": type_error, "actionable": True}

    try:
        config = _load_config()
    except Exception as exc:
        return _error_dict(exc)

    domain_cfg = _find_domain(config, domain)
    if domain_cfg is None:
        return {
            "error_code": ErrorCode.DOMAIN_NOT_FOUND.value,
            "message": f"Domain '{domain}' is not configured",
            "actionable": True,
        }

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
                },
                "created": False,
                "source_id": f"{domain}:{existing.name}",
            }
            if existing.quality_tier >= 3:
                dup_result["warning"] = "Quality tier 3+ source — content may have lower authority."
            return dup_result

    # Determine next quality_tier based on type
    quality_tier = 1 if type in ("api", "rss") else 2
    _TIER_TOS_MAP = {1: "open", 2: "licensed", 3: "restricted", 4: "sensitive"}
    tos_classification = _TIER_TOS_MAP.get(quality_tier, "open")

    from autoinfo.config import SourceConfig

    new_source = SourceConfig(name=name, type=type, url=url, quality_tier=quality_tier, tos_classification=tos_classification)
    domain_cfg.sources.append(new_source)
    _save_config(config)

    result: dict[str, Any] = {
        "source": {
            "name": name,
            "type": type,
            "url": url,
            "domain": domain,
            "quality_tier": quality_tier,
            "tos_classification": tos_classification,
        },
        "created": True,
        "source_id": f"{domain}:{name}",
    }

    # Advisory warning for tier 3+ sources
    if quality_tier >= 3:
        result["warning"] = "Quality tier 3+ source — content may have lower authority."

    return result


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
            )
            if "error_code" in result:
                errored += 1
                results.append({"index": idx, **result})
            else:
                results.append({"index": idx, **result})
        except Exception as exc:
            errored += 1
            results.append({
                "index": idx,
                "error_code": ErrorCode.INTERNAL_ERROR.value,
                "message": str(exc),
                "actionable": True,
            })

    return {
        "results": results,
        "total": len(sources),
        "succeeded": len(sources) - errored,
        "errored": errored,
    }


def _handle_remove_source(source_id: str, confirm: bool = True) -> dict[str, Any]:
    """Remove a source by its source_id (``domain:name``)."""
    if not confirm:
        return {
            "error_code": ErrorCode.CONFIRMATION_REQUIRED.value,
            "message": (
                f"This operation is destructive and requires confirmation. "
                f"Pass confirm=True to proceed."
            ),
            "actionable": True,
        }
    try:
        config = _load_config()
    except Exception as exc:
        return _error_dict(exc)

    parts = source_id.split(":", 1)
    if len(parts) != 2:
        return {
            "error_code": ErrorCode.INVALID_SOURCE_ID.value,
            "message": "source_id must be in format 'domain:name'",
            "actionable": True,
        }
    domain_name, source_name = parts

    domain_cfg = _find_domain(config, domain_name)
    if domain_cfg is None:
        return {
            "error_code": ErrorCode.DOMAIN_NOT_FOUND.value,
            "message": f"Domain '{domain_name}' is not configured",
            "actionable": True,
        }

    for i, existing in enumerate(domain_cfg.sources):
        if existing.name == source_name:
            removed = domain_cfg.sources.pop(i)
            _save_config(config)
            return {
                "removed": True,
                "source_id": source_id,
                "source": {
                    "name": removed.name,
                    "type": removed.type,
                    "url": removed.url,
                },
            }

    return {
        "error_code": ErrorCode.SOURCE_NOT_FOUND.value,
        "message": f"Source '{source_name}' not found in domain '{domain_name}'",
        "actionable": True,
    }


def _suggest_extract_fields(source_type: str) -> list[str]:
    """Return recommended extract fields for a given source type."""
    suggestions: dict[str, list[str]] = {
        "pubmed": ["pmid", "doi", "authors", "journal"],
        "api": ["pmid", "doi", "authors", "journal"],
        "rss": ["title", "pub_date", "description"],
        "web": ["description", "author", "published_date"],
    }
    return suggestions.get(source_type, ["title", "description"])


def _handle_test_source(url: str, type: str = "api") -> dict[str, Any]:
    """Test whether a source URL is reachable."""
    url_error = _validate_url(url)
    if url_error:
        return {"reachable": False, "error_code": ErrorCode.VALIDATION_ERROR.value, "message": url_error, "actionable": True}
    type_error = _validate_source_type(type)
    if type_error:
        return {"reachable": False, "error_code": ErrorCode.VALIDATION_ERROR.value, "message": type_error, "actionable": True}
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

        return {
            "reachable": resp.status_code < 500,
            "status_code": resp.status_code,
            "content_type": content_type_header,
            "content_preview": content_preview,
            "size_kb": round(size_kb, 1),
            "format": _infer_format(content_type_header, content_preview),
            "suggested_extract_fields": suggested_fields,
        }
    except httpx.TimeoutException:
        return {
            "reachable": False,
            "error_code": ErrorCode.TIMEOUT.value,
            "message": f"Request to '{url}' timed out",
            "actionable": True,
        }
    except Exception as exc:
        return {
            "reachable": False,
            "error_code": ErrorCode.INTERNAL_ERROR.value,
            "message": str(exc),
            "actionable": True,
        }


def _infer_format(content_type: str, content_preview: str) -> str:
    """Infer content format from content-type header and body preview."""
    if "xml" in content_type:
        return "xml"
    if "json" in content_type:
        return "json"
    if "html" in content_type or "xhtml" in content_type:
        return "html"
    if content_preview.strip().startswith(("<rss", "<feed", "<?xml")):
        return "rss"
    if content_preview.strip().startswith("{"):
        return "json"
    return "unknown"


def _handle_list_sources(domain: str) -> dict[str, Any]:
    """List all sources for a given domain."""
    try:
        config = _load_config()
    except Exception as exc:
        return _error_dict(exc)

    domain_cfg = _find_domain(config, domain)
    if domain_cfg is None:
        return {
            "error_code": ErrorCode.DOMAIN_NOT_FOUND.value,
            "message": f"Domain '{domain}' is not configured",
            "actionable": True,
        }

    sources = [
        {
            "source_id": f"{domain}:{s.name}",
            "name": s.name,
            "type": s.type,
            "url": s.url,
            "quality_tier": s.quality_tier,
            "tos_classification": s.tos_classification,
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
        config = _load_config()
    except Exception as exc:
        return _error_dict(exc)

    domain_cfg = _find_domain(config, domain)
    if domain_cfg is None:
        return {
            "error_code": ErrorCode.DOMAIN_NOT_FOUND.value,
            "message": f"Domain '{domain}' is not configured",
            "actionable": True,
        }

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
    _save_config(config)

    return {
        "topic": {"name": name, "keywords": keywords or []},
        "created": True,
        "topic_id": f"{domain}:{name}",
    }


def _handle_remove_topic(domain: str, topic_id: str, confirm: bool = True) -> dict[str, Any]:
    """Remove a topic by its topic_id (``domain:name``)."""
    if not confirm:
        return {
            "error_code": ErrorCode.CONFIRMATION_REQUIRED.value,
            "message": (
                f"This operation is destructive and requires confirmation. "
                f"Pass confirm=True to proceed."
            ),
            "actionable": True,
        }
    try:
        config = _load_config()
    except Exception as exc:
        return _error_dict(exc)

    domain_cfg = _find_domain(config, domain)
    if domain_cfg is None:
        return {
            "error_code": ErrorCode.DOMAIN_NOT_FOUND.value,
            "message": f"Domain '{domain}' is not configured",
            "actionable": True,
        }

    topic_name = topic_id.split(":", 1)[-1] if ":" in topic_id else topic_id
    for i, existing in enumerate(domain_cfg.topics):
        if existing.name == topic_name:
            removed = domain_cfg.topics.pop(i)
            _save_config(config)
            return {
                "removed": True,
                "topic_id": topic_id,
                "topic": {"name": removed.name, "keywords": removed.keywords},
            }

    return {
        "error_code": ErrorCode.TOPIC_NOT_FOUND.value,
        "message": f"Topic '{topic_name}' not found in domain '{domain}'",
        "actionable": True,
    }


def _handle_list_topics(domain: str) -> dict[str, Any]:
    """List all topics for a given domain."""
    try:
        config = _load_config()
    except Exception as exc:
        return _error_dict(exc)

    domain_cfg = _find_domain(config, domain)
    if domain_cfg is None:
        return {
            "error_code": ErrorCode.DOMAIN_NOT_FOUND.value,
            "message": f"Domain '{domain}' is not configured",
            "actionable": True,
        }

    topics = [
        {"name": t.name, "keywords": t.keywords}
        for t in domain_cfg.topics
    ]
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
        config = _load_config()
    except Exception as exc:
        return _error_dict(exc)

    domain_cfg = _find_domain(config, domain)
    if domain_cfg is None:
        return {
            "error_code": ErrorCode.DOMAIN_NOT_FOUND.value,
            "message": f"Domain '{domain}' is not configured",
            "actionable": True,
        }

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
            "keyword_count": len(t.keywords) if isinstance(t.keywords, list) else sum(len(v) for v in t.keywords.values()) if isinstance(t.keywords, dict) else 0,
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
# Keywords management tools (approve / reject / suggest)
# ---------------------------------------------------------------------------


def _handle_approve_keyword(domain: str, keyword: str) -> dict[str, Any]:
    """Approve a keyword — move from ``auto_added`` → ``verified``."""
    from autoinfo.keywords import KeywordsFile

    kf = KeywordsFile()
    result = kf.approve_keyword(domain=domain, keyword=keyword)
    if result is None:
        return {
            "error_code": ErrorCode.KEYWORD_NOT_FOUND.value,
            "message": f"Keyword '{keyword}' not found in domain '{domain}'",
            "actionable": True,
        }
    return {
        "success": True,
        "domain": domain,
        "keyword": keyword,
        "state": result.state.value,
    }


def _handle_reject_keyword(domain: str, keyword: str) -> dict[str, Any]:
    """Reject a keyword — move to ``deprecated``."""
    from autoinfo.keywords import KeywordsFile

    kf = KeywordsFile()
    result = kf.deprecate_keyword(domain=domain, keyword=keyword)
    if result is None:
        return {
            "error_code": ErrorCode.KEYWORD_NOT_FOUND.value,
            "message": f"Keyword '{keyword}' not found in domain '{domain}'",
            "actionable": True,
        }
    return {
        "success": True,
        "domain": domain,
        "keyword": keyword,
        "state": result.state.value,
    }


def _handle_suggest_keywords(
    domain: str,
    text: str,
    limit: int = 10,
) -> dict[str, Any]:
    """Use LLM to suggest keywords from the given text."""
    import json

    import litellm  # noqa: PLC0415 — deferred import

    from autoinfo.config import get_config_path, load_config

    try:
        config_path = get_config_path()
        if config_path:
            config = load_config(config_path)
            model = config.llm.model or "deepseek/deepseek-chat"
            api_key = config.llm.api_key or os.environ.get("AUTOINFO_LLM_API_KEY", "")
            base_url = config.llm.base_url or None
        else:
            model = "deepseek/deepseek-chat"
            api_key = os.environ.get("AUTOINFO_LLM_API_KEY", "")
            base_url = None
    except Exception:
        model = "deepseek/deepseek-chat"
        api_key = os.environ.get("AUTOINFO_LLM_API_KEY", "")
        base_url = None

    system_prompt = (
        "You are a keyword extraction assistant. Given a text, suggest "
        f"up to {limit} relevant keywords or short phrases (2-5 words) "
        "that capture the core topics. "
        "Respond with valid JSON only: an array of strings. "
        "Example: [\"machine learning\", \"neural networks\", \"deep learning\"]"
    )

    user_prompt = f"Extract up to {limit} keywords from this text:\n\n{text}"

    try:
        response = litellm.completion(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=500,
            temperature=0.3,
            api_base=base_url,
            api_key=api_key or None,
        )
        content: str = response.choices[0].message.content  # type: ignore[union-attr]

        parsed = json.loads(content)
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
        return _error_dict(exc)


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
        return {
            "error_code": ErrorCode.NOT_FOUND.value,
            "message": f"Entry '{content_id}' not found",
            "actionable": True,
        }

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
        return {
            "error_code": ErrorCode.NOT_FOUND.value,
            "message": f"Entry '{content_id}' not found",
            "actionable": True,
        }

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


# ---------------------------------------------------------------------------
# KB / output tools (v0.1 stubs — v0.2+ implementation)
# ---------------------------------------------------------------------------


def _handle_search_knowledge_base(
    query: str,
    domain: str = "",
    limit: int = 20,
    offset: int = 0,
    mode: str = "fts5",
    filter_tags: list[str] | None = None,
    filter_date_from: str | None = None,
    filter_date_to: str | None = None,
    filter_quality_tier_min: int | None = None,
    filter_quality_tier_max: int | None = None,
    filter_content_type: str | None = None,
    filter_language: str | None = None,
    user_id: str | None = None,
    include_stale: bool = False,
) -> dict[str, Any]:
    """Search the knowledge base using FTS5 full-text search.

    Parameters
    ----------
    mode:
        Search mode: ``"fts5"`` (default), ``"hybrid"`` (FTS5 + vector),
        or ``"vector"``.  Falls back to FTS5 when vector search is
        unavailable.
    include_stale:
        If False (default), stale entries are demoted to the bottom
        of search results.
    """
    from autoinfo.kb import KBStore

    store = KBStore()
    return store.search_knowledge_base(
        query=query,
        domain=domain,
        limit=limit,
        offset=offset,
        mode=mode,
        filter_tags=filter_tags,
        filter_date_from=filter_date_from,
        filter_date_to=filter_date_to,
        filter_quality_tier_min=filter_quality_tier_min,
        filter_quality_tier_max=filter_quality_tier_max,
        filter_content_type=filter_content_type,
        filter_language=filter_language,
        filter_user_id=user_id,
        include_stale=include_stale,
    )


def _handle_query_knowledge_graph(
    entity: str,
    relation: str = "related_to",
    domain: str = "",
    limit: int = 20,
) -> dict[str, Any]:
    """Query the knowledge graph for entities related to *entity*."""
    from autoinfo.kb import KBStore

    store = KBStore()
    return store.query_knowledge_graph(
        entity=entity,
        relation=relation,
        domain=domain,
        limit=limit,
    )


def _handle_flag_for_knowledge_base(
    summary_id: str,
    tags: list[str] | None = None,
    importance: int = 3,
) -> dict[str, Any]:
    """Flag a summary for KB inclusion.

    Dispatches to ``KBStore.flag_for_knowledge_base``.
    """
    from autoinfo.kb import KBStore

    store = KBStore()
    return store.flag_for_knowledge_base(
        summary_id=summary_id, tags=tags, importance=importance
    )


def _handle_get_summary(summary_id: str) -> dict[str, Any]:
    """Return full detail for a summary entry.

    Dispatches to ``KBStore.get_summary``.
    """
    from autoinfo.kb import KBStore

    store = KBStore()
    return store.get_summary(summary_id=summary_id)


def _handle_link_items(
    item_a_id: str,
    item_b_id: str,
    relation_type: str = "related",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a link between two KB entries."""
    from autoinfo.kb import KBStore

    store = KBStore()
    return store.link_items(
        item_a_id=item_a_id,
        item_b_id=item_b_id,
        relation_type=relation_type,
        metadata=metadata,
    )


def _handle_get_item_relations(
    item_id: str,
    relation_type: str | None = None,
) -> dict[str, Any]:
    """Return all relations where an item participates."""
    from autoinfo.kb import KBStore

    store = KBStore()
    relations = store.get_item_relations(
        item_id=item_id, relation_type=relation_type
    )
    return {"item_id": item_id, "relations": relations, "count": len(relations)}


def _handle_get_entry_history(entry_id: str) -> dict[str, Any]:
    """Return all saved backup versions for an entry."""
    from autoinfo.kb import KBStore

    store = KBStore()
    versions = store.get_entry_history(entry_id=entry_id)
    return {"entry_id": entry_id, "versions": versions, "count": len(versions)}


def _handle_restore_entry_version(version_id: str) -> dict[str, Any]:
    """Restore an entry from a saved version backup."""
    from autoinfo.kb import KBStore

    store = KBStore()
    return store.restore_entry_version(version_id=version_id)


def _handle_compare_versions(
    entry_id: str, version_a: str, version_b: str
) -> dict[str, Any]:
    """Compare two versions of a KB entry and return a structured diff."""
    from autoinfo.kb import KBStore

    store = KBStore()
    return store.compare_versions(
        entry_id=entry_id, version_a=version_a, version_b=version_b
    )


def _handle_get_collection_stats(period: str = "daily") -> dict[str, Any]:
    """Aggregated collection statistics for the given period."""
    from autoinfo.kb import KBStore

    store = KBStore()
    return store.get_collection_stats(period=period)


def _handle_get_collection_diff(since_collection_id: str) -> dict[str, Any]:
    """Return entries collected since a previous collection ID."""
    from autoinfo.kb import KBStore

    store = KBStore()
    return store.get_collection_diff(
        since_collection_id=since_collection_id
    )


def _handle_get_domain_decay(
    domain: str, ttl_days: int = 90
) -> dict[str, Any]:
    """Compute decay / staleness metrics for a domain."""
    from autoinfo.kb import KBStore

    store = KBStore()
    return store.get_domain_decay(domain=domain, ttl_days=ttl_days)


def _handle_create_kb_draft(
    raw_ids: list[str],
    title: str,
    summary: str = "",
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Create a Draft entry from one or more Raw entries."""
    from autoinfo.kb import KBStore

    store = KBStore()
    try:
        entry = store.create_kb_draft(
            raw_ids=raw_ids, title=title, summary=summary, tags=tags
        )
        return entry.to_dict()
    except ValueError as exc:
        return {
            "error_code": ErrorCode.VALIDATION_ERROR.value,
            "message": str(exc),
            "actionable": True,
        }


def _handle_reject_kb_draft(
    draft_id: str,
    reason: str = "",
    action: str = "back_to_raw",
) -> dict[str, Any]:
    """Reject a Draft, moving it back to 01-Raw or archiving."""
    from autoinfo.kb import KBStore

    store = KBStore()
    try:
        return store.reject_kb_draft(
            draft_id=draft_id, reason=reason, action=action
        )
    except (ValueError, FileNotFoundError) as exc:
        return {
            "error_code": ErrorCode.INTERNAL_ERROR.value,
            "message": str(exc),
            "actionable": True,
        }


def _handle_list_kb_tier(
    domain: str,
    tier: str,
    limit: int = 50,
    offset: int = 0,
    user_id: str | None = None,
) -> dict[str, Any]:
    """List entries in a specific KB tier.

    Parameters
    ----------
    user_id:
        Optional user_id filter — only entries belonging to this user
        are returned. When ``None``, no user filter is applied.
    """
    from autoinfo.kb import KBStore

    store = KBStore()
    entries = store.list_kb_tier(domain=domain, tier=tier, limit=limit, offset=offset, user_id=user_id)
    return {
        "domain": domain,
        "tier": tier,
        "entries": entries,
        "count": len(entries),
    }


def _handle_reindex_kb(domain: str) -> dict[str, Any]:
    """Rebuild SQLite index from disk frontmatter.

    Dispatches to ``KBStore.reindex_knowledge_base``.
    """
    from autoinfo.kb import KBStore

    store = KBStore()
    return store.reindex_knowledge_base(domain=domain)


def _handle_list_output_templates(domain: str = "", user_id: str | None = None) -> dict[str, Any]:
    """List available output templates for a domain, optionally filtered by user tier.

    When *user_id* is provided, templates are filtered so that only those
    whose ``access_level`` is accessible to the user are returned.
    When *user_id* is ``None``, all templates are returned (backward compatible).
    """
    from autoinfo.output import list_output_templates as _list_output_templates
    from autoinfo.billing import check_access

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

    return result


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
) -> dict[str, Any]:
    """Generate a digest of KB entries for *domain* over the given *period*.

    Dispatches to :func:`autoinfo.output.generate_digest`.
    """
    from autoinfo.output import generate_digest as _generate_digest

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
        )
        if format in ("json", "agent"):
            # Parse JSON string back to dict for structured MCP response
            import json as _json

            return {"success": True, "format": format, "content": _json.loads(result)}
        if format == "audio":
            return {
                "success": True,
                "format": "audio",
                "content_type": "audio/mp3",
                "encoding": "base64",
                "content": result,
            }
        return {"success": True, "format": format, "content": result}
    except ValueError as exc:
        return {
            "error_code": ErrorCode.VALIDATION_ERROR.value,
            "message": str(exc),
            "actionable": True,
        }
    except Exception as exc:
        logger.exception("Digest generation failed for domain '%s'", domain)
        return _error_dict(exc)


def _handle_generate_report(
    domain: str,
    format: str = "markdown",
    period: str = "month",
    custom_instructions: str = "",
    target_audience: str = "",
    user_id: str = "",
) -> dict[str, Any]:
    """Generate a structured report for *domain* over the given *period*.

    Dispatches to :func:`autoinfo.output.generate_report`.
    """
    from autoinfo.output import generate_report as _generate_report

    try:
        result = _generate_report(domain=domain, format=format, period=period, custom_instructions=custom_instructions, target_audience=target_audience, user_id=user_id)
        if format in ("json", "agent"):
            import json as _json

            parsed = _json.loads(result)
            return {
                "success": True,
                "domain": domain,
                "format": format,
                "period": period,
                "content": parsed,
            }
        if format == "audio":
            return {
                "success": True,
                "domain": domain,
                "format": "audio",
                "period": period,
                "content_type": "audio/mp3",
                "encoding": "base64",
                "content": result,
            }
        return {
            "success": True,
            "domain": domain,
            "format": format,
            "period": period,
            "content": result,
        }
    except ValueError as exc:
        return {
            "error_code": ErrorCode.VALIDATION_ERROR.value,
            "message": str(exc),
            "actionable": True,
        }
    except Exception as exc:
        logger.exception("Report generation failed for domain '%s'", domain)
        return _error_dict(exc)


def _handle_generate_tutorial(
    domain: str,
    topic: str | None = None,
    format: str = "markdown",
    custom_instructions: str = "",
) -> dict[str, Any]:
    """Generate a structured tutorial for *domain*.

    Thin wrapper around :func:`autoinfo.output.generate_tutorial`.
    """
    from autoinfo.output import generate_tutorial as _generate_tutorial

    try:
        result = _generate_tutorial(domain=domain, format=format, custom_instructions=custom_instructions)
        return {"success": True, "format": format, "domain": domain, "topic": topic, "content": result}
    except ValueError as exc:
        return {
            "error_code": ErrorCode.VALIDATION_ERROR.value,
            "message": str(exc),
            "actionable": True,
        }
    except Exception as exc:
        logger.exception("Tutorial generation failed for domain '%s'", domain)
        return _error_dict(exc)


def _handle_generate_presentation(
    domain: str,
    topic: str | None = None,
    slides: int = 10,
    format: str = "markdown",
    custom_instructions: str = "",
) -> dict[str, Any]:
    """Generate a slide-based presentation for *topic* within *domain*.

    Thin wrapper around :func:`autoinfo.output.generate_presentation`.
    """
    from autoinfo.output import generate_presentation as _generate_presentation

    try:
        topic_str = topic or ""
        result = _generate_presentation(domain=domain, topic=topic_str, slide_count=slides, format=format, custom_instructions=custom_instructions)
        return {"success": True, "domain": domain, "topic": topic, "slides": slides, "format": format, "content": result}
    except ValueError as exc:
        return {
            "error_code": ErrorCode.VALIDATION_ERROR.value,
            "message": str(exc),
            "actionable": True,
        }
    except Exception as exc:
        logger.exception("Presentation generation failed for domain '%s'", domain)
        return _error_dict(exc)


def _handle_send_email_digest(
    domain: str,
    period: str = "weekly",
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

    Returns
    -------
    dict
        ``{success, message, recipients, domain, period}``.
    """
    from autoinfo.email_sender import send_digest as _send_email

    try:
        config = _load_config()
    except Exception as exc:
        return _error_dict(exc)

    if not config.email.enabled:
        return {
            "error_code": ErrorCode.EMAIL_NOT_ENABLED.value,
            "message": (
                "Email delivery is not enabled. "
                "Set 'email.enabled: true' in .autoinfo/config.yaml "
                "and configure email.smtp_host, email.from_addr, "
                "and email.to_addrs."
            ),
            "actionable": True,
        }

    try:
        result = _send_email(domain=domain, period=period, config=config)
        return result
    except RuntimeError as exc:
        return {
            "error_code": ErrorCode.EMAIL_SEND_FAILED.value,
            "message": str(exc),
            "actionable": True,
        }
    except Exception as exc:
        logger.exception("Email digest send failed for domain '%s'", domain)
        return _error_dict(exc)


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
        return result
    except ValueError as exc:
        return {
            "error_code": ErrorCode.VALIDATION_ERROR.value,
            "message": str(exc),
            "actionable": True,
        }
    except Exception as exc:
        logger.exception("Localization failed")
        return _error_dict(exc)


# ---------------------------------------------------------------------------
# Export / Import (2)
# ---------------------------------------------------------------------------


def _handle_export_kb(
    domain: str,
    format: str = "markdown",
    scope: str = "domain",
    entry_ids: list[str] | None = None,
    output_path: str | None = None,
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

        result = _export_kb(domain=domain, format=format, collection_id=collection_id)

        file_path = result.get("path", "")
        if file_path and os.path.isfile(file_path):
            result["file_size_bytes"] = os.path.getsize(file_path)
        else:
            result["file_size_bytes"] = 0

        return result
    except ValueError as exc:
        return {
            "error_code": ErrorCode.VALIDATION_ERROR.value,
            "message": str(exc),
            "actionable": True,
        }
    except Exception as exc:
        logger.exception("Export KB failed for domain '%s'", domain)
        return _error_dict(exc)


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
        return result
    except ValueError as exc:
        return {
            "error_code": ErrorCode.VALIDATION_ERROR.value,
            "message": str(exc),
            "actionable": True,
        }
    except Exception as exc:
        logger.exception("Import KB failed for domain '%s'", domain)
        return _error_dict(exc)


# ---------------------------------------------------------------------------
# Schedule management tools
# ---------------------------------------------------------------------------


def _handle_list_schedules() -> dict[str, Any]:
    """List all configured schedules."""
    try:
        from autoinfo.cli.cron import load_schedules

        schedules = load_schedules()
        items = []
        for name, s in schedules.items():
            items.append({
                "name": name,
                "expression": s.expression,
                "domain": s.domain,
                "enabled": s.enabled,
                "last_run": s.last_run,
                "created_at": s.created_at,
            })
        return {"schedules": items, "count": len(items)}
    except Exception as exc:
        return _error_dict(exc)


def _handle_add_schedule(
    name: str,
    expression: str,
    domain: str,
    schedule_type: str = "collection",
    recipients: list[str] | None = None,
    output_format: str = "html",
) -> dict[str, Any]:
    """Add a new collection or digest schedule."""
    try:
        if schedule_type not in ("collection", "digest"):
            return {
                "error_code": ErrorCode.VALIDATION_ERROR.value,
                "message": f"Invalid schedule type '{schedule_type}'. Must be 'collection' or 'digest'.",
                "actionable": True,
            }

        if schedule_type == "digest":
            if not recipients:
                return {
                    "error_code": ErrorCode.VALIDATION_ERROR.value,
                    "message": "Recipients are required for digest-type schedules.",
                    "actionable": True,
                }
            try:
                config = _load_config()
            except Exception as exc:
                return _error_dict(exc)
            if not config.email.enabled:
                return {
                    "error_code": ErrorCode.EMAIL_NOT_ENABLED.value,
                    "message": (
                        "Email delivery is not enabled. Digest schedules require "
                        "email to be configured. Set 'email.enabled: true' in "
                        ".autoinfo/config.yaml and configure email.smtp_host, "
                        "email.from_addr, and email.to_addrs."
                    ),
                    "actionable": True,
                }

        from croniter import croniter

        if not croniter.is_valid(expression):
            return {
                "error_code": ErrorCode.INVALID_CRON_EXPRESSION.value,
                "message": f"'{expression}' is not a valid cron expression",
                "actionable": True,
            }

        from autoinfo.cli.cron import Schedule, _now_iso, load_schedules, save_schedules

        schedules = load_schedules()
        if name in schedules:
            return {
                "error_code": ErrorCode.SCHEDULE_ALREADY_EXISTS.value,
                "message": f"A schedule named '{name}' already exists",
                "actionable": True,
            }

        new_schedule = Schedule(
            name=name,
            expression=expression,
            domain=domain,
            type=schedule_type,
            enabled=True,
            last_run=None,
            created_at=_now_iso(),
            recipients=recipients or [],
            format=output_format,
        )
        schedules[name] = new_schedule
        save_schedules(schedules)
        return {
            "created": True,
            "schedule": {
                "name": name,
                "expression": expression,
                "domain": domain,
                "type": schedule_type,
                "enabled": True,
                "last_run": None,
                "created_at": new_schedule.created_at,
                "recipients": recipients or [],
                "format": output_format,
            },
        }
    except Exception as exc:
        return _error_dict(exc)


def _handle_remove_schedule(name: str, confirm: bool = False) -> dict[str, Any]:
    """Remove a collection schedule."""
    if not confirm:
        return {
            "error_code": ErrorCode.CONFIRMATION_REQUIRED.value,
            "message": (
                f"This operation is destructive and requires confirmation. "
                f"Pass confirm=True to proceed."
            ),
            "actionable": True,
        }
    try:
        from autoinfo.cli.cron import load_schedules, save_schedules

        schedules = load_schedules()
        if name not in schedules:
            return {
                "error_code": ErrorCode.SCHEDULE_NOT_FOUND.value,
                "message": f"Schedule '{name}' not found",
                "actionable": True,
            }
        removed = schedules.pop(name)
        save_schedules(schedules)
        return {
            "removed": True,
            "schedule": {
                "name": removed.name,
                "expression": removed.expression,
                "domain": removed.domain,
            },
        }
    except Exception as exc:
        return _error_dict(exc)


def _handle_run_schedules(
    dry_run: bool = False,
    name: str | None = None,
) -> dict[str, Any]:
    """Run due schedules."""
    try:
        from autoinfo.cli.cron import run_due_schedules

        results = run_due_schedules(
            dry_run=dry_run,
            schedule_filter=name,
            json_output=True,
        )
        due_count = sum(1 for r in results if r.get("due"))
        ran_count = sum(1 for r in results if r.get("ran"))
        return {
            "results": results,
            "due_count": due_count,
            "ran_count": ran_count,
            "total_checked": len(results),
        }
    except Exception as exc:
        return _error_dict(exc)


def _handle_get_schedule_status(
    schedule_id: str | None = None,
) -> dict[str, Any]:
    """Get status of all schedules or a specific one."""
    try:
        from autoinfo.cli.cron import get_schedule_status

        schedules = get_schedule_status(schedule_id=schedule_id)
        return {
            "schedules": schedules,
            "count": len(schedules),
        }
    except Exception as exc:
        return _error_dict(exc)


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
        config = _load_config()
        model_config: dict[str, Any] = {}
        if config.cefr.model:
            model_config["model"] = config.cefr.model
        elif config.llm.provider and config.llm.model:
            model_config["model"] = f"{config.llm.provider}/{config.llm.model}"
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


# ---------------------------------------------------------------------------
# Source health / feedback tools
# ---------------------------------------------------------------------------


def _handle_get_source_health(source_id: str) -> dict[str, Any]:
    """Return health status for a single source."""
    from autoinfo.status import get_source_health

    return get_source_health(source_id=source_id)


def _handle_rate_item(
    item_id: str,
    rating: int,
    feedback: str = "",
) -> dict[str, Any]:
    """Store user rating/feedback for a collected item."""
    from autoinfo.status import rate_item

    return rate_item(item_id=item_id, rating=rating, feedback=feedback)


# ---------------------------------------------------------------------------
# Q&A tool
# ---------------------------------------------------------------------------


def _handle_query_collected(
    query: str,
    domain: str,
    content_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Q&A on collected content via FTS5 + LLM synthesis.

    Dispatches to ``autoinfo.qa.query_collected``.
    """
    from autoinfo.qa import query_collected as _qa

    return _qa(query=query, domain=domain, content_ids=content_ids)


# ---------------------------------------------------------------------------
# Project / batch / config tools (v0.5)
# ---------------------------------------------------------------------------


def _handle_init_project(
    domain: str,
    project_name: str = "",
    dry_run: bool = False,
    llm_provider: str = "",
    llm_model: str = "",
    llm_base_url: str = "",
) -> dict[str, Any]:
    """Initialize AutoInfo project skeleton (creates .autoinfo/ directory,
    config, demo domain). Idempotent — safe to call when already initialized.

    Parameters
    ----------
    domain:
        Demo domain name (e.g. medical-research).
    project_name:
        Optional human-friendly project name.
    dry_run:
        If True, preview what would be created without writing files.
    llm_provider:
        Override the default LLM provider (e.g. \"openai\").
    llm_model:
        Override the default LLM model (e.g. \"gpt-4\").
    llm_base_url:
        Override the default LLM base URL (e.g. \"http://localhost:11434/v1\").
    """
    # Lazy imports to avoid circular dependencies
    from autoinfo.cli.init import _DEMO_DOMAINS_DIR, _ensure_dir, _run_init
    from autoinfo.mcp.errors import ErrorCode, error_dict

    autoinfo_dir = Path.cwd() / ".autoinfo"
    config_path = autoinfo_dir / "config.yaml"

    # Idempotency check — skip if already initialized
    if config_path.exists() and not dry_run:
        return {
            "status": "skipped",
            "message": "Already initialized",
        }

    # Validate domain against available demo domains
    demo_sources = _DEMO_DOMAINS_DIR / domain / "sources.yaml"
    if not demo_sources.is_file():
        available = sorted(
            d.name for d in _DEMO_DOMAINS_DIR.iterdir()
            if d.is_dir()
        )
        return {
            "error_code": ErrorCode.VALIDATION_ERROR.value,
            "message": f"Unknown demo domain '{domain}'. Available: {available}",
            "actionable": True,
            "success": False,
            "error": {
                "code": ErrorCode.VALIDATION_ERROR.value,
                "message": f"Unknown demo domain '{domain}'. Available: {available}",
                "actionable": True,
            },
        }

    if dry_run:
        return {
            "status": "dry_run",
            "domain": domain,
            "project_name": project_name,
            "autoinfo_dir": str(autoinfo_dir),
            "llm_provider": llm_provider or "(default)",
            "llm_model": llm_model or "(default)",
            "llm_base_url": llm_base_url or "(default)",
            "would_create_dirs": [
                ".autoinfo/",
                ".autoinfo/knowledge/00-Inbox/",
                ".autoinfo/knowledge/01-Raw/",
                ".autoinfo/knowledge/02-Draft/",
                ".autoinfo/knowledge/03-Wiki/",
                ".autoinfo/collections/",
                ".autoinfo/outputs/",
            ],
            "would_create_files": [
                ".autoinfo/config.yaml",
                ".autoinfo/sources.yaml",
            ],
            "message": "Dry run — no files were created",
        }

    try:
        _ensure_dir(autoinfo_dir)
        _run_init(domain, autoinfo_dir, project_name=project_name)

        if llm_provider or llm_model or llm_base_url:
            import yaml
            config_path = autoinfo_dir / "config.yaml"
            if config_path.exists():
                with open(config_path, "r") as f:
                    cfg = yaml.safe_load(f)
                if llm_provider:
                    cfg.setdefault("llm", {})["provider"] = llm_provider
                if llm_model:
                    cfg.setdefault("llm", {})["model"] = llm_model
                if llm_base_url:
                    cfg.setdefault("llm", {})["base_url"] = llm_base_url
                with open(config_path, "w") as f:
                    yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)

        return {
            "status": "success",
            "domain": domain,
            "project_name": project_name,
            "autoinfo_dir": str(autoinfo_dir),
            "llm_provider": llm_provider or "(default)",
            "llm_model": llm_model or "(default)",
            "llm_base_url": llm_base_url or "(default)",
            "message": f"AutoInfo initialized for '{domain}'",
        }
    except Exception as exc:
        logger.exception("Init project failed for domain '%s'", domain)
        return {
            "error_code": ErrorCode.INTERNAL_ERROR.value,
            "message": str(exc),
            "actionable": True,
            "success": False,
            "error": {
                "code": ErrorCode.INTERNAL_ERROR.value,
                "message": str(exc),
                "actionable": True,
            },
        }


def _handle_list_projects(status: str = "") -> dict[str, Any]:
    """List all configured projects with domain/source summaries."""
    try:
        config = _load_config()
    except Exception as exc:
        return {"projects": [], "count": 0, "error_code": ErrorCode.INTERNAL_ERROR.value, "message": str(exc), "actionable": True}

    from autoinfo.config import get_config_path

    cfg_path = get_config_path()
    projects = [
        {
            "name": config.project.name if hasattr(config, "project") else "default",
            "config_path": str(cfg_path) if cfg_path else "",
            "domain_count": len([d for d in config.domains if d.active]),
            "total_sources": sum(
                len(d.sources) for d in config.domains if d.active
            ),
            "total_topics": sum(
                len(d.topics) for d in config.domains if d.active
            ),
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

    return assets


def _handle_archive_project(reason: str = "", confirm: bool = False) -> dict[str, Any]:
    """Archive the current project (refuses unless published to 03-Wiki)."""
    if not confirm:
        return {
            "error_code": ErrorCode.CONFIRMATION_REQUIRED.value,
            "message": (
                f"This operation is destructive and requires confirmation. "
                f"Pass confirm=True to proceed."
            ),
            "actionable": True,
        }
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
        return {
            "error_code": ErrorCode.NOT_PUBLISHED.value,
            "message": (
                "Cannot archive project: no entries have been promoted to "
                "03-Wiki. Publish at least one Draft entry before archiving. "
                "Use create_kb_draft raw_ids=[...] title=... to create a Draft, "
                "then the human director can promote it to 03-Wiki."
            ),
            "actionable": True,
        }

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
) -> dict[str, Any]:
    """Run collect + process in sequence for a domain. Returns per-phase results."""
    from autoinfo.collect import run_collection
    from autoinfo.process import ProcessResult, run_processing

    from datetime import datetime, timezone

    start_time = datetime.now(timezone.utc)
    phases: list[dict[str, Any]] = []

    collect_args: dict[str, Any] = {"domain": domain, "limit": limit}
    if topic:
        collect_args["topic"] = topic

    phase_start = datetime.now(timezone.utc)
    try:
        collected = run_collection(**collect_args)
        phase_duration = (datetime.now(timezone.utc) - phase_start).total_seconds()
        phases.append({
            "phase": "collection",
            "status": "completed",
            "result": collected,
            "duration_s": round(phase_duration, 2),
        })
    except Exception as exc:
        phase_duration = (datetime.now(timezone.utc) - phase_start).total_seconds()
        phases.append({
            "phase": "collection",
            "status": "failed",
            "error": str(exc),
            "duration_s": round(phase_duration, 2),
        })

    if phases[-1]["status"] == "completed":
        process_args: dict[str, Any] = {"domain": domain}
        if model:
            process_args["model"] = model

        phase_start = datetime.now(timezone.utc)
        try:
            processed: ProcessResult = run_processing(**process_args)
            processed_dict = asdict(processed)
            phase_duration = (datetime.now(timezone.utc) - phase_start).total_seconds()
            phases.append({
                "phase": "processing",
                "status": "completed",
                "result": processed_dict,
                "duration_s": round(phase_duration, 2),
            })
        except Exception as exc:
            phase_duration = (datetime.now(timezone.utc) - phase_start).total_seconds()
            phases.append({
                "phase": "processing",
                "status": "failed",
                "error": str(exc),
                "duration_s": round(phase_duration, 2),
            })
    else:
        phases.append({
            "phase": "processing",
            "status": "skipped",
            "reason": "collection failed",
        })

    total_duration = (datetime.now(timezone.utc) - start_time).total_seconds()
    overall_success = all(p["status"] == "completed" for p in phases)

    return {
        "domain": domain,
        "topic": topic or "*",
        "phases": phases,
        "overall_success": overall_success,
        "total_duration_s": round(total_duration, 2),
    }


def _handle_list_active_collections(domain: str = "") -> dict[str, Any]:
    """List active / in-progress collection runs."""
    from autoinfo.collect import list_active_collections as _list_active

    try:
        active = _list_active()
    except Exception as exc:
        return {"active_collections": [], "count": 0, "error_code": ErrorCode.INTERNAL_ERROR.value, "message": str(exc), "actionable": True}

    if domain:
        active = [c for c in active if c.get("domain") == domain]

    return {
        "active_collections": active,
        "count": len(active),
    }


# ---------------------------------------------------------------------------
# Gate config handlers
# ---------------------------------------------------------------------------


def _handle_get_gate_config(domain: str, gate: str) -> dict[str, Any]:
    """Return gate configuration for a domain.

    Checks both quality gates (G0-G5 etc.) and delivery gates (D1-D3 etc.),
    falling back to global defaults when the gate is not set at the domain level.
    """
    try:
        config = _load_config()
    except Exception as exc:
        return _error_dict(exc)

    domain_cfg = _find_domain(config, domain)
    if domain_cfg is None:
        return {
            "error_code": ErrorCode.DOMAIN_NOT_FOUND.value,
            "message": f"Domain '{domain}' is not configured",
            "actionable": True,
        }

    from dataclasses import asdict as _asdict

    # Check quality gates first, then delivery gates, then global defaults
    gate_config: dict[str, Any] | None = None
    gate_type: str = ""

    if gate in domain_cfg.quality_gates:
        gate_config = _asdict(domain_cfg.quality_gates[gate])
        gate_type = "quality"
    elif gate in domain_cfg.delivery_gates:
        gate_config = _asdict(domain_cfg.delivery_gates[gate])
        gate_type = "delivery"
    elif gate in config.quality_gates:
        gate_config = _asdict(config.quality_gates[gate])
        gate_type = "quality"
    elif gate in config.delivery_gates:
        gate_config = _asdict(config.delivery_gates[gate])
        gate_type = "delivery"

    if gate_config is None:
        return {
            "error_code": "GateNotFound",
            "message": f"Gate '{gate}' is not configured for domain '{domain}'",
            "actionable": True,
        }

    # Remove internal fields from serialization
    gate_config.pop("name", None)

    return {
        "domain": domain,
        "gate": gate,
        "gate_type": gate_type,
        "config": gate_config,
    }


def _handle_set_gate_config(
    domain: str,
    gate: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Update gate configuration for a domain.

    *config* should contain gate-specific fields (e.g. ``action``, ``threshold``
    for quality gates; ``enabled``, ``action_on_failure`` for delivery gates).
    """
    try:
        cfg = _load_config()
    except Exception as exc:
        return _error_dict(exc)

    domain_cfg = _find_domain(cfg, domain)
    if domain_cfg is None:
        return {
            "error_code": ErrorCode.DOMAIN_NOT_FOUND.value,
            "message": f"Domain '{domain}' is not configured",
            "actionable": True,
        }

    from autoinfo.config import DeliveryGateConfig, QualityGateConfig

    # Determine if this is a quality or delivery gate
    is_delivery = (
        gate in domain_cfg.delivery_gates
        or ("action_on_failure" in config)
        or ("enabled" in config and "category" not in config)
    )
    is_quality = (gate in domain_cfg.quality_gates) or not is_delivery

    new_gc: QualityGateConfig | None = None
    new_dc: DeliveryGateConfig | None = None

    if is_quality:
        new_gc = QualityGateConfig(
            name=gate,
            category=str(config.get("category", "soft")),
            retries=int(config.get("retries", 0)),
            retry_models=list(config.get("retry_models", [])),
            action=str(config.get("action", "flag")),
            threshold=config.get("threshold", None),
        )
        domain_cfg.quality_gates[gate] = new_gc
    else:
        new_dc = DeliveryGateConfig(
            name=gate,
            enabled=bool(config.get("enabled", True)),
            action_on_failure=str(config.get("action_on_failure", "block")),
        )
        domain_cfg.delivery_gates[gate] = new_dc

    _save_config(cfg)

    # Both branches of is_quality/is_delivery set one of new_gc/new_dc
    if is_quality and new_gc is not None:
        from dataclasses import asdict as _asdict
        config_dict = _asdict(new_gc)
    elif new_dc is not None:
        from dataclasses import asdict as _asdict
        config_dict = _asdict(new_dc)
    else:
        config_dict = {}

    return {
        "domain": domain,
        "gate": gate,
        "updated": True,
        "config": config_dict,
    }


# ---------------------------------------------------------------------------
# Budget threshold handlers (F45)
# ---------------------------------------------------------------------------


def _handle_get_budget_thresholds() -> dict[str, Any]:
    """Return current budget thresholds with spend status.

    Reads ``cost_alerts.budget_thresholds`` from the project config and
    queries ``CostMeter`` for total spend, then returns each threshold
    with its comparison status.
    """
    try:
        config = _load_config()
    except Exception as exc:
        return _error_dict(exc)

    thresholds = config.cost_alerts.budget_thresholds
    if not thresholds:
        thresholds = [50.0, 75.0, 90.0, 100.0]

    from autoinfo.cost import CostMeter
    meter = CostMeter()
    report = meter.get_report()
    current_spend = report["total_cost"]

    status: list[dict[str, Any]] = []
    for t in sorted(thresholds):
        pct = round(current_spend / t * 100, 2) if t > 0 else 0.0
        breached = current_spend >= t
        status.append({
            "threshold": t,
            "current_spend": round(current_spend, 8),
            "pct_used": pct,
            "breached": breached,
            "severity": "critical" if t >= 100 and breached else "warning" if breached else "ok",
        })

    return {
        "budget_thresholds": thresholds,
        "current_spend": round(current_spend, 8),
        "auto_remediation_enabled": config.cost_alerts.auto_remediation_enabled,
        "alert_webhook": config.cost_alerts.alert_webhook,
        "threshold_status": status,
    }


def _handle_set_budget_thresholds(
    thresholds: list[float],
    auto_remediation_enabled: bool = False,
    alert_webhook: str = "",
) -> dict[str, Any]:
    """Update budget thresholds in the project config (in-memory + persist).

    Parameters
    ----------
    thresholds:
        New percentage thresholds (e.g. ``[30.0, 60.0, 90.0, 100.0]``).
    auto_remediation_enabled:
        Whether auto-remediation is active (V2 — not yet implemented).
    alert_webhook:
        Optional webhook URL for budget alert notifications.
    """
    try:
        config = _load_config()
    except Exception as exc:
        return _error_dict(exc)

    if not thresholds:
        return {
            "error_code": "InvalidArguments",
            "message": "thresholds must be a non-empty list of floats",
            "actionable": True,
        }

    config.cost_alerts.budget_thresholds = [float(t) for t in thresholds]
    if auto_remediation_enabled:
        config.cost_alerts.auto_remediation_enabled = True
    if alert_webhook:
        config.cost_alerts.alert_webhook = alert_webhook

    _save_config(config)

    return {
        "budget_thresholds": config.cost_alerts.budget_thresholds,
        "auto_remediation_enabled": config.cost_alerts.auto_remediation_enabled,
        "alert_webhook": config.cost_alerts.alert_webhook,
        "updated": True,
    }


# ---------------------------------------------------------------------------
# Product handlers
# ---------------------------------------------------------------------------


def _handle_get_product(domain: str, product_type: str) -> dict[str, Any]:
    """Return product configuration for a domain and product type.

    *product_type* is ``"RAW"`` or ``"PROCESSED"``.  Products are derived
    from the domain's configuration (sources, quality gates, delivery
    channels, etc.).
    """
    try:
        cfg = _load_config()
    except Exception as exc:
        return _error_dict(exc)

    domain_cfg = _find_domain(cfg, domain)
    if domain_cfg is None:
        return {
            "error_code": ErrorCode.DOMAIN_NOT_FOUND.value,
            "message": f"Domain '{domain}' is not configured",
            "actionable": True,
        }

    product_type_upper = product_type.upper()
    if product_type_upper not in ("RAW", "PROCESSED"):
        return {
            "error_code": "ValidationError",
            "message": f"Invalid product_type '{product_type}'. Must be 'RAW' or 'PROCESSED'.",
            "actionable": True,
        }

    if product_type_upper == "RAW":
        product = {
            "id": f"{domain}-raw",
            "domain": domain,
            "type": "raw",
            "name": f"{domain} RAW Feed",
            "config": {
                "sources": [
                    {"name": s.name, "type": s.type, "url": s.url}
                    for s in domain_cfg.sources
                ],
                "extract_fields": list(getattr(domain_cfg, "extract_fields", [])),
            },
            "templates": [],
            "delivery_channels": ["api"],
            "quality_gates": list(domain_cfg.quality_gates.keys()),
        }
    else:
        product = {
            "id": f"{domain}-processed",
            "domain": domain,
            "type": "processed",
            "name": f"{domain} PROCESSED Output",
            "config": {
                "delivery_gates": {
                    dg: _gate_to_dict(gc)
                    for dg, gc in domain_cfg.delivery_gates.items()
                },
                "webhook_urls": list(getattr(domain_cfg, "webhook_urls", [])),
                "search_mode": getattr(domain_cfg, "search_mode", "keyword"),
            },
            "templates": ["digest", "report", "tutorial", "presentation"],
            "delivery_channels": ["webhook", "smtp", "api", "export"],
            "quality_gates": list(domain_cfg.quality_gates.keys()),
        }

    return {"product": product}


def _handle_list_products(domain: str) -> dict[str, Any]:
    """List all configured products for a domain.

    Returns both RAW and PROCESSED product types derived from the
    domain's configuration.
    """
    try:
        cfg = _load_config()
    except Exception as exc:
        return _error_dict(exc)

    domain_cfg = _find_domain(cfg, domain)
    if domain_cfg is None:
        return {
            "error_code": ErrorCode.DOMAIN_NOT_FOUND.value,
            "message": f"Domain '{domain}' is not configured",
            "actionable": True,
        }

    raw_product = {
        "id": f"{domain}-raw",
        "domain": domain,
        "type": "raw",
        "name": f"{domain} RAW Feed",
        "source_count": len(domain_cfg.sources),
        "extract_fields": list(getattr(domain_cfg, "extract_fields", [])),
        "quality_gate_count": len(domain_cfg.quality_gates),
    }

    processed_product = {
        "id": f"{domain}-processed",
        "domain": domain,
        "type": "processed",
        "name": f"{domain} PROCESSED Output",
        "delivery_channel_count": len(
            list(getattr(domain_cfg, "webhook_urls", [])) + ["smtp", "api", "export"]
        ),
        "delivery_gate_count": len(domain_cfg.delivery_gates),
        "templates": ["digest", "report", "tutorial", "presentation"],
    }

    return {
        "domain": domain,
        "products": [raw_product, processed_product],
        "count": 2,
    }


def _handle_send_to_enduser(
    end_user_id: str,
    product_type: str,
    product_id: str,
    channel: str | None = None,
) -> dict[str, Any]:
    """Dispatch a product to an end user through a delivery channel.

    Looks up the end-user profile, resolves the delivery channel
    (from the *channel* parameter or the user's stored preferences),
    builds a :class:`Product` model, and dispatches through the
    existing :func:`deliver_with_retry` framework.

    Parameters
    ----------
    end_user_id:
        User ID of the recipient (must exist in the user store).
    product_type:
        ``"raw"`` or ``"processed"``.
    product_id:
        Product identifier (e.g. ``"medical-research-processed"``).
    channel:
        Delivery channel name (``"smtp"``, ``"webhook"``, …).
        Falls back to the user's ``delivery_preferences["channel"]``
        when omitted, then to ``"smtp"``.

    Returns
    -------
    dict
        ``{delivery_id, status, channel, recipient_count, error}``.
    """
    import uuid as _uuid

    from autoinfo.delivery import deliver_with_retry, get_channel
    from autoinfo.models import Product, ProductType
    from autoinfo.user_store import get_profile as _get_profile

    profile = _get_profile(end_user_id)
    if profile is None:
        return {
            "error_code": ErrorCode.VALIDATION_ERROR.value,
            "message": f"End user '{end_user_id}' not found",
            "actionable": True,
        }

    channel_name: str = (
        channel
        or profile.delivery_preferences.get("channel")
        or "smtp"
    )

    domain: str = product_id
    for suffix in ("-raw", "-processed"):
        if product_id.endswith(suffix):
            domain = product_id[: -len(suffix)]
            break

    product = Product(
        id=product_id,
        domain=domain,
        type=ProductType(product_type.lower()) if product_type.lower() in ("raw", "processed") else ProductType.PROCESSED,
        name=f"Product {product_id}",
        delivery_channels=[channel_name],
    )

    delivery_id = str(_uuid.uuid4())
    payload: dict[str, Any] = {
        "delivery_id": delivery_id,
        "product_id": product_id,
        "product_type": product_type,
        "end_user_id": end_user_id,
        "domain": domain,
    }

    recipients: list[str] = [profile.email] if profile.email else []


    try:
        channel_instance = get_channel(channel_name)
        result = deliver_with_retry(
            channel=channel_instance,
            product=product,
            payload=payload,
            recipients=recipients,
            subscription_id=delivery_id,
        )
    except ValueError as exc:
        return {
            "error_code": ErrorCode.VALIDATION_ERROR.value,
            "message": str(exc),
            "actionable": True,
        }
    except Exception as exc:
        logger.exception("send_to_enduser dispatch failed")
        return _error_dict(exc)

    return {
        "delivery_id": delivery_id,
        "status": result.status,
        "channel": channel_name,
        "recipient_count": result.recipient_count,
        "error": result.error,
    }


# ---------------------------------------------------------------------------
# Alert rule handlers
# ---------------------------------------------------------------------------


def _handle_get_alert_rules(domain: str) -> dict[str, Any]:
    """List alert rules for a domain."""
    from autoinfo.alerts import list_alert_rules

    try:
        rules = list_alert_rules(domain=domain)
    except Exception as exc:
        return {
            "error_code": ErrorCode.INTERNAL_ERROR.value,
            "message": f"Failed to list alert rules: {exc}",
            "actionable": True,
        }

    from dataclasses import asdict as _asdict

    return {
        "domain": domain,
        "alert_rules": [_asdict(r) for r in rules],
        "count": len(rules),
    }


def _handle_add_alert_rule(
    domain: str,
    topic_keywords: list[str] | None = None,
    relevance_threshold: float = 0.0,
    channel: Literal["email", "webhook"] = "email",
    enabled: bool = True,
) -> dict[str, Any]:
    """Add a new alert rule for a domain."""
    from autoinfo.alerts import add_alert_rule

    try:
        rule = add_alert_rule(
            domain=domain,
            topic_keywords=topic_keywords,
            relevance_threshold=relevance_threshold,
            channel=channel,
            enabled=enabled,
        )
    except Exception as exc:
        return {
            "error_code": ErrorCode.INTERNAL_ERROR.value,
            "message": f"Failed to add alert rule: {exc}",
            "actionable": True,
        }

    from dataclasses import asdict as _asdict

    return {
        "alert_rule": _asdict(rule),
        "created": True,
    }


def _handle_remove_alert_rule(id: str) -> dict[str, Any]:
    """Remove an alert rule by ID."""
    from autoinfo.alerts import remove_alert_rule

    try:
        removed = remove_alert_rule(id)
    except Exception as exc:
        return {
            "error_code": ErrorCode.INTERNAL_ERROR.value,
            "message": f"Failed to remove alert rule: {exc}",
            "actionable": True,
        }

    if not removed:
        return {
            "error_code": "AlertRuleNotFound",
            "message": f"Alert rule '{id}' not found",
            "actionable": True,
        }

    return {
        "removed": True,
        "alert_rule_id": id,
    }


def _gate_to_dict(gate_obj: Any) -> dict[str, Any]:
    """Serialize a QualityGateConfig or DeliveryGateConfig to a plain dict."""
    from dataclasses import asdict as _asdict

    d = _asdict(gate_obj)
    d.pop("name", None)
    return d


def _handle_get_config(section: str = "") -> dict[str, Any]:
    """Return the current configuration as a structured dict.

    Supports optional *section* filter: 'project', 'llm', 'domains'.
    Returns the full config when *section* is empty.
    """
    try:
        config = _load_config()
    except Exception as exc:
        return _error_dict(exc)

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
                domains_list.append({
                    "name": d.name,
                    "active": d.active if hasattr(d, "active") else False,
                    "source_count": len(d.sources) if hasattr(d, "sources") else 0,
                    "topic_count": len(d.topics) if hasattr(d, "topics") else 0,
                })
        config_dict["domains"] = domains_list

    if section and section not in ("project", "llm", "domains"):
        return {
            "error_code": ErrorCode.INVALID_SECTION.value,
            "message": f"Unknown config section '{section}'. Valid: project, llm, domains",
            "actionable": True,
        }

    config_dict["config_path"] = str(_config_path())

    return {"config": config_dict}


def _handle_trace_item(name: str, arguments: dict) -> dict[str, Any]:
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
                kb_entries.append({
                    "entry_id": fm.get("entry_id", ""),
                    "title": fm.get("title", ""),
                    "domain": fm.get("domain", ""),
                    "tier": fm.get("tier", ""),
                    "file_path": str(md_file),
                    "collected_at": fm.get("collected_at", ""),
                    "language": fm.get("language", ""),
                    "dedup_status": fm.get("dedup_status", ""),
                })

    # -- Timeline from pipeline events -----------------------------------
    timeline: list[dict[str, Any]] = []
    for evt in pipeline_events:
        timeline.append({
            "stage": evt.get("module", "?"),
            "timestamp": evt.get("timestamp", ""),
            "status": evt.get("level", "?"),
            "message": evt.get("message", ""),
            "item_id": evt.get("item_id", ""),
        })

    return {
        "trace_id": trace_id,
        "pipeline_events": pipeline_events,
        "timeline": timeline,
        "kb_entries": kb_entries,
        "event_count": len(pipeline_events),
        "kb_entry_count": len(kb_entries),
    }


def _handle_get_metrics(name: str, arguments: dict) -> dict[str, Any]:
    domain = arguments.get("domain")
    from autoinfo.metrics import get_metrics as _get_metrics
    return _get_metrics(domain=domain)


def _handle_get_prometheus_metrics(name: str, arguments: dict) -> dict[str, Any]:
    """Return raw Prometheus exposition-format metrics in a dict wrapper."""
    from autoinfo.metrics import format_prometheus, get_metrics as _get_metrics

    data = _get_metrics()
    return {"format": "prometheus", "metrics_text": format_prometheus(data)}


def _handle_soft_delete_entry(name: str, arguments: dict) -> dict[str, Any]:
    from autoinfo.kb import KBStore
    store = KBStore()
    return store.soft_delete_entry(arguments["entry_id"])


def _handle_mark_stale(name: str, arguments: dict) -> dict[str, Any]:
    from autoinfo.kb import mark_stale
    return mark_stale(arguments["entry_id"])


def _handle_restore_entry(name: str, arguments: dict) -> dict[str, Any]:
    from autoinfo.kb import KBStore
    store = KBStore()
    return store.restore_entry(arguments["entry_id"])


def _handle_export_user_data(name: str, arguments: dict) -> dict[str, Any]:
    from autoinfo.user_store import get_profile
    profile = get_profile(arguments["user_id"])
    return {"user_id": arguments["user_id"], "profile": profile}


def _handle_delete_user_data(name: str, arguments: dict) -> dict[str, Any]:
    from autoinfo.kb import KBStore
    store = KBStore()
    purge = arguments.get("purge", False)
    if not purge:
        return {
            "error_code": ErrorCode.VALIDATION_ERROR.value,
            "message": "Must set purge=True for permanent deletion",
            "actionable": True,
            "success": False,
            "error": {
                "code": ErrorCode.VALIDATION_ERROR.value,
                "message": "Must set purge=True for permanent deletion",
                "actionable": True,
            },
        }
    return store.delete_user_data(arguments["user_id"])


def _handle_query_delivery_log(name: str, arguments: dict) -> dict[str, Any] | list[dict[str, Any]]:
    import dataclasses
    from autoinfo.delivery_log import query_delivery_log
    subscription_id = arguments.get("subscription_id")
    limit = arguments.get("limit", 50)
    status = arguments.get("status")
    from_date = arguments.get("from_date")
    to_date = arguments.get("to_date")
    results = query_delivery_log(
        subscription_id=subscription_id,
        limit=limit,
        date_from=from_date,
        date_to=to_date,
    )
    if status:
        results = [r for r in results if r.status == status]
    return [dataclasses.asdict(r) for r in results]


def _handle_list_active_deliveries() -> dict[str, Any]:
    """List all active/in-progress deliveries (status retrying/pending/in_progress)."""
    try:
        from autoinfo.delivery_log import list_active_deliveries

        items = list_active_deliveries()
        import dataclasses

        return {
            "deliveries": [dataclasses.asdict(item) for item in items],
            "count": len(items),
        }
    except Exception as exc:
        logger.exception("list_active_deliveries failed")
        return _error_dict(exc)


def _handle_get_delivery_log(
    status: str | None = None,
    domain: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """Query delivery log with optional filters (status, domain) and pagination."""
    try:
        from autoinfo.delivery_log import query_delivery_log

        items = query_delivery_log(
            limit=limit,
            offset=offset,
        )
        if status:
            items = [item for item in items if item.status == status]
        # domain filter is accepted for API compatibility; delivery_log
        # table does not currently store domain — no-op filtering.
        if domain:
            pass
        import dataclasses

        return {
            "deliveries": [dataclasses.asdict(item) for item in items],
            "count": len(items),
            "limit": limit,
            "offset": offset,
        }
    except Exception as exc:
        logger.exception("get_delivery_log failed")
        return _error_dict(exc)


def _handle_get_channel_health(
    channel_name: str | None = None,
) -> list[dict[str, Any]]:
    """Return health status for all or a specific delivery channel."""
    from autoinfo.delivery import _CHANNEL_REGISTRY

    results: list[dict[str, Any]] = []
    if channel_name is not None:
        channel_cls = _CHANNEL_REGISTRY.get(channel_name)
        if channel_cls is None:
            return [{"healthy": False, "latency_ms": 0.0, "error": f"unknown channel: {channel_name}", "channel": channel_name}]
        instance = channel_cls()
        results.append(instance.health_check())
    else:
        for name, channel_cls in _CHANNEL_REGISTRY.items():
            try:
                instance = channel_cls()
                results.append(instance.health_check())
            except Exception as exc:
                results.append({"healthy": False, "latency_ms": 0.0, "error": str(exc), "channel": name})
    return results


# ---------------------------------------------------------------------------
# Portal / end-user self-service tools
# ---------------------------------------------------------------------------


def _handle_get_enduser_history(end_user_id: str, limit: int = 20) -> dict[str, Any]:
    """Return delivery history for an end-user.

    Mirrors the ``portal history`` CLI command — looks up the end-user's
    subscriptions and queries the delivery log for their delivery attempts.

    Parameters
    ----------
    end_user_id:
        End-user ID (e.g. ``alice``).
    limit:
        Max entries to return (default 20).

    Returns
    -------
    dict
        ``{end_user_id, entries, count, subscription_count}``.
    """
    from autoinfo.delivery_log import query_delivery_log as _query_log
    from autoinfo.user_store import get_profile, list_subscriptions

    profile = get_profile(end_user_id)
    if profile is None:
        return {
            "error_code": ErrorCode.NOT_FOUND.value,
            "message": f"End-user '{end_user_id}' not found",
            "actionable": True,
        }

    subscriptions = list_subscriptions(user_id=end_user_id)
    sub_ids: list[str] = []
    for s in subscriptions:
        sid = getattr(s, "sub_id", None) or getattr(s, "subscription_id", None)
        if sid:
            sub_ids.append(sid)

    if not sub_ids:
        return {
            "end_user_id": end_user_id,
            "entries": [],
            "count": 0,
            "subscription_count": 0,
        }

    all_entries: list[dict[str, Any]] = []
    for sid in sub_ids:
        raw = _query_log(subscription_id=sid, limit=limit)
        for entry in raw:
            all_entries.append(entry.to_dict())

    all_entries.sort(key=lambda e: e.get("last_attempt", ""), reverse=True)
    page = all_entries[:limit]

    return {
        "end_user_id": end_user_id,
        "entries": page,
        "count": len(page),
        "subscription_count": len(sub_ids),
    }


def _handle_get_enduser_products(end_user_id: str) -> dict[str, Any]:
    """Return products (subscriptions) for an end-user.

    Mirrors the ``portal`` CLI's subscription lookup — retrieves all
    subscriptions linked to the given end-user and returns their product
    details (plan, status, dates, auto-renew flag).

    Parameters
    ----------
    end_user_id:
        End-user ID (e.g. ``alice``).

    Returns
    -------
    dict
        ``{end_user_id, products, count}``.
    """
    from autoinfo.user_store import get_profile, list_subscriptions

    profile = get_profile(end_user_id)
    if profile is None:
        return {
            "error_code": ErrorCode.NOT_FOUND.value,
            "message": f"End-user '{end_user_id}' not found",
            "actionable": True,
        }

    subscriptions = list_subscriptions(user_id=end_user_id)
    products: list[dict[str, Any]] = []
    for sub in subscriptions:
        products.append({
            "subscription_id": getattr(sub, "subscription_id", getattr(sub, "sub_id", "")),
            "user_id": sub.user_id,
            "plan": getattr(sub, "plan", getattr(sub, "product_id", "")),
            "status": sub.status,
            "start_date": sub.start_date,
            "end_date": sub.end_date,
            "auto_renew": sub.auto_renew,
        })

    return {
        "end_user_id": end_user_id,
        "products": products,
        "count": len(products),
    }


# ---------------------------------------------------------------------------
# Error response helper
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Cross-collection merge (F53)
# ---------------------------------------------------------------------------


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
        return result
    except Exception as exc:
        logger.exception("merge_items failed")
        return _error_dict(exc)


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
        logger.exception("find_similar_items failed")
        return _error_dict(exc)


def _handle_calculate_freshness_score(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle calculate_freshness_score — fetch entry, compute freshness."""
    entry_id = arguments["entry_id"]
    ttl_days = arguments.get("ttl_days", 90)
    from autoinfo.kb import KBStore, calculate_freshness_score

    store = KBStore()
    entry = store.get_entry(entry_id)
    if entry is None:
        return {
            "error_code": ErrorCode.NOT_FOUND.value,
            "message": f"Entry not found: {entry_id}",
            "actionable": True,
            "success": False,
            "error": {
                "code": ErrorCode.NOT_FOUND.value,
                "message": f"Entry not found: {entry_id}",
                "actionable": True,
            },
        }
    score = calculate_freshness_score(entry, ttl_days)
    return {"entry_id": entry_id, "freshness_score": score, "ttl_days": ttl_days}


# ---------------------------------------------------------------------------
# End-User Trial handlers (Task 14)
# ---------------------------------------------------------------------------


def _handle_activate_trial(
    end_user_id: str,
    days: int = 14,
) -> dict[str, Any]:
    """Activate or reset the trial period for an end-user."""
    from autoinfo.user_store import activate_trial

    try:
        return activate_trial(end_user_id=end_user_id, days=days)
    except Exception as exc:
        logger.exception("activate_trial failed for '%s'", end_user_id)
        return {
            "error_code": ErrorCode.INTERNAL_ERROR.value,
            "message": str(exc),
            "actionable": True,
        }


def _handle_check_trial_expiry(end_user_id: str) -> dict[str, Any]:
    """Check trial expiry status for an end-user."""
    from autoinfo.user_store import check_trial_expiry

    try:
        return check_trial_expiry(end_user_id=end_user_id)
    except Exception as exc:
        logger.exception("check_trial_expiry failed for '%s'", end_user_id)
        return {
            "error_code": ErrorCode.INTERNAL_ERROR.value,
            "message": str(exc),
            "actionable": True,
        }


# ---------------------------------------------------------------------------
# Stripe Billing handlers (2)
# ---------------------------------------------------------------------------


def _handle_create_checkout_session(
    product_id: str,
    end_user_id: str,
    *,
    success_url: str = "http://localhost:8741/success",
    cancel_url: str = "http://localhost:8741/cancel",
    email: str = "",
    name: str = "",
) -> dict[str, Any]:
    """Create a Stripe Checkout Session for a product."""
    from autoinfo.billing import create_checkout_session

    try:
        return create_checkout_session(
            product_id=product_id,
            end_user_id=end_user_id,
            success_url=success_url,
            cancel_url=cancel_url,
            email=email,
            name=name,
        )
    except Exception as exc:
        logger.exception("create_checkout_session failed for '%s'", end_user_id)
        return {
            "error_code": ErrorCode.INTERNAL_ERROR.value,
            "message": str(exc),
            "actionable": True,
        }


def _handle_get_subscription_status(end_user_id: str) -> dict[str, Any]:
    """Check Stripe subscription status for an end-user."""
    from autoinfo.billing import get_subscription_status

    try:
        return get_subscription_status(end_user_id=end_user_id)
    except Exception as exc:
        logger.exception("get_subscription_status failed for '%s'", end_user_id)
        return {
            "error_code": ErrorCode.INTERNAL_ERROR.value,
            "message": str(exc),
            "actionable": True,
        }


def _handle_get_billing_summary(
    user_id: str,
    period: str = "month",
) -> dict[str, Any]:
    """Return combined billing summary — usage + subscription.

    Combines CostMeter usage data with Stripe subscription status into
    a single read-only summary.

    Parameters
    ----------
    user_id:
        AutoInfo end-user ID (e.g. ``alice``).
    period:
        Time period: ``"today"``, ``"week"``, ``"month"``, ``"all"``.
        Defaults to ``"month"``.

    Returns
    -------
    dict with keys: ``user_id``, ``period``, ``usage``, ``subscription``.
    """
    from autoinfo.billing import get_subscription_status
    from autoinfo.cost import CostMeter

    try:
        meter = CostMeter()
        usage = meter.get_enduser_usage(end_user_id=user_id, period=period)
        subscription = get_subscription_status(end_user_id=user_id)
    except Exception as exc:
        logger.exception("get_billing_summary failed for '%s'", user_id)
        return {
            "error_code": ErrorCode.INTERNAL_ERROR.value,
            "message": str(exc),
            "actionable": True,
        }

    return {
        "user_id": user_id,
        "period": period,
        "usage": {
            "llm_units": usage.get("llm_units", 0),
            "storage_mb": usage.get("storage_mb", 0.0),
            "api_call_units": usage.get("api_call_units", 0),
        },
        "subscription": {
            "status": subscription.get("profile_status", "unknown"),
            "plan": subscription.get("plan", "free"),
            "stripe_status": subscription.get("stripe_status", "none"),
            "customer_id": subscription.get("customer_id", ""),
        },
    }


# ---------------------------------------------------------------------------
# Usage-based billing handlers (G16 — 2)
# ---------------------------------------------------------------------------


def _handle_get_enduser_usage(
    end_user_id: str,
    period: str = "month",
) -> dict[str, Any]:
    """Return billable usage for an end-user over a period.

    Delegates to ``CostMeter.get_enduser_usage``, which queries the cost_log
    and maps internal CostMeter units to customer-billable units:
    LLM tokens → llm_units, storage items → storage_mb, API calls → api_call_units.
    """
    from autoinfo.cost import CostMeter

    try:
        meter = CostMeter()
        return meter.get_enduser_usage(end_user_id=end_user_id, period=period)
    except Exception as exc:
        logger.exception("get_enduser_usage failed for '%s'", end_user_id)
        return {
            "error_code": ErrorCode.INTERNAL_ERROR.value,
            "message": str(exc),
            "actionable": True,
        }


def _handle_get_enduser_invoice(
    end_user_id: str,
    period: str = "month",
) -> dict[str, Any]:
    """Return an invoice-like summary with usage and estimated cost.

    Delegates to ``CostMeter.get_enduser_invoice``, which computes billable
    units via get_enduser_usage and applies configurable unit pricing.
    """
    from autoinfo.cost import CostMeter

    try:
        meter = CostMeter()
        return meter.get_enduser_invoice(end_user_id=end_user_id, period=period)
    except Exception as exc:
        logger.exception("get_enduser_invoice failed for '%s'", end_user_id)
        return {
            "error_code": ErrorCode.INTERNAL_ERROR.value,
            "message": str(exc),
            "actionable": True,
        }


# ---------------------------------------------------------------------------
# Agent Callback handlers (3)
# ---------------------------------------------------------------------------
# End-User Preferences handlers (Task 16)
# ---------------------------------------------------------------------------


def _handle_update_preferences(
    end_user_id: str,
    preferences: dict[str, Any],
) -> dict[str, Any]:
    """Merge preferences into stored preferences for an end-user."""
    from autoinfo.user_store import update_preferences

    try:
        return update_preferences(end_user_id=end_user_id, preferences=preferences)
    except Exception as exc:
        logger.exception("update_preferences failed for '%s'", end_user_id)
        return {
            "error_code": ErrorCode.INTERNAL_ERROR.value,
            "message": str(exc),
            "actionable": True,
        }


def _handle_get_preferences(end_user_id: str) -> dict[str, Any]:
    """Return stored preferences for an end-user."""
    from autoinfo.user_store import get_preferences

    try:
        return get_preferences(end_user_id=end_user_id)
    except Exception as exc:
        logger.exception("get_preferences failed for '%s'", end_user_id)
        return {
            "error_code": ErrorCode.INTERNAL_ERROR.value,
            "message": str(exc),
            "actionable": True,
        }


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
        return {
            "error_code": ErrorCode.VALIDATION_ERROR.value,
            "message": str(exc),
            "actionable": True,
        }
    except Exception as exc:
        logger.exception("set_agent_callback failed")
        return {
            "error_code": ErrorCode.INTERNAL_ERROR.value,
            "message": str(exc),
            "actionable": True,
        }


def _handle_list_agent_callbacks() -> list[dict[str, Any]]:
    """List all registered agent callbacks."""
    from autoinfo.agent_callback import list_agent_callbacks

    try:
        return list_agent_callbacks()
    except Exception as exc:
        logger.exception("list_agent_callbacks failed")
        return {
            "error_code": ErrorCode.INTERNAL_ERROR.value,
            "message": str(exc),
            "actionable": True,
        }


def _handle_remove_agent_callback(callback_id: str) -> dict[str, Any]:
    """Remove a registered agent callback."""
    from autoinfo.agent_callback import remove_agent_callback

    try:
        removed = remove_agent_callback(callback_id)
        if removed:
            return {"callback_id": callback_id, "removed": True}
        return {
            "error_code": ErrorCode.NOT_FOUND.value,
            "message": f"Callback '{callback_id}' not found",
            "actionable": True,
        }
    except Exception as exc:
        logger.exception("remove_agent_callback failed")
        return {
            "error_code": ErrorCode.INTERNAL_ERROR.value,
            "message": str(exc),
            "actionable": True,
        }


def _error_dict(exc: Exception) -> dict[str, Any]:
    """Build a dual-format error dict (flat + envelope) for backward compat.

    Returns both the legacy flat fields (``error_code``, ``message``,
    ``actionable``) and the new envelope fields (``success``, ``error``).
    Callers receive a fully populated error dict that passes through the
    standard call_tool wrapping unchanged (idempotent).
    """
    code_str = ErrorCode.INTERNAL_ERROR.value
    message_str = str(exc)
    return {
        "error_code": code_str,
        "message": message_str,
        "actionable": True,
        "success": False,
        "error": {
            "code": code_str,
            "message": message_str,
            "actionable": True,
        },
    }


def _error_response(exc: Exception) -> list[TextContent]:
    """Build a standardised error response in the envelope format.

    Returns ``list[TextContent]`` with the uniform ``{success, error}`` shape.
    """
    return [
        TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": {
                    "code": ErrorCode.INTERNAL_ERROR.value,
                    "message": str(exc),
                    "actionable": True,
                },
            }),
        )
    ]


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

app = Server("autoinfo")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """Declare the 30 available tools with their input schemas."""
    return [
        # -- System (2) ---------------------------------------------------
        Tool(
            name="health_check",
            description="Check server health status",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_tool_count",
            description="Return the number of registered MCP tools",
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
        # -- Discovery (7) ------------------------------------------------
        Tool(
            name="list_domains",
            description="List all configured domains with source/topic counts",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="list_available_platforms",
            description="List all supported source platform types with descriptions",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_domain_schema",
            description="Return the extraction schema and structure for a domain",
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
            description="List configured LLM models with provider and task info",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_effective_llm_config",
            description="Resolve the effective LLM configuration for a task",
            inputSchema={
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": (
                            "Optional task name (e.g. extraction, "
                            "summarization)"
                        ),
                        "default": None,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="activate_domain",
            description="Activate a domain (set domain.active = True)",
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
            description="Deactivate a domain (set domain.active = False)",
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
            description="Remove a domain configuration. Preserves all collected data on disk.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Domain name to remove",
                    },
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="get_domain_config",
            description="Return full domain config including sources, topics, extract_fields",
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
        # -- Source Management (5) ----------------------------------------
        Tool(
            name="add_source",
            description=(
                "Add a data source (idempotent — dedup by url + type + domain)"
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
                        "description": "Source URL",
                    },
                    "type": {
                        "type": "string",
                        "description": "Source type (api, rss, web)",
                        "default": "api",
                        "enum": ["api", "rss", "web"],
                    },
                    "domain": {
                        "type": "string",
                        "description": "Domain to add this source to",
                    },
                },
                "required": ["name", "url", "domain"],
            },
        ),
        Tool(
            name="add_sources",
            description="Batch-add sources with per-source error isolation",
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
                                    "description": "Source URL",
                                },
                                "type": {
                                    "type": "string",
                                    "default": "api",
                                    "description": "Source type (api, rss, web)",
                                    "enum": ["api", "rss", "web"],
                                },
                                "domain": {
                                    "type": "string",
                                    "description": "Domain to add this source to",
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
            description="Remove a source by its source_id (format: 'domain:name')",
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
                },
                "required": ["source_id"],
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
                        "description": "Source type (api, rss, web)",
                        "default": "api",
                        "enum": ["api", "rss", "web"],
                    },
                },
                "required": ["url"],
            },
        ),
        Tool(
            name="list_sources",
            description="List all sources for a given domain",
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
        # -- Topic Management (4) -----------------------------------------
        Tool(
            name="add_topic",
            description="Add a topic to a domain (idempotent by name+domain)",
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
            description="Remove a topic from a domain",
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
                },
                "required": ["domain", "topic_id"],
            },
        ),
        Tool(
            name="list_topics",
            description="List all topics for a given domain",
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
        # -- Keywords Management (3) ---------------------------------------
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
            description="Reject a keyword — move to deprecated state",
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
        # -- Collection / Processing (5) ----------------------------------
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
            name="get_collection_progress",
            description="Return current collection progress for a domain (in-memory state)",
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
            description="Return full collection results for a domain (last run)",
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
            name="get_processing_progress",
            description="Get processing progress for a domain or job_id",
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
        # -- Knowledge Base (4) -------------------------------------------
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
                    "user_id": {
                        "type": "string",
                        "description": "Optional user_id filter (accepted for multi-user compatibility; direct ID lookup is user-independent)",
                    },
                },
                "required": ["entry_id"],
            },
        ),
        Tool(
            name="search_knowledge_base",
            description=(
                "Search the knowledge base using FTS5 full-text, vector, "
                "or hybrid (FTS5 + vector) search. "
                "Supports simple term queries with optional domain and "
                "faceted filters (tags, date range, quality tier, "
                "content type, language)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                    },
                    "domain": {
                        "type": "string",
                        "description": "Optional domain filter",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results",
                        "default": 20,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Pagination offset",
                        "default": 0,
                    },
                    "mode": {
                        "type": "string",
                        "description": "Search mode: 'fts5' (default, full-text only), 'hybrid' (FTS5 + vector fusion), or 'vector' (vector-only). Falls back to FTS5 when vector search is unavailable.",
                        "default": "fts5",
                        "enum": ["fts5", "hybrid", "vector"],
                    },
                    "filter_tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Only include entries whose tags contain ANY of the given values",
                    },
                    "filter_date_from": {
                        "type": "string",
                        "description": "Only entries with collected_at >= this ISO date (e.g. 2025-01-01)",
                    },
                    "filter_date_to": {
                        "type": "string",
                        "description": "Only entries with collected_at <= this ISO date (e.g. 2025-06-30)",
                    },
                    "filter_quality_tier_min": {
                        "type": "integer",
                        "description": "Only entries with quality_tier >= this value",
                    },
                    "filter_quality_tier_max": {
                        "type": "integer",
                        "description": "Only entries with quality_tier <= this value",
                    },
                    "filter_content_type": {
                        "type": "string",
                        "description": "Only entries with this exact content_type",
                    },
                    "filter_language": {
                        "type": "string",
                        "description": "Only entries with this exact language",
                    },
                    "user_id": {
                        "type": "string",
                        "description": "Optional user_id filter — only entries belonging to this user",
                    },
                    "include_stale": {
                        "type": "boolean",
                        "description": "If false (default), stale entries are demoted to the bottom of search results. If true, stale entries are mixed normally with fresh results.",
                        "default": False,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="query_knowledge_graph",
            description=(
                "Query the knowledge graph for entities related to a given "
                "entity.  Returns related entities with relation type and "
                "co-occurrence strength."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {
                        "type": "string",
                        "description": "Entity name to query (case-insensitive partial match)",
                    },
                    "relation": {
                        "type": "string",
                        "description": "Relation type filter (default: 'related_to'). Use empty string for all.",
                        "default": "related_to",
                    },
                    "domain": {
                        "type": "string",
                        "description": "Optional domain scope filter",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results",
                        "default": 20,
                    },
                },
                "required": ["entity"],
            },
        ),
        Tool(
            name="flag_for_knowledge_base",
            description=(
                "Flag a summary entry for KB inclusion — tags it in the "
                "SQLite index with importance rating.  Does NOT create a "
                "Draft; call create_kb_draft separately."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "summary_id": {
                        "type": "string",
                        "description": "Summary entry ID",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tags to apply (merged with existing, no duplicates)",
                    },
                    "importance": {
                        "type": "integer",
                        "description": "Importance rating 1-5",
                        "default": 3,
                    },
                },
                "required": ["summary_id"],
            },
        ),
        # -- KB: get_summary -----------------------------------------
        Tool(
            name="get_summary",
            description=(
                "Return full detail for a summary entry including key "
                "points parsed from the body, quality scores, tags, "
                "importance, and source provenance."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "summary_id": {
                        "type": "string",
                        "description": "Summary entry ID",
                    },
                },
                "required": ["summary_id"],
            },
        ),
        # -- KB: Relations (2) --------------------------------------------
        Tool(
            name="link_items",
            description=(
                "Create a link between two KB entries. Idempotent — "
                "calling with the same (item_a, item_b, relation_type) "
                "returns the existing relation."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "item_a_id": {
                        "type": "string",
                        "description": "First entry ID",
                    },
                    "item_b_id": {
                        "type": "string",
                        "description": "Second entry ID",
                    },
                    "relation_type": {
                        "type": "string",
                        "description": "Relation type (e.g. related, references)",
                        "default": "related",
                    },
                    "metadata": {
                        "type": "object",
                        "description": "Optional metadata dict (e.g. matched_tags)",
                    },
                },
                "required": ["item_a_id", "item_b_id"],
            },
        ),
        Tool(
            name="get_item_relations",
            description=(
                "Return all relations where an item participates. "
                "Optionally filtered by relation_type."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "item_id": {
                        "type": "string",
                        "description": "Entry ID to query",
                    },
                    "relation_type": {
                        "type": "string",
                        "description": "Optional relation type filter",
                    },
                },
                "required": ["item_id"],
            },
        ),
        # -- KB: Versioning (2) -------------------------------------------
        Tool(
            name="get_entry_history",
            description=(
                "Return all saved backup versions for an entry, "
                "newest first. Up to 5 versions are retained."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "entry_id": {
                        "type": "string",
                        "description": "Entry ID to query",
                    },
                },
                "required": ["entry_id"],
            },
        ),
        Tool(
            name="restore_entry_version",
            description=(
                "Restore an entry from a saved version backup. "
                "Copies the .bak file back over the original."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "version_id": {
                        "type": "string",
                        "description": "Version ID to restore",
                    },
                },
                "required": ["version_id"],
            },
        ),
        Tool(
            name="compare_versions",
            description=(
                "Compare two versions of a KB entry and return a "
                "structured diff showing which fields changed, their "
                "old and new values, and a summary of changes."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "entry_id": {
                        "type": "string",
                        "description": "KB entry ID whose versions to compare",
                    },
                    "version_a": {
                        "type": "string",
                        "description": (
                            "First version identifier (version_id like "
                            "'entry_abc--v1' or version number string like '1')"
                        ),
                    },
                    "version_b": {
                        "type": "string",
                        "description": (
                            "Second version identifier (version_id like "
                            "'entry_abc--v2' or version number string like '2')"
                        ),
                    },
                },
                "required": ["entry_id", "version_a", "version_b"],
            },
        ),
        # -- KB: Monitor (2) ----------------------------------------------
        Tool(
            name="get_collection_stats",
            description=(
                "Aggregated collection statistics across all domains "
                "for daily, weekly, or monthly periods."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "description": "Period: daily (default), weekly, monthly",
                        "default": "daily",
                        "enum": ["daily", "weekly", "monthly"],
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="get_collection_diff",
            description=(
                "Return entries collected since a previous collection ID, "
                "showing new entries grouped by domain."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "since_collection_id": {
                        "type": "string",
                        "description": "Collection ID (timestamp) to compare against",
                    },
                },
                "required": ["since_collection_id"],
            },
        ),
        Tool(
            name="get_domain_decay",
            description=(
                "Compute decay / staleness metrics for a domain. "
                "Returns staleness ratio, average TTL remaining, "
                "decay grade (GREEN/YELLOW/RED), and re-collection suggestions."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name to compute decay metrics for",
                    },
                    "ttl_days": {
                        "type": "integer",
                        "description": (
                            "Days before an entry is considered fully stale "
                            "(default: 90)"
                        ),
                        "default": 90,
                    },
                },
                "required": ["domain"],
            },
        ),
        # -- KB: Draft tools (3) ------------------------------------------
        Tool(
            name="create_kb_draft",
            description=(
                "Create a Draft entry from one or more Raw entries. "
                "Validates all raw_ids exist in 01-Raw, merges content, "
                "and creates a file in 02-Draft/."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "raw_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "One or more 01-Raw entry IDs to compile into a Draft",
                    },
                    "title": {
                        "type": "string",
                        "description": "Title for the new Draft entry",
                    },
                    "summary": {
                        "type": "string",
                        "description": "Optional summary text",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional tags for the Draft entry",
                    },
                },
                "required": ["raw_ids", "title"],
            },
        ),
        Tool(
            name="reject_kb_draft",
            description=(
                "Reject a Draft entry, moving it back to 01-Raw or "
                "archiving it.  Adds rejection_reason to frontmatter."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "draft_id": {
                        "type": "string",
                        "description": "Entry ID of the Draft to reject",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Optional rejection reason",
                    },
                    "action": {
                        "type": "string",
                        "description": (
                            "'back_to_raw' (default) moves to 01-Raw; "
                            "'archive' moves to _archive/"
                        ),
                        "default": "back_to_raw",
                        "enum": ["back_to_raw", "archive"],
                    },
                },
                "required": ["draft_id"],
            },
        ),
        Tool(
            name="list_kb_tier",
            description=(
                "List all entries in a specific KB tier (01-Raw, 02-Draft) "
                "for a domain."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                    "tier": {
                        "type": "string",
                        "description": "Tier to list (01-Raw, 02-Draft)",
                        "enum": ["01-Raw", "02-Draft"],
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max entries to return",
                        "default": 50,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Pagination offset",
                        "default": 0,
                    },
                    "user_id": {
                        "type": "string",
                        "description": "Optional user_id filter — only entries belonging to this user",
                    },
                },
                "required": ["domain", "tier"],
            },
        ),
        Tool(
            name="reindex_kb",
            description="Rebuild SQLite FTS5 search index from disk frontmatter",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain to reindex (empty = all domains)",
                    },
                },
                "required": ["domain"],
            },
        ),
        # -- Output (5) ---------------------------------------------------
        Tool(
            name="list_output_templates",
            description="List available output templates for a domain. Each template includes access_level (free/premium/enterprise) for freemium gating (G15).",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (optional)",
                        "default": "",
                    },
                    "user_id": {
                        "type": "string",
                        "description": (
                            "Optional end-user ID for tier-based filtering. "
                            "When set, only templates accessible to this user "
                            "are returned. When omitted, all templates are returned."
                        ),
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="generate_digest",
            description=(
                "Generate a digest of KB entries for a domain over a given "
                "period (daily, weekly, monthly).  Returns markdown by "
                "default; also supports html, json, agent (JSON-LD), and audio (base64-encoded MP3).  "
                "Accepts optional custom_instructions to tailor output."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                    "period": {
                        "type": "string",
                        "description": "Digest period: daily, weekly, monthly",
                        "default": "weekly",
                        "enum": ["daily", "weekly", "monthly"],
                    },
                    "format": {
                        "type": "string",
                        "description": "Output format: markdown, html, json, agent, audio",
                        "default": "markdown",
                        "enum": ["markdown", "html", "json", "agent", "audio"],
                    },
                    "custom_instructions": {
                        "type": "string",
                        "description": "Optional custom instructions to tailor the output content",
                        "default": "",
                    },
                    "target_audience": {
                        "type": "string",
                        "description": "Optional target audience description to tailor output tone and depth (e.g. \"healthcare professionals\", \"general public\")",
                        "default": "",
                    },
                    "include_stale": {
                        "type": "boolean",
                        "description": "Include stale entries in the digest (default: false). When false, entries below the domain freshness threshold are excluded.",
                        "default": False,
                    },
                    "recipients": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of email recipient addresses for direct digest delivery",
                    },
                    "user_id": {
                        "type": "string",
                        "description": "Optional user ID for preference-based personalization. When provided, stored preferences (target_audience, format, max_items) are auto-loaded from the user's profile.",
                        "default": "",
                    },
                    "max_items": {
                        "type": "integer",
                        "description": "Optional maximum number of KB entries to include (default: 0 = use built-in limit of 200). Can be auto-set from stored user preferences when user_id is provided.",
                        "default": 0,
                    },
                },
                "required": ["domain"],
            },
        ),
        Tool(
            name="generate_report",
            description=(
                "Generate a structured report for a domain over a given "
                "period (day, week, month).  Returns markdown by default; "
                "also supports json, html, agent (JSON-LD), and audio.  "
                "Accepts optional custom_instructions to tailor output."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                    "format": {
                        "type": "string",
                        "description": "Output format: markdown, json, html, agent, audio",
                        "default": "markdown",
                        "enum": ["markdown", "json", "html", "agent", "audio"],
                    },
                    "period": {
                        "type": "string",
                        "description": "Report period: day, week, month",
                        "default": "month",
                        "enum": ["day", "week", "month"],
                    },
                    "custom_instructions": {
                        "type": "string",
                        "description": "Optional custom instructions to tailor the output content",
                        "default": "",
                    },
                    "target_audience": {
                        "type": "string",
                        "description": "Optional target audience description to tailor output tone and depth (e.g. \"healthcare professionals\", \"general public\")",
                        "default": "",
                    },
                    "user_id": {
                        "type": "string",
                        "description": "Optional end-user ID for freemium access gating (G15). Premium reports are blocked for non-subscribers.",
                        "default": "",
                    },
                },
                "required": ["domain"],
            },
        ),
        Tool(
            name="generate_tutorial",
            description=(
                "Generate a structured tutorial for a domain. "
                "Accepts optional custom_instructions to tailor output."
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
                        "description": "Optional topic filter",
                    },
                    "format": {
                        "type": "string",
                        "description": "Output format (markdown)",
                        "default": "markdown",
                        "enum": ["markdown"],
                    },
                    "custom_instructions": {
                        "type": "string",
                        "description": "Optional custom instructions to tailor the output content",
                        "default": "",
                    },
                },
                "required": ["domain"],
            },
        ),
        Tool(
            name="generate_presentation",
            description=(
                "Generate a slide-based presentation for a topic within a domain. "
                "Accepts optional custom_instructions to tailor output."
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
                        "description": "Presentation topic",
                    },
                    "slides": {
                        "type": "integer",
                        "description": "Desired number of slides (3-30)",
                        "default": 10,
                    },
                    "format": {
                        "type": "string",
                        "description": (
                            "Output format: 'markdown' (default, Reveal.js-flavoured "
                            "Markdown), 'html' (standalone Reveal.js HTML5 via CDN), "
                            "or 'mkslides' (mkslides build with HTML fallback)."
                        ),
                        "default": "markdown",
                        "enum": ["markdown", "html", "mkslides"],
                    },
                    "custom_instructions": {
                        "type": "string",
                        "description": "Optional custom instructions to tailor the output content",
                        "default": "",
                    },
                },
                "required": ["domain", "topic"],
            },
        ),
        Tool(
            name="localize_content",
            description=(
                "Translate a KB entry or raw text into a target language. "
                "Two modes: (1) pass content_id to translate a stored KB "
                "entry (stores the translation as a new file), or (2) pass "
                "content + source_lang for direct translation without storage. "
                "Preserves medical terminology, drug names, procedures, "
                "statistics, and citations. Optionally accepts a domain "
                "name to inject terminology guardrails."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "content_id": {
                        "type": "string",
                        "description": (
                            "KB entry ID to translate.  The entry must "
                            "exist in the KB store."
                        ),
                    },
                    "content": {
                        "type": "string",
                        "description": (
                            "Raw text to translate directly (no KB lookup). "
                            "Requires source_lang."
                        ),
                    },
                    "source_lang": {
                        "type": "string",
                        "description": (
                            "Source language code (e.g. en, zh).  Required "
                            "for direct content mode; auto-detected from "
                            "the KB entry for content_id mode."
                        ),
                    },
                    "target_lang": {
                        "type": "string",
                        "description": (
                            "Target language code (e.g. zh, fr, ja)."
                        ),
                    },
                    "domain": {
                        "type": "string",
                        "description": (
                            "Domain name (e.g. medical-research). When "
                            "provided, loads domain-specific terminology "
                            "guardrails from knowledge/<domain>/_terminology.yaml. "
                            "In content_id mode, inferred from KB entry "
                            "if not specified."
                        ),
                    },
                },
                "required": ["target_lang"],
            },
        ),
        # -- Export / Import (2) -----------------------------------------------
        Tool(
            name="export_kb",
            description=(
                "Export knowledge base entries to specified format. "
                "Supports markdown, json, sqlite, csv, pdf, graphml, rss formats."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                    "format": {
                        "type": "string",
                        "description": "Output format: markdown, json, sqlite, csv, pdf, graphml, rss",
                        "default": "markdown",
                        "enum": ["markdown", "json", "sqlite", "csv", "pdf", "graphml", "rss"],
                    },
                    "scope": {
                        "type": "string",
                        "description": "Export scope: domain (all entries), entry (specific IDs), collection (collection-scoped)",
                        "default": "domain",
                        "enum": ["entry", "collection", "domain"],
                    },
                    "entry_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific entry IDs to export (used when scope is 'entry')",
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Optional explicit output path. Auto-generated when omitted.",
                    },
                },
                "required": ["domain", "format"],
            },
        ),
        Tool(
            name="import_kb",
            description=(
                "Import entries or source suggestions into the KB. "
                "Supports 4 formats: markdown (YAML+Markdown frontmatter), "
                "json, csv, and opml. "
                "All entry imports land in 01-Raw (KB pipeline). "
                "OPML returns source suggestions only — does NOT auto-add sources."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Target domain name (e.g. medical-research)",
                    },
                    "format": {
                        "type": "string",
                        "description": "Import format: markdown (YAML+Markdown), json, csv, opml",
                        "enum": ["markdown", "json", "csv", "opml"],
                    },
                    "data": {
                        "type": "string",
                        "description": (
                            "Raw content string to import. "
                            "For markdown: YAML frontmatter (--- delimited) + Markdown body. "
                            "For json: JSON array or single object with title, source_url, content. "
                            "For csv: CSV with header row (title, source_url, content required). "
                            "For opml: OPML XML with <outline> elements."
                        ),
                    },
                },
                "required": ["domain", "format", "data"],
            },
        ),
        # -- Email (1) --------------------------------------------------------
        Tool(
            name="send_email_digest",
            description=(
                "Generate and send a digest via SMTP email. "
                "Only sends when email is enabled in config "
                "(email.enabled: true). Requires email.smtp_host, "
                "email.from_addr, and email.to_addrs to be configured."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain to generate digest for (e.g. medical-research)",
                    },
                    "period": {
                        "type": "string",
                        "description": "Digest period: daily, weekly, monthly",
                        "default": "weekly",
                        "enum": ["daily", "weekly", "monthly"],
                    },
                },
                "required": ["domain"],
            },
        ),
        # -- Custom Extraction (2) -----------------------------------------
        Tool(
            name="extract_fields",
            description=(
                "On-demand re-extraction with a custom schema. "
                "Retrieves the KB entry, runs LLM extraction with the "
                "given field names, and returns the result "
                "(does NOT persist)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "content_id": {
                        "type": "string",
                        "description": "KB entry ID to re-extract",
                    },
                    "schema": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Custom field names to extract "
                            "(e.g. methodology, findings)"
                        ),
                    },
                },
                "required": ["content_id", "schema"],
            },
        ),
        Tool(
            name="get_extraction",
            description=(
                "Return the extracted fields stored for a KB entry. "
                "Reads the Markdown frontmatter to retrieve "
                "``extracted_fields``."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "content_id": {
                        "type": "string",
                        "description": "KB entry ID",
                    },
                },
                "required": ["content_id"],
            },
        ),
        # -- Schedule Management (4) ----------------------------------------
        Tool(
            name="list_schedules",
            description="List all configured collection schedules",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="add_schedule",
            description="Add a new collection or digest schedule with a cron expression",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Unique schedule name",
                    },
                    "expression": {
                        "type": "string",
                        "description": (
                            "Cron expression (e.g. '0 2 * * *' for daily at 2 AM)"
                        ),
                    },
                    "domain": {
                        "type": "string",
                        "description": "Domain to collect or generate digest for",
                    },
                    "schedule_type": {
                        "type": "string",
                        "description": "Schedule type: collection or digest",
                        "default": "collection",
                    },
                    "recipients": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Email recipients (required for digest type)",
                    },
                    "output_format": {
                        "type": "string",
                        "description": "Digest format: html or markdown",
                        "default": "html",
                    },
                },
                "required": ["name", "expression", "domain"],
            },
        ),
        Tool(
            name="remove_schedule",
            description="Remove a collection schedule by name",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Schedule name to remove",
                    },
                    "confirm": {
                        "type": "boolean",
                        "description": "Must be True to confirm this destructive operation",
                        "default": False,
                    },
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="run_schedules",
            description="Run due schedules now (checks cron expressions against last_run)",
            inputSchema={
                "type": "object",
                "properties": {
                    "dry_run": {
                        "type": "boolean",
                        "description": (
                            "If true, report which schedules would run "
                            "without executing"
                        ),
                        "default": False,
                    },
                    "name": {
                        "type": "string",
                        "description": (
                            "Optional single schedule name to run "
                            "(runs all due if omitted)"
                        ),
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="get_schedule_status",
            description="Get status of all schedules or a specific one (last_run, next_run, is_active, domain)",
            inputSchema={
                "type": "object",
                "properties": {
                    "schedule_id": {
                        "type": "string",
                        "description": (
                            "Optional schedule name to get status for. "
                            "When omitted, returns status for all schedules."
                        ),
                    },
                },
                "required": [],
            },
        ),
        # -- Q&A (1) -------------------------------------------------------
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
                            "Optional explicit list of entry IDs to use "
                            "instead of FTS5 search"
                        ),
                    },
                },
                "required": ["query", "domain"],
            },
        ),
        # -- Source Health / Feedback (2) ----------------------------------
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
        # -- CEFR Classification (1) ----------------------------------------
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
        # -- Project / Batch / Config (6) ------------------------------------
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
                        "description": "Optional asset type filter (collections, knowledge, database, exports, config)",
                        "default": "",
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
                },
                "required": ["domain"],
            },
        ),
        Tool(
            name="list_active_collections",
            description=(
                "List currently active or in-progress collection runs. "
                "Optionally filter by domain."
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
        # -- Webhooks (2) ----------------------------------------------------
        Tool(
            name="set_domain_webhooks",
            description=(
                "Set webhook URLs for a domain. All newly collected items "
                "will be POSTed to these URLs as JSON. Replaces any existing "
                "URLs. Fire-and-forget with retry (3 attempts)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                    "webhook_urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "List of webhook URLs (must start with "
                            "http:// or https://)"
                        ),
                    },
                },
                "required": ["domain", "webhook_urls"],
            },
        ),
        Tool(
            name="get_domain_webhooks",
            description="Return the configured webhook URLs for a domain",
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
        # -- Gate Config (2) ------------------------------------------------
        Tool(
            name="get_gate_config",
            description="Return gate configuration (quality or delivery) for a domain — checks domain-level config, falls back to global defaults",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                    "gate": {
                        "type": "string",
                        "description": "Gate name (e.g. G0, G1, D1, D2)",
                    },
                },
                "required": ["domain", "gate"],
            },
        ),
        Tool(
            name="set_gate_config",
            description="Update gate configuration for a domain. Provide gate-specific fields (action, threshold, retries for quality gates; enabled, action_on_failure for delivery gates)",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                    "gate": {
                        "type": "string",
                        "description": "Gate name (e.g. G0, G1, D1, D2)",
                    },
                    "config": {
                        "type": "object",
                        "description": "Gate configuration dict (e.g. {\"action\": \"block\", \"retries\": 3, \"retry_models\": [...]} for quality gates; {\"enabled\": true, \"action_on_failure\": \"flag\"} for delivery gates)",
                        "properties": {
                            "action": {
                                "type": "string",
                                "description": "Action on failure: block, retry, flag, skip, archive",
                            },
                            "retries": {
                                "type": "integer",
                                "description": "Number of retry attempts (quality gates)",
                            },
                            "retry_models": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Fallback model chain (quality gates)",
                            },
                            "threshold": {
                                "type": "number",
                                "description": "Score threshold 0-100 (quality gates)",
                            },
                            "enabled": {
                                "type": "boolean",
                                "description": "Whether the gate is enabled (delivery gates)",
                            },
                            "action_on_failure": {
                                "type": "string",
                                "description": "Action on failure: block, fallback, flag (delivery gates)",
                            },
                        },
                    },
                },
                "required": ["domain", "gate", "config"],
            },
        ),
        # -- Product (2) ----------------------------------------------------
        Tool(
            name="get_product",
            description="Return product configuration for a domain and product type (RAW or PROCESSED). Products are derived from domain config",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                    "product_type": {
                        "type": "string",
                        "description": "Product type: RAW or PROCESSED",
                        "enum": ["RAW", "PROCESSED"],
                    },
                },
                "required": ["domain", "product_type"],
            },
        ),
        Tool(
            name="list_products",
            description="List all configured products (RAW and PROCESSED) for a domain, derived from its configuration",
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
        # -- End User Delivery (1) -------------------------------------------
        Tool(
            name="send_to_enduser",
            description="Dispatch a product to an end user through a delivery channel. Looks up the user profile, resolves the channel, and dispatches via the DeliveryChannel framework",
            inputSchema={
                "type": "object",
                "properties": {
                    "end_user_id": {
                        "type": "string",
                        "description": "User ID of the recipient (must exist in the user store)",
                    },
                    "product_type": {
                        "type": "string",
                        "description": "Product type: raw or processed",
                        "enum": ["raw", "processed"],
                    },
                    "product_id": {
                        "type": "string",
                        "description": "Product identifier (e.g. medical-research-processed)",
                    },
                    "channel": {
                        "type": "string",
                        "description": "Delivery channel name (e.g. smtp, webhook, discord). Falls back to user's preferences, then smtp",
                    },
                },
                "required": ["end_user_id", "product_type", "product_id"],
            },
        ),
        # -- Alert Rules (3) ------------------------------------------------
        Tool(
            name="get_alert_rules",
            description="List alert rules for a domain. Returns all rules filtered by domain",
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
            name="add_alert_rule",
            description="Create a new threshold-based alert rule for a domain. Triggers notifications when collected items match the configured keywords and relevance threshold",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                    "topic_keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Keywords to match against item title and content. Empty list matches all items",
                        "default": [],
                    },
                    "relevance_threshold": {
                        "type": "number",
                        "description": "Minimum relevance score (0-100) to trigger",
                        "default": 0.0,
                    },
                    "channel": {
                        "type": "string",
                        "description": "Delivery channel: email or webhook",
                        "default": "email",
                        "enum": ["email", "webhook"],
                    },
                    "enabled": {
                        "type": "boolean",
                        "description": "Whether the rule is active",
                        "default": True,
                    },
                },
                "required": ["domain"],
            },
        ),
        Tool(
            name="remove_alert_rule",
            description="Remove an alert rule by its ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "Alert rule ID to remove (returned by add_alert_rule in the response)",
                    },
                },
                "required": ["id"],
            },
        ),
        # -- Budget Thresholds (2) -------------------------------------------
        Tool(
            name="get_budget_thresholds",
            description=(
                "Return current budget thresholds with spend status. "
                "Compares total spend from CostMeter against each threshold "
                "and reports breach status (ok/warning/critical)."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="set_budget_thresholds",
            description=(
                "Update budget thresholds in the project config. "
                "Thresholds are percentage values (0-100+) at which budget "
                "alerts fire. Persisted to .autoinfo/config.yaml."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "thresholds": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Percentage thresholds (e.g. [30.0, 60.0, 90.0, 100.0])",
                    },
                    "auto_remediation_enabled": {
                        "type": "boolean",
                        "description": "Whether auto-remediation is active (V2 — not yet implemented)",
                        "default": False,
                    },
                    "alert_webhook": {
                        "type": "string",
                        "description": "Optional webhook URL for budget alert notifications",
                        "default": "",
                    },
                },
                "required": ["thresholds"],
            },
        ),
        # -- Init (1) --------------------------------------------------------
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
                        "enum": ["medical-research", "ai-commercial", "language-learning"],
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
                        "description": "Override default LLM provider (e.g. \"openai\")",
                        "default": "",
                    },
                    "llm_model": {
                        "type": "string",
                        "description": "Override default LLM model (e.g. \"gpt-4\")",
                        "default": "",
                    },
                    "llm_base_url": {
                        "type": "string",
                        "description": "Override default LLM base URL (e.g. \"http://localhost:11434/v1\")",
                        "default": "",
                    },
                },
                "required": ["domain"],
            },
        ),
        # -- Metrics (2) --------------------------------------------------
        Tool(
            name="get_metrics",
            description="Get Prometheus-format metrics for monitoring",
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
        # -- Soft-delete & GDPR (4) -------------------------------------------
        Tool(
            name="soft_delete_entry",
            description="Mark an entry as deleted without permanent removal",
            inputSchema={
                "type": "object",
                "properties": {
                    "entry_id": {"type": "string"},
                },
                "required": ["entry_id"],
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
            description="Restore a soft-deleted entry",
            inputSchema={
                "type": "object",
                "properties": {
                    "entry_id": {"type": "string"},
                },
                "required": ["entry_id"],
            },
        ),
        Tool(
            name="export_user_data",
            description="Export all data for a user (GDPR compliance)",
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
            description="Delete all user data (GDPR right to be forgotten)",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "purge": {"type": "boolean"},
                },
                "required": ["user_id"],
            },
        ),
        # -- Trace (1) -------------------------------------------------------
        Tool(
            name="trace_item",
            description="Trace the full pipeline history for a trace_id",
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
            description="Merge multiple KB entries into one (cross-collection dedup)",
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
                    },
                },
                "required": ["item_ids"],
            },
        ),
        # -- Find Similar (1) -------------------------------------------------
        Tool(
            name="find_similar_items",
            description="Find items similar to a query using text similarity",
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
        # -- KB Freshness (1) --------------------------------------------------
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
                        "description": "Time-to-live in days (default: 90)",
                        "default": 90,
                    },
                },
                "required": ["entry_id"],
            },
        ),
        # -- Portal / End-user Self-service (2) ------------------------------
        Tool(
            name="get_enduser_history",
            description="Return delivery history for an end-user. Mirrors the portal CLI history command — looks up subscriptions and queries the delivery log for delivery attempts.",
            inputSchema={
                "type": "object",
                "properties": {
                    "end_user_id": {
                        "type": "string",
                        "description": "End-user ID (e.g. alice)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max entries to return (default: 20)",
                        "default": 20,
                    },
                },
                "required": ["end_user_id"],
            },
        ),
        Tool(
            name="get_enduser_products",
            description="Return products (subscriptions) for an end-user. Mirrors the portal CLI subscription lookup — returns plan, status, dates, and auto-renew flag.",
            inputSchema={
                "type": "object",
                "properties": {
                    "end_user_id": {
                        "type": "string",
                        "description": "End-user ID (e.g. alice)",
                    },
                },
                "required": ["end_user_id"],
            },
        ),
        # -- Delivery Log (1) ------------------------------------------------
        Tool(
            name="query_delivery_log",
            description="Query the delivery log with optional filters (subscription_id, status, date range)",
            inputSchema={
                "type": "object",
                "properties": {
                    "subscription_id": {
                        "type": "string",
                        "description": "Filter by subscription ID",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of entries to return (default: 50)",
                        "default": 50,
                    },
                    "status": {
                        "type": "string",
                        "description": "Filter by delivery status (e.g. success, failed, retrying)",
                    },
                    "from_date": {
                        "type": "string",
                        "description": "Filter by last_attempt >= this ISO-8601 timestamp",
                    },
                    "to_date": {
                        "type": "string",
                        "description": "Filter by last_attempt <= this ISO-8601 timestamp",
                    },
                },
                "required": [],
            },
        ),
        # -- Delivery Monitor (2) -------------------------------------------
        Tool(
            name="list_active_deliveries",
            description="List all active/in-progress deliveries (status: retrying, pending, in_progress)",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_delivery_log",
            description="Query delivery history with optional filters (status, domain) and pagination",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Filter by delivery status (e.g. success, failed, retrying, pending)",
                    },
                    "domain": {
                        "type": "string",
                        "description": "Filter by domain name (delivery_log does not store domain yet — accepted for API compatibility)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max entries to return (default: 20)",
                        "default": 20,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Pagination offset (default: 0)",
                        "default": 0,
                    },
                },
                "required": [],
            },
        ),
        # -- End-User Trial (2) ------------------------------------------------
        Tool(
            name="activate_trial",
            description="Activate or reset trial period for an end-user. Sets trial_started_at to now with configurable duration (default 14 days). Also sets user status to trial if not active.",
            inputSchema={
                "type": "object",
                "properties": {
                    "end_user_id": {
                        "type": "string",
                        "description": "End-user ID (e.g. alice)",
                    },
                    "days": {
                        "type": "integer",
                        "description": "Trial duration in days (default: 14)",
                        "default": 14,
                    },
                },
                "required": ["end_user_id"],
            },
        ),
        Tool(
            name="check_trial_expiry",
            description="Check trial status for an end-user. Returns days_remaining (int), status (expired/active/no_trial), trial_started_at, and trial_days.",
            inputSchema={
                "type": "object",
                "properties": {
                    "end_user_id": {
                        "type": "string",
                        "description": "End-user ID (e.g. alice)",
                    },
                },
                "required": ["end_user_id"],
            },
        ),
        # -- End-User Preferences (2) ------------------------------------------
        Tool(
            name="update_preferences",
            description="Merge preferences into stored preferences for an end-user. Accepts a dict of keys to update (format, delivery_channel, timezone, max_items). Deep-merges with existing preferences.",
            inputSchema={
                "type": "object",
                "properties": {
                    "end_user_id": {
                        "type": "string",
                        "description": "End-user ID (e.g. alice)",
                    },
                    "preferences": {
                        "type": "object",
                        "description": "Dict of preference keys to set (e.g. {format: markdown, delivery_channel: email, timezone: UTC, max_items: 50})",
                    },
                },
                "required": ["end_user_id", "preferences"],
            },
        ),
        Tool(
            name="get_preferences",
            description="Return stored preferences for an end-user. Returns dict with user_id and preferences object.",
            inputSchema={
                "type": "object",
                "properties": {
                    "end_user_id": {
                        "type": "string",
                        "description": "End-user ID (e.g. alice)",
                    },
                },
                "required": ["end_user_id"],
            },
        ),
        # -- Stripe Billing (2) ------------------------------------------------
        Tool(
            name="create_checkout_session",
            description="Create a Stripe Checkout Session for a product. Creates (or looks up) a Stripe Customer for the end-user and generates a checkout URL. Works with stripe-mock (localhost:12111) or live/test Stripe keys via STRIPE_API_KEY env var.",
            inputSchema={
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "string",
                        "description": "Stripe Price ID (e.g. price_xxx)",
                    },
                    "end_user_id": {
                        "type": "string",
                        "description": "AutoInfo end-user ID (e.g. alice)",
                    },
                    "success_url": {
                        "type": "string",
                        "description": "Redirect URL after successful payment (default: http://localhost:8741/success)",
                        "default": "http://localhost:8741/success",
                    },
                    "cancel_url": {
                        "type": "string",
                        "description": "Redirect URL on cancellation (default: http://localhost:8741/cancel)",
                        "default": "http://localhost:8741/cancel",
                    },
                    "email": {
                        "type": "string",
                        "description": "Customer email (optional)",
                        "default": "",
                    },
                    "name": {
                        "type": "string",
                        "description": "Customer display name (optional)",
                        "default": "",
                    },
                },
                "required": ["product_id", "end_user_id"],
            },
        ),
        Tool(
            name="get_subscription_status",
            description="Check Stripe subscription status for an end-user. Looks up the Stripe subscription via stored stripe_subscription_id and returns status, plan, and customer info.",
            inputSchema={
                "type": "object",
                "properties": {
                    "end_user_id": {
                        "type": "string",
                        "description": "AutoInfo end-user ID (e.g. alice)",
                    },
                },
                "required": ["end_user_id"],
            },
        ),
        Tool(
            name="get_billing_summary",
            description="Return combined billing summary — usage data and subscription status for an end-user. Combines CostMeter usage data (LLM tokens, storage, API calls) with Stripe subscription info in a single read-only result.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "AutoInfo end-user ID (e.g. alice)",
                    },
                    "period": {
                        "type": "string",
                        "description": "Time period: today, week, month, all (default: month)",
                        "default": "month",
                    },
                },
                "required": ["user_id"],
            },
        ),
        # -- End-user Usage & Invoice (G16 — 2) ------------------------------
        Tool(
            name="get_enduser_usage",
            description="Return billable usage for an end-user over a period. Queries CostMeter and maps internal tracking to customer-billable units: LLM tokens → llm_units, storage items → storage_mb, API calls → api_call_units.",
            inputSchema={
                "type": "object",
                "properties": {
                    "end_user_id": {
                        "type": "string",
                        "description": "End-user ID (e.g. alice)",
                    },
                    "period": {
                        "type": "string",
                        "description": "Time period: today, week, month, all (default: month)",
                        "default": "month",
                    },
                },
                "required": ["end_user_id"],
            },
        ),
        Tool(
            name="get_enduser_invoice",
            description="Return an invoice-like summary with usage and estimated cost for an end-user. Computes billable units via CostMeter and applies configurable unit pricing.",
            inputSchema={
                "type": "object",
                "properties": {
                    "end_user_id": {
                        "type": "string",
                        "description": "End-user ID (e.g. alice)",
                    },
                    "period": {
                        "type": "string",
                        "description": "Time period: today, week, month, all (default: month)",
                        "default": "month",
                    },
                },
                "required": ["end_user_id"],
            },
        ),
        # -- Channel Health (1) -------------------------------------------
        Tool(
            name="get_channel_health",
            description=(
                "Check health of delivery channels. "
                "Return health status (healthy, latency_ms, error) for one or all channels. "
                "When channel_name is omitted, returns health for all 11 channels."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_name": {
                        "type": "string",
                        "description": (
                            "Specific channel to check (smtp, webhook, rest_api, file_export, "
                            "discord, telegram, wechat_work, wechat_oa, dingtalk, feishu, rss). "
                            "When omitted, all channels are checked."
                        ),
                    },
                },
                "required": [],
            },
        ),
        # -- Agent Callbacks (3) --------------------------------------------
        Tool(
            name="set_agent_callback",
            description=(
                "Register an agent callback URL for push events "
                "(new_digest, new_report, new_tutorial). "
                "Returns a callback_id for later removal. "
                "NOT shared with set_domain_webhooks — this is a separate system."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "agent_url": {
                        "type": "string",
                        "description": "Callback URL (must start with http:// or https://)",
                    },
                    "events": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Events to subscribe to: new_digest, new_report, new_tutorial",
                    },
                },
                "required": ["agent_url", "events"],
            },
        ),
        Tool(
            name="list_agent_callbacks",
            description="List all registered agent callbacks with their URLs and subscribed events",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="remove_agent_callback",
            description="Remove a registered agent callback by its callback_id",
            inputSchema={
                "type": "object",
                "properties": {
                    "callback_id": {
                        "type": "string",
                        "description": "Callback ID returned by set_agent_callback",
                    },
                },
                "required": ["callback_id"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Dispatch tool calls to the appropriate implementation."""
    try:
        # -- health_check is exempted — keep flat for the entry-point tool
        if name == "health_check":
            result = _handle_health_check()
            return [TextContent(type="text", text=json.dumps(result))]

        # -- System (2) ---------------------------------------------------
        if name == "get_tool_count":
            result = _handle_get_tool_count()
        elif name == "diagnose_system":
            result = _handle_diagnose_system()

        # -- Discovery (7) ------------------------------------------------
        elif name == "list_domains":
            result = _handle_list_domains()
        elif name == "list_available_platforms":
            result = _handle_list_available_platforms()
        elif name == "get_domain_schema":
            result = _handle_get_domain_schema(**arguments)
        elif name == "list_available_models":
            result = _handle_list_available_models()
        elif name == "get_effective_llm_config":
            result = _handle_get_effective_llm_config(**arguments)
        elif name == "activate_domain":
            result = _handle_activate_domain(**arguments)
        elif name == "deactivate_domain":
            result = _handle_deactivate_domain(**arguments)
        elif name == "add_domain":
            result = _handle_add_domain(**arguments)
        elif name == "remove_domain":
            result = _handle_remove_domain(**arguments)
        elif name == "get_domain_config":
            result = _handle_get_domain_config(**arguments)

        # -- Source Management (5) ----------------------------------------
        elif name == "add_source":
            result = _handle_add_source(**arguments)
        elif name == "add_sources":
            result = _handle_add_sources(**arguments)
        elif name == "remove_source":
            result = _handle_remove_source(**arguments)
        elif name == "test_source":
            result = _handle_test_source(**arguments)
        elif name == "list_sources":
            result = _handle_list_sources(**arguments)

        # -- Topic Management (4) -----------------------------------------
        elif name == "add_topic":
            result = _handle_add_topic(**arguments)
        elif name == "remove_topic":
            result = _handle_remove_topic(**arguments)
        elif name == "list_topics":
            result = _handle_list_topics(**arguments)
        elif name == "list_keywords":
            result = _handle_list_keywords(**arguments)

        # -- Keywords Management (3) --------------------------------------
        elif name == "approve_keyword":
            result = _handle_approve_keyword(**arguments)
        elif name == "reject_keyword":
            result = _handle_reject_keyword(**arguments)
        elif name == "suggest_keywords":
            result = _handle_suggest_keywords(**arguments)

        # -- Collection / Processing (5) ----------------------------------
        elif name == "collect_sources":
            result = _handle_collect_sources(**arguments)
        elif name == "get_collection_progress":
            result = _handle_get_collection_progress(**arguments)
        elif name == "get_collection_status":
            result = _handle_get_collection_status(**arguments)
        elif name == "process_collection":
            result = _handle_process_collection(**arguments)
        elif name == "get_processing_progress":
            result = _handle_get_processing_progress(**arguments)

        # -- Knowledge Base (4) -------------------------------------------
        elif name == "list_summaries":
            result = _handle_list_summaries(**arguments)
        elif name == "get_kb_entry":
            result = _handle_get_kb_entry(**arguments)
        elif name == "search_knowledge_base":
            result = _handle_search_knowledge_base(**arguments)
        elif name == "query_knowledge_graph":
            result = _handle_query_knowledge_graph(**arguments)
        elif name == "flag_for_knowledge_base":
            result = _handle_flag_for_knowledge_base(**arguments)
        elif name == "get_summary":
            result = _handle_get_summary(**arguments)

        elif name == "link_items":
            result = _handle_link_items(**arguments)
        elif name == "get_item_relations":
            result = _handle_get_item_relations(**arguments)

        elif name == "get_entry_history":
            result = _handle_get_entry_history(**arguments)
        elif name == "restore_entry_version":
            result = _handle_restore_entry_version(**arguments)
        elif name == "compare_versions":
            result = _handle_compare_versions(**arguments)

        elif name == "get_collection_stats":
            result = _handle_get_collection_stats(**arguments)
        elif name == "get_collection_diff":
            result = _handle_get_collection_diff(**arguments)

        elif name == "get_domain_decay":
            result = _handle_get_domain_decay(**arguments)

        # -- KB: Draft tools (3) ------------------------------------------
        elif name == "create_kb_draft":
            result = _handle_create_kb_draft(**arguments)
        elif name == "reject_kb_draft":
            result = _handle_reject_kb_draft(**arguments)
        elif name == "list_kb_tier":
            result = _handle_list_kb_tier(**arguments)
        elif name == "reindex_kb":
            result = _handle_reindex_kb(**arguments)

        # -- CEFR Classification (1) ----------------------------------------
        elif name == "classify_cefr":
            result = _handle_classify_cefr(**arguments)

        # -- Output (5) ---------------------------------------------------
        elif name == "list_output_templates":
            result = _handle_list_output_templates(**arguments)
        elif name == "generate_digest":
            result = _handle_generate_digest(**arguments)
        elif name == "generate_report":
            result = _handle_generate_report(**arguments)
        elif name == "generate_tutorial":
            result = _handle_generate_tutorial(**arguments)
        elif name == "generate_presentation":
            result = _handle_generate_presentation(**arguments)
        elif name == "localize_content":
            result = _handle_localize_content(**arguments)

        # -- Export / Import (2) -----------------------------------------------
        elif name == "export_kb":
            result = _handle_export_kb(**arguments)
        elif name == "import_kb":
            result = _handle_import_kb(**arguments)

        # -- Email (1) --------------------------------------------------------
        elif name == "send_email_digest":
            result = _handle_send_email_digest(**arguments)

        # -- Custom Extraction (2) ----------------------------------------
        elif name == "extract_fields":
            result = _handle_extract_fields(**arguments)
        elif name == "get_extraction":
            result = _handle_get_extraction(**arguments)

        # -- Schedule Management (5) ---------------------------------------
        elif name == "list_schedules":
            result = _handle_list_schedules()
        elif name == "add_schedule":
            result = _handle_add_schedule(**arguments)
        elif name == "remove_schedule":
            result = _handle_remove_schedule(**arguments)
        elif name == "run_schedules":
            result = _handle_run_schedules(**arguments)
        elif name == "get_schedule_status":
            result = _handle_get_schedule_status(**arguments)

        # -- Q&A (1) -------------------------------------------------------
        elif name == "query_collected":
            result = _handle_query_collected(**arguments)

        # -- Source Health / Feedback (2) ----------------------------------
        elif name == "get_source_health":
            result = _handle_get_source_health(**arguments)
        elif name == "rate_item":
            result = _handle_rate_item(**arguments)

        # -- Webhooks (2) -------------------------------------------------
        elif name == "set_domain_webhooks":
            result = _handle_set_domain_webhooks(**arguments)
        elif name == "get_domain_webhooks":
            result = _handle_get_domain_webhooks(**arguments)

        # -- Init / Project / Batch / Config (7) --------------------------
        elif name == "init_project":
            result = _handle_init_project(**arguments)
        elif name == "list_projects":
            result = _handle_list_projects()
        elif name == "get_project_assets":
            result = _handle_get_project_assets()
        elif name == "archive_project":
            result = _handle_archive_project(**arguments)
        elif name == "batch_run":
            result = _handle_batch_run(**arguments)
        elif name == "list_active_collections":
            result = _handle_list_active_collections()
        elif name == "get_config":
            result = _handle_get_config(**arguments)

        # -- Gate Config (2) ------------------------------------------------
        elif name == "get_gate_config":
            result = _handle_get_gate_config(**arguments)
        elif name == "set_gate_config":
            result = _handle_set_gate_config(**arguments)

        # -- Product (2) ----------------------------------------------------
        elif name == "get_product":
            result = _handle_get_product(**arguments)
        elif name == "list_products":
            result = _handle_list_products(**arguments)

        # -- End User Delivery (1) -------------------------------------------
        elif name == "send_to_enduser":
            result = _handle_send_to_enduser(**arguments)

        # -- Alert Rules (3) ------------------------------------------------
        elif name == "get_alert_rules":
            result = _handle_get_alert_rules(**arguments)
        elif name == "add_alert_rule":
            result = _handle_add_alert_rule(**arguments)
        elif name == "remove_alert_rule":
            result = _handle_remove_alert_rule(**arguments)

        # -- Budget Thresholds (2) -------------------------------------------
        elif name == "get_budget_thresholds":
            result = _handle_get_budget_thresholds()
        elif name == "set_budget_thresholds":
            result = _handle_set_budget_thresholds(**arguments)

        # -- Metrics (2) --------------------------------------------------
        elif name == "get_metrics":
            result = _handle_get_metrics(name, arguments)
        elif name == "get_prometheus_metrics":
            result = _handle_get_prometheus_metrics(name, arguments)

        # -- Trace (1) ----------------------------------------------------
        elif name == "trace_item":
            result = _handle_trace_item(name, arguments)

        # -- Soft-delete & GDPR (4) -----------------------------------------
        elif name == "soft_delete_entry":
            result = _handle_soft_delete_entry(name, arguments)
        elif name == "mark_stale":
            result = _handle_mark_stale(name, arguments)
        elif name == "restore_entry":
            result = _handle_restore_entry(name, arguments)
        elif name == "export_user_data":
            result = _handle_export_user_data(name, arguments)
        elif name == "delete_user_data":
            result = _handle_delete_user_data(name, arguments)

        # -- Portal / End-user Self-service (2) ------------------------------
        elif name == "get_enduser_history":
            result = _handle_get_enduser_history(**arguments)
        elif name == "get_enduser_products":
            result = _handle_get_enduser_products(**arguments)

        # -- Delivery Log (1) ------------------------------------------------
        elif name == "query_delivery_log":
            result = _handle_query_delivery_log(name, arguments)

        # -- Delivery Monitor (2) ------------------------------------------
        elif name == "list_active_deliveries":
            result = _handle_list_active_deliveries()
        elif name == "get_delivery_log":
            result = _handle_get_delivery_log(**arguments)

        # -- Channel Health (1) ------------------------------------------
        elif name == "get_channel_health":
            result = _handle_get_channel_health(**arguments)

        # -- Merge / Find Similar (2) ---------------------------------
        elif name == "merge_items":
            result = _handle_merge_items(**arguments)
        elif name == "find_similar_items":
            result = _handle_find_similar_items(**arguments)

        # -- KB Freshness (1) ---------------------------------------------
        elif name == "calculate_freshness_score":
            result = _handle_calculate_freshness_score(name, arguments)

        # -- End-User Trial (2) ----------------------------------------------
        elif name == "activate_trial":
            result = _handle_activate_trial(**arguments)
        elif name == "check_trial_expiry":
            result = _handle_check_trial_expiry(**arguments)

        # -- End-User Preferences (2) ----------------------------------------
        elif name == "update_preferences":
            result = _handle_update_preferences(**arguments)
        elif name == "get_preferences":
            result = _handle_get_preferences(**arguments)

        # -- Stripe Billing (3) ------------------------------------------------
        elif name == "create_checkout_session":
            result = _handle_create_checkout_session(**arguments)
        elif name == "get_subscription_status":
            result = _handle_get_subscription_status(**arguments)
        elif name == "get_billing_summary":
            result = _handle_get_billing_summary(**arguments)

        # -- Usage-based Billing (G16 — 2) -----------------------------------
        elif name == "get_enduser_usage":
            result = _handle_get_enduser_usage(**arguments)
        elif name == "get_enduser_invoice":
            result = _handle_get_enduser_invoice(**arguments)

        # -- Agent Callbacks (3) --------------------------------------------
        elif name == "set_agent_callback":
            result = _handle_set_agent_callback(**arguments)
        elif name == "list_agent_callbacks":
            result = _handle_list_agent_callbacks()
        elif name == "remove_agent_callback":
            result = _handle_remove_agent_callback(**arguments)

        else:
            return [
                TextContent(
                    type="text",
                    text=json.dumps(error_response(
                        code=ErrorCode.UNKNOWN_TOOL,
                        message=f"Unknown tool: {name}",
                        actionable=False,
                    )),
                )
            ]

        # Wrap non-health responses in uniform envelope
        # Backward-compat: detect pre-wrapped dual-format responses
        if isinstance(result, dict) and "success" in result:
            # Already in envelope format (dual-format from handlers),
            # pass through unchanged — no re-wrapping needed.
            wrapped = result
        elif isinstance(result, dict) and "error_code" in result:
            # Legacy flat format: wrap into envelope with both
            # flat fields and nested error for backward compat.
            wrapped = {
                "success": False,
                "error_code": result["error_code"],
                "message": result.get("message", ""),
                "actionable": result.get("actionable", True),
                "error": {
                    "code": result["error_code"],
                    "message": result.get("message", ""),
                    "actionable": result.get("actionable", True),
                },
            }
        else:
            wrapped = success_response(result)
        return [TextContent(type="text", text=json.dumps(wrapped))]
    except NotImplementedError:
        # Stub tools return a graceful error response
        return _error_response(NotImplementedError(str(arguments.get("message", "Not implemented in v0.1"))))
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
