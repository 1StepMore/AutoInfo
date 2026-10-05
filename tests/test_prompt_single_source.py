"""Prompt single-source guards (issue #426).

Three prompt bodies used to live inline at more than one call site:

- the keyword-suggestion system prompt, byte-identical in ``cli/keywords.py``
  and ``mcp/server.py``;
- the translator system prompt in ``translation_qa.py``, twice with the
  source/target languages swapped at the back-translate site;
- the markdown verdict-block contract in ``agent_review/battery.py``.

Each is now defined once — the first two now live in
``data/prompts/*.md`` and are loaded through :mod:`autoinfo.prompts`.  These
tests lock BOTH halves of that claim: the definition is unique (a scan, so a
future inline copy fails), and the rendered text is unchanged (a pin, so a
refactor cannot quietly rewrite a prompt the model sees).

Stdlib only, no network, no LLM.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC = _REPO_ROOT / "src" / "autoinfo"
_AGENT_REVIEW = _REPO_ROOT / "scripts" / "agent_review"

# scripts/agent_review/ is not a package — load it via sys.path.
sys.path.insert(0, str(_AGENT_REVIEW))

import battery  # noqa: E402

from autoinfo.keywords import keyword_suggestion_system_prompt  # noqa: E402
from autoinfo.prompts import render_prompt  # noqa: E402

# Rendered before the #426 extraction, with limit=5.
_KEYWORD_PROMPT_PINNED = (
    "You are a keyword extraction assistant. Given a text, suggest up to 5 "
    "relevant keywords or short phrases (2-5 words) that capture the core "
    "topics. Respond with valid JSON only: an array of strings. Example: "
    '["machine learning", "neural networks", "deep learning"]'
)

# Rendered before the #426 extraction, with source="EN", target="ZH".
_TRANSLATOR_PROMPT_PINNED = (
    "You are a professional translator. Translate the given text from EN to "
    "ZH. Return only the translated text, no explanations or commentary."
)


def _python_sources() -> list[Path]:
    return sorted(_SRC.rglob("*.py"))


# ---------------------------------------------------------------------------
# Keyword-suggestion system prompt
# ---------------------------------------------------------------------------


def test_keyword_prompt_defined_once() -> None:
    needle = '"You are a keyword extraction assistant'
    hits = [p for p in _python_sources() if needle in p.read_text(encoding="utf-8")]

    assert hits == [], f"keyword prompt literal back inline in {hits}"

    for consumer in ("cli/keywords.py", "mcp/server.py"):
        source = (_SRC / consumer).read_text(encoding="utf-8")
        assert "keyword_suggestion_system_prompt(" in source, (
            f"{consumer} must call the shared builder, not inline the literal"
        )


def test_keyword_prompt_text_pinned() -> None:
    assert keyword_suggestion_system_prompt(5) == _KEYWORD_PROMPT_PINNED


# ---------------------------------------------------------------------------
# Translator system prompt
# ---------------------------------------------------------------------------


def test_translator_template_defined_once() -> None:
    needle = '"You are a professional translator'
    hits = [p for p in _python_sources() if needle in p.read_text(encoding="utf-8")]

    assert hits == [], f"translator prompt literal back inline in {hits}"

    assert render_prompt("translator_system", source="EN", target="ZH") == _TRANSLATOR_PROMPT_PINNED


def test_back_translate_prompt_inverts_languages() -> None:
    """The back-translate site targets the source language, not the target.

    Inverting source/target here would silently back-translate into the wrong
    language and make every faithfulness score meaningless, while still
    rendering a well-formed prompt — so it is pinned separately from the
    single-source check above.
    """
    source = (_SRC / "translation_qa.py").read_text(encoding="utf-8")
    call_sites = source.split('render_prompt(\n                        "translator_system",')[1:]

    assert len(call_sites) == 2, "expected the forward and back-translate call sites"
    swapped = [site for site in call_sites if "source=target_lang" in site]
    assert len(swapped) == 1, "the back-translate site must pass source=target_lang"


# ---------------------------------------------------------------------------
# Verdict-block output schema
# ---------------------------------------------------------------------------


def test_verdict_schema_block_defined_once() -> None:
    source = (_AGENT_REVIEW / "battery.py").read_text(encoding="utf-8")

    assert source.count('"OUTPUT SCHEMA — respond with EXACTLY ONE block') == 1


def test_judge_prompt_carries_shared_verdict_schema() -> None:
    item = {
        "family": "digest",
        "files": [],
        "name": "sample",
        "blind_spot": "SAMPLE",
        "check_desc": "check",
        "evidence_required": "evidence",
    }

    prompt = battery._judge_prompt(item)

    assert battery._VERDICT_SCHEMA_BLOCK in prompt
    assert "Do not add prose before or " in prompt
