"""Tests for the ``python -m autoinfo.cli`` module entry point (issue #137).

The ``autoinfo`` console script (pyproject ``[project.scripts] autoinfo =
"autoinfo.cli:app"``) is the primary entry point. ``python -m autoinfo.cli``
must behave identically; this guards against regressions of the module entry
(e.g. the file being removed or the guard being dropped).
"""

from __future__ import annotations

import inspect
import shutil
import subprocess
import sys

import pytest

import autoinfo.cli.__main__ as cli_main
from autoinfo.cli import app as cli_app


def test_main_module_imports_cleanly() -> None:
    """``import autoinfo.cli.__main__`` succeeds."""
    assert cli_main is not None


def test_main_module_uses_name_main_guard() -> None:
    """The module entry runs the app only under ``__main__`` (no side effects on import)."""
    source = inspect.getsource(cli_main)
    assert 'if __name__ == "__main__":' in source
    assert "app()" in source


def test_main_module_app_is_cli_app() -> None:
    """``__main__`` imports the same Typer app as the console script."""
    assert cli_main.app is cli_app


def test_python_m_autoinfo_cli_help_exit_zero() -> None:
    """``python -m autoinfo.cli --help`` exits 0 and prints usage."""
    result = subprocess.run(
        [sys.executable, "-m", "autoinfo.cli", "--help"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "Usage" in result.stdout


def _normalize_help(text: str) -> list[str]:
    """Normalize rich help output for comparison.

    ``python -m autoinfo.cli`` is longer than ``autoinfo``, so rich pads
    every line of the panel to the wider invocation's width. Normalize the
    invocation name and strip trailing padding so both outputs compare equal.
    """
    normalized: list[str] = []
    for line in text.splitlines():
        line = line.replace("python -m autoinfo.cli", "autoinfo")
        normalized.append(line.rstrip())
    return normalized


@pytest.mark.skipif(
    shutil.which("autoinfo") is None,
    reason="autoinfo console script not installed on PATH",
)
def test_python_m_matches_console_script_help() -> None:
    """Module entry help is identical to the console script (same Typer app)."""
    module = subprocess.run(
        [sys.executable, "-m", "autoinfo.cli", "--help"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    script = subprocess.run(
        ["autoinfo", "--help"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert module.returncode == 0, module.stderr
    assert script.returncode == 0, script.stderr
    assert _normalize_help(module.stdout) == _normalize_help(script.stdout)


def test_python_m_autoinfo_cli_lists_subcommands() -> None:
    """``python -m autoinfo.cli`` exposes the expected top-level commands."""
    result = subprocess.run(
        [sys.executable, "-m", "autoinfo.cli", "--help"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0
    for cmd in ("collect", "process", "doctor", "kb", "output"):
        assert cmd in result.stdout
