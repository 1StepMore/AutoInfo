"""MCP tool schemas — End-user delivery, alerts, budget, cost (8 tools).

Phase 1 of #581: schemas extracted from ``mcp/server.py::_full_tool_list``
verbatim.  ``build_tools()`` returns FRESH ``Tool`` objects on every call,
so ``_decorate_tools`` mutation never leaks across calls.
"""

from __future__ import annotations

from mcp.types import Tool


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
