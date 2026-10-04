"""ANSI-escape helpers for CLI output assertions.

rich/typer render ``--help`` and usage output with ANSI styling whenever the
runtime looks like a terminal (``TTY_COMPATIBLE=1``, ``PY_COLORS=1``,
``FORCE_COLOR``, ``GITHUB_ACTIONS``, ...).  A style boundary can land inside
a double-dash option, so ``--domain`` arrives as::

    \\x1b[1;33m-\\x1b[0m\\x1b[1;36m-domain\\x1b[0m

and a naive ``assert "--domain" in result.stdout`` fails even though the
option is genuinely printed.  Assertions must therefore run on the de-styled
text: ``assert "--domain" in strip_ansi(result.stdout)``.

``strip_ansi`` only removes escape sequences — it never drops, rewrites or
weakens the visible text, so no assertion becomes looser by using it.
"""

from __future__ import annotations

import re

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
"""CSI sequences: ``\\x1b[1m``, ``\\x1b[1;33m``, ``\\x1b[0m``, ``\\x1b[39m``, ..."""


def strip_ansi(text: str) -> str:
    """Return ``text`` with ANSI CSI escape sequences removed."""
    return _ANSI_RE.sub("", text)
