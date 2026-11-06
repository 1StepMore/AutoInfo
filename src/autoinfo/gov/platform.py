"""Interpreter + platform discovery — concentrated in ONE place (plan 1.1.3).

``resolve_python()`` is the only interpreter-resolution helper in the repo:
``sys.executable`` (when it can import the project) → ``.venv/Scripts/
python.exe`` → ``.venv/bin/python`` → ``python3`` → ``python``. The Makefile
carries no platform probe and no other module may re-implement this chain.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from autoinfo.gov.contract import resolve_repo_root

#: Candidate chain from the governance contract [platform].python_candidates.
CANDIDATE_PARTS: tuple[tuple[str, ...], ...] = (
    (".venv", "Scripts", "python.exe"),
    (".venv", "Scripts", "python"),
    (".venv", "bin", "python"),
)


def _can_import_project(python: str) -> bool:
    """True when *python* can ``import autoinfo`` (cheap probe subprocess)."""
    try:
        proc = subprocess.run(
            [python, "-c", "import autoinfo"],
            capture_output=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


def candidate_paths(root: Path | None = None) -> list[str]:
    """Return every candidate interpreter that exists on this machine."""
    if root is None:
        try:
            root = resolve_repo_root()
        except Exception:  # noqa: BLE001 — discovery must never raise
            root = Path.cwd()
    found = [sys.executable] if sys.executable else []
    for parts in CANDIDATE_PARTS:
        cand = root.joinpath(*parts)
        try:
            if cand.is_file():
                found.append(str(cand))
        except OSError:
            continue
    for name in ("python3", "python"):
        which = shutil.which(name)
        if which:
            found.append(which)
    seen: set[str] = set()
    unique: list[str] = []
    for item in found:
        key = str(Path(item).resolve().as_posix()).lower()
        if key not in seen:
            seen.add(key)
            unique.append(str(item))
    return unique


def resolve_python(root: Path | None = None) -> str:
    """Resolve THE interpreter for spawned tooling (venv-aware, one place)."""
    candidates = candidate_paths(root)
    for cand in candidates:
        if _can_import_project(cand):
            return cand
    # Nothing importable — return the first existing candidate so callers get
    # a working interpreter for error reporting rather than a crash here.
    return candidates[0] if candidates else sys.executable


def platform_name() -> str:
    """'Windows' | 'Linux' | 'Darwin' | other sys.platform value."""
    if sys.platform.startswith("win"):
        return "Windows"
    if sys.platform.startswith("linux"):
        return "Linux"
    if sys.platform == "darwin":
        return "Darwin"
    return sys.platform


def is_windows() -> bool:
    return platform_name() == "Windows"
