"""REST API server — exposes AutoInfo capabilities over HTTP.

Usage::

    python -m autoinfo.api.server

The server listens on ``http://127.0.0.1:8741`` by default.
Port and host are configurable via ``.autoinfo/config.yaml`` under the
``rest_api`` key.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from autoinfo import __version__

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# RestAPIConfig — imported from autoinfo.config (Task 3)
# ---------------------------------------------------------------------------

from autoinfo.config import RestAPIConfig


# ---------------------------------------------------------------------------
# Config I/O (mirrors mcp/server.py pattern)
# ---------------------------------------------------------------------------


def _config_path() -> Path:
    """Return the path to the project's ``.autoinfo/config.yaml``."""
    return Path.cwd() / ".autoinfo" / "config.yaml"


def _load_rest_config() -> RestAPIConfig:
    """Load REST API config from ``.autoinfo/config.yaml``.

    Looks for a ``rest_api`` section with ``port`` and ``host`` keys.
    When the config file is absent or the section is missing, falls back
    to defaults (127.0.0.1:8741).

    Once Task 3 adds ``rest_api`` to the :class:`Config` dataclass, the
    ``getattr`` path below will return the parsed ``RestAPIConfig``
    directly from YAML.
    """
    config_path = _config_path()
    if not config_path.is_file():
        logger.info("No config found at %s, using defaults", config_path)
        return RestAPIConfig()

    # Try the structured Config object first (Task 3+)
    try:
        from autoinfo.config import load_config

        config = load_config(config_path)
        rest_api: Any = getattr(config, "rest_api", None)
        if rest_api is not None and isinstance(rest_api, RestAPIConfig):
            return rest_api
    except Exception:
        logger.debug("Could not load rest_api from Config object", exc_info=True)

    # Fall back to reading raw YAML
    try:
        import yaml

        with open(config_path, "r", encoding="utf-8") as fh:
            raw: dict[str, Any] = yaml.safe_load(fh) or {}
        rest_api_raw: dict[str, Any] = raw.get("rest_api", {}) or {}
        return RestAPIConfig(
            port=int(rest_api_raw.get("port", 8741)),
            host=str(rest_api_raw.get("host", "127.0.0.1")),
        )
    except Exception:
        logger.warning("Failed to parse rest_api config, using defaults", exc_info=True)
        return RestAPIConfig()


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

_server_start_time: float = time.time()

app = FastAPI(title="AutoInfo API", version=__version__)

# -- CORS: allow all origins (localhost security zone) ------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# API v1 Router
# ---------------------------------------------------------------------------

from autoinfo.api.routes import router as api_v1_router

app.include_router(api_v1_router, prefix="/api/v1")

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> dict[str, Any]:
    """Quick status ping — returns version and server uptime."""
    return {
        "status": "ok",
        "version": __version__,
        "uptime_s": round(time.time() - _server_start_time, 2),
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Start the REST API server via ``uvicorn.run()``."""
    import uvicorn

    cfg = _load_rest_config()
    logger.info(
        "Starting AutoInfo API on http://%s:%d",
        cfg.host,
        cfg.port,
    )
    uvicorn.run(app, host=cfg.host, port=cfg.port)


if __name__ == "__main__":
    main()
