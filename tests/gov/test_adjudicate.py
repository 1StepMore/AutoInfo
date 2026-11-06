"""Authority-order adjudication tests (T02/G3, DoD #4: deterministic 3/3)."""

from __future__ import annotations

import pytest

from autoinfo.gov import adjudicate as adj
from autoinfo.gov.contract import load


def test_readme_beats_contributing_for_mcp_tools() -> None:
    contract = load()
    data = adj.adjudicate(contract, "mcp_tools", "README.md=151,CONTRIBUTING.md=999")
    assert data["winner"]["source"] == "README.md"
    assert data["winner"]["value"] == 151
    assert data["winner"]["authority"] == "README.md#status"


def test_determinism_three_runs() -> None:
    contract = load()
    winners = {
        adj.adjudicate(contract, "mcp_tools", "README.md=151,CONTRIBUTING.md=999")["winner"][
            "value"
        ]
        for _ in range(3)
    }
    assert winners == {151}


def test_runtime_authority_wins_over_every_doc() -> None:
    contract = load()
    data = adj.adjudicate(contract, "mcp_tools", "runtime:derived_facts=151,README.md=150")
    assert data["winner"]["source"] == "runtime:derived_facts"
    assert data["winner"]["rank"] == 0


def test_adr_prefix_matching() -> None:
    contract = load()
    data = adj.adjudicate(contract, "adr_count", "docs/adr/0009-dco.md=12,AGENTS.md=7")
    assert data["winner"]["source"] == "docs/adr/0009-dco.md"
    assert data["winner"]["authority"] == "docs/adr/*"


def test_unknown_source_falls_to_other_docs() -> None:
    contract = load()
    data = adj.adjudicate(contract, "mcp_tools", "somewhere/else.md=3,AGENTS.md=151")
    assert data["winner"]["source"] == "AGENTS.md"
    loser = [c for c in data["candidates"] if c["source"] == "somewhere/else.md"][0]
    assert loser["authority"] == "other_docs"


def test_malformed_candidates_raise_value_error() -> None:
    with pytest.raises(ValueError, match="malformed"):
        adj.parse_candidates("README.md-151")
    with pytest.raises(ValueError, match="malformed"):
        adj.parse_candidates("=151")
