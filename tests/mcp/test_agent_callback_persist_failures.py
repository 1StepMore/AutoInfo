"""#395: a notification lost at enqueue time must be distinguishable and counted.

``enqueue_agent_notification`` had three ``return 0`` paths with completely
different meanings:

1. unknown/unsupported event name — a programming error, and **nothing was
   ever supposed to be sent**;
2. payload not JSON-serialisable — a notification that **should** have been
   delivered was silently dropped;
3. SQLite write failure (e.g. ``database is locked``) — same data loss.

A caller could not tell (1) from (2)/(3). #387 is the demonstrated cost: 8 of
2400 events were lost under concurrency, and nothing surfaced beyond a
``logger.warning`` that carried no trace/product identity.

The fix separates the semantics — ``> 0`` persisted, ``0`` deliberately not
enqueued, ``_OUTBOX_PERSIST_FAILED`` (-1) lost — and counts the loss in
``outbox_persist_failures_total``. That counter is deliberately NOT
``delivery_failures_total``: a row lost here never reaches the drain, so the
delivery-failure counter structurally cannot observe it.

Hermeticity: the DB path is patched to a per-test tmp SQLite DB; the
persistence-failure paths inject the failure directly. No network, no repo
pollution.
"""

from __future__ import annotations

import json
import sqlite3

import pytest

import autoinfo.agent_callback as ac
from autoinfo.metrics import METRIC_NAMES, format_prometheus, get_metrics


@pytest.fixture
def ac_module(monkeypatch, tmp_path):
    """Hermetic agent_callback module: per-test tmp SQLite DB."""
    db_path = tmp_path / "autoinfo.db"
    monkeypatch.setattr(ac, "_default_db_path", lambda: db_path)
    monkeypatch.setattr(ac, "_outbox_persist_failures_total", 0)
    monkeypatch.setattr(ac, "_schedule_drain", lambda: None)
    return ac


def _enqueue(**overrides):
    kwargs = {
        "event": "new_digest",
        "payload": {"k": "v"},
        "trace_id": "t-1",
        "product_id": "p-1",
    }
    kwargs.update(overrides)
    return ac.enqueue_agent_notification(**kwargs)


class TestSuccessPath:
    def test_persisted_returns_positive_row_id(self, ac_module) -> None:
        assert _enqueue() > 0

    def test_success_does_not_count_a_persist_failure(self, ac_module) -> None:
        _enqueue()
        assert ac.get_outbox_persist_failures() == 0


class TestUnknownEventIsNotDataLoss:
    """Path 1 returns 0 and must NOT be counted as a lost notification."""

    def test_unknown_event_returns_zero(self, ac_module) -> None:
        assert _enqueue(event="not_a_real_event") == 0

    def test_unknown_event_is_not_counted_as_persist_failure(self, ac_module) -> None:
        """A programming error loses nothing, so it must not pollute the
        data-loss counter an operator alerts on."""
        _enqueue(event="not_a_real_event")
        assert ac.get_outbox_persist_failures() == 0


class TestUnserialisablePayloadIsDataLoss:
    """Path 2 returns the dedicated failure sentinel and is counted."""

    def test_returns_persist_failed_sentinel(self, ac_module) -> None:
        circular: dict = {}
        circular["self"] = circular  # -> ValueError: circular reference

        result = _enqueue(payload=circular)

        assert result == ac._OUTBOX_PERSIST_FAILED
        assert result != 0, "must be distinguishable from a deliberate skip"

    def test_counts_the_loss(self, ac_module) -> None:
        circular: dict = {}
        circular["self"] = circular
        _enqueue(payload=circular)

        assert ac.get_outbox_persist_failures() == 1

    def test_logs_trace_and_product_identity(self, ac_module, caplog) -> None:
        circular: dict = {}
        circular["self"] = circular
        with caplog.at_level("WARNING"):
            _enqueue(payload=circular, trace_id="t-42", product_id="prod-xyz")

        blob = json.dumps([r.getMessage() for r in caplog.records])
        assert "prod-xyz" in blob, "operator must be able to find the lost product"
        assert "t-42" in blob, "log must carry the trace id"


class TestWriteFailureIsDataLoss:
    """Path 3 — the #387 shape — returns the sentinel and is counted."""

    def test_db_write_failure_returns_sentinel(self, ac_module, monkeypatch) -> None:
        def _boom():
            raise sqlite3.OperationalError("database is locked")

        monkeypatch.setattr(ac_module, "_connect", _boom)

        result = _enqueue()

        assert result == ac._OUTBOX_PERSIST_FAILED
        assert result < 0

    def test_db_write_failure_is_counted(self, ac_module, monkeypatch) -> None:
        def _boom():
            raise sqlite3.OperationalError("database is locked")

        monkeypatch.setattr(ac_module, "_connect", _boom)
        _enqueue()

        assert ac.get_outbox_persist_failures() == 1

    def test_db_write_failure_logs_product_identity(self, ac_module, monkeypatch, caplog) -> None:
        def _boom():
            raise sqlite3.OperationalError("database is locked")

        monkeypatch.setattr(ac_module, "_connect", _boom)
        with caplog.at_level("WARNING"):
            _enqueue(trace_id="t-7", product_id="prod-lost")

        blob = json.dumps([r.getMessage() for r in caplog.records])
        assert "prod-lost" in blob


class TestReturnContractIsThreeValued:
    """The three semantics must be mutually distinguishable (#395's core)."""

    def test_three_outcomes_are_distinct(self, ac_module, monkeypatch) -> None:
        def _boom():
            raise sqlite3.OperationalError("database is locked")

        circular: dict = {}
        circular["self"] = circular

        persisted = _enqueue()
        skipped = _enqueue(event="not_a_real_event")
        monkeypatch.setattr(ac_module, "_connect", _boom)
        lost = _enqueue()

        assert persisted > 0
        assert skipped == 0
        assert lost == ac._OUTBOX_PERSIST_FAILED
        assert len({persisted, skipped, lost}) == 3, (
            "the three outcomes must be mutually distinguishable: a persisted "
            "row id, a deliberate skip, and a lost notification"
        )
        assert lost < skipped < persisted


class TestMetricSurfacing:
    def test_counter_is_exported_as_a_prometheus_metric(self, ac_module, monkeypatch) -> None:
        """The loss must be visible to operators, not only in a log line."""

        def _boom():
            raise sqlite3.OperationalError("database is locked")

        monkeypatch.setattr(ac_module, "_connect", _boom)
        _enqueue()

        metrics = get_metrics()

        assert metrics["outbox_persist_failures_total"] == 1
        assert "outbox_persist_failures_total" in METRIC_NAMES, (
            "without a METRIC_NAMES entry the counter is silently dropped from "
            "Prometheus exposition by format_prometheus"
        )

    def test_counter_is_rendered_in_prometheus_output(self, ac_module, monkeypatch) -> None:
        def _boom():
            raise sqlite3.OperationalError("database is locked")

        monkeypatch.setattr(ac_module, "_connect", _boom)
        _enqueue()

        rendered = format_prometheus(get_metrics())

        assert "outbox_persist_failures_total 1" in rendered
