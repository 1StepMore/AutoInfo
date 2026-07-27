"""Consumption event tracking system.

SQLite-backed store for recording and querying consumption events
(delivered, opened, clicked) tied to users and products.

Database file is at ``.autoinfo/consumption.db`` in the project root.

Usage::

    from autoinfo.consumption import ConsumptionEvent, ConsumptionStore

    store = ConsumptionStore()
    store.record_event(
        user_id="user_abc",
        product_type="digest",
        product_id="medical-research-weekly",
        event_type="delivered",
    )
    events = store.list_events("user_abc", limit=10)
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)

_DB_PATH: Path | None = None


def _get_db_path() -> Path:
    global _DB_PATH
    if _DB_PATH is None:
        _DB_PATH = Path.cwd() / ".autoinfo" / "consumption.db"
    return _DB_PATH


def _connect() -> sqlite3.Connection:
    """Open a SQLite connection with WAL journal mode.

    Creates the parent directory if it does not already exist.
    """
    db_path = _get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass
class ConsumptionEvent:
    """A single consumption event (delivered, opened, clicked).

    Attributes
    ----------
    event_id:
        Auto-generated UUID on instantiation.
    user_id:
        Identity of the end user who received/interacted with the product.
    product_type:
        Product category (e.g. ``"digest"``, ``"report"``).
    product_id:
        Product identifier (e.g. ``"medical-research-weekly"``).
    event_type:
        Type of consumption action.  One of ``"delivered"`` (product was
        generated/sent), ``"opened"`` (user accessed the product),
        ``"clicked"`` (user interacted with a link/CTA inside the product).
    timestamp:
        ISO-8601 timestamp.  Auto-set to ``now`` when left empty.
    metadata:
        Arbitrary key/value payload attached to the event (domain, period,
        format, entry count, etc.).
    """

    user_id: str = ""
    product_type: str = ""
    product_id: str = ""
    event_type: Literal["delivered", "opened", "clicked"] = "delivered"
    timestamp: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    event_id: str = ""

    def __post_init__(self) -> None:
        if not self.event_id:
            self.event_id = str(uuid.uuid4())
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConsumptionEvent:
        """Create a :class:`ConsumptionEvent` from a dict.

        Unknown keys are silently ignored.  Missing optional fields are
        filled with their declared defaults.
        """
        valid_fields = set(cls.__dataclass_fields__.keys())
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)


# ---------------------------------------------------------------------------
# Row → dict helper
# ---------------------------------------------------------------------------


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """Convert a SQLite Row to a plain dict with parsed metadata."""
    data = dict(row)
    raw_meta = data.get("metadata", "{}")
    if isinstance(raw_meta, str):
        try:
            data["metadata"] = json.loads(raw_meta)
        except (json.JSONDecodeError, TypeError):
            data["metadata"] = {}
    return data


# ---------------------------------------------------------------------------
# ConsumptionStore
# ---------------------------------------------------------------------------


class ConsumptionStore:
    """SQLite-backed store for consumption events.

    The database file is created lazily at ``.autoinfo/consumption.db``
    on first use.  The schema is bootstrapped automatically — callers
    never need to worry about initialization.

    Usage::

        store = ConsumptionStore()
        store.record_event(
            user_id="user_abc",
            product_type="digest",
            product_id="medical-research-weekly",
            event_type="delivered",
        )
        events = store.list_events("user_abc")
    """

    def __init__(self) -> None:
        self._init_db()

    # ------------------------------------------------------------------
    # Schema bootstrap
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        """Create the ``consumption_events`` table if it does not exist.

        Idempotent — safe to call on every instantiation.
        """
        with _connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS consumption_events (
                    id          TEXT PRIMARY KEY,
                    user_id     TEXT NOT NULL,
                    product_type TEXT NOT NULL,
                    product_id  TEXT NOT NULL,
                    event_type  TEXT NOT NULL,
                    timestamp   TEXT NOT NULL,
                    metadata    TEXT DEFAULT '{}'
                );
            """)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def record_event(
        self,
        event: ConsumptionEvent | None = None,
        *,
        user_id: str = "",
        product_type: str = "",
        product_id: str = "",
        event_type: str = "delivered",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Persist a consumption event and return a success indicator.

        Two calling conventions are supported:

        1. Pass a :class:`ConsumptionEvent` object as the first positional
           argument::

               store.record_event(my_event)

        2. Pass individual keyword arguments (a :class:`ConsumptionEvent`
           is constructed internally)::

               store.record_event(
                   user_id="user_abc",
                   product_type="digest",
                   event_type="delivered",
               )

        Parameters
        ----------
        event:
            Optional :class:`ConsumptionEvent` instance.  When ``None``,
            the keyword arguments are used to construct one.
        user_id:
            End-user identity (only used when *event* is ``None``).
        product_type:
            Product category, e.g. ``"digest"`` or ``"report"``.
        product_id:
            Product identifier string.
        event_type:
            One of ``"delivered"``, ``"opened"``, ``"clicked"``.
        metadata:
            Arbitrary key/value payload serialized as JSON.

        Returns
        -------
        dict
            ``{"success": True, "event_id": "<uuid>"}``.
        """
        if event is None:
            event = ConsumptionEvent(
                user_id=user_id,
                product_type=product_type,
                product_id=product_id,
                event_type=event_type,  # type: ignore[arg-type]
                metadata=metadata or {},
            )

        with _connect() as conn:
            conn.execute(
                """INSERT INTO consumption_events
                   (id, user_id, product_type, product_id,
                    event_type, timestamp, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    event.event_id,
                    event.user_id,
                    event.product_type,
                    event.product_id,
                    event.event_type,
                    event.timestamp,
                    json.dumps(event.metadata),
                ),
            )

        logger.debug(
            "Recorded consumption event '%s' for user '%s' (%s/%s)",
            event.event_id,
            event.user_id,
            event.product_type,
            event.event_type,
        )
        return {"success": True, "event_id": event.event_id}

    def list_events(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Return consumption events for a specific user.

        Events are ordered by timestamp descending (newest first).

        Parameters
        ----------
        user_id:
            End-user identity to filter by.
        limit:
            Maximum number of events to return (default 50).
        offset:
            Number of events to skip (for pagination).

        Returns
        -------
        list[dict]
            Each dict has keys: ``id``, ``user_id``, ``product_type``,
            ``product_id``, ``event_type``, ``timestamp``, ``metadata``
            (parsed as a dict).
        """
        with _connect() as conn:
            rows = conn.execute(
                """SELECT * FROM consumption_events
                   WHERE user_id = ?
                   ORDER BY timestamp DESC
                   LIMIT ? OFFSET ?""",
                (user_id, limit, offset),
            ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def list_all_events(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Return consumption events across all users.

        Events are ordered by timestamp descending (newest first).

        Parameters
        ----------
        limit:
            Maximum number of events to return (default 50).
        offset:
            Number of events to skip (for pagination).

        Returns
        -------
        list[dict]
            Each dict has keys: ``id``, ``user_id``, ``product_type``,
            ``product_id``, ``event_type``, ``timestamp``, ``metadata``
            (parsed as a dict).
        """
        with _connect() as conn:
            rows = conn.execute(
                """SELECT * FROM consumption_events
                   ORDER BY timestamp DESC
                   LIMIT ? OFFSET ?""",
                (limit, offset),
            ).fetchall()
        return [_row_to_dict(r) for r in rows]
