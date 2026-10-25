"""MCP tool schemas — Schedules + delivery schedules (8 tools).

Phase 1 of #581: schemas extracted from ``mcp/server.py::_full_tool_list``
verbatim.  ``build_tools()`` returns FRESH ``Tool`` objects on every call,
so ``_decorate_tools`` mutation never leaks across calls.
"""

from __future__ import annotations

from typing import Any

from mcp.types import Tool

from autoinfo.mcp import context as mcp_context
from autoinfo.mcp.errors import ErrorCode, error_response


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


def _handle_list_schedules() -> dict[str, Any]:
    """List all configured schedules."""
    try:
        from autoinfo.cli.cron import load_schedules

        schedules = load_schedules()
        items = []
        for name, s in schedules.items():
            items.append(
                {
                    "name": name,
                    "expression": s.expression,
                    "domain": s.domain,
                    "enabled": s.enabled,
                    "last_run": s.last_run,
                    "created_at": s.created_at,
                }
            )
        return {"schedules": items, "count": len(items)}
    except Exception as exc:
        return mcp_context._error_from_exc(exc, "Failed to list schedules")


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
            return error_response(
                code=ErrorCode.VALIDATION_ERROR,
                message=f"Invalid schedule type '{schedule_type}'. Must be 'collection' or 'digest'.",
                actionable=True,
            )

        if schedule_type == "digest":
            if not recipients:
                return error_response(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Recipients are required for digest-type schedules. Provide the recipients list (e.g. email addresses).",
                    actionable=True,
                )
            try:
                config = mcp_context._load_config()
            except Exception as exc:
                return mcp_context._error_from_exc(exc, "Failed to load the project configuration")
            if not config.email.enabled:
                return error_response(
                    code=ErrorCode.EMAIL_NOT_ENABLED,
                    message="Email delivery is not enabled. Digest schedules require email to be configured. Set 'email.enabled: true' in .autoinfo/config.yaml and configure email.smtp_host, email.from_addr, and email.to_addrs.",
                    actionable=True,
                )

        from croniter import croniter

        if not croniter.is_valid(expression):
            return error_response(
                code=ErrorCode.INVALID_CRON_EXPRESSION,
                message=f"'{expression}' is not a valid cron expression",
                actionable=True,
            )

        from autoinfo.cli.cron import Schedule, _now_iso, load_schedules, save_schedules

        schedules = load_schedules()
        if name in schedules:
            return error_response(
                code=ErrorCode.SCHEDULE_ALREADY_EXISTS,
                message=f"A schedule named '{name}' already exists",
                actionable=True,
            )

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
        return mcp_context._error_from_exc(exc, "Failed to add schedule")


def _handle_remove_schedule(
    name: str, confirm: bool = False, actor: str = "agent"
) -> dict[str, Any]:
    """Remove a collection schedule."""
    if not confirm:
        return error_response(
            code=ErrorCode.CONFIRMATION_REQUIRED,
            message="This operation is destructive and requires confirmation. Pass confirm=True to proceed.",
            actionable=True,
        )
    try:
        from autoinfo.cli.cron import load_schedules, save_schedules

        schedules = load_schedules()
        if name not in schedules:
            return error_response(
                code=ErrorCode.SCHEDULE_NOT_FOUND,
                message=f"Schedule '{name}' not found",
                actionable=True,
            )
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
        return mcp_context._error_from_exc(exc, "Failed to remove schedule")


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
        return mcp_context._error_from_exc(exc, "Failed to run schedules")


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
        return mcp_context._error_from_exc(exc, "Failed to get schedule status")


def _handle_add_delivery_schedule(
    domain: str,
    cron_expression: str,
    output_type: str = "digest",
    channel: str = "email",
    recipients: list[str] | None = None,
    output_format: str = "html",
    period: str = "weekly",
    user_id: str = "",
) -> dict[str, Any]:
    """Add a new delivery schedule for periodic output generation + delivery.

    Parameters
    ----------
    domain:
        Domain to generate output for.
    cron_expression:
        Cron expression (e.g. ``"0 8 * * 1"`` for Monday 8 AM).
    output_type:
        Output type: ``"digest"`` or ``"report"``.
    channel:
        Delivery channel name (e.g. ``"email"``, ``"webhook"``).
    recipients:
        Recipient identifiers (emails, webhook URLs, …).
    output_format:
        Output format: ``"markdown"``, ``"html"``, ``"json"``, ``"agent"``,
        ``"audio"``, ``"pdf"``.
    period:
        Content period: ``"daily"``, ``"weekly"``, ``"monthly"``.
    user_id:
        Optional end-user ID whose stored ``content_preference`` is
        applied when the scheduled output is generated.  Empty by
        default (no preference lookup).
    """
    try:
        from autoinfo.delivery.scheduler import (
            VALID_CHANNELS,
            VALID_FORMATS,
            VALID_OUTPUT_TYPES,
            DeliverySchedule,
            DeliveryScheduler,
        )

        if output_type not in VALID_OUTPUT_TYPES:
            return error_response(
                code=ErrorCode.VALIDATION_ERROR,
                message=f"Invalid output_type '{output_type}'. Must be one of: {', '.join(sorted(VALID_OUTPUT_TYPES))}",
                actionable=True,
            )
        if output_format not in VALID_FORMATS:
            return error_response(
                code=ErrorCode.VALIDATION_ERROR,
                message=f"Invalid format '{output_format}'. Must be one of: {', '.join(sorted(VALID_FORMATS))}",
                actionable=True,
            )
        if channel not in VALID_CHANNELS:
            return error_response(
                code=ErrorCode.VALIDATION_ERROR,
                message=f"Invalid channel '{channel}'. Must be one of: {', '.join(sorted(VALID_CHANNELS))}",
                actionable=True,
            )

        from croniter import croniter

        if not croniter.is_valid(cron_expression):
            return error_response(
                code=ErrorCode.INVALID_CRON_EXPRESSION,
                message=f"'{cron_expression}' is not a valid cron expression",
                actionable=True,
            )

        new_schedule = DeliverySchedule(
            cron_expression=cron_expression,
            domain=domain,
            output_type=output_type,
            format=output_format,
            channel=channel,
            recipients=recipients or [],
            period=period,
            user_id=user_id,
        )
        scheduler = DeliveryScheduler()
        scheduler.add_schedule(new_schedule)

        return {
            "created": True,
            "schedule_id": new_schedule.id,
            "schedule": {
                "id": new_schedule.id,
                "cron_expression": new_schedule.cron_expression,
                "domain": new_schedule.domain,
                "output_type": new_schedule.output_type,
                "format": new_schedule.format,
                "channel": new_schedule.channel,
                "recipients": new_schedule.recipients,
                "period": new_schedule.period,
                "user_id": new_schedule.user_id,
                "enabled": new_schedule.enabled,
                "created_at": new_schedule.created_at,
            },
        }
    except Exception as exc:
        return mcp_context._error_from_exc(exc, "Failed to add delivery schedule")


def _handle_list_delivery_schedules() -> dict[str, Any]:
    """List all configured delivery schedules."""
    try:
        from dataclasses import asdict

        from autoinfo.delivery.scheduler import DeliveryScheduler

        scheduler = DeliveryScheduler()
        schedules = scheduler.list_schedules()
        items = []
        for s in schedules:
            d = asdict(s)
            items.append(d)
        return {"schedules": items, "count": len(items)}
    except Exception as exc:
        return mcp_context._error_from_exc(exc, "Failed to list delivery schedules")


def _handle_remove_delivery_schedule(
    schedule_id: str,
    confirm: bool = False,
) -> dict[str, Any]:
    """Remove a delivery schedule by ID."""
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
        from autoinfo.delivery.scheduler import DeliveryScheduler

        scheduler = DeliveryScheduler()
        removed = scheduler.remove_schedule(schedule_id)
        if not removed:
            return error_response(
                code=ErrorCode.SCHEDULE_NOT_FOUND,
                message=f"Delivery schedule '{schedule_id}' not found",
                actionable=True,
            )
        return {
            "removed": True,
            "schedule_id": schedule_id,
        }
    except Exception as exc:
        return mcp_context._error_from_exc(exc, "Failed to remove delivery schedule")
