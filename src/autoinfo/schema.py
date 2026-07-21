"""Database schema versioning and migration framework.

Provides a lightweight, forward-only migration system for AutoInfo's
SQLite knowledge base index.

Usage::

    from autoinfo.schema import check_schema, SCHEMA_VERSION

    conn = sqlite3.connect("autoinfo.db")
    check_schema(conn)  # auto-migrates to SCHEMA_VERSION
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

SCHEMA_VERSION = 1

# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class SchemaVersionError(Exception):
    """Raised when the database schema version is incompatible.

    This can happen when:
    * The code expects a newer schema than the database has (auto-migrate
      should normally handle this, but may fail if a migration is missing).
    * The database has a *newer* schema than the code understands
      (indicating the user downgraded autoinfo or ran a newer version
      before).
    * A downgrade was explicitly attempted.
    """


# ---------------------------------------------------------------------------
# Schema version table management
# ---------------------------------------------------------------------------


def ensure_schema_version_table(conn: sqlite3.Connection) -> None:
    """Create the ``_schema_version`` table if it does not exist.

    The table records every migration that has been applied::

        _schema_version (
            version     INTEGER  NOT NULL,
            applied_at  TEXT     NOT NULL,
            description TEXT     NOT NULL DEFAULT ''
        )
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS _schema_version (
            version     INTEGER NOT NULL,
            applied_at  TEXT    NOT NULL,
            description TEXT    NOT NULL DEFAULT ''
        )
    """)


def get_schema_version(conn: sqlite3.Connection) -> int:
    """Return the current schema version of the database.

    Returns ``0`` if the ``_schema_version`` table is missing or empty
    (fresh / legacy database).
    """
    ensure_schema_version_table(conn)
    row = conn.execute("SELECT MAX(version) FROM _schema_version").fetchone()
    return row[0] if row and row[0] is not None else 0


# ---------------------------------------------------------------------------
# Migration functions (named _migrate_v{N}, called in order)
# ---------------------------------------------------------------------------


def _migrate_v1(conn: sqlite3.Connection) -> None:
    """Initial schema: create the _schema_version table.

    This is the baseline migration.  Existing databases that were created
    before schema versioning was introduced will pass through this
    migration with no side effects because ``ensure_schema_version_table``
    is idempotent.
    """
    ensure_schema_version_table(conn)


# Registry: version → migration function
_MIGRATIONS: dict[int, Any] = {
    1: _migrate_v1,
}


# ---------------------------------------------------------------------------
# Apply & check
# ---------------------------------------------------------------------------


def apply_migrations(conn: sqlite3.Connection, target_version: int) -> None:
    """Run migration functions sequentially from current → *target_version*.

    Parameters
    ----------
    conn:
        Open SQLite connection.
    target_version:
        Target schema version to migrate to.

    Raises
    ------
    SchemaVersionError
        If *target_version* < current version (downgrade not supported),
        or if a migration function for an intermediate version is missing.
    """
    current = get_schema_version(conn)

    if target_version < current:
        raise SchemaVersionError(
            f"Schema downgrade is not supported: "
            f"current={current}, target={target_version}"
        )

    for v in range(current + 1, target_version + 1):
        migrator = _MIGRATIONS.get(v)
        if migrator is None:
            raise SchemaVersionError(
                f"No migration function found for version {v}. "
                f"Available versions: {sorted(_MIGRATIONS)}"
            )
        migrator(conn)
        conn.execute(
            "INSERT INTO _schema_version (version, applied_at, description) "
            "VALUES (?, ?, ?)",
            (
                v,
                datetime.now(timezone.utc).isoformat(),
                (migrator.__doc__ or "").strip() or f"Migration to v{v}",
            ),
        )
        conn.commit()


def check_schema(conn: sqlite3.Connection) -> None:
    """Check the database schema version and auto-migrate if needed.

    * If the database is at an older version than ``SCHEMA_VERSION``,
      ``apply_migrations`` is called to upgrade it.
    * If the database is at a *newer* version than ``SCHEMA_VERSION``,
      :class:`SchemaVersionError` is raised — the code is too old for
      this database.

    Parameters
    ----------
    conn:
        Open SQLite connection.

    Raises
    ------
    SchemaVersionError
        If the database schema is newer than the code, or if auto-migration
        fails (e.g. a missing migration function).
    """
    current = get_schema_version(conn)

    if current < SCHEMA_VERSION:
        apply_migrations(conn, SCHEMA_VERSION)
    elif current > SCHEMA_VERSION:
        raise SchemaVersionError(
            f"Database schema is newer than the installed code: "
            f"db={current}, code={SCHEMA_VERSION}. "
            "Please upgrade autoinfo."
        )
