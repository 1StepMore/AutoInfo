"""Envelope conformance — T-S-02 (Todo 14).

Every declared MCP tool must return the canonical envelope:

    success: ``{"success": true, "data": ...}``
    failure: ``{"success": false, "error": {"code", "message", "actionable"}}``

This locks the regression floor for the unified envelope:

1. **Static, full coverage** — every ``_handle_*`` function in
   ``server.py`` is AST-checked: no ``Return`` of a dict literal may carry
   a flat ``error_code`` key or a bare ``success`` key without the
   ``data``/``error`` envelope (hybrid shapes are banned outright).
2. **Runtime, representative dispatch** — canonical success, canonical
   error, previously-flat error handlers, and the LLM guard are dispatched
   through ``call_tool`` and the parsed JSON is asserted to have exactly
   the canonical top-level keys.
"""

from __future__ import annotations

import ast
import json
from unittest.mock import patch

import pytest

from autoinfo.mcp import server as mcp_server
from autoinfo.mcp.server import call_tool
from tests.mcp._source_corpus import source_corpus

_CANONICAL_SUCCESS_KEYS = frozenset({"success", "data"})
_CANONICAL_ERROR_KEYS = frozenset({"success", "error"})
_CANONICAL_ERROR_DETAIL_KEYS = frozenset({"code", "message", "actionable"})


def _response_body(out: list[object]) -> dict:
    """Extract the JSON envelope dict from a direct ``call_tool`` result.

    ``call_tool`` returns either the flat ``[TextContent]`` form or the
    (content, structured) tuple form ``([TextContent], dict)`` that the
    output-schema work uses; both must carry the same canonical envelope.
    """
    first = out[0]
    if isinstance(first, list):
        return json.loads(first[0].text)
    if hasattr(first, "text"):
        return json.loads(first.text)
    raise AssertionError(f"unexpected call_tool result shape: {out!r}")


def _handler_returns() -> list[tuple[str, str, int, list[str]]]:
    """Return ``(file, handler_name, lineno, keys)`` for every ``_handle_*``
    function whose return value is a dict literal, across the source corpus."""
    returns: list[tuple[str, str, int, list[str]]] = []
    for path, source in source_corpus():
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("_handle_"):
                continue
            for child in ast.walk(node):
                if not isinstance(child, ast.Return):
                    continue
                value = child.value
                if value is None:
                    continue
                if isinstance(value, ast.IfExp):
                    # return <A> if <cond> else <dict> — inspect the dict branch
                    for branch in (value.body, value.orelse):
                        if isinstance(branch, ast.Dict):
                            returns.append((path.name, node.name, child.lineno, _dict_keys(branch)))
                    continue
                if isinstance(value, ast.Dict):
                    returns.append((path.name, node.name, child.lineno, _dict_keys(value)))
    return returns


def _dict_keys(d: ast.Dict) -> list[str]:
    return [k.value for k in d.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)]


class TestStaticEnvelopeConformance:
    """AST-level check over every handler: zero flat/hybrid return shapes."""

    def test_no_handler_returns_flat_error_dict(self) -> None:
        flat = [
            (name, lineno)
            for _file, name, lineno, keys in _handler_returns()
            if "error_code" in keys
        ]
        assert flat == [], f"Handlers still return flat error dicts (error_code key): {flat}"

    def test_no_handler_returns_bare_success_dict(self) -> None:
        # A dict with a success key but without data/error is a bare/hybrid
        # success shape — must be success_response() instead.
        bare = [
            (file, name, lineno, keys)
            for file, name, lineno, keys in _handler_returns()
            if "success" in keys and not {"data", "error"} & set(keys)
        ]
        assert bare == [], f"Handlers still return bare success dicts: {bare}"

    def test_no_flat_error_key_anywhere_in_mcp_sources(self) -> None:
        # The only legitimate mentions are inside the _canonicalize() boundary
        # helper, which detects legacy flat dicts forwarded from lower-level
        # helpers. Everywhere else the legacy key is banned. The helper is
        # declared several times — the typing.overload stubs plus the
        # implementation — so strip every definition carrying that name rather
        # than an arbitrary first match, which would land on a stub.
        helper_seen = False
        for path, source in source_corpus():
            tree = ast.parse(source)
            helpers = [
                n
                for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "_canonicalize"
            ]
            if not helpers:
                continue
            helper_seen = True
            helper_srcs = [ast.get_source_segment(source, h) or "" for h in helpers]
            # Keep the check from silently going vacuous: the helper itself
            # must still be the place the legacy key is handled.
            assert any("error_code" in src for src in helper_srcs), (
                f"{path.name}: _canonicalize() no longer mentions the legacy flat "
                "key — re-point this test at wherever the legacy-key boundary moved to"
            )
            rest = source
            for helper_src in helper_srcs:
                rest = rest.replace(helper_src, "")
            assert "error_code" not in rest, (
                f"{path.name} references the legacy flat 'error_code' key outside "
                "the _canonicalize() boundary helper"
            )
        assert helper_seen, "no MCP source file defines the _canonicalize() boundary helper"


class TestRuntimeEnvelopeConformance:
    """Dispatch representative success + failure paths through call_tool."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("tool", "args"),
        [
            # previously-flat success entry point (was exempt from wrapping)
            ("health_check", {}),
            ("get_tool_count", {}),
            # previously-flat error handlers (were hybrid-wrapped)
            ("remove_source", {"source_id": "no-colon-here"}),
            ("list_domains", {}),
            ("list_available_models", {}),
            # LLM guard (canonical error envelope from the dispatcher)
            ("classify_cefr", {"text": ""}),
            # unknown tool (canonical error envelope)
            ("unknown_tool_xyz", {}),
        ],
    )
    async def test_dispatch_returns_canonical_envelope(self, tool, args) -> None:
        with patch.object(mcp_server, "_is_llm_configured", return_value=False):
            out = await call_tool(tool, args)
        body = _response_body(out)
        assert isinstance(body, dict), f"{tool}: non-dict response {body!r}"
        assert "success" in body, f"{tool}: missing success key: {body}"
        assert set(body.keys()) in (
            _CANONICAL_SUCCESS_KEYS,
            _CANONICAL_ERROR_KEYS,
        ), f"{tool}: non-canonical envelope keys: {sorted(body)}"
        if body["success"]:
            assert "data" in body and "error" not in body
        else:
            assert "error" in body and "data" not in body
            err = body["error"]
            assert set(err.keys()) == _CANONICAL_ERROR_DETAIL_KEYS, (
                f"{tool}: non-canonical error detail: {sorted(err)}"
            )
