from __future__ import annotations

"""Email CLI — send digest emails via SMTP.

Usage::

    autoinfo email send-digest --domain medical-research --period weekly
    autoinfo email config
    autoinfo email config --smtp-server smtp.gmail.com --smtp-port 587 --enable
"""


import smtplib
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

import typer

from autoinfo.config import Config, EmailConfig, get_config_path, load_config, save_config

app = typer.Typer(help="Send email digests via SMTP")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load() -> tuple[Path, Config]:
    """Load the config and return ``(config_path, config)``.

    Exits with code 1 when no project config exists.
    """
    cfg_path = get_config_path()
    if cfg_path is None:
        typer.echo("Error: No configuration found. Run 'autoinfo init' first. See docs/dev/required-api-keys.md for API key setup.", err=True)
        raise typer.Exit(1)
    config = load_config(cfg_path)
    return cfg_path, config


def _send_test_email(email_cfg: EmailConfig) -> None:
    """Send a simple test email using the current SMTP configuration."""
    if not email_cfg.smtp_host:
        typer.echo("Error: SMTP server not configured. Use --smtp-server first.", err=True)
        raise typer.Exit(1)

    from_addr = email_cfg.from_addr or email_cfg.smtp_user
    if not from_addr:
        typer.echo(
            "Error: No from address configured. Set email.from_addr in config.", err=True
        )
        raise typer.Exit(1)

    to_addrs = email_cfg.to_addrs
    if not to_addrs:
        typer.echo(
            "Error: No recipients configured. Set email.to_addrs in config.", err=True
        )
        raise typer.Exit(1)

    msg = MIMEText(
        "This is a test email from AutoInfo.\n\n"
        "If you received this, SMTP configuration is working correctly."
    )
    msg["Subject"] = "[AutoInfo] Test Email"
    msg["From"] = from_addr
    msg["To"] = ", ".join(to_addrs)

    server = None
    try:
        server = smtplib.SMTP(email_cfg.smtp_host, email_cfg.smtp_port, timeout=30)
        server.ehlo()
        if server.has_extn("STARTTLS"):
            server.starttls()
            server.ehlo()
        if email_cfg.smtp_user and email_cfg.smtp_pass:
            server.login(email_cfg.smtp_user, email_cfg.smtp_pass)
        server.sendmail(from_addr, to_addrs, msg.as_string())
        typer.echo(f"Test email sent successfully to {', '.join(to_addrs)}")
    except smtplib.SMTPException as exc:
        typer.echo(f"Error: SMTP delivery failed: {exc}", err=True)
        raise typer.Exit(1) from exc
    except Exception as exc:
        typer.echo(f"Error: Test email failed: {exc}", err=True)
        raise typer.Exit(1) from exc
    finally:
        if server is not None:
            try:
                server.quit()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


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


@app.command()
def config(
    smtp_server: Optional[str] = typer.Option(
        None, "--smtp-server", help="SMTP server hostname"
    ),
    smtp_port: Optional[int] = typer.Option(
        None, "--smtp-port", help="SMTP server port"
    ),
    username: Optional[str] = typer.Option(
        None, "--username", help="SMTP username"
    ),
    password: Optional[str] = typer.Option(
        None, "--password", help="SMTP password"
    ),
    enable: bool = typer.Option(
        False, "--enable", help="Enable email sending"
    ),
    disable: bool = typer.Option(
        False, "--disable", help="Disable email sending"
    ),
    test: bool = typer.Option(
        False, "--test", help="Send a test email using current config"
    ),
) -> None:
    """View or update email SMTP configuration.

    Displays current email settings from ``.autoinfo/config.yaml``.
    Use options to update individual fields. Password is masked in output.
    """
    cfg_path, cfg = _load()
    email_cfg = cfg.email

    # --conflict detection & change tracking--
    if enable and disable:
        typer.echo("Error: Cannot use both --enable and --disable.", err=True)
        raise typer.Exit(1)

    changed = False

    if smtp_server is not None:
        email_cfg.smtp_host = smtp_server
        changed = True
    if smtp_port is not None:
        email_cfg.smtp_port = smtp_port
        changed = True
    if username is not None:
        email_cfg.smtp_user = username
        changed = True
    if password is not None:
        email_cfg.smtp_pass = password
        changed = True
    if enable:
        email_cfg.enabled = True
        changed = True
    if disable:
        email_cfg.enabled = False
        changed = True

    if changed:
        save_config(cfg, cfg_path)
        typer.echo("Email configuration updated.")
        typer.echo("")

    # --display current configuration--
    password_display = "****" if email_cfg.smtp_pass else "(not set)"
    to_str = ", ".join(email_cfg.to_addrs) if email_cfg.to_addrs else "(not set)"

    typer.echo("Email Configuration:")
    typer.echo(f"  SMTP Server:   {email_cfg.smtp_host or '(not set)'}")
    typer.echo(f"  SMTP Port:     {email_cfg.smtp_port}")
    typer.echo(f"  Username:      {email_cfg.smtp_user or '(not set)'}")
    typer.echo(f"  Password:      {password_display}")
    typer.echo(f"  From Address:  {email_cfg.from_addr or '(not set)'}")
    typer.echo(f"  To Addresses:  {to_str}")
    typer.echo(f"  Enabled:       {'yes' if email_cfg.enabled else 'no'}")

    # --optional test email--
    if test:
        typer.echo("")
        _send_test_email(email_cfg)
