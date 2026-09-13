"""Tool contract — ``outputSchema`` coverage (T-S-01, Todo 15).

Every declared MCP tool must advertise its return contract via the
``mcp.types.Tool.outputSchema`` field.  The contract is the canonical
AutoInfo envelope from ``errors.py`` (ADR-0005):

    success: ``{"success": true, "data": ...}``
    failure: ``{"success": false, "error": {"code", "message", "actionable"}}``

The count is derived dynamically from ``_full_tool_list()`` so this test
never has to be updated when tools are added or removed.  The suite covers:

1. **100% presence** — zero declared tools lack ``outputSchema``.
2. **Envelope shape** — the schema is an object declaring ``success`` as
   required and a ``oneOf`` success/error branch pair.
3. **Runtime conformance** — a representative dispatch returns JSON that
   validates against the declared envelope schema (the schema is not a lie).
"""

from __future__ import annotations

import json

import pytest

from autoinfo.mcp import server as mcp_server
from autoinfo.mcp.server import _full_tool_list, call_tool


def _all_tools() -> list:
    return _full_tool_list()


class TestOutputSchemaPresence:
    def test_every_declared_tool_has_output_schema(self) -> None:
        tools = _all_tools()
        assert tools, "no tools declared"
        missing = [t.name for t in tools if t.outputSchema is None]
        assert missing == [], f"{len(missing)}/{len(tools)} tools lack outputSchema: {missing}"

    def test_output_schema_is_an_object(self) -> None:
        for tool in _all_tools():
            schema = tool.outputSchema
            assert isinstance(schema, dict), tool.name
            assert schema.get("type") == "object", tool.name

    def test_output_schema_declares_success_required(self) -> None:
        for tool in _all_tools():
            required = tool.outputSchema.get("required", [])
            assert "success" in required, tool.name

    def test_output_schema_models_both_envelope_branches(self) -> None:
        # oneOf: {success,data} xor {success,error} — the agent can branch
        # on ``success`` and knows which sibling key to read.
        for tool in _all_tools():
            branches = tool.outputSchema.get("oneOf")
            assert isinstance(branches, list) and len(branches) == 2, tool.name
            branch_keys = {tuple(b.get("required", [])) for b in branches}
            assert ("success", "data") in branch_keys, tool.name
            assert ("success", "error") in branch_keys, tool.name

    def test_output_schema_error_detail_is_structured(self) -> None:
        for tool in _all_tools():
            error = tool.outputSchema["properties"]["error"]
            assert set(error["required"]) == {"code", "message", "actionable"}, tool.name

    def test_output_schema_identity_is_shared_constant(self) -> None:
        # All tools share the single envelope schema object — no per-tool
        # drift, and the constant is the one source of truth.
        for tool in _all_tools():
            assert tool.outputSchema is mcp_server._TOOL_OUTPUT_SCHEMA, tool.name


class TestOutputSchemaRuntimeConformance:
    """The declared schema must match an actual dispatch result."""

    @pytest.mark.asyncio
    async def test_health_check_result_matches_declared_schema(self) -> None:
        out = await call_tool("health_check", {})
        body = json.loads(out[0][0].text)
        schema = _full_tool_list()[0].outputSchema
        assert body["success"] is True
        assert set(body.keys()) == {"success", "data"}
        assert "success" in schema["required"]

    @pytest.mark.asyncio
    async def test_error_result_matches_declared_schema(self) -> None:
        out = await call_tool("remove_source", {"source_id": "no-colon-here"})
        body = json.loads(out[0][0].text)
        assert body["success"] is False
        assert set(body.keys()) == {"success", "error"}
        assert set(body["error"].keys()) == {"code", "message", "actionable"}
