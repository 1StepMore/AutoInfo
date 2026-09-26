#!/usr/bin/env python3
"""Runtime-enumerated scenario portability gate (issue #381).

Replaces the hand-picked two-scenario list in the ``scenario-portability``
CI job with a runtime enumeration over ``load_scenarios()``: every scenario
that is safe to execute without an LLM key and without network is run here,
and any non-passing scenario must either be in the committed
:data:`KNOWN_RED_BASELINE` below or the gate fails.

The candidate set is derived at runtime, never hardcoded — count and
membership move automatically as the scenario library grows.  The baseline
is the only hardcoded list, and it cannot grow silently: an entry that stops
failing is itself reported as a gate failure, forcing its removal.

Exclusion rules (each is an explicit, statically checkable precondition that
``run_scenario`` would otherwise gate as ``unconfigured`` or that would fail
for a reason unrelated to portability):

* ``requires_env`` is non-empty — the scenario declares a required key
  (LLM, Stripe, a source API) the CI checkout does not provide.
* a step calls an ``server._LLM_REQUIRED_TOOLS`` tool — ``call_tool`` blocks
  it with ``LLMNotConfigured`` when no key is set, which is not a portability
  signal.
* a step has ``expect.llm_assert`` — needs a real judge model call.
* a step has ``kind: http`` or the scenario declares ``requires_http`` —
  needs a live service and network.
* ``requires_domain`` is non-empty, or ``matrix_domains`` is non-empty — CI
  runs only ``pip install`` with no ``autoinfo init``, and the harness unions
  both into its domain precondition, so it gates these as ``unconfigured``
  before any step runs (see DESIGN NOTE below).

Anything else that fails is a portability defect and must be fixed, not
silently skipped.  A scenario that turns out to need a key or network at
runtime (only visible from a ``kind: cli`` subprocess, which the static
enumeration cannot see) lands in the baseline with an explicit reason.

DESIGN NOTE — why ``requires_domain`` scenarios are excluded rather than
initialised: this job's contract (#347) is "each scenario runs as-is in a
clean checkout + standard venv".  Initialising demo domains would turn the
job into a stateful, order-dependent KB exercise and would hide the
portability signal behind project setup.  The domain-bound scenarios are
exercised by the local full-suite runs instead.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from autoinfo.mcp import server
from autoinfo.mcp.validation import load_scenarios, run_scenario

# Known-red baseline: scenario name -> reason it still fails in the keyless,
# networkless CI checkout.  Every entry is checked in both directions: an
# unlisted non-pass fails the gate, and a listed scenario that PASSES fails the
# gate as a stale entry (so this dict cannot grow silently).
#
# The candidate set is derived at runtime; this baseline was computed from a
# full gate run on the commit that introduced it.  Every reason names the
# observed failure, not a guess.  Entries fall into two classes:
#   (a) the scenario pins a hardcoded `collected_at` date that has since aged
#       past the domain freshness threshold, so the generator refuses the now
#       stale entry (a scenario time-bomb, not a product defect);
#   (b) the scenario asserts a wall-clock threshold that a shared runner
#       cannot reproduce, so it measures runner load rather than the code.
KNOWN_RED_BASELINE: dict[str, str] = {
    # -- (a) hardcoded-date time-bomb: entry now exceeds freshness -----------
    "fault-injection": (
        "time-bomb: the seeded entry's collected_at 2026-08-01 is now older "
        "than the ai-commercial freshness threshold, so generate_digest raises "
        "StaleSourceError before the injected fault path runs"
    ),
    "regression-magazine-editorial": (
        "time-bomb: the seeded entries' collected_at 2026-07-29 is now older "
        "than the general-news freshness threshold, so generate_digest raises "
        "StaleSourceError"
    ),
    # -- (b) wall-clock threshold, not reproducible on a shared runner ------
    "perf-concurrency": (
        "machine-dependent timing: asserts 10 concurrent runs finish within "
        "2.0x a single run's wall time. Observed 4.27x on a GitHub runner "
        "(single=0.749s concurrent=3.194s) while passing on a dev box, so the "
        "ratio measures runner load, not the code. Needs a dedicated perf "
        "harness with a load-relative threshold, not a fixed ratio"
    ),
}

# Scenarios that assert against a *configured* project.  These were previously
# baselined as "needs a configured project" because the gate ran in a bare
# checkout and they all returned ConfigNotFound.  They are run in a second pass
# against a throwaway project instead, so they are real assertions rather than
# permanently-exempt known-red.  Listed explicitly (not detected by retrying on
# failure) so that one of them breaking is reported as a failure rather than
# silently retried into a pass.
PROJECT_SCENARIOS: frozenset[str] = frozenset(
    {
        "cli-ops",
        "cost-budget",
        "delivery-channels",
        "discovery",
        "error-boundary",
        "kb-import-export",
        "output-discovery",
        "projects-config",
        "regression-llm-pool-config",
    }
)

#: Domain initialised for the project pass; the scenarios only assert that a
#: configured project resolves, not any domain-specific content.
_PROJECT_DOMAIN = "medical-research"


def _steps(scenario: dict[str, Any]) -> list[dict[str, Any]]:
    return [*scenario.get("steps", []), *scenario.get("cleanup_steps", [])]


def _uses_llm_tool(scenario: dict[str, Any]) -> bool:
    """True when an ``kind: mcp`` step calls an LLM-required tool."""
    return any(
        step.get("kind", "mcp") == "mcp" and step.get("tool") in server._LLM_REQUIRED_TOOLS
        for step in _steps(scenario)
    )


def _has_llm_assert(scenario: dict[str, Any]) -> bool:
    """True when a step declares an ``expect.llm_assert`` judge call."""
    return any((step.get("expect") or {}).get("llm_assert") for step in _steps(scenario))


def _uses_http(scenario: dict[str, Any]) -> bool:
    """True when the scenario needs network (HTTP step or requires_http)."""
    return bool(scenario.get("requires_http")) or any(
        step.get("kind") == "http" for step in _steps(scenario)
    )


def _requires_configured_domain(scenario: dict[str, Any]) -> bool:
    """True when ``run_scenario`` gates the scenario on a configured domain.

    ``requires_domain`` and the per-run ``matrix_domains`` members are unioned
    by the harness before the precondition check, so both gate as
    ``unconfigured`` without a project config.
    """
    return bool(scenario.get("requires_domain")) or bool(scenario.get("matrix_domains"))


def select_candidates(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return the keyless, networkless, domain-free candidate scenarios."""
    return [
        scenario
        for scenario in scenarios
        if not scenario.get("requires_env")
        and not _requires_configured_domain(scenario)
        and not _uses_llm_tool(scenario)
        and not _has_llm_assert(scenario)
        and not _uses_http(scenario)
    ]


async def _dispatch(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Real MCP dispatch: parse the ``{success, data}`` JSON envelope."""
    texts = await server.call_tool(name, arguments)
    return json.loads(texts[0][0].text)


def _failure_reason(result: dict[str, Any]) -> str:
    """Compact ``step -> status: detail`` for the first non-passing step."""
    for step in result.get("steps", []):
        if step.get("status") not in (None, "passed"):
            detail = str(step.get("detail", ""))[:300].replace("\n", " ")
            return f"{step.get('name')} -> {step.get('status')}: {detail}"
    return str(result.get("unconfigured_reason") or result.get("status"))


async def _run_candidate(name: str, timeout: float) -> tuple[str, str, str]:
    """Run one scenario; return ``(name, status, reason)``.

    A harness exception (e.g. an mcp step with no dispatch) is reported as
    ``failed`` rather than crashing the gate, and its message becomes the
    reason.
    """
    try:
        result = await run_scenario(name, dispatch=_dispatch, timeout=timeout)
    except Exception as exc:  # noqa: BLE001 - a raised scenario is a failed scenario
        return name, "failed", f"harness exception: {exc}"[:300]
    status = str(result.get("status", "unknown"))
    return name, status, _failure_reason(result)


async def _run_project_pass(names: list[str], timeout: float) -> dict[str, tuple[str, str]]:
    """Run *names* against a throwaway initialised project.

    These scenarios read project config, so a bare checkout makes every one of
    them return ``ConfigNotFound`` and assert nothing.  Initialising a project
    in a temp cwd turns them into real assertions.  The cwd and the directory
    are always restored/removed, so the pass leaves no state behind and cannot
    affect the scenarios that run before it.
    """
    results: dict[str, tuple[str, str]] = {}
    if not names:
        return results
    previous = Path.cwd()
    workdir = Path(tempfile.mkdtemp(prefix="scenario-gate-project-"))
    try:
        os.chdir(workdir)
        envelope = await _dispatch("init_project", {"domain": _PROJECT_DOMAIN})
        if not envelope.get("success"):
            reason = f"init_project failed: {envelope.get('error')}"[:300]
            return {name: ("failed", reason) for name in names}
        for index, name in enumerate(names, start=1):
            _, status, reason = await _run_candidate(name, timeout)
            results[name] = (status, reason)
            suffix = "" if status == "passed" else f"  <-- {reason}"
            print(f"[project {index}/{len(names)}] {name}: {status}{suffix}", flush=True)
    finally:
        os.chdir(previous)
        shutil.rmtree(workdir, ignore_errors=True)
    return results


async def _main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="list candidates and exit")
    parser.add_argument("--timeout", type=float, default=180.0, help="per-step timeout (s)")
    parser.add_argument("--json", default="", help="write full results as JSON to this path")
    parser.add_argument(
        "--only",
        default="",
        help="comma-separated scenario names to restrict the run (debugging)",
    )
    args = parser.parse_args(argv)

    scenarios = load_scenarios()
    scenario_names = {scenario["name"] for scenario in scenarios}
    unknown_baseline = sorted(set(KNOWN_RED_BASELINE) - scenario_names)
    reasonless = sorted(n for n, reason in KNOWN_RED_BASELINE.items() if not reason.strip())
    if unknown_baseline or reasonless:
        for name in unknown_baseline:
            print(f"Baseline names an unknown scenario: {name}", file=sys.stderr)
        for name in reasonless:
            print(f"Baseline entry has no reason: {name}", file=sys.stderr)
        return 1

    candidates = select_candidates(scenarios)
    candidate_names = {c["name"] for c in candidates}
    unknown_project = sorted(PROJECT_SCENARIOS - candidate_names)
    if unknown_project:
        for name in unknown_project:
            print(
                f"PROJECT_SCENARIOS names {name!r}, which is not a runtime candidate "
                "(renamed, or newly gated on env/LLM/HTTP/domain)",
                file=sys.stderr,
            )
        return 1
    if args.only:
        wanted = {n for n in args.only.split(",") if n}
        candidates = [c for c in candidates if c["name"] in wanted]

    print(
        f"Runtime-enumerated candidates: {len(candidates)} "
        f"(of {len(scenarios)} scenarios); baseline entries: {len(KNOWN_RED_BASELINE)}"
    )
    if args.list:
        for scenario in candidates:
            print(f"  {scenario['name']}")
        return 0

    # Sequential: scenarios mutate shared KB/DB/output state, so running them
    # concurrently produces cross-scenario interference, not a portability
    # verdict.  Progress is printed (and flushed) as each scenario finishes so
    # a long run is observable.
    statuses: dict[str, str] = {}
    reasons: dict[str, str] = {}
    project_names: list[str] = []
    plain_names: list[str] = []
    for scenario in candidates:
        name = scenario["name"]
        if name in PROJECT_SCENARIOS:
            project_names.append(name)
        else:
            plain_names.append(name)

    for index, scenario in enumerate(candidates, start=1):
        if scenario["name"] in PROJECT_SCENARIOS:
            continue
        name, status, reason = await _run_candidate(scenario["name"], args.timeout)
        statuses[name] = status
        reasons[name] = reason
        suffix = "" if status == "passed" else f"  <-- {reason}"
        print(f"[{index}/{len(candidates)}] {name}: {status}{suffix}", flush=True)

    for name, (status, reason) in (await _run_project_pass(project_names, args.timeout)).items():
        statuses[name] = status
        reasons[name] = reason
    if args.json:
        Path(args.json).write_text(
            json.dumps(
                {"candidates": [c["name"] for c in candidates], "reasons": reasons},
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    failed = sorted(n for n, s in statuses.items() if s == "failed")
    unconfigured = sorted(n for n, s in statuses.items() if s == "unconfigured")
    passed = sorted(n for n, s in statuses.items() if s == "passed")
    non_passing = sorted(set(failed) | set(unconfigured))

    print(f"\nSummary: passed={len(passed)} failed={len(failed)} unconfigured={len(unconfigured)}")
    if non_passing:
        print("Non-passing details:")
        for name in non_passing:
            print(f"  {name}: {statuses[name]} -- {reasons.get(name, '')}")

    unlisted = sorted(n for n in non_passing if n not in KNOWN_RED_BASELINE)
    # A restricted `--only` run does not execute the whole candidate set, so any
    # baseline entry it skipped would look stale. Judge only the direction that
    # the run can actually speak to.
    stale = [] if args.only else sorted(n for n in KNOWN_RED_BASELINE if n not in non_passing)
    if unlisted:
        print("\nNon-passing scenarios NOT in the known-red baseline:", file=sys.stderr)
        for name in unlisted:
            print(f"  {name}: {statuses[name]}", file=sys.stderr)
    if stale:
        print(
            "\nStale baseline entries (no longer non-passing; remove them):",
            file=sys.stderr,
        )
        for name in stale:
            print(f"  {name}", file=sys.stderr)
    if unlisted or stale:
        return 1

    print("\nAll non-passing scenarios are accounted for by the known-red baseline.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main(sys.argv[1:])))
