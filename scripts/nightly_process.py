#!/usr/bin/env python3
"""Backlog-triggered AutoInfo processing stage for the nightly batch (#554).

The nightly batch used to go straight from ``collect`` to ``nightly_gap.py``.
Collect only writes cache files under ``collections/``; processing is the step
that turns those cache files into knowledge-base entries.  Without it entries
can stay flat for weeks even while the cache grows.

Running the LLM-heavy process stage for every domain every night is expensive,
so this script computes a per-domain backlog and only invokes ``autoinfo
process`` when the backlog reaches ``--min-backlog``::

    backlog = cached JSON items - last_processed_index (processing_progress)

The cursor is intentionally read from the same ``autoinfo.db`` /
``processing_progress`` table that the process CLI maintains.  A missing DB or
missing table means "nothing processed yet" and therefore the full cache is
treated as backlog.

The stage runs under a hard total budget (#596): ``--max-seconds`` (default
2400) is shared fairly across the due domains, so the lane returns inside the
systemd window and cannot eat the next stage's time.  When ``--batch-size`` is
left at 0 the per-domain item cap is derived from that fair share and
``--seconds-per-item`` (default 40 s, measured on the 2026-10-21 backlog), which
keeps a subprocess from being killed mid-item.  A domain that no longer fits is
reported as ``skipped_budget`` instead of being started anyway.
``--max-seconds 0`` disables the budget for manual / backlog runs.

#596 also left processing oldest-first, so a nightly run with a budget only
ever reached stale entries.  ``--since-days N`` restricts the backlog (and the
subprocess) to items collected within the last N days, and ``--newest-first``
processes the newest cached items first; both default to off.

Exit codes:
    0  all selected domains processed successfully, or nothing was due
    1  at least one selected domain failed
    2  usage or environment error

The result is machine-readable JSON plus a short Markdown table.  The nightly
batch records this step separately from collect/gap so an LLM failure is
visible without hiding the freshness report.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

REPO = Path(__file__).resolve().parent.parent
DEFAULT_DOMAINS_DIR = REPO / "src" / "autoinfo" / "data" / "domains"
DEFAULT_COLLECTIONS = REPO / "collections"
DEFAULT_DB = REPO / "autoinfo.db"
DEFAULT_MIN_BACKLOG = 20
DEFAULT_TIMEOUT = 7200
DEFAULT_MAX_SECONDS = 2400
DEFAULT_SECONDS_PER_ITEM = 40
SCHEMA = "autoinfo-nightly-process/1"


@dataclass(frozen=True)
class ProcessRequest:
    """One planned ``autoinfo process`` invocation."""

    domain: str
    repo: Path
    timeout_s: int
    batch_size: int = 0
    since_days: int = 0
    newest_first: bool = False


Runner = Callable[[ProcessRequest], tuple[int, float]]


def domain_names(domains_dir: Path) -> list[str]:
    """Return configured domains (directories with a ``sources.yaml``)."""
    if not domains_dir.is_dir():
        return []
    return sorted(
        d.name for d in domains_dir.iterdir() if d.is_dir() and (d / "sources.yaml").is_file()
    )


def count_cached_items(collections: Path, domain: str, since_days: int = 0) -> int:
    """Count usable cached item JSON files for one domain.

    Mirrors the loader's conventions: ``_runs.json`` and paths under a
    directory whose name starts with ``_`` are bookkeeping, not items.
    With *since_days* > 0, files under a date-named directory older than that
    window are skipped; non-date directories never filter a file out.  Only
    path/name parsing is done — cache files are never read.
    """
    root = collections / domain
    if not root.is_dir():
        return 0

    cutoff: date | None = None
    if since_days > 0:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=since_days)).date()

    count = 0
    for path in root.rglob("*.json"):
        rel_parts = path.relative_to(root).parts
        if path.name.startswith("_"):
            continue
        if any(part.startswith("_") for part in rel_parts[:-1]):
            continue
        if cutoff is not None:
            try:
                parent_date = date.fromisoformat(path.parent.name)
            except ValueError:
                parent_date = None
            if parent_date is not None and parent_date < cutoff:
                continue
        count += 1
    return count


def read_processed_count(db_path: Path, domain: str) -> int:
    """Read the processed-item count for a domain; 0 when unavailable.

    Prefers the item-id ledger (``processing_items``, AutoInfo#596): its row
    count is the number of distinct ids the processing cursor has consumed,
    unaffected by the cache total changing between runs.  Falls back to the
    legacy ``last_processed_index`` column when that table or domain has no
    ledger rows (pre-#596 projects / domains not yet migrated).
    """
    if not db_path.is_file():
        return 0

    conn: sqlite3.Connection | None = None
    try:
        uri = db_path.resolve().as_uri() + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=5)
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM processing_items WHERE domain = ?",
                (domain,),
            ).fetchone()
        except sqlite3.Error:
            row = None
        if row and row[0]:
            return max(0, int(row[0]))
        row = conn.execute(
            "SELECT last_processed_index FROM processing_progress WHERE domain = ?",
            (domain,),
        ).fetchone()
        return max(0, int(row[0])) if row and row[0] is not None else 0
    except (sqlite3.Error, OSError, ValueError):
        return 0
    finally:
        if conn is not None:
            conn.close()


def _autoinfo_cmd(python: str) -> list[str]:
    """Prefer the console script from the same venv; fall back to ``-m``."""
    # Do not resolve(): a venv's bin/python is a symlink to the system Python.
    candidate = python if "/" not in python else str(Path(python).absolute().parent / "autoinfo")
    if candidate != python and Path(candidate).is_file():
        return [candidate]
    return [python, "-m", "autoinfo.cli"]


def _derive_batch_size(
    allowance_s: float, seconds_per_item: int, backlog: int, budget_enabled: bool
) -> int:
    """Items that fit in *allowance_s*; 0 means "all" when no budget applies."""
    if not budget_enabled:
        return 0
    return max(1, min(backlog, int(allowance_s // seconds_per_item)))


def _run_process(request: ProcessRequest) -> tuple[int, float]:
    """Run ``autoinfo process --domain ... --resume-from auto``."""
    cmd = [
        *_autoinfo_cmd(sys.executable),
        "process",
        "--domain",
        request.domain,
        "--resume-from",
        "auto",
    ]
    if request.batch_size > 0:
        cmd += ["--batch-size", str(request.batch_size)]
    if request.since_days > 0:
        cmd += ["--since-days", str(request.since_days)]
    if request.newest_first:
        cmd += ["--newest-first"]
    started = time.monotonic()
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(request.repo),
            timeout=request.timeout_s,
            check=False,
        )
        return completed.returncode, round(time.monotonic() - started, 1)
    except subprocess.TimeoutExpired:
        return 124, round(time.monotonic() - started, 1)
    except OSError:
        return 127, round(time.monotonic() - started, 1)


def _log_row(row: dict[str, object]) -> None:
    print(
        f"[nightly-process] {row['domain']}: cached={row['cached_items']} "
        f"processed={row['processed_count']} backlog={row['backlog']} "
        f"budget={row['budget_s']}s batch={row['batch_size']} -> {row['action']}",
        flush=True,
    )


def _render_md(report: dict[str, object]) -> str:
    rows = report["domains"]
    assert isinstance(rows, list)
    summary = report["summary"]
    assert isinstance(summary, dict)
    lines = [
        "# AutoInfo nightly process (#554)",
        "",
        f"- generated: {report['generated_at']}",
        f"- min backlog: {report['min_backlog']}",
        f"- max seconds: {report['max_seconds']} (0 = unlimited)",
        f"- dry run: {str(report['dry_run']).lower()}",
        f"- selected: {summary['selected']} / executed: {summary['executed']} / "
        f"failed: {summary['failed']} / skipped: {summary['skipped']} / "
        f"skipped_budget: {summary['skipped_budget']}",
        "",
        "| domain | cached | processed | backlog | action | budget_s | batch | exit | seconds |",
        "|:---|---:|---:|---:|:---|---:|---:|---:|---:|",
    ]
    for row in rows:
        assert isinstance(row, dict)
        lines.append(
            f"| {row['domain']} | {row['cached_items']} | "
            f"{row['processed_count']} | {row['backlog']} | "
            f"{row['action']} | {row['budget_s']} | {row['batch_size']} | "
            f"{row['exit_code']} | {row['duration_s']} |"
        )
    if not rows:
        lines += ["", "No configured domain has cached items."]
    return "\n".join(lines) + "\n"


def main(
    argv: list[str] | None = None,
    runner: Runner | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> int:
    ap = argparse.ArgumentParser(
        prog="nightly_process.py",
        description="Run AutoInfo process only for domains with a cache backlog.",
    )
    ap.add_argument("--domains-dir", default=str(DEFAULT_DOMAINS_DIR))
    ap.add_argument("--collections", default=str(DEFAULT_COLLECTIONS))
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--repo", default=str(REPO))
    ap.add_argument(
        "--domain",
        action="append",
        default=[],
        help="Limit to one domain; repeat for multiple (default: all configured).",
    )
    ap.add_argument(
        "--min-backlog",
        type=int,
        default=DEFAULT_MIN_BACKLOG,
        help=f"Run when cached - processed is at least this many items "
        f"(default: {DEFAULT_MIN_BACKLOG}).",
    )
    ap.add_argument(
        "--max-seconds",
        type=int,
        default=DEFAULT_MAX_SECONDS,
        help=f"Hard budget for the whole run in seconds; 0 disables it "
        f"(default: {DEFAULT_MAX_SECONDS}).",
    )
    ap.add_argument(
        "--seconds-per-item",
        type=int,
        default=DEFAULT_SECONDS_PER_ITEM,
        help=f"Expected seconds per item, used to derive a per-domain batch size "
        f"when --batch-size is 0 (default: {DEFAULT_SECONDS_PER_ITEM}).",
    )
    ap.add_argument(
        "--batch-size",
        type=int,
        default=0,
        help="Process at most N items per domain (0 = derive from the budget).",
    )
    ap.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Per-domain process timeout cap in seconds (default: {DEFAULT_TIMEOUT}).",
    )
    ap.add_argument(
        "--since-days",
        type=int,
        default=0,
        help="Only process items collected within the last N days (0 = no window).",
    )
    ap.add_argument(
        "--newest-first",
        action="store_true",
        help="Process the newest cached items first instead of oldest-first.",
    )
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json-out", default="")
    ap.add_argument("--md-out", default="")
    args = ap.parse_args(argv)

    if args.min_backlog < 1:
        ap.error("--min-backlog must be >= 1")
    if args.max_seconds < 0:
        ap.error("--max-seconds must be >= 0")
    if args.seconds_per_item < 1:
        ap.error("--seconds-per-item must be >= 1")
    if args.batch_size < 0:
        ap.error("--batch-size must be >= 0")
    if args.timeout < 1:
        ap.error("--timeout must be >= 1")

    domains_dir = Path(args.domains_dir)
    collections = Path(args.collections)
    db_path = Path(args.db)
    repo = Path(args.repo)
    if not domains_dir.is_dir():
        print(f"nightly_process: domains dir not found: {domains_dir}", file=sys.stderr)
        return 2
    if not collections.is_dir():
        print(
            f"nightly_process: collections dir not found: {collections}",
            file=sys.stderr,
        )
        return 2
    if not repo.is_dir():
        print(f"nightly_process: repo dir not found: {repo}", file=sys.stderr)
        return 2

    configured = domain_names(domains_dir)
    if args.domain:
        requested = set(args.domain)
        configured = [d for d in configured if d in requested]
        unknown = sorted(requested - set(domain_names(domains_dir)))
        if unknown:
            print(
                "nightly_process: ignoring unknown domain(s): " + ", ".join(unknown),
                file=sys.stderr,
            )

    rows: list[dict[str, object]] = []
    for domain in configured:
        cached = count_cached_items(collections, domain, since_days=args.since_days)
        if cached == 0:
            continue
        processed = read_processed_count(db_path, domain)
        backlog = max(0, cached - processed)
        rows.append(
            {
                "domain": domain,
                "cached_items": cached,
                "processed_count": processed,
                "backlog": backlog,
                "action": "pending" if backlog >= args.min_backlog else "skip",
                "budget_s": 0.0,
                "batch_size": 0,
                "exit_code": 0,
                "duration_s": 0.0,
                "since_days": args.since_days,
                "newest_first": args.newest_first,
            }
        )

    run = runner or _run_process
    budget_enabled = args.max_seconds > 0
    started_at = clock()
    due_count = sum(1 for row in rows if row["action"] == "pending")
    assigned = 0
    projected_used = 0.0
    for row in rows:
        if row["action"] != "pending":
            continue
        assigned += 1
        remaining_due = due_count - assigned + 1
        backlog = int(row["backlog"])
        allowance = float(args.timeout)
        if budget_enabled:
            # A dry run cannot observe real durations, so it projects that every
            # domain consumes exactly its fair share; a real run uses elapsed time.
            consumed = projected_used if args.dry_run else clock() - started_at
            remaining = args.max_seconds - consumed
            if remaining <= 0:
                row["action"] = "skipped_budget"
                _log_row(row)
                continue
            allowance = remaining / remaining_due
            if allowance < args.seconds_per_item:
                if remaining_due > 1:
                    # Defer this domain: a smaller due set may still fit.
                    row["action"] = "skipped_budget"
                    _log_row(row)
                    continue
                allowance = remaining
                if allowance < args.seconds_per_item:
                    row["action"] = "skipped_budget"
                    _log_row(row)
                    continue
        batch = args.batch_size or _derive_batch_size(
            allowance, args.seconds_per_item, backlog, budget_enabled
        )
        if args.dry_run:
            row.update(action="would_run", budget_s=round(allowance, 1), batch_size=batch)
            projected_used += allowance
        else:
            timeout = max(1, int(min(args.timeout, allowance))) if budget_enabled else args.timeout
            exit_code, duration_s = run(
                ProcessRequest(
                    str(row["domain"]),
                    repo,
                    timeout,
                    batch,
                    args.since_days,
                    args.newest_first,
                )
            )
            row.update(
                action="run",
                budget_s=float(timeout),
                batch_size=batch,
                exit_code=exit_code,
                duration_s=duration_s,
            )
        _log_row(row)

    selected = sum(1 for row in rows if row["action"] in ("run", "would_run"))
    executed = sum(1 for row in rows if row["action"] == "run")
    failed = sum(1 for row in rows if row["action"] == "run" and row["exit_code"] != 0)
    skipped_budget = sum(1 for row in rows if row["action"] == "skipped_budget")
    report = {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "min_backlog": args.min_backlog,
        "max_seconds": args.max_seconds,
        "seconds_per_item": args.seconds_per_item,
        "batch_size": args.batch_size,
        "dry_run": args.dry_run,
        "domains_dir": str(domains_dir),
        "collections": str(collections),
        "db": str(db_path),
        "domains": rows,
        "summary": {
            "domains": len(rows),
            "selected": selected,
            "executed": executed,
            "failed": failed,
            "skipped": sum(1 for row in rows if row["action"] == "skip"),
            "skipped_budget": skipped_budget,
            "budget_exhausted": budget_enabled and skipped_budget > 0,
        },
    }

    md_text = _render_md(report)
    try:
        if args.json_out:
            out = Path(args.json_out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        if args.md_out:
            out = Path(args.md_out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(md_text, encoding="utf-8")
    except OSError as exc:
        print(f"nightly_process: failed to write report: {exc}", file=sys.stderr)
        return 2

    print(md_text)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
