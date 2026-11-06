"""Artifacts tests (T03): deterministic facts.json + separate runtime evidence."""

from __future__ import annotations

import json
from pathlib import Path

from autoinfo.gov import artifacts as artifacts_mod

FACTS: dict[str, object] = {
    "mcp_tools": 151,
    "cli_groups": 31,
    "validation_scenarios": {"total": 189, "functional": 86, "regression": 103},
    "tests": 6844,
    "demo_domains": 21,
    "delivery_channels": 13,
    "llm_required_tools": 16,
    "adr_count": 14,
}


def test_input_hash_is_deterministic_and_order_free() -> None:
    a = artifacts_mod.input_hash(2, FACTS)
    b = artifacts_mod.input_hash(2, dict(reversed(list(FACTS.items()))))
    assert a == b
    assert a.startswith("sha256:")


def test_input_hash_changes_with_any_input() -> None:
    base = artifacts_mod.input_hash(2, FACTS)
    assert artifacts_mod.input_hash(3, FACTS) != base  # contract version drifts it
    drifted = dict(FACTS)
    drifted["mcp_tools"] = 150
    assert artifacts_mod.input_hash(2, drifted) != base  # a fact value drifts it


def test_render_facts_has_no_runtime_fields() -> None:
    text = artifacts_mod.render_facts(2, FACTS)
    data = json.loads(text)
    assert set(data) == {"contract_version", "generator_version", "input_hash", "facts"}
    assert "ts" not in data and "run_id" not in data  # R7: never mix run state in
    # canonical serialization: sorted keys, compact separators
    assert text == json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def test_write_and_load_artifacts_roundtrip(tmp_path: Path) -> None:
    facts_path, evidence_path = artifacts_mod.write_artifacts(tmp_path, 2, FACTS)
    assert facts_path.read_bytes().endswith(b"\n")
    loaded = artifacts_mod.load_cached_facts(tmp_path)
    assert loaded == FACTS
    evidence = artifacts_mod.load_cached_evidence(tmp_path)
    assert evidence is not None
    # commit_sha is None outside a git repo (tmp_path); the rest must be real.
    for field in ("run_id", "input_hash", "ts"):
        assert evidence[field], field
    assert evidence["commit_sha"] is None
    assert evidence["input_hash"] == artifacts_mod.input_hash(2, FACTS)
    assert evidence_path.name == "evidence.json"


def test_load_cached_missing_or_broken_is_none(tmp_path: Path) -> None:
    assert artifacts_mod.load_cached_facts(tmp_path) is None
    assert artifacts_mod.load_cached_evidence(tmp_path) is None
    (tmp_path / ".autoinfo" / "gov").mkdir(parents=True)
    (tmp_path / ".autoinfo" / "gov" / "facts.json").write_text("{broken", encoding="utf-8")
    assert artifacts_mod.load_cached_facts(tmp_path) is None


def test_evidence_fields_are_complete(tmp_path: Path) -> None:
    evidence = artifacts_mod.evidence(tmp_path, 2, FACTS)
    for field in ("run_id", "commit_sha", "input_hash", "ts"):
        assert field in evidence
    assert evidence["ts"].endswith("Z")
