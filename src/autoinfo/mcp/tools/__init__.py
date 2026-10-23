"""MCP tool schema registry (#581 phase 1).

``CATEGORY_BUILDERS`` preserves the original ``_full_tool_list`` registration
order exactly; ``build_all_tools()`` returns fresh Tool objects each call.
"""

from __future__ import annotations

from collections.abc import Callable

from mcp.types import Tool

from autoinfo.mcp.tools import (
    config_admin,
    enduser,
    enduser_billing,
    kb_lifecycle,
    knowledge,
    misc,
    ops,
    output,
    qa,
    runtime,
    scheduling,
    sources,
    system,
)

CATEGORY_BUILDERS: tuple[Callable[[], list[Tool]], ...] = (
    system.build_tools,  # System + Discovery
    sources.build_tools,  # Sources, topics, keywords, collection
    knowledge.build_tools,  # Knowledge base + graph + draft tools
    output.build_tools,  # Output, export/import, email, custom extraction
    scheduling.build_tools,  # Schedules + delivery schedules
    qa.build_tools,  # Q&A + source health
    ops.build_tools,  # Audit, CEFR, project/batch config
    config_admin.build_tools,  # Webhooks, gate config, product
    enduser.build_tools,  # End-user delivery, alerts, budget, cost
    runtime.build_tools,  # Init, metrics, soft-delete/GDPR
    kb_lifecycle.build_tools,  # Trace, merge, similarity, KB freshness
    enduser_billing.build_tools,  # Portal, delivery logs, trials, billing
    misc.build_tools,  # Cache, channel health, callbacks, validation
)


def build_all_tools() -> list[Tool]:
    """Build every MCP tool schema in the original registration order."""
    tools: list[Tool] = []
    for build in CATEGORY_BUILDERS:
        tools.extend(build())
    return tools
