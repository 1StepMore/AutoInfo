"""Issue #801: ``load_config`` loads a dotenv layer before ``${ENV}`` expansion."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pytest

from autoinfo.config import _parse_dotenv, load_config

KEY = "TEST_DOTENV_KEY"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(KEY, raising=False)
    monkeypatch.delenv("AUTOINFO_DOTENV", raising=False)


def _write_config(root: Path, api_key: str = "${TEST_DOTENV_KEY}") -> Path:
    config_path = root / ".autoinfo" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(f"llm:\n  api_key: {api_key}\n", encoding="utf-8")
    return config_path


def _write_dotenv(path: Path, contents: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")
    return path


def test_dotenv_next_to_config_is_loaded(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path / "proj")
    _write_dotenv(config_path.parent / ".env", f"{KEY}=from-dotenv\n")

    config = load_config(config_path)

    assert config.llm.api_key == "from-dotenv"


def test_real_env_var_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = _write_config(tmp_path / "proj")
    _write_dotenv(config_path.parent / ".env", f"{KEY}=from-dotenv\n")
    monkeypatch.setenv(KEY, "from-env")

    config = load_config(config_path)

    assert config.llm.api_key == "from-env"


def test_autoinfo_dotenv_overrides_location(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = _write_config(tmp_path / "proj")
    _write_dotenv(config_path.parent / ".env", f"{KEY}=from-project\n")
    other = _write_dotenv(tmp_path / "elsewhere" / "custom.env", f"{KEY}=from-override\n")
    monkeypatch.setenv("AUTOINFO_DOTENV", str(other))

    config = load_config(config_path)

    assert config.llm.api_key == "from-override"


def test_autoinfo_dotenv_missing_falls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    config_path = _write_config(tmp_path / "proj")
    _write_dotenv(config_path.parent / ".env", f"{KEY}=from-project\n")
    missing = tmp_path / "nope" / "custom.env"
    monkeypatch.setenv("AUTOINFO_DOTENV", str(missing))

    config = load_config(config_path)

    assert config.llm.api_key == "from-project"
    assert any("AUTOINFO_DOTENV points at" in r.getMessage() for r in caplog.records)


def test_parse_dotenv_rules(tmp_path: Path) -> None:
    path = _write_dotenv(
        tmp_path / ".env",
        "\n".join(
            [
                "# a comment",
                "",
                '  QUOTED_DOUBLE = "hello world"  ',
                "QUOTED_SINGLE='single'",
                "NO_EQUALS_LINE",
                "export EXPORTED=exported-value",
                'UNPAIRED="mismatch\'',
                "EMPTY=",
            ]
        ),
    )

    values = _parse_dotenv(path)

    assert values["QUOTED_DOUBLE"] == "hello world"
    assert values["QUOTED_SINGLE"] == "single"
    assert values["EXPORTED"] == "exported-value"
    assert values["UNPAIRED"] == "\"mismatch'"
    assert values["EMPTY"] == ""
    assert "NO_EQUALS_LINE" not in values
    assert len(values) == 5


def test_cwd_dotenv_is_not_loaded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = _write_config(tmp_path / "proj")
    cwd = tmp_path / "cwd"
    _write_dotenv(cwd / ".env", f"{KEY}=from-cwd\n")
    monkeypatch.chdir(cwd)

    config = load_config(config_path)

    assert KEY not in os.environ
    assert config.llm.api_key == ""


def test_no_dotenv_is_silent(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="autoinfo.config")
    config_path = _write_config(tmp_path / "proj")

    config = load_config(config_path)

    assert config.llm.api_key == ""
    assert not [r for r in caplog.records if "loaded " in r.getMessage() and " from " in r.getMessage()]
