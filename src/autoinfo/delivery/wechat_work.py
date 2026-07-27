"""WeChat Work (企业微信) delivery channel.

Sends application text/notice messages through WeChat Work's `message/send` API.

Token lifecycle
--------------
1. On first ``send()`` call, ``POST /gettoken`` is called with ``corpid`` and
   ``corpsecret`` to obtain an ``access_token`` (valid for 7200 s).
2. The token is cached in memory for the lifetime of the channel instance.
3. If the API returns ``errcode`` 40014 (invalid credential) or 42001
   (token expired) the cached token is discarded and a fresh one is obtained
   on the next attempt.
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

_BASE_URL = "https://qyapi.weixin.qq.com"
_GETTOKEN_URL = _BASE_URL + "/cgi-bin/gettoken"
_SEND_URL = _BASE_URL + "/cgi-bin/message/send"
_TOKEN_EXPIRY_BUFFER = 60  # seconds before real expiry to consider token stale
_DEFAULT_TIMEOUT = 15.0  # seconds for HTTP requests


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class WeChatWorkError(RuntimeError):
    """WeChat Work API returned a non-zero ``errcode``."""


# ---------------------------------------------------------------------------
# Channel
# ---------------------------------------------------------------------------


class WeChatWorkDeliveryChannel(DeliveryChannel):
    """Deliver application messages via WeChat Work (企业微信).

    Configuration keys (*required*):

    ==============  ============================================
    Key             Description
    ==============  ============================================
    ``corp_id``     Corporate ID (企业ID)
    ``corp_secret`` Application secret (应用的Secret)
    ``agent_id``    Application agent ID (应用AgentId)
    ==============  ============================================

    Recipients are WeChat Work user IDs (``userid1|userid2|…``),
    party IDs (``partyid1|partyid2``), or tag IDs.

    The *payload* dict should contain at minimum a ``"content"`` key.
    Optional keys:

    - ``"msgtype"`` — ``"text"`` (default), ``"markdown"``, ``"news"``,
      ``"textcard"``, …  See WeChat Work API docs.
    - ``"safe"`` — ``0`` (default) or ``1`` to mark as confidential.
    - ``"enable_id_trans"`` — ``0`` / ``1``.
    - ``"enable_duplicate_check"`` — ``0`` / ``1``.
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
        return "wechat_work"

    def send(
        self,
        product: Product,
        payload: dict[str, Any],
        recipients: list[str],
    ) -> DeliveryResult:
        config = product.config or {}

        corp_id = config.get("corp_id", "")
        corp_secret = config.get("corp_secret", "")
        agent_id = config.get("agent_id", "")

        if not corp_id or not corp_secret or not agent_id:
            return DeliveryResult(
                product_id=product.id,
                channel=self.name,
                status="failed",
                timestamp=_now_utc(),
                recipient_count=0,
                error="Missing required config: corp_id, corp_secret, agent_id",
            )

        # Join recipients into a pipe-separated user list
        touser = "|".join(r.strip() for r in recipients if r.strip())
        if not touser:
            return DeliveryResult(
                product_id=product.id,
                channel=self.name,
                status="failed",
                timestamp=_now_utc(),
                recipient_count=0,
                error="At least one recipient (userid) is required",
            )

        try:
            token = self._get_token(corp_id, corp_secret)
            self._send_message(token, agent_id, touser, payload)
            return DeliveryResult(
                product_id=product.id,
                channel=self.name,
                status="success",
                timestamp=_now_utc(),
                recipient_count=len(recipients),
                error=None,
            )
        except (WeChatWorkError, httpx.HTTPError, OSError) as exc:
            logger.error("WeChat Work delivery failed: %s", exc)
            return DeliveryResult(
                product_id=product.id,
                channel=self.name,
                status="failed",
                timestamp=_now_utc(),
                recipient_count=0,
                error=str(exc),
            )

    def validate_config(self, config: dict[str, Any]) -> bool:
        corp_id = config.get("corp_id", "")
        corp_secret = config.get("corp_secret", "")
        agent_id = config.get("agent_id", "")
        return bool(corp_id and corp_secret and agent_id)

    def health_check(self) -> dict[str, Any]:
        import os as _os
        import time as _time
        start = _time.time()
        try:
            corp_id = _os.environ.get("WECHAT_WORK_CORPID", "")
            corp_secret = _os.environ.get("WECHAT_WORK_CORPSECRET", "")
            if not corp_id or not corp_secret:
                latency = (_time.time() - start) * 1000
                return {"healthy": False, "latency_ms": latency, "error": "missing config: WECHAT_WORK_CORPID or WECHAT_WORK_CORPSECRET not set", "channel": "wechat_work"}
            latency = (_time.time() - start) * 1000
            return {"healthy": True, "latency_ms": latency, "error": None, "channel": "wechat_work"}
        except Exception as e:
            latency = (_time.time() - start) * 1000
            return {"healthy": False, "latency_ms": latency, "error": str(e), "channel": "wechat_work"}

    # ------------------------------------------------------------------
    # Token management
    # ------------------------------------------------------------------

    def _get_token(self, corp_id: str, corp_secret: str) -> str:
        """Return a valid ``access_token``, refreshing if necessary."""
        now = _time.time()
        if self._token is not None and now < self._token_expires_at:
            return self._token

        # Fetch new token
        params = {"corpid": corp_id, "corpsecret": corp_secret}
        with httpx.Client(timeout=_DEFAULT_TIMEOUT) as client:
            resp = client.get(_GETTOKEN_URL, params=params)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()

        errcode = data.get("errcode", 0)
        if errcode != 0:
            errmsg = data.get("errmsg", "unknown error")
            raise WeChatWorkError(
                f"Failed to obtain access_token "
                f"(errcode={errcode}, errmsg={errmsg})"
            )

        token: str = data["access_token"]
        expires_in: int = data.get("expires_in", 7200)

        self._token = token
        self._token_expires_at = now + expires_in - _TOKEN_EXPIRY_BUFFER

        logger.debug(
            "WeChat Work access_token refreshed, "
            "expires in %d s (cached until %d s)",
            expires_in,
            expires_in - _TOKEN_EXPIRY_BUFFER,
        )
        return token

    # ------------------------------------------------------------------
    # Message sending
    # ------------------------------------------------------------------

    def _send_message(
        self,
        token: str,
        agent_id: str,
        touser: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """POST a message to WeChat Work and return the JSON response.

        Retries on 5xx errors with exponential backoff (up to 3 attempts).
        On token expiry (errcode 40014/42001), clears the cached token and
        raises so the caller can retry.
        """
        msgtype = payload.get("msgtype", "text")
        content = payload.get("content", "")
        safe = payload.get("safe", 0)

        # Build the message body
        body: dict[str, Any] = {
            "touser": touser,
            "msgtype": msgtype,
            "agentid": int(agent_id),
            "safe": safe,
        }

        # Set the content sub-object per msgtype
        if msgtype == "text":
            body["text"] = {"content": content}
        elif msgtype == "markdown":
            body["markdown"] = {"content": content}
        elif msgtype == "textcard":
            body["textcard"] = {
                "title": payload.get("title", ""),
                "description": content,
                "url": payload.get("url", ""),
                "btntxt": payload.get("btntxt", "详情"),
            }
        elif msgtype == "news":
            body["news"] = {
                "articles": payload.get("articles", [{"title": "", "url": ""}])
            }
        elif msgtype == "file":
            body["file"] = {"media_id": payload.get("media_id", "")}
        elif msgtype == "image":
            body["image"] = {"media_id": payload.get("media_id", "")}
        else:
            # For custom or future msgtypes, pass the sub-object directly
            if msgtype in payload:
                body[msgtype] = payload[msgtype]

        # Optional flags
        for flag in (
            "enable_id_trans",
            "enable_duplicate_check",
            "duplicate_check_interval",
        ):
            if flag in payload:
                body[flag] = payload[flag]

        # POST with retry
        url = f"{_SEND_URL}?access_token={token}"
        last_exc: Exception | None = None

        for attempt in range(3):
            try:
                with httpx.Client(timeout=_DEFAULT_TIMEOUT) as client:
                    resp = client.post(url, json=body)
                if resp.status_code < 500:
                    # 2xx or 4xx — terminal
                    data: dict[str, Any] = resp.json()
                    errcode = data.get("errcode", -1)
                    if errcode == 0:
                        return data

                    # Token expired → clear cache and raise
                    if errcode in (40014, 42001):
                        self._token = None
                        self._token_expires_at = 0.0
                        raise WeChatWorkError(
                            f"Access token expired/invalid "
                            f"(errcode={errcode}, errmsg={data.get('errmsg', '')})"
                        )

                    # Other API error — terminal
                    raise WeChatWorkError(
                        f"Message send failed "
                        f"(errcode={errcode}, errmsg={data.get('errmsg', '')})"
                    )
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_exc = exc
                if attempt == 2:
                    raise
            _time.sleep(2**attempt)  # 1s, 2s, 4s

        raise RuntimeError("Unreachable") from last_exc  # pragma: no cover



