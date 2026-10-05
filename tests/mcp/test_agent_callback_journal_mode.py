"""#387: the WAL journal-mode conversion must not run on every connection.

``PRAGMA journal_mode=WAL`` needs a brief EXCLUSIVE lock and SQLite does not
run the busy handler for it, so ``busy_timeout`` does not cover it. With many
threads opening a fresh database, the losers raised
``OperationalError: database is locked``, which
``enqueue_agent_notification`` swallowed into a return of 0 — a silently dropped
outbox row. #395 renamed that return to ``_OUTBOX_PERSIST_FAILED`` (-1) and
counted it, so such a drop is now both distinguishable and counted rather than
indistinguishable from a correct skip.

``scripts/repro_outbox_lock.py`` demonstrates the failure probabilistically
(8 drops per 2400 writes before the fix, 0 after). These tests lock the
*mechanism* deterministically instead, so the guard cannot be removed and pass
by luck: a database already in WAL must not be converted again, and a fresh
one must still be converted.

The test that motivated this is probabilistic
(``test_concurrent_outbox_writes_no_lost_events``), so on its own it cannot
prove the fix; these assertions can.

#484 kept that determinism from leaking. The recorder below is installed as a
``sqlite3.connect`` **factory**, and that patch is process-wide for the duration
of a test: tracked daemon drain workers (``agent_callback._schedule_drain``) and
straggler writer threads from ``test_agent_callback.py`` open their own
connections through it. With the buffer on the class, those foreign statements
shared one list with the connection under test, so the comparison in
``test_busy_timeout_is_still_applied_before_the_mode_check`` mixed two
connections and failed probabilistically in CI (sha 72b6fca4: one run 1 failed /
6004 passed, the re-run 6005 passed / 0 failed). What tips such a comparison is a
foreign connection whose *first* statement is a journal-mode one —
``agent_callback._connect`` always sets ``busy_timeout`` first, but
``kb.SQLiteIndex._connect``, ``delivery_log``, ``user_store``, ``audit`` and
``cost`` all issue ``PRAGMA journal_mode=WAL`` first — landing ahead of this
test's own ``busy_timeout``. The buffer is therefore per connection instance and
every assertion reads the connection the test itself opened, so foreign
statements are structurally excluded from the window.
"""

from __future__ import annotations

import functools
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path

import pytest

from autoinfo import agent_callback as ac


@dataclass(frozen=True)
class _Statement:
    """One recorded statement plus the thread that executed it.

    The thread id is kept so a failure message can say *who* recorded a
    statement: under a process-wide ``sqlite3.connect`` patch, "which thread was
    this" is the first question when an ordering assertion misbehaves (#484).
    """

    sql: str
    thread_id: int


class _RecordingConnection(sqlite3.Connection):
    """Connection that records every statement executed against *it*.

    The class is only the ``sqlite3.connect`` factory target; the buffer is an
    instance attribute, so a connection's statement window is its own and no
    other connection in the process can insert into it (#484).
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        self.executed: list[_Statement] = []
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]

    def execute(self, sql: str, *args: object) -> sqlite3.Cursor:
        self.executed.append(_Statement(sql=sql, thread_id=threading.get_ident()))
        return super().execute(sql, *args)  # type: ignore[arg-type]


@pytest.fixture
def recording_connect(monkeypatch: pytest.MonkeyPatch) -> type[_RecordingConnection]:
    """Route every ``sqlite3.connect`` in the module through the recorder.

    ``agent_callback`` connects through this very ``sqlite3`` module object, so
    the patch is process-wide and reaches threads the test does not own (#484).
    Isolation is therefore the recorder's job, not the fixture's: each connection
    keeps its own statement list, and the assertions below read only the
    connection they opened.
    """
    # Pre-binding the factory keeps the recorder on every connection whatever the
    # caller passes; a caller-supplied ``factory`` is dropped for the same reason.
    connect_recording = functools.partial(sqlite3.connect, factory=_RecordingConnection)

    def _factory(*args: object, **kwargs: object) -> sqlite3.Connection:
        kwargs.pop("factory", None)
        return connect_recording(*args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", _factory)
    return _RecordingConnection


def _seed_wal(path: Path) -> None:
    """Put the database in WAL before the connection under test opens it.

    The seed connection goes through the same patched ``sqlite3.connect`` as
    everything else, but its statements land on its own recorder and die with
    the object, so nothing has to be cleared afterwards (#484).
    """
    seed = sqlite3.connect(str(path))
    seed.execute("PRAGMA journal_mode=WAL")
    seed.close()


def _statements(conn: sqlite3.Connection) -> list[_Statement]:
    """Return the statement window recorded on ``conn`` itself.

    Scoping every assertion to the connection the test opened is what keeps a
    foreign connection (another thread's drain worker or writer) out of the
    window (#484). The ``isinstance`` check doubles as proof that the
    ``sqlite3.connect`` patch is actually in place for this test.
    """
    assert isinstance(conn, _RecordingConnection), (
        "connection did not come from the recording factory; the module-wide "
        "sqlite3.connect patch is not in place"
    )
    return conn.executed


def _trace(statements: list[_Statement]) -> str:
    """Render a statement window for a failure message, with recording threads."""
    return "\n".join(f"  [{s.thread_id}] {s.sql}" for s in statements) or "  <none>"


def _wal_writes(statements: list[_Statement]) -> list[_Statement]:
    return [s for s in statements if "journal_mode=WAL" in s.sql]


def _wal_reads(statements: list[_Statement]) -> list[_Statement]:
    return [s for s in statements if "journal_mode" in s.sql and "journal_mode=WAL" not in s.sql]


def test_fresh_database_is_converted_to_wal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, recording_connect: type[_RecordingConnection]
) -> None:
    """A database not yet in WAL must still be converted (no regression)."""
    monkeypatch.setattr(ac, "_default_db_path", lambda: tmp_path / "autoinfo.db")

    conn = ac._connect()
    try:
        assert str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower() == "wal"
        statements = _statements(conn)
        assert _wal_writes(statements), (
            "fresh database was never converted to WAL; statements on this connection:\n"
            f"{_trace(statements)}"
        )
    finally:
        conn.close()


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
        statements = _statements(conn)
    finally:
        conn.close()

    assert _wal_reads(statements), (
        "current journal mode should be read first; statements on this connection:\n"
        f"{_trace(statements)}"
    )
    assert not _wal_writes(statements), (
        "re-issued the WAL conversion on an already-WAL database; that write takes an "
        "EXCLUSIVE lock that busy_timeout does not cover (#387). Statements on this "
        f"connection:\n{_trace(statements)}"
    )


def test_busy_timeout_is_still_applied_before_the_mode_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, recording_connect: type[_RecordingConnection]
) -> None:
    """busy_timeout must stay, and must precede the journal-mode handling.

    #67 added it for ordinary statements; #387 is not a reason to remove it, only
    to stop relying on it for the journal-mode write.

    The window is this test's own connection (#484): with a process-wide
    ``sqlite3.connect`` patch, a foreign connection recording a journal-mode
    statement first used to invert the comparison and fail intermittently.
    """
    monkeypatch.setattr(ac, "_default_db_path", lambda: tmp_path / "autoinfo.db")
    _seed_wal(tmp_path / "autoinfo.db")

    conn = ac._connect()
    try:
        statements = _statements(conn)
    finally:
        conn.close()

    busy_idx = next(i for i, s in enumerate(statements) if "busy_timeout" in s.sql)
    mode_idx = next(i for i, s in enumerate(statements) if "journal_mode" in s.sql)
    assert busy_idx < mode_idx, (
        "busy_timeout must be set before touching journal_mode; statements on this "
        f"connection (idle={busy_idx}, journal_mode={mode_idx}):\n{_trace(statements)}"
    )
