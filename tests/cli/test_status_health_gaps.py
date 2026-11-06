"""Coverage for autoinfo.status source-health internals + the CLI report card.

Backfills the paths the 2026-11-06 goal work left below the coverage floor
(cli/validate.py detail_lines render; status.py health aggregation branches).
Direct, hermetic unit tests — no network, no global config.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from autoinfo import status as status_mod
from autoinfo.cli.validate import _render_report_card
from autoinfo.validation_matrix import MatrixReport


def _write_runs(
    autoinfo_dir: Path,
    domain: str,
    source: str,
    runs: list[dict[str, Any]],
) -> None:
    """_collect_source_health resolves runs at autoinfo_dir.parent/collections."""
    runs_dir = autoinfo_dir.parent / "collections" / domain / source
    runs_dir.mkdir(parents=True, exist_ok=True)
    (runs_dir / "_runs.json").write_text(json.dumps(runs), encoding="utf-8")


def _recent_ts(days: int = 0) -> str:
    return (date.today() - timedelta(days=days)).isoformat()


class TestCollectSourceHealth:
    def test_healthy_recent_successful_run(self, tmp_path: Path) -> None:
        _write_runs(
            tmp_path / ".autoinfo",
            "d1",
            "s1",
            [{"timestamp": _recent_ts(), "status": "success"}],
        )
        health = status_mod._collect_source_health(
            tmp_path / ".autoinfo", "d1", [SimpleNamespace(name="s1")]
        )
        assert health[0]["status"] == "healthy"
        assert health[0]["total_runs"] == 1

    def test_stale_old_run(self, tmp_path: Path) -> None:
        _write_runs(
            tmp_path / ".autoinfo",
            "d1",
            "s1",
            [{"timestamp": _recent_ts(days=30), "status": "success"}],
        )
        health = status_mod._collect_source_health(
            tmp_path / ".autoinfo", "d1", [SimpleNamespace(name="s1")]
        )
        assert health[0]["status"] == "stale"

    def test_disabled_auto_breaker_state(self, tmp_path: Path) -> None:
        _write_runs(
            tmp_path / ".autoinfo",
            "d1",
            "s1",
            [{"timestamp": _recent_ts(), "status": "disabled_auto"}],
        )
        health = status_mod._collect_source_health(
            tmp_path / ".autoinfo", "d1", [SimpleNamespace(name="s1")]
        )
        assert health[0]["status"] == "disabled_auto"

    def test_misconfigured_explicit_skip_reason(self, tmp_path: Path) -> None:
        _write_runs(
            tmp_path / ".autoinfo",
            "d1",
            "s1",
            [{"timestamp": _recent_ts(), "status": "skipped", "skip_reason": "credential_missing"}],
        )
        health = status_mod._collect_source_health(
            tmp_path / ".autoinfo", "d1", [SimpleNamespace(name="s1")]
        )
        assert health[0]["status"] == "misconfigured"

    def test_misconfigured_marker_fallback(self, tmp_path: Path) -> None:
        """Pre-skip_reason records: the marker path reads errors[] directly."""
        _write_runs(
            tmp_path / ".autoinfo",
            "d1",
            "s1",
            [
                {
                    "timestamp": _recent_ts(),
                    "status": "skipped",
                    "errors": [{"robots_disallowed": True}],
                }
            ],
        )
        health = status_mod._collect_source_health(
            tmp_path / ".autoinfo", "d1", [SimpleNamespace(name="s1")]
        )
        assert health[0]["status"] == "misconfigured"

    def test_unknown_without_runs_file(self, tmp_path: Path) -> None:
        health = status_mod._collect_source_health(
            tmp_path / ".autoinfo", "d1", [SimpleNamespace(name="ghost")]
        )
        assert health[0]["status"] == "unknown"

    def test_error_on_unparsable_runs(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "collections" / "d1" / "s1"
        runs_dir.mkdir(parents=True)
        (runs_dir / "_runs.json").write_text("{not json", encoding="utf-8")
        health = status_mod._collect_source_health(
            tmp_path / ".autoinfo", "d1", [SimpleNamespace(name="s1")]
        )
        assert health[0]["status"] == "error"


def test_runs_skip_reason_from_markers() -> None:
    assert status_mod._runs_skip_reason_from_markers({"errors": [{"app_review_required": 1}]}) == (
        "app_review_required"
    )
    assert status_mod._runs_skip_reason_from_markers({"errors": ["not-a-dict"]}) == ""
    assert status_mod._runs_skip_reason_from_markers({"errors": None}) == ""
    assert status_mod._runs_skip_reason_from_markers({}) == ""


def test_is_recent() -> None:
    assert status_mod._is_recent(_recent_ts()) is True
    assert status_mod._is_recent("") is False
    assert status_mod._is_recent("not-a-date") is False
    assert status_mod._is_recent(_recent_ts(days=30)) is False


class TestResolveDomains:
    def test_named_domain_found(self) -> None:
        d1 = SimpleNamespace(name="a", active=True)
        config = SimpleNamespace(domains=[d1])
        assert status_mod._resolve_domains(config, "a") == [d1]

    def test_named_domain_missing(self) -> None:
        config = SimpleNamespace(domains=[SimpleNamespace(name="a", active=True)])
        assert status_mod._resolve_domains(config, "b") == []

    def test_all_active_domains(self) -> None:
        active = SimpleNamespace(name="a", active=True)
        inactive = SimpleNamespace(name="b", active=False)
        assert status_mod._resolve_domains(SimpleNamespace(domains=[active, inactive]), None) == [
            active
        ]


class TestShowStatusFilesystemFallback:
    def test_fs_fallback_counts_when_index_missing(self, tmp_path: Path) -> None:
        """No SQLite index + files on disk → counts come from the filesystem."""
        (tmp_path / "knowledge" / "d1").mkdir(parents=True)
        today = date.today().isoformat()
        (tmp_path / "knowledge" / "d1" / f"entry-{today}.md").write_text("x", encoding="utf-8")
        (tmp_path / "knowledge" / "d1" / "entry-old.md").write_text("x", encoding="utf-8")
        config = SimpleNamespace(
            domains=[SimpleNamespace(name="d1", active=True, sources=[])],
            config_path=tmp_path / ".autoinfo" / "config.yaml",
        )
        (tmp_path / ".autoinfo").mkdir(exist_ok=True)
        (tmp_path / ".autoinfo" / "config.yaml").write_text("domains: []", encoding="utf-8")
        with (
            patch.object(status_mod, "get_config_path", return_value=config.config_path),
            patch.object(status_mod, "load_config", return_value=config),
            patch("pathlib.Path.cwd", return_value=tmp_path),
        ):
            report = status_mod.show_status("d1")
        domain = report["domains"][0]
        assert domain["total_entries"] == 2
        assert domain["items_today"] == 1


class TestRenderReportCardDetailLines:
    def _report(self, assertions: list[dict[str, Any]]) -> MatrixReport:
        return MatrixReport(
            commit="deadbeef",
            products=[
                {
                    "domain": "d1",
                    "product": "digest",
                    "status": "failed",
                    "assertions": assertions,
                }
            ],
            summary={"total_products": 1, "total_asserts": len(assertions), "passed": 0},
        )

    def test_failing_assertions_are_attributable(self, capsys: Any) -> None:
        _render_report_card(
            self._report(
                [
                    {
                        "name": "assert-a",
                        "passed": False,
                        "issue": "placeholder leaked\nsecond line",
                    },
                    {"name": "assert-b", "passed": True, "issue": "ignored"},
                ]
            )
        )
        out = capsys.readouterr().out
        assert "d1/digest :: assert-a — placeholder leaked second line" in out
        assert "assert-b" not in out

    def test_more_than_thirty_details_are_summarized(self, capsys: Any) -> None:
        assertions = [
            {"name": f"assert-{i}", "passed": False, "issue": f"issue-{i}"} for i in range(35)
        ]
        _render_report_card(self._report(assertions))
        out = capsys.readouterr().out
        assert "5 more failing assertions" in out
