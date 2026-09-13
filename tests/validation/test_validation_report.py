"""Tests for scripts/validation_report.py report generation (issue #139).

Covers:
- ``generate`` renders the root-cause ``## Blockers`` section — every failing
  step of every failed scenario listed as ``<scenario> step <index> <name>
  (<tool>) — <detail>`` with ``llm_reason`` / ``llm_meta`` appended when
  present — and the ``## Per-step trace`` appendix with the full trace table
  (scenario | step_index | name | tool | status | duration | trace_id).
- The verdict table, executive summary, and appendix pointer sections stay
  intact.

The script's ``RUNS`` / ``REPORTS`` module globals are monkeypatched to
``tmp_path`` so the tests never touch the real ``validation-runs/`` tree.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]

# Load the real scripts/validation_report.py (same pattern as the sibling
# test_validation_delivery.py) so the tests exercise the script's own code.
_SPEC = importlib.util.spec_from_file_location(
    "validation_report", ROOT / "scripts" / "validation_report.py"
)
assert _SPEC is not None and _SPEC.loader is not None
vr = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(vr)


def _step(
    name: str,
    tool: str,
    status: str,
    detail: Any,
    step_index: int,
    trace_id: str,
    duration: float,
    **extra: Any,
) -> dict[str, Any]:
    """Build a scenario step result dict shaped like run_scenario's output."""
    step: dict[str, Any] = {
        "name": name,
        "tool": tool,
        "status": status,
        "detail": detail,
        "step_index": step_index,
        "duration": duration,
        "arguments": {},
        "trace_id": trace_id,
    }
    step.update(extra)
    return step


@pytest.fixture
def runs_dir(tmp_path: Path) -> Path:
    """A tmp validation-runs tree with one scenarios.json fixture run."""
    run_dir = tmp_path / "validation-runs" / "2026-08-06_120000_000001"
    run_dir.mkdir(parents=True)
    trace_id = "11111111-2222-4333-8444-555555555555"
    scenarios: list[dict[str, Any]] = [
        {
            "scenario": "alpha-pass",
            "description": "Passing scenario",
            "category": "general",
            "status": "passed",
            "summary": {"passed": 1, "failed": 0, "unconfigured": 0, "recovered": 0, "total": 1},
            "trace_id": trace_id,
            "steps": [
                _step(
                    "collect data",
                    "test_source",
                    "passed",
                    {"success": True, "data": {"ok": True}},
                    1,
                    trace_id,
                    0.123,
                ),
            ],
        },
        {
            "scenario": "beta-fail",
            "description": "Failing scenario",
            "category": "general",
            "status": "failed",
            "summary": {"passed": 0, "failed": 2, "unconfigured": 0, "recovered": 0, "total": 2},
            "trace_id": trace_id,
            "steps": [
                _step(
                    "llm verify",
                    "classify_cefr",
                    "failed",
                    "llm_assert FAILED: level mismatch. Tool output: ...",
                    1,
                    trace_id,
                    1.234,
                    llm_reason="level mismatch",
                    llm_meta={
                        "model": "deepseek/deepseek-chat",
                        "tokens": {"prompt_tokens": 10, "total_tokens": 25},
                        "duration": 0.5,
                    },
                ),
                _step(
                    "long detail step", "collect_sources", "failed", "x" * 500, 2, trace_id, 0.456
                ),
            ],
        },
        {
            "scenario": "gamma-gated",
            "description": "Env-gated scenario",
            "category": "general",
            "status": "unconfigured",
            "summary": {"passed": 0, "failed": 0, "unconfigured": 1, "recovered": 0, "total": 1},
            "trace_id": trace_id,
            "steps": [
                _step(
                    "gated step",
                    "health_check",
                    "unconfigured",
                    "missing required env var(s): X",
                    1,
                    trace_id,
                    0.0,
                ),
            ],
        },
    ]
    payload = {
        "run_id": run_dir.name,
        "timestamp": "2026-08-06T12:00:00",
        "scenarios": scenarios,
    }
    (run_dir / "scenarios.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return tmp_path


@pytest.fixture
def report(runs_dir: Path, monkeypatch) -> Path:
    """Generate the report against the tmp fixture and return its path."""
    monkeypatch.setattr(vr, "RUNS", runs_dir / "validation-runs")
    monkeypatch.setattr(vr, "REPORTS", runs_dir / "reports")
    return vr.generate(version="1.0", run_id="2026-08-06_120000_000001")


class TestValidationReport:
    """Report generation against a tmp scenarios.json fixture."""

    def test_report_written_to_tmp_reports(self, report: Path) -> None:
        """The report lands under the monkeypatched REPORTS dir."""
        assert report.exists()
        assert report.parent.name == "reports"
        assert report.name.startswith("launch-validation-1.0-")

    def test_verdict_table_and_executive_summary_kept(self, report: Path) -> None:
        """The verdict table, executive summary, and appendix pointer remain."""
        text = report.read_text(encoding="utf-8")
        assert "## Verdicts" in text
        assert "| Scenario | Status | Passed/Total |" in text
        assert "| alpha-pass | passed | 1/1 |" in text
        assert "| beta-fail | failed | 0/2 |" in text
        assert "## Executive summary" in text
        assert "1 scenario(s) failed and 1 were unconfigured; 1 passed." in text
        assert "## Appendix pointer" in text
        assert "Generated by" in text

    def test_blockers_lists_failing_steps_by_name_and_tool(self, report: Path) -> None:
        """Failed steps appear as `<scenario> step <i> <name> (<tool>) — detail`."""
        text = report.read_text(encoding="utf-8")
        assert "## Blockers" in text
        # Only the failed scenario contributes blocker lines.
        assert "`beta-fail` step 1 llm verify (classify_cefr)" in text
        assert "`beta-fail` step 2 long detail step (collect_sources)" in text
        # Passing / unconfigured scenarios are not listed.
        assert "alpha-pass` step" not in text
        assert "gamma-gated` step" not in text

    def test_blockers_appends_llm_reason_and_llm_meta(self, report: Path) -> None:
        """llm_reason / llm_meta are appended when present on the step."""
        text = report.read_text(encoding="utf-8")
        assert "llm_reason: level mismatch" in text
        assert 'llm_meta: {"model": "deepseek/deepseek-chat"' in text
        assert '"prompt_tokens": 10' in text

    def test_blockers_truncates_long_details(self, report: Path) -> None:
        """Details longer than ~200 chars are truncated."""
        text = report.read_text(encoding="utf-8")
        blockers = text.split("## Blockers", 1)[1].split("## Per-step trace", 1)[0]
        line = [ln for ln in blockers.splitlines() if "long detail step" in ln][0]
        assert "…" in line
        # ~200-char detail + the ~80-char prefix/suffix renders < 320 total.
        assert len(line) < 320

    def test_per_step_trace_appendix(self, report: Path) -> None:
        """The per-step trace table exposes the new trace fields per scenario."""
        text = report.read_text(encoding="utf-8")
        assert "## Per-step trace" in text
        assert "| Scenario | Step | Name | Tool | Status | Duration (s) | Trace ID |" in text
        # Every scenario's steps appear with step_index, duration, trace_id.
        assert "| alpha-pass | 1 | collect data | test_source | passed | 0.123 |" in text
        assert "| beta-fail | 1 | llm verify | classify_cefr | failed | 1.234 |" in text
        assert "| beta-fail | 2 | long detail step | collect_sources | failed | 0.456 |" in text
        assert "| gamma-gated | 1 | gated step | health_check | unconfigured | 0.000 |" in text
        assert "11111111-2222-4333-8444-555555555555" in text

    def test_report_contains_scenario_and_run_ids(self, report: Path) -> None:
        """Header lines carry the version, run id, and status counts."""
        text = report.read_text(encoding="utf-8")
        assert "# Launch Validation Run Report 1.0 (2026-08-06_120000_000001)" in text
        assert "(passed=1, failed=1, unconfigured=1)" in text

    def test_no_failed_scenarios_renders_placeholder(self, tmp_path: Path, monkeypatch) -> None:
        """An all-pass run renders a placeholder line instead of an empty list."""
        run_dir = tmp_path / "runs" / "r1"
        run_dir.mkdir(parents=True)
        (run_dir / "scenarios.json").write_text(
            json.dumps(
                {
                    "run_id": "r1",
                    "scenarios": [
                        {
                            "scenario": "ok",
                            "description": "d",
                            "category": "general",
                            "status": "passed",
                            "summary": {
                                "passed": 1,
                                "failed": 0,
                                "unconfigured": 0,
                                "recovered": 0,
                                "total": 1,
                            },
                            "trace_id": "t",
                            "steps": [
                                {
                                    "name": "s",
                                    "tool": "t1",
                                    "status": "passed",
                                    "detail": "d",
                                    "step_index": 1,
                                    "duration": 0.1,
                                    "arguments": {},
                                    "trace_id": "t",
                                }
                            ],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(vr, "RUNS", tmp_path / "runs")
        monkeypatch.setattr(vr, "REPORTS", tmp_path / "reports")
        out = vr.generate(version="1.0", run_id="r1")
        text = out.read_text(encoding="utf-8")
        blockers = text.split("## Blockers", 1)[1].split("## Per-step trace", 1)[0]
        assert "(no failing scenarios in this run)" in blockers


class TestAggregateRunReportConsumption:
    """R-S-05: the report renders the whole suite from ONE aggregate run.

    ``run_all_scenarios`` persists a single ``run_type="suite"`` run; the
    report consumes its ``scenarios[]`` array with no external aggregation
    scripting and renders every scenario row.
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
    tool: ok_tool
    arguments: {{}}
    expect:
      success: true
"""

    async def test_report_renders_all_scenarios_from_one_aggregate_run(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from autoinfo.mcp.validation import run_all_scenarios

        sd = tmp_path / "scenarios"
        sd.mkdir()
        names = ["scenario-a", "scenario-b", "scenario-c"]
        for name in names:
            (sd / f"{name}.yaml").write_text(self.SCENARIO_TMPL.format(name=name), encoding="utf-8")

        async def dispatch(tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
            return {"success": True, "data": {"result": "ok"}}

        runs_dir = tmp_path / "runs"
        result = await run_all_scenarios(dispatch, scenarios_dir=sd, runs_dir=runs_dir, save=True)

        monkeypatch.setattr(vr, "RUNS", runs_dir)
        monkeypatch.setattr(vr, "REPORTS", tmp_path / "reports")
        run_id = (runs_dir / "latest.txt").read_text().strip()
        assert run_id == Path(result["saved_run"]).name
        out = vr.generate(version="suite", run_id=run_id)
        text = out.read_text(encoding="utf-8")

        assert "Type: suite" in text
        assert "Scenarios: 3" in text
        for name in names:
            assert f"| {name} | passed | 1/1 |" in text


def _ident_step(
    name: str,
    tool: str,
    status: str,
    detail: Any,
    step_id: str,
    trace_id: str,
    **extra: Any,
) -> dict[str, Any]:
    """Build a step carrying the run-unique ``step_id`` + ``step_index``."""
    step: dict[str, Any] = {
        "name": name,
        "tool": tool,
        "status": status,
        "detail": detail,
        "step_id": step_id,
        "step_index": step_id,
        "duration": 0.1,
        "arguments": {},
        "trace_id": trace_id,
    }
    step.update(extra)
    return step


@pytest.fixture
def causal_runs_dir(tmp_path: Path) -> Path:
    """A run whose failures span every cause class plus repeated signatures."""
    run_dir = tmp_path / "validation-runs" / "2026-08-07_causal_001"
    run_dir.mkdir(parents=True)
    tid = "causal-trace"
    envelope_ok_dup = (
        "expected success=True, got success=False: {'error': {'code': 'DOMAIN_NOT_FOUND'}}"
    )
    scenarios: list[dict[str, Any]] = [
        {
            "scenario": "causal-fail",
            "description": "mixed causes",
            "category": "failure",
            "status": "failed",
            "summary": {"passed": 0, "failed": 4, "unconfigured": 1, "recovered": 0, "total": 5},
            "trace_id": tid,
            "steps": [
                _ident_step(
                    "env gated",
                    "collect_sources",
                    "unconfigured",
                    "missing required env var(s): REDDIT_KEY",
                    "1",
                    tid,
                ),
                _ident_step(
                    "judge parse",
                    "classify_cefr",
                    "failed",
                    "llm_assert error: LLM judge returned non-JSON: '??'",
                    "2",
                    tid,
                ),
                _ident_step(
                    "slow build", "generate_report", "failed", "timed out after 180s", "3", tid
                ),
                _ident_step(
                    "assert mismatch",
                    "search_knowledge_base",
                    "failed",
                    "data_has keys missing: ['results']. Available keys: []",
                    "4",
                    tid,
                ),
                _ident_step(
                    "envelope err",
                    "add_source",
                    "failed",
                    envelope_ok_dup,
                    "5",
                    tid,
                    recovery=[
                        _ident_step(
                            "envelope retry",
                            "add_source",
                            "failed",
                            envelope_ok_dup,
                            "5.recovery.1",
                            tid,
                        ),
                    ],
                ),
            ],
        },
        {
            "scenario": "causal-fail-2",
            "description": "repeats two signatures",
            "category": "failure",
            "status": "failed",
            "summary": {"passed": 0, "failed": 2, "unconfigured": 0, "recovered": 0, "total": 2},
            "trace_id": tid,
            "steps": [
                _ident_step(
                    "envelope err again", "add_source", "failed", envelope_ok_dup, "1", tid
                ),
                _ident_step(
                    "slow build again",
                    "generate_report",
                    "failed",
                    "timed out after 180s",
                    "2",
                    tid,
                ),
            ],
        },
    ]
    (run_dir / "scenarios.json").write_text(
        json.dumps({"run_id": run_dir.name, "scenarios": scenarios}, indent=2),
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def causal_report(causal_runs_dir: Path, monkeypatch) -> Path:
    monkeypatch.setattr(vr, "RUNS", causal_runs_dir / "validation-runs")
    monkeypatch.setattr(vr, "REPORTS", causal_runs_dir / "reports")
    return vr.generate(version="causal", run_id="2026-08-07_causal_001")


class TestCausalReport:
    """TR-S-02: the blocker list becomes a classified causal report."""

    def test_cause_classification_table(self, causal_report: Path) -> None:
        text = causal_report.read_text(encoding="utf-8")
        assert "### Cause classification" in text
        assert "| unconfigured-env | 1 | 1 |" in text
        assert "| timeout | 2 | 1 |" in text
        assert "| error-envelope | 3 | 1 |" in text
        assert "| llm-parse | 1 | 1 |" in text
        assert "| assertion-failed | 1 | 1 |" in text

    def test_first_cause_candidate_is_most_upstream(self, causal_report: Path) -> None:
        text = causal_report.read_text(encoding="utf-8")
        block = text.split("### First-cause candidate", 1)[1].split("### Failure groups", 1)[0]
        assert "`causal-fail` step 1 env gated (collect_sources)" in block
        assert "`unconfigured-env`" in block

    def test_repeated_failures_deduplicated(self, causal_report: Path) -> None:
        text = causal_report.read_text(encoding="utf-8")
        block = text.split("### Failure groups (deduplicated)", 1)[1].split("### Failing steps", 1)[
            0
        ]
        assert "`[timeout]` ×2" in block
        assert "`[error-envelope]` ×3" in block

    def test_each_failure_attributed_to_a_cause(self, causal_report: Path) -> None:
        text = causal_report.read_text(encoding="utf-8")
        assert "[unconfigured-env]" in text
        assert "[timeout]" in text
        assert "[error-envelope]" in text
        assert "[llm-parse]" in text
        assert "[assertion-failed]" in text

    def test_per_step_trace_uses_unique_step_id(self, causal_report: Path) -> None:
        text = causal_report.read_text(encoding="utf-8")
        trace = text.split("## Per-step trace", 1)[1].split("## Appendix pointer", 1)[0]
        assert "| causal-fail | 5.recovery.1 | envelope retry |" in trace
        assert "| causal-fail | 1 | env gated |" in trace


class TestCategoryPyramidHistorySection:
    """TR-B-01/TR-B-02: the report surfaces per-cell pass history and N-run
    rates with the hard 5/5 / soft 4/5 gate, and never fakes an unmeasured
    pass.
    """

    RUN_ID = "2026-09-13_000002_000002"

    @staticmethod
    def _scenario(status: str) -> dict[str, Any]:
        return {
            "scenario": "alpha",
            "category": "happy_path",
            "pyramid_layer": "component",
            "status": status,
            "summary": {
                "passed": 1 if status == "passed" else 0,
                "failed": 1 if status == "failed" else 0,
                "unconfigured": 1 if status == "unconfigured" else 0,
                "recovered": 0,
                "total": 1,
            },
        }

    def _write_run(self, runs: Path, run_id: str, status: str) -> None:
        run_dir = runs / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "scenarios.json").write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "timestamp": "2026-09-13T00:00:00",
                    "run_type": "suite",
                    "scenarios": [self._scenario(status)],
                }
            ),
            encoding="utf-8",
        )

    def test_section_renders_history_and_nrun_rates(self, tmp_path: Path, monkeypatch) -> None:
        from autoinfo.mcp.validation import record_category_pyramid_history

        runs = tmp_path / "validation-runs"
        for i, status in enumerate(["passed", "passed"], start=1):
            run_id = f"2026-09-13_00000{i}_00000{i}"
            record_category_pyramid_history([self._scenario(status)], run_id=run_id, runs_dir=runs)
        self._write_run(runs, self.RUN_ID, "passed")

        monkeypatch.setattr(vr, "RUNS", runs)
        monkeypatch.setattr(vr, "REPORTS", tmp_path / "reports")
        text = vr.generate(version="suite", run_id=self.RUN_ID).read_text(encoding="utf-8")
        assert "## Category × pyramid pass history" in text
        assert "Suite runs recorded: 2" in text
        assert "| happy_path | component | 2 | 2 | 100% | PASS | PASS | P P |" in text
        assert "Cells failing hard rule: 0; cells failing soft rule: 0." in text
        # The unmeasured grid cells render "-", never a faked PASS.
        assert "| performance | red_team | 0 | 0 | - | - | - | - |" in text

    def test_soft_only_rate_renders_hard_fail_soft_pass(self, tmp_path: Path, monkeypatch) -> None:
        from autoinfo.mcp.validation import record_category_pyramid_history

        runs = tmp_path / "validation-runs"
        for i, status in enumerate(["passed", "passed", "passed", "passed", "failed"], start=1):
            record_category_pyramid_history(
                [self._scenario(status)],
                run_id=f"2026-09-14_00000{i}_00000{i}",
                runs_dir=runs,
            )
        self._write_run(runs, self.RUN_ID, "failed")

        monkeypatch.setattr(vr, "RUNS", runs)
        monkeypatch.setattr(vr, "REPORTS", tmp_path / "reports")
        text = vr.generate(version="suite", run_id=self.RUN_ID).read_text(encoding="utf-8")
        assert "| happy_path | component | 5 | 4 | 80% | FAIL | PASS | P P P P F |" in text
        assert "Cells failing hard rule: 1; cells failing soft rule: 0." in text

    def test_no_history_renders_placeholder(self, tmp_path: Path, monkeypatch) -> None:
        runs = tmp_path / "validation-runs"
        self._write_run(runs, self.RUN_ID, "passed")
        monkeypatch.setattr(vr, "RUNS", runs)
        monkeypatch.setattr(vr, "REPORTS", tmp_path / "reports")
        text = vr.generate(version="suite", run_id=self.RUN_ID).read_text(encoding="utf-8")
        assert "## Category × pyramid pass history" in text
        assert "(no suite-run history recorded yet" in text
