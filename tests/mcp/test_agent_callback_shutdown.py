"""Issue #378 — agent outbox drain worker shutdown regression tests.

Failing-first (RED) contract for the agent-outbox daemon lifecycle:

(a) An unexpected ``_drain_outbox`` exception must NOT escape the worker
    target into :data:`threading.excepthook` — it must be contained at the
    worker boundary.
(b) A scheduled drain worker is tracked in ``_drain_threads``; during
    shutdown it is joined and removed from that registry.
(c) ``_schedule_drain`` after shutdown has begun is suppressed — no worker
    starts and ``_drain_outbox`` is never invoked.

Why this matters: an uncontained drain traceback written to buffered stderr
while the interpreter finalizes hits CPython's ``_enter_buffered_busy`` fatal
path (CI job 106313918530 exited 134). Containing the worker and joining it
before finalization removes that race.

These tests are RED against the current implementation:

- ``test_unexpected_drain_exception_does_not_reach_thread_excepthook`` runs
  against the CURRENT ``_schedule_drain`` / ``_drain_outbox`` interface and
  fails because the ``RuntimeError`` reaches the recording
  :data:`threading.excepthook`.
- The lifecycle tests bind to the intended private interface
  (``_DRAIN_JOIN_TIMEOUT``, ``_drain_threads``, ``_shutdown_event``,
  ``_drain_worker``, ``_join_drain_threads(timeout=...)``,
  ``_register_shutdown_hook()``) and fail because that interface does not
  exist yet.

Determinism: every handshake is a :class:`threading.Event`; every thread is
awaited with a bounded :meth:`~threading.Thread.join`; no ``sleep``, no real
sockets, and the repository-root ``autoinfo.db`` is never touched (the
per-test ``ac_module`` fixture redirects ``_default_db_path``).
"""

from __future__ import annotations

import threading
from typing import Any

import pytest

import autoinfo.agent_callback as ac

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def ac_module(monkeypatch, tmp_path):
    """Hermetic agent_callback module: per-test tmp SQLite DB.

    Mirrors ``tests/mcp/test_agent_callback.py`` so no code path — even an
    accidental one — can reach the repository-root ``autoinfo.db``.
    """
    db_path = tmp_path / "autoinfo.db"
    monkeypatch.setattr(ac, "_default_db_path", lambda: db_path)
    return ac


def _reset_drain_lifecycle(ac_module: Any) -> None:
    """Restore process-wide shutdown state so tests stay isolated.

    Invoked in ``finally`` (and in the Given phase): joins any live tracked
    worker, then clears the shutdown event and the registry. ``getattr``
    guards keep it a no-op against the current untracked module, so the RED
    tests isolate even when the fix has not landed.
    """
    join = getattr(ac_module, "_join_drain_threads", None)
    if callable(join):
        join(timeout=0.5)
    event = getattr(ac_module, "_shutdown_event", None)
    if event is not None:
        event.clear()
    registry = getattr(ac_module, "_drain_threads", None)
    if registry is not None:
        registry.clear()


def _install_thread_spy(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[list[threading.Thread], list[threading.Thread]]:
    """Spy on the exact ``threading.Thread`` seam ``_schedule_drain`` uses.

    ``_schedule_drain`` constructs ``threading.Thread`` directly, so replacing
    that module attribute is the narrowest observable boundary: if shutdown
    suppresses scheduling, the class is never instantiated (and therefore
    never started), regardless of what the worker body would have done. The
    spy subclasses the real thread and delegates ``start`` so a regression
    still produces a real, joinable worker rather than a hanging fake.

    Returns ``(constructed, started)`` — the two lists the spy appends to.
    """
    constructed: list[threading.Thread] = []
    started: list[threading.Thread] = []

    class _RecordingThread(threading.Thread):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            constructed.append(self)

        def start(self) -> None:
            started.append(self)
            super().start()

    monkeypatch.setattr(threading, "Thread", _RecordingThread)
    return constructed, started


# ---------------------------------------------------------------------------
# (a) Unexpected drain exception is contained — NOT routed to excepthook
# ---------------------------------------------------------------------------


def test_unexpected_drain_exception_does_not_reach_thread_excepthook(ac_module, monkeypatch):
    """Given a drain body that raises, When scheduled, Then no traceback escapes.

    The current implementation starts ``threading.Thread(target=_drain_outbox)``
    with no containment boundary, so the ``RuntimeError`` propagates into
    :data:`threading.excepthook` — the buffered-stderr traceback that overlaps
    interpreter finalization. The contractual outcome is containment: the
    recording excepthook receives nothing.
    """
    started = threading.Event()
    escaped: list[BaseException] = []
    worker_threads: list[threading.Thread] = []

    def _recording_excepthook(args: Any) -> None:
        escaped.append(args.exc_value)

    def _exploding_drain() -> None:
        worker_threads.append(threading.current_thread())
        started.set()
        raise RuntimeError("synthetic drain failure")

    _reset_drain_lifecycle(ac_module)
    monkeypatch.setattr(ac, "_drain_outbox", _exploding_drain)
    monkeypatch.setattr(threading, "excepthook", _recording_excepthook)
    try:
        # When: the normal scheduling entry point starts the worker.
        ac._schedule_drain()

        # Then: the worker actually ran, and the thread has fully terminated
        # (excepthook, if any, is invoked before the underlying tstate is
        # released, i.e. before join() returns).
        assert started.wait(5.0), "scheduled drain worker never entered _drain_outbox"
        assert worker_threads, "drain worker never ran on a thread"
        worker = worker_threads[0]
        worker.join(5.0)
        assert not worker.is_alive(), "drain worker did not terminate"
    finally:
        _reset_drain_lifecycle(ac_module)

    assert escaped == [], (
        "unexpected _drain_outbox exception escaped to threading.excepthook: "
        f"{[type(e).__name__ for e in escaped]}"
    )


# ---------------------------------------------------------------------------
# (b) Shutdown joins a tracked worker and clears its registry entry
# ---------------------------------------------------------------------------


def test_shutdown_joins_tracked_drain_worker_and_clears_registry(ac_module, monkeypatch):
    """Given a live tracked worker, When shutdown joins, Then joined + removed.

    Binds the intended lifecycle interface: ``_drain_worker`` is the tracked
    thread target, ``_drain_threads`` the registry, ``_DRAIN_JOIN_TIMEOUT``
    the join budget, ``_shutdown_event`` the shutdown state, and
    ``_join_drain_threads(timeout=...)`` the join primitive.
    """
    release = threading.Event()
    started = threading.Event()
    worker_threads: list[threading.Thread] = []

    def _blocking_worker() -> None:
        worker_threads.append(threading.current_thread())
        started.set()
        release.wait(10.0)

    _reset_drain_lifecycle(ac_module)
    monkeypatch.setattr(ac, "_drain_worker", _blocking_worker)
    try:
        # Given: the shutdown hook is registered and a worker is scheduled.
        ac._register_shutdown_hook()
        ac._schedule_drain()
        assert started.wait(5.0), "scheduled drain worker never started"
        assert worker_threads, "drain worker never ran on a thread"
        worker = worker_threads[0]
        assert worker in ac._drain_threads, "live drain worker was not tracked"

        # When: shutdown begins (state flips, worker released, join runs).
        release.set()
        ac._shutdown_event.set()
        ac._join_drain_threads(timeout=ac._DRAIN_JOIN_TIMEOUT)

        # Then: the worker is joined and no longer tracked.
        assert not worker.is_alive(), "shutdown did not join the drain worker"
        assert worker not in ac._drain_threads, "joined drain worker was left in the registry"
    finally:
        release.set()
        _reset_drain_lifecycle(ac_module)


# ---------------------------------------------------------------------------
# (c) Scheduling after shutdown begins is suppressed
# ---------------------------------------------------------------------------


def test_schedule_drain_is_suppressed_after_shutdown_begins(ac_module, monkeypatch):
    """Given shutdown has begun, When scheduling, Then no Thread is built/started.

    After ``_shutdown_event`` is set, ``_schedule_drain`` must not construct or
    start a ``threading.Thread`` at all — checking only "the worker body ran"
    would pass vacuously for a worker that starts and immediately exits. The
    spy on ``threading.Thread`` (the exact seam ``_schedule_drain`` uses) makes
    construction itself the observable, so a spuriously-started worker fails
    regardless of how quickly it terminates.
    """
    drain_ran = threading.Event()

    def _recording_drain() -> None:
        drain_ran.set()

    _reset_drain_lifecycle(ac_module)
    monkeypatch.setattr(ac, "_drain_outbox", _recording_drain)
    constructed, started = _install_thread_spy(monkeypatch)
    try:
        ac._shutdown_event.set()

        # When: a drain is scheduled after shutdown has begun.
        ac._schedule_drain()

        # Then: no thread was constructed or started, and the body never ran.
        assert constructed == [], (
            "threading.Thread was constructed after shutdown began: "
            f"{[t.name for t in constructed]}"
        )
        assert started == [], (
            f"a drain thread was started after shutdown began: {[t.name for t in started]}"
        )
        assert not drain_ran.is_set(), "drain body ran after shutdown began"
    finally:
        _reset_drain_lifecycle(ac_module)


def test_thread_spy_observes_scheduling_when_shutdown_is_clear(ac_module, monkeypatch):
    """Control: with shutdown clear, ``_schedule_drain`` uses ``threading.Thread``.

    This proves the suppression test's spy is wired to the real seam — without
    it, an empty ``constructed`` list could pass vacuously if the spy never
    observed anything at all.
    """

    def _noop_drain() -> None:
        return

    _reset_drain_lifecycle(ac_module)
    monkeypatch.setattr(ac, "_drain_outbox", _noop_drain)
    constructed, started = _install_thread_spy(monkeypatch)
    try:
        # When: a drain is scheduled while shutdown is clear.
        ac._schedule_drain()

        # Then: the spy observed construction and start.
        assert constructed, "spy did not observe threading.Thread construction"
        assert started, "spy did not observe Thread.start()"
    finally:
        _reset_drain_lifecycle(ac_module)
