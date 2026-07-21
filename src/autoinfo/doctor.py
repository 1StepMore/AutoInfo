"""System health diagnostics.

Provides ``run_doctor()`` used by ``autoinfo doctor`` to validate the
runtime environment, configuration, LLM connectivity, and source
reachability.
"""

from __future__ import annotations

import os
import sqlite3
import sys
import time
from typing import Any

from pathlib import Path

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
