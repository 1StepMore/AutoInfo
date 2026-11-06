"""Per-gate read-only source readers (T06).

Every reader returns a state dict; a reader that cannot run reports
``UNMEASURED`` + reason instead of raising — an unstable instrument is honest
degradation, never a crash and never a fake pass.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any, Callable

from autoinfo.gov import artifacts
from autoinfo.gov.contract import Contract

#: Gates whose readers live here; status.py dispatches by gate id.
PARITY_ARTIFACT = "derived-parity.json"


def _fresh_evidence(contract: Contract, input_hash: str) -> dict[str, Any]:
    return artifacts.evidence(contract.root, contract.version, {"_": input_hash}) | {
        "input_hash": input_hash
    }


def _ruff_failures(root: Path) -> tuple[int, str]:
    """Run the full-tree ruff exactly like ci.yml's informational step."""
    try:
        proc = subprocess.run(
            ["ruff", "check", "src/", "tests/", "--exit-zero", "--output-format", "concise"],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return -1, f"ruff failed to run: {exc}"
    # concise lines are "path:line:col: CODE message"; ruff's summary lines
    # ("All checks passed!", "Found N errors.") must not count as findings.
    finding = re.compile(r"^\S+:\d+:\d+: [A-Z]+[0-9]+ ")
    lines = [ln for ln in proc.stdout.splitlines() if finding.match(ln)]
    return len(lines), proc.stdout


def read_facts_parity(contract: Contract, derived: dict[str, Any]) -> dict[str, Any]:
    """facts_parity: derive + full-repo scan, fresh every run."""
    del derived  # symmetric signature with the other readers
    from autoinfo.gov import facts as facts_mod

    result = facts_mod.check(contract.root)
    ih = str(result["input_hash"])
    violations = list(result["violations"])
    state = "PASS" if result["fail"] == 0 else "FAIL"
    return {
        "state": state,
        "reason": "" if state == "PASS" else f"{len(violations)} drift violation(s)",
        "missing": [],
        "evidence": _fresh_evidence(contract, ih),
        "violations": violations,
        "facts": result["facts"],
        "files_scanned": result["files_scanned"],
    }


def read_ruff_full(contract: Contract, derived: dict[str, Any]) -> dict[str, Any]:
    """ruff_full: informational full-tree lint — advisory, never blocks."""
    failures, output = _ruff_failures(contract.root)
    if failures < 0:
        return {
            "state": "UNMEASURED",
            "reason": output,
            "missing": ["ruff"],
            "evidence": None,
        }
    ih = artifacts.input_hash(contract.version, derived)
    state = "PASS" if failures == 0 else "ADVISORY"
    return {
        "state": state,
        "reason": "" if failures == 0 else f"{failures} pre-existing full-tree ruff finding(s)",
        "missing": [],
        "evidence": _fresh_evidence(contract, ih),
        "failures": failures,
        "output_tail": output.splitlines()[-5:],
    }


def read_derived_parity(contract: Contract, derived: dict[str, Any]) -> dict[str, Any]:
    """derived_parity: CI-written parity evidence, STALE-checked against now.

    The guard.yml step (T09, report-only first) writes derived-parity.json
    after its own gov check; this reader replays it. No artifact → NOT_RUN
    (the contract carries the not_run_allowed_reason).
    """
    path = artifacts.artifact_dir(contract.root) / PARITY_ARTIFACT
    if not path.is_file():
        return {
            "state": "NOT_RUN",
            "reason": "no derived-parity evidence yet (guard.yml writes it; report-only)"
            if contract.gates.get("derived_parity", {}).get("not_run_allowed_reason")
            else "no derived-parity evidence",
            "missing": [PARITY_ARTIFACT],
            "evidence": None,
        }
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "state": "UNMEASURED",
            "reason": f"unreadable parity artifact: {exc}",
            "missing": [],
            "evidence": None,
        }
    current_ih = artifacts.input_hash(contract.version, derived)
    stored_ih = str(stored.get("input_hash", ""))
    if stored_ih != current_ih:
        return {
            "state": "STALE",
            "reason": f"stored parity input_hash {stored_ih[:16]} != current {current_ih[:16]}"
            " — rerun gov check",
            "missing": [],
            "evidence": stored.get("evidence"),
        }
    return {
        "state": "PASS",
        "reason": "",
        "missing": [],
        "evidence": stored.get("evidence") or _fresh_evidence(contract, current_ih),
    }


def read_preview_smoke(contract: Contract, derived: dict[str, Any]) -> dict[str, Any]:
    """preview_smoke: advisory manual instrument; NOT_RUN never blocks."""
    del derived
    return {
        "state": "NOT_RUN",
        "reason": "advisory manual instrument (scripts/preview_smoke.sh); not part of PR CI",
        "missing": [],
        "evidence": None,
    }


def read_known_red(contract: Contract, derived: dict[str, Any]) -> dict[str, Any]:
    """known_red: budget consumer over tests/TRIAGE.md (wired fully in T08)."""
    triage = contract.root / "tests" / "TRIAGE.md"
    if not triage.is_file():
        return {
            "state": "UNCONFIGURED",
            "reason": "tests/TRIAGE.md missing",
            "missing": ["tests/TRIAGE.md"],
            "evidence": None,
        }
    if "```known-red-budget" not in triage.read_text(encoding="utf-8", errors="replace"):
        return {
            "state": "UNCONFIGURED",
            "reason": "no ```known-red-budget block in tests/TRIAGE.md yet (T08 wires the budget)",
            "missing": ["```known-red-budget"],
            "evidence": None,
        }
    budget = _parse_known_red_budget(triage)
    observed = _observed_failures(contract.root)
    ih = artifacts.input_hash(contract.version, derived)
    if budget is None:
        return {
            "state": "UNCONFIGURED",
            "reason": "known-red-budget block has no `count` key",
            "missing": ["count"],
            "evidence": None,
        }
    if observed is None:
        return {
            "state": "NOT_RUN",
            "reason": "budget parsed but no nightly junit.xml present — observed unknown",
            "missing": ["nightly-junit.xml"],
            "evidence": None,
            "budget": budget,
            "observed": None,
        }
    state = "PASS" if observed <= budget else "FAIL"
    return {
        "state": state,
        "reason": "" if state == "PASS" else f"observed failures {observed} exceed budget {budget}",
        "missing": [],
        "evidence": _fresh_evidence(contract, ih),
        "budget": budget,
        "observed": observed,
        "delta": observed - budget,
    }


def _parse_known_red_budget(triage: Path) -> int | None:
    """Parse the fenced ```known-red-budget block (count = N)."""
    text = triage.read_text(encoding="utf-8", errors="replace")
    marker = "```known-red-budget"
    start = text.find(marker)
    if start == -1:
        return None
    end = text.find("```", start + len(marker))
    if end == -1:
        return None
    body = text[start + len(marker) : end]
    for line in body.splitlines():
        key, sep, value = line.partition("=")
        if sep and key.strip() == "count":
            try:
                return int(value.strip())
            except ValueError:
                return None
    return None


def _observed_failures(root: Path) -> int | None:
    """Failures+errors from the nightly junit.xml (None when absent/unreadable)."""
    path = root / "nightly-junit.xml"
    if not path.is_file():
        return None
    try:
        import xml.etree.ElementTree as ET

        root_el = ET.parse(path).getroot()
        suite = root_el if root_el.tag == "testsuite" else root_el.find(".//testsuite")
        if suite is None:
            return None
        failures = int(suite.get("failures", "0"))
        errors = int(suite.get("errors", "0"))
    except (OSError, ET.ParseError, ValueError):
        return None
    return failures + errors


def read_coverage_base(contract: Contract, derived: dict[str, Any]) -> dict[str, Any]:
    """coverage_base: the swallowed base-suite exit from coverage.yml (T07).

    coverage.yml measures the merge-base suite and MUST NOT abort on its
    failure (immutable history). That exit code used to vanish; the workflow
    now persists it to .autoinfo/gov/coverage-base.json, and this reader turns
    a non-zero base exit into DEGRADED — visible, never blocking, never fake.
    """
    del derived
    path = artifacts.artifact_dir(contract.root) / "coverage-base.json"
    if not path.is_file():
        return {
            "state": "NOT_RUN",
            "reason": "no coverage-base evidence yet (coverage.yml writes it on PR runs)",
            "missing": ["coverage-base.json"],
            "evidence": None,
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "state": "UNMEASURED",
            "reason": f"unreadable coverage-base artifact: {exc}",
            "missing": [],
            "evidence": None,
        }
    exit_code_val = int(data.get("base_suite_exit", -1))
    if exit_code_val != 0:
        return {
            "state": "DEGRADED",
            "reason": f"base suite exited {exit_code_val} at {data.get('base_sha', 'unknown')}"
            " — gate still measured, failure made visible",
            "missing": [],
            "evidence": None,
            "base_suite_exit": exit_code_val,
        }
    return {
        "state": "PASS",
        "reason": "",
        "missing": [],
        "evidence": None,
        "base_suite_exit": 0,
    }


READERS: dict[str, Callable[[Contract, dict[str, Any]], dict[str, Any]]] = {
    "facts_parity": read_facts_parity,
    "ruff_full": read_ruff_full,
    "derived_parity": read_derived_parity,
    "preview_smoke": read_preview_smoke,
    "known_red": read_known_red,
    "coverage_base": read_coverage_base,
}


def read_gate(
    gate_id: str,
    contract: Contract,
    derived: dict[str, Any],
) -> dict[str, Any]:
    """Dispatch to a reader; ANY reader failure degrades to UNMEASURED."""
    reader = READERS.get(gate_id)
    if reader is None:
        return {
            "state": "UNMEASURED",
            "reason": f"no source reader registered for gate {gate_id!r}",
            "missing": [f"reader:{gate_id}"],
            "evidence": None,
        }
    try:
        return reader(contract, derived)
    except Exception as exc:  # noqa: BLE001 — readers must never raise
        return {
            "state": "UNMEASURED",
            "reason": f"reader {gate_id!r} failed: {type(exc).__name__}: {exc}",
            "missing": [f"reader:{gate_id}"],
            "evidence": None,
        }
