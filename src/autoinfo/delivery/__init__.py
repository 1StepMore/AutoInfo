"""Delivery channel abstraction for AutoInfo.

Provides a pluggable :class:`DeliveryChannel` ABC with concrete
:class:`SMTPDeliveryChannel` and :class:`WebhookDeliveryChannel`
implementations, plus a :func:`get_channel` factory.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

import httpx

from autoinfo.delivery_log import append_delivery_log
from autoinfo.email_sender import send_digest
from autoinfo.models import DeliveryResult, Product

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SLA / retry constants
# ---------------------------------------------------------------------------

# Max retries per SLA tier (does not include the initial attempt)
_SLA_RETRIES: dict[str, int] = {
    "critical": 5,
    "standard": 3,
    "bulk": 1,
}

# Exponential backoff in seconds between retries (indexed by attempt-1)
_RETRY_BACKOFF: list[float] = [1.0, 5.0, 30.0]


def _max_retries(sla_tier: str) -> int:
    """Return the maximum number of retries for *sla_tier*.

    Falls back to ``standard`` (3) for unknown tiers.
    """
    return _SLA_RETRIES.get(sla_tier, _SLA_RETRIES["standard"])


def _backoff_for_attempt(attempt: int) -> float:
    """Return the backoff in seconds before the *attempt*-th retry.

    Attempt numbering is 1-based.  The last entry in
    :data:`_RETRY_BACKOFF` is repeated for attempts beyond the list.
    """
    if attempt <= 0:
        return 0.0
    idx = min(attempt - 1, len(_RETRY_BACKOFF) - 1)
    return _RETRY_BACKOFF[idx]


def deliver_with_retry(
    channel: DeliveryChannel,
    product: Product,
    payload: dict[str, Any],
    recipients: list[str],
    subscription_id: str = "",
    sla_tier: str = "standard",
) -> DeliveryResult:
    """Deliver *payload* to *recipients* via *channel* with retry and logging.

    Wraps :meth:`DeliveryChannel.send` with:

    * SLA-tier-dependent retry count (critical=5, standard=3, bulk=1)
    * Exponential backoff (1 s, 5 s, 30 s — last value repeats)
    * Full :class:`DeliveryLog` persistence per attempt
    * Per-attempt error capture

    Parameters
    ----------
    channel:
        The delivery channel to use.
    product:
        Product being delivered.
    payload:
        Content dict to deliver.
    recipients:
        Destination identifiers (email addresses, URLs, …).
    subscription_id:
        Optional subscription ID for log correlation.
    sla_tier:
        SLA classification — ``"critical"``, ``"standard"``, or ``"bulk"``.
        Defaults to ``"standard"``.

    Returns
    -------
    DeliveryResult
        Outcome of the final delivery attempt.
    """
    import time as _time

    sla_tier = sla_tier or "standard"
    max_retries = _max_retries(sla_tier)
    message_type = product.type.value if product.type else "unknown"
    attempt = 1

    while True:
        try:
            result = channel.send(product, payload, recipients)

            # Log the attempt
            append_delivery_log(
                subscription_id=subscription_id,
                channel=channel.name,
                message_type=message_type,
                status=result.status,
                attempt_count=attempt,
                error_message=result.error or "",
                sla_tier=sla_tier,
            )

            # Success or partial — return immediately
            if result.status != "failed":
                return result

            # Failed — check if we should retry
            if attempt > max_retries:
                return result

            error_msg = result.error or "unknown error"

        except Exception as exc:
            error_msg = str(exc)

            # Log the failed attempt
            append_delivery_log(
                subscription_id=subscription_id,
                channel=channel.name,
                message_type=message_type,
                status="failed",
                attempt_count=attempt,
                error_message=error_msg,
                sla_tier=sla_tier,
            )

            if attempt > max_retries:
                # Exhausted — fabricate a failed DeliveryResult
                return DeliveryResult(
                    product_id=product.id,
                    channel=channel.name,
                    status="failed",
                    timestamp=_now_utc(),
                    recipient_count=0,
                    error=error_msg,
                )

        # Log retry status
        append_delivery_log(
            subscription_id=subscription_id,
            channel=channel.name,
            message_type=message_type,
            status="retrying",
            attempt_count=attempt,
            error_message=f"Attempt {attempt}/{max_retries + 1} failed: {error_msg}",
            sla_tier=sla_tier,
        )

        # Exponential backoff before next attempt
        _time.sleep(_backoff_for_attempt(attempt))
        attempt += 1


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class DeliveryChannel(ABC):
    """Abstract delivery channel.

    Subclasses must implement :meth:`send`, :meth:`validate_config`,
    and the :attr:`name` property.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable channel name (e.g. ``"smtp"``, ``"webhook"``)."""

    @abstractmethod
    def send(
        self,
        product: Product,
        payload: dict[str, Any],
        recipients: list[str],
    ) -> DeliveryResult:
        """Deliver *payload* to *recipients*.

        Parameters
        ----------
        product:
            The product being delivered (carries type, format, config).
        payload:
            The content to deliver (domain-specific dict).
        recipients:
            List of destination identifiers (email addresses, URLs, …).

        Returns
        -------
        DeliveryResult
            Outcome of the delivery attempt.
        """

    @abstractmethod
    def validate_config(self, config: dict[str, Any]) -> bool:
        """Return ``True`` when *config* contains valid settings for this channel.

        Implementations should check required keys, formats, and
        (optionally) connectivity — but must **never** raise.
        """


def _now_utc() -> str:
    """Return ISO-8601 UTC timestamp string."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# SMTP
# ---------------------------------------------------------------------------


class SMTPDeliveryChannel(DeliveryChannel):
    """Deliver via SMTP email, wrapping :func:`email_sender.send_digest`."""

    @property
    def name(self) -> str:
        return "smtp"

    def send(
        self,
        product: Product,
        payload: dict[str, Any],
        recipients: list[str],
    ) -> DeliveryResult:
        domain = payload.get("domain", product.domain)
        period = payload.get("period", "weekly")
        config = payload.get("config", None)

        try:
            result = send_digest(domain=domain, period=period, config=config)
            return DeliveryResult(
                product_id=product.id,
                channel=self.name,
                status="success",
                timestamp=_now_utc(),
                recipient_count=len(result.get("recipients", recipients)),
                error=None,
            )
        except RuntimeError as exc:
            logger.error("SMTP delivery failed: %s", exc)
            return DeliveryResult(
                product_id=product.id,
                channel=self.name,
                status="failed",
                timestamp=_now_utc(),
                recipient_count=0,
                error=str(exc),
            )

    def validate_config(self, config: dict[str, Any]) -> bool:
        host = config.get("smtp_host", "")
        port = config.get("smtp_port", 0)
        from_addr = config.get("from_addr", "")
        return bool(host and port and from_addr)


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------


class WebhookDeliveryChannel(DeliveryChannel):
    """Deliver via HTTP POST (webhook) with retry logic.

    Wraps the same pattern used by ``collect.py`` — POSTs JSON to each
    recipient URL with up to 3 retries and exponential backoff.
    """

    @property
    def name(self) -> str:
        return "webhook"

    def send(
        self,
        product: Product,
        payload: dict[str, Any],
        recipients: list[str],
    ) -> DeliveryResult:
        failed_urls: list[str] = []
        success_count = 0

        for url in recipients:
            try:
                self._post_webhook(url, payload)
                success_count += 1
            except Exception as exc:
                logger.warning("Webhook to %s failed: %s", url, exc)
                failed_urls.append(url)

        all_succeeded = len(failed_urls) == 0
        return DeliveryResult(
            product_id=product.id,
            channel=self.name,
            status="success" if all_succeeded else "partial",
            timestamp=_now_utc(),
            recipient_count=success_count,
            error=None if all_succeeded else f"{len(failed_urls)} webhook(s) failed",
        )

    def validate_config(self, config: dict[str, Any]) -> bool:
        url = config.get("url", "")
        if not isinstance(url, str):
            return False
        return url.startswith("http://") or url.startswith("https://")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _post_webhook(
        url: str,
        payload: dict[str, Any],
        retries: int = 3,
    ) -> None:
        """POST *payload* to *url* with exponential backoff.

        Retries on 5xx and network errors.  2xx and 4xx are terminal.
        Raises the last exception when all retries are exhausted.
        """
        import time as _time

        for attempt in range(retries):
            try:
                with httpx.Client(timeout=10.0) as client:
                    resp = client.post(url, json=payload)
                if resp.status_code < 500:
                    return  # 2xx or 4xx — terminal
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt == retries - 1:
                    raise
            _time.sleep(2**attempt)  # 2s, 4s, 8s


# ---------------------------------------------------------------------------
# REST API
# ---------------------------------------------------------------------------


class RESTAPIDeliveryChannel(DeliveryChannel):
    """Deliver via HTTP POST to a REST API endpoint.

    POSTs JSON payload to each recipient URL with up to 3 retries
    and exponential backoff (same retry policy as webhook).
    """

    @property
    def name(self) -> str:
        return "rest_api"

    def send(
        self,
        product: Product,
        payload: dict[str, Any],
        recipients: list[str],
    ) -> DeliveryResult:
        failed_urls: list[str] = []
        success_count = 0

        for url in recipients:
            try:
                self._post_payload(url, payload)
                success_count += 1
            except Exception as exc:
                logger.warning("REST API POST to %s failed: %s", url, exc)
                failed_urls.append(url)

        all_succeeded = len(failed_urls) == 0
        return DeliveryResult(
            product_id=product.id,
            channel=self.name,
            status="success" if all_succeeded else "partial",
            timestamp=_now_utc(),
            recipient_count=success_count,
            error=None if all_succeeded else f"{len(failed_urls)} endpoint(s) failed",
        )

    def validate_config(self, config: dict[str, Any]) -> bool:
        url = config.get("url", "")
        if not isinstance(url, str):
            return False
        return url.startswith("http://") or url.startswith("https://")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _post_payload(
        url: str,
        payload: dict[str, Any],
        retries: int = 3,
    ) -> None:
        """POST *payload* to *url* with exponential backoff.

        Retries on 5xx and network errors.  2xx and 4xx are terminal.
        Raises the last exception when all retries are exhausted.
        """
        import time as _time

        for attempt in range(retries):
            try:
                with httpx.Client(timeout=10.0) as client:
                    resp = client.post(url, json=payload)
                if resp.status_code < 500:
                    return  # 2xx or 4xx — terminal
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt == retries - 1:
                    raise
            _time.sleep(2**attempt)  # 2s, 4s, 8s


# ---------------------------------------------------------------------------
# File Export
# ---------------------------------------------------------------------------


class FileExportDeliveryChannel(DeliveryChannel):
    """Deliver by writing payload (as JSON) to a local file path.

    The output path is resolved in order:
      1. First entry in *recipients* list (literal file path)
      2. ``config["export_path"]``
      3. ``config["path"]``

    If none of these are provided the delivery is marked as failed.
    """

    @property
    def name(self) -> str:
        return "file_export"

    def send(
        self,
        product: Product,
        payload: dict[str, Any],
        recipients: list[str],
    ) -> DeliveryResult:
        import json as _json

        config = product.config or {}
        path: str | None = None

        if recipients:
            path = recipients[0]
        elif config.get("export_path"):
            path = config["export_path"]
        elif config.get("path"):
            path = config["path"]

        if not path:
            return DeliveryResult(
                product_id=product.id,
                channel=self.name,
                status="failed",
                timestamp=_now_utc(),
                recipient_count=0,
                error="No output path provided (recipients, "
                'config["export_path"], or config["path"])',
            )

        try:
            with open(path, "w", encoding="utf-8") as fh:
                _json.dump(payload, fh, ensure_ascii=False, indent=2)
            logger.info("Exported delivery payload to %s", path)
            return DeliveryResult(
                product_id=product.id,
                channel=self.name,
                status="success",
                timestamp=_now_utc(),
                recipient_count=1,
                error=None,
            )
        except OSError as exc:
            logger.error("File export to %s failed: %s", path, exc)
            return DeliveryResult(
                product_id=product.id,
                channel=self.name,
                status="failed",
                timestamp=_now_utc(),
                recipient_count=0,
                error=str(exc),
            )

    def validate_config(self, config: dict[str, Any]) -> bool:
        path = config.get("export_path") or config.get("path")
        if not isinstance(path, str):
            return False
        return len(path.strip()) > 0


# ---------------------------------------------------------------------------
# Discord / Telegram / DingTalk / Feishu / WeChat
# ---------------------------------------------------------------------------

from autoinfo.delivery.discord import DiscordDeliveryChannel  # noqa: E402
from autoinfo.delivery.telegram import TelegramDeliveryChannel  # noqa: E402
from autoinfo.delivery.wechat_work import WeChatWorkDeliveryChannel  # noqa: E402
from autoinfo.delivery.wechat_oa import WeChatOADeliveryChannel  # noqa: E402
from autoinfo.delivery.dingtalk import DingTalkDeliveryChannel  # noqa: E402
from autoinfo.delivery.feishu import FeiShuDeliveryChannel  # noqa: E402

# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_CHANNEL_REGISTRY: dict[str, type[DeliveryChannel]] = {
    "smtp": SMTPDeliveryChannel,
    "webhook": WebhookDeliveryChannel,
    "rest_api": RESTAPIDeliveryChannel,
    "file_export": FileExportDeliveryChannel,
    "discord": DiscordDeliveryChannel,
    "telegram": TelegramDeliveryChannel,
    "wechat_work": WeChatWorkDeliveryChannel,
    "wechat_oa": WeChatOADeliveryChannel,
    "dingtalk": DingTalkDeliveryChannel,
    "feishu": FeiShuDeliveryChannel,
}


def get_channel(name: str) -> DeliveryChannel:
    """Return a :class:`DeliveryChannel` instance for *name*.

    Parameters
    ----------
    name:
        Channel name — ``"smtp"``, ``"webhook"``, ``"rest_api"``,
        ``"file_export"``, ``"discord"``, ``"feishu"``, ``"wechat_work"``, …

    Returns
    -------
    DeliveryChannel
        An instance of the matching channel class.

    Raises
    ------
    ValueError
        If *name* is not a registered channel.
    """
    cls = _CHANNEL_REGISTRY.get(name)
    if cls is None:
        valid = ", ".join(sorted(_CHANNEL_REGISTRY))
        raise ValueError(
            f"Unknown delivery channel {name!r}. Valid channels: {valid}"
        )
    return cls()


def list_channels() -> list[str]:
    """Return the list of registered channel names."""
    return sorted(_CHANNEL_REGISTRY)


def get_available_channels() -> list[str]:
    """Return the list of available delivery channel names.

    Returns
    -------
    list[str]
        Sorted list of registered channel names (e.g. ``["discord", "file_export", "rest_api", "smtp", "webhook"]``).
    """
    return sorted(_CHANNEL_REGISTRY)
