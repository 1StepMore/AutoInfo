"""Agent callback system — new push-based agent subscription.

NOT shared with the existing ``set_domain_webhooks`` system.
Events fire when products are generated: ``new_digest``, ``new_report``,
``new_tutorial``.  Agents subscribe via ``register_agent_callback`` and
receive HTTP POST notifications when matching products are created.

Usage::

    cid = register_agent_callback("https://agent.example.com/hook",
                                  ["new_digest", "new_report"])
    await notify_agent("new_digest", {"title": "Weekly Digest", ...})
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory callback storage
# ---------------------------------------------------------------------------

_callbacks: dict[str, dict[str, Any]] = {}

_VALID_EVENTS = {"new_digest", "new_report", "new_tutorial"}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def register_agent_callback(agent_url: str, events: list[str]) -> str:
    """Register a new agent callback URL for specified events.

    Args:
        agent_url: Callback URL (must start with ``http://`` or ``https://``).
        events: List of event names from {new_digest, new_report, new_tutorial}.

    Returns:
        A short callback ID string (8-char UUID prefix).

    Raises:
        ValueError: If *agent_url* is invalid or *events* contains unknown names.
    """
    if not agent_url.startswith(("http://", "https://")):
        raise ValueError(
            f"Invalid agent_url: must start with http:// or https://, "
            f"got {agent_url!r}"
        )

    invalid = [e for e in events if e not in _VALID_EVENTS]
    if invalid:
        raise ValueError(
            f"Invalid events: {invalid}. Valid events: {sorted(_VALID_EVENTS)}"
        )

    callback_id = str(uuid.uuid4())[:8]
    _callbacks[callback_id] = {
        "callback_id": callback_id,
        "agent_url": agent_url,
        "events": list(events),
    }
    logger.info(
        "Registered agent callback %s for %s (events: %s)",
        callback_id, agent_url, events,
    )
    return callback_id


def list_agent_callbacks() -> list[dict[str, Any]]:
    """Return all registered agent callbacks as a list of dicts."""
    return list(_callbacks.values())


def remove_agent_callback(callback_id: str) -> bool:
    """Remove a registered callback.

    Returns:
        ``True`` if the callback was found and removed, ``False`` otherwise.
    """
    if callback_id in _callbacks:
        del _callbacks[callback_id]
        logger.info("Removed agent callback %s", callback_id)
        return True
    return False


async def notify_agent(event: str, payload: dict[str, Any]) -> None:
    """POST a JSON payload to every agent URL registered for *event*.

    Fire-and-forget — individual failures are logged but do not propagate.
    Simple POST only; no retry / backoff.

    Args:
        event: One of ``new_digest``, ``new_report``, ``new_tutorial``.
        payload: Arbitrary JSON-serialisable dict to POST.
    """
    if event not in _VALID_EVENTS:
        logger.warning("Unknown event %r — skipping notification", event)
        return

    targets = [cb for cb in _callbacks.values() if event in cb["events"]]
    if not targets:
        return

    async with httpx.AsyncClient(timeout=10.0) as client:
        for cb in targets:
            try:
                resp = await client.post(
                    cb["agent_url"],
                    json={"event": event, "payload": payload},
                    headers={"Content-Type": "application/json"},
                )
                resp.raise_for_status()
                logger.info(
                    "Notified agent %s for event %s: HTTP %s",
                    cb["callback_id"], event, resp.status_code,
                )
            except Exception:
                logger.warning(
                    "Failed to notify agent %s at %s",
                    cb["callback_id"], cb["agent_url"],
                    exc_info=True,
                )
