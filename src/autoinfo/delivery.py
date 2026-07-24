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

from autoinfo.email_sender import send_digest
from autoinfo.models import DeliveryResult, Product

logger = logging.getLogger(__name__)


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
# Factory
# ---------------------------------------------------------------------------

_CHANNEL_REGISTRY: dict[str, type[DeliveryChannel]] = {
    "smtp": SMTPDeliveryChannel,
    "webhook": WebhookDeliveryChannel,
}


def get_channel(name: str) -> DeliveryChannel:
    """Return a :class:`DeliveryChannel` instance for *name*.

    Parameters
    ----------
    name:
        Channel name — ``"smtp"`` or ``"webhook"``.

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
