"""MCP tool schemas — Cache, channel health, callbacks, validation (12 tools).

Phase 1 of #581: schemas extracted from ``mcp/server.py::_full_tool_list``
verbatim.  ``build_tools()`` returns FRESH ``Tool`` objects on every call,
so ``_decorate_tools`` mutation never leaks across calls.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from mcp.types import Tool

from autoinfo.mcp import context as mcp_context
from autoinfo.mcp.errors import ErrorCode, error_response, success_response


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


def _handle_clean_cache(
    collections: bool = False,
    outputs: bool = False,
    everything: bool = False,
    dry_run: bool = False,
    confirm: bool = False,
    actor: str = "agent",
) -> dict[str, Any]:
    """Remove cached artifacts and temporary files.

    Parameters
    ----------
    collections:
        Remove cached collections/ contents.
    outputs:
        Remove outputs/ contents.
    everything:
        Remove ALL cached data (collections + outputs + knowledge + DB).
    dry_run:
        Show what would be deleted without deleting (default False).

    Returns
    -------
    dict
        ``{items_removed, dry_run, targets}``.
    """
    if everything and not confirm and not dry_run:
        return error_response(
            code=ErrorCode.CONFIRMATION_REQUIRED,
            message="clean_cache(everything=True) requires confirm=true — this deletes the entire knowledge/ directory and database",
            actionable=True,
        )
    import shutil

    targets: list[str] = []
    total = 0

    if collections or everything:
        path = Path("collections")
        if path.is_dir():
            if dry_run:
                cnt = sum(1 for _ in path.iterdir())
            else:
                cnt = 0
                for child in path.iterdir():
                    if child.is_dir():
                        shutil.rmtree(child)
                    else:
                        child.unlink()
                    cnt += 1
            total += cnt
            targets.append(f"collections ({cnt} items)")
    if outputs or everything:
        path = Path("outputs")
        if path.is_dir():
            if dry_run:
                cnt = sum(1 for _ in path.iterdir())
            else:
                cnt = 0
                for child in path.iterdir():
                    if child.is_dir():
                        shutil.rmtree(child)
                    else:
                        child.unlink()
                    cnt += 1
            total += cnt
            targets.append(f"outputs ({cnt} items)")
    if everything:
        path = Path("knowledge")
        if path.is_dir():
            if dry_run:
                cnt = sum(1 for _ in path.iterdir())
            else:
                cnt = 0
                for child in path.iterdir():
                    if child.is_dir():
                        shutil.rmtree(child)
                    else:
                        child.unlink()
                    cnt += 1
            total += cnt
            targets.append(f"knowledge ({cnt} items)")

        db_path = Path("autoinfo.db")
        if db_path.is_file():
            if not dry_run:
                db_path.unlink()
            total += 1
            targets.append("autoinfo.db")

    return {
        "items_removed": total,
        "dry_run": dry_run,
        "targets": targets,
    }


def _handle_get_channel_health(
    channel_name: str | None = None,
) -> list[dict[str, Any]]:
    """Return health status for all or a specific delivery channel."""
    from autoinfo.delivery import _CHANNEL_REGISTRY

    results: list[dict[str, Any]] = []
    if channel_name is not None:
        channel_cls = _CHANNEL_REGISTRY.get(channel_name)
        if channel_cls is None:
            return [
                {
                    "healthy": False,
                    "latency_ms": 0.0,
                    "error": f"unknown channel: {channel_name}",
                    "channel": channel_name,
                }
            ]
        instance = channel_cls()
        results.append(instance.health_check())
    else:
        for name, channel_cls in _CHANNEL_REGISTRY.items():
            try:
                instance = channel_cls()
                results.append(instance.health_check())
            except Exception as exc:
                results.append(
                    {"healthy": False, "latency_ms": 0.0, "error": str(exc), "channel": name}
                )
    return mcp_context._canonicalize(results)


def _handle_set_agent_callback(
    agent_url: str,
    events: list[str],
) -> dict[str, Any]:
    """Register a new agent callback URL for specified events."""
    from autoinfo.agent_callback import register_agent_callback

    try:
        callback_id = register_agent_callback(agent_url=agent_url, events=events)
        return {
            "callback_id": callback_id,
            "agent_url": agent_url,
            "events": events,
            "created": True,
        }
    except ValueError as exc:
        return mcp_context._error_from_exc(
            exc, "set_agent_callback failed", code=ErrorCode.VALIDATION_ERROR
        )
    except Exception as exc:
        mcp_context.logger.exception("set_agent_callback failed")
        return mcp_context._error_from_exc(exc, "set_agent_callback failed")


def _handle_list_agent_callbacks() -> dict[str, Any] | list[dict[str, Any]]:
    """List all registered agent callbacks."""
    from autoinfo.agent_callback import list_agent_callbacks

    try:
        return mcp_context._canonicalize(list_agent_callbacks())
    except Exception as exc:
        mcp_context.logger.exception("list_agent_callbacks failed")
        return mcp_context._error_from_exc(exc, "list_agent_callbacks failed")


def _handle_remove_agent_callback(callback_id: str) -> dict[str, Any]:
    """Remove a registered agent callback."""
    from autoinfo.agent_callback import remove_agent_callback

    try:
        removed = remove_agent_callback(callback_id)
        if removed:
            return {"callback_id": callback_id, "removed": True}
        return error_response(
            code=ErrorCode.NOT_FOUND,
            message=f"Callback '{callback_id}' not found",
            actionable=True,
        )
    except Exception as exc:
        mcp_context.logger.exception("remove_agent_callback failed")
        return mcp_context._error_from_exc(exc, "remove_agent_callback failed")


def _handle_recommend_content(
    user_id: str,
    query: str = "",
    domain: str = "",
    limit: int = 10,
) -> dict[str, Any]:
    """Handle recommend_content MCP tool."""
    try:
        from autoinfo.recommend import ContentBasedEngine

        engine = ContentBasedEngine()
        items = engine.recommend(
            user_id=user_id,
            query=query,
            domain=domain or None,
            limit=limit,
        )
        return {
            "user_id": user_id,
            "query": query,
            "items": [
                {
                    "entry_id": item.entry_id,
                    "title": item.title,
                    "score": item.score,
                    "reason": item.reason,
                    "source_url": item.source_url,
                    "domain": item.domain,
                }
                for item in items
            ],
            "count": len(items),
        }
    except Exception as exc:
        mcp_context.logger.error("recommend_content failed: %s", exc)
        return mcp_context._error_from_exc(exc, "recommend_content failed")


def _handle_simplify_content(
    content: str,
    target_level: str,
    language: str = "en",
) -> dict[str, Any]:
    """Handle simplify_content MCP tool."""
    from autoinfo.output import simplify_text

    result = simplify_text(content, target_level, language)

    if target_level not in (frozenset({"A1", "A2", "B1", "B2", "C1"})):
        return error_response(
            code=ErrorCode.VALIDATION_ERROR,
            message=(f"Invalid target_level: '{target_level}'. Must be one of A1, A2, B1, B2, C1."),
            actionable=True,
        )

    error_msg = result.get("error")
    if error_msg and not result["verified"]:
        return success_response({**result, "warning": error_msg})

    return success_response(result)


def _handle_list_validation_scenarios() -> dict[str, Any]:
    """Handle list_validation_scenarios MCP tool."""
    from autoinfo.mcp.validation import list_scenarios

    return mcp_context._canonicalize(list_scenarios())


async def _handle_run_validation_scenario(
    scenario: str,
    steps: list[int] | None = None,
    save_results: bool = False,
    timeout: float = 180.0,
) -> dict[str, Any]:
    """Handle run_validation_scenario MCP tool."""
    from autoinfo.mcp.validation import run_scenario, save_scenario_results

    async def _validation_dispatch(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        from autoinfo.mcp.server import call_tool

        texts = await call_tool(name, arguments)
        return cast(dict[str, Any], json.loads(texts[0][0].text))

    try:
        result = await run_scenario(
            scenario,
            dispatch=_validation_dispatch,
            steps=steps,
            timeout=timeout,
        )
        if save_results:
            from autoinfo.output.run_report import (
                build_run_report,
                persist_run_report,
            )

            # ``or ""`` keeps this a ``str``: both consumers only test truthiness
            # (``save_scenario_results`` skips a falsy id; ``build_run_report``
            # raises on one), so an absent id behaved as "" already.
            session_id = result.get("session_id") or result.get("trace_id") or ""
            run_dir = save_scenario_results([result], session_id=session_id)
            result["saved_run"] = str(run_dir)
            report = build_run_report(session_id, [result], kind="single")
            result["report_path"] = str(persist_run_report(report))
        return result
    except ValueError as exc:
        return mcp_context._error_from_exc(
            exc,
            "run_validation_scenario failed",
            code=ErrorCode.VALIDATION_ERROR,
        )


def _handle_get_coverage_report() -> dict[str, Any]:
    """Handle get_coverage_report MCP tool (register T-A-02/T-A-03/T-A-07).

    Delegates to ``scripts/stage_user_coverage.py::build_report`` so the MCP
    surface and the CLI report are the same classification (one source of
    truth).  The script reads live scenario tags, the Todo 23 disposition
    tables and the catalog matrix at call time — no cached classification.
    """
    import importlib.util
    from pathlib import Path

    root = Path(__file__).resolve().parents[4]
    script = root / "scripts" / "stage_user_coverage.py"
    try:
        spec = importlib.util.spec_from_file_location("_autoinfo_stage_user_coverage", script)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load coverage script at {script}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # The script is loaded dynamically, so its ``build_report`` return
        # type is invisible to mypy; the report is a plain JSON-able dict.
        report: dict[str, Any] = module.build_report(root=root)
        return mcp_context._canonicalize(report)
    except Exception as exc:  # noqa: BLE001 - surface a typed error, never a silent pass
        return mcp_context._error_from_exc(
            exc,
            "get_coverage_report failed",
            code=ErrorCode.VALIDATION_ERROR,
        )


async def _handle_run_all_validation_scenarios(
    save_results: bool = True,
    timeout: float = 180.0,
) -> dict[str, Any]:
    """Handle run_all_validation_scenarios MCP tool (R-S-05).

    Runs the full live scenario library once and persists a single aggregate
    run (``run_type="suite"``) whose ``scenarios[]`` array carries every
    per-scenario result, so ``scripts/validation_report.py`` renders the whole
    suite from one run without external aggregation scripting.
    """
    from autoinfo.mcp.validation import run_all_scenarios

    async def _validation_dispatch(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        from autoinfo.mcp.server import call_tool

        texts = await call_tool(name, arguments)
        return cast(dict[str, Any], json.loads(texts[0][0].text))

    try:
        return await run_all_scenarios(
            dispatch=_validation_dispatch,
            timeout=timeout,
            save=save_results,
        )
    except Exception as exc:  # noqa: BLE001 - typed envelope, never a silent pass
        return mcp_context._error_from_exc(
            exc,
            "run_all_validation_scenarios failed",
            code=ErrorCode.VALIDATION_ERROR,
        )


def _handle_get_run_decisions(session_id: str) -> dict[str, Any]:
    """Handle get_run_decisions MCP tool (TR-A-01/TR-A-02, B2.6/F69).

    Return the structured decision trail for one run/session correlation id:
    every scenario verdict, every step decision in execution order, and the
    anomaly list (failures, timeouts, unconfigured/recovered steps, warnings).
    Reads the persisted report under ``validation-runs/sessions/<id>.json``;
    when no separate report exists it falls back to scanning saved runs, so an
    already-persisted run is still queryable.  Use after
    ``run_validation_scenario(save_results=true)`` or
    ``run_all_validation_scenarios()`` to reconstruct what happened without
    re-running anything.
    """
    from autoinfo.output.run_report import load_run_report

    report = load_run_report(session_id)
    if report is None:
        return error_response(
            code=ErrorCode.NOT_FOUND,
            message=(
                f"No run report found for session_id '{session_id}'. Run "
                "run_validation_scenario(save_results=true) or "
                "run_all_validation_scenarios() first, then query the "
                "returned session_id."
            ),
            actionable=True,
        )
    return success_response(report)
