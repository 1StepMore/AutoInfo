"""Thin CLI forward to the single governance entry point (T04).

``autoinfo gov <verb> ...`` forwards argv verbatim to
``autoinfo.gov.__main__.main`` — zero business logic, byte-identical output.
Deliberately a single passthrough *command*, not a Typer sub-app, so the
derived ``cli_groups`` fact stays at 31 (a sub-app would shift every count
surface without adding a real group). Registered in ``cli/__init__.py`` via
``app.command(...)`` on the existing app (no new entry point).
"""

from __future__ import annotations

from typing import Any

import typer

_GOV_CONTEXT = {"allow_extra_args": True, "ignore_unknown_options": True}


def gov(ctx: typer.Context) -> Any:
    """Forward everything after ``gov`` to ``python -m autoinfo.gov``."""
    from autoinfo.gov.__main__ import main as gov_main

    code = gov_main(list(ctx.args))
    raise typer.Exit(code=code)
