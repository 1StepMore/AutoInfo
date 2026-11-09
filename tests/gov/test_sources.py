"""Source-reader tests (T06/T07/T08): honest degradation, budget parsing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from autoinfo.gov import sources
from autoinfo.gov.contract import load


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_known_red_budget_parsed_from_triage() -> None:
    contract = load()
    result = sources.read_known_red(contract, {})
    # T08 wired the fenced block: budget must parse (empty since 2026-10-12)
    assert result.get("budget") == 0
    assert result["state"] in {"NOT_RUN", "PASS", "FAIL"}  # depends on junit presence
    if result["state"] == "FAIL":
        assert result["observed"] is not None and result["observed"] > 0


def test_known_red_budget_zero_with_observed_failure_fails(tmp_path: Path) -> None:
    """Negative control: budget=0 + observed>0 must FAIL (plan T08 acceptance)."""
    import textwrap

    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "TRIAGE.md").write_text(
        textwrap.dedent(
            """\
            # Triage

            ```known-red-budget
            count = 0
            baseline = "2026-10-12"
            ```
            """
        ),
        encoding="utf-8",
    )
    junit = """<?xml version='1.0' encoding='utf-8'?>
<testsuites><testsuite name="pytest" failures="2" errors="1" tests="100"/></testsuites>
"""
    (tmp_path / "nightly-junit.xml").write_text(junit, encoding="utf-8")
    contract = load()
    # Contract is frozen; build a shallow proxy carrying the tmp root.
    proxy = SimpleNamespace(contract, root=tmp_path)
    result = sources.read_known_red(proxy, {})  # type: ignore[arg-type]
    assert result["state"] == "FAIL"
    assert result["budget"] == 0
    assert result["observed"] == 3
    assert result["delta"] == 3


def test_coverage_base_degraded_on_nonzero_exit(tmp_path: Path) -> None:
    """Negative control: a swallowed base-suite exit surfaces as DEGRADED."""
    gov_dir = tmp_path / ".autoinfo" / "gov"
    gov_dir.mkdir(parents=True)
    (gov_dir / "coverage-base.json").write_text(
        json.dumps({"base_suite_exit": 3, "base_sha": "abc12345"}), encoding="utf-8"
    )
    contract = load()
    proxy = SimpleNamespace(contract, root=tmp_path)
    result = sources.read_coverage_base(proxy, {})  # type: ignore[arg-type]
    assert result["state"] == "DEGRADED"
    assert result["base_suite_exit"] == 3


def test_coverage_base_pass_on_zero_exit(tmp_path: Path) -> None:
    gov_dir = tmp_path / ".autoinfo" / "gov"
    gov_dir.mkdir(parents=True)
    (gov_dir / "coverage-base.json").write_text(
        json.dumps({"base_suite_exit": 0, "base_sha": "abc12345"}), encoding="utf-8"
    )
    contract = load()
    proxy = SimpleNamespace(contract, root=tmp_path)
    result = sources.read_coverage_base(proxy, {})  # type: ignore[arg-type]
    assert result["state"] == "PASS"


def test_missing_coverage_base_evidence_is_not_run() -> None:
    contract = load()
    result = sources.read_coverage_base(contract, {})
    assert result["state"] == "NOT_RUN"
    assert result["missing"] == ["coverage-base.json"]


def test_reader_failure_degrades_to_unmeasured() -> None:
    """A crashing reader must never raise and never fake-pass (plan T06)."""
    contract = load()

    def boom(contract: Any, derived: Any) -> Any:
        raise RuntimeError("instrument exploded")

    saved = sources.READERS["known_red"]
    sources.READERS["known_red"] = boom
    try:
        result = sources.read_gate("known_red", contract, {})
    finally:
        sources.READERS["known_red"] = saved
    assert result["state"] == "UNMEASURED"
    assert "instrument exploded" in result["reason"]
    assert sources.read_gate("no_such_gate", contract, {})["state"] == "UNMEASURED"


def test_derived_parity_stale_detection(tmp_path: Path) -> None:
    """T09 mechanism: stored parity evidence with an old hash must be STALE."""
    gov_dir = tmp_path / ".autoinfo" / "gov"
    gov_dir.mkdir(parents=True)
    (gov_dir / "derived-parity.json").write_text(
        json.dumps({"input_hash": "sha256:OLDOLDOLDOLD", "evidence": None}), encoding="utf-8"
    )
    contract = load()
    facts: dict[str, Any] = {"mcp_tools": 151}
    proxy = SimpleNamespace(contract, root=tmp_path)
    result = sources.read_derived_parity(proxy, facts)  # type: ignore[arg-type]
    assert result["state"] == "STALE"
    assert "rerun gov check" in result["reason"]


def test_derived_parity_missing_artifact_names_the_producer(tmp_path: Path) -> None:
    contract = load()
    proxy = SimpleNamespace(contract, root=tmp_path)
    result = sources.read_derived_parity(proxy, {"mcp_tools": 151})  # type: ignore[arg-type]
    assert result["state"] == "NOT_RUN"
    assert "gov check --write-evidence" in result["reason"]


def test_derived_parity_written_record_replays_as_pass(tmp_path: Path) -> None:
    from autoinfo.gov import artifacts

    contract = load()
    facts: dict[str, Any] = {"mcp_tools": 151}
    clean = {"fail": 0, "stale": 0, "unexplained_not_run": 0, "files_scanned": 7}
    artifacts.write_parity_evidence(tmp_path, contract.version, facts, clean)
    proxy = SimpleNamespace(contract, root=tmp_path)
    result = sources.read_derived_parity(proxy, facts)  # type: ignore[arg-type]
    assert result["state"] == "PASS"
    assert result["evidence"]["input_hash"] == artifacts.input_hash(contract.version, facts)


def test_derived_parity_non_clean_record_cannot_pass(tmp_path: Path) -> None:
    from autoinfo.gov import artifacts

    contract = load()
    facts: dict[str, Any] = {"mcp_tools": 151}
    artifacts.write_parity_evidence(
        tmp_path,
        contract.version,
        facts,
        {"fail": 2, "stale": 0, "unexplained_not_run": 0, "files_scanned": 7},
    )
    proxy = SimpleNamespace(contract, root=tmp_path)
    result = sources.read_derived_parity(proxy, facts)  # type: ignore[arg-type]
    assert result["state"] == "FAIL"
    assert "not clean" in result["reason"]


def test_cmd_check_write_evidence_only_on_clean_run(tmp_path: Path, monkeypatch: Any) -> None:
    import argparse

    from autoinfo.gov import __main__ as gov_main
    from autoinfo.gov import artifacts
    from autoinfo.gov import facts as facts_mod

    contract = load()
    facts: dict[str, Any] = {"mcp_tools": 151}

    def fake_check(fail: int) -> Any:
        return lambda: {
            "fail": fail,
            "stale": 0,
            "unexplained_not_run": 0,
            "violations": [],
            "files_scanned": 7,
            "facts": facts,
            "flat_facts": {},
            "input_hash": artifacts.input_hash(contract.version, facts),
            "contract_version": contract.version,
            "generator_version": artifacts.GENERATOR_VERSION,
        }

    monkeypatch.setattr(
        "autoinfo.gov.contract.load", lambda: SimpleNamespace(contract, root=tmp_path)
    )
    args = argparse.Namespace(write_evidence=True)

    monkeypatch.setattr(facts_mod, "check", fake_check(1))
    data, rc = gov_main.cmd_check(args)
    assert rc == 1
    assert data["parity_evidence"] is None
    assert not (tmp_path / ".autoinfo" / "gov" / "derived-parity.json").exists()

    monkeypatch.setattr(facts_mod, "check", fake_check(0))
    data, rc = gov_main.cmd_check(args)
    assert rc == 0
    assert data["parity_evidence"] is not None
    assert (tmp_path / ".autoinfo" / "gov" / "derived-parity.json").is_file()


class SimpleNamespace:
    """Read-only stand-in exposing .root on a frozen Contract."""

    def __init__(self, contract: Any, root: Path) -> None:
        self._contract = contract
        self.root = root

    def __getattr__(self, name: str) -> Any:
        return getattr(self._contract, name)
