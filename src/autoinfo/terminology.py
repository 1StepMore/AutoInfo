"""Per-domain terminology management — ``_terminology.yaml`` loader.

Provides the :class:`Terminology` and :class:`TermEntry` dataclasses and the
:func:`load_terminology` function used to inject terminology guardrails into
LLM translation prompts.

File format (``knowledge/<domain>/_terminology.yaml``)::

    score_weights:
      faithfulness: 40
      terminology: 30
      style: 20
      readability: 10
    terms:
      CRISPR:
        type: do_not_translate
        note: Gene editing tool
      "in vitro fertilization":
        preferred: 体外受精
        variants: ["IVF"]
        confidence: 0.95
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


@dataclass
class TermEntry:
    """A single terminology entry.

    Parameters
    ----------
    type:
        ``"do_not_translate"`` or ``"preferred"`` (default).
    preferred:
        Preferred translation (only for type ``"preferred"``).
    variants:
        Alternative forms of the term (e.g. acronyms, synonyms).
    confidence:
        How confident we are in the preferred translation (0.0 – 1.0).
    note:
        Human-readable note about the term.
    """

    type: str = "preferred"
    preferred: str = ""
    variants: list[str] = field(default_factory=list)
    confidence: float = 1.0
    note: str = ""


@dataclass
class Terminology:
    """Terminology data loaded from a domain's ``_terminology.yaml``.

    Parameters
    ----------
    terms:
        Map of source term → :class:`TermEntry`.
    score_weights:
        Weights for scoring translation quality.
    """

    terms: dict[str, TermEntry] = field(default_factory=dict)
    score_weights: dict[str, int] = field(
        default_factory=lambda: {
            "faithfulness": 40,
            "terminology": 30,
            "style": 20,
            "readability": 10,
        },
    )


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def load_terminology(domain: str) -> Terminology:
    """Load terminology data for *domain* from its ``_terminology.yaml``.

    Looks for ``knowledge/<domain>/_terminology.yaml`` relative to the
    current working directory.

    Returns an empty :class:`Terminology` when the file does not exist
    (no error, no crash — graceful degradation).
    """
    path = Path("knowledge") / domain / "_terminology.yaml"
    if not path.is_file():
        logger.debug("No terminology file for domain '%s': %s", domain, path)
        return Terminology()

    try:
        raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        logger.warning("Failed to parse terminology file: %s", path, exc_info=True)
        return Terminology()

    terms: dict[str, TermEntry] = {}
    raw_terms: dict[str, Any] = raw.get("terms", {}) or {}
    for term, entry in raw_terms.items():
        if entry is None:
            entry = {}
        if not isinstance(entry, dict):
            continue
        try:
            terms[term] = TermEntry(**entry)
        except Exception:
            logger.warning("Skipping invalid term entry '%s': %s", term, entry)
            continue

    raw_weights: dict[str, Any] = raw.get("score_weights", {}) or {}
    weights: dict[str, int] = {k: int(v) for k, v in raw_weights.items() if isinstance(v, (int, str))}
    return Terminology(terms=terms, score_weights=weights)
