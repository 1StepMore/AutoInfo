"""MCP tool schemas — Portal, delivery logs, trials, billing (19 tools).

Phase 1 of #581: schemas extracted from ``mcp/server.py::_full_tool_list``
verbatim.  ``build_tools()`` returns FRESH ``Tool`` objects on every call,
so ``_decorate_tools`` mutation never leaks across calls.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from mcp.types import Tool

from autoinfo.mcp import context as mcp_context
from autoinfo.mcp.errors import ErrorCode, error_response, success_response


def build_tools() -> list[Tool]:
    """Return the 19 schemas for this module, in registration order."""
    return [
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
                        "enum": ["success", "failed", "retrying", "pending", "in_progress"],
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
        # -- Delivery Monitor (2) --------------------------------------------
        Tool(
            name="list_active_deliveries",
            description="List all active/in-progress deliveries (status: retrying, pending, in_progress). Use to monitor the delivery pipeline and spot stuck items before they violate SLA; pairs with the delivery log tools for a full picture.",
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
                        "enum": ["success", "failed", "retrying", "pending", "in_progress"],
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
        # -- End-User Trial (2) ----------------------------------------------
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
        # -- End-User Preferences (2) ----------------------------------------
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
        # -- End-User CRUD (5) -----------------------------------------------
        Tool(
            name="enduser_create",
            description="Create a new end-user profile. Requires user_id and name. Optional: email, delivery_prefs (JSON dict), status (trial/active/suspended/cancelled), tier (free/pro/enterprise).",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "Unique user identifier (e.g. alice)",
                    },
                    "name": {
                        "type": "string",
                        "description": "User display name",
                    },
                    "email": {
                        "type": "string",
                        "description": "Email address",
                        "default": "",
                    },
                    "delivery_prefs": {
                        "type": "object",
                        "description": "Delivery preferences as a JSON object (e.g. {channel: email})",
                    },
                    "status": {
                        "type": "string",
                        "description": "Account status (trial/active/suspended/cancelled)",
                        "default": "trial",
                        "enum": ["trial", "active", "suspended", "cancelled"],
                    },
                    "tier": {
                        "type": "string",
                        "description": "Account tier (free/pro/enterprise)",
                        "default": "free",
                        "enum": ["free", "premium", "enterprise"],
                    },
                },
                "required": ["user_id", "name"],
            },
        ),
        Tool(
            name="enduser_get",
            description="Get an end-user profile by user ID. Returns the full profile dict or an error if not found.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "User identifier to look up (e.g. alice)",
                    },
                },
                "required": ["user_id"],
            },
        ),
        Tool(
            name="enduser_update",
            description="Update an end-user profile (partial update). Only provided fields are changed. Returns the updated profile.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "User identifier to update (e.g. alice)",
                    },
                    "name": {
                        "type": "string",
                        "description": "New display name (optional)",
                    },
                    "email": {
                        "type": "string",
                        "description": "New email address (optional)",
                    },
                    "delivery_prefs": {
                        "type": "object",
                        "description": "New delivery preferences JSON object (optional)",
                    },
                    "status": {
                        "type": "string",
                        "description": "New account status (optional)",
                        "enum": ["trial", "active", "suspended", "cancelled"],
                    },
                    "tier": {
                        "type": "string",
                        "description": "New account tier (optional)",
                        "enum": ["free", "premium", "enterprise"],
                    },
                },
                "required": ["user_id"],
            },
        ),
        Tool(
            name="enduser_delete",
            description="Delete an end-user profile and associated subscriptions. Returns success or not-found error.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "User identifier to delete (e.g. alice)",
                    },
                },
                "required": ["user_id"],
            },
        ),
        Tool(
            name="enduser_list",
            description="List all end-user profiles. Returns an items array with each profile's user_id, name, email, status, tier, and subscription count plus a total count. Use to browse the user directory before targeting a delivery.",
            inputSchema={"type": "object", "properties": {}},
        ),
        # -- Stripe Billing (3) ----------------------------------------------
        Tool(
            name="create_checkout_session",
            description="Create a Stripe Checkout Session for a product (subscription or one-time payment). Creates (or looks up) a Stripe Customer for the end-user and generates a checkout URL. Works with stripe-mock (localhost:12111) or live/test Stripe keys via STRIPE_API_KEY env var.",
            inputSchema={
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "string",
                        "description": "Stripe Price ID (e.g. price_xxx for subscriptions; name for payment mode)",
                    },
                    "end_user_id": {
                        "type": "string",
                        "description": "AutoInfo end-user ID (e.g. alice)",
                    },
                    "mode": {
                        "type": "string",
                        "description": "Checkout mode: 'subscription' (default) or 'payment' (one-time purchase)",
                        "default": "subscription",
                        "enum": ["subscription", "payment"],
                    },
                    "article_id": {
                        "type": "string",
                        "description": "Article identifier for single-purchase metadata (payment mode only)",
                        "default": "",
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
                        "description": 'AutoInfo end-user ID (e.g. alice). Optional — defaults to config multi_user.default_user_id, then "default".',
                        "default": "",
                    },
                },
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
                        "description": 'AutoInfo end-user ID (e.g. alice). Optional — defaults to config multi_user.default_user_id, then "default".',
                        "default": "",
                    },
                    "period": {
                        "type": "string",
                        "description": "Time period: today, week, month, all (default: month)",
                        "default": "month",
                        "enum": ["today", "week", "month", "all"],
                    },
                },
            },
        ),
        # -- End-user Usage & Invoice (2) ------------------------------------
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
                        "enum": ["today", "week", "month", "all"],
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
                        "enum": ["today", "week", "month", "all"],
                    },
                },
                "required": ["end_user_id"],
            },
        ),
    ]


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
        return error_response(
            code=ErrorCode.NOT_FOUND,
            message=f"End-user '{end_user_id}' not found",
            actionable=True,
        )

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
            all_entries.append(asdict(entry))

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
        return error_response(
            code=ErrorCode.NOT_FOUND,
            message=f"End-user '{end_user_id}' not found",
            actionable=True,
        )

    subscriptions = list_subscriptions(user_id=end_user_id)
    products: list[dict[str, Any]] = []
    for sub in subscriptions:
        products.append(
            {
                "subscription_id": getattr(sub, "subscription_id", getattr(sub, "sub_id", "")),
                "user_id": sub.user_id,
                "plan": getattr(sub, "plan", getattr(sub, "product_id", "")),
                "status": sub.status,
                "start_date": sub.start_date,
                "end_date": sub.end_date,
                "auto_renew": sub.auto_renew,
            }
        )

    return {
        "end_user_id": end_user_id,
        "products": products,
        "count": len(products),
    }


def _handle_query_delivery_log(
    name: str, arguments: dict[str, Any]
) -> dict[str, Any] | list[dict[str, Any]]:
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
        mcp_context.logger.exception("list_active_deliveries failed")
        return mcp_context._error_from_exc(exc, "list_active_deliveries failed")


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
        mcp_context.logger.exception("get_delivery_log failed")
        return mcp_context._error_from_exc(exc, "get_delivery_log failed")


def _handle_activate_trial(
    end_user_id: str,
    days: int = 14,
) -> dict[str, Any]:
    """Activate or reset the trial period for an end-user."""
    from autoinfo.user_store import activate_trial

    try:
        return mcp_context._canonicalize(activate_trial(end_user_id=end_user_id, days=days))
    except Exception as exc:
        mcp_context.logger.exception("activate_trial failed for '%s'", end_user_id)
        return mcp_context._error_from_exc(exc, "activate_trial failed")


def _handle_check_trial_expiry(end_user_id: str) -> dict[str, Any]:
    """Check trial expiry status for an end-user."""
    from autoinfo.user_store import check_trial_expiry

    try:
        return mcp_context._canonicalize(check_trial_expiry(end_user_id=end_user_id))
    except Exception as exc:
        mcp_context.logger.exception("check_trial_expiry failed for '%s'", end_user_id)
        return mcp_context._error_from_exc(exc, "check_trial_expiry failed")


def _handle_update_preferences(
    end_user_id: str,
    preferences: dict[str, Any],
) -> dict[str, Any]:
    """Merge preferences into stored preferences for an end-user."""
    from autoinfo.user_store import (  # noqa: PLC0415
        CONTENT_PREFERENCE_VALUES,
        update_preferences,
    )

    if "content_preference" in preferences:
        cp = preferences["content_preference"]
        if cp not in CONTENT_PREFERENCE_VALUES:
            return error_response(
                code=ErrorCode.VALIDATION_ERROR,
                message=(
                    f"Invalid content_preference '{cp}'. "
                    f"Must be one of: {', '.join(sorted(CONTENT_PREFERENCE_VALUES))}"
                ),
                actionable=True,
            )

    try:
        return mcp_context._canonicalize(
            update_preferences(end_user_id=end_user_id, preferences=preferences)
        )
    except Exception as exc:
        mcp_context.logger.exception("update_preferences failed for '%s'", end_user_id)
        return mcp_context._error_from_exc(exc, "update_preferences failed")


def _handle_get_preferences(end_user_id: str) -> dict[str, Any]:
    """Return stored preferences for an end-user."""
    from autoinfo.user_store import get_preferences

    try:
        return mcp_context._canonicalize(get_preferences(end_user_id=end_user_id))
    except Exception as exc:
        mcp_context.logger.exception("get_preferences failed for '%s'", end_user_id)
        return mcp_context._error_from_exc(exc, "get_preferences failed")


def _handle_enduser_create(
    user_id: str,
    name: str,
    email: str = "",
    delivery_prefs: dict[str, Any] | None = None,
    status: str = "trial",
    tier: str = "free",
) -> dict[str, Any]:
    """Create a new end-user profile (mirrors ``autoinfo enduser create``)."""
    from dataclasses import asdict as _asdict

    from autoinfo.user_store import create_profile

    try:
        profile = create_profile(
            user_id=user_id,
            name=name,
            email=email,
            delivery_prefs=delivery_prefs or {},
            status=status,
            tier=tier,
        )
    except Exception as exc:
        mcp_context.logger.exception("enduser_create failed for '%s'", user_id)
        return mcp_context._error_from_exc(exc, "enduser_create failed")

    return success_response(_asdict(profile))


def _handle_enduser_get(user_id: str) -> dict[str, Any]:
    """Get an end-user profile by user ID (mirrors ``autoinfo enduser get``)."""
    from dataclasses import asdict as _asdict

    from autoinfo.user_store import get_profile

    try:
        profile = get_profile(user_id)
    except Exception as exc:
        mcp_context.logger.exception("enduser_get failed for '%s'", user_id)
        return mcp_context._error_from_exc(exc, "enduser_get failed")

    if profile is None:
        return error_response(
            code=ErrorCode.NOT_FOUND,
            message=f"End-user '{user_id}' not found",
            actionable=True,
        )

    return success_response(_asdict(profile))


def _handle_enduser_update(
    user_id: str,
    name: str | None = None,
    email: str | None = None,
    delivery_prefs: dict[str, Any] | None = None,
    status: str | None = None,
    tier: str | None = None,
) -> dict[str, Any]:
    """Update an end-user profile (partial update, mirrors ``autoinfo enduser update``)."""
    from dataclasses import asdict as _asdict

    from autoinfo.user_store import update_profile

    try:
        profile = update_profile(
            user_id=user_id,
            name=name,
            email=email,
            delivery_prefs=delivery_prefs,
            status=status,
            tier=tier,
        )
    except Exception as exc:
        mcp_context.logger.exception("enduser_update failed for '%s'", user_id)
        return mcp_context._error_from_exc(exc, "enduser_update failed")

    if profile is None:
        return error_response(
            code=ErrorCode.NOT_FOUND,
            message=f"End-user '{user_id}' not found",
            actionable=True,
        )

    return success_response(_asdict(profile))


def _handle_enduser_delete(user_id: str) -> dict[str, Any]:
    """Delete an end-user profile and associated subscriptions (mirrors ``autoinfo enduser delete``)."""
    from autoinfo.user_store import delete_profile

    try:
        ok = delete_profile(user_id)
    except Exception as exc:
        mcp_context.logger.exception("enduser_delete failed for '%s'", user_id)
        return mcp_context._error_from_exc(exc, "enduser_delete failed")

    if not ok:
        return error_response(
            code=ErrorCode.NOT_FOUND,
            message=f"End-user '{user_id}' not found",
            actionable=True,
        )

    return success_response({"user_id": user_id, "deleted": True})


def _handle_enduser_list() -> dict[str, Any]:
    """List all end-user profiles (mirrors ``autoinfo enduser list``)."""
    from dataclasses import asdict as _asdict

    from autoinfo.user_store import list_profiles

    try:
        profiles = list_profiles()
    except Exception as exc:
        mcp_context.logger.exception("enduser_list failed")
        return mcp_context._error_from_exc(exc, "enduser_list failed")

    items = [_asdict(p) for p in profiles]
    return success_response({"items": items, "count": len(items)})


def _handle_create_checkout_session(
    product_id: str,
    end_user_id: str,
    *,
    mode: str = "subscription",
    success_url: str = "http://localhost:8741/success",
    cancel_url: str = "http://localhost:8741/cancel",
    email: str = "",
    name: str = "",
    article_id: str = "",
) -> dict[str, Any]:
    """Create a Stripe Checkout Session for a product."""
    from autoinfo.billing import create_checkout_session

    try:
        return mcp_context._canonicalize(
            create_checkout_session(
                product_id=product_id,
                end_user_id=end_user_id,
                mode=mode,
                success_url=success_url,
                cancel_url=cancel_url,
                email=email,
                name=name,
                article_id=article_id,
            )
        )
    except Exception as exc:
        mcp_context.logger.exception("create_checkout_session failed for '%s'", end_user_id)
        return mcp_context._error_from_exc(exc, "create_checkout_session failed")


def _handle_get_subscription_status(end_user_id: str = "") -> dict[str, Any]:
    """Check Stripe subscription status for an end-user."""
    from autoinfo.billing import get_subscription_status, resolve_user_id

    end_user_id = resolve_user_id(end_user_id or None)
    try:
        return mcp_context._canonicalize(get_subscription_status(end_user_id=end_user_id))
    except Exception as exc:
        mcp_context.logger.exception("get_subscription_status failed for '%s'", end_user_id)
        return mcp_context._error_from_exc(exc, "get_subscription_status failed")


def _handle_get_billing_summary(
    user_id: str = "",
    period: str = "month",
) -> dict[str, Any]:
    """Return combined billing summary — usage + subscription.

    Combines CostMeter usage data with Stripe subscription status into
    a single read-only summary.

    Parameters
    ----------
    user_id:
        AutoInfo end-user ID (e.g. ``alice``).  Optional — falls back
        to ``multi_user.default_user_id`` from config, then ``"default"``.
    period:
        Time period: ``"today"``, ``"week"``, ``"month"``, ``"all"``.
        Defaults to ``"month"``.

    Returns
    -------
    dict with keys: ``user_id``, ``period``, ``usage``, ``subscription``.
    """
    from autoinfo.billing import get_subscription_status, resolve_user_id
    from autoinfo.cost import CostMeter

    user_id = resolve_user_id(user_id or None)
    try:
        meter = CostMeter()
        usage = meter.get_enduser_usage(end_user_id=user_id, period=period)
        subscription = get_subscription_status(end_user_id=user_id)
    except Exception as exc:
        mcp_context.logger.exception("get_billing_summary failed for '%s'", user_id)
        return mcp_context._error_from_exc(exc, "get_billing_summary failed")

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
        return mcp_context._canonicalize(
            meter.get_enduser_usage(end_user_id=end_user_id, period=period)
        )
    except Exception as exc:
        mcp_context.logger.exception("get_enduser_usage failed for '%s'", end_user_id)
        return mcp_context._error_from_exc(exc, "get_enduser_usage failed")


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
        return mcp_context._canonicalize(
            meter.get_enduser_invoice(end_user_id=end_user_id, period=period)
        )
    except Exception as exc:
        mcp_context.logger.exception("get_enduser_invoice failed for '%s'", end_user_id)
        return mcp_context._error_from_exc(exc, "get_enduser_invoice failed")
