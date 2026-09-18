"""Coverage for the process CLI additions: ``--topic``/``--batch-size``/
``--check-factual``/``--check-translation``/``--resume-from`` forwarding,
noop + full output paths (per-command and global ``--json``), error handlers,
and the human per-item renderer.

Complements ``test_process_topic_flag.py`` (topic forwarding only).
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from autoinfo.cli import _output
from autoinfo.cli import app as main_app
from autoinfo.cli.process import app as process_app
from autoinfo.process import ProcessResult

runner = CliRunner()


@pytest.fixture(autouse=True)
def _hermetic(tmp_path, monkeypatch):
    """Isolate cwd + HOME; reset the global-json context afterwards."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    yield
    _output.set_global_json(False)


def _full_result(**overrides: Any) -> ProcessResult:
    """A ProcessResult with mixed per-item logs exercising every render branch."""
    defaults: dict[str, Any] = {
        "domain": "medical-research",
        "total_items": 3,
        "processed_count": 2,
        "remaining_count": 1,
        "is_complete": False,
        "passed_gates": 2,
        "kb_entries_created": 1,
        "errors": [{"item_id": "item-3", "error": "llm exploded"}],
        "duration_s": 1.2,
        "per_item_logs": [
            {
                "status": "ok",
                "item_id": "item-1",
                "title": "Title One",
                "g3_score": 85,
                "duration_s": 0.5,
            },
            {
                "status": "duplicate",
                "item_id": "item-2",
                "title": "Title Two",
                "detail": "url",
            },
            {
                "status": "error",
                "item_id": "item-3",
                "title": "Title Three",
                "error": "llm exploded",
            },
        ],
    }
    defaults.update(overrides)
    return ProcessResult(**defaults)


class TestProcessFlagForwarding:
    def test_all_pipeline_flags_are_forwarded(self) -> None:
        captured: dict[str, Any] = {}

        def _fake_run(**kwargs: Any) -> ProcessResult:
            captured.update(kwargs)
            return ProcessResult(domain=kwargs["domain"], total_items=0)

        with patch("autoinfo.cli.process.run_processing", side_effect=_fake_run):
            result = runner.invoke(
                process_app,
                [
                    "--domain",
                    "medical-research",
                    "--topic",
                    "ivf",
                    "--model",
                    "deepseek/deepseek-chat",
                    "--batch-size",
                    "5",
                    "--check-factual",
                    "--check-translation",
                    "--resume-from",
                    "auto",
                ],
            )

        assert result.exit_code == 0, result.output
        assert captured == {
            "domain": "medical-research",
            "topic": "ivf",
            "model": "deepseek/deepseek-chat",
            "batch_size": 5,
            "check_factual": True,
            "check_translation": True,
            "resume_from": "auto",
        }


class TestProcessErrorHandlers:
    def test_file_not_found_exits_nonzero(self) -> None:
        with patch(
            "autoinfo.cli.process.run_processing",
            side_effect=FileNotFoundError("no cached items dir"),
        ):
            result = runner.invoke(process_app, ["--domain", "medical-research"])

        assert result.exit_code == 1, result.output
        assert "Error: no cached items dir" in result.output

    def test_value_error_exits_nonzero(self) -> None:
        with patch(
            "autoinfo.cli.process.run_processing",
            side_effect=ValueError("invalid batch size"),
        ):
            result = runner.invoke(process_app, ["--domain", "medical-research"])

        assert result.exit_code == 1, result.output
        assert "Error: invalid batch size" in result.output

    def test_unexpected_error_exits_nonzero(self) -> None:
        with patch(
            "autoinfo.cli.process.run_processing",
            side_effect=RuntimeError("llm blew up"),
        ):
            result = runner.invoke(process_app, ["--domain", "medical-research"])

        assert result.exit_code == 1, result.output
        assert "Unexpected error: llm blew up" in result.output


class TestProcessNoopOutput:
    def test_noop_json_output_reports_noop_status(self) -> None:
        with patch(
            "autoinfo.cli.process.run_processing",
            return_value=ProcessResult(domain="medical-research", total_items=0),
        ):
            result = runner.invoke(process_app, ["--domain", "medical-research", "--json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert payload == {
            "status": "noop",
            "total_items": 0,
            "message": (
                "No cached items found for domain 'medical-research'. Run collect_sources() first."
            ),
            "domain": "medical-research",
        }

    def test_noop_global_json_emits_envelope(self) -> None:
        with patch(
            "autoinfo.cli.process.run_processing",
            return_value=ProcessResult(domain="medical-research", total_items=0),
        ):
            result = runner.invoke(main_app, ["--json", "process", "--domain", "medical-research"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert payload["success"] is True
        assert payload["data"]["status"] == "noop"


class TestProcessFullOutput:
    def test_full_json_output_carries_all_fields(self) -> None:
        expected = _full_result(is_complete=True, errors=[], remaining_count=0)
        with patch("autoinfo.cli.process.run_processing", return_value=expected):
            result = runner.invoke(process_app, ["--domain", "medical-research", "--json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert payload["domain"] == "medical-research"
        assert payload["total_items"] == 3
        assert payload["processed_count"] == 2
        assert payload["is_complete"] is True
        assert payload["passed_gates"] == 2
        assert payload["kb_entries_created"] == 1
        assert payload["errors"] == []
        assert payload["duration_s"] == 1.2
        assert len(payload["per_item_logs"]) == 3

    def test_full_global_json_emits_envelope_and_exits_zero_without_errors(self) -> None:
        with patch(
            "autoinfo.cli.process.run_processing",
            return_value=_full_result(is_complete=True, errors=[], remaining_count=0),
        ):
            result = runner.invoke(main_app, ["--json", "process", "--domain", "medical-research"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert payload["success"] is True
        assert payload["data"]["total_items"] == 3

    def test_full_global_json_exits_nonzero_when_items_failed(self) -> None:
        with patch(
            "autoinfo.cli.process.run_processing",
            return_value=_full_result(),
        ):
            result = runner.invoke(main_app, ["--json", "process", "--domain", "medical-research"])

        assert result.exit_code == 1, result.output
        payload = json.loads(result.stdout)
        assert payload["success"] is True
        assert payload["data"]["errors"] == [{"item_id": "item-3", "error": "llm exploded"}]

    def test_full_global_json_noop_exits_nonzero_when_items_failed(self) -> None:
        with patch(
            "autoinfo.cli.process.run_processing",
            return_value=ProcessResult(
                domain="medical-research",
                total_items=0,
                errors=[{"item_id": "item-x", "error": "gate crash"}],
            ),
        ):
            result = runner.invoke(main_app, ["--json", "process", "--domain", "medical-research"])

        assert result.exit_code == 1, result.output

    def test_human_output_renders_item_logs_and_exits_nonzero_on_errors(self) -> None:
        with patch(
            "autoinfo.cli.process.run_processing",
            return_value=_full_result(),
        ):
            result = runner.invoke(process_app, ["--domain", "medical-research"])

        assert result.exit_code == 1, result.output
        assert "Processing domain: medical-research" in result.output
        assert "✓ item-1: Title One [score=85, 0.50s]" in result.output
        assert "⚠ item-2: Title Two (duplicate, matched by url)" in result.output
        assert "✗ item-3: Title Three" in result.output
        assert "↳ llm exploded" in result.output
        assert "Summary: 3 items → 2 passed G1-G3 → 1 KB entries created (1.2s)" in result.output
        assert "Batch progress: 2 processed, 1 remaining (incomplete)" in result.output
        assert "1 item(s) failed processing" in result.output

    def test_human_output_complete_batch_has_no_batch_progress_line(self) -> None:
        with patch(
            "autoinfo.cli.process.run_processing",
            return_value=_full_result(is_complete=True, remaining_count=0, errors=[]),
        ):
            result = runner.invoke(process_app, ["--domain", "medical-research"])

        assert result.exit_code == 0, result.output
        assert "Batch progress" not in result.output
        assert "failed processing" not in result.output
