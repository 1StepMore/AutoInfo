#!/usr/bin/env python3
"""Repro harness for #387 — concurrent outbox writes drop notification rows.

`test_concurrent_outbox_writes_no_lost_events` fails under machine load with
``1 of 16 events dropped (database is locked)``, and ``enqueue_agent_notification``
swallows the error and returns 0, so the drop is silent in production.

This harness exists because the obvious fix is already known to be wrong:
``busy_timeout`` has been set *before* the WAL transition since 502a63c5
(issue #67/#387), and the failure still surfaces on that transition. Do not
"fix" it by adding another busy_timeout without a root cause first.

Two details make the race reachable, which is why a naive loop often shows
nothing:

1. **A fresh database per round.** ``PRAGMA journal_mode=WAL`` only does real
   work when the database is not already in WAL mode. Against a database that
   is already WAL, the pragma is effectively a no-op and never contends. Every
   round therefore gets its own database, so 16 threads genuinely race the
   journal-mode conversion.
2. **CPU pressure.** The failure is load-sensitive; on an idle box it may not
   reproduce at all. ``--load`` adds background burners.

It attributes a failure to the statement that raised rather than inferring it
from a log line, which is the part ``TRIAGE.md`` records as unproven.

Usage::

    python3 scripts/repro_outbox_lock.py                  # 20 rounds x 16 threads
    python3 scripts/repro_outbox_lock.py --rounds 100 --load 12
    python3 scripts/repro_outbox_lock.py --threads 64

Exit code 0 = no drops observed; 1 = at least one drop (the flake reproduced).
"""

from __future__ import annotations

import argparse
import multiprocessing
import os
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
import traceback
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# Drain workers are async; give them time to finish before deleting their DB.
_DRAIN_SETTLE_S = 1.0

STATEMENT_FAILURES: Counter[str] = Counter()
_SAMPLES: dict[str, str] = {}
_LOCK = threading.Lock()


def _record(label: str, exc: BaseException) -> None:
    with _LOCK:
        STATEMENT_FAILURES[f"{label} -> {exc}"] += 1
        _SAMPLES.setdefault(label, traceback.format_exc())


def _busy(duration: float) -> None:
    """Background CPU burner, to recreate the load the flake needs."""
    import hashlib

    deadline = threading.Event()
    waiter = threading.Thread(target=deadline.wait, args=(duration,), daemon=True)
    waiter.start()
    blob = b"x" * 100_000
    while not deadline.is_set():
        hashlib.sha256(blob).hexdigest()


def _one_round(agent_callback, db_dir: Path, threads: int) -> tuple[int, int]:
    """Run *threads* concurrent enqueues against a fresh DB. Returns (ok, dropped).

    Chdirs into *db_dir* so ``_default_db_path()`` resolves the fresh database;
    the caller guarantees the directory is new, which is what makes the WAL
    transition do real work.
    """
    previous = os.getcwd()
    os.chdir(db_dir)
    try:
        results: list[int] = []
        guard = threading.Lock()

        def writer(index: int) -> None:
            row_id = agent_callback.enqueue_agent_notification(
                event="new_digest",
                payload={"writer": index},
                trace_id=f"repro-{index}",
                product_id=f"writer-{index}",
            )
            with guard:
                results.append(row_id)

        workers = [threading.Thread(target=writer, args=(i,)) for i in range(threads)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
        ok = sum(1 for row_id in results if row_id > 0)
        return ok, len(results) - ok
    finally:
        os.chdir(previous)


def _cleanup(dirs: list[Path]) -> None:
    """Remove round directories after all drain threads have finished."""
    time.sleep(_DRAIN_SETTLE_S)
    for directory in dirs:
        shutil.rmtree(directory, ignore_errors=True)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, default=20, help="fresh-database rounds")
    parser.add_argument("--threads", type=int, default=16, help="concurrent writers per round")
    parser.add_argument(
        "--load",
        type=int,
        default=0,
        help="background CPU burners; the flake is load-sensitive",
    )
    args = parser.parse_args(argv)

    if args.load:
        burners = [
            multiprocessing.Process(target=_busy, args=(3600.0,), daemon=True)
            for _ in range(args.load)
        ]
        for burner in burners:
            burner.start()
        print(f"started {len(burners)} background load generator(s)")

    from autoinfo import agent_callback as ac

    # Attribute the failure without altering the statement sequence: run the
    # real _connect, and only if it raises, replay the sequence step by step to
    # find which statement is responsible.
    real_connect = ac._connect

    def traced_connect(db_path: Path | None = None) -> sqlite3.Connection:
        try:
            return real_connect(db_path)
        except sqlite3.OperationalError as exc:
            # The original traceback already names the failing statement inside
            # _connect, so read it rather than replaying the sequence: the lock
            # is transient, and a replay races to observe a lock that has
            # already been released.
            culprit = ""
            for frame in traceback.extract_tb(exc.__traceback__):
                if frame.filename.endswith("agent_callback.py") and frame.name == "_connect":
                    culprit = f"{Path(frame.filename).name}:{frame.lineno}  {frame.line}"
            _record(culprit or "unattributed", exc)
            raise

    ac._connect = traced_connect

    total_ok = 0
    total_dropped = 0
    failed_rounds: list[int] = []
    round_dirs: list[Path] = []
    for round_index in range(1, args.rounds + 1):
        # Fresh dir per round so journal_mode=WAL has real work to do.
        round_dir = Path(tempfile.mkdtemp(prefix="repro-outbox-lock-"))
        ok, dropped = _one_round(ac, round_dir, args.threads)
        # Deliberately NOT removed here: enqueue schedules async drain workers,
        # and deleting the database underneath a live drain thread surfaces as
        # an unrelated "disk I/O error" that looks like a product fault.  The
        # directories are removed in _cleanup() once every thread has finished.
        round_dirs.append(round_dir)
        total_ok += ok
        total_dropped += dropped
        if dropped:
            failed_rounds.append(round_index)
        marker = "  <-- DROPPED" if dropped else ""
        print(
            f"round {round_index}/{args.rounds}: {ok}/{args.threads} persisted{marker}",
            flush=True,
        )

    attempted = total_ok + total_dropped
    print(f"\ntotal: persisted={total_ok} dropped={total_dropped} of {attempted}")
    if failed_rounds:
        rate = len(failed_rounds) / args.rounds
        print(f"REPRODUCED in {len(failed_rounds)}/{args.rounds} rounds ({rate:.0%})")

    if STATEMENT_FAILURES:
        print("\nfailing statement attribution:")
        for label, count in STATEMENT_FAILURES.most_common():
            print(f"  {count:4d}x  {label}")
        for label, sample in _SAMPLES.items():
            print(f"\n--- sample ({label}) ---\n{sample}")
    else:
        print("\nno sqlite3.OperationalError captured in _connect()")

    _cleanup(round_dirs)

    if not failed_rounds:
        print(
            "\nNo drops observed. The flake is load-sensitive: retry with --load 12 "
            "and more rounds before concluding it is absent."
        )
    return 1 if failed_rounds else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
