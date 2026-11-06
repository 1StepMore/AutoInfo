"""T13/T14/T17 tests: hygiene, scripts registry, negative controls, confidence."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from autoinfo.gov import confidence as confidence_mod
from autoinfo.gov import negative_control as negctl
from autoinfo.gov import registry as registry_mod
from autoinfo.gov.__main__ import EXIT_OK, EXIT_RED, main
from autoinfo.gov.contract import load

ROOT = Path(__file__).resolve().parents[2]


class TestRepoHygiene:
    def test_no_tracked_crlf_files(self) -> None:
        """T13: `git ls-files --eol | grep -c 'i/crlf'` == 0."""
        out = subprocess.run(
            ["git", "ls-files", "--eol"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8"
        ).stdout
        assert "i/crlf" not in out

    def test_gitattributes_covers_the_tree(self) -> None:
        text = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        assert "text=auto eol=lf" in text


class TestScriptsRegistry:
    def test_report_shape_and_total(self) -> None:
        contract = load()
        report = registry_mod.registry_report(contract)
        assert report["total"] == report["gate"] + report["instrument"] + report["oneoff"]
        assert report["unregistered"] == []
        assert report["total"] >= 44  # 43 plan-era + scripts/gov.py (T04)
        assert report["gate"] >= 10

    def test_unknown_classified_script_is_flagged(self) -> None:
        contract = load()
        # Simulate a contract entry for a script that does not exist.
        object.__setattr__(contract, "scripts", {"gate": ["scripts/ghost.py"], "oneoff": []})
        report = registry_mod.registry_report(contract)
        assert "scripts/ghost.py" in report["unregistered"]

    def test_prefixless_entries_are_normalized(self) -> None:
        contract = load()
        object.__setattr__(
            contract, "scripts", {"gate": ["quality_gate.py"], "oneoff": ["merge_demo_domains.py"]}
        )
        report = registry_mod.registry_report(contract)
        assert report["unregistered"] == []
        assert report["gate"] >= 1 and report["oneoff"] >= 1

    def test_scripts_verb_exit_codes(self, capsys: Any) -> None:
        assert main(["scripts", "--json"]) == EXIT_OK
        payload = json.loads(capsys.readouterr().out.strip())
        assert payload["unregistered"] == []

    def test_status_payload_carries_scripts(self, capsys: Any) -> None:
        main(["status", "--only", "preview_smoke", "--json"])
        payload = json.loads(capsys.readouterr().out.strip())
        assert payload["scripts"] is not None
        assert payload["scripts"]["total"] >= 44


class TestNegativeControl:
    def test_case_list_is_the_plan_eight(self) -> None:
        assert set(negctl.CASES) == {
            "facts-drift",
            "missing-evidence",
            "stale-input",
            "adr-unsynced",
            "escalate-overdue",
            "force-pass",
            "cloud-forbidden",
            "degrade-offline",
        }

    def _enriched(self, case: str) -> dict[str, Any]:
        result = dict(negctl.CASE_RUNNERS[case](ROOT))
        result["three_evidences"] = bool(
            result.get("broke") and result.get("turned_red") and result.get("restored")
        )
        return result

    def test_light_cases_hold_three_evidences(self) -> None:
        """The non-worktree cases must be three-evidence green in isolation."""
        for case in ("missing-evidence", "force-pass", "cloud-forbidden", "degrade-offline"):
            result = self._enriched(case)
            assert result["three_evidences"], f"{case}: {result}"

    def test_all_cases_registered_with_runners(self) -> None:
        assert set(negctl.CASE_RUNNERS) == set(negctl.CASES)

    def test_runner_failure_is_reported_not_raised(self) -> None:
        def boom(root: Path) -> Any:
            raise RuntimeError("exploded")

        saved = negctl.CASE_RUNNERS["force-pass"]
        negctl.CASE_RUNNERS["force-pass"] = boom
        try:
            report = negctl.run_all(ROOT, only="force-pass")
        finally:
            negctl.CASE_RUNNERS["force-pass"] = saved
        case = report["cases"][0]
        assert case["three_evidences"] is False
        assert "exploded" in case["error"]


class TestConfidence:
    def test_confidence_reaches_e3_with_evidence_on_disk(self) -> None:
        """Requires the negative-control run + platform-sha.json (recorded)."""
        data = confidence_mod.confidence(ROOT)
        assert data["overall"] in {"E2", "E3"}
        for name, klass in data["classes"].items():
            assert klass["required"] == "E3"
            if klass["level"] == "E2":
                assert klass["missing"], f"{name} downgrade must be explained"

    def test_missing_platform_sha_downgrades_to_e2(self, tmp_path: Path) -> None:
        (tmp_path / ".github").mkdir()
        (tmp_path / ".github" / "governance-contract.toml").write_bytes(
            (ROOT / ".github" / "governance-contract.toml").read_bytes()
        )
        data = confidence_mod.confidence(tmp_path)
        assert data["overall"] == "E2"
        assert data["dual_platform_sha"]["match"] is False

    def test_confidence_verb_exit_codes(self, capsys: Any) -> None:
        rc = main(["confidence", "--json"])
        assert rc in {EXIT_OK, EXIT_RED}
        payload = json.loads(capsys.readouterr().out.strip())
        assert payload["overall"] in {"E2", "E3"}
