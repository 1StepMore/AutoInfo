"""Tests for CLI v2 subcommand stubs: sources, topics, kb, output, cron.

Uses ``CliRunner`` to invoke ``--help`` on each subcommand and verify
the expected command names and options appear in the output.  No core
logic is tested — the stubs only print ``"not yet implemented"``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests._ansi import strip_ansi

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cli_runner() -> Any:
    """Return a CliRunner instance."""
    from typer.testing import CliRunner

    return CliRunner()


@pytest.fixture
def app() -> Any:
    """Return the AutoInfo CLI app."""
    from autoinfo.cli import app

    return app


# ---------------------------------------------------------------------------
# autoinfo sources
# ---------------------------------------------------------------------------


class TestSourcesCommand:
    """Tests for ``autoinfo sources`` stub."""

    def test_sources_shows_in_help(self, cli_runner: Any, app: Any) -> None:
        """``autoinfo --help`` lists the sources subcommand."""
        result = cli_runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "sources" in strip_ansi(result.stdout)

    def test_sources_help_shows_commands(self, cli_runner: Any, app: Any) -> None:
        """``autoinfo sources --help`` shows add, list, remove, test."""
        result = cli_runner.invoke(app, ["sources", "--help"])
        assert result.exit_code == 0
        assert "add" in strip_ansi(result.stdout)
        assert "list" in strip_ansi(result.stdout)
        assert "remove" in strip_ansi(result.stdout)
        assert "test" in strip_ansi(result.stdout)

    def test_sources_add_help_shows_options(self, cli_runner: Any, app: Any) -> None:
        """``autoinfo sources add --help`` shows all MCP add_source params."""
        result = cli_runner.invoke(app, ["sources", "add", "--help"])
        assert result.exit_code == 0
        assert "--name" in strip_ansi(result.stdout)
        assert "--url" in strip_ansi(result.stdout)
        assert "--type" in strip_ansi(result.stdout)
        assert "--domain" in strip_ansi(result.stdout)
        assert "--settings" in strip_ansi(result.stdout)
        assert "--requires-key" in strip_ansi(result.stdout)
        assert "--no-requires-key" in strip_ansi(result.stdout)
        assert "--imap-server" in strip_ansi(result.stdout)
        assert "--imap-port" in strip_ansi(result.stdout)
        assert "--imap-username" in strip_ansi(result.stdout)
        assert "--imap-password" in strip_ansi(result.stdout)
        assert "--imap-mailbox" in strip_ansi(result.stdout)
        assert "--webhook-secret" in strip_ansi(result.stdout)

    def test_sources_list_help_shows_options(self, cli_runner: Any, app: Any) -> None:
        """``autoinfo sources list --help`` shows --domain."""
        result = cli_runner.invoke(app, ["sources", "list", "--help"])
        assert result.exit_code == 0
        assert "--domain" in strip_ansi(result.stdout)

    def test_sources_remove_help_shows_options(self, cli_runner: Any, app: Any) -> None:
        """``autoinfo sources remove --help`` shows --domain, --source-id."""
        result = cli_runner.invoke(app, ["sources", "remove", "--help"])
        assert result.exit_code == 0
        assert "--domain" in strip_ansi(result.stdout)
        assert "--source-id" in strip_ansi(result.stdout)

    def test_sources_test_help_shows_options(self, cli_runner: Any, app: Any) -> None:
        """``autoinfo sources test --help`` shows --url, --type."""
        result = cli_runner.invoke(app, ["sources", "test", "--help"])
        assert result.exit_code == 0
        assert "--url" in strip_ansi(result.stdout)
        assert "--type" in strip_ansi(result.stdout)

    def test_sources_add_requires_domain(self, cli_runner: Any, app: Any, tmp_path: Path) -> None:
        """``autoinfo sources add`` fails when domain is not configured."""
        from unittest.mock import patch

        import yaml

        config_dir = tmp_path / ".autoinfo"
        config_dir.mkdir(exist_ok=True)
        (config_dir / "config.yaml").write_text(
            yaml.dump(
                {
                    "project": {"name": "T", "created_at": ""},
                    "llm": {"provider": "openai", "model": "m", "api_key": ""},
                    "domains": [],
                }
            ),
            encoding="utf-8",
        )
        with patch("pathlib.Path.cwd", return_value=tmp_path):
            result = cli_runner.invoke(
                app,
                [
                    "sources",
                    "add",
                    "--name",
                    "test",
                    "--url",
                    "https://example.com",
                    "--type",
                    "api",
                    "--domain",
                    "test-domain",
                ],
            )
        assert result.exit_code != 0
        assert "not configured" in strip_ansi(result.stderr)


# ---------------------------------------------------------------------------
# autoinfo topics
# ---------------------------------------------------------------------------


class TestTopicsCommand:
    """Tests for ``autoinfo topics`` stub."""

    def test_topics_shows_in_help(self, cli_runner: Any, app: Any) -> None:
        """``autoinfo --help`` lists the topics subcommand."""
        result = cli_runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "topics" in strip_ansi(result.stdout)

    def test_topics_help_shows_commands(self, cli_runner: Any, app: Any) -> None:
        """``autoinfo topics --help`` shows add, list, remove."""
        result = cli_runner.invoke(app, ["topics", "--help"])
        assert result.exit_code == 0
        assert "add" in strip_ansi(result.stdout)
        assert "list" in strip_ansi(result.stdout)
        assert "remove" in strip_ansi(result.stdout)

    def test_topics_add_help_shows_options(self, cli_runner: Any, app: Any) -> None:
        """``autoinfo topics add --help`` shows --domain, --name, --keywords."""
        result = cli_runner.invoke(app, ["topics", "add", "--help"])
        assert result.exit_code == 0
        assert "--domain" in strip_ansi(result.stdout)
        assert "--name" in strip_ansi(result.stdout)
        assert "--keywords" in strip_ansi(result.stdout)

    def test_topics_list_help_shows_options(self, cli_runner: Any, app: Any) -> None:
        """``autoinfo topics list --help`` shows --domain."""
        result = cli_runner.invoke(app, ["topics", "list", "--help"])
        assert result.exit_code == 0
        assert "--domain" in strip_ansi(result.stdout)

    def test_topics_remove_help_shows_options(self, cli_runner: Any, app: Any) -> None:
        """``autoinfo topics remove --help`` shows --domain, --topic-id."""
        result = cli_runner.invoke(app, ["topics", "remove", "--help"])
        assert result.exit_code == 0
        assert "--domain" in strip_ansi(result.stdout)
        assert "--topic-id" in strip_ansi(result.stdout)


# ---------------------------------------------------------------------------
# autoinfo kb
# ---------------------------------------------------------------------------


class TestKbCommand:
    """Tests for ``autoinfo kb`` stub."""

    def test_kb_shows_in_help(self, cli_runner: Any, app: Any) -> None:
        """``autoinfo --help`` lists the kb subcommand."""
        result = cli_runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "kb" in strip_ansi(result.stdout)

    def test_kb_help_shows_commands(self, cli_runner: Any, app: Any) -> None:
        """``autoinfo kb --help`` shows search, list, reindex, promote."""
        result = cli_runner.invoke(app, ["kb", "--help"])
        assert result.exit_code == 0
        assert "search" in strip_ansi(result.stdout)
        assert "list" in strip_ansi(result.stdout)
        assert "reindex" in strip_ansi(result.stdout)
        assert "promote" in strip_ansi(result.stdout)

    def test_kb_search_help_shows_options(self, cli_runner: Any, app: Any) -> None:
        """``autoinfo kb search --help`` shows --query, --domain, --limit, --offset."""
        result = cli_runner.invoke(app, ["kb", "search", "--help"])
        assert result.exit_code == 0
        assert "--query" in strip_ansi(result.stdout)
        assert "--domain" in strip_ansi(result.stdout)
        assert "--limit" in strip_ansi(result.stdout)
        assert "--offset" in strip_ansi(result.stdout)

    def test_kb_list_help_shows_options(self, cli_runner: Any, app: Any) -> None:
        """``autoinfo kb list --help`` shows --domain, --tier."""
        result = cli_runner.invoke(app, ["kb", "list", "--help"])
        assert result.exit_code == 0
        assert "--domain" in strip_ansi(result.stdout)
        assert "--tier" in strip_ansi(result.stdout)

    def test_kb_reindex_help_shows_options(self, cli_runner: Any, app: Any) -> None:
        """``autoinfo kb reindex --help`` shows --domain."""
        result = cli_runner.invoke(app, ["kb", "reindex", "--help"])
        assert result.exit_code == 0
        assert "--domain" in strip_ansi(result.stdout)

    def test_kb_promote_help_shows_options(self, cli_runner: Any, app: Any) -> None:
        """``autoinfo kb promote --help`` shows --entry-id."""
        result = cli_runner.invoke(app, ["kb", "promote", "--help"])
        assert result.exit_code == 0
        assert "--entry-id" in strip_ansi(result.stdout)


# ---------------------------------------------------------------------------
# autoinfo output
# ---------------------------------------------------------------------------


class TestOutputCommand:
    """Tests for ``autoinfo output`` stub."""

    def test_output_shows_in_help(self, cli_runner: Any, app: Any) -> None:
        """``autoinfo --help`` lists the output subcommand."""
        result = cli_runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "output" in strip_ansi(result.stdout)

    def test_output_help_shows_commands(self, cli_runner: Any, app: Any) -> None:
        """``autoinfo output --help`` shows digest, report, export."""
        result = cli_runner.invoke(app, ["output", "--help"])
        assert result.exit_code == 0
        assert "digest" in strip_ansi(result.stdout)
        assert "report" in strip_ansi(result.stdout)
        assert "export" in strip_ansi(result.stdout)

    def test_output_digest_help_shows_options(self, cli_runner: Any, app: Any) -> None:
        """``autoinfo output digest --help`` shows all MCP generate_digest params."""
        result = cli_runner.invoke(app, ["output", "digest", "--help"])
        assert result.exit_code == 0
        assert "--domain" in strip_ansi(result.stdout)
        assert "--period" in strip_ansi(result.stdout)
        assert "--format" in strip_ansi(result.stdout)
        assert "--custom-instructions" in strip_ansi(result.stdout)
        assert "--target-audience" in strip_ansi(result.stdout)
        assert "--include-stale" in strip_ansi(result.stdout)
        assert "--recipients" in strip_ansi(result.stdout)
        assert "--max-items" in strip_ansi(result.stdout)
        assert "--persist" in strip_ansi(result.stdout)

    def test_output_report_help_shows_options(self, cli_runner: Any, app: Any) -> None:
        """``autoinfo output report --help`` shows --domain, --format."""
        result = cli_runner.invoke(app, ["output", "report", "--help"])
        assert result.exit_code == 0
        assert "--domain" in strip_ansi(result.stdout)
        assert "--format" in strip_ansi(result.stdout)

    def test_output_export_help_shows_options(self, cli_runner: Any, app: Any) -> None:
        """``autoinfo output export --help`` shows --domain, --format."""
        result = cli_runner.invoke(app, ["output", "export", "--help"])
        assert result.exit_code == 0
        assert "--domain" in strip_ansi(result.stdout)
        assert "--format" in strip_ansi(result.stdout)


# ---------------------------------------------------------------------------
# autoinfo cron
# ---------------------------------------------------------------------------


class TestCronCommand:
    """Tests for ``autoinfo cron`` stub."""

    def test_cron_shows_in_help(self, cli_runner: Any, app: Any) -> None:
        """``autoinfo --help`` lists the cron subcommand."""
        result = cli_runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "cron" in strip_ansi(result.stdout)

    def test_cron_help_shows_commands(self, cli_runner: Any, app: Any) -> None:
        """``autoinfo cron --help`` shows run, list-schedules, add-schedule, remove-schedule."""
        result = cli_runner.invoke(app, ["cron", "--help"])
        assert result.exit_code == 0
        assert "run" in strip_ansi(result.stdout)
        assert "list-schedules" in strip_ansi(result.stdout)
        assert "add-schedule" in strip_ansi(result.stdout)
        assert "remove-schedule" in strip_ansi(result.stdout)

    def test_cron_run_help(self, cli_runner: Any, app: Any) -> None:
        """``autoinfo cron run --help`` works."""
        result = cli_runner.invoke(app, ["cron", "run", "--help"])
        assert result.exit_code == 0

    def test_cron_list_schedules_help(self, cli_runner: Any, app: Any) -> None:
        """``autoinfo cron list-schedules --help`` works."""
        result = cli_runner.invoke(app, ["cron", "list-schedules", "--help"])
        assert result.exit_code == 0

    def test_cron_add_schedule_help_shows_options(
        self, cli_runner: Any, app: Any
    ) -> None:
        """``autoinfo cron add-schedule --help`` shows --name, --expression, --domain."""
        result = cli_runner.invoke(app, ["cron", "add-schedule", "--help"])
        assert result.exit_code == 0
        assert "--name" in strip_ansi(result.stdout)
        assert "--expression" in strip_ansi(result.stdout)
        assert "--domain" in strip_ansi(result.stdout)

    def test_cron_remove_schedule_help_shows_options(
        self, cli_runner: Any, app: Any
    ) -> None:
        """``autoinfo cron remove-schedule --help`` shows --name."""
        result = cli_runner.invoke(app, ["cron", "remove-schedule", "--help"])
        assert result.exit_code == 0
        assert "--name" in strip_ansi(result.stdout)


# ---------------------------------------------------------------------------
# autoinfo --help (all top-level commands)
# ---------------------------------------------------------------------------


class TestTopLevelHelp:
    """Verify all subcommands appear in top-level --help."""

    def test_help_lists_all_v2_commands(self, cli_runner: Any, app: Any) -> None:
        """Top-level --help lists sources, topics, kb, output, cron."""
        result = cli_runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        for cmd in ("sources", "topics", "kb", "output", "cron"):
            assert cmd in strip_ansi(result.stdout), f"'{cmd}' missing from --help"
