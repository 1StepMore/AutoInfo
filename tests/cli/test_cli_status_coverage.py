"""Coverage for the status CLI additions: ``--metrics`` output (human +
global ``--json``), the ValueError/ImportError handlers, and the
no-domains human branch.

Complements ``test_cli_commands.py`` (human/JSON happy path, FileNotFoundError).
"""

from __future__ import annotations

import json
import sys
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from autoinfo.cli import _output
from autoinfo.cli import app as main_app
from autoinfo.cli.status import app as status_app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _hermetic(tmp_path, monkeypatch):
    """Isolate cwd + HOME; reset the global-json context afterwards."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    yield
    _output.set_global_json(False)


_PROMETHEUS_SAMPLE = (
    "# HELP autoinfo_collections_total 3\n# TYPE autoinfo_collections_total counter\n"
)


class TestStatusMetrics:
    @patch("autoinfo.metrics.format_prometheus", return_value=_PROMETHEUS_SAMPLE)
    @patch("autoinfo.metrics.get_metrics", return_value={"collections_total": 3})
    def test_metrics_prints_prometheus_text(
        self, mock_get_metrics: MagicMock, mock_format: MagicMock
    ) -> None:
        result = runner.invoke(status_app, ["--metrics"])

        assert result.exit_code == 0, result.output
        assert _PROMETHEUS_SAMPLE in result.output
        mock_get_metrics.assert_called_once_with()

    @patch("autoinfo.metrics.format_prometheus", return_value=_PROMETHEUS_SAMPLE)
    @patch("autoinfo.metrics.get_metrics", return_value={"collections_total": 3})
    def test_metrics_global_json_emits_envelope(
        self, mock_get_metrics: MagicMock, mock_format: MagicMock
    ) -> None:
        result = runner.invoke(main_app, ["--json", "status", "--metrics"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert payload["success"] is True
        assert payload["data"] == {"format": "prometheus", "content": _PROMETHEUS_SAMPLE}

    @patch("autoinfo.metrics.get_metrics", side_effect=RuntimeError("registry down"))
    def test_metrics_failure_exits_nonzero(self, mock_get_metrics: MagicMock) -> None:
        result = runner.invoke(status_app, ["--metrics"])

        assert result.exit_code == 1, result.output
        assert "Error: registry down" in result.output


class TestStatusErrorHandlers:
    @patch("autoinfo.status.show_status", side_effect=ValueError("unknown domain"))
    def test_value_error_exits_nonzero(self, mock_show: MagicMock) -> None:
        result = runner.invoke(status_app, ["--domain", "nope"])

        assert result.exit_code == 1, result.output
        assert "Error: unknown domain" in result.output

    def test_missing_status_module_exits_nonzero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(sys.modules, "autoinfo.status", None)

        result = runner.invoke(status_app, [])

        assert result.exit_code == 1, result.output
        assert "status module not available" in result.output


class TestStatusHumanOutput:
    @patch("autoinfo.status.show_status", return_value={"domains": []})
    def test_no_domains_prints_placeholder(self, mock_show: MagicMock) -> None:
        result = runner.invoke(status_app, ["--domain", "empty-domain"])

        assert result.exit_code == 0, result.output
        assert "No domains found." in result.output
        mock_show.assert_called_once_with(domain="empty-domain")
