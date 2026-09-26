"""#387: the WAL journal-mode conversion must not run on every connection.

``PRAGMA journal_mode=WAL`` needs a brief EXCLUSIVE lock and SQLite does not
run the busy handler for it, so ``busy_timeout`` does not cover it. With many
threads opening a fresh database, the losers raised
``OperationalError: database is locked``, which
``enqueue_agent_notification`` swallows into a return of 0 — a silently dropped
outbox row.

``scripts/repro_outbox_lock.py`` demonstrates the failure probabilistically
(8 drops per 2400 writes before the fix, 0 after). These tests lock the
*mechanism* deterministically instead, so the guard cannot be removed and pass
by luck: a database already in WAL must not be converted again, and a fresh
one must still be converted.

The test that motivated this is probabilistic
(``test_concurrent_outbox_writes_no_lost_events``), so on its own it cannot
prove the fix; these assertions can.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from autoinfo import agent_callback as ac


class _RecordingConnection(sqlite3.Connection):
    """Connection that records every statement executed against it."""

    executed: list[str] = []

    def execute(self, sql: str, *args: object) -> sqlite3.Cursor:  # type: ignore[override]
        type(self).executed.append(sql)
        return super().execute(sql, *args)  # type: ignore[arg-type]


@pytest.fixture
def recording_connect(monkeypatch: pytest.MonkeyPatch) -> type[_RecordingConnection]:
    """Route every ``sqlite3.connect`` in the module through the recorder."""
    _RecordingConnection.executed = []
    real_connect = sqlite3.connect

    def _factory(*args: object, **kwargs: object) -> sqlite3.Connection:
        kwargs.pop("factory", None)
        return real_connect(*args, factory=_RecordingConnection, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(ac.sqlite3, "connect", _factory)
    return _RecordingConnection


def _seed_wal(path: Path) -> None:
    """Put the database in WAL, then clear the recorder.

    The recorder patches ``sqlite3.connect`` module-wide, so the seeding
    connection is recorded too; its ``journal_mode=WAL`` would otherwise be
    attributed to ``_connect``.
    """
    seed = sqlite3.connect(str(path))
    seed.execute("PRAGMA journal_mode=WAL")
    seed.close()
    _RecordingConnection.executed = []


def _wal_writes(recorder: type[_RecordingConnection]) -> list[str]:
    return [sql for sql in recorder.executed if "journal_mode=WAL" in sql]


def _wal_reads(recorder: type[_RecordingConnection]) -> list[str]:
    return [
        sql for sql in recorder.executed if "journal_mode" in sql and "journal_mode=WAL" not in sql
    ]


def test_fresh_database_is_converted_to_wal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, recording_connect: type[_RecordingConnection]
) -> None:
    """A database not yet in WAL must still be converted (no regression)."""
    monkeypatch.setattr(ac, "_default_db_path", lambda: tmp_path / "autoinfo.db")

    conn = ac._connect()
    try:
        assert str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower() == "wal"
    finally:
        conn.close()

    assert _wal_writes(recording_connect), "fresh database was never converted to WAL"


def test_already_wal_database_is_not_converted_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, recording_connect: type[_RecordingConnection]
) -> None:
    """An existing WAL database must not re-issue the exclusively-locked write.

    This is the regression lock: re-issuing ``PRAGMA journal_mode=WAL`` on every
    connection is what dropped outbox rows under concurrency (#387).
    """
    monkeypatch.setattr(ac, "_default_db_path", lambda: tmp_path / "autoinfo.db")
    _seed_wal(tmp_path / "autoinfo.db")

    conn = ac._connect()
    try:
        assert str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower() == "wal"
    finally:
        conn.close()

    assert _wal_reads(recording_connect), "current journal mode should be read first"
    assert not _wal_writes(recording_connect), (
        "re-issued the WAL conversion on an already-WAL database; that write takes an "
        "EXCLUSIVE lock that busy_timeout does not cover (#387)"
    )


def test_busy_timeout_is_still_applied_before_the_mode_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, recording_connect: type[_RecordingConnection]
) -> None:
    """busy_timeout must stay, and must precede the journal-mode handling.

    #67 added it for ordinary statements; #387 is not a reason to remove it, only
    to stop relying on it for the journal-mode write.
    """
    monkeypatch.setattr(ac, "_default_db_path", lambda: tmp_path / "autoinfo.db")
    _seed_wal(tmp_path / "autoinfo.db")

    conn = ac._connect()
    conn.close()

    statements = recording_connect.executed
    busy_idx = next(i for i, sql in enumerate(statements) if "busy_timeout" in sql)
    mode_idx = next(i for i, sql in enumerate(statements) if "journal_mode" in sql)
    assert busy_idx < mode_idx, "busy_timeout must be set before touching journal_mode"
