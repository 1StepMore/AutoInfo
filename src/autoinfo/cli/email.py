from __future__ import annotations

"""Email CLI — send digest emails via SMTP.

Usage::

    autoinfo email send-digest --domain medical-research --period weekly
"""


import typer

app = typer.Typer(help="Send email digests via SMTP")


@app.command(name="send-digest")
def send_digest(
    domain: str = typer.Option(..., "--domain", help="Domain to generate digest for"),
    period: str = typer.Option(
        "weekly", "--period", help="Digest period: daily, weekly, monthly"
    ),
) -> None:
    """Generate and send a digest email for a domain over the given period.

    Reads SMTP configuration from ``.autoinfo/config.yaml`` (``email.*`` section).
    Only sends when ``email.enabled`` is ``true``.
    """
    from autoinfo.email_sender import send_digest as _send  # noqa: PLC0415

    try:
        result = _send(domain=domain, period=period)
        typer.echo(result["message"])
        if result.get("entry_count", 0) >= 0:
            typer.echo(f"  Domain: {result['domain']}")
            typer.echo(f"  Period: {result['period']}")
            typer.echo(f"  Recipients: {', '.join(result['recipients'])}")
    except RuntimeError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        typer.echo(f"Unexpected error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
