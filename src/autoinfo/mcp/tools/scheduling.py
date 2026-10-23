"""MCP tool schemas — Schedules + delivery schedules (8 tools).

Phase 1 of #581: schemas extracted from ``mcp/server.py::_full_tool_list``
verbatim.  ``build_tools()`` returns FRESH ``Tool`` objects on every call,
so ``_decorate_tools`` mutation never leaks across calls.
"""

from __future__ import annotations

from mcp.types import Tool


def build_tools() -> list[Tool]:
    """Return the 8 schemas for this module, in registration order."""
    return [
        # -- Schedule Management (5) -----------------------------------------
        Tool(
            name="list_schedules",
            description=(
                "List all scheduled collection jobs that fetch sources on a "
                "cron cadence, showing job id and enabled state. Use to "
                "review or remove collection automation."
            ),
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
                        "description": ("Cron expression (e.g. '0 2 * * *' for daily at 2 AM)"),
                    },
                    "domain": {
                        "type": "string",
                        "description": "Domain to collect or generate digest for",
                    },
                    "schedule_type": {
                        "type": "string",
                        "description": "Schedule type: collection or digest",
                        "default": "collection",
                        "enum": ["collection", "digest"],
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
                        "enum": ["html", "markdown"],
                    },
                },
                "required": ["name", "expression", "domain"],
            },
        ),
        Tool(
            name="remove_schedule",
            description="Remove a collection schedule by name. Deletes the named cron schedule so run_schedules no longer triggers it. Use to stop a recurring collection job while keeping the domain configuration intact.",
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
                    "actor": {
                        "type": "string",
                        "description": "Required. Actor requesting this destructive operation (must be passed explicitly)",
                    },
                },
                "required": ["name", "actor"],
            },
        ),
        Tool(
            name="run_schedules",
            description="Run due schedules now (checks cron expressions against last_run). Executes every collection or digest schedule whose cron window has elapsed. Use to trigger pending jobs on demand instead of waiting for the cron daemon.",
            inputSchema={
                "type": "object",
                "properties": {
                    "dry_run": {
                        "type": "boolean",
                        "description": (
                            "If true, report which schedules would run without executing"
                        ),
                        "default": False,
                    },
                    "name": {
                        "type": "string",
                        "description": (
                            "Optional single schedule name to run (runs all due if omitted)"
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
        # -- Delivery Schedule Management (3) --------------------------------
        Tool(
            name="add_delivery_schedule",
            description="Add a new delivery schedule for periodic output generation + channel delivery",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain to generate output for",
                    },
                    "cron_expression": {
                        "type": "string",
                        "description": "Cron expression (e.g. '0 8 * * 1' for Monday 8 AM)",
                    },
                    "output_type": {
                        "type": "string",
                        "description": "Output type: digest or report",
                        "default": "digest",
                        "enum": ["digest", "report"],
                    },
                    "channel": {
                        "type": "string",
                        "description": "Delivery channel: email, webhook, rest, telegram, discord, etc.",
                        "default": "email",
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
                    "recipients": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Recipient identifiers (emails, webhook URLs, etc.)",
                    },
                    "output_format": {
                        "type": "string",
                        "description": "Output format: markdown, html, json, agent, audio, pdf",
                        "default": "html",
                        "enum": ["html", "markdown"],
                    },
                    "period": {
                        "type": "string",
                        "description": "Content period: daily, weekly, monthly",
                        "default": "weekly",
                        "enum": ["daily", "weekly", "monthly"],
                    },
                    "user_id": {
                        "type": "string",
                        "description": "Optional end-user ID whose stored content_preference (raw_only / processed_only / both) is applied when generating the scheduled output. Empty = no preference lookup.",
                        "default": "",
                    },
                },
                "required": ["domain", "cron_expression"],
            },
        ),
        Tool(
            name="list_delivery_schedules",
            description=(
                "List all delivery schedules that generate and push outputs "
                "(digests, reports) to end-user channels on a cron cadence. "
                "Shows output type, channel, and next run time per schedule."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="remove_delivery_schedule",
            description="Remove a delivery schedule by ID. Cancels the recurring output generation + delivery for that schedule_id. Use when a product's cadence is retired or the recipient set changes permanently.",
            inputSchema={
                "type": "object",
                "properties": {
                    "schedule_id": {
                        "type": "string",
                        "description": "Schedule ID to remove",
                    },
                    "confirm": {
                        "type": "boolean",
                        "description": "Must be True to confirm this destructive operation",
                        "default": False,
                    },
                },
                "required": ["schedule_id"],
            },
        ),
    ]
