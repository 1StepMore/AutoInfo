"""Structured JSON logging for the AutoInfo pipeline.

Provides a :class:`PipelineLogger` that writes JSON log lines to daily
rotated files (``logs/pipeline-{YYYY-MM-DD}.log``).  The factory function
:func:`get_pipeline_logger` returns a logger instance for a named module.

Usage::

    from autoinfo.logging import get_pipeline_logger

    plog = get_pipeline_logger("collect")
    plog.info("Collection started", extra={"domain": "medical"})
    plog.info("Source collected", item_id="abc123", source_type="pubmed",
              duration_ms=1520.3)
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

# Re-export standard logging so callers can do ``from autoinfo.logging import logging``
# when they need stdlib logging alongside the pipeline logger.
logging = logging

_LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
_LOG_LOCK = threading.Lock()
_LOGGERS: dict[str, "PipelineLogger"] = {}


class PipelineLogger:
    """Structured JSON logger for pipeline operations.

    Each log entry is a single JSON line written to a daily rotated file at
    ``logs/pipeline-{YYYY-MM-DD}.log``.

    Parameters
    ----------
    name : str
        Module / component name (appears in the ``module`` field of every
        log entry).
    """

    def __init__(self, name: str) -> None:
        self._name = name
        _LOG_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public logging methods
    # ------------------------------------------------------------------

    def debug(
        self,
        message: str,
        *,
        item_id: Optional[str] = None,
        source_type: Optional[str] = None,
        duration_ms: Optional[float] = None,
        extra: Optional[dict[str, Any]] = None,
        trace_id: Optional[str] = None,
    ) -> None:
        """Write a DEBUG-level structured log entry."""
        self._log("DEBUG", message, item_id, source_type, duration_ms, extra, trace_id)

    def info(
        self,
        message: str,
        *,
        item_id: Optional[str] = None,
        source_type: Optional[str] = None,
        duration_ms: Optional[float] = None,
        extra: Optional[dict[str, Any]] = None,
        trace_id: Optional[str] = None,
    ) -> None:
        """Write an INFO-level structured log entry."""
        self._log("INFO", message, item_id, source_type, duration_ms, extra, trace_id)

    def warning(
        self,
        message: str,
        *,
        item_id: Optional[str] = None,
        source_type: Optional[str] = None,
        duration_ms: Optional[float] = None,
        extra: Optional[dict[str, Any]] = None,
        trace_id: Optional[str] = None,
    ) -> None:
        """Write a WARNING-level structured log entry."""
        self._log("WARNING", message, item_id, source_type, duration_ms, extra, trace_id)

    def error(
        self,
        message: str,
        *,
        item_id: Optional[str] = None,
        source_type: Optional[str] = None,
        duration_ms: Optional[float] = None,
        extra: Optional[dict[str, Any]] = None,
        trace_id: Optional[str] = None,
    ) -> None:
        """Write an ERROR-level structured log entry."""
        self._log("ERROR", message, item_id, source_type, duration_ms, extra, trace_id)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _log(
        self,
        level: str,
        message: str,
        item_id: Optional[str] = None,
        source_type: Optional[str] = None,
        duration_ms: Optional[float] = None,
        extra: Optional[dict[str, Any]] = None,
        trace_id: Optional[str] = None,
    ) -> None:
        """Build the JSON entry, serialise, and append to the daily log file."""
        entry: dict[str, Any] = {
            "timestamp": datetime.now().astimezone().isoformat(),
            "level": level,
            "module": self._name,
            "message": message,
        }
        if item_id is not None:
            entry["item_id"] = item_id
        if source_type is not None:
            entry["source_type"] = source_type
        if duration_ms is not None:
            entry["duration_ms"] = duration_ms
        if trace_id is not None:
            entry["trace_id"] = trace_id
        if extra:
            entry["extra"] = extra

        log_path = _LOG_DIR / f"pipeline-{date.today().isoformat()}.log"

        # Thread-safe append
        with _LOG_LOCK:
            with open(log_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")


def get_pipeline_logger(name: str) -> PipelineLogger:
    """Return a :class:`PipelineLogger` instance for the given *name*.

    Loggers are cached so that repeated calls with the same *name* return
    the same instance.
    """
    if name not in _LOGGERS:
        _LOGGERS[name] = PipelineLogger(name)
    return _LOGGERS[name]
