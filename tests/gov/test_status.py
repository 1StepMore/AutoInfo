"""Status-model tests (T06): the 7 judgment rules, locked (plan §2)."""

from __future__ import annotations

from typing import Any

from autoinfo.gov import status as status_mod
from autoinfo.gov.contract import load


def _full_evidence(input_hash: str = "sha256:abc") -> dict[str, Any]:
    return {
        "run_id": "test-run-1",
        "commit_sha": "deadbeef",
        "input_hash": input_hash,
        "ts": "2026-11-06T00:00:00Z",
    }


def _gate_cfg(**overrides: Any) -> dict[str, Any]:
    cfg: dict[str, Any] = {"kind": "gate", "required": True, "advisory": False}
    cfg.update(overrides)
    return cfg


def _raw(state: str, **overrides: Any) -> dict[str, Any]:
    raw: dict[str, Any] = {
        "state": state,
        "reason": "",
        "missing": [],
        "evidence": _full_evidence() if state == "PASS" else None,
    }
    raw.update(overrides)
    return raw


def test_pass_with_missing_evidence_fails_rule_1() -> None:
    raw = _raw("PASS", evidence={"run_id": "x"})  # missing 3 of 4 fields
    gate = status_mod._judge(raw, _gate_cfg(), "sha256:abc")
    assert gate["state"] == "FAIL"
    assert gate["reason"] == "missing_evidence"
    assert set(gate["missing"]) == {"commit_sha", "input_hash", "ts"}


def test_stale_evidence_rule_2() -> None:
    raw = _raw("PASS", evidence=_full_evidence("sha256:OLD"))
    gate = status_mod._judge(raw, _gate_cfg(), "sha256:NEW")
    assert gate["state"] == "STALE"
    assert "input_hash" in gate["reason"]


def test_matching_input_hash_stays_pass() -> None:
    raw = _raw("PASS", evidence=_full_evidence("sha256:same"))
    gate = status_mod._judge(raw, _gate_cfg(), "sha256:same")
    assert gate["state"] == "PASS"


def test_unexplained_not_run_required_blocks_rule_4() -> None:
    gate = status_mod._judge(_raw("NOT_RUN"), _gate_cfg(required=True), "")
    assert gate.get("blocking") is True
    allowed = status_mod._judge(
        _raw("NOT_RUN"),
        _gate_cfg(required=True, not_run_allowed_reason="wiring lands in T09"),
        "",
    )
    assert allowed.get("blocking") is None


def test_full_report_shape_and_green_aggregate() -> None:
    contract = load()
    report = status_mod.status(contract, {}, only="preview_smoke")
    assert report["verdict"]["overall"] in {"green", "amber"}
    assert report["pass_total_excludes_advisory"] is True
    assert report["gates"][0]["id"] == "preview_smoke"


def test_advisory_never_counts_into_pass_rule_3() -> None:
    contract = load()
    report = status_mod.status(contract, {}, only="ruff_full")
    gate = report["gates"][0]
    assert gate["advisory"] is True
    # whatever the state, an advisory gate cannot inflate pass_total
    if gate["state"] == "PASS":
        assert report["pass_total"] == 0


def test_exit_codes_rule_6() -> None:
    red = {"verdict": {"overall": "red", "reasons": ["x"]}}
    green = {"verdict": {"overall": "green", "reasons": []}}
    amber = {"verdict": {"overall": "amber", "reasons": ["y"]}}
    degraded = {"verdict": {"overall": "degraded", "reasons": []}}
    assert status_mod.exit_code(red) == 1
    assert status_mod.exit_code(green) == 0
    assert status_mod.exit_code(amber) == 0
    assert status_mod.exit_code(degraded) == 0
