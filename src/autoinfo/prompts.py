"""Prompt registry and loader (issue #426).

Every LLM prompt in AutoInfo used to be an inline string literal in the module
that consumed it.  That scattered the product's most model-visible text across
a dozen modules, gave it no versioning, and made "did this prompt change?"
unanswerable without a full diff.  This module gives prompts the same treatment
the output templates already have in ``data/templates/*.md.j2``: one prompt per
file under :data:`PROMPTS_DIR`, loaded through a single deep interface.

Why ``$name`` and not ``str.format``
------------------------------------
The obvious mechanism — ``str.format`` with ``{placeholder}`` — cannot be used
here because several real prompt bodies contain literal, non-placeholder
braces.  ``translation_system.md`` asks for
``{"translated_title": "...", "translated_body": "..."}``, ``g4_factual_system.md``
asks for ``{"contradiction": bool, "explanation": str}``, ``product_judge.md``
asks for ``{"ok": true|false, "reason": "..."}``, and ``validation_judge.md``
asks for ``{"verdict": "PASS" or "FAIL", ...}``.  Under ``str.format`` those
braces are field references, so loading them would raise ``KeyError`` — and
"fixing" them by doubling the braces would silently corrupt the prompt the
model actually receives.  ``$name`` is used instead: no prompt body contains a
``$``, so a ``$`` in a prompt file is unambiguously a placeholder.

Substitution is implemented with an explicit :data:`re` substitution over the
*declared* placeholder set rather than :class:`string.Template`:
``Template.substitute`` treats every ``$`` as special and reports stray ones
only as an opaque ``ValueError``, whereas the declared set lets the loader name
the exact offending placeholder and lets the test-suite pin each prompt's
required set.

Trailing newline
----------------
Prompt files are POSIX text files and therefore end with ``\\n``; the model
must never see it.  :func:`get_prompt` removes exactly one trailing newline and
nothing else, so leading whitespace, interior blank lines, and trailing spaces
on a line are all preserved byte-for-byte.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

PROMPTS_DIR: Path = Path(__file__).resolve().parent / "data" / "prompts"

_PROMPT_SUFFIX = ".md"

#: Prompt name -> the placeholders its file declares.  A prompt absent from
#: this mapping is static: ``render_prompt`` rejects any value for it.
PROMPT_PLACEHOLDERS: dict[str, tuple[str, ...]] = {
    "keyword_suggestion_system": ("limit",),
    "product_judge": ("output_format", "body"),
    "translator_system": ("source", "target"),
    "validation_judge": ("assertion", "tool_output_json"),
}

#: Prompt name -> version of its text.  ``1.0.0`` is the text as it read
#: verbatim in the inline literal before this extraction; bump the minor on a
#: wording edit and the major on a structural (placeholder set) edit.
PROMPT_VERSIONS: dict[str, str] = {
    "cefr_system": "1.0.0",
    "digest_system": "1.0.0",
    "extraction_system": "1.0.0",
    "g4_factual_system": "1.0.0",
    "g5_translation_system": "1.0.0",
    "keyword_suggestion_system": "1.0.0",
    "presentation_system": "1.0.0",
    "product_judge": "1.0.0",
    "relevance_scoring_system": "1.0.0",
    "report_synthesis_system": "1.0.0",
    "text_simplification_system": "1.0.0",
    "translation_quality_evaluator_system": "1.0.0",
    "translation_system": "1.0.0",
    "translator_system": "1.0.0",
    "tutorial_system": "1.0.0",
    "validation_judge": "1.0.0",
}

_PLACEHOLDER_RE = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")


class PromptError(Exception):
    """A prompt file is missing, unreadable, or inconsistently declared."""


class PromptRenderError(PromptError):
    """A prompt could not be rendered from the supplied values."""


def list_prompts() -> list[str]:
    """Return every registered prompt name, sorted."""
    return sorted(PROMPT_VERSIONS)


def prompt_path(name: str) -> Path:
    """Return the on-disk path of *name*."""
    return PROMPTS_DIR / f"{name}{_PROMPT_SUFFIX}"


def placeholders(name: str) -> tuple[str, ...]:
    """Return the placeholders *name* declares, in declaration order."""
    _check_known(name)
    return PROMPT_PLACEHOLDERS.get(name, ())


def get_prompt(name: str) -> str:
    """Return the raw text of prompt *name*.

    One trailing newline is removed (see the module docstring); everything else
    is returned byte-for-byte.

    Raises
    ------
    PromptError
        If *name* is not a registered prompt, or its file is missing.
    """
    _check_known(name)
    path = prompt_path(name)
    if not path.is_file():
        raise PromptError(f"Prompt {name!r} has no file at {path}")
    text = path.read_text(encoding="utf-8")
    if text.endswith("\n"):
        text = text[:-1]
    return text


def render_prompt(name: str, **values: object) -> str:
    """Substitute *values* into prompt *name* and return the result.

    Raises
    ------
    PromptRenderError
        If a placeholder is missing from *values*, if *values* supplies
        something the prompt does not declare, or if the file contains a ``$name``
        that :data:`PROMPT_PLACEHOLDERS` does not declare.  Every message names
        the offending placeholder or value.
    """
    declared = set(placeholders(name))
    found = set(_PLACEHOLDER_RE.findall(get_prompt(name)))

    undeclared = found - declared
    if undeclared:
        raise PromptRenderError(
            f"Prompt {name!r} uses undeclared placeholder(s) "
            f"{sorted(undeclared)}; add them to PROMPT_PLACEHOLDERS or remove them "
            f"from {prompt_path(name)}"
        )

    missing = declared - set(values)
    if missing:
        raise PromptRenderError(
            f"Prompt {name!r} requires placeholder(s) {sorted(missing)}; "
            f"missing {sorted(missing)} from the supplied values"
        )

    unused = set(values) - declared
    if unused:
        raise PromptRenderError(
            f"Prompt {name!r} does not use supplied value(s) {sorted(unused)}; "
            f"declared placeholders are {sorted(declared)}"
        )

    def substitute(match: re.Match[str]) -> str:
        return str(values[match.group(1)])

    return _PLACEHOLDER_RE.sub(substitute, get_prompt(name))


@lru_cache(maxsize=None)
def _check_known(name: str) -> None:
    if name not in PROMPT_VERSIONS:
        known = ", ".join(list_prompts())
        raise PromptError(f"Unknown prompt {name!r}; registered prompts are: {known}")
