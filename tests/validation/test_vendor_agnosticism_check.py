"""Model/vendor agnosticism contract tests (T-S-12; AGENTS #194/#195).

Exercises `scripts/vendor_agnosticism_check.py`: no `JUDGMENT_MODEL` code
constant, no vendor/model literal in judge/battery executable code, vendor-free
blind-spot descriptions, config-driven battery channel, and config-first
judgment resolution (override → llm.model → loud error).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
VENDOR_SCRIPT = ROOT / "scripts" / "vendor_agnosticism_check.py"


@pytest.fixture(scope="module")
def vendor_check() -> Any:
    spec = importlib.util.spec_from_file_location("vendor_agnosticism_check", VENDOR_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_all_vendor_agnosticism_checks_pass(vendor_check: Any) -> None:
    checks = vendor_check.run_checks()
    failed = [f"{c.name}: {c.detail}" for c in checks if not c.ok]
    assert not failed, "\n".join(failed)


def test_no_judgment_model_constant(vendor_check: Any) -> None:
    check = vendor_check._judgment_constant_check()
    assert check.ok, check.detail


def test_blindspots_are_vendor_free(vendor_check: Any) -> None:
    check = vendor_check._blindspots_check()
    assert check.ok, check.detail


def test_battery_uses_config_channel(vendor_check: Any) -> None:
    check = vendor_check._battery_channel_check()
    assert check.ok, check.detail


def test_docstrings_are_not_scanned(vendor_check: Any, tmp_path: Path) -> None:
    """A vendor name in a docstring/comment is documentation, not a literal."""
    sample = tmp_path / "sample.py"
    sample.write_text(
        '"""Module docstring mentioning openai/deepseek."""\n'
        "\n"
        "def f() -> None:\n"
        '    """Function docstring mentioning claude."""\n'
        "    # comment mentioning openrouter\n",
        encoding="utf-8",
    )
    assert vendor_check._non_docstring_string_constants(sample) == []


def test_executable_vendor_literal_is_flagged(
    vendor_check: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A judge path that pins a vendor model must fail the contract."""
    sample = tmp_path / "judge.py"
    sample.write_text('MODEL = "deepseek/deepseek-chat"\n', encoding="utf-8")
    monkeypatch.setattr(vendor_check, "JUDGE_PATHS", (sample,))
    check = vendor_check._judge_path_vendor_check()
    assert not check.ok
    assert "deepseek" in check.detail


def test_main_returns_zero(vendor_check: Any) -> None:
    assert vendor_check.main(["--json"]) == 0
