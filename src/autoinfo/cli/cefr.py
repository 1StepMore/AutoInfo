from __future__ import annotations

"""CEFR classification CLI — classify text difficulty levels (A1-C2).

Usage::

    autoinfo cefr classify "Hello, how are you?" --lang en
    autoinfo cefr classify "今天天气很好" --lang zh
"""

import json

import typer

from autoinfo.cefr import classify_text

app = typer.Typer(
    name="cefr",
    help="CEFR text classification (A1-C2) for language learning content",
)


@app.command()
def classify(
    text: str = typer.Argument(..., help="Text to classify"),
    lang: str = typer.Option("en", "--lang", help="Language code: en, zh, ja"),
) -> None:
    """Classify text into a CEFR level (A1-C2) using the configured LLM."""
    result = classify_text(text=text, lang=lang)
    output = {
        "cefr_level": result["cefr_level"],
        "confidence": result["confidence"],
        "text_preview": text[:100] + "..." if len(text) > 100 else text,
    }
    typer.echo(json.dumps(output, indent=2, ensure_ascii=False))


@app.command()
def batch(
    texts: list[str] = typer.Option([], "--texts", help="Text(s) to classify (repeatable)"),
    input: str | None = typer.Option(None, "--input", help="File path to read texts from (one per line)"),
    lang: str = typer.Option("en", "--lang", help="Language code: en, zh, ja"),
    output: str | None = typer.Option(None, "--output", help="Output file path (JSON array)"),
) -> None:
    """Batch classify multiple texts into CEFR levels (A1-C2).

    Provide texts via --texts (repeatable) or --input (file, one per line).
    Results are output as a JSON array of {text, cefr_level, confidence} dicts.
    Per-text errors are included in the array with an \"error\" key.
    """
    # --- Collect input texts --------------------------------------------------
    all_texts: list[str] = list(texts)

    if input is not None:
        try:
            with open(input, "r", encoding="utf-8") as fh:
                for line in fh:
                    stripped = line.strip()
                    if stripped:
                        all_texts.append(stripped)
        except FileNotFoundError:
            typer.echo(json.dumps({"error": f"Input file not found: {input}"}))
            raise typer.Exit(code=1)
        except OSError as exc:
            typer.echo(json.dumps({"error": f"Cannot read input file {input}: {exc}"}))
            raise typer.Exit(code=1)

    if not all_texts:
        typer.echo(json.dumps({"error": "No texts provided. Use --texts or --input."}))
        raise typer.Exit(code=1)

    # --- Classify each text ---------------------------------------------------
    results: list[dict[str, object]] = []
    for t in all_texts:
        try:
            result = classify_text(text=t, lang=lang)
            results.append({
                "text": t,
                "cefr_level": result["cefr_level"],
                "confidence": result["confidence"],
            })
        except Exception as exc:
            results.append({
                "text": t,
                "error": str(exc),
            })

    # --- Output ---------------------------------------------------------------
    payload = json.dumps(results, indent=2, ensure_ascii=False)
    if output is not None:
        with open(output, "w", encoding="utf-8") as fh:
            fh.write(payload)
        typer.echo(json.dumps({"written": output, "count": len(results)}))
    else:
        typer.echo(payload)
