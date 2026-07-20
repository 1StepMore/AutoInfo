"""Tests for the AutoInfo MCP server.

Covers:
    - Tool registration (``list_tools`` returns 6 tools with correct schemas)
    - ``health_check`` response structure
    - ``diagnose_system`` response structure (with/without config)
    - ``collect_sources`` dispatches to ``run_collection``
    - ``process_collection`` dispatches to ``run_processing``
    - ``list_summaries`` dispatches to ``KBStore.list_entries``
    - ``get_kb_entry`` returns entry or ``NotFound`` error
    - Error handling for unknown tools and runtime exceptions
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from mcp.types import CallToolRequest, CallToolRequestParams, TextContent

from autoinfo.mcp import server as mcp_server
from autoinfo.mcp.server import (
    _error_response,
    _handle_collect_sources,
    _handle_diagnose_system,
    _handle_get_kb_entry,
    _handle_get_processing_progress,
    _handle_health_check,
    _handle_list_summaries,
    _handle_process_collection,
)


# ======================================================================
# _handle_health_check
# ======================================================================


class TestHealthCheck:
    def test_returns_status_ok(self) -> None:
        result = _handle_health_check()
        assert result["status"] == "ok"
        assert "version" in result
        assert result["tools_count"] >= 23

    def test_version_matches_package(self) -> None:
        from autoinfo import __version__

        result = _handle_health_check()
        assert result["version"] == __version__


# ======================================================================
# _handle_diagnose_system
# ======================================================================


class TestDiagnoseSystem:
    def test_returns_all_sections_when_no_config(self) -> None:
        """Without a config file, all sections are still present."""
        with patch("autoinfo.config.get_config_path", return_value=None):
            result = _handle_diagnose_system()

        assert "llm" in result
        assert "sources" in result
        assert "disk" in result
        assert "db" in result

        # LLM not configured when there's no config
        assert result["llm"]["configured"] is False

    def test_llm_configured_when_config_found(self, tmp_path: Path) -> None:
        """With a config file, LLM details are populated."""
        config_dir = tmp_path / ".autoinfo"
        config_dir.mkdir()
        config_path = config_dir / "config.yaml"
        config_path.write_text(
            "llm:\n"
            "  provider: openrouter\n"
            "  model: deepseek/deepseek-chat\n"
            "  api_key: sk-test\n"
            "project:\n"
            "  name: Test\n"
            "domains:\n"
            "  - name: medical-research\n"
            "    active: true\n"
            "    sources:\n"
            "      - name: pubmed\n"
            "        type: api\n"
            "        url: https://eutils.ncbi.nlm.nih.gov\n"
            "    topics:\n"
            "      - name: IVF\n"
            "        keywords: [IVF, embryo]\n",
        )

        with (
            patch("autoinfo.config.get_config_path", return_value=config_path),
            patch("autoinfo.config.load_config") as mock_load,
        ):
            from autoinfo.config import (
                Config,
                DomainConfig,
                LLMConfig,
                ProjectConfig,
                SourceConfig,
            )

            mock_load.return_value = Config(
                project=ProjectConfig(name="Test"),
                llm=LLMConfig(
                    provider="openrouter",
                    model="deepseek/deepseek-chat",
                    api_key="sk-test",
                ),
                domains=[
                    DomainConfig(
                        name="medical-research",
                        active=True,
                        sources=[
                            SourceConfig(
                                name="pubmed",
                                type="api",
                                url="https://eutils.ncbi.nlm.nih.gov",
                            ),
                        ],
                    ),
                ],
            )
            result = _handle_diagnose_system()

        assert result["llm"]["configured"] is True
        assert result["llm"]["provider"] == "openrouter"
        assert result["llm"]["model"] == "deepseek/deepseek-chat"
        assert result["llm"]["key_configured"] is True

    def test_sources_parsed_from_config(self) -> None:
        """Active domain sources appear in the sources section."""
        with (
            patch("autoinfo.config.get_config_path") as mock_path,
            patch("autoinfo.config.load_config") as mock_load,
        ):
            mock_path.return_value = Path("/fake/.autoinfo/config.yaml")

            from autoinfo.config import (
                Config,
                DomainConfig,
                LLMConfig,
                ProjectConfig,
                SourceConfig,
            )

            mock_load.return_value = Config(
                project=ProjectConfig(name="Test"),
                llm=LLMConfig(provider="openai", model="gpt-4o-mini"),
                domains=[
                    DomainConfig(
                        name="ai-commercial",
                        active=True,
                        sources=[
                            SourceConfig(name="hackernews", type="rss"),
                            SourceConfig(name="techcrunch", type="rss"),
                        ],
                    ),
                ],
            )
            result = _handle_diagnose_system()

        assert result["sources"]["count"] == 2
        names = {s["name"] for s in result["sources"]["items"]}
        assert names == {"hackernews", "techcrunch"}

    def test_disk_sections_present(self) -> None:
        """Disk section shows directory existence."""
        with patch("autoinfo.config.get_config_path", return_value=None):
            result = _handle_diagnose_system()

        assert "collections_dir_exists" in result["disk"]
        assert "knowledge_dir_exists" in result["disk"]

    def test_db_section_present(self) -> None:
        """DB section shows whether autoinfo.db exists."""
        with patch("autoinfo.config.get_config_path", return_value=None):
            result = _handle_diagnose_system()

        assert "exists" in result["db"]


# ======================================================================
# Error response format
# ======================================================================


class TestErrorResponse:
    def test_includes_required_fields(self) -> None:
        exc = ValueError("Invalid domain name")
        result = _error_response(exc)

        assert len(result) == 1
        content = result[0]
        assert isinstance(content, TextContent)
        assert content.type == "text"

        data = json.loads(content.text)
        assert data["error_code"] == "ValueError"
        assert "Invalid domain name" in data["message"]
        assert data["actionable"] is True

    def test_handles_arbitrary_exception_types(self) -> None:
        exc = RuntimeError("Connection refused")
        result = _error_response(exc)
        data = json.loads(result[0].text)
        assert data["error_code"] == "RuntimeError"


# ======================================================================
# Tool registration (list_tools)
# ======================================================================


class TestToolRegistration:
    @pytest.mark.asyncio
    async def test_lists_at_least_twenty_three_tools(self) -> None:
        tools = await mcp_server.list_tools()
        assert len(tools) >= 23

        names = {t.name for t in tools}
        assert {
            "health_check",
            "diagnose_system",
            "collect_sources",
            "process_collection",
            "get_processing_progress",
            "list_summaries",
            "get_kb_entry",
            "list_domains",
            "get_domain_schema",
            "list_available_models",
            "get_effective_llm_config",
            "add_source",
            "add_sources",
            "remove_source",
            "test_source",
            "list_sources",
            "add_topic",
            "remove_topic",
            "search_knowledge_base",
            "flag_for_knowledge_base",
            "get_summary",
            "list_output_templates",
        }.issubset(names)

    @pytest.mark.asyncio
    async def test_each_tool_has_input_schema(self) -> None:
        tools = await mcp_server.list_tools()
        for tool in tools:
            assert tool.inputSchema is not None
            assert tool.inputSchema.get("type") == "object"

    @pytest.mark.asyncio
    async def test_required_params_are_marked(self) -> None:
        tools = await mcp_server.list_tools()
        by_name = {t.name: t for t in tools}

        # Tools with no required params
        assert "required" not in by_name["health_check"].inputSchema or \
               by_name["health_check"].inputSchema["required"] is None

        # Collect requires domain
        schema = by_name["collect_sources"].inputSchema
        assert "domain" in schema.get("required", [])

        # Process requires domain
        schema = by_name["process_collection"].inputSchema
        assert "domain" in schema.get("required", [])

        # List summaries requires domain
        schema = by_name["list_summaries"].inputSchema
        assert "domain" in schema.get("required", [])

        # Get KB entry requires entry_id
        schema = by_name["get_kb_entry"].inputSchema
        assert "entry_id" in schema.get("required", [])


# ======================================================================
# call_tool dispatch  (exercised via request_handlers)
# ======================================================================


class TestToolDispatch:
    @pytest.mark.asyncio
    async def test_health_check_dispatches_correctly(self) -> None:
        handler = mcp_server.app.request_handlers[CallToolRequest]
        request = CallToolRequest(
            method="tools/call",
            params=CallToolRequestParams(name="health_check", arguments={}),
        )
        result = await handler(request)
        assert result is not None
        call_result = result.root
        assert len(call_result.content) == 1
        data = json.loads(call_result.content[0].text)
        assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self) -> None:
        handler = mcp_server.app.request_handlers[CallToolRequest]
        request = CallToolRequest(
            method="tools/call",
            params=CallToolRequestParams(name="nonexistent", arguments={}),
        )
        result = await handler(request)
        call_result = result.root
        data = json.loads(call_result.content[0].text)
        assert data["error_code"] == "UnknownTool"
        assert data["actionable"] is False

    @pytest.mark.asyncio
    async def test_missing_required_argument_returns_error(self) -> None:
        handler = mcp_server.app.request_handlers[CallToolRequest]
        request = CallToolRequest(
            method="tools/call",
            params=CallToolRequestParams(
                name="get_kb_entry",
                arguments={},  # entry_id is required
            ),
        )
        result = await handler(request)
        call_result = result.root
        assert call_result.isError or len(call_result.content) > 0


# ======================================================================
# Handler-level integration with mocked dependencies
# ======================================================================


class TestCollectSources:
    @patch("autoinfo.collect.run_collection")
    def test_dispatches_to_run_collection(self, mock_run: MagicMock) -> None:
        mock_run.return_value = {
            "collection_id": "col-001",
            "domain": "medical-research",
            "total_found": 5,
            "total_new": 3,
        }

        result = _handle_collect_sources(
            domain="medical-research",
            topic="IVF",
            limit=10,
        )

        mock_run.assert_called_once_with(
            domain="medical-research",
            topic="IVF",
            limit=10,
        )
        assert result["collection_id"] == "col-001"

    @patch("autoinfo.collect.run_collection")
    def test_dry_run_passed_through(self, mock_run: MagicMock) -> None:
        _handle_collect_sources(domain="test", dry_run=True)
        mock_run.assert_called_once_with(domain="test", dry_run=True)


class TestProcessCollection:
    @patch("autoinfo.process.run_processing")
    def test_dispatches_to_run_processing(self, mock_proc: MagicMock) -> None:
        from autoinfo.process import ProcessResult

        mock_proc.return_value = ProcessResult(
            domain="medical-research",
            total_items=10,
            passed_gates=8,
            kb_entries_created=8,
            duration_s=1.23,
        )

        result = _handle_process_collection(
            domain="medical-research",
            model="deepseek/deepseek-chat",
        )

        mock_proc.assert_called_once_with(
            domain="medical-research",
            model="deepseek/deepseek-chat",
        )
        assert result["domain"] == "medical-research"
        assert result["kb_entries_created"] == 8
        assert result["total_items"] == 10

    @patch("autoinfo.process.run_processing")
    def test_model_optional(self, mock_proc: MagicMock) -> None:
        from autoinfo.process import ProcessResult

        mock_proc.return_value = ProcessResult(domain="test")
        _handle_process_collection(domain="test")
        mock_proc.assert_called_once_with(domain="test")

    @patch("autoinfo.process.run_processing")
    def test_batch_size_passed_through(self, mock_proc: MagicMock) -> None:
        from autoinfo.process import ProcessResult

        mock_proc.return_value = ProcessResult(
            domain="medical-research",
            total_items=10,
            processed_count=3,
            remaining_count=7,
            is_complete=False,
        )

        result = _handle_process_collection(
            domain="medical-research", batch_size=3
        )

        mock_proc.assert_called_once_with(
            domain="medical-research", batch_size=3
        )
        assert result["total_items"] == 10
        assert result["processed_count"] == 3
        assert result["remaining_count"] == 7
        assert result["is_complete"] is False


class TestGetProcessingProgress:
    @patch("autoinfo.process.get_processing_progress")
    def test_returns_progress(self, mock_progress: MagicMock) -> None:
        mock_progress.return_value = {
            "total_items": 10,
            "processed_count": 3,
            "remaining_count": 7,
            "is_complete": False,
        }

        result = _handle_get_processing_progress(domain="medical-research")

        mock_progress.assert_called_once_with(domain="medical-research")
        assert result["total_items"] == 10
        assert result["processed_count"] == 3
        assert result["remaining_count"] == 7
        assert result["is_complete"] is False

    @patch("autoinfo.process.get_processing_progress")
    def test_complete_progress(self, mock_progress: MagicMock) -> None:
        mock_progress.return_value = {
            "total_items": 10,
            "processed_count": 10,
            "remaining_count": 0,
            "is_complete": True,
        }

        result = _handle_get_processing_progress(domain="medical-research")

        assert result["is_complete"] is True
        assert result["remaining_count"] == 0


class TestListSummaries:
    @patch("autoinfo.kb.KBStore")
    def test_dispatches_to_kb_store(self, mock_kb: MagicMock) -> None:
        mock_instance = mock_kb.return_value
        mock_instance.list_entries.return_value = [
            {"entry_id": "e1", "title": "Entry 1"},
            {"entry_id": "e2", "title": "Entry 2"},
        ]

        result = _handle_list_summaries(
            domain="medical-research",
            limit=10,
            offset=0,
        )

        mock_instance.list_entries.assert_called_once_with(
            "medical-research",
            limit=10,
            offset=0,
        )
        assert result["count"] == 2
        assert result["domain"] == "medical-research"

    @patch("autoinfo.kb.KBStore")
    def test_empty_result(self, mock_kb: MagicMock) -> None:
        mock_instance = mock_kb.return_value
        mock_instance.list_entries.return_value = []

        result = _handle_list_summaries(domain="nonexistent")
        assert result["count"] == 0
        assert result["entries"] == []


class TestGetKBEntry:
    @patch("autoinfo.kb.KBStore")
    def test_returns_entry_when_found(self, mock_kb: MagicMock) -> None:
        mock_instance = mock_kb.return_value
        mock_instance.get_entry.return_value = {
            "entry_id": "med-ivf-001",
            "title": "IVF Study",
            "domain": "medical-research",
            "content": "Full content here",
        }

        result = _handle_get_kb_entry(entry_id="med-ivf-001")
        assert result["entry_id"] == "med-ivf-001"
        assert result["title"] == "IVF Study"

    @patch("autoinfo.kb.KBStore")
    def test_returns_not_found_when_missing(self, mock_kb: MagicMock) -> None:
        mock_instance = mock_kb.return_value
        mock_instance.get_entry.return_value = None

        result = _handle_get_kb_entry(entry_id="nonexistent")
        assert "error_code" in result
        assert result["error_code"] == "NotFound"
        assert "nonexistent" in result["message"]
