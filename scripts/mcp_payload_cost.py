"""Measure the MCP ``tools/list`` payload cost (issue #562).

A token count is only meaningful together with the tokenizer and the exact
serialization, so both are pinned here. The measurement also fixes the view
(which tools the client may discover) and the shape:

Views
    ``director``  every tool declared by ``_full_tool_list()``
    ``agent``     the director-only surface removed (146 of 149)
    ``readonly``  only the ``_READONLY_TOOLS`` whitelist

Shapes
    ``wire``       ``tool.model_dump(mode="json", exclude_none=True)`` per tool,
                   including ``outputSchema``; compact JSON — what the server
                   actually sends.
    ``input-only`` ``{name, description, inputSchema}`` per tool with default
                   ``json.dumps`` separators — the shape the issue #562 repro
                   used, kept so its 25.8k figure stays reproducible.

Run ``.venv/bin/python scripts/mcp_payload_cost.py`` after any change to the
tool surface; the baseline is recorded in ``docs/dev/specs/mcp-tools.md``.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

ENCODINGS = ("cl100k_base", "o200k_base")


def _views() -> dict[str, list[Any]]:
    from autoinfo.mcp.server import _DIRECTOR_ONLY_TOOLS, _READONLY_TOOLS, _full_tool_list

    tools = list(_full_tool_list())
    return {
        "director": tools,
        "agent": [tool for tool in tools if tool.name not in _DIRECTOR_ONLY_TOOLS],
        "readonly": [tool for tool in tools if tool.name in _READONLY_TOOLS],
    }


def _input_only(tool: Any) -> dict[str, Any]:
    return {
        "name": tool.name,
        "description": tool.description or "",
        "inputSchema": tool.inputSchema or {},
    }


def _blob(payload: Any, *, compact: bool) -> bytes:
    if compact:
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    return json.dumps(payload, ensure_ascii=False).encode()


def _tokens(blob: bytes, encoding: str) -> int | None:
    try:
        import tiktoken
    except ImportError:
        return None
    return len(tiktoken.get_encoding(encoding).encode(blob.decode("utf-8")))


def measure() -> dict[str, Any]:
    views = _views()
    rows: dict[str, Any] = {}

    def record(name: str, payload: Any, *, compact: bool, tools: int) -> None:
        blob = _blob(payload, compact=compact)
        rows[name] = {
            "tools": tools,
            "bytes": len(blob),
            "tokens": {encoding: _tokens(blob, encoding) for encoding in ENCODINGS},
        }

    for view, tools in views.items():
        wire = [tool.model_dump(mode="json", exclude_none=True) for tool in tools]
        record(f"{view}/wire", {"tools": wire}, compact=True, tools=len(tools))
        record(
            f"{view}/input-only",
            {"tools": [_input_only(tool) for tool in tools]},
            compact=False,
            tools=len(tools),
        )

    director_wire = [tool.model_dump(mode="json", exclude_none=True) for tool in views["director"]]
    without = [
        {key: value for key, value in item.items() if key != "outputSchema"}
        for item in director_wire
    ]
    record(
        "director/wire-without-output-schema",
        {"tools": without},
        compact=True,
        tools=len(without),
    )

    schemas = {
        json.dumps(item["outputSchema"], sort_keys=True)
        for item in director_wire
        if "outputSchema" in item
    }
    full_bytes = rows["director/wire"]["bytes"]
    without_bytes = rows["director/wire-without-output-schema"]["bytes"]
    return {
        "views": {view: len(tools) for view, tools in views.items()},
        "rows": rows,
        "output_schema": {
            "present": sum("outputSchema" in item for item in director_wire),
            "distinct": len(schemas),
            "share_of_payload": round((full_bytes - without_bytes) / full_bytes, 4),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measure the MCP tools/list payload cost.")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    data = measure()
    if args.json:
        print(json.dumps(data, indent=2))
        return 0

    header = f"{'view':<9} {'shape':<27} {'tools':>5} {'bytes':>8} " + " ".join(
        f"{encoding:>11}" for encoding in ENCODINGS
    )
    print(header)
    for name, row in data["rows"].items():
        view, shape = name.split("/", 1)
        tokens = " ".join(
            f"{(row['tokens'][encoding] if row['tokens'][encoding] is not None else '-'):>11}"
            for encoding in ENCODINGS
        )
        print(f"{view:<9} {shape:<27} {row['tools']:>5} {row['bytes']:>8} {tokens}")

    schema = data["output_schema"]
    print(
        f"\noutputSchema: present on {schema['present']} tools, {schema['distinct']} distinct, "
        f"{schema['share_of_payload']:.1%} of the director wire payload"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
