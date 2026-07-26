"""SQLite-backed storage for UserProfile and Subscription.

Tables are created lazily on first access.  All public functions call
:func:`init_db` before any operation so the caller never needs to
worry about schema bootstrapping.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from autoinfo.models import Subscription, UserProfile

logger = logging.getLogger(__name__)

_DB_PATH: Path | None = None


def _get_db_path() -> Path:
    global _DB_PATH
    if _DB_PATH is None:
        _DB_PATH = Path.cwd() / ".autoinfo" / "users.db"
    return _DB_PATH


def _connect() -> sqlite3.Connection:
    db_path = _get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ---------------------------------------------------------------------------
# Schema bootstrap
# ---------------------------------------------------------------------------


def init_db() -> None:
    """Create tables if they do not already exist.

    Idempotent — safe to call on every request.
    """
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id        TEXT PRIMARY KEY,
                name           TEXT NOT NULL,
                email          TEXT DEFAULT '',
                delivery_prefs TEXT DEFAULT '{}',
                status         TEXT DEFAULT 'trial',
                tier           TEXT DEFAULT 'free',
                created_at     TEXT DEFAULT '',
                updated_at     TEXT DEFAULT '',
                trial_start    TEXT DEFAULT '',
                trial_end      TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS subscriptions (
                sub_id     TEXT PRIMARY KEY,
                user_id    TEXT NOT NULL,
                product_id TEXT DEFAULT '',
                status     TEXT DEFAULT 'active',
                start_date TEXT DEFAULT '',
                end_date   TEXT DEFAULT '',
                auto_renew INTEGER DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES user_profiles(user_id)
            );
        """)


# ---------------------------------------------------------------------------
# Row → model helpers
# ---------------------------------------------------------------------------


def _row_to_profile(row: sqlite3.Row) -> UserProfile:
    data = dict(row)
    raw_prefs = data.get("delivery_prefs", "{}")
    try:
        data["delivery_prefs"] = json.loads(raw_prefs) if isinstance(raw_prefs, str) else raw_prefs
    except (json.JSONDecodeError, TypeError):
        data["delivery_prefs"] = {}
    return UserProfile(**data)


def _row_to_subscription(row: sqlite3.Row) -> Subscription:
    data = dict(row)
    data["auto_renew"] = bool(data.get("auto_renew", True))
    return Subscription(**data)


# ---------------------------------------------------------------------------
# UserProfile CRUD
# ---------------------------------------------------------------------------


def create_profile(
    user_id: str,
    name: str,
    email: str = "",
    delivery_prefs: dict[str, Any] | None = None,
    status: str = "trial",
    tier: str = "free",
) -> UserProfile:
    """Insert a new user profile.

    When *status* is ``"trial"``, ``trial_start`` is set to now and
    ``trial_end`` is set to 14 days later.

    Raises :class:`sqlite3.IntegrityError` if *user_id* already exists.
    """
    init_db()
    now = datetime.now(timezone.utc).isoformat()
    from datetime import timedelta
    trial_start = now if status == "trial" else ""
    trial_end = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat() if status == "trial" else ""
    profile = UserProfile(
        user_id=user_id,
        name=name,
        email=email,
        delivery_prefs=delivery_prefs or {},
        status=status,
        tier=tier,
        created_at=now,
        updated_at=now,
        trial_start=trial_start,
        trial_end=trial_end,
    )
    with _connect() as conn:
        conn.execute(
            """INSERT INTO user_profiles
               (user_id, name, email, delivery_prefs, status, tier, created_at, updated_at, trial_start, trial_end)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                profile.user_id,
                profile.name,
                profile.email,
                json.dumps(profile.delivery_prefs),
                profile.status,
                profile.tier,
                profile.created_at,
                profile.updated_at,
                profile.trial_start,
                profile.trial_end,
            ),
        )
    return profile


def get_profile(user_id: str) -> UserProfile | None:
    """Return a user profile by *user_id*, or ``None``."""
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM user_profiles WHERE user_id = ?", (user_id,)
        ).fetchone()
    return _row_to_profile(row) if row is not None else None


def update_profile(
    user_id: str,
    name: str | None = None,
    email: str | None = None,
    delivery_prefs: dict[str, Any] | None = None,
    status: str | None = None,
    tier: str | None = None,
) -> UserProfile | None:
    """Update fields on an existing user profile.

    Only the provided fields are changed.  Returns the updated profile,
    or ``None`` if *user_id* does not exist.
    """
    init_db()
    existing = get_profile(user_id)
    if existing is None:
        return None

    now = datetime.now(timezone.utc).isoformat()
    new_name = name if name is not None else existing.name
    new_email = email if email is not None else existing.email
    new_prefs = delivery_prefs if delivery_prefs is not None else existing.delivery_prefs
    new_status = status if status is not None else existing.status
    new_tier = tier if tier is not None else existing.tier

    with _connect() as conn:
        conn.execute(
            """UPDATE user_profiles
               SET name=?, email=?, delivery_prefs=?, status=?, tier=?, updated_at=?
               WHERE user_id=?""",
            (
                new_name,
                new_email,
                json.dumps(new_prefs),
                new_status,
                new_tier,
                now,
                user_id,
            ),
        )

    # Return fresh data
    return get_profile(user_id)


def delete_profile(user_id: str) -> bool:
    """Delete a user profile by *user_id*.

    Also deletes associated subscriptions (CASCADE emulated via explicit
    delete).  Returns ``True`` if a row was removed.
    """
    init_db()
    with _connect() as conn:
        conn.execute("DELETE FROM subscriptions WHERE user_id = ?", (user_id,))
        cursor = conn.execute("DELETE FROM user_profiles WHERE user_id = ?", (user_id,))
        return cursor.rowcount > 0


def list_profiles() -> list[UserProfile]:
    """Return all user profiles ordered by creation date (newest first)."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM user_profiles ORDER BY created_at DESC"
        ).fetchall()
    return [_row_to_profile(r) for r in rows]


# ---------------------------------------------------------------------------
# Subscription CRUD (basic — expanded in later phases)
# ---------------------------------------------------------------------------


def create_subscription(
    user_id: str,
    product_id: str = "",
    status: str = "active",
    start_date: str = "",
    end_date: str = "",
    auto_renew: bool = True,
) -> Subscription:
    """Create a new subscription for a user."""
    init_db()
    import uuid

    sub = Subscription(
        sub_id=str(uuid.uuid4()),
        user_id=user_id,
        product_id=product_id,
        status=status,
        start_date=start_date or datetime.now(timezone.utc).isoformat(),
        end_date=end_date,
        auto_renew=auto_renew,
    )
    with _connect() as conn:
        conn.execute(
            """INSERT INTO subscriptions
               (sub_id, user_id, product_id, status, start_date, end_date, auto_renew)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                sub.sub_id,
                sub.user_id,
                sub.product_id,
                sub.status,
                sub.start_date,
                sub.end_date,
                int(sub.auto_renew),
            ),
        )
    return sub


def list_subscriptions(user_id: str | None = None) -> list[Subscription]:
    """List subscriptions, optionally filtered by *user_id*."""
    init_db()
    with _connect() as conn:
        if user_id:
            rows = conn.execute(
                "SELECT * FROM subscriptions WHERE user_id = ? ORDER BY start_date DESC",
                (user_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM subscriptions ORDER BY start_date DESC"
            ).fetchall()
    return [_row_to_subscription(r) for r in rows]


# ---------------------------------------------------------------------------
# F38 — End User Lifecycle State Machine
# ---------------------------------------------------------------------------

_VALID_TRANSITIONS: dict[str, list[str]] = {
    "trial": ["active", "cancelled"],
    "active": ["suspended", "cancelled"],
    "suspended": ["active", "cancelled"],
    "cancelled": [],
}
"""Valid status transitions for the end-user lifecycle.

Diagram::

    trial ──→ active ⇄ suspended
       │          │         │
       └─→ cancelled ←────┘
"""


def transition_end_user(
    user_id: str,
    new_status: str,
) -> dict[str, Any]:
    """Transition an end-user's status with lifecycle validation.

    Valid transitions (per :data:`_VALID_TRANSITIONS`):

    - ``trial → active``, ``trial → cancelled``
    - ``active → suspended``, ``active → cancelled``
    - ``suspended → active``, ``suspended → cancelled``
    - ``cancelled →`` *(none — terminal state)*

    Each transition is logged to the immutable audit log via
    :func:`autoinfo.audit.append_audit_log`.

    Parameters
    ----------
    user_id:
        The end-user to transition.
    new_status:
        Target status.

    Returns
    -------
    dict
        ``{success, user_id, from_status, to_status, trial_start, trial_end}``
        on success, or an error dict with ``error_code`` and ``message``.
    """
    init_db()
    profile = get_profile(user_id)
    if profile is None:
        return {
            "error_code": "NotFound",
            "message": f"End-user '{user_id}' not found",
            "actionable": True,
        }

    old_status = profile.status

    if old_status == new_status:
        return {
            "error_code": "NoOp",
            "message": f"End-user '{user_id}' already has status '{new_status}'",
            "actionable": True,
        }

    allowed = _VALID_TRANSITIONS.get(old_status, [])
    if new_status not in allowed:
        terminal = "(none — terminal state)" if not allowed else ", ".join(allowed)
        return {
            "error_code": "InvalidTransition",
            "message": (
                f"Cannot transition end-user '{user_id}' from "
                f"'{old_status}' to '{new_status}'. "
                f"Valid transitions from '{old_status}': {terminal}"
            ),
            "actionable": True,
        }

    now = datetime.now(timezone.utc).isoformat()
    trial_start = profile.trial_start or ""
    trial_end = profile.trial_end or ""

    if old_status == "trial" and new_status == "active" and not trial_end:
        trial_end = now

    with _connect() as conn:
        conn.execute(
            "UPDATE user_profiles SET status=?, updated_at=?, trial_end=? WHERE user_id=?",
            (new_status, now, trial_end, user_id),
        )

    try:
        from autoinfo.audit import append_audit_log

        append_audit_log(
            actor="system",
            action="transition_end_user",
            resource_type="user_profile",
            resource_id=user_id,
            details={
                "from_status": old_status,
                "to_status": new_status,
                "tier": profile.tier,
            },
        )
    except Exception:
        logger.warning(
            "Failed to write audit log for user '%s' transition %s → %s",
            user_id,
            old_status,
            new_status,
            exc_info=True,
        )

    return {
        "success": True,
        "user_id": user_id,
        "from_status": old_status,
        "to_status": new_status,
        "trial_start": trial_start,
        "trial_end": trial_end,
    }
