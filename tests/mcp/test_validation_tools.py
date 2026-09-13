"""Tests for the Agent-native MCP validation toolset.

Covers the scenario loader and executor (:mod:`autoinfo.mcp.validation`)
as well as the server-integrated MCP tools ``list_validation_scenarios``
and ``run_validation_scenario``.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

import httpx
import pytest
from mcp.types import CallToolRequest, CallToolRequestParams

from autoinfo.mcp import server as mcp_server
from autoinfo.mcp import validation as validation_mod
from autoinfo.mcp.validation import (
    CATEGORY_PYRAMID_HISTORY_FILE,
    PYRAMID_LAYERS,
    SCENARIO_CATEGORIES,
    _normalize_envelope,
    aggregate_category_pyramid,
    category_pyramid_history_report,
    diff_scenario_runs,
    list_scenarios,
    list_validation_runs,
    load_category_pyramid_history,
    load_scenario_results,
    load_scenarios,
    record_category_pyramid_history,
    run_all_scenarios,
    run_scenario,
    save_scenario_results,
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
            "name: my-test\n"
            "description: Test\n"
            "category: happy_path\n"
            "pyramid_layer: component\n"
            "pipeline_stage: A7\n"
            "user_level: B2.5\n"
            "steps:\n"
            ""
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
            "description: Test\n"
            "category: happy_path\n"
            "pyramid_layer: component\n"
            "pipeline_stage: A7\n"
            "user_level: B2.5\n"
            ""
            "steps:\n  - name: s\n    tool: health_check\n",
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
            "name: test\n"
            "description: Test\n"
            "category: happy_path\n"
            "pyramid_layer: component\n"
            "pipeline_stage: A7\n"
            "user_level: B2.5\n"
            "steps: []\n"
            "",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="empty-steps\\.yaml.*non-empty"):
            load_scenarios(sd)

    def test_raises_on_step_missing_name(self, tmp_path: Path) -> None:
        """Step missing 'name' should raise ValueError."""
        sd = tmp_path / "scenarios"
        sd.mkdir()
        (sd / "bad-step.yaml").write_text(
            "name: test\n"
            "description: Test\n"
            "category: happy_path\n"
            "pyramid_layer: component\n"
            "pipeline_stage: A7\n"
            "user_level: B2.5\n"
            ""
            "steps:\n  - tool: health_check\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="bad-step\\.yaml.*step\\[0\\].*'name'"):
            load_scenarios(sd)

    def test_raises_on_step_missing_tool(self, tmp_path: Path) -> None:
        """Step missing 'tool' should raise ValueError."""
        sd = tmp_path / "scenarios"
        sd.mkdir()
        (sd / "bad-step.yaml").write_text(
            "name: test\n"
            "description: Test\n"
            "category: happy_path\n"
            "pyramid_layer: component\n"
            "pipeline_stage: A7\n"
            "user_level: B2.5\n"
            ""
            "steps:\n  - name: s\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="bad-step\\.yaml.*step\\[0\\].*'tool'"):
            load_scenarios(sd)


# ============================================================================
# Unit tests: keyword-management scenario seeds (issue #194)
# ============================================================================


class TestKeywordManagementScenario:
    """The packaged keyword-management scenario must seed its own keywords.

    Regression for #194: the scenario approves ``multicenter`` and rejects
    ``time-lapse embryo imaging``, but those keywords no longer exist in the
    runtime keyword store.  Because approve/reject return ``None`` (and the
    MCP layer surfaces ``KEYWORD_NOT_FOUND``) for unknown keywords, the
    scenario must create both keywords via ``kind: cli`` seed steps that run
    BEFORE the mutating MCP steps — while keeping the backup/restore
    self-cleaning contract (backup first, restore last).
    """

    @pytest.fixture()
    def scenario(self) -> dict[str, Any]:
        matches = [sc for sc in load_scenarios() if sc["name"] == "keyword-management"]
        assert len(matches) == 1, (
            f"expected exactly one keyword-management scenario, got {len(matches)}"
        )
        return matches[0]

    @staticmethod
    def _seed_step_index(steps: list[dict[str, Any]], keyword: str) -> int:
        """Index of the kind: cli step that seeds *keyword* via add_keyword."""
        for i, step in enumerate(steps):
            command = step.get("command", "")
            if step.get("kind") == "cli" and "add_keyword" in command and keyword in command:
                return i
        raise AssertionError(f"no seed step calls add_keyword for {keyword!r}")

    @staticmethod
    def _mutate_step_index(steps: list[dict[str, Any]], keyword: str, tool: str) -> int:
        """Index of the mcp step that approves/rejects *keyword* via *tool*."""
        for i, step in enumerate(steps):
            if step.get("tool") == tool and step.get("arguments", {}).get("keyword") == keyword:
                return i
        raise AssertionError(f"no {tool} step found for keyword {keyword!r}")

    def test_seed_steps_precede_approve_reject(self, scenario: dict[str, Any]) -> None:
        """Each keyword is seeded by a cli step before its mutate step."""
        steps = scenario["steps"]
        for keyword, tool in (
            ("multicenter", "approve_keyword"),
            ("time-lapse embryo imaging", "reject_keyword"),
        ):
            seed_i = self._seed_step_index(steps, keyword)
            mutate_i = self._mutate_step_index(steps, keyword, tool)
            assert seed_i < mutate_i, (
                f"seed step for {keyword!r} (index {seed_i}) must run before "
                f"{tool} step (index {mutate_i})"
            )

    def test_seed_steps_expect_success_marker(self, scenario: dict[str, Any]) -> None:
        """Seed steps must pass (exit_code 0) and print a SEEDED marker."""
        steps = scenario["steps"]
        for keyword in ("multicenter", "time-lapse embryo imaging"):
            step = steps[self._seed_step_index(steps, keyword)]
            expect = step.get("expect", {})
            assert expect.get("exit_code") == 0, (
                f"seed step for {keyword!r} must expect exit_code 0, got {expect}"
            )
            markers = expect.get("stdout_has", [])
            assert any("SEEDED" in m and keyword in m for m in markers), (
                f"seed step for {keyword!r} must expect a 'SEEDED:{keyword}' "
                f"stdout marker, got {markers}"
            )

    def test_self_cleaning_order(self, scenario: dict[str, Any]) -> None:
        """Backup runs first, seeds in between, restore runs last."""
        steps = scenario["steps"]
        backup_i = next(
            i
            for i, step in enumerate(steps)
            if step.get("kind") == "cli" and "copyfile" in step.get("command", "")
        )
        restore_i = next(
            i
            for i, step in enumerate(steps)
            if step.get("kind") == "cli" and "KEYWORDS_RESTORED" in step.get("command", "")
        )
        assert restore_i == len(steps) - 1, (
            f"restore step (index {restore_i}) must be last of {len(steps)} steps"
        )
        for keyword in ("multicenter", "time-lapse embryo imaging"):
            seed_i = self._seed_step_index(steps, keyword)
            assert backup_i < seed_i < restore_i, (
                f"seed step for {keyword!r} (index {seed_i}) must run after "
                f"backup (index {backup_i}) and before restore (index {restore_i})"
            )


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
category: happy_path
requires_env: []
pyramid_layer: component
pipeline_stage: A7
user_level: B2.5
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
category: happy_path
requires_env: []
pyramid_layer: component
pipeline_stage: A7
user_level: B2.5
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
category: happy_path
requires_env: ["MISSING_VAR_XYZ"]
pyramid_layer: component
pipeline_stage: A7
user_level: B2.5
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
        if name == "fake_error_actionable":
            return {
                "success": False,
                "error": {"code": "Timeout", "message": "timeout", "actionable": True},
            }
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

    async def test_collect_artifacts_skips_excluded_paths(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """collect_artifacts never collects non-deliverable artifacts (#192).

        Rejected KB promotion drafts under ``knowledge/_failed/<domain>/**``
        and internal ``outputs/coverage-matrix/**`` reports must be absent
        from the artifacts list, while a legit file next to them is kept.
        """
        # Trailing "**" matches only dirs on Python < 3.13 (CPython gh-70303),
        # so all patterns follow the "**/*.ext" convention the packaged
        # scenarios use — otherwise 3.12 collects zero files here.
        sd = self._write_scenario(
            tmp_path,
            "artifact-glob",
            "name: artifact-glob\ndescription: Test\n"
            "category: happy_path\npyramid_layer: component\npipeline_stage: A7\nuser_level: B2.5\n"
            'collect_artifacts: ["knowledge/**/*.md", "outputs/**/*.md"]\n'
            "steps:\n"
            "  - name: step\n    tool: fake_tool\n    arguments: {}\n"
            "    expect:\n      success: true\n",
        )
        cwd = tmp_path / "cwd"
        legit = cwd / "knowledge" / "medical-research" / "01-Raw" / "x" / "entry.md"
        legit.parent.mkdir(parents=True)
        legit.write_text("# Legit entry\n", encoding="utf-8")
        rejected = cwd / "knowledge" / "_failed" / "medical-research" / "rejected.md"
        rejected.parent.mkdir(parents=True)
        rejected.write_text("# Rejected draft\n", encoding="utf-8")
        matrix = cwd / "outputs" / "coverage-matrix" / "matrix-report.md"
        matrix.parent.mkdir(parents=True)
        matrix.write_text("# Coverage Matrix\n", encoding="utf-8")

        monkeypatch.chdir(cwd)
        result = await run_scenario("artifact-glob", dispatch=self._fake_dispatch, scenarios_dir=sd)
        artifact_paths = {a["path"] for a in result["artifacts"]}
        assert str(legit) in artifact_paths, f"legit artifact missing: {artifact_paths}"
        assert not any("_failed" in p for p in artifact_paths), (
            f"_failed draft leaked into artifacts: {artifact_paths}"
        )
        assert not any("coverage-matrix" in p for p in artifact_paths), (
            f"coverage-matrix report leaked into artifacts: {artifact_paths}"
        )

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
            "name: bad-code\n"
            "description: Test\n"
            "category: happy_path\n"
            "pyramid_layer: component\n"
            "pipeline_stage: A7\n"
            "user_level: B2.5\n"
            "steps:\n"
            ""
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

    async def test_error_actionable_check_passes_when_actionable(self, tmp_path: Path) -> None:
        """error_actionable: true passes when the envelope carries actionable."""
        sd = tmp_path / "scenarios"
        sd.mkdir()
        (sd / "act-ok.yaml").write_text(
            "name: act-ok\n"
            "description: Test\n"
            "category: happy_path\n"
            "pyramid_layer: component\n"
            "pipeline_stage: A7\n"
            "user_level: B2.5\n"
            "steps:\n"
            ""
            "  - name: step\n    tool: fake_error_actionable\n    arguments: {}\n"
            "    expect:\n      success: false\n      error_code: Timeout\n"
            "      error_actionable: true\n",
            encoding="utf-8",
        )
        result = await run_scenario(
            "act-ok",
            dispatch=self._fake_dispatch,
            scenarios_dir=sd,
        )
        assert result["status"] == "passed"
        assert result["steps"][0]["status"] == "passed"

    async def test_error_actionable_check_fails_when_missing(self, tmp_path: Path) -> None:
        """error_actionable: true fails when the envelope omits actionable."""
        sd = tmp_path / "scenarios"
        sd.mkdir()
        (sd / "act-bad.yaml").write_text(
            "name: act-bad\n"
            "description: Test\n"
            "category: happy_path\n"
            "pyramid_layer: component\n"
            "pipeline_stage: A7\n"
            "user_level: B2.5\n"
            "steps:\n"
            ""
            "  - name: step\n    tool: fake_error\n    arguments: {}\n"
            "    expect:\n      success: false\n      error_code: Timeout\n"
            "      error_actionable: true\n",
            encoding="utf-8",
        )
        result = await run_scenario(
            "act-bad",
            dispatch=self._fake_dispatch,
            scenarios_dir=sd,
        )
        assert result["status"] == "failed"
        assert result["steps"][0]["status"] == "failed"
        assert "actionable" in result["steps"][0].get("detail", "")

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
            os.environ,
            "get",
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

    async def test_llm_assert_judge_error_fails(self, scenario_dir: Path, monkeypatch) -> None:
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
            "name: exc-test\n"
            "description: Test\n"
            "category: happy_path\n"
            "pyramid_layer: component\n"
            "pipeline_stage: A7\n"
            "user_level: B2.5\n"
            "steps:\n"
            ""
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

    # --- #157: env-prereq failures report "unconfigured", not "failed" ----

    HTTP_REQUIRED_YAML = """\
name: http-required
description: "Scenario requiring a reachable HTTP endpoint"
category: happy_path
requires_http: ["http://127.0.0.1:9/health"]
pyramid_layer: component
pipeline_stage: A7
user_level: B2.5
steps:
  - name: "all-pass step"
    tool: fake_tool
    arguments: {}
    expect:
      success: true
      data_has: ["result"]
"""

    def _write_scenario(self, tmp_path: Path, name: str, content: str) -> Path:
        sd = tmp_path / "scenarios"
        sd.mkdir()
        (sd / f"{name}.yaml").write_text(content, encoding="utf-8")
        return sd

    async def test_requires_http_unreachable_reports_unconfigured(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """A scenario whose requires_http endpoint is unreachable reports
        'unconfigured' with the URL in the reason — not 'failed' (#157)."""
        sd = self._write_scenario(tmp_path, "http-required", self.HTTP_REQUIRED_YAML)
        monkeypatch.setattr("autoinfo.mcp.validation._http_reachable", lambda url: False)
        result = await run_scenario("http-required", dispatch=self._fake_dispatch, scenarios_dir=sd)
        assert result["status"] == "unconfigured"
        assert "http://127.0.0.1:9/health" in result["unconfigured_reason"]
        assert result["summary"]["unconfigured"] == result["summary"]["total"]
        assert result["summary"]["failed"] == 0
        assert all(step["status"] == "unconfigured" for step in result["steps"])

    async def test_requires_http_reachable_runs_steps(self, tmp_path: Path, monkeypatch) -> None:
        """When the requires_http endpoint is reachable the steps run and are
        NOT marked unconfigured (#157)."""
        sd = self._write_scenario(tmp_path, "http-required", self.HTTP_REQUIRED_YAML)
        monkeypatch.setattr("autoinfo.mcp.validation._http_reachable", lambda url: True)
        result = await run_scenario("http-required", dispatch=self._fake_dispatch, scenarios_dir=sd)
        assert result["status"] == "passed"
        assert result["steps"][0]["status"] == "passed"
        assert result["summary"]["unconfigured"] == 0

    async def test_reddit_oauth_missing_classified_unconfigured(self, tmp_path: Path) -> None:
        """A dispatch raising Reddit-OAuth-missing ValueError is classified
        as unconfigured, not failed (#157)."""
        sd = self._write_scenario(
            tmp_path,
            "reddit-oauth",
            "name: reddit-oauth\n"
            "description: Test\n"
            "category: happy_path\n"
            "pyramid_layer: component\n"
            "pipeline_stage: A7\n"
            "user_level: B2.5\n"
            "steps:\n"
            ""
            "  - name: step\n    tool: reddit_tool\n    arguments: {}\n",
        )

        async def raise_dispatch(name: str, arguments: dict) -> dict:
            raise ValueError("Reddit OAuth2 requires client_id and client_secret in config.")

        result = await run_scenario("reddit-oauth", dispatch=raise_dispatch, scenarios_dir=sd)
        step = result["steps"][0]
        assert step["status"] == "unconfigured"
        assert "Reddit" in step["detail"]
        assert result["status"] == "unconfigured"

    async def test_tts_network_error_classified_unconfigured(self, tmp_path: Path) -> None:
        """A dispatch raising the TTS network RuntimeError is classified as
        unconfigured, not failed (#157)."""
        sd = self._write_scenario(
            tmp_path,
            "tts-net",
            "name: tts-net\n"
            "description: Test\n"
            "category: happy_path\n"
            "pyramid_layer: component\n"
            "pipeline_stage: A7\n"
            "user_level: B2.5\n"
            "steps:\n"
            ""
            "  - name: step\n    tool: tts_tool\n    arguments: {}\n",
        )

        async def raise_dispatch(name: str, arguments: dict) -> dict:
            raise RuntimeError("OpenAI TTS network error: Network is unreachable")

        result = await run_scenario("tts-net", dispatch=raise_dispatch, scenarios_dir=sd)
        step = result["steps"][0]
        assert step["status"] == "unconfigured"
        assert "TTS" in step["detail"]

    async def test_connect_error_classified_unconfigured(self, tmp_path: Path) -> None:
        """An httpx connection error raised from dispatch is classified as
        unconfigured, not failed (#157)."""
        sd = self._write_scenario(
            tmp_path,
            "connect-err",
            "name: connect-err\n"
            "description: Test\n"
            "category: happy_path\n"
            "pyramid_layer: component\n"
            "pipeline_stage: A7\n"
            "user_level: B2.5\n"
            "steps:\n"
            ""
            "  - name: step\n    tool: http_tool\n    arguments: {}\n",
        )

        async def raise_dispatch(name: str, arguments: dict) -> dict:
            raise httpx.ConnectError("connection refused")

        result = await run_scenario("connect-err", dispatch=raise_dispatch, scenarios_dir=sd)
        step = result["steps"][0]
        assert step["status"] == "unconfigured"
        assert "connect" in step["detail"].lower()

    async def test_other_exception_still_failed(self, tmp_path: Path) -> None:
        """BACKWARD-COMPAT GUARD: exceptions that are NOT an environment
        prereq gap keep the historic 'failed' classification (#157)."""
        sd = self._write_scenario(
            tmp_path,
            "generic-boom",
            "name: generic-boom\n"
            "description: Test\n"
            "category: happy_path\n"
            "pyramid_layer: component\n"
            "pipeline_stage: A7\n"
            "user_level: B2.5\n"
            "steps:\n"
            ""
            "  - name: step\n    tool: boom_tool\n    arguments: {}\n",
        )

        async def raise_dispatch(name: str, arguments: dict) -> dict:
            raise RuntimeError("boom")

        result = await run_scenario("generic-boom", dispatch=raise_dispatch, scenarios_dir=sd)
        step = result["steps"][0]
        assert step["status"] == "failed"  # NOT unconfigured
        assert "dispatch exception" in step["detail"]
        assert result["status"] == "failed"


class TestRunScenarioCliHttp:
    """run_scenario tests for the cli/http step kinds (real execution)."""

    CLI_SCENARIO_YAML = """\
name: cli-scenario
description: "CLI execution scenario"
category: happy_path
requires_env: []
pyramid_layer: component
pipeline_stage: A7
user_level: B2.5
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
category: happy_path
requires_env: []
pyramid_layer: component
pipeline_stage: A7
user_level: B2.5
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
category: happy_path
requires_env: []
pyramid_layer: component
pipeline_stage: A7
user_level: B2.5
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
        yaml_text = (
            "name: bad\n"
            "description: T\n"
            "category: happy_path\n"
            "pyramid_layer: component\n"
            "pipeline_stage: A7\n"
            "user_level: B2.5\n"
            ""
            "steps:\n  - name: s\n    kind: cli\n"
        )
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
            tmp_path,
            "badhttp",
            "name: badhttp\n"
            "description: T\n"
            "category: happy_path\n"
            "pyramid_layer: component\n"
            "pipeline_stage: A7\n"
            "user_level: B2.5\n"
            "steps:\n"
            ""
            "  - name: s\n    kind: http\n    method: GET\n",
        )
        with pytest.raises(ValueError, match="kind=http.*'url'"):
            load_scenarios(sd)


class TestRunScenarioCleanupSteps:
    """run_scenario tests for the cleanup_steps contract: always-run,
    best-effort, verdict-neutral cleanup of scenario-created state."""

    CLEANUP_SCENARIO_YAML = """\
name: cleanup-scenario
description: "Cleanup-steps scenario"
category: happy_path
requires_env: []
pyramid_layer: component
pipeline_stage: A7
user_level: B2.5
steps:
  - name: "main pass step"
    tool: fake_tool
    arguments: {}
    expect:
      success: true
      data_has: ["result"]
cleanup_steps:
  - name: "cleanup step"
    tool: fake_tool
    arguments: {}
    expect:
      success: true
      data_has: ["result"]
"""

    FAILING_CLEANUP_SCENARIO_YAML = """\
name: cleanup-fail-scenario
description: "Cleanup-steps scenario with failing main step"
category: happy_path
requires_env: []
pyramid_layer: component
pipeline_stage: A7
user_level: B2.5
steps:
  - name: "main fail step"
    tool: fake_error
    arguments: {}
    expect:
      success: true
      data_has: ["result"]
cleanup_steps:
  - name: "cleanup step"
    tool: fake_tool
    arguments: {}
    expect:
      success: true
      data_has: ["result"]
"""

    FAILING_CLEANUP_STEP_YAML = """\
name: cleanup-bad-step-scenario
description: "Cleanup-steps scenario with failing cleanup step"
category: happy_path
requires_env: []
pyramid_layer: component
pipeline_stage: A7
user_level: B2.5
steps:
  - name: "main pass step"
    tool: fake_tool
    arguments: {}
    expect:
      success: true
      data_has: ["result"]
cleanup_steps:
  - name: "cleanup fail step"
    tool: fake_error
    arguments: {}
    expect:
      success: true
      data_has: ["result"]
"""

    ENV_GATED_CLEANUP_YAML = """\
name: env-gated-cleanup
description: "Env-gated scenario with cleanup"
category: happy_path
requires_env: ["MISSING_VAR_XYZ"]
pyramid_layer: component
pipeline_stage: A7
user_level: B2.5
steps:
  - name: "should report unconfigured"
    tool: health_check
    arguments: {}
cleanup_steps:
  - name: "cleanup must not run"
    tool: fake_tool
    arguments: {}
"""

    @pytest.fixture
    def cleanup_scenario_dir(self, tmp_path: Path) -> Path:
        sd = tmp_path / "scenarios"
        sd.mkdir()
        (sd / "cleanup-scenario.yaml").write_text(self.CLEANUP_SCENARIO_YAML, encoding="utf-8")
        (sd / "cleanup-fail-scenario.yaml").write_text(
            self.FAILING_CLEANUP_SCENARIO_YAML, encoding="utf-8"
        )
        (sd / "cleanup-bad-step-scenario.yaml").write_text(
            self.FAILING_CLEANUP_STEP_YAML, encoding="utf-8"
        )
        (sd / "env-gated-cleanup.yaml").write_text(self.ENV_GATED_CLEANUP_YAML, encoding="utf-8")
        return sd

    @pytest.fixture
    def cleanup_calls(self) -> list[str]:
        return []

    async def _fake_dispatch(self, name: str, arguments: dict) -> dict:
        if name == "fake_tool":
            return {"success": True, "data": {"result": "ok"}}
        if name == "fake_error":
            return {"success": False, "error": {"code": "Timeout", "message": "timeout"}}
        return {"success": True, "data": {}}

    async def _tracking_dispatch(
        self, name: str, arguments: dict, cleanup_calls: list[str]
    ) -> dict:
        cleanup_calls.append(name)
        return await self._fake_dispatch(name, arguments)

    async def test_cleanup_runs_and_is_reported(self, cleanup_scenario_dir: Path) -> None:
        """Cleanup steps run after a passing scenario and are reported."""
        result = await run_scenario(
            "cleanup-scenario",
            dispatch=self._fake_dispatch,
            scenarios_dir=cleanup_scenario_dir,
        )
        assert result["status"] == "passed"
        assert result["summary"]["passed"] == 1
        assert "cleanup" in result
        assert result["cleanup"]["summary"]["passed"] == 1
        assert result["cleanup"]["summary"]["total"] == 1
        assert result["cleanup"]["steps"][0]["status"] == "passed"

    async def test_cleanup_runs_after_main_failure(self, cleanup_scenario_dir: Path) -> None:
        """Cleanup runs even when a main step failed (state may exist)."""
        result = await run_scenario(
            "cleanup-fail-scenario",
            dispatch=self._fake_dispatch,
            scenarios_dir=cleanup_scenario_dir,
        )
        assert result["status"] == "failed"
        assert result["summary"]["failed"] == 1
        assert "cleanup" in result
        assert result["cleanup"]["summary"]["passed"] == 1

    async def test_cleanup_failure_does_not_flip_status(self, cleanup_scenario_dir: Path) -> None:
        """A failing cleanup step is reported but never flips scenario status."""
        result = await run_scenario(
            "cleanup-bad-step-scenario",
            dispatch=self._fake_dispatch,
            scenarios_dir=cleanup_scenario_dir,
        )
        assert result["status"] == "passed"
        assert result["summary"]["failed"] == 0
        assert "cleanup" in result
        assert result["cleanup"]["summary"]["failed"] == 1
        assert result["cleanup"]["steps"][0]["status"] == "failed"

    async def test_cleanup_runs_on_subset_run(
        self, cleanup_scenario_dir: Path, cleanup_calls: list[str]
    ) -> None:
        """steps=[1] still triggers cleanup (partial runs create state too)."""

        async def dispatch(name: str, arguments: dict) -> dict:
            return await self._tracking_dispatch(name, arguments, cleanup_calls)

        result = await run_scenario(
            "cleanup-scenario",
            dispatch=dispatch,
            steps=[1],
            scenarios_dir=cleanup_scenario_dir,
        )
        assert result["status"] == "passed"
        assert result["summary"]["total"] == 1
        assert "cleanup" in result
        assert result["cleanup"]["summary"]["total"] == 1
        assert cleanup_calls.count("fake_tool") == 2  # main + cleanup

    async def test_cleanup_skipped_when_unconfigured(self, cleanup_scenario_dir: Path) -> None:
        """Env-gated early return runs nothing, so cleanup must not run."""
        env_before = os.environ.pop("MISSING_VAR_XYZ", None)
        try:
            result = await run_scenario(
                "env-gated-cleanup",
                dispatch=self._fake_dispatch,
                scenarios_dir=cleanup_scenario_dir,
            )
            assert result["status"] == "unconfigured"
            assert "cleanup" not in result
        finally:
            if env_before is not None:
                os.environ["MISSING_VAR_XYZ"] = env_before

    async def test_cleanup_step_missing_tool_raises(self, tmp_path: Path) -> None:
        """cleanup_steps are schema-validated like steps."""
        sd = tmp_path / "scenarios"
        sd.mkdir()
        (sd / "bad-cleanup.yaml").write_text(
            "name: bad-cleanup\n"
            "description: T\n"
            "category: happy_path\n"
            "pyramid_layer: component\n"
            "pipeline_stage: A7\n"
            "user_level: B2.5\n"
            "steps:\n"
            ""
            "  - name: s\n    tool: fake_tool\n"
            "cleanup_steps:\n  - name: no-tool-step\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="cleanup_step\\[0\\].*'tool'"):
            load_scenarios(sd)

    async def test_cleanup_cli_step_validates_command(self, tmp_path: Path) -> None:
        """kind=cli cleanup steps require a command."""
        sd = tmp_path / "scenarios"
        sd.mkdir()
        (sd / "bad-cli-cleanup.yaml").write_text(
            "name: bad-cli-cleanup\n"
            "description: T\n"
            "category: happy_path\n"
            "pyramid_layer: component\n"
            "pipeline_stage: A7\n"
            "user_level: B2.5\n"
            "steps:\n"
            ""
            "  - name: s\n    tool: fake_tool\n"
            "cleanup_steps:\n  - name: no-command\n    kind: cli\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="cleanup_step\\[0\\].*kind=cli.*'command'"):
            load_scenarios(sd)


class TestRunScenarioRecovery:
    """Issue #138: per-step recovery_steps + scenario-level partial policy.

    A failed primary step (assertion mismatch, dispatch exception, or
    timeout) runs its recovery_steps; a recovery success is counted as
    ``recovered`` (never a plain failure), and ``min_passing``/``pass_ratio``
    turn partial success into a scenario pass.
    """

    RECOVERY_SCENARIO_YAML = """\
name: recovery-scenario
description: "Recovery-steps scenario"
category: happy_path
requires_env: []
pyramid_layer: component
pipeline_stage: A7
user_level: B2.5
steps:
  - name: "primary fails, recovery succeeds"
    tool: flaky_tool
    arguments: {}
    expect:
      success: true
      data_has: ["result"]
    recovery_steps:
      - name: "recovery pass step"
        tool: fake_tool
        arguments: {}
        expect:
          success: true
          data_has: ["result"]

  - name: "primary fails, recovery also fails"
    tool: flaky_tool
    arguments: {}
    expect:
      success: true
      data_has: ["result"]
    recovery_steps:
      - name: "recovery fail step"
        tool: fake_error
        arguments: {}
        expect:
          success: true
          data_has: ["result"]

  - name: "passing step never triggers recovery"
    tool: fake_tool
    arguments: {}
    expect:
      success: true
      data_has: ["result"]
    recovery_steps:
      - name: "recovery must not run"
        tool: fake_tool
        arguments: {}
        expect:
          success: true
"""

    PARTIAL_SCENARIO_YAML = """\
name: partial-recovery-scenario
description: "Partial-pass policy scenario"
category: happy_path
requires_env: []
min_passing: 2
pyramid_layer: component
pipeline_stage: A7
user_level: B2.5
steps:
  - name: "primary fails, recovery succeeds"
    tool: flaky_tool
    arguments: {}
    expect:
      success: true
    recovery_steps:
      - name: "recovery pass"
        tool: fake_tool
        arguments: {}
        expect:
          success: true

  - name: "plain pass"
    tool: fake_tool
    arguments: {}
    expect:
      success: true
      data_has: ["result"]

  - name: "unrecovered failure"
    tool: flaky_tool
    arguments: {}
    expect:
      success: true
"""

    STRICT_PARTIAL_SCENARIO_YAML = """\
name: strict-partial-recovery-scenario
description: "Strict partial-pass policy scenario"
category: happy_path
requires_env: []
min_passing: 3
pyramid_layer: component
pipeline_stage: A7
user_level: B2.5
steps:
  - name: "primary fails, recovery succeeds"
    tool: flaky_tool
    arguments: {}
    expect:
      success: true
    recovery_steps:
      - name: "recovery pass"
        tool: fake_tool
        arguments: {}
        expect:
          success: true

  - name: "plain pass"
    tool: fake_tool
    arguments: {}
    expect:
      success: true
      data_has: ["result"]

  - name: "unrecovered failure"
    tool: flaky_tool
    arguments: {}
    expect:
      success: true
"""

    RATIO_SCENARIO_YAML = """\
name: ratio-recovery-scenario
description: "Pass-ratio policy scenario"
category: happy_path
requires_env: []
pass_ratio: 0.5
pyramid_layer: component
pipeline_stage: A7
user_level: B2.5
steps:
  - name: "primary fails, recovery succeeds"
    tool: flaky_tool
    arguments: {}
    expect:
      success: true
    recovery_steps:
      - name: "recovery pass"
        tool: fake_tool
        arguments: {}
        expect:
          success: true

  - name: "unrecovered failure"
    tool: flaky_tool
    arguments: {}
    expect:
      success: true
"""

    RATIO_STRICT_SCENARIO_YAML = """\
name: ratio-strict-recovery-scenario
description: "Strict pass-ratio policy scenario"
category: happy_path
requires_env: []
pass_ratio: 0.9
pyramid_layer: component
pipeline_stage: A7
user_level: B2.5
steps:
  - name: "primary fails, recovery succeeds"
    tool: flaky_tool
    arguments: {}
    expect:
      success: true
    recovery_steps:
      - name: "recovery pass"
        tool: fake_tool
        arguments: {}
        expect:
          success: true

  - name: "unrecovered failure"
    tool: flaky_tool
    arguments: {}
    expect:
      success: true
"""

    TIMEOUT_RECOVERY_SCENARIO_YAML = """\
name: timeout-recovery-scenario
description: "Timeout-triggered recovery scenario"
category: happy_path
requires_env: []
pyramid_layer: component
pipeline_stage: A7
user_level: B2.5
steps:
  - name: "hanging primary triggers recovery"
    tool: slow_tool
    arguments: {}
    expect:
      success: true
    recovery_steps:
      - name: "recovery after timeout"
        tool: fake_tool
        arguments: {}
        expect:
          success: true
          data_has: ["result"]
"""

    UNCONFIGURED_PARTIAL_SCENARIO_YAML = """\
name: unconfigured-partial-scenario
description: "Partial-pass with an unconfigured step (R-S-06)"
category: happy_path
requires_env: []
min_passing: 1
pyramid_layer: component
pipeline_stage: A7
user_level: B2.5
steps:
  - name: "plain pass"
    tool: fake_tool
    arguments: {}
    expect:
      success: true

  - name: "environment-gated step"
    tool: unconfigured_tool
    arguments: {}
    expect:
      success: true
"""

    UNCONFIGURED_STRICT_SCENARIO_YAML = """\
name: unconfigured-strict-scenario
description: "Partial-pass threshold not met with an unconfigured step (R-S-06)"
category: happy_path
requires_env: []
min_passing: 2
pyramid_layer: component
pipeline_stage: A7
user_level: B2.5
steps:
  - name: "plain pass"
    tool: fake_tool
    arguments: {}
    expect:
      success: true

  - name: "environment-gated step"
    tool: unconfigured_tool
    arguments: {}
    expect:
      success: true
"""

    UNCONFIGURED_RATIO_SCENARIO_YAML = """\
name: unconfigured-ratio-scenario
description: "Pass-ratio met alongside an unconfigured step (R-S-06)"
category: happy_path
requires_env: []
pass_ratio: 0.5
pyramid_layer: component
pipeline_stage: A7
user_level: B2.5
steps:
  - name: "plain pass"
    tool: fake_tool
    arguments: {}
    expect:
      success: true

  - name: "environment-gated step"
    tool: unconfigured_tool
    arguments: {}
    expect:
      success: true
"""

    @pytest.fixture
    def recovery_dir(self, tmp_path: Path) -> Path:
        sd = tmp_path / "scenarios"
        sd.mkdir()
        files = {
            "recovery-scenario.yaml": self.RECOVERY_SCENARIO_YAML,
            "partial-recovery-scenario.yaml": self.PARTIAL_SCENARIO_YAML,
            "strict-partial-recovery-scenario.yaml": self.STRICT_PARTIAL_SCENARIO_YAML,
            "ratio-recovery-scenario.yaml": self.RATIO_SCENARIO_YAML,
            "ratio-strict-recovery-scenario.yaml": self.RATIO_STRICT_SCENARIO_YAML,
            "timeout-recovery-scenario.yaml": self.TIMEOUT_RECOVERY_SCENARIO_YAML,
            "unconfigured-partial-scenario.yaml": self.UNCONFIGURED_PARTIAL_SCENARIO_YAML,
            "unconfigured-strict-scenario.yaml": self.UNCONFIGURED_STRICT_SCENARIO_YAML,
            "unconfigured-ratio-scenario.yaml": self.UNCONFIGURED_RATIO_SCENARIO_YAML,
        }
        for name, content in files.items():
            (sd / name).write_text(content, encoding="utf-8")
        return sd

    async def _fake_dispatch(self, name: str, arguments: dict) -> dict:
        if name == "fake_tool":
            return {"success": True, "data": {"result": "ok"}}
        if name == "fake_error":
            return {"success": False, "error": {"code": "Timeout", "message": "timeout"}}
        if name == "flaky_tool":
            return {"success": False, "error": {"code": "SourceUnreachable", "message": "boom"}}
        if name == "unconfigured_tool":
            raise httpx.ConnectError("simulated unreachable service")
        if name == "slow_tool":
            await asyncio.sleep(5)
            return {"success": True, "data": {}}
        return {"success": True, "data": {}}

    async def test_recovery_step_runs_and_expect_is_evaluated(self, recovery_dir: Path) -> None:
        """A failed primary runs its recovery step; the recovery step's own
        expect assertions are evaluated (data_has on fake_tool passes)."""
        result = await run_scenario(
            "recovery-scenario",
            dispatch=self._fake_dispatch,
            steps=[1],
            scenarios_dir=recovery_dir,
        )
        step = result["steps"][0]
        assert step["status"] == "failed"  # primary's own assertion failed
        assert step["recovered"] is True
        assert step["recovery_status"] == "passed"
        assert len(step["recovery"]) == 1
        assert step["recovery"][0]["status"] == "passed"
        assert step["recovery"][0]["name"] == "recovery pass step"
        # Recovery is counted separately from failed.
        assert result["summary"]["recovered"] == 1
        assert result["summary"]["failed"] == 0
        # No unrecovered failure → default all-or-nothing still passes.
        assert result["status"] == "passed"

    async def test_recovery_failure_fails_scenario(self, recovery_dir: Path) -> None:
        """When the recovery step's own expect fails, the primary stays a
        plain failure and the scenario fails."""
        result = await run_scenario(
            "recovery-scenario",
            dispatch=self._fake_dispatch,
            steps=[2],
            scenarios_dir=recovery_dir,
        )
        step = result["steps"][0]
        assert step["status"] == "failed"
        assert step["recovered"] is False
        assert step["recovery_status"] == "failed"
        assert step["recovery"][0]["status"] == "failed"
        # The recovery step's own expect was evaluated and failed on success.
        assert "expected success=True, got success=False" in step["recovery"][0].get("detail", "")
        assert result["summary"]["failed"] == 1
        assert result["summary"]["recovered"] == 0
        assert result["status"] == "failed"

    async def test_recovery_skipped_when_primary_passes(self, recovery_dir: Path) -> None:
        """A passing primary never runs its recovery steps."""
        result = await run_scenario(
            "recovery-scenario",
            dispatch=self._fake_dispatch,
            steps=[3],
            scenarios_dir=recovery_dir,
        )
        step = result["steps"][0]
        assert step["status"] == "passed"
        assert "recovered" not in step
        assert "recovery" not in step
        assert result["summary"]["recovered"] == 0
        assert result["status"] == "passed"

    async def test_mixed_scenario_counts_recovered_not_failed(self, recovery_dir: Path) -> None:
        """Recovered + failed mix: summary separates them; one unrecovered
        failure still fails the default all-or-nothing policy."""
        result = await run_scenario(
            "recovery-scenario",
            dispatch=self._fake_dispatch,
            steps=[1, 2],
            scenarios_dir=recovery_dir,
        )
        assert result["summary"]["recovered"] == 1
        assert result["summary"]["failed"] == 1
        assert result["status"] == "failed"

    async def test_partial_policy_min_passing_satisfied(self, recovery_dir: Path) -> None:
        """min_passing satisfied → scenario passes even with an unrecovered
        failure (3/7-sources-OK style partial success is not an overall fail)."""
        result = await run_scenario(
            "partial-recovery-scenario",
            dispatch=self._fake_dispatch,
            scenarios_dir=recovery_dir,
        )
        assert result["summary"] == {
            "passed": 1,
            "failed": 1,
            "unconfigured": 0,
            "recovered": 1,
            "total": 3,
        }
        assert result["status"] == "passed"

    async def test_partial_policy_min_passing_not_met(self, recovery_dir: Path) -> None:
        """min_passing not met → scenario fails."""
        result = await run_scenario(
            "strict-partial-recovery-scenario",
            dispatch=self._fake_dispatch,
            scenarios_dir=recovery_dir,
        )
        assert result["summary"]["recovered"] == 1
        assert result["summary"]["passed"] == 1
        assert result["summary"]["failed"] == 1
        assert result["status"] == "failed"

    async def test_partial_policy_pass_ratio(self, recovery_dir: Path) -> None:
        """pass_ratio 0.5 with 1 recovered of 2 → pass; 0.9 → fail."""
        result = await run_scenario(
            "ratio-recovery-scenario",
            dispatch=self._fake_dispatch,
            scenarios_dir=recovery_dir,
        )
        assert result["summary"]["recovered"] == 1
        assert result["status"] == "passed"

        strict = await run_scenario(
            "ratio-strict-recovery-scenario",
            dispatch=self._fake_dispatch,
            scenarios_dir=recovery_dir,
        )
        assert strict["status"] == "failed"

    async def test_recovery_triggered_by_timeout(self, recovery_dir: Path) -> None:
        """A per-step timeout (simulated outage) triggers recovery too."""
        result = await run_scenario(
            "timeout-recovery-scenario",
            dispatch=self._fake_dispatch,
            scenarios_dir=recovery_dir,
            timeout=0.1,
        )
        step = result["steps"][0]
        assert step["status"] == "failed"
        assert "timed out" in step["detail"]
        assert step["recovered"] is True
        assert step["recovery"][0]["status"] == "passed"
        assert result["summary"]["recovered"] == 1
        assert result["status"] == "passed"

    async def test_recovery_does_not_reevaluate_primary_assertion(self, recovery_dir: Path) -> None:
        """R-S-03: recovery is recovered-only — the primary keeps its original
        failure detail; its assertion is never re-evaluated into a pass."""
        result = await run_scenario(
            "recovery-scenario",
            dispatch=self._fake_dispatch,
            steps=[1],
            scenarios_dir=recovery_dir,
        )
        step = result["steps"][0]
        assert step["status"] == "failed"
        assert step["recovered"] is True
        # The primary's detail is its own assertion failure, not the recovery's
        # successful payload — proof the primary was not re-evaluated.
        assert "expected success=True, got success=False" in step["detail"]
        assert "result" not in step["detail"]
        assert step["recovery"][0]["detail"]["data"] == {"result": "ok"}

    def test_contract_recovery_semantics_recovered_only(self) -> None:
        """R-S-03: the contract must describe recovered-only recovery (no
        re-evaluation of the primary), matching the engine."""
        contract = (
            Path(__file__).resolve().parents[2] / "docs" / "dev" / "validation-scenario-contract.md"
        ).read_text(encoding="utf-8")
        assert "then re-evaluate" not in contract
        assert "not re-evaluated" in contract

    async def test_unconfigured_does_not_block_met_threshold(self, recovery_dir: Path) -> None:
        """R-S-06: a met min_passing threshold passes even when another step is
        unconfigured; the unconfigured step is never counted as a pass."""
        result = await run_scenario(
            "unconfigured-partial-scenario",
            dispatch=self._fake_dispatch,
            scenarios_dir=recovery_dir,
        )
        assert result["summary"] == {
            "passed": 1,
            "failed": 0,
            "unconfigured": 1,
            "recovered": 0,
            "total": 2,
        }
        assert result["status"] == "passed"
        assert result["steps"][1]["status"] == "unconfigured"

    async def test_unconfigured_outranks_when_threshold_not_met(self, recovery_dir: Path) -> None:
        """R-S-06: when the threshold is not met, an unconfigured step makes the
        scenario unconfigured (not failed)."""
        result = await run_scenario(
            "unconfigured-strict-scenario",
            dispatch=self._fake_dispatch,
            scenarios_dir=recovery_dir,
        )
        assert result["summary"]["unconfigured"] == 1
        assert result["summary"]["passed"] == 1
        assert result["status"] == "unconfigured"

    async def test_unconfigured_does_not_block_met_pass_ratio(self, recovery_dir: Path) -> None:
        """R-S-06: a met pass_ratio also wins over an unconfigured step."""
        result = await run_scenario(
            "unconfigured-ratio-scenario",
            dispatch=self._fake_dispatch,
            scenarios_dir=recovery_dir,
        )
        assert result["status"] == "passed"
        assert result["summary"]["unconfigured"] == 1

    def test_leak_scan_raises_on_broken_store(self, monkeypatch) -> None:
        """R-S-07: a broken KB store must fail loudly, not report no leaks."""
        import autoinfo.kb as kb_mod

        def _boom(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("kb store unavailable")

        monkeypatch.setattr(kb_mod, "KBStore", _boom)
        with pytest.raises(validation_mod.LeakScanError):
            validation_mod._scan_autoinfo_test_leaks()

    async def test_run_scenario_surfaces_leak_scan_error(
        self, recovery_dir: Path, monkeypatch
    ) -> None:
        """R-S-07: a failed leak scan surfaces as a LEAK_SCAN_ERROR warning so a
        passing run is never silently reported leak-free."""

        def _boom() -> list[str]:
            raise validation_mod.LeakScanError("kb store unavailable")

        monkeypatch.setattr(validation_mod, "_scan_autoinfo_test_leaks", _boom)
        result = await run_scenario(
            "recovery-scenario",
            dispatch=self._fake_dispatch,
            steps=[3],
            scenarios_dir=recovery_dir,
        )
        assert result["status"] == "passed"
        warnings = result.get("warnings", [])
        assert any("LEAK_SCAN_ERROR" in w for w in warnings)
        assert any("UNKNOWN" in w for w in warnings)

    async def test_recovery_schema_validation(self, tmp_path: Path) -> None:
        """recovery_steps must be a list of valid steps (same schema)."""
        bad_cases = {
            "bad-recovery-list.yaml": (
                "name: bad-recovery-list\n"
                "description: T\n"
                "category: happy_path\n"
                "pyramid_layer: component\n"
                "pipeline_stage: A7\n"
                ""
                "user_level: B2.5\n"
                "steps:\n"
                "  - name: s\n    tool: fake_tool\n"
                "    recovery_steps: {}\n",
                "recovery_steps.*must be a list",
            ),
            "bad-recovery-tool.yaml": (
                "name: bad-recovery-tool\n"
                "description: T\n"
                "category: happy_path\n"
                "pyramid_layer: component\n"
                "pipeline_stage: A7\n"
                ""
                "user_level: B2.5\n"
                "steps:\n"
                "  - name: s\n    tool: fake_tool\n"
                "    recovery_steps:\n      - name: no-tool-step\n",
                r"recovery_steps\[0\].*'tool'",
            ),
            "bad-min-passing.yaml": (
                "name: bad-min-passing\ndescription: T\nmin_passing: 0\n"
                "steps:\n  - name: s\n    tool: fake_tool\n",
                "min_passing.*positive integer",
            ),
            "bad-pass-ratio.yaml": (
                "name: bad-pass-ratio\ndescription: T\npass_ratio: 2.5\n"
                "steps:\n  - name: s\n    tool: fake_tool\n",
                "pass_ratio.*\\(0, 1\\]",
            ),
        }
        for i, (file_name, (content, pattern)) in enumerate(bad_cases.items()):
            sd = tmp_path / f"scenarios{i}"
            sd.mkdir()
            (sd / file_name).write_text(content, encoding="utf-8")
            with pytest.raises(ValueError, match=pattern):
                load_scenarios(sd)

    def test_diff_populates_recovered_bucket(self, tmp_path) -> None:
        """A step failed in base but passing-with-recovery in head shows up
        in the recovered bucket — the previously-dead wiring (issue #138)."""

        def result(status: str, steps: list[dict]) -> dict:
            return {
                "scenario": "rec",
                "status": status,
                "summary": {
                    "passed": 0,
                    "failed": 1,
                    "unconfigured": 0,
                    "recovered": 0,
                    "total": 1,
                },
                "steps": steps,
            }

        base = save_scenario_results(
            [result("failed", [{"name": "collect", "tool": "test_source", "status": "failed"}])],
            runs_dir=tmp_path,
        )
        head = save_scenario_results(
            [
                result(
                    "passed",
                    [
                        {
                            "name": "collect",
                            "tool": "test_source",
                            "status": "failed",
                            "recovered": True,
                            "recovery_status": "passed",
                            "recovery": [{"name": "fallback", "tool": "echo", "status": "passed"}],
                        }
                    ],
                )
            ],
            runs_dir=tmp_path,
        )
        diff = diff_scenario_runs(base, head)
        assert diff["recovered"] == ["rec"]
        assert diff["recovered_steps"] == {"rec": ["collect"]}
        # Not double-counted as a new pass.
        assert diff["new_passes"] == []
        assert diff["head_passed"] == 1

    def test_diff_recovered_requires_base_failure(self, tmp_path) -> None:
        """Head-passed-with-recovery against a base that was not failed is a
        new pass, not a recovery."""

        def result(status: str, steps: list[dict]) -> dict:
            return {
                "scenario": "rec",
                "status": status,
                "summary": {
                    "passed": 0,
                    "failed": 1,
                    "unconfigured": 0,
                    "recovered": 0,
                    "total": 1,
                },
                "steps": steps,
            }

        base = save_scenario_results([result("passed", [])], runs_dir=tmp_path)
        head = save_scenario_results(
            [result("passed", [{"name": "collect", "status": "failed", "recovered": True}])],
            runs_dir=tmp_path,
        )
        diff = diff_scenario_runs(base, head)
        assert diff["recovered"] == []
        assert diff["new_passes"] == []

    def test_diff_without_recovery_data_unchanged(self, tmp_path) -> None:
        """Diff of runs without recovery metadata behaves as before."""
        base = save_scenario_results(
            [
                {
                    "scenario": "a",
                    "status": "passed",
                    "summary": {
                        "passed": 1,
                        "failed": 0,
                        "unconfigured": 0,
                        "recovered": 0,
                        "total": 1,
                    },
                },
                {
                    "scenario": "b",
                    "status": "failed",
                    "summary": {
                        "passed": 0,
                        "failed": 1,
                        "unconfigured": 0,
                        "recovered": 0,
                        "total": 1,
                    },
                },
            ],
            runs_dir=tmp_path,
        )
        head = save_scenario_results(
            [
                {
                    "scenario": "a",
                    "status": "passed",
                    "summary": {
                        "passed": 1,
                        "failed": 0,
                        "unconfigured": 0,
                        "recovered": 0,
                        "total": 1,
                    },
                },
                {
                    "scenario": "b",
                    "status": "passed",
                    "summary": {
                        "passed": 1,
                        "failed": 0,
                        "unconfigured": 0,
                        "recovered": 0,
                        "total": 1,
                    },
                },
            ],
            runs_dir=tmp_path,
        )
        diff = diff_scenario_runs(base, head)
        assert sorted(diff["new_passes"]) == ["b"]
        assert diff["recovered"] == []
        assert diff["recovered_steps"] == {}
        assert diff["unchanged"] == 1


class TestPerStepTimeoutAndArtifacts:
    """Todo 11 (R-S-01, R-S-02): the engine honors a step-level
    ``timeout_seconds`` (step → scenario ``timeout`` → MCP/global default) and
    a step-level ``collect_artifacts`` list, and rejects unknown/ambiguous
    placements instead of silently ignoring them.
    """

    _META = "category: happy_path\npyramid_layer: component\npipeline_stage: A7\nuser_level: B2.5\n"

    async def _dispatch(self, name: str, arguments: dict) -> dict:
        if name == "slow_tool":
            await asyncio.sleep(5)
            return {"success": True, "data": {}}
        return {"success": True, "data": {"result": "ok"}}

    def _write(self, tmp_path: Path, name: str, body: str) -> Path:
        sd = tmp_path / "scenarios"
        sd.mkdir(exist_ok=True)
        (sd / f"{name}.yaml").write_text(body, encoding="utf-8")
        return sd

    async def test_step_timeout_seconds_cuts_hanging_step(self, tmp_path: Path) -> None:
        """A step declaring ``timeout_seconds: 1`` is cut at ~1s even though the
        dispatch hangs for 5s and the MCP/global default is 180s (R-S-01)."""
        sd = self._write(
            tmp_path,
            "step-timeout",
            "name: step-timeout\ndescription: d\n" + self._META + "steps:\n"
            "  - name: hang\n    tool: slow_tool\n    timeout_seconds: 1\n"
            "    arguments: {}\n    expect:\n      success: true\n",
        )
        start = time.monotonic()
        result = await run_scenario("step-timeout", dispatch=self._dispatch, scenarios_dir=sd)
        elapsed = time.monotonic() - start
        step = result["steps"][0]
        assert step["status"] == "failed"
        assert step["detail"] == "timed out after 1.0s"
        assert elapsed < 3.0, f"per-step timeout ignored: ran {elapsed:.2f}s"
        assert result["status"] == "failed"

    async def test_step_timeout_falls_back_to_scenario_timeout(self, tmp_path: Path) -> None:
        """With no step-level budget, the scenario-level ``timeout`` bounds the
        step — the middle rung of the inheritance chain."""
        sd = self._write(
            tmp_path,
            "scenario-timeout",
            "name: scenario-timeout\ndescription: d\n" + self._META + "timeout: 1\n"
            "steps:\n"
            "  - name: hang\n    tool: slow_tool\n"
            "    arguments: {}\n    expect:\n      success: true\n",
        )
        start = time.monotonic()
        result = await run_scenario("scenario-timeout", dispatch=self._dispatch, scenarios_dir=sd)
        elapsed = time.monotonic() - start
        assert result["steps"][0]["status"] == "failed"
        assert result["steps"][0]["detail"] == "timed out after 1.0s"
        assert elapsed < 3.0

    async def test_step_level_collect_artifacts_is_honored(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """A step-level ``collect_artifacts`` list is collected, additively with
        the scenario-level default (R-S-02)."""
        sd = self._write(
            tmp_path,
            "step-artifacts",
            "name: step-artifacts\ndescription: d\n"
            + self._META
            + 'collect_artifacts: ["outputs/**/*.md"]\n'
            "steps:\n"
            "  - name: emits\n    tool: fake_tool\n"
            '    collect_artifacts: ["knowledge/**/*.md"]\n'
            "    arguments: {}\n    expect:\n      success: true\n",
        )
        cwd = tmp_path / "cwd"
        baseline = cwd / "outputs" / "medical-research" / "digest.md"
        baseline.parent.mkdir(parents=True)
        baseline.write_text("# digest\n", encoding="utf-8")
        step_artifact = cwd / "knowledge" / "medical-research" / "01-Raw" / "e.md"
        step_artifact.parent.mkdir(parents=True)
        step_artifact.write_text("# entry\n", encoding="utf-8")
        monkeypatch.chdir(cwd)

        result = await run_scenario("step-artifacts", dispatch=self._dispatch, scenarios_dir=sd)
        paths = {a["path"] for a in result["artifacts"]}
        assert str(step_artifact) in paths, f"step artifact missing: {paths}"
        assert str(baseline) in paths, f"scenario baseline missing: {paths}"

    def test_cleanup_step_collect_artifacts_rejected(self, tmp_path: Path) -> None:
        """A cleanup-step ``collect_artifacts`` cannot be honored (the artifact
        snapshot precedes cleanup) — the loader rejects it instead of dropping
        it (R-S-02)."""
        sd = self._write(
            tmp_path,
            "cleanup-artifacts",
            "name: cleanup-artifacts\ndescription: d\n"
            + self._META
            + "steps:\n  - name: s\n    tool: fake_tool\n    arguments: {}\n"
            "cleanup_steps:\n"
            "  - name: c\n    tool: fake_tool\n"
            '    collect_artifacts: ["outputs/**/*.md"]\n',
        )
        with pytest.raises(ValueError, match="collect_artifacts.*cleanup"):
            load_scenarios(sd)

    def test_nested_collect_artifacts_is_unknown_placement(self, tmp_path: Path) -> None:
        """``collect_artifacts`` nested under ``expect`` is never read — reject
        it as an unknown placement rather than silently ignoring it."""
        sd = self._write(
            tmp_path,
            "nested-artifacts",
            "name: nested-artifacts\ndescription: d\n"
            + self._META
            + "steps:\n  - name: s\n    tool: fake_tool\n    arguments: {}\n"
            "    expect:\n      success: true\n"
            '      collect_artifacts: ["outputs/**/*.md"]\n',
        )
        with pytest.raises(ValueError, match="collect_artifacts.*unknown"):
            load_scenarios(sd)

    def test_malformed_collect_artifacts_rejected(self, tmp_path: Path) -> None:
        """A non-list ``collect_artifacts`` value fails to load."""
        sd = self._write(
            tmp_path,
            "bad-artifacts",
            "name: bad-artifacts\ndescription: d\n"
            + self._META
            + 'collect_artifacts: "outputs/**/*.md"\n'
            "steps:\n  - name: s\n    tool: fake_tool\n    arguments: {}\n",
        )
        with pytest.raises(ValueError, match="collect_artifacts.*list"):
            load_scenarios(sd)


class TestRunScenarioRecoveryPackaged:
    """Issue #138: the packaged recovery scenarios execute end-to-end via the
    real MCP dispatch and pass on partial/recovered accounting."""

    @pytest.mark.asyncio
    async def test_collect_failure_recovery_via_dispatch(self) -> None:
        """The packaged collect-failure-recovery scenario passes with
        recovered accounting via the MCP dispatch handler."""
        handler = mcp_server.app.request_handlers[CallToolRequest]
        request = CallToolRequest(
            method="tools/call",
            params=CallToolRequestParams(
                name="run_validation_scenario",
                arguments={"scenario": "collect-failure-recovery"},
            ),
        )
        result = await handler(request)
        call_result = result.root
        data = json.loads(call_result.content[0].text)

        assert data["success"] is True
        assert data["data"]["status"] == "passed"
        assert data["data"]["summary"]["recovered"] == 1
        assert data["data"]["summary"]["failed"] == 0
        primary = data["data"]["steps"][0]
        assert primary["recovered"] is True
        assert primary["recovery_status"] == "passed"
        assert primary["recovery"][0]["status"] == "passed"

    @pytest.mark.asyncio
    async def test_llm_failure_recovery_via_dispatch(self) -> None:
        """The packaged llm-failure-recovery scenario passes whether or not an
        LLM key is present: without a key the LLM-required primary fails and
        the fallback recovery recovers it (min_passing 2 still met)."""
        handler = mcp_server.app.request_handlers[CallToolRequest]
        request = CallToolRequest(
            method="tools/call",
            params=CallToolRequestParams(
                name="run_validation_scenario",
                arguments={"scenario": "llm-failure-recovery"},
            ),
        )
        result = await handler(request)
        call_result = result.root
        data = json.loads(call_result.content[0].text)

        assert data["success"] is True
        assert data["data"]["status"] == "passed"
        # Without a key: 1 recovered + 1 passed.  With a key: 2 passed.
        assert data["data"]["summary"]["recovered"] + data["data"]["summary"]["passed"] == 2
        assert data["data"]["summary"]["failed"] == 0


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
            params=CallToolRequestParams(name="list_validation_scenarios", arguments={}),
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
    async def test_run_llm_gated_reports_unconfigured_without_key(self, monkeypatch) -> None:
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


# ============================================================================
# Unit tests: validation run persistence + cross-run diff (fixes #129 P0-3)
# ============================================================================


class TestValidationRunPersistence:
    """save_scenario_results / list_validation_runs / load_scenario_results /
    diff_scenario_runs regression coverage."""

    def _result(self, status: str, total: int = 1) -> dict:
        passed = 1 if status == "passed" else 0
        return {
            "scenario": "unused",
            "status": status,
            "summary": {
                "passed": passed,
                "failed": total - passed,
                "unconfigured": 0,
                "total": total,
            },
        }

    def test_save_writes_scenarios_json_and_latest_pointer(self, tmp_path) -> None:
        run_dir = save_scenario_results(
            [{"scenario": "a", "status": "passed", "summary": {}}], runs_dir=tmp_path
        )
        assert run_dir.is_dir()
        assert (run_dir / "scenarios.json").exists()
        assert (tmp_path / "latest.txt").read_text().strip() == run_dir.name

    def test_list_returns_newest_first(self, tmp_path) -> None:
        save_scenario_results([self._result("passed")], runs_dir=tmp_path)
        save_scenario_results([self._result("failed")], runs_dir=tmp_path)
        runs = list_validation_runs(tmp_path)
        assert len(runs) == 2
        # latest.txt points at the most recent run, and list is newest-first.
        assert (tmp_path / "latest.txt").read_text().strip() == runs[0].name

    def test_load_roundtrip(self, tmp_path) -> None:
        run_dir = save_scenario_results(
            [{"scenario": "a", "status": "passed", "summary": {"passed": 2, "total": 2}}],
            runs_dir=tmp_path,
        )
        loaded = load_scenario_results(run_dir)
        assert loaded is not None
        assert loaded["scenarios"][0]["scenario"] == "a"

    def test_diff_detects_regression_and_new_pass(self, tmp_path) -> None:
        base = save_scenario_results(
            [
                {"scenario": "a", "status": "passed", "summary": {}},
                {"scenario": "b", "status": "failed", "summary": {}},
                {"scenario": "c", "status": "passed", "summary": {}},
            ],
            runs_dir=tmp_path,
        )
        head = save_scenario_results(
            [
                {"scenario": "a", "status": "passed", "summary": {}},
                {"scenario": "b", "status": "passed", "summary": {}},
                {"scenario": "c", "status": "failed", "summary": {}},
            ],
            runs_dir=tmp_path,
        )
        diff = diff_scenario_runs(base, head)
        assert sorted(diff["regressed"]) == ["c"]
        assert sorted(diff["new_passes"]) == ["b"]
        assert diff["head_passed"] == 2
        assert diff["head_failed"] == 1


class TestDiffScenarioClassification:
    """TR-S-01: ``diff_scenario_runs`` must classify persistent non-passed
    statuses as unchanged — never as fresh ``new_failures`` — and must count
    each unchanged scenario exactly once."""

    @staticmethod
    def _run(tmp_path: Path, name: str, scenarios: list[tuple[str, str]]) -> Path:
        return save_scenario_results(
            [{"scenario": n, "status": s, "summary": {}} for n, s in scenarios],
            runs_dir=tmp_path / name,
        )

    def test_identical_failed_and_unconfigured_not_new_failures(self, tmp_path) -> None:
        """Two identical runs of {failed, unconfigured} are fully unchanged."""
        scenarios = [("f", "failed"), ("u", "unconfigured")]
        base = self._run(tmp_path, "base", scenarios)
        head = self._run(tmp_path, "head", scenarios)
        diff = diff_scenario_runs(base, head)
        assert diff["new_failures"] == []
        assert diff["new_passes"] == []
        assert diff["regressed"] == []
        assert diff["unchanged"] == 2

    def test_same_status_same_status_is_unchanged(self, tmp_path) -> None:
        for status in ("passed", "failed", "unconfigured", "skipped", "error"):
            base = self._run(tmp_path, "base", [("s", status)])
            head = self._run(tmp_path, "head", [("s", status)])
            diff = diff_scenario_runs(base, head)
            assert diff["unchanged"] == 1, status
            assert diff["new_failures"] == [], status
            assert diff["new_passes"] == [], status
            assert diff["regressed"] == [], status

    def test_persistent_failure_is_not_new_failure(self, tmp_path) -> None:
        base = self._run(tmp_path, "base", [("s", "failed")])
        head = self._run(tmp_path, "head", [("s", "failed")])
        diff = diff_scenario_runs(base, head)
        assert diff["new_failures"] == []
        assert diff["unchanged"] == 1

    def test_failed_to_passed_is_new_pass(self, tmp_path) -> None:
        base = self._run(tmp_path, "base", [("s", "failed")])
        head = self._run(tmp_path, "head", [("s", "passed")])
        diff = diff_scenario_runs(base, head)
        assert diff["new_passes"] == ["s"]
        assert diff["new_failures"] == []
        assert diff["regressed"] == []
        assert diff["unchanged"] == 0

    def test_passed_to_failed_is_regression(self, tmp_path) -> None:
        base = self._run(tmp_path, "base", [("s", "passed")])
        head = self._run(tmp_path, "head", [("s", "failed")])
        diff = diff_scenario_runs(base, head)
        assert diff["regressed"] == ["s"]
        assert diff["new_passes"] == []
        assert diff["new_failures"] == []
        assert diff["unchanged"] == 0

    def test_new_scenario_failed_is_new_failure(self, tmp_path) -> None:
        base = self._run(tmp_path, "base", [])
        head = self._run(tmp_path, "head", [("s", "failed")])
        diff = diff_scenario_runs(base, head)
        assert diff["new_failures"] == ["s"]
        assert diff["new_passes"] == []
        assert diff["regressed"] == []
        assert diff["unchanged"] == 0

    def test_new_scenario_passed_is_new_pass(self, tmp_path) -> None:
        base = self._run(tmp_path, "base", [])
        head = self._run(tmp_path, "head", [("s", "passed")])
        diff = diff_scenario_runs(base, head)
        assert diff["new_passes"] == ["s"]
        assert diff["new_failures"] == []
        assert diff["regressed"] == []
        assert diff["unchanged"] == 0

    def test_passed_to_unconfigured_is_regression(self, tmp_path) -> None:
        base = self._run(tmp_path, "base", [("s", "passed")])
        head = self._run(tmp_path, "head", [("s", "unconfigured")])
        diff = diff_scenario_runs(base, head)
        assert diff["regressed"] == ["s"]
        assert diff["new_passes"] == []
        assert diff["new_failures"] == []
        assert diff["unchanged"] == 0


# ============================================================================
# Unit tests: run_all_scenarios aggregate suite run (R-S-05)
# ============================================================================


class TestRunAllScenariosAggregate:
    """R-S-05: one suite invocation runs the whole live library and persists a
    single aggregate run whose ``scenarios[]`` carries every scenario result.

    The per-scenario ``run_validation_scenario`` save path stays a single-
    scenario run (``run_type="single"``); the suite path must not change it.
    """

    SCENARIO_TMPL = """\
name: {name}
description: "aggregate {name}"
category: happy_path
requires_env: []
pyramid_layer: component
pipeline_stage: A7
user_level: B2.5
steps:
  - name: "step"
    tool: {tool}
    arguments: {{}}
    expect:
      success: true
"""

    def _scenarios_dir(self, tmp_path: Path) -> Path:
        sd = tmp_path / "scenarios"
        sd.mkdir()
        for name, tool in (
            ("alpha-ok", "ok_tool"),
            ("beta-ok", "ok_tool"),
            ("gamma-fail", "fail_tool"),
        ):
            (sd / f"{name}.yaml").write_text(
                self.SCENARIO_TMPL.format(name=name, tool=tool), encoding="utf-8"
            )
        return sd

    async def _dispatch(self, name: str, arguments: dict) -> dict:
        if name == "ok_tool":
            return {"success": True, "data": {"result": "ok"}}
        if name == "fail_tool":
            return {"success": False, "error": {"code": "X", "message": "boom"}}
        return {"success": True, "data": {}}

    async def test_aggregate_run_runs_library_and_persists_one_run(self, tmp_path: Path) -> None:
        sd = self._scenarios_dir(tmp_path)
        runs_dir = tmp_path / "runs"

        result = await run_all_scenarios(
            self._dispatch, scenarios_dir=sd, runs_dir=runs_dir, save=True
        )

        assert result["suite"] is True
        assert result["count"] == 3
        assert result["status"] == "failed"  # gamma-fail — never misleading
        assert result["summary"]["total"] == 3
        assert result["summary"]["passed"] == 2
        assert result["summary"]["failed"] == 1
        assert sorted(s["scenario"] for s in result["scenarios"]) == [
            "alpha-ok",
            "beta-ok",
            "gamma-fail",
        ]

        saved = Path(result["saved_run"])
        assert saved.parent == runs_dir
        assert (runs_dir / "latest.txt").read_text().strip() == saved.name
        # ONE aggregate run only — not one directory per scenario.
        assert len(list_validation_runs(runs_dir)) == 1
        payload = load_scenario_results(saved)
        assert payload is not None
        assert payload["run_type"] == "suite"
        assert payload["scenarios"][0]["scenario"] == "alpha-ok"
        assert len(payload["scenarios"]) == 3

    async def test_aggregate_all_pass_reports_passed(self, tmp_path: Path) -> None:
        sd = tmp_path / "scenarios"
        sd.mkdir()
        for name in ("alpha-ok", "beta-ok"):
            (sd / f"{name}.yaml").write_text(
                self.SCENARIO_TMPL.format(name=name, tool="ok_tool"),
                encoding="utf-8",
            )
        result = await run_all_scenarios(
            self._dispatch, scenarios_dir=sd, runs_dir=tmp_path / "runs"
        )
        assert result["status"] == "passed"
        assert result["summary"]["failed"] == 0
        assert result["summary"]["unconfigured"] == 0

    async def test_aggregate_save_false_writes_no_run(self, tmp_path: Path) -> None:
        sd = self._scenarios_dir(tmp_path)
        runs_dir = tmp_path / "runs"
        result = await run_all_scenarios(
            self._dispatch, scenarios_dir=sd, runs_dir=runs_dir, save=False
        )
        assert "saved_run" not in result
        assert not runs_dir.exists()

    def test_save_defaults_to_single_run_type(self, tmp_path: Path) -> None:
        run_dir = save_scenario_results(
            [{"scenario": "a", "status": "passed", "summary": {}}],
            runs_dir=tmp_path,
        )
        payload = load_scenario_results(run_dir)
        assert payload is not None
        assert payload["run_type"] == "single"


# ============================================================================
# Unit tests: category x pyramid ledger + N-run pass-rate history
# (TR-B-01 / TR-B-02)
# ============================================================================


class TestCategoryPyramidLedger:
    """TR-B-01/TR-B-02: per-scenario results aggregate into the 5x4
    category x pyramid grid, and pass history accumulates across suite runs
    (never overwritten) so N-run pass rates can be gated hard 5/5 / soft 4/5.
    """

    @staticmethod
    def _scenario(name: str, category: str, layer: str, status: str) -> dict:
        return {
            "scenario": name,
            "category": category,
            "pyramid_layer": layer,
            "status": status,
            "summary": {
                "passed": 1 if status == "passed" else 0,
                "failed": 1 if status == "failed" else 0,
                "unconfigured": 1 if status == "unconfigured" else 0,
                "recovered": 0,
                "total": 1,
            },
        }

    def test_aggregate_grid_and_unclassified(self) -> None:
        agg = aggregate_category_pyramid(
            [
                self._scenario("a", "happy_path", "component", "passed"),
                self._scenario("b", "happy_path", "e2e", "failed"),
                self._scenario("c", "failure", "component", "passed"),
                {"scenario": "bad", "category": "nope", "status": "passed"},
            ]
        )
        assert set(agg["cells"]) == {
            "happy_path|component",
            "happy_path|e2e",
            "failure|component",
        }
        hp = agg["cells"]["happy_path|component"]
        assert hp["scenarios"] == 1
        assert hp["status"] == "passed"
        assert hp["passed"] == 1
        assert agg["cells"]["happy_path|e2e"]["status"] == "failed"
        assert [u["scenario"] for u in agg["unclassified"]] == ["bad"]
        assert agg["total"] == 4

    def test_cell_verdict_unconfigured_semantics(self) -> None:
        all_gated = aggregate_category_pyramid(
            [
                self._scenario("u1", "happy_path", "unit", "unconfigured"),
            ]
        )
        assert all_gated["cells"]["happy_path|unit"]["status"] == "unconfigured"
        mixed = aggregate_category_pyramid(
            [
                self._scenario("p", "happy_path", "unit", "passed"),
                self._scenario("u", "happy_path", "unit", "unconfigured"),
            ]
        )
        assert mixed["cells"]["happy_path|unit"]["status"] == "partial"

    def test_suite_save_records_ledger_single_does_not(self, tmp_path: Path) -> None:
        runs = tmp_path / "runs"
        save_scenario_results(
            [self._scenario("a", "happy_path", "component", "passed")],
            runs_dir=runs,
            run_type="single",
        )
        assert not (runs / CATEGORY_PYRAMID_HISTORY_FILE).exists()
        save_scenario_results(
            [self._scenario("a", "happy_path", "component", "passed")],
            runs_dir=runs,
            run_type="suite",
        )
        ledger = load_category_pyramid_history(runs)
        assert len(ledger["runs"]) == 1
        assert ledger["runs"][0]["run_type"] == "suite"
        assert ledger["runs"][0]["cells"]["happy_path|component"]["status"] == "passed"

    async def test_two_suite_runs_accumulate_not_overwrite(self, tmp_path: Path) -> None:
        sd = tmp_path / "scenarios"
        sd.mkdir()
        (sd / "one.yaml").write_text(
            TestRunAllScenariosAggregate.SCENARIO_TMPL.format(name="one", tool="ok_tool"),
            encoding="utf-8",
        )

        async def dispatch(tool: str, arguments: dict) -> dict:
            return {"success": True, "data": {}}

        runs = tmp_path / "runs"
        await run_all_scenarios(dispatch, scenarios_dir=sd, runs_dir=runs)
        assert len(load_category_pyramid_history(runs)["runs"]) == 1
        await run_all_scenarios(dispatch, scenarios_dir=sd, runs_dir=runs)
        entries = load_category_pyramid_history(runs)["runs"]
        assert len(entries) == 2
        assert len({r["run_id"] for r in entries}) == 2

    def test_n_run_rates_hard_soft_and_unmeasured(self, tmp_path: Path) -> None:
        runs = tmp_path / "runs"
        for i, status in enumerate(["passed", "passed", "passed", "passed", "failed"]):
            record_category_pyramid_history(
                [self._scenario("a", "happy_path", "component", status)],
                run_id=f"2026-01-0{i + 1}_000000_000000",
                runs_dir=runs,
            )
        rep = category_pyramid_history_report(runs)
        cell = rep["cells"]["happy_path|component"]
        assert rep["total_runs"] == 5
        assert cell["runs"] == 5
        assert cell["passes"] == 4
        assert cell["rate"] == pytest.approx(0.8)
        assert cell["meets_hard"] is False
        assert cell["meets_soft"] is True
        assert sum(1 for h in cell["history"] if h["status"] == "passed") == 4
        unmeasured = rep["cells"]["performance|red_team"]
        assert unmeasured["runs"] == 0
        assert unmeasured["rate"] is None
        assert unmeasured["meets_hard"] is False
        assert unmeasured["meets_soft"] is False

    def test_five_of_five_meets_hard(self, tmp_path: Path) -> None:
        runs = tmp_path / "runs"
        for i in range(5):
            record_category_pyramid_history(
                [self._scenario("a", "happy_path", "component", "passed")],
                run_id=f"2026-02-0{i + 1}_000000_000000",
                runs_dir=runs,
            )
        cell = category_pyramid_history_report(runs)["cells"]["happy_path|component"]
        assert cell["passes"] == 5
        assert cell["rate"] == 1.0
        assert cell["meets_hard"] is True
        assert cell["meets_soft"] is True

    def test_window_restricts_rate_but_reports_total(self, tmp_path: Path) -> None:
        runs = tmp_path / "runs"
        for i, status in enumerate(["failed", "passed", "passed", "passed", "passed"]):
            record_category_pyramid_history(
                [self._scenario("a", "happy_path", "component", status)],
                run_id=f"2026-03-0{i + 1}_000000_000000",
                runs_dir=runs,
            )
        rep = category_pyramid_history_report(runs, window=4)
        assert rep["total_runs"] == 5
        cell = rep["cells"]["happy_path|component"]
        assert cell["runs"] == 4
        assert cell["passes"] == 4
        assert cell["meets_hard"] is True


# ============================================================================
# Unit tests: run_scenario per-step timeout (issue #134, engine part)
# ============================================================================


class TestRunScenarioTimeout:
    """Per-step timeout enforcement in run_scenario (issue #134)."""

    SCENARIO_YAML = """\
name: timeout-scenario
description: "Scenario with a hang-prone step"
category: happy_path
requires_env: []
pyramid_layer: component
pipeline_stage: A7
user_level: B2.5
steps:
  - name: "fast step"
    tool: fast_tool
    arguments: {}
    expect:
      success: true

  - name: "slow step"
    tool: slow_tool
    arguments: {}
    expect:
      success: true

  - name: "post-hang step"
    tool: fast_tool
    arguments: {}
    expect:
      success: true
"""

    CLEANUP_SCENARIO_YAML = """\
name: timeout-cleanup-scenario
description: "Scenario whose cleanup step hangs"
category: happy_path
requires_env: []
pyramid_layer: component
pipeline_stage: A7
user_level: B2.5
steps:
  - name: "fast step"
    tool: fast_tool
    arguments: {}
    expect:
      success: true
cleanup_steps:
  - name: "slow cleanup step"
    tool: slow_tool
    arguments: {}
    expect:
      success: true
"""

    @pytest.fixture
    def scenario_dir(self, tmp_path: Path) -> Path:
        sd = tmp_path / "scenarios"
        sd.mkdir()
        (sd / "timeout-scenario.yaml").write_text(self.SCENARIO_YAML, encoding="utf-8")
        (sd / "timeout-cleanup-scenario.yaml").write_text(
            self.CLEANUP_SCENARIO_YAML, encoding="utf-8"
        )
        return sd

    async def _fake_dispatch(self, name: str, arguments: dict) -> dict:
        """Hang far beyond the 0.1s test timeout for slow_tool; pass otherwise."""
        if name == "slow_tool":
            await asyncio.sleep(5)
        return {"success": True, "data": {"result": "ok"}}

    async def test_hanging_step_times_out_and_fails_scenario(self, scenario_dir: Path) -> None:
        """A step exceeding the per-step timeout reports failed with 'timed out'."""
        result = await run_scenario(
            "timeout-scenario",
            dispatch=self._fake_dispatch,
            steps=[2],
            scenarios_dir=scenario_dir,
            timeout=0.1,
        )
        assert result["status"] == "failed"
        assert result["summary"]["failed"] == 1
        step = result["steps"][0]
        assert step["status"] == "failed"
        assert "timed out" in step["detail"]
        assert "0.1" in step["detail"]

    async def test_cleanup_timeout_reported_but_does_not_flip_status(
        self, scenario_dir: Path
    ) -> None:
        """A timed-out cleanup step is reported but never flips scenario status."""
        result = await run_scenario(
            "timeout-cleanup-scenario",
            dispatch=self._fake_dispatch,
            scenarios_dir=scenario_dir,
            timeout=0.1,
        )
        assert result["status"] == "passed"
        assert result["summary"]["failed"] == 0
        assert "cleanup" in result
        assert result["cleanup"]["summary"]["failed"] == 1
        cleanup_step = result["cleanup"]["steps"][0]
        assert cleanup_step["status"] == "failed"
        assert "timed out" in cleanup_step["detail"]

    async def test_default_timeout_backward_compatible(self, scenario_dir: Path) -> None:
        """Without a timeout arg, a fast step passes as before."""
        result = await run_scenario(
            "timeout-scenario",
            dispatch=self._fake_dispatch,
            steps=[1],
            scenarios_dir=scenario_dir,
        )
        assert result["status"] == "passed"
        assert result["steps"][0]["status"] == "passed"

    async def test_hang_on_middle_step_loop_continues(self, scenario_dir: Path) -> None:
        """Timeout is per-step: a hang on step 2 fails it but steps 1 and 3 still run."""
        calls: list[str] = []

        async def tracking_dispatch(name: str, arguments: dict) -> dict:
            calls.append(name)
            if name == "slow_tool":
                await asyncio.sleep(5)
            return {"success": True, "data": {"result": "ok"}}

        result = await run_scenario(
            "timeout-scenario",
            dispatch=tracking_dispatch,
            scenarios_dir=scenario_dir,
            timeout=0.1,
        )
        assert result["status"] == "failed"
        assert calls == ["fast_tool", "slow_tool", "fast_tool"]
        assert result["steps"][0]["status"] == "passed"
        assert result["steps"][1]["status"] == "failed"
        assert "timed out" in result["steps"][1]["detail"]
        assert result["steps"][2]["status"] == "passed"


class TestMCPRunValidationScenarioTimeout:
    """E4: MCP run_validation_scenario handler passes timeout to run_scenario."""

    @staticmethod
    def _mock_result() -> dict[str, Any]:
        return {
            "status": "passed",
            "steps": [],
            "counts": {"passed": 0, "failed": 0, "unconfigured": 0},
        }

    @pytest.mark.asyncio
    async def test_handler_passes_timeout_to_run_scenario(self) -> None:
        """timeout param forwarded to run_scenario."""
        from unittest.mock import AsyncMock, patch

        with patch(
            "autoinfo.mcp.validation.run_scenario",
            new_callable=AsyncMock,
            return_value=self._mock_result(),
        ) as mock_rs:
            from autoinfo.mcp.server import _handle_run_validation_scenario

            result = await _handle_run_validation_scenario(scenario="test-scene", timeout=60.0)
            mock_rs.assert_called_once()
            call_kwargs = mock_rs.call_args.kwargs
            assert call_kwargs.get("timeout") == 60.0
            assert result["status"] == "passed"

    @pytest.mark.asyncio
    async def test_handler_default_timeout(self) -> None:
        """Default timeout is 180.0."""
        from unittest.mock import AsyncMock, patch

        with patch(
            "autoinfo.mcp.validation.run_scenario",
            new_callable=AsyncMock,
            return_value=self._mock_result(),
        ) as mock_rs:
            from autoinfo.mcp.server import _handle_run_validation_scenario

            result = await _handle_run_validation_scenario(scenario="test-scene")
            mock_rs.assert_called_once()
            call_kwargs = mock_rs.call_args.kwargs
            assert call_kwargs.get("timeout") == 180.0
            assert result["status"] == "passed"


# ============================================================================
# Unit tests: per-step execution trace (issue #139)
# ============================================================================


class TestStepExecutionTrace:
    """Issue #139: every step result carries step_index / duration /
    arguments / trace_id, and llm_assert steps embed judge observability
    (llm_meta) while keeping the top-level llm_reason."""

    TRACE_SCENARIO_YAML = """\
name: trace-scenario
description: "Trace-field scenario"
category: happy_path
requires_env: []
pyramid_layer: component
pipeline_stage: A7
user_level: B2.5
steps:
  - name: "pass with args"
    tool: fake_tool
    arguments: {limit: 5, q: "alpha"}
    expect:
      success: true
      data_has: ["result"]

  - name: "failing step"
    tool: fake_error
    arguments: {}
    expect:
      success: true
"""

    LLM_TRACE_SCENARIO_YAML = """\
name: llm-trace-scenario
description: "LLM trace-field scenario"
category: happy_path
requires_env: []
pyramid_layer: component
pipeline_stage: A7
user_level: B2.5
steps:
  - name: "llm pass with meta"
    tool: fake_tool
    arguments: {}
    expect:
      success: true
      llm_assert: "Is the result ok?"

  - name: "llm fail with meta"
    tool: fake_tool
    arguments: {}
    expect:
      success: true
      llm_assert: "Is the result bad?"
"""

    @pytest.fixture
    def trace_dir(self, tmp_path: Path) -> Path:
        sd = tmp_path / "scenarios"
        sd.mkdir()
        (sd / "trace-scenario.yaml").write_text(self.TRACE_SCENARIO_YAML, encoding="utf-8")
        (sd / "llm-trace-scenario.yaml").write_text(self.LLM_TRACE_SCENARIO_YAML, encoding="utf-8")
        (sd / "env-gated.yaml").write_text(
            "name: env-gated\ndescription: T\ncategory: happy_path\n"
            "pyramid_layer: component\npipeline_stage: A7\nuser_level: B2.5\n"
            "requires_env: [MISSING_VAR_XYZ]\n"
            "steps:\n  - name: gated\n    tool: health_check\n    arguments: {}\n",
            encoding="utf-8",
        )
        return sd

    async def _fake_dispatch(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "fake_tool":
            return {"success": True, "data": {"result": "ok"}}
        if name == "fake_error":
            return {"success": False, "error": {"code": "Timeout", "message": "timeout"}}
        return {"success": True, "data": {}}

    async def test_steps_carry_trace_fields(self, trace_dir: Path) -> None:
        """Every step result carries step_index/duration/arguments/trace_id."""
        result = await run_scenario(
            "trace-scenario",
            dispatch=self._fake_dispatch,
            scenarios_dir=trace_dir,
        )
        assert result["status"] == "failed"  # step 2 fails
        trace_id = result["trace_id"]
        assert len(trace_id) == 36  # uuid4 string form
        assert len(result["steps"]) == 2
        for i, step in enumerate(result["steps"], start=1):
            assert step["step_index"] == i
            assert isinstance(step["duration"], float)
            assert step["duration"] >= 0.0
            assert step["trace_id"] == trace_id
            # Pre-existing keys are preserved alongside the new fields.
            assert step["name"]
            assert step["tool"]
            assert step["status"]
            assert "detail" in step
        assert result["steps"][0]["arguments"] == {"limit": 5, "q": "alpha"}
        assert result["steps"][1]["arguments"] == {}

    async def test_trace_id_shared_across_steps(self, trace_dir: Path) -> None:
        """One uuid per run, shared by every step and the top-level result."""
        result = await run_scenario(
            "trace-scenario",
            dispatch=self._fake_dispatch,
            scenarios_dir=trace_dir,
        )
        ids = {step["trace_id"] for step in result["steps"]}
        assert ids == {result["trace_id"]}

    async def test_llm_meta_embedded_on_llm_assert_pass(self, trace_dir: Path, monkeypatch) -> None:
        """llm_assert PASS path embeds llm_meta while keeping llm_reason."""
        monkeypatch.setattr("autoinfo.mcp.validation._is_llm_configured", lambda: True)
        monkeypatch.setattr(
            "autoinfo.mcp.validation._llm_judge",
            lambda assertion, output: {
                "verdict": "PASS",
                "reason": "result is ok",
                "model": "test-model",
                "tokens": {"prompt_tokens": 10, "total_tokens": 20},
                "duration": 0.5,
            },
        )
        result = await run_scenario(
            "llm-trace-scenario",
            dispatch=self._fake_dispatch,
            steps=[1],
            scenarios_dir=trace_dir,
        )
        step = result["steps"][0]
        assert step["status"] == "passed"
        assert step["llm_reason"] == "result is ok"
        assert step["llm_meta"] == {
            "model": "test-model",
            "tokens": {"prompt_tokens": 10, "total_tokens": 20},
            "duration": 0.5,
        }
        assert step["step_index"] == 1
        assert step["trace_id"] == result["trace_id"]

    async def test_llm_meta_embedded_on_llm_assert_fail(self, trace_dir: Path, monkeypatch) -> None:
        """llm_assert FAIL path embeds llm_meta alongside llm_reason."""
        monkeypatch.setattr("autoinfo.mcp.validation._is_llm_configured", lambda: True)
        monkeypatch.setattr(
            "autoinfo.mcp.validation._llm_judge",
            lambda assertion, output: {
                "verdict": "FAIL",
                "reason": "output is bad",
                "model": "test-model",
                "tokens": {"prompt_tokens": 3, "total_tokens": 9},
                "duration": 0.25,
            },
        )
        result = await run_scenario(
            "llm-trace-scenario",
            dispatch=self._fake_dispatch,
            steps=[2],
            scenarios_dir=trace_dir,
        )
        step = result["steps"][0]
        assert step["status"] == "failed"
        assert step["llm_reason"] == "output is bad"
        assert step["llm_meta"]["model"] == "test-model"
        assert step["llm_meta"]["duration"] == 0.25
        assert step["trace_id"] == result["trace_id"]

    async def test_unconfigured_early_return_carries_trace_fields(self, trace_dir: Path) -> None:
        """Env-gated early return decorates its steps with trace fields."""
        env_before = os.environ.pop("MISSING_VAR_XYZ", None)
        try:
            result = await run_scenario(
                "env-gated",
                dispatch=self._fake_dispatch,
                scenarios_dir=trace_dir,
            )
            assert result["status"] == "unconfigured"
            assert result["trace_id"]
            step = result["steps"][0]
            assert step["step_index"] == 1
            assert step["duration"] == 0.0
            assert step["arguments"] == {}
            assert step["trace_id"] == result["trace_id"]
        finally:
            if env_before is not None:
                os.environ["MISSING_VAR_XYZ"] = env_before

    async def test_recovery_steps_carry_trace_fields(self, tmp_path: Path) -> None:
        """Recovery step results carry the primary's step_index + run trace_id,
        and the primary duration includes the recovery execution."""
        sd = tmp_path / "scenarios"
        sd.mkdir()
        (sd / "rec-trace.yaml").write_text(
            "name: rec-trace\ndescription: T\ncategory: happy_path\nrequires_env: []\n"
            "pyramid_layer: component\npipeline_stage: A7\nuser_level: B2.5\n"
            "steps:\n"
            "  - name: flaky primary\n    tool: flaky_tool\n    arguments: {retry: 2}\n"
            "    expect:\n      success: true\n"
            "    recovery_steps:\n"
            "      - name: recovery pass\n        tool: fake_tool\n        arguments: {}\n"
            "        expect:\n          success: true\n",
            encoding="utf-8",
        )

        async def dispatch(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
            if name == "flaky_tool":
                return {"success": False, "error": {"code": "X", "message": "boom"}}
            return {"success": True, "data": {"result": "ok"}}

        result = await run_scenario(
            "rec-trace",
            dispatch=dispatch,
            scenarios_dir=sd,
        )
        step = result["steps"][0]
        assert step["recovered"] is True
        assert step["step_index"] == 1
        assert step["step_id"] == "1"
        assert step["arguments"] == {"retry": 2}
        assert step["trace_id"] == result["trace_id"]
        rec = step["recovery"][0]
        assert rec["step_index"] != step["step_index"]
        assert rec["step_id"] == "1.recovery.1"
        assert rec["trace_id"] == result["trace_id"]
        assert rec["arguments"] == {}
        assert isinstance(rec["duration"], float)
        # Primary duration covers the recovery execution too.
        assert step["duration"] >= rec["duration"]

    async def test_step_identity_unique_across_recovery_and_cleanup(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """TR-S-03: no recovery/cleanup step collides with any other identity."""
        monkeypatch.setattr("autoinfo.mcp.validation._scan_autoinfo_test_leaks", lambda: [])
        sd = tmp_path / "scenarios"
        sd.mkdir()
        (sd / "identity.yaml").write_text(
            "name: identity\ndescription: T\ncategory: happy_path\nrequires_env: []\n"
            "pyramid_layer: component\npipeline_stage: A7\nuser_level: B2.5\n"
            "steps:\n"
            "  - name: primary one\n    tool: bad_tool\n    arguments: {}\n"
            "    expect:\n      success: true\n"
            "    recovery_steps:\n"
            "      - name: rec one\n        tool: ok_tool\n        arguments: {}\n"
            "        expect:\n          success: true\n"
            "      - name: rec two\n        tool: bad_tool\n        arguments: {}\n"
            "        expect:\n          success: true\n"
            "  - name: primary two\n    tool: bad_tool\n    arguments: {}\n"
            "    expect:\n      success: true\n"
            "cleanup_steps:\n"
            "  - name: cleanup one\n    tool: ok_tool\n    arguments: {}\n"
            "    expect:\n      success: true\n"
            "  - name: cleanup two\n    tool: bad_tool\n    arguments: {}\n"
            "    expect:\n      success: true\n",
            encoding="utf-8",
        )

        async def dispatch(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
            if name == "bad_tool":
                return {"success": False, "error": {"code": "X", "message": "boom"}}
            return {"success": True, "data": {"result": "ok"}}

        result = await run_scenario("identity", dispatch=dispatch, scenarios_dir=sd)
        identities: list[dict[str, Any]] = []
        for step in result["steps"]:
            identities.append(step)
            identities.extend(step.get("recovery", []))
        identities.extend(result.get("cleanup", {}).get("steps", []))

        indexes = [s["step_index"] for s in identities]
        step_ids = [s["step_id"] for s in identities]
        assert len(indexes) == len(set(indexes)), indexes
        assert len(step_ids) == len(set(step_ids)), step_ids
        assert set(step_ids) == {
            "1",
            "1.recovery.1",
            "1.recovery.2",
            "2",
            "cleanup.1",
            "cleanup.2",
        }

    async def test_timeout_step_carries_trace_fields(self, tmp_path: Path) -> None:
        """A timed-out step still carries the per-step trace fields."""
        sd = tmp_path / "scenarios"
        sd.mkdir()
        (sd / "slow-trace.yaml").write_text(
            "name: slow-trace\ndescription: T\ncategory: happy_path\nrequires_env: []\n"
            "pyramid_layer: component\npipeline_stage: A7\nuser_level: B2.5\n"
            "steps:\n  - name: hang\n    tool: slow_tool\n    arguments: {}\n"
            "    expect:\n      success: true\n",
            encoding="utf-8",
        )

        async def dispatch(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
            await asyncio.sleep(5)
            return {"success": True, "data": {}}

        result = await run_scenario(
            "slow-trace",
            dispatch=dispatch,
            scenarios_dir=sd,
            timeout=0.1,
        )
        step = result["steps"][0]
        assert step["status"] == "failed"
        assert "timed out" in step["detail"]
        assert step["step_index"] == 1
        assert isinstance(step["duration"], float)
        assert step["duration"] >= 0.1
        assert step["arguments"] == {}
        assert step["trace_id"] == result["trace_id"]


class TestLLMJudgeObservability:
    """Issue #139: _llm_judge captures model / tokens / duration."""

    @staticmethod
    def _patch_litellm(monkeypatch, *, with_usage: bool = True) -> dict[str, Any]:
        """Install a fake litellm module returning a canned completion."""
        import sys
        import types

        class _FakeUsage:
            prompt_tokens = 10
            total_tokens = 25

        class _FakeMessage:
            content = '{"verdict": "PASS", "reason": "looks good"}'

        class _FakeChoice:
            message = _FakeMessage()

        class _FakeResponse:
            def __init__(self) -> None:
                self.usage = _FakeUsage() if with_usage else None
                self.choices = [_FakeChoice()]

        calls: dict[str, Any] = {}

        def fake_completion(**kwargs: Any) -> _FakeResponse:
            calls["model"] = kwargs["model"]
            return _FakeResponse()

        fake_litellm = types.SimpleNamespace(completion=fake_completion)
        monkeypatch.setitem(sys.modules, "litellm", fake_litellm)
        monkeypatch.setattr(
            "autoinfo.mcp.validation._resolve_llm_config",
            lambda: {"model": "test-model", "api_key": "k", "api_base": None},
        )
        return calls

    def test_llm_judge_returns_model_tokens_duration(self, monkeypatch) -> None:
        """Judge result carries model, usage tokens, and wall-clock duration."""
        calls = self._patch_litellm(monkeypatch)
        verdict = validation_mod._llm_judge("assertion", {"data": 1})
        assert verdict["verdict"] == "PASS"
        assert verdict["reason"] == "looks good"
        assert verdict["model"] == "test-model"
        assert verdict["tokens"] == {"prompt_tokens": 10, "total_tokens": 25}
        assert isinstance(verdict["duration"], float)
        assert verdict["duration"] >= 0.0
        assert calls["model"] == "test-model"

    def test_llm_judge_tokens_none_without_usage(self, monkeypatch) -> None:
        """Without usage info the tokens field is None (not a crash)."""
        self._patch_litellm(monkeypatch, with_usage=False)
        verdict = validation_mod._llm_judge("assertion", {"data": 1})
        assert verdict["verdict"] == "PASS"
        assert verdict["tokens"] is None
        assert verdict["model"] == "test-model"


# ============================================================================
# Issue #140: regression scenario fields
# ============================================================================


class TestRegressionScenarios:
    """Regression scenarios carry regression / regression_issue fields."""

    def test_loads_regression_scenarios(self) -> None:
        """load_scenarios picks up regression/ subdir scenarios with new fields."""
        scs = load_scenarios()
        regr = [s for s in scs if s.get("regression")]
        assert len(regr) >= 5, f"Expected ≥5 regression scenarios, got {len(regr)}"
        for s in regr:
            assert s["regression"] is True
            assert "regression_issue" in s
            assert isinstance(s["regression_issue"], str)
            assert s["regression_issue"].strip()
        func = [s for s in scs if not s.get("regression")]
        for s in func:
            assert "regression" not in s
            assert "regression_issue" not in s

    @pytest.fixture
    def regression_scenario_dir(self, tmp_path: Path) -> Path:
        sd = tmp_path / "scenarios"
        sd.mkdir()
        (sd / "regression").mkdir()
        (sd / "regression" / "fake-regression.yaml").write_text(
            "name: fake-regression\n"
            'description: "Regression test"\n'
            "category: happy_path\n"
            "pyramid_layer: component\npipeline_stage: A7\nuser_level: B2.5\n"
            "regression: true\n"
            'regression_issue: "#999"\n'
            "requires_env: []\n"
            "steps:\n"
            "  - name: step1\n"
            "    tool: fake_tool\n"
            "    arguments: {}\n"
            "    expect:\n"
            "      success: true\n"
            "      data_has: [result]\n",
            encoding="utf-8",
        )
        (sd / "functional.yaml").write_text(
            "name: functional\n"
            'description: "Functional test"\n'
            "category: happy_path\npyramid_layer: component\npipeline_stage: A7\nuser_level: B2.5\n"
            "requires_env: []\n"
            "steps:\n"
            "  - name: step1\n"
            "    tool: fake_tool\n"
            "    arguments: {}\n"
            "    expect:\n"
            "      success: true\n",
            encoding="utf-8",
        )
        return sd

    async def test_run_scenario_carry_regression_fields(
        self, regression_scenario_dir: Path
    ) -> None:
        async def dispatch(name: str, args: dict) -> dict:
            return {"success": True, "data": {"result": "ok"}}

        result = await run_scenario(
            "fake-regression", dispatch, scenarios_dir=regression_scenario_dir
        )
        assert result["regression"] is True
        assert result["regression_issue"] == "#999"
        assert result["status"] == "passed"

    async def test_run_scenario_no_regression_fields_on_functional(
        self, regression_scenario_dir: Path
    ) -> None:
        async def dispatch(name: str, args: dict) -> dict:
            return {"success": True, "data": {}}

        result = await run_scenario("functional", dispatch, scenarios_dir=regression_scenario_dir)
        assert "regression" not in result
        assert "regression_issue" not in result

    async def test_regression_env_unconfigured_carries_fields(
        self, regression_scenario_dir: Path
    ) -> None:
        """Env-gated regression scenario: unconfigured result carries regression fields."""
        (regression_scenario_dir / "regression" / "env-gated-reg.yaml").write_text(
            "name: env-gated-reg\n"
            'description: "Env gated regression"\n'
            "category: happy_path\n"
            "pyramid_layer: component\npipeline_stage: A7\nuser_level: B2.5\n"
            "regression: true\n"
            'regression_issue: "#888"\n'
            "requires_env: [MISSING_VAR_XYZ_888]\n"
            "steps:\n"
            "  - name: gated\n"
            "    tool: health_check\n",
            encoding="utf-8",
        )
        result = await run_scenario(
            "env-gated-reg", dispatch=None, scenarios_dir=regression_scenario_dir
        )
        assert result["status"] == "unconfigured"
        assert result["regression"] is True
        assert result["regression_issue"] == "#888"


# ============================================================================
# Unit tests: category taxonomy + required pyramid_layer (T-B-01 / T-B-02)
# ============================================================================


class TestScenarioCategoryPyramidMetadata:
    """Every scenario declares one of the 5 fixed categories and a pyramid layer.

    The category taxonomy (happy_path / edge_case / failure /
    agent_interaction / performance) and the 4-layer validation pyramid
    (unit / component / e2e / red_team) are only machine-measurable when the
    loader enforces them.  ``load_scenarios`` rejects a missing/unknown
    ``pyramid_layer`` and an unknown (or missing) ``category``.
    """

    _STEPS = "steps:\n  - name: s\n    tool: health_check\n"

    def _write(self, tmp_path: Path, name: str, body: str) -> Path:
        sd = tmp_path / "scenarios"
        sd.mkdir(parents=True, exist_ok=True)
        (sd / f"{name}.yaml").write_text(body, encoding="utf-8")
        return sd

    def test_missing_pyramid_layer_fails_to_load(self, tmp_path: Path) -> None:
        sd = self._write(
            tmp_path,
            "no-pyramid",
            "name: no-pyramid\ndescription: d\ncategory: happy_path\n"
            "pipeline_stage: A3\nuser_level: B2.4\n" + self._STEPS,
        )
        with pytest.raises(ValueError, match="no-pyramid\\.yaml.*'pyramid_layer'"):
            load_scenarios(sd)

    def test_unknown_pyramid_layer_fails_to_load(self, tmp_path: Path) -> None:
        sd = self._write(
            tmp_path,
            "bad-pyramid",
            "name: bad-pyramid\ndescription: d\ncategory: happy_path\n"
            "pyramid_layer: pyramid\n"
            "pipeline_stage: A3\nuser_level: B2.4\n" + self._STEPS,
        )
        with pytest.raises(ValueError, match="bad-pyramid\\.yaml.*'pyramid_layer'"):
            load_scenarios(sd)

    def test_unknown_category_fails_to_load(self, tmp_path: Path) -> None:
        sd = self._write(
            tmp_path,
            "bad-category",
            "name: bad-category\ndescription: d\ncategory: general\n"
            "pyramid_layer: component\n"
            "pipeline_stage: A3\nuser_level: B2.4\n" + self._STEPS,
        )
        with pytest.raises(ValueError, match="bad-category\\.yaml.*'category'"):
            load_scenarios(sd)

    def test_missing_category_fails_to_load(self, tmp_path: Path) -> None:
        sd = self._write(
            tmp_path,
            "no-category",
            "name: no-category\ndescription: d\npyramid_layer: component\n"
            "pipeline_stage: A3\nuser_level: B2.4\n" + self._STEPS,
        )
        with pytest.raises(ValueError, match="no-category\\.yaml.*'category'"):
            load_scenarios(sd)

    def test_valid_metadata_loads(self, tmp_path: Path) -> None:
        sd = self._write(
            tmp_path,
            "good",
            "name: good\ndescription: d\ncategory: failure\n"
            "pyramid_layer: red_team\n"
            "pipeline_stage: A4\nuser_level: B2.4\n" + self._STEPS,
        )
        scs = load_scenarios(sd)
        assert len(scs) == 1
        assert scs[0]["category"] == "failure"
        assert scs[0]["pyramid_layer"] == "red_team"

    def test_all_on_disk_scenarios_carry_valid_category_and_layer(self) -> None:
        scs = load_scenarios()
        assert scs, "load_scenarios() returned no scenarios"
        for sc in scs:
            assert sc["category"] in SCENARIO_CATEGORIES, (
                f"scenario {sc['name']!r}: invalid category {sc.get('category')!r}"
            )
            assert sc["pyramid_layer"] in PYRAMID_LAYERS, (
                f"scenario {sc['name']!r}: invalid pyramid_layer {sc.get('pyramid_layer')!r}"
            )

    def test_list_scenarios_surfaces_category_and_layer(self) -> None:
        result = list_scenarios()
        assert result["count"] == len(result["scenarios"])
        assert result["count"] > 0
        for sc in result["scenarios"]:
            assert sc["category"] in SCENARIO_CATEGORIES, (
                f"list_scenarios item {sc['name']!r} missing/invalid category"
            )
            assert sc["pyramid_layer"] in PYRAMID_LAYERS, (
                f"list_scenarios item {sc['name']!r} missing/invalid pyramid_layer"
            )


class TestLoaderInvariants:
    """Todo 13 (TR-S-04/05/06): loader rejects ambiguous/unsafe scenario sets.

    - duplicate ``name`` (would silently shadow the later file),
    - ``regression: true`` without ``regression_issue`` (link unenforceable),
    - both ``min_passing`` and ``pass_ratio`` (contradictory partial policy).
    ``list_scenarios`` surfaces ``regression_issue`` so the bug→scenario link
    is auditable.
    """

    _META = "category: happy_path\npyramid_layer: component\npipeline_stage: A7\nuser_level: B2.5\n"

    def _write(self, tmp_path: Path, filenames_to_bodies: dict[str, str]) -> Path:
        sd = tmp_path / "scenarios"
        sd.mkdir(parents=True, exist_ok=True)
        for filename, body in filenames_to_bodies.items():
            (sd / filename).write_text(body, encoding="utf-8")
        return sd

    def test_duplicate_scenario_name_fails_to_load(self, tmp_path: Path) -> None:
        """Two files declaring the same ``name`` must fail to load (TR-S-04)."""
        first = (
            "name: same-name\ndescription: d\n"
            + self._META
            + "steps:\n  - name: s\n    tool: health_check\n"
        )
        second = (
            "name: same-name\ndescription: d\n"
            + self._META
            + "steps:\n  - name: s\n    tool: health_check\n"
        )
        sd = self._write(tmp_path, {"a.yaml": first, "b.yaml": second})
        with pytest.raises(ValueError, match="duplicate scenario name.*same-name"):
            load_scenarios(sd)

    def test_regression_without_issue_fails_to_load(self, tmp_path: Path) -> None:
        """``regression: true`` without ``regression_issue`` fails (TR-S-05)."""
        body = (
            "name: reg-no-issue\ndescription: d\n" + self._META + "regression: true\n"
            "steps:\n  - name: s\n    tool: health_check\n"
        )
        sd = self._write(tmp_path, {"reg.yaml": body})
        with pytest.raises(ValueError, match="reg\\.yaml.*regression.*requires.*regression_issue"):
            load_scenarios(sd)

    def test_min_passing_and_pass_ratio_are_exclusive(self, tmp_path: Path) -> None:
        """A scenario cannot set both partial-pass policies."""
        body = (
            "name: both-policies\ndescription: d\n" + self._META + "min_passing: 2\n"
            "pass_ratio: 0.5\n"
            "steps:\n  - name: s\n    tool: health_check\n"
        )
        sd = self._write(tmp_path, {"both.yaml": body})
        with pytest.raises(ValueError, match="both\\.yaml.*mutually exclusive"):
            load_scenarios(sd)

    def test_valid_regression_and_functional_load_and_are_surfaced(self, tmp_path: Path) -> None:
        """A valid regression scenario loads; ``list_scenarios`` surfaces the
        issue ID for regression and ``None`` for functional scenarios."""
        reg = (
            "name: valid-reg\ndescription: d\n" + self._META + "regression: true\n"
            'regression_issue: "#4242"\n'
            "steps:\n  - name: s\n    tool: health_check\n"
        )
        func = (
            "name: valid-func\ndescription: d\n"
            + self._META
            + "steps:\n  - name: s\n    tool: health_check\n"
        )
        sd = self._write(tmp_path, {"reg.yaml": reg, "func.yaml": func})
        scs = load_scenarios(sd)
        assert len(scs) == 2

        result = list_scenarios(sd)
        by_name = {sc["name"]: sc for sc in result["scenarios"]}
        assert by_name["valid-reg"]["regression"] is True
        assert by_name["valid-reg"]["regression_issue"] == "#4242"
        assert by_name["valid-func"]["regression"] is False
        assert by_name["valid-func"]["regression_issue"] is None


class TestUniversalTimeoutCancellation:
    """A timed-out step must actually stop its worker, for every step kind.

    ``asyncio.wait_for`` cancels the coroutine, but it cannot cancel work
    offloaded through ``asyncio.to_thread`` — the worker thread (and the
    subprocess / HTTP request it owns) keeps running after the step's budget
    expired.  These tests assert the resource is released on timeout:

    - ``kind: cli``  — the spawned process group is gone (no orphan);
    - ``kind: http`` — the in-flight request is aborted (no dribbling reader);
    - ``kind: mcp``  — the coroutine dispatch receives ``CancelledError``.
    """

    CLI_ORPHAN_SLEEP = 31337
    CLI_LONG_INNER_SLEEP = 31338

    @staticmethod
    def _write(tmp_path: Path, name: str, yaml_text: str) -> Path:
        sd = tmp_path / "scenarios"
        sd.mkdir(exist_ok=True)
        (sd / f"{name}.yaml").write_text(yaml_text, encoding="utf-8")
        return sd

    @staticmethod
    def _pgrep(pattern: str) -> str:
        """Return matching PIDs (``pgrep -f``); raise if pgrep is unavailable.

        ``pgrep`` exits 1 when there is no match (expected) and 0 when it
        matched.  Any other status means the probe itself failed — raising
        keeps a broken probe from being mistaken for "no orphan".
        """
        proc = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True)
        if proc.returncode not in (0, 1):
            raise RuntimeError(f"pgrep probe failed (rc={proc.returncode}): {proc.stderr!r}")
        return proc.stdout.strip()

    async def _wait_until_no_process(self, pattern: str, budget: float) -> str:
        """Poll ``pgrep`` until *pattern* disappears; return the last match."""
        deadline = time.monotonic() + budget
        remaining = self._pgrep(pattern)
        while remaining and time.monotonic() < deadline:
            await asyncio.sleep(0.05)
            remaining = self._pgrep(pattern)
        return remaining

    @staticmethod
    def _http_step_yaml(name: str, url: str, timeout: float) -> str:
        return (
            f"name: {name}\n"
            f"description: {name}\n"
            "category: happy_path\n"
            "requires_env: []\n"
            "pyramid_layer: component\n"
            "pipeline_stage: A7\n"
            "user_level: B2.5\n"
            "steps:\n"
            "  - name: probe\n"
            "    kind: http\n"
            "    method: GET\n"
            f'    url: "{url}"\n'
            f"    timeout_seconds: {timeout}\n"
            "    expect:\n"
            "      success: true\n"
        )

    @staticmethod
    def _cli_step_yaml(name: str, command: str, timeout: float) -> str:
        return (
            f"name: {name}\n"
            f"description: {name}\n"
            "category: happy_path\n"
            "requires_env: []\n"
            "pyramid_layer: component\n"
            "pipeline_stage: A7\n"
            "user_level: B2.5\n"
            "steps:\n"
            "  - name: probe\n"
            "    kind: cli\n"
            f'    command: "{command}"\n'
            f"    timeout_seconds: {timeout}\n"
            "    expect:\n"
            "      success: true\n"
        )

    async def test_http_slow_drip_request_aborted_on_timeout(self, tmp_path: Path) -> None:
        """A dribbling response evades httpx's per-read timeout; the harness
        must abort the request itself when the step budget expires.
        """
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        state = {"active": 0, "aborted": 0, "finished": 0}
        lock = threading.Lock()

        class DripHandler(BaseHTTPRequestHandler):
            def log_message(self, *args: Any) -> None:  # noqa: ANN002
                pass

            def do_GET(self) -> None:  # noqa: N802
                with lock:
                    state["active"] += 1
                try:
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain")
                    self.send_header("Content-Length", "200")
                    self.end_headers()
                    # One byte every 0.2s — below httpx's read timeout, so the
                    # request never self-times-out; only explicit cancellation
                    # can stop it.
                    for _ in range(100):
                        self.wfile.write(b"x")
                        self.wfile.flush()
                        time.sleep(0.2)
                    with lock:
                        state["finished"] += 1
                except (BrokenPipeError, ConnectionResetError):
                    with lock:
                        state["aborted"] += 1
                finally:
                    with lock:
                        state["active"] -= 1

        server = ThreadingHTTPServer(("127.0.0.1", 0), DripHandler)
        server.daemon_threads = True
        port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()
        sd = self._write(
            tmp_path,
            "http-drip",
            self._http_step_yaml("http-drip", f"http://127.0.0.1:{port}/drip", 0.5),
        )
        try:
            result = await run_scenario("http-drip", dispatch=None, scenarios_dir=sd)
            assert result["status"] == "failed"
            assert "timed out" in result["steps"][0]["detail"]

            with lock:
                remaining = state["active"]
            deadline = time.monotonic() + 3.0
            while remaining and time.monotonic() < deadline:
                await asyncio.sleep(0.05)
                with lock:
                    remaining = state["active"]
            with lock:
                assert remaining == 0, (
                    "HTTP request survived the step timeout (orphan reader still dribbling)"
                )
                assert state["aborted"] >= 1, "server never saw the aborted connection"
        finally:
            server.shutdown()
            server.server_close()

    async def test_cli_step_no_orphan_after_timeout(self, tmp_path: Path) -> None:
        """A real ``sleep`` CLI step is killed when the step budget expires."""
        sd = self._write(
            tmp_path,
            "cli-orphan",
            self._cli_step_yaml("cli-orphan", f"sleep {self.CLI_ORPHAN_SLEEP}", 0.5),
        )
        result = await run_scenario("cli-orphan", dispatch=None, scenarios_dir=sd)
        assert result["status"] == "failed"
        assert "timed out" in result["steps"][0]["detail"]

        remaining = await self._wait_until_no_process(f"sleep {self.CLI_ORPHAN_SLEEP}", 3.0)
        assert remaining == "", f"orphan CLI subprocess survived the timeout: pids={remaining!r}"

    async def test_cli_worker_cancelled_even_with_long_internal_timeout(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The harness must cancel the worker; it must not depend on the
        worker's own ``communicate(timeout=...)``.

        The root cause (R-S-04) is that ``asyncio.wait_for`` cannot cancel a
        ``to_thread`` worker.  This test invokes the real CLI runner with a
        30s internal timeout while the step budget is 0.5s: a correctly
        universal cancellation mechanism still reaps the process group,
        because the harness releases it directly on timeout.
        """
        real_cli = validation_mod._run_cli_step

        def long_inner(
            command: str, timeout: float = 180.0, cancel_token: Any = None
        ) -> dict[str, Any]:
            try:
                return real_cli(command, timeout=30.0, cancel_token=cancel_token)
            except TypeError:
                # Pre-fix signature has no cancel_token parameter.
                return real_cli(command, timeout=30.0)

        monkeypatch.setattr(validation_mod, "_run_cli_step", long_inner)
        sd = self._write(
            tmp_path,
            "cli-long-inner",
            self._cli_step_yaml("cli-long-inner", f"sleep {self.CLI_LONG_INNER_SLEEP}", 0.5),
        )
        result = await run_scenario("cli-long-inner", dispatch=None, scenarios_dir=sd)
        assert result["status"] == "failed"
        assert "timed out" in result["steps"][0]["detail"]

        remaining = await self._wait_until_no_process(f"sleep {self.CLI_LONG_INNER_SLEEP}", 3.0)
        assert remaining == "", f"harness did not cancel the CLI worker: orphan pids={remaining!r}"

    async def test_mcp_step_cancelled_on_timeout(self, tmp_path: Path) -> None:
        """The MCP coroutine dispatch receives CancelledError on timeout."""
        cancelled = {"flag": False}

        async def dispatch(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
            try:
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                cancelled["flag"] = True
                raise
            return {"success": True, "data": {}}

        yaml_text = (
            "name: mcp-cancel\n"
            "description: mcp-cancel\n"
            "category: happy_path\n"
            "requires_env: []\n"
            "pyramid_layer: component\n"
            "pipeline_stage: A7\n"
            "user_level: B2.5\n"
            "steps:\n"
            "  - name: probe\n"
            "    tool: slow_tool\n"
            "    arguments: {}\n"
            "    timeout_seconds: 0.3\n"
            "    expect:\n"
            "      success: true\n"
        )
        sd = self._write(tmp_path, "mcp-cancel", yaml_text)
        result = await run_scenario("mcp-cancel", dispatch=dispatch, scenarios_dir=sd)
        assert result["status"] == "failed"
        assert "timed out" in result["steps"][0]["detail"]
        for _ in range(10):
            if cancelled["flag"]:
                break
            await asyncio.sleep(0.01)
        assert cancelled["flag"] is True, "MCP dispatch was not cancelled"
