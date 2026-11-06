"""Confidence grading (T17) — E2/E3, honest downgrades.

- **E2** = the artifact exists and its evidence carries all four fields.
- **E3** = E2 **plus** the negative control proved the mechanism turns red,
  **plus** the dual-platform ``facts.json`` sha256 comparison matched.

Three classes are FORCED to E3 by the plan (§2): derived-fact mechanisms,
human-judgment mechanisms, and platform-consistency mechanisms. A class
missing any E3 ingredient reports E2 with the exact missing item — a
downgrade is always explainable, never hidden.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from autoinfo.gov import artifacts as artifacts_mod
from autoinfo.gov import negative_control as negctl
from autoinfo.gov.contract import Contract, load

#: mechanism class → the negative-control cases that prove it turns red.
CLASS_CASES: dict[str, tuple[str, ...]] = {
    "derived_facts": ("facts-drift", "stale-input"),
    "human_judgment": ("missing-evidence", "escalate-overdue", "force-pass"),
    "platform_consistency": ("cloud-forbidden", "degrade-offline", "adr-unsynced"),
}

PLATFORM_SHA_ARTIFACT = "platform-sha.json"


def _artifacts_healthy(root: Path) -> tuple[bool, list[str]]:
    missing: list[str] = []
    facts = artifacts_mod.load_cached_facts(root)
    evidence = artifacts_mod.load_cached_evidence(root)
    if facts is None:
        missing.append("facts.json")
    if evidence is None:
        missing.append("evidence.json")
    else:
        for field in ("run_id", "commit_sha", "input_hash", "ts"):
            if not evidence.get(field):
                missing.append(f"evidence.{field}")
    return not missing, missing


def _platform_sha_match(root: Path) -> tuple[bool, str]:
    """Dual-platform sha evidence (DoD #5). Honest: absent artifact = not proven."""
    path = artifacts_mod.artifact_dir(root) / PLATFORM_SHA_ARTIFACT
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, (
            f"no {PLATFORM_SHA_ARTIFACT} — run derive on both platforms and record the shas"
        )
    match = bool(data.get("match")) and data.get("windows_sha") and data.get("wsl_sha")
    return bool(match), "" if match else "platform-sha.json records a mismatch"


def confidence(root: Path | None = None) -> dict[str, Any]:
    """Grade every forced-E3 class (plus the overall level)."""
    contract: Contract = load(root) if root else load()
    root_path = contract.root
    artifacts_ok, artifacts_missing = _artifacts_healthy(root_path)
    sha_ok, sha_reason = _platform_sha_match(root_path)
    negctl_results = negctl.run_all(root_path)
    negctl_by_case = {c["case"]: c for c in negctl_results["cases"]}

    classes: dict[str, Any] = {}
    for class_name, cases in CLASS_CASES.items():
        missing: list[str] = []
        if not artifacts_ok:
            missing.extend(f"artifact:{m}" for m in artifacts_missing)
        for case in cases:
            result = negctl_by_case.get(case)
            if result is None or not result.get("three_evidences"):
                missing.append(f"negative-control:{case}")
        if class_name == "platform_consistency" and not sha_ok:
            missing.append(f"dual-platform-sha:{sha_reason}")
        level = "E3" if not missing else "E2"
        classes[class_name] = {
            "level": level,
            "required": "E3",
            "meets_requirement": level == "E3",
            "missing": missing,
        }

    overall = "E3" if all(c["meets_requirement"] for c in classes.values()) else "E2"
    return {
        "overall": overall,
        "classes": classes,
        "negative_controls": {
            "all_three_evidences": negctl_results["all_three_evidences"],
            "case_count": negctl_results["case_count"],
        },
        "artifacts": {"present": artifacts_ok, "missing": artifacts_missing},
        "dual_platform_sha": {"match": sha_ok, "reason": sha_reason},
    }
