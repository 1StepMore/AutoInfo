"""Unit tests for the structured run report (B2.6 / F69, TR-A-01/TR-A-02)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from autoinfo.mcp.validation import save_scenario_results
from autoinfo.output import run_report

SESSION_ID = "11111111-1111-1111-1111-111111111111"


def _step(
    name: str,
    status: str = "passed",
    *,
    step_index: int = 1,
    detail: Any = None,
    recovered: bool = False,
) -> dict[str, Any]:
    step = {
        "name": name,
        "tool": "fake_tool",
        "status": status,
        "step_index": step_index,
        "step_id": str(step_index),
        "duration": 0.1,
        "arguments": {},
        "trace_id": f"trace-{name}",
        "session_id": SESSION_ID,
    }
    if detail is not None:
        step["detail"] = detail
    if recovered:
        step["recovered"] = True
        step["recovery"] = [{"name": f"{name}-recovery", "status": "passed"}]
    return step


def _result(
    name: str = "s1",
    status: str = "passed",
    *,
    steps: list[dict[str, Any]] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "scenario": name,
        "status": status,
        "session_id": SESSION_ID,
        "trace_id": f"trace-{name}",
        "pipeline_stage": "A4",
        "user_level": "B2.4",
        "pyramid_layer": "component",
        "category": "happy_path",
        "summary": {"passed": 1, "failed": 0, "unconfigured": 0, "recovered": 0, "total": 1},
        "steps": steps if steps is not None else [_step("step")],
    }
    result.update(extra)
    return result


class TestBuildRunReport:
    def test_summary_and_ordered_decision_trail(self) -> None:
        report = run_report.build_run_report(
            SESSION_ID,
            [_result("a"), _result("b", "failed")],
            kind="suite",
        )
        assert report["session_id"] == SESSION_ID
        assert report["kind"] == "suite"
        assert report["summary"]["total"] == 2
        assert report["summary"]["passed"] == 1
        assert report["summary"]["failed"] == 1

        decisions = report["decisions"]
        assert [d["seq"] for d in decisions] == list(range(1, len(decisions) + 1))
        assert [d["level"] for d in decisions] == ["scenario", "step", "scenario", "step"]
        assert all(d["session_id"] == SESSION_ID for d in decisions)
        assert all(v["pipeline_stage"] == "A4" for v in report["verdicts"])

    def test_requires_non_empty_session_id(self) -> None:
        with pytest.raises(ValueError, match="session_id"):
            run_report.build_run_report("", [])

    def test_anomalies_classify_failure_timeout_recovered_and_warning(self) -> None:
        failed = _result(
            "failed",
            "failed",
            steps=[_step("boom", "failed", detail="timed out after 1s")],
        )
        recovered = _result(
            "recovered",
            "passed",
            steps=[_step("flaky", "failed", recovered=True)],
        )
        warned = _result("warned", "passed", warnings=["SCENARIO_LEAK: x"])
        report = run_report.build_run_report(SESSION_ID, [failed, recovered, warned])
        kinds = [a["kind"] for a in report["anomalies"]]
        assert run_report.ANOMALY_SCENARIO_FAILED in kinds
        assert run_report.ANOMALY_STEP_FAILED not in kinds
        assert run_report.ANOMALY_TIMEOUT in kinds
        assert run_report.ANOMALY_RECOVERED in kinds
        assert run_report.ANOMALY_WARNING in kinds
        assert report["summary"]["anomalies"] == len(report["anomalies"])

    def test_report_is_json_serializable(self) -> None:
        report = run_report.build_run_report(SESSION_ID, [_result()])
        assert json.loads(json.dumps(report))["session_id"] == SESSION_ID


class TestPersistAndLoad:
    def test_persist_and_load_roundtrip(self, tmp_path: Path) -> None:
        report = run_report.build_run_report(SESSION_ID, [_result()])
        path = run_report.persist_run_report(report, runs_dir=tmp_path)
        assert path.is_file()
        assert path.name == f"{SESSION_ID}.json"
        loaded = run_report.load_run_report(SESSION_ID, runs_dir=tmp_path)
        assert loaded is not None
        assert loaded["decisions"] == report["decisions"]

    def test_load_unknown_returns_none(self, tmp_path: Path) -> None:
        assert run_report.load_run_report("nope", runs_dir=tmp_path) is None

    def test_load_falls_back_to_saved_run(self, tmp_path: Path) -> None:
        save_scenario_results(
            [_result("legacy", "passed")],
            runs_dir=tmp_path,
            run_type="suite",
            session_id=SESSION_ID,
        )
        loaded = run_report.load_run_report(SESSION_ID, runs_dir=tmp_path)
        assert loaded is not None
        assert loaded["kind"] == "suite"
        assert loaded["verdicts"][0]["scenario"] == "legacy"
