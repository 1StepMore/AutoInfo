"""Tests for MCP ``call_tool()`` dispatch correctness.

Verifies that tool names route to the correct handler via ``call_tool()``,
not just directly via ``_handle_*`` functions. Catches dispatch bugs like
missing ``elif`` branches or orphaned handler calls that cause:

- UNKNOWN_TOOL errors for valid tool names
- Side-effect pollution (one tool's handler overwriting another's result)

See also:
    - ``test_mcp_init_project.py`` — direct handler tests for ``_handle_init_project``
    - ``test_mcp_server.py`` — direct handler tests for other tools
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from mcp.types import TextContent

from autoinfo.mcp.server import call_tool


class TestInitProjectDispatch:
    """``call_tool("init_project", ...)`` must route to ``_handle_init_project``."""

    async def test_init_project_returns_success_not_unknown_tool(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """After the dispatch fix, init_project should succeed, not UNKNOWN_TOOL."""
        monkeypatch.chdir(tmp_path)
        result_list = await call_tool(
            "init_project",
            {"domain": "medical-research"},
        )
        assert len(result_list) == 1
        assert isinstance(result_list[0], TextContent)
        body = json.loads(result_list[0].text)
        # Success envelope — NOT an error_response
        assert body["success"] is True
        assert body["data"]["status"] == "success"
        assert body["data"]["domain"] == "medical-research"

    async def test_init_project_creates_exactly_one_domain(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A string domain must be treated as ONE domain, never split char-by-char.

        Regression for M0T4: ``_handle_init_project`` passed the bare string to
        ``_run_init`` (which expects ``list[str]``), so "medical-research" was
        iterated into 16 single-char domains and the real domain was never
        created. The MCP tool contract takes ``domain: str`` — one domain per
        call.
        """
        monkeypatch.chdir(tmp_path)

        init_result = await call_tool(
            "init_project",
            {"domain": "medical-research"},
        )
        init_body = json.loads(init_result[0].text)
        assert init_body["success"] is True

        # The generated config must contain exactly one domain: medical-research
        config_path = tmp_path / ".autoinfo" / "config.yaml"
        import yaml

        cfg = yaml.safe_load(config_path.read_text())
        domain_names = [d["name"] for d in cfg["domains"]]
        assert domain_names == ["medical-research"]
        # No single-char domains from iterating the string
        assert all(len(name) > 1 for name in domain_names)

        # And get_domain_webhooks must succeed for the single real domain
        hook_result = await call_tool(
            "get_domain_webhooks",
            {"domain": "medical-research"},
        )
        hook_body = json.loads(hook_result[0].text)
        assert hook_body["success"] is True
        assert hook_body["data"]["domain"] == "medical-research"


class TestGetDomainWebhooksDispatch:
    """``call_tool("get_domain_webhooks", ...)`` must NOT be polluted by init_project."""

    async def test_get_domain_webhooks_not_polluted_by_init_project(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify get_domain_webhooks returns webhook data, not init_project result."""
        monkeypatch.chdir(tmp_path)

        # First initialize the project so the domain config exists
        init_result = await call_tool(
            "init_project",
            {"domain": "medical-research"},
        )
        init_body = json.loads(init_result[0].text)
        assert init_body["success"] is True

        # Now call get_domain_webhooks — before the fix this would
        # accidentally return init_project data due to the orphaned
        # _handle_init_project call on line 5113 (old line number).
        result_list = await call_tool(
            "get_domain_webhooks",
            {"domain": "medical-research"},
        )
        assert len(result_list) == 1
        assert isinstance(result_list[0], TextContent)
        body = json.loads(result_list[0].text)

        # Must be a success response with webhook data
        assert body["success"] is True
        assert "webhook_urls" in body["data"]
        assert body["data"]["domain"] == "medical-research"

        # Must NOT contain init_project-specific fields
        assert "status" not in body["data"]
        assert "autoinfo_dir" not in body["data"]
