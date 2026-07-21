"""Webhook payload handler for push-based ingestion.

Provides the :class:`WebhookHandler` class which validates incoming JSON
payloads, optionally verifies HMAC signatures, enforces rate limits, and
creates :class:`Item <autoinfo.models.Item>` instances.

This is a **message handler** — it processes already-received payloads.
It does NOT implement an HTTP server.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from collections import deque
from typing import Any

from autoinfo.models import Item

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = frozenset({"title", "content", "source_url"})

# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


class WebhookHandler:
    """Validate and process webhook payloads into :class:`Item` instances.

    Usage::

        handler = WebhookHandler()
        item = handler.handle(
            payload={"title": "...", "content": "...", "source_url": "..."},
            config={"secret": "my-hmac-secret"},
        )
    """

    def __init__(self, source_name: str = "webhook") -> None:
        self.source_name = source_name
        # In-memory sliding-window rate limiting state
        self._request_timestamps: deque[float] = deque()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def handle(
        self,
        payload: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> Item:
        """Process a single webhook payload into an :class:`Item`.

        Parameters
        ----------
        payload : dict
            JSON payload with at least ``title``, ``content``, and
            ``source_url`` keys.
        config : dict or None
            Optional configuration dict.  Supported keys:

            * ``secret`` — HMAC-SHA256 shared secret.  When set, the
              handler looks for a ``signature`` key in *payload* (or
              *config*) and verifies it against
              ``HMAC-SHA256(secret, payload_body)``.
            * ``signature`` — HMAC signature value (fallback lookup
              when not present in *payload*).
            * ``max_requests_per_minute`` — rate limit threshold.

        Returns
        -------
        Item

        Raises
        ------
        ValueError
            If required fields are missing, HMAC verification fails, or
            rate limit is exceeded.
        """
        config = config or {}

        # -- Rate limiting --------------------------------------------------
        max_rpm = config.get("max_requests_per_minute", 0)
        if max_rpm > 0:
            self._check_rate_limit(max_rpm)

        # -- Required field validation --------------------------------------
        missing = REQUIRED_FIELDS - payload.keys()
        if missing:
            raise ValueError(
                f"Missing required webhook fields: {', '.join(sorted(missing))}"
            )

        title = payload["title"]
        content = payload["content"]
        source_url = payload["source_url"]

        # -- HMAC signature verification ------------------------------------
        secret = config.get("secret", "")
        if secret:
            signature = payload.get("signature") or config.get("signature") or ""
            if not signature:
                raise ValueError(
                    "HMAC secret configured but no signature provided"
                )
            self._verify_hmac(secret, payload, signature)

        # -- Build and return Item ------------------------------------------
        item_id = _make_item_id(source_url, title)

        return Item(
            id=item_id,
            source_name=self.source_name,
            source_type="webhook",
            source_url=source_url,
            title=title,
            content=content,
            content_type="text",
            raw_data={
                k: v for k, v in payload.items() if k not in REQUIRED_FIELDS
            },
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_rate_limit(self, max_rpm: int) -> None:
        """Enforce a simple in-memory sliding-window rate limit.

        Raises ``ValueError`` if the limit is exceeded.
        """
        now = time.time()
        window = 60.0  # 1 minute

        # Prune timestamps older than the window
        while (
            self._request_timestamps
            and self._request_timestamps[0] < now - window
        ):
            self._request_timestamps.popleft()

        if len(self._request_timestamps) >= max_rpm:
            raise ValueError(
                f"Rate limit exceeded: {max_rpm} requests per minute"
            )

        self._request_timestamps.append(now)

    @staticmethod
    def _verify_hmac(
        secret: str,
        payload: dict[str, Any],
        signature: str,
    ) -> None:
        """Verify an HMAC-SHA256 signature against the payload body.

        The expected signature format is the hex-encoded HMAC-SHA256
        digest, optionally prefixed with ``sha256=`` (the
        ``X-Hub-Signature-256`` header format used by GitHub & friends).

        Parameters
        ----------
        secret : str
            The shared HMAC secret.
        payload : dict
            The full payload dict (serialised to JSON for verification).
        signature : str
            The signature value to verify (with or without ``sha256=``
            prefix).

        Raises
        ------
        ValueError
            If the signature does not match.
        """
        # Exclude the signature key from the payload before computing
        # the HMAC — this matches real-world webhook behaviour where
        # the signature is computed on the raw request body (which does
        # not include the signature header).
        body_dict = {k: v for k, v in payload.items() if k != "signature"}
        body = json.dumps(body_dict, sort_keys=True, separators=(",", ":"))

        expected = hmac.new(
            secret.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        # Strip optional "sha256=" prefix
        provided = signature.removeprefix("sha256=")

        if not hmac.compare_digest(expected, provided):
            raise ValueError("HMAC signature mismatch")


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _make_item_id(source_url: str, title: str) -> str:
    """Produce a stable item identifier from source URL and title."""
    raw = f"{source_url}::{title}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
