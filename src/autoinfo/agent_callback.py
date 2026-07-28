"""Agent callback system — push-based agent subscription, persisted in SQLite.

NOT shared with the existing ``set_domain_webhooks`` system.
Events fire when products are generated: ``new_digest``, ``new_report``,
``new_tutorial``.  Agents subscribe via ``register_agent_callback`` and
receive HTTP POST notifications when matching products are created.

Callbacks survive MCP server restarts because they are stored in the
same ``autoinfo.db`` SQLite database used by the KB pipeline (shared
connection pattern, ``CREATE TABLE IF NOT EXISTS``).

Usage::

    cid = register_agent_callback("https://agent.example.com/hook",
                                  ["new_digest", "new_report"])
    await notify_agent("new_digest", {"title": "Weekly Digest", ...})
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SQLite table DDL
# ---------------------------------------------------------------------------

_AGENT_CALLBACK_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS agent_callbacks (
    callback_id TEXT PRIMARY KEY,
    agent_url   TEXT NOT NULL,
    events      TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
"""

_VALID_EVENTS = {"new_digest", "new_report", "new_tutorial"}


# ---------------------------------------------------------------------------
# Connection helpers (same pattern as delivery_log.py / SQLiteIndex)
# ---------------------------------------------------------------------------


def _default_db_path() -> Path:
    """Return the default path to ``autoinfo.db`` in CWD."""
    return Path.cwd() / "autoinfo.db"


def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    """Open a connection to the shared SQLite database.

    Creates the ``agent_callbacks`` table on first connection (idempotent).
    Uses WAL journal mode for better concurrency with the KB pipeline.
    """
    resolved = db_path or _default_db_path()
    conn = sqlite3.connect(str(resolved))
    conn.row_factory = sqlite3.Row
    _ = conn.execute("PRAGMA journal_mode=WAL")
    _ = conn.execute("PRAGMA synchronous=NORMAL")
    _ = conn.executescript(_AGENT_CALLBACK_TABLE_DDL)
    return conn


def _now_utc() -> str:
    """Return ISO-8601 UTC timestamp string."""
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """Convert a SQLite Row to the dict shape expected by callers."""
    return {
        "callback_id": row["callback_id"],
        "agent_url": row["agent_url"],
        "events": json.loads(row["events"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def register_agent_callback(agent_url: str, events: list[str]) -> str:
    """Register a new agent callback URL for specified events.

    Persisted to SQLite so callbacks survive server restarts.

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
            (
                f"Invalid agent_url: must start with http:// or https://, "
                f"got {agent_url!r}"
            )
        )

    invalid = [e for e in events if e not in _VALID_EVENTS]
    if invalid:
        raise ValueError(
            f"Invalid events: {invalid}. Valid events: {sorted(_VALID_EVENTS)}"
        )

    callback_id = str(uuid.uuid4())[:8]
    now = _now_utc()
    events_json = json.dumps(list(events))

    with _connect() as conn:
        _ = conn.execute(
            (
                "INSERT INTO agent_callbacks (callback_id, agent_url, events, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)"
            ),
            (callback_id, agent_url, events_json, now, now),
        )
        conn.commit()

    logger.info(
        "Registered agent callback %s for %s (events: %s)",
        callback_id, agent_url, events,
    )
    return callback_id


def list_agent_callbacks() -> list[dict[str, Any]]:
    """Return all registered agent callbacks as a list of dicts.

    Reads from SQLite so results reflect the persisted state.
    """
    with _connect() as conn:
        rows = conn.execute(
            (
                "SELECT callback_id, agent_url, events, created_at, updated_at "
                "FROM agent_callbacks ORDER BY created_at DESC"
            )
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def remove_agent_callback(callback_id: str) -> bool:
    """Remove a registered callback from the SQLite store.

    Returns:
        ``True`` if the callback was found and removed, ``False`` otherwise.
    """
    with _connect() as conn:
        cursor = conn.execute(
            "DELETE FROM agent_callbacks WHERE callback_id = ?",
            (callback_id,),
        )
        conn.commit()
        removed = cursor.rowcount > 0
    if removed:
        logger.info("Removed agent callback %s", callback_id)
    return removed


async def notify_agent(event: str, payload: dict[str, Any]) -> None:
    """POST a JSON payload to every agent URL registered for *event*.

    Fire-and-forget — individual failures are logged but do not propagate.
    Simple POST only; no retry / backoff.

    Reads target callbacks from SQLite.

    Args:
        event: One of ``new_digest``, ``new_report``, ``new_tutorial``.
        payload: Arbitrary JSON-serialisable dict to POST.
    """
    if event not in _VALID_EVENTS:
        logger.warning("Unknown event %r — skipping notification", event)
        return

    with _connect() as conn:
        rows = conn.execute(
            (
                "SELECT callback_id, agent_url, events "
                "FROM agent_callbacks"
            )
        ).fetchall()

    # Filter in Python — SQLite stores events as JSON text
    targets = [
        _row_to_dict(row)
        for row in rows
        if event in json.loads(row["events"])
    ]
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
                _ = resp.raise_for_status()
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
