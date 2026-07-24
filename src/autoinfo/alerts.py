"""Alert stream configuration module — threshold-based notifications.

Alert rules are persisted in ``.autoinfo/alerts.yaml`` using the same YAML
pattern as ``cron.py`` schedules.  After each collection run,
:func:`check_alerts` is called to match new items against configured rules
and push notifications via the configured channel (email or webhook).
"""

from __future__ import annotations

import logging
import smtplib
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Literal

import yaml

from autoinfo.config import get_config_path, load_config
from autoinfo.delivery import get_channel
from autoinfo.models import AlertRule, Item, Product, ProductType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALERTS_DIRNAME = ".autoinfo"
ALERTS_FILENAME = "alerts.yaml"


# ---------------------------------------------------------------------------
# Storage helpers  (same pattern as cron.py Schedule persistence)
# ---------------------------------------------------------------------------


def _alerts_path() -> Path:
    """Return the absolute path to ``.autoinfo/alerts.yaml``."""
    return Path.cwd() / ALERTS_DIRNAME / ALERTS_FILENAME


def _load_alerts_raw() -> dict[str, Any]:
    """Load the alerts YAML file, returning a dict with an ``alerts`` key."""
    path = _alerts_path()
    if not path.is_file():
        return {"alerts": {}}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        return data if isinstance(data, dict) else {"alerts": {}}
    except yaml.YAMLError:
        logger.warning("Failed to parse alerts file at %s", path)
        return {"alerts": {}}


def _dump_alerts_raw(data: dict[str, Any]) -> None:
    """Write the alerts YAML file."""
    path = _alerts_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        yaml.dump(data, fh, default_flow_style=False, sort_keys=False, allow_unicode=True)


# ---------------------------------------------------------------------------
# Public API — CRUD
# ---------------------------------------------------------------------------


def load_alerts() -> dict[str, AlertRule]:
    """Load all alert rules from disk.

    Returns
    -------
    dict[str, AlertRule]
        Mapping of alert rule ID → :class:`AlertRule`.
    """
    raw = _load_alerts_raw()
    alerts: dict[str, AlertRule] = {}
    for alert_id, s in raw.get("alerts", {}).items():
        try:
            alerts[alert_id] = AlertRule.from_dict({"id": alert_id, **s})
        except Exception:
            logger.exception("Failed to load alert rule '%s' — skipping", alert_id)
    return alerts


def save_alerts(alerts: dict[str, AlertRule]) -> None:
    """Persist alert rules to disk.

    Parameters
    ----------
    alerts : dict[str, AlertRule]
        Mapping of alert rule ID → :class:`AlertRule`.
    """
    raw: dict[str, Any] = {"alerts": {}}
    for alert_id, rule in alerts.items():
        # Serialize rule, omitting the ``id`` field (it's the dict key)
        rule_dict = {k: v for k, v in asdict(rule).items() if k != "id"}
        raw["alerts"][alert_id] = rule_dict
    _dump_alerts_raw(raw)


def add_alert_rule(
    domain: str,
    topic_keywords: list[str] | None = None,
    relevance_threshold: float = 0.0,
    channel: Literal["email", "webhook"] = "email",
    enabled: bool = True,
) -> AlertRule:
    """Create a new alert rule and persist it.

    Parameters
    ----------
    domain : str
        Domain name this rule applies to.
    topic_keywords : list[str] | None
        Keywords to match against item title, content, and topic tags.
        An empty list matches all items.
    relevance_threshold : float
        Minimum relevance score (0-100) required to trigger.  Default 0.0.
    channel : str
        Delivery channel — ``"email"`` or ``"webhook"``.
    enabled : bool
        Whether the rule is active.

    Returns
    -------
    AlertRule
        The newly created rule.
    """
    alert_id = f"alert-{uuid.uuid4().hex[:8]}"
    rule = AlertRule(
        id=alert_id,
        domain=domain,
        topic_keywords=topic_keywords or [],
        relevance_threshold=relevance_threshold,
        channel=channel,
        enabled=enabled,
    )
    alerts = load_alerts()
    alerts[alert_id] = rule
    save_alerts(alerts)
    logger.info("Alert rule '%s' added for domain '%s'", alert_id, domain)
    return rule


def remove_alert_rule(alert_id: str) -> bool:
    """Remove an alert rule by ID.

    Parameters
    ----------
    alert_id : str
        The rule identifier.

    Returns
    -------
    bool
        ``True`` if the rule existed and was removed, ``False`` otherwise.
    """
    alerts = load_alerts()
    if alert_id not in alerts:
        return False
    del alerts[alert_id]
    save_alerts(alerts)
    logger.info("Alert rule '%s' removed", alert_id)
    return True


def list_alert_rules(domain: str | None = None) -> list[AlertRule]:
    """Return all alert rules, optionally filtered by domain.

    Parameters
    ----------
    domain : str | None
        If provided, only rules for this domain are returned.

    Returns
    -------
    list[AlertRule]
        Sorted list of alert rules.
    """
    rules = list(load_alerts().values())
    if domain:
        rules = [r for r in rules if r.domain == domain]
    return sorted(rules, key=lambda r: r.id)


# ---------------------------------------------------------------------------
# Alert checking  (called post-collection)
# ---------------------------------------------------------------------------


def check_alerts(item: Item, domain: str) -> list[dict[str, Any]]:
    """Check *item* against all enabled alert rules for *domain*.

    For each matching rule a notification is sent via the rule's configured
    channel.  Results are returned as a list of delivery result dicts.

    Parameters
    ----------
    item : Item
        The newly collected item to check.
    domain : str
        Domain the item belongs to.

    Returns
    -------
    list[dict[str, Any]]
        One dict per triggered rule with keys ``status``, ``channel``,
        ``rule_id``, and optionally ``error``.
    """
    results: list[dict[str, Any]] = []

    for rule in load_alerts().values():
        # --- Skip non-matching rules ------------------------------------------
        if not rule.enabled:
            continue
        if rule.domain != domain:
            continue

        # Relevance threshold check
        relevance_score = _get_relevance_score(item)
        if relevance_score < rule.relevance_threshold:
            continue

        # Keyword matching (empty keyword list = match all)
        if not _matches_keywords(item, rule.topic_keywords):
            continue

        # --- Match!  Send notification ---------------------------------------
        logger.info(
            "Alert rule '%s' matched item '%s' "
            "(relevance=%.1f, threshold=%.1f, channel=%s)",
            rule.id,
            item.id,
            relevance_score,
            rule.relevance_threshold,
            rule.channel,
        )
        result = _dispatch_notification(rule, item, domain)
        results.append(result)

    return results


# ---------------------------------------------------------------------------
# Internal helpers — matching
# ---------------------------------------------------------------------------


def _get_relevance_score(item: Item) -> float:
    """Extract the relevance score from an item.

    For processed items the score lives in ``raw_data``.  Unprocessed items
    default to 1.0 so they aren't silently filtered out.
    """
    if not isinstance(item.raw_data, dict):
        return 1.0
    score = item.raw_data.get("relevance_score", None)
    if score is None:
        return 1.0
    try:
        return float(score)
    except (TypeError, ValueError):
        return 1.0


def _matches_keywords(item: Item, keywords: list[str]) -> bool:
    """Return ``True`` when *item* matches at least one keyword.

    Matching is case-insensitive and searches across title, content, and
    topic tags.  An empty keyword list matches everything.
    """
    if not keywords:
        return True

    haystack = " ".join(
        [
            item.title or "",
            item.content or "",
            " ".join(item.topic_tags or []),
        ]
    ).lower()

    for kw in keywords:
        if kw.lower() in haystack:
            return True
    return False


# ---------------------------------------------------------------------------
# Internal helpers — notification dispatch
# ---------------------------------------------------------------------------


def _dispatch_notification(
    rule: AlertRule, item: Item, domain: str
) -> dict[str, Any]:
    """Dispatch a notification for a matched alert rule.

    Routes to the appropriate channel implementation.
    """
    if rule.channel == "webhook":
        return _notify_webhook(rule, item, domain)
    return _notify_email(rule, item, domain)


def _build_alert_payload(rule: AlertRule, item: Item, domain: str) -> dict[str, Any]:
    """Build a JSON-serialisable payload for alert notifications."""
    return {
        "alert_id": rule.id,
        "domain": domain,
        "item_id": item.id,
        "title": item.title,
        "url": item.source_url,
        "source": item.source_name,
        "source_type": item.source_type,
        "topic_tags": item.topic_tags,
        "content_preview": (item.content or "")[:500],
        "triggered_at": datetime.now(timezone.utc).isoformat(),
    }


def _notify_webhook(
    rule: AlertRule, item: Item, domain: str
) -> dict[str, Any]:
    """Send an alert via webhook POST to the domain's configured URLs."""
    # Load domain webhook URLs from config
    urls: list[str] = []
    try:
        config_path = get_config_path()
        if config_path:
            config = load_config(config_path)
            domain_cfg = next((d for d in config.domains if d.name == domain), None)
            urls = list(domain_cfg.webhook_urls) if domain_cfg else []
    except Exception:
        logger.exception("Failed to load config for webhook alert")
        return {
            "status": "failed",
            "channel": "webhook",
            "rule_id": rule.id,
            "error": "config_load_failed",
        }

    if not urls:
        logger.warning(
            "Alert rule '%s' uses webhook channel but no webhook URLs "
            "configured for domain '%s'",
            rule.id,
            domain,
        )
        return {
            "status": "skipped",
            "channel": "webhook",
            "rule_id": rule.id,
            "reason": "no_webhook_urls",
        }

    # Build a minimal Product for delivery channel compatibility
    product = Product(
        id=f"alert-{rule.id}",
        domain=domain,
        type=ProductType.PROCESSED,
        name=f"Alert: {rule.id}",
    )
    payload = _build_alert_payload(rule, item, domain)
    channel = get_channel("webhook")
    delivery_result = channel.send(product, payload, recipients=urls)

    logger.info(
        "Webhook alert '%s' delivered to %d URL(s): %s",
        rule.id,
        len(urls),
        delivery_result.status,
    )
    return {
        "status": delivery_result.status,
        "channel": "webhook",
        "rule_id": rule.id,
        "url_count": len(urls),
    }


def _notify_email(rule: AlertRule, item: Item, domain: str) -> dict[str, Any]:
    """Send an alert via SMTP email using the project's email config."""
    # Load email config
    try:
        config_path = get_config_path()
        if not config_path:
            return {
                "status": "skipped",
                "channel": "email",
                "rule_id": rule.id,
                "reason": "no_config",
            }
        config = load_config(config_path)
    except Exception:
        logger.exception("Failed to load config for email alert")
        return {
            "status": "failed",
            "channel": "email",
            "rule_id": rule.id,
            "error": "config_load_failed",
        }

    email_cfg = config.email
    if not email_cfg.enabled:
        logger.warning(
            "Alert rule '%s' uses email channel but email is not enabled in config",
            rule.id,
        )
        return {
            "status": "skipped",
            "channel": "email",
            "rule_id": rule.id,
            "reason": "email_not_enabled",
        }
    if not email_cfg.smtp_host or not email_cfg.from_addr or not email_cfg.to_addrs:
        logger.warning(
            "Alert rule '%s' uses email channel but SMTP is not fully configured",
            rule.id,
        )
        return {
            "status": "skipped",
            "channel": "email",
            "rule_id": rule.id,
            "reason": "smtp_not_configured",
        }

    # Build email
    subject = f"[AutoInfo Alert] {domain}: {item.title[:80]}"
    body = _build_alert_email_body(rule, item, domain)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = email_cfg.from_addr
    msg["To"] = ", ".join(email_cfg.to_addrs)
    msg["Date"] = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    msg.attach(MIMEText(body, "plain", "utf-8"))

    # Send
    try:
        _send_smtp(email_cfg, msg)
        logger.info("Email alert '%s' sent to %d recipient(s)", rule.id, len(email_cfg.to_addrs))
        return {
            "status": "success",
            "channel": "email",
            "rule_id": rule.id,
            "recipient_count": len(email_cfg.to_addrs),
        }
    except RuntimeError as exc:
        logger.error("Email alert '%s' delivery failed: %s", rule.id, exc)
        return {
            "status": "failed",
            "channel": "email",
            "rule_id": rule.id,
            "error": str(exc),
        }


def _build_alert_email_body(rule: AlertRule, item: Item, domain: str) -> str:
    """Build a plain-text notification email body."""
    lines = [
        f"Alert Triggered — {domain}",
        "",
        f"  Rule ID:      {rule.id}",
        f"  Channel:      {rule.channel}",
        f"  Keywords:     {', '.join(rule.topic_keywords) if rule.topic_keywords else '(any)'}",
        f"  Threshold:    {rule.relevance_threshold}",
        "",
        f"  Item:         {item.title}",
        f"  URL:          {item.source_url}",
        f"  Source:       {item.source_name} ({item.source_type})",
        f"  Topic tags:   {', '.join(item.topic_tags) if item.topic_tags else '(none)'}",
        "",
        "--- Content Preview ---",
        (item.content or "")[:1000],
        "",
        "---",
        f"Triggered at: {datetime.now(timezone.utc).isoformat()}",
        "AutoInfo Alert Stream",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal helpers — SMTP transport  (mirrors email_sender._send_smtp)
# ---------------------------------------------------------------------------


def _send_smtp(email_cfg: Any, msg: MIMEMultipart) -> None:
    """Connect to SMTP server and send the message.

    Uses STARTTLS for secure delivery.  Logs in when credentials are
    provided.  Raises ``RuntimeError`` on failure.
    """
    server: smtplib.SMTP | None = None
    try:
        server = smtplib.SMTP(email_cfg.smtp_host, email_cfg.smtp_port, timeout=30)
        server.ehlo()

        if server.has_extn("STARTTLS"):
            server.starttls()
            server.ehlo()

        if email_cfg.smtp_user and email_cfg.smtp_pass:
            server.login(email_cfg.smtp_user, email_cfg.smtp_pass)

        server.sendmail(
            email_cfg.from_addr,
            email_cfg.to_addrs,
            msg.as_string(),
        )
    except smtplib.SMTPException as exc:
        raise RuntimeError(f"SMTP delivery failed: {exc}") from exc
    except Exception as exc:
        raise RuntimeError(f"Email delivery failed: {exc}") from exc
    finally:
        if server is not None:
            try:
                server.quit()
            except Exception:
                pass
