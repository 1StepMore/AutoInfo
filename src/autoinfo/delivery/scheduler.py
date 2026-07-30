"""Delivery scheduler — periodic output generation + channel delivery via cron.

Provides :class:`DeliverySchedule` dataclass, :class:`DeliveryScheduler` for
YAML-persisted schedule CRUD, and :func:`run_due_schedules` for executing
due delivery schedules as part of the existing ``autoinfo cron run`` flow.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from autoinfo.models import Product, ProductType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEDULES_PATH = Path(".autoinfo/delivery_schedules.yaml")

VALID_OUTPUT_TYPES = {"digest", "report"}
VALID_FORMATS = {"markdown", "html", "json", "agent", "audio", "pdf"}
VALID_CHANNELS = {
    "email", "webhook", "rest", "smtp", "telegram", "discord",
    "dingtalk", "feishu", "wechat_work", "wechat_oa", "rss", "file_export",
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class DeliverySchedule:
    """A scheduled delivery of an output product via a delivery channel.

    Attributes
    ----------
    id:
        Unique schedule identifier (UUID).
    cron_expression:
        Cron expression (e.g. ``"0 8 * * 1"`` for Monday 8 AM).
    domain:
        Domain name to generate output for.  Can be ``"*"`` for all domains.
    output_type:
        Output product type: ``"digest"`` or ``"report"``.
    format:
        Output format: ``"markdown"``, ``"html"``, ``"json"``, ``"agent"``,
        ``"audio"``, ``"pdf"``.
    channel:
        Delivery channel name (e.g. ``"email"``, ``"webhook"``).
    recipients:
        List of recipient identifiers (email addresses, webhook URLs, …).
    period:
        Content period for the output: ``"daily"``, ``"weekly"``, ``"monthly"``.
    enabled:
        Whether this schedule is active.
    created_at:
        ISO-8601 creation timestamp.
    last_run:
        ISO-8601 timestamp of last successful run, or ``None``.
    last_error:
        Error message from last failed run, or ``None``.
    """

    id: str = ""
    cron_expression: str = ""
    domain: str = ""
    output_type: str = "digest"
    format: str = "markdown"
    channel: str = "email"
    recipients: list[str] = field(default_factory=list)
    period: str = "weekly"
    enabled: bool = True
    created_at: str = ""
    last_run: str | None = None
    last_error: str | None = None

    def __post_init__(self) -> None:
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = _now_iso()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _schedules_path() -> Path:
    return Path.cwd() / SCHEDULES_PATH


# ---------------------------------------------------------------------------
# DeliveryScheduler
# ---------------------------------------------------------------------------


class DeliveryScheduler:
    """CRUD and persistence for :class:`DeliverySchedule` objects.

    Schedules are persisted to ``.autoinfo/delivery_schedules.yaml``.
    """

    def __init__(self) -> None:
        self._schedules: dict[str, DeliverySchedule] = {}
        self._loaded = False

    # -- Persistence -----------------------------------------------------------

    def _load(self) -> None:
        """Load schedules from YAML file into ``self._schedules``."""
        path = _schedules_path()
        if not path.is_file():
            self._schedules = {}
            self._loaded = True
            return
        try:
            with open(path, "r", encoding="utf-8") as fh:
                raw = yaml.safe_load(fh) or {}
        except yaml.YAMLError:
            logger.warning("Failed to parse delivery schedules at %s", path)
            self._schedules = {}
            self._loaded = True
            return
        schedules_list = raw.get("schedules", [])
        self._schedules = {}
        for item in schedules_list:
            sched = DeliverySchedule(
                id=item.get("id", ""),
                cron_expression=item.get("cron_expression", ""),
                domain=item.get("domain", ""),
                output_type=item.get("output_type", "digest"),
                format=item.get("format", "markdown"),
                channel=item.get("channel", "email"),
                recipients=item.get("recipients", []),
                period=item.get("period", "weekly"),
                enabled=item.get("enabled", True),
                created_at=item.get("created_at", ""),
                last_run=item.get("last_run"),
                last_error=item.get("last_error"),
            )
            self._schedules[sched.id] = sched
        self._loaded = True

    def _save(self) -> None:
        """Persist schedules to YAML file."""
        path = _schedules_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        schedules_list: list[dict[str, Any]] = []
        for sched in self._schedules.values():
            item: dict[str, Any] = {
                "id": sched.id,
                "cron_expression": sched.cron_expression,
                "domain": sched.domain,
                "output_type": sched.output_type,
                "format": sched.format,
                "channel": sched.channel,
                "recipients": sched.recipients,
                "period": sched.period,
                "enabled": sched.enabled,
                "created_at": sched.created_at,
                "last_run": sched.last_run,
                "last_error": sched.last_error,
            }
            schedules_list.append(item)
        raw: dict[str, Any] = {"schedules": schedules_list}
        with open(path, "w", encoding="utf-8") as fh:
            yaml.dump(raw, fh, default_flow_style=False, sort_keys=False, allow_unicode=True)

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self._load()

    # -- CRUD -----------------------------------------------------------------

    def add_schedule(self, schedule: DeliverySchedule) -> DeliverySchedule:
        """Add a delivery schedule and persist.

        Parameters
        ----------
        schedule:
            The schedule to add.  Must have a non-empty *cron_expression*
            and at least one *domain*.

        Returns
        -------
        DeliverySchedule
            The added schedule (with generated ID if not provided).

        Raises
        ------
        ValueError
            If ``cron_expression`` is empty or format/channel is invalid.
        """
        self._ensure_loaded()
        if not schedule.cron_expression:
            raise ValueError("cron_expression must not be empty")
        if schedule.output_type not in VALID_OUTPUT_TYPES:
            raise ValueError(
                f"Invalid output_type '{schedule.output_type}'. "
                f"Must be one of: {', '.join(sorted(VALID_OUTPUT_TYPES))}"
            )
        if schedule.format not in VALID_FORMATS:
            raise ValueError(
                f"Invalid format '{schedule.format}'. "
                f"Must be one of: {', '.join(sorted(VALID_FORMATS))}"
            )
        if schedule.channel not in VALID_CHANNELS:
            raise ValueError(
                f"Invalid channel '{schedule.channel}'. "
                f"Must be one of: {', '.join(sorted(VALID_CHANNELS))}"
            )
        self._schedules[schedule.id] = schedule
        self._save()
        return schedule

    def list_schedules(self) -> list[DeliverySchedule]:
        """Return all schedules as a list."""
        self._ensure_loaded()
        return list(self._schedules.values())

    def get_schedule(self, schedule_id: str) -> DeliverySchedule | None:
        """Return a schedule by ID, or ``None``."""
        self._ensure_loaded()
        return self._schedules.get(schedule_id)

    def remove_schedule(self, schedule_id: str) -> bool:
        """Remove a schedule by ID.

        Returns
        -------
        bool
            ``True`` if removed, ``False`` if not found.
        """
        self._ensure_loaded()
        if schedule_id not in self._schedules:
            return False
        del self._schedules[schedule_id]
        self._save()
        return True

    def get_due_schedules(self, now: datetime | None = None) -> list[DeliverySchedule]:
        """Return schedules that are due to run.

        Parameters
        ----------
        now:
            Reference time (defaults to UTC now).

        Returns
        -------
        list[DeliverySchedule]
            Enabled schedules whose next cron occurrence after *last_run* is
            at or before *now*.  Schedules that have never run are always due.
        """
        from croniter import croniter

        if now is None:
            now = datetime.now(timezone.utc)

        self._ensure_loaded()
        due: list[DeliverySchedule] = []
        for sched in self._schedules.values():
            if not sched.enabled:
                continue
            if not sched.cron_expression:
                continue
            if sched.last_run is None:
                due.append(sched)
                continue
            try:
                last_dt = datetime.fromisoformat(sched.last_run)
                cron = croniter(sched.cron_expression, last_dt)
                next_time = cron.get_next(datetime)
                if next_time <= now:
                    due.append(sched)
            except (ValueError, KeyError):
                logger.warning(
                    "Invalid cron expression '%s' for schedule %s",
                    sched.cron_expression, sched.id,
                )
        return due

    def mark_run(self, schedule_id: str, error: str | None = None) -> None:
        """Update ``last_run`` (and optionally ``last_error``) on a schedule.

        Parameters
        ----------
        schedule_id:
            Schedule to update.
        error:
            Error message from the run, or ``None`` for success.
        """
        self._ensure_loaded()
        sched = self._schedules.get(schedule_id)
        if sched is None:
            return
        sched.last_run = _now_iso()
        sched.last_error = error
        self._save()


# ---------------------------------------------------------------------------
# Execution — run due delivery schedules
# ---------------------------------------------------------------------------


def run_delivery_schedules(
    dry_run: bool = False,
    json_output: bool = False,
) -> list[dict[str, Any]]:
    """Run all due delivery schedules, returning result dicts.

    Called from within the existing :func:`autoinfo.cli.cron.run_due_schedules`
    when ``autoinfo cron run`` is executed.

    Parameters
    ----------
    dry_run:
        If ``True``, only report which schedules *would* run.
    json_output:
        If ``True``, include full output content in result dicts.

    Returns
    -------
    list[dict]
        One dict per due schedule with keys: ``schedule_id``, ``domain``,
        ``output_type``, ``channel``, ``ran``, ``dry_run``, ``error``,
        ``output`` (only when ``json_output=True``).
    """
    scheduler = DeliveryScheduler()
    due_schedules = scheduler.get_due_schedules()
    results: list[dict[str, Any]] = []

    for sched in due_schedules:
        entry: dict[str, Any] = {
            "schedule_id": sched.id,
            "domain": sched.domain,
            "output_type": sched.output_type,
            "channel": sched.channel,
            "cron_expression": sched.cron_expression,
            "recipients": sched.recipients,
            "due": True,
        }

        if dry_run:
            entry["ran"] = False
            entry["dry_run"] = True
            results.append(entry)
            continue

        # --- Generate output -------------------------------------------------
        try:
            content = _generate_output(
                domain=sched.domain,
                output_type=sched.output_type,
                format=sched.format,
                period=sched.period,
            )
        except Exception as exc:
            logger.exception(
                "Output generation failed for schedule %s (domain=%s)",
                sched.id, sched.domain,
            )
            scheduler.mark_run(sched.id, error=str(exc))
            entry["ran"] = False
            entry["error"] = str(exc)
            results.append(entry)
            continue

        # --- Deliver via channel ---------------------------------------------
        try:
            _deliver_output(
                channel_name=sched.channel,
                domain=sched.domain,
                output_type=sched.output_type,
                content=content,
                recipients=sched.recipients,
                format=sched.format,
            )
            scheduler.mark_run(sched.id)
            entry["ran"] = True
            if json_output:
                entry["output"] = content
        except Exception as exc:
            logger.exception(
                "Delivery failed for schedule %s via %s",
                sched.id, sched.channel,
            )
            scheduler.mark_run(sched.id, error=str(exc))
            entry["ran"] = False
            entry["error"] = str(exc)

        results.append(entry)

    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _generate_output(
    domain: str,
    output_type: str,
    format: str,
    period: str,
) -> object:
    """Generate output content for the given parameters.

    Parameters
    ----------
    domain:
        Domain name or ``"*"`` (all domains).
    output_type:
        ``"digest"`` or ``"report"``.
    format:
        Output format string.
    period:
        Content period: ``"daily"``, ``"weekly"``, ``"monthly"``.

    Returns
    -------
    str or dict
        The generated output content.

    Raises
    ------
    ValueError
        If *output_type* is unknown.
    """
    import json as _json

    if output_type == "digest":
        from autoinfo.output import generate_digest

        result = generate_digest(
            domain=domain,
            period=period,
            format=format,
        )
        if format in ("json", "agent"):
            return _json.loads(result) if isinstance(result, str) else result
        return result

    if output_type == "report":
        from autoinfo.output import generate_report

        result = generate_report(
            domain=domain,
            period=period,
            format=format,
        )
        if format in ("json", "agent"):
            return _json.loads(result) if isinstance(result, str) else result
        return result

    raise ValueError(f"Unknown output_type: {output_type}")


def _deliver_output(
    channel_name: str,
    domain: str,
    output_type: str,
    content: str | dict[str, Any] | object,
    recipients: list[str],
    format: str,
) -> None:
    """Deliver generated content via the specified channel.

    Parameters
    ----------
    channel_name:
        Channel name from ``VALID_CHANNELS``.
    domain:
        Domain the content belongs to.
    output_type:
        ``"digest"`` or ``"report"``.
    content:
        The generated output (string or dict for JSON-like formats).
    recipients:
        List of recipient identifiers.
    format:
        Output format string.

    Raises
    ------
    ValueError
        If the channel is not supported.
    """
    # Email / SMTP channel
    if channel_name in ("email", "smtp"):
        _deliver_via_email(
            domain=domain,
            content=content,
            recipients=recipients,
            output_type=output_type,
            format=format,
        )
        return

    # Other channels: use the delivery channel abstraction
    from autoinfo.delivery import get_channel
    from autoinfo.delivery import deliver_with_retry as _deliver_with_retry

    product = Product(
        id=f"sched-{output_type}-{domain}",
        domain=domain,
        type=ProductType.PROCESSED,
        name=f"{output_type}-{domain}",
    )

    payload: dict[str, Any] = {
        "domain": domain,
        "output_type": output_type,
        "format": format,
        "content": content,
    }

    channel = get_channel(channel_name)
    _deliver_with_retry(
        channel=channel,
        product=product,
        payload=payload,
        recipients=recipients,
        sla_tier="standard",
    )


def _deliver_via_email(
    domain: str,
    content: object,
    recipients: list[str],
    output_type: str,
    format: str,
) -> None:
    """Deliver generated content via SMTP email."""
    if output_type == "digest":
        from autoinfo.email_sender import send_digest as _send_email_digest  # noqa: PLC0415

        _send_email_digest(domain=domain, period="daily", config=None)
        return

    # For report: render content as email body and send
    _send_email_content(
        domain=domain,
        content=content,
        recipients=recipients,
        output_type=output_type,
        format=format,
    )


def _send_email_content(
    domain: str,
    content: object,
    recipients: list[str],
    output_type: str,
    format: str,
) -> None:
    """Send arbitrary content as an email via SMTP."""
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    from autoinfo.config import get_config_path, load_config

    config_path = get_config_path()
    if config_path is None:
        raise RuntimeError("No configuration file found.")

    config = load_config(config_path)
    email_cfg = config.email

    if not email_cfg.enabled:
        raise RuntimeError("Email delivery is not enabled.")

    if not email_cfg.smtp_host or not email_cfg.from_addr:
        raise RuntimeError("SMTP not configured.")

    # Build message
    msg = MIMEMultipart("alternative")
    subject = f"[AutoInfo] {output_type.title()}: {domain}"
    msg["Subject"] = subject
    msg["From"] = email_cfg.from_addr
    msg["To"] = ", ".join(recipients)

    body_text = content if isinstance(content, str) else str(content)
    subtype = "html" if format == "html" else "plain"
    msg.attach(MIMEText(body_text, subtype, "utf-8"))

    # Send
    server: smtplib.SMTP | None = None
    try:
        server = smtplib.SMTP(email_cfg.smtp_host, email_cfg.smtp_port, timeout=30)
        server.ehlo()
        if server.has_extn("STARTTLS"):
            server.starttls()
            server.ehlo()
        if email_cfg.smtp_user and email_cfg.smtp_pass:
            server.login(email_cfg.smtp_user, email_cfg.smtp_pass)
        server.sendmail(email_cfg.from_addr, recipients, msg.as_string())
        server.quit()
        logger.info("Email delivered: %s → %s", subject, len(recipients))
    except Exception as exc:
        raise RuntimeError(f"SMTP send failed: {exc}") from exc


# ---------------------------------------------------------------------------
# CLI integration helper — to be called from cron run command
# ---------------------------------------------------------------------------


def get_delivery_schedule_summary() -> dict[str, Any]:
    """Return summary counts for all delivery schedules.

    Used by the ``autoinfo cron run`` command to report delivery results
    alongside collection results.

    Returns
    -------
    dict
        ``{"total": int, "enabled": int, "due": int, "last_error_count": int}``.
    """
    scheduler = DeliveryScheduler()
    all_scheds = scheduler.list_schedules()
    due = scheduler.get_due_schedules()
    return {
        "total": len(all_scheds),
        "enabled": sum(1 for s in all_scheds if s.enabled),
        "due": len(due),
        "last_error_count": sum(1 for s in all_scheds if s.last_error),
    }
