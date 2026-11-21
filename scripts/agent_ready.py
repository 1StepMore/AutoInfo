#!/usr/bin/env python3
"""Agent-ready entrypoint: one command every agent runs FIRST (#884).

Answers the first question of any shift: **can I work in this repo right
now, and what is my next action?**  Aggregates the existing checks instead
of asking the agent to read documents and guess:

- venv            interpreter sanity + venv presence (blocked:no-venv)
- deps            declared python deps installed (via scripts/check_deps.py
                  probe, reused verbatim) (blocked:missing-dep)
- llm             model ladder, implemented in code (blocked:no-llm-key)
- docs            doc-inventory gate (degraded = run doc_inventory.py)
- matrix-evidence P2 evidence root parses (degraded = evidence missing)

Contract (issue #884, executable spec):

    {"schema": "agent-ready/v1", "ok": bool, "checks": [...],
     "next_action": str}

- status vocabulary: ok | degraded | blocked
- code vocabulary:   ok | blocked:no-llm-key | blocked:missing-dep |
                     blocked:no-venv | blocked:not-onboarded
- exit codes: 0 green (degraded allowed) / 2 no-llm-key / 3 missing-dep /
  4 other blocked.  Precedence: 2 > 3 > 4.

Design constraints (hard, mirrors check_deps.py):
- stdlib only; runs on Windows and POSIX; --json for machine readers;
- never touches the network; never mutates any state; never prints values
  of secrets — presence only; no vendor hardcoding (the ladder probes are
  protocol names, not vendor names).

Usage::

    python scripts/agent_ready.py            # human-readable
    python scripts/agent_ready.py --json     # machine-readable contract
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

SCHEMA = "agent-ready/v1"

# Exit codes (issue #884): 0 green / 2 no-llm-checks / 3 missing-dep / 4 other.
EXIT_OK = 0
EXIT_NO_LLM_KEY = 2
EXIT_MISSING_DEP = 3
EXIT_OTHER_BLOCKED = 4


# ---------------------------------------------------------------------------
# venv / deps
# ---------------------------------------------------------------------------


def _load_check_deps() -> Any:
    """Load scripts/check_deps.py as a module (scripts/ is not a package)."""
    script = Path(__file__).resolve().parent / "check_deps.py"
    spec = importlib.util.spec_from_file_location("check_deps", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_deps"] = module
    spec.loader.exec_module(module)
    return module


def check_venv() -> dict[str, Any]:
    """venv presence: VIRTUAL_ENV env or the repo-root .venv directory."""
    if os.environ.get("VIRTUAL_ENV") or (REPO_ROOT / ".venv").is_dir():
        return {
            "id": "venv",
            "status": "ok",
            "code": "ok",
            "detail": "interpreter runs; venv present",
        }
    return {
        "id": "venv",
        "status": "blocked",
        "code": "blocked:no-venv",
        "detail": "no VIRTUAL_ENV and no .venv/ at repo root",
        "remedy": 'python -m venv .venv && pip install -e ".[dev,ebook]"',
    }


def check_deps_state() -> dict[str, Any]:
    """Declared python deps installed?  Reuses the check_deps probe verbatim."""
    report = _load_check_deps().collect()
    missing = list(report["python_deps"]["core_missing"])
    if not missing:
        return {
            "id": "deps",
            "status": "ok",
            "code": "ok",
            "detail": "all declared python deps importable",
        }
    return {
        "id": "deps",
        "status": "blocked",
        "code": "blocked:missing-dep",
        "detail": "missing python deps: " + ", ".join(missing[:8]),
        "remedy": 'pip install -e ".[dev,ebook]"',
    }


# ---------------------------------------------------------------------------
# llm ladder (issue #884: implemented in code, no vendor hardcoding)
# ---------------------------------------------------------------------------

# Step-1 probe: an OpenAI-compatible harness injection contract.  These are
# protocol-standard variable names, not vendor names — a harness that can
# inject a model into subprocesses exposes them; nothing here is厂商-specific.
_HARNESS_ENDPOINT_VARS = ("OPENAI_BASE_URL", "OPENAI_API_BASE")
_HARNESS_KEY_VARS = ("OPENAI_API_KEY",)


def _config_llm_reference() -> str | None:
    """Resolve the repo config's llm.api_key ${ENV} reference (presence only).

    Returns the env-var NAME the config references (BYOK contract), or None
    when the config is absent/unreadable — never the value.
    """
    config_path = REPO_ROOT / ".autoinfo" / "config.yaml"
    if not config_path.is_file():
        return None
    try:
        import yaml  # PyYAML is a project dependency

        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        llm = raw.get("llm") or {}
        api_key = llm.get("api_key") or ""
        if api_key.startswith("${") and api_key.endswith("}"):
            return api_key[2:-1]
    except Exception:
        return None
    return None


def check_llm() -> dict[str, Any]:
    """Model ladder (issue #884): harness default -> machine endpoint -> ask."""
    ladder: list[dict[str, Any]] = []

    step1 = "absent"
    if any(os.environ.get(v) for v in _HARNESS_ENDPOINT_VARS) and any(
        os.environ.get(v) for v in _HARNESS_KEY_VARS
    ):
        step1 = "present"
    ladder.append({"step": 1, "probe": "harness-default", "result": step1})

    step2 = "absent"
    if os.environ.get("AUTOINFO_LLM_API_KEY"):
        step2 = "present"
    else:
        ref = _config_llm_reference()
        if ref and os.environ.get(ref):
            step2 = f"present (config llm.api_key -> ${{{ref}}})"
    ladder.append({"step": 2, "probe": "machine-endpoint", "result": step2})

    ladder.append({"step": 3, "probe": "ask-human", "result": "required"})

    if step1 == "present" or step2.startswith("present"):
        return {
            "id": "llm",
            "status": "ok",
            "code": "ok",
            "detail": "usable model resolved via ladder step "
            + ("1" if step1 == "present" else "2"),
            "ladder": ladder,
        }
    return {
        "id": "llm",
        "status": "blocked",
        "code": "blocked:no-llm-key",
        "detail": "no usable model on ladder steps 1-2",
        "ladder": ladder,
        "remedy": "provide base_url + key + model (ask the human on step 3)",
    }


# ---------------------------------------------------------------------------
# docs gate / matrix evidence
# ---------------------------------------------------------------------------


def check_docs() -> dict[str, Any]:
    """Doc-inventory gate: exit 0 = ok, anything else = degraded (advisory)."""
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parent / "doc_inventory.py"), "--check"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return {
            "id": "docs",
            "status": "ok",
            "code": "ok",
            "detail": "doc_inventory --check exit 0",
        }
    tail = (result.stdout or result.stderr or "").strip().splitlines()[-1:]
    return {
        "id": "docs",
        "status": "degraded",
        "code": "ok",
        "detail": "doc_inventory --check failed: " + ("; ".join(tail) or "see the gate output"),
        "remedy": "python scripts/doc_inventory.py",
    }


def check_matrix_evidence() -> dict[str, Any]:
    """P2 evidence root parses (advisory: absent evidence degrades, not blocks)."""
    evidence = REPO_ROOT / "docs/dev/validation-reports/capability-27x3/matrix.json"
    if not evidence.is_file():
        return {
            "id": "matrix-evidence",
            "status": "degraded",
            "code": "ok",
            "detail": "P2 evidence root not found: " + str(evidence.relative_to(REPO_ROOT)),
            "remedy": "python scripts/capability_matrix.py --domains ... (owner-directed)",
        }
    try:
        json.loads(evidence.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "id": "matrix-evidence",
            "status": "degraded",
            "code": "ok",
            "detail": f"evidence root does not parse: {exc}",
        }
    return {
        "id": "matrix-evidence",
        "status": "ok",
        "code": "ok",
        "detail": "P2 evidence root parses",
    }


# ---------------------------------------------------------------------------
# assembly
# ---------------------------------------------------------------------------


def collect_checks() -> list[dict[str, Any]]:
    """Run every check; a broken check must not kill the whole entrypoint."""
    checks: list[dict[str, Any]] = []
    for fn in (check_venv, check_deps_state, check_llm, check_docs, check_matrix_evidence):
        try:
            checks.append(fn())
        except Exception as exc:
            checks.append(
                {
                    "id": fn.__name__.removeprefix("check_"),
                    "status": "degraded",
                    "code": "ok",
                    "detail": f"check itself failed: {exc.__class__.__name__}: {exc}",
                }
            )
    return checks


def exit_code_for(checks: list[dict[str, Any]]) -> int:
    """Issue #884 mapping: 0 green / 2 no-llm-key / 3 missing-dep / 4 other."""
    codes = [c["code"] for c in checks if c.get("status") == "blocked"]
    if "blocked:no-llm-key" in codes:
        return EXIT_NO_LLM_KEY
    if "blocked:missing-dep" in codes:
        return EXIT_MISSING_DEP
    if codes:
        return EXIT_OTHER_BLOCKED
    return EXIT_OK


def build_report() -> dict[str, Any]:
    checks = collect_checks()
    blocked = [c for c in checks if c.get("status") == "blocked"]
    next_action = (
        blocked[0].get("remedy") or blocked[0]["detail"]
        if blocked
        else "run the goal gate: python scripts/agent/autonomy.py gate"
    )
    return {
        "schema": SCHEMA,
        "ok": not blocked,
        "checks": checks,
        "next_action": next_action,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="machine-readable contract")
    args = parser.parse_args()
    report = build_report()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for c in report["checks"]:
            mark = {"ok": "OK ", "degraded": "WARN", "blocked": "FAIL"}[c["status"]]
            print(f"[{mark}] {c['id']}: {c['code']} - {c['detail']}")
        print(f"next_action: {report['next_action']}")
    return exit_code_for(report["checks"])


if __name__ == "__main__":
    sys.exit(main())
