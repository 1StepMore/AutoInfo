"""Tests for the deterministic acceptance-report generator (scripts/acceptance_report.py).

Locks three things:

1. **The anti-fabrication guard.** The three human-reserved rows
   (``AC3-human``, ``AC5-director``, ``overall``) are structurally incapable of
   carrying a machine ``PASS``: ``_machine_row`` refuses any human-reserved
   ``dim_id``, ``_human_rows`` is the only producer of reserved rows, and
   ``render_report`` asserts the overall verdict is the reserved token. A
   fixture where every mechanical input *pleads* PASS still yields
   ``PENDING HUMAN`` / ``PENDING HUMAN`` / ``PENDING DIRECTOR SIGN-OFF``.

2. **The per-dimension decision rules (AC1-AC9).** Each row is derived from a
   real artifact shape (scenarios.json, coverage json, delivery manifest,
   coverage-gaps.json, pytest rc/collect count, doc_inventory rc, cost
   dashboard) — never hardcoded — and every mechanical row must carry an
   evidence pointer naming its artifact and decisive value.

3. **The §10 report skeleton.** Per-dimension verdict table with the five
   columns, executive summary, blockers, the four-concern director table, the
   unsigned Director/Date/Verdict block, and the Chinese summary section.

No LLM, no network: the loaders/helpers are pure or read ``tmp_path`` fixtures;
``run_pytest`` is exercised against a one-line throwaway test file.
"""

from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path
from typing import Any

import pytest

# scripts/ is not a package — load it via sys.path like the sibling test files.
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

import acceptance_report as ar  # noqa: E402  (sys.path insert above)

# ---------------------------------------------------------------------------
# Fixtures / builders
# ---------------------------------------------------------------------------


def _all_pass_inputs(**overrides: Any) -> ar.AcceptanceInputs:
    """An ``AcceptanceInputs`` where every mechanical input pleads PASS.

    The human-reserved rows must still come out non-PASS regardless (that is
    the whole point of the guard).
    """
    scenarios = {
        "_path": "validation-runs/2026-09-30_test/scenarios.json",
        "run_id": "2026-09-30_test",
        "scenarios": [
            {"scenario": "enduser-journey", "status": "passed"},
            {
                "scenario": "regression-b1-content-preference",
                "status": "passed",
                "regression": True,
            },
            {"scenario": "error-boundary", "status": "passed"},
            {"scenario": "promotion-provenance", "status": "passed"},
        ],
    }
    manifest = {
        "files": [
            {"file": "01-RAW/x.json", "kind": "RAW", "quality": "PASS", "gates": {}},
            {
                "file": "02-PROCESSED/digest.md",
                "kind": "PROCESSED",
                "quality": "PASS",
                "gates": {"authenticity": {"authenticity": "pass", "reason": "ok"}},
            },
        ],
        "rejected": [],
    }
    delivery = {
        "dir": "validation-deliveries/2026-09-30",
        "manifest": manifest,
        "manifest_path": "validation-deliveries/2026-09-30/manifest.json",
        "coverage_gaps": {
            "summary": {
                "required": 10,
                "produced": 10,
                "gap": 0,
                "unconfigured": 0,
                "not_applicable": 0,
            }
        },
        "gaps_path": "validation-deliveries/2026-09-30/04-MATRIX/coverage-gaps.json",
        "gate_reports": {"reports": []},
        "gate_index_path": "validation-deliveries/2026-09-30/01-QA-GATES/gate-reports-index.json",
    }
    base: dict[str, Any] = {
        "run_id": "2026-09-30_test",
        "scenarios": scenarios,
        "coverage": {
            "_path": "validation-runs/coverage/coverage-2026-09-30_045218.json",
            "missing_tools": [],
        },
        "delivery": delivery,
        "pytest_kb_rc": 0,
        "pytest_collected": 5766,
        "bug_test_count": 0,
        "doc_inventory_rc": 0,
        "cost_dashboard": {"summary": {"total_cost": 0.0}},
        "pr_range": "origin/main..HEAD",
        "commit_violations": (),
    }
    base.update(overrides)
    return ar.AcceptanceInputs(**base)


def _by_id(rows: list[ar.DimensionRow]) -> dict[str, ar.DimensionRow]:
    return {r.dim_id: r for r in rows}


def _delivery_with(processed: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    manifest = {"files": [{"file": "01-RAW/x.json", "kind": "RAW", "quality": "PASS"}] + processed}
    return {
        "dir": "validation-deliveries/2026-09-30",
        "manifest": manifest,
        "manifest_path": "validation-deliveries/2026-09-30/manifest.json",
        "coverage_gaps": {"summary": {"gap": 0, "unconfigured": 0}},
        "gaps_path": "validation-deliveries/2026-09-30/04-MATRIX/coverage-gaps.json",
        "gate_reports": None,
        **extra,
    }


# ---------------------------------------------------------------------------
# Anti-fabrication guard
# ---------------------------------------------------------------------------


def test_machine_row_rejects_human_reserved_dim() -> None:
    for dim_id in sorted(ar.HUMAN_RESERVED):
        with pytest.raises(AssertionError):
            ar._machine_row(dim_id, "PASS", evidence="x")


def test_machine_row_rejects_unknown_verdict() -> None:
    for bogus in ("PARTIAL", "N/A", "pass", "SKIP"):
        with pytest.raises(AssertionError):
            ar._machine_row("AC1", bogus, evidence="x")


def test_machine_row_requires_evidence_pointer() -> None:
    with pytest.raises(AssertionError):
        ar._machine_row("AC1", "PASS", evidence="")


def test_verdict_vocabulary_is_fixed() -> None:
    # acceptance-framework.md §7.3 — exactly four verdicts, no inventions.
    assert ar.MACHINE_VERDICTS == frozenset({"PASS", "FAIL", "RISK", "unconfigured"})
    assert ar.HUMAN_RESERVED == frozenset({"AC3-human", "AC5-director", "overall"})
    assert ar.RESERVED_TOKEN == {
        "AC3-human": "PENDING HUMAN",
        "AC5-director": "PENDING HUMAN",
        "overall": "PENDING DIRECTOR SIGN-OFF",
    }


def test_human_rows_are_non_pass_tokens() -> None:
    rows = _by_id(ar._human_rows(5))
    assert rows["AC3-human"].verdict == "PENDING HUMAN"
    assert rows["AC5-director"].verdict == "PENDING HUMAN"
    assert rows["overall"].verdict == "PENDING DIRECTOR SIGN-OFF"
    assert "0/5" in rows["AC5-director"].notes


def test_all_mechanical_inputs_pleading_pass_still_yield_pending() -> None:
    rows = _by_id(ar.compute_dimensions(_all_pass_inputs()))
    assert rows["AC3-human"].verdict == "PENDING HUMAN"
    assert rows["AC5-director"].verdict == "PENDING HUMAN"
    assert rows["overall"].verdict == "PENDING DIRECTOR SIGN-OFF"
    # None of the reserved rows ever carries a machine verdict.
    for dim_id in ar.HUMAN_RESERVED:
        assert rows[dim_id].verdict not in ar.MACHINE_VERDICTS


def test_render_report_rejects_tampered_overall() -> None:
    rows = ar.compute_dimensions(_all_pass_inputs())
    tampered = [
        dataclasses.replace(r, verdict="PASS") if r.dim_id == "overall" else r for r in rows
    ]
    with pytest.raises(AssertionError):
        ar.render_report("1.14.1", "2026-09-30", tampered)


def test_render_report_rejects_tampered_reserved_row() -> None:
    rows = ar.compute_dimensions(_all_pass_inputs())
    tampered = [
        dataclasses.replace(r, verdict="PASS") if r.dim_id == "AC3-human" else r for r in rows
    ]
    with pytest.raises(AssertionError):
        ar.render_report("1.14.1", "2026-09-30", tampered)


def test_every_machine_row_has_evidence_pointer() -> None:
    for row in ar.compute_dimensions(_all_pass_inputs()):
        if row.dim_id in ar.HUMAN_RESERVED:
            continue
        assert row.evidence.strip(), f"{row.dim_id} has no evidence pointer"


def test_compute_dimensions_covers_all_skeleton_rows() -> None:
    rows = ar.compute_dimensions(_all_pass_inputs())
    assert [r.dim_id for r in rows] == [
        "AC1",
        "AC2",
        "AC3-agent",
        "AC3-human",
        "AC4",
        "AC5-gates",
        "AC5-director",
        "AC6",
        "AC7",
        "AC8",
        "AC9",
        "overall",
    ]


# ---------------------------------------------------------------------------
# AC1 — user model integrity
# ---------------------------------------------------------------------------


def test_ac1_all_present_passed_is_pass() -> None:
    rows = _by_id(ar.compute_dimensions(_all_pass_inputs()))
    assert rows["AC1"].verdict == "PASS"


def test_ac1_missing_scenario_is_risk() -> None:
    scenarios = _all_pass_inputs().scenarios
    scenarios = {
        **scenarios,
        "scenarios": [s for s in scenarios["scenarios"] if s["scenario"] != "error-boundary"],
    }
    rows = _by_id(ar.compute_dimensions(_all_pass_inputs(scenarios=scenarios)))
    assert rows["AC1"].verdict == "RISK"
    assert "error-boundary" in rows["AC1"].notes


def test_ac1_failed_scenario_is_fail() -> None:
    scenarios = _all_pass_inputs().scenarios
    scenarios = {
        **scenarios,
        "scenarios": [
            {**s, "status": "failed"} if s["scenario"] == "enduser-journey" else s
            for s in scenarios["scenarios"]
        ],
    }
    rows = _by_id(ar.compute_dimensions(_all_pass_inputs(scenarios=scenarios)))
    assert rows["AC1"].verdict == "FAIL"


def test_ac1_unconfigured_is_never_pass() -> None:
    scenarios = _all_pass_inputs().scenarios
    scenarios = {
        **scenarios,
        "scenarios": [
            {**s, "status": "unconfigured"} if s["scenario"] == "enduser-journey" else s
            for s in scenarios["scenarios"]
        ],
    }
    rows = _by_id(ar.compute_dimensions(_all_pass_inputs(scenarios=scenarios)))
    assert rows["AC1"].verdict == "RISK"


# ---------------------------------------------------------------------------
# AC2 — data-layer integrity
# ---------------------------------------------------------------------------


def test_ac2_pass_when_tests_kb_provenance_and_raw_present() -> None:
    rows = _by_id(ar.compute_dimensions(_all_pass_inputs()))
    assert rows["AC2"].verdict == "PASS"


def test_ac2_pytest_failure_is_fail() -> None:
    rows = _by_id(ar.compute_dimensions(_all_pass_inputs(pytest_kb_rc=1)))
    assert rows["AC2"].verdict == "FAIL"


def test_ac2_no_raw_file_is_fail() -> None:
    base = _all_pass_inputs().delivery
    delivery = {
        **base,
        "manifest": {
            "files": [
                {
                    "file": "02-PROCESSED/digest.md",
                    "kind": "PROCESSED",
                    "quality": "PASS",
                    "gates": {"authenticity": {"authenticity": "pass"}},
                }
            ]
        },
    }
    rows = _by_id(ar.compute_dimensions(_all_pass_inputs(delivery=delivery)))
    assert rows["AC2"].verdict == "FAIL"
    assert "RAW" in rows["AC2"].evidence


def test_ac2_missing_provenance_scenario_is_risk() -> None:
    scenarios = _all_pass_inputs().scenarios
    scenarios = {
        **scenarios,
        "scenarios": [s for s in scenarios["scenarios"] if s["scenario"] != "promotion-provenance"],
    }
    rows = _by_id(ar.compute_dimensions(_all_pass_inputs(scenarios=scenarios)))
    assert rows["AC2"].verdict == "RISK"


# ---------------------------------------------------------------------------
# AC3 — dual orientation (agent) + human reserved
# ---------------------------------------------------------------------------


def test_ac3_agent_pass_when_no_missing_tools() -> None:
    rows = _by_id(ar.compute_dimensions(_all_pass_inputs()))
    assert rows["AC3-agent"].verdict == "PASS"
    assert "missing_tools=[]" in rows["AC3-agent"].evidence


def test_ac3_agent_missing_tools_is_fail() -> None:
    rows = _by_id(
        ar.compute_dimensions(
            _all_pass_inputs(coverage={"_path": "coverage.json", "missing_tools": ["foo"]})
        )
    )
    assert rows["AC3-agent"].verdict == "FAIL"


def test_ac3_agent_no_coverage_is_unconfigured() -> None:
    rows = _by_id(ar.compute_dimensions(_all_pass_inputs(coverage=None)))
    assert rows["AC3-agent"].verdict == "unconfigured"


# ---------------------------------------------------------------------------
# AC4 — coverage commitment
# ---------------------------------------------------------------------------


def test_ac4_gap_zero_is_pass_and_surfaces_unconfigured() -> None:
    delivery = _delivery_with(
        [],
        coverage_gaps={"summary": {"gap": 0, "unconfigured": 3}},
    )
    rows = _by_id(ar.compute_dimensions(_all_pass_inputs(delivery=delivery)))
    assert rows["AC4"].verdict == "PASS"
    assert "unconfigured=3" in rows["AC4"].notes
    assert "never a pass" in rows["AC4"].notes


def test_ac4_gap_positive_is_fail() -> None:
    delivery = _delivery_with([], coverage_gaps={"summary": {"gap": 2, "unconfigured": 0}})
    rows = _by_id(ar.compute_dimensions(_all_pass_inputs(delivery=delivery)))
    assert rows["AC4"].verdict == "FAIL"


def test_ac4_missing_coverage_gaps_is_unconfigured() -> None:
    delivery = _delivery_with([], coverage_gaps=None, gaps_path="")
    rows = _by_id(ar.compute_dimensions(_all_pass_inputs(delivery=delivery)))
    assert rows["AC4"].verdict == "unconfigured"


# ---------------------------------------------------------------------------
# AC5 — quality automated gates + director reserved
# ---------------------------------------------------------------------------


def test_ac5_gates_pass_when_all_processed_clean() -> None:
    rows = _by_id(ar.compute_dimensions(_all_pass_inputs()))
    assert rows["AC5-gates"].verdict == "PASS"


def test_ac5_gates_fail_on_quality_fail() -> None:
    delivery = _delivery_with(
        [
            {
                "file": "02-PROCESSED/digest.md",
                "kind": "PROCESSED",
                "quality": "FAIL",
                "gates": {"authenticity": {"authenticity": "pass"}},
            }
        ]
    )
    rows = _by_id(ar.compute_dimensions(_all_pass_inputs(delivery=delivery)))
    assert rows["AC5-gates"].verdict == "FAIL"


def test_ac5_gates_fail_on_authenticity_fail() -> None:
    delivery = _delivery_with(
        [
            {
                "file": "02-PROCESSED/digest.md",
                "kind": "PROCESSED",
                "quality": "PASS",
                "gates": {"authenticity": {"authenticity": "fail", "reason": "fabricated"}},
            }
        ]
    )
    rows = _by_id(ar.compute_dimensions(_all_pass_inputs(delivery=delivery)))
    assert rows["AC5-gates"].verdict == "FAIL"


def test_ac5_gates_no_processed_is_unconfigured() -> None:
    rows = _by_id(ar.compute_dimensions(_all_pass_inputs(delivery=_delivery_with([]))))
    assert rows["AC5-gates"].verdict == "unconfigured"


def test_ac5_director_is_reserved_even_with_many_forms() -> None:
    delivery = _delivery_with(
        [
            {
                "file": f"02-PROCESSED/p{i}.md",
                "kind": "PROCESSED",
                "quality": "PASS",
                "gates": {"authenticity": {"authenticity": "pass"}},
            }
            for i in range(4)
        ]
    )
    rows = _by_id(ar.compute_dimensions(_all_pass_inputs(delivery=delivery)))
    assert rows["AC5-director"].verdict == "PENDING HUMAN"
    assert "0/4" in rows["AC5-director"].notes


# ---------------------------------------------------------------------------
# AC6 — commercial viability
# ---------------------------------------------------------------------------


def test_ac6_dashboard_present_is_pass() -> None:
    rows = _by_id(ar.compute_dimensions(_all_pass_inputs()))
    assert rows["AC6"].verdict == "PASS"


def test_ac6_no_dashboard_is_unconfigured() -> None:
    rows = _by_id(ar.compute_dimensions(_all_pass_inputs(cost_dashboard=None)))
    assert rows["AC6"].verdict == "unconfigured"


# ---------------------------------------------------------------------------
# AC7 — process & governance
# ---------------------------------------------------------------------------


def test_ac7_without_pr_range_is_unconfigured() -> None:
    rows = _by_id(ar.compute_dimensions(_all_pass_inputs(pr_range=None, commit_violations=())))
    assert rows["AC7"].verdict == "unconfigured"


def test_ac7_clean_commits_is_pass() -> None:
    rows = _by_id(ar.compute_dimensions(_all_pass_inputs()))
    assert rows["AC7"].verdict == "PASS"


def test_ac7_violating_commit_is_fail() -> None:
    rows = _by_id(
        ar.compute_dimensions(_all_pass_inputs(commit_violations=("non-Conventional: x",)))
    )
    assert rows["AC7"].verdict == "FAIL"


def test_commit_violations_accepts_conventional_with_signoff() -> None:
    commits = [("feat(mcp): add tool", "Body.\n\nSigned-off-by: Dev <dev@example.com>")]
    assert ar._commit_violations(commits) == []


def test_commit_violations_flags_bad_subject_and_missing_trailer() -> None:
    good = [("feat: ok", "Signed-off-by: Dev <dev@example.com>")]
    assert ar._commit_violations(good) == []
    bad_subject = [("WIP stuff", "Signed-off-by: Dev <dev@example.com>")]
    assert ar._commit_violations(bad_subject)
    missing_trailer = [("fix: bug", "no trailer here")]
    assert ar._commit_violations(missing_trailer)


# ---------------------------------------------------------------------------
# AC8 — documentation health
# ---------------------------------------------------------------------------


def test_ac8_rc_zero_is_pass() -> None:
    rows = _by_id(ar.compute_dimensions(_all_pass_inputs()))
    assert rows["AC8"].verdict == "PASS"


def test_ac8_rc_nonzero_is_fail() -> None:
    rows = _by_id(ar.compute_dimensions(_all_pass_inputs(doc_inventory_rc=1)))
    assert rows["AC8"].verdict == "FAIL"


def test_ac8_not_run_is_unconfigured() -> None:
    rows = _by_id(ar.compute_dimensions(_all_pass_inputs(doc_inventory_rc=None)))
    assert rows["AC8"].verdict == "unconfigured"


# ---------------------------------------------------------------------------
# AC9 — test & validation health
# ---------------------------------------------------------------------------


def test_ac9_clean_is_pass() -> None:
    rows = _by_id(ar.compute_dimensions(_all_pass_inputs()))
    assert rows["AC9"].verdict == "PASS"


def test_ac9_bug_named_test_is_fail() -> None:
    rows = _by_id(ar.compute_dimensions(_all_pass_inputs(bug_test_count=1)))
    assert rows["AC9"].verdict == "FAIL"


def test_ac9_regression_failure_is_risk() -> None:
    scenarios = _all_pass_inputs().scenarios
    scenarios = {
        **scenarios,
        "scenarios": [
            {**s, "status": "failed"} if s["scenario"] == "regression-b1-content-preference" else s
            for s in scenarios["scenarios"]
        ],
    }
    rows = _by_id(ar.compute_dimensions(_all_pass_inputs(scenarios=scenarios)))
    assert rows["AC9"].verdict == "RISK"


def test_ac9_collect_failure_is_unconfigured() -> None:
    rows = _by_id(ar.compute_dimensions(_all_pass_inputs(pytest_collected=None)))
    assert rows["AC9"].verdict == "unconfigured"


# ---------------------------------------------------------------------------
# Report rendering — §10 skeleton
# ---------------------------------------------------------------------------


def test_render_report_has_skeleton_columns_and_rows() -> None:
    text = ar.render_report("1.14.1", "2026-09-30", ar.compute_dimensions(_all_pass_inputs()))
    assert "| Dimension | Verdict | Blockers | Evidence artifacts | Notes |" in text
    for label in (
        "AC1 User model integrity",
        "AC2 Data-layer integrity",
        "AC3 Dual orientation (agent)",
        "AC3 Dual orientation (human)",
        "AC4 Coverage commitment",
        "AC5 Quality (automated gates)",
        "AC5 Quality (director review)",
        "AC6 Commercial viability",
        "AC7 Process & governance",
        "AC8 Documentation health",
        "AC9 Test & validation health",
        "**Overall verdict**",
    ):
        assert label in text, label


def test_render_report_has_executive_summary_blockers_and_chinese() -> None:
    text = ar.render_report("1.14.1", "2026-09-30", ar.compute_dimensions(_all_pass_inputs()))
    assert "## Executive summary" in text
    assert "## Blockers" in text
    assert "## 中文摘要（Director）" in text


def test_render_report_has_unsigned_director_block() -> None:
    text = ar.render_report("1.14.1", "2026-09-30", ar.compute_dimensions(_all_pass_inputs()))
    assert "| Director | _(unsigned)_ |" in text
    assert "| Date | _(unsigned)_ |" in text
    assert "| Verdict | **PENDING DIRECTOR SIGN-OFF** |" in text


def test_render_report_has_director_four_concern_table_pending() -> None:
    text = ar.render_report("1.14.1", "2026-09-30", ar.compute_dimensions(_all_pass_inputs()))
    for concern in ("Completeness / accuracy", "Depth / freshness", "Traceability / presentation"):
        assert concern in text
    assert "(pending)" in text


def test_render_report_states_unconfigured_never_pass() -> None:
    text = ar.render_report("1.14.1", "2026-09-30", ar.compute_dimensions(_all_pass_inputs()))
    assert "never a pass" in text.lower()


def test_render_report_surfaces_unconfigured_verdict_when_check_absent() -> None:
    text = ar.render_report(
        "1.14.1", "2026-09-30", ar.compute_dimensions(_all_pass_inputs(cost_dashboard=None))
    )
    assert "unconfigured" in text


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def test_load_run_scenarios_reads_payload(tmp_path: Path) -> None:
    run = tmp_path / "run1"
    run.mkdir()
    (run / "scenarios.json").write_text(
        json.dumps({"run_id": "run1", "scenarios": [{"scenario": "x", "status": "passed"}]}),
        encoding="utf-8",
    )
    payload = ar.load_run_scenarios("run1", runs_dir=tmp_path)
    assert payload["run_id"] == "run1"
    assert payload["scenarios"][0]["scenario"] == "x"


def test_load_run_scenarios_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        ar.load_run_scenarios("nope", runs_dir=tmp_path)


def test_load_run_scenarios_defaults_to_latest_pointer(tmp_path: Path) -> None:
    run = tmp_path / "run2"
    run.mkdir()
    (run / "scenarios.json").write_text(json.dumps({"run_id": "run2", "scenarios": []}))
    (tmp_path / "latest.txt").write_text("run2", encoding="utf-8")
    assert ar.load_run_scenarios(runs_dir=tmp_path)["run_id"] == "run2"


def test_load_coverage_picks_newest(tmp_path: Path) -> None:
    (tmp_path / "coverage-2026-01-01_000000.json").write_text(
        json.dumps({"missing_tools": ["old"]}), encoding="utf-8"
    )
    (tmp_path / "coverage-2026-09-30_045218.json").write_text(
        json.dumps({"missing_tools": []}), encoding="utf-8"
    )
    payload = ar.load_coverage(coverage_dir=tmp_path)
    assert payload is not None
    assert payload["missing_tools"] == []


def test_load_coverage_absent_returns_none(tmp_path: Path) -> None:
    assert ar.load_coverage(coverage_dir=tmp_path) is None


def test_load_delivery_reads_manifest_gaps_and_index(tmp_path: Path) -> None:
    (tmp_path / "manifest.json").write_text(json.dumps({"files": []}), encoding="utf-8")
    matrix = tmp_path / "04-MATRIX"
    matrix.mkdir()
    (matrix / "coverage-gaps.json").write_text(json.dumps({"summary": {"gap": 0}}))
    qa = tmp_path / "01-QA-GATES"
    qa.mkdir()
    (qa / "gate-reports-index.json").write_text(json.dumps({"reports": []}))
    delivery = ar.load_delivery(tmp_path)
    assert delivery["manifest"] == {"files": []}
    assert delivery["coverage_gaps"] == {"summary": {"gap": 0}}
    assert delivery["gate_reports"] == {"reports": []}


def test_load_delivery_absent_dir_is_empty(tmp_path: Path) -> None:
    delivery = ar.load_delivery(tmp_path)
    assert delivery["manifest"] is None
    assert delivery["coverage_gaps"] is None


# ---------------------------------------------------------------------------
# run_pytest
# ---------------------------------------------------------------------------


def test_run_pytest_collects_real_subprocess(tmp_path: Path) -> None:
    (tmp_path / "test_trivial.py").write_text("def test_ok() -> None:\n    assert True\n")
    result = ar.run_pytest(["--collect-only", "-q", "test_trivial.py"], cwd=tmp_path)
    assert result["rc"] == 0
    assert result["collected"] == 1


def test_parse_collected_handles_plural_and_absent() -> None:
    assert ar._parse_collected("10 tests collected in 0.02s") == 10
    assert ar._parse_collected("1 test collected in 0.01s") == 1
    assert ar._parse_collected("no summary here") is None


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def test_main_writes_report_and_returns_zero(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr(ar, "_gather_inputs", lambda args: _all_pass_inputs())
    out = tmp_path / "report.md"
    rc = ar.main(["--version", "1.14.1", "--date", "2026-09-30", "--out", str(out)])
    assert rc == 0
    text = out.read_text(encoding="utf-8")
    assert "PENDING DIRECTOR SIGN-OFF" in text
    assert "## 中文摘要（Director）" in text
    assert "# Acceptance Run Report 1.14.1 (2026-09-30)" in text


def test_main_without_out_uses_validation_reports_default(tmp_path: Path, monkeypatch: Any) -> None:
    # Redirect the report dir so the test never writes under docs/.
    monkeypatch.setattr(ar, "REPORTS", tmp_path / "reports")
    monkeypatch.setattr(ar, "_gather_inputs", lambda args: _all_pass_inputs())
    rc = ar.main(["--version", "1.14.1", "--date", "2026-09-30"])
    assert rc == 0
    written = list((tmp_path / "reports").glob("acceptance-*.md"))
    assert len(written) == 1
