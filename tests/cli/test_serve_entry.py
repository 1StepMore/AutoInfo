"""AutoInfo#972: `autoinfo serve` must start the MCP server, not print help.

A bare `autoinfo serve` used to hit ``no_args_is_help=True`` on the Typer
sub-app, print usage and exit 0 — so an MCP client configured with
``command=autoinfo, args=[serve]`` got a process that never answers
``initialize``. ``python -m autoinfo.mcp.server`` worked, which is why no
existing test noticed.

These tests drive the CLI the way a client does: a real subprocess, a real
stdio handshake.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "serve-probe", "version": "1"},
    },
}


def _cli(*args: str, payload: str = "", timeout: int = 180) -> subprocess.CompletedProcess:
    """Invoke the Typer app in a subprocess, stdin fed with ``payload``."""
    env = dict(os.environ)
    env.pop("AUTOINFO_TESTING", None)
    return subprocess.run(
        [sys.executable, "-c", "from autoinfo.cli import app; app()", *args],
        input=payload,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
        env=env,
    )


def test_serve_starts_the_mcp_server(tmp_path: Path):
    """`autoinfo serve` must answer initialize with serverInfo (#972)."""
    proc = _cli("serve", payload=json.dumps(_INITIALIZE) + "\n")
    assert "serverInfo" in proc.stdout, (
        "autoinfo serve did not answer initialize — it printed help and exited\n"
        f"stdout={proc.stdout[:600]!r}\nstderr={proc.stderr[:400]!r}"
    )
    assert "Usage: " not in proc.stdout.split("\n")[1], "serve fell back to printing usage"


def test_serve_help_still_works():
    """--help must still render, and advertise a single command (no phantom COMMAND)."""
    proc = _cli("serve", "--help")
    assert proc.returncode == 0
    assert "Usage:" in proc.stdout
    assert "COMMAND" not in proc.stdout, (
        "usage still advertises a COMMAND argument while serve has no subcommands"
    )
