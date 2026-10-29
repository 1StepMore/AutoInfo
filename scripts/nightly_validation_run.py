#!/usr/bin/env python3
"""Nightly validation-suite run with persistence (agent-infra remediation plan
2026-10-30, decision B1).

Runs the full live scenario library through the same engine entry the MCP
``run_all_validation_scenarios`` tool uses (real MCP dispatch, no mocks) and
persists everything the verification loop consumes:

- ``validation-runs/<stamp>/scenarios.json`` aggregate suite run (+ ``latest.txt``)
- ``validation-runs/sessions/<session_id>.json`` structured B2.6 run report
- ``validation-runs/category-pyramid-history.json`` ledger entry (the data
  source ax_metrics M-01 reads; ``run_all_scenarios`` persists the run and the
  report but not this ledger, so it is recorded here from the persisted
  envelopes)

Env/domain-gated scenarios report ``unconfigured`` on a fresh checkout —
honest by design, never silently skipped, never fake-passed.

Exit code: 0 when the run completed and was persisted (scenario failures are
printed, not fatal — PR CI already gates the keyless subset via
``scenario_portability_gate``; the nightly's deliverable is the persisted
evidence). 1 when the run itself could not execute or persist.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, cast


async def _run_suite(timeout: float) -> dict[str, Any]:
    from autoinfo.mcp.server import call_tool
    from autoinfo.mcp.validation import (
        load_scenario_results,
        record_category_pyramid_history,
        run_all_scenarios,
    )

    async def dispatch(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        texts = await call_tool(name, arguments)
        return cast(dict[str, Any], json.loads(texts[0][0].text))

    aggregate = await run_all_scenarios(dispatch=dispatch, timeout=timeout, save=True)
    run_dir = Path(aggregate["saved_run"])
    payload = load_scenario_results(run_dir) or {}
    record_category_pyramid_history(
        list(payload.get("scenarios") or []),
        run_id=run_dir.name,
        run_type="suite",
        session_id=str(aggregate["session_id"]),
    )
    return aggregate


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Persisted nightly validation suite run (plan decision B1)."
    )
    parser.add_argument(
        "--timeout", type=float, default=180.0, help="Per-step fallback timeout (seconds)."
    )
    args = parser.parse_args()
    try:
        aggregate = asyncio.run(_run_suite(args.timeout))
    except Exception as exc:  # noqa: BLE001 - the runner reports, never hangs silently
        print(f"nightly validation run FAILED to execute: {exc}", file=sys.stderr)
        return 1
    summary = aggregate.get("summary", {})
    print(
        "suite run persisted: {status} — {passed} passed / {failed} failed / "
        "{unconfigured} unconfigured / {total} total".format(
            status=aggregate.get("status"),
            passed=summary.get("passed", 0),
            failed=summary.get("failed", 0),
            unconfigured=summary.get("unconfigured", 0),
            total=summary.get("total", 0),
        )
    )
    print(f"run dir: {aggregate.get('saved_run')}")
    print(f"report:  {aggregate.get('report_path')}")
    failures = [
        s["scenario"] for s in aggregate.get("scenarios", []) if s.get("status") == "failed"
    ]
    if failures:
        print(f"failed scenarios ({len(failures)}): {', '.join(failures)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
