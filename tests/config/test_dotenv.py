"""Tests for user-level dotenv loading (``autoinfo.dotenv``, issue #847).

``~/.autoinfo/.env`` lets the owner keep credentials out of the frozen
harness process environment.  Contract under test:

- parser: comments / blanks / ``export `` prefix / paired quotes; keys
  must be identifiers; malformed lines are skipped, never fatal.
- ``load_user_env``: **setdefault semantics** — the process environment
  always wins, file values only fill gaps; missing file is a no-op.
- secrets hygiene: diagnostics carry key names only, never values.

All tests run against ``tmp_path`` files; the developer's real
``~/.autoinfo/.env`` is never touched.
"""

from __future__ import annotations

import os

import pytest

from autoinfo.dotenv import load_user_env, parse_env_text

# --- parse_env_text ------------------------------------------------------


def test_parse_basic_pair() -> None:
    assert parse_env_text("FOO=bar\n") == {"FOO": "bar"}


def test_parse_comments_and_blanks() -> None:
    text = "# a comment\n\n  # indented comment\nKEY=value\n"
    assert parse_env_text(text) == {"KEY": "value"}


def test_parse_export_prefix() -> None:
    assert parse_env_text("export FOO=bar\nexport\tBAD=no-space-after-export\n") == {"FOO": "bar"}


def test_parse_strips_whitespace_around_key_and_value() -> None:
    assert parse_env_text("  FOO  =  bar  \n") == {"FOO": "bar"}


def test_parse_strips_paired_quotes() -> None:
    text = "A='x y'\nB=\"z w\"\nC='mismatch\"\n"
    assert parse_env_text(text) == {"A": "x y", "B": "z w", "C": "'mismatch\""}


def test_parse_empty_value_is_kept() -> None:
    assert parse_env_text("EMPTY=\n") == {"EMPTY": ""}


def test_parse_skips_lines_without_equals() -> None:
    assert parse_env_text("NOTAPAIR\nKEY=v\n") == {"KEY": "v"}


def test_parse_skips_non_identifier_keys() -> None:
    text = "1BAD=v\nHAS SPACE=v\nOK_KEY=v\n"
    assert parse_env_text(text) == {"OK_KEY": "v"}


def test_parse_colon_credentials_survive() -> None:
    # iFlytek-style "APIKey:APISecret" bearer values must round-trip.
    assert parse_env_text("KEY=abc:def:ghi\n") == {"KEY": "abc:def:ghi"}


def test_parse_no_interpolation() -> None:
    # Documented non-feature: $VAR is passed through verbatim.
    assert parse_env_text("KEY=$HOME/bin\n") == {"KEY": "$HOME/bin"}


# --- load_user_env -------------------------------------------------------


def test_load_missing_file_is_noop(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("AUTOINFO_DOTENV_TEST_X", raising=False)
    loaded = load_user_env(tmp_path / "absent.env")
    assert loaded == []
    assert "AUTOINFO_DOTENV_TEST_X" not in os.environ


def test_load_fills_missing_keys(tmp_path) -> None:
    f = tmp_path / "user.env"
    f.write_text("AUTOINFO_DOTENV_TEST_A=from-file\n", encoding="utf-8")
    loaded = load_user_env(f)
    assert loaded == ["AUTOINFO_DOTENV_TEST_A"]
    assert os.environ["AUTOINFO_DOTENV_TEST_A"] == "from-file"
    del os.environ["AUTOINFO_DOTENV_TEST_A"]


def test_load_never_overrides_process_environment(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AUTOINFO_DOTENV_TEST_B", "from-process")
    f = tmp_path / "user.env"
    f.write_text(
        "AUTOINFO_DOTENV_TEST_B=from-file\nAUTOINFO_DOTENV_TEST_C=file-only\n", encoding="utf-8"
    )
    loaded = load_user_env(f)
    # Existing var untouched; only the gap was filled.
    assert loaded == ["AUTOINFO_DOTENV_TEST_C"]
    assert os.environ["AUTOINFO_DOTENV_TEST_B"] == "from-process"
    del os.environ["AUTOINFO_DOTENV_TEST_C"]


def test_load_tolerates_utf8_bom(tmp_path) -> None:
    f = tmp_path / "bom.env"
    f.write_bytes("AUTOINFO_DOTENV_TEST_D=v\n".encode("utf-8-sig"))
    loaded = load_user_env(f)
    assert loaded == ["AUTOINFO_DOTENV_TEST_D"]
    del os.environ["AUTOINFO_DOTENV_TEST_D"]


def test_load_skips_malformed_lines_but_loads_rest(tmp_path) -> None:
    f = tmp_path / "mixed.env"
    f.write_text(
        "# comment\nGARBAGE LINE\nAUTOINFO_DOTENV_TEST_E=v\nBAD-NAME=v\n",
        encoding="utf-8",
    )
    loaded = load_user_env(f)
    assert loaded == ["AUTOINFO_DOTENV_TEST_E"]
    del os.environ["AUTOINFO_DOTENV_TEST_E"]


def test_load_is_idempotent_process_env_wins_on_second_call(tmp_path) -> None:
    f = tmp_path / "user.env"
    f.write_text("AUTOINFO_DOTENV_TEST_F=v1\n", encoding="utf-8")
    assert load_user_env(f) == ["AUTOINFO_DOTENV_TEST_F"]
    # Second call: the key now exists (set by the first call) — not reloaded.
    assert load_user_env(f) == []
    assert os.environ["AUTOINFO_DOTENV_TEST_F"] == "v1"
    del os.environ["AUTOINFO_DOTENV_TEST_F"]


@pytest.mark.parametrize("content", ["", "\n", "# only comments\n"])
def test_load_empty_or_comment_only_file_loads_nothing(tmp_path, content) -> None:
    f = tmp_path / "empty.env"
    f.write_text(content, encoding="utf-8")
    assert load_user_env(f) == []
