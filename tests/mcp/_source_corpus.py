"""Source corpus for MCP static audits (#581 phase 3).

The envelope-conformance, error-code-enum, error-message, and dispatch-freeze
audits all scan the same modules: the server hub, the shared context helper
tier, and the per-domain tools modules. One corpus definition means a module
added to ``tools/`` is audited automatically, and no audit can go vacuously
green because code moved between files.

The corpus is a LIST of ``(path, text)`` pairs, never one concatenated string:
concatenating would raise ``SyntaxError: from __future__ imports must occur at
the beginning of the file`` and destroy per-file line numbers.
"""

from __future__ import annotations

from pathlib import Path

MCP_DIR = Path(__file__).resolve().parents[2] / "src" / "autoinfo" / "mcp"


def source_paths() -> list[Path]:
    """Return server.py, context.py, then every tools/*.py module."""
    tools = sorted((MCP_DIR / "tools").glob("*.py"))
    return [MCP_DIR / "server.py", MCP_DIR / "context.py", *tools]


def source_corpus() -> list[tuple[Path, str]]:
    """Return ``(path, text)`` pairs for every audited MCP source file."""
    return [(path, path.read_text(encoding="utf-8")) for path in source_paths()]
