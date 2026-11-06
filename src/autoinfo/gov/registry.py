"""scripts/ registry (T14): every tracked script is classifiable.

The total is DERIVED from ``git ls-files 'scripts/*.py'`` (recursive); the
contract's ``[scripts]`` section explicitly declares ``gate`` and ``oneoff``
scripts — everything else defaults to ``instrument`` (the plan's risk
control for subjective classifications). ``unregistered`` lists scripts the
contract names but that no longer exist, or entries with an unknown class —
it must be empty for the gate to read clean.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from autoinfo.gov.contract import Contract

KNOWN_CLASSES = ("gate", "oneoff", "instrument")


def tracked_scripts(root: Path) -> list[str]:
    """Git-tracked scripts/*.py (posix relative paths, sorted)."""
    proc = subprocess.run(
        ["git", "-c", "core.quotepath=false", "ls-files", "-z", "--", "scripts/*.py"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git ls-files failed: {proc.stderr.strip()}")
    return sorted(f.replace("\\", "/") for f in proc.stdout.split("\0") if f)


def _normalize(entry: str) -> str:
    """'quality_gate.py' -> 'scripts/quality_gate.py' (prefix-tolerant)."""
    entry = str(entry).replace("\\", "/").lstrip("./")
    return entry if entry.startswith("scripts/") else f"scripts/{entry}"


def registry_report(contract: Contract) -> dict[str, Any]:
    """{total, gate, instrument, oneoff, unregistered} per plan T14.

    ``unregistered`` flags registry errors: a declared entry pointing at a
    script that no longer exists, or one declared in two classes at once.
    """
    declared = contract.scripts or {}
    gate = {_normalize(s) for s in declared.get("gate", [])}
    oneoff = {_normalize(s) for s in declared.get("oneoff", [])}
    tracked = tracked_scripts(contract.root)
    tracked_set = set(tracked)

    unregistered = sorted((gate | oneoff) - tracked_set)
    double_declared = sorted(gate & oneoff)
    instruments = sorted(tracked_set - gate - oneoff)
    return {
        "total": len(tracked),
        "gate": len(gate & tracked_set),
        "instrument": len(instruments),
        "oneoff": len(oneoff & tracked_set),
        "unregistered": unregistered + [f"{e} (declared twice)" for e in double_declared],
    }
