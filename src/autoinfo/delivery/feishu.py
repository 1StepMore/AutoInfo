"""FeiShu (飞书 / Lark) delivery channel for AutoInfo.

Sends messages via either:

1. **Webhook bot** — POST JSON to a FeiShu webhook URL.
2. **App API** — Obtain a ``tenant_access_token`` via ``app_id`` +
   ``app_secret``, then POST to ``/open-apis/im/v1/messages``.

Token lifecycle (API mode)
--------------------------
1. On first ``send()`` call, ``POST /open-apis/auth/v3/tenant_access_token/internal``
   is called to obtain a ``tenant_access_token`` (valid for 7200 s).
2. The token is cached in memory for the lifetime of the channel instance.
3. If the API returns a non-zero ``code`` indicating token expiry (``99991663``,
   ``99991664``), the cached token is discarded and a fresh one is obtained on
   the next attempt.
"""

from __future__ import annotations

import logging
import time as _time
from datetime import datetime, timezone
from typing import Any

import httpx

from autoinfo.delivery import DeliveryChannel
from autoinfo.models import DeliveryResult, Product

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FEISHU_OPEN_API = "https://open.feishu.cn/open-apis"

# Webhook bot URL template: {base}/bot/v2/hook/{hook_key}
_WEBHOOK_URL_PREFIX = f"{_FEISHU_OPEN_API}/bot/v2/hook"

# API auth endpoint
_AUTH_URL = f"{_FEISHU_OPEN_API}/auth/v3/tenant_access_token/internal"

# API message send endpoint
_SEND_URL = f"{_FEISHU_OPEN_API}/im/v1/messages"

_TOKEN_EXPIRY_BUFFER = 60  # seconds before real expiry to consider token stale
_DEFAULT_TIMEOUT = 15.0  # seconds for HTTP requests

# Token error codes that trigger a refresh
_TOKEN_EXPIRED_CODES = {99991663, 99991664}

# Supported message types
_MSGTYPE_TEXT = "text"
_MSGTYPE_POST = "post"
_MSGTYPE_INTERACTIVE = "interactive"
_MSGTYPE_SHARE_CHAT = "share_chat"
_MSGTYPE_IMAGE = "image"
_MSGTYPE_FILE = "file"
_MSGTYPE_AUDIO = "audio"
_MSGTYPE_MEDIA = "media"
_MSGTYPE_TEMPLATE = "template"

_SUPPORTED_MSGTYPES = frozenset({
    _MSGTYPE_TEXT,
    _MSGTYPE_POST,
    _MSGTYPE_INTERACTIVE,
    _MSGTYPE_SHARE_CHAT,
    _MSGTYPE_IMAGE,
    _MSGTYPE_FILE,
    _MSGTYPE_AUDIO,
    _MSGTYPE_MEDIA,
    _MSGTYPE_TEMPLATE,
})


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class FeiShuError(RuntimeError):
    """FeiShu API returned a non-zero ``code``."""


# ---------------------------------------------------------------------------
# Channel
# ---------------------------------------------------------------------------


class FeiShuDeliveryChannel(DeliveryChannel):
    """Deliver messages via FeiShu (飞书 / Lark).

    Two mutually exclusive modes are supported, controlled via config:

    ==================== ====================================================
    Config key           Description
    ==================== ====================================================
    ``mode``             ``"webhook"`` (default) or ``"api"``
    ``webhook_url``      Full webhook URL (required in webhook mode).
    ``app_id``           FeiShu app ID (required in API mode).
    ``app_secret``       FeiShu app secret (required in API mode).
    ==================== ====================================================

    Webhook mode
    ------------
    A single recipient entry is used as the *webhook key* appended to
    ``/bot/v2/hook/{key}``.  Alternatively, provide the full URL via
    ``config["webhook_url"]``.

    API mode
    --------
    Recipients are FeiShu ``open_id``, ``user_id``, ``union_id``, ``email``,
    or ``chat_id`` values.  The ``receive_id_type`` is inferred from the
    recipient format or can be set explicitly in the payload.

    Payload keys
    ------------
    ==================== ====================================================
    Key                  Description
    ==================== ====================================================
    ``content``          Message body text (for ``text`` / ``post`` types).
    ``msg_type``         ``"text"`` (default), ``"post"``, ``"interactive"``,
                         ``"share_chat"``, ``"image"``, ``"file"``,
                         ``"audio"``, ``"media"``, ``"template"``.
    ``receive_id_type``  ``"open_id"`` (default), ``"user_id"``,
                         ``"union_id"``, ``"email"``, ``"chat_id"``.
    ==================== ====================================================

    .. note::

       This adapter does **not** implement interactive cards, message recall,
       or event subscriptions.
    """

    # ------------------------------------------------------------------
    # Token cache (per-instance, API mode only)
    # ------------------------------------------------------------------

    def __init__(self) -> None:
        self._token: str | None = None
        self._token_expires_at: float = 0.0  # unix timestamp

    # ------------------------------------------------------------------
    # DeliveryChannel protocol
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "feishu"

    def send(
        self,
        product: Product,
        payload: dict[str, Any],
        recipients: list[str],
    ) -> DeliveryResult:
        config = product.config or {}
        mode: str = (config.get("mode") or "webhook").lower().strip()

        if mode == "webhook":
            return self._send_via_webhook(product, config, payload, recipients)
        elif mode == "api":
            return self._send_via_api(product, config, payload, recipients)
        else:
            return DeliveryResult(
                product_id=product.id,
                channel=self.name,
                status="failed",
                timestamp=_now_utc(),
                recipient_count=0,
                error=(
                    f"Unknown FeiShu mode {mode!r}. "
                    f"Expected 'webhook' or 'api'."
                ),
            )

    def validate_config(self, config: dict[str, Any]) -> bool:
        mode = (config.get("mode") or "webhook").lower().strip()
        if mode not in ("webhook", "api"):
            return False

        if mode == "webhook":
            url = config.get("webhook_url", "")
            if url and isinstance(url, str):
                return url.startswith("http://") or url.startswith("https://")
            return False

        # API mode
        app_id = config.get("app_id", "")
        app_secret = config.get("app_secret", "")
        return bool(app_id and app_secret)

    def health_check(self) -> dict[str, Any]:
        import os as _os
        import time as _time
        start = _time.time()
        try:
            app_id = _os.environ.get("FEISHU_APP_ID", "")
            app_secret = _os.environ.get("FEISHU_APP_SECRET", "")
            if not app_id or not app_secret:
                latency = (_time.time() - start) * 1000
                return {"healthy": False, "latency_ms": latency, "error": "missing config: FEISHU_APP_ID or FEISHU_APP_SECRET not set", "channel": "feishu"}
            latency = (_time.time() - start) * 1000
            return {"healthy": True, "latency_ms": latency, "error": None, "channel": "feishu"}
        except Exception as e:
            latency = (_time.time() - start) * 1000
            return {"healthy": False, "latency_ms": latency, "error": str(e), "channel": "feishu"}

    # ------------------------------------------------------------------
    # Webhook mode
    # ------------------------------------------------------------------

    def _send_via_webhook(
        self,
        product: Product,
        config: dict[str, Any],
        payload: dict[str, Any],
        recipients: list[str],
    ) -> DeliveryResult:
        # Resolve webhook URL
        webhook_url: str | None = config.get("webhook_url")

        # Fallback: use first recipient as the webhook key
        if not webhook_url and recipients:
            webhook_url = f"{_WEBHOOK_URL_PREFIX}/{recipients[0]}"

        if not webhook_url:
            return DeliveryResult(
                product_id=product.id,
                channel=self.name,
                status="failed",
                timestamp=_now_utc(),
                recipient_count=0,
                error=(
                    "FeiShu webhook_url is required in config or as first "
                    "recipient (webhook key)."
                ),
            )

        body = self._build_message_body(payload)

        try:
            self._post_webhook(webhook_url, body)
            return DeliveryResult(
                product_id=product.id,
                channel=self.name,
                status="success",
                timestamp=_now_utc(),
                recipient_count=len(recipients) if recipients else 1,
                error=None,
            )
        except (httpx.HTTPError, OSError) as exc:
            logger.error("FeiShu webhook delivery failed: %s", exc)
            return DeliveryResult(
                product_id=product.id,
                channel=self.name,
                status="failed",
                timestamp=_now_utc(),
                recipient_count=0,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # API mode
    # ------------------------------------------------------------------

    def _send_via_api(
        self,
        product: Product,
        config: dict[str, Any],
        payload: dict[str, Any],
        recipients: list[str],
    ) -> DeliveryResult:
        app_id = config.get("app_id", "")
        app_secret = config.get("app_secret", "")

        if not app_id or not app_secret:
            return DeliveryResult(
                product_id=product.id,
                channel=self.name,
                status="failed",
                timestamp=_now_utc(),
                recipient_count=0,
                error="FeiShu app_id and app_secret are required in API mode",
            )

        # Resolve recipients
        receive_ids: list[str] = [r.strip() for r in recipients if r.strip()]
        if not receive_ids:
            return DeliveryResult(
                product_id=product.id,
                channel=self.name,
                status="failed",
                timestamp=_now_utc(),
                recipient_count=0,
                error="At least one recipient (open_id / user_id / chat_id) is required",
            )

        receive_id_type: str = (
            payload.get("receive_id_type")
            or config.get("receive_id_type")
            or "open_id"
        )

        try:
            token = self._get_token(app_id, app_secret)
            body = self._build_message_body(payload)

            success_count = 0
            failed_ids: list[str] = []

            for rid in receive_ids:
                try:
                    self._send_api_message(token, rid, receive_id_type, body)
                    success_count += 1
                except (FeiShuError, httpx.HTTPError, OSError) as exc:
                    logger.warning(
                        "FeiShu API message to %s failed: %s", rid, exc
                    )
                    failed_ids.append(rid)

            all_succeeded = len(failed_ids) == 0
            return DeliveryResult(
                product_id=product.id,
                channel=self.name,
                status="success" if all_succeeded else "partial",
                timestamp=_now_utc(),
                recipient_count=success_count,
                error=(
                    None
                    if all_succeeded
                    else f"{len(failed_ids)} recipient(s) failed"
                ),
            )

        except (FeiShuError, httpx.HTTPError, OSError) as exc:
            logger.error("FeiShu API delivery failed: %s", exc)
            return DeliveryResult(
                product_id=product.id,
                channel=self.name,
                status="failed",
                timestamp=_now_utc(),
                recipient_count=0,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # Message building
    # ------------------------------------------------------------------

    @staticmethod
    def _build_message_body(payload: dict[str, Any]) -> dict[str, Any]:
        """Build a FeiShu API message body dict from *payload*.

        The ``msg_type`` defaults to ``"text"``.  For text messages
        the ``content`` key is wrapped into ``{"text": content}``.
        """
        msg_type: str = payload.get("msg_type", _MSGTYPE_TEXT)
        content_raw = payload.get("content", "")

        if msg_type not in _SUPPORTED_MSGTYPES:
            logger.warning(
                "Unsupported FeiShu msg_type %r, falling back to 'text'",
                msg_type,
            )
            msg_type = _MSGTYPE_TEXT

        # Build the content JSON string
        if msg_type == _MSGTYPE_TEXT:
            content_obj: dict[str, Any] = {"text": str(content_raw)}
        elif msg_type == _MSGTYPE_POST:
            # post expects a pre-built dict or falls back to text
            if isinstance(content_raw, dict):
                content_obj = content_raw
            else:
                content_obj = {
                    "zh_cn": {
                        "title": payload.get("title", ""),
                        "content": [
                            [{"tag": "text", "text": str(content_raw)}]
                        ],
                    }
                }
        elif msg_type == _MSGTYPE_INTERACTIVE:
            # interactive (card) expects a dict — use as-is or fall back
            content_obj = (
                content_raw if isinstance(content_raw, dict) else {"elements": []}
            )
        else:
            # image, file, audio, media, share_chat, template
            # Each expects a specific structured dict
            if isinstance(content_raw, dict):
                content_obj = content_raw
            else:
                content_obj = {}

        import json as _json

        body: dict[str, Any] = {
            "msg_type": msg_type,
            "content": _json.dumps(content_obj, ensure_ascii=False),
        }

        return body

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _post_webhook(
        url: str,
        body: dict[str, Any],
        retries: int = 3,
    ) -> None:
        """POST *body* to a FeiShu webhook URL with exponential backoff.

        Retries on 5xx and network errors.  2xx and 4xx are terminal.
        """
        for attempt in range(retries):
            try:
                with httpx.Client(timeout=_DEFAULT_TIMEOUT) as client:
                    resp = client.post(url, json=body)
                if resp.status_code < 500:
                    return  # 2xx or 4xx — terminal
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt == retries - 1:
                    raise
            _time.sleep(2**attempt)  # 2s, 4s, 8s

    # ------------------------------------------------------------------
    # Token management (API mode)
    # ------------------------------------------------------------------

    def _get_token(self, app_id: str, app_secret: str) -> str:
        """Return a valid ``tenant_access_token``, refreshing if necessary."""
        now = _time.time()
        if self._token is not None and now < self._token_expires_at:
            return self._token

        # Fetch new token
        body = {"app_id": app_id, "app_secret": app_secret}
        with httpx.Client(timeout=_DEFAULT_TIMEOUT) as client:
            resp = client.post(_AUTH_URL, json=body)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()

        code: int = data.get("code", -1)
        if code != 0:
            msg = data.get("msg", "unknown error")
            raise FeiShuError(
                f"Failed to obtain tenant_access_token "
                f"(code={code}, msg={msg})"
            )

        token: str = data["tenant_access_token"]
        expires_in: int = data.get("expire", 7200)

        self._token = token
        self._token_expires_at = now + expires_in - _TOKEN_EXPIRY_BUFFER

        logger.debug(
            "FeiShu tenant_access_token refreshed, "
            "expires in %d s (cached until %d s)",
            expires_in,
            expires_in - _TOKEN_EXPIRY_BUFFER,
        )
        return token

    # ------------------------------------------------------------------
    # Send API message
    # ------------------------------------------------------------------

    def _send_api_message(
        self,
        token: str,
        receive_id: str,
        receive_id_type: str,
        body: dict[str, Any],
        retries: int = 3,
    ) -> dict[str, Any]:
        """POST a message to the FeiShu IM API and return the JSON response.

        Retries on 5xx errors with exponential backoff (up to *retries*
        attempts).  On token expiry (code 99991663/99991664), clears
        the cached token and raises so the caller can retry.
        """
        url = f"{_SEND_URL}?receive_id_type={receive_id_type}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        # Add receive_id to body
        send_body = dict(body)
        send_body["receive_id"] = receive_id

        last_exc: Exception | None = None

        for attempt in range(retries):
            try:
                with httpx.Client(timeout=_DEFAULT_TIMEOUT) as client:
                    resp = client.post(url, json=send_body, headers=headers)
                if resp.status_code < 500:
                    # 2xx or 4xx — terminal
                    data: dict[str, Any] = resp.json()
                    code: int = data.get("code", -1)

                    if code == 0:
                        return data

                    # Token expired → clear cache and raise
                    if code in _TOKEN_EXPIRED_CODES:
                        self._token = None
                        self._token_expires_at = 0.0
                        raise FeiShuError(
                            f"Tenant access token expired/invalid "
                            f"(code={code}, msg={data.get('msg', '')})"
                        )

                    # Other API error — terminal
                    raise FeiShuError(
                        f"Message send failed "
                        f"(code={code}, msg={data.get('msg', '')})"
                    )
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_exc = exc
                if attempt == retries - 1:
                    raise
            _time.sleep(2**attempt)  # 1s, 2s, 4s

        raise RuntimeError("Unreachable") from last_exc  # pragma: no cover


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_utc() -> str:
    """Return ISO-8601 UTC timestamp string."""
    return datetime.now(timezone.utc).isoformat()
