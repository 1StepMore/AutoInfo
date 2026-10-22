"""Regression tests for the first-WAL-conversion race (issue #571).

Before this fix every business connection could issue
``PRAGMA journal_mode=WAL`` on a brand-new database. That statement takes an
EXCLUSIVE lock and bypasses the SQLite busy handler, so under the 16-thread
first-writer race recorded in ``tests/TRIAGE.md`` it raised
``database is locked``. The conversion now belongs to
:func:`autoinfo.db.ensure_initialized` and is never re-issued.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any

import pytest

from autoinfo.db import DatabaseInitializationError, connect, ensure_initialized


@pytest.fixture
def statements(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    seen: list[str] = []
    real_connect = sqlite3.connect

    def recording_connect(*args: Any, **kwargs: Any) -> sqlite3.Connection:
        conn = real_connect(*args, **kwargs)
        conn.set_trace_callback(seen.append)
        return conn

    monkeypatch.setattr("autoinfo.db.sqlite3.connect", recording_connect)
    return seen


def _wal_switches(statements: list[str]) -> list[str]:
    return [s for s in statements if "journal_mode=wal" in s.lower()]


def test_concurrent_first_connect_converts_once(tmp_path: Path, statements: list[str]) -> None:
    db_path = tmp_path / "kb.db"
    errors: list[BaseException] = []
    barrier = threading.Barrier(16)

    def worker(index: int) -> None:
        try:
            barrier.wait()
            conn = connect(db_path)
            conn.execute("CREATE TABLE IF NOT EXISTS t (x INTEGER)")
            conn.execute("INSERT INTO t VALUES (?)", (index,))
            conn.commit()
            conn.close()
        except BaseException as exc:  # noqa: BLE001 - asserted below
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(16)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert len(_wal_switches(statements)) == 1

    conn = connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 16
    conn.close()


def test_existing_wal_db_never_reissues_journal_mode(tmp_path: Path, statements: list[str]) -> None:
    db_path = tmp_path / "kb.db"
    ensure_initialized(db_path)
    statements.clear()

    for _ in range(5):
        conn = connect(db_path)
        conn.execute("SELECT 1").fetchone()
        conn.close()

    assert _wal_switches(statements) == []


def test_ensure_initialized_is_idempotent(tmp_path: Path, statements: list[str]) -> None:
    db_path = tmp_path / "kb.db"
    ensure_initialized(db_path)
    ensure_initialized(db_path)
    ensure_initialized(db_path)

    assert len(_wal_switches(statements)) == 1


def test_contended_first_conversion_raises_typed_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("autoinfo.db._JOURNAL_MODE_ATTEMPTS", 2)
    monkeypatch.setattr("autoinfo.db._JOURNAL_MODE_RETRY_S", 0.01)
    db_path = tmp_path / "kb.db"

    holder = sqlite3.connect(db_path)
    holder.execute("CREATE TABLE t (x INTEGER)")
    holder.commit()
    holder.execute("BEGIN IMMEDIATE")
    holder.execute("INSERT INTO t VALUES (1)")
    try:
        with pytest.raises(DatabaseInitializationError) as excinfo:
            connect(db_path)
        assert isinstance(excinfo.value, sqlite3.OperationalError)
        assert "write lock" in str(excinfo.value)
    finally:
        holder.rollback()
        holder.close()

    conn = connect(db_path)
    assert str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower() == "wal"
    conn.close()


def test_readonly_connection_never_converts(tmp_path: Path, statements: list[str]) -> None:
    db_path = tmp_path / "kb.db"
    writer = sqlite3.connect(db_path)
    writer.execute("CREATE TABLE t (x INTEGER)")
    writer.commit()
    writer.close()
    statements.clear()

    conn = connect(db_path, readonly=True)
    assert str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower() == "delete"
    conn.close()
    assert _wal_switches(statements) == []


def test_memory_database_is_untouched(statements: list[str]) -> None:
    conn = connect(":memory:")
    assert str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower() == "memory"
    conn.close()
    assert _wal_switches(statements) == []
