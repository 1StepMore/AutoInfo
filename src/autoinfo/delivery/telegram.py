"""Telegram Bot delivery channel for AutoInfo.

Sends text messages to Telegram chats via the Bot API
(``POST bot{token}/sendMessage``).

Requires a Telegram Bot Token (configured under ``bot_token``)
and a target chat ID (configured under ``chat_id``).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from autoinfo.delivery import DeliveryChannel, _now_utc
from autoinfo.models import DeliveryResult, Product

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TELEGRAM_API_BASE = "https://api.telegram.org"
"""Telegram Bot API base URL."""

_SEND_MESSAGE_ENDPOINT = "/bot{token}/sendMessage"
"""API endpoint for sending messages (token injected at call time)."""

_MAX_MESSAGE_LENGTH = 4096
"""Maximum characters allowed in a Telegram message ``text`` field."""

_DEFAULT_TIMEOUT = 15.0
"""HTTP request timeout in seconds."""


# ---------------------------------------------------------------------------
# Telegram delivery
# ---------------------------------------------------------------------------


class TelegramDeliveryChannel(DeliveryChannel):
    """Deliver messages to a Telegram chat via the Bot API.

    The target chat is resolved in this order:

    1. Each entry in *recipients* (treated as a chat ID).
    2. ``config["chat_id"]``.
    3. ``payload["chat_id"]``.

    Authentication
    --------------
    A Telegram Bot Token must be provided via ``config["bot_token"]``.
    The token is passed as a URL path parameter (``/bot<token>/sendMessage``).

    Payload keys understood by ``send()``:

    * ``text`` — message body (truncated to 4096 chars).  Falls back to
      ``content`` for compatibility with generic payloads.
    * ``parse_mode`` — ``"HTML"`` or ``"MarkdownV2"`` (optional).
    * ``disable_web_page_preview`` — ``True`` to strip link previews.
    * ``disable_notification`` — ``True`` to send silently.
    * ``protect_content`` — ``True`` to prevent forwarding/saving.

    .. note::

       This adapter only sends messages via the Bot API.  It does **not**
       implement command handling, inline queries, or webhook listeners.
    """

    @property
    def name(self) -> str:
        return "telegram"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send(
        self,
        product: Product,
        payload: dict[str, Any],
        recipients: list[str],
    ) -> DeliveryResult:
        """Deliver *payload* to Telegram chat(s).

        Parameters
        ----------
        product:
            Product being delivered (its ``.config`` may carry the
            bot token and default chat ID).
        payload:
            Should contain at least a ``"text"`` or ``"content"`` key.
            May optionally include ``parse_mode``, ``disable_web_page_preview``,
            ``disable_notification``, and ``protect_content``.
        recipients:
            If non-empty each entry is treated as a chat ID.
            When empty the chat ID is read from ``product.config``
            (or ``payload``).

        Returns
        -------
        DeliveryResult
        """
        config = product.config or {}

        bot_token: str | None = (
            config.get("bot_token")
            or payload.get("bot_token")
        )

        if not bot_token:
            return DeliveryResult(
                product_id=product.id,
                channel=self.name,
                status="failed",
                timestamp=_now_utc(),
                recipient_count=0,
                error="Telegram bot_token is required in config",
            )

        # Resolve target chat IDs
        chat_ids: list[str] = list(recipients) if recipients else []

        if not chat_ids:
            cid = (
                config.get("chat_id")
                or payload.get("chat_id")
            )
            if cid is not None:
                chat_ids.append(str(cid))

        if not chat_ids:
            return DeliveryResult(
                product_id=product.id,
                channel=self.name,
                status="failed",
                timestamp=_now_utc(),
                recipient_count=0,
                error=(
                    "No Telegram chat_id provided.  Pass via recipients, "
                    'config["chat_id"], or payload["chat_id"].'
                ),
            )

        # Build message body
        body = self._build_message(payload)

        # Deliver to each chat
        failed: list[str] = []
        success_count = 0

        for cid in chat_ids:
            try:
                self._send_message(bot_token, cid, body)
                success_count += 1
            except Exception as exc:
                logger.warning("Telegram chat %s failed: %s", cid, exc)
                failed.append(cid)

        all_succeeded = len(failed) == 0
        return DeliveryResult(
            product_id=product.id,
            channel=self.name,
            status="success" if all_succeeded else "partial",
            timestamp=_now_utc(),
            recipient_count=success_count,
            error=(
                None
                if all_succeeded
                else f"{len(failed)} Telegram chat(s) failed"
            ),
        )

    def validate_config(self, config: dict[str, Any]) -> bool:
        """Return ``True`` when *config* contains a bot token.

        A chat ID is recommended but not strictly required at
        validation time (it can be supplied per-invocation).
        """
        token = config.get("bot_token", "")
        return bool(token and isinstance(token, str) and len(token.strip()) > 0)

    def health_check(self) -> dict[str, Any]:
        import os as _os
        import time as _time
        start = _time.time()
        try:
            token = _os.environ.get("TELEGRAM_BOT_TOKEN", "")
            if not token:
                latency = (_time.time() - start) * 1000
                return {"healthy": False, "latency_ms": latency, "error": "missing config: TELEGRAM_BOT_TOKEN not set", "channel": "telegram"}
            latency = (_time.time() - start) * 1000
            return {"healthy": True, "latency_ms": latency, "error": None, "channel": "telegram"}
        except Exception as e:
            latency = (_time.time() - start) * 1000
            return {"healthy": False, "latency_ms": latency, "error": str(e), "channel": "telegram"}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_message(payload: dict[str, Any]) -> dict[str, Any]:
        """Build a Telegram ``sendMessage`` body from *payload*.

        * Extracts ``text`` (falls back to ``content`` then ``""``).
        * Truncates text to 4096 characters.
        * Passes through optional keys: ``parse_mode``,
          ``disable_web_page_preview``, ``disable_notification``,
          ``protect_content``.
        """
        body: dict[str, Any] = {}

        text = payload.get("text") or payload.get("content", "")
        body["text"] = str(text)[:_MAX_MESSAGE_LENGTH]

        for key in (
            "parse_mode",
            "disable_web_page_preview",
            "disable_notification",
            "protect_content",
        ):
            if key in payload:
                body[key] = payload[key]

        return body

    @staticmethod
    def _send_message(
        bot_token: str,
        chat_id: str,
        body: dict[str, Any],
        retries: int = 3,
    ) -> None:
        """POST *body* to the Telegram Bot API for *chat_id*.

        Inserts ``chat_id`` into the body before sending.

        Retries on 5xx and network errors with exponential backoff.
        2xx and 4xx are considered terminal (4xx errors are logged).
        """
        import time as _time

        url = f"{TELEGRAM_API_BASE}{_SEND_MESSAGE_ENDPOINT.format(token=bot_token)}"
        headers = {"Content-Type": "application/json"}

        # Stamp the target chat into the body
        payload = dict(body, chat_id=chat_id)

        for attempt in range(retries):
            try:
                with httpx.Client(timeout=_DEFAULT_TIMEOUT) as client:
                    resp = client.post(url, json=payload, headers=headers)

                if resp.status_code < 400:
                    return  # 2xx — success
                if resp.status_code < 500:
                    # 4xx — client error (e.g. bad token, chat not found)
                    logger.error(
                        "Telegram API returned %d for chat %s: %s",
                        resp.status_code,
                        chat_id,
                        resp.text[:500],
                    )
                    return  # terminal — don't retry
                # 5xx — server error, will retry
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt == retries - 1:
                    raise
            _time.sleep(2**attempt)  # 2s, 4s, 8s
