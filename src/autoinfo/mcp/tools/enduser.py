"""MCP tool schemas — End-user delivery, alerts, budget, cost (8 tools).

Phase 1 of #581: schemas extracted from ``mcp/server.py::_full_tool_list``
verbatim.  ``build_tools()`` returns FRESH ``Tool`` objects on every call,
so ``_decorate_tools`` mutation never leaks across calls.
"""

from __future__ import annotations

from typing import Any, Literal

from mcp.types import Tool

from autoinfo.mcp import context as mcp_context
from autoinfo.mcp.errors import ErrorCode, error_response


def build_tools() -> list[Tool]:
    """Return the 8 schemas for this module, in registration order."""
    return [
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
                        "enum": [
                            "smtp",
                            "webhook",
                            "rest_api",
                            "file_export",
                            "discord",
                            "telegram",
                            "wechat_work",
                            "wechat_oa",
                            "dingtalk",
                            "feishu",
                            "rss",
                            "social_publish",
                            "push",
                        ],
                    },
                },
                "required": ["end_user_id", "product_type", "product_id"],
            },
        ),
        # -- Alert Rules (3) -------------------------------------------------
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
            description="Create a new threshold-based alert rule for a domain. Triggers notifications when collected items match the configured keywords and relevance threshold, or when a configured source is missing its required API key (kind=source_credential_missing)",
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
                    "kind": {
                        "type": "string",
                        "description": "Rule kind: content (item matching) or source_credential_missing (fires when a configured source requires an API key absent from the operator environment)",
                        "default": "content",
                        "enum": ["content", "source_credential_missing"],
                    },
                },
                "required": ["domain"],
            },
        ),
        Tool(
            name="remove_alert_rule",
            description="Remove an alert rule by its ID. Deletes the rule returned by add_alert_rule so no further checks or dispatches fire for it. Use to clean up stale thresholds after a budget re-plan.",
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
        # -- Cost Dashboard & Allocation (2) ---------------------------------
        Tool(
            name="cost_dashboard",
            description=(
                "Show cost dashboard — totals by domain, daily trend, "
                "top models/sources, and budget status."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "description": "Time period: today, week, month, all",
                        "default": "week",
                        "enum": ["today", "week", "month", "all"],
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="cost_allocation",
            description=(
                "Show cost allocation broken down by domain and user. "
                "Supports filtering by domain, user_id, and time period."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Optional domain filter (empty = all)",
                        "default": "",
                    },
                    "user_id": {
                        "type": "string",
                        "description": "Optional user ID filter (empty = all)",
                        "default": "",
                    },
                    "period": {
                        "type": "string",
                        "description": "Time period: all, today, week, month",
                        "default": "all",
                        "enum": ["all", "today", "week", "month"],
                    },
                },
                "required": [],
            },
        ),
    ]


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
        return error_response(
            code=ErrorCode.VALIDATION_ERROR,
            message=f"End user '{end_user_id}' not found",
            actionable=True,
        )

    # --- Content-preference tier guard (B-001) -------------------------------
    # Block deliveries whose product kind conflicts with the user's stored
    # content_preference instead of silently bypassing the preference gate.
    from autoinfo.user_store import (  # noqa: PLC0415
        resolve_content_preference as _resolve_cp,
    )

    effective_preference = _resolve_cp(profile.preferences)
    product_kind = (
        product_type.lower() if product_type.lower() in ("raw", "processed") else "processed"
    )
    preference_conflict: str | None = None
    if effective_preference == "raw_only" and product_kind != "raw":
        preference_conflict = (
            f"User '{end_user_id}' has content_preference='raw_only' "
            f"(wants only 01-Raw content), but product '{product_id}' "
            f"is a '{product_kind}' product. "
            "Use update_preferences() to switch content_preference to "
            "'both' or 'processed_only', or deliver a raw product instead."
        )
    elif effective_preference == "processed_only" and product_kind != "processed":
        preference_conflict = (
            f"User '{end_user_id}' has content_preference='processed_only' "
            f"(wants only 02-Draft/03-Wiki content), but product "
            f"'{product_id}' is a '{product_kind}' product. "
            "Use update_preferences() to switch content_preference to "
            "'both' or 'raw_only', or deliver a processed product instead."
        )
    if preference_conflict is not None:
        return error_response(
            code=ErrorCode.VALIDATION_ERROR,
            message=preference_conflict,
            actionable=True,
        )

    channel_name: str = channel or profile.delivery_preferences.get("channel") or "smtp"

    domain: str = product_id
    for suffix in ("-raw", "-processed"):
        if product_id.endswith(suffix):
            domain = product_id[: -len(suffix)]
            break

    product = Product(
        id=product_id,
        domain=domain,
        type=ProductType(product_type.lower())
        if product_type.lower() in ("raw", "processed")
        else ProductType.PROCESSED,
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
        return mcp_context._error_from_exc(
            exc, "send_to_enduser failed", code=ErrorCode.VALIDATION_ERROR
        )
    except Exception as exc:
        mcp_context.logger.exception("send_to_enduser dispatch failed")
        return mcp_context._error_from_exc(exc, "send_to_enduser dispatch failed")

    return {
        "delivery_id": delivery_id,
        "status": result.status,
        "channel": channel_name,
        "recipient_count": result.recipient_count,
        "error": result.error,
    }


def _handle_get_alert_rules(domain: str) -> dict[str, Any]:
    """List alert rules for a domain."""
    from autoinfo.alerts import list_alert_rules

    try:
        rules = list_alert_rules(domain=domain)
    except Exception as exc:
        return error_response(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"Failed to list alert rules: {exc}",
            actionable=True,
        )

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
    kind: str = "content",
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
            kind=kind,
        )
    except Exception as exc:
        return error_response(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"Failed to add alert rule: {exc}",
            actionable=True,
        )

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
        return error_response(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"Failed to remove alert rule: {exc}",
            actionable=True,
        )

    if not removed:
        return error_response(
            code=ErrorCode.ALERT_RULE_NOT_FOUND,
            message=f"Alert rule '{id}' not found",
            actionable=True,
        )

    return {
        "removed": True,
        "alert_rule_id": id,
    }


def _handle_get_budget_thresholds() -> dict[str, Any]:
    """Return current budget thresholds with spend status.

    Reads ``cost_alerts.budget_thresholds`` from the project config and
    queries ``CostMeter`` for total spend, then returns each threshold
    with its comparison status.
    """
    try:
        config = mcp_context._load_config()
    except Exception as exc:
        return mcp_context._error_from_exc(exc, "Failed to load the project configuration")

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
        status.append(
            {
                "threshold": t,
                "current_spend": round(current_spend, 8),
                "pct_used": pct,
                "breached": breached,
                "severity": "critical"
                if t >= 100 and breached
                else "warning"
                if breached
                else "ok",
            }
        )

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
        config = mcp_context._load_config()
    except Exception as exc:
        return mcp_context._error_from_exc(exc, "Failed to load the project configuration")

    if not thresholds:
        return error_response(
            code=ErrorCode.INVALID_ARGUMENTS,
            message="thresholds must be a non-empty list of floats",
            actionable=True,
        )

    config.cost_alerts.budget_thresholds = [float(t) for t in thresholds]
    if auto_remediation_enabled:
        config.cost_alerts.auto_remediation_enabled = True
    if alert_webhook:
        config.cost_alerts.alert_webhook = alert_webhook

    mcp_context._save_config(config)

    return {
        "budget_thresholds": config.cost_alerts.budget_thresholds,
        "auto_remediation_enabled": config.cost_alerts.auto_remediation_enabled,
        "alert_webhook": config.cost_alerts.alert_webhook,
        "updated": True,
    }


def _handle_cost_dashboard(
    period: str = "week",
) -> dict[str, Any]:
    """Show cost dashboard — totals by domain, daily trend, top models/sources, budget status.

    Parameters
    ----------
    period:
        Time period: ``"today"``, ``"week"``, ``"month"``, ``"all"`` (default ``"week"``).

    Returns
    -------
    dict
        Cost dashboard data with ``total_cost``, ``by_domain``, ``daily_trend``,
        ``top_models``, ``top_sources``, ``budget_status``.
    """
    try:
        from autoinfo.cost import CostMeter

        meter = CostMeter()
        return mcp_context._canonicalize(meter.get_cost_dashboard(period=period))
    except Exception as exc:
        mcp_context.logger.exception("Cost dashboard failed")
        return mcp_context._error_from_exc(exc, "Cost dashboard failed")


def _handle_cost_allocation(
    domain: str = "",
    user_id: str = "",
    period: str = "all",
) -> dict[str, Any]:
    """Show cost allocation broken down by domain and user.

    Parameters
    ----------
    domain:
        Optional domain filter (empty = all).
    user_id:
        Optional user ID filter (empty = all).
    period:
        Time period: ``"all"``, ``"today"``, ``"week"``, ``"month"`` (default ``"all"``).

    Returns
    -------
    dict
        ``{period, domain_filter, user_id_filter, total_cost, log_count, by_domain, by_user}``.
    """
    try:
        from autoinfo.cost import CostMeter

        meter = CostMeter()
        return mcp_context._canonicalize(
            meter.get_cost_allocation(domain=domain, user_id=user_id, period=period)
        )
    except Exception as exc:
        mcp_context.logger.exception("Cost allocation failed")
        return mcp_context._error_from_exc(exc, "Cost allocation failed")
