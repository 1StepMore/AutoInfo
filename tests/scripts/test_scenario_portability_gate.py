"""Tests for the scenario portability gate's LLM-seam static check (issue #623)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


def _load_gate() -> Any:
    path = Path(__file__).resolve().parents[2] / "scripts" / "scenario_portability_gate.py"
    spec = importlib.util.spec_from_file_location("scenario_portability_gate", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = _load_gate()


def _scenario(command: str, requires_env: list[str] | None = None) -> dict[str, Any]:
    return {
        "name": "fixture",
        "requires_env": requires_env or [],
        "steps": [{"name": "step", "kind": "cli", "command": command}],
    }


def test_unneutralized_delivery_gate_call_is_flagged() -> None:
    scenario = _scenario(
        "python3 -c '\n"
        "from autoinfo.output import _apply_delivery_gates\n"
        "_apply_delivery_gates(body, 'markdown', [], {}, 'PROCESSED')\n"
        "'"
    )
    assert gate._unneutralized_judge_steps(scenario) == ["step"]


def test_patched_judge_seam_is_not_flagged() -> None:
    scenario = _scenario(
        "python3 -c '\n"
        "import autoinfo.output as out\n"
        "out.call_with_fallback = lambda *a, **k: None\n"
        "from autoinfo.output import _apply_delivery_gates\n"
        "_apply_delivery_gates(body, 'markdown', [], {}, 'PROCESSED')\n"
        "'"
    )
    assert gate._unneutralized_judge_steps(scenario) == []


def test_scenario_declaring_an_env_requirement_is_exempt() -> None:
    scenario = _scenario(
        "python3 -c '\n"
        "from autoinfo.output import _apply_delivery_gates\n"
        "_apply_delivery_gates(body, 'markdown', [], {}, 'PROCESSED')\n"
        "'",
        requires_env=["AUTOINFO_LLM_API_KEY"],
    )
    assert gate._unneutralized_judge_steps(scenario) == []
