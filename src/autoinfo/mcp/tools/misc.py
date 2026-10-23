"""MCP tool schemas — Cache, channel health, callbacks, validation (12 tools).

Phase 1 of #581: schemas extracted from ``mcp/server.py::_full_tool_list``
verbatim.  ``build_tools()`` returns FRESH ``Tool`` objects on every call,
so ``_decorate_tools`` mutation never leaks across calls.
"""

from __future__ import annotations

from mcp.types import Tool


def build_tools() -> list[Tool]:
    """Return the 12 schemas for this module, in registration order."""
    return [
        # -- Clean Cache (1) -------------------------------------------------
        Tool(
            name="clean_cache",
            description=(
                "Remove cached artifacts and temporary files. "
                "Supports selective cleanup (collections, outputs) or "
                "--everything mode. dry_run shows what would be deleted "
                "without actually deleting."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "collections": {
                        "type": "boolean",
                        "description": "Remove cached collections/ contents",
                        "default": False,
                    },
                    "outputs": {
                        "type": "boolean",
                        "description": "Remove outputs/ contents",
                        "default": False,
                    },
                    "everything": {
                        "type": "boolean",
                        "description": "Remove ALL cached data (collections + outputs + knowledge + DB)",
                        "default": False,
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "Show what would be deleted without deleting",
                        "default": False,
                    },
                    "confirm": {
                        "type": "boolean",
                        "description": "Required. Must be True when everything=True — this deletes the entire knowledge/ directory and database",
                    },
                    "actor": {
                        "type": "string",
                        "description": "Required. Actor requesting this destructive operation (must be passed explicitly)",
                    },
                },
                "required": ["actor", "confirm"],
            },
        ),
        # -- Channel Health (1) ----------------------------------------------
        Tool(
            name="get_channel_health",
            description=(
                "Check health of delivery channels. "
                "Return health status (healthy, latency_ms, error) for one or all channels. "
                "When channel_name is omitted, returns health for all 13 channels."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_name": {
                        "type": "string",
                        "description": (
                            "Specific channel to check: smtp, webhook, rest_api, "
                            "file_export, discord, telegram, wechat_work, "
                            "wechat_oa, dingtalk, feishu, rss, social_publish, or "
                            "push. When omitted, all 13 channels are checked."
                        ),
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
                "required": [],
            },
        ),
        # -- Agent Callbacks (3) ---------------------------------------------
        Tool(
            name="set_agent_callback",
            description=(
                "Register an agent callback URL for push events "
                "(new_digest, new_report, new_tutorial, source_requires_key). "
                "Returns a callback_id for later removal. "
                "NOT shared with set_domain_webhooks — this is a separate system."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "agent_url": {
                        "type": "string",
                        "description": "Callback URL (must start with http:// or https://)",
                    },
                    "events": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                "new_digest",
                                "new_report",
                                "new_tutorial",
                                "source_requires_key",
                            ],
                        },
                        "description": (
                            "Events to subscribe to. Recognized events: "
                            "new_digest, new_report, new_tutorial, "
                            "source_requires_key."
                        ),
                    },
                },
                "required": ["agent_url", "events"],
            },
        ),
        Tool(
            name="list_agent_callbacks",
            description="List all registered agent callbacks with their URLs and subscribed events",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="remove_agent_callback",
            description="Remove a registered agent callback by its callback_id. Stops future push notifications to that endpoint. Use when an agent handler is retired or its URL must be rotated.",
            inputSchema={
                "type": "object",
                "properties": {
                    "callback_id": {
                        "type": "string",
                        "description": "Callback ID returned by set_agent_callback",
                    },
                },
                "required": ["callback_id"],
            },
        ),
        # -- Recommendation (1) ----------------------------------------------
        Tool(
            name="recommend_content",
            description="Return content-based recommendations for a user query. Scores existing KB entries by relevance to the query using lexical signals and returns the top matches with their scores. Use to surface curated reading lists without generating a full digest.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "User identifier",
                    },
                    "query": {
                        "type": "string",
                        "description": "Search/recommendation query",
                    },
                    "domain": {
                        "type": "string",
                        "description": "Domain filter (optional)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default 10)",
                    },
                },
                "required": ["user_id"],
            },
        ),
        # -- Simplification (1) ----------------------------------------------
        Tool(
            name="simplify_content",
            description=(
                "Simplify text content to a target CEFR reading level using LLM. "
                "Classifies original level, rewrites at target level, and verifies "
                "the result. Returns simplified text, original/simplified CEFR levels, "
                "and a verified flag. Target levels: A1, A2, B1, B2, C1."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Text content to simplify",
                    },
                    "target_level": {
                        "type": "string",
                        "description": "Target CEFR level: A1, A2, B1, B2, or C1",
                        "enum": ["A1", "A2", "B1", "B2", "C1"],
                    },
                    "language": {
                        "type": "string",
                        "description": "Language code: en, zh, or ja (default: en)",
                    },
                },
                "required": ["content", "target_level"],
            },
        ),
        # -- Validation (5) --------------------------------------------------
        Tool(
            name="list_validation_scenarios",
            description=(
                "List available Agent-native validation scenarios "
                "(MCP tool-call scenarios; SKIP when requires_env vars missing)"
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="run_validation_scenario",
            description=(
                "Execute an Agent-native validation scenario in-process: "
                "each step calls an MCP tool and asserts on the "
                "{success, data} envelope. Returns per-step passed/failed/skipped status"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "scenario": {
                        "type": "string",
                        "description": "Scenario name from list_validation_scenarios",
                    },
                    "steps": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "1-based step indices to run only a subset",
                    },
                    "save_results": {
                        "type": "boolean",
                        "description": (
                            "Persist this run's result to validation-runs/<date>/"
                            " (scenarios.json + latest.txt) for cross-run regression"
                        ),
                    },
                    "timeout": {
                        "type": "number",
                        "default": 180.0,
                        "description": (
                            "Per-step timeout in seconds (default 180). "
                            "Each step may run for at most this long."
                        ),
                    },
                },
                "required": ["scenario"],
            },
        ),
        Tool(
            name="get_coverage_report",
            description=(
                "Classify every stage×user cell (7 pipeline stages A1-A7 × 18 "
                "lifecycle stages = 126) plus the 72 founder expectations "
                "F01-F72 into exactly one committed state (validated / "
                "implemented-unvalidated / out-of-scope / blocked-with-record / "
                "documented-limit), with zero-unclassified enforcement. Use to "
                "audit coverage gaps and reconcile the 18-stage spine against "
                "the live scenario tags and disposition tables."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="run_all_validation_scenarios",
            description=(
                "Run the full live validation scenario library as one suite: "
                "executes every scenario once through the real engine, persists "
                "a single aggregate run (validation-runs/<run>/scenarios.json "
                "with a scenarios[] array holding every per-scenario result), "
                "and returns aggregate passed/failed/unconfigured counts plus "
                "the saved run path. Use to feed scripts/validation_report.py "
                "from one run instead of collecting per-scenario runs."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "save_results": {
                        "type": "boolean",
                        "default": True,
                        "description": (
                            "Persist the aggregate run to validation-runs/<date>/ "
                            "(scenarios.json + latest.txt) so the report consumes "
                            "all scenarios from one run."
                        ),
                    },
                    "timeout": {
                        "type": "number",
                        "default": 180.0,
                        "description": (
                            "Fallback per-step timeout in seconds (default 180) "
                            "applied to every scenario step."
                        ),
                    },
                },
            },
        ),
        Tool(
            name="get_run_decisions",
            description=(
                "Return the structured decision trail for one run/session "
                "correlation id: every scenario verdict, every step decision in "
                "execution order, and the anomaly list (failures, timeouts, "
                "unconfigured/recovered steps, warnings) as machine-readable "
                "JSON. Reads the persisted report written by "
                "run_validation_scenario(save_results=true) or "
                "run_all_validation_scenarios(), with a fallback scan of saved "
                "runs. Use to reconstruct what ran and why a verdict was reached "
                "across the A1-A7 pipeline without re-running anything."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": (
                            "Session/action correlation id returned as "
                            "session_id by run_validation_scenario or "
                            "run_all_validation_scenarios."
                        ),
                    },
                },
                "required": ["session_id"],
            },
        ),
    ]
