from __future__ import annotations
"""Keywords CLI — manage per-domain keyword lifecycle.

Usage::

    autoinfo keywords list --domain medical
    autoinfo keywords list --domain medical --status auto_added
    autoinfo keywords approve medical "IVF"
    autoinfo keywords reject medical "IVF"
"""

import typer

from autoinfo.keywords import KeywordsFile, KeywordState

app = typer.Typer(help="Manage per-domain keyword lifecycle")


def _find_state(status: str | None) -> KeywordState | None:
    """Parse a status string into a :class:`KeywordState`, or ``None``."""
    if status is None:
        return None
    try:
        return KeywordState(status.lower())
    except ValueError:
        typer.echo(
            f"Error: Invalid status '{status}'. "
            f"Valid: verified, auto_added, deprecated",
            err=True,
        )
        raise typer.Exit(code=1) from None


@app.command()
def list(  # noqa: A001 — shadowing built-in list is intentional for CLI
    domain: str = typer.Option(..., "--domain", help="Domain name"),
    status: str | None = typer.Option(
        None, "--status", help="Filter by state (verified, auto_added, deprecated)"
    ),
) -> None:
    """List keywords for a domain, optionally filtered by status."""
    state = _find_state(status)
    kf = KeywordsFile()
    entries = kf.list_keywords(domain=domain, status=state)

    if not entries:
        msg = f"No keywords found for domain '{domain}'"
        if status:
            msg += f" with status '{status}'"
        typer.echo(msg)
        return

    # Determine column widths
    kw_width = max(len(e.keyword) for e in entries) + 2
    state_width = max(len(e.state.value) for e in entries) + 2
    source_width = max((len(e.source) if e.source else 4) for e in entries) + 2

    header = (
        f"{'Keyword':<{kw_width}} {'State':<{state_width}} "
        f"{'Source':<{source_width}} Created"
    )
    typer.echo(header)
    typer.echo("-" * len(header))
    for e in entries:
        typer.echo(
            f"{e.keyword:<{kw_width}} {e.state.value:<{state_width}} "
            f"{(e.source or '-'):<{source_width}} {e.created_at or '-'}"
        )


@app.command()
def approve(
    domain: str = typer.Argument(..., help="Domain name"),
    keyword: str = typer.Argument(..., help="Keyword to approve"),
) -> None:
    """Approve a keyword (move from auto_added → verified)."""
    kf = KeywordsFile()
    result = kf.approve_keyword(domain=domain, keyword=keyword)
    if result is None:
        typer.echo(
            f"Error: Keyword '{keyword}' not found in domain '{domain}'",
            err=True,
        )
        raise typer.Exit(code=1)
    typer.echo(f"Approved keyword '{keyword}' in domain '{domain}' (→ verified)")


@app.command()
def reject(
    domain: str = typer.Argument(..., help="Domain name"),
    keyword: str = typer.Argument(..., help="Keyword to reject"),
) -> None:
    """Reject a keyword (move to deprecated)."""
    kf = KeywordsFile()
    result = kf.deprecate_keyword(domain=domain, keyword=keyword)
    if result is None:
        typer.echo(
            f"Error: Keyword '{keyword}' not found in domain '{domain}'",
            err=True,
        )
        raise typer.Exit(code=1)
    typer.echo(f"Rejected keyword '{keyword}' in domain '{domain}' (→ deprecated)")
