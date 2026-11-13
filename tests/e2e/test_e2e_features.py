"""E2E baseline — journeys in ``tests/e2e/features/`` executed against the
existing validation-scenario engine (issue #729, decision 8).

Decision 8 pins the selection: NO new framework (no Playwright).  Every
journey file maps to existing validation-scenario IDs and the journey's
execution IS running those scenarios through the shipped engine
(:func:`autoinfo.mcp.validation.run_scenario` — the same engine the
``run_validation_scenario`` MCP tool exposes).  This module is the
``E2E_CMD``: ``pytest tests/e2e/test_e2e_features.py -q``.

Honesty contract (mirrors the engine's own):

* a mapped scenario that reports ``passed`` satisfies the journey;
* ``unconfigured`` (the engine's explicit environment-prerequisite reading,
  with ``unconfigured_reason``) surfaces as SKIPPED with the reason — a
  blocked reading, never a silent pass, never a false FAILED;
* anything else (``failed`` / missing scenario id / malformed journey file)
  is red.

Wellformedness is its own test: every ``features/*.md`` must carry the five
contract fields (前置 / 步骤 / 期望终态 / 挂接场景ID / 证据类型) and every
mapped scenario id must exist in the live library, so a renamed scenario
turns red here instead of silently vanishing from the baseline.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from autoinfo.mcp.validation import list_scenarios, run_scenario

FEATURES_DIR = Path(__file__).resolve().parent / "features"

REQUIRED_FIELDS = ("前置", "步骤", "期望终态", "挂接场景ID", "证据类型")

_SCENARIO_LINE = re.compile(r"挂接场景ID\*\*?[:：]\s*(.+)")
_SPLIT = re.compile(r"[\s,、，;；]+")


def _journey_files() -> list[Path]:
    return sorted(FEATURES_DIR.glob("journey-*.md"))


def _journey_scenario_ids(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    m = _SCENARIO_LINE.search(text)
    if m is None:
        return []
    return [tok for tok in _SPLIT.split(m.group(1).strip()) if tok]


def _known_scenario_ids() -> set[str]:
    listing = list_scenarios()
    return {str(s["name"]) for s in listing["scenarios"]}


async def _validation_dispatch(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Route MCP-kind scenario steps through the in-process tool table.

    Same wiring the ``run_validation_scenario`` MCP tool uses; cli/http kind
    steps never reach this (the engine executes them itself).
    """
    import json
    from typing import cast

    from autoinfo.mcp.server import call_tool

    texts = await call_tool(name, arguments)
    return cast(dict[str, Any], json.loads(texts[0][0].text))


async def _run_one(name: str) -> dict[str, Any]:
    return await run_scenario(name, dispatch=_validation_dispatch, timeout=180.0)


# ---------------------------------------------------------------------------
# Wellformedness of the journey contracts
# ---------------------------------------------------------------------------


def test_journey_inventory_is_the_pinned_baseline() -> None:
    """The baseline has its ~20 pinned journeys (P4-S4 / CP-06 sample size).

    A silent shrink of the baseline (deleted journey files) would quietly
    hollow out the E2E layer — the count is part of the contract.
    """
    files = _journey_files()
    assert len(files) >= 20, f"E2E baseline shrank to {len(files)} journeys"


def test_every_journey_carries_the_contract_fields() -> None:
    """前置 / 步骤(仅终态断言) / 期望终态 / 挂接场景ID / 证据类型 — all five."""
    for path in _journey_files():
        text = path.read_text(encoding="utf-8")
        missing = [f for f in REQUIRED_FIELDS if f not in text]
        assert not missing, f"{path.name}: missing field(s) {missing}"


def test_every_mapped_scenario_id_exists() -> None:
    """A mapped scenario id must exist in the live library.

    Renames/deletions of scenarios turn red here instead of silently
    shrinking the E2E baseline.
    """
    known = _known_scenario_ids()
    for path in _journey_files():
        ids = _journey_scenario_ids(path)
        assert ids, f"{path.name}: no 挂接场景ID line"
        unknown = [sid for sid in ids if sid not in known]
        assert not unknown, f"{path.name}: unknown scenario id(s) {unknown}"


# ---------------------------------------------------------------------------
# Journey execution — each mapped scenario runs through the real engine
# ---------------------------------------------------------------------------


def _journey_params() -> list[pytest.Param]:
    params: list[pytest.Param] = []
    for path in _journey_files():
        ids = _journey_scenario_ids(path)
        params.append(pytest.param(path, ids, id=path.stem))
    return params


@pytest.mark.parametrize("path,scenario_ids", _journey_params())
class TestJourneyExecution:
    async def test_all_mapped_scenarios_pass(self, path: Path, scenario_ids: list[str]) -> None:
        for sid in scenario_ids:
            result = await _run_one(sid)
            status = str(result.get("status"))
            if status == "unconfigured":
                reason = result.get("unconfigured_reason") or "environment prerequisite missing"
                pytest.skip(f"blocked-unconfigured: {sid} — {reason}")
            assert status == "passed", (
                f"{path.name}: mapped scenario '{sid}' reported '{status}' — "
                f"{result.get('summary')}"
            )
