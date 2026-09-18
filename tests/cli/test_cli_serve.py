"""Coverage for the ``serve`` CLI entry (``autoinfo serve``, read-only agent
mode, subcommand guard, and the ``python -m autoinfo.cli.serve`` script
entry).

The MCP server itself is never started: ``autoinfo.mcp.server.run`` is
patched, and the tests assert on how the CLI wires ``readonly``.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from autoinfo.cli import app as main_app
from autoinfo.cli.serve import serve

runner = CliRunner()

_SERVE_MODULE = Path(__file__).resolve().parents[2] / "src" / "autoinfo" / "cli" / "serve.py"


class TestServeCommand:
    @patch("autoinfo.mcp.server.run")
    def test_serve_agent_mode_starts_readonly_server(self, mock_run: MagicMock) -> None:
        result = runner.invoke(main_app, ["serve", "--agent"])

        assert result.exit_code == 0, result.output
        mock_run.assert_called_once_with(readonly=True)

    @patch("autoinfo.mcp.server.run")
    def test_serve_without_agent_starts_full_server(self, mock_run: MagicMock) -> None:
        """Default (no --agent) wiring starts the full server, readonly=False.

        Invoked directly because ``no_args_is_help=True`` means a bare
        ``autoinfo serve`` prints help without reaching the callback.
        """
        serve(ctx=MagicMock(invoked_subcommand=None), agent=False)

        mock_run.assert_called_once_with(readonly=False)

    @patch("autoinfo.mcp.server.run")
    def test_serve_guard_ignores_invoked_subcommand(self, mock_run: MagicMock) -> None:
        """A subcommand context must not start the stdio server."""
        serve(ctx=MagicMock(invoked_subcommand="some-subcommand"), agent=False)

        mock_run.assert_not_called()


class TestServeScriptEntry:
    def test_module_entry_prints_help_and_exits_zero(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``python -m autoinfo.cli.serve`` delegates to the same Typer app."""
        monkeypatch.setattr(sys, "argv", ["serve", "--help"])

        with pytest.raises(SystemExit) as excinfo:
            runpy.run_path(str(_SERVE_MODULE), run_name="__main__")

        assert excinfo.value.code == 0
        assert "Run the AutoInfo MCP server" in capsys.readouterr().out
