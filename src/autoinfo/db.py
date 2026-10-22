"""Unified SQLite connection factory for AutoInfo.

Every business connection to ``autoinfo.db`` (and the sibling stores) must go
through :func:`connect` so PRAGMA settings cannot drift between modules — a
connection without ``busy_timeout`` fails immediately with ``database is
locked`` under the same write contention that a sibling connection waits out
(issue #563).

``busy_timeout`` is set **before** any journal-mode handling: ``PRAGMA
journal_mode=WAL`` takes a brief EXCLUSIVE lock and SQLite does not run the
busy handler for it, so the timeout must already be in place (issue #387).

The **first** WAL conversion is not a business-connection concern (issue #571):
:func:`ensure_initialized` owns it, serialised by a process-wide per-path lock,
and :func:`connect` only *reads* the current journal mode afterwards. Once a
database is in WAL, no connection ever issues ``PRAGMA journal_mode=WAL``
again — that statement is what raised ``database is locked`` under the
16-thread first-writer race recorded in ``tests/TRIAGE.md``.
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time

_DEFAULT_BUSY_TIMEOUT_MS = 30000
_BUSY_TIMEOUT_ENV = "AUTOINFO_DB_BUSY_TIMEOUT_MS"

# A brand-new database can be created by several connections at once; only one
# wins the WAL conversion. The switch itself bypasses the SQLite busy handler,
# so the losers wait and retry rather than raising (issue #387). 30 x 100ms is
# the documented total budget (issue #571).
_JOURNAL_MODE_ATTEMPTS = 30
_JOURNAL_MODE_RETRY_S = 0.1

# One lock per database path, so threads in this process serialise the first
# conversion instead of racing on `PRAGMA journal_mode=WAL` (issue #571).
_INIT_LOCKS: dict[str, threading.Lock] = {}
_INIT_LOCKS_GUARD = threading.Lock()


class DatabaseInitializationError(sqlite3.OperationalError):
    """A non-WAL database could not be converted because a writer holds it.

    Subclasses :class:`sqlite3.OperationalError` so existing ``except
    OperationalError`` handlers keep working.
    """


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


def _is_memory(path: str) -> bool:
    return path == ":memory:" or path.startswith("file::memory:") or "mode=memory" in path


def _journal_mode(conn: sqlite3.Connection) -> str:
    return str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()


def _initialization_lock(path: str) -> threading.Lock:
    key = os.path.abspath(path)
    with _INIT_LOCKS_GUARD:
        lock = _INIT_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _INIT_LOCKS[key] = lock
        return lock


def ensure_initialized(db_path: str | os.PathLike[str]) -> None:
    """Convert *db_path* to WAL exactly once, serialised per path.

    Safe to call from many threads: the process-wide lock means one thread
    converts and the rest observe WAL on entry. Another process converting at
    the same time is handled by a bounded retry (30 x 100ms) rather than by
    the caller's ``busy_timeout``, because SQLite does not run the busy handler
    for ``PRAGMA journal_mode``. Raises
    :class:`DatabaseInitializationError` when the budget runs out.
    """
    path = os.fspath(db_path)
    if _is_memory(path):
        return
    with _initialization_lock(path):
        conn = sqlite3.connect(path)
        try:
            conn.execute(f"PRAGMA busy_timeout={busy_timeout_ms()}")
            if _journal_mode(conn) == "wal":
                return
            for attempt in range(_JOURNAL_MODE_ATTEMPTS):
                try:
                    conn.execute("PRAGMA journal_mode=WAL")
                    return
                except sqlite3.OperationalError as exc:
                    if attempt == _JOURNAL_MODE_ATTEMPTS - 1:
                        raise DatabaseInitializationError(
                            f"{path}: cannot enable WAL journal mode after "
                            f"{_JOURNAL_MODE_ATTEMPTS * _JOURNAL_MODE_RETRY_S:.1f}s — "
                            "another connection holds a write lock. Retry once "
                            "the writer finishes, or run `autoinfo init` before "
                            "starting concurrent workers."
                        ) from exc
                    time.sleep(_JOURNAL_MODE_RETRY_S)
        finally:
            conn.close()


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

    The first WAL switch is delegated to :func:`ensure_initialized`, so a
    business connection never races another one on ``PRAGMA journal_mode=WAL``
    (issue #571). A ``readonly`` connection cannot convert at all and keeps
    whatever mode the file already has.
    """
    path = os.fspath(db_path)
    for attempt in range(2):
        if readonly:
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        else:
            conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        # busy_timeout FIRST — it must cover every later statement, including
        # the journal-mode transition (issue #387).
        conn.execute(f"PRAGMA busy_timeout={busy_timeout_ms()}")
        if foreign_keys:
            conn.execute("PRAGMA foreign_keys=ON")
        if readonly or _is_memory(path) or _journal_mode(conn) == "wal":
            break
        # SQLite caches the journal mode per connection: a handle opened before
        # the conversion keeps using the rollback journal, so reopen after it.
        conn.close()
        ensure_initialized(path)
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn
