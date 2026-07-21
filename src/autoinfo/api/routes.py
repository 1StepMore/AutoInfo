"""REST API routes — CRUD + search endpoints for the knowledge base.

All routes are mounted under ``/api/v1`` in ``server.py``.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from autoinfo.kb import KBStore
from autoinfo.models import Item

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# KBStore singleton (lazy-init)
# ---------------------------------------------------------------------------

_store: KBStore | None = None


def _get_store() -> KBStore:
    global _store
    if _store is None:
        _store = KBStore()
    return _store


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class EntryCreate(BaseModel):
    """Request body for ``POST /entries``."""

    title: str = Field(..., min_length=1, description="Entry title")
    content: str = Field("", description="Entry body text")
    domain: str = Field("default", description="Domain namespace")
    tier: str = Field("01-Raw", description="KB pipeline tier")
    source_url: str = Field("", description="Original source URL")
    source_type: str = Field("api", description="Source type (rss, api, web)")
    source_platform: str = Field("api", description="Source platform name")
    tags: list[str] = Field(default_factory=list, description="Topic tags")
    language: str = Field("", description="Content language code")


class EntryResponse(BaseModel):
    """Response body for a single entry."""

    entry_id: str
    title: str
    domain: str
    tier: str
    source_url: str
    source_type: str
    source_platform: str
    collected_at: str
    summary: str
    tags: list[str]
    quality_tier: int
    relevance_score: float
    dedup_status: str
    file_path: str
    content: str = ""
    language: str = ""


class ErrorResponse(BaseModel):
    """Standard error payload."""

    detail: str
    error_code: str = "unknown"


class SearchQuery(BaseModel):
    """Query parameters for the search endpoint."""

    q: str = Field(..., description="Search query string")
    mode: str = Field("fts5", pattern=r"^(fts5|hybrid|vector)$")
    domain: str = Field("", description="Optional domain filter")
    limit: int = Field(20, ge=1, le=200)
    offset: int = Field(0, ge=0)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(tags=["entries"])


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _entry_to_response(entry: dict[str, Any]) -> dict[str, Any]:
    """Normalise a raw entry dict from the index into a response dict.

    Handles deserialising the ``tags`` JSON string into a list.
    """
    tags_raw = entry.get("tags") or []
    if isinstance(tags_raw, str):
        import json
        try:
            tags = json.loads(tags_raw)
        except (json.JSONDecodeError, TypeError):
            tags = [tags_raw] if tags_raw else []
    else:
        tags = list(tags_raw) if tags_raw else []
    return {
        "entry_id": entry.get("entry_id", ""),
        "title": entry.get("title", ""),
        "domain": entry.get("domain", ""),
        "tier": entry.get("tier", "01-Raw"),
        "source_url": entry.get("source_url", ""),
        "source_type": entry.get("source_type", ""),
        "source_platform": entry.get("source_platform", ""),
        "collected_at": entry.get("collected_at", ""),
        "summary": entry.get("summary", ""),
        "tags": tags,
        "quality_tier": entry.get("quality_tier", 1),
        "relevance_score": entry.get("relevance_score", 0.0),
        "dedup_status": entry.get("dedup_status", "unique"),
        "file_path": entry.get("file_path", ""),
        "content": entry.get("content", ""),
        "language": entry.get("language", ""),
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/entries", response_model=list[EntryResponse])
async def list_entries(
    skip: int = Query(0, ge=0, description="Number of entries to skip"),
    limit: int = Query(20, ge=1, le=200, description="Max entries to return"),
    domain: str | None = Query(None, description="Optional domain filter"),
    tier: str | None = Query(None, description="Optional tier filter (01-Raw, 02-Draft, 03-Wiki)"),
    q: str | None = Query(None, description="Full-text search query"),
    date_from: str | None = Query(None, description="ISO date filter (collected_at >=)"),
) -> list[dict[str, Any]]:
    """List entries with optional search, filters, and pagination."""
    store = _get_store()

    # When a search query is provided, use search_knowledge_base
    if q:
        result = store.search_knowledge_base(
            query=q,
            domain=domain or "",
            limit=limit,
            offset=skip,
            mode="fts5",
        )
        raw_entries: list[dict[str, Any]] = result.get("entries", [])
        return [_entry_to_response(e) for e in raw_entries]

    # Otherwise, list all entries with optional filters
    raw = store.list_all_entries(
        domain=domain,
        tier=tier,
        date_from=date_from,
        limit=limit,
        offset=skip,
    )
    return [_entry_to_response(e) for e in raw]


@router.get("/entries/{entry_id}", response_model=EntryResponse)
async def get_entry(entry_id: str) -> dict[str, Any]:
    """Return a single entry with full content."""
    store = _get_store()
    entry = store.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Entry '{entry_id}' not found")
    return _entry_to_response(entry)


@router.post("/entries", response_model=EntryResponse, status_code=201)
async def create_entry(body: EntryCreate) -> dict[str, Any]:
    """Create a new KB entry from the provided fields."""
    store = _get_store()

    # Build an Item from the request body
    item = Item(
        id=str(uuid4()),
        source_name=body.source_platform,
        source_type=body.source_type,
        source_url=body.source_url,
        title=body.title,
        content=body.content,
        domain=body.domain,
        topic_tags=body.tags[:],
        collected_at=datetime.now(timezone.utc).isoformat(),
        language=body.language,
        content_type="text",
        quality_tier=1,
    )

    try:
        entry = store.store_entry(item=item, tier=body.tier)
    except PermissionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Fetch the full entry with content to return
    full = store.get_entry(entry.entry_id) or entry.to_dict()
    return _entry_to_response(full)


@router.delete("/entries/{entry_id}", status_code=204)
async def delete_entry(entry_id: str) -> None:
    """Delete an entry by its ID.

    Returns ``204 No Content`` on success.
    Raises ``404`` when the entry does not exist.
    """
    store = _get_store()
    result = store.delete_entry(entry_id)
    if not result.get("deleted"):
        raise HTTPException(
            status_code=404,
            detail=result.get("error", f"Entry '{entry_id}' not found"),
        )


@router.get("/search", response_model=dict[str, Any])
async def search_entries(
    q: str = Query(..., description="Search query string"),
    mode: str = Query("fts5", description="Search mode: fts5, hybrid, or vector"),
    domain: str = Query("", description="Optional domain filter"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    filter_tags: str | None = Query(None, description="Comma-separated tag filter"),
    filter_date_from: str | None = Query(None, description="ISO date lower bound"),
    filter_date_to: str | None = Query(None, description="ISO date upper bound"),
    filter_quality_tier_min: int | None = Query(None, ge=1, le=5),
    filter_quality_tier_max: int | None = Query(None, ge=1, le=5),
    filter_language: str | None = Query(None),
) -> dict[str, Any]:
    """Full-text and hybrid search across the knowledge base.

    Supports all search modes (fts5, hybrid, vector) and the full set of
    faceted filters from the underlying FTS5 engine.
    """
    store = _get_store()

    parsed_tags: list[str] = []
    if filter_tags:
        parsed_tags = [t.strip() for t in filter_tags.split(",") if t.strip()]

    result = store.search_knowledge_base(
        query=q,
        domain=domain,
        limit=limit,
        offset=offset,
        mode=mode,
        filter_tags=parsed_tags or None,
        filter_date_from=filter_date_from,
        filter_date_to=filter_date_to,
        filter_quality_tier_min=filter_quality_tier_min,
        filter_quality_tier_max=filter_quality_tier_max,
        filter_language=filter_language,
    )

    # Normalise entries in the result
    result["entries"] = [_entry_to_response(e) for e in result.get("entries", [])]
    return result
