"""REST API server — exposes AutoInfo capabilities over HTTP.

Usage::

    python -m autoinfo.api.server

The server listens on ``http://127.0.0.1:8741`` by default.
Port and host are configurable via ``.autoinfo/config.yaml`` under the
``rest_api`` key.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import uvicorn
import yaml
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

from autoinfo import __version__
from autoinfo.api.portal import router as portal_router
from autoinfo.api.routes import router as api_v1_router
from autoinfo.api.storefront import router as storefront_router
from autoinfo.config import RestAPIConfig

logger = logging.getLogger(__name__)

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

app.include_router(api_v1_router, prefix="/api/v1")

# ---------------------------------------------------------------------------
# Portal router — read-only end-user dashboard (Jinja2 + Bootstrap 5)
# ---------------------------------------------------------------------------

app.include_router(portal_router)

# ---------------------------------------------------------------------------
# Storefront router — end-user product catalog & subscription creation
# ---------------------------------------------------------------------------

app.include_router(storefront_router)

# ---------------------------------------------------------------------------
# Dashboard (read-only web UI)
# ---------------------------------------------------------------------------

_DASHBOARD_HTML_PATH = Path(__file__).resolve().parent / "dashboard.html"


def _load_dashboard_html() -> str:
    """Read the dashboard HTML file from disk (cached per-process)."""
    global _dashboard_html_cache
    if _dashboard_html_cache is None:
        if _DASHBOARD_HTML_PATH.is_file():
            _dashboard_html_cache = _DASHBOARD_HTML_PATH.read_text(encoding="utf-8")
        else:
            _dashboard_html_cache = (
                "<!doctype html><html><body>"
                "<h1>AutoInfo Dashboard</h1>"
                "<p>dashboard.html not found at "
                f"{_DASHBOARD_HTML_PATH}</p>"
                "</body></html>"
            )
    return _dashboard_html_cache


_dashboard_html_cache: str | None = None


@app.get("/", response_class=HTMLResponse)
async def dashboard_root() -> str:
    """Serve the read-only dashboard at the site root."""
    return _load_dashboard_html()


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard() -> str:
    """Serve the read-only dashboard at ``/dashboard``."""
    return _load_dashboard_html()


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


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics() -> str:
    """Prometheus-format metrics for scraping."""
    from autoinfo.metrics import format_prometheus, get_metrics

    data = get_metrics()
    return format_prometheus(data)


# ---------------------------------------------------------------------------
# Stripe webhook endpoint
# ---------------------------------------------------------------------------


@app.post("/api/v1/webhook/stripe")
async def stripe_webhook(request: Request) -> JSONResponse:
    """Accept Stripe webhook events with signature verification.

    Verifies the webhook signature using ``stripe.Webhook.construct_event``.
    When ``STRIPE_WEBHOOK_SECRET`` is not configured, verification is
    skipped and a warning is logged (dev/stripe-mock mode).

    Returns a ``JSONResponse`` on invalid signature (400) or the result
    dict from :func:`autoinfo.billing.handle_webhook` on success.
    """
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature", "")

    # --- Resolve webhook secret ------------------------------------------------
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

    if not webhook_secret:
        # Try config file as fallback
        try:
            from autoinfo.config import get_config_path, load_config

            config_path = get_config_path()
            if config_path:
                cfg = load_config(config_path)
                webhook_secret = cfg.stripe.webhook_secret
        except Exception:
            logger.debug(
                "Could not load stripe.webhook_secret from config", exc_info=True,
            )

    # --- Signature verification ------------------------------------------------
    if webhook_secret:
        try:
            import stripe

            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except ValueError as exc:
            logger.warning("Stripe webhook: invalid payload: %s", exc)
            return JSONResponse(
                status_code=400,
                content={"error": "invalid_signature", "detail": str(exc)},
            )
        except stripe.error.SignatureVerificationError as exc:
            logger.warning("Stripe webhook: signature verification failed: %s", exc)
            return JSONResponse(
                status_code=400,
                content={"error": "invalid_signature", "detail": str(exc)},
            )
    else:
        # Dev mode: no secret configured — parse raw JSON
        logger.warning(
            "STRIPE_WEBHOOK_SECRET not set — "
            "skipping signature verification (dev mode)",
        )
        try:
            event = json.loads(payload)
        except json.JSONDecodeError as exc:
            return JSONResponse(
                status_code=400,
                content={"error": "invalid_payload", "detail": str(exc)},
            )

    # --- Dispatch to billing handler -------------------------------------------
    from autoinfo.billing import handle_webhook

    result = handle_webhook(dict(event))
    return JSONResponse(content=result)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Start the REST API server via ``uvicorn.run()``."""
    cfg = _load_rest_config()
    logger.info(
        "Starting AutoInfo API on http://%s:%d",
        cfg.host,
        cfg.port,
    )
    uvicorn.run(app, host=cfg.host, port=cfg.port)


if __name__ == "__main__":
    main()
