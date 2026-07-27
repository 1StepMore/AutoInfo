"""Discord delivery channel for AutoInfo.

Sends messages to Discord channels via the Discord REST API
(``POST /channels/{channel_id}/messages``).

Requires a Discord Bot Token (configured under ``bot_token``).
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

DISCORD_API_BASE = "https://discord.com/api/v10"
"""Discord REST API base URL."""

_MAX_CONTENT_LENGTH = 2000
"""Maximum characters allowed in a Discord message ``content`` field."""


# ---------------------------------------------------------------------------
# Discord delivery
# ---------------------------------------------------------------------------


class DiscordDeliveryChannel(DeliveryChannel):
    """Deliver messages to a Discord channel via the REST API.

    The channel(s) to post to are resolved in this order:

    1. Each entry in *recipients* (treated as a Discord channel ID).
    2. ``config["channel_id"]``.
    3. ``config["discord_channel_id"]`` (legacy alias).

    Authentication
    --------------
    A Discord Bot Token must be provided via ``config["bot_token"]``
    (or ``config["discord_bot_token"]`` as a legacy alias). The token
    is sent as ``Authorization: Bot {token}``.

    Payload keys understood by ``send()``:

    * ``content`` — plain-text message body (truncated to 2000 chars).
    * ``embeds`` — list of Discord embed dicts (optional).
    * ``components`` — list of Discord component dicts (optional).

    .. note::

       This adapter only sends via the REST API.  It does **not**
       implement gateway intents, slash commands, or button handlers.
    """

    @property
    def name(self) -> str:
        return "discord"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send(
        self,
        product: Product,
        payload: dict[str, Any],
        recipients: list[str],
    ) -> DeliveryResult:
        """Deliver *payload* to Discord channel(s).

        Parameters
        ----------
        product:
            Product being delivered (its ``.config`` may carry the
            bot token and default channel ID).
        payload:
            Must contain at least a ``"content"`` key.  May optionally
            include ``"embeds"`` and ``"components"``.
        recipients:
            If non-empty each entry is treated as a Discord channel ID.
            When empty the channel ID is read from ``product.config``.

        Returns
        -------
        DeliveryResult
        """
        config = product.config or {}
        bot_token: str | None = (
            config.get("bot_token")
            or config.get("discord_bot_token")
            or payload.get("bot_token")
        )

        if not bot_token:
            return DeliveryResult(
                product_id=product.id,
                channel=self.name,
                status="failed",
                timestamp=_now_utc(),
                recipient_count=0,
                error="Discord bot_token is required in config",
            )

        # Resolve target channel IDs
        channel_ids: list[str] = list(recipients) if recipients else []

        if not channel_ids:
            cid = (
                config.get("channel_id")
                or config.get("discord_channel_id")
                or payload.get("channel_id")
            )
            if cid:
                channel_ids.append(str(cid))

        if not channel_ids:
            return DeliveryResult(
                product_id=product.id,
                channel=self.name,
                status="failed",
                timestamp=_now_utc(),
                recipient_count=0,
                error=(
                    "No Discord channel_id provided.  Pass via recipients, "
                    'config["channel_id"], or payload["channel_id"].'
                ),
            )

        # Prepare message body
        body = self._build_message(payload)

        failed: list[str] = []
        success_count = 0

        for cid in channel_ids:
            try:
                self._post_message(bot_token, cid, body)
                success_count += 1
            except Exception as exc:
                logger.warning("Discord channel %s failed: %s", cid, exc)
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
                else f"{len(failed)} Discord channel(s) failed"
            ),
        )

    def validate_config(self, config: dict[str, Any]) -> bool:
        """Return ``True`` when *config* contains a bot token.

        A channel ID is recommended but not strictly required at
        validation time (it can be supplied per-invocation).
        """
        token = config.get("bot_token") or config.get("discord_bot_token")
        return bool(token and isinstance(token, str) and len(token.strip()) > 0)

    def health_check(self) -> dict[str, Any]:
        import os as _os
        import time as _time
        start = _time.time()
        try:
            token = _os.environ.get("DISCORD_BOT_TOKEN", "")
            if not token:
                latency = (_time.time() - start) * 1000
                return {"healthy": False, "latency_ms": latency, "error": "missing config: DISCORD_BOT_TOKEN not set", "channel": "discord"}
            latency = (_time.time() - start) * 1000
            return {"healthy": True, "latency_ms": latency, "error": None, "channel": "discord"}
        except Exception as e:
            latency = (_time.time() - start) * 1000
            return {"healthy": False, "latency_ms": latency, "error": str(e), "channel": "discord"}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_message(payload: dict[str, Any]) -> dict[str, Any]:
        """Build a Discord API message dict from *payload*.

        * Truncates ``content`` to 2000 characters.
        * Passes ``embeds`` and ``components`` through if present.
        """
        body: dict[str, Any] = {}

        content = payload.get("content", "")
        if content:
            body["content"] = str(content)[:_MAX_CONTENT_LENGTH]

        embeds = payload.get("embeds")
        if embeds is not None:
            body["embeds"] = embeds

        components = payload.get("components")
        if components is not None:
            body["components"] = components

        # Ensure at least one of content / embeds is present
        if not body:
            body["content"] = "(empty message)"

        return body

    @staticmethod
    def _post_message(
        bot_token: str,
        channel_id: str,
        body: dict[str, Any],
        retries: int = 3,
    ) -> None:
        """POST *body* to the Discord REST API for *channel_id*.

        Retries on 5xx and network errors with exponential backoff.
        2xx and 4xx are considered terminal (4xx errors are logged).
        """
        url = f"{DISCORD_API_BASE}/channels/{channel_id}/messages"
        headers = {
            "Authorization": f"Bot {bot_token}",
            "Content-Type": "application/json",
        }

        import time as _time

        for attempt in range(retries):
            try:
                with httpx.Client(timeout=10.0) as client:
                    resp = client.post(url, json=body, headers=headers)

                if resp.status_code < 400:
                    return  # 2xx — success
                if resp.status_code < 500:
                    # 4xx — client error (e.g. missing permissions, bad token)
                    logger.error(
                        "Discord API returned %d for channel %s: %s",
                        resp.status_code,
                        channel_id,
                        resp.text[:500],
                    )
                    return  # terminal — don't retry
                # 5xx — server error, will retry
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt == retries - 1:
                    raise
            _time.sleep(2**attempt)  # 2s, 4s, 8s
