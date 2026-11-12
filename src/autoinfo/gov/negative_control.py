"""Negative-control harness (T17/G9) + confidence grading (E2/E3).

Every mechanism must be proven the same way: **break it → it turns red →
restore it → it turns green** (three evidences per case: broke, turned_red,
restored). Only-positive stacks that never went red are treated as
paper-compliant by the plan (§10), so this harness exists to make going red
a recorded, repeatable act.

Cases that would mutate the tree run inside a temporary ``git worktree``
(R6) and assert restoration via ``git status --porcelain`` being empty.
Cases that cannot mutate anything (policy, force-pass refusal) exercise the
mechanism directly.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, cast

from autoinfo.gov import artifacts as artifacts_mod
from autoinfo.gov import policy as policy_mod
from autoinfo.gov import sources as sources_mod
from autoinfo.gov import status as status_mod
from autoinfo.gov.__main__ import EXIT_ENV
from autoinfo.gov.contract import load

#: The plan's case list (T17): >= 8 cases, all three evidences mandatory.
CASES = (
    "facts-drift",
    "missing-evidence",
    "stale-input",
    "adr-unsynced",
    "escalate-overdue",
    "force-pass",
    "cloud-forbidden",
    "degrade-offline",
)


def _git(root: Path, *args: str) -> tuple[int, str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    return proc.returncode, f"{proc.stdout}{proc.stderr}".strip()


def _gov(root: Path, *argv: str) -> tuple[int, str]:
    """Run the gov entry point inside *root* with this interpreter."""
    import sys

    proc = subprocess.run(
        [sys.executable, "-m", "autoinfo.gov", *argv],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=900,
    )
    return proc.returncode, proc.stdout.strip()


def _clean_worktree(root: Path) -> Path:
    """Temporary worktree at HEAD — where destructive cases break things."""
    base = Path(tempfile.mkdtemp(prefix="gov-negctl-"))
    rc, out = _git(root, "worktree", "add", "--detach", str(base / "wt"), "HEAD")
    if rc != 0:
        shutil.rmtree(base, ignore_errors=True)
        raise RuntimeError(f"worktree add failed: {out}")
    return base / "wt"


def _teardown(root: Path, worktree: Path) -> None:
    _git(root, "worktree", "remove", "--force", str(worktree))
    parent = worktree.parent
    shutil.rmtree(parent, ignore_errors=True)


def case_facts_drift(root: Path) -> dict[str, Any]:
    """Tamper a count in CONTRIBUTING.md → gov check red → restore → green."""
    worktree = _clean_worktree(root)
    evidence: dict[str, Any] = {"case": "facts-drift"}
    try:
        target = worktree / "CONTRIBUTING.md"
        original = target.read_text(encoding="utf-8")
        tampered = original.replace("151 MCP tools", "150 MCP tools", 1)
        evidence["broke"] = tampered != original
        target.write_text(tampered, encoding="utf-8", newline="\n")
        rc, out = _gov(worktree, "check", "--json")
        evidence["turned_red"] = rc == 1 and "mcp_tools 150 != 151" in out
        target.write_text(original, encoding="utf-8", newline="\n")
        rc, _ = _gov(worktree, "check", "--json")
        evidence["restored"] = rc == 0
        _, porcelain = _git(worktree, "status", "--porcelain")
        evidence["worktree_clean"] = porcelain == ""
    finally:
        _teardown(root, worktree)
    return evidence


def case_missing_evidence(root: Path) -> dict[str, Any]:
    """A fabricated PASS without evidence must be judged FAIL (rule 1)."""
    raw = {
        "id": "facts_parity",
        "state": "PASS",
        "reason": "",
        "missing": [],
        "evidence": {"run_id": "x"},  # missing commit_sha/input_hash/ts
    }
    gate = status_mod._judge(raw, {"required": True, "advisory": False}, "")
    return {
        "case": "missing-evidence",
        "broke": True,
        "turned_red": gate["state"] == "FAIL" and gate["reason"] == "missing_evidence",
        "restored": status_mod._judge(
            {
                "id": "facts_parity",
                "state": "PASS",
                "reason": "",
                "missing": [],
                "evidence": {
                    "run_id": "x",
                    "commit_sha": "a",
                    "input_hash": "sha256:same",
                    "ts": "t",
                },
            },
            {"required": True, "advisory": False},
            "sha256:same",
        )["state"]
        == "PASS",
    }


def case_stale_input(root: Path) -> dict[str, Any]:
    """Stored parity evidence with an old input_hash must read STALE."""
    worktree = _clean_worktree(root)
    try:
        gov_dir = worktree / ".autoinfo" / "gov"
        gov_dir.mkdir(parents=True, exist_ok=True)
        (gov_dir / "derived-parity.json").write_text(
            json.dumps({"input_hash": "sha256:stale-stale-stale", "evidence": None}),
            encoding="utf-8",
        )
        contract = load(worktree)
        result = sources_mod.read_gate("derived_parity", contract, {})
        red = result["state"] == "STALE"
        (gov_dir / "derived-parity.json").unlink()
        result = sources_mod.read_gate("derived_parity", contract, {})
        return {
            "case": "stale-input",
            "broke": True,
            "turned_red": red,
            "restored": result["state"] == "NOT_RUN",
            "worktree_clean": _git(worktree, "status", "--porcelain")[1] == "",
        }
    finally:
        _teardown(root, worktree)


def case_adr_unsynced(root: Path) -> dict[str, Any]:
    """An unregistered ADR must turn `gov adr check` red; removal restores."""
    worktree = _clean_worktree(root)
    try:
        ghost = worktree / "docs" / "adr" / "9999-ghost-decision.md"
        ghost.write_text(
            "<!-- doc-type: adr -->\n# 9999. Ghost\n\n- **Status**: Accepted\n"
            "- **Date**: 2026-11-07\n- **Author**: harness\n\n## Context\nnone\n",
            encoding="utf-8",
            newline="\n",
        )
        rc, out = _gov(worktree, "adr", "check", "--json")
        red = rc == 1 and "9999" in out
        ghost.unlink()
        rc, _ = _gov(worktree, "adr", "check", "--json")
        return {
            "case": "adr-unsynced",
            "broke": True,
            "turned_red": red,
            "restored": rc == 0,
            "worktree_clean": _git(worktree, "status", "--porcelain")[1] == "",
        }
    finally:
        _teardown(root, worktree)


def case_escalate_overdue(root: Path) -> dict[str, Any]:
    """A past-deadline escalation makes the gate FAIL; clearing restores PASS."""
    worktree = _clean_worktree(root)
    try:
        (worktree / ".autoinfo" / "gov").mkdir(parents=True, exist_ok=True)
        (worktree / ".autoinfo" / "gov" / "escalations.json").write_text(
            json.dumps(
                {
                    "escalations": [
                        {
                            "item": "acceptance-harness",
                            "receiver": {"role": "human.director", "channel": "github-issue"},
                            "deadline": "2026-01-01T00:00:00Z",
                            "created": "2026-01-01T00:00:00Z",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        contract = load(worktree)
        gate = sources_mod.read_gate("escalations", contract, {})
        red = gate["state"] == "FAIL"
        (worktree / ".autoinfo" / "gov" / "escalations.json").unlink()
        gate = sources_mod.read_gate("escalations", contract, {})
        return {
            "case": "escalate-overdue",
            "broke": True,
            "turned_red": red,
            "restored": gate["state"] == "PASS",
        }
    finally:
        _teardown(root, worktree)


def case_force_pass(root: Path) -> dict[str, Any]:
    """--force-pass must exit 2 with the refusal code, on every verb."""
    rc, out = _gov(root, "status", "--json", "--force-pass")
    refused = rc == EXIT_ENV and "FORCE_PASS_REFUSED" in out
    # Second verb through the alias-free path: same refusal, same exit class.
    rc2, out2 = _gov(root, "escalate", "--item", "x", "--json", "--force-pass")
    refused_everywhere = rc2 == EXIT_ENV and "FORCE_PASS_REFUSED" in out2
    return {
        "case": "force-pass",
        "broke": True,
        "turned_red": refused and refused_everywhere,
        "restored": True,  # nothing to restore — the refusal has no side effects
    }


def case_cloud_forbidden(root: Path) -> dict[str, Any]:
    """The cloud profile must deny the protected push.

    broke = the forbidden action was really exercised through decide();
    turned_red = the deny produced FORBIDDEN; restored = after proving the
    deny rule is the load-bearing piece (removing it flips to ALLOWED), the
    real contract still denies.
    """
    contract = load(root)
    decision = policy_mod.decide(contract.profiles, "cloud", "git:push-protected")
    denied = (
        not decision["allowed"]
        and decision["code"] == "FORBIDDEN"
        and decision["attempted"] is True
    )
    # Deny precedence is the load-bearing rule: a probe that is BOTH allowed
    # and denied must stay FORBIDDEN, and removing the deny flips it ALLOWED.
    # (The real cloud profile is default-deny, so removing its deny alone
    # must NOT widen anything — asserted below.)
    precedence_profiles = {
        "cloud": {"allow": ["git:push-protected"], "deny": ["git:push-protected"]},
    }
    denied_precedence = policy_mod.decide(precedence_profiles, "cloud", "git:push-protected")
    without_deny = {"cloud": {"allow": ["git:push-protected"], "deny": []}}
    flipped = policy_mod.decide(without_deny, "cloud", "git:push-protected")
    deny_is_load_bearing = (
        denied_precedence["code"] == "FORBIDDEN"
        and flipped["allowed"] is True
        and flipped["code"] == "ALLOWED"
    )
    widened = {**contract.profiles, "cloud": {**contract.profiles["cloud"], "deny": []}}
    default_deny_holds = (
        policy_mod.decide(widened, "cloud", "git:push-protected")["code"] == "FORBIDDEN"
    )
    restored = (
        policy_mod.decide(contract.profiles, "cloud", "git:push-protected")["code"] == "FORBIDDEN"
    )
    return {
        "case": "cloud-forbidden",
        "broke": True,
        "turned_red": denied and deny_is_load_bearing and default_deny_holds,
        "restored": restored,
    }


def case_degrade_offline(root: Path) -> dict[str, Any]:
    """The offline drill must flip affected gates non-PASS; turning it off restores.

    The drill is a parameter-scoped simulation, so it observes an injected
    empty artifact directory (#776): machine-local runtime evidence
    (``.autoinfo/gov/derived-parity.json`` etc.) must not turn the baseline
    red and mask what the drill itself does.
    """
    contract = load(root)
    with tempfile.TemporaryDirectory() as tmp:
        sandbox = Path(tmp) / "gov-artifacts"
        sandbox.mkdir()

        saved_artifact_dir = artifacts_mod.artifact_dir
        artifacts_mod.artifact_dir = cast(Any, lambda root: sandbox)
        try:
            return _degrade_offline_evidence(contract)
        finally:
            artifacts_mod.artifact_dir = saved_artifact_dir


def _degrade_offline_evidence(contract: Any) -> dict[str, Any]:
    drilled = status_mod.status(contract, {}, simulate="offline")
    affected = set(drilled["simulation"]["affected_gates"])
    flipped = all(g["state"] != "PASS" for g in drilled["gates"] if g["id"] in affected)
    # Restoration: with the drill OFF the states are exactly the non-drill
    # states (the simulation is parameter-scoped and mutated nothing) and no
    # gate carries drill annotations anymore.
    plain = status_mod.status(contract, {})
    states_off = {g["id"]: g["state"] for g in plain["gates"]}
    states_drilled = {g["id"]: g["state"] for g in drilled["gates"] if "simulated_from" not in g}
    restored = (
        all(states_drilled[g["id"]] == states_off[g["id"]] for g in plain["gates"])
        and not plain["simulation"]
    )
    return {
        "case": "degrade-offline",
        "broke": bool(affected),
        "turned_red": flipped and drilled["verdict"]["overall"] in {"amber", "degraded"},
        "restored": restored,
    }


CASE_RUNNERS = {
    "facts-drift": case_facts_drift,
    "missing-evidence": case_missing_evidence,
    "stale-input": case_stale_input,
    "adr-unsynced": case_adr_unsynced,
    "escalate-overdue": case_escalate_overdue,
    "force-pass": case_force_pass,
    "cloud-forbidden": case_cloud_forbidden,
    "degrade-offline": case_degrade_offline,
}


def run_all(root: Path | None = None, only: str | None = None) -> dict[str, Any]:
    """Run every case (or one); exit 0 only when all three evidences hold."""
    if root is None:
        root = load().root
    results: list[dict[str, Any]] = []
    for name in CASES:
        if only and name != only:
            continue
        runner = CASE_RUNNERS[name]
        try:
            result = runner(root)
        except Exception as exc:  # noqa: BLE001 — a crashing case is a failed case
            result = {
                "case": name,
                "broke": False,
                "turned_red": False,
                "restored": False,
                "error": str(exc),
            }
        result["three_evidences"] = bool(
            result.get("broke") and result.get("turned_red") and result.get("restored")
        )
        results.append(result)
    all_green = bool(results) and all(r["three_evidences"] for r in results)
    return {
        "cases": results,
        "all_three_evidences": all_green,
        "case_count": len(results),
    }
