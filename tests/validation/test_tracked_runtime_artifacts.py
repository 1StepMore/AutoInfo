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
tracked path lives under one of those runtime directories. ``.omo/`` is runtime
scratch with **no** exception — anything learned there is distilled into
in-repo artifacts, so nothing under ``.omo/`` may be tracked.

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

#: A path under .omo/ that must stay ignored. It used to be re-included by a
#: ``!.omo/evidence/validation-runs/`` negation, which a later unanchored
#: ``validation-runs/`` rule silently defeated — so the guard's "tracked-by-
#: exception" whitelist was inert and its comment was false. The probe in
#: ``test_omo_is_fully_ignored`` locks the intent: every .omo/ path is ignored.
OMO_PROBE = ".omo/evidence/validation-runs/__guard_probe__"


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
            if path.startswith(runtime_dir):
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


def test_omo_is_fully_ignored() -> None:
    """No ``.omo/`` path may be tracked, and git must ignore the whole tree.

    The ``check-ignore`` probe is the non-vacuous half: it fails when a
    ``.gitignore`` rule (e.g. an unanchored ``validation-runs/``) resurrects a
    path that a negation had re-included — exactly how the previous
    "tracked-by-exception subtree" claim became false.
    """
    tracked = _git_ls_files()
    assert tracked, "git ls-files returned nothing — guard cannot verify the index"

    tracked_omo = [path for path in tracked if path.startswith(".omo/")]
    assert not tracked_omo, (
        ".omo/ is runtime scratch space (AGENTS.md §Runtime Artifacts vs Source "
        f"Files); nothing there may be tracked, found: {tracked_omo}"
    )

    probe = subprocess.run(
        ["git", "check-ignore", "-v", OMO_PROBE],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert probe.returncode == 0, (
        f"{OMO_PROBE} is NOT ignored — .omo/ must be entirely runtime state. An "
        "unanchored ignore rule (e.g. `validation-runs/`) may be defeating the "
        "`.omo/` rule; anchor it (e.g. `/validation-runs/`).\n"
        f"git check-ignore stderr: {probe.stderr.strip()}"
    )
