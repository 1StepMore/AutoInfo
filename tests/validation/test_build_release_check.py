"""Build/release surface validation tests (T-S-11).

Exercises `scripts/build_release_check.py` — the executable form of the
methodology's build-from-AGENTS acid test: editable install importable,
version synced with the release-please manifest, console script registered,
pyproject structurally sound.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
BUILD_SCRIPT = ROOT / "scripts" / "build_release_check.py"


@pytest.fixture(scope="module")
def build_check() -> Any:
    spec = importlib.util.spec_from_file_location("build_release_check", BUILD_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_all_build_release_checks_pass(build_check: Any) -> None:
    checks = build_check.run_checks()
    failed = [f"{c.name}: {c.detail}" for c in checks if not c.ok]
    assert not failed, "\n".join(failed)


def test_key_surfaces_are_asserted(build_check: Any) -> None:
    names = " | ".join(c.name for c in build_check.run_checks())
    for surface in (
        "import autoinfo",
        "installed version",
        "editable/source install",
        "console script",
        "pyproject.toml",
        "release-please manifest",
        "CHANGELOG.md",
    ):
        assert surface in names, f"missing build/release check: {surface}"


def test_main_returns_zero(build_check: Any) -> None:
    assert build_check.main(["--json"]) == 0


def test_run_checks_flags_a_missing_pyproject(
    build_check: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A missing pyproject must be a failure, not a silent pass."""
    monkeypatch.setattr(build_check, "PYPROJECT", tmp_path / "absent.toml")
    checks, data = build_check._pyproject_checks()
    assert data is None
    assert any(not c.ok for c in checks)
