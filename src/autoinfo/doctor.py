"""System health diagnostics.

Provides ``run_doctor()`` used by ``autoinfo doctor`` to validate the
runtime environment, configuration, LLM connectivity, and source
reachability.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

from autoinfo.config import get_config_path, load_config, validate_config
from autoinfo.schema import get_schema_version as _get_schema_version

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_doctor() -> dict[str, Any]:
    """Run a comprehensive system health check.

    Returns
    -------
    dict
        A nested dict with per-check results::

            {
                "python": {"status": "ok" | "error", "version": str},
                "config": {"status": "ok" | "error", "path": str | None,
                           "errors": [str, ...]},
                "llm": {"status": "ok" | "error", "provider": str,
                        "model": str, "key_configured": bool},
                "sources": [
                    {"name": str, "status": "ok" | "error" | "skipped",
                     "latency_ms": float},
                ],
            }
    """
    results: dict[str, Any] = {}

    # -- Python version check -----------------------------------------------
    py_ok = sys.version_info[:2] >= (3, 11)
    results["python"] = {
        "status": "ok" if py_ok else "error",
        "version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    }

    # -- Config check -------------------------------------------------------
    config_path = get_config_path()
    config_errors: list[str] = []
    if config_path is None:
        config_errors.append("No configuration file found")
    else:
        try:
            config = load_config(config_path)
            config_errors = validate_config(config)
        except Exception as exc:
            config_errors.append(str(exc))

    results["config"] = {
        "status": "ok" if not config_errors else "error",
        "path": str(config_path) if config_path else None,
        "errors": config_errors,
    }

    # -- LLM key check ------------------------------------------------------
    llm_provider = ""
    llm_model = ""
    key_configured = False

    # Check env var first, then config
    env_key = os.environ.get("AUTOINFO_LLM_API_KEY", "")
    if env_key:
        key_configured = True

    if config_path:
        try:
            cfg = load_config(config_path)
            llm_provider = cfg.llm.provider
            llm_model = cfg.llm.model
            if cfg.llm.api_key and not key_configured:
                key_configured = True
        except Exception:
            pass

    results["llm"] = {
        "status": "ok" if key_configured else "error",
        "provider": llm_provider,
        "model": llm_model,
        "key_configured": key_configured,
    }

    # -- Source reachability checks -----------------------------------------
    sources_status: list[dict[str, Any]] = []
    if config_path and not config_errors:
        try:
            cfg = load_config(config_path)
            for domain in cfg.domains:
                if not domain.active:
                    continue
                for src in domain.sources:
                    src_result = _check_source(src.url, src.name)
                    sources_status.append(src_result)
        except Exception:
            pass

    results["sources"] = sources_status

    # -- KB database schema version -------------------------------------------
    schema_ver: int | None = None
    try:
        # Default KB database is autoinfo.db alongside knowledge/
        kb_path = Path("autoinfo.db")
        if kb_path.is_file():
            conn = sqlite3.connect(str(kb_path))
            try:
                schema_ver = _get_schema_version(conn)
            finally:
                conn.close()
    except Exception:
        pass
    results["schema_version"] = schema_ver

    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_TIMEOUT_S = 10


def _check_source(url: str, name: str) -> dict[str, Any]:
    """Check if a source URL is reachable with a HEAD request.

    Returns a dict with ``name``, ``status``, and ``latency_ms``.
    """
    if not url:
        return {
            "name": name,
            "status": "skipped",
            "latency_ms": 0.0,
            "detail": "No URL configured",
        }

    try:
        import httpx

        start = time.time()
        with httpx.Client(timeout=_TIMEOUT_S, verify=False) as client:
            resp = client.head(url, follow_redirects=True)
        elapsed = (time.time() - start) * 1000

        if resp.status_code < 500:
            status = "ok"
        else:
            status = "error"

        return {
            "name": name,
            "status": status,
            "latency_ms": round(elapsed, 1),
            "status_code": resp.status_code,
        }
    except Exception as exc:
        return {
            "name": name,
            "status": "error",
            "latency_ms": 0.0,
            "detail": str(exc),
        }


def diagnose_pipeline(deep: bool = False) -> dict[str, Any]:
    """Extended pipeline diagnostics: run history, error rates, latency, source health, cost.

    All metrics are derived from real stores:

    * ``logs/pipeline-*.log`` — structured JSON pipeline logs written by
      :mod:`autoinfo.logging` (one JSON line per event, ``level`` /
      ``module`` / ``message`` / optional ``duration_ms`` fields).
    * ``collections/**/_runs.json`` — collection run records written by
      :func:`autoinfo.collect._log_run` (``status``, ``errors``,
      ``duration_ms`` per run).
    * CostMeter cost log (LLM tokens / API calls) via
      :meth:`autoinfo.cost.CostMeter.get_report`.

    Parameters
    ----------
    deep : bool
        If True, include source health aggregation and cost summaries.

    Returns
    -------
    dict
        Pipeline diagnostics data with ``status``, ``health_score``,
        ``error_rates`` (total_runs/total_errors/error_pct + per-stage
        breakdown), ``latency`` (min/p50/p95/p99/max/avg ms), ``run_history``
        (recent pipeline log entries), ``source_health`` and ``cost``
        (when *deep*).  When a store holds no data the corresponding section
        carries ``data_available: False`` instead of fabricated zeros.
    """
    run_history = _load_run_history()
    error_rates = compute_error_rates()
    latency = compute_latency_percentiles()

    result: dict[str, Any] = {
        "status": "ok",
        "deep": deep,
        "health_score": 100,
        "run_history": run_history,
        "error_rates": error_rates,
        "latency": latency,
    }

    # -- status + health_score derived from the real error rate --------------
    err = error_rates
    error_pct = float(err.get("error_pct", 0.0))
    data_available = bool(err.get("data_available"))
    if not data_available:
        result["status"] = "no_data"
    elif error_pct == 0.0:
        result["status"] = "ok"
    elif error_pct < 10.0:
        result["status"] = "degraded"
    else:
        result["status"] = "error"
    result["health_score"] = max(0, 100 - int(error_pct * 5))

    if deep:
        result["source_health"] = _compute_source_health()
        result["cost"] = _compute_cost_summary()

    return result


# ---------------------------------------------------------------------------
# Real diagnostics helpers (error rates / latency from available stores)
# ---------------------------------------------------------------------------


def _pipeline_log_dir() -> Path:
    """Locate the structured pipeline log directory (``logs/`` at repo root)."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    log_dir = repo_root / "logs"
    if log_dir.is_dir():
        return log_dir
    return Path("logs")


def _load_run_history(limit: int = 50) -> list[dict[str, Any]]:
    """Load the most recent pipeline log entries (newest first).

    Reads ``logs/pipeline-*.log`` — the JSON structured log written by
    :mod:`autoinfo.logging` (daily rotation, one JSON object per line).
    """
    entries: list[dict[str, Any]] = []
    log_dir = _pipeline_log_dir()
    if not log_dir.is_dir():
        return entries
    for log_file in sorted(log_dir.glob("pipeline-*.log")):
        try:
            with open(log_file, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(entry, dict):
                        entries.append(entry)
        except OSError:
            continue
    entries.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
    return entries[:limit]


def _load_collection_runs() -> list[dict[str, Any]]:
    """Load all collection run records from ``collections/**/_runs.json``.

    Each record is written by :func:`autoinfo.collect._log_run` and carries
    ``status`` (success/skipped/error), ``errors``, ``duration_ms`` and
    ``timestamp``.  Records missing the newer fields (legacy format) are
    treated as successful runs without latency samples.
    """
    runs: list[dict[str, Any]] = []
    runs_dir = Path("collections")
    if not runs_dir.is_dir():
        return runs
    for runs_file in sorted(runs_dir.rglob("_runs.json")):
        try:
            data = json.loads(runs_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError):
            continue
        if isinstance(data, list):
            runs.extend(entry for entry in data if isinstance(entry, dict))
    return runs


def compute_error_rates() -> dict[str, Any]:
    """Compute real error rates from pipeline logs and collection run logs.

    Returns
    -------
    dict
        Keys: ``total_runs`` (pipeline log events + collection runs),
        ``total_errors``, ``error_pct``, ``data_available`` plus a
        ``by_stage`` breakdown keyed by pipeline stage ("collection",
        "processing", "delivery") with per-stage ``total``/``errors``/
        ``error_pct``.
    """
    log_entries = _load_run_history(limit=None)
    runs = _load_collection_runs()

    # Stage classification: module of the pipeline log entry.
    stage_modules: dict[str, tuple[str, ...]] = {
        "collection": ("collect",),
        "processing": ("process", "llm"),
        "delivery": ("delivery",),
    }

    stage_totals: dict[str, int] = {s: 0 for s in stage_modules}
    stage_errors: dict[str, int] = {s: 0 for s in stage_modules}
    total_events = len(log_entries)
    log_errors = 0
    for entry in log_entries:
        level = entry.get("level", "")
        module = str(entry.get("module", ""))
        if level == "ERROR":
            log_errors += 1
            for stage, modules in stage_modules.items():
                if module in modules:
                    stage_errors[stage] += 1
        for stage, modules in stage_modules.items():
            if module in modules:
                stage_totals[stage] += 1

    run_total = len(runs)
    run_errors = 0
    for run in runs:
        status = run.get("status")
        errors = run.get("errors")
        # Legacy run records predate the status/errors fields — count as success.
        if status not in (None, "success") or (isinstance(errors, list) and errors):
            run_errors += 1

    total_runs = total_events + run_total
    total_errors = log_errors + run_errors
    error_pct = round(total_errors * 100.0 / total_runs, 2) if total_runs else 0.0

    by_stage: dict[str, dict[str, float | int]] = {}
    for stage in stage_modules:
        st_total = stage_totals[stage]
        st_errors = stage_errors[stage]
        by_stage[stage] = {
            "total": st_total,
            "errors": st_errors,
            "error_pct": round(st_errors * 100.0 / st_total, 2) if st_total else 0.0,
        }

    return {
        "total_runs": total_runs,
        "total_errors": total_errors,
        "error_pct": error_pct,
        "log_events": total_events,
        "log_errors": log_errors,
        "collection_runs": run_total,
        "collection_run_errors": run_errors,
        "by_stage": by_stage,
        "data_available": total_runs > 0,
    }


def _percentile(sorted_values: list[float], pct: float) -> float:
    """Return the *pct*-th percentile of a sorted list (linear interpolation)."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = (len(sorted_values) - 1) * pct / 100.0
    lower = int(rank)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = rank - lower
    return sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight


def compute_latency_percentiles() -> dict[str, Any]:
    """Compute latency percentiles (p50/p95/p99) from recorded durations.

    Latency samples are collected from:

    * ``duration_ms`` fields on pipeline log entries
      (:mod:`autoinfo.logging` schema — e.g. "Source collected" events).
    * ``duration_ms`` fields on collection run records
      (``collections/**/_runs.json``).

    When no samples exist the result carries ``data_available: False`` and
    zero percentiles rather than fabricated numbers.
    """
    samples: list[float] = []

    for entry in _load_run_history(limit=None):
        dur = entry.get("duration_ms")
        if isinstance(dur, (int, float)) and dur >= 0:
            samples.append(float(dur))

    for run in _load_collection_runs():
        dur = run.get("duration_ms")
        if isinstance(dur, (int, float)) and dur >= 0:
            samples.append(float(dur))

    result: dict[str, Any] = {
        "count": len(samples),
        "min_ms": 0.0,
        "p50_ms": 0.0,
        "p95_ms": 0.0,
        "p99_ms": 0.0,
        "max_ms": 0.0,
        "avg_ms": 0.0,
        "data_available": bool(samples),
    }
    if samples:
        ordered = sorted(samples)
        result["min_ms"] = round(ordered[0], 1)
        result["max_ms"] = round(ordered[-1], 1)
        result["avg_ms"] = round(sum(samples) / len(samples), 1)
        result["p50_ms"] = round(_percentile(ordered, 50), 1)
        result["p95_ms"] = round(_percentile(ordered, 95), 1)
        result["p99_ms"] = round(_percentile(ordered, 99), 1)
    return result


def _compute_source_health() -> list[dict[str, Any]]:
    """Aggregate per-source health from collection run records.

    Sources are identified by the directory name under ``collections/``
    (the run record's parent directory).  Status mapping: no runs →
    ``"unknown"``; all runs successful → ``"healthy"``; some failures →
    ``"degraded"``; every run failed → ``"error"``.
    """
    runs_dir = Path("collections")
    if not runs_dir.is_dir():
        return []
    per_source: dict[str, dict[str, Any]] = {}
    for runs_file in sorted(runs_dir.rglob("_runs.json")):
        name = runs_file.parent.name
        try:
            data = json.loads(runs_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError):
            continue
        if not isinstance(data, list):
            continue
        agg = per_source.setdefault(
            name,
            {"runs": 0, "errors": 0, "durations_ms": [], "latest": ""},
        )
        for entry in data:
            if not isinstance(entry, dict):
                continue
            agg["runs"] += 1
            status = entry.get("status")
            errors = entry.get("errors")
            if status not in (None, "success") or (
                isinstance(errors, list) and errors
            ):
                agg["errors"] += 1
            dur = entry.get("duration_ms")
            if isinstance(dur, (int, float)) and dur >= 0:
                agg["durations_ms"].append(float(dur))
            ts = entry.get("timestamp", "")
            if ts > agg["latest"]:
                agg["latest"] = ts

    health: list[dict[str, Any]] = []
    for name, agg in sorted(per_source.items()):
        if agg["runs"] == 0:
            status = "unknown"
        elif agg["errors"] == 0:
            status = "healthy"
        elif agg["errors"] < agg["runs"]:
            status = "degraded"
        else:
            status = "error"
        durations = agg["durations_ms"]
        health.append(
            {
                "name": name,
                "status": status,
                "error_count": agg["errors"],
                "total_runs": agg["runs"],
                "avg_response_time_ms": round(sum(durations) / len(durations), 1)
                if durations
                else 0.0,
                "latest_run": agg["latest"],
            }
        )
    return health


def _compute_cost_summary() -> dict[str, Any]:
    """Return a cost summary from the CostMeter cost log."""
    try:
        from autoinfo.cost import CostMeter

        meter = CostMeter()
        report = meter.get_report(period="all")
        if not isinstance(report, dict):
            return {"data_available": False}
        total_cost = report.get("total_cost", 0.0)
        summary: dict[str, Any] = {
            "total_cost": total_cost,
            "log_count": report.get("log_count", 0),
            "by_type": report.get("by_type", {}),
            "llm_models": report.get("llm_models", {}),
            "api_sources": report.get("api_sources", {}),
            "data_available": report.get("log_count", 0) > 0 or total_cost > 0,
        }
        return summary
    except Exception as exc:  # pragma: no cover - defensive
        return {"data_available": False, "error": str(exc)}
