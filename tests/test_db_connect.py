"""Unified SQLite connection factory (issue #563).

Every business connection must use the same PRAGMAs. Before the fix, only
``kb`` and ``process`` set ``busy_timeout``; cost, consumption, user, delivery,
audit and callback connections failed immediately with ``database is locked``
under the exact contention the KB connection waited out.

These tests assert the factory defaults directly and then walk every
``_connect`` entry point so configuration drift cannot reappear.
"""

from __future__ import annotations

import functools
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from autoinfo import agent_callback, audit, consumption, cost, db, delivery_log, process, user_store
from autoinfo.kb import SQLiteIndex


def _assert_default_pragmas(conn: sqlite3.Connection) -> None:
    assert conn.row_factory is sqlite3.Row
    assert str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower() == "wal"
    assert conn.execute("PRAGMA synchronous").fetchone()[0] == 1  # NORMAL
    assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == db.busy_timeout_ms()


def test_connect_defaults(tmp_path: Path) -> None:
    conn = db.connect(tmp_path / "default.db")
    try:
        _assert_default_pragmas(conn)
    finally:
        conn.close()


def test_busy_timeout_matches_kb_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    from autoinfo.kb import _db_busy_timeout_ms

    assert _db_busy_timeout_ms() == db.busy_timeout_ms() == 30000
    monkeypatch.setenv("AUTOINFO_DB_BUSY_TIMEOUT_MS", "12345")
    assert _db_busy_timeout_ms() == db.busy_timeout_ms() == 12345
    monkeypatch.setenv("AUTOINFO_DB_BUSY_TIMEOUT_MS", "not-a-number")
    assert _db_busy_timeout_ms() == db.busy_timeout_ms() == 30000


def test_cost_connect(tmp_path: Path) -> None:
    meter = cost.CostMeter.__new__(cost.CostMeter)
    meter._db_path = tmp_path / "cost.db"
    conn = meter._connect()
    try:
        _assert_default_pragmas(conn)
    finally:
        conn.close()


def test_kb_connect(tmp_path: Path) -> None:
    conn = SQLiteIndex(tmp_path / "kb.db")._connect()
    try:
        _assert_default_pragmas(conn)
    finally:
        conn.close()


def test_consumption_connect(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(consumption, "_DB_PATH", tmp_path / "consumption.db")
    conn = consumption._connect()
    try:
        _assert_default_pragmas(conn)
    finally:
        conn.close()


def test_user_store_connect(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(user_store, "_DB_PATH", tmp_path / "users.db")
    conn = user_store._connect()
    try:
        _assert_default_pragmas(conn)
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        conn.close()


def test_delivery_log_connect(tmp_path: Path) -> None:
    conn = delivery_log._connect(tmp_path / "delivery.db")
    try:
        _assert_default_pragmas(conn)
    finally:
        conn.close()


def test_audit_connect(tmp_path: Path) -> None:
    conn = audit._connect(tmp_path / "audit.db")
    try:
        _assert_default_pragmas(conn)
    finally:
        conn.close()


def test_agent_callback_connect(tmp_path: Path) -> None:
    conn = agent_callback._connect(tmp_path / "callback.db")
    try:
        _assert_default_pragmas(conn)
    finally:
        conn.close()


def test_process_progress_connect(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(process, "_get_progress_db_path", lambda: tmp_path / "progress.db")
    conn = process._connect_progress_db()
    try:
        _assert_default_pragmas(conn)
    finally:
        conn.close()


def test_readonly_rejects_writes(tmp_path: Path) -> None:
    path = tmp_path / "readonly.db"
    writer = db.connect(path)
    try:
        writer.execute("CREATE TABLE t (x INTEGER)")
        writer.execute("INSERT INTO t VALUES (1)")
        writer.commit()
    finally:
        writer.close()

    reader = db.connect(path, readonly=True)
    try:
        assert reader.execute("SELECT x FROM t").fetchone()[0] == 1
        with pytest.raises(sqlite3.OperationalError):
            reader.execute("INSERT INTO t VALUES (2)")
    finally:
        reader.close()


class _RecordingConnection(sqlite3.Connection):
    """Records statements on this connection only (see #484 for the pattern)."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.executed: list[str] = []
        super().__init__(*args, **kwargs)

    def execute(self, sql: str, *args: Any) -> sqlite3.Cursor:
        self.executed.append(sql)
        return super().execute(sql, *args)


def test_busy_timeout_precedes_journal_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """busy_timeout must be set before any journal-mode statement (#387/#563)."""
    recording = functools.partial(sqlite3.connect, factory=_RecordingConnection)

    def _factory(*args: Any, **kwargs: Any) -> sqlite3.Connection:
        kwargs.pop("factory", None)
        return recording(*args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", _factory)
    conn = db.connect(tmp_path / "order.db")
    try:
        assert isinstance(conn, _RecordingConnection)
        statements = conn.executed
    finally:
        conn.close()

    busy_idx = next(i for i, sql in enumerate(statements) if "busy_timeout" in sql)
    mode_idx = next(i for i, sql in enumerate(statements) if "journal_mode" in sql)
    assert busy_idx < mode_idx, statements
