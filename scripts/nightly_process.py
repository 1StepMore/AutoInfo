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
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

REPO = Path(__file__).resolve().parent.parent
DEFAULT_DOMAINS_DIR = REPO / "src" / "autoinfo" / "data" / "domains"
DEFAULT_COLLECTIONS = REPO / "collections"
DEFAULT_DB = REPO / "autoinfo.db"
DEFAULT_MIN_BACKLOG = 20
DEFAULT_TIMEOUT = 7200
SCHEMA = "autoinfo-nightly-process/1"

Runner = Callable[[str, Path, int], tuple[int, float]]


def domain_names(domains_dir: Path) -> list[str]:
    """Return configured domains (directories with a ``sources.yaml``)."""
    if not domains_dir.is_dir():
        return []
    return sorted(
        d.name for d in domains_dir.iterdir() if d.is_dir() and (d / "sources.yaml").is_file()
    )


def count_cached_items(collections: Path, domain: str) -> int:
    """Count usable cached item JSON files for one domain.

    Mirrors the loader's conventions: ``_runs.json`` and paths under a
    directory whose name starts with ``_`` are bookkeeping, not items.
    """
    root = collections / domain
    if not root.is_dir():
        return 0

    count = 0
    for path in root.rglob("*.json"):
        rel_parts = path.relative_to(root).parts
        if path.name.startswith("_"):
            continue
        if any(part.startswith("_") for part in rel_parts[:-1]):
            continue
        count += 1
    return count


def read_processed_count(db_path: Path, domain: str) -> int:
    """Read ``last_processed_index`` for a domain; 0 when unavailable."""
    if not db_path.is_file():
        return 0

    conn: sqlite3.Connection | None = None
    try:
        uri = db_path.resolve().as_uri() + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=5)
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


def _run_process(domain: str, repo: Path, timeout: int) -> tuple[int, float]:
    """Run ``autoinfo process --domain ... --resume-from auto``."""
    cmd = [
        *_autoinfo_cmd(sys.executable),
        "process",
        "--domain",
        domain,
        "--resume-from",
        "auto",
    ]
    started = time.monotonic()
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(repo),
            timeout=timeout,
            check=False,
        )
        return completed.returncode, round(time.monotonic() - started, 1)
    except subprocess.TimeoutExpired:
        return 124, round(time.monotonic() - started, 1)
    except OSError:
        return 127, round(time.monotonic() - started, 1)


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
        f"- dry run: {str(report['dry_run']).lower()}",
        f"- selected: {summary['selected']} / executed: {summary['executed']} / "
        f"failed: {summary['failed']} / skipped: {summary['skipped']}",
        "",
        "| domain | cached | processed | backlog | action | exit | seconds |",
        "|:---|---:|---:|---:|:---|---:|---:|",
    ]
    for row in rows:
        assert isinstance(row, dict)
        lines.append(
            f"| {row['domain']} | {row['cached_items']} | "
            f"{row['processed_count']} | {row['backlog']} | "
            f"{row['action']} | {row['exit_code']} | {row['duration_s']} |"
        )
    if not rows:
        lines += ["", "No configured domain has cached items."]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None, runner: Runner | None = None) -> int:
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
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Per-domain process timeout in seconds (default: {DEFAULT_TIMEOUT}).",
    )
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json-out", default="")
    ap.add_argument("--md-out", default="")
    args = ap.parse_args(argv)

    if args.min_backlog < 1:
        ap.error("--min-backlog must be >= 1")
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

    run = runner or _run_process
    rows: list[dict[str, object]] = []
    for domain in configured:
        cached = count_cached_items(collections, domain)
        if cached == 0:
            continue
        processed = read_processed_count(db_path, domain)
        backlog = max(0, cached - processed)
        should_run = backlog >= args.min_backlog

        if not should_run:
            action = "skip"
            exit_code = 0
            duration_s = 0.0
        elif args.dry_run:
            action = "would_run"
            exit_code = 0
            duration_s = 0.0
        else:
            action = "run"
            exit_code, duration_s = run(domain, repo, args.timeout)

        print(
            f"[nightly-process] {domain}: cached={cached} "
            f"processed={processed} backlog={backlog} -> {action}",
            flush=True,
        )
        rows.append(
            {
                "domain": domain,
                "cached_items": cached,
                "processed_count": processed,
                "backlog": backlog,
                "action": action,
                "exit_code": exit_code,
                "duration_s": duration_s,
            }
        )

    selected = sum(1 for row in rows if row["action"] in ("run", "would_run"))
    executed = sum(1 for row in rows if row["action"] == "run")
    failed = sum(1 for row in rows if row["action"] == "run" and row["exit_code"] != 0)
    report = {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "min_backlog": args.min_backlog,
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
            "skipped": len(rows) - selected,
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
