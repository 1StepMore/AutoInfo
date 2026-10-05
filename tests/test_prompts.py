"""Prompt registry contract tests (issue #426).

``src/autoinfo/prompts.py`` is a loader; a loader is only as trustworthy as
the invariants nobody re-checks.  These tests pin four things:

1. every registered prompt loads and renders;
2. each prompt's declared placeholder set matches the placeholders actually in
   its file — in BOTH directions, so a dropped placeholder and a newly invented
   one both fail;
3. a missing value raises an error that names the offending placeholder;
4. the loaded text is byte-identical to the inline literal it replaced, pinned
   per prompt against the pre-migration string.

Plus the directory/registry agreement check: no orphan file, no dangling name.

Test 4 is the load-bearing one.  Prompt wording is product behaviour — the
model sees these bytes — so the registry cannot be treated as a refactor that
may "tidy" whitespace, re-indent a JSON example, or rewrap a sentence.  Each
expected string below was captured from the inline literal before #426
extracted it, not retyped by hand.

Stdlib only, no network, no LLM.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from autoinfo import prompts
from autoinfo.prompts import (
    PROMPT_PLACEHOLDERS,
    PROMPT_VERSIONS,
    PROMPTS_DIR,
    PromptError,
    PromptRenderError,
    get_prompt,
    list_prompts,
    prompt_path,
    render_prompt,
)

# ---------------------------------------------------------------------------
# 1. Every registered prompt loads and renders
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(PROMPT_VERSIONS))
def test_registered_prompt_loads_and_renders(name: str) -> None:
    """A static prompt renders to itself; a templated one renders with its values."""
    text = get_prompt(name)
    assert text, f"{name} is empty"
    assert text == text.strip("\n"), f"{name} must not begin or end with a newline"

    values: dict[str, object] = {p: f"<{p}>" for p in PROMPT_PLACEHOLDERS.get(name, ())}
    rendered = render_prompt(name, **values)
    assert rendered, f"{name} rendered empty"
    assert "$" not in rendered, f"{name} left an unsubstituted placeholder: {rendered!r}"


@pytest.mark.parametrize("name", sorted(PROMPT_VERSIONS))
def test_prompt_version_is_declared(name: str) -> None:
    assert name in PROMPT_VERSIONS
    assert re.fullmatch(r"\d+\.\d+\.\d+", PROMPT_VERSIONS[name]), (
        f"{name} version {PROMPT_VERSIONS[name]!r} is not semver"
    )


def test_unknown_prompt_names_the_registered_ones() -> None:
    with pytest.raises(PromptError, match="no_such_prompt"):
        get_prompt("no_such_prompt")


# ---------------------------------------------------------------------------
# 2. Declared placeholders match the placeholders in the file, both ways
# ---------------------------------------------------------------------------

_PLACEHOLDER_RE = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")


@pytest.mark.parametrize("name", sorted(PROMPT_VERSIONS))
def test_declared_placeholders_match_file(name: str) -> None:
    """Fails if a file drops a declared placeholder or invents an undeclared one.

    Both directions are asserted in one test because they are the same
    invariant seen from two sides: the declared set must equal the set the
    loader will actually substitute.  A dropped placeholder would otherwise
    leave a caller passing a value the prompt silently ignores; an invented one
    would otherwise reach the model as a literal ``$word``.
    """
    declared = set(prompts.placeholders(name))
    present = set(_PLACEHOLDER_RE.findall(get_prompt(name)))

    assert declared == present, (
        f"{name}: declared placeholders {sorted(declared)} != placeholders in "
        f"{prompt_path(name)} {sorted(present)}; "
        f"dropped={sorted(declared - present)} added={sorted(present - declared)}"
    )


def test_declared_placeholders_are_a_subset_of_registered_prompts() -> None:
    unknown = set(PROMPT_PLACEHOLDERS) - set(PROMPT_VERSIONS)
    assert not unknown, f"PROMPT_PLACEHOLDERS declares unregistered prompts: {sorted(unknown)}"


def test_no_prompt_body_contains_a_stray_dollar() -> None:
    """A ``$`` not part of a declared placeholder would reach the model verbatim."""
    for name in list_prompts():
        body = get_prompt(name)
        for stray in re.findall(r"\$(?![A-Za-z_])", body):
            pytest.fail(f"{name} contains a bare '$' that the loader will not substitute")


# ---------------------------------------------------------------------------
# 3. Render errors name the offending placeholder
# ---------------------------------------------------------------------------


def test_missing_placeholder_raises_and_names_it() -> None:
    with pytest.raises(PromptRenderError) as excinfo:
        render_prompt("translator_system", source="EN")

    message = str(excinfo.value)
    assert "target" in message, f"error message must name the missing placeholder: {message}"
    assert "translator_system" in message


def test_every_declared_placeholder_is_required() -> None:
    """Omitting any single placeholder must fail, and name that placeholder."""
    for name, declared in sorted(PROMPT_PLACEHOLDERS.items()):
        full = {p: "X" for p in declared}
        for omitted in declared:
            partial = {k: v for k, v in full.items() if k != omitted}
            with pytest.raises(PromptRenderError) as excinfo:
                render_prompt(name, **partial)
            assert omitted in str(excinfo.value), (
                f"{name}: omitting {omitted!r} did not name it — {excinfo.value}"
            )


def test_unused_supplied_value_raises_and_names_it() -> None:
    with pytest.raises(PromptRenderError) as excinfo:
        render_prompt("digest_system", stray="X")

    message = str(excinfo.value)
    assert "stray" in message, f"error message must name the unused value: {message}"
    assert "digest_system" in message


def test_static_prompt_rejects_any_value() -> None:
    with pytest.raises(PromptRenderError):
        render_prompt("extraction_system", anything="X")


def test_undeclared_placeholder_in_file_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """A ``$word`` added to a file without a matching declaration is a hard error.

    Without this the loader would substitute nothing and hand the model a
    literal ``$word``.  The file body is stubbed because no committed prompt
    file should ever contain one — that is the point: the error has to be
    reachable before such a file lands.
    """
    monkeypatch.setattr(prompts, "get_prompt", lambda name: "speak $undeclared now")

    with pytest.raises(PromptRenderError) as excinfo:
        render_prompt("digest_system")

    message = str(excinfo.value)
    assert "undeclared" in message
    assert "PROMPT_PLACEHOLDERS" in message, f"message must say how to fix it: {message}"


# ---------------------------------------------------------------------------
# 4. Byte-exactness pins
# ---------------------------------------------------------------------------

# Captured verbatim from the inline literals before #426 moved them into
# data/prompts/.  Do NOT re-wrap, re-indent, or "fix" these — a mismatch is the
# signal that a prompt the model reads has changed.
_PINNED: dict[str, str] = {
    "cefr_system": (
        "You are a CEFR classification assistant. "
        "Classify the given text into a CEFR level (A1, A2, B1, B2, C1, or C2)."
    ),
    "digest_system": (
        "You are a research digest assistant. Given a list of knowledge base "
        "entries from the past period, synthesize them into a concise digest. "
        "Respond with valid JSON only, no markdown formatting."
    ),
    "extraction_system": (
        "You are AutoInfo, an information extraction assistant. "
        "Extract structured information from the following article. "
        "Respond with valid JSON only, no markdown formatting."
    ),
    "g4_factual_system": (
        "You are a quality assurance checker. Compare the source text "
        "with its summary. Determine if the summary contradicts the source. "
        'Answer ONLY with JSON: {"contradiction": bool, "explanation": str}'
    ),
    "g5_translation_system": (
        "You are a quality assurance checker specialized in translation accuracy. "
        "Compare the source text with its translation. Determine if the translation "
        "faithfully represents the source content, preserving meaning, tone, and "
        "factual claims. "
        'Answer ONLY with JSON: {"faithful": bool, "explanation": str, "issues": [str]}'
    ),
    "presentation_system": (
        "You are a presentation designer. Given knowledge base "
        "entries, generate structured slide content. "
        "Respond with valid JSON only, no markdown formatting."
    ),
    "relevance_scoring_system": (
        "You are a relevance scoring assistant. "
        "Rate the relevance of the given content to the specified keywords "
        "on a 0-100 scale. 0 = completely irrelevant, 100 = highly relevant. "
        "Return ONLY a single integer number, nothing else."
    ),
    "report_synthesis_system": (
        "You are a report synthesis assistant. Given knowledge "
        "base entries and themes, write a concise executive "
        "summary, key findings, and recommendations. Respond "
        "with plain Markdown only — no JSON, no code fences."
    ),
    "text_simplification_system": (
        "You are a text simplification assistant. Your task is to rewrite "
        "the given text so that it is suitable for readers at a specific "
        "CEFR level. Follow these rules:\n"
        "- Use vocabulary and sentence structures appropriate for the target CEFR level.\n"
        "- Preserve the core meaning, key facts, and important details.\n"
        "- Do NOT add new information or opinions.\n"
        "- Return ONLY the simplified text — no explanations, no prefixes, no markdown wrapping."
    ),
    "translation_system": (
        "You are a professional medical translator. Translate the following "
        "knowledge base entry into the target language. "
        "CRITICAL: Preserve all medical terminology, drug names, procedures, "
        "and technical terms in their original form — do NOT translate terms "
        "like IVF, RCT, embryo, blastocyst, gonadotropin, etc. "
        "Keep numbers, statistics, and citations exactly as-is. "
        "Respond with valid JSON only: "
        '{"translated_title": "...", "translated_body": "..."}'
    ),
    "translation_quality_evaluator_system": (
        "You are a translation quality evaluator. Compare the ORIGINAL source text "
        "with the BACK-TRANSLATED text (i.e. text that was translated to another "
        "language and then translated back). "
        "Assess how faithfully the back-translated text preserves the meaning, "
        "tone, and factual content of the original.\n\n"
        "Return JSON with:\n"
        '- "faithfulness_score": integer 0-100 (100 = perfect preservation)\n'
        '- "issues": list of objects, each with:\n'
        '    - "severity": "minor" | "major" | "critical"\n'
        '    - "description": what changed or was lost\n'
        '    - "position": where in the text the issue occurs (e.g. "paragraph 2", '
        '"sentence 1", "last line")\n\n'
        "If no significant issues are found, return an empty issues list."
    ),
    "tutorial_system": (
        "You are a tutorial designer. Given knowledge base "
        "entries, structure them into a coherent learning path. "
        "Respond with valid JSON only, no markdown formatting."
    ),
}

# Templated prompts: the render is pinned at a non-empty sentinel so a dropped
# or reordered placeholder shows up as a diff, not as a coincidence.
_PINNED_TEMPLATES: dict[str, dict[str, object]] = {
    "keyword_suggestion_system": {"limit": 5},
    "product_judge": {"output_format": "HTML", "body": "BODY"},
    "translator_system": {"source": "EN", "target": "ZH"},
    "validation_judge": {"assertion": "ASSERT", "tool_output_json": "JSON"},
}

_PINNED_RENDERS: dict[str, str] = {
    "keyword_suggestion_system": (
        "You are a keyword extraction assistant. Given a text, suggest up to 5 "
        "relevant keywords or short phrases (2-5 words) that capture the core "
        "topics. Respond with valid JSON only: an array of strings. Example: "
        '["machine learning", "neural networks", "deep learning"]'
    ),
    "product_judge": (
        "You are a product quality reviewer. Review the following rendered HTML "
        "product body and decide whether it contains non-trivial content covering "
        "the required sections (executive summary, key findings, recommendations)."
        '\n\nReturn ONLY a JSON object: {"ok": true|false, "reason": "..."}.\n'
        "Set ok=false when the body is empty, garbled, or missing required "
        "sections.\n\n--- BODY START ---\nBODY\n--- BODY END ---"
    ),
    "translator_system": (
        "You are a professional translator. Translate the given text from EN to "
        "ZH. Return only the translated text, no explanations or commentary."
    ),
    "validation_judge": (
        "You are a validation judge for the AutoInfo platform. Determine whether "
        "the assertion holds for the given tool output.\n\nASSERTION:\nASSERT\n\n"
        'TOOL OUTPUT (JSON):\nJSON\n\nReply with JSON exactly: {"verdict": "PASS" '
        'or "FAIL", "reason": "one-sentence justification"}'
    ),
}


@pytest.mark.parametrize("name", sorted(_PINNED))
def test_static_prompt_is_byte_exact(name: str) -> None:
    assert get_prompt(name) == _PINNED[name]


@pytest.mark.parametrize("name", sorted(_PINNED_TEMPLATES))
def test_templated_prompt_renders_byte_exact(name: str) -> None:
    assert render_prompt(name, **_PINNED_TEMPLATES[name]) == _PINNED_RENDERS[name]


def test_every_registered_prompt_is_pinned() -> None:
    """A new prompt must arrive with its pin, or this fails."""
    assert set(_PINNED) | set(_PINNED_TEMPLATES) == set(PROMPT_VERSIONS)


def test_templated_prompts_pin_every_declared_placeholder() -> None:
    for name, values in _PINNED_TEMPLATES.items():
        assert set(values) == set(PROMPT_PLACEHOLDERS.get(name, ())), (
            f"{name} pin supplies {sorted(values)} but declares "
            f"{sorted(PROMPT_PLACEHOLDERS.get(name, ()))}"
        )


def test_prompt_files_are_posix_text() -> None:
    """Files end with exactly one newline; the loader strips exactly one.

    A CRLF checkout or a hand-edit that adds a blank line would otherwise reach
    the model as a trailing ``\\r\\n\\n``.
    """
    for name in list_prompts():
        raw = prompt_path(name).read_text(encoding="utf-8")
        assert raw.endswith("\n"), f"{name}.md does not end with a newline"
        assert not raw.endswith("\n\n"), f"{name}.md ends with a blank line"
        assert "\r" not in raw, f"{name}.md contains a carriage return"


def test_loader_strips_exactly_one_trailing_newline() -> None:
    for name in list_prompts():
        raw = prompt_path(name).read_text(encoding="utf-8")
        assert get_prompt(name) == raw[:-1], f"{name} lost or gained more than one character"


# ---------------------------------------------------------------------------
# 5. Directory and registry agree
# ---------------------------------------------------------------------------


def test_list_prompts_matches_the_registry() -> None:
    assert list_prompts() == sorted(PROMPT_VERSIONS)
    assert list_prompts() == sorted(set(PROMPT_VERSIONS)), "PROMPT_VERSIONS has a duplicate key"


def test_prompts_dir_has_no_orphan_files() -> None:
    on_disk = {p.stem for p in PROMPTS_DIR.glob("*.md")}
    registered = set(PROMPT_VERSIONS)

    orphans = on_disk - registered
    assert not orphans, (
        f"prompt file(s) on disk but not registered: {sorted(orphans)}; add them to PROMPT_VERSIONS"
    )

    dangling = registered - on_disk
    assert not dangling, f"registered prompt(s) with no file: {sorted(dangling)}"


def test_prompts_dir_has_no_unexpected_files() -> None:
    everything = {p.name for p in PROMPTS_DIR.iterdir() if p.is_file()}
    expected = {f"{name}.md" for name in PROMPT_VERSIONS}
    assert everything == expected, (
        f"unexpected file(s) in {PROMPTS_DIR}: {sorted(everything - expected)}"
    )


def test_prompts_dir_is_the_packaged_location() -> None:
    """The loader must resolve inside the installed package, not the CWD."""
    assert PROMPTS_DIR.is_dir(), f"{PROMPTS_DIR} does not exist"
    assert PROMPTS_DIR.name == "prompts"
    assert PROMPTS_DIR.parent.name == "data"
    assert PROMPTS_DIR.parent.parent == Path(prompts.__file__).resolve().parent


def test_get_prompt_is_stable_across_calls() -> None:
    """The loader must not be a cache whose staleness a prompt edit would expose."""
    for name in list_prompts():
        assert get_prompt(name) == get_prompt(name)
