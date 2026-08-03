"""Tests for the Agent-native MCP validation toolset.

Covers the scenario loader and executor (:mod:`autoinfo.mcp.validation`)
as well as the server-integrated MCP tools ``list_validation_scenarios``
and ``run_validation_scenario``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from mcp.types import CallToolRequest, CallToolRequestParams

from autoinfo.mcp import server as mcp_server
from autoinfo.mcp.validation import (
    _normalize_envelope,
    list_scenarios,
    load_scenarios,
    run_scenario,
)

# ============================================================================
# Unit tests: load_scenarios
# ============================================================================


class TestLoadScenarios:
    """Test the scenario YAML loader."""

    def test_loads_packaged_scenarios(self) -> None:
        """Should load 6 or more scenarios from the built-in scenarios/ dir."""
        scs = load_scenarios()
        assert len(scs) >= 6, f"Expected ≥6 scenarios, got {len(scs)}"

        for sc in scs:
            assert "name" in sc
            assert "description" in sc
            assert "steps" in sc
            assert isinstance(sc["steps"], list)
            assert len(sc["steps"]) >= 1
            for step in sc["steps"]:
                assert "name" in step
                # Each step must have a dispatch target for its kind:
                # mcp → tool, cli → command, http → url
                kind = step.get("kind", "mcp")
                assert ("tool" in step) or ("command" in step) or ("url" in step), (
                    f"step {step['name']!r} (kind={kind}) missing tool/command/url"
                )

    def test_loads_from_custom_dir(self, tmp_path: Path) -> None:
        """Should load scenarios from a user-provided directory."""
        sd = tmp_path / "scenarios"
        sd.mkdir()
        (sd / "my-test.yaml").write_text(
            "name: my-test\ndescription: Test\nsteps:\n"
            "  - name: step1\n    tool: health_check\n",
            encoding="utf-8",
        )
        scs = load_scenarios(sd)
        assert len(scs) == 1
        assert scs[0]["name"] == "my-test"

    def test_raises_on_bad_yaml(self, tmp_path: Path) -> None:
        """Bad YAML should raise ValueError."""
        sd = tmp_path / "scenarios"
        sd.mkdir()
        bad_path = sd / "bad.yaml"
        bad_path.write_text(": : : bad yaml\n", encoding="utf-8")

        with pytest.raises(ValueError, match="bad\\.yaml"):
            load_scenarios(sd)

    def test_raises_on_missing_name(self, tmp_path: Path) -> None:
        """Missing 'name' field should raise ValueError."""
        sd = tmp_path / "scenarios"
        sd.mkdir()
        (sd / "no-name.yaml").write_text(
            "description: Test\nsteps:\n  - name: s\n    tool: health_check\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="no-name\\.yaml.*missing.*'name'"):
            load_scenarios(sd)

    def test_raises_on_missing_steps(self, tmp_path: Path) -> None:
        """Missing 'steps' field should raise ValueError."""
        sd = tmp_path / "scenarios"
        sd.mkdir()
        (sd / "no-steps.yaml").write_text(
            "name: test\ndescription: Test\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="no-steps\\.yaml.*missing.*'steps'"):
            load_scenarios(sd)

    def test_raises_on_empty_steps(self, tmp_path: Path) -> None:
        """Empty steps list should raise ValueError."""
        sd = tmp_path / "scenarios"
        sd.mkdir()
        (sd / "empty-steps.yaml").write_text(
            "name: test\ndescription: Test\nsteps: []\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="empty-steps\\.yaml.*non-empty"):
            load_scenarios(sd)

    def test_raises_on_step_missing_name(self, tmp_path: Path) -> None:
        """Step missing 'name' should raise ValueError."""
        sd = tmp_path / "scenarios"
        sd.mkdir()
        (sd / "bad-step.yaml").write_text(
            "name: test\ndescription: Test\nsteps:\n  - tool: health_check\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="bad-step\\.yaml.*step\\[0\\].*'name'"):
            load_scenarios(sd)

    def test_raises_on_step_missing_tool(self, tmp_path: Path) -> None:
        """Step missing 'tool' should raise ValueError."""
        sd = tmp_path / "scenarios"
        sd.mkdir()
        (sd / "bad-step.yaml").write_text(
            "name: test\ndescription: Test\nsteps:\n  - name: s\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="bad-step\\.yaml.*step\\[0\\].*'tool'"):
            load_scenarios(sd)


# ============================================================================
# Unit tests: list_scenarios
# ============================================================================


class TestListScenarios:
    """Test the scenario listing function."""

    def test_returns_summary_shape(self) -> None:
        """Should return scenarios list with summary fields."""
        result = list_scenarios()
        assert "scenarios" in result
        assert "count" in result
        assert result["count"] >= 6
        for sc in result["scenarios"]:
            assert "name" in sc
            assert "description" in sc
            assert "category" in sc
            assert "step_count" in sc
            assert "requires_env" in sc


# ============================================================================
# Unit tests: _normalize_envelope
# ============================================================================


class TestNormalizeEnvelope:
    """Test the envelope normaliser for flat health_check responses."""

    def test_passes_through_envelope(self) -> None:
        """Envelope dicts pass through unchanged."""
        env = {"success": True, "data": {"key": "value"}}
        assert _normalize_envelope(env) == env

    def test_wraps_flat_dict(self) -> None:
        """Flat dicts (e.g. health_check) get wrapped into an envelope."""
        flat = {"status": "ok", "version": "1.0"}
        result = _normalize_envelope(flat)
        assert result["success"] is True
        assert result["data"] == flat

    def test_wraps_flat_error_error_code(self) -> None:
        """Flat error dicts with error_code (legacy) get wrapped."""
        flat = {"error_code": "NotFound", "message": "not found"}
        result = _normalize_envelope(flat)
        assert result["success"] is True  # no "success" key → treated as success
        assert result["data"] == flat


# ============================================================================
# Unit tests: run_scenario (with fake dispatch)
# ============================================================================


class TestRunScenarioFakeDispatch:
    """run_scenario tests using a controlled fake dispatch."""

    SCENARIO_YAML = """\
name: fake-scenario
description: "Fake scenario for unit testing"
category: test
requires_env: []
steps:
  - name: "all-pass step"
    tool: fake_tool
    arguments: {}
    expect:
      success: true
      data_has: ["result"]

  - name: "error-expected step"
    tool: fake_error
    arguments: {}
    expect:
      success: false
      error_code: "Timeout"

  - name: "missing-key step"
    tool: fake_tool
    arguments: {}
    expect:
      success: true
      data_has: ["missing_key"]
"""

    SCENARIO_LLM_YAML = """\
name: llm-scenario
description: "LLM-assert scenario"
category: test
requires_env: []
steps:
  - name: "llm-pass step"
    tool: fake_tool
    arguments: {}
    expect:
      success: true
      llm_assert: "Is the result ok?"

  - name: "llm-fail step"
    tool: fake_tool
    arguments: {}
    expect:
      success: true
      llm_assert: "Is the result bad?"
"""

    SCENARIO_ENV_GATED_YAML = """\
name: env-gated
description: "Env-gated scenario"
category: test
requires_env: ["MISSING_VAR_XYZ"]
steps:
  - name: "should report unconfigured"
    tool: health_check
    arguments: {}
"""

    @pytest.fixture
    def scenario_dir(self, tmp_path: Path) -> Path:
        sd = tmp_path / "scenarios"
        sd.mkdir()
        (sd / "fake-scenario.yaml").write_text(self.SCENARIO_YAML, encoding="utf-8")
        (sd / "llm-scenario.yaml").write_text(self.SCENARIO_LLM_YAML, encoding="utf-8")
        (sd / "env-gated.yaml").write_text(self.SCENARIO_ENV_GATED_YAML, encoding="utf-8")
        return sd

    async def _fake_dispatch(self, name: str, arguments: dict) -> dict:
        """Return controlled envelopes for fake tools."""
        if name == "fake_tool":
            return {"success": True, "data": {"result": "ok"}}
        if name == "fake_error":
            return {"success": False, "error": {"code": "Timeout", "message": "timeout"}}
        if name == "bad_tool":
            return 42  # non-dict response — should trigger exception
        return {"success": True, "data": {}}

    async def test_all_pass_scenario(self, scenario_dir: Path) -> None:
        """All-pass steps should return status 'passed'."""
        result = await run_scenario(
            "fake-scenario",
            dispatch=self._fake_dispatch,
            steps=[1, 2],
            scenarios_dir=scenario_dir,
        )
        assert result["status"] == "passed"
        assert result["summary"]["passed"] == 2
        assert result["summary"]["failed"] == 0
        assert result["summary"]["total"] == 2

    async def test_assertion_mismatch_fails(self, scenario_dir: Path) -> None:
        """An assertion mismatch should report failed step."""
        # Step 3 expects data_has: ["missing_key"] which is not in the response
        result = await run_scenario(
            "fake-scenario",
            dispatch=self._fake_dispatch,
            steps=[3],
            scenarios_dir=scenario_dir,
        )
        assert result["status"] == "failed"
        assert result["summary"]["failed"] == 1
        step = result["steps"][0]
        assert step["status"] == "failed"
        assert "missing_key" in step.get("detail", "")

    async def test_error_code_check_passes(self, scenario_dir: Path) -> None:
        """Error code assertion should pass when codes match."""
        result = await run_scenario(
            "fake-scenario",
            dispatch=self._fake_dispatch,
            steps=[2],
            scenarios_dir=scenario_dir,
        )
        assert result["status"] == "passed"

    async def test_error_code_check_fails_on_mismatch(self, tmp_path: Path) -> None:
        """Error code mismatch should report a failure."""
        sd = tmp_path / "scenarios"
        sd.mkdir()
        (sd / "bad-code.yaml").write_text(
            "name: bad-code\ndescription: Test\nsteps:\n"
            "  - name: step\n    tool: fake_error\n    arguments: {}\n"
            "    expect:\n      success: false\n      error_code: WrongCode\n",
            encoding="utf-8",
        )
        result = await run_scenario(
            "bad-code",
            dispatch=self._fake_dispatch,
            scenarios_dir=sd,
        )
        assert result["status"] == "failed"
        assert result["steps"][0]["status"] == "failed"
        assert "WrongCode" in result["steps"][0].get("detail", "")

    async def test_requires_env_reports_unconfigured(self, scenario_dir: Path) -> None:
        """Scenario with missing env var should report 'unconfigured' — not
        silently skipped. Director User is obligated to provide BYOK keys."""
        env_before = os.environ.pop("MISSING_VAR_XYZ", None)
        try:
            result = await run_scenario(
                "env-gated",
                dispatch=self._fake_dispatch,
                scenarios_dir=scenario_dir,
            )
            assert result["status"] == "unconfigured"
            assert "MISSING_VAR_XYZ" in result["unconfigured_reason"]
            assert "Director User" in result["unconfigured_reason"]
            assert result["summary"]["unconfigured"] == result["summary"]["total"]
            assert result["steps"][0]["status"] == "unconfigured"
        finally:
            if env_before is not None:
                os.environ["MISSING_VAR_XYZ"] = env_before

    async def test_llm_assert_pass(self, scenario_dir: Path, monkeypatch) -> None:
        """llm_assert step should PASS when the real LLM judge says PASS."""
        monkeypatch.setattr(
            os.environ, "get",
            lambda k, d=None: "sk-test" if k == "AUTOINFO_LLM_API_KEY" else d,
        )
        monkeypatch.setattr(
            "autoinfo.mcp.validation._is_llm_configured",
            lambda: True,
        )

        def fake_judge(assertion: str, output: Any) -> dict:
            if "bad" in assertion.lower():
                return {"verdict": "FAIL", "reason": "result is bad"}
            return {"verdict": "PASS", "reason": "result is ok"}

        monkeypatch.setattr(
            "autoinfo.mcp.validation._llm_judge",
            fake_judge,
        )

        result = await run_scenario(
            "llm-scenario",
            dispatch=self._fake_dispatch,
            steps=[1],
            scenarios_dir=scenario_dir,
        )
        assert result["status"] == "passed"
        assert result["steps"][0]["status"] == "passed"
        assert "llm_reason" in result["steps"][0]

    async def test_llm_assert_fail(self, scenario_dir: Path, monkeypatch) -> None:
        """llm_assert step should FAIL when the real LLM judge says FAIL."""
        monkeypatch.setattr(
            "autoinfo.mcp.validation._is_llm_configured",
            lambda: True,
        )

        def fake_judge(assertion: str, output: Any) -> dict:
            return {"verdict": "FAIL", "reason": "output is bad"}

        monkeypatch.setattr(
            "autoinfo.mcp.validation._llm_judge",
            fake_judge,
        )

        result = await run_scenario(
            "llm-scenario",
            dispatch=self._fake_dispatch,
            steps=[1],
            scenarios_dir=scenario_dir,
        )
        assert result["status"] == "failed"
        assert result["steps"][0]["status"] == "failed"
        assert "output is bad" in result["steps"][0]["detail"]

    async def test_llm_assert_unconfigured_without_key(
        self, scenario_dir: Path, monkeypatch
    ) -> None:
        """llm_assert step without LLM key should report 'unconfigured' — not
        silently skipped and not falsely passed."""
        monkeypatch.delenv("AUTOINFO_LLM_API_KEY", raising=False)
        monkeypatch.setattr(
            "autoinfo.mcp.validation._is_llm_configured",
            lambda: False,
        )

        result = await run_scenario(
            "llm-scenario",
            dispatch=self._fake_dispatch,
            steps=[1],
            scenarios_dir=scenario_dir,
        )
        assert result["status"] == "unconfigured"
        assert result["steps"][0]["status"] == "unconfigured"
        assert "LLM API key" in result["steps"][0]["detail"]

    async def test_llm_assert_judge_error_fails(
        self, scenario_dir: Path, monkeypatch
    ) -> None:
        """A judge exception should surface as FAIL — no silent swallowing."""
        monkeypatch.setattr(
            "autoinfo.mcp.validation._is_llm_configured",
            lambda: True,
        )

        async def broken_judge(assertion: str, output: Any) -> dict:
            raise RuntimeError("simulated LLM outage")

        monkeypatch.setattr(
            "autoinfo.mcp.validation._llm_judge",
            broken_judge,
        )

        result = await run_scenario(
            "llm-scenario",
            dispatch=self._fake_dispatch,
            steps=[1],
            scenarios_dir=scenario_dir,
        )
        assert result["status"] == "failed"
        assert "llm_assert error" in result["steps"][0]["detail"]

    async def test_unknown_scenario_raises(self, scenario_dir: Path) -> None:
        """Unknown scenario name should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown validation scenario: no-such.*Available:"):
            await run_scenario(
                "no-such",
                dispatch=self._fake_dispatch,
                scenarios_dir=scenario_dir,
            )

    async def test_steps_subset_runs_only_selected(self, scenario_dir: Path) -> None:
        """steps=[1] should only run step 1."""
        result = await run_scenario(
            "fake-scenario",
            dispatch=self._fake_dispatch,
            steps=[1],
            scenarios_dir=scenario_dir,
        )
        assert result["summary"]["total"] == 1
        assert result["steps"][0]["name"] == "all-pass step"

    async def test_steps_out_of_range_raises(self, scenario_dir: Path) -> None:
        """Out-of-range step index should raise ValueError."""
        with pytest.raises(ValueError, match="out of range"):
            await run_scenario(
                "fake-scenario",
                dispatch=self._fake_dispatch,
                steps=[99],
                scenarios_dir=scenario_dir,
            )

    async def test_empty_steps_raises(self, scenario_dir: Path) -> None:
        """Empty steps list should raise ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            await run_scenario(
                "fake-scenario",
                dispatch=self._fake_dispatch,
                steps=[],
                scenarios_dir=scenario_dir,
            )

    async def test_dispatch_exception_handled(self, tmp_path: Path) -> None:
        """A dispatch that raises should be caught and reported as failed step."""
        sd = tmp_path / "scenarios"
        sd.mkdir()
        (sd / "exc.yaml").write_text(
            "name: exc-test\ndescription: Test\nsteps:\n"
            "  - name: step\n    tool: will_raise\n    arguments: {}\n",
            encoding="utf-8",
        )

        async def raise_dispatch(name: str, arguments: dict) -> dict:
            raise RuntimeError("simulated crash")

        result = await run_scenario(
            "exc-test",
            dispatch=raise_dispatch,
            scenarios_dir=sd,
        )
        assert result["status"] == "failed"
        assert result["steps"][0]["status"] == "failed"
        assert "dispatch exception" in result["steps"][0].get("detail", "")


class TestRunScenarioCliHttp:
    """run_scenario tests for the cli/http step kinds (real execution)."""

    CLI_SCENARIO_YAML = """\
name: cli-scenario
description: "CLI execution scenario"
category: test
requires_env: []
steps:
  - name: "echo success"
    kind: cli
    command: "echo validation-works"
    expect:
      success: true
      exit_code: 0
      stdout_has: ["validation-works"]

  - name: "exit code check"
    kind: cli
    command: "exit 3"
    expect:
      success: false
"""

    HTTP_SCENARIO_YAML = """\
name: http-scenario
description: "HTTP execution scenario"
category: test
requires_env: []
steps:
  - name: "example.com reachable"
    kind: http
    method: GET
    url: "https://example.com"
    expect:
      success: true
      status_code: 200
"""

    HTTP_JSON_SCENARIO_YAML = """\
name: http-json-scenario
description: "HTTP JSON body assertion"
category: test
requires_env: []
steps:
  - name: "jsonplaceholder returns json"
    kind: http
    method: GET
    url: "https://jsonplaceholder.typicode.com/todos/1"
    expect:
      success: true
      status_code: 200
      json_has: ["userId", "id", "title"]
"""

    def _write(self, tmp_path: Path, name: str, content: str) -> Path:
        sd = tmp_path / "scenarios"
        sd.mkdir(exist_ok=True)
        p = sd / f"{name}.yaml"
        p.write_text(content, encoding="utf-8")
        return sd

    async def test_cli_success_and_exit_code(self, tmp_path: Path) -> None:
        sd = self._write(tmp_path, "cli-scenario", self.CLI_SCENARIO_YAML)
        result = await run_scenario("cli-scenario", dispatch=None, scenarios_dir=sd)
        assert result["status"] == "passed"
        assert result["summary"]["passed"] == 2

    async def test_cli_missing_command_raises(self, tmp_path: Path) -> None:
        yaml_text = "name: bad\ndescription: T\nsteps:\n  - name: s\n    kind: cli\n"
        sd = self._write(tmp_path, "bad", yaml_text)
        with pytest.raises(ValueError, match="kind=cli.*'command'"):
            load_scenarios(sd)

    async def test_http_success(self, tmp_path: Path) -> None:
        sd = self._write(tmp_path, "http-scenario", self.HTTP_SCENARIO_YAML)
        result = await run_scenario("http-scenario", dispatch=None, scenarios_dir=sd)
        assert result["status"] == "passed"
        assert result["summary"]["passed"] == 1

    async def test_http_json_assert(self, tmp_path: Path) -> None:
        sd = self._write(tmp_path, "http-json-scenario", self.HTTP_JSON_SCENARIO_YAML)
        result = await run_scenario("http-json-scenario", dispatch=None, scenarios_dir=sd)
        assert result["status"] == "passed"
        assert result["summary"]["passed"] == 1

    async def test_http_missing_url_raises(self, tmp_path: Path) -> None:
        sd = self._write(
            tmp_path, "badhttp",
            "name: badhttp\ndescription: T\nsteps:\n"
            "  - name: s\n    kind: http\n    method: GET\n",
        )
        with pytest.raises(ValueError, match="kind=http.*'url'"):
            load_scenarios(sd)


# ============================================================================
# Integration tests: MCP server dispatch
# ============================================================================


class TestValidationToolsDispatch:
    """Integration tests exercising the tools through the MCP app's
    request handler (matching the pattern used in test_mcp_server.py)."""

    @pytest.mark.asyncio
    async def test_list_validation_scenarios_via_dispatch(self, monkeypatch) -> None:
        """Should return ≥6 scenarios via the MCP dispatch handler."""
        handler = mcp_server.app.request_handlers[CallToolRequest]
        request = CallToolRequest(
            method="tools/call",
            params=CallToolRequestParams(
                name="list_validation_scenarios", arguments={}
            ),
        )
        result = await handler(request)
        call_result = result.root
        data = json.loads(call_result.content[0].text)

        assert data["success"] is True
        assert data["data"]["count"] >= 6
        assert len(data["data"]["scenarios"]) >= 6

        for sc in data["data"]["scenarios"]:
            assert "name" in sc
            assert "description" in sc
            assert "category" in sc
            assert "step_count" in sc

    @pytest.mark.asyncio
    async def test_run_system_health_via_dispatch(self, monkeypatch) -> None:
        """system-health scenario should pass via MCP dispatch."""
        handler = mcp_server.app.request_handlers[CallToolRequest]
        request = CallToolRequest(
            method="tools/call",
            params=CallToolRequestParams(
                name="run_validation_scenario",
                arguments={"scenario": "system-health"},
            ),
        )
        result = await handler(request)
        call_result = result.root
        data = json.loads(call_result.content[0].text)

        assert data["success"] is True
        assert data["data"]["status"] == "passed"
        assert data["data"]["summary"]["passed"] == 3
        assert data["data"]["summary"]["failed"] == 0

    @pytest.mark.asyncio
    async def test_run_llm_gated_reports_unconfigured_without_key(
        self, monkeypatch
    ) -> None:
        """llm-gated scenario should report 'unconfigured' when
        AUTOINFO_LLM_API_KEY is absent — never silently skipped."""
        # Ensure the key is not set for this test
        monkeypatch.delenv("AUTOINFO_LLM_API_KEY", raising=False)

        handler = mcp_server.app.request_handlers[CallToolRequest]
        request = CallToolRequest(
            method="tools/call",
            params=CallToolRequestParams(
                name="run_validation_scenario",
                arguments={"scenario": "llm-gated"},
            ),
        )
        result = await handler(request)
        call_result = result.root
        data = json.loads(call_result.content[0].text)

        assert data["success"] is True
        # Without a key this must surface as unconfigured (real environment
        # check), NOT as a pass or a silent skip.
        assert data["data"]["status"] == "unconfigured"
        # llm-gated has 3 steps (classify_cefr, suggest_keywords, cefr_batch)
        assert data["data"]["summary"]["unconfigured"] == 3

    @pytest.mark.asyncio
    async def test_unknown_scenario_via_dispatch(self) -> None:
        """Unknown scenario through dispatch should return a proper error
        envelope (not a raw traceback)."""
        handler = mcp_server.app.request_handlers[CallToolRequest]
        request = CallToolRequest(
            method="tools/call",
            params=CallToolRequestParams(
                name="run_validation_scenario",
                arguments={"scenario": "nonexistent-scenario-xyz"},
            ),
        )
        result = await handler(request)
        call_result = result.root
        data = json.loads(call_result.content[0].text)

        assert data["success"] is False
        assert data["error"]["code"] == "ValidationError"
        assert "nonexistent-scenario-xyz" in data["error"]["message"]
