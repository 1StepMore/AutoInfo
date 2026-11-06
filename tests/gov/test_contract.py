"""Contract load + validation tests (T02).

The contract is the single machine-readable authority; a structural or
importability defect must fail HERE, not at first use (plan §8.5).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from autoinfo.gov import contract as contract_mod


def _contract_text() -> str:
    path = Path(__file__).resolve().parents[2] / ".github" / "governance-contract.toml"
    return path.read_text(encoding="utf-8")


def test_real_contract_loads_and_validates() -> None:
    """The committed contract is structurally valid and every target imports."""
    contract = contract_mod.load()
    assert contract.version >= 2
    assert contract.authority_order[0] == "runtime:src+derived_facts"
    assert len(contract.facts) == 8
    assert set(contract.profiles) == {"cloud", "local"}
    errors = contract_mod.validate(contract)
    assert errors == []


def test_contract_check_payload_is_green() -> None:
    data = contract_mod.check()
    assert data["valid"] is True
    assert data["errors"] == []
    assert data["unsynced"] == []


def test_missing_contract_is_environment_error(tmp_path: Path) -> None:
    with pytest.raises(contract_mod.ContractError):
        contract_mod.load(tmp_path)


def test_unparsable_contract_is_environment_error(tmp_path: Path) -> None:
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "governance-contract.toml").write_text("not [ toml", encoding="utf-8")
    with pytest.raises(contract_mod.ContractError):
        contract_mod.load(tmp_path)


def _write_contract(tmp_path: Path, text: str) -> Path:
    (tmp_path / ".github").mkdir(exist_ok=True)
    (tmp_path / ".github" / "governance-contract.toml").write_text(text, encoding="utf-8")
    return tmp_path


def test_exclusion_without_reason_fails_validation(tmp_path: Path) -> None:
    text = _contract_text().replace(
        'path = "docs/archive/**"\nreason = "historical snapshots legitimately '
        'preserve old strings (doc-manager convention 1.7)"',
        'path = "docs/archive/**"\nreason = ""',
    )
    root = _write_contract(tmp_path, text)
    errors = contract_mod.validate(contract_mod.load(root))
    assert any("docs/archive/**" in e and "reason" in e for e in errors)


def test_unimportable_derive_target_fails_validation(tmp_path: Path) -> None:
    text = _contract_text().replace(
        'derive = "autoinfo.gov.facts:mcp_tools"',
        'derive = "autoinfo.gov.nope_module:missing_fn"',
    )
    root = _write_contract(tmp_path, text)
    errors = contract_mod.validate(contract_mod.load(root))
    assert any("autoinfo.gov.nope_module:missing_fn" in e for e in errors)


def test_non_callable_derive_target_fails_validation(tmp_path: Path) -> None:
    text = _contract_text().replace(
        'derive = "autoinfo.gov.facts:mcp_tools"',
        'derive = "autoinfo.gov.facts:DERIVERS"',
    )
    root = _write_contract(tmp_path, text)
    errors = contract_mod.validate(contract_mod.load(root))
    assert any("not callable" in e for e in errors)


def test_uncompilable_pattern_fails_load(tmp_path: Path) -> None:
    text = _contract_text().replace(
        r"pattern = '(?<![A-Za-z0-9])(\d+)\s+(?:MCP\s+)?tools?\b'",
        "pattern = '(unclosed['",
    )
    root = _write_contract(tmp_path, text)
    with pytest.raises(contract_mod.ContractError, match="does not compile"):
        contract_mod.load(root)


def test_profile_key_set_mismatch_fails_validation(tmp_path: Path) -> None:
    text = _contract_text().replace(
        '[profiles.local]\nallow = ["*"]\ndeny = []',
        '[profiles.local]\nallow = ["*"]',
    )
    root = _write_contract(tmp_path, text)
    errors = contract_mod.validate(contract_mod.load(root))
    assert any("key sets differ" in e for e in errors)


def test_decision_missing_adr_file_fails_validation(tmp_path: Path) -> None:
    text = _contract_text() + (
        '\n[decisions.dco_identity]\nadr = "9999"\n'
        'consumers = [{ file = "AGENTS.md", expect = "ADR-9999" }]\n'
    )
    root = _write_contract(tmp_path, text)
    errors = contract_mod.validate(contract_mod.load(root))
    assert any("9999" in e for e in errors)


def test_every_exclusion_has_a_reason() -> None:
    """P3: a default-ON scan may only exclude paths with written reasons."""
    contract = contract_mod.load()
    assert contract.excludes
    assert all(exc.reason.strip() for exc in contract.excludes)


def test_states_and_evidence_fields_are_locked() -> None:
    """The 8-state enum and evidence schema are the plan's single口径 (§2)."""
    assert contract_mod.STATES == (
        "PASS",
        "FAIL",
        "NOT_RUN",
        "STALE",
        "UNMEASURED",
        "ADVISORY",
        "UNCONFIGURED",
        "DEGRADED",
    )
    assert contract_mod.EVIDENCE_FIELDS == ("run_id", "commit_sha", "input_hash", "ts")
