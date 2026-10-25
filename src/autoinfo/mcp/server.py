"""MCP server — exposes AutoInfo capabilities as MCP tools over stdio.

This is the primary agent-facing interface for AutoInfo. It exposes 149 tools
across 35 categories — the full catalog lives in the README "MCP Tools" table
and is discoverable at runtime via ``list_tools()``.  ``get_tool_count()``
returns the live count.

Usage::

    python -m autoinfo.mcp.server

The server listens on stdio (JSON-RPC 2.0) and responds to
``CallToolRequest`` messages.  Connect with any MCP client::

    async with stdio_client(["python", "-m", "autoinfo.mcp.server"]) as (read, write):
        async with ClientSession(read, write) as session:
            result = await session.call_tool("health_check", {})
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from typing import Any, Callable, cast

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from autoinfo.kb import is_director
from autoinfo.mcp.errors import ErrorCode, error_response, success_response

# ---------------------------------------------------------------------------
# Config I/O helpers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Job state persistence (SQLite-backed, survives server restarts)
# ---------------------------------------------------------------------------

# Reuse the same autoinfo.db that KBStore uses.
# KBStore places it at ``Path("knowledge").resolve().parent / "autoinfo.db"``,
# which resolves to ``<cwd>/autoinfo.db`` when running from the project root.


# ---------------------------------------------------------------------------
# Tool implementations
#
# These are plain (sync) functions so they can be tested without an async
# test harness.  The ``call_tool`` handler wraps them in ``TextContent``.
# ---------------------------------------------------------------------------


# -- Platform metadata (static) -------------------------------------------

# Curated metadata for well-known source types; anything missing from this
# map still gets advertised via ``list_available_platforms`` with a default
# entry so PLATFORMS always mirrors VALID_SOURCE_TYPES.


# ---------------------------------------------------------------------------
# Source key requirements (D4: requirement awareness at onboarding)
# ---------------------------------------------------------------------------

# Canonical env vars per source type live in
# ``autoinfo.config.SOURCE_KEY_ENV_VARS`` — the single source of truth
# shared with ``alerts.py`` (B3 credential-missing detection) so the two
# key-maps can never drift apart.  Mirrors the collector contract:
# handlers with ``requires_key() -> True`` (ap_api, reuters_mcp, unpaywall,
# youtube) plus the collect-time key guards (nyt, spotify, quandl, kaggle,
# core, email, email_imap).  Drives the missing-key detection behind
# ``init_project`` next_steps and the ``test_source`` key warning.

# Source settings keys that carry a credential directly, satisfying the
# requirement without any env var.


# ---------------------------------------------------------------------------
# Error response helper
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Agent Callback handlers (3)


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

app = Server("autoinfo")

# Director-only operations (T-S-08 / AC1.3).  These are reserved for the
# human director and are gated at the CODE level, not merely documented: a
# default agent neither discovers them in ``list_tools()`` nor can invoke
# them (the dispatch guard below refuses with ``DIRECTOR_ONLY``).  Keeping
# the single source of truth here means discovery, the machine-readable
# per-tool marker, and the dispatch guard can never drift apart.
_DIRECTOR_ONLY_TOOLS: frozenset[str] = frozenset(
    {
        "demote_kb_wiki",  # 03-Wiki is append-only: director-only demotion
        "force_promote",  # skip the curation/admission gate: director-only
        "remove_domain",  # destructive config removal: human/director decides
    }
)

# JSON Schema extension keyword marking a tool as director-only.  Unknown
# keywords are ignored by standard JSON Schema consumers, so this rides
# alongside the normal schema while staying machine-readable to an agent.
DIRECTOR_ONLY_MARKER = "x-autoinfo-director-only"


def _caller_actor_for_discovery() -> str:
    """Resolve the actor identity used to decide director-surface visibility.

    The MCP stdio transport carries no per-request caller identity, so the
    server identity is taken from ``AUTOINFO_ACTOR`` (the same variable the
    audit trail uses).  When that is unset but ``AUTOINFO_DIRECTOR_ACTORS``
    is explicitly configured, the server adopts the first whitelisted actor
    as its identity — i.e. a director-operated server.  A default agent
    (neither variable set) resolves to ``"agent:mcp"``, which the default
    ``"director"`` whitelist never matches, so director tools stay hidden.
    """
    actor = os.environ.get("AUTOINFO_ACTOR")
    if actor and actor.strip():
        return actor.strip()
    raw = os.environ.get("AUTOINFO_DIRECTOR_ACTORS")
    if raw and raw.strip():
        first = next((a.strip() for a in raw.split(",") if a.strip()), "")
        if first:
            return first
    return "agent:mcp"


def _caller_is_director() -> bool:
    """Return whether the current server identity is a whitelisted director."""
    if _is_readonly():
        return False
    return is_director(_caller_actor_for_discovery())


@app.list_tools()  # type: ignore[untyped-decorator,no-untyped-call]
async def list_tools() -> list[Tool]:
    """Declare the available MCP tools with their input schemas.

    Read-only mode (gate 1): exposes ONLY the ``_READONLY_TOOLS`` whitelist.

    Director gating (T-S-08): a default agent never sees the
    ``_DIRECTOR_ONLY_TOOLS`` surface — an operation it cannot invoke is not
    advertised.  A server whose identity resolves to a whitelisted
    ``AUTOINFO_DIRECTOR_ACTORS`` entry sees the full declaration; those
    tools also carry the machine-readable ``DIRECTOR_ONLY_MARKER``.
    """
    tools = _full_tool_list()
    if _is_readonly():
        return [t for t in tools if t.name in _READONLY_TOOLS]
    if not _caller_is_director():
        return [t for t in tools if t.name not in _DIRECTOR_ONLY_TOOLS]
    return tools


# Canonical param spellings with their legacy alias (T-S-03). The alias is
# accepted at dispatch and exposed as an optional schema property; it is then
# normalized to whichever spelling the handler signature expects.
_USER_ID_ALIASES = ("user_id", "end_user_id")
_DOMAIN_ALIASES = ("name", "domain")
_DOMAIN_IDENTITY_TOOLS = frozenset(
    {
        "activate_domain",
        "deactivate_domain",
        "add_domain",
        "remove_domain",
        "get_domain_config",
    }
)


def _inject_param_alias(
    schema: dict[str, Any],
    canonical: str,
    alias: str,
    alias_description: str,
) -> None:
    """Expose ``alias`` as an optional spelling of ``canonical``.

    ``canonical`` stays required alongside the alias so the contract still
    demands the value while either spelling satisfies it (JSON Schema
    ``required`` is presence-only — dispatch collapses the alias).
    """
    props = schema.setdefault("properties", {})
    if canonical not in props or alias in props:
        return
    props[alias] = {
        "type": props[canonical].get("type", "string"),
        "description": alias_description,
        "deprecated": True,
    }


def _inject_param_aliases(tool: Tool) -> None:
    """Expose legacy param spellings as optional aliases (T-S-03).

    ``user_id``/``end_user_id`` and ``domain``/``name`` are the same entity
    spelled two ways across the surface.  Both spellings remain callable;
    dispatch normalizes to whichever spelling the handler expects.  The
    canonical spelling stays in ``required`` when the handler needs it; the
    alias is optional so existing required-param contracts don't break.
    """
    schema = tool.inputSchema
    if not isinstance(schema, dict):
        return
    props = schema.get("properties", {})
    if "user_id" in props:
        _inject_param_alias(
            schema,
            "user_id",
            "end_user_id",
            "Alias of user_id (deprecated spelling; both are accepted).",
        )
    elif "end_user_id" in props:
        _inject_param_alias(
            schema,
            "end_user_id",
            "user_id",
            "Alias of end_user_id (canonical spelling; both are accepted).",
        )
    if tool.name in _DOMAIN_IDENTITY_TOOLS and "name" in props:
        _inject_param_alias(
            schema,
            "name",
            "domain",
            "Alias of name (domain identity; both are accepted).",
        )


def _decorate_tools(tools: list[Tool]) -> list[Tool]:
    """Inject legacy param aliases and the director-only marker.

    ``outputSchema`` is deliberately not attached: the canonical envelope is
    documented once (ADR 0010, ``docs/dev/specs/mcp-tools.md``) instead of
    being repeated on all 149 tools.  Per-tool schemas are a follow-up (#581).
    """
    for tool in tools:
        _inject_param_aliases(tool)
        if tool.name in _DIRECTOR_ONLY_TOOLS and isinstance(tool.inputSchema, dict):
            tool.inputSchema[DIRECTOR_ONLY_MARKER] = True
    return tools


def _full_tool_list() -> list[Tool]:
    """Return the MCP tool schemas in their stable registration order.

    Schemas live in :mod:`autoinfo.mcp.tools` (one module per domain; #581
    phase 1).  Every call builds fresh ``Tool`` objects before decoration, so
    ``_decorate_tools`` mutations never leak across calls.
    """
    from autoinfo.mcp.tools import build_all_tools

    return _decorate_tools(build_all_tools())


# -- LLM-required tools (16) ------------------------------------------------
# Tools in this set require LLM configuration to function.  When the LLM
# is not configured (no api_key), call_tool will block them with a clear
# error response before dispatching to the handler.
_LLM_REQUIRED_TOOLS: frozenset[str] = frozenset(
    {
        "suggest_keywords",
        "classify_cefr",
        "cefr_batch",
        "extract_fields",
        "generate_digest",
        "generate_report",
        "generate_cross_domain_report",
        "generate_tutorial",
        "generate_presentation",
        "localize_content",
        "query_collected",
        "process_collection",
        "recommend_content",
        "simplify_content",
        "promote_kb_draft",
        "batch_run",
    }
)


# -- Read-only server mode (``autoinfo serve --agent``) ----------------------
# SECURITY: double gate — list_tools() lists ONLY whitelisted tools;
# call_tool() returns an explicit READ_ONLY_SERVER error envelope for any
# non-whitelisted name (never silent).  ``run_validation_scenario`` is
# EXPLICITLY EXCLUDED (its steps contain write ops: collect/promote/delete).
# ``export_kb`` / ``search_knowledge_base`` are not in _LLM_REQUIRED_TOOLS,
# and export_kb(format="agent") is served by the pure-function path
# (_export_agent_json — no LLM, no disk), so readonly mode works keyless.
_READONLY_TOOLS: frozenset[str] = frozenset(
    {
        "search_knowledge_base",
        "get_kb_entry",
        "export_kb",
        "list_validation_scenarios",
    }
)

# Mode is decided at startup (--readonly / serve --agent), never mid-session.
_READONLY_MODE = False


def set_readonly_mode(enabled: bool) -> None:
    """Enable/disable read-only server mode (process-wide)."""
    global _READONLY_MODE
    _READONLY_MODE = bool(enabled)


def _is_readonly() -> bool:
    """Return ``True`` when the server runs in read-only mode."""
    return _READONLY_MODE


def _is_llm_configured() -> bool:
    """Return ``True`` if an LLM API key has been configured.

    Mirrors the logic in ``_handle_diagnose_system`` — reads the config
    and checks both the config field and the ``AUTOINFO_LLM_API_KEY``
    environment variable.  Fails closed (``False``) on error.
    """
    try:
        from autoinfo.config import get_config_path, load_config

        config_path = get_config_path()
        if config_path:
            config = load_config(config_path)
            return bool(config.llm.api_key or os.environ.get("AUTOINFO_LLM_API_KEY"))
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------------
# Dispatch-level audit hook (M1T15)
#
# Every MCP tool call is recorded in the append-only audit log with the
# whitelisted fields ONLY: actor, action, tool, resource, result_code,
# trace_id.  Tool inputs and response data are NEVER written here — the
# privacy grep (`grep -rn "api_key\|arguments\|payload" server.py |
# grep -i audit`) must stay empty.
# ---------------------------------------------------------------------------

# Explicit exclusion list (volume control): high-frequency read probes.
#  * ``health_check``  — entry-point health probe
#  * ``get_tool_count`` — static introspection
#  * every ``list_*`` tool (list_domains, list_sources, list_topics,
#    list_summaries, ...) — read-only discovery probes that fire in tight
#    agent loops and would otherwise dominate the log.
# All other tools (mutations + parameterised reads) are audited.
_AUDIT_EXCLUDED_TOOLS: frozenset[str] = frozenset(
    {
        "health_check",
        "get_tool_count",
    }
)

_AUDIT_WRITE_FAILURES = 0  # in-process counter surfaced via pipeline logs


def _audit_excluded(tool_name: str) -> bool:
    """Return ``True`` when *tool_name* is on the audit exclusion list.

    Exclusion list (documented, explicit):
      * ``health_check``
      * ``get_tool_count``
      * every tool whose name starts with ``list_``
    """
    return tool_name in _AUDIT_EXCLUDED_TOOLS or tool_name.startswith("list_")


def _handler_declares(tool_name: str, param: str) -> bool:
    """Return whether the handler *explicitly* declares ``param`` (T-S-03).

    Unlike :func:`_handler_accepts`, this ignores ``**kwargs`` absorption:
    a handler that only takes ``(name, arguments)`` — or a ``**kwargs``
    catch-all — does *not* declare either spelling, and the alias resolver
    must not assume the handler reads a specific key just because its
    signature can absorb one.
    """
    import inspect

    handler = globals().get(f"_handle_{tool_name}")
    if handler is None:
        return False
    try:
        sig = inspect.signature(handler)
    except (TypeError, ValueError):
        return False
    return param in sig.parameters


def _handler_accepts(tool_name: str, param: str) -> bool:
    """Return whether the tool's handler accepts ``param`` at dispatch time."""
    import inspect

    handler = globals().get(f"_handle_{tool_name}")
    if handler is None:
        return False
    try:
        sig = inspect.signature(handler)
    except (TypeError, ValueError):
        return False
    if param in sig.parameters:
        return True
    return any(p.kind is inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())


def _normalize_param_aliases(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Normalize legacy param spellings to what the handler expects (T-S-03).

    The surface exposes ``user_id``/``end_user_id`` and
    ``domain``/``name`` as the same entity.  Both spellings are accepted;
    here the alias is collapsed onto whichever spelling the handler
    signature *explicitly declares*, so explicit-signature handlers never
    see an unexpected keyword and callers keep working with either
    spelling.

    Generic handlers — ``(name, arguments)`` or ``**kwargs`` collectors —
    declare neither spelling, so their signature cannot tell us which key
    they read.  Collapsing to the alias would break a handler that reads
    ``arguments["user_id"]`` (the canonical spelling); therefore the
    canonical spelling is used as the fallback target.
    """
    args = dict(arguments)
    for canonical, alias in (_USER_ID_ALIASES,):
        present = [p for p in (canonical, alias) if p in args]
        if not present:
            continue
        value = args[present[0]]
        if _handler_declares(tool_name, alias) and not _handler_declares(tool_name, canonical):
            target = alias
        else:
            target = canonical
        for p in (canonical, alias):
            args.pop(p, None)
        args[target] = value
    if tool_name in _DOMAIN_IDENTITY_TOOLS:
        present = [p for p in _DOMAIN_ALIASES if p in args]
        if present:
            value = args[present[0]]
            if _handler_declares(tool_name, "domain") and not _handler_declares(tool_name, "name"):
                target = "domain"
            else:
                target = "name"
            for p in _DOMAIN_ALIASES:
                args.pop(p, None)
            args[target] = value
    return args


def _current_actor() -> str:
    """Resolve a stable actor id for dispatch-level audit entries.

    Taxonomy: ``"agent:<session>"`` (interactive MCP agent client),
    ``"cli"`` (command-line driven), ``"cron"`` (scheduled job),
    ``"system"`` (internal / server-originated).

    The MCP dispatch does not carry caller identity in its handler
    signature, so the actor is taken from the ``AUTOINFO_ACTOR``
    environment variable when a launcher (cron wrapper, CLI shim) sets
    it, defaulting to ``"agent:mcp"`` for the stdio/SSE agent surface.
    """
    return os.environ.get("AUTOINFO_ACTOR") or "agent:mcp"


def _safe_resource(args: dict[str, Any]) -> str:
    """Extract a single low-sensitivity resource identifier for audit rows.

    Returns the ``domain`` (then ``topic``, then ``name``) argument when
    present, else ``""``.  Only configuration-level identifiers (domain /
    topic / entity names) are ever used — never URLs, credentials, or
    free-form content — so the audit row's resource field cannot carry
    secrets.
    """
    for key in ("domain", "topic", "name"):
        value = args.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _audit_tool_call(tool_name: str, code: str, resource: str = "") -> None:
    """Append one dispatch-level row to the audit log (fire-and-forget).

    Writes exactly the whitelisted fields: ``actor``, ``action``,
    ``tool``, ``resource``, ``result_code``, ``trace_id`` — nothing else
    (no tool inputs, no response data).

    Best-effort by design: the write is wrapped in try/except so an audit
    failure can never fail the tool call itself; failures are logged and
    counted (``_AUDIT_WRITE_FAILURES``) instead.
    """
    global _AUDIT_WRITE_FAILURES
    if _audit_excluded(tool_name):
        return
    try:
        from autoinfo.audit import append_audit_log

        append_audit_log(
            actor=_current_actor(),
            action="tool_call",
            tool=tool_name,
            resource_id=resource,
            details={
                "result_code": code,
                "trace_id": str(uuid.uuid4()),
            },
        )
    except Exception:
        _AUDIT_WRITE_FAILURES += 1
        logger.warning(
            "Audit write failed for tool '%s' (code=%s) — call result unaffected",
            tool_name,
            code,
            exc_info=True,
        )
        from autoinfo.logging import get_pipeline_logger

        get_pipeline_logger("mcp.dispatch").warning(
            "Audit write failure",
            extra={"tool": tool_name, "result_code": code, "failures": _AUDIT_WRITE_FAILURES},
        )


def _envelope_result(
    envelope: dict[str, Any],
) -> tuple[list[TextContent], dict[str, Any]]:
    """Pack an envelope as ``(text_content, structured_content)``.

    Returning the tuple form lets clients read the same JSON either as text
    or as structured data, both carrying the canonical envelope.
    """
    return (
        [TextContent(type="text", text=json.dumps(envelope))],
        envelope,
    )


# #581 phase 2: data-driven dispatch.  Handler + invocation mode, in the
# same category order as the former if/elif chain (149 tools).  Keep this
# table in lock-step with ``_full_tool_list`` (enforced by
# tests/mcp/test_tool_dispatch_registry.py).
_TOOL_DISPATCH: dict[str, tuple[str, str]] = {
    # -- System (3) ---------------------------------------------------
    "health_check": ("_handle_health_check", "noargs"),
    "get_tool_count": ("_handle_get_tool_count", "noargs"),
    "diagnose_system": ("_handle_diagnose_system", "noargs"),
    # -- Discovery (7) ------------------------------------------------
    "list_domains": ("_handle_list_domains", "noargs"),
    "list_available_platforms": ("_handle_list_available_platforms", "noargs"),
    "get_domain_schema": ("_handle_get_domain_schema", "kwargs"),
    "list_available_models": ("_handle_list_available_models", "noargs"),
    "get_effective_llm_config": ("_handle_get_effective_llm_config", "kwargs"),
    "activate_domain": ("_handle_activate_domain", "kwargs"),
    "deactivate_domain": ("_handle_deactivate_domain", "kwargs"),
    "add_domain": ("_handle_add_domain", "kwargs"),
    "remove_domain": ("_handle_remove_domain", "kwargs"),
    "get_domain_config": ("_handle_get_domain_config", "kwargs"),
    # -- Source Management (5) ----------------------------------------
    "add_source": ("_handle_add_source", "kwargs"),
    "add_sources": ("_handle_add_sources", "kwargs"),
    "remove_source": ("_handle_remove_source", "kwargs"),
    "test_source": ("_handle_test_source", "kwargs"),
    "list_sources": ("_handle_list_sources", "kwargs"),
    # -- Topic Management (6) -----------------------------------------
    "add_topic": ("_handle_add_topic", "kwargs"),
    "remove_topic": ("_handle_remove_topic", "kwargs"),
    "list_topics": ("_handle_list_topics", "kwargs"),
    "list_keywords": ("_handle_list_keywords", "kwargs"),
    "topic_group_add": ("_handle_topic_group_add", "kwargs"),
    "topic_group_remove": ("_handle_topic_group_remove", "kwargs"),
    # -- Keywords Management (3) --------------------------------------
    "approve_keyword": ("_handle_approve_keyword", "kwargs"),
    "reject_keyword": ("_handle_reject_keyword", "kwargs"),
    "suggest_keywords": ("_handle_suggest_keywords", "thread"),
    # -- Collection / Processing (5) ----------------------------------
    # collect/process/batch_run are long-running sync handlers; offload
    # them so the asyncio event loop stays responsive and the progress
    # tools (get_collection_progress / get_processing_progress) keep
    # answering while a run is in flight (issue #136).
    "collect_sources": ("_handle_collect_sources", "thread"),
    "get_collection_progress": ("_handle_get_collection_progress", "kwargs"),
    "get_collection_status": ("_handle_get_collection_status", "kwargs"),
    "process_collection": ("_handle_process_collection", "thread"),
    "get_processing_progress": ("_handle_get_processing_progress", "kwargs"),
    # -- Knowledge Base (4) -------------------------------------------
    "list_summaries": ("_handle_list_summaries", "kwargs"),
    "get_kb_entry": ("_handle_get_kb_entry", "kwargs"),
    "search_knowledge_base": ("_handle_search_knowledge_base", "kwargs"),
    "query_knowledge_graph": ("_handle_query_knowledge_graph", "kwargs"),
    "knowledge_graph_export": ("_handle_knowledge_graph_export", "kwargs"),
    "flag_for_knowledge_base": ("_handle_flag_for_knowledge_base", "kwargs"),
    "get_summary": ("_handle_get_summary", "kwargs"),
    "link_items": ("_handle_link_items", "kwargs"),
    "get_item_relations": ("_handle_get_item_relations", "kwargs"),
    "get_entry_history": ("_handle_get_entry_history", "kwargs"),
    "restore_entry_version": ("_handle_restore_entry_version", "kwargs"),
    "compare_versions": ("_handle_compare_versions", "kwargs"),
    "get_collection_stats": ("_handle_get_collection_stats", "kwargs"),
    "get_collection_diff": ("_handle_get_collection_diff", "kwargs"),
    "get_domain_decay": ("_handle_get_domain_decay", "kwargs"),
    # -- KB: Draft tools (4) ------------------------------------------
    "create_kb_draft": ("_handle_create_kb_draft", "kwargs"),
    "reject_kb_draft": ("_handle_reject_kb_draft", "kwargs"),
    "list_kb_tier": ("_handle_list_kb_tier", "kwargs"),
    "promote_kb_draft": ("_handle_promote_kb_draft", "thread"),
    "demote_kb_wiki": ("_handle_demote_kb_wiki", "kwargs"),
    "force_promote": ("_handle_force_promote", "kwargs"),
    "promote_pending": ("_handle_promote_pending", "kwargs"),
    "reindex_kb": ("_handle_reindex_kb", "kwargs"),
    "create_kb_entry": ("_handle_create_kb_entry", "kwargs"),
    # -- Audit (1) -------------------------------------------------------
    "query_audit_log": ("_handle_query_audit_log", "kwargs"),
    # -- CEFR Classification (1) ----------------------------------------
    "classify_cefr": ("_handle_classify_cefr", "thread"),
    "cefr_batch": ("_handle_cefr_batch", "thread"),
    # -- Output (6) ---------------------------------------------------
    "list_output_templates": ("_handle_list_output_templates", "kwargs"),
    "generate_digest": ("_handle_generate_digest", "thread"),
    "generate_report": ("_handle_generate_report", "thread"),
    "generate_cross_domain_report": ("_handle_generate_cross_domain_report", "thread"),
    "generate_tutorial": ("_handle_generate_tutorial", "thread"),
    "generate_presentation": ("_handle_generate_presentation", "thread"),
    "localize_content": ("_handle_localize_content", "thread"),
    # -- Export / Import (2) -----------------------------------------------
    "export_kb": ("_handle_export_kb", "kwargs"),
    "import_kb": ("_handle_import_kb", "kwargs"),
    # -- Email (1) --------------------------------------------------------
    "send_email_digest": ("_handle_send_email_digest", "kwargs"),
    "email_config": ("_handle_email_config", "kwargs"),
    # -- Custom Extraction (2) ----------------------------------------
    "extract_fields": ("_handle_extract_fields", "thread"),
    "get_extraction": ("_handle_get_extraction", "kwargs"),
    # -- Schedule Management (5) ---------------------------------------
    "list_schedules": ("_handle_list_schedules", "noargs"),
    "add_schedule": ("_handle_add_schedule", "kwargs"),
    "remove_schedule": ("_handle_remove_schedule", "kwargs"),
    "run_schedules": ("_handle_run_schedules", "kwargs"),
    "get_schedule_status": ("_handle_get_schedule_status", "kwargs"),
    # -- Delivery Schedule Management (3) --------------------------------
    "add_delivery_schedule": ("_handle_add_delivery_schedule", "kwargs"),
    "list_delivery_schedules": ("_handle_list_delivery_schedules", "noargs"),
    "remove_delivery_schedule": ("_handle_remove_delivery_schedule", "kwargs"),
    # -- Q&A (1) -------------------------------------------------------
    "query_collected": ("_handle_query_collected", "thread"),
    # -- Source Health / Feedback (2) ----------------------------------
    "get_source_health": ("_handle_get_source_health", "kwargs"),
    "rate_item": ("_handle_rate_item", "kwargs"),
    # -- Webhooks (2) -------------------------------------------------
    "set_domain_webhooks": ("_handle_set_domain_webhooks", "kwargs"),
    "get_domain_webhooks": ("_handle_get_domain_webhooks", "kwargs"),
    # -- Init / Project / Batch / Config (8) --------------------------
    "init_project": ("_handle_init_project", "kwargs"),
    "configure_llm": ("_handle_configure_llm", "kwargs"),
    "test_llm_connection": ("_handle_test_llm_connection", "thread"),
    "list_projects": ("_handle_list_projects", "noargs"),
    "get_project_assets": ("_handle_get_project_assets", "noargs"),
    "archive_project": ("_handle_archive_project", "kwargs"),
    "batch_run": ("_handle_batch_run", "thread"),
    "get_feeds": ("_handle_get_feeds", "kwargs"),
    "list_active_collections": ("_handle_list_active_collections", "noargs"),
    "get_config": ("_handle_get_config", "kwargs"),
    # -- Gate Config (2) ------------------------------------------------
    "get_gate_config": ("_handle_get_gate_config", "kwargs"),
    "set_gate_config": ("_handle_set_gate_config", "kwargs"),
    # -- Product (2) ----------------------------------------------------
    "get_product": ("_handle_get_product", "kwargs"),
    "list_products": ("_handle_list_products", "kwargs"),
    # -- End User Delivery (1) -------------------------------------------
    "send_to_enduser": ("_handle_send_to_enduser", "kwargs"),
    # -- Alert Rules (3) ------------------------------------------------
    "get_alert_rules": ("_handle_get_alert_rules", "kwargs"),
    "add_alert_rule": ("_handle_add_alert_rule", "kwargs"),
    "remove_alert_rule": ("_handle_remove_alert_rule", "kwargs"),
    # -- Budget Thresholds (2) -------------------------------------------
    "get_budget_thresholds": ("_handle_get_budget_thresholds", "noargs"),
    "set_budget_thresholds": ("_handle_set_budget_thresholds", "kwargs"),
    "cost_dashboard": ("_handle_cost_dashboard", "kwargs"),
    "cost_allocation": ("_handle_cost_allocation", "kwargs"),
    # -- Metrics (2) --------------------------------------------------
    "get_metrics": ("_handle_get_metrics", "raw"),
    "get_prometheus_metrics": ("_handle_get_prometheus_metrics", "raw"),
    # -- Trace (1) ----------------------------------------------------
    "trace_item": ("_handle_trace_item", "raw"),
    # -- Soft-delete & GDPR (4) -----------------------------------------
    "soft_delete_entry": ("_handle_soft_delete_entry", "raw"),
    "mark_stale": ("_handle_mark_stale", "raw"),
    "restore_entry": ("_handle_restore_entry", "raw"),
    "export_user_data": ("_handle_export_user_data", "raw"),
    "delete_user_data": ("_handle_delete_user_data", "raw"),
    # -- Portal / End-user Self-service (2) ------------------------------
    "get_enduser_history": ("_handle_get_enduser_history", "kwargs"),
    "get_enduser_products": ("_handle_get_enduser_products", "kwargs"),
    # -- Delivery Log (1) ------------------------------------------------
    "query_delivery_log": ("_handle_query_delivery_log", "raw"),
    # -- Delivery Monitor (2) ------------------------------------------
    "list_active_deliveries": ("_handle_list_active_deliveries", "noargs"),
    "get_delivery_log": ("_handle_get_delivery_log", "kwargs"),
    # -- Clean Cache (1) -------------------------------------------------
    "clean_cache": ("_handle_clean_cache", "kwargs"),
    # -- Channel Health (1) ------------------------------------------
    "get_channel_health": ("_handle_get_channel_health", "kwargs"),
    # -- Merge / Find Similar (2) ---------------------------------
    "merge_items": ("_handle_merge_items", "kwargs"),
    "find_similar_items": ("_handle_find_similar_items", "kwargs"),
    # -- KB Freshness (1) ---------------------------------------------
    "calculate_freshness_score": ("_handle_calculate_freshness_score", "raw"),
    # -- End-User Trial (2) ----------------------------------------------
    "activate_trial": ("_handle_activate_trial", "kwargs"),
    "check_trial_expiry": ("_handle_check_trial_expiry", "kwargs"),
    # -- End-User Preferences (2) ----------------------------------------
    "update_preferences": ("_handle_update_preferences", "kwargs"),
    "get_preferences": ("_handle_get_preferences", "kwargs"),
    # -- End-User CRUD (5) --------------------------------------------------
    "enduser_create": ("_handle_enduser_create", "kwargs"),
    "enduser_get": ("_handle_enduser_get", "kwargs"),
    "enduser_update": ("_handle_enduser_update", "kwargs"),
    "enduser_delete": ("_handle_enduser_delete", "kwargs"),
    "enduser_list": ("_handle_enduser_list", "noargs"),
    # -- Stripe Billing (3) ------------------------------------------------
    "create_checkout_session": ("_handle_create_checkout_session", "kwargs"),
    "get_subscription_status": ("_handle_get_subscription_status", "kwargs"),
    "get_billing_summary": ("_handle_get_billing_summary", "kwargs"),
    # -- Usage-based Billing (G16 — 2) -----------------------------------
    "get_enduser_usage": ("_handle_get_enduser_usage", "kwargs"),
    "get_enduser_invoice": ("_handle_get_enduser_invoice", "kwargs"),
    # -- Agent Callbacks (3) --------------------------------------------
    "set_agent_callback": ("_handle_set_agent_callback", "kwargs"),
    "list_agent_callbacks": ("_handle_list_agent_callbacks", "noargs"),
    "remove_agent_callback": ("_handle_remove_agent_callback", "kwargs"),
    # -- Recommendation (1) --------------------------------------------
    "recommend_content": ("_handle_recommend_content", "thread"),
    # -- Simplification (1) --------------------------------------------
    "simplify_content": ("_handle_simplify_content", "thread"),
    # -- Validation (5) ------------------------------------------------
    "list_validation_scenarios": ("_handle_list_validation_scenarios", "noargs"),
    "run_validation_scenario": ("_handle_run_validation_scenario", "async"),
    "run_all_validation_scenarios": ("_handle_run_all_validation_scenarios", "async"),
    "get_coverage_report": ("_handle_get_coverage_report", "thread_noargs"),
    "get_run_decisions": ("_handle_get_run_decisions", "thread"),
}


async def _invoke_tool(
    spec: tuple[str, str],
    name: str,
    arguments: dict[str, Any],
) -> dict[str, Any] | list[dict[str, Any]]:
    """Invoke one dispatched handler using its registered call shape.

    The registry stores the handler *name*, resolved through module globals at
    call time: tests monkeypatch ``autoinfo.mcp.server._handle_*`` and that
    seam must keep working after the dispatch chain became a table.
    """
    handler_name, mode = spec
    handler = cast(Callable[..., Any], globals()[handler_name])
    result: dict[str, Any] | list[dict[str, Any]]
    if mode == "kwargs":
        result = handler(**arguments)
    elif mode == "thread":
        result = await asyncio.to_thread(handler, **arguments)
    elif mode == "noargs":
        result = handler()
    elif mode == "raw":
        result = handler(name, arguments)
    elif mode == "thread_noargs":
        result = await asyncio.to_thread(handler)
    elif mode == "async":
        result = await handler(**arguments)
    else:
        raise RuntimeError(f"unknown dispatch mode {mode!r} for tool {name!r}")
    return result


@app.call_tool()  # type: ignore[untyped-decorator]
async def call_tool(
    name: str, arguments: dict[str, Any]
) -> tuple[list[TextContent], dict[str, Any]]:
    """Dispatch tool calls to the appropriate implementation."""
    _dispatch_audit: dict[str, str] = {"code": "success"}
    result: dict[str, Any] | list[dict[str, Any]]
    arguments = _normalize_param_aliases(name, arguments)
    try:
        # -- Read-only gate (gate 2): whitelist enforcement ---------------
        # Explicit error envelope for non-whitelisted names — never silent.
        if _is_readonly() and name not in _READONLY_TOOLS:
            _dispatch_audit["code"] = "read_only"
            return _envelope_result(
                error_response(
                    code=ErrorCode.READ_ONLY_SERVER,
                    message=(
                        f"Tool '{name}' is not available in read-only "
                        "server mode (autoinfo serve --agent). "
                        f"Allowed tools: {', '.join(sorted(_READONLY_TOOLS))}. "
                        "Restart the server without --readonly for full access."
                    ),
                    actionable=True,
                )
            )

        # -- LLM guard: block LLM-required tools when not configured ------
        if name in _LLM_REQUIRED_TOOLS and not _is_llm_configured():
            _dispatch_audit["code"] = "blocked"
            return _envelope_result(
                error_response(
                    code=ErrorCode.LLM_NOT_CONFIGURED,
                    message="LLM is not configured. Use configure_llm() to set up your API key. See docs/dev/required-api-keys.md for the full list of API keys and environment variables.",
                    actionable=True,
                )
            )

        # -- Director-only guard: demote / force-promote / remove-domain --
        # Enforced at dispatch against the AUTOINFO_DIRECTOR_ACTORS
        # whitelist so a non-director actor is refused before anything is
        # mutated; an omitted actor defaults to the non-privileged "agent",
        # never to a privileged role.  demote_kb_wiki / force_promote repeat
        # the check in the store; soft_delete_entry enforces the same
        # whitelist at the store for 03-Wiki targets.
        if name in _DIRECTOR_ONLY_TOOLS:
            actor = arguments.get("actor") or "agent"
            if not is_director(actor):
                _dispatch_audit["code"] = "director_only"
                return _envelope_result(
                    error_response(
                        code=ErrorCode.DIRECTOR_ONLY,
                        message=(f"actor '{actor}' not whitelisted in AUTOINFO_DIRECTOR_ACTORS"),
                        actionable=True,
                    )
                )

        spec = _TOOL_DISPATCH.get(name)
        if spec is None:
            _dispatch_audit["code"] = "unknown_tool"
            return _envelope_result(
                error_response(
                    code=ErrorCode.UNKNOWN_TOOL,
                    message=f"Unknown tool: {name}",
                    actionable=False,
                )
            )
        result = await _invoke_tool(spec, name, arguments)

        # Canonical envelope only: handlers return either the success envelope
        # or the error envelope; flat success payloads are wrapped here.
        if isinstance(result, dict) and "success" in result:
            wrapped = result
        else:
            wrapped = success_response(result)
        return _envelope_result(wrapped)
    except NotImplementedError:
        # Stub tools return a graceful error response using canonical envelope
        _dispatch_audit["code"] = "not_implemented"
        return _envelope_result(
            error_response(
                code=ErrorCode.INTERNAL_ERROR,
                message=str(arguments.get("message", "Not implemented in v0.1")),
                actionable=True,
            )
        )
    except TypeError as exc:
        # Missing required arguments — client-side call error, not a server bug
        _dispatch_audit["code"] = "validation_error"
        return _envelope_result(
            _error_from_exc(
                exc,
                f"Tool '{name}' call failed",
                code=ErrorCode.VALIDATION_ERROR,
            )
        )
    except Exception as exc:
        _dispatch_audit["code"] = "error"
        logger.exception("Tool '%s' failed", name)
        return _envelope_result(_error_response(exc))
    finally:
        resource = _safe_resource(arguments)
        _audit_tool_call(name, _dispatch_audit["code"], resource)


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


async def main(readonly: bool = False) -> None:
    """Run the MCP server over stdio transport.

    Opens the stdio read/write streams and enters the server's main loop.
    The server processes incoming JSON-RPC messages until the client
    disconnects.

    Parameters
    ----------
    readonly:
        When ``True``, expose ONLY the ``_READONLY_TOOLS`` whitelist
        (read-only server mode — ``autoinfo serve --agent`` /
        ``python -m autoinfo.mcp.server --readonly``).
    """
    set_readonly_mode(readonly)
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


def run(readonly: bool = False) -> None:
    """Synchronous entry point (used by ``python -m autoinfo.mcp.server``)."""
    asyncio.run(main(readonly=readonly))


# Re-export surface for the shared helper tier (#581 phase 3): handler code
# and external imports keep these names without importing context directly.
from autoinfo.mcp.context import _PERSIST_EXT_BY_FORMAT as _PERSIST_EXT_BY_FORMAT
from autoinfo.mcp.context import _PLATFORM_INFO as _PLATFORM_INFO
from autoinfo.mcp.context import _REQUIRED_KEYS_DOCS_REF as _REQUIRED_KEYS_DOCS_REF
from autoinfo.mcp.context import _SOURCE_SETTINGS_KEY_KEYS as _SOURCE_SETTINGS_KEY_KEYS
from autoinfo.mcp.context import _VALID_SOURCE_TYPES as _VALID_SOURCE_TYPES
from autoinfo.mcp.context import OUTPUTS_DIR as OUTPUTS_DIR
from autoinfo.mcp.context import PLATFORMS as PLATFORMS
from autoinfo.mcp.context import T as T
from autoinfo.mcp.context import _canonicalize as _canonicalize
from autoinfo.mcp.context import _chain_contains_timeout as _chain_contains_timeout
from autoinfo.mcp.context import _classify_exception as _classify_exception
from autoinfo.mcp.context import _config_path as _config_path
from autoinfo.mcp.context import _default_platform_info as _default_platform_info
from autoinfo.mcp.context import _demo_sources_defs as _demo_sources_defs
from autoinfo.mcp.context import _detect_kb_status as _detect_kb_status
from autoinfo.mcp.context import _detect_missing_source_keys as _detect_missing_source_keys
from autoinfo.mcp.context import _detect_phase as _detect_phase
from autoinfo.mcp.context import _error_from_exc as _error_from_exc
from autoinfo.mcp.context import _error_response as _error_response
from autoinfo.mcp.context import _find_domain as _find_domain
from autoinfo.mcp.context import _gate_to_dict as _gate_to_dict
from autoinfo.mcp.context import _infer_format as _infer_format
from autoinfo.mcp.context import _init_job_state_table as _init_job_state_table
from autoinfo.mcp.context import _job_db_path as _job_db_path
from autoinfo.mcp.context import _load_config as _load_config
from autoinfo.mcp.context import _load_job_state as _load_job_state
from autoinfo.mcp.context import _load_latest_domain_state as _load_latest_domain_state
from autoinfo.mcp.context import _maybe_persist_output as _maybe_persist_output
from autoinfo.mcp.context import _merge_fallback_entries as _merge_fallback_entries
from autoinfo.mcp.context import _output_text as _output_text
from autoinfo.mcp.context import _parse_tags as _parse_tags
from autoinfo.mcp.context import _persist_output as _persist_output
from autoinfo.mcp.context import _safe_json_load as _safe_json_load
from autoinfo.mcp.context import _save_config as _save_config
from autoinfo.mcp.context import _save_job_state as _save_job_state
from autoinfo.mcp.context import _source_key_status as _source_key_status
from autoinfo.mcp.context import _suggest_extract_fields as _suggest_extract_fields
from autoinfo.mcp.context import _text_payload_metadata as _text_payload_metadata
from autoinfo.mcp.context import _validate_llm_pool_params as _validate_llm_pool_params
from autoinfo.mcp.context import _validate_source_type as _validate_source_type
from autoinfo.mcp.context import _validate_url as _validate_url
from autoinfo.mcp.context import _with_job_db as _with_job_db
from autoinfo.mcp.context import logger as logger
from autoinfo.mcp.tools.config_admin import (
    _handle_get_domain_webhooks as _handle_get_domain_webhooks,
)
from autoinfo.mcp.tools.config_admin import _handle_get_gate_config as _handle_get_gate_config
from autoinfo.mcp.tools.config_admin import _handle_get_product as _handle_get_product
from autoinfo.mcp.tools.config_admin import _handle_list_products as _handle_list_products
from autoinfo.mcp.tools.config_admin import (
    _handle_set_domain_webhooks as _handle_set_domain_webhooks,
)
from autoinfo.mcp.tools.config_admin import _handle_set_gate_config as _handle_set_gate_config
from autoinfo.mcp.tools.enduser import _handle_add_alert_rule as _handle_add_alert_rule
from autoinfo.mcp.tools.enduser import _handle_cost_allocation as _handle_cost_allocation
from autoinfo.mcp.tools.enduser import _handle_cost_dashboard as _handle_cost_dashboard
from autoinfo.mcp.tools.enduser import _handle_get_alert_rules as _handle_get_alert_rules
from autoinfo.mcp.tools.enduser import (
    _handle_get_budget_thresholds as _handle_get_budget_thresholds,
)
from autoinfo.mcp.tools.enduser import _handle_remove_alert_rule as _handle_remove_alert_rule
from autoinfo.mcp.tools.enduser import _handle_send_to_enduser as _handle_send_to_enduser
from autoinfo.mcp.tools.enduser import (
    _handle_set_budget_thresholds as _handle_set_budget_thresholds,
)
from autoinfo.mcp.tools.enduser_billing import _handle_activate_trial as _handle_activate_trial
from autoinfo.mcp.tools.enduser_billing import (
    _handle_check_trial_expiry as _handle_check_trial_expiry,
)
from autoinfo.mcp.tools.enduser_billing import (
    _handle_create_checkout_session as _handle_create_checkout_session,
)
from autoinfo.mcp.tools.enduser_billing import _handle_enduser_create as _handle_enduser_create
from autoinfo.mcp.tools.enduser_billing import _handle_enduser_delete as _handle_enduser_delete
from autoinfo.mcp.tools.enduser_billing import _handle_enduser_get as _handle_enduser_get
from autoinfo.mcp.tools.enduser_billing import _handle_enduser_list as _handle_enduser_list
from autoinfo.mcp.tools.enduser_billing import _handle_enduser_update as _handle_enduser_update
from autoinfo.mcp.tools.enduser_billing import (
    _handle_get_billing_summary as _handle_get_billing_summary,
)
from autoinfo.mcp.tools.enduser_billing import _handle_get_delivery_log as _handle_get_delivery_log
from autoinfo.mcp.tools.enduser_billing import (
    _handle_get_enduser_history as _handle_get_enduser_history,
)
from autoinfo.mcp.tools.enduser_billing import (
    _handle_get_enduser_invoice as _handle_get_enduser_invoice,
)
from autoinfo.mcp.tools.enduser_billing import (
    _handle_get_enduser_products as _handle_get_enduser_products,
)
from autoinfo.mcp.tools.enduser_billing import (
    _handle_get_enduser_usage as _handle_get_enduser_usage,
)
from autoinfo.mcp.tools.enduser_billing import _handle_get_preferences as _handle_get_preferences
from autoinfo.mcp.tools.enduser_billing import (
    _handle_get_subscription_status as _handle_get_subscription_status,
)
from autoinfo.mcp.tools.enduser_billing import (
    _handle_list_active_deliveries as _handle_list_active_deliveries,
)
from autoinfo.mcp.tools.enduser_billing import (
    _handle_query_delivery_log as _handle_query_delivery_log,
)
from autoinfo.mcp.tools.enduser_billing import (
    _handle_update_preferences as _handle_update_preferences,
)
from autoinfo.mcp.tools.kb_lifecycle import (
    _handle_calculate_freshness_score as _handle_calculate_freshness_score,
)
from autoinfo.mcp.tools.kb_lifecycle import _handle_find_similar_items as _handle_find_similar_items
from autoinfo.mcp.tools.kb_lifecycle import _handle_merge_items as _handle_merge_items
from autoinfo.mcp.tools.kb_lifecycle import _handle_trace_item as _handle_trace_item
from autoinfo.mcp.tools.knowledge import _handle_compare_versions as _handle_compare_versions
from autoinfo.mcp.tools.knowledge import _handle_create_kb_draft as _handle_create_kb_draft
from autoinfo.mcp.tools.knowledge import _handle_create_kb_entry as _handle_create_kb_entry
from autoinfo.mcp.tools.knowledge import _handle_demote_kb_wiki as _handle_demote_kb_wiki
from autoinfo.mcp.tools.knowledge import (
    _handle_flag_for_knowledge_base as _handle_flag_for_knowledge_base,
)
from autoinfo.mcp.tools.knowledge import _handle_force_promote as _handle_force_promote
from autoinfo.mcp.tools.knowledge import _handle_get_collection_diff as _handle_get_collection_diff
from autoinfo.mcp.tools.knowledge import (
    _handle_get_collection_stats as _handle_get_collection_stats,
)
from autoinfo.mcp.tools.knowledge import _handle_get_domain_decay as _handle_get_domain_decay
from autoinfo.mcp.tools.knowledge import _handle_get_entry_history as _handle_get_entry_history
from autoinfo.mcp.tools.knowledge import _handle_get_item_relations as _handle_get_item_relations
from autoinfo.mcp.tools.knowledge import _handle_get_kb_entry as _handle_get_kb_entry
from autoinfo.mcp.tools.knowledge import _handle_get_summary as _handle_get_summary
from autoinfo.mcp.tools.knowledge import (
    _handle_knowledge_graph_export as _handle_knowledge_graph_export,
)
from autoinfo.mcp.tools.knowledge import _handle_link_items as _handle_link_items
from autoinfo.mcp.tools.knowledge import _handle_list_kb_tier as _handle_list_kb_tier
from autoinfo.mcp.tools.knowledge import _handle_list_summaries as _handle_list_summaries
from autoinfo.mcp.tools.knowledge import _handle_promote_kb_draft as _handle_promote_kb_draft
from autoinfo.mcp.tools.knowledge import _handle_promote_pending as _handle_promote_pending
from autoinfo.mcp.tools.knowledge import (
    _handle_query_knowledge_graph as _handle_query_knowledge_graph,
)
from autoinfo.mcp.tools.knowledge import _handle_reindex_kb as _handle_reindex_kb
from autoinfo.mcp.tools.knowledge import _handle_reject_kb_draft as _handle_reject_kb_draft
from autoinfo.mcp.tools.knowledge import (
    _handle_restore_entry_version as _handle_restore_entry_version,
)
from autoinfo.mcp.tools.knowledge import (
    _handle_search_knowledge_base as _handle_search_knowledge_base,
)
from autoinfo.mcp.tools.misc import _handle_clean_cache as _handle_clean_cache
from autoinfo.mcp.tools.misc import _handle_get_channel_health as _handle_get_channel_health
from autoinfo.mcp.tools.misc import _handle_get_coverage_report as _handle_get_coverage_report
from autoinfo.mcp.tools.misc import _handle_get_run_decisions as _handle_get_run_decisions
from autoinfo.mcp.tools.misc import _handle_list_agent_callbacks as _handle_list_agent_callbacks
from autoinfo.mcp.tools.misc import (
    _handle_list_validation_scenarios as _handle_list_validation_scenarios,
)
from autoinfo.mcp.tools.misc import _handle_recommend_content as _handle_recommend_content
from autoinfo.mcp.tools.misc import _handle_remove_agent_callback as _handle_remove_agent_callback
from autoinfo.mcp.tools.misc import (
    _handle_run_all_validation_scenarios as _handle_run_all_validation_scenarios,
)
from autoinfo.mcp.tools.misc import (
    _handle_run_validation_scenario as _handle_run_validation_scenario,
)
from autoinfo.mcp.tools.misc import _handle_set_agent_callback as _handle_set_agent_callback
from autoinfo.mcp.tools.misc import _handle_simplify_content as _handle_simplify_content
from autoinfo.mcp.tools.ops import _handle_archive_project as _handle_archive_project
from autoinfo.mcp.tools.ops import _handle_batch_run as _handle_batch_run
from autoinfo.mcp.tools.ops import _handle_cefr_batch as _handle_cefr_batch
from autoinfo.mcp.tools.ops import _handle_classify_cefr as _handle_classify_cefr
from autoinfo.mcp.tools.ops import _handle_get_config as _handle_get_config
from autoinfo.mcp.tools.ops import _handle_get_feeds as _handle_get_feeds
from autoinfo.mcp.tools.ops import _handle_get_project_assets as _handle_get_project_assets
from autoinfo.mcp.tools.ops import (
    _handle_list_active_collections as _handle_list_active_collections,
)
from autoinfo.mcp.tools.ops import _handle_list_projects as _handle_list_projects
from autoinfo.mcp.tools.ops import _handle_query_audit_log as _handle_query_audit_log
from autoinfo.mcp.tools.output import _handle_email_config as _handle_email_config
from autoinfo.mcp.tools.output import _handle_export_kb as _handle_export_kb
from autoinfo.mcp.tools.output import _handle_extract_fields as _handle_extract_fields
from autoinfo.mcp.tools.output import (
    _handle_generate_cross_domain_report as _handle_generate_cross_domain_report,
)
from autoinfo.mcp.tools.output import _handle_generate_digest as _handle_generate_digest
from autoinfo.mcp.tools.output import _handle_generate_presentation as _handle_generate_presentation
from autoinfo.mcp.tools.output import _handle_generate_report as _handle_generate_report
from autoinfo.mcp.tools.output import _handle_generate_tutorial as _handle_generate_tutorial
from autoinfo.mcp.tools.output import _handle_get_extraction as _handle_get_extraction
from autoinfo.mcp.tools.output import _handle_import_kb as _handle_import_kb
from autoinfo.mcp.tools.output import _handle_list_output_templates as _handle_list_output_templates
from autoinfo.mcp.tools.output import _handle_localize_content as _handle_localize_content
from autoinfo.mcp.tools.output import _handle_send_email_digest as _handle_send_email_digest
from autoinfo.mcp.tools.qa import _handle_get_source_health as _handle_get_source_health
from autoinfo.mcp.tools.qa import _handle_query_collected as _handle_query_collected
from autoinfo.mcp.tools.qa import _handle_rate_item as _handle_rate_item
from autoinfo.mcp.tools.runtime import _handle_configure_llm as _handle_configure_llm
from autoinfo.mcp.tools.runtime import _handle_delete_user_data as _handle_delete_user_data
from autoinfo.mcp.tools.runtime import _handle_export_user_data as _handle_export_user_data
from autoinfo.mcp.tools.runtime import _handle_get_metrics as _handle_get_metrics
from autoinfo.mcp.tools.runtime import (
    _handle_get_prometheus_metrics as _handle_get_prometheus_metrics,
)
from autoinfo.mcp.tools.runtime import _handle_init_project as _handle_init_project
from autoinfo.mcp.tools.runtime import _handle_mark_stale as _handle_mark_stale
from autoinfo.mcp.tools.runtime import _handle_restore_entry as _handle_restore_entry
from autoinfo.mcp.tools.runtime import _handle_soft_delete_entry as _handle_soft_delete_entry
from autoinfo.mcp.tools.runtime import _handle_test_llm_connection as _handle_test_llm_connection
from autoinfo.mcp.tools.scheduling import (
    _handle_add_delivery_schedule as _handle_add_delivery_schedule,
)
from autoinfo.mcp.tools.scheduling import _handle_add_schedule as _handle_add_schedule
from autoinfo.mcp.tools.scheduling import _handle_get_schedule_status as _handle_get_schedule_status
from autoinfo.mcp.tools.scheduling import (
    _handle_list_delivery_schedules as _handle_list_delivery_schedules,
)
from autoinfo.mcp.tools.scheduling import _handle_list_schedules as _handle_list_schedules
from autoinfo.mcp.tools.scheduling import (
    _handle_remove_delivery_schedule as _handle_remove_delivery_schedule,
)
from autoinfo.mcp.tools.scheduling import _handle_remove_schedule as _handle_remove_schedule
from autoinfo.mcp.tools.scheduling import _handle_run_schedules as _handle_run_schedules
from autoinfo.mcp.tools.sources import _handle_add_source as _handle_add_source
from autoinfo.mcp.tools.sources import _handle_add_sources as _handle_add_sources
from autoinfo.mcp.tools.sources import _handle_add_topic as _handle_add_topic
from autoinfo.mcp.tools.sources import _handle_approve_keyword as _handle_approve_keyword
from autoinfo.mcp.tools.sources import _handle_collect_sources as _handle_collect_sources
from autoinfo.mcp.tools.sources import (
    _handle_get_collection_progress as _handle_get_collection_progress,
)
from autoinfo.mcp.tools.sources import (
    _handle_get_collection_status as _handle_get_collection_status,
)
from autoinfo.mcp.tools.sources import (
    _handle_get_processing_progress as _handle_get_processing_progress,
)
from autoinfo.mcp.tools.sources import _handle_list_keywords as _handle_list_keywords
from autoinfo.mcp.tools.sources import _handle_list_sources as _handle_list_sources
from autoinfo.mcp.tools.sources import _handle_list_topics as _handle_list_topics
from autoinfo.mcp.tools.sources import _handle_process_collection as _handle_process_collection
from autoinfo.mcp.tools.sources import _handle_reject_keyword as _handle_reject_keyword
from autoinfo.mcp.tools.sources import _handle_remove_source as _handle_remove_source
from autoinfo.mcp.tools.sources import _handle_remove_topic as _handle_remove_topic
from autoinfo.mcp.tools.sources import _handle_suggest_keywords as _handle_suggest_keywords
from autoinfo.mcp.tools.sources import _handle_test_source as _handle_test_source
from autoinfo.mcp.tools.sources import _handle_topic_group_add as _handle_topic_group_add
from autoinfo.mcp.tools.sources import _handle_topic_group_remove as _handle_topic_group_remove
from autoinfo.mcp.tools.system import _handle_activate_domain as _handle_activate_domain
from autoinfo.mcp.tools.system import _handle_add_domain as _handle_add_domain
from autoinfo.mcp.tools.system import _handle_deactivate_domain as _handle_deactivate_domain
from autoinfo.mcp.tools.system import _handle_diagnose_system as _handle_diagnose_system
from autoinfo.mcp.tools.system import _handle_get_domain_config as _handle_get_domain_config
from autoinfo.mcp.tools.system import _handle_get_domain_schema as _handle_get_domain_schema
from autoinfo.mcp.tools.system import (
    _handle_get_effective_llm_config as _handle_get_effective_llm_config,
)
from autoinfo.mcp.tools.system import _handle_get_tool_count as _handle_get_tool_count
from autoinfo.mcp.tools.system import _handle_health_check as _handle_health_check
from autoinfo.mcp.tools.system import _handle_list_available_models as _handle_list_available_models
from autoinfo.mcp.tools.system import (
    _handle_list_available_platforms as _handle_list_available_platforms,
)
from autoinfo.mcp.tools.system import _handle_list_domains as _handle_list_domains
from autoinfo.mcp.tools.system import _handle_remove_domain as _handle_remove_domain

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Run the AutoInfo MCP server (stdio transport).",
    )
    parser.add_argument(
        "--readonly",
        action="store_true",
        help="Read-only mode: expose only the 4 read-only tools "
        "(search_knowledge_base, get_kb_entry, export_kb(format=agent), "
        "list_validation_scenarios). Equivalent to 'autoinfo serve --agent'.",
    )
    args = parser.parse_args()
    run(readonly=args.readonly)
