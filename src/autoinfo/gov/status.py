"""Unified 8-state status model (T06) — the single "is everything OK" answer.

Judgment rules are the plan's seven (§2), locked here:

1. ``PASS`` with any missing evidence field → ``FAIL(missing_evidence)``.
2. stored evidence whose ``input_hash`` != the current derived hash → ``STALE``.
3. ``ADVISORY`` never enters ``counts.pass`` and never blocks.
4. ``required`` + ``NOT_RUN`` without a contract ``not_run_allowed_reason`` → blocking.
5. ``UNCONFIGURED / DEGRADED / UNMEASURED`` → overall amber (min) with reason + missing.
6. Exit codes: 0 = no FAIL/STALE/unexplained NOT_RUN (green|amber); 1 = red; 2 = env error.
7. No force-pass path exists — the flag is refused before the model runs.

``verdict.overall`` ∈ {green, amber, red, degraded}; there is no ``unknown``.
"""

from __future__ import annotations

from typing import Any

from autoinfo.gov import degrade, sources
from autoinfo.gov.contract import EVIDENCE_FIELDS, STATES, Contract

AMBER_STATES = ("UNCONFIGURED", "DEGRADED", "UNMEASURED")


def _missing_evidence(evidence: Any) -> list[str]:
    if not isinstance(evidence, dict):
        return list(EVIDENCE_FIELDS)
    return [field for field in EVIDENCE_FIELDS if not evidence.get(field)]


def _judge(
    raw: dict[str, Any],
    gate_cfg: dict[str, Any],
    current_input_hash: str,
) -> dict[str, Any]:
    """Apply the §2 judgment rules to one raw reader result."""
    gate: dict[str, Any] = {
        "id": raw.get("id", ""),
        "state": raw.get("state", "UNMEASURED"),
        "required": bool(gate_cfg.get("required", False)),
        "advisory": bool(gate_cfg.get("advisory", False)),
        "reason": str(raw.get("reason", "")),
        "missing": list(raw.get("missing", [])),
        "evidence": raw.get("evidence"),
    }
    gate.update({k: v for k, v in raw.items() if k not in gate and k != "id"})

    # Rule 2 — stored evidence gone stale against the current derivation.
    evidence = gate["evidence"]
    if (
        gate["state"] == "PASS"
        and isinstance(evidence, dict)
        and evidence.get("input_hash")
        and current_input_hash
        and evidence["input_hash"] != current_input_hash
    ):
        gate["state"] = "STALE"
        gate["reason"] = (
            f"evidence input_hash != current derived input_hash ({evidence['input_hash']})"
        )

    # Rule 1 — a PASS must carry complete evidence.
    if gate["state"] == "PASS":
        missing_fields = _missing_evidence(evidence)
        if missing_fields:
            gate["state"] = "FAIL"
            gate["reason"] = "missing_evidence"
            gate["missing"] = missing_fields

    # Rule 4 — required + NOT_RUN needs the contract's written reason.
    not_run_allowed = bool(gate_cfg.get("not_run_allowed_reason"))
    gate["not_run_allowed"] = not_run_allowed
    if gate["state"] == "NOT_RUN" and gate["required"] and not not_run_allowed:
        gate["blocking"] = True
    return gate


def status(
    contract: Contract,
    derived: dict[str, Any],
    only: str | None = None,
    simulate: str | None = None,
) -> dict[str, Any]:
    """Aggregate every contract gate into the 8-state report."""
    # `_input_hash` rides along as metadata; readers must see the CLEAN facts
    # tree so their evidence hashes match the aggregate's current hash exactly.
    current_input_hash = str(derived.get("_input_hash", ""))
    facts_clean = {k: v for k, v in derived.items() if k != "_input_hash"}
    gates: list[dict[str, Any]] = []
    for gate_id, gate_cfg in contract.gates.items():
        if only and gate_id != only:
            continue
        raw = sources.read_gate(gate_id, contract, facts_clean)
        raw["id"] = gate_id
        if simulate:
            raw = degrade.apply_simulation(raw, simulate)
        gates.append(_judge(raw, gate_cfg, current_input_hash))

    counts = {state: 0 for state in STATES}
    for gate in gates:
        counts[gate["state"]] = counts.get(gate["state"], 0) + 1

    # Rule 3 — advisory never counts as a pass; the self-certifying flag
    # exists so a consumer can assert the exclusion is in effect.
    passing = [g for g in gates if g["state"] == "PASS" and not g["advisory"]]
    blocking = [
        g["id"]
        for g in gates
        if g["state"] in {"FAIL", "STALE"} or (g["state"] == "NOT_RUN" and g.get("blocking"))
    ]
    degraded_states = [g["id"] for g in gates if g["state"] in AMBER_STATES]

    if blocking:
        overall = "red"
    elif degraded_states:
        overall = "amber"
    else:
        overall = "green"

    reasons: list[str] = []
    if blocking:
        reasons.append(f"blocking gates: {', '.join(blocking)}")
    if degraded_states:
        reasons.append(f"degraded/unconfigured gates: {', '.join(degraded_states)}")

    simulation: dict[str, Any] | None = None
    if simulate:
        capability = degrade.SIMULATIONS.get(simulate, "")
        flipped = [g["id"] for g in gates if g.get("simulated_from") == "PASS"]
        affected = degrade.affected_gates([g["id"] for g in gates], simulate)
        simulation = {
            "mode": simulate,
            "capability": capability,
            "affected_gates": affected,
            "flipped_from_pass": flipped,
        }
        # A drill IS a degraded environment by declaration: even when no gate
        # depends on the missing capability (e.g. no-key today — no gov
        # instrument is key-bound by design), the drill must not read green.
        if overall == "green":
            overall = "amber"
            reasons.append(
                f"simulated {simulate} drill: {len(affected)} affected gate(s) "
                f"({', '.join(affected) or 'none depends on ' + capability})"
            )

    return {
        "verdict": {"overall": overall, "reasons": reasons},
        "gates": gates,
        "counts": counts,
        "pass_total": len(passing),
        "pass_total_excludes_advisory": True,
        "blocking": blocking,
        "simulation": simulation,
    }


def exit_code(report: dict[str, Any]) -> int:
    """Rule 6 — 0 green/amber, 1 red, (2 is reserved for env errors upstream)."""
    overall = report["verdict"]["overall"]
    if overall == "red":
        return 1
    if overall in {"green", "amber", "degraded"}:
        return 0
    return 1
