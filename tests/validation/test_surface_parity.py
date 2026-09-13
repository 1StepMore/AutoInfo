"""Surface parity matrix tests (T-S-10).

Asserts the REST half of `docs/dev/cli-mcp-rest-parity.md` against the live
FastAPI route table via `scripts/surface_parity.py`:

* zero unaccounted endpoints;
* the historical eight endpoints are scenario-covered (not artifact-only);
* every declared artifact exists and references its route;
* the parity doc enumerates every live endpoint.

The negative test proves the classifier actually reports a gap.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
PARITY_SCRIPT = ROOT / "scripts" / "surface_parity.py"


@pytest.fixture(scope="module")
def parity() -> Any:
    spec = importlib.util.spec_from_file_location("surface_parity", PARITY_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register before exec so dataclasses can resolve this module's annotations.
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module


@pytest.fixture(scope="module")
def report(parity: Any) -> dict[str, Any]:
    return parity.compute_parity()


def test_no_unaccounted_rest_endpoints(report: dict[str, Any]) -> None:
    assert report["by_kind"]["unaccounted"] == 0, report["unaccounted"]
    assert report["count"] > 0


def test_canonical_eight_are_scenario_covered(report: dict[str, Any]) -> None:
    """The historical REST parity claim names eight endpoints; each must have
    a real scenario HTTP step, never merely a test artifact."""
    assert len(report["canonical_scenario_endpoints"]) == 8
    assert report["canonical_missing"] == [], report["canonical_missing"]
    covered = {
        (row["method"], row["path"])
        for row in report["endpoints"]
        if row["evidence_kind"] == "scenario"
    }
    for method, path in report["canonical_scenario_endpoints"]:
        assert (method, path) in covered


def test_artifacts_exist_and_reference_their_route(parity: Any) -> None:
    assert parity.verify_artifacts() == []


def test_parity_doc_lists_every_live_endpoint(parity: Any, report: dict[str, Any]) -> None:
    assert parity.doc_missing_paths(report) == []


def test_route_template_matches_concrete_path(parity: Any) -> None:
    assert parity._route_matches("/api/v1/entries/{entry_id}", "/api/v1/entries/abc")
    assert not parity._route_matches("/api/v1/entries/{entry_id}", "/api/v1/entries/abc/def")
    assert parity._route_matches("/health", "/health")


def test_classifier_reports_a_gap(parity: Any) -> None:
    """A synthetic unaccounted endpoint must surface as `unaccounted`."""
    endpoints = [{"method": "GET", "path": "/definitely/unmapped", "name": "x"}]
    rows = parity.classify_endpoints(endpoints, scenario_endpoints=set())
    assert rows[0]["evidence_kind"] == "unaccounted"


def test_scenario_http_parsing_finds_canonical_paths(parity: Any) -> None:
    covered = parity.scenario_http_endpoints()
    for method, path in parity.CANONICAL_SCENARIO_ENDPOINTS:
        assert (method, path) in covered, f"missing scenario HTTP step for {method} {path}"


def test_main_check_exits_zero(parity: Any) -> None:
    assert parity.main(["--check"]) == 0
