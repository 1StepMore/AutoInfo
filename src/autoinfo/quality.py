"""Quality gates G1-G5 for the AutoInfo pipeline.

Runs advisory checks on collected items: source authority (G1),
dedup status (G2), relevance scoring (G3), factual consistency (G4),
and translation accuracy (G5).

G4 is optional — it requires an LLM call and is only run when explicitly
requested via the ``--check-factual`` flag.

G5 is optional — it requires an LLM call and is only run when explicitly
requested via the ``--check-translation`` flag.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from autoinfo.models import ExtractionResult, Item, KBEntry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@dataclass
class QualityResult:
    """Outcome of a single quality gate check."""

    gate_name: str
    passed: bool
    score: float = 0.0
    details: dict[str, object] = field(default_factory=dict)
    flagged: bool = False


# ---------------------------------------------------------------------------
# G1 — Source Authority
# ---------------------------------------------------------------------------


class G1SourceAuthority:
    """Checks whether the source of an item is authoritative enough.

    Quality tiers:
        - 1-2: trusted / authoritative (no flag)
        - 3-4: community / low-authority (advisory warning)

    This gate is **advisory only** — it never blocks or fails items.
    """

    def check(self, item: Item, source_config: dict[str, Any] | None = None) -> QualityResult:
        """Check source authority tier for *item*.

        Parameters
        ----------
        item:
            The collected item to check.
        source_config:
            Optional source configuration dict.  If provided, *quality_tier*
            from *source_config* takes precedence over ``item.quality_tier``
            (the latter is typically set at collection time).

        Returns
        -------
        QualityResult
            Always returns ``passed=True``.  Items from tier 3+ sources
            have ``flagged=True`` with an advisory warning.
        """
        tier = (
            source_config.get("quality_tier", item.quality_tier)
            if source_config
            else item.quality_tier
        )

        if tier <= 2:
            return QualityResult(
                gate_name="G1-SourceAuthority",
                passed=True,
                score=float(tier),
                flagged=False,
                details={"quality_tier": tier, "source_name": item.source_name},
            )

        return QualityResult(
            gate_name="G1-SourceAuthority",
            passed=True,
            score=float(tier),
            flagged=True,
            details={
                "quality_tier": tier,
                "source_name": item.source_name,
                "warning": "low quality source",
            },
        )


# ---------------------------------------------------------------------------
# G2 — Dedup
# ---------------------------------------------------------------------------


class G2Dedup:
    """Checks whether an item is a duplicate of an existing KB entry.

    Matches are attempted in order:
        1. Exact URL match
        2. PMID match (from ``item.raw_data``)
        3. DOI match (from ``item.raw_data``)
    """

    def check(self, item: Item, existing_entries: list[KBEntry]) -> QualityResult:
        """Check if *item* is a duplicate of any entry in *existing_entries*.

        Parameters
        ----------
        item:
            The collected item to check.
        existing_entries:
            Previously stored KB entries to compare against.

        Returns
        -------
        QualityResult
            ``passed=True`` when the item appears unique,
            ``passed=False`` when a duplicate is found.
        """
        # 1. URL match
        for entry in existing_entries:
            if entry.source_url and item.source_url and entry.source_url == item.source_url:
                return QualityResult(
                    gate_name="G2-Dedup",
                    passed=False,
                    flagged=True,
                    details={
                        "is_duplicate": True,
                        "matched_by": "url",
                        "existing_id": entry.entry_id,
                    },
                )

        # 2. PMID match
        item_pmid = item.raw_data.get("pmid")
        if item_pmid:
            for entry in existing_entries:
                entry_pmid = (
                    entry.custom_fields.get("pmid")
                    if hasattr(entry, "custom_fields")
                    else None
                )
                if entry_pmid and str(entry_pmid) == str(item_pmid):
                    return QualityResult(
                        gate_name="G2-Dedup",
                        passed=False,
                        flagged=True,
                        details={
                            "is_duplicate": True,
                            "matched_by": "pmid",
                            "existing_id": entry.entry_id,
                        },
                    )

        # 3. DOI match
        item_doi = item.raw_data.get("doi")
        if item_doi:
            for entry in existing_entries:
                extract = entry.extracted_fields or {}
                entry_doi = extract.get("doi") or entry.custom_fields.get("doi", "")
                if entry_doi and str(entry_doi).lower() == str(item_doi).lower():
                    return QualityResult(
                        gate_name="G2-Dedup",
                        passed=False,
                        flagged=True,
                        details={
                            "is_duplicate": True,
                            "matched_by": "doi",
                            "existing_id": entry.entry_id,
                        },
                    )

        # No match found — unique
        return QualityResult(
            gate_name="G2-Dedup",
            passed=True,
            score=1.0,
            details={"is_duplicate": False, "matched_by": None},
        )


# ---------------------------------------------------------------------------
# G3 — Relevance Scoring
# ---------------------------------------------------------------------------


class G3RelevanceScoring:
    """Scores item relevance against a set of topic keywords.

    Uses simple keyword overlap scoring (term-count / total-keywords × 100).
    Items scoring below *threshold* are flagged with ``hidden: true``.

    Supports both single-language keywords (``list[str]``) and multi-language
    keywords (``dict[str, list[str]]``) for backwards compatibility.

    Future enhancement:
        LLM-based semantic scoring will be added in a later version.
        The current implementation is purely lexical and serves as a
        reasonable heuristic for v0.1.
    """

    def check(
        self,
        item: Item,
        topic_keywords: list[str] | dict[str, list[str]],
        threshold: int = 30,
    ) -> QualityResult:
        """Score *item* relevance against *topic_keywords*.

        Parameters
        ----------
        item:
            The collected item to score.
        topic_keywords:
            List of keywords that define the topic (e.g. ``["IVF", "embryo"]``)
            or a dict mapping language codes to keyword lists
            (e.g. ``{"en": ["IVF"], "zh": ["试管婴儿"]}``).
        threshold:
            Minimum score (0-100) below which the item is flagged as hidden.
            Defaults to 30.

        Returns
        -------
        QualityResult
            Contains the relevance ``score`` (0-100). Items below threshold
            have ``flagged=True`` and ``details["hidden"] = True``.
        """
        # Normalise multi-language keywords to a flat list
        if isinstance(topic_keywords, dict):
            # When multi-language, flatten all language keyword lists
            flat_keywords: list[str] = []
            for lang_kws in topic_keywords.values():
                flat_keywords.extend(lang_kws)
            topic_keywords = flat_keywords

        if not topic_keywords:
            return QualityResult(
                gate_name="G3-RelevanceScoring",
                passed=True,
                score=100.0,
                details={
                    "hidden": False,
                    "reason": "no keywords to match against",
                    "multi_language": True,
                },
            )

        # Combine title + content into a single searchable text.
        # Lower-case everything for case-insensitive matching.
        text = (item.title + " " + item.content).lower()

        matches = sum(1 for kw in topic_keywords if kw.lower() in text)
        score = min(round((matches / len(topic_keywords)) * 100), 100)

        if score < threshold:
            return QualityResult(
                gate_name="G3-RelevanceScoring",
                passed=False,
                score=float(score),
                flagged=True,
                details={
                    "hidden": True,
                    "reason": "below relevance threshold",
                    "keyword_matches": matches,
                    "total_keywords": len(topic_keywords),
                    "threshold": threshold,
                },
            )

        return QualityResult(
            gate_name="G3-RelevanceScoring",
            passed=True,
            score=float(score),
            flagged=False,
            details={
                "hidden": False,
                "keyword_matches": matches,
                "total_keywords": len(topic_keywords),
            },
        )


# ---------------------------------------------------------------------------
# G4 — Factual Consistency
# ---------------------------------------------------------------------------


class G4FactualConsistency:
    """Check if the extracted summary contradicts the source text.

    This gate sends an LLM prompt comparing the source content with the
    extracted summary (TL;DR) and asks the model to determine whether the
    summary contradicts the source.

    The gate is **advisory only** — it never blocks or fails items.

    Parameters
    ----------
    model : str
        LiteLLM model string (e.g. ``"openrouter/deepseek/deepseek-chat"``).
    """

    SYSTEM_PROMPT = (
        "You are a quality assurance checker. Compare the source text "
        "with its summary. Determine if the summary contradicts the source. "
        'Answer ONLY with JSON: {"contradiction": bool, "explanation": str}'
    )

    def __init__(self, model: str = "openrouter/deepseek/deepseek-chat") -> None:
        self._model = model

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(self, item: Item, extraction: ExtractionResult) -> QualityResult:
        """Send an LLM prompt to compare *item* content with *extraction* summary.

        Parameters
        ----------
        item:
            The collected item whose content is used as the source of truth.
        extraction:
            The LLM extraction result containing the ``tl_dr`` summary to check.

        Returns
        -------
        QualityResult
            ``flagged=True`` when the summary is found to contradict the source.
            ``flagged=False`` when no contradiction is detected.
            If the LLM call fails or returns malformed JSON, the item is flagged
            as uncertain (``contradiction: None``).
        """
        # No summary to check — trivially consistent
        if not extraction.tl_dr:
            return QualityResult(
                gate_name="G4-SummaryFactual",
                passed=True,
                flagged=False,
                details={
                    "contradiction": False,
                    "explanation": "No summary to check",
                },
            )

        _litellm = self._get_litellm()
        if _litellm is None:
            return QualityResult(
                gate_name="G4-SummaryFactual",
                passed=False,
                flagged=True,
                details={
                    "contradiction": None,
                    "explanation": "litellm is not available",
                },
            )

        try:
            response = _litellm.completion(
                model=self._model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"SOURCE TEXT: {item.content[:4000]}\n\n"
                            f"SUMMARY: {extraction.tl_dr}"
                        ),
                    },
                ],
                response_format={"type": "json_object"},
                max_tokens=500,
                temperature=0.0,
            )

            content: str = response.choices[0].message.content  # type: ignore[union-attr]
            parsed = json.loads(content)
            contradiction = bool(parsed.get("contradiction", False))
            explanation = str(parsed.get("explanation", ""))

            return QualityResult(
                gate_name="G4-SummaryFactual",
                passed=not contradiction,
                score=0.0 if contradiction else 1.0,
                flagged=contradiction,
                details={
                    "contradiction": contradiction,
                    "explanation": explanation,
                },
            )

        except (json.JSONDecodeError, KeyError, AttributeError) as exc:
            logger.warning("G4 malformed LLM response: %s", exc)
            return QualityResult(
                gate_name="G4-SummaryFactual",
                passed=False,
                flagged=True,
                details={
                    "contradiction": None,
                    "explanation": f"Failed to parse LLM response: {exc}",
                },
            )

        except Exception as exc:
            logger.warning("G4 LLM call failed: %s", exc)
            return QualityResult(
                gate_name="G4-SummaryFactual",
                passed=False,
                flagged=True,
                details={
                    "contradiction": None,
                    "explanation": f"LLM check failed: {exc}",
                },
            )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _get_litellm() -> Any:
        """Lazily import and return the ``litellm`` module.

        Returns ``None`` when the package is not available (graceful
        degradation for environments where LiteLLM is not installed).
        """
        try:
            import litellm  # noqa: PLC0415 — deferred import

            return litellm
        except (ImportError, ModuleNotFoundError):
            logger.error("litellm is not installed — run 'pip install litellm'")
            return None


# ---------------------------------------------------------------------------
# G5 — Translation Accuracy
# ---------------------------------------------------------------------------


class G5TranslationAccuracy:
    """Check if the translation faithfully represents the source text.

    This gate sends an LLM prompt comparing the source content with its
    translation and asks the model to determine whether the translation
    faithfully preserves meaning, tone, and factual claims.

    The gate is **advisory only** — it never blocks or fails items.

    Parameters
    ----------
    model : str
        LiteLLM model string (e.g. ``"openrouter/deepseek/deepseek-chat"``).
    """

    SYSTEM_PROMPT = (
        "You are a quality assurance checker specialized in translation accuracy. "
        "Compare the source text with its translation. Determine if the translation "
        "faithfully represents the source content, preserving meaning, tone, and "
        "factual claims. "
        'Answer ONLY with JSON: {"faithful": bool, "explanation": str, "issues": [str]}'
    )

    def __init__(self, model: str = "openrouter/deepseek/deepseek-chat") -> None:
        self._model = model

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(self, item: Item, extraction: ExtractionResult) -> QualityResult:
        """Send an LLM prompt to compare *item* content with its translation.

        Parameters
        ----------
        item:
            The collected item whose content is used as the source of truth.
        extraction:
            The LLM extraction result whose ``custom_fields["translation"]``
            contains the translated text to check.

        Returns
        -------
        QualityResult
            ``flagged=True`` when the translation is found to be unfaithful.
            ``flagged=False`` when the translation is faithful.
            If the LLM call fails or returns malformed JSON, the item is flagged
            as uncertain (``faithful: None``).
        """
        # Get translation from extraction custom_fields
        translation = (extraction.custom_fields or {}).get("translation", "")

        # No translation to check — trivially accurate
        if not translation:
            return QualityResult(
                gate_name="G5-TranslationAccuracy",
                passed=True,
                flagged=False,
                details={
                    "faithful": True,
                    "explanation": "No translation to check",
                    "issues": [],
                },
            )

        _litellm = self._get_litellm()
        if _litellm is None:
            return QualityResult(
                gate_name="G5-TranslationAccuracy",
                passed=False,
                flagged=True,
                details={
                    "faithful": None,
                    "explanation": "litellm is not available",
                    "issues": [],
                },
            )

        try:
            response = _litellm.completion(
                model=self._model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"SOURCE TEXT: {item.content[:4000]}\n\n"
                            f"TRANSLATION: {translation}"
                        ),
                    },
                ],
                response_format={"type": "json_object"},
                max_tokens=500,
                temperature=0.0,
            )

            content: str = response.choices[0].message.content  # type: ignore[union-attr]
            parsed = json.loads(content)
            faithful = bool(parsed.get("faithful", False))
            explanation = str(parsed.get("explanation", ""))
            issues = list(parsed.get("issues", []))

            return QualityResult(
                gate_name="G5-TranslationAccuracy",
                passed=faithful,
                score=1.0 if faithful else 0.0,
                flagged=not faithful,
                details={
                    "faithful": faithful,
                    "explanation": explanation,
                    "issues": issues,
                },
            )

        except (json.JSONDecodeError, KeyError, AttributeError) as exc:
            logger.warning("G5 malformed LLM response: %s", exc)
            return QualityResult(
                gate_name="G5-TranslationAccuracy",
                passed=False,
                flagged=True,
                details={
                    "faithful": None,
                    "explanation": f"Failed to parse LLM response: {exc}",
                    "issues": [],
                },
            )

        except Exception as exc:
            logger.warning("G5 LLM call failed: %s", exc)
            return QualityResult(
                gate_name="G5-TranslationAccuracy",
                passed=False,
                flagged=True,
                details={
                    "faithful": None,
                    "explanation": f"LLM check failed: {exc}",
                    "issues": [],
                },
            )

    # ------------------------------------------------------------------
    # Detailed check (uses all 5 translation quality gates)
    # ------------------------------------------------------------------

    def check_detailed(
        self,
        source: str,
        target: str,
        source_lang: str,
        target_lang: str,
        terminology_dict: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run all 5 translation quality gates via the orchestrator."""
        return run_translation_quality_gates(
            source=source,
            target=target,
            source_lang=source_lang,
            target_lang=target_lang,
            terminology_dict=terminology_dict,
            model=self._model,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _get_litellm() -> Any:
        """Lazily import and return the ``litellm`` module.

        Returns ``None`` when the package is not available (graceful
        degradation for environments where LiteLLM is not installed).
        """
        try:
            import litellm  # noqa: PLC0415 — deferred import

            return litellm
        except (ImportError, ModuleNotFoundError):
            logger.error("litellm is not installed — run 'pip install litellm'")
            return None


# ---------------------------------------------------------------------------
# Translation Quality Gate Functions (deterministic, no LLM)
# ---------------------------------------------------------------------------


def check_inline_tags(
    source: str,
    target: str,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Gate 1: Verify markdown inline elements preserved in translation."""
    import re

    patterns: dict[str, str] = {
        "code": r"`[^`]+`",
        "link": r"\[([^\]]+)\]\([^)]+\)",
        "image": r"!\[([^\]]*)\]\([^)]+\)",
    }
    if tags:
        patterns = {k: v for k, v in patterns.items() if k in tags}

    def _extract(text: str) -> set[tuple[str, str]]:
        result: set[tuple[str, str]] = set()
        for tag_name, pat in patterns.items():
            for m in re.finditer(pat, text):
                result.add((tag_name, m.group(0)))
        return result

    source_set = _extract(source)
    target_set = _extract(target)
    missing = sorted(source_set - target_set)
    extra = sorted(target_set - source_set)

    return {
        "passed": len(missing) == 0,
        "missing_tags": [f"{t}:{v}" for t, v in missing],
        "extra_tags": [f"{t}:{v}" for t, v in extra],
    }


def check_terminology(
    source: str,  # noqa: ARG001 — unused, kept for API symmetry
    target: str,
    terminology_dict: dict[str, Any],
) -> dict[str, Any]:
    """Gate 2: Check do_not_translate terms and preferred translations.

    Parameters
    ----------
    source:
        Original source text (unused, kept for API symmetry).
    target:
        Translated target text to inspect.
    terminology_dict:
        Mapping of ``term -> {type, preferred, ...}``.
        ``type="do_not_translate"`` — term must appear literally in target.
        ``type="preferred"`` — ``preferred`` value must appear in target.

    Returns
    -------
    dict
        ``passed`` — bool
        ``violations`` — list of ``{term, expected, actual}``
    """
    violations: list[dict[str, str]] = []
    for term, config in terminology_dict.items():
        term_type = config.get("type", "preferred")

        if term_type == "do_not_translate":
            if term.lower() not in target.lower():
                violations.append({
                    "term": term,
                    "expected": f"present as '{term}'",
                    "actual": "missing or translated",
                })

        elif term_type == "preferred":
            preferred = config.get("preferred", "")
            if preferred and preferred not in target:
                violations.append({
                    "term": term,
                    "expected": preferred,
                    "actual": "missing preferred translation",
                })

    return {"passed": len(violations) == 0, "violations": violations}


def check_length_ratio(
    source: str,
    target: str,
    min_ratio: float = 0.5,
    max_ratio: float = 2.0,
) -> dict[str, Any]:
    """Gate 3: Check target/source length ratio.

    Compute ``ratio = len(target) / max(len(source), 1)``.
    Passes when *ratio* falls within [*min_ratio*, *max_ratio*].

    Returns
    -------
    dict
        ``passed`` — bool
        ``ratio`` — float
    """
    if not source and not target:
        return {"passed": True, "ratio": 1.0}
    if not source:
        return {"passed": False, "ratio": float("inf")}

    ratio = len(target) / len(source)
    passed = min_ratio <= ratio <= max_ratio
    return {"passed": passed, "ratio": round(ratio, 4)}


def check_source_copy(source: str, target: str, threshold: float = 0.9) -> dict[str, Any]:
    """Gate 4: Detect near-identical copy (translation not actually applied).

    Uses character-level :class:`difflib.SequenceMatcher` similarity.
    Fails when similarity >= *threshold*.

    Returns
    -------
    dict
        ``passed`` — bool (``True`` when similarity is **below** threshold)
        ``similarity`` — float 0.0–1.0
    """
    from difflib import SequenceMatcher

    similarity = SequenceMatcher(None, source, target).ratio()
    passed = similarity < threshold
    return {"passed": passed, "similarity": round(similarity, 4)}


# ---------------------------------------------------------------------------
# Gate 5 — LLM-based translation evaluation
# ---------------------------------------------------------------------------


def llm_judge(
    source: str,
    target: str,
    source_lang: str,
    target_lang: str,
    model: str | None = None,
) -> dict[str, Any]:
    """Gate 5: LLM-based quality eval (faithfulness, terminology, style, readability 0-100)."""
    try:
        import litellm as _lm_mod  # noqa: PLC0415
    except ImportError:
        logger.error("litellm is not installed")
        return {"faithfulness": 0, "terminology": 0, "style": 0, "readability": 0,
                "issues": ["litellm unavailable"]}

    _lm: Any = _lm_mod
    if model is None:
        model = _resolve_llm_model()

    prompt = (
        f"Evaluate translation {source_lang}->{target_lang}.\n"
        f"Source: {source[:3000]}\nTarget: {target[:3000]}\n"
        "Score 0-100: faithfulness(meaning), terminology(domain terms), "
        "style(tone), readability(fluency). List issues.\n"
        'Return JSON: {"faithfulness":int,"terminology":int,"style":int,"readability":int,"issues":[str]}'
    )

    try:
        resp = _lm.completion(model=model, messages=[{"role": "user", "content": prompt}],
                              response_format={"type": "json_object"}, max_tokens=1000, temperature=0.0)
        parsed = json.loads(resp.choices[0].message.content)
    except Exception as e:
        logger.warning("llm_judge failed: %s", e)
        return {"faithfulness": 0, "terminology": 0, "style": 0, "readability": 0,
                "issues": [f"LLM eval failed: {e}"]}

    return {
        "faithfulness": max(0, min(100, int(parsed.get("faithfulness", 0)))),
        "terminology": max(0, min(100, int(parsed.get("terminology", 0)))),
        "style": max(0, min(100, int(parsed.get("style", 0)))),
        "readability": max(0, min(100, int(parsed.get("readability", 0)))),
        "issues": list(parsed.get("issues", [])),
    }


def _resolve_llm_model() -> str:
    """Resolve LLM model string from config, falling back to defaults."""
    from autoinfo.config import Config, get_config_path, load_config  # noqa: PLC0415

    try:
        config_path = get_config_path()
        if config_path:
            config = load_config(config_path)
        else:
            config = Config()
    except Exception:
        config = Config()

    provider = config.llm.provider or "openrouter"
    model = config.llm.model or "deepseek/deepseek-chat"
    return f"{provider}/{model}"


def run_translation_quality_gates(
    source: str,
    target: str,
    source_lang: str,
    target_lang: str,
    terminology_dict: dict[str, Any] | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Run all 5 translation quality gates and compute composite score.

    Gates 1-4 are deterministic (no LLM).  Gate 5 calls the LLM.
    Composite score computed via
    :func:`~autoinfo.translation_qa.calculate_quality_score`.

    Returns
    -------
    dict
        ``gates`` — dict of ``{gate_name: gate_result}`` for all 5 gates
        ``composite_score`` — weighted composite from calculate_quality_score
    """
    from autoinfo.translation_qa import calculate_quality_score  # noqa: PLC0415

    g1 = check_inline_tags(source, target)
    g2 = check_terminology(source, target, terminology_dict or {})
    g3 = check_length_ratio(source, target)
    g4 = check_source_copy(source, target)
    g5 = llm_judge(source, target, source_lang, target_lang, model)

    composite = calculate_quality_score(
        faithfulness=float(g5["faithfulness"]),
        terminology=float(g5["terminology"]),
        style=float(g5["style"]),
        readability=float(g5["readability"]),
    )

    return {
        "gates": {
            "inline_tags": g1,
            "terminology": g2,
            "length_ratio": g3,
            "source_copy": g4,
            "llm_judge": g5,
        },
        "composite_score": composite,
    }


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def run_quality_gates(
    item: Item,
    context: dict[str, Any] | None = None,
) -> dict[str, QualityResult]:
    """Run all three quality gates (G1, G2, G3) on *item*.

    Parameters
    ----------
    item:
        The collected item to check.
    context:
        Optional dictionary that may contain:

        - ``source_config`` — source configuration dict (for G1)
        - ``existing_entries`` — list of :class:`KBEntry` (for G2)
        - ``topic_keywords`` — list of keyword strings (for G3)
        - ``threshold`` — relevance threshold integer (for G3)

    Returns
    -------
    dict[str, QualityResult]
        Mapping of ``gate_name`` → :class:`QualityResult`.
    """
    ctx = context or {}

    source_config: dict[str, Any] | None = ctx.get("source_config")
    existing_entries: list[KBEntry] = ctx.get("existing_entries", [])
    topic_keywords: list[str] = ctx.get("topic_keywords", [])
    threshold: int = ctx.get("threshold", 30)

    g1 = G1SourceAuthority()
    g2 = G2Dedup()
    g3 = G3RelevanceScoring()

    results: dict[str, QualityResult] = {}

    results["G1-SourceAuthority"] = g1.check(item, source_config)
    results["G2-Dedup"] = g2.check(item, existing_entries)
    results["G3-RelevanceScoring"] = g3.check(item, topic_keywords, threshold)

    return results
