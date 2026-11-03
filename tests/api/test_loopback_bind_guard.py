# mypy: ignore-errors
"""Tests for the REST API loopback bind guard (issue #680, ADR-0012).

AutoInfo is a single-tenant, locally operated agent tool; its trust boundary
is the OS process plus loopback HTTP.  These tests lock the serve-path
behavior:

1. A loopback bind (the default) starts as before, with allow-all CORS —
   the localhost security zone.
2. A non-loopback bind without ``AUTOINFO_ALLOW_NON_LOOPBACK=1`` refuses to
   start: non-zero exit, an actionable stderr message, no server.
3. A confirmed non-loopback bind starts with a WARN log and CORS narrowed
   from ``*`` to the configured origins (``rest_api.cors_origins`` /
   ``AUTOINFO_CORS_ORIGINS``); unset origins deny every cross-origin request.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from autoinfo.api import server as api_server

# ---------------------------------------------------------------------------
# Isolation fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _restore_app_cors() -> Iterator[None]:
    """Keep the module-level app's middleware stack pristine across tests.

    Starlette assembles the middleware stack lazily on first use and caches
    it; resetting ``middleware_stack`` forces a rebuild from the (restored)
    ``user_middleware`` list so mutations in one test never leak into another.
    """
    saved_middleware = list(api_server.app.user_middleware)
    yield
    api_server.app.user_middleware[:] = saved_middleware
    api_server.app.middleware_stack = None  # type: ignore[assignment]


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    """Pin the guard env vars to unset and read config from an empty directory."""
    monkeypatch.delenv("AUTOINFO_ALLOW_NON_LOOPBACK", raising=False)
    monkeypatch.delenv("AUTOINFO_CORS_ORIGINS", raising=False)
    monkeypatch.chdir(tmp_path)
    yield


@pytest.fixture
def uvicorn_run(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Capture the ``uvicorn.run`` call instead of starting a real server."""
    calls: dict[str, Any] = {}

    def fake_run(app: Any, host: str, port: int, **kwargs: Any) -> None:
        calls["host"] = host
        calls["port"] = port

    monkeypatch.setattr(api_server.uvicorn, "run", fake_run)
    return calls


def _cors_allow_origins() -> list[str]:
    """Return the ``allow_origins`` configured on the app's CORS middleware."""
    for mw in api_server.app.user_middleware:
        if mw.cls is CORSMiddleware:
            origins = mw.kwargs.get("allow_origins")
            assert isinstance(origins, list)
            return origins
    raise AssertionError("no CORS middleware on the app")


# ---------------------------------------------------------------------------
# 1. Loopback bind — the default posture is unchanged
# ---------------------------------------------------------------------------


def test_loopback_bind_starts_with_allow_all_cors(
    uvicorn_run: dict[str, Any], caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="autoinfo.api.server"):
        api_server.main(["--host", "127.0.0.1", "--port", "8999"])

    assert uvicorn_run["host"] == "127.0.0.1"
    assert uvicorn_run["port"] == 8999
    # The localhost security zone is unchanged for loopback binds.
    assert _cors_allow_origins() == ["*"]
    # The startup log states the loopback/CORS posture.
    posture = [r for r in caplog.records if "bind=loopback-only" in r.getMessage()]
    assert posture, "expected a loopback posture line in the startup log"


def test_localhost_and_loopback_range_are_loopback() -> None:
    assert api_server._is_loopback_host("127.0.0.1")
    assert api_server._is_loopback_host("localhost")
    assert api_server._is_loopback_host("::1")
    assert api_server._is_loopback_host("127.7.7.7")  # whole 127.0.0.0/8
    assert not api_server._is_loopback_host("0.0.0.0")
    assert not api_server._is_loopback_host("::")
    assert not api_server._is_loopback_host("192.168.1.10")
    assert not api_server._is_loopback_host("")  # uvicorn's "all interfaces"


# ---------------------------------------------------------------------------
# 2. Non-loopback bind without confirmation — refuse to start
# ---------------------------------------------------------------------------


def test_non_loopback_without_confirmation_refuses(
    uvicorn_run: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as excinfo:
        api_server.main(["--host", "0.0.0.0"])

    # Non-zero exit, no server, clean actionable message (no traceback).
    assert excinfo.value.code == 2
    assert uvicorn_run == {}
    err = capsys.readouterr().err
    assert "not a loopback address" in err
    assert "AUTOINFO_ALLOW_NON_LOOPBACK" in err
    assert "0.0.0.0" in err


def test_unconfirmed_bind_leaves_cors_untouched(
    uvicorn_run: dict[str, Any],
) -> None:
    with pytest.raises(SystemExit):
        api_server.main(["--host", "0.0.0.0"])
    # Refusal happens before any CORS mutation.
    assert _cors_allow_origins() == ["*"]


# ---------------------------------------------------------------------------
# 3. Confirmed non-loopback bind — WARN log + narrowed CORS, never "*"
# ---------------------------------------------------------------------------


def test_confirmed_non_loopback_warns_and_narrows_cors(
    uvicorn_run: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("AUTOINFO_ALLOW_NON_LOOPBACK", "1")
    monkeypatch.setenv("AUTOINFO_CORS_ORIGINS", "https://ops.example.com, https://dash.example.com")

    with caplog.at_level(logging.WARNING, logger="autoinfo.api.server"):
        api_server.main(["--host", "0.0.0.0", "--port", "8999"])

    assert uvicorn_run["host"] == "0.0.0.0"
    warnings = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING and "NON-LOOPBACK BIND" in r.getMessage()
    ]
    assert warnings, "expected a NON-LOOPBACK BIND warning in the startup log"

    # allow_origins is narrowed to the configured value, never "*".
    assert _cors_allow_origins() == ["https://ops.example.com", "https://dash.example.com"]
    client = TestClient(api_server.app)
    allowed = client.options(
        "/health",
        headers={
            "Origin": "https://ops.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert allowed.headers.get("access-control-allow-origin") == "https://ops.example.com"
    foreign = client.options(
        "/health",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert foreign.headers.get("access-control-allow-origin") != "*"


def test_confirmed_non_loopback_without_origins_denies_cors(
    uvicorn_run: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("AUTOINFO_ALLOW_NON_LOOPBACK", "1")

    with caplog.at_level(logging.WARNING, logger="autoinfo.api.server"):
        api_server.main(["--host", "0.0.0.0"])

    assert uvicorn_run["host"] == "0.0.0.0"
    # Unset cors_origins on a non-loopback bind = deny all cross-origin.
    assert _cors_allow_origins() == []
    client = TestClient(api_server.app)
    response = client.options(
        "/health",
        headers={
            "Origin": "https://ops.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in response.headers


# ---------------------------------------------------------------------------
# Config surface: rest_api.cors_origins parsing + env fallback
# ---------------------------------------------------------------------------


def test_rest_config_reads_cors_origins_from_yaml(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_dir = tmp_path / ".autoinfo"
    config_dir.mkdir()
    (config_dir / "config.yaml").write_text(
        "rest_api:\n"
        "  host: 127.0.0.1\n"
        "  port: 8741\n"
        "  cors_origins:\n"
        "    - https://ops.example.com\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("AUTOINFO_CORS_ORIGINS", raising=False)
    monkeypatch.chdir(tmp_path)

    cfg = api_server._load_rest_config()
    assert cfg.cors_origins == ("https://ops.example.com",)


def test_cors_origins_env_is_fallback_not_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_dir = tmp_path / ".autoinfo"
    config_dir.mkdir()
    (config_dir / "config.yaml").write_text(
        "rest_api:\n  host: 127.0.0.1\n  cors_origins:\n    - https://from-config.example.com\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AUTOINFO_CORS_ORIGINS", "https://from-env.example.com")
    monkeypatch.chdir(tmp_path)

    cfg = api_server._load_rest_config()
    # Config file wins over the environment (repo precedence).
    assert cfg.cors_origins == ("https://from-config.example.com",)
