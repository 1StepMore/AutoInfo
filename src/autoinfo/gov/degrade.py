"""Degraded-environment simulation (T16/G7).

Every gate declares which external capabilities its instrument needs; a
simulation mode pretends one capability is gone and the affected gates must
report UNCONFIGURED/DEGRADED — never PASS. Restoring the environment restores
PASS. The simulation is a drill: it never mutates the real instruments, and
it is logged like any other run.

Dependency vocabulary:
- ``network``       — evidence that arrives from remote runs (CI artifacts, nightly junit)
- ``local-service`` — a local server/artifact the instrument probes
- ``tooling``       — an executable the instrument shells out to
- ``llm-key``       — an LLM key (no gov instrument needs one today, BYOK-free
  by design; declared so the no-key drill is meaningful the day one appears)
"""

from __future__ import annotations

from typing import Any

#: gate id → capabilities the gate's instrument requires.
GATE_DEPS: dict[str, frozenset[str]] = {
    "facts_parity": frozenset({"tooling"}),
    "ruff_full": frozenset({"tooling"}),
    "derived_parity": frozenset({"network", "tooling"}),
    "known_red": frozenset({"network"}),
    "preview_smoke": frozenset({"network", "local-service"}),
    "coverage_base": frozenset({"network"}),
}

#: simulation mode → capability that is gone.
SIMULATIONS: dict[str, str] = {
    "offline": "network",
    "no-service": "local-service",
    "no-key": "llm-key",
}

#: state a gate reports when its capability is unavailable in a drill.
DRILL_STATE = "UNCONFIGURED"


def affected_gates(gate_ids: list[str], simulate: str) -> list[str]:
    """Gates whose dependencies intersect the simulated outage."""
    capability = SIMULATIONS.get(simulate)
    if capability is None:
        return []
    return [gate_id for gate_id in gate_ids if capability in GATE_DEPS.get(gate_id, frozenset())]


def apply_simulation(raw: dict[str, Any], simulate: str) -> dict[str, Any]:
    """Rewrite a reader result under the drill; honest about no-op drills."""
    capability = SIMULATIONS.get(simulate)
    if capability is None:
        return raw
    gate_id = str(raw.get("id", ""))
    if capability not in GATE_DEPS.get(gate_id, frozenset()):
        return raw
    previous_state = str(raw.get("state", "UNMEASURED"))
    if previous_state == "PASS":
        return {
            **raw,
            "state": DRILL_STATE,
            "reason": f"simulated {simulate}: {capability} unavailable "
            "(was PASS — the drill flipped it, T16)",
            "missing": sorted({*raw.get("missing", []), capability}),
            "simulated_from": previous_state,
        }
    # Already non-PASS: keep the honest state, annotate the drill.
    return {
        **raw,
        "reason": f"simulated {simulate}: {capability} unavailable; was already "
        f"{previous_state} — {raw.get('reason', '')}".strip(),
    }
