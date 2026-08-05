"""Q&A over collected content CLI — mirror of the MCP ``query_collected`` tool.

Usage::

    autoinfo query-collected --query "What are the latest IVF breakthroughs?" \
        --domain medical-research
    autoinfo query-collected --query "X" --domain medical-research --json

Search is FTS5-scoped to the domain, and the LLM synthesises an answer with
``[1]``/``[2]`` source citations. The tool requires an LLM key — when none is
configured the command fails gracefully with the same guidance the MCP
dispatch returns (``LLM_NOT_CONFIGURED``), never a raw auth error.
"""

from __future__ import annotations

import json

import typer

app = typer.Typer(
    name="query-collected",
    help="Q&A over collected content (FTS5 + LLM) — mirrors MCP query_collected",
)


@app.callback(invoke_without_command=True)
def query_collected(  # noqa: A001 — mirrors the MCP tool name
    query: str = typer.Option(
        ..., "--query", help="Natural-language question to answer"
    ),
    domain: str = typer.Option(
        ..., "--domain", help="Domain to scope the search to (e.g. medical-research)"
    ),
    content_ids: list[str] = typer.Option(
        [],
        "--content-ids",
        help="Optional explicit entry IDs to use instead of FTS5 search (repeatable)",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Search collected content and synthesise an answer with citations.

    Mirrors the MCP ``query_collected`` tool: FTS5 retrieval (top 5) followed
    by LLM synthesis. Parameter names are identical (query, domain,
    content_ids).
    """
    # Graceful LLM_NOT_CONFIGURED guard — same config resolution as the MCP
    # dispatch guard (server.py _is_llm_configured) and the keywords CLI.
    from autoinfo.config import get_config_path, load_config

    try:
        config_path = get_config_path()
        if config_path:
            config = load_config(config_path)
            api_key = config.llm.api_key or ""
        else:
            api_key = ""
    except Exception:  # noqa: BLE001 — fails closed like _is_llm_configured
        api_key = ""

    import os

    if not (api_key or os.environ.get("AUTOINFO_LLM_API_KEY")):
        message = (
            "LLM is not configured. Use 'configure_llm()' or set "
            "AUTOINFO_LLM_API_KEY to set up your API key. See "
            "docs/dev/required-api-keys.md for the full list of API keys "
            "and environment variables."
        )
        if json_output:
            typer.echo(
                json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "LLMNotConfigured",
                            "message": message,
                            "actionable": True,
                        },
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            )
        else:
            typer.echo(f"Error: {message}", err=True)
        raise typer.Exit(code=1)

    # Deferred import — mirrors the MCP handler
    from autoinfo.qa import query_collected as _qa

    result = _qa(query=query, domain=domain, content_ids=content_ids or None)

    if json_output:
        typer.echo(json.dumps(result, indent=2, ensure_ascii=False))
        return

    typer.echo(result.get("answer", ""))
    sources = result.get("sources", [])
    typer.echo("")
    typer.echo(f"Sources ({len(sources)}):")
    for idx, source in enumerate(sources, start=1):
        typer.echo(f"  [{idx}] {source.get('title', '')} ({source.get('entry_id', '')})")
