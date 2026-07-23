"""Output CLI — generate digests, reports, tutorials, presentations, exports, and translations.

Usage::

    autoinfo output digest --domain medical --period weekly --format markdown
    autoinfo output report --domain medical --format html
    autoinfo output tutorial --domain medical --audience student
    autoinfo output presentation --domain medical --topic "IVF" --slides 10
    autoinfo output export --domain medical --format json
    autoinfo output export --domain medical --format markdown
    autoinfo output export --format json          # full KB
    autoinfo output translate --content-id X --target-lang zh
    autoinfo output translate --content "Hello" --source-lang en --target-lang fr
"""

from __future__ import annotations

import json

import typer

from autoinfo.output import export_kb

app = typer.Typer(help="Generate digests, reports, tutorials, presentations, exports, and translations")


@app.command(name="list-templates")
def list_templates(
    domain: str = typer.Option(
        "", "--domain", help="Optional domain filter"
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Output as JSON"
    ),
) -> None:
    """List available output templates."""
    from autoinfo.mcp.server import _handle_list_output_templates

    result = _handle_list_output_templates(domain=domain)
    if json_output:
        typer.echo(json.dumps(result, indent=2, ensure_ascii=False))
        return

    templates = result.get("templates", [])
    if not templates:
        typer.echo("No output templates available.")
        return

    typer.echo(f"Available output templates{(' for ' + domain) if domain else ''}:")
    for t in templates:
        typer.echo(f"  - {t}")


@app.command()
def digest(
    domain: str = typer.Option(..., "--domain", help="Domain to generate digest for"),
    period: str = typer.Option(
        "weekly", "--period", help="Digest period (daily, weekly, monthly)"
    ),
    format: str = typer.Option(
        "markdown", "--format", help="Output format (markdown, html, json)"
    ),
) -> None:
    """Generate a digest of KB entries for a domain over a given period.

    Queries the knowledge base for entries in the given period, optionally
    synthesizes them via LLM, and renders the result through a Jinja2 template.
    """
    from autoinfo.output import generate_digest

    try:
        result = generate_digest(domain=domain, period=period, format=format)
        typer.echo(result)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command()
def report(
    domain: str = typer.Option(..., "--domain", help="Domain to generate report for"),
    collection_id: str = typer.Option(
        None, "--collection-id", help="Optional collection ID to scope the report",
    ),
    format: str = typer.Option(
        "markdown", "--format", help="Output format (markdown or json)"
    ),
) -> None:
    """Generate a structured report with themed sections and executive summary.

    Groups KB entries by theme using LLM, generates per-section content,
    and renders through a Jinja2 template or returns a JSON structure.
    """
    from autoinfo.output import generate_report

    try:
        result = generate_report(
            domain=domain,
            collection_id=collection_id,
            format=format,
        )
        typer.echo(result)
    except (ValueError, FileNotFoundError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        typer.echo(f"Unexpected error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command()
def export(
    domain: str | None = typer.Option(
        None, "--domain", help="Domain to export (default: all domains)"
    ),
    format: str = typer.Option(
        "json", "--format", help="Export format (json, markdown, sqlite, pdf)"
    ),
) -> None:
    """Export knowledge base data to a file.

    Produces a JSON array, a Markdown tar.gz archive, a SQLite copy,
    or a PDF document in the ``exports/`` directory.
    """
    try:
        result = export_kb(domain=domain, format=format)
        typer.echo(
            f"Exported {result['entries_count']} entries "
            f"to {result['path']}"
        )
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command()
def translate(
    content_id: str | None = typer.Option(
        None, "--content-id", help="KB entry ID to translate"
    ),
    content: str | None = typer.Option(
        None, "--content", help="Raw text to translate directly"
    ),
    source_lang: str = typer.Option(
        "", "--source-lang", help="Source language code (e.g. en, zh)"
    ),
    target_lang: str = typer.Option(
        ..., "--target-lang", help="Target language code (e.g. zh, fr, ja)"
    ),
    domain: str = typer.Option(
        "", "--domain", help="Domain name for terminology guardrails (e.g. medical-research)"
    ),
) -> None:
    """Translate a KB entry or raw text into a target language.

    Two modes:

    \b
    1. Content-ID mode (stores translation):
       autoinfo output translate --content-id kb-entry-001 --target-lang zh

    2. Direct content mode (returns only):
       autoinfo output translate --content "Hello" --source-lang en --target-lang fr
    """
    from autoinfo.output import localize_content

    try:
        result = localize_content(
            content_id=content_id,
            content=content,
            source_lang=source_lang,
            target_lang=target_lang,
            domain=domain,
        )
        if result.get("success"):
            typer.echo("Translation successful!")
            if result.get("translated_title"):
                typer.echo(f"  Title: {result['translated_title']}")
            if result.get("file_path"):
                typer.echo(f"  Saved to: {result['file_path']}")
            if result.get("translated_body"):
                # Print first 500 chars as preview
                body = result["translated_body"]
                preview = body[:500] + ("..." if len(body) > 500 else "")
                typer.echo(f"  Preview: {preview}")
        else:
            typer.echo(f"Translation failed: {result.get('error', 'Unknown error')}", err=True)
            raise typer.Exit(code=1)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        typer.echo(f"Unexpected error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command()
def tutorial(
    domain: str = typer.Option(..., "--domain", help="Domain to generate tutorial for"),
    target_audience: str = typer.Option(
        "student",
        "--audience",
        help="Target audience: researcher, clinician, executive, student",
    ),
    collection_id: str = typer.Option(
        None, "--collection-id", help="Optional collection ID to scope the tutorial",
    ),
    format: str = typer.Option(
        "markdown", "--format", help="Output format (markdown only currently)"
    ),
) -> None:
    """Generate a structured tutorial adapted to the target audience.

    Fetches KB entries, uses LLM to structure a learning path with
    objectives, content sections, and exercises, and renders through
    a Jinja2 template.
    """
    from autoinfo.output import generate_tutorial

    try:
        result = generate_tutorial(
            domain=domain,
            collection_id=collection_id,
            target_audience=target_audience,
            format=format,
        )
        typer.echo(result)
    except (ValueError, FileNotFoundError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        typer.echo(f"Unexpected error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command()
def presentation(
    domain: str = typer.Option(..., "--domain", help="Domain to scope the presentation"),
    topic: str = typer.Option(..., "--topic", help="Presentation topic"),
    slide_count: int = typer.Option(
        10, "--slides", help="Number of slides (3-30, default: 10)"
    ),
    target_audience: str = typer.Option(
        "executive",
        "--audience",
        help="Target audience: researcher, clinician, executive, student",
    ),
    format: str = typer.Option(
        "markdown", "--format", help="Output format (markdown only currently)"
    ),
) -> None:
    """Generate a slide-based presentation on a topic.

    Searches KB for topic-related entries, uses LLM to produce
    structured slide content, and renders through a Jinja2 template.
    """
    from autoinfo.output import generate_presentation

    try:
        result = generate_presentation(
            domain=domain,
            topic=topic,
            slide_count=slide_count,
            target_audience=target_audience,
            format=format,
        )
        typer.echo(result)
    except (ValueError, FileNotFoundError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        typer.echo(f"Unexpected error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
