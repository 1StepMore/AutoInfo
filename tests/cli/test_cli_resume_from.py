"""CLI ``--resume-from`` wiring tests (R-A-01).

Verifies the flag is plumbed through to the real recovery entry points:

* ``autoinfo collect --resume-from`` → ``run_collection(resume_from=...)``
* ``autoinfo process --resume-from`` → ``run_processing(resume_from=...)``
* omitting the flag preserves the legacy call shape (no ``resume_from`` kwarg).
"""

from __future__ import annotations

from unittest.mock import ANY, MagicMock, patch

from typer.testing import CliRunner

from autoinfo.cli.collect import app as collect_app
from autoinfo.cli.process import app as process_app
from autoinfo.process import ProcessResult


def _collect_result() -> dict[str, object]:
    return {
        "collection_id": "col-resume",
        "domain": "medical-research",
        "total_found": 0,
        "total_new": 0,
        "resumed_skipped": [],
        "duration_s": 0.1,
        "per_source": [],
        "unknown_sources": [],
        "dry_run": False,
    }


class TestCollectResumeFlag:
    @patch("autoinfo.collect.run_collection")
    def test_resume_from_is_forwarded(self, mock_run: MagicMock, cli_runner: CliRunner) -> None:
        mock_run.return_value = _collect_result()
        result = cli_runner.invoke(
            collect_app,
            ["--domain", "medical-research", "--resume-from", "auto"],
        )
        assert result.exit_code == 0, result.output
        mock_run.assert_called_once_with(
            domain="medical-research",
            topic="",
            sources=None,
            limit=20,
            dry_run=False,
            progress_cb=ANY,
            resume_from="auto",
        )

    @patch("autoinfo.collect.run_collection")
    def test_omitting_flag_keeps_legacy_call(
        self, mock_run: MagicMock, cli_runner: CliRunner
    ) -> None:
        mock_run.return_value = _collect_result()
        result = cli_runner.invoke(collect_app, ["--domain", "medical-research"])
        assert result.exit_code == 0, result.output
        _, kwargs = mock_run.call_args
        assert "resume_from" not in kwargs


class TestProcessResumeFlag:
    @patch("autoinfo.cli.process.run_processing")
    def test_resume_from_is_forwarded(self, mock_run: MagicMock, cli_runner: CliRunner) -> None:
        mock_run.return_value = ProcessResult(domain="medical-research", total_items=0)
        result = cli_runner.invoke(
            process_app,
            ["--domain", "medical-research", "--resume-from", "start"],
        )
        assert result.exit_code == 0, result.output
        _, kwargs = mock_run.call_args
        assert kwargs["resume_from"] == "start"

    @patch("autoinfo.cli.process.run_processing")
    def test_omitting_flag_keeps_legacy_call(
        self, mock_run: MagicMock, cli_runner: CliRunner
    ) -> None:
        mock_run.return_value = ProcessResult(domain="medical-research", total_items=0)
        result = cli_runner.invoke(process_app, ["--domain", "medical-research"])
        assert result.exit_code == 0, result.output
        _, kwargs = mock_run.call_args
        assert kwargs.get("resume_from") is None
