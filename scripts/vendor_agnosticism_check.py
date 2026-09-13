#!/usr/bin/env python3
"""Model/vendor agnosticism contract check (T-S-12; AGENTS #194/#195).

Run from the project root::

    python3 scripts/vendor_agnosticism_check.py

The invariant (AGENTS.md #194/#195): the judge/battery paths must carry **no
hardcoded vendor or model name**, and judgment-model resolution must be
**config-first** — ``llm.judgment_model`` → ``llm.model`` → loud error, never
a code constant.  This script makes that contract executable:

1. No ``JUDGMENT_MODEL`` code constant exists anywhere in ``src/autoinfo``
   (the #195 decision: the release pin lives in ``default_config.yaml``).
2. The judge/battery paths contain no vendor/model string literal in
   executable code (docstrings/comments excluded — they legitimately explain
   the contract).
3. Every L1 blind-spot ``check_desc`` is free of vendor/model names (the
   blind-spot manifest describes *what* a product must satisfy, never *which
   model* judges it).
4. The battery calls the repo's config-driven channel (``call_with_fallback``)
   rather than constructing a model string itself.
5. ``resolve_judgment_model`` is config-first: the deployment override wins,
   the deployment's own model is the fallback, and an unconfigured deployment
   raises ``JudgmentModelNotConfiguredError`` (never a guessed constant).
6. The shipped ``default_config.yaml`` carries ``llm.judgment_model`` (a
   config value, editable per deployment — not code).

Exit 0 only when every check passes.  Never hard-code counts; the checked
paths are enumerated from the live files.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "autoinfo"
BATTERY = ROOT / "scripts" / "agent_review" / "battery.py"
BLINDSPOTS = ROOT / "scripts" / "agent_review" / "blindspots.yaml"
DEFAULT_CONFIG = SRC / "data" / "default_config.yaml"

#: Paths that implement judging / the L1 battery.  A vendor or model literal
#: here is a #195 violation.  ``config.py`` is checked separately (the
#: behavioral ``resolve_judgment_model`` checks + the ``JUDGMENT_MODEL``
#: constant scan) because it legitimately carries non-judgment transport
#: defaults (retry-chain models, TTS engine) that are not judge pins.
JUDGE_PATHS: tuple[Path, ...] = (
    SRC / "quality.py",
    BATTERY,
)

#: Vendor / model-name tokens that must never appear as an executable literal
#: in a judge path.  Deliberately token-based (not an exhaustive registry) so
#: a new vendor literal still trips the contract when it names one of these.
VENDOR_RX = re.compile(
    r"\b(deepseek|openrouter|openai|anthropic|claude|gemini|gpt-[0-9]|mimo|"
    r"llama|nvidia|mistral|cohere|groq|ollama)\b",
    re.IGNORECASE,
)


class Check:
    """One named vendor-agnosticism assertion."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.ok = True
        self.detail = ""

    def pass_(self, detail: str = "") -> "Check":
        self.ok = True
        self.detail = detail
        return self

    def fail(self, detail: str) -> "Check":
        self.ok = False
        self.detail = detail
        return self


# ---------------------------------------------------------------------------
# Static checks
# ---------------------------------------------------------------------------


def _rel(path: Path) -> str:
    """Repo-relative label for a path, tolerating paths outside the repo."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _non_docstring_string_constants(path: Path) -> list[tuple[int, str]]:
    """Return ``(lineno, value)`` for executable string literals in *path*.

    Docstrings (module/class/function first statements) and comments are
    excluded: they document the contract and may legitimately name a vendor to
    explain what is forbidden.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    docstring_ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if ast.get_docstring(node, clean=False) is not None and node.body:
                first = node.body[0]
                if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                    docstring_ids.add(id(first.value))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in docstring_ids:
                continue
            found.append((node.lineno, node.value))
    return found


def _judgment_constant_check() -> Check:
    check = Check("no JUDGMENT_MODEL code constant in src/autoinfo")
    hits: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            hits.append(f"{_rel(path)}: SyntaxError {exc}")
            continue
        for node in ast.walk(tree):
            targets: list[ast.expr] = []
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id == "JUDGMENT_MODEL":
                    hits.append(f"{_rel(path)}:{node.lineno}")
    if hits:
        return check.fail(
            "JUDGMENT_MODEL constant defined at " + ", ".join(hits) + " — #195 "
            "moved the release pin to default_config.yaml llm.judgment_model"
        )
    return check.pass_("absent (config-first resolution)")


def _judge_path_vendor_check() -> Check:
    check = Check("no vendor/model literal in judge/battery executable code")
    hits: list[str] = []
    for path in JUDGE_PATHS:
        if not path.is_file():
            hits.append(f"{_rel(path)} missing")
            continue
        for lineno, value in _non_docstring_string_constants(path):
            if VENDOR_RX.search(value):
                hits.append(f"{_rel(path)}:{lineno}: {value!r}")
    if hits:
        return check.fail("vendor/model literals: " + "; ".join(hits))
    return check.pass_(f"scanned {len(JUDGE_PATHS)} judge/battery paths")


def _blindspots_check() -> Check:
    check = Check("blind-spot check_desc carries no vendor/model name")
    if not BLINDSPOTS.is_file():
        return check.fail(f"{BLINDSPOTS.relative_to(ROOT)} missing")
    data = yaml.safe_load(BLINDSPOTS.read_text(encoding="utf-8"))
    hits: list[str] = []
    families = data if isinstance(data, list) else []
    for family in families:
        for spot in (family or {}).get("blind_spots", []) or []:
            desc = str(spot.get("check_desc", ""))
            if VENDOR_RX.search(desc):
                hits.append(f"{family.get('family')}/{spot.get('id')}")
    if hits:
        return check.fail("vendor/model named in check_desc: " + ", ".join(hits))
    return check.pass_(f"{len(families)} families scanned")


def _battery_channel_check() -> Check:
    check = Check("battery uses the config-driven llm channel")
    if not BATTERY.is_file():
        return check.fail(f"{BATTERY.relative_to(ROOT)} missing")
    text = BATTERY.read_text(encoding="utf-8")
    if "call_with_fallback" not in text:
        return check.fail("battery does not call llm.call_with_fallback")
    if "import litellm" in text or "from litellm" in text:
        return check.fail("battery imports the vendor SDK directly")
    return check.pass_("call_with_fallback referenced; no direct SDK import")


# ---------------------------------------------------------------------------
# Behavioral checks (config-first judgment resolution)
# ---------------------------------------------------------------------------


def _resolution_checks() -> list[Check]:
    checks: list[Check] = []
    sys.path.insert(0, str(SRC.parent))
    try:
        from autoinfo.config import (
            JUDGMENT_TASKS,
            JudgmentModelNotConfiguredError,
            LLMConfig,
            resolve_judgment_model,
        )
    except Exception as exc:  # pragma: no cover - environment failure path
        return [Check("import judgment resolution helpers").fail(f"{type(exc).__name__}: {exc}")]
    finally:
        sys.path.pop(0)

    expected_tasks = {"g4_factual", "g5_translation", "llm_judge"}
    tasks_check = Check("judgment task set is the code constant (g4/g5/llm_judge)")
    if set(JUDGMENT_TASKS) == expected_tasks:
        checks.append(tasks_check.pass_(sorted(JUDGMENT_TASKS)))
    else:
        checks.append(tasks_check.fail(f"got {sorted(JUDGMENT_TASKS)}"))

    override_check = Check("config llm.judgment_model wins")
    override = resolve_judgment_model(
        LLMConfig(provider="p", model="base-model", judgment_model="deployment-judge"),
        "g4_factual",
    )
    if override == "deployment-judge":
        checks.append(override_check.pass_(override))
    else:
        checks.append(override_check.fail(f"got {override!r}"))

    fallback_check = Check("falls back to provider-qualified llm.model")
    fallback = resolve_judgment_model(LLMConfig(provider="p", model="base-model"), "g5_translation")
    if fallback == "p/base-model":
        checks.append(fallback_check.pass_(fallback))
    else:
        checks.append(fallback_check.fail(f"got {fallback!r}"))

    loud_check = Check("unconfigured judgment raises (never guesses a constant)")
    try:
        resolve_judgment_model(LLMConfig(), "llm_judge")
    except JudgmentModelNotConfiguredError as exc:
        checks.append(loud_check.pass_(type(exc).__name__))
    except Exception as exc:  # pragma: no cover - wrong error type
        checks.append(
            loud_check.fail(
                f"raised {type(exc).__name__}, expected JudgmentModelNotConfiguredError"
            )
        )
    else:
        checks.append(loud_check.fail("did not raise — a guessed/None model would be used"))

    default_check = Check("default_config.yaml ships llm.judgment_model")
    if DEFAULT_CONFIG.is_file():
        raw = yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8")) or {}
        llm = raw.get("llm", {})
        if llm.get("judgment_model") and llm.get("model"):
            default_check.pass_("config value present (editable per deployment)")
        else:
            default_check.fail(f"llm={llm!r} missing judgment_model/model")
    else:
        default_check.fail(f"{DEFAULT_CONFIG.relative_to(ROOT)} missing")
    checks.append(default_check)
    return checks


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def run_checks() -> list[Check]:
    checks = [
        _judgment_constant_check(),
        _judge_path_vendor_check(),
        _blindspots_check(),
        _battery_channel_check(),
    ]
    checks.extend(_resolution_checks())
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Model/vendor agnosticism contract check (T-S-12)."
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON results.")
    args = parser.parse_args(argv)

    checks = run_checks()
    failed = [c for c in checks if not c.ok]

    if args.json:
        print(
            json.dumps(
                {
                    "checks": [{"name": c.name, "ok": c.ok, "detail": c.detail} for c in checks],
                    "passed": len(checks) - len(failed),
                    "total": len(checks),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        for check in checks:
            mark = "ok" if check.ok else "FAIL"
            print(f"  [{mark}] {check.name}" + (f" — {check.detail}" if check.detail else ""))
        print(f"vendor-agnosticism checks passed: {len(checks) - len(failed)}/{len(checks)}")

    if failed:
        print("VENDOR_AGNOSTICISM_FAIL")
        return 1
    print("VENDOR_AGNOSTICISM_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
