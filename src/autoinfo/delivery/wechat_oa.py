"""WeChat OA (公众号) delivery channel for AutoInfo.

Sends template messages to WeChat Official Account followers via the
``cgi-bin/message/template/send`` API.

Token lifecycle
---------------
1. On first ``send()`` call, ``GET cgi-bin/token`` is called with
   ``appid`` and ``secret`` to obtain an ``access_token`` (valid for 7200 s).
2. The token is cached in memory and transparently refreshed when near expiry.
3. If the ``send`` API returns ``errcode`` 40014 or 42001 the cached token
   is discarded and a fresh one is obtained on the next attempt.
"""

from __future__ import annotations

import logging
import time as _time
from typing import Any

import httpx

from autoinfo.delivery import DeliveryChannel, _now_utc
from autoinfo.models import DeliveryResult, Product

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BASE_URL = "https://api.weixin.qq.com"
_TOKEN_URL = _BASE_URL + "/cgi-bin/token"
_SEND_URL = _BASE_URL + "/cgi-bin/message/template/send"
_TOKEN_EXPIRY_BUFFER = 300  # seconds buffer before real expiry (2h → ~1h55m)
_DEFAULT_TIMEOUT = 15.0  # seconds for HTTP requests

# WeChat error codes that indicate token expiry / invalidity
_TOKEN_EXPIRED_CODES = {40014, 42001}


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class WeChatOAError(RuntimeError):
    """WeChat OA API returned a non-zero ``errcode``."""


# ---------------------------------------------------------------------------
# Channel
# ---------------------------------------------------------------------------


class WeChatOADeliveryChannel(DeliveryChannel):
    """Deliver template messages via WeChat Official Account (公众号).

    Configuration keys (*required*):

    ================  ============================================
    Key               Description
    ================  ============================================
    ``app_id``        WeChat OA App ID (AppID)
    ``app_secret``    WeChat OA App Secret (AppSecret)
    ``template_id``   Template message ID (模板ID)
    ================  ============================================

    Recipients are WeChat OA user ``open_id`` values (one per recipient entry).

    The *payload* dict may contain:

    * ``data`` — dict of template data fields (``{{keyword.DATA}}``)
    * ``url`` — optional redirect URL when user taps the template
    * ``miniprogram`` — optional mini-program redirect dict
      (``{"appid": "...", "pagepath": "..."}``)

    Example payload::

        {
            "data": {
                "first": {"value": "You have a new message", "color": "#173177"},
                "keyword1": {"value": "Order 12345", "color": "#173177"},
                "keyword2": {"value": "2024-01-07", "color": "#173177"},
                "remark": {"value": "Please check your order status.", "color": "#173177"},
            },
            "url": "https://example.com/order/12345",
        }
    """

    # ------------------------------------------------------------------
    # Token cache (per-instance)
    # ------------------------------------------------------------------

    def __init__(self) -> None:
        self._token: str | None = None
        self._token_expires_at: float = 0.0  # unix timestamp

    # ------------------------------------------------------------------
    # DeliveryChannel protocol
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "wechat_oa"

    def send(
        self,
        product: Product,
        payload: dict[str, Any],
        recipients: list[str],
    ) -> DeliveryResult:
        """Send a WeChat OA template message to *recipients*.

        Each entry in *recipients* is treated as an ``open_id``.

        Parameters
        ----------
        product:
            Product being delivered (its ``.config`` carries
            ``app_id``, ``app_secret``, and ``template_id``).
        payload:
            Template data.  See class docstring for supported keys.
        recipients:
            List of WeChat OA ``open_id`` values to receive the message.

        Returns
        -------
        DeliveryResult
        """
        config = product.config or {}

        app_id = config.get("app_id", "")
        app_secret = config.get("app_secret", "")
        template_id = config.get("template_id", "")

        if not app_id or not app_secret or not template_id:
            return DeliveryResult(
                product_id=product.id,
                channel=self.name,
                status="failed",
                timestamp=_now_utc(),
                recipient_count=0,
                error="Missing required config: app_id, app_secret, template_id",
            )

        if not recipients:
            return DeliveryResult(
                product_id=product.id,
                channel=self.name,
                status="failed",
                timestamp=_now_utc(),
                recipient_count=0,
                error="At least one recipient (open_id) is required",
            )

        # Template data — support both nested (under payload["data"])
        # and flat payload for convenience.
        template_data = payload.get("data", payload)

        try:
            token = self._get_token(app_id, app_secret)
        except (WeChatOAError, httpx.HTTPError, OSError) as exc:
            logger.error("WeChat OA token acquisition failed: %s", exc)
            return DeliveryResult(
                product_id=product.id,
                channel=self.name,
                status="failed",
                timestamp=_now_utc(),
                recipient_count=0,
                error=str(exc),
            )

        failed_ids: list[str] = []
        success_count = 0

        for open_id in recipients:
            oid = open_id.strip()
            if not oid:
                continue
            try:
                self._send_template(token, oid, template_id, template_data, payload)
                success_count += 1
            except Exception as exc:
                logger.warning(
                    "WeChat OA send to %s failed: %s", oid, exc
                )
                failed_ids.append(oid)

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
                else f"{len(failed_ids)} open_id(s) failed"
            ),
        )

    def validate_config(self, config: dict[str, Any]) -> bool:
        """Return ``True`` when *config* has valid WeChat OA credentials.

        Checks for non-empty ``app_id``, ``app_secret``, and ``template_id``.
        """
        app_id = config.get("app_id", "")
        app_secret = config.get("app_secret", "")
        template_id = config.get("template_id", "")
        return bool(app_id and app_secret and template_id)

    def health_check(self) -> dict[str, Any]:
        import os as _os
        import time as _time
        start = _time.time()
        try:
            app_id = _os.environ.get("WECHAT_OA_APPID", "")
            app_secret = _os.environ.get("WECHAT_OA_APPSECRET", "")
            if not app_id or not app_secret:
                latency = (_time.time() - start) * 1000
                return {"healthy": False, "latency_ms": latency, "error": "missing config: WECHAT_OA_APPID or WECHAT_OA_APPSECRET not set", "channel": "wechat_oa"}
            latency = (_time.time() - start) * 1000
            return {"healthy": True, "latency_ms": latency, "error": None, "channel": "wechat_oa"}
        except Exception as e:
            latency = (_time.time() - start) * 1000
            return {"healthy": False, "latency_ms": latency, "error": str(e), "channel": "wechat_oa"}

    # ------------------------------------------------------------------
    # Token management
    # ------------------------------------------------------------------

    def _get_token(self, app_id: str, app_secret: str) -> str:
        """Return a valid ``access_token``, fetching or refreshing if necessary.

        The token is cached in memory for the instance lifetime.
        A 300-second buffer is subtracted from the TTL to avoid
        edge-of-expiry failures.
        """
        now = _time.time()
        if self._token is not None and now < self._token_expires_at:
            return self._token

        # Fetch new token
        params: dict[str, str] = {
            "grant_type": "client_credential",
            "appid": app_id,
            "secret": app_secret,
        }
        with httpx.Client(timeout=_DEFAULT_TIMEOUT) as client:
            resp = client.get(_TOKEN_URL, params=params)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()

        errcode = data.get("errcode", 0)
        if errcode != 0:
            errmsg = data.get("errmsg", "unknown error")
            raise WeChatOAError(
                f"Failed to obtain access_token "
                f"(errcode={errcode}, errmsg={errmsg})"
            )

        token: str = data["access_token"]
        expires_in: int = data.get("expires_in", 7200)

        self._token = token
        self._token_expires_at = now + expires_in - _TOKEN_EXPIRY_BUFFER

        logger.debug(
            "WeChat OA access_token refreshed, "
            "expires in %d s (cached until %d s)",
            expires_in,
            expires_in - _TOKEN_EXPIRY_BUFFER,
        )
        return token

    # ------------------------------------------------------------------
    # Template message sending
    # ------------------------------------------------------------------

    def _send_template(
        self,
        token: str,
        open_id: str,
        template_id: str,
        template_data: dict[str, Any],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """POST a template message to a single WeChat OA user.

        Retries on 5xx errors with exponential backoff (up to 3 attempts).
        On token expiry (errcode 40014/42001), clears the cached token and
        raises so the callers ``send()`` can retry on the next recipient.
        """
        body: dict[str, Any] = {
            "touser": open_id,
            "template_id": template_id,
            "data": template_data,
        }

        # Optional: redirect URL or mini-program
        url = payload.get("url")
        if url:
            body["url"] = url

        miniprogram = payload.get("miniprogram")
        if miniprogram:
            body["miniprogram"] = miniprogram

        # POST with retry
        api_url = f"{_SEND_URL}?access_token={token}"
        last_exc: Exception | None = None

        for attempt in range(3):
            try:
                with httpx.Client(timeout=_DEFAULT_TIMEOUT) as client:
                    resp = client.post(api_url, json=body)
                if resp.status_code < 500:
                    # 2xx or 4xx — terminal
                    data: dict[str, Any] = resp.json()
                    errcode = data.get("errcode", -1)
                    if errcode == 0:
                        return data

                    # Token expired → clear cache and raise
                    if errcode in _TOKEN_EXPIRED_CODES:
                        self._token = None
                        self._token_expires_at = 0.0
                        raise WeChatOAError(
                            f"Access token expired/invalid "
                            f"(errcode={errcode}, errmsg={data.get('errmsg', '')})"
                        )

                    # Other API error — terminal (e.g. invalid template_id,
                    # open_id not subscribed, etc.)
                    raise WeChatOAError(
                        f"Template send failed "
                        f"(errcode={errcode}, errmsg={data.get('errmsg', '')})"
                    )
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_exc = exc
                if attempt == 2:
                    raise
            _time.sleep(2**attempt)  # 1s, 2s, 4s

        raise RuntimeError("Unreachable") from last_exc  # pragma: no cover
