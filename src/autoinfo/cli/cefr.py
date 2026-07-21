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
