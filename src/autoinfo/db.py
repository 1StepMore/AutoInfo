"""Unified SQLite connection factory for AutoInfo.

Every business connection to ``autoinfo.db`` (and the sibling stores) must go
through :func:`connect` so PRAGMA settings cannot drift between modules — a
connection without ``busy_timeout`` fails immediately with ``database is
locked`` under the same write contention that a sibling connection waits out
(issue #563).

``busy_timeout`` is set **before** any journal-mode handling: ``PRAGMA
journal_mode=WAL`` takes a brief EXCLUSIVE lock and SQLite does not run the
busy handler for it, so the timeout must already be in place (issue #387).
"""

from __future__ import annotations

import os
import sqlite3
import time

_DEFAULT_BUSY_TIMEOUT_MS = 30000
_BUSY_TIMEOUT_ENV = "AUTOINFO_DB_BUSY_TIMEOUT_MS"

# A brand-new database can be created by several connections at once; only one
# wins the WAL conversion. A short bounded retry covers that first-writer race
# (the budget agent_callback established for issue #387).
_JOURNAL_MODE_ATTEMPTS = 20
_JOURNAL_MODE_RETRY_S = 0.01

def busy_timeout_ms() -> int:
    """Return the SQLite ``busy_timeout`` (ms) for AutoInfo connections.

    Parallel workers write to the same SQLite DB; under external-writer
    contention a write can raise ``OperationalError: database is locked``.  A
    generous busy timeout makes a connection wait for the lock instead of
    failing immediately.  Configurable via ``AUTOINFO_DB_BUSY_TIMEOUT_MS``
    (default 30000); unparsable values fall back to the default.
    """
    raw = os.environ.get(_BUSY_TIMEOUT_ENV)
    if raw is None:
        return _DEFAULT_BUSY_TIMEOUT_MS
    try:
        return int(raw)
    except (TypeError, ValueError):
        return _DEFAULT_BUSY_TIMEOUT_MS


def _ensure_wal(conn: sqlite3.Connection, *, readonly: bool) -> None:
    """Leave *conn* on WAL, converting only when necessary (#387).

    ``PRAGMA journal_mode=WAL`` needs an EXCLUSIVE lock and bypasses the busy
    handler, so re-issuing it on an already-WAL database is what dropped
    outbox rows under concurrency.  A read-only connection cannot convert at
    all, so it only reads the current mode.
    """
    mode = str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()
    if mode == "wal" or readonly:
        return
    for attempt in range(_JOURNAL_MODE_ATTEMPTS):
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            return
        except sqlite3.OperationalError:
            if attempt == _JOURNAL_MODE_ATTEMPTS - 1:
                raise
            time.sleep(_JOURNAL_MODE_RETRY_S)


def connect(
    db_path: str | os.PathLike[str],
    *,
    readonly: bool = False,
    foreign_keys: bool = False,
) -> sqlite3.Connection:
    """Open a SQLite connection with AutoInfo's standard PRAGMAs.

    ``row_factory=Row``, WAL journaling, ``synchronous=NORMAL`` and
    ``busy_timeout`` (see :func:`busy_timeout_ms`) are applied to every
    connection.  ``readonly`` opens ``mode=ro`` (reads only; writes raise
    ``sqlite3.OperationalError``).  ``foreign_keys`` enables FK enforcement.
    """
    path = os.fspath(db_path)
    if readonly:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    else:
        conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    # busy_timeout FIRST — it must cover every later statement, including the
    # journal-mode transition (issue #387).
    conn.execute(f"PRAGMA busy_timeout={busy_timeout_ms()}")
    if foreign_keys:
        conn.execute("PRAGMA foreign_keys=ON")
    _ensure_wal(conn, readonly=readonly)
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn
