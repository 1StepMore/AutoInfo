"""Dispatch-table parity for the #581 phase-2 extraction.

The former 148-branch ``if name == ...`` chain is now ``_TOOL_DISPATCH``:
``tool name -> (handler name, invocation mode)``.  These tests lock the two
properties that make the table equivalent to the chain:

1. Its keys are exactly the declared ``tools/list`` surface.
2. Every handler resolves to a real callable of the right kind (sync for the
   sync/thread modes, coroutine for ``async``).

Handler names are stored as strings (not callables) on purpose: dispatch
resolves them through module globals at call time, so existing tests that
monkeypatch ``autoinfo.mcp.server._handle_*`` keep working.
"""

from __future__ import annotations

import inspect

import pytest

from autoinfo.mcp import server as mcp_server

VALID_MODES = frozenset({"kwargs", "thread", "noargs", "raw", "thread_noargs", "async"})
VALID_MODES_WITH_KWARGS = frozenset({"kwargs", "thread"})


def test_dispatch_registry_covers_exactly_the_declared_tool_surface() -> None:
    declared = {tool.name for tool in mcp_server._full_tool_list()}
    assert set(mcp_server._TOOL_DISPATCH) == declared


def test_dispatch_registry_has_no_extra_or_missing_tool() -> None:
    declared = {tool.name for tool in mcp_server._full_tool_list()}
    missing = declared - set(mcp_server._TOOL_DISPATCH)
    extra = set(mcp_server._TOOL_DISPATCH) - declared
    assert not missing, f"declared tools without a dispatch entry: {sorted(missing)}"
    assert not extra, f"dispatch entries without a declared tool: {sorted(extra)}"


@pytest.mark.parametrize(
    ("tool", "spec"),
    sorted(mcp_server._TOOL_DISPATCH.items()),
    ids=lambda value: value if isinstance(value, str) else "",
)
def test_dispatch_entry_resolves_to_the_right_handler_kind(
    tool: str, spec: tuple[str, str]
) -> None:
    handler_name, mode = spec
    assert mode in VALID_MODES, f"{tool}: unknown invocation mode {mode!r}"
    assert handler_name.startswith("_handle_"), f"{tool}: unexpected handler {handler_name!r}"

    handler = getattr(mcp_server, handler_name, None)
    assert callable(handler), f"{tool}: {handler_name} is not a callable module global"

    is_coroutine = inspect.iscoroutinefunction(handler)
    assert is_coroutine is (mode == "async"), (
        f"{tool}: mode {mode!r} but {handler_name} "
        f"{'is' if is_coroutine else 'is not'} a coroutine function"
    )


def test_invoke_tool_resolves_handler_through_module_globals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The table stores names, so monkeypatching the module global still works."""
    seen: list[str] = []

    def fake_health_check() -> dict[str, object]:
        seen.append("called")
        return {"status": "ok"}

    monkeypatch.setitem(mcp_server.__dict__, "_handle_health_check", fake_health_check)

    import asyncio

    result = asyncio.run(
        mcp_server._invoke_tool(("_handle_health_check", "noargs"), "health_check", {})
    )
    assert result == {"status": "ok"}
    assert seen == ["called"]


def test_unknown_tool_is_not_in_the_registry() -> None:
    assert "definitely_not_a_real_tool" not in mcp_server._TOOL_DISPATCH
