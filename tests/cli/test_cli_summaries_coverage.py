"""Coverage for the summaries CLI additions: ``list`` error handlers,
``flag`` config-missing / failure / not-flagged / envelope paths, and the
whole ``show`` command (human, JSON, global ``--json``, not-found).

Complements ``test_cli_commands.py`` and ``test_cli_summaries_tags.py``
(happy-path list/flag against a real KBStore).
"""

from __future__ import annotations

import json
import sys
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from autoinfo.cli import _output
from autoinfo.cli import app as main_app
from autoinfo.cli.summaries import app as summaries_app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _hermetic(tmp_path, monkeypatch):
    """Isolate cwd + HOME so get_config_path only sees this test's tree."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    yield
    _output.set_global_json(False)


def _write_config(tmp_path) -> None:
    config_dir = tmp_path / ".autoinfo"
    config_dir.mkdir(exist_ok=True)
    (config_dir / "config.yaml").write_text(
        json.dumps({"project": {"name": "cov"}, "domains": []}),
        encoding="utf-8",
    )


def _summary_detail() -> dict[str, Any]:
    return {
        "entry_id": "kb-entry-009",
        "title": "Retrieval-augmented generation survey",
        "tl_dr": "A survey of RAG techniques.",
        "relevance_score": 87.0,
        "importance": 4,
        "file_path": "knowledge/01-Raw/kb-entry-009.md",
        "tags": ["rag", "survey"],
        "source_provenance": {
            "source_platform": "arxiv",
            "source_url": "https://arxiv.org/abs/1234.5678",
            "collected_at": "2026-08-01T09:00:00Z",
        },
        "key_points": ["Dense retrieval dominates", "Hybrid search helps"],
        "quality_scores": {"G1": True, "G3": False},
    }


class TestSummariesList:
    def test_list_file_not_found_exits_nonzero(self, tmp_path) -> None:
        _write_config(tmp_path)
        with patch("autoinfo.kb.KBStore") as mock_store:
            mock_store.return_value.list_entries.side_effect = FileNotFoundError(
                "knowledge/ missing"
            )
            result = runner.invoke(summaries_app, ["list", "--domain", "medical-research"])

        assert result.exit_code == 1, result.output
        assert "Error: knowledge/ missing" in result.output

    def test_list_missing_module_exits_nonzero(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_config(tmp_path)
        monkeypatch.setitem(sys.modules, "autoinfo.kb", None)

        result = runner.invoke(summaries_app, ["list", "--domain", "medical-research"])

        assert result.exit_code == 1, result.output
        assert "summaries module not available" in result.output


class TestSummariesFlag:
    def test_flag_without_config_exits_nonzero(self) -> None:
        result = runner.invoke(summaries_app, ["flag", "kb-entry-001"])

        assert result.exit_code == 1, result.output
        assert "No configuration found" in result.output

    def test_flag_store_failure_exits_nonzero(self, tmp_path) -> None:
        _write_config(tmp_path)
        with patch("autoinfo.kb.KBStore") as mock_store:
            mock_store.return_value.flag_for_knowledge_base.side_effect = RuntimeError(
                "store write failed"
            )
            result = runner.invoke(summaries_app, ["flag", "kb-entry-001", "--tag", "keep"])

        assert result.exit_code == 1, result.output
        assert "Error: store write failed" in result.output

    def test_flag_unknown_entry_exits_nonzero(self, tmp_path) -> None:
        _write_config(tmp_path)
        with patch("autoinfo.kb.KBStore") as mock_store:
            mock_store.return_value.flag_for_knowledge_base.return_value = {
                "flagged": False,
                "error": "Entry not found",
            }
            result = runner.invoke(summaries_app, ["flag", "missing-entry"])

        assert result.exit_code == 1, result.output
        assert "Error: Entry not found: missing-entry" in result.output

    def test_flag_success_global_json_emits_envelope(self, tmp_path) -> None:
        _write_config(tmp_path)
        flagged = {"flagged": True, "entry_id": "kb-entry-001", "tags": ["keep"], "importance": 3}
        with patch("autoinfo.kb.KBStore") as mock_store:
            mock_store.return_value.flag_for_knowledge_base.return_value = flagged
            result = runner.invoke(main_app, ["--json", "summaries", "flag", "kb-entry-001"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert payload["success"] is True
        assert payload["data"] == flagged
        assert "Flagged kb-entry-001" not in result.stdout


class TestSummariesShow:
    def test_show_without_config_exits_nonzero(self) -> None:
        result = runner.invoke(summaries_app, ["show", "kb-entry-001"])

        assert result.exit_code == 1, result.output
        assert "No configuration found" in result.output

    def test_show_store_failure_exits_nonzero(self, tmp_path) -> None:
        _write_config(tmp_path)
        with patch("autoinfo.kb.KBStore") as mock_store:
            mock_store.return_value.get_summary.side_effect = RuntimeError("read failed")
            result = runner.invoke(summaries_app, ["show", "kb-entry-001"])

        assert result.exit_code == 1, result.output
        assert "Error: read failed" in result.output

    def test_show_unknown_entry_exits_nonzero(self, tmp_path) -> None:
        _write_config(tmp_path)
        with patch("autoinfo.kb.KBStore") as mock_store:
            mock_store.return_value.get_summary.return_value = {"error": "Entry not found"}
            result = runner.invoke(summaries_app, ["show", "missing-entry"])

        assert result.exit_code == 1, result.output
        assert "Error: Entry not found: missing-entry" in result.output

    def test_show_renders_human_detail(self, tmp_path) -> None:
        _write_config(tmp_path)
        with patch("autoinfo.kb.KBStore") as mock_store:
            mock_store.return_value.get_summary.return_value = _summary_detail()
            result = runner.invoke(summaries_app, ["show", "kb-entry-009"])

        assert result.exit_code == 0, result.output
        assert "Entry ID:   kb-entry-009" in result.output
        assert "Title:      Retrieval-augmented generation survey" in result.output
        assert "TL;DR:      A survey of RAG techniques." in result.output
        assert "Relevance:  87/100" in result.output
        assert "Importance: 4/5" in result.output
        assert "Tags:       rag, survey" in result.output
        assert "Source:     arxiv — https://arxiv.org/abs/1234.5678" in result.output
        assert "Collected:  2026-08-01T09:00:00Z" in result.output
        assert "Key Points:" in result.output
        assert "1. Dense retrieval dominates" in result.output
        assert "Quality Flags:" in result.output
        assert "G1: Flagged" in result.output
        assert "G3: Passed" in result.output

    def test_show_json_output_emits_detail(self, tmp_path) -> None:
        _write_config(tmp_path)
        detail = _summary_detail()
        with patch("autoinfo.kb.KBStore") as mock_store:
            mock_store.return_value.get_summary.return_value = detail
            result = runner.invoke(summaries_app, ["show", "kb-entry-009", "--json"])

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == detail

    def test_show_global_json_emits_envelope(self, tmp_path) -> None:
        _write_config(tmp_path)
        detail = _summary_detail()
        with patch("autoinfo.kb.KBStore") as mock_store:
            mock_store.return_value.get_summary.return_value = detail
            result = runner.invoke(main_app, ["--json", "summaries", "show", "kb-entry-009"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert payload["success"] is True
        assert payload["data"] == detail
