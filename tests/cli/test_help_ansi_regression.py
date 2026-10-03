"""Regression locks: ``--help`` / usage assertions must be ANSI-immune.

rich/typer render help output with ANSI escapes whenever the runtime looks
like a terminal (``TTY_COMPATIBLE=1``, ``PY_COLORS=1``, ``FORCE_COLOR``,
``GITHUB_ACTIONS``).  A style boundary can land inside a double-dash flag —
``--domain`` arrives as ``\\x1b[1;33m-\\x1b[0m\\x1b[1;36m-domain\\x1b[0m`` — so a
naive ``assert "--domain" in result.stdout`` fails on CI while the flag is
genuinely printed.

These tests pin both halves of the fix:

1. ``strip_ansi`` really recovers the flag from styled text (unit level).
2. A real ANSI-rendered ``--help`` still satisfies the assertion style used
   across the suite (integration level).

Neither check weakens anything: the visible text is never dropped, only the
escape sequences are.
"""

from __future__ import annotations

import pytest

from tests._ansi import strip_ansi

#: A styled option line as rich/typer emit it inside a help panel: the panel
#: rule, then ``-`` and ``-domain`` under two different styles.
ANSI_STYLED_OPTION = "\x1b[1m│\x1b[0m \x1b[1;36m-\x1b[0m\x1b[1;36m-domain\x1b[0m"

#: The escape sequences rich uses most: bold, bold-yellow, dim, default-fg.
ANSI_SAMPLE = (
    "\x1b[1mbold\x1b[0m "
    "\x1b[1;33m-\x1b[0m\x1b[1;36m-domain\x1b[0m "
    "\x1b[2mconsole\x1b[0m "
    "\x1b[39mplain\x1b[0m"
)


class TestStripAnsiUnit:
    """Unit-level proof that the helper recovers split double-dash flags."""

    def test_rich_styled_option_is_genuinely_split(self) -> None:
        # The fixture must be a real split, otherwise the next test is vacuous.
        assert "--domain" not in ANSI_STYLED_OPTION
        assert "\x1b[" in ANSI_STYLED_OPTION

    def test_strip_ansi_recovers_double_dash_flag(self) -> None:
        assert "--domain" in strip_ansi(ANSI_STYLED_OPTION)

    def test_strip_ansi_handles_common_rich_sequences(self) -> None:
        # \x1b[1m / \x1b[1;33m / \x1b[0m / \x1b[2m / \x1b[39m all end in a letter.
        # The styled "-" + "-domain" pair must reassemble into "--domain".
        assert strip_ansi(ANSI_SAMPLE) == "bold --domain console plain"

    def test_strip_ansi_is_a_noop_on_plain_text(self) -> None:
        assert strip_ansi("--domain --json") == "--domain --json"


class TestHelpUnderForcedAnsi:
    """Integration-level: a real ANSI-rendered ``--help`` still passes."""

    def test_sources_list_help_assertions_survive_ansi(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from typer.testing import CliRunner

        from autoinfo.cli import app

        # rich reads TTY_COMPATIBLE per render, so forcing it here really does
        # turn on escape sequences for this invocation only.
        monkeypatch.setenv("TTY_COMPATIBLE", "1")

        result = CliRunner().invoke(app, ["sources", "list", "--help"])
        assert result.exit_code == 0
        assert "\x1b[" in result.stdout, (
            "expected rich to render ANSI under TTY_COMPATIBLE=1 — "
            "otherwise this test no longer exercises the CI failure mode"
        )
        # The assertion style the suite uses on help text.
        assert "--domain" in strip_ansi(result.stdout)

    def test_usage_error_assertions_survive_ansi(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from typer.testing import CliRunner

        from autoinfo.cli import app

        monkeypatch.setenv("TTY_COMPATIBLE", "1")

        # --domain is given, so typer fails on the missing --target-lang and
        # prints the option name inside its error panel — styled, i.e. split.
        result = CliRunner().invoke(
            app, ["output", "localize", "--domain", "medical-research"]
        )
        assert result.exit_code != 0
        assert "\x1b[" in result.output
        assert "--target-lang" in strip_ansi(result.output)
