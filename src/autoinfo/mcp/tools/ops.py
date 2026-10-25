"""MCP tool schemas — Audit, CEFR, project/batch config (10 tools).

Phase 1 of #581: schemas extracted from ``mcp/server.py::_full_tool_list``
verbatim.  ``build_tools()`` returns FRESH ``Tool`` objects on every call,
so ``_decorate_tools`` mutation never leaks across calls.
"""

from __future__ import annotations

import concurrent.futures
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from mcp.types import Tool

from autoinfo.mcp import context as mcp_context
from autoinfo.mcp.errors import ErrorCode, error_response


def build_tools() -> list[Tool]:
    """Return the 10 schemas for this module, in registration order."""
    return [
        # -- Audit (1) -------------------------------------------------------
        Tool(
            name="query_audit_log",
            description=(
                "Query the immutable audit log with optional filters. "
                "All filters are optional and combined with AND logic. "
                "Results returned newest-first."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "actor": {
                        "type": "string",
                        "description": "Filter by actor name",
                    },
                    "action": {
                        "type": "string",
                        "description": "Filter by action name",
                    },
                    "resource_type": {
                        "type": "string",
                        "description": "Filter by resource type",
                    },
                    "date_from": {
                        "type": "string",
                        "description": "ISO-8601 lower bound on timestamp",
                    },
                    "date_to": {
                        "type": "string",
                        "description": "ISO-8601 upper bound on timestamp",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max entries to return (default 100)",
                        "default": 100,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Pagination offset (default 0)",
                        "default": 0,
                    },
                },
                "required": [],
            },
        ),
        # -- CEFR Classification (1) -----------------------------------------
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
        # -- CEFR Batch (1) --------------------------------------------------
        Tool(
            name="cefr_batch",
            description=(
                "Batch classify multiple texts into CEFR levels (A1-C2). "
                "Each text is classified independently. Per-text errors are "
                "included with an error key in the results array."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "texts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Texts to classify (non-empty)",
                    },
                    "lang": {
                        "type": "string",
                        "description": "Language code: en, zh, or ja",
                        "default": "en",
                        "enum": ["en", "zh", "ja"],
                    },
                },
                "required": ["texts"],
            },
        ),
        # -- Project / Batch / Config (7) ------------------------------------
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
                        "enum": ["active", "archived"],
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
                        "description": (
                            "Optional asset-type filter: collections, knowledge, "
                            "database, exports, or config. Omit to return every "
                            "asset group."
                        ),
                        "enum": [
                            "collections",
                            "knowledge",
                            "database",
                            "exports",
                            "config",
                        ],
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
                    "resume_from": {
                        "type": "string",
                        "description": (
                            "Checkpoint/resume mode for the collect + process "
                            "pipeline (R-A-01): 'auto' resumes both phases from "
                            "their persisted checkpoints, 'start' checkpoints a "
                            "fresh run, or a source name to start collection at "
                            "that source. Omit for a legacy run."
                        ),
                        "default": "",
                    },
                },
                "required": ["domain"],
            },
        ),
        Tool(
            name="get_feeds",
            description=(
                "Return a paginated feed of KB entries for a domain. "
                "Supports optional filters by topic tag, source type, "
                "and collected-at date.  Output format: JSON (default) or RSS 2.0 XML."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain to query (required)",
                    },
                    "topic": {
                        "type": "string",
                        "description": "Optional filter by topic tag",
                    },
                    "source_type": {
                        "type": "string",
                        "description": "Optional filter by source type (e.g. rss, api)",
                    },
                    "since": {
                        "type": "string",
                        "description": "Optional ISO date filter (collected_at >=)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max items to return (1-200)",
                        "default": 50,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Number of items to skip for pagination",
                        "default": 0,
                    },
                    "format": {
                        "type": "string",
                        "description": "Output format: 'json' (paginated JSON envelope) or 'rss' (RSS 2.0 XML feed)",
                        "default": "json",
                        "enum": ["json", "rss"],
                    },
                },
                "required": ["domain"],
            },
        ),
        Tool(
            name="list_active_collections",
            description=(
                "List currently active or in-progress collection runs. Optionally filter by domain."
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
    ]


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
        mcp_context.logger.exception("Audit log query failed")
        return mcp_context._error_from_exc(exc, "Audit log query failed")


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


def _handle_list_projects(status: str = "") -> dict[str, Any]:
    """List all configured projects with domain/source summaries."""
    try:
        config = mcp_context._load_config()
    except Exception as exc:
        return mcp_context._error_from_exc(exc, "Failed to list projects")

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

    return mcp_context._canonicalize(assets)


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
        _wiki_count = store.index.count_entries()
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
            tags = mcp_context._parse_tags(entry)
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
            **mcp_context._text_payload_metadata(
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
        return mcp_context._error_from_exc(exc, "Failed to list active collections")

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
        return mcp_context._error_from_exc(exc, "Failed to load the project configuration")

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
