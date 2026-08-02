"""Push notification delivery adapter for AutoInfo.

Provides a generic HTTP-POST-based push channel that delivers content
to a configured endpoint with optional Bearer-token authentication.

No platform-specific SDK — uses a plain HTTP POST endpoint.
Content is sent as JSON payload.

Design
------
* :class:`PushDeliveryChannel` — DeliveryChannel ABC implementation
* Registered as ``"push"`` in the channel registry
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

_RETRIES = 3
"""Number of retry attempts for transient failures."""

_DEFAULT_TIMEOUT = 30.0
"""Default HTTP timeout in seconds."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_token(config: dict[str, Any]) -> str | None:
    """Resolve the push token from config, supporting ``${ENV_VAR}`` references.

    Looks up ``push_token`` in *config*.  Strips env-var reference
    syntax ``${…}`` and resolves from ``os.environ`` if present.

    Returns
    -------
    str or None
        The resolved token, or ``None`` if not configured.
    """
    import os as _os

    token: str | None = config.get("push_token")
    if not token:
        return None

    # Unwrap ${VAR_NAME} references
    if isinstance(token, str) and token.startswith("${") and token.endswith("}"):
        var_name = token[2:-1]
        token = _os.environ.get(var_name, token)

    return token if token else None


# ---------------------------------------------------------------------------
# Push delivery channel
# ---------------------------------------------------------------------------


class PushDeliveryChannel(DeliveryChannel):
    """Deliver content to a generic push notification endpoint via HTTP POST.

    Formats KB content (title + body) into a JSON payload and POSTs
    it to the configured push endpoint with optional Bearer-token
    authentication.

    Configuration
    -------------
    Required keys in ``product.config`` (or environment):

    * ``push_endpoint`` — URL to POST to (or ``${PUSH_ENDPOINT}`` env var)

    Optional:

    * ``push_token`` — Bearer token (or ``${PUSH_TOKEN}`` env var reference)
    * ``timeout`` — HTTP timeout in seconds (default: 30)

    Payload keys understood by ``send()``:

    * ``title`` — notification title
    * ``content`` — notification body
    * ``url`` — link included in the payload
    * ``extra`` — dict of extra fields to include in the payload

    .. note::

       This adapter uses a **generic HTTP POST pattern**.  It does not
       implement platform-specific Web Push (RFC 8030), VAPID, or
       browser-based push APIs.  For browser push notifications, use a
       dedicated Web Push library (e.g. ``pywebpush``) as an optional extra.
    """

    @property
    def name(self) -> str:
        return "push"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send(
        self,
        product: Product,
        payload: dict[str, Any],
        recipients: list[str],
    ) -> DeliveryResult:
        """Deliver *payload* to the push endpoint.

        Parameters
        ----------
        product:
            Product being delivered.  ``.config`` carries push
            configuration (push_endpoint, push_token, timeout).
        payload:
            Content to push (title, content, url, extra, …).
        recipients:
            Optional list of endpoint URLs.  When empty the endpoint
            is read from ``product.config["push_endpoint"]`` or the
            ``PUSH_ENDPOINT`` environment variable.

        Returns
        -------
        DeliveryResult
        """
        import os as _os

        config = product.config or {}

        # Resolve endpoint
        # Resolve token
        token = _resolve_token(config)
        if not token:
            token = payload.get("push_token", "")

        # Build the notification payload
        body: dict[str, Any] = {
            "title": payload.get("title", ""),
            "body": payload.get("content", ""),
            "source": payload.get("url", ""),
        }
        # Merge extra fields
        extra = payload.get("extra", {})
        if isinstance(extra, dict):
            body.update(extra)

        # Resolve timeout
        timeout = float(config.get("timeout", _DEFAULT_TIMEOUT))

        # Determine target endpoints — recipients take priority over config/ep env
        urls: list[str]
        if recipients:
            urls = list(recipients)
        else:
            endpoint: str | None = (
                config.get("push_endpoint")
                or payload.get("push_endpoint")
                or _os.environ.get("PUSH_ENDPOINT", "")
            )
            if not endpoint:
                return DeliveryResult(
                    product_id=product.id,
                    channel=self.name,
                    status="failed",
                    timestamp=_now_utc(),
                    recipient_count=0,
                    error=(
                        "No push endpoint configured.  Set push_endpoint in config, "
                        "payload, or PUSH_ENDPOINT environment variable."
                    ),
                )
            urls = [endpoint]

        # Deliver to each endpoint
        headers: dict[str, str] = {
            "Content-Type": "application/json",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        failed: list[str] = []
        success_count = 0

        for url in urls:
            try:
                self._post_push(url, body, headers, timeout)
                success_count += 1
            except Exception as exc:
                logger.warning("Push delivery to %s failed: %s", url, exc)
                failed.append(url)

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
                else f"{len(failed)} endpoint(s) failed"
            ),
        )

    def validate_config(self, config: dict[str, Any]) -> bool:
        """Return ``True`` when *config* contains a push endpoint.

        A push token is optional — endpoints may not require auth.
        """
        endpoint = config.get("push_endpoint", "")
        return bool(endpoint and isinstance(endpoint, str) and len(endpoint.strip()) > 0)

    def health_check(self) -> dict[str, Any]:
        import os as _os

        start = _time.time()
        try:
            endpoint = _os.environ.get("PUSH_ENDPOINT", "")
            token = _os.environ.get("PUSH_TOKEN", "")

            if not endpoint:
                latency = (_time.time() - start) * 1000
                return {
                    "healthy": False,
                    "latency_ms": latency,
                    "error": "missing config: PUSH_ENDPOINT not set",
                    "channel": "push",
                }

            # Quick connectivity check — HEAD request
            headers: dict[str, str] = {}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            with httpx.Client(timeout=5.0) as client:
                resp = client.head(
                    endpoint,
                    headers=headers,
                )
            latency = (_time.time() - start) * 1000
            healthy = resp.status_code < 500
            return {
                "healthy": healthy,
                "latency_ms": latency,
                "error": None if healthy else f"HTTP {resp.status_code}",
                "channel": "push",
            }
        except Exception as e:
            latency = (_time.time() - start) * 1000
            return {
                "healthy": False,
                "latency_ms": latency,
                "error": str(e),
                "channel": "push",
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _post_push(
        url: str,
        body: dict[str, Any],
        headers: dict[str, str],
        timeout: float = _DEFAULT_TIMEOUT,
        retries: int = _RETRIES,
    ) -> None:
        """POST *body* to *url* as a push notification.

        Uses Bearer token authentication if provided.  Retries on 5xx
        and network errors with exponential backoff.  2xx is success,
        4xx is terminal (logged and raised).

        Raises
        ------
        httpx.HTTPStatusError
            On 4xx auth/permission errors (terminal — no retry).
        httpx.TimeoutException / httpx.NetworkError
            When all retries are exhausted.
        """
        for attempt in range(retries):
            try:
                with httpx.Client(timeout=timeout) as client:
                    resp = client.post(url, json=body, headers=headers)

                if resp.status_code < 400:
                    return  # 2xx — success
                if resp.status_code < 500:
                    # 4xx — client error (e.g. bad token, permission denied)
                    logger.error(
                        "Push endpoint %s returned %d: %s",
                        url,
                        resp.status_code,
                        resp.text[:500],
                    )
                    raise httpx.HTTPStatusError(
                        f"Push endpoint returned "
                        f"{resp.status_code}: {resp.text[:200]}",
                        request=resp.request,
                        response=resp,
                    )
                # 5xx — server error, will retry
                logger.warning(
                    "Push endpoint %s returned 5xx %d (attempt %d/%d)",
                    url,
                    resp.status_code,
                    attempt + 1,
                    retries,
                )
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt == retries - 1:
                    raise
            except httpx.HTTPStatusError:
                raise  # 4xx — no retry
            _time.sleep(2**attempt)  # 2s, 4s, 8s

        # If we exhaust retries on 5xx, the last exception will have been
        # raised inside the loop.  This line is a safeguard.
        raise RuntimeError(
            f"Failed to push to {url} after {retries} retries"
        )
