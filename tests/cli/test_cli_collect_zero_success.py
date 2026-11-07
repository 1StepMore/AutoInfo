"""B14: ``collect`` must exit non-zero when no source succeeded.

A run where every attempted source errored (network down, all 403, proxy
broken) currently printed ``Total: 0 new items from 0 found`` and exited 0,
so batch scripts recorded it as a healthy run.  These tests lock the new
contract: only fix the exit code when every attempted source failed, never
when at least one succeeded or when no source was attempted at all.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from autoinfo.cli.collect import app as collect_app
from tests._ansi import strip_ansi


@pytest.fixture(autouse=True)
def _hermetic(tmp_path, monkeypatch):
    """Pin config discovery to ``tmp_path`` so no real config leaks in."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    yield


def _write_config(tmp_path, domains: list[dict[str, Any]]) -> None:
    config_dir = tmp_path / ".autoinfo"
    config_dir.mkdir(exist_ok=True)
    (config_dir / "config.yaml").write_text(
        json.dumps({"project": {"name": "zero"}, "domains": domains}),
        encoding="utf-8",
    )


def _domain_entry(name: str) -> dict[str, Any]:
    return {
        "name": name,
        "active": True,
        "sources": [{"name": "pubmed", "type": "api", "url": "https://example.com"}],
        "topics": [{"name": "t", "keywords": ["k"]}],
    }


def _per_source(status: str, source: str = "pubmed") -> dict[str, Any]:
    return {
        "source": source,
        "status": status,
        "items_found": 0,
        "items_new": 0,
        "items_filtered": 0,
        "errors": [{"message": "boom"}] if status == "error" else [],
        "duration_s": 0.1,
    }


def _result(domain: str, statuses: list[str], **overrides: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "collection_id": f"col-{domain}",
        "domain": domain,
        "total_found": 0,
        "total_new": 0,
        "duration_s": 0.1,
        "per_source": [_per_source(s, f"src{i}") for i, s in enumerate(statuses)],
        "dry_run": False,
        "resumed_skipped": [],
    }
    result.update(overrides)
    return result


class TestCollectZeroSuccess:
    @patch("autoinfo.collect.run_collection")
    def test_all_domains_all_errors_exits_nonzero(
        self, mock_run: MagicMock, cli_runner, tmp_path
    ) -> None:
        _write_config(tmp_path, [_domain_entry("alpha"), _domain_entry("beta")])
        mock_run.side_effect = lambda **kw: _result(kw["domain"], ["error", "error"])

        result = cli_runner.invoke(collect_app, ["--all"])

        assert result.exit_code != 0, result.output
        assert "no source succeeded" in strip_ansi(result.output)

    @patch("autoinfo.collect.run_collection")
    def test_all_domains_one_success_exits_zero(
        self, mock_run: MagicMock, cli_runner, tmp_path
    ) -> None:
        _write_config(tmp_path, [_domain_entry("alpha"), _domain_entry("beta")])
        mock_run.side_effect = lambda **kw: _result(kw["domain"], ["error", "success"])

        result = cli_runner.invoke(collect_app, ["--all"])

        assert result.exit_code == 0, result.output
        assert "no source succeeded" not in strip_ansi(result.output)

    @patch("autoinfo.collect.run_collection")
    def test_all_domains_unattempted_sources_exit_zero(
        self, mock_run: MagicMock, cli_runner, tmp_path
    ) -> None:
        _write_config(tmp_path, [_domain_entry("alpha"), _domain_entry("beta")])
        mock_run.side_effect = lambda **kw: _result(kw["domain"], ["skipped", "disabled_auto"])

        result = cli_runner.invoke(collect_app, ["--all"])

        assert result.exit_code == 0, result.output
        assert "no source succeeded" not in strip_ansi(result.output)

    @patch("autoinfo.collect.run_collection")
    def test_single_domain_all_errors_exits_nonzero(
        self, mock_run: MagicMock, cli_runner
    ) -> None:
        mock_run.return_value = _result("medical-research", ["error"])

        result = cli_runner.invoke(collect_app, ["--domain", "medical-research"])

        assert result.exit_code != 0, result.output
        assert "no source succeeded" in strip_ansi(result.output)

    @patch("autoinfo.collect.run_collection")
    def test_dry_run_all_errors_does_not_exit(self, mock_run: MagicMock, cli_runner) -> None:
        mock_run.return_value = _result("medical-research", ["error"], dry_run=True)

        result = cli_runner.invoke(collect_app, ["--domain", "medical-research", "--dry-run"])

        assert result.exit_code == 0, result.output
        assert "no source succeeded" not in strip_ansi(result.output)
