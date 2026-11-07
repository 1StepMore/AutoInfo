"""T12/T15/T16 tests: capability boundary, degradation drills, escalations."""

from __future__ import annotations

import json
from typing import Any

import pytest

from autoinfo.gov import acceptance as acceptance_mod
from autoinfo.gov import degrade as degrade_mod
from autoinfo.gov import escalate as escalate_mod
from autoinfo.gov import policy as policy_mod
from autoinfo.gov.__main__ import EXIT_OK, EXIT_RED, main
from autoinfo.gov.contract import load

PROFILES: dict[str, dict[str, list[str]]] = {
    "cloud": {
        "allow": ["read:repo", "write:workspace", "run:gov-*"],
        "deny": ["git:push-protected", "secret:read", "path:outside-workspace"],
    },
    "local": {"allow": ["*"], "deny": []},
}


class TestPolicy:
    def test_cloud_forbidden_probe_is_denied_and_attempted(self, tmp_path: Any) -> None:
        decision = policy_mod.decide(PROFILES, "cloud", "git:push-protected", log_dir=tmp_path)
        assert decision["allowed"] is False
        assert decision["code"] == "FORBIDDEN"
        assert decision["attempted"] is True  # the request really reached decide()
        log = (tmp_path / "attempts.jsonl").read_text(encoding="utf-8").splitlines()
        assert len(log) == 1 and json.loads(log[0])["action"] == "git:push-protected"

    def test_local_allows_the_same_probe(self, tmp_path: Any) -> None:
        decision = policy_mod.decide(PROFILES, "local", "git:push-protected", log_dir=tmp_path)
        assert decision["allowed"] is True
        assert decision["code"] == "ALLOWED"

    def test_cloud_allows_gov_prefix_read_and_write(self, tmp_path: Any) -> None:
        assert policy_mod.decide(PROFILES, "cloud", "read:repo", log_dir=tmp_path)["allowed"]
        assert policy_mod.decide(PROFILES, "cloud", "run:gov-check", log_dir=tmp_path)["allowed"]

    def test_unknown_profile_is_not_attempted(self) -> None:
        decision = policy_mod.decide(PROFILES, "nope", "read:repo")
        assert decision["attempted"] is False
        assert decision["code"] == "UNKNOWN_PROFILE"

    def test_default_deny_for_unlisted_action(self) -> None:
        decision = policy_mod.decide(PROFILES, "cloud", "deploy:prod")
        assert decision["allowed"] is False
        assert decision["code"] == "FORBIDDEN"

    def test_diff_profiles_structurally_empty(self) -> None:
        assert policy_mod.diff_profiles(PROFILES) == []

    def test_diff_profiles_flags_key_set_drift(self) -> None:
        broken = {**PROFILES, "edge": {"allow": ["*"]}}
        diffs = policy_mod.diff_profiles(broken)
        assert diffs and "edge" in diffs[0]


class TestRunVerb:
    def test_cloud_forbidden_exits_nonzero_with_code(self, capsys: Any) -> None:
        rc = main(["run", "--mode", "cloud", "--probe", "git:push-protected", "--json"])
        assert rc == EXIT_RED
        payload = json.loads(capsys.readouterr().out.strip())
        assert payload["code"] == "FORBIDDEN"
        assert payload["attempted"] is True

    def test_local_allowed_exits_zero(self, capsys: Any) -> None:
        rc = main(["run", "--mode", "local", "--probe", "git:push-protected", "--json"])
        assert rc == EXIT_OK
        payload = json.loads(capsys.readouterr().out.strip())
        assert payload["code"] == "ALLOWED"

    def test_diff_profiles_empty(self, capsys: Any) -> None:
        rc = main(["run", "--diff-profiles", "--json"])
        assert rc == EXIT_OK
        assert json.loads(capsys.readouterr().out.strip())["diff"] == []


class TestDegrade:
    def test_offline_flips_network_gates(self) -> None:
        affected = degrade_mod.affected_gates(list(degrade_mod.GATE_DEPS), "offline")
        assert {"derived_parity", "known_red", "preview_smoke", "coverage_base"} <= set(affected)

    def test_simulation_flips_pass_to_unconfigured(self) -> None:
        raw = {"id": "known_red", "state": "PASS", "reason": "", "missing": []}
        drilled = degrade_mod.apply_simulation(raw, "offline")
        assert drilled["state"] == "UNCONFIGURED"
        assert drilled["simulated_from"] == "PASS"
        assert "network" in drilled["missing"]

    def test_simulation_never_upgrades_a_non_pass(self) -> None:
        raw = {"id": "known_red", "state": "FAIL", "reason": "budget", "missing": []}
        drilled = degrade_mod.apply_simulation(raw, "offline")
        assert drilled["state"] == "FAIL"

    def test_no_key_drill_is_explicitly_empty(self) -> None:
        affected = degrade_mod.affected_gates(list(degrade_mod.GATE_DEPS), "no-key")
        assert affected == []  # no gov instrument is key-bound today (BYOK-free)

    def test_status_simulate_is_at_least_amber(self) -> None:
        contract = load()
        report = status_with(contract, "no-key")
        assert report["verdict"]["overall"] in {"amber", "degraded"}
        assert report["simulation"]["mode"] == "no-key"

    def test_status_simulate_offline_has_no_pass_in_affected(self) -> None:
        contract = load()
        report = status_with(contract, "offline")
        affected = set(report["simulation"]["affected_gates"])
        for gate in report["gates"]:
            if gate["id"] in affected:
                assert gate["state"] != "PASS"


def status_with(contract: Any, mode: str) -> Any:
    from autoinfo.gov import status as status_mod

    return status_mod.status(contract, {}, simulate=mode)


class TestEscalate:
    def test_escalation_roundtrip_and_overdue(self, tmp_path: Any) -> None:
        contract = load()
        proxy = SimpleRoot(contract, tmp_path)
        record = escalate_mod.escalate(proxy, "acceptance-1.21.17")  # type: ignore[arg-type]
        assert record["receiver"]["role"] == "human.director"
        assert record["receiver"]["role"] != "executor.profile"
        assert record["deadline"]
        assert record["escalation"]["state"] == "PENDING"
        chased = escalate_mod.escalate(proxy, "acceptance-1.21.17", deadline="2026-01-01T00:00:00Z")  # type: ignore[arg-type]
        assert chased["escalation"]["state"] == "OVERDUE"

    def test_executor_role_refused(self, tmp_path: Any) -> None:
        contract = load()
        proxy = SimpleRoot(contract, tmp_path)
        with pytest.raises(escalate_mod.EscalationError, match="executor.profile"):
            escalate_mod.escalate(proxy, "x", role="executor.profile")  # type: ignore[arg-type]

    def test_overdue_deadline_is_exit_red_with_gate_fail(self, tmp_path: Any, capsys: Any) -> None:
        """DoD #9: past deadline -> escalation OVERDUE, gate FAIL, never PASS."""
        contract = load()
        proxy = SimpleRoot(contract, tmp_path)
        escalate_mod.escalate(proxy, "acc-1", deadline="2026-01-01T00:00:00Z")  # type: ignore[arg-type]
        # Re-point the repo root through the store the CLI actually reads:
        # the CLI loads the real contract, so drive the store file instead.
        store_dir = contract.root / ".autoinfo" / "gov"
        store_dir.mkdir(parents=True, exist_ok=True)
        (store_dir / "escalations.json").write_text(
            (tmp_path / ".autoinfo" / "gov" / "escalations.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        try:
            rc = main(["escalate", "--item", "acc-1", "--json"])
            assert rc == EXIT_RED
            payload = json.loads(capsys.readouterr().out.strip())
            assert payload["escalation"]["state"] == "OVERDUE"
            assert payload["gate"]["state"] == "FAIL"
        finally:
            (store_dir / "escalations.json").unlink()

    def test_status_never_folds_open_escalation_to_pass(self, tmp_path: Any) -> None:
        contract = load()
        proxy = SimpleRoot(contract, tmp_path)
        escalate_mod.escalate(proxy, "acc-2")  # type: ignore[arg-type]
        from autoinfo.gov import sources

        gate = sources.read_gate("escalations", proxy, {})  # type: ignore[arg-type]
        assert gate["state"] == "FAIL"
        assert "never folded" in gate["reason"]


class TestAcceptanceBridge:
    def test_bridge_imports_human_reserved_without_rewriting(self) -> None:
        data = acceptance_mod.check()
        assert data["human_reserved"] == ["AC3-human", "AC5-director", "overall"]
        assert data["reserved_token"]["overall"] == "PENDING DIRECTOR SIGN-OFF"
        assert data["machine_refusal_works"] is True

    def test_machine_allowed_refuses_human_ids(self) -> None:
        with pytest.raises(ValueError, match="human-reserved"):
            acceptance_mod.assert_machine_allowed("overall")

    def test_machine_allowed_passes_machine_ids(self) -> None:
        acceptance_mod.assert_machine_allowed("AC1")


class SimpleRoot:
    """Read-only stand-in exposing .root on a frozen Contract."""

    def __init__(self, contract: Any, root: Any) -> None:
        self._contract = contract
        self.root = root

    def __getattr__(self, name: str) -> Any:
        return getattr(self._contract, name)


def test_scripts_verb_reports_clean_registry() -> None:
    assert main(["scripts", "--json"]) == EXIT_OK
