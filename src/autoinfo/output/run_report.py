"""Structured run/session report — B2.6 / F69, TR-A-01/TR-A-02.

A *session* is one correlated execution of the validation engine:

* **single** — one ``run_validation_scenario`` run, where the session id is the
  run's own ``trace_id``;
* **suite** — one aggregate ``run_all_validation_scenarios`` run, where a single
  generated session id is threaded into every scenario (:func:`run_scenario`)
  and every step, so the whole library run shares one correlation id.

The report answers the B2.6 question — *what ran, what were the verdicts, what
went wrong* — as machine-readable JSON, and is queryable by the correlation id
via ``get_run_decisions``.  Every step and scenario verdict carries the
``session_id``, so one id reconstructs the full A1–A7 action sequence.

This module is **pure stdlib** (no AutoInfo imports, no third-party deps) so the
validation engine and the MCP layer can both use it without import cycles or
heavy package side effects.  Persistence is one JSON file per session under
``validation-runs/sessions/<session_id>.json``.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any, Iterable

#: Sub-directory of the runs dir that holds per-session reports.
SESSION_DIRNAME = "sessions"

#: Canonical report filename inside a session directory.
REPORT_FILENAME = "run-report.json"

#: Default runs base (repo-root ``validation-runs``) — mirrors
#: ``autoinfo.mcp.validation.VALIDATION_RUNS_DIR`` without importing it.
DEFAULT_RUNS_DIR: Path = Path(__file__).resolve().parents[3] / "validation-runs"

#: Decision classes that ``anomalies`` reports (never a silent "all clean").
ANOMALY_SCENARIO_FAILED = "scenario_failed"
ANOMALY_STEP_FAILED = "step_failed"
ANOMALY_TIMEOUT = "timeout"
ANOMALY_UNCONFIGURED = "unconfigured"
ANOMALY_RECOVERED = "recovered"
ANOMALY_WARNING = "warning"


def _runs_dir(runs_dir: Path | str | None) -> Path:
    """Resolve the runs base directory (defaults to repo-root ``validation-runs``)."""
    return Path(runs_dir) if runs_dir is not None else DEFAULT_RUNS_DIR


def sessions_dir(runs_dir: Path | str | None = None) -> Path:
    """Return the ``<runs_dir>/sessions`` directory (may not exist yet)."""
    return _runs_dir(runs_dir) / SESSION_DIRNAME


def _now_iso() -> str:
    """Current local timestamp, second resolution (stable, human-readable)."""
    return datetime.datetime.now().isoformat(timespec="seconds")


def _jsonable(value: Any) -> Any:
    """Coerce *value* into a JSON-safe structure (dicts/lists walked)."""
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return str(value)


def _truncate(value: Any, limit: int = 500) -> Any:
    """Truncate a rendered detail string so the report stays bounded."""
    if isinstance(value, str) and len(value) > limit:
        return value[:limit] + "…"
    return value


def _iter_steps(result: dict[str, Any]) -> Iterable[tuple[str, dict[str, Any]]]:
    """Yield ``(step_kind, step)`` for main, recovery and cleanup steps.

    ``step_kind`` is one of ``"step"`` (a primary step), ``"recovery"`` (a
    recovery step nested under its primary) or ``"cleanup"`` (a cleanup step).
    Recovery steps are yielded immediately after their primary so the ordered
    decision trail matches execution order.
    """
    for step in result.get("steps", []) or []:
        yield "step", step
        for rec in step.get("recovery", []) or []:
            yield "recovery", rec
    cleanup = result.get("cleanup")
    if isinstance(cleanup, dict):
        for step in cleanup.get("steps", []) or []:
            yield "cleanup", step


def _step_decision(
    seq: int,
    session_id: str,
    scenario: str | None,
    step_kind: str,
    step: dict[str, Any],
) -> dict[str, Any]:
    """Build one step-level decision record."""
    recovered = bool(step.get("recovered"))
    status = step.get("status")
    return {
        "seq": seq,
        "level": "step",
        "session_id": session_id,
        "scenario": scenario,
        "step_kind": step_kind,
        "step_index": step.get("step_index"),
        "step_id": step.get("step_id"),
        "tool": step.get("tool"),
        "decision": "recovered" if recovered else status,
        "status": status,
        "recovered": recovered,
        "trace_id": step.get("trace_id"),
        "detail": _truncate(_jsonable(step.get("detail"))),
    }


def _scenario_decision(
    seq: int,
    session_id: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Build the scenario-level decision that opens that scenario's trail."""
    return {
        "seq": seq,
        "level": "scenario",
        "session_id": session_id,
        "scenario": result.get("scenario"),
        "decision": result.get("status"),
        "status": result.get("status"),
        "pipeline_stage": result.get("pipeline_stage"),
        "user_level": result.get("user_level"),
        "pyramid_layer": result.get("pyramid_layer"),
        "category": result.get("category"),
        "trace_id": result.get("trace_id"),
        "detail": _truncate(_jsonable(result.get("unconfigured_reason"))),
    }


def _scenario_verdict(result: dict[str, Any]) -> dict[str, Any]:
    """Compact per-scenario verdict row for the report's ``verdicts`` list."""
    summary = result.get("summary") or {}
    return {
        "scenario": result.get("scenario"),
        "status": result.get("status"),
        "category": result.get("category"),
        "pipeline_stage": result.get("pipeline_stage"),
        "user_level": result.get("user_level"),
        "pyramid_layer": result.get("pyramid_layer"),
        "trace_id": result.get("trace_id"),
        "session_id": result.get("session_id"),
        "summary": _jsonable(summary),
        "regression": bool(result.get("regression", False)),
    }


def _collect_anomalies(session_id: str, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Enumerate every anomaly of the session, ordered by occurrence.

    An anomaly is anything a director must be able to see without re-reading
    the raw run: a failed scenario, a failed/timeout step, an unconfigured
    scenario/step, a recovered step, or a run warning (e.g. the leak guard).
    An all-green session yields an empty list — that is a fact, not silence.
    """
    anomalies: list[dict[str, Any]] = []
    for result in results:
        scenario = result.get("scenario")
        if result.get("status") == "failed":
            anomalies.append(
                {
                    "kind": ANOMALY_SCENARIO_FAILED,
                    "session_id": session_id,
                    "scenario": scenario,
                    "detail": _truncate(_jsonable(result.get("unconfigured_reason"))),
                }
            )
        elif result.get("status") == "unconfigured":
            anomalies.append(
                {
                    "kind": ANOMALY_UNCONFIGURED,
                    "session_id": session_id,
                    "scenario": scenario,
                    "detail": _truncate(_jsonable(result.get("unconfigured_reason"))),
                }
            )
        for step_kind, step in _iter_steps(result):
            status = step.get("status")
            detail = _truncate(_jsonable(step.get("detail")))
            if step.get("recovered"):
                anomalies.append(
                    {
                        "kind": ANOMALY_RECOVERED,
                        "session_id": session_id,
                        "scenario": scenario,
                        "step_kind": step_kind,
                        "step_id": step.get("step_id"),
                        "tool": step.get("tool"),
                        "detail": detail,
                    }
                )
            elif status == "unconfigured":
                anomalies.append(
                    {
                        "kind": ANOMALY_UNCONFIGURED,
                        "session_id": session_id,
                        "scenario": scenario,
                        "step_kind": step_kind,
                        "step_id": step.get("step_id"),
                        "tool": step.get("tool"),
                        "detail": detail,
                    }
                )
            elif status == "failed":
                timed_out = isinstance(detail, str) and "timed out after" in detail
                anomalies.append(
                    {
                        "kind": (ANOMALY_TIMEOUT if timed_out else ANOMALY_STEP_FAILED),
                        "session_id": session_id,
                        "scenario": scenario,
                        "step_kind": step_kind,
                        "step_id": step.get("step_id"),
                        "tool": step.get("tool"),
                        "detail": detail,
                    }
                )
        for warning in result.get("warnings", []) or []:
            anomalies.append(
                {
                    "kind": ANOMALY_WARNING,
                    "session_id": session_id,
                    "scenario": scenario,
                    "detail": _truncate(_jsonable(warning)),
                }
            )
    return anomalies


def build_run_report(
    session_id: str,
    scenarios: list[dict[str, Any]],
    *,
    kind: str = "suite",
    started_at: str | None = None,
    finished_at: str | None = None,
    source_run: str | None = None,
) -> dict[str, Any]:
    """Build the structured B2.6 run report for one correlation id.

    Parameters
    ----------
    session_id:
        The correlation id shared by every scenario/step of this session.
        Must be non-empty — a report without a queryable id is not a report.
    scenarios:
        Per-scenario result envelopes (as returned by ``run_scenario``).
    kind:
        ``"suite"`` for an aggregate full-library run, ``"single"`` for one
        scenario.
    started_at / finished_at:
        ISO timestamps; default to now for ``finished_at`` and to
        ``finished_at`` for ``started_at`` when omitted.
    source_run:
        Optional run directory path the report was derived from.

    Returns
    -------
    dict
        ``{session_id, kind, started_at, finished_at, duration_seconds,
        summary, verdicts, decisions, anomalies}``.  ``summary`` counts scenario
        verdicts plus the anomaly total; ``decisions`` is the ordered trail
        (scenario verdict then its steps); ``anomalies`` is the non-silent
        failure/recovery/warning list.
    """
    if not session_id or not str(session_id).strip():
        raise ValueError("build_run_report requires a non-empty session_id")
    session_id = str(session_id)

    finished = finished_at or _now_iso()
    started = started_at or finished
    results = list(scenarios)

    summary = {"passed": 0, "failed": 0, "unconfigured": 0, "recovered": 0}
    for result in results:
        status = result.get("status")
        if status in summary:
            summary[status] += 1
        step_summary = result.get("summary") or {}
        summary["recovered"] += int(step_summary.get("recovered", 0) or 0)
    summary["total"] = len(results)

    decisions: list[dict[str, Any]] = []
    seq = 0
    for result in results:
        seq += 1
        decisions.append(_scenario_decision(seq, session_id, result))
        for step_kind, step in _iter_steps(result):
            seq += 1
            decisions.append(
                _step_decision(seq, session_id, result.get("scenario"), step_kind, step)
            )

    anomalies = _collect_anomalies(session_id, results)
    summary["anomalies"] = len(anomalies)

    report: dict[str, Any] = {
        "session_id": session_id,
        "kind": kind,
        "started_at": started,
        "finished_at": finished,
        "duration_seconds": _duration_seconds(started, finished),
        "summary": summary,
        "verdicts": [_scenario_verdict(result) for result in results],
        "decisions": decisions,
        "anomalies": anomalies,
    }
    if source_run:
        report["source_run"] = source_run
    return report


def _duration_seconds(started_at: str, finished_at: str) -> float | None:
    """Best-effort wall-clock duration between two ISO timestamps."""
    try:
        start = datetime.datetime.fromisoformat(started_at)
        end = datetime.datetime.fromisoformat(finished_at)
    except ValueError:
        return None
    return round((end - start).total_seconds(), 3)


def session_report_path(session_id: str, runs_dir: Path | str | None = None) -> Path:
    """Return the canonical report path for *session_id* (not written)."""
    return sessions_dir(runs_dir) / f"{session_id}.json"


def persist_run_report(report: dict[str, Any], runs_dir: Path | str | None = None) -> Path:
    """Persist *report* to ``<runs_dir>/sessions/<session_id>.json``.

    Returns the path written.  The report is validated for a session id so a
    nameless file can never be written (it would be unqueryable).
    """
    session_id = str(report.get("session_id") or "").strip()
    if not session_id:
        raise ValueError("persist_run_report: report has no session_id")
    path = session_report_path(session_id, runs_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_jsonable(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def load_run_report(  # noqa: PLR0912 - explicit fallback chain
    session_id: str, runs_dir: Path | str | None = None
) -> dict[str, Any] | None:
    """Load the report whose ``session_id`` matches *session_id*.

    Lookup order:

    1. ``<runs_dir>/sessions/<session_id>.json`` — the canonical report.
    2. Fallback: scan persisted runs for a ``scenarios.json`` whose payload
       ``session_id`` (or any scenario ``trace_id``/``session_id``) matches —
       so runs saved by the legacy per-run persistence are still queryable.

    Returns ``None`` when no match exists.
    """
    session_id = str(session_id or "").strip()
    if not session_id:
        return None

    path = session_report_path(session_id, runs_dir)
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
        except (json.JSONDecodeError, OSError):
            return None

    base = _runs_dir(runs_dir)
    if not base.is_dir():
        return None
    for run_dir in sorted(base.iterdir(), reverse=True):
        payload_path = run_dir / "scenarios.json"
        if not run_dir.is_dir() or not payload_path.is_file():
            continue
        try:
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        results = payload.get("scenarios") or []
        matches = payload.get("session_id") == session_id or any(
            r.get("session_id") == session_id or r.get("trace_id") == session_id for r in results
        )
        if not matches:
            continue
        return build_run_report(
            session_id,
            results,
            kind=str(payload.get("run_type") or "single"),
            source_run=str(run_dir),
        )
    return None


def list_run_reports(runs_dir: Path | str | None = None) -> list[Path]:
    """Return persisted session report paths, newest filename first."""
    base = sessions_dir(runs_dir)
    if not base.is_dir():
        return []
    return sorted(
        (p for p in base.glob("*.json") if p.is_file()),
        key=lambda p: p.name,
        reverse=True,
    )
