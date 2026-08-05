"""Immutable audit log — append-only record of user-facing MCP operations.

Every call to :func:`append_audit_log` writes one immutable entry to the
``audit_log`` SQLite table.  No UPDATE or DELETE operations are exposed
(append-only semantics).  Once committed, an entry can never be altered.

Query via :func:`query_audit_log` with optional filters by actor, action,
resource_type, and time range.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from autoinfo.models import AuditLog

# ---------------------------------------------------------------------------
# Table DDL (append-only — no UPDATE/DELETE triggers, no soft-delete column)
# ---------------------------------------------------------------------------

_AUDIT_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS audit_log (
    log_id        TEXT PRIMARY KEY,
    timestamp     TEXT NOT NULL,
    actor         TEXT NOT NULL,
    action        TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id   TEXT NOT NULL DEFAULT '',
    details       TEXT NOT NULL DEFAULT '{}',
    ip_address    TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_audit_actor
    ON audit_log(actor);

CREATE INDEX IF NOT EXISTS idx_audit_action
    ON audit_log(action);

CREATE INDEX IF NOT EXISTS idx_audit_resource_type
    ON audit_log(resource_type);

CREATE INDEX IF NOT EXISTS idx_audit_timestamp
    ON audit_log(timestamp);
"""

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _default_db_path() -> Path:
    """Return the default path to ``autoinfo.db`` in CWD."""
    return Path.cwd() / "autoinfo.db"


def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    """Open a connection to the audit SQLite database.

    Creates the ``audit_log`` table on first connection (idempotent).
    """
    resolved = db_path or _default_db_path()
    conn = sqlite3.connect(str(resolved))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(_AUDIT_TABLE_DDL)
    return conn


def _now_utc() -> str:
    """Return ISO-8601 UTC timestamp string."""
    return datetime.now(timezone.utc).isoformat()


def _row_to_audit_log(row: sqlite3.Row) -> AuditLog:
    """Convert a SQLite row to an :class:`AuditLog` instance."""
    details_raw = row["details"] if row["details"] else "{}"
    try:
        details = json.loads(details_raw)
    except (json.JSONDecodeError, TypeError):
        details = {}
    return AuditLog(
        log_id=row["log_id"],
        timestamp=row["timestamp"],
        actor=row["actor"],
        action=row["action"],
        resource_type=row["resource_type"],
        resource_id=row["resource_id"],
        details=details,
        ip_address=row["ip_address"],
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def append_audit_log(
    actor: str,
    action: str,
    resource_type: str = "",
    resource_id: str = "",
    details: dict[str, Any] | None = None,
    ip_address: str = "",
    tool: str | None = None,
    db_path: Path | None = None,
) -> AuditLog:
    """Append one immutable entry to the audit log.

    Parameters
    ----------
    actor:
        Who performed the action.  Stable taxonomy ids:

        * ``"agent:<session>"`` — interactive MCP agent client
        * ``"cli"`` — command-line driven operation
        * ``"cron"`` — scheduled job
        * ``"system"`` — internal / server-originated operation
    action:
        What action was taken (e.g. ``"collect_sources"``,
        ``"create_kb_draft"``, ``"tool_call"``).
    resource_type:
        The kind of resource affected (e.g. ``"domain"``, ``"source"``,
        ``"kb_entry"``, ``"config"``, ``"mcp_tool"``).
    resource_id:
        Identifier of the affected resource (optional).  For dispatch-level
        entries this is a low-sensitivity identifier only (e.g. a domain or
        topic name) — never URLs, credentials, or free-form content.
    details:
        Arbitrary JSON-serialisable payload capturing additional context.
        Dispatch-level entries put only ``result_code`` and ``trace_id``
        here — never tool inputs or response data.
    ip_address:
        Originating IP address (optional).
    tool:
        MCP tool name for dispatch-level entries.  When given and
        *resource_type* is empty, the tool name is recorded in the
        ``resource_type`` column (the tool being invoked is the resource
        type of a tool call).  This keeps the schema append-only while
        letting callers pass either a broad category or a tool name.
    db_path:
        Path to the SQLite database.  Defaults to ``autoinfo.db`` in CWD.

    Returns
    -------
    AuditLog
        The entry that was written (reflects the committed row).

    Raises
    ------
    sqlite3.Error
        On any database error — callers should handle appropriately.
    """
    log_id = str(uuid.uuid4())
    timestamp = _now_utc()
    details_json = json.dumps(details or {}, ensure_ascii=False)
    effective_resource_type = resource_type or tool or ""

    conn = _connect(db_path)
    try:
        conn.execute(
            """INSERT INTO audit_log
               (log_id, timestamp, actor, action, resource_type, resource_id,
                details, ip_address)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                log_id,
                timestamp,
                actor,
                action,
                effective_resource_type,
                resource_id,
                details_json,
                ip_address,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return AuditLog(
        log_id=log_id,
        timestamp=timestamp,
        actor=actor,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details or {},
        ip_address=ip_address,
    )


def query_audit_log(
    actor: str | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 100,
    offset: int = 0,
    db_path: Path | None = None,
) -> list[AuditLog]:
    """Query the audit log with optional filters.

    All filters are **optional** — omit a filter to skip it.
    Filters are combined with AND logic.

    Parameters
    ----------
    actor:
        Only entries whose ``actor`` equals this value.
    action:
        Only entries whose ``action`` equals this value.
    resource_type:
        Only entries whose ``resource_type`` equals this value.
    date_from:
        Only entries with ``timestamp >=`` this ISO-8601 string.
    date_to:
        Only entries with ``timestamp <=`` this ISO-8601 string.
    limit:
        Maximum number of entries to return (default 100).
    offset:
        Pagination offset (default 0).
    db_path:
        Path to the SQLite database.  Defaults to ``autoinfo.db`` in CWD.

    Returns
    -------
    list[AuditLog]
        Matching entries ordered by **timestamp descending** (newest first).

    Raises
    ------
    sqlite3.Error
        On any database error.
    """
    clauses: list[str] = []
    params: list[Any] = []

    if actor:
        clauses.append("actor = ?")
        params.append(actor)
    if action:
        clauses.append("action = ?")
        params.append(action)
    if resource_type:
        clauses.append("resource_type = ?")
        params.append(resource_type)
    if date_from:
        clauses.append("timestamp >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("timestamp <= ?")
        params.append(date_to)

    where = ""
    if clauses:
        where = "WHERE " + " AND ".join(clauses)

    sql = f"SELECT * FROM audit_log {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    conn = _connect(db_path)
    try:
        rows = conn.execute(sql, params).fetchall()
        return [_row_to_audit_log(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Convenience: ensure the table exists (useful for CLI / init scripts)
# ---------------------------------------------------------------------------


def init_audit_table(db_path: Path | None = None) -> None:
    """Explicitly create the ``audit_log`` table and indexes.

    Idempotent — safe to call multiple times.  The table is also created
    lazily on first :func:`append_audit_log` or :func:`query_audit_log`.
    """
    conn = _connect(db_path)
    try:
        conn.executescript(_AUDIT_TABLE_DDL)
        conn.commit()
    finally:
        conn.close()
