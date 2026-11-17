"""User-level dotenv loading — credentials decoupled from IDE restarts.

AutoInfo reads configuration exclusively from the process environment
(``os.environ``).  On harnesses that freeze the process environment at IDE
start (the Windows harness does — issue #847), rotating an API key via
``setx`` requires restarting the IDE before agents see the new value.
This module lets the owner keep credentials in a user-level env file
instead: ``~/.autoinfo/.env`` is read at CLI / MCP-server startup and
merged into ``os.environ`` **without overwriting** anything the process
environment already provides.

Precedence (highest wins)::

    process environment  >  ~/.autoinfo/.env

Supported file syntax (a deliberate subset — no inline comments, no
variable interpolation, no multi-line values): ``KEY=VALUE`` lines,
``#`` full-line comments, blank lines, optional ``export `` prefix,
optional paired single/double quotes around the value.  Keys must match
``[A-Za-z_][A-Za-z0-9_]*``.  Malformed lines are skipped, never fatal.

The file carries secrets: nothing here ever logs or returns values —
diagnostics report the path and loaded key names only.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

__all__ = ["USER_ENV_FILE", "load_user_env", "parse_env_text"]

USER_ENV_FILE = Path.home() / ".autoinfo" / ".env"

_KEY_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def parse_env_text(text: str) -> dict[str, str]:
    """Parse dotenv-format text into a ``{KEY: VALUE}`` dict.

    See the module docstring for the supported subset.  Malformed lines
    (no ``=``, empty key, non-identifier key) are skipped, never fatal.
    """
    pairs: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, sep, value = line.partition("=")
        if not sep:
            continue
        key = key.strip()
        if not _KEY_RE.fullmatch(key):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        pairs[key] = value
    return pairs


def load_user_env(path: Path | None = None) -> list[str]:
    """Load the user env file into ``os.environ`` without overriding it.

    Only keys absent from the process environment are set (setdefault
    semantics — the process environment always wins).  A missing file is
    a no-op; an unreadable file warns on stderr and is skipped.  Returns
    the list of key names that were loaded from the file (values are
    never included — the file carries secrets).
    """
    env_path = Path(path) if path is not None else USER_ENV_FILE
    try:
        text = env_path.read_text(encoding="utf-8-sig", errors="replace")
    except FileNotFoundError:
        return []
    except OSError as exc:
        print(f"autoinfo: user env file unreadable, skipped: {env_path} ({exc})", file=sys.stderr)
        return []
    loaded: list[str] = []
    for key, value in parse_env_text(text).items():
        if key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
    return loaded
