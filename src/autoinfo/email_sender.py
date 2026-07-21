"""SMTP email digest delivery for AutoInfo.

Uses stdlib ``smtplib`` and ``email.mime`` — no additional dependencies.
"""

from __future__ import annotations

import logging
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from autoinfo.config import Config, EmailConfig, get_config_path, load_config
from autoinfo.output import PERIOD_LABELS, generate_digest

logger = logging.getLogger(__name__)


def send_digest(
    domain: str,
    period: str = "weekly",
    config: Config | None = None,
) -> dict[str, Any]:
    """Generate and send an email digest via SMTP.

    Parameters
    ----------
    domain:
        Domain to generate the digest for.
    period:
        Digest period: ``"daily"``, ``"weekly"``, ``"monthly"``.
    config:
        Optional :class:`Config` override. Auto-detected from project when
        omitted.

    Returns
    -------
    dict
        Keys: ``success`` (bool), ``message`` (str), ``recipients`` (list),
        ``domain``, ``period``, ``entry_count``.

    Raises
    ------
    RuntimeError
        If email is not enabled in config, SMTP is not properly configured,
        or the SMTP server rejects the message.
    """
    # --- Load config ---
    if config is None:
        config_path = get_config_path()
        if config_path is None:
            raise RuntimeError("No configuration file found. Run 'autoinfo init' first.")
        config = load_config(config_path)

    email_cfg = config.email

    # --- Guard: email must be enabled ---
    if not email_cfg.enabled:
        raise RuntimeError(
            "Email delivery is not enabled. Set 'email.enabled: true' in config."
        )

    # --- Validate SMTP settings ---
    if not email_cfg.smtp_host:
        raise RuntimeError("SMTP host not configured (email.smtp_host)")
    if not email_cfg.from_addr:
        raise RuntimeError("From address not configured (email.from_addr)")
    if not email_cfg.to_addrs:
        raise RuntimeError("No recipients configured (email.to_addrs)")

    # --- Generate digest content ---
    try:
        digest_md = generate_digest(
            domain=domain, period=period, format="markdown", llm_config=config
        )
    except ValueError as exc:
        raise RuntimeError(f"Digest generation failed: {exc}") from exc

    digest_html = _md_to_html(digest_md)

    # --- Build email ---
    msg = MIMEMultipart("alternative")
    msg["Subject"] = _build_subject(domain, period)
    msg["From"] = email_cfg.from_addr
    msg["To"] = ", ".join(email_cfg.to_addrs)
    msg["Date"] = _format_date()

    # Plaintext part
    part_plain = MIMEText(digest_md, "plain", "utf-8")
    msg.attach(part_plain)

    # HTML part
    html_body = _build_html_wrapper(digest_html, domain, period)
    part_html = MIMEText(html_body, "html", "utf-8")
    msg.attach(part_html)

    # --- Send ---
    _send_smtp(email_cfg, msg)

    return {
        "success": True,
        "message": f"Digest sent to {len(email_cfg.to_addrs)} recipient(s): {', '.join(email_cfg.to_addrs)}",
        "recipients": email_cfg.to_addrs,
        "domain": domain,
        "period": period,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_subject(domain: str, period: str) -> str:
    """Build a descriptive email subject line."""
    period_label = PERIOD_LABELS.get(period, period.capitalize())
    return f"[AutoInfo] {period_label} Digest — {domain}"


def _format_date() -> str:
    """Return RFC 2822 formatted date string (UTC)."""
    now = datetime.now(timezone.utc)
    return now.strftime("%a, %d %b %Y %H:%M:%S +0000")


def _md_to_html(md_text: str) -> str:
    """Convert Markdown text to HTML using the ``markdown`` library.

    Falls back to wrapping the text in ``<pre>`` tags if the library
    is not installed.
    """
    try:
        import markdown as md_lib  # noqa: PLC0415 — deferred import

        return md_lib.markdown(md_text, extensions=["fenced_code", "tables"])
    except ImportError:
        logger.warning("markdown library not available — returning plain text as HTML")
        return f"<pre>{md_text}</pre>"


def _build_html_wrapper(body_html: str, domain: str, period: str) -> str:
    """Wrap the digest HTML in a complete email document with inline styling."""
    period_label = PERIOD_LABELS.get(period, period.capitalize())
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #333; line-height: 1.6; max-width: 700px; margin: 0 auto; padding: 20px; }}
        h1 {{ color: #1a73e8; border-bottom: 2px solid #1a73e8; padding-bottom: 8px; }}
        h2 {{ color: #444; margin-top: 24px; }}
        a {{ color: #1a73e8; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        .entry {{ margin: 16px 0; padding: 12px; background: #f8f9fa; border-radius: 6px; }}
        .entry-title {{ font-size: 16px; font-weight: 600; }}
        .entry-summary {{ font-size: 14px; color: #555; margin-top: 4px; }}
        .entry-meta {{ font-size: 12px; color: #888; margin-top: 4px; }}
        .footer {{ margin-top: 32px; padding-top: 16px; border-top: 1px solid #ddd; font-size: 12px; color: #888; }}
    </style>
</head>
<body>
    <h1>{period_label} Digest — {domain}</h1>
    {body_html}
    <div class="footer">
        <p>Generated by AutoInfo — {_format_date()}</p>
    </div>
</body>
</html>"""


def _send_smtp(email_cfg: EmailConfig, msg: MIMEMultipart) -> None:
    """Connect to SMTP server and send the message.

    Uses STARTTLS for secure delivery. Logs in when credentials are
    provided. On failure, raises ``RuntimeError`` with details.
    """
    server: smtplib.SMTP | None = None
    try:
        server = smtplib.SMTP(email_cfg.smtp_host, email_cfg.smtp_port, timeout=30)
        server.ehlo()

        # Try STARTTLS
        if server.has_extn("STARTTLS"):
            server.starttls()
            server.ehlo()

        # Login if credentials are provided
        if email_cfg.smtp_user and email_cfg.smtp_pass:
            server.login(email_cfg.smtp_user, email_cfg.smtp_pass)

        # Send
        server.sendmail(
            email_cfg.from_addr,
            email_cfg.to_addrs,
            msg.as_string(),
        )

        logger.info(
            "Digest sent via %s:%d to %d recipient(s)",
            email_cfg.smtp_host,
            email_cfg.smtp_port,
            len(email_cfg.to_addrs),
        )

    except smtplib.SMTPException as exc:
        logger.error("SMTP delivery failed: %s", exc)
        raise RuntimeError(f"SMTP delivery failed: {exc}") from exc
    except Exception as exc:
        logger.error("Email delivery failed: %s", exc)
        raise RuntimeError(f"Email delivery failed: {exc}") from exc
    finally:
        if server is not None:
            try:
                server.quit()
            except Exception:
                pass
