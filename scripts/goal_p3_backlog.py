#!/usr/bin/env python3
"""Goal checker for the P3 goal (docs/dev/goals.md) — owner-delegated 2026-11-21.

P3 = 遗留债清偿 + 质量底线维持 (backlog burn-down while holding the P2 bar).

Exit 0 iff ALL of:
  1. the P2 quality bar still holds on the current tree
     (scripts/goal_matrix_quality.py exit 0 — the achieved floor stays green);
  2. every P3-scoped issue is closed:
     #884 agent_ready entrypoint, #862 Windows dir sanitize, #851 year
     assertion tuning, #849 Windows full-suite hang, #887 KB parity, #730
     gh-aw timing item.  #863/#865 closed via their PRs (#902/#903).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

P3_ISSUES = (884, 862, 851, 849, 887, 730)


def main() -> int:
    messages: list[str] = []

    bar = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "goal_matrix_quality.py")],
        capture_output=True,
        text=True,
    )
    if bar.returncode != 0:
        tail = (bar.stdout or bar.stderr or "").strip().splitlines()[-2:]
        messages.append("P2 quality bar regressed: " + " | ".join(tail))

    for n in P3_ISSUES:
        probe = subprocess.run(
            ["gh", "issue", "view", str(n), "--json", "state", "--template", "{{.state}}"],
            capture_output=True,
            text=True,
        )
        state = probe.stdout.strip()
        if probe.returncode != 0 or state != "CLOSED":
            messages.append(f"issue #{n} still {state or 'unqueryable'} (open work)")

    if messages:
        for m in messages:
            print(f"GAP: {m}")
        print(f"goal_p3_backlog: NOT ACHIEVED ({len(messages)} gap(s))")
        return 1
    print(
        "goal_p3_backlog: ACHIEVED - P2 bar green (goal_matrix_quality exit 0), "
        "P3 issues all closed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
