"""Build/release surface validation tests (T-S-11).

Exercises `scripts/build_release_check.py` — the executable form of the
methodology's build-from-AGENTS acid test: editable install importable,
version synced with the release-please manifest, console script registered,
pyproject structurally sound.
"""

from __future__ import annotations

import importlib
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


def test_cli_group_count_is_reconciled_against_the_code(build_check: Any) -> None:
    """Docs and code must agree on the CLI group count.

    `doc_inventory.py --check` only compares the docs to each other, so a
    consistently wrong number passes it; this assertion is the docs-to-code
    half that was missing when `32` sat on `main` with a green build.
    """
    names = " | ".join(c.name for c in build_check.run_checks())
    assert "documented CLI group count" in names

    cli = importlib.import_module("autoinfo.cli")
    registered = len(getattr(cli.app, "registered_groups", []))

    matching = build_check._cli_group_count_matches_docs(registered)
    assert matching.ok, f"docs/code disagree on {registered}: {matching.detail}"

    drifted = build_check._cli_group_count_matches_docs(registered + 1)
    assert not drifted.ok
    assert "registered" in drifted.detail


def test_declared_cli_group_count_ignores_a_missing_readme(
    build_check: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(build_check, "README", tmp_path / "absent.md")
    monkeypatch.setattr(build_check, "ROOT", tmp_path)
    assert build_check._declared_cli_group_count() is None
    check = build_check._cli_group_count_matches_docs(31)
    assert not check.ok
    assert "declares no CLI" in check.detail
