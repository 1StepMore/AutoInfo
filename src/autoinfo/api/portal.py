"""Portal router — read-only end-user dashboard (FastAPI + Jinja2).

Serves a Bootstrap 5 web UI at ``/portal/{user_id}`` that mirrors the
styling of the existing ``/dashboard`` SPA.  All pages are read-only;
preference editing and subscription management are intentionally excluded
(operator-managed per v1).

Routes
------
- ``GET /portal/{user_id}``            — landing dashboard
- ``GET /portal/{user_id}/preferences`` — read-only delivery preferences
- ``GET /portal/{user_id}/history``     — paginated delivery log
- ``GET /portal/{user_id}/products``    — delivered products archive
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Templates (module-level singleton — directory is fixed)
# ---------------------------------------------------------------------------

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates" / "portal"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(tags=["portal"])

# Default page size for the delivery history table.
_DEFAULT_PAGE_SIZE = 20


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _trial_info(profile: Any) -> dict[str, Any]:
    """Compute trial status info for a user profile.

    Returns a dict with ``days_remaining``, ``status``, ``trial_started_at``,
    ``trial_ends_at``, and ``trial_days``.  Delegates the heavy lifting to
    :func:`autoinfo.user_store.check_trial_expiry` when available, falling
    back to a local computation on error.
    """
    try:
        from autoinfo.user_store import check_trial_expiry

        result = check_trial_expiry(profile.user_id)
        if "error_code" in result:
            # Fall through to local computation
            pass
        else:
            return {
                "days_remaining": result.get("days_remaining", 0),
                "status": result.get("status", "no_trial"),
                "trial_started_at": result.get("trial_started_at", "")
                or profile.trial_started_at,
                "trial_ends_at": profile.trial_ends_at,
                "trial_days": result.get("trial_days", profile.trial_days),
            }
    except Exception:  # pragma: no cover — defensive
        logger.debug("check_trial_expiry failed, computing locally", exc_info=True)

    return {
        "days_remaining": 0,
        "status": "no_trial",
        "trial_started_at": profile.trial_started_at,
        "trial_ends_at": profile.trial_ends_at,
        "trial_days": profile.trial_days,
    }


def _delivery_history(
    user_id: str, limit: int, offset: int
) -> tuple[list[dict[str, Any]], int]:
    """Return ``(page_entries, total)`` for a user's delivery log.

    Aggregates across all of the user's subscriptions, sorts newest-first,
    and applies the pagination slice.
    """
    from autoinfo.delivery_log import query_delivery_log
    from autoinfo.user_store import list_subscriptions

    subscriptions = list_subscriptions(user_id=user_id)
    sub_ids = [s.subscription_id for s in subscriptions if s.subscription_id]

    if not sub_ids:
        return [], 0

    all_entries: list[dict[str, Any]] = []
    for sid in sub_ids:
        raw = query_delivery_log(
            subscription_id=sid,
            limit=10000,
            offset=0,
        )
        for entry in raw:
            all_entries.append(asdict(entry))

    all_entries.sort(key=lambda e: e.get("last_attempt", ""), reverse=True)
    total = len(all_entries)
    page = all_entries[offset : offset + limit]
    return page, total


def _list_all_products() -> list[dict[str, Any]]:
    """Return all configured products across every domain.

    Calls the MCP backend's ``_handle_list_products`` for each configured
    domain.  Returns an empty list when no domains are configured or the
    config cannot be loaded.
    """
    try:
        from autoinfo.mcp.server import _handle_list_products, _load_config

        cfg = _load_config()
    except Exception:  # pragma: no cover — defensive
        logger.debug("Could not load config for product listing", exc_info=True)
        return []

    products: list[dict[str, Any]] = []
    for domain in getattr(cfg, "domains", []) or []:
        name = getattr(domain, "name", "")
        if not name:
            continue
        result = _handle_list_products(domain=name)
        if "error_code" in result:
            continue
        for product in result.get("products", []):
            products.append(product)
    return products


def _render_error(
    request: Request, user_id: str, message: str, status_code: int = 404
) -> HTMLResponse:
    """Render the error template with navigation intact."""
    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "user_id": user_id,
            "error_message": message,
        },
        status_code=status_code,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/portal/{user_id}", response_class=HTMLResponse)
async def portal_dashboard(
    user_id: str,
    request: Request,
) -> HTMLResponse:
    """Landing page: user info, subscription status, trial info, quick stats."""
    from autoinfo.user_store import get_profile, list_subscriptions

    profile = get_profile(user_id)
    if profile is None:
        return _render_error(
            request, user_id, f"User '{user_id}' not found.", status_code=404
        )

    subscriptions = list_subscriptions(user_id=user_id)
    active_subs = [s for s in subscriptions if s.status == "active"]

    # Total deliveries across all subscriptions
    _, total_deliveries = _delivery_history(user_id, limit=1, offset=0)

    trial = _trial_info(profile)

    context = {
        "user_id": user_id,
        "profile": profile,
        "subscriptions": subscriptions,
        "active_subscriptions": active_subs,
        "active_sub_count": len(active_subs),
        "total_subscriptions": len(subscriptions),
        "total_deliveries": total_deliveries,
        "trial": trial,
    }
    return templates.TemplateResponse(request, "dashboard.html", context)


@router.get("/portal/{user_id}/preferences", response_class=HTMLResponse)
async def portal_preferences(
    user_id: str,
    request: Request,
) -> HTMLResponse:
    """Read-only delivery preferences display."""
    from autoinfo.user_store import get_profile

    profile = get_profile(user_id)
    if profile is None:
        return _render_error(
            request, user_id, f"User '{user_id}' not found.", status_code=404
        )

    # delivery_preferences is the canonical model field name
    prefs = profile.delivery_preferences or {}

    context = {
        "user_id": user_id,
        "profile": profile,
        "preferences": prefs,
        "preferences_items": list(prefs.items()),
    }
    return templates.TemplateResponse(request, "preferences.html", context)


@router.get("/portal/{user_id}/history", response_class=HTMLResponse)
async def portal_history(
    user_id: str,
    request: Request,
    limit: int = Query(
        _DEFAULT_PAGE_SIZE, ge=1, le=200, description="Page size"
    ),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> HTMLResponse:
    """Paginated delivery log table."""
    from autoinfo.user_store import get_profile

    profile = get_profile(user_id)
    if profile is None:
        return _render_error(
            request, user_id, f"User '{user_id}' not found.", status_code=404
        )

    entries, total = _delivery_history(user_id, limit=limit, offset=offset)

    # Pagination controls
    has_prev = offset > 0
    has_next = offset + limit < total
    prev_offset = max(0, offset - limit)
    next_offset = offset + limit

    # Showing X-Y of Z
    showing_from = offset + 1 if total > 0 else 0
    showing_to = min(offset + limit, total)

    context = {
        "user_id": user_id,
        "profile": profile,
        "entries": entries,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_prev": has_prev,
        "has_next": has_next,
        "prev_offset": prev_offset,
        "next_offset": next_offset,
        "showing_from": showing_from,
        "showing_to": showing_to,
    }
    return templates.TemplateResponse(request, "history.html", context)


@router.get("/portal/{user_id}/products", response_class=HTMLResponse)
async def portal_products(
    user_id: str,
    request: Request,
) -> HTMLResponse:
    """List of delivered products (derived from domain config)."""
    from autoinfo.user_store import get_profile

    profile = get_profile(user_id)
    if profile is None:
        return _render_error(
            request, user_id, f"User '{user_id}' not found.", status_code=404
        )

    products = _list_all_products()

    context = {
        "user_id": user_id,
        "profile": profile,
        "products": products,
        "product_count": len(products),
    }
    return templates.TemplateResponse(request, "products.html", context)