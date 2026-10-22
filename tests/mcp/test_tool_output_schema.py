"""Tool contract — the canonical envelope is documented once (ADR 0010).

``tools/list`` deliberately does **not** advertise an ``outputSchema``.  Before
#588 every tool carried the same envelope schema, repeated 149 times: it cost
58.6% of the payload and added no per-tool information.  The envelope contract
lives in ``docs/dev/specs/mcp-tools.md`` (and ADR 0010); per-tool schemas are a
follow-up once the tool registry lands (#581).

These tests pin the new contract:
1. no declared tool advertises ``outputSchema``;
2. a dispatch still returns the documented envelope shape;
3. the decoration layer still injects param aliases + the director marker.
"""

from __future__ import annotations

import json

import pytest

from autoinfo.mcp.server import DIRECTOR_ONLY_MARKER, _full_tool_list, call_tool


def _all_tools() -> list:
    return _full_tool_list()


class TestNoSharedOutputSchema:
    def test_no_tool_advertises_output_schema(self) -> None:
        tools = _all_tools()
        assert tools, "no tools declared"
        advertised = [t.name for t in tools if t.outputSchema is not None]
        assert advertised == [], (
            f"outputSchema re-added to {len(advertised)} tools: {advertised[:5]}"
        )

    def test_legacy_shared_schema_is_gone(self) -> None:
        import autoinfo.mcp.server as server

        assert not hasattr(server, "_TOOL_OUTPUT_SCHEMA")


class TestEnvelopeRuntimeConformance:
    """The documented envelope must match an actual dispatch result."""

    @pytest.mark.asyncio
    async def test_success_envelope(self) -> None:
        out = await call_tool("health_check", {})
        body = json.loads(out[0][0].text)
        assert body["success"] is True
        assert set(body.keys()) == {"success", "data"}

    @pytest.mark.asyncio
    async def test_error_envelope(self) -> None:
        out = await call_tool("remove_source", {"source_id": "no-colon-here"})
        body = json.loads(out[0][0].text)
        assert body["success"] is False
        assert set(body.keys()) == {"success", "error"}
        assert set(body["error"].keys()) == {"code", "message", "actionable"}


class TestDecorationStillRuns:
    def test_param_alias_is_injected(self) -> None:
        with_alias = [
            tool for tool in _all_tools() if "user_id" in tool.inputSchema.get("properties", {})
        ]
        assert with_alias, "expected at least one tool with user_id"
        for tool in with_alias:
            props = tool.inputSchema["properties"]
            assert "end_user_id" in props, tool.name

    def test_director_marker_is_injected(self) -> None:
        marked = [
            tool for tool in _all_tools() if tool.inputSchema.get(DIRECTOR_ONLY_MARKER) is True
        ]
        assert marked, "expected at least one director-only tool"
