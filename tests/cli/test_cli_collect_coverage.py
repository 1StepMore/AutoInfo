"""Coverage for the collect CLI additions (multi-domain ``--all``, resume,
dry-run notice, auto-process wiring, progress printer, error envelopes).

Complements ``test_cli_collect_sources.py`` (``--source`` regression) and
``test_cli_resume_from.py`` by exercising the code paths those files do not
reach: the ``--all`` branch, the failure handlers, and the human helpers.
"""

from __future__ import annotations

import json
import sys
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from autoinfo.cli import _output
from autoinfo.cli import app as main_app
from autoinfo.cli.collect import app as collect_app
from autoinfo.process import ProcessResult

runner = CliRunner()


@pytest.fixture(autouse=True)
def _hermetic(tmp_path, monkeypatch):
    """Isolate cwd + HOME so no real config leaks into the CLI runs."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    yield
    _output.set_global_json(False)


def _write_config(tmp_path, domains: list[dict[str, Any]]) -> None:
    config_dir = tmp_path / ".autoinfo"
    config_dir.mkdir(exist_ok=True)
    (config_dir / "config.yaml").write_text(
        json.dumps({"project": {"name": "cov"}, "domains": domains}),
        encoding="utf-8",
    )


def _domain_entry(name: str, active: bool = True) -> dict[str, Any]:
    return {
        "name": name,
        "active": active,
        "sources": [{"name": "pubmed", "type": "api", "url": "https://example.com"}],
        "topics": [{"name": "t", "keywords": ["k"]}],
    }


def _collection_result(domain: str = "medical-research", **overrides: Any) -> dict[str, Any]:
    """A full ``run_collection`` result dict for CLI output tests."""
    result: dict[str, Any] = {
        "collection_id": f"col-{domain}",
        "domain": domain,
        "total_found": 12,
        "total_new": 5,
        "duration_s": 1.25,
        "per_source": [
            {
                "source": "pubmed",
                "status": "success",
                "items_found": 12,
                "items_new": 5,
                "items_filtered": 0,
                "errors": [],
                "duration_s": 1.25,
            }
        ],
        "dry_run": False,
        "resumed_skipped": [],
    }
    result.update(overrides)
    return result


# ---------------------------------------------------------------------------
# Flag validation
# ---------------------------------------------------------------------------


class TestCollectFlagValidation:
    def test_all_with_domain_is_rejected(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(collect_app, ["--all", "--domain", "medical-research"])

        assert result.exit_code == 1, result.output
        assert "Cannot use --all with --domain" in result.output

    def test_neither_all_nor_domain_is_rejected(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(collect_app, [])

        assert result.exit_code == 1, result.output
        assert "Either --domain or --all must be provided." in result.output


# ---------------------------------------------------------------------------
# Multi-domain (--all) branch
# ---------------------------------------------------------------------------


class TestCollectAllDomains:
    def test_all_without_config_exits_nonzero(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(collect_app, ["--all"])

        assert result.exit_code == 1, result.output
        assert "No configuration found" in result.output

    def test_all_without_active_domains_exits_nonzero(self, cli_runner, tmp_path) -> None:
        _write_config(tmp_path, [_domain_entry("sleepy", active=False)])

        result = cli_runner.invoke(collect_app, ["--all"])

        assert result.exit_code == 1, result.output
        assert "No active domains found" in result.output

    @patch("autoinfo.collect.run_collection")
    def test_all_collects_each_active_domain(
        self, mock_run: MagicMock, cli_runner, tmp_path
    ) -> None:
        _write_config(tmp_path, [_domain_entry("alpha"), _domain_entry("beta")])
        mock_run.side_effect = lambda **kw: _collection_result(domain=kw["domain"])

        result = cli_runner.invoke(collect_app, ["--all"])

        assert result.exit_code == 0, result.output
        domains_called = [call.kwargs["domain"] for call in mock_run.call_args_list]
        assert domains_called == ["alpha", "beta"]
        assert "── Collecting for domain 'alpha' ──" in result.output
        assert "── Collecting for domain 'beta' ──" in result.output
        # Each per-domain result is rendered in human form.
        assert "Collection col-alpha for domain 'alpha'" in result.output

    @patch("autoinfo.collect.run_collection")
    def test_all_json_output_aggregates_domains(
        self, mock_run: MagicMock, cli_runner, tmp_path
    ) -> None:
        _write_config(tmp_path, [_domain_entry("alpha"), _domain_entry("beta")])
        mock_run.side_effect = lambda **kw: _collection_result(domain=kw["domain"])

        result = cli_runner.invoke(collect_app, ["--all", "--json"])

        assert result.exit_code == 0, result.output
        # Per-command --json keeps the historical shape: the domain banners are
        # printed first (pre-existing behavior; only global --json suppresses
        # them), so the aggregate document starts at the first brace.
        assert "── Collecting for domain 'alpha' ──" in result.stdout
        stdout = result.stdout
        payload = json.loads(stdout[stdout.index("{") :])
        assert payload["total_domains"] == 2
        assert [d["domain"] for d in payload["domains"]] == ["alpha", "beta"]
        assert payload["total_new"] == 10
        assert payload["dry_run"] is False

    @patch("autoinfo.collect.run_collection")
    def test_all_forwards_force_full_and_resume(
        self, mock_run: MagicMock, cli_runner, tmp_path
    ) -> None:
        _write_config(tmp_path, [_domain_entry("alpha")])
        mock_run.side_effect = lambda **kw: _collection_result(domain=kw["domain"])

        result = cli_runner.invoke(collect_app, ["--all", "--force-full", "--resume-from", "auto"])

        assert result.exit_code == 0, result.output
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["force_full"] is True
        assert call_kwargs["resume_from"] == "auto"

    @patch("autoinfo.process.run_processing")
    @patch("autoinfo.collect.run_collection")
    def test_all_auto_process_runs_only_for_domains_with_new_items(
        self, mock_run: MagicMock, mock_process: MagicMock, cli_runner, tmp_path
    ) -> None:
        _write_config(tmp_path, [_domain_entry("alpha"), _domain_entry("beta")])
        mock_run.side_effect = lambda **kw: _collection_result(
            domain=kw["domain"], total_new=5 if kw["domain"] == "alpha" else 0
        )
        mock_process.return_value = ProcessResult(domain="alpha", total_items=5)

        result = cli_runner.invoke(collect_app, ["--all", "--auto-process"])

        assert result.exit_code == 0, result.output
        assert "── Running auto-process for 'alpha' ──" in result.output
        assert "No new items for 'beta' — skipping auto-process." in result.output
        mock_process.assert_called_once_with(domain="alpha", topic=None)

    @patch("autoinfo.collect.run_collection")
    def test_all_global_json_emits_envelope(
        self, mock_run: MagicMock, cli_runner, tmp_path
    ) -> None:
        _write_config(tmp_path, [_domain_entry("alpha")])
        mock_run.side_effect = lambda **kw: _collection_result(domain=kw["domain"])

        result = cli_runner.invoke(main_app, ["--json", "collect", "--all"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert payload["success"] is True
        assert payload["data"]["total_domains"] == 1
        assert payload["data"]["domains"][0]["domain"] == "alpha"
        assert "── Collecting" not in result.stdout

    @patch("autoinfo.collect.run_collection")
    def test_all_unknown_requested_source_exits_nonzero(
        self, mock_run: MagicMock, cli_runner, tmp_path
    ) -> None:
        _write_config(tmp_path, [_domain_entry("alpha")])
        mock_run.return_value = _collection_result(domain="alpha", unknown_sources=["rss"])

        result = cli_runner.invoke(collect_app, ["--all", "--source", "rss"])

        assert result.exit_code == 1, result.output
        assert "requested source(s) not found in domain config: 'rss' (domain 'alpha')" in (
            result.output
        )


# ---------------------------------------------------------------------------
# Single-domain branch: output modes, auto-process, dry-run, failures
# ---------------------------------------------------------------------------


class TestCollectSingleDomain:
    @patch("autoinfo.collect.run_collection")
    def test_json_output_emits_result_verbatim(self, mock_run: MagicMock, cli_runner) -> None:
        expected = _collection_result()
        mock_run.return_value = expected

        result = cli_runner.invoke(collect_app, ["--domain", "medical-research", "--json"])

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == expected

    @patch("autoinfo.collect.run_collection")
    def test_force_full_is_forwarded(self, mock_run: MagicMock, cli_runner) -> None:
        mock_run.return_value = _collection_result()

        result = cli_runner.invoke(collect_app, ["--domain", "medical-research", "--force-full"])

        assert result.exit_code == 0, result.output
        assert mock_run.call_args.kwargs["force_full"] is True

    @patch("autoinfo.process.run_processing")
    @patch("autoinfo.collect.run_collection")
    def test_auto_process_runs_when_new_items_collected(
        self, mock_run: MagicMock, mock_process: MagicMock, cli_runner
    ) -> None:
        mock_run.return_value = _collection_result()
        mock_process.return_value = ProcessResult(
            domain="medical-research",
            total_items=5,
            passed_gates=4,
            kb_entries_created=4,
            duration_s=0.5,
        )

        result = cli_runner.invoke(collect_app, ["--domain", "medical-research", "--auto-process"])

        assert result.exit_code == 0, result.output
        assert "── Running auto-process ──" in result.output
        assert "Processing: 5 items → 4 passed G1-G3 → 4 KB entries created (0.5s)" in (
            result.output
        )

    @patch("autoinfo.process.run_processing")
    @patch("autoinfo.collect.run_collection")
    def test_auto_process_failure_is_reported_not_fatal(
        self, mock_run: MagicMock, mock_process: MagicMock, cli_runner
    ) -> None:
        mock_run.return_value = _collection_result()
        mock_process.side_effect = RuntimeError("no llm key")

        result = cli_runner.invoke(collect_app, ["--domain", "medical-research", "--auto-process"])

        assert result.exit_code == 0, result.output
        assert "Auto-process failed: no llm key" in result.output

    @patch("autoinfo.process.run_processing")
    @patch("autoinfo.collect.run_collection")
    def test_auto_process_skipped_without_new_items(
        self, mock_run: MagicMock, mock_process: MagicMock, cli_runner
    ) -> None:
        mock_run.return_value = _collection_result(total_new=0)

        result = cli_runner.invoke(collect_app, ["--domain", "medical-research", "--auto-process"])

        assert result.exit_code == 0, result.output
        assert "No new items — skipping auto-process." in result.output
        mock_process.assert_not_called()

    @patch("autoinfo.process.run_processing")
    @patch("autoinfo.collect.run_collection")
    def test_auto_process_reports_failed_items(
        self, mock_run: MagicMock, mock_process: MagicMock, cli_runner
    ) -> None:
        mock_run.return_value = _collection_result()
        mock_process.return_value = ProcessResult(
            domain="medical-research",
            total_items=5,
            errors=[{"item_id": "item-x", "error": "gate crash"}],
        )

        result = cli_runner.invoke(collect_app, ["--domain", "medical-research", "--auto-process"])

        assert result.exit_code == 0, result.output
        assert "1 item(s) failed" in result.output

    @patch("autoinfo.process.run_processing")
    @patch("autoinfo.collect.run_collection")
    def test_auto_process_output_suppressed_under_global_json(
        self, mock_run: MagicMock, mock_process: MagicMock, cli_runner
    ) -> None:
        mock_run.return_value = _collection_result()
        mock_process.return_value = ProcessResult(
            domain="medical-research",
            total_items=5,
            passed_gates=4,
            kb_entries_created=4,
            duration_s=0.5,
        )

        result = cli_runner.invoke(
            main_app, ["--json", "collect", "--domain", "medical-research", "--auto-process"]
        )

        assert result.exit_code == 0, result.output
        assert "Processing:" not in result.stdout
        payload = json.loads(result.stdout)
        assert payload["success"] is True
        assert payload["data"]["domain"] == "medical-research"

    @patch("autoinfo.collect.run_collection")
    def test_dry_run_prints_notice(self, mock_run: MagicMock, cli_runner) -> None:
        mock_run.return_value = _collection_result(dry_run=True, total_new=0)

        result = cli_runner.invoke(collect_app, ["--domain", "medical-research", "--dry-run"])

        assert result.exit_code == 0, result.output
        assert "ℹ Dry-run — no items were stored." in result.output
        assert mock_run.call_args.kwargs["dry_run"] is True

    @patch("autoinfo.collect.run_collection")
    def test_dry_run_notice_suppressed_under_global_json(
        self, mock_run: MagicMock, cli_runner
    ) -> None:
        mock_run.return_value = _collection_result(dry_run=True)

        result = cli_runner.invoke(main_app, ["--json", "collect", "--domain", "medical-research"])

        assert result.exit_code == 0, result.output
        assert "Dry-run" not in result.stdout
        payload = json.loads(result.stdout)
        assert payload["success"] is True
        assert payload["data"]["domain"] == "medical-research"

    @patch("autoinfo.collect.run_collection")
    def test_run_collection_file_not_found_exits_nonzero(
        self, mock_run: MagicMock, cli_runner
    ) -> None:
        mock_run.side_effect = FileNotFoundError("collections/ dir missing")

        result = cli_runner.invoke(collect_app, ["--domain", "medical-research"])

        assert result.exit_code == 1, result.output
        assert "Error: collections/ dir missing" in result.output

    @patch("autoinfo.collect.run_collection")
    def test_run_collection_value_error_exits_nonzero(
        self, mock_run: MagicMock, cli_runner
    ) -> None:
        mock_run.side_effect = ValueError("bad limit")

        result = cli_runner.invoke(collect_app, ["--domain", "medical-research"])

        assert result.exit_code == 1, result.output
        assert "Error: bad limit" in result.output

    def test_missing_collect_module_exits_nonzero(self, cli_runner, monkeypatch) -> None:
        monkeypatch.setitem(sys.modules, "autoinfo.collect", None)

        result = cli_runner.invoke(collect_app, ["--domain", "medical-research"])

        assert result.exit_code == 1, result.output
        assert "collect module not available" in result.output

    @patch("autoinfo.collect.run_collection")
    def test_global_json_suppresses_progress_printer(self, mock_run: MagicMock, cli_runner) -> None:
        mock_run.return_value = _collection_result()

        result = cli_runner.invoke(main_app, ["--json", "collect", "--domain", "medical-research"])

        assert result.exit_code == 0, result.output
        assert mock_run.call_args.kwargs["progress_cb"] is None


# ---------------------------------------------------------------------------
# Human helpers
# ---------------------------------------------------------------------------


class TestCollectHumanOutput:
    @patch("autoinfo.collect.run_collection")
    def test_print_human_renders_filtered_errors_and_resume(
        self, mock_run: MagicMock, cli_runner
    ) -> None:
        mock_run.return_value = _collection_result(
            per_source=[
                {
                    "source": "pubmed",
                    "status": "error",
                    "items_found": 12,
                    "items_new": 5,
                    "items_filtered": 2,
                    "errors": [{"message": "PubMed down"}],
                    "duration_s": 1.25,
                }
            ],
            resumed_skipped=["arxiv", "crossref"],
        )

        result = cli_runner.invoke(collect_app, ["--domain", "medical-research"])

        assert result.exit_code == 0, result.output
        assert "✗ pubmed: 5 new / 12 found (2 filtered) (1.2s)" in result.output
        assert "↳ PubMed down" in result.output
        assert "resumed: skipped 2 completed source(s): arxiv, crossref" in result.output
        assert "Total: 5 new items from 12 found in 1.2s" in result.output

    @patch("autoinfo.collect.run_collection")
    def test_progress_printer_reports_each_source_live(
        self, mock_run: MagicMock, cli_runner
    ) -> None:
        captured: dict[str, Any] = {}

        def _fake_run(**kwargs: Any) -> dict[str, Any]:
            captured.update(kwargs)
            progress_cb = kwargs["progress_cb"]
            assert progress_cb is not None, "human mode must get a progress callback"
            progress_cb(
                SimpleNamespace(
                    status="success",
                    source="pubmed",
                    items_new=3,
                    items_found=10,
                    items_filtered=2,
                    duration_s=1.5,
                )
            )
            progress_cb(
                SimpleNamespace(
                    status="weird-status",
                    source="rss",
                    items_new=0,
                    items_found=1,
                    items_filtered=0,
                    duration_s=0.0,
                )
            )
            return _collection_result()

        mock_run.side_effect = _fake_run

        result = cli_runner.invoke(collect_app, ["--domain", "medical-research"])

        assert result.exit_code == 0, result.output
        assert "✓ pubmed: 3 new / 10 found (2 filtered) (1.5s)" in result.output
        assert "? rss: 0 new / 1 found (0.0s)" in result.output
