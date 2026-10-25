"""MCP tool schemas — Init, metrics, soft-delete/GDPR (10 tools).

Phase 1 of #581: schemas extracted from ``mcp/server.py::_full_tool_list``
verbatim.  ``build_tools()`` returns FRESH ``Tool`` objects on every call,
so ``_decorate_tools`` mutation never leaks across calls.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp.types import Tool

from autoinfo.cli.init import _list_demo_domains
from autoinfo.kb import DirectorOnlyError
from autoinfo.llm import call_with_fallback
from autoinfo.mcp import context as mcp_context
from autoinfo.mcp.errors import ErrorCode, error_response, success_response


def build_tools() -> list[Tool]:
    """Return the 10 schemas for this module, in registration order."""
    return [
        # -- Init (3) --------------------------------------------------------
        Tool(
            name="init_project",
            description=(
                "Initialize AutoInfo project skeleton (creates .autoinfo/ "
                "directory, config, demo domain). Idempotent — safe to call "
                "when already initialized."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Demo domain name (e.g. medical-research)",
                        "enum": _list_demo_domains(),
                    },
                    "project_name": {
                        "type": "string",
                        "description": "Optional human-friendly project name",
                        "default": "",
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "Preview what would be created without writing files",
                        "default": False,
                    },
                    "llm_provider": {
                        "type": "string",
                        "description": 'Override default LLM provider (e.g. "openai")',
                        "default": "",
                    },
                    "llm_model": {
                        "type": "string",
                        "description": 'Override default LLM model (e.g. "gpt-4")',
                        "default": "",
                    },
                    "llm_base_url": {
                        "type": "string",
                        "description": 'Override default LLM base URL (e.g. "http://localhost:11434/v1")',
                        "default": "",
                    },
                },
                "required": ["domain"],
            },
        ),
        Tool(
            name="configure_llm",
            description=(
                "Update LLM configuration in .autoinfo/config.yaml. "
                "Incremental: only updates fields explicitly provided. "
                "api_key is stored as env var reference (${AUTOINFO_LLM_API_KEY}), "
                "never the raw key. No-op when no parameters are supplied. "
                "llm_fallback configures the fallback chain (None = unchanged, "
                "[] = clear, entries merge by (provider, model) identity); "
                "llm_tasks configures per-task model routing (None = unchanged, "
                "{} = clear; judgment tasks still resolve to the release-pinned "
                "the effective judgment model at runtime)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "provider": {
                        "type": "string",
                        "description": 'LLM provider name (e.g. "openai", "openrouter")',
                        "default": "",
                    },
                    "model": {
                        "type": "string",
                        "description": 'LLM model name (e.g. "gpt-4", "deepseek/deepseek-chat")',
                        "default": "",
                    },
                    "api_key": {
                        "type": "string",
                        "description": "API key — stored as env var reference (${AUTOINFO_LLM_API_KEY}), not raw key. Set AUTOINFO_LLM_API_KEY env var separately.",
                        "default": "",
                    },
                    "base_url": {
                        "type": "string",
                        "description": 'LLM base URL (e.g. "http://localhost:11434/v1")',
                        "default": "",
                    },
                    "llm_fallback": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "model": {
                                    "type": "string",
                                    "description": "Fallback model name (required)",
                                },
                                "provider": {
                                    "type": "string",
                                    "description": "Fallback provider; empty inherits the primary provider (provider inheritance does not grant the primary API key — key inheritance requires a matching base_url)",
                                },
                                "base_url": {
                                    "type": "string",
                                    "description": "Fallback base URL",
                                },
                                "api_key": {
                                    "type": "string",
                                    "description": "Fallback API key (env var reference ${...}); empty inherits the primary key ONLY when base_url matches the primary gateway — a cross-endpoint fallback must carry its own explicit key",
                                },
                                "json_mode": {
                                    "type": "boolean",
                                    "description": "Force JSON response format for this fallback",
                                },
                                "reasoning_model": {
                                    "type": "boolean",
                                    "description": "Mark this fallback as a reasoning model",
                                },
                                "timeout": {
                                    "type": "number",
                                    "description": "Per-call timeout in seconds",
                                },
                            },
                            "required": ["model"],
                        },
                        "description": "Fallback chain entries. None = leave unchanged; [] = clear; entries merge by (provider, model) identity.",
                    },
                    "llm_tasks": {
                        "type": "object",
                        "description": "Per-task LLM overrides keyed by task name (model/provider/max_tokens). None = leave unchanged; {} = clear. Judgment tasks (g4_factual/g5_translation/llm_judge) still resolve to the effective judgment model (llm.judgment_model/llm.model) at runtime.",
                        "additionalProperties": {
                            "type": "object",
                            "properties": {
                                "model": {
                                    "type": "string",
                                    "description": "Task model override",
                                },
                                "provider": {
                                    "type": "string",
                                    "description": "Task provider override",
                                },
                                "max_tokens": {
                                    "type": "integer",
                                    "description": "Task max_tokens override",
                                },
                            },
                        },
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="test_llm_connection",
            description=(
                "Test LLM connectivity with the current or overridden "
                "configuration. Makes a minimal completion call and reports "
                "connectable, tested_model, latency_ms, and config_source "
                "(params when any override is supplied, else config). "
                "Pass api_key explicitly to test a key without persisting it."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "provider": {
                        "type": "string",
                        "description": 'LLM provider override (e.g. "openai", "openrouter")',
                        "default": "",
                    },
                    "model": {
                        "type": "string",
                        "description": 'LLM model override (e.g. "gpt-4", "deepseek/deepseek-chat")',
                        "default": "",
                    },
                    "base_url": {
                        "type": "string",
                        "description": 'LLM base URL override (e.g. "http://localhost:11434/v1")',
                        "default": "",
                    },
                    "api_key": {
                        "type": "string",
                        "description": "API key override for this test only (never persisted). Empty inherits the config/env key.",
                        "default": "",
                    },
                },
                "required": [],
            },
        ),
        # -- Metrics (2) -----------------------------------------------------
        Tool(
            name="get_metrics",
            description="Get Prometheus-format metrics for monitoring. Exposes counters and gauges for collection, processing, LLM spend and delivery as text exposition format. Use when scraping into a monitoring stack or debugging a live server.",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Optional domain filter",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="get_prometheus_metrics",
            description="Get raw Prometheus exposition-format metrics (same format as /metrics HTTP endpoint)",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        # -- Soft-delete & GDPR (5) ------------------------------------------
        Tool(
            name="soft_delete_entry",
            description="Mark an entry as deleted (soft-delete) or permanently remove it (hard-delete). Set purge=True for permanent deletion. 03-Wiki entries are append-only: only an actor whitelisted in AUTOINFO_DIRECTOR_ACTORS (default 'director') can delete them.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entry_id": {"type": "string"},
                    "purge": {
                        "type": "boolean",
                        "description": "If False (default), performs soft-delete (mark as deleted). If True, permanently deletes the entry from index, FTS5, and disk.",
                        "default": False,
                    },
                    "actor": {
                        "type": "string",
                        "description": "Required. Acting actor. 03-Wiki entries require an actor whitelisted in AUTOINFO_DIRECTOR_ACTORS",
                    },
                },
                "required": ["entry_id", "actor"],
            },
        ),
        Tool(
            name="mark_stale",
            description="Mark a knowledge base entry as stale (demoted in search, excluded from digests)",
            inputSchema={
                "type": "object",
                "properties": {
                    "entry_id": {"type": "string"},
                },
                "required": ["entry_id"],
            },
        ),
        Tool(
            name="restore_entry",
            description="Restore a soft-deleted entry. Reverses soft_delete_entry within the retention window, returning the entry to its previous tier. Use to recover a mistakenly archived item before permanent purge.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entry_id": {"type": "string"},
                    "actor": {
                        "type": "string",
                        "description": "Required. Actor requesting this destructive operation (must be passed explicitly)",
                    },
                },
                "required": ["entry_id", "actor"],
            },
        ),
        Tool(
            name="export_user_data",
            description="Export all data for a user (GDPR compliance). Bundles the profile, subscriptions, preferences, delivery log and audit rows into a single JSON payload. Use to fulfill a data-subject access request.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                },
                "required": ["user_id"],
            },
        ),
        Tool(
            name="delete_user_data",
            description="Delete all user data (GDPR right to be forgotten). Permanently erases the end-user profile, subscriptions, delivery history and derived records. Use only for a verified erasure request; requires actor for audit.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "purge": {"type": "boolean"},
                    "actor": {
                        "type": "string",
                        "description": "Required. Actor requesting this destructive operation (must be passed explicitly)",
                    },
                },
                "required": ["user_id", "actor"],
            },
        ),
    ]


def _handle_init_project(
    domain: str,
    project_name: str = "",
    dry_run: bool = False,
    llm_provider: str = "",
    llm_model: str = "",
    llm_base_url: str = "",
) -> dict[str, Any]:
    """Initialize AutoInfo project skeleton (creates .autoinfo/ directory,
    config, demo domain). Idempotent — safe to call when already initialized.

    Parameters
    ----------
    domain:
        Demo domain name (e.g. medical-research).
    project_name:
        Optional human-friendly project name.
    dry_run:
        If True, preview what would be created without writing files.
    llm_provider:
        Override the default LLM provider (e.g. \"openai\").
    llm_model:
        Override the default LLM model (e.g. \"gpt-4\").
    llm_base_url:
        Override the default LLM base URL (e.g. \"http://localhost:11434/v1\").
    """
    # Lazy imports to avoid circular dependencies
    from autoinfo.cli.init import _DEMO_DOMAINS_DIR, _ensure_dir, _run_init
    from autoinfo.mcp.errors import ErrorCode

    autoinfo_dir = Path.cwd() / ".autoinfo"
    config_path = autoinfo_dir / "config.yaml"

    # Idempotency check — skip if already initialized
    if config_path.exists() and not dry_run:
        return {
            "status": "skipped",
            "message": "Already initialized",
        }

    # Validate domain against available demo domains
    demo_sources = _DEMO_DOMAINS_DIR / domain / "sources.yaml"
    if not demo_sources.is_file():
        available = sorted(d.name for d in _DEMO_DOMAINS_DIR.iterdir() if d.is_dir())
        return error_response(
            code=ErrorCode.VALIDATION_ERROR,
            message=f"Unknown demo domain '{domain}'. Available: {available}",
            actionable=True,
        )

    if dry_run:
        missing_keys = mcp_context._detect_missing_source_keys(domain, sources_yaml=demo_sources)
        next_steps = [
            "configure_llm(api_key='...', provider='...', model='...')",
            "configure_llm(llm_fallback=[{'model': 'mimo-v2.5', 'base_url': 'https://opencode.ai/zen/go/v1'}], llm_tasks={'extraction': {'model': 'deepseek-v4-flash'}}); verify with test_llm_connection()",
            f"collect_sources(domain='{domain}')",
            f"process_collection(domain='{domain}')",
        ]
        for mk in missing_keys:
            if mk["env_vars"]:
                envs = ", ".join(mk["env_vars"])
                next_steps.append(
                    f"Set {envs} for source '{mk['name']}' (type: {mk['type']}) before collecting from it"
                )
            else:
                next_steps.append(
                    f"Configure an API key for source '{mk['name']}' (type: {mk['type']}) before collecting from it"
                )
        if missing_keys:
            next_steps.append(
                f"See {mcp_context._REQUIRED_KEYS_DOCS_REF} for the full catalog of source API keys and environment variables"
            )
        return {
            "status": "dry_run",
            "domain": domain,
            "project_name": project_name,
            "autoinfo_dir": str(autoinfo_dir),
            "llm_provider": llm_provider or "(default)",
            "llm_model": llm_model or "(default)",
            "llm_base_url": llm_base_url or "(default)",
            "would_create_dirs": [
                ".autoinfo/",
                "knowledge/00-Inbox/",
                "knowledge/01-Raw/",
                "knowledge/02-Draft/",
                "knowledge/03-Wiki/",
                "collections/",
                "outputs/",
            ],
            "would_create_files": [
                ".autoinfo/config.yaml",
            ],
            "message": "Dry run — no files were created",
            "next_steps": next_steps,
        }

    try:
        _ensure_dir(autoinfo_dir)
        # _run_init takes list[str]; a bare str would iterate char-by-char.
        _run_init([domain], autoinfo_dir, project_name=project_name)

        if llm_provider or llm_model or llm_base_url:
            import yaml

            config_path = autoinfo_dir / "config.yaml"
            if config_path.exists():
                with open(config_path, "r") as f:
                    cfg = yaml.safe_load(f)
                if llm_provider:
                    cfg.setdefault("llm", {})["provider"] = llm_provider
                if llm_model:
                    cfg.setdefault("llm", {})["model"] = llm_model
                if llm_base_url:
                    cfg.setdefault("llm", {})["base_url"] = llm_base_url
                with open(config_path, "w") as f:
                    yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)

        missing_keys = mcp_context._detect_missing_source_keys(domain, sources_yaml=demo_sources)
        next_steps = [
            "configure_llm(api_key='...', provider='...', model='...')",
            "configure_llm(llm_fallback=[{'model': 'mimo-v2.5', 'base_url': 'https://opencode.ai/zen/go/v1'}], llm_tasks={'extraction': {'model': 'deepseek-v4-flash'}}); verify with test_llm_connection()",
            f"collect_sources(domain='{domain}')",
            f"process_collection(domain='{domain}')",
        ]
        for mk in missing_keys:
            if mk["env_vars"]:
                envs = ", ".join(mk["env_vars"])
                next_steps.append(
                    f"Set {envs} for source '{mk['name']}' (type: {mk['type']}) before collecting from it"
                )
            else:
                next_steps.append(
                    f"Configure an API key for source '{mk['name']}' (type: {mk['type']}) before collecting from it"
                )
        if missing_keys:
            next_steps.append(
                f"See {mcp_context._REQUIRED_KEYS_DOCS_REF} for the full catalog of source API keys and environment variables"
            )
        return {
            "status": "success",
            "domain": domain,
            "project_name": project_name,
            "autoinfo_dir": str(autoinfo_dir),
            "llm_provider": llm_provider or "(default)",
            "llm_model": llm_model or "(default)",
            "llm_base_url": llm_base_url or "(default)",
            "message": f"AutoInfo initialized for '{domain}'",
            "next_steps": next_steps,
            "docs": "See docs/dev/director-user-guide.md for the full human-agent interaction workflow.",
        }
    except Exception as exc:
        mcp_context.logger.exception("Init project failed for domain '%s'", domain)
        return mcp_context._error_from_exc(exc, "Init project failed")


def _handle_configure_llm(
    provider: str = "",
    model: str = "",
    api_key: str = "",
    base_url: str = "",
    llm_fallback: list[dict[str, Any]] | None = None,
    llm_tasks: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Update LLM configuration in .autoinfo/config.yaml.

    Parameters
    ----------
    provider:
        LLM provider name (e.g. \"openai\", \"openrouter\").
    model:
        LLM model name (e.g. \"gpt-4\", \"deepseek/deepseek-chat\").
    api_key:
        API key reference — stored as ``${AUTOINFO_LLM_API_KEY}``
        (env var reference), never the raw key.
        The caller should set the ``AUTOINFO_LLM_API_KEY`` env var.
    base_url:
        LLM base URL (e.g. \"http://localhost:11434/v1\").
    llm_fallback:
        Fallback chain entries (list of dicts, each with a required
        ``model``).  ``None`` leaves the existing fallback untouched;
        ``[]`` clears it; entries merge by ``(provider, model)`` identity.
    llm_tasks:
        Per-task LLM overrides keyed by task name (``model``/``provider``/
        ``max_tokens``).  ``None`` leaves existing tasks untouched;
        ``{}`` clears them.  Judgment tasks (g4_factual/g5_translation/
        llm_judge) are writable but still resolve to the effective
        judgment model (llm.judgment_model → llm.model → loud error,
        issue #195) at runtime.
    """
    config_path = mcp_context._config_path()

    # No-op when nothing is supplied
    if not any([provider, model, api_key, base_url]) and llm_fallback is None and llm_tasks is None:
        return {
            "status": "noop",
            "message": ("No parameters supplied. Nothing to configure."),
        }

    # Check config exists
    if not config_path.exists():
        return error_response(
            ErrorCode.CONFIG_NOT_FOUND,
            (
                "Configuration not found. "
                "Run init_project first to create .autoinfo/config.yaml. "
                "See docs/dev/required-api-keys.md for API key setup."
            ),
            actionable=True,
        )

    try:
        import yaml

        with open(config_path, "r") as f:
            cfg = yaml.safe_load(f)
        if cfg is None:
            cfg = {}

        llm = cfg.setdefault("llm", {})

        # Validate BEFORE writing so a failed validation leaves the file
        # untouched (mtime unchanged).
        validation_error = mcp_context._validate_llm_pool_params(llm_fallback, llm_tasks)
        if validation_error:
            return error_response(
                ErrorCode.VALIDATION_ERROR,
                validation_error,
                actionable=True,
            )

        # Incremental updates — only write fields explicitly provided
        if provider:
            llm["provider"] = provider
        if model:
            llm["model"] = model
        if base_url:
            llm["base_url"] = base_url
        if api_key:
            # Store env var reference, NEVER the raw key
            llm["api_key"] = "${AUTOINFO_LLM_API_KEY}"

        # Fallback merge — keyed on (provider or primary, model) identity.
        # None = don't touch; [] = clear; list = merge with dedup.
        if llm_fallback is not None:
            if not llm_fallback:
                llm["fallback"] = []
            else:
                primary_provider = llm.get("provider", "")
                primary_model = llm.get("model", "")
                existing_fallback = llm.get("fallback", []) or []
                llm["fallback"] = mcp_context._merge_fallback_entries(
                    existing_fallback,
                    llm_fallback,
                    primary_provider,
                    primary_model,
                )

        # Tasks merge — by task name.  None = don't touch; {} = clear.
        if llm_tasks is not None:
            if not llm_tasks:
                llm["tasks"] = {}
            else:
                existing_tasks = llm.get("tasks", {}) or {}
                merged_tasks = dict(existing_tasks)
                for task_name, task_cfg in llm_tasks.items():
                    merged_tasks[str(task_name)] = task_cfg
                llm["tasks"] = merged_tasks

        with open(config_path, "w") as f:
            yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)

        # Write-then-verify: round-trip through load_config so a malformed
        # write surfaces as an error instead of a silently-broken config.
        try:
            from autoinfo.config import load_config

            loaded = load_config(config_path)
            if llm_fallback is not None and len(loaded.llm.fallback) != len(llm["fallback"]):
                raise RuntimeError("fallback count mismatch after round-trip")
            if llm_tasks is not None and set(loaded.llm.tasks) != set(llm["tasks"]):
                raise RuntimeError("task names mismatch after round-trip")
        except Exception as exc:
            mcp_context.logger.exception("configure_llm round-trip verification failed")
            return error_response(
                ErrorCode.INTERNAL_ERROR,
                f"Config written but failed round-trip verification: {exc}",
                actionable=True,
            )

        updated = {
            "provider": provider or "(unchanged)",
            "model": model or "(unchanged)",
            "base_url": base_url or "(unchanged)",
            "api_key": (
                "${AUTOINFO_LLM_API_KEY} (env var reference written)" if api_key else "(unchanged)"
            ),
        }
        if llm_fallback is not None:
            updated["fallback"] = llm["fallback"]
        if llm_tasks is not None:
            updated["tasks"] = llm["tasks"]

        message = (
            "LLM configured. "
            "Also set AUTOINFO_LLM_API_KEY env var for the API key. "
            "See docs/dev/required-api-keys.md for the full list of "
            "API keys and environment variables."
        )
        if llm_tasks:
            from autoinfo.config import JUDGMENT_TASKS

            judgment_written = sorted(set(llm_tasks) & set(JUDGMENT_TASKS))
            if judgment_written:
                message += (
                    f" Judgment task(s) {', '.join(judgment_written)} "
                    "are written to llm.tasks but 运行期仍强制 judgment model "
                    "(llm.judgment_model/llm.model; llm.tasks cannot override "
                    "judgment models)."
                )

        return success_response(
            {
                "status": "success",
                "message": message,
                "updated": updated,
                "config_path": str(config_path),
            }
        )

    except Exception as exc:
        mcp_context.logger.exception("configure_llm failed")
        return mcp_context._error_from_exc(exc, "configure_llm failed")


def _handle_test_llm_connection(
    provider: str = "",
    model: str = "",
    base_url: str = "",
    api_key: str = "",
) -> dict[str, Any]:
    """Test LLM connectivity with the current or overridden configuration.

    Mirrors ``_handle_test_source``: entry validation → error envelope →
    result dict.  Key validation is handler-internal (NOT the dispatcher
    guard) so an explicit ``api_key`` param can bypass the config/env key
    check.  ``config_source`` is ``"params"`` when any override param is
    supplied, else ``"config"``.
    """
    import time

    from autoinfo.config import Config, LLMConfig, get_config_path, load_config

    # Resolve current effective config — param overrides win, the rest
    # inherits the on-disk values (the same source get_effective_llm_config
    # reads internally).
    current_provider = ""
    current_model = ""
    current_base_url = ""
    current_key = ""
    current_timeout: float | None = None
    current_json_mode = False
    current_reasoning_model = False
    current_fallback: list[LLMConfig] = []
    try:
        config_path = get_config_path()
        if config_path:
            config = load_config(config_path)
            current_provider = config.llm.provider
            current_model = config.llm.model
            current_base_url = config.llm.base_url
            current_key = config.llm.api_key
            current_timeout = config.llm.timeout
            current_json_mode = config.llm.json_mode
            current_reasoning_model = config.llm.reasoning_model
            current_fallback = config.llm.fallback
    except Exception:
        pass

    eff_provider = provider or current_provider
    eff_model = model or current_model
    eff_base_url = base_url or current_base_url
    eff_key = api_key or current_key

    # Resolve ${ENV} references so a placeholder without a backing env var
    # does not count as a real key.
    if eff_key.startswith("${") and eff_key.endswith("}"):
        eff_key = os.environ.get(eff_key[2:-1], "")
    if not eff_key:
        eff_key = os.environ.get("AUTOINFO_LLM_API_KEY", "")

    # Handler-internal key check (mirrors _handle_suggest_keywords): an
    # explicit api_key param skips the check; otherwise a config/env key is
    # required.  NOT the dispatcher guard — that only inspects config/env
    # keys and would make explicit overrides unreachable.
    if not eff_key:
        return error_response(
            code=ErrorCode.LLM_NOT_CONFIGURED,
            message=(
                "LLM is not configured. Use configure_llm() to set up your "
                "API key or pass api_key explicitly. "
                f"See {mcp_context._REQUIRED_KEYS_DOCS_REF} for the full list of API keys "
                "and environment variables."
            ),
            actionable=True,
        )

    # Temporary config: param overrides on top of the inherited values so the
    # configured fallback chain still applies to the probe call.
    temp_llm = LLMConfig(
        provider=eff_provider,
        model=eff_model,
        api_key=eff_key,
        base_url=eff_base_url,
        json_mode=current_json_mode,
        reasoning_model=current_reasoning_model,
        # current_timeout is Optional (absent when no on-disk config exists);
        # coerce to the LLMConfig default (120.0) so LLMConfig.timeout stays float.
        timeout=current_timeout or 120.0,
        fallback=current_fallback,
    )
    temp_config = Config(llm=temp_llm)

    tested_model = temp_llm.resolve_model() or (
        f"{eff_provider or 'openrouter'}/{eff_model or 'deepseek/deepseek-chat'}"
    )
    config_source = "params" if any([provider, model, base_url, api_key]) else "config"

    start = time.monotonic()
    try:
        response = call_with_fallback(
            messages=[{"role": "user", "content": "Reply with exactly: OK"}],
            max_tokens=16,
            temperature=0.0,
            timeout=current_timeout,
            config=temp_config,
        )
        latency_ms = round((time.monotonic() - start) * 1000.0, 1)
        _content = ""
        if response is not None and getattr(response, "choices", None):
            _content = response.choices[0].message.content or ""
        return {
            "connectable": True,
            "tested_model": tested_model,
            "latency_ms": latency_ms,
            "message": f"LLM connection successful ({tested_model}).",
            "config_source": config_source,
        }
    except Exception as exc:
        mcp_context.logger.exception("LLM connection test failed")
        if mcp_context._chain_contains_timeout(exc):
            return error_response(
                code=ErrorCode.TIMEOUT,
                message=(
                    f"LLM connection test timed out for '{tested_model}'. "
                    "Check the base_url and network connectivity. "
                    f"See {mcp_context._REQUIRED_KEYS_DOCS_REF}."
                ),
                actionable=True,
            )
        return error_response(
            code=ErrorCode.INTERNAL_ERROR,
            message=(
                f"LLM connection test failed for '{tested_model}': {exc}. "
                "Check the provider/model/base_url configuration. "
                f"See {mcp_context._REQUIRED_KEYS_DOCS_REF}."
            ),
            actionable=True,
        )


def _handle_get_metrics(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    from autoinfo.metrics import get_metrics as _get_metrics

    return mcp_context._canonicalize(_get_metrics())


def _handle_get_prometheus_metrics(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Return raw Prometheus exposition-format metrics in a self-describing wrapper.

    T-S-09: the exposition text alone is an unlabelled blob.  ``metrics_text``
    carries the text and ``_text_payload_metadata`` adds machine-readable
    ``format`` / ``content_type`` / ``encoding`` / ``length`` / ``bytes`` keys.
    ``content_type`` is the Prometheus text exposition media type
    (``text/plain; version=0.0.4``), so a consumer can route the payload
    without sniffing the body.
    """
    from autoinfo.metrics import format_prometheus
    from autoinfo.metrics import get_metrics as _get_metrics

    data = _get_metrics()
    metrics_text = format_prometheus(data)
    return {
        **mcp_context._text_payload_metadata(
            metrics_text,
            format="prometheus",
            content_type="text/plain; version=0.0.4; charset=utf-8",
        ),
        "metrics_text": metrics_text,
    }


def _handle_soft_delete_entry(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    from autoinfo.kb import KBStore

    store = KBStore()
    actor = arguments.get("actor") or "agent"
    purge = arguments.get("purge", False)
    try:
        if purge:
            return mcp_context._canonicalize(store.delete_entry(arguments["entry_id"], actor=actor))
        return mcp_context._canonicalize(
            store.soft_delete_entry(arguments["entry_id"], actor=actor)
        )
    except DirectorOnlyError as exc:
        return mcp_context._error_from_exc(
            exc, "soft_delete_entry refused", code=ErrorCode.DIRECTOR_ONLY
        )


def _handle_mark_stale(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    from autoinfo.kb import mark_stale

    return mcp_context._canonicalize(mark_stale(arguments["entry_id"]))


def _handle_restore_entry(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    from autoinfo.kb import KBStore

    store = KBStore()
    return mcp_context._canonicalize(store.restore_entry(arguments["entry_id"]))


def _handle_export_user_data(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    from autoinfo.user_store import get_profile

    profile = get_profile(arguments["user_id"])
    return {"user_id": arguments["user_id"], "profile": profile}


def _handle_delete_user_data(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    from autoinfo.kb import KBStore

    store = KBStore()
    purge = arguments.get("purge", False)
    if not purge:
        return error_response(
            code=ErrorCode.VALIDATION_ERROR,
            message="Must set purge=True for permanent deletion",
            actionable=True,
        )
    return mcp_context._canonicalize(store.delete_user_data(arguments["user_id"]))
