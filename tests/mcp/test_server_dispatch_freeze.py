"""Guard: the MCP dispatch chain in ``server.py`` must not grow.

``src/autoinfo/mcp/server.py`` is a ~11.9k-line god module that dispatches all
149 MCP tools through one flat ``if/elif name == "<tool>"`` chain, each branch
calling its own ``_handle_<tool>`` function. Adding a tool therefore means
editing three places in the same file (tool declaration table, dispatch chain,
permission whitelist), which is exactly the change-amplification the planned
registry refactor is meant to remove.

The refactor is deliberately deferred (splitting an 11.9k-line module in one
move would swamp the current known-red baseline). Until it happens this guard
freezes the shape: the dispatch chain and the handler set may not grow. A new
MCP tool must first extract a registry so dispatch and implementation are
decoupled — then this guard's numbers get raised in the same change that
performs the extraction.

Counts are frozen at the 2026-09-17 measurement.

Reference: docs/project-health-assessment-2026-09-17.md §3.1 / §5 action 4.
"""

from __future__ import annotations

import re
from pathlib import Path

SERVER_PY = Path(__file__).resolve().parents[2] / "src" / "autoinfo" / "mcp" / "server.py"

# Frozen shape at 2026-09-17 (149 MCP tools).
FROZEN_DISPATCH_BRANCHES = 149
FROZEN_HANDLERS = 149

_DISPATCH_BRANCH = re.compile(r'^\s*(?:if|elif)\s+name\s*==\s*"', re.MULTILINE)
_HANDLER_DEF = re.compile(r"^(?:async\s+)?def\s+_handle_\w+\s*\(", re.MULTILINE)


def _server_source() -> str:
    """Return server.py's text, skipping the guard when the file is absent."""
    if not SERVER_PY.is_file():
        import pytest

        pytest.skip(f"server.py not found at {SERVER_PY}")
    return SERVER_PY.read_text(encoding="utf-8")


def test_dispatch_chain_does_not_grow() -> None:
    """A new tool must not append another ``if/elif name ==`` branch."""
    branches = len(_DISPATCH_BRANCH.findall(_server_source()))
    assert branches <= FROZEN_DISPATCH_BRANCHES, (
        f"server.py's `if/elif name ==` dispatch chain grew to {branches} branches "
        f"(frozen at {FROZEN_DISPATCH_BRANCHES}). Adding a tool here re-creates the "
        "god-module change amplification. Extract a dispatch registry first, then "
        "raise FROZEN_DISPATCH_BRANCHES in the same change — see "
        "docs/project-health-assessment-2026-09-17.md §5 action 4."
    )


def test_handler_set_does_not_grow() -> None:
    """A new tool must not add another ``_handle_*`` definition either."""
    handlers = len(_HANDLER_DEF.findall(_server_source()))
    assert handlers <= FROZEN_HANDLERS, (
        f"server.py defines {handlers} `_handle_*` functions (frozen at "
        f"{FROZEN_HANDLERS}). Move new handler implementations into their own "
        "module (like collectors/output already do) instead of appending to "
        "server.py — see docs/project-health-assessment-2026-09-17.md §5 action 4."
    )
