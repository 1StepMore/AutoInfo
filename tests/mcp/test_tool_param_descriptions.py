"""Regression test for issue #974: every MCP tool parameter must carry a
non-empty ``description`` in its ``inputSchema``.

Missing parameter descriptions forced callers (agents especially) to guess
argument semantics on write/sensitive tools (soft_delete_entry, mark_stale,
restore_entry, export_user_data, delete_user_data, find_similar_items) —
guessing wrong there is destructive.
"""

from __future__ import annotations

import pytest

from autoinfo.mcp import server as mcp_server


def _missing_descriptions(tools) -> list[str]:
    """Return ``"<tool>.<param>"`` pairs whose schema lacks a description."""
    offenders: list[str] = []
    for tool in tools:
        schema = tool.inputSchema or {}
        for prop_name, prop in (schema.get("properties") or {}).items():
            if not (prop or {}).get("description", "").strip():
                offenders.append(f"{tool.name}.{prop_name}")
    return offenders


def test_full_tool_list_every_param_has_description() -> None:
    """All declared tools (including the director-only surface) qualify."""
    offenders = _missing_descriptions(mcp_server._full_tool_list())
    assert offenders == [], (
        "MCP tools with parameters missing a non-empty description: "
        + ", ".join(offenders)
    )


@pytest.mark.asyncio
async def test_list_tools_every_param_has_description() -> None:
    """The default-visibility ``tools/list`` surface qualifies too."""
    tools = await mcp_server.list_tools()
    offenders = _missing_descriptions(tools)
    assert offenders == [], (
        "MCP tools with parameters missing a non-empty description: "
        + ", ".join(offenders)
    )


@pytest.mark.asyncio
async def test_issue_974_sensitive_tools_have_descriptions() -> None:
    """Pin the six write/sensitive tools named by issue #974 specifically."""
    tools = {t.name: t for t in await mcp_server.list_tools()}
    for name in (
        "soft_delete_entry",
        "mark_stale",
        "restore_entry",
        "export_user_data",
        "delete_user_data",
        "find_similar_items",
    ):
        tool = tools[name]
        schema = tool.inputSchema or {}
        assert schema.get("properties"), f"{name} declares no parameters"
        for prop_name, prop in schema["properties"].items():
            assert (prop or {}).get("description", "").strip(), (
                f"{name}.{prop_name} is missing a parameter description"
            )
