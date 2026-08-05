"""Alert stream configuration module — threshold-based notifications.

Alert rules are persisted in ``.autoinfo/alerts.yaml`` using the same YAML
pattern as ``cron.py`` schedules.  After each collection run,
:func:`check_alerts` is called to match new items against configured rules
and push notifications via the configured channel (email or webhook).
"""

from __future__ import annotations

import logging
import os
import re
import smtplib
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Literal

import yaml

from autoinfo.config import SourceConfig, get_config_path, load_config
from autoinfo.delivery import get_channel
from autoinfo.models import AlertRule, Item, Product, ProductType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALERTS_DIRNAME = ".autoinfo"
ALERTS_FILENAME = "alerts.yaml"

# Alert rule kinds. "content" is the legacy item-matching rule;
# "source_credential_missing" fires when a configured source requires an
# API key/credential that is absent from the operator environment
# (B3 escalation: only the B3 human can supply the key).
SOURCE_ALERT_KINDS = ("source_credential_missing",)

# Source type -> environment variable NAME that supplies its credential.
# Derived from the collectors (required-api-keys.md catalog). Only types
# that genuinely refuse to fetch without the credential are listed. The
# values are env var names; raw key values never appear in alerts or
# callback payloads.
_SOURCE_KEY_ENV: dict[str, str] = {
    "ap_api": "AUTOINFO_AP_API_KEY",
    "nyt": "AUTOINFO_NYT_API_KEY",
    "quandl": "AUTOINFO_QUANDL_API_KEY",
    "reuters_mcp": "AUTOINFO_REUTERS_API_KEY",
    "youtube": "AUTOINFO_YOUTUBE_API_KEY",
    "spotify": "AUTOINFO_SPOTIFY_CLIENT_ID",
    "core": "AUTOINFO_CORE_API_KEY",
    "kaggle": "KAGGLE_KEY",
    "email": "AUTOINFO_EMAIL_PASSWORD",
    "email_imap": "AUTOINFO_EMAIL_PASSWORD",
}

_ENV_REF_PATTERN = re.compile(r"\$\{([^}]+)\}")


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
    kind: str = "content",
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
    kind : str
        Rule kind: ``"content"`` (default, item matching) or
        ``"source_credential_missing"`` (fires when a configured source
        requires a credential that is absent from the operator
        environment).

    Returns
    -------
    AlertRule
        The newly created rule.

    Raises
    ------
    ValueError
        If *kind* is not a registered alert rule kind.
    """
    if kind not in ("content", *SOURCE_ALERT_KINDS):
        raise ValueError(
            f"Invalid alert rule kind {kind!r}. Valid kinds: "
            f"{sorted(('content', *SOURCE_ALERT_KINDS))}"
        )
    alert_id = f"alert-{uuid.uuid4().hex[:8]}"
    rule = AlertRule(
        id=alert_id,
        domain=domain,
        topic_keywords=topic_keywords or [],
        relevance_threshold=relevance_threshold,
        channel=channel,
        enabled=enabled,
        kind=kind,
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
# Budget alert evaluation  (F45: spend threshold monitoring)
# ---------------------------------------------------------------------------


def evaluate_budget_alerts() -> list:
    """Evaluate spend against configured budget thresholds.

    Queries the :class:`CostMeter` for total spend and compares it against
    percentage thresholds from the project configuration (``cost_alerts.budget_thresholds``).
    Returns a list of alert dicts when thresholds are breached.

    Returns
    -------
    list[dict]
        One dict per breached threshold with keys ``type``, ``threshold``,
        ``current_spend``, and ``severity``.  Returns an empty list when
        cost tracking is not configured or no thresholds are breached.
    """
    try:
        from autoinfo.cost import CostMeter

        # Load thresholds from config, falling back to defaults
        thresholds: list[float] = [50.0, 75.0, 90.0, 100.0]
        try:
            config_path = get_config_path()
            if config_path:
                config = load_config(config_path)
                thresholds = config.cost_alerts.budget_thresholds
        except Exception:
            logger.debug("Could not load budget thresholds from config — using defaults")

        meter = CostMeter()
        report = meter.get_report()
        current_spend = report["total_cost"]

        alerts: list[dict[str, object]] = []
        for threshold in thresholds:
            if current_spend >= threshold:
                alerts.append({
                    "type": "budget_threshold",
                    "threshold": threshold,
                    "current_spend": current_spend,
                    "severity": "warning" if threshold < 100 else "critical",
                })

        return alerts
    except Exception:
        logger.warning("Budget alert evaluation failed", exc_info=True)
        return []


def execute_auto_remediation(alert: dict) -> dict:
    """Execute auto-remediation actions for critical alerts.

    For critical-severity budget alerts this logs a warning and records
    a ``notified`` action.  The remediation is intentionally conservative
    (log + notify only) to avoid disrupting the pipeline.

    Parameters
    ----------
    alert : dict
        An alert dict as returned by :func:`evaluate_budget_alerts`.

    Returns
    -------
    dict
        Keys: ``status`` (``"executed"``) and ``actions`` (list of action
        descriptions).
    """
    actions: list[str] = []

    if alert.get("severity") == "critical":
        actions.append("notified: budget threshold exceeded")
        logger.warning(
            "Budget alert: %s - current $%.2f / threshold $%.2f",
            alert.get("severity"),
            alert.get("current_spend", 0),
            alert.get("threshold", 0),
        )

    return {"status": "executed", "actions": actions}


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
# Source credential alerts  (B3 escalation: missing keys reach the operator)
# ---------------------------------------------------------------------------


def check_source_credentials(domain: str) -> list[dict[str, str]]:
    """Return configured sources in *domain* that lack their required credential.

    Detection is deterministic and never touches key values: a source is
    reported missing when its raw (unresolved) ``settings`` carry an
    ``${ENV_VAR}`` reference whose variable is unset/empty, or when its
    source type is a known key-requiring type (see ``_SOURCE_KEY_ENV``)
    whose variable is unset/empty and no literal credential is configured
    in settings.

    Returns
    -------
    list[dict[str, str]]
        One dict per missing credential with keys ``source`` (source name),
        ``source_type``, and ``key_ref`` (the environment variable NAME that
        must be set — never the key value).
    """
    try:
        config_path = get_config_path()
        if not config_path:
            return []
        config = load_config(config_path)
    except Exception:
        logger.exception("Failed to load config for source credential check")
        return []

    domain_config = next((d for d in config.domains if d.name == domain), None)
    if domain_config is None:
        return []

    # Raw (unresolved) settings per source name: load_config resolves
    # ${ENV_VAR} references, so the ref must be read from the source YAML.
    raw_settings = _load_raw_source_settings(config_path, domain)

    missing: list[dict[str, str]] = []
    for source in domain_config.sources:
        cred = _missing_credential_for(source, raw_settings.get(source.name, {}))
        if cred is not None:
            missing.append(cred)
    return missing


def _load_raw_source_settings(
    config_path: str | Path, domain: str
) -> dict[str, dict[str, Any]]:
    """Return ``{source_name: settings}`` from the raw YAML (env refs unresolved)."""
    try:
        with open(config_path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
    except (yaml.YAMLError, OSError):
        return {}

    result: dict[str, dict[str, Any]] = {}
    for domain_raw in raw.get("domains", []) or []:
        if not isinstance(domain_raw, dict) or domain_raw.get("name") != domain:
            continue
        for source_raw in domain_raw.get("sources", []) or []:
            if isinstance(source_raw, dict) and source_raw.get("name"):
                settings = source_raw.get("settings")
                result[str(source_raw["name"])] = (
                    settings if isinstance(settings, dict) else {}
                )
    return result


def check_source_alerts(
    domain: str,
    missing: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Check *domain* sources against enabled credential alert rules.

    For each missing credential (from :func:`check_source_credentials`,
    or the precomputed *missing* list) and each enabled rule of kind
    ``"source_credential_missing"`` for *domain*, one notification is
    dispatched via the rule's configured channel (email/webhook).  Mirror
    of :func:`check_alerts` for the non-item rule kinds.

    Parameters
    ----------
    domain : str
        Domain to check.
    missing : list[dict[str, str]] | None
        Precomputed missing-credential list (avoids re-loading config).

    Returns
    -------
    list[dict[str, Any]]
        One dict per dispatched notification with keys ``status``,
        ``channel``, ``rule_id``, and optionally ``error``/``reason``.
    """
    results: list[dict[str, Any]] = []
    if missing is None:
        missing = check_source_credentials(domain)
    if not missing:
        return results

    for rule in load_alerts().values():
        if not rule.enabled:
            continue
        if rule.domain != domain:
            continue
        if rule.kind not in SOURCE_ALERT_KINDS:
            continue

        for cred in missing:
            logger.info(
                "Alert rule '%s' matched missing credential for source '%s' "
                "(key_ref=%s, channel=%s)",
                rule.id,
                cred["source"],
                cred["key_ref"],
                rule.channel,
            )
            results.append(_dispatch_source_notification(rule, cred, domain))

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
# Internal helpers — source credential detection
# ---------------------------------------------------------------------------


def _extract_key_ref(value: str) -> str | None:
    """Return the env var name from a ``${ENV_VAR}`` reference, else ``None``."""
    match = _ENV_REF_PATTERN.fullmatch(value.strip())
    return match.group(1) if match else None


def _missing_credential_for(
    source: SourceConfig, raw_settings: dict[str, Any] | None = None
) -> dict[str, str] | None:
    """Return ``{source, source_type, key_ref}`` when *source* lacks a credential.

    Detection order:
    1. An ``${ENV_VAR}`` reference in a raw credential setting (``api_key``,
       ``password``, ``client_id``, ``token``) whose variable is
       unset/empty. The raw settings are required because ``load_config``
       resolves references to empty strings when the variable is unset.
    2. A literal credential in the resolved settings.
    3. A known key-requiring source type (``_SOURCE_KEY_ENV``) whose
       variable is unset/empty.

    ``key_ref`` is always the environment variable NAME; key values are
    never read into or returned from this function.
    """
    raw = raw_settings or {}
    for setting_key in ("api_key", "password", "client_id", "token"):
        raw_value = raw.get(setting_key)
        if isinstance(raw_value, str):
            ref = _extract_key_ref(raw_value)
            if ref is not None:
                if not os.environ.get(ref, "").strip():
                    return {
                        "source": source.name,
                        "source_type": source.type,
                        "key_ref": ref,
                    }
                return None  # env var set, credential configured

    settings = source.settings or {}
    for setting_key in ("api_key", "password", "client_id", "token"):
        value = settings.get(setting_key)
        if isinstance(value, str) and value.strip():
            return None  # a literal credential is configured

    env_name = _SOURCE_KEY_ENV.get(source.type)
    if env_name is not None and not os.environ.get(env_name, "").strip():
        return {
            "source": source.name,
            "source_type": source.type,
            "key_ref": env_name,
        }
    return None


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


def _dispatch_source_notification(
    rule: AlertRule, cred: dict[str, str], domain: str
) -> dict[str, Any]:
    """Dispatch a source-credential notification for a matched alert rule.

    Routes to the same channel implementations as content alerts
    (``_notify_webhook`` / ``_notify_email`` family), mirroring the
    existing pattern.
    """
    if rule.channel == "webhook":
        return _notify_source_webhook(rule, cred, domain)
    return _notify_source_email(rule, cred, domain)


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


def _load_webhook_urls(domain: str) -> list[str]:
    """Return the configured webhook URLs for *domain* (empty on failure)."""
    try:
        config_path = get_config_path()
        if config_path:
            config = load_config(config_path)
            domain_cfg = next((d for d in config.domains if d.name == domain), None)
            return list(domain_cfg.webhook_urls) if domain_cfg else []
    except Exception:
        logger.exception("Failed to load config for webhook alert")
    return []


def _notify_webhook(
    rule: AlertRule, item: Item, domain: str
) -> dict[str, Any]:
    """Send an alert via webhook POST to the domain's configured URLs."""
    # Load domain webhook URLs from config
    urls = _load_webhook_urls(domain)

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


def _build_source_alert_payload(
    rule: AlertRule, cred: dict[str, str], domain: str
) -> dict[str, Any]:
    """Build a JSON-serialisable payload for a source-credential alert.

    ``key_ref`` is the environment variable NAME that must be set; the
    key value is never included.
    """
    return {
        "alert_id": rule.id,
        "kind": rule.kind,
        "domain": domain,
        "source": cred["source"],
        "source_type": cred["source_type"],
        "key_ref": cred["key_ref"],
        "severity": "critical",
        "triggered_at": datetime.now(timezone.utc).isoformat(),
    }


def _notify_source_webhook(
    rule: AlertRule, cred: dict[str, str], domain: str
) -> dict[str, Any]:
    """Send a source-credential alert via webhook POST (mirror of _notify_webhook)."""
    urls = _load_webhook_urls(domain)

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

    product = Product(
        id=f"alert-{rule.id}",
        domain=domain,
        type=ProductType.PROCESSED,
        name=f"Alert: {rule.id}",
    )
    payload = _build_source_alert_payload(rule, cred, domain)
    channel = get_channel("webhook")
    delivery_result = channel.send(product, payload, recipients=urls)

    logger.info(
        "Webhook source-credential alert '%s' delivered to %d URL(s): %s",
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


def _notify_source_email(
    rule: AlertRule, cred: dict[str, str], domain: str
) -> dict[str, Any]:
    """Send a source-credential alert via SMTP email (mirror of _notify_email)."""
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

    subject = f"[AutoInfo Alert] Missing credential: {cred['source']} ({domain})"
    body = _build_source_alert_email_body(rule, cred, domain)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = email_cfg.from_addr
    msg["To"] = ", ".join(email_cfg.to_addrs)
    msg["Date"] = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        _send_smtp(email_cfg, msg)
        logger.info(
            "Email source-credential alert '%s' sent to %d recipient(s)",
            rule.id,
            len(email_cfg.to_addrs),
        )
        return {
            "status": "success",
            "channel": "email",
            "rule_id": rule.id,
            "recipient_count": len(email_cfg.to_addrs),
        }
    except RuntimeError as exc:
        logger.error("Email source-credential alert '%s' delivery failed: %s", rule.id, exc)
        return {
            "status": "failed",
            "channel": "email",
            "rule_id": rule.id,
            "error": str(exc),
        }


def _build_source_alert_email_body(
    rule: AlertRule, cred: dict[str, str], domain: str
) -> str:
    """Build a plain-text notification email body for a missing credential."""
    lines = [
        f"AutoInfo Alert - Missing Source Credential ({domain})",
        "",
        f"  Rule ID:      {rule.id}",
        f"  Channel:      {rule.channel}",
        f"  Domain:       {domain}",
        f"  Source:       {cred['source']} ({cred['source_type']})",
        f"  Key ref:      {cred['key_ref']}",
        "  Severity:     critical",
        "",
        (
            "A configured source requires an API key that is not present "
            "in the operator environment. Collection for this source "
            "cannot proceed until the key is supplied."
        ),
        (
            f"Set the {cred['key_ref']} environment variable (the key value "
            "itself is never transmitted by AutoInfo)."
        ),
        "",
        "---",
        f"Triggered at: {datetime.now(timezone.utc).isoformat()}",
        "AutoInfo Alert Stream",
    ]
    return "\n".join(lines)


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
