"""Agent-native MCP validation toolset.

Provides scenario loading, listing, and execution for validating MCP tool
behavior at runtime.  Each scenario is a YAML file in ``scenarios/`` that
defines a sequence of tool-call steps with expected envelope assertions.

This module is standalone — it does NOT import from ``autoinfo.mcp.server``
to avoid circular dependencies.  Dispatch is injected as a callable.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Awaitable, Callable

import yaml

SCENARIOS_DIR: Path = Path(__file__).resolve().parent / "scenarios"


def _run_cli_step(command: str, timeout: float = 180.0) -> dict[str, Any]:
    """Execute a CLI command in a real subprocess and normalize to an envelope.

    Returns ``{"success": exit_code == 0, "data": {exit_code, stdout, stderr}}``.
    Real process execution — never mocked.  Raises on timeout.
    """
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return {
        "success": result.returncode == 0,
        "data": {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        },
    }


def _run_http_step(
    method: str,
    url: str,
    timeout: float = 60.0,
    **kwargs: Any,
) -> dict[str, Any]:
    """Perform a real HTTP request and normalize to an envelope.

    Returns ``{"success": 2xx/3xx, "data": {status_code, json, text}}``.
    Real network call — never mocked.  Raises on connection error.
    """
    import httpx  # noqa: PLC0415 — deferred import

    resp = httpx.request(method.upper(), url, timeout=timeout, **kwargs)
    try:
        body = resp.json()
    except Exception:
        body = None
    return {
        "success": 200 <= resp.status_code < 400,
        "data": {
            "status_code": resp.status_code,
            "json": body,
            "text": resp.text,
        },
    }

# ---------------------------------------------------------------------------
# LLM semantic judging (llm_assert) — real calls only, never mocked.
# Unconfigured LLM ⇒ step reports ``unconfigured`` (Director User BYOK
# obligation), never silently skipped.
# ---------------------------------------------------------------------------


def _is_llm_configured() -> bool:
    """Return ``True`` when a real LLM API key is available.

    Mirrors ``server._is_llm_configured`` but resolves ``${ENV_VAR}``
    references in ``config.llm.api_key`` so a placeholder value without
    an actual environment variable does not count as configured.
    """
    from autoinfo.config import get_config_path, load_config  # noqa: PLC0415

    try:
        config_path = get_config_path()
        if config_path:
            config = load_config(config_path)
            key = config.llm.api_key
            if key:
                if isinstance(key, str) and key.startswith("${") and key.endswith("}"):
                    return bool(os.environ.get(key[2:-1]))
                return True
    except Exception:
        pass
    return bool(os.environ.get("AUTOINFO_LLM_API_KEY"))


def _resolve_llm_config() -> dict[str, Any]:
    """Resolve the LLM call config from the project config.

    Returns ``{"model", "api_key", "api_base"}``.  ``model`` keeps its
    configured form (already prefixed with provider when configured that
    way); ``api_key`` comes from the config (with ``${ENV}`` references
    resolved by the config loader) or the ``AUTOINFO_LLM_API_KEY`` env var.
    """
    from autoinfo.config import Config, get_config_path, load_config  # noqa: PLC0415

    try:
        config_path = get_config_path()
        config = load_config(config_path) if config_path else Config()
    except Exception:
        config = Config()

    provider = config.llm.provider or "openrouter"
    model = config.llm.model or "deepseek/deepseek-chat"
    if "/" not in model:
        model = f"{provider}/{model}"
    api_key = config.llm.api_key or os.environ.get("AUTOINFO_LLM_API_KEY", "")
    return {
        "model": model,
        "api_key": api_key,
        "api_base": config.llm.base_url or None,
    }


def _resolve_llm_model() -> str:
    """Resolve the LLM model string from config, falling back to defaults.

    Same pattern as ``quality._resolve_llm_model``.
    """
    return _resolve_llm_config()["model"]


def _parse_llm_verdict(content: str | None) -> dict[str, Any]:
    """Parse the judge LLM response into ``{"verdict", "reason"}``.

    Tolerates bare JSON and ```json fenced blocks.  Raises ValueError on
    unexpected content so a broken judge response surfaces as FAIL.
    """
    if not content:
        raise ValueError("LLM judge returned empty content")
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError(f"LLM judge returned non-JSON: {content[:200]!r}")
    data = json.loads(text[start : end + 1])
    verdict = str(data.get("verdict", "")).strip().upper()
    if verdict not in ("PASS", "FAIL"):
        raise ValueError(f"Unexpected LLM verdict: {verdict!r}")
    return {"verdict": verdict, "reason": str(data.get("reason", ""))}


def _llm_judge(assertion: str, tool_output: Any) -> dict[str, Any]:
    """Judge tool output against a natural-language assertion using a real
    LLM call (LiteLLM completion — the same path G4/G5 use).

    Returns ``{"verdict": "PASS"|"FAIL", "reason": str}``.

    Raises
    ------
    RuntimeError
        If litellm is unavailable or every configured model fails.
    ValueError
        If the judge response cannot be parsed.
    """
    import litellm  # noqa: PLC0415 — deferred import (same as llm.py)

    llm_cfg = _resolve_llm_config()
    prompt = (
        "You are a validation judge for the AutoInfo platform. Determine "
        "whether the assertion holds for the given tool output.\n\n"
        f"ASSERTION:\n{assertion}\n\n"
        f"TOOL OUTPUT (JSON):\n{json.dumps(tool_output, ensure_ascii=False)[:8000]}\n\n"
        'Reply with JSON exactly: {"verdict": "PASS" or "FAIL", '
        '"reason": "one-sentence justification"}'
    )
    response = litellm.completion(
        model=llm_cfg["model"],
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500,
        temperature=0.0,
        api_base=llm_cfg["api_base"],
        api_key=llm_cfg["api_key"] or None,
    )
    content = response.choices[0].message.content  # type: ignore[union-attr]
    return _parse_llm_verdict(content)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_envelope(env: dict[str, Any]) -> dict[str, Any]:
    """Normalize a potential flat response into the standard envelope shape.

    Some tools (notably ``health_check``) return a flat dict without a
    ``success`` key because they bypass the standard ``call_tool`` wrapping.
    This helper transparently wraps flat responses so that assertion logic
    always operates on a uniform ``{success, data|error}`` envelope.
    """
    if "success" in env:
        return env  # already canonical envelope

    # Health-like flat responses have a "status" key (e.g. health_check)
    # but no "success" key.  Treat these as implicit success.
    return {"success": True, "data": env}


def _step_assert(
    step_name: str,
    tool: str,
    env: dict[str, Any],
    expect: dict[str, Any],
) -> dict[str, Any]:
    """Run assertions on a single tool-call envelope and return a step result.

    Supports the canonical envelope fields (``success`` / ``data_has`` /
    ``error_code``) plus surface-specific fields:

    - CLI (``kind: cli``): ``exit_code``, ``stdout_has``, ``stderr_has``
    - HTTP (``kind: http``): ``status_code``, ``json_has``
    """
    expected_success = expect.get("success", True)

    if env.get("success") != expected_success:
        return {
            "name": step_name,
            "tool": tool,
            "status": "failed",
            "detail": (
                f"expected success={expected_success}, "
                f"got success={env.get('success')}: {env}"
            ),
        }

    if expected_success:
        data = env.get("data")

        data_has = expect.get("data_has")
        if data_has is not None:
            if not isinstance(data, dict):
                return {
                    "name": step_name,
                    "tool": tool,
                    "status": "failed",
                    "detail": (
                        f"expected data_has={data_has} but data is not a dict: "
                        f"got {type(data).__name__}"
                    ),
                }
            missing = [k for k in data_has if k not in data]
            if missing:
                return {
                    "name": step_name,
                    "tool": tool,
                    "status": "failed",
                    "detail": (
                        f"data_has keys missing: {missing}. "
                        f"Available keys: {list(data.keys())}"
                    ),
                }

        exit_code = expect.get("exit_code")
        if exit_code is not None and isinstance(data, dict):
            actual = data.get("exit_code")
            if actual != exit_code:
                return {
                    "name": step_name,
                    "tool": tool,
                    "status": "failed",
                    "detail": (
                        f"expected exit_code={exit_code}, got {actual}. "
                        f"stderr: {data.get('stderr', '')[:500]}"
                    ),
                }

        stdout_has = expect.get("stdout_has")
        if stdout_has is not None and isinstance(data, dict):
            stdout = data.get("stdout", "")
            missing = [s for s in stdout_has if s not in stdout]
            if missing:
                return {
                    "name": step_name,
                    "tool": tool,
                    "status": "failed",
                    "detail": (
                        f"stdout missing substrings: {missing}. "
                        f"stdout: {stdout[:500]}"
                    ),
                }

        stderr_has = expect.get("stderr_has")
        if stderr_has is not None and isinstance(data, dict):
            stderr = data.get("stderr", "")
            missing = [s for s in stderr_has if s not in stderr]
            if missing:
                return {
                    "name": step_name,
                    "tool": tool,
                    "status": "failed",
                    "detail": (
                        f"stderr missing substrings: {missing}. "
                        f"stderr: {stderr[:500]}"
                    ),
                }

        status_code = expect.get("status_code")
        if status_code is not None and isinstance(data, dict):
            actual = data.get("status_code")
            if actual != status_code:
                return {
                    "name": step_name,
                    "tool": tool,
                    "status": "failed",
                    "detail": (
                        f"expected status_code={status_code}, got {actual}. "
                        f"body: {data.get('text', '')[:500]}"
                    ),
                }

        json_has = expect.get("json_has")
        if json_has is not None and isinstance(data, dict):
            body = data.get("json")
            if not isinstance(body, dict):
                return {
                    "name": step_name,
                    "tool": tool,
                    "status": "failed",
                    "detail": (
                        f"expected json_has={json_has} but body is not a dict: "
                        f"got {type(body).__name__}: {data.get('text', '')[:300]}"
                    ),
                }
            missing = [k for k in json_has if k not in body]
            if missing:
                return {
                    "name": step_name,
                    "tool": tool,
                    "status": "failed",
                    "detail": (
                        f"json_has keys missing: {missing}. "
                        f"Available keys: {list(body.keys())}"
                    ),
                }
    else:
        # expected_success == False — check error_code if specified
        error_code = expect.get("error_code")
        if error_code is not None:
            error = env.get("error", {})
            actual = error.get("code") if isinstance(error, dict) else None
            if actual != error_code:
                return {
                    "name": step_name,
                    "tool": tool,
                    "status": "failed",
                    "detail": (
                        f"expected error_code={error_code}, "
                        f"got {actual}: {env}"
                    ),
                }

    return {
        "name": step_name,
        "tool": tool,
        "status": "passed",
        "detail": env,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_scenarios(scenarios_dir: Path | None = None) -> list[dict[str, Any]]:
    """Load all ``*.yaml`` scenario files, sorted by filename.

    Parameters
    ----------
    scenarios_dir:
        Directory containing scenario YAML files.  Defaults to the built-in
        ``scenarios/`` directory next to this module.

    Returns
    -------
    list[dict]
        Each dict has ``name``, ``description``, ``steps``, and optionally
        ``category`` / ``requires_env``.

    Raises
    ------
    ValueError
        If a YAML file cannot be parsed, or if a scenario is missing the
        required ``name``, ``description``, or ``steps`` fields, or if any
        step is missing ``name`` or ``tool``.
    """
    sd = scenarios_dir or SCENARIOS_DIR
    scenarios: list[dict[str, Any]] = []

    if not sd.is_dir():
        return scenarios

    for yaml_path in sorted(sd.glob("*.yaml")):
        try:
            with open(yaml_path, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
        except yaml.YAMLError as exc:
            raise ValueError(f"Failed to parse {yaml_path.name}: {exc}") from exc

        if not isinstance(data, dict):
            raise ValueError(
                f"Scenario file {yaml_path.name} must contain a YAML mapping "
                f"(got {type(data).__name__})"
            )

        # Validate required top-level fields
        for field in ("name", "description", "steps"):
            if field not in data:
                raise ValueError(
                    f"Scenario file {yaml_path.name} is missing required "
                    f"field: '{field}'"
                )

        steps = data["steps"]
        if not isinstance(steps, list) or len(steps) == 0:
            raise ValueError(
                f"Scenario file {yaml_path.name}: 'steps' must be a non-empty list"
            )

        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                raise ValueError(
                    f"Scenario file {yaml_path.name}, step[{i}]: "
                    f"must be a mapping, got {type(step).__name__}"
                )
            if "name" not in step:
                raise ValueError(
                    f"Scenario file {yaml_path.name}, step[{i}]: "
                    f"missing required field 'name'"
                )
            kind = step.get("kind", "mcp")
            if kind == "cli":
                if "command" not in step:
                    raise ValueError(
                        f"Scenario file {yaml_path.name}, step[{i}] (kind=cli): "
                        f"missing required field 'command'"
                    )
            elif kind == "http":
                for field in ("method", "url"):
                    if field not in step:
                        raise ValueError(
                            f"Scenario file {yaml_path.name}, step[{i}] "
                            f"(kind=http): missing required field '{field}'"
                        )
            else:
                if "tool" not in step:
                    raise ValueError(
                        f"Scenario file {yaml_path.name}, step[{i}] (kind=mcp): "
                        f"missing required field 'tool'"
                    )

        # Set defaults for optional fields
        data.setdefault("category", "general")
        data.setdefault("requires_env", [])
        for step in steps:
            step.setdefault("arguments", {})
            step.setdefault("expect", {})

        scenarios.append(data)

    return scenarios


def list_scenarios(scenarios_dir: Path | None = None) -> dict[str, Any]:
    """Return a summary of all available validation scenarios.

    Returns
    -------
    dict
        ``{"scenarios": [{name, description, category, step_count, requires_env},
        ...], "count": N}``
    """
    scs = load_scenarios(scenarios_dir)
    return {
        "scenarios": [
            {
                "name": sc["name"],
                "description": sc["description"],
                "category": sc.get("category", "general"),
                "step_count": len(sc["steps"]),
                "requires_env": sc.get("requires_env", []),
            }
            for sc in scs
        ],
        "count": len(scs),
    }


async def run_scenario(
    name: str,
    dispatch: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]],
    steps: list[int] | None = None,
    scenarios_dir: Path | None = None,
) -> dict[str, Any]:
    """Execute a named validation scenario against the given dispatch function.

    Parameters
    ----------
    name:
        Scenario name (must match the ``name`` field of exactly one scenario file).
    dispatch:
        Async callable ``(tool_name, arguments) -> envelope dict``.
        The returned dict is expected to be a parsed JSON envelope
        ``{success, data}`` or ``{success, error}``.  Flat responses
        (e.g. from ``health_check``) are transparently normalised.
    steps:
        Optional list of 1-based step indices to run.  When provided, only
        those steps are executed; summary counts reflect only the executed
        steps.
    scenarios_dir:
        Directory to load scenarios from.  Defaults to the built-in
        ``scenarios/`` directory.

    Returns
    -------
    dict
        ``{"scenario", "description", "category", "status", "summary",
        "steps", ("unconfigured_reason")}``

    Raises
    ------
    ValueError
        If *name* does not match any loaded scenario, or if a *steps* index
        is out of range.
    """
    scs = load_scenarios(scenarios_dir)
    scenario = next((sc for sc in scs if sc["name"] == name), None)

    if scenario is None:
        available = ", ".join(sorted(sc["name"] for sc in scs))
        raise ValueError(
            f"Unknown validation scenario: {name}. Available: {available}"
        )

    requires_env: list[str] = scenario.get("requires_env", [])
    missing_env = [v for v in requires_env if not os.environ.get(v)]
    if missing_env:
        all_steps = scenario["steps"]
        unconfigured_steps = [
            {
                "name": s["name"],
                "tool": s.get("tool") or s.get("command") or s.get("url", ""),
                "status": "unconfigured",
                "detail": (
                    f"missing required env var(s): {', '.join(missing_env)}. "
                    "Director User must configure these during onboarding "
                    "(BYOK — see docs/dev/required-api-keys.md)."
                ),
            }
            for s in all_steps
        ]
        return {
            "scenario": name,
            "description": scenario["description"],
            "category": scenario.get("category", "general"),
            "status": "unconfigured",
            "unconfigured_reason": (
                f"missing required env var(s): {', '.join(missing_env)}. "
                "Director User must configure these during onboarding "
                "(BYOK — see docs/dev/required-api-keys.md)."
            ),
            "summary": {
                "passed": 0,
                "failed": 0,
                "unconfigured": len(unconfigured_steps),
                "total": len(unconfigured_steps),
            },
            "steps": unconfigured_steps,
        }

    # Determine which steps to run
    if steps is not None:
        if not steps:
            raise ValueError("steps list must not be empty when provided")
        max_idx = len(scenario["steps"])
        for idx in steps:
            if idx < 1 or idx > max_idx:
                raise ValueError(
                    f"Step index {idx} out of range (1-{max_idx}) for "
                    f"scenario '{name}'"
                )
        selected = [(idx, scenario["steps"][idx - 1]) for idx in steps]
    else:
        selected = [(i + 1, s) for i, s in enumerate(scenario["steps"])]

    step_results: list[dict[str, Any]] = []
    passed = 0
    failed = 0
    unconfigured = 0

    for step_idx, step_def in selected:
        expect = step_def.get("expect", {})
        kind = step_def.get("kind", "mcp")
        label = step_def["name"]
        tool_ref = step_def.get("tool") or step_def.get("command") or step_def.get("url", kind)

        try:
            if kind == "cli":
                env = await asyncio.to_thread(
                    _run_cli_step, step_def["command"]
                )
            elif kind == "http":
                env = await asyncio.to_thread(
                    _run_http_step,
                    step_def.get("method", "GET"),
                    step_def["url"],
                    **step_def.get("http_options", {}),
                )
            else:
                env = await dispatch(step_def["tool"], step_def.get("arguments", {}))
                if isinstance(env, dict):
                    env = _normalize_envelope(env)
        except Exception as exc:
            step_results.append({
                "name": label,
                "tool": tool_ref,
                "status": "failed",
                "detail": f"dispatch exception: {exc}",
            })
            failed += 1
            continue

        sr = _step_assert(
            label,
            tool_ref,
            env,
            expect,
        )

        llm_assert = expect.get("llm_assert")
        if sr["status"] == "passed" and llm_assert:
            if not _is_llm_configured():
                sr = {
                    "name": label,
                    "tool": tool_ref,
                    "status": "unconfigured",
                    "detail": (
                        "llm_assert requires a real LLM API key, but none is "
                        "configured. Director User must run configure_llm() / "
                        "set AUTOINFO_LLM_API_KEY during onboarding (BYOK)."
                    ),
                }
                unconfigured += 1
            else:
                try:
                    verdict = await asyncio.to_thread(
                        _llm_judge, llm_assert, env.get("data")
                    )
                    if verdict["verdict"] == "PASS":
                        sr = {
                            "name": label,
                            "tool": tool_ref,
                            "status": "passed",
                            "detail": env,
                            "llm_reason": verdict["reason"],
                        }
                        passed += 1
                    else:
                        sr = {
                            "name": label,
                            "tool": tool_ref,
                            "status": "failed",
                            "detail": (
                                f"llm_assert FAILED: {verdict['reason']}. "
                                f"Tool output: {json.dumps(env, ensure_ascii=False)[:2000]}"
                            ),
                            "llm_reason": verdict["reason"],
                        }
                        failed += 1
                except Exception as exc:
                    sr = {
                        "name": label,
                        "tool": tool_ref,
                        "status": "failed",
                        "detail": f"llm_assert error: {exc}",
                    }
                    failed += 1
        elif sr["status"] == "passed":
            passed += 1
        elif sr["status"] == "unconfigured":
            unconfigured += 1
        else:
            failed += 1

        step_results.append(sr)

    if failed > 0:
        status = "failed"
    elif unconfigured > 0:
        status = "unconfigured"
    else:
        status = "passed"

    return {
        "scenario": name,
        "description": scenario["description"],
        "category": scenario.get("category", "general"),
        "status": status,
        "summary": {
            "passed": passed,
            "failed": failed,
            "unconfigured": unconfigured,
            "total": len(step_results),
        },
        "steps": step_results,
    }
