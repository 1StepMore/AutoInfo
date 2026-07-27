"""DingTalk (钉钉) delivery channel.

Supports two modes:

1. **Robot webhook** — POST JSON to a DingTalk group robot webhook URL.
   Optionally signs requests with HMAC-SHA256 when ``secret`` is configured.

2. **App API** — Acquires an OAuth2 ``access_token`` via ``app_key`` +
   ``app_secret``, then sends messages via the robot batch-send API.

Token lifecycle (API mode)
--------------------------
1. On first ``send()`` call, ``POST /v1.0/oauth2/accessToken`` is called
   with ``app_key`` and ``app_secret`` to obtain a token (valid 7200 s).
2. The token is cached in memory for the lifetime of the channel instance.
3. If the API returns 401 the cached token is discarded and a fresh one
   is obtained on the next attempt.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time as _time
from base64 import b64encode
from typing import Any

import httpx

from autoinfo.delivery import DeliveryChannel, _now_utc
from autoinfo.models import DeliveryResult, Product

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ROBOT_SEND_URL = "https://oapi.dingtalk.com/robot/send"
"""DingTalk robot webhook endpoint."""

_OAUTH_TOKEN_URL = "https://oapi.dingtalk.com/v1.0/oauth2/accessToken"
"""DingTalk OAuth2 token endpoint (API mode)."""

_BATCH_SEND_URL = "https://oapi.dingtalk.com/v1.0/robot/oToMessages/batchSend"
"""DingTalk robot batch-send endpoint (API mode)."""

_TOKEN_EXPIRY_BUFFER = 60  # seconds before real expiry to consider token stale
_DEFAULT_TIMEOUT = 15.0  # seconds for HTTP requests
_MAX_CONTENT_LENGTH = 20000  # DingTalk max text length


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class DingTalkError(RuntimeError):
    """DingTalk API returned a non-success status or error code."""


# ---------------------------------------------------------------------------
# Channel
# ---------------------------------------------------------------------------


class DingTalkDeliveryChannel(DeliveryChannel):
    """Deliver messages via DingTalk (钉钉).

    Two mutually exclusive configuration modes are supported:

    **Robot webhook mode** (simpler — sends to a group):

    ===============  ===================================================
    Config key       Description
    ===============  ===================================================
    ``webhook_url``  Full robot webhook URL including ``access_token``
                     query parameter.  Example::
                       https://oapi.dingtalk.com/robot/send?access_token=abc123
    ``access_token`` DingTalk robot access token (alternative to
                     providing the full ``webhook_url``).
    ``secret``       Signing secret for HMAC-SHA256 verification
                     (optional — omit for unsigned webhooks).
    ===============  ===================================================

    **App API mode** (for sending to specific users):

    ===============  ===================================================
    Config key       Description
    ===============  ===================================================
    ``app_key``      App Key (AppKey) of the DingTalk application.
    ``app_secret``   App Secret (AppSecret) of the DingTalk application.
    ``robot_code``   Robot code of the group robot bound to the app
                     (required for API-mode batch send).
    ===============  ===================================================

    Recipients (API mode only)
        List of DingTalk user IDs to receive the message.  Ignored in
        robot webhook mode (the robot posts to the group it belongs to).

    Payload keys understood by ``send()``:

    * ``content`` — message body text (required for ``"text"`` msgtype).
    * ``msgtype`` — ``"text"`` (default), ``"markdown"``, ``"link"``,
      ``"action_card"``.
    * ``title`` — title for ``"markdown"`` and ``"action_card"`` messages.
    * ``text`` — markdown content for ``"markdown"`` msgtype (falls back
      to ``content`` if absent).
    * ``message_url`` — URL for ``"link"`` msgtype.
    * ``pic_url`` — image URL for ``"link"`` msgtype.
    * ``btn_orientation`` — ``"0"`` (horizontal) or ``"1"`` (vertical)
      for ``"action_card"`` msgtype (default ``"0"``).
    * ``single_title`` / ``single_url`` — single-button action card.
    * ``btns`` — list of ``{"title": str, "action_url": str}`` for
      multi-button action cards.
    * ``at_mobiles`` — list of phone numbers to @-mention (robot mode).
    * ``at_all`` — ``True`` to @-everyone (robot mode, default ``False``).

    .. note::

       This adapter only sends messages.  It does **not** manage
       interactive cards, webhook management, or bot callbacks.
    """

    # ------------------------------------------------------------------
    # Token cache (API mode, per-instance)
    # ------------------------------------------------------------------

    def __init__(self) -> None:
        self._token: str | None = None
        self._token_expires_at: float = 0.0  # unix timestamp

    # ------------------------------------------------------------------
    # DeliveryChannel protocol
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "dingtalk"

    def send(
        self,
        product: Product,
        payload: dict[str, Any],
        recipients: list[str],
    ) -> DeliveryResult:
        config = product.config or {}

        # Decide which mode to use
        webhook_url = config.get("webhook_url") or self._build_webhook_url(config)
        app_key = config.get("app_key", "")
        app_secret = config.get("app_secret", "")

        if webhook_url:
            return self._send_via_robot(
                product, payload, webhook_url, config
            )
        if app_key and app_secret:
            return self._send_via_api(
                product, payload, recipients, config
            )

        return DeliveryResult(
            product_id=product.id,
            channel=self.name,
            status="failed",
            timestamp=_now_utc(),
            recipient_count=0,
            error=(
                "No valid DingTalk config found. Provide either "
                '"webhook_url" (or "access_token"), or '
                '"app_key" + "app_secret".'
            ),
        )

    def validate_config(self, config: dict[str, Any]) -> bool:
        """Return ``True`` when *config* has valid DingTalk settings.

        Accepts either robot webhook or app API credentials.
        """
        webhook_url = config.get("webhook_url") or self._build_webhook_url(config)
        if webhook_url:
            return bool(
                isinstance(webhook_url, str)
                and webhook_url.startswith("https://oapi.dingtalk.com/")
            )

        app_key = config.get("app_key", "")
        app_secret = config.get("app_secret", "")
        return bool(app_key and app_secret)

    def health_check(self) -> dict[str, Any]:
        import os as _os
        import time as _time
        start = _time.time()
        try:
            app_key = _os.environ.get("DINGTALK_APP_KEY", "")
            app_secret = _os.environ.get("DINGTALK_APP_SECRET", "")
            if not app_key or not app_secret:
                latency = (_time.time() - start) * 1000
                return {"healthy": False, "latency_ms": latency, "error": "missing config: DINGTALK_APP_KEY or DINGTALK_APP_SECRET not set", "channel": "dingtalk"}
            latency = (_time.time() - start) * 1000
            return {"healthy": True, "latency_ms": latency, "error": None, "channel": "dingtalk"}
        except Exception as e:
            latency = (_time.time() - start) * 1000
            return {"healthy": False, "latency_ms": latency, "error": str(e), "channel": "dingtalk"}

    # ------------------------------------------------------------------
    # Robot webhook mode
    # ------------------------------------------------------------------

    def _send_via_robot(
        self,
        product: Product,
        payload: dict[str, Any],
        webhook_url: str,
        config: dict[str, Any],
    ) -> DeliveryResult:
        """Send message using the robot webhook."""
        secret = config.get("secret", "")

        try:
            url = self._sign_webhook_url(webhook_url, secret)
            body = self._build_robot_message(payload)
            self._post_json(url, body)

            return DeliveryResult(
                product_id=product.id,
                channel=self.name,
                status="success",
                timestamp=_now_utc(),
                recipient_count=1,
                error=None,
            )
        except (DingTalkError, httpx.HTTPError, OSError) as exc:
            logger.error("DingTalk robot delivery failed: %s", exc)
            return DeliveryResult(
                product_id=product.id,
                channel=self.name,
                status="failed",
                timestamp=_now_utc(),
                recipient_count=0,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # App API mode
    # ------------------------------------------------------------------

    def _send_via_api(
        self,
        product: Product,
        payload: dict[str, Any],
        recipients: list[str],
        config: dict[str, Any],
    ) -> DeliveryResult:
        """Send message using the DingTalk OAuth2 API."""
        app_key = config.get("app_key", "")
        app_secret = config.get("app_secret", "")
        robot_code = config.get("robot_code", "")

        if not robot_code:
            return DeliveryResult(
                product_id=product.id,
                channel=self.name,
                status="failed",
                timestamp=_now_utc(),
                recipient_count=0,
                error="robot_code is required in API mode",
            )

        if not recipients:
            return DeliveryResult(
                product_id=product.id,
                channel=self.name,
                status="failed",
                timestamp=_now_utc(),
                recipient_count=0,
                error="At least one recipient (user ID) is required in API mode",
            )

        try:
            token = self._get_oauth_token(app_key, app_secret)
            self._send_batch_message(token, robot_code, recipients, payload)

            return DeliveryResult(
                product_id=product.id,
                channel=self.name,
                status="success",
                timestamp=_now_utc(),
                recipient_count=len(recipients),
                error=None,
            )
        except (DingTalkError, httpx.HTTPError, OSError) as exc:
            logger.error("DingTalk API delivery failed: %s", exc)
            return DeliveryResult(
                product_id=product.id,
                channel=self.name,
                status="failed",
                timestamp=_now_utc(),
                recipient_count=0,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # Internal helpers — URL / signing
    # ------------------------------------------------------------------

    @staticmethod
    def _build_webhook_url(config: dict[str, Any]) -> str | None:
        """Build a robot webhook URL from ``access_token`` alone."""
        token = config.get("access_token")
        if not token:
            return None
        return f"{_ROBOT_SEND_URL}?access_token={token}"

    @staticmethod
    def _sign_webhook_url(url: str, secret: str) -> str:
        """Append timestamp and signature query parameters if *secret* is set.

        DingTalk HMAC-SHA256 signing scheme::

            timestamp = current_unix_timestamp_ms
            sign = base64(hmac_sha256(secret, timestamp + "\\n" + secret))
        """
        if not secret:
            return url

        timestamp = int(_time.time() * 1000)
        string_to_sign = f"{timestamp}\n{secret}"
        signature = b64encode(
            hmac.new(
                secret.encode("utf-8"),
                string_to_sign.encode("utf-8"),
                digestmod=hashlib.sha256,
            ).digest()
        ).decode("utf-8")

        separator = "&" if "?" in url else "?"
        return f"{url}{separator}timestamp={timestamp}&sign={signature}"

    # ------------------------------------------------------------------
    # Internal helpers — message building
    # ------------------------------------------------------------------

    def _build_robot_message(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Build a DingTalk robot webhook message dict from *payload*.

        Returns a dict conforming to the DingTalk robot webhook schema.
        """
        msgtype = payload.get("msgtype", "text")
        content = payload.get("content", "")

        body: dict[str, Any] = {
            "msgtype": msgtype,
        }

        if msgtype == "text":
            body["text"] = {"content": str(content)[:_MAX_CONTENT_LENGTH]}

        elif msgtype == "markdown":
            body["markdown"] = {
                "title": str(payload.get("title", content)[:64]),
                "text": str(payload.get("text", content)),
            }

        elif msgtype == "link":
            body["link"] = {
                "title": str(payload.get("title", "")[:64]),
                "text": str(content)[:_MAX_CONTENT_LENGTH],
                "messageUrl": str(payload.get("message_url", "")),
                "picUrl": str(payload.get("pic_url", "")),
            }

        elif msgtype == "action_card":
            card: dict[str, Any] = {
                "title": str(payload.get("title", "")[:64]),
                "text": str(content),
                "btnOrientation": str(payload.get("btn_orientation", "0")),
            }
            # Single-button vs multi-button action card
            single_title = payload.get("single_title")
            single_url = payload.get("single_url")
            btns = payload.get("btns")

            if single_title and single_url:
                card["singleTitle"] = str(single_title)
                card["singleURL"] = str(single_url)
            elif btns and isinstance(btns, list):
                card["btns"] = [
                    {
                        "title": str(b.get("title", "")),
                        "actionURL": str(b.get("action_url", "")),
                    }
                    for b in btns
                ]

            body["action_card"] = card

        else:
            # For custom / future msgtypes, pass the content directly
            body[msgtype] = payload.get(msgtype, {"content": str(content)})

        # @-mentions (only applicable for text and markdown)
        at_mobiles = payload.get("at_mobiles")
        at_all = payload.get("at_all", False)

        if at_mobiles or at_all:
            at: dict[str, Any] = {}
            if at_mobiles:
                at["atMobiles"] = list(at_mobiles)
            if at_all:
                at["isAtAll"] = True
            body["at"] = at

        return body

    # ------------------------------------------------------------------
    # Internal helpers — OAuth token management (API mode)
    # ------------------------------------------------------------------

    def _get_oauth_token(self, app_key: str, app_secret: str) -> str:
        """Return a valid OAuth2 ``access_token``, refreshing if necessary."""
        now = _time.time()
        if self._token is not None and now < self._token_expires_at:
            return self._token

        body = {"appKey": app_key, "appSecret": app_secret}

        with httpx.Client(timeout=_DEFAULT_TIMEOUT) as client:
            resp = client.post(_OAUTH_TOKEN_URL, json=body)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()

        token: str = data.get("accessToken", "")
        if not token:
            raise DingTalkError(
                "Failed to obtain DingTalk access_token: "
                f"response missing 'accessToken' field — {data}"
            )

        expires_in: int = data.get("expiresIn", 7200)

        self._token = token
        self._token_expires_at = now + expires_in - _TOKEN_EXPIRY_BUFFER

        logger.debug(
            "DingTalk access_token refreshed, "
            "expires in %d s (cached until %d s)",
            expires_in,
            expires_in - _TOKEN_EXPIRY_BUFFER,
        )
        return token

    # ------------------------------------------------------------------
    # Internal helpers — API mode batch send
    # ------------------------------------------------------------------

    def _send_batch_message(
        self,
        token: str,
        robot_code: str,
        user_ids: list[str],
        payload: dict[str, Any],
    ) -> None:
        """Send a batch message via the DingTalk robot OAuth2 API.

        Retries on 5xx and network errors (up to 3 attempts).
        On 401 response the cached token is cleared and an error is raised.
        """
        msgtype = payload.get("msgtype", "sampleText")

        # Build msgParam per msgtype
        msg_param = self._build_api_msg_param(msgtype, payload)

        body = {
            "robotCode": robot_code,
            "userIds": user_ids,
            "msgKey": msgtype,
            "msgParam": json.dumps(msg_param, ensure_ascii=False),
        }

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                with httpx.Client(timeout=_DEFAULT_TIMEOUT) as client:
                    resp = client.post(
                        _BATCH_SEND_URL, json=body, headers=headers
                    )

                if resp.status_code == 401:
                    # Token expired — clear cache and raise
                    self._token = None
                    self._token_expires_at = 0.0
                    raise DingTalkError(
                        f"Access token expired/invalid: {resp.text[:500]}"
                    )

                if resp.status_code < 500:
                    # 2xx or 4xx — terminal
                    # Check for business error codes
                    data: dict[str, Any] = resp.json()
                    errcode = data.get("errcode", 0)
                    if errcode != 0:
                        raise DingTalkError(
                            f"Message send failed "
                            f"(errcode={errcode}, "
                            f"errmsg={data.get('errmsg', data.get('message', ''))})"
                        )
                    return  # success

            except httpx.TimeoutException as exc:
                last_exc = exc
                if attempt == 2:
                    raise
            except httpx.NetworkError as exc:
                last_exc = exc
                if attempt == 2:
                    raise
            _time.sleep(2**attempt)  # 1s, 2s, 4s

        raise RuntimeError("Unreachable") from last_exc  # pragma: no cover

    # ------------------------------------------------------------------
    # Internal helpers — HTTP POST (robot mode, shared)
    # ------------------------------------------------------------------

    @staticmethod
    def _post_json(
        url: str,
        body: dict[str, Any],
        retries: int = 3,
    ) -> dict[str, Any]:
        """POST *body* to *url* with exponential backoff.

        Retries on 5xx and network errors.  2xx and 4xx are terminal.
        Raises :class:`DingTalkError` on non-zero ``errcode``.
        """
        for attempt in range(retries):
            try:
                with httpx.Client(timeout=_DEFAULT_TIMEOUT) as client:
                    resp = client.post(url, json=body)
                if resp.status_code < 500:
                    # 2xx or 4xx — terminal
                    data: dict[str, Any] = resp.json()
                    errcode = data.get("errcode", 0)
                    if errcode != 0:
                        errmsg = data.get("errmsg", "unknown error")
                        raise DingTalkError(
                            f"DingTalk robot API error "
                            f"(errcode={errcode}, errmsg={errmsg})"
                        )
                    return data
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt == retries - 1:
                    raise
            _time.sleep(2**attempt)  # 2s, 4s, 8s

        raise RuntimeError("Unreachable")  # pragma: no cover

    # ------------------------------------------------------------------
    # Internal helpers — API message param builder
    # ------------------------------------------------------------------

    @staticmethod
    def _build_api_msg_param(
        msgtype: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Build the ``msgParam`` dict for DingTalk API mode.

        The API mode uses ``msgKey`` + ``msgParam`` (JSON string) instead
        of the robot webhook schema.  This builder maps common types.
        """
        content = payload.get("content", "")

        if msgtype == "sampleText":
            return {"content": str(content)[:_MAX_CONTENT_LENGTH]}

        if msgtype == "sampleMarkdown":
            return {
                "title": str(payload.get("title", content))[:64],
                "text": str(payload.get("text", content)),
            }

        if msgtype == "sampleActionCard":
            card: dict[str, Any] = {
                "title": str(payload.get("title", ""))[:64],
                "text": str(content),
                "btnOrientation": str(payload.get("btn_orientation", "0")),
            }
            single_title = payload.get("single_title")
            single_url = payload.get("single_url")
            btns = payload.get("btns")
            if single_title and single_url:
                card["singleTitle"] = str(single_title)
                card["singleURL"] = str(single_url)
            elif btns and isinstance(btns, list):
                card["btns"] = [
                    {
                        "title": str(b.get("title", "")),
                        "actionURL": str(b.get("action_url", "")),
                    }
                    for b in btns
                ]
            return card

        # For unknown msgtypes, pass content as-is wrapped in a dict
        return {"content": str(content)}
