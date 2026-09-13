"""Session-level traceability + B2.6 structured run report (TR-A-01/TR-A-02).

Locks the agent-facing guarantees of the session correlation feature:

1. One session id spans every scenario and every step of a suite run, so a
   single id reconstructs the full action sequence.
2. ``run_all_scenarios`` persists a structured report (what ran, verdicts,
   anomalies) queryable by that id.
3. ``get_run_decisions`` returns the decision trail through the real MCP
   dispatch; an unknown id returns a canonical ``NotFound`` error envelope.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from mcp.types import CallToolRequest, CallToolRequestParams

from autoinfo.mcp import server as mcp_server
from autoinfo.mcp.validation import run_all_scenarios, run_scenario
from autoinfo.output import run_report

PASS_SCENARIO = """\
name: session-pass
description: "Passing scenario for session correlation"
category: happy_path
pyramid_layer: component
pipeline_stage: A4
user_level: B2.4
steps:
  - name: "first"
    tool: fake_tool
    arguments: {}
    expect:
      success: true
      data_has: ["result"]
  - name: "second"
    tool: fake_tool
    arguments: {}
    expect:
      success: true
      data_has: ["result"]
"""

FAIL_SCENARIO = """\
name: session-fail
description: "Failing scenario for anomaly reporting"
category: failure
pyramid_layer: e2e
pipeline_stage: A5
user_level: B2.5
steps:
  - name: "boom"
    tool: fake_tool
    arguments: {}
    expect:
      success: false
      error_code: "Timeout"
"""


async def _fake_dispatch(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "fake_tool":
        return {"success": True, "data": {"result": "ok"}}
    return {"success": True, "data": {}}


def _scenarios_dir(tmp_path: Path) -> Path:
    sd = tmp_path / "scenarios"
    sd.mkdir(exist_ok=True)
    (sd / "session-pass.yaml").write_text(PASS_SCENARIO, encoding="utf-8")
    (sd / "session-fail.yaml").write_text(FAIL_SCENARIO, encoding="utf-8")
    return sd


def _response_body(out: Any) -> dict[str, Any]:
    first = out[0]
    if isinstance(first, list):
        return json.loads(first[0].text)
    if hasattr(first, "text"):
        return json.loads(first.text)
    raise AssertionError(f"unexpected call_tool result shape: {out!r}")


class TestSessionCorrelation:
    """One correlation id spans every scenario and step of a suite run."""

    @pytest.mark.asyncio
    async def test_session_id_shared_by_all_scenarios_and_steps(self, tmp_path: Path) -> None:
        aggregate = await run_all_scenarios(
            dispatch=_fake_dispatch,
            scenarios_dir=_scenarios_dir(tmp_path),
            runs_dir=tmp_path,
            save=False,
        )
        session_id = aggregate["session_id"]
        assert session_id

        results = [
            await run_scenario(
                name,
                dispatch=_fake_dispatch,
                scenarios_dir=_scenarios_dir(tmp_path),
                session_id=session_id,
            )
            for name in ("session-pass", "session-fail")
        ]
        step_ids = set()
        for result in results:
            assert result["session_id"] == session_id
            assert result["trace_id"] != session_id
            for step in result["steps"]:
                assert step["session_id"] == session_id
                step_ids.add(step["session_id"])
        assert step_ids == {session_id}

    @pytest.mark.asyncio
    async def test_standalone_run_defaults_session_to_trace_id(self, tmp_path: Path) -> None:
        result = await run_scenario(
            "session-pass",
            dispatch=_fake_dispatch,
            scenarios_dir=_scenarios_dir(tmp_path),
        )
        assert result["session_id"] == result["trace_id"]
        assert all(s["session_id"] == result["trace_id"] for s in result["steps"])

    @pytest.mark.asyncio
    async def test_provided_session_id_overrides_the_default(self, tmp_path: Path) -> None:
        result = await run_scenario(
            "session-pass",
            dispatch=_fake_dispatch,
            scenarios_dir=_scenarios_dir(tmp_path),
            session_id="corr-abc",
        )
        assert result["session_id"] == "corr-abc"


class TestStructuredRunReport:
    """The persisted report records what ran, verdicts and anomalies."""

    @pytest.mark.asyncio
    async def test_suite_persists_queryable_structured_report(self, tmp_path: Path) -> None:
        aggregate = await run_all_scenarios(
            dispatch=_fake_dispatch,
            scenarios_dir=_scenarios_dir(tmp_path),
            runs_dir=tmp_path,
            save=True,
        )
        session_id = aggregate["session_id"]

        assert Path(aggregate["report_path"]).is_file()
        report = run_report.load_run_report(session_id, runs_dir=tmp_path)
        assert report is not None
        assert report["session_id"] == session_id
        assert report["kind"] == "suite"
        assert set(report) >= {
            "session_id",
            "kind",
            "summary",
            "verdicts",
            "decisions",
            "anomalies",
        }

        summary = report["summary"]
        assert summary["total"] == 2
        assert summary["passed"] == 1
        assert summary["failed"] == 1
        assert summary["anomalies"] >= 1

        verdicts = {v["scenario"]: v for v in report["verdicts"]}
        assert verdicts["session-pass"]["status"] == "passed"
        assert verdicts["session-pass"]["pipeline_stage"] == "A4"
        assert verdicts["session-pass"]["user_level"] == "B2.4"
        assert verdicts["session-fail"]["status"] == "failed"

        scenario_decisions = [d for d in report["decisions"] if d["level"] == "scenario"]
        step_decisions = [d for d in report["decisions"] if d["level"] == "step"]
        assert {d["scenario"] for d in scenario_decisions} == {"session-pass", "session-fail"}
        assert len(step_decisions) == 3
        assert all(d["session_id"] == session_id for d in report["decisions"])
        assert [d["seq"] for d in report["decisions"]] == list(
            range(1, len(report["decisions"]) + 1)
        )

        anomaly_kinds = {a["kind"] for a in report["anomalies"]}
        assert run_report.ANOMALY_SCENARIO_FAILED in anomaly_kinds


class TestGetRunDecisionsHandler:
    """The MCP tool returns the trail via the real dispatch."""

    @pytest.mark.asyncio
    async def test_handler_returns_trail_for_known_session(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(run_report, "DEFAULT_RUNS_DIR", tmp_path)
        aggregate = await run_all_scenarios(
            dispatch=_fake_dispatch,
            scenarios_dir=_scenarios_dir(tmp_path),
            runs_dir=tmp_path,
            save=True,
        )
        response = mcp_server._handle_get_run_decisions(aggregate["session_id"])
        assert response["success"] is True
        assert response["data"]["session_id"] == aggregate["session_id"]
        assert response["data"]["decisions"]

    @pytest.mark.asyncio
    async def test_unknown_session_returns_not_found_envelope(self) -> None:
        response = mcp_server._handle_get_run_decisions("no-such-session")
        assert response["success"] is False
        assert response["error"]["code"] == "NotFound"
        assert response["error"]["actionable"] is True

    @pytest.mark.asyncio
    async def test_tool_reachable_through_dispatch(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(run_report, "DEFAULT_RUNS_DIR", tmp_path)
        aggregate = await run_all_scenarios(
            dispatch=_fake_dispatch,
            scenarios_dir=_scenarios_dir(tmp_path),
            runs_dir=tmp_path,
            save=True,
        )
        handler = mcp_server.app.request_handlers[CallToolRequest]
        request = CallToolRequest(
            method="tools/call",
            params=CallToolRequestParams(
                name="get_run_decisions",
                arguments={"session_id": aggregate["session_id"]},
            ),
        )
        result = await handler(request)
        data = json.loads(result.root.content[0].text)
        assert data["success"] is True
        assert data["data"]["session_id"] == aggregate["session_id"]

    def test_tool_is_declared(self) -> None:
        names = [t.name for t in mcp_server._full_tool_list()]
        assert "get_run_decisions" in names
