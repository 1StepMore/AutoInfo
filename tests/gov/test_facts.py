"""Derived-fact instrument tests (T03, P2: derived over declared)."""

from __future__ import annotations

import subprocess

import pytest

from autoinfo.gov import facts as facts_mod


def test_mcp_tools_matches_live_registry() -> None:
    assert facts_mod.mcp_tools() == 151


def test_cli_groups_counts_registered_groups() -> None:
    from autoinfo.cli import app

    expected = len([i.name for i in getattr(app, "registered_groups", []) if i.name])
    assert facts_mod.cli_groups() == expected
    assert facts_mod.cli_groups() == 31


def test_validation_scenarios_split_matches_disk() -> None:
    split = facts_mod.validation_scenarios()
    assert split["total"] == split["functional"] + split["regression"]
    assert split == {"total": 189, "functional": 86, "regression": 103}


def test_demo_domains_and_adr_count_and_channels() -> None:
    assert facts_mod.demo_domains() == 21
    assert facts_mod.adr_count() == 12  # T10 adds 0013/0014 → 14
    assert facts_mod.delivery_channels() == 13
    assert facts_mod.llm_required_tools() == 16


def test_tests_derive_parses_pytest_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """The slow collector is only a regex over pytest's tail line — lock the parse."""

    class FakeProc:
        returncode = 0
        stdout = "6786 tests collected in 42.00s"
        stderr = ""

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: FakeProc())
    assert facts_mod.tests() == 6786


def test_tests_derive_unparsable_output_is_environment_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeProc:
        returncode = 1
        stdout = "no importable autoinfo"
        stderr = "ModuleNotFoundError"

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: FakeProc())
    with pytest.raises(facts_mod.FactsError, match="unparsable"):
        facts_mod.tests()


def test_derive_all_covers_every_contract_fact_in_order() -> None:
    from autoinfo.gov.contract import load

    contract = load()
    tree = facts_mod.derive_all(contract)
    assert list(tree) == list(contract.facts)
    assert len(tree) == 8


def test_derive_all_rejects_fact_without_deriver() -> None:
    """A contract fact without a local deriver is a hard mismatch (exit-2 class)."""
    from autoinfo.gov.contract import load

    contract = load()
    saved = facts_mod.DERIVERS.pop("mcp_tools")
    try:
        with pytest.raises(facts_mod.FactsError, match="no deriver"):
            facts_mod.derive_all(contract)
    finally:
        facts_mod.DERIVERS["mcp_tools"] = saved


def test_flatten_maps_dotted_paths() -> None:
    flat = facts_mod.flatten({"mcp_tools": 151, "validation_scenarios": {"total": 189}})
    assert flat == {"mcp_tools": 151, "validation_scenarios.total": 189}


def test_contract_mcp_tools_pattern_fits_canonical_phrasings() -> None:
    from autoinfo.gov.contract import load

    contract = load()
    pattern = contract.facts["mcp_tools"].matches[0].pattern
    assert pattern.search("151 tools across 35 categories")
    assert pattern.search("151 MCP tools")
