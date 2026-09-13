"""Global ``--json`` envelope helper for the AutoInfo CLI (T-S-07).

The root callback (``src/autoinfo/cli/__init__.py``) accepts a global
``--json`` flag before any command (``autoinfo --json <group> <cmd>``) and
records it in a :class:`contextvars.ContextVar`.  This module turns that flag
into the same canonical envelope every MCP tool returns:

* success: ``{"success": true, "data": ...}``
* failure: ``{"success": false, "error": {"code", "message", "actionable"}}``

Why a ContextVar instead of a ``ctx.obj`` read in every command:

* Commands can honour the global flag **without** a signature change, so
  tests and internal callers that invoke command callables directly keep
  working (the flag defaults to ``False`` outside a CLI invocation).
* The root callback is the single writer; every command module is a reader
  via :func:`emit_if_global` / :func:`fail_if_global`.

Per-command ``--json`` flags keep their historical (bespoke) shapes — only the
**global** flag is normalised to the canonical envelope, so script consumers
get byte-identical structure from the MCP surface.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from contextvars import ContextVar
from typing import Any

import typer

from autoinfo.mcp.errors import error_response

_GLOBAL_JSON: ContextVar[bool] = ContextVar("autoinfo_cli_global_json", default=False)


class _EnvelopeExit(SystemExit):
    """Exit signal for the canonical envelope.

    Deliberately a :class:`SystemExit` (BaseException) rather than
    ``typer.Exit`` (an ``Exception``): command bodies wrap their work in
    ``except Exception`` for error reporting, and a ``typer.Exit`` raised by
    :func:`fail_if_global` would be swallowed there — emitting a second
    envelope and losing the exit code.
    """


def set_global_json(enabled: bool) -> None:
    """Record whether the global ``--json`` flag is active (root callback)."""
    _GLOBAL_JSON.set(bool(enabled))


def global_json() -> bool:
    """Return ``True`` when the global ``--json`` flag is active."""
    return _GLOBAL_JSON.get()


def detect_global_json(argv: Sequence[str]) -> bool:
    """Return ``True`` when the *global* ``--json`` flag leads *argv*.

    The root callback (which calls :func:`set_global_json`) runs *after*
    ``Group.invoke`` resolves the command, so it never runs for an unknown
    top-level command or a bad group-level flag.  This argv scan is the only
    signal available in those cases.

    Only **leading** option tokens are inspected — the scan stops at the first
    non-``-`` token — so a per-command ``--json`` (e.g. ``domain list --json``)
    is not misread as the global flag.  The root group has no value-taking
    option, so stopping at the first positional token is safe.
    """
    for token in argv:
        if not token.startswith("-") or token == "-":
            return False
        if token == "--json":
            return True
    return False


def is_usage_error(exc: BaseException) -> bool:
    """Return ``True`` when *exc* is a Click/Typer usage error.

    Typer vendors Click under ``typer._click``, so the installed
    ``click.exceptions.UsageError`` is a **different class** — an ``isinstance``
    check against it would miss.  Usage errors (``UsageError``, ``BadParameter``,
    ``NoSuchOption``, …) all carry ``exit_code == 2``; classify structurally.
    """
    return getattr(exc, "exit_code", None) == 2


def emit_error_envelope(
    code: str,
    message: str,
    actionable: bool = True,
) -> None:
    """Write the canonical error envelope unconditionally (no ContextVar gate)."""
    typer.echo(
        json.dumps(
            error_response(code, message, actionable),
            ensure_ascii=False,
            indent=2,
        )
    )


def emit_if_global(data: Any) -> bool:
    """Emit the canonical success envelope when global ``--json`` is active.

    Returns ``True`` when the envelope was written (the caller should stop so
    the human path is not also printed), ``False`` otherwise.
    """
    if not global_json():
        return False
    typer.echo(json.dumps({"success": True, "data": data}, ensure_ascii=False, indent=2))
    return True


def fail_if_global(
    code: str,
    message: str,
    actionable: bool = True,
    exit_code: int = 1,
) -> None:
    """Emit the canonical error envelope when global ``--json`` is active.

    Raises :class:`typer.Exit` after writing the envelope.  A no-op outside
    global json mode so the command's existing human error path runs instead.
    """
    if not global_json():
        return
    emit_error_envelope(code, message, actionable)
    raise _EnvelopeExit(exit_code)
