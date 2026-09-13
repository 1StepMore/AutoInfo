"""AX metrics instrumentation + gate tests (plan Todo 21 / M-01..M-06).

Exercises ``scripts/ax_metrics.py``: each metric is measured from a real live
artifact shape (category-pyramid ledger, ``TOOL_SELECTION_OK`` trace marker,
recover-* scenario results, the doc-inventory checker, the keyless
deterministic product-text benchmark + ``llm_meta.tokens`` traces, actionable
error envelopes), and the gate exits non-zero on a breach.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ax_metrics.py"


@pytest.fixture(scope="module")
def ax() -> Any:
    spec = importlib.util.spec_from_file_location("ax_metrics", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def _fast_doc_check(ax: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the gate tests fast: M-04's real checker shells out to pytest collect."""
    monkeypatch.setattr(ax, "_default_doc_check", lambda: (0, "check passed: ok\n"))


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _cell(
    category: str,
    layer: str,
    *,
    passed: int = 1,
    failed: int = 0,
    unconfigured: int = 0,
) -> dict[str, Any]:
    status = "failed" if failed else ("unconfigured" if unconfigured and not passed else "passed")
    return {
        "category": category,
        "pyramid_layer": layer,
        "scenarios": passed + failed + unconfigured,
        "status": status,
        "passed": passed,
        "failed": failed,
        "unconfigured": unconfigured,
        "steps_passed": passed,
        "steps_failed": failed,
        "steps_unconfigured": unconfigured,
        "steps_total": passed + failed + unconfigured,
    }


def _write_ledger(
    runs_dir: Path,
    cells: dict[str, Any],
    run_id: str = "2026-01-01_000000_000000",
) -> None:
    runs_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "runs": [
            {
                "run_id": run_id,
                "timestamp": "2026-01-01T00:00:00",
                "run_type": "suite",
                "session_id": "test",
                "cells": cells,
                "unclassified": [],
            }
        ],
    }
    (runs_dir / "category-pyramid-history.json").write_text(json.dumps(payload), encoding="utf-8")


def _write_run(runs_dir: Path, run_id: str, scenarios: list[dict[str, Any]]) -> Path:
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "scenarios.json").write_text(
        json.dumps({"run_id": run_id, "run_type": "suite", "scenarios": scenarios}),
        encoding="utf-8",
    )
    return run_dir


def _stdout_step(text: str) -> dict[str, Any]:
    return {
        "name": "step",
        "status": "passed",
        "detail": {"success": True, "data": {"stdout": text, "stderr": ""}},
    }


# ---------------------------------------------------------------------------
# Spec / shape
# ---------------------------------------------------------------------------


def test_spec_pins_six_metrics_with_plan_targets(ax: Any) -> None:
    ids = [spec[0] for spec in ax.SPEC]
    assert ids == ["M-01", "M-02", "M-03", "M-04", "M-05", "M-06"]
    thresholds = {spec[0]: (spec[4], spec[5]) for spec in ax.SPEC}
    assert thresholds["M-01"] == (">", 0.95)
    assert thresholds["M-02"] == (">", 0.98)
    assert thresholds["M-03"] == (">", 0.99)
    assert thresholds["M-04"] == ("==", 1.0)
    assert thresholds["M-05"] == ("<=", 0.10)
    assert thresholds["M-06"] == ("<", 30.0)


def test_seed_scenarios_cover_the_deterministic_metrics(ax: Any) -> None:
    names = set(ax.SEED_SCENARIOS)
    assert "agent-tool-selection" in names
    assert "error-boundary" in names
    assert {"recover-pipeline-resume", "recover-rollback"} <= names
    assert "perf-token-budget" in names


# ---------------------------------------------------------------------------
# M-01 task completion rate
# ---------------------------------------------------------------------------


def test_m01_passes_on_all_passed_suite_run(ax: Any, tmp_path: Path) -> None:
    _write_ledger(
        tmp_path,
        {
            "happy_path|component": _cell("happy_path", "component", passed=2),
            "failure|component": _cell("failure", "component", passed=1),
        },
    )
    metric = ax.measure_m01(tmp_path)
    assert metric["verdict"] == "PASS"
    assert metric["value"] == 1.0


def test_m01_fails_below_threshold(ax: Any, tmp_path: Path) -> None:
    _write_ledger(
        tmp_path,
        {
            "happy_path|component": _cell("happy_path", "component", passed=1),
            "failure|component": _cell("failure", "component", passed=0, failed=1),
        },
    )
    metric = ax.measure_m01(tmp_path)
    assert metric["verdict"] == "FAIL"
    assert metric["value"] == pytest.approx(0.5)


def test_m01_excludes_unconfigured_from_denominator(ax: Any, tmp_path: Path) -> None:
    _write_ledger(
        tmp_path,
        {
            "happy_path|component": _cell("happy_path", "component", passed=1),
            "edge_case|component": _cell("edge_case", "component", passed=0, unconfigured=3),
        },
    )
    metric = ax.measure_m01(tmp_path)
    # 1 passed / (1 passed + 0 failed) — the 3 unconfigured are reported, not failed.
    assert metric["verdict"] == "PASS"
    assert metric["value"] == 1.0
    assert "unconfigured excluded: 3" in metric["detail"]


def test_m01_unmeasured_without_attempts(ax: Any, tmp_path: Path) -> None:
    _write_ledger(
        tmp_path,
        {"edge_case|component": _cell("edge_case", "component", passed=0, unconfigured=2)},
    )
    assert ax.measure_m01(tmp_path)["verdict"] == "UNMEASURED"


def test_m01_unmeasured_without_ledger(ax: Any, tmp_path: Path) -> None:
    assert ax.measure_m01(tmp_path)["verdict"] == "UNMEASURED"


# ---------------------------------------------------------------------------
# M-02 tool-call accuracy
# ---------------------------------------------------------------------------


def test_m02_reads_the_emitted_marker(ax: Any, tmp_path: Path) -> None:
    _write_run(
        tmp_path,
        "2026-01-01_000000_000001",
        [
            {
                "scenario": "agent-tool-selection",
                "status": "passed",
                "steps": [_stdout_step("TOOL_SELECTION_OK 20/20 accuracy=1.00 threshold=0.98\n")],
            }
        ],
    )
    metric = ax.measure_m02(tmp_path)
    assert metric["verdict"] == "PASS"
    assert metric["value"] == 1.0
    assert "20/20" in metric["sample"]


def test_m02_fails_on_a_sub_threshold_marker(ax: Any, tmp_path: Path) -> None:
    _write_run(
        tmp_path,
        "2026-01-01_000000_000002",
        [
            {
                "scenario": "agent-tool-selection",
                "status": "failed",
                "steps": [_stdout_step("TOOL_SELECTION_OK 19/20 accuracy=0.95 threshold=0.98\n")],
            }
        ],
    )
    assert ax.measure_m02(tmp_path)["verdict"] == "FAIL"


def test_m02_unmeasured_without_marker(ax: Any, tmp_path: Path) -> None:
    assert ax.measure_m02(tmp_path)["verdict"] == "UNMEASURED"


# ---------------------------------------------------------------------------
# M-03 recovery success rate
# ---------------------------------------------------------------------------


def test_m03_counts_recover_scenarios_and_step_recovery(ax: Any, tmp_path: Path) -> None:
    _write_run(
        tmp_path,
        "2026-01-01_000000_000003",
        [
            {"scenario": "recover-pipeline-resume", "status": "passed", "steps": []},
            {"scenario": "recover-rollback", "status": "failed", "steps": []},
            {
                "scenario": "collect-failure-recovery",
                "status": "passed",
                "steps": [
                    {
                        "name": "r",
                        "status": "failed",
                        "recovery": {"x": 1},
                        "recovered": True,
                    }
                ],
            },
        ],
    )
    metric = ax.measure_m03(tmp_path)
    assert metric["value"] == pytest.approx(2 / 3)
    assert metric["verdict"] == "FAIL"  # 66% < 99%


def test_m03_unmeasured_without_recovery_data(ax: Any, tmp_path: Path) -> None:
    assert ax.measure_m03(tmp_path)["verdict"] == "UNMEASURED"


# ---------------------------------------------------------------------------
# M-04 documentation freshness
# ---------------------------------------------------------------------------


def test_m04_pass_and_fail_from_checker_exit(ax: Any) -> None:
    good = ax.measure_m04(lambda: (0, "check passed: ok\n"))
    assert good["verdict"] == "PASS"
    assert good["value"] == 1.0
    bad = ax.measure_m04(lambda: (1, "check FAILED (1 issue(s)):\n  - fact mismatch\n"))
    assert bad["verdict"] == "FAIL"
    assert bad["value"] == 0.0
    assert "fact mismatch" in bad["detail"]


# ---------------------------------------------------------------------------
# M-05 token efficiency
# ---------------------------------------------------------------------------


def _token_scenario(totals: list[int]) -> dict[str, Any]:
    return {
        "scenario": "llm-task",
        "status": "passed",
        "steps": [
            {"name": f"llm-{i}", "status": "passed", "llm_meta": {"tokens": {"total_tokens": t}}}
            for i, t in enumerate(totals)
        ],
    }


def _baseline(path: Path, *, deterministic: float, llm: float | None = None) -> None:
    payload: dict[str, Any] = {
        "version": 2,
        "signal": "deterministic_product_text_tokens_per_task",
        "baseline_tokens_per_task": deterministic,
    }
    if llm is not None:
        payload["llm_tokens_per_task"] = llm
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_m05_default_baseline_path_is_tracked(ax: Any) -> None:
    assert ax.DEFAULT_TOKEN_BASELINE == ROOT / "scripts" / "ax_token_baseline.json"
    assert ax.DEFAULT_TOKEN_BASELINE.exists(), "M-05 baseline must be committed, not gitignored"


def test_m05_deterministic_product_tokens_are_real_and_stable(ax: Any) -> None:
    first = ax.deterministic_product_tokens()
    second = ax.deterministic_product_tokens()
    assert first == second
    assert len(first) == len(ax._BENCH_PRODUCTS)
    assert all(count > 0 for count in first)


def test_m05_passes_within_threshold(
    ax: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ax, "deterministic_product_tokens", lambda: [300, 320])
    baseline = tmp_path / "b.json"
    _baseline(baseline, deterministic=300.0)
    metric = ax.measure_m05(tmp_path, baseline)
    assert metric["verdict"] == "PASS"
    assert metric["value"] == pytest.approx((310 - 300) / 300)


def test_m05_fails_on_benchmark_regression(
    ax: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ax, "deterministic_product_tokens", lambda: [400])
    baseline = tmp_path / "b.json"
    _baseline(baseline, deterministic=300.0)
    metric = ax.measure_m05(tmp_path, baseline)
    assert metric["value"] == pytest.approx(1 / 3)
    assert metric["verdict"] == "FAIL"


def test_m05_unmeasured_without_baseline(
    ax: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ax, "deterministic_product_tokens", lambda: [300])
    assert ax.measure_m05(tmp_path, tmp_path / "absent.json")["verdict"] == "UNMEASURED"


def test_m05_unmeasured_when_benchmark_fails(
    ax: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom() -> list[int]:
        raise RuntimeError("template missing")

    monkeypatch.setattr(ax, "deterministic_product_tokens", _boom)
    baseline = tmp_path / "b.json"
    _baseline(baseline, deterministic=300.0)
    metric = ax.measure_m05(tmp_path, baseline)
    assert metric["verdict"] == "UNMEASURED"  # never a faked pass
    assert "benchmark failed" in metric["detail"]


def test_m05_llm_channel_gated_when_pinned(
    ax: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ax, "deterministic_product_tokens", lambda: [300])
    _write_run(tmp_path, "2026-01-01_000000_000005", [_token_scenario([4000])])
    baseline = tmp_path / "b.json"
    _baseline(baseline, deterministic=300.0, llm=1000.0)
    metric = ax.measure_m05(tmp_path, baseline)
    assert metric["value"] == pytest.approx(3.0)  # (4000-1000)/1000 dominates
    assert metric["verdict"] == "FAIL"
    assert "llm_meta" in metric["detail"]


def test_m05_llm_channel_reported_not_gated_when_unpinned(
    ax: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ax, "deterministic_product_tokens", lambda: [300])
    _write_run(tmp_path, "2026-01-01_000000_000006", [_token_scenario([4000])])
    baseline = tmp_path / "b.json"
    _baseline(baseline, deterministic=300.0)  # no llm reference
    metric = ax.measure_m05(tmp_path, baseline)
    assert metric["verdict"] == "PASS"
    assert "llm_meta" in metric["detail"]


def test_m05_update_token_baseline_writes_file(
    ax: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ax, "deterministic_product_tokens", lambda: [100, 200])
    out = tmp_path / "baseline.json"
    path = ax.update_token_baseline(tmp_path, out)
    assert path == out and out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["version"] == 2
    assert data["baseline_tokens_per_task"] == pytest.approx(150.0)
    assert data["sample_tasks"] == 2
    assert data["llm_tokens_per_task"] is None


def test_m05_update_token_baseline_records_llm_channel(
    ax: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ax, "deterministic_product_tokens", lambda: [300])
    _write_run(tmp_path, "2026-01-01_000000_000007", [_token_scenario([1000, 3000])])
    out = tmp_path / "baseline.json"
    ax.update_token_baseline(tmp_path, out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["llm_tokens_per_task"] == pytest.approx(4000.0)


def test_m05_live_tracked_baseline_passes(ax: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """The committed baseline must match the live benchmark (gate stays active)."""
    monkeypatch.setattr(ax, "_default_doc_check", lambda: (0, "check passed: ok\n"))
    metric = ax.measure_m05(ROOT / "validation-runs")
    assert metric["verdict"] == "PASS"
    assert metric["value"] <= 0.10


# ---------------------------------------------------------------------------
# M-06 error recovery time
# ---------------------------------------------------------------------------


def _error_step(name: str, duration: float, *, actionable: bool) -> dict[str, Any]:
    return {
        "name": name,
        "status": "failed",
        "duration": duration,
        "detail": {
            "success": False,
            "error": {"code": "X", "message": "m", "actionable": actionable},
        },
    }


def test_m06_passes_under_thirty_seconds(ax: Any, tmp_path: Path) -> None:
    _write_run(
        tmp_path,
        "2026-01-01_000000_000009",
        [
            {
                "scenario": "error-boundary",
                "status": "passed",
                "steps": [
                    _error_step("a", 12.0, actionable=True),
                    _error_step("b", 99.0, actionable=False),
                ],
            }
        ],
    )
    metric = ax.measure_m06(tmp_path)
    assert metric["value"] == pytest.approx(12.0)
    assert metric["verdict"] == "PASS"


def test_m06_fails_at_or_above_thirty_seconds(ax: Any, tmp_path: Path) -> None:
    _write_run(
        tmp_path,
        "2026-01-01_000000_000010",
        [
            {
                "scenario": "error-boundary",
                "status": "failed",
                "steps": [_error_step("a", 30.0, actionable=True)],
            }
        ],
    )
    assert ax.measure_m06(tmp_path)["verdict"] == "FAIL"


def test_m06_unmeasured_without_actionable_errors(ax: Any, tmp_path: Path) -> None:
    _write_run(
        tmp_path,
        "2026-01-01_000000_000011",
        [{"scenario": "x", "status": "failed", "steps": [_error_step("a", 5.0, actionable=False)]}],
    )
    assert ax.measure_m06(tmp_path)["verdict"] == "UNMEASURED"


# ---------------------------------------------------------------------------
# Gate exit codes (planted breach → non-zero; restored → 0)
# ---------------------------------------------------------------------------


def test_gate_exit_nonzero_on_breach(
    ax: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_ledger(
        tmp_path,
        {
            "happy_path|component": _cell("happy_path", "component", passed=1),
            "failure|component": _cell("failure", "component", passed=0, failed=1),
        },
    )
    rc = ax.main(["--runs-dir", str(tmp_path)])
    assert rc == 1
    assert "GATE FAILED" in capsys.readouterr().out


def test_gate_exit_zero_when_restored(
    ax: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_ledger(tmp_path, {"happy_path|component": _cell("happy_path", "component", passed=3)})
    rc = ax.main(["--runs-dir", str(tmp_path)])
    assert rc == 0
    assert "GATE PASSED" in capsys.readouterr().out


def test_no_gate_flag_never_fails(ax: Any, tmp_path: Path) -> None:
    _write_ledger(
        tmp_path,
        {"failure|component": _cell("failure", "component", passed=0, failed=2)},
    )
    assert ax.main(["--runs-dir", str(tmp_path), "--no-gate"]) == 0


def test_json_report_shape(ax: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write_ledger(tmp_path, {"happy_path|component": _cell("happy_path", "component", passed=1)})
    assert ax.main(["--runs-dir", str(tmp_path), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert [m["id"] for m in payload["metrics"]] == ["M-01", "M-02", "M-03", "M-04", "M-05", "M-06"]
