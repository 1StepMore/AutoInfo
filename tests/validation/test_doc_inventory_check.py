"""Integration test: doc_inventory.py --check stays green (docs-as-code gate).

Runs ``scripts/doc_inventory.py --check`` and asserts exit 0. This is the
self-enforcement gate that keeps the drift-prone facts in README.md, AGENTS.md
and the doc-manager skill (SKILL.md) mutually consistent, so a doc-sync wave
can never silently leave the skill's own numbers stale again.

Reference: .opencode/skills/doc-manager-skill/SKILL.md §3 Step 4 (verify step).
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "doc_inventory.py"

# scripts/ is not a package — load it via sys.path like the sibling test files.
sys.path.insert(0, str(ROOT / "scripts"))

import doc_inventory as di  # noqa: E402  (sys.path insert above)


def test_doc_inventory_check_passes() -> None:
    """--check must exit 0: README↔AGENTS↔SKILL facts agree, no stray files."""
    assert SCRIPT.exists(), f"Missing: {SCRIPT}"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, (
        f"doc_inventory.py --check failed (exit {proc.returncode})\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )


def test_environment_failure_is_none_in_a_healthy_env() -> None:
    """A sound interpreter must not be flagged: never a false red on a working setup."""
    assert di.environment_failure() is None


def test_environment_failure_names_interpreter_and_fix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing dep must yield the interpreter path plus the remedy, not drift prose."""
    real = importlib.util.find_spec
    monkeypatch.setattr(
        importlib.util,
        "find_spec",
        lambda name: None if name in ("autoinfo", "pytest") else real(name),
    )
    msg = di.environment_failure()
    assert msg is not None
    assert sys.executable in msg
    assert "NOT documentation drift" in msg
    assert "Fix:" in msg


def test_check_reports_env_mismatch_instead_of_drift(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """--check must short-circuit on the env and never print the misleading drift lines."""
    real = importlib.util.find_spec
    monkeypatch.setattr(
        importlib.util,
        "find_spec",
        lambda name: None if name in ("autoinfo", "pytest") else real(name),
    )
    assert di.main(["--check"]) == 1
    out = capsys.readouterr().out
    assert "NOT documentation drift" in out
    assert "could not read live tool list" not in out
    assert "unparsable pytest output" not in out
