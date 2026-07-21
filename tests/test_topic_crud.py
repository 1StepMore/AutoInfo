"""Tests for Topic CRUD — CLI commands and MCP handlers.

Covers:
    - ``autoinfo topics add`` CLI command
    - ``autoinfo topics list`` CLI command
    - ``autoinfo topics remove`` CLI command
    - Idempotency (re-adding same topic is a no-op)
    - Error cases (domain not found, topic not found, no config)
    - MCP ``_handle_add_topic`` handler
    - MCP ``_handle_remove_topic`` handler
    - MCP ``_handle_list_topics`` handler
    - MCP tool registration for ``list_topics``
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
import yaml
from mcp.types import CallToolRequest, CallToolRequestParams

from autoinfo.mcp.server import (
    _handle_add_topic,
    _handle_list_topics,
    _handle_remove_topic,
)

if TYPE_CHECKING:
    from typer.testing import CliRunner


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def cli_runner() -> CliRunner:
    """Return a CliRunner instance."""
    from typer.testing import CliRunner

    return CliRunner()


@pytest.fixture
def app() -> Any:
    """Return the AutoInfo CLI app."""
    from autoinfo.cli import app

    return app


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Create a temporary project with an initial config (no topics)."""
    config_dir = tmp_path / ".autoinfo"
    config_dir.mkdir(parents=True, exist_ok=True)

    config = {
        "project": {"name": "Test Project", "created_at": "2026-07-01"},
        "llm": {
            "provider": "openrouter",
            "model": "deepseek/deepseek-chat",
            "api_key": "test-key",
        },
        "domains": [
            {
                "name": "medical-research",
                "active": True,
                "sources": [
                    {
                        "name": "pubmed",
                        "type": "api",
                        "url": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/",
                        "quality_tier": 1,
                    }
                ],
                "topics": [],
            },
            {
                "name": "ai-commercial",
                "active": True,
                "sources": [],
                "topics": [{"name": "LLM trends", "keywords": ["LLM", "GPT"]}],
            },
        ],
    }

    config_path = config_dir / "config.yaml"
    with open(config_path, "w", encoding="utf-8") as fh:
        yaml.dump(config, fh, default_flow_style=False)

    return tmp_path


# ======================================================================
# CLI: autoinfo topics add
# ======================================================================


class TestTopicsAddCLI:
    def test_add_topic_success(self, cli_runner: Any, app: Any, tmp_project: Path) -> None:
        """Adding a new topic persists it to config and prints confirmation."""
        with patch("pathlib.Path.cwd", return_value=tmp_project):
            result = cli_runner.invoke(
                app,
                [
                    "topics",
                    "add",
                    "--domain",
                    "medical-research",
                    "--name",
                    "IVF breakthroughs",
                    "--keywords",
                    "IVF,embryo",
                ],
                catch_exceptions=False,
            )
        assert result.exit_code == 0
        assert "Added topic" in result.stdout
        assert "IVF breakthroughs" in result.stdout

        # Verify config was written
        config_path = tmp_project / ".autoinfo" / "config.yaml"
        with open(config_path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
        topics = raw["domains"][0]["topics"]
        assert len(topics) == 1
        assert topics[0]["name"] == "IVF breakthroughs"
        assert topics[0]["keywords"] == ["IVF", "embryo"]

    def test_add_topic_idempotent(self, cli_runner: Any, app: Any, tmp_project: Path) -> None:
        """Adding the same topic name+domain again is a no-op."""
        # First add
        with patch("pathlib.Path.cwd", return_value=tmp_project):
            cli_runner.invoke(
                app,
                ["topics", "add", "--domain", "medical-research", "--name", "IVF", "--keywords", "IVF"],
                catch_exceptions=False,
            )
        # Second add (same)
        with patch("pathlib.Path.cwd", return_value=tmp_project):
            result = cli_runner.invoke(
                app,
                ["topics", "add", "--domain", "medical-research", "--name", "IVF", "--keywords", "IVF,embryo"],
                catch_exceptions=False,
            )
        assert result.exit_code == 0
        assert "already exists" in result.stdout

        # Still exactly one topic
        config_path = tmp_project / ".autoinfo" / "config.yaml"
        with open(config_path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
        topics = raw["domains"][0]["topics"]
        assert len(topics) == 1

    def test_add_topic_domain_not_found(self, cli_runner: Any, app: Any, tmp_project: Path) -> None:
        """Adding a topic to a non-existent domain prints an error."""
        result = cli_runner.invoke(
            app,
            ["topics", "add", "--domain", "nonexistent", "--name", "Test", "--keywords", "a"],
            catch_exceptions=False,
        )
        assert result.exit_code == 1
        assert "not configured" in result.stdout

    def test_add_topic_no_config(self, cli_runner: Any, app: Any, tmp_path: Path) -> None:
        """Running topics add without a config file exits gracefully."""
        with patch("pathlib.Path.cwd", return_value=tmp_path):
            result = cli_runner.invoke(
                app,
                ["topics", "add", "--domain", "x", "--name", "Test", "--keywords", "a"],
            )
            assert result.exit_code == 1
            assert "Run 'autoinfo init' first" in result.stdout


# ======================================================================
# CLI: autoinfo topics list
# ======================================================================


class TestTopicsListCLI:
    def test_list_topics_success(self, cli_runner: Any, app: Any, tmp_project: Path) -> None:
        """List shows all topics for a domain."""
        # Add two topics first
        with patch("pathlib.Path.cwd", return_value=tmp_project):
            cli_runner.invoke(
                app,
                ["topics", "add", "--domain", "medical-research", "--name", "IVF", "--keywords", "IVF,embryo"],
                catch_exceptions=False,
            )
            cli_runner.invoke(
                app,
                ["topics", "add", "--domain", "medical-research", "--name", "Gene therapy", "--keywords", "CRISPR,gene"],
                catch_exceptions=False,
            )

            result = cli_runner.invoke(
                app,
                ["topics", "list", "--domain", "medical-research"],
                catch_exceptions=False,
            )
        assert result.exit_code == 0
        assert "IVF" in result.stdout
        assert "Gene therapy" in result.stdout
        assert "IVF, embryo" in result.stdout or "IVF,embryo" in result.stdout

    def test_list_topics_empty(self, cli_runner: Any, app: Any, tmp_project: Path) -> None:
        """Domain with no topics shows 'No topics configured'."""
        with patch("pathlib.Path.cwd", return_value=tmp_project):
            result = cli_runner.invoke(
                app,
                ["topics", "list", "--domain", "medical-research"],
                catch_exceptions=False,
            )
        assert result.exit_code == 0
        assert "No topics configured" in result.stdout

    def test_list_topics_domain_not_found(self, cli_runner: Any, app: Any, tmp_project: Path) -> None:
        """Listing topics for a non-existent domain prints an error."""
        result = cli_runner.invoke(
            app,
            ["topics", "list", "--domain", "nonexistent"],
            catch_exceptions=False,
        )
        assert result.exit_code == 1
        assert "not configured" in result.stdout

    def test_list_topics_no_config(self, cli_runner: Any, app: Any, tmp_path: Path) -> None:
        """Running topics list without a config file exits gracefully."""
        with patch("pathlib.Path.cwd", return_value=tmp_path):
            result = cli_runner.invoke(app, ["topics", "list", "--domain", "x"])
            assert result.exit_code == 1
            assert "Run 'autoinfo init' first" in result.stdout


# ======================================================================
# CLI: autoinfo topics remove
# ======================================================================


class TestTopicsRemoveCLI:
    def test_remove_topic_success(self, cli_runner: Any, app: Any, tmp_project: Path) -> None:
        """Removing an existing topic deletes it from config and prints confirmation."""
        # Add a topic first
        with patch("pathlib.Path.cwd", return_value=tmp_project):
            cli_runner.invoke(
                app,
                ["topics", "add", "--domain", "medical-research", "--name", "IVF", "--keywords", "IVF"],
                catch_exceptions=False,
            )

            result = cli_runner.invoke(
                app,
                ["topics", "remove", "--domain", "medical-research", "--topic-id", "IVF"],
                catch_exceptions=False,
            )
        assert result.exit_code == 0
        assert "Removed topic" in result.stdout

        # Verify config
        config_path = tmp_project / ".autoinfo" / "config.yaml"
        with open(config_path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
        assert len(raw["domains"][0]["topics"]) == 0

    def test_remove_topic_not_found(self, cli_runner: Any, app: Any, tmp_project: Path) -> None:
        """Removing a non-existent topic prints an error."""
        with patch("pathlib.Path.cwd", return_value=tmp_project):
            result = cli_runner.invoke(
                app,
                ["topics", "remove", "--domain", "medical-research", "--topic-id", "nonexistent"],
                catch_exceptions=False,
            )
        assert result.exit_code == 1
        assert "not found" in result.stdout

    def test_remove_topic_domain_not_found(self, cli_runner: Any, app: Any, tmp_project: Path) -> None:
        """Removing a topic from a non-existent domain prints an error."""
        result = cli_runner.invoke(
            app,
            ["topics", "remove", "--domain", "nonexistent", "--topic-id", "x"],
            catch_exceptions=False,
        )
        assert result.exit_code == 1
        assert "not configured" in result.stdout

    def test_remove_topic_no_config(self, cli_runner: Any, app: Any, tmp_path: Path) -> None:
        """Running topics remove without a config file exits gracefully."""
        with patch("pathlib.Path.cwd", return_value=tmp_path):
            result = cli_runner.invoke(
                app, ["topics", "remove", "--domain", "x", "--topic-id", "y"]
            )
            assert result.exit_code == 1
            assert "Run 'autoinfo init' first" in result.stdout


# ======================================================================
# MCP: _handle_add_topic
# ======================================================================


class TestMCPAddTopic:
    def test_adds_topic_and_returns_created(self, tmp_path: Path) -> None:
        """Adding a new topic returns created=True and persists it."""
        _setup_minimal_config(tmp_path)

        with patch("autoinfo.mcp.server._config_path", return_value=tmp_path / ".autoinfo" / "config.yaml"):
            result = _handle_add_topic(
                domain="medical-research",
                name="Gene therapy",
                keywords=["CRISPR", "gene editing"],
            )

        assert result["created"] is True
        assert result["topic"]["name"] == "Gene therapy"
        assert result["topic"]["keywords"] == ["CRISPR", "gene editing"]
        assert result["topic_id"] == "medical-research:Gene therapy"

    def test_idempotent_returns_existing(self, tmp_path: Path) -> None:
        """Adding the same topic again returns created=False with existing data."""
        _setup_minimal_config(tmp_path)

        with patch("autoinfo.mcp.server._config_path", return_value=tmp_path / ".autoinfo" / "config.yaml"):
            result1 = _handle_add_topic(domain="medical-research", name="Gene therapy", keywords=["CRISPR"])
            result2 = _handle_add_topic(domain="medical-research", name="Gene therapy", keywords=["different"])

        assert result1["created"] is True
        assert result2["created"] is False
        # Returning the EXISTING keywords (not the new ones)
        assert result2["topic"]["keywords"] == ["CRISPR"]

    def test_domain_not_found(self, tmp_path: Path) -> None:
        """Adding to a non-existent domain returns DomainNotFound error."""
        _setup_minimal_config(tmp_path)

        with patch("autoinfo.mcp.server._config_path", return_value=tmp_path / ".autoinfo" / "config.yaml"):
            result = _handle_add_topic(domain="nonexistent", name="Test")

        assert result["error_code"] == "DomainNotFound"

    def test_no_config_returns_error(self, tmp_path: Path) -> None:
        """When no config file exists, returns an error dict."""
        with patch("autoinfo.mcp.server._config_path", return_value=tmp_path / ".autoinfo" / "config.yaml"):
            result = _handle_add_topic(domain="medical-research", name="Test")

        assert "error_code" in result


# ======================================================================
# MCP: _handle_remove_topic
# ======================================================================


class TestMCPRemoveTopic:
    def test_removes_topic_and_returns_removed(self, tmp_path: Path) -> None:
        """Removing an existing topic returns removed=True."""
        _setup_config_with_topics(tmp_path)

        with patch("autoinfo.mcp.server._config_path", return_value=tmp_path / ".autoinfo" / "config.yaml"):
            result = _handle_remove_topic(domain="medical-research", topic_id="IVF")

        assert result["removed"] is True
        assert result["topic"]["name"] == "IVF"

    def test_topic_not_found(self, tmp_path: Path) -> None:
        """Removing a non-existent topic returns TopicNotFound error."""
        _setup_config_with_topics(tmp_path)

        with patch("autoinfo.mcp.server._config_path", return_value=tmp_path / ".autoinfo" / "config.yaml"):
            result = _handle_remove_topic(domain="medical-research", topic_id="nonexistent")

        assert result["error_code"] == "TopicNotFound"

    def test_domain_not_found(self, tmp_path: Path) -> None:
        """Removing from a non-existent domain returns DomainNotFound error."""
        _setup_config_with_topics(tmp_path)

        with patch("autoinfo.mcp.server._config_path", return_value=tmp_path / ".autoinfo" / "config.yaml"):
            result = _handle_remove_topic(domain="nonexistent", topic_id="IVF")

        assert result["error_code"] == "DomainNotFound"

    def test_no_config_returns_error(self, tmp_path: Path) -> None:
        """When no config file exists, returns an error dict."""
        with patch("autoinfo.mcp.server._config_path", return_value=tmp_path / ".autoinfo" / "config.yaml"):
            result = _handle_remove_topic(domain="medical-research", topic_id="IVF")

        assert "error_code" in result


# ======================================================================
# MCP: _handle_list_topics
# ======================================================================


class TestMCPListTopics:
    def test_lists_topics_for_domain(self, tmp_path: Path) -> None:
        """Listing topics returns all topics for the domain."""
        _setup_config_with_topics(tmp_path)

        with patch("autoinfo.mcp.server._config_path", return_value=tmp_path / ".autoinfo" / "config.yaml"):
            result = _handle_list_topics(domain="medical-research")

        assert result["count"] == 2
        names = {t["name"] for t in result["topics"]}
        assert names == {"IVF", "CRISPR"}
        assert result["domain"] == "medical-research"

    def test_empty_list_when_no_topics(self, tmp_path: Path) -> None:
        """Domain with no topics returns an empty list."""
        _setup_minimal_config(tmp_path)

        with patch("autoinfo.mcp.server._config_path", return_value=tmp_path / ".autoinfo" / "config.yaml"):
            result = _handle_list_topics(domain="medical-research")

        assert result["count"] == 0
        assert result["topics"] == []

    def test_domain_not_found(self, tmp_path: Path) -> None:
        """Listing topics for a non-existent domain returns DomainNotFound."""
        _setup_minimal_config(tmp_path)

        with patch("autoinfo.mcp.server._config_path", return_value=tmp_path / ".autoinfo" / "config.yaml"):
            result = _handle_list_topics(domain="nonexistent")

        assert result["error_code"] == "DomainNotFound"

    def test_no_config_returns_error(self, tmp_path: Path) -> None:
        """When no config file exists, returns an error dict."""
        with patch("autoinfo.mcp.server._config_path", return_value=tmp_path / ".autoinfo" / "config.yaml"):
            result = _handle_list_topics(domain="medical-research")

        assert "error_code" in result


# ======================================================================
# MCP: Tool registration
# ======================================================================


class TestMCPToolRegistration:
    @pytest.mark.asyncio
    async def test_list_topics_tool_is_registered(self) -> None:
        """``list_tools`` includes the ``list_topics`` tool with correct schema."""
        from autoinfo.mcp import server as mcp_server

        tools = await mcp_server.list_tools()
        by_name = {t.name: t for t in tools}

        assert "list_topics" in by_name
        tool = by_name["list_topics"]
        assert "domain" in tool.inputSchema.get("required", [])

    @pytest.mark.asyncio
    async def test_all_topic_tools_have_input_schemas(self) -> None:
        """add_topic, remove_topic, list_topics all have valid schemas."""
        from autoinfo.mcp import server as mcp_server

        tools = await mcp_server.list_tools()
        by_name = {t.name: t for t in tools}

        for name in ("add_topic", "remove_topic", "list_topics"):
            assert name in by_name, f"{name} missing from tools"
            schema = by_name[name].inputSchema
            assert schema is not None
            assert schema.get("type") == "object"

    @pytest.mark.asyncio
    async def test_list_topics_dispatch(self) -> None:
        """``list_topics`` call_tool dispatches to ``_handle_list_topics``."""
        from autoinfo.mcp import server as mcp_server

        handler = mcp_server.app.request_handlers[CallToolRequest]
        request = CallToolRequest(
            method="tools/call",
            params=CallToolRequestParams(
                name="list_topics",
                arguments={"domain": "nonexistent"},
            ),
        )
        result = await handler(request)
        call_result = result.root
        data = json.loads(call_result.content[0].text)
        # Should return DomainNotFound (since config won't exist)
        assert "error_code" in data


# ======================================================================
# Helpers
# ======================================================================


def _setup_minimal_config(tmp_path: Path) -> None:
    """Write a minimal config with one domain and no topics."""
    config_dir = tmp_path / ".autoinfo"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.yaml"

    config = {
        "project": {"name": "Test", "created_at": "2026-07-01"},
        "llm": {"provider": "openai", "model": "gpt-4o-mini", "api_key": "sk-test"},
        "domains": [
            {
                "name": "medical-research",
                "active": True,
                "sources": [
                    {"name": "pubmed", "type": "api", "url": "https://pubmed.ncbi.nlm.nih.gov/", "quality_tier": 1},
                ],
                "topics": [],
            },
        ],
    }
    with open(config_path, "w", encoding="utf-8") as fh:
        yaml.dump(config, fh, default_flow_style=False)


def _setup_config_with_topics(tmp_path: Path) -> None:
    """Write a config with a domain that has two topics."""
    config_dir = tmp_path / ".autoinfo"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.yaml"

    config = {
        "project": {"name": "Test", "created_at": "2026-07-01"},
        "llm": {"provider": "openai", "model": "gpt-4o-mini", "api_key": "sk-test"},
        "domains": [
            {
                "name": "medical-research",
                "active": True,
                "sources": [
                    {"name": "pubmed", "type": "api", "url": "https://pubmed.ncbi.nlm.nih.gov/", "quality_tier": 1},
                ],
                "topics": [
                    {"name": "IVF", "keywords": ["IVF", "embryo"]},
                    {"name": "CRISPR", "keywords": ["CRISPR", "gene editing"]},
                ],
            },
        ],
    }
    with open(config_path, "w", encoding="utf-8") as fh:
        yaml.dump(config, fh, default_flow_style=False)
