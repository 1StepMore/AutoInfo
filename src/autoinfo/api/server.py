"""REST API server — exposes AutoInfo capabilities over HTTP.

Usage::

    python -m autoinfo.api.server [--host HOST] [--port PORT]

The server listens on ``http://127.0.0.1:8741`` by default.
Port and host are configurable via ``.autoinfo/config.yaml`` under the
``rest_api`` key or the ``--host``/``--port`` flags.

AutoInfo is a single-tenant, locally operated agent tool (ADR-0012): the
trust boundary is the OS process plus loopback HTTP.  A non-loopback bind
is therefore refused at startup unless the operator explicitly confirms it
with ``AUTOINFO_ALLOW_NON_LOOPBACK=1`` — and a confirmed non-loopback bind
never serves allow-all CORS: it serves exactly the origins configured via
``rest_api.cors_origins`` (or ``AUTOINFO_CORS_ORIGINS``), defaulting to
none, which denies every cross-origin browser request.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import logging
import os
import sys
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, cast

import uvicorn
import yaml
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse

from autoinfo import __version__
from autoinfo.api.portal import router as portal_router
from autoinfo.api.routes import router as api_v1_router
from autoinfo.api.storefront import router as storefront_router
from autoinfo.config import RestAPIConfig, parse_cors_origins
from autoinfo.mcp.errors import ErrorCode

logger = logging.getLogger(__name__)

#: Explicit operator confirmation required for a non-loopback bind (ADR-0012
#: residual risk follow-up, issue #680).  Anything else refuses to start.
ALLOW_NON_LOOPBACK_ENV = "AUTOINFO_ALLOW_NON_LOOPBACK"

#: Comma-separated CORS origins, consulted when ``rest_api.cors_origins`` is
#: unset.  Config file wins over the environment (repo precedence).
CORS_ORIGINS_ENV = "AUTOINFO_CORS_ORIGINS"

# ---------------------------------------------------------------------------
# Config I/O (mirrors mcp/server.py pattern)
# ---------------------------------------------------------------------------


def _config_path() -> Path:
    """Return the path to the project's ``.autoinfo/config.yaml``."""
    return Path.cwd() / ".autoinfo" / "config.yaml"


def _load_rest_config() -> RestAPIConfig:
    """Load REST API config from ``.autoinfo/config.yaml`` plus env fallbacks.

    Looks for a ``rest_api`` section with ``port``, ``host`` and
    ``cors_origins`` keys.  When the config file is absent or the section is
    missing, falls back to defaults (127.0.0.1:8741, no CORS origins).  The
    config file wins over the environment (repo precedence): CORS origins
    fall back to ``AUTOINFO_CORS_ORIGINS`` only when the section does not
    configure them.
    """
    cfg = _read_rest_config()
    if not cfg.cors_origins:
        env_raw = os.environ.get(CORS_ORIGINS_ENV, "").strip()
        if env_raw:
            cfg.cors_origins = parse_cors_origins(env_raw)
    return cfg


def _read_rest_config() -> RestAPIConfig:
    """Read the ``rest_api`` section from ``.autoinfo/config.yaml``."""
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
            cors_origins=parse_cors_origins(rest_api_raw.get("cors_origins")),
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
# Domain validation helper — shared between middleware and routes
# ---------------------------------------------------------------------------


def _known_domains() -> set[str]:
    """Return the set of known domain names.

    Checks configured domains in ``.autoinfo/config.yaml`` first,
    then falls back to scanning the ``knowledge/`` directory for
    directories that represent domain namespaces.
    """
    domains: set[str] = set()

    # -- From config -----------------------------------------------------------
    try:
        from autoinfo.config import get_config_path, load_config

        config_path = get_config_path()
        if config_path and config_path.is_file():
            config = load_config(config_path)
            for d in config.domains:
                domains.add(d.name)
    except Exception:
        logger.debug("Could not load domains from config", exc_info=True)

    # -- From filesystem (fallback) -------------------------------------------
    kb_dir = Path("knowledge")
    if kb_dir.is_dir():
        for entry in kb_dir.iterdir():
            if entry.is_dir() and not entry.name.startswith("."):
                domains.add(entry.name)

    return domains


# ---------------------------------------------------------------------------
# HTTP middleware — domain precondition check for domain-specific routes
# ---------------------------------------------------------------------------


@app.middleware("http")
async def domain_validation_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Validate that the ``domain`` query parameter refers to an existing domain.

    Only applies to ``/api/v1/*`` GET and DELETE routes that accept a
    ``domain`` query parameter.  Returns ``404 DOMAIN_NOT_FOUND`` when
    a domain value is provided but not recognised.

    POST routes handle domain validation inline (the middleware cannot
    safely read the request body).
    """
    path = request.url.path
    if request.method in ("GET", "DELETE") and path.startswith("/api/v1/"):
        domain = request.query_params.get("domain", "").strip()
        if domain:
            known = _known_domains()
            if domain not in known:
                return _error_envelope(
                    status_code=404,
                    error_code=ErrorCode.DOMAIN_NOT_FOUND,
                    message=(
                        f"Domain '{domain}' not found. "
                        f"Use add_domain(name='{domain}') to create it."
                    ),
                )

    return await call_next(request)


# ---------------------------------------------------------------------------
# Exception handlers — canonical {success, error: {code, message}} envelope
# ---------------------------------------------------------------------------


def _error_envelope(
    status_code: int,
    error_code: str | ErrorCode,
    message: str,
    actionable: bool = True,
) -> JSONResponse:
    """Build a JSONResponse with the canonical error envelope."""
    code_str = error_code.value if isinstance(error_code, ErrorCode) else error_code
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {
                "code": code_str,
                "message": message,
                "actionable": actionable,
            },
        },
    )


def _success_envelope(data: Any) -> dict[str, Any]:
    """Build the canonical success envelope ``{success: True, data: ...}``.

    Mirrors :func:`autoinfo.mcp.errors.success_response` — the REST-side
    counterpart of the MCP envelope.  Pairs with :func:`_error_envelope`
    which returns the error counterpart.  ``/health`` is the single
    documented exemption (flat ops probe, mirrors MCP ``health_check``).
    """
    return {"success": True, "data": data}


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Map FastAPI ``RequestValidationError`` → 422 with canonical envelope.

    FastAPI's default 422 body is a bare ``{detail: [...]}`` list; the M1
    contract requires every REST error to carry the canonical
    ``{success: False, error: {code, message, actionable}}`` envelope.
    The first validation error is summarized into a readable message
    (e.g. ``body.title: Field required``).
    """
    errors = exc.errors()
    first = errors[0] if errors else {}
    loc = ".".join(str(part) for part in first.get("loc", []))
    msg = str(first.get("msg", "Request validation failed"))
    message = f"{loc}: {msg}" if loc else msg
    logger.warning(
        "RequestValidationError in %s %s (422): %s",
        request.method,
        request.url.path,
        message,
    )
    return _error_envelope(
        status_code=422,
        error_code=ErrorCode.VALIDATION_ERROR,
        message=message,
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Map FastAPI HTTPException → same status with canonical envelope."""
    code = ErrorCode.VALIDATION_ERROR if 400 <= exc.status_code < 500 else ErrorCode.INTERNAL_ERROR
    logger.warning(
        "HTTPException in %s %s (%d): %s",
        request.method,
        request.url.path,
        exc.status_code,
        exc.detail,
    )
    return _error_envelope(
        status_code=exc.status_code,
        error_code=code,
        message=str(exc.detail),
        actionable=exc.status_code < 500,
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Map ValueError → 400 Bad Request."""
    logger.warning(
        "ValueError in %s %s: %s",
        request.method,
        request.url.path,
        exc,
    )
    return _error_envelope(
        status_code=400,
        error_code=ErrorCode.VALIDATION_ERROR,
        message=str(exc),
    )


@app.exception_handler(KeyError)
async def key_error_handler(request: Request, exc: KeyError) -> JSONResponse:
    """Map KeyError → 400 Bad Request."""
    logger.warning(
        "KeyError in %s %s: %s",
        request.method,
        request.url.path,
        exc,
    )
    return _error_envelope(
        status_code=400,
        error_code=ErrorCode.VALIDATION_ERROR,
        message=str(exc),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler for all unhandled exceptions → 500."""
    logger.error(
        "Unhandled exception in %s %s: %s",
        request.method,
        request.url.path,
        exc,
        exc_info=True,
    )
    return _error_envelope(
        status_code=500,
        error_code=ErrorCode.INTERNAL_ERROR,
        message=str(exc) if str(exc) else "An unhandled server error occurred.",
        actionable=False,
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
# Media serving — podcast MP3 hosting
# ---------------------------------------------------------------------------

# Allowed root directories for media file serving (security: prevent
# path traversal outside these directories).
_MEDIA_ROOTS: tuple[Path, ...] = (
    Path("exports"),
    Path("data"),
)


@app.get("/media/{file_path:path}")
async def serve_media(file_path: str) -> FileResponse:
    """Serve a static media file (e.g. podcast MP3) from ``exports/`` or ``data/``.

    Security: only serves files from allowed media root directories.
    Returns 404 when the path escapes the allowed roots or the file
    does not exist.
    """
    cwd = Path.cwd().resolve()
    resolved_abs = (cwd / file_path).resolve()

    allowed = False
    for media_root in _MEDIA_ROOTS:
        try:
            root_abs = (cwd / media_root).resolve()
            if str(resolved_abs).startswith(str(root_abs) + os.sep) or resolved_abs == root_abs:
                if resolved_abs.is_file():
                    allowed = True
                    break
        except (ValueError, OSError):
            continue

    if not allowed:
        raise HTTPException(
            status_code=404,
            detail=f"Media file not found: {file_path}",
        )

    return FileResponse(
        path=str(resolved_abs),
        media_type="audio/mpeg",
        headers={"Accept-Ranges": "bytes"},
    )


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
                "Could not load stripe.webhook_secret from config",
                exc_info=True,
            )

    # --- Signature verification ------------------------------------------------
    if webhook_secret:
        try:
            import stripe

            # ``stripe.Webhook.construct_event`` ships without annotations
            # upstream, so bind it to an explicitly ``Any``-typed name rather
            # than suppressing a strict-mode error at the call site.
            construct_event: Any = stripe.Webhook.construct_event
            event = construct_event(payload, sig_header, webhook_secret)
        except ValueError as exc:
            logger.warning("Stripe webhook: invalid payload: %s", exc)
            return _error_envelope(
                status_code=400,
                error_code=ErrorCode.VALIDATION_ERROR,
                message=f"invalid_signature: {exc}",
            )
        except stripe.error.SignatureVerificationError as exc:
            logger.warning("Stripe webhook: signature verification failed: %s", exc)
            return _error_envelope(
                status_code=400,
                error_code=ErrorCode.VALIDATION_ERROR,
                message=f"invalid_signature: {exc}",
            )
    else:
        # Dev mode: no secret configured — parse raw JSON
        logger.warning(
            "STRIPE_WEBHOOK_SECRET not set — skipping signature verification (dev mode)",
        )
        try:
            event = json.loads(payload)
        except json.JSONDecodeError as exc:
            return _error_envelope(
                status_code=400,
                error_code=ErrorCode.VALIDATION_ERROR,
                message=f"invalid_payload: {exc}",
            )

    # --- Dispatch to billing handler -------------------------------------------
    from autoinfo.billing import handle_webhook

    # ``construct_event`` returns a ``StripeObject`` (not a ``dict``); dev mode
    # and test doubles hand over a plain ``dict``.  Normalize both shapes.
    event_dict: dict[str, Any] = event.to_dict() if hasattr(event, "to_dict") else dict(event)
    result = handle_webhook(event_dict)
    return JSONResponse(content=result)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse serve entry-point flags (``.autoinfo/config.yaml`` stays the default)."""
    parser = argparse.ArgumentParser(
        prog="python -m autoinfo.api.server",
        description=(
            "Start the AutoInfo REST API server "
            "(single-tenant, loopback bind by default — ADR-0012)."
        ),
    )
    parser.add_argument(
        "--host",
        default=None,
        help=(
            "Bind address (default: rest_api.host from .autoinfo/config.yaml, else 127.0.0.1). "
            "A non-loopback bind requires AUTOINFO_ALLOW_NON_LOOPBACK=1."
        ),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Bind port (default: rest_api.port from .autoinfo/config.yaml, else 8741)",
    )
    return parser.parse_args(argv)


def _is_loopback_host(host: str) -> bool:
    """True when *host* binds to loopback only.

    ``localhost`` and the whole IPv4/IPv6 loopback ranges (``127.0.0.0/8``,
    ``::1``) count; anything else — including ``0.0.0.0``, ``::`` and an empty
    host — exposes the server beyond the ADR-0012 trust boundary.
    """
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host.strip()).is_loopback
    except ValueError:
        return False


def _enforce_loopback_bind(host: str) -> None:
    """Refuse a non-loopback bind unless the operator explicitly confirmed.

    AutoInfo is a single-tenant, locally operated agent tool (ADR-0012): the
    trust boundary is the OS process plus loopback HTTP, and the REST API has
    no authentication.  A non-loopback bind turns the server into a real
    exposure and must never start silently — the operator confirms it via
    ``AUTOINFO_ALLOW_NON_LOOPBACK=1``, ideally only behind an authenticated
    reverse proxy.
    """
    if _is_loopback_host(host):
        return
    confirmed = os.environ.get(ALLOW_NON_LOOPBACK_ENV, "").strip().lower()
    if confirmed in {"1", "true", "yes", "on"}:
        return
    sys.stderr.write(
        f"AutoInfo API refused to start: host {host!r} is not a loopback address.\n"
        "\n"
        "AutoInfo is a single-tenant, locally operated agent tool (ADR-0012); its trust\n"
        "boundary is the OS process plus loopback HTTP, and the REST API has no\n"
        "authentication. A non-loopback bind exposes it beyond the local machine and\n"
        "is not supported.\n"
        "\n"
        "If you really need a non-loopback bind, place an authenticated reverse proxy\n"
        f"in front and set {ALLOW_NON_LOOPBACK_ENV}=1; narrow CORS via rest_api.cors_origins\n"
        f"in .autoinfo/config.yaml or {CORS_ORIGINS_ENV}.\n"
    )
    raise SystemExit(2)


def _resolve_cors_origins(host: str, configured: tuple[str, ...]) -> tuple[str, ...]:
    """Effective ``allow_origins`` for the resolved bind address.

    A loopback bind keeps the historical allow-all: only local origins can
    reach a loopback socket, so ``*`` stays inside the ADR-0012 trust
    boundary.  A non-loopback bind never serves ``*`` (issue #680) — it
    serves exactly the configured origins, defaulting to none, which denies
    every cross-origin browser request until the operator narrows in real
    origins.
    """
    if _is_loopback_host(host):
        return ("*",)
    return tuple(configured)


def _apply_cors(origins: tuple[str, ...]) -> None:
    """Rebuild the app's CORS middleware with *origins*.

    ``app`` is module-level with the loopback allow-all baked in; the
    middleware stack is assembled lazily on startup, so replacing the CORS
    entry here — before ``uvicorn.run`` — is the serve-time narrowing point.
    Dropping any previously built stack forces a rebuild from the updated
    list (Starlette refuses ``add_middleware`` once a stack exists).
    """
    app.middleware_stack = None
    # ``Middleware.cls`` is typed as a generic factory; cast to a plain class
    # object so the identity comparison typechecks.
    app.user_middleware[:] = [
        mw for mw in app.user_middleware if cast("type[Any]", mw.cls) is not CORSMiddleware
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _ensure_posture_logging() -> logging.Logger:
    """Return the module logger with one console handler for posture lines.

    Under a bare ``uvicorn.run`` uvicorn configures only its own loggers, so
    the module logger has no handler — INFO would be dropped and the operator
    would never see the bind/CORS posture.  Attach one stderr handler at INFO
    so the posture prints next to uvicorn's own lines.  Existing handlers
    (tests, embedding hosts) are left untouched.
    """
    posture_logger = logging.getLogger(__name__)
    if not posture_logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(levelname)-8s %(message)s"))
        posture_logger.addHandler(handler)
    if posture_logger.level == logging.NOTSET or posture_logger.level > logging.INFO:
        posture_logger.setLevel(logging.INFO)
    return posture_logger


def main(argv: list[str] | None = None) -> None:
    """Start the REST API server via ``uvicorn.run()``."""
    args = _parse_args(argv)
    cfg = _load_rest_config()
    if args.host is not None:
        cfg.host = args.host
    if args.port is not None:
        cfg.port = args.port

    _enforce_loopback_bind(cfg.host)
    origins = _resolve_cors_origins(cfg.host, cfg.cors_origins)
    _apply_cors(origins)

    # Posture lines through a module-logger console handler: under a bare
    # ``uvicorn.run`` uvicorn configures only its own loggers, so an INFO
    # posture line would otherwise be dropped (WARNING+ survive via
    # ``lastResort``) and the operator would never see the bind/CORS posture.
    console = _ensure_posture_logging()
    if _is_loopback_host(cfg.host):
        console.info(
            "Starting AutoInfo API on http://%s:%d "
            "(bind=loopback-only, CORS=allow-all inside the localhost security zone — ADR-0012)",
            cfg.host,
            cfg.port,
        )
    else:
        console.warning(
            "NON-LOOPBACK BIND: AutoInfo API serves on http://%s:%d "
            "(%s=1 accepted). Single-tenant local tool with no authentication — "
            "keep an authenticated reverse proxy in front. CORS allow_origins=%s "
            "(configure via rest_api.cors_origins in .autoinfo/config.yaml or %s; "
            "empty denies all cross-origin requests).",
            cfg.host,
            cfg.port,
            ALLOW_NON_LOOPBACK_ENV,
            list(origins),
            CORS_ORIGINS_ENV,
        )

    uvicorn.run(app, host=cfg.host, port=cfg.port)


if __name__ == "__main__":
    main()
