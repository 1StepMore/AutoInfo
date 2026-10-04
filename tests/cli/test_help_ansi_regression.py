"""Regression locks: ``--help`` / usage assertions must be ANSI-immune.

rich/typer render help output with ANSI escapes whenever the runtime looks
like a terminal (``TTY_COMPATIBLE=1``, ``PY_COLORS=1``, ``FORCE_COLOR``,
``GITHUB_ACTIONS``).  A style boundary can land inside a double-dash flag —
``--domain`` arrives as ``\\x1b[1;33m-\\x1b[0m\\x1b[1;36m-domain\\x1b[0m`` — so a
naive ``assert "--domain" in result.stdout`` fails on CI while the flag is
genuinely printed.

CI, however, pins ``TERM=dumb`` precisely to suppress ANSI, so *whether* an
invocation is colourised is an environment detail these tests must not
depend on.  The contract under test is unconditional:

    **help/usage assertions written as ``"--flag" in strip_ansi(text)`` hold
    on the same output regardless of whether it carries ANSI.**

These tests pin both halves of the fix:

1. ``strip_ansi`` really recovers the flag from styled text (unit level).
2. A real ``--help`` / usage-error invocation satisfies the assertion style
   used across the suite, and the same real output still satisfies it after
   rich's own escape pattern is spliced into it (integration level, coloured
   path covered by controlled injection rather than by trusting the
   environment to colourise).

Neither check weakens anything: the visible text is never dropped, only the
escape sequences are.
"""

from __future__ import annotations

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


def splice_rich_style(text: str, flag: str) -> str:
    """Return ``text`` with its first ``flag`` split exactly the way rich does.

    This is the *controlled injection* used to cover the coloured path: the
    rendering entry point is not poked at and no environment variable is
    trusted — rich's escape pattern is spliced into the real rendered output
    so the test exercises a genuinely split flag whatever the runtime did.

    The splice anchors on ``strip_ansi(text)`` so it behaves identically when
    the environment already colourised the output (where ``flag`` is then
    split and not findable contiguously).
    """
    assert flag.startswith("--"), flag
    base = strip_ansi(text)
    assert flag in base, f"{flag!r} absent from output — nothing to splice"
    styled = f"\x1b[1;33m-\x1b[0m\x1b[1;36m{flag[1:]}\x1b[0m"
    injected = base.replace(flag, styled, 1)
    # Non-vacuous: the escape sequence really landed and the raw flag no
    # longer exists contiguously at that position.
    assert "\x1b[1;33m-" in injected
    assert injected.count(flag) == base.count(flag) - 1
    return injected


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


class TestHelpAssertionsSurviveAnsi:
    """Integration-level: the assertion style holds on real CLI output.

    No environment precondition — CI's ``TERM=dumb`` yields plain help text
    and a plain usage error, and that must pass exactly like a colourised
    run.  The coloured path is covered by ``splice_rich_style`` below.
    """

    def test_sources_list_help_assertions_survive_ansi(self) -> None:
        from typer.testing import CliRunner

        from autoinfo.cli import app

        result = CliRunner().invoke(app, ["sources", "list", "--help"])
        assert result.exit_code == 0
        # The assertion style the suite uses on help text — must hold on the
        # output exactly as the environment produced it.
        assert "--domain" in strip_ansi(result.stdout)
        # ...and on that output re-styled with rich's escape pattern.
        coloured = splice_rich_style(result.stdout, "--domain")
        assert "--domain" in strip_ansi(coloured)

    def test_usage_error_assertions_survive_ansi(self) -> None:
        from typer.testing import CliRunner

        from autoinfo.cli import app

        # --domain is given, so typer fails on the missing --target-lang and
        # prints the option name inside its error panel.
        result = CliRunner().invoke(app, ["output", "localize", "--domain", "medical-research"])
        assert result.exit_code != 0
        assert "--target-lang" in strip_ansi(result.output)
        coloured = splice_rich_style(result.output, "--target-lang")
        assert "--target-lang" in strip_ansi(coloured)
