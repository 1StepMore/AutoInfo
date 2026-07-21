"""CEFR (Common European Framework of Reference) classification module.

Uses LLM to classify text difficulty level (A1-C2) for language learning
content. Supports EN, ZH, JA languages.

Typical usage::

    from autoinfo.cefr import classify_text

    result = classify_text("Hello, how are you?", lang="en")
    print(result["cefr_level"])  # "A1"
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CEFR_LEVELS = frozenset({"A1", "A2", "B1", "B2", "C1", "C2"})

_LANG_NAMES = {
    "en": "English",
    "zh": "Chinese",
    "ja": "Japanese",
}

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def classify_text(
    text: str,
    lang: str = "en",
    model_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify *text* into a CEFR level (A1-C2) using LLM.

    Parameters
    ----------
    text:
        The text to classify.
    lang:
        Language code: ``"en"``, ``"zh"``, or ``"ja"`` (default ``"en"``).
    model_config:
        Optional dict with ``model``, ``api_key``, ``base_url`` keys.
        Falls back to autoinfo config if not provided.

    Returns
    -------
    dict
        ``{cefr_level: str, confidence: float}``.
        *cefr_level* is one of ``A1``, ``A2``, ``B1``, ``B2``, ``C1``,
        ``C2``, or ``"unknown"``.
        *confidence* is ``0.0`` when level is ``"unknown"``.
    """
    if not text or not text.strip():
        return {"cefr_level": "unknown", "confidence": 0.0}

    lang_name = _LANG_NAMES.get(lang, "English")
    model, api_key, base_url = _resolve_model_config(model_config)

    # --- Build prompts -------------------------------------------------------
    system_prompt = (
        "You are a CEFR classification assistant. "
        "Classify the given text into a CEFR level (A1, A2, B1, B2, C1, or C2). "
        "Respond with ONLY the level name, nothing else."
    )

    user_prompt = (
        f"Language: {lang_name}\n\n"
        f"Text: {text[:3000]}\n\n"
        "What is the CEFR level of this text? "
        "Respond with only the level (A1, A2, B1, B2, C1, or C2)."
    )

    # For Chinese and Japanese, add guidance about approximated equivalents
    # since CEFR was designed for European languages.
    if lang in ("zh", "ja"):
        user_prompt += (
            "\n\nNote: CEFR was designed for European languages. For "
            "Chinese/Japanese, use approximated equivalents based on "
            "vocabulary complexity, sentence structure, and abstraction level."
        )

    # --- Call LLM ------------------------------------------------------------
    try:
        import litellm  # noqa: PLC0415 — deferred import
    except ImportError:
        logger.error("litellm is not installed — cannot classify CEFR")
        return {"cefr_level": "unknown", "confidence": 0.0}

    try:
        response = litellm.completion(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=10,
            temperature=0.1,
            api_base=base_url or None,
            api_key=api_key or None,
        )
        content: str = response.choices[0].message.content  # type: ignore[union-attr]
        return _parse_level(content)
    except Exception as exc:
        logger.warning("CEFR classification failed: %s", exc)
        return {"cefr_level": "unknown", "confidence": 0.0}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_model_config(
    model_config: dict[str, Any] | None,
) -> tuple[str, str, str]:
    """Resolve ``(model, api_key, base_url)`` from config.

    Priority:
    1. Explicit *model_config* dict (if it contains a ``model`` key).
    2. AutoInfo project config (``.autoinfo/config.yaml``), using the
       CEFR-specific model if configured, else the base LLM model.
    3. Hard-coded fallback (``deepseek/deepseek-chat``).
    """
    if model_config and model_config.get("model"):
        return (
            model_config["model"],
            model_config.get("api_key", ""),
            model_config.get("base_url", ""),
        )

    try:
        from autoinfo.config import get_config_path, load_config

        config_path = get_config_path()
        if config_path is not None:
            config = load_config(config_path)
            if config.cefr.model:
                model = config.cefr.model
            else:
                provider = config.llm.provider or "openrouter"
                llm_model = config.llm.model or "deepseek/deepseek-chat"
                model = f"{provider}/{llm_model}"
            api_key = config.llm.api_key or ""
            base_url = config.llm.base_url or ""
            return model, api_key, base_url
    except Exception:
        logger.debug("Could not load autoinfo config for CEFR", exc_info=True)

    return "openrouter/deepseek/deepseek-chat", "", ""


def _parse_level(raw: str) -> dict[str, Any]:
    """Parse the LLM response into a ``{cefr_level, confidence}`` dict.

    Strategies (in order):
    1. Exact match against known levels.
    2. Substring match (e.g. ``"A2."`` or ``"Level: B1"``).
    3. Regex for bare letter+digit patterns (e.g. ``C1`` embedded in text).
    """
    level = raw.strip().upper()

    # Strategy 1 — exact match
    if level in CEFR_LEVELS:
        return {"cefr_level": level, "confidence": 0.85}

    # Strategy 2 — substring match
    for lvl in CEFR_LEVELS:
        if lvl in level:
            return {"cefr_level": lvl, "confidence": 0.75}

    # Strategy 3 — regex pattern (e.g. "C2" or "B1" anywhere)
    match = re.search(r"\b([ABC][12])\b", level)
    if match:
        found = match.group(1).upper()
        if found in CEFR_LEVELS:
            return {"cefr_level": found, "confidence": 0.65}

    return {"cefr_level": "unknown", "confidence": 0.0}
