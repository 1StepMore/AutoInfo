"""Platform/environment diagnostics (T05) — read-only, hint-only.

``gov doctor`` reports what a machine needs to run the governance stack:
make, interpreter consistency, autocrlf, tracked CRLF files, longpaths,
filemode/symlinks, venv. It never mutates anything; every finding carries a
hint. Exit code is 0 unless the environment itself is broken (exit 2).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from autoinfo.gov.platform import candidate_paths, is_windows, platform_name


def _git(root: Path, *args: str) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, str(exc)
    return proc.returncode, f"{proc.stdout}\n{proc.stderr}".strip()


def _interpreter_rows(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cand in candidate_paths(root):
        try:
            proc = subprocess.run(
                [cand, "-c", "import sys; print('.'.join(map(str, sys.version_info[:3])))"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
            )
            version = proc.stdout.strip() if proc.returncode == 0 else "unreadable"
        except (OSError, subprocess.SubprocessError):
            version = "unreadable"
        rows.append({"path": cand, "version": version})
    return rows


def doctor(root: Path) -> dict[str, Any]:
    """Run all diagnostics; return the report payload (exit 0 material)."""
    checks: list[dict[str, Any]] = []

    def add(check_id: str, severity: str, state: str, detail: str, hint: str) -> None:
        checks.append(
            {"id": check_id, "severity": severity, "state": state, "detail": detail, "hint": hint}
        )

    make = shutil.which("make")
    if make:
        add("make", "info", "ok", f"found at {make}", "")
    elif is_windows():
        add(
            "make",
            "P1",
            "missing",
            "make is not on PATH",
            "run governance targets from WSL, or install make (scoop/winget/choco)",
        )
    else:
        add("make", "info", "ok", "make available on PATH", "")

    interpreters = _interpreter_rows(root)
    versions = sorted({row["version"] for row in interpreters if row["version"] != "unreadable"})
    if len(versions) > 1:
        add(
            "interpreters",
            "P1",
            "mixed",
            f"{len(versions)} distinct versions: {', '.join(versions)}",
            "pin one interpreter (the project venv) and re-run the gates with it",
        )
    else:
        add(
            "interpreters",
            "info",
            "ok" if versions else "unknown",
            f"{len(interpreters)} interpreter(s), version(s): {', '.join(versions) or 'n/a'}",
            "",
        )

    rc, out = _git(root, "config", "--get", "core.autocrlf")
    autocrlf = out.splitlines()[0].strip() if rc == 0 and out else ""
    if autocrlf == "true":
        add(
            "core.autocrlf",
            "P1",
            "true",
            "core.autocrlf=true rewrites EOLs on checkout",
            "set core.autocrlf=false (or input) and renormalize (T13)",
        )
    else:
        add(
            "core.autocrlf", "info", autocrlf or "unset", f"core.autocrlf={autocrlf or 'unset'}", ""
        )

    rc, eol_out = _git(root, "ls-files", "--eol")
    crlf_files: list[str] = []
    if rc == 0:
        for line in eol_out.splitlines():
            if "i/crlf" in line:
                crlf_files.append(line.split("\t", 1)[-1].strip())
    if crlf_files:
        add(
            "tracked-crlf",
            "P0",
            "crlf-tracked",
            f"{len(crlf_files)} tracked file(s) with CRLF in the index "
            f"(first: {', '.join(crlf_files[:5])})",
            "add '<path> text eol=lf' to .gitattributes and run one "
            "'git add --renormalize .' commit (T13)",
        )
    else:
        add("tracked-crlf", "info", "ok", "no tracked CRLF files (index side)", "")

    longpaths = _git(root, "config", "--get", "core.longpaths")
    longpaths_value = (
        longpaths[1].splitlines()[0].strip() if longpaths[0] == 0 and longpaths[1] else ""
    )
    if is_windows() and longpaths_value != "true":
        add(
            "core.longpaths",
            "P2",
            "unset" if not longpaths_value else longpaths_value,
            "Windows without core.longpaths can break deep checkouts",
            "git config core.longpaths true",
        )
    else:
        add(
            "core.longpaths",
            "info",
            longpaths_value or "unset",
            f"core.longpaths={longpaths_value or 'unset'}",
            "",
        )

    in_venv = sys.prefix != sys.base_prefix
    if in_venv:
        add("venv", "info", "active", f"active venv at {sys.prefix}", "")
    else:
        add(
            "venv",
            "P2",
            "inactive",
            "running on the base interpreter",
            "create/activate .venv (pip install -e '.[dev]') so gates resolve to project deps",
        )

    rc, filemode = _git(root, "config", "--get", "core.filemode")
    filemode_value = filemode.splitlines()[0].strip() if rc == 0 and filemode else "unset"
    add("core.filemode", "info", filemode_value, f"core.filemode={filemode_value}", "")
    rc, symlinks = _git(root, "config", "--get", "core.symlinks")
    symlinks_value = symlinks.splitlines()[0].strip() if rc == 0 and symlinks else "unset"
    add("core.symlinks", "info", symlinks_value, f"core.symlinks={symlinks_value}", "")

    p0 = sum(1 for c in checks if c["severity"] == "P0")
    p1 = sum(1 for c in checks if c["severity"] == "P1")
    p2 = sum(1 for c in checks if c["severity"] == "P2")
    return {
        "platform": platform_name(),
        "python": ".".join(map(str, sys.version_info[:3])),
        "checks": checks,
        "p0": p0,
        "p1": p1,
        "p2": p2,
    }
