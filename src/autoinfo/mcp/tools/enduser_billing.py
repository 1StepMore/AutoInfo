"""MCP tool schemas — Portal, delivery logs, trials, billing (19 tools).

Phase 1 of #581: schemas extracted from ``mcp/server.py::_full_tool_list``
verbatim.  ``build_tools()`` returns FRESH ``Tool`` objects on every call,
so ``_decorate_tools`` mutation never leaks across calls.
"""

from __future__ import annotations

from mcp.types import Tool


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
