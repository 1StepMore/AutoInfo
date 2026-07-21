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
from dataclasses import asdict
from pathlib import Path
from typing import Any

import httpx
import yaml
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from autoinfo import __version__

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
        "progress_pct": float,
        "items_collected": int,
        "errors": int,
        "items_per_source": dict[str, int],
        "duration_s": float,
    }
"""

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
        "tools_count": 58,
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
    from datetime import datetime, timezone

    from autoinfo.collect import run_collection

    domain = kwargs.get("domain", "unknown")
    _collection_state[domain] = {
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": "",
        "progress_pct": 0.0,
        "items_collected": 0,
        "errors": 0,
        "items_per_source": {},
        "duration_s": 0.0,
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
        return result
    except Exception:
        _collection_state[domain].update({
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "progress_pct": 100.0,
        })
        raise


def _handle_get_collection_progress(domain: str = "") -> dict[str, Any]:
    """Return current collection progress for *domain* (or all domains)."""
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
    from datetime import datetime, timezone

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
    from autoinfo.process import run_processing

    result = run_processing(**kwargs)
    return asdict(result)


def _handle_get_processing_progress(domain: str) -> dict[str, Any]:
    """Return processing progress from ``autoinfo.process.get_processing_progress``."""
    from autoinfo.process import get_processing_progress

    return get_processing_progress(domain=domain)


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
# Discovery tools
# ---------------------------------------------------------------------------


def _handle_list_domains() -> dict[str, Any]:
    """List all configured domains with source/topic counts."""
    try:
        config = _load_config()
    except Exception as exc:
        return {"domains": [], "count": 0, "error": str(exc)}

    domains = []
    for d in config.domains:
        domains.append({
            "name": d.name,
            "active": d.active,
            "source_count": len(d.sources),
            "topic_count": len(d.topics),
        })
    return {"domains": domains, "count": len(domains)}


def _handle_activate_domain(name: str) -> dict[str, Any]:
    """Activate a domain (set domain.active = True)."""
    try:
        config = _load_config()
    except Exception as exc:
        return _error_dict(exc)

    domain_cfg = _find_domain(config, name)
    if domain_cfg is None:
        return {
            "error_code": "DomainNotFound",
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
            "error_code": "DomainNotFound",
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


def _handle_get_domain_config(name: str) -> dict[str, Any]:
    """Return full domain config including sources, topics, extract_fields."""
    try:
        config = _load_config()
    except Exception as exc:
        return _error_dict(exc)

    domain_cfg = _find_domain(config, name)
    if domain_cfg is None:
        return {
            "error_code": "DomainNotFound",
            "message": f"Domain '{name}' is not configured",
            "actionable": True,
        }

    sources = [
        {
            "name": s.name,
            "type": s.type,
            "url": s.url,
            "quality_tier": s.quality_tier,
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


def _handle_get_domain_schema(domain: str) -> dict[str, Any]:
    """Return the schema / structure for a given domain."""
    try:
        config = _load_config()
    except Exception as exc:
        return _error_dict(exc)

    domain_cfg = _find_domain(config, domain)
    if domain_cfg is None:
        return {
            "error_code": "DomainNotFound",
            "message": f"Domain '{domain}' is not configured",
            "actionable": True,
        }

    sources = [
        {"name": s.name, "type": s.type, "url": s.url, "quality_tier": s.quality_tier}
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
        "output_templates": ["digest", "report", "tutorial", "presentation"],
        "topics": topics,
        "sources": sources,
    }


def _handle_list_available_models() -> dict[str, Any]:
    """List available LLM models from configuration."""
    try:
        config = _load_config()
    except Exception as exc:
        return {"models": [], "count": 0, "error": str(exc)}

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
        return {"error_code": "ValidationError", "message": url_error, "actionable": True}

    type_error = _validate_source_type(type)
    if type_error:
        return {"error_code": "ValidationError", "message": type_error, "actionable": True}

    try:
        config = _load_config()
    except Exception as exc:
        return _error_dict(exc)

    domain_cfg = _find_domain(config, domain)
    if domain_cfg is None:
        return {
            "error_code": "DomainNotFound",
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
                },
                "created": False,
                "source_id": f"{domain}:{existing.name}",
            }
            if existing.quality_tier >= 3:
                dup_result["warning"] = "Quality tier 3+ source — content may have lower authority."
            return dup_result

    # Determine next quality_tier based on type
    quality_tier = 1 if type in ("api", "rss") else 2

    from autoinfo.config import SourceConfig

    new_source = SourceConfig(name=name, type=type, url=url, quality_tier=quality_tier)
    domain_cfg.sources.append(new_source)
    _save_config(config)

    result: dict[str, Any] = {
        "source": {
            "name": name,
            "type": type,
            "url": url,
            "domain": domain,
            "quality_tier": quality_tier,
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
                "error_code": type(exc).__name__,
                "message": str(exc),
                "actionable": True,
            })

    return {
        "results": results,
        "total": len(sources),
        "succeeded": len(sources) - errored,
        "errored": errored,
    }


def _handle_remove_source(source_id: str) -> dict[str, Any]:
    """Remove a source by its source_id (``domain:name``)."""
    try:
        config = _load_config()
    except Exception as exc:
        return _error_dict(exc)

    parts = source_id.split(":", 1)
    if len(parts) != 2:
        return {
            "error_code": "InvalidSourceId",
            "message": "source_id must be in format 'domain:name'",
            "actionable": True,
        }
    domain_name, source_name = parts

    domain_cfg = _find_domain(config, domain_name)
    if domain_cfg is None:
        return {
            "error_code": "DomainNotFound",
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
        "error_code": "SourceNotFound",
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
        return {"reachable": False, "error_code": "ValidationError", "message": url_error, "actionable": True}
    type_error = _validate_source_type(type)
    if type_error:
        return {"reachable": False, "error_code": "ValidationError", "message": type_error, "actionable": True}
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
            "error_code": "Timeout",
            "message": f"Request to '{url}' timed out",
            "actionable": True,
        }
    except Exception as exc:
        return {
            "reachable": False,
            "error_code": exc.__class__.__name__,
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
            "error_code": "DomainNotFound",
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
            "error_code": "DomainNotFound",
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


def _handle_remove_topic(domain: str, topic_id: str) -> dict[str, Any]:
    """Remove a topic by its topic_id (``domain:name``)."""
    try:
        config = _load_config()
    except Exception as exc:
        return _error_dict(exc)

    domain_cfg = _find_domain(config, domain)
    if domain_cfg is None:
        return {
            "error_code": "DomainNotFound",
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
        "error_code": "TopicNotFound",
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
            "error_code": "DomainNotFound",
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

    Returns keywords per domain/topic from config.  When *topic* is provided,
    only keywords for that topic are returned.
    """
    try:
        config = _load_config()
    except Exception as exc:
        return _error_dict(exc)

    domain_cfg = _find_domain(config, domain)
    if domain_cfg is None:
        return {
            "error_code": "DomainNotFound",
            "message": f"Domain '{domain}' is not configured",
            "actionable": True,
        }

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

    return {
        "domain": domain,
        "topic": topic or "*",
        "topics": results,
        "count": len(results),
    }


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
            "error_code": "NotFound",
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
            "error_code": "NotFound",
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
) -> dict[str, Any]:
    """Search the knowledge base using FTS5 full-text search."""
    from autoinfo.kb import KBStore

    store = KBStore()
    return store.search_knowledge_base(
        query=query, domain=domain, limit=limit, offset=offset
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
            "error_code": "ValidationError",
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
            "error_code": type(exc).__name__,
            "message": str(exc),
            "actionable": True,
        }


def _handle_list_kb_tier(
    domain: str,
    tier: str,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """List entries in a specific KB tier."""
    from autoinfo.kb import KBStore

    store = KBStore()
    entries = store.list_kb_tier(domain=domain, tier=tier, limit=limit, offset=offset)
    return {
        "domain": domain,
        "tier": tier,
        "entries": entries,
        "count": len(entries),
    }


def _handle_list_output_templates(domain: str = "") -> dict[str, Any]:
    """List available output templates for a domain."""
    templates = ["digest", "report", "tutorial", "presentation"]
    return {"domain": domain, "templates": templates, "count": len(templates)}


def _handle_generate_digest(
    domain: str,
    period: str = "weekly",
    format: str = "markdown",
) -> dict[str, Any]:
    """Generate a digest of KB entries for *domain* over the given *period*.

    Dispatches to :func:`autoinfo.output.generate_digest`.
    """
    from autoinfo.output import generate_digest as _generate_digest

    try:
        result = _generate_digest(domain=domain, period=period, format=format)
        if format == "json":
            # Parse JSON string back to dict for structured MCP response
            import json as _json

            return {"success": True, "format": format, "content": _json.loads(result)}
        return {"success": True, "format": format, "content": result}
    except ValueError as exc:
        return {
            "error_code": "ValidationError",
            "message": str(exc),
            "actionable": True,
        }
    except Exception as exc:
        logger.exception("Digest generation failed for domain '%s'", domain)
        return _error_dict(exc)


def _handle_generate_tutorial(
    domain: str,
    topic: str | None = None,
    format: str = "markdown",
) -> dict[str, Any]:
    """Generate a structured tutorial for *domain*.

    Thin wrapper around :func:`autoinfo.output.generate_tutorial`.
    """
    from autoinfo.output import generate_tutorial as _generate_tutorial

    try:
        result = _generate_tutorial(domain=domain, format=format)
        return {"success": True, "format": format, "domain": domain, "topic": topic, "content": result}
    except ValueError as exc:
        return {
            "error_code": "ValidationError",
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
) -> dict[str, Any]:
    """Generate a slide-based presentation for *topic* within *domain*.

    Thin wrapper around :func:`autoinfo.output.generate_presentation`.
    """
    from autoinfo.output import generate_presentation as _generate_presentation

    try:
        topic_str = topic or ""
        result = _generate_presentation(domain=domain, topic=topic_str, slide_count=slides)
        return {"success": True, "domain": domain, "topic": topic, "slides": slides, "content": result}
    except ValueError as exc:
        return {
            "error_code": "ValidationError",
            "message": str(exc),
            "actionable": True,
        }
    except Exception as exc:
        logger.exception("Presentation generation failed for domain '%s'", domain)
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
            "error_code": "ValidationError",
            "message": str(exc),
            "actionable": True,
        }
    except Exception as exc:
        logger.exception("Localization failed")
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
) -> dict[str, Any]:
    """Add a new collection schedule."""
    try:
        from croniter import croniter

        if not croniter.is_valid(expression):
            return {
                "error_code": "InvalidCronExpression",
                "message": f"'{expression}' is not a valid cron expression",
                "actionable": True,
            }

        from autoinfo.cli.cron import Schedule, load_schedules, save_schedules, _now_iso

        schedules = load_schedules()
        if name in schedules:
            return {
                "error_code": "ScheduleAlreadyExists",
                "message": f"A schedule named '{name}' already exists",
                "actionable": True,
            }

        new_schedule = Schedule(
            name=name,
            expression=expression,
            domain=domain,
            enabled=True,
            last_run=None,
            created_at=_now_iso(),
        )
        schedules[name] = new_schedule
        save_schedules(schedules)
        return {
            "created": True,
            "schedule": {
                "name": name,
                "expression": expression,
                "domain": domain,
                "enabled": True,
                "last_run": None,
                "created_at": new_schedule.created_at,
            },
        }
    except Exception as exc:
        return _error_dict(exc)


def _handle_remove_schedule(name: str) -> dict[str, Any]:
    """Remove a collection schedule."""
    try:
        from autoinfo.cli.cron import load_schedules, save_schedules

        schedules = load_schedules()
        if name not in schedules:
            return {
                "error_code": "ScheduleNotFound",
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


def _handle_list_projects() -> dict[str, Any]:
    """List all configured projects with domain/source summaries."""
    try:
        config = _load_config()
    except Exception as exc:
        return {"projects": [], "count": 0, "error": str(exc)}

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
        }
    ]
    return {"projects": projects, "count": len(projects)}


def _handle_get_project_assets() -> dict[str, Any]:
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

    return assets


def _handle_archive_project(reason: str = "") -> dict[str, Any]:
    """Archive the current project (refuses unless published to 03-Wiki)."""
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
            "error_code": "NotPublished",
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
    """Run collect + process in sequence for a domain."""
    from autoinfo.collect import run_collection
    from autoinfo.process import ProcessResult, run_processing

    collect_args: dict[str, Any] = {"domain": domain, "limit": limit}
    if topic:
        collect_args["topic"] = topic

    try:
        collected = run_collection(**collect_args)
    except Exception as exc:
        return {
            "error_code": "CollectionFailed",
            "message": f"Collection phase failed: {exc}",
            "actionable": True,
        }

    process_args: dict[str, Any] = {"domain": domain}
    if model:
        process_args["model"] = model

    try:
        processed: ProcessResult = run_processing(**process_args)
        processed_dict = asdict(processed)
    except Exception as exc:
        return {
            "error_code": "ProcessingFailed",
            "message": f"Processing phase failed: {exc}",
            "actionable": True,
            "collection_result": collected,
        }

    return {
        "domain": domain,
        "topic": topic or "*",
        "collection_result": collected,
        "processing_result": processed_dict,
        "success": True,
    }


def _handle_list_active_collections() -> dict[str, Any]:
    """List active / in-progress collection runs."""
    from autoinfo.collect import list_active_collections as _list_active

    try:
        active = _list_active()
    except Exception as exc:
        return {"active_collections": [], "count": 0, "error": str(exc)}

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
            "error_code": "InvalidSection",
            "message": f"Unknown config section '{section}'. Valid: project, llm, domains",
            "actionable": True,
        }

    config_dict["config_path"] = str(_config_path())

    return {"config": config_dict}


# ---------------------------------------------------------------------------
# Error response helper
# ---------------------------------------------------------------------------


def _error_dict(exc: Exception) -> dict[str, Any]:
    """Build a standardised error dict (same shape as _error_response)."""
    return {
        "error_code": type(exc).__name__,
        "message": str(exc),
        "actionable": True,
    }


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
    """Declare the 30 available tools with their input schemas."""
    return [
        # -- System (2) ---------------------------------------------------
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
        # -- Discovery (7) ------------------------------------------------
        Tool(
            name="list_domains",
            description="List all configured domains with source/topic counts",
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
                    },
                },
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
                                "name": {"type": "string"},
                                "url": {"type": "string"},
                                "type": {
                                    "type": "string",
                                    "default": "api",
                                },
                                "domain": {"type": "string"},
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
                        "description": "Source identifier in 'domain:name' format",
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
                        "description": "Topic identifier (name or 'domain:name' format)",
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
                    },
                },
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
            description="Get processing progress for a domain",
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
                },
                "required": ["entry_id"],
            },
        ),
        Tool(
            name="search_knowledge_base",
            description=(
                "Search the knowledge base using FTS5 full-text search. "
                "Supports simple term queries with optional domain filter."
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
                    },
                },
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
                },
                "required": ["domain", "tier"],
            },
        ),
        # -- Output (5) ---------------------------------------------------
        Tool(
            name="list_output_templates",
            description="List available output templates for a domain",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (optional)",
                    },
                },
            },
        ),
        Tool(
            name="generate_digest",
            description=(
                "Generate a digest of KB entries for a domain over a given "
                "period (daily, weekly, monthly).  Returns markdown by "
                "default; also supports html and json."
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
                    },
                    "format": {
                        "type": "string",
                        "description": "Output format: markdown, html, json",
                        "default": "markdown",
                    },
                },
                "required": ["domain"],
            },
        ),
        Tool(
            name="generate_tutorial",
            description="Generate a structured tutorial for a domain",
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
                        "description": "Output format (markdown, html, json)",
                        "default": "markdown",
                    },
                },
                "required": ["domain"],
            },
        ),
        Tool(
            name="generate_presentation",
            description="Generate a slide-based presentation for a topic within a domain",
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
                "statistics, and citations."
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
                },
                "required": ["target_lang"],
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
            description="Add a new collection schedule with a cron expression",
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
                        "description": "Domain to collect on this schedule",
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
                        "description": "Source identifier in 'domain:name' format",
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
        # -- Project / Batch / Config (6) ------------------------------------
        Tool(
            name="list_projects",
            description=(
                "List all configured projects with domain count, source/topic "
                "summaries, and LLM provider info."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_project_assets",
            description=(
                "Return project asset paths and sizes — collections, knowledge "
                "directories, database, exports, and config directory."
            ),
            inputSchema={"type": "object", "properties": {}},
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
                    },
                },
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
                "Returns status, progress, and start time per collection."
            ),
            inputSchema={"type": "object", "properties": {}},
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
                    },
                },
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Dispatch tool calls to the appropriate implementation."""
    try:
        # -- System (2) ---------------------------------------------------
        if name == "health_check":
            result = _handle_health_check()
        elif name == "diagnose_system":
            result = _handle_diagnose_system()

        # -- Discovery (7) ------------------------------------------------
        elif name == "list_domains":
            result = _handle_list_domains()
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

        elif name == "get_collection_stats":
            result = _handle_get_collection_stats(**arguments)
        elif name == "get_collection_diff":
            result = _handle_get_collection_diff(**arguments)

        # -- KB: Draft tools (3) ------------------------------------------
        elif name == "create_kb_draft":
            result = _handle_create_kb_draft(**arguments)
        elif name == "reject_kb_draft":
            result = _handle_reject_kb_draft(**arguments)
        elif name == "list_kb_tier":
            result = _handle_list_kb_tier(**arguments)

        # -- Output (5) ---------------------------------------------------
        elif name == "list_output_templates":
            result = _handle_list_output_templates(**arguments)
        elif name == "generate_digest":
            result = _handle_generate_digest(**arguments)
        elif name == "generate_tutorial":
            result = _handle_generate_tutorial(**arguments)
        elif name == "generate_presentation":
            result = _handle_generate_presentation(**arguments)
        elif name == "localize_content":
            result = _handle_localize_content(**arguments)

        # -- Custom Extraction (2) ----------------------------------------
        elif name == "extract_fields":
            result = _handle_extract_fields(**arguments)
        elif name == "get_extraction":
            result = _handle_get_extraction(**arguments)

        # -- Schedule Management (4) ---------------------------------------
        elif name == "list_schedules":
            result = _handle_list_schedules()
        elif name == "add_schedule":
            result = _handle_add_schedule(**arguments)
        elif name == "remove_schedule":
            result = _handle_remove_schedule(**arguments)
        elif name == "run_schedules":
            result = _handle_run_schedules(**arguments)

        # -- Q&A (1) -------------------------------------------------------
        elif name == "query_collected":
            result = _handle_query_collected(**arguments)

        # -- Source Health / Feedback (2) ----------------------------------
        elif name == "get_source_health":
            result = _handle_get_source_health(**arguments)
        elif name == "rate_item":
            result = _handle_rate_item(**arguments)

        # -- Project / Batch / Config (6) ---------------------------------
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
