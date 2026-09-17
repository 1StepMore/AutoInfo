"""Guard: runtime artifacts declared gitignored by AGENTS.md must not be tracked.

``AGENTS.md`` §Runtime Artifacts vs Source Files declares ``collections/``,
``knowledge/``, ``outputs/``, ``validation-runs/``, ``validation-deliveries/``
and ``.omo/`` to be gitignored runtime state — not source. Those paths were
nevertheless tracked (they were committed before the ignore rules landed, and
git never re-applies ignore rules to paths already in the index), so 6,968 of
7,828 tracked files — 89% of the repository — were runtime data. That made the
worktree permanently dirty, drowned real source diffs in review noise and
inflated ``.git``.

This guard locks the boundary: walking ``git ls-files`` and failing when any
tracked path lives under one of those runtime directories. ``.omo/`` carries a
single documented tracked-by-exception subtree.

Fix hint for a reported violation: ``git rm -r --cached <path>`` (keeps the
file on disk, drops it from the index).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

# AGENTS.md §Runtime Artifacts vs Source Files — directories declared runtime
# state and gitignored. Keep in sync with .gitignore.
RUNTIME_DIRS: tuple[str, ...] = (
    "collections/",
    "knowledge/",
    "outputs/",
    "validation-runs/",
    "validation-deliveries/",
    ".omo/",
)

# .omo/ is tracked-by-exception: .gitignore whitelists this subtree only.
OMO_TRACKED_WHITELIST: tuple[str, ...] = (".omo/evidence/validation-runs/",)


def _git_ls_files() -> list[str]:
    """Return every tracked path, repo-relative and POSIX-separated."""
    try:
        completed = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=ROOT,
            capture_output=True,
            check=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:  # pragma: no cover
        pytest.skip(f"git is unavailable — tracked-artifact guard skipped: {exc}")
    return [path for path in completed.stdout.split("\0") if path]


def test_no_tracked_runtime_artifacts() -> None:
    """No path under a declared runtime directory may be tracked by git."""
    tracked = _git_ls_files()
    assert tracked, "git ls-files returned nothing — guard cannot verify the index"

    violations: list[str] = []
    for path in tracked:
        for runtime_dir in RUNTIME_DIRS:
            if not path.startswith(runtime_dir):
                continue
            if path.startswith(OMO_TRACKED_WHITELIST):
                continue
            violations.append(path)
            break

    if violations:
        shown = violations[:20]
        detail = "\n".join(f"  {path}" for path in shown)
        if len(violations) > len(shown):
            detail += f"\n  ... and {len(violations) - len(shown)} more"
        pytest.fail(
            "Runtime artifacts must not be tracked by git (AGENTS.md "
            "§Runtime Artifacts vs Source Files). Untrack them with "
            "`git rm -r --cached <path>` (files stay on disk).\n"
            f"{len(violations)} tracked path(s) under {RUNTIME_DIRS}:\n{detail}"
        )


def test_omo_whitelist_is_the_only_omo_exception() -> None:
    """Every tracked .omo/ path must live under the documented whitelist."""
    tracked = _git_ls_files()
    assert tracked, "git ls-files returned nothing — guard cannot verify the index"

    omo_tracked = [path for path in tracked if path.startswith(".omo/")]
    strays = [path for path in omo_tracked if not path.startswith(OMO_TRACKED_WHITELIST)]

    assert not strays, (
        ".omo/ is runtime scratch space (AGENTS.md §Runtime Artifacts vs Source "
        f"Files); only {OMO_TRACKED_WHITELIST} may be tracked, found: {strays}"
    )
