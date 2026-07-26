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

import html.parser
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

import yaml

from autoinfo.config import QualityGateConfig
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
# G0 — Schema Integrity
# ---------------------------------------------------------------------------


class G0SchemaIntegrity:
    """Validates schema integrity of a raw collected item before Item construction.

    Checks mandatory fields (source_url, source_type, source_platform) and
    optional frontmatter YAML validity.

    This gate is **HARD** — on persistent failure after one retry it blocks
    the item from entering the pipeline.
    """

    MANDATORY_FIELDS = ["source_url", "source_type", "source_platform"]

    def check(
        self,
        item: dict[str, Any],
        context: dict[str, Any] | None = None,
        gate_config: QualityGateConfig | None = None,
    ) -> QualityResult:
        """Validate *item* dict schema integrity.

        Parameters
        ----------
        item:
            Raw collected item dict (not yet constructed into Item).
        context:
            Optional context dict (reserved for future use).
        gate_config:
            Optional gate config. If provided, ``retries`` controls how many
            re-validation attempts are made on failure (default: 1).

        Returns
        -------
        QualityResult
            ``passed=True`` when all mandatory fields are non-empty strings
            and frontmatter (if present) is valid YAML.

            On persistent failure after retries: ``passed=False`` with
            ``action="block"`` in details.
        """
        failed_fields: list[dict[str, object]] = []

        def _validate() -> list[dict[str, object]]:
            """Run validation once, return list of field errors."""
            errors: list[dict[str, object]] = []

            for field in self.MANDATORY_FIELDS:
                val = item.get(field)
                if not isinstance(val, str) or not val.strip():
                    errors.append({
                        "field": field,
                        "reason": "missing or empty",
                        "value": val,
                    })

            frontmatter = item.get("frontmatter")
            if frontmatter is not None:
                if isinstance(frontmatter, str) and frontmatter.strip():
                    try:
                        yaml.safe_load(frontmatter)
                    except yaml.YAMLError as exc:
                        errors.append({
                            "field": "frontmatter",
                            "reason": f"invalid YAML: {exc}",
                            "value": frontmatter[:200],
                        })
                elif not isinstance(frontmatter, str):
                    errors.append({
                        "field": "frontmatter",
                        "reason": "not a string",
                        "value": str(type(frontmatter)),
                    })

            return errors

        # First attempt
        failed_fields = _validate()

        # Determine max retries from gate config (default 1 for backward compat)
        max_retries = 1
        if gate_config is not None and gate_config.retries is not None and gate_config.retries > 0:
            max_retries = gate_config.retries

        retry_count = 0
        if failed_fields:
            logger.warning(
                "G0 first attempt failed for fields: %s",
                [f["field"] for f in failed_fields],
            )
            for _ in range(max_retries):
                retry_count += 1
                failed_fields = _validate()
                if not failed_fields:
                    break

        if not failed_fields:
            return QualityResult(
                gate_name="G0-SchemaIntegrity",
                passed=True,
                score=1.0,
                details={"valid": True},
            )

        return QualityResult(
            gate_name="G0-SchemaIntegrity",
            passed=False,
            score=0.0,
            flagged=True,
            details={
                "action": "block",
                "retry_count": retry_count,
                "failed_fields": failed_fields,
                "error": (
                    "Schema integrity check failed for fields: "
                    f"{[f['field'] for f in failed_fields]}"
                ),
            },
        )


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

    def check(
        self,
        item: Item,
        source_config: dict[str, Any] | None = None,
        gate_config: QualityGateConfig | None = None,
    ) -> QualityResult:
        """Check source authority tier for *item*.

        Parameters
        ----------
        item:
            The collected item to check.
        source_config:
            Optional source configuration dict.  If provided, *quality_tier*
            from *source_config* takes precedence over ``item.quality_tier``
            (the latter is typically set at collection time).
        gate_config:
            Optional gate configuration dict.  If provided, the *action*
            field controls what the caller should do on failure:

            - ``"flag"`` (default): item passes with an advisory warning
            - ``"skip"``: item is returned as ``passed=False`` with
              ``action="skip"`` in details, signalling the caller to skip it.

            When *gate_config* is ``None``, the default action ``"flag"``
            is used (backward compatible with v1.4 behaviour).

        Returns
        -------
        QualityResult
            When action is ``"skip"`` and tier > 2, returns ``passed=False``
            with ``action="skip"`` in details.  Otherwise always returns
            ``passed=True``.  Items from tier 3+ sources have
            ``flagged=True`` with an advisory warning.
        """
        tier = (
            source_config.get("quality_tier", item.quality_tier)
            if source_config
            else item.quality_tier
        )
        action = gate_config.action if gate_config else "flag"

        if tier <= 2:
            return QualityResult(
                gate_name="G1-SourceAuthority",
                passed=True,
                score=float(tier),
                flagged=False,
                details={
                    "quality_tier": tier,
                    "source_name": item.source_name,
                    "action": action,
                },
            )

        # tier 3+
        if action == "skip":
            return QualityResult(
                gate_name="G1-SourceAuthority",
                passed=False,
                score=float(tier),
                flagged=True,
                details={
                    "quality_tier": tier,
                    "source_name": item.source_name,
                    "action": action,
                    "warning": "low quality source",
                },
            )

        return QualityResult(
            gate_name="G1-SourceAuthority",
            passed=True,
            score=float(tier),
            flagged=True,
            details={
                "quality_tier": tier,
                "source_name": item.source_name,
                "action": action,
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

    def check(
        self,
        item: Item,
        existing_entries: list[KBEntry],
        gate_config: QualityGateConfig | None = None,
    ) -> QualityResult:
        """Check if *item* is a duplicate of any entry in *existing_entries*.

        Parameters
        ----------
        item:
            The collected item to check.
        existing_entries:
            Previously stored KB entries to compare against.
        gate_config:
            Optional gate configuration dict.  If provided, the *action*
            field controls how the result is annotated:

            - ``"flag"`` (default): duplicate is reported with ``flagged=True``
            - ``"skip"``: duplicate is reported with ``action="skip"`` in
              details, signalling the caller to skip this item.

            When *gate_config* is ``None``, the default action ``"flag"``
            is used (backward compatible with v1.4 behaviour).

        Returns
        -------
        QualityResult
            ``passed=True`` when the item appears unique,
            ``passed=False`` when a duplicate is found.
        """
        action = gate_config.action if gate_config else "flag"

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
                        "action": action,
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
                            "action": action,
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
                            "action": action,
                        },
                    )

        # No match found — unique
        return QualityResult(
            gate_name="G2-Dedup",
            passed=True,
            score=1.0,
            details={"is_duplicate": False, "matched_by": None, "action": action},
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
        gate_config: QualityGateConfig | None = None,
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
        gate_config:
            Optional gate configuration dict.  If provided, the *action*
            field controls how below-threshold items are annotated:

            - ``"archive"`` (default): item is marked with both
              ``hidden=True`` and ``archive=True`` in details.
            - ``"flag"``: item is marked with ``hidden=True`` only.

            When *gate_config* is ``None``, the default action ``"archive"``
            is used (backward compatible with v1.4 behaviour).

        Returns
        -------
        QualityResult
            Contains the relevance ``score`` (0-100). Items below threshold
            have ``flagged=True`` and ``details["hidden"] = True``.  When
            action is ``"archive"``, ``details["archive"]`` is also set to
            ``True``.
        """
        action = gate_config.action if gate_config else "archive"

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
                    "action": action,
                    "reason": "no keywords to match against",
                    "multi_language": True,
                },
            )

        # Combine title + content into a single searchable text.
        # Lower-case everything for case-insensitive matching.
        text = (item.title + " " + item.content).lower()

        matches = sum(1 for kw in topic_keywords if kw.lower() in text)
        score_val = min(round((matches / len(topic_keywords)) * 100), 100)

        if score_val < threshold:
            details: dict[str, object] = {
                "hidden": True,
                "action": action,
                "reason": "below relevance threshold",
                "keyword_matches": matches,
                "total_keywords": len(topic_keywords),
                "threshold": threshold,
            }
            if action == "archive":
                details["archive"] = True

            return QualityResult(
                gate_name="G3-RelevanceScoring",
                passed=False,
                score=float(score_val),
                flagged=True,
                details=details,
            )

        return QualityResult(
            gate_name="G3-RelevanceScoring",
            passed=True,
            score=float(score_val),
            flagged=False,
            details={
                "hidden": False,
                "action": action,
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

    When a *gate_config* with retries is provided to :meth:`check`, the
    gate implements a retry chain with escalating context and different
    models per attempt.  On all retries exhausted the item is blocked and
    diagnostics are written to ``collections/<domain>/_failed/<item_id>.json``.

    Parameters
    ----------
    model : str
        LiteLLM model string (e.g. ``"openrouter/deepseek/deepseek-chat"``).
    collections_path : str | Path, optional
        Root path for the collections directory (default ``"collections"``).
    """

    SYSTEM_PROMPT = (
        "You are a quality assurance checker. Compare the source text "
        "with its summary. Determine if the summary contradicts the source. "
        'Answer ONLY with JSON: {"contradiction": bool, "explanation": str}'
    )

    def __init__(
        self,
        model: str = "openrouter/deepseek/deepseek-chat",
        collections_path: str | Path = "collections",
    ) -> None:
        self._model = model
        self._collections_path = Path(collections_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(
        self,
        item: Item,
        extraction: ExtractionResult,
        gate_config: QualityGateConfig | None = None,
    ) -> QualityResult:
        """Compare *item* content with *extraction* summary using LLM.

        When *gate_config* is provided with ``retries > 0``, the gate
        implements a retry chain: each failed attempt uses the next model
        from ``gate_config.retry_models`` and includes the previous
        attempt's contradiction evidence in the prompt.  On all retries
        exhausted the item is blocked and ``_failed/`` diagnostics are
        written.

        Parameters
        ----------
        item:
            The collected item whose content is used as the source of truth.
        extraction:
            The LLM extraction result containing the ``tl_dr`` summary.
        gate_config:
            Optional gate configuration.  When ``None`` (default), the
            legacy single-call advisory behaviour is used.

        Returns
        -------
        QualityResult
            When contradiction is found after all retries: ``passed=False``,
            ``action="block"``, ``retry_count=N``.
            When no contradiction: ``passed=True``, ``flagged=False``.
            When litellm unavailable: ``flagged=True`` with explanation.
        """
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

        if gate_config is not None and gate_config.retries > 0:
            retry_models = list(gate_config.retry_models) if gate_config.retry_models else []
            models = [self._model] + retry_models
            max_attempts = gate_config.retries
        else:
            max_attempts = 1
            models = [self._model]

        retry_log: list[dict[str, Any]] = []
        last_error: str | None = None

        for attempt in range(max_attempts):
            model = models[min(attempt, len(models) - 1)]

            try:
                user_content = (
                    f"SOURCE TEXT: {item.content[:4000]}\n\n"
                    f"SUMMARY: {extraction.tl_dr}"
                )

                if attempt > 0 and retry_log:
                    prev = retry_log[-1]
                    if prev.get("explanation"):
                        user_content += (
                            f"\n\nPREVIOUS ASSESSMENT: The summary was previously "
                            f"flagged as potentially contradictory:\n"
                            f"{prev['explanation']}\n\n"
                            f"Please re-evaluate carefully."
                        )

                response = _litellm.completion(
                    model=model,
                    messages=[
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": user_content},
                    ],
                    response_format={"type": "json_object"},
                    max_tokens=500,
                    temperature=0.0,
                )

                raw_content: str = response.choices[0].message.content
                parsed = json.loads(raw_content)
                contradiction = bool(parsed.get("contradiction", False))
                explanation = str(parsed.get("explanation", ""))

                if not contradiction:
                    return QualityResult(
                        gate_name="G4-SummaryFactual",
                        passed=True,
                        score=1.0,
                        flagged=False,
                        details={
                            "contradiction": False,
                            "explanation": explanation,
                            "retry_count": attempt,
                            "retries": list(retry_log),
                        },
                    )

                retry_log.append({
                    "attempt": attempt + 1,
                    "model": model,
                    "contradiction": True,
                    "explanation": explanation,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

            except (json.JSONDecodeError, KeyError, AttributeError) as exc:
                logger.warning("G4 malformed LLM response (attempt %d): %s", attempt + 1, exc)
                if gate_config is None or gate_config.retries <= 0:
                    return QualityResult(
                        gate_name="G4-SummaryFactual",
                        passed=False,
                        flagged=True,
                        details={
                            "contradiction": None,
                            "explanation": f"Failed to parse LLM response: {exc}",
                        },
                    )
                retry_log.append({
                    "attempt": attempt + 1,
                    "model": model,
                    "error": f"Failed to parse LLM response: {exc}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                last_error = str(exc)

            except Exception as exc:
                logger.warning("G4 LLM call failed (attempt %d): %s", attempt + 1, exc)
                if gate_config is None or gate_config.retries <= 0:
                    return QualityResult(
                        gate_name="G4-SummaryFactual",
                        passed=False,
                        flagged=True,
                        details={
                            "contradiction": None,
                            "explanation": f"LLM check failed: {exc}",
                        },
                    )
                retry_log.append({
                    "attempt": attempt + 1,
                    "model": model,
                    "error": f"LLM check failed: {exc}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                last_error = str(exc)

        if gate_config is not None and gate_config.retries > 0:
            self._write_failed_diagnostics(item, extraction, retry_log, last_error)
            return QualityResult(
                gate_name="G4-SummaryFactual",
                passed=False,
                flagged=True,
                score=0.0,
                details={
                    "contradiction": True,
                    "action": "block",
                    "retry_count": len(retry_log),
                    "retries": list(retry_log),
                    "explanation": (
                        f"All {max_attempts} attempt(s) exhausted. "
                        f"Last error: {last_error}" if last_error
                        else f"All {max_attempts} attempt(s) exhausted. "
                        f"Summary contradicts source."
                    ),
                },
            )

        fallback_explanation = (
            retry_log[0].get("explanation", "Contradiction detected")
            if retry_log else "Contradiction detected"
        )
        return QualityResult(
            gate_name="G4-SummaryFactual",
            passed=False,
            flagged=True,
            score=0.0,
            details={
                "contradiction": True,
                "explanation": fallback_explanation,
            },
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _write_failed_diagnostics(
        self,
        item: Item,
        extraction: ExtractionResult,
        retries: list[dict[str, Any]],
        final_error: str | None,
    ) -> None:
        """Write blocked-item diagnostics to ``collections/<domain>/_failed/<item_id>.json``."""
        domain = item.domain or "unknown"
        failed_dir = self._collections_path / domain / "_failed"
        failed_dir.mkdir(parents=True, exist_ok=True)

        diagnostics = {
            "item_id": item.id,
            "source_url": item.source_url,
            "retries": retries,
            "final_error": final_error,
            "item_snapshot": {
                "id": item.id,
                "source_name": item.source_name,
                "source_type": item.source_type,
                "source_url": item.source_url,
                "title": item.title,
                "domain": item.domain,
                "language": item.language,
                "collected_at": item.collected_at,
            },
        }

        failed_path = failed_dir / f"{item.id}.json"
        with open(failed_path, "w", encoding="utf-8") as fh:
            json.dump(diagnostics, fh, indent=2, ensure_ascii=False)

        logger.warning(
            "G4 blocked item %s — diagnostics written to %s",
            item.id,
            failed_path,
        )

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
# D1 — Product Completeness
# ---------------------------------------------------------------------------


class D1ProductCompleteness:
    """Verify that a delivered product contains all required sections.

    Checks for the presence and non-emptiness of sections like
    ``key_findings``, ``summary``, and ``recommendations`` in the
    product output dict.

    This gate runs at **output time** for PROCESSED products only.
    It is **skipped** for RAW products.

    Parameters
    ----------
    action_on_failure:
        What to do when the check fails.  One of ``"block"``, ``"fallback"``,
        ``"flag"``.  Defaults to ``"block"``.
    required_sections:
        List of section keys that must be present and non-empty.
        Defaults to ``["key_findings", "summary", "recommendations"]``.
    """

    gate_type: Literal["delivery"] = "delivery"

    def __init__(
        self,
        action_on_failure: str = "block",
        required_sections: list[str] | None = None,
    ) -> None:
        self.action_on_failure = action_on_failure
        self.required_sections = required_sections or [
            "key_findings",
            "summary",
            "recommendations",
        ]

    def check(
        self,
        product_output: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> QualityResult:
        """Check *product_output* for completeness.

        Parameters
        ----------
        product_output:
            The rendered product output dict.  Expected to contain a
            ``format`` key and one or more section keys (e.g.
            ``key_findings``, ``summary``, ``recommendations``).
            May also contain an ``entries`` list with individual entry
            data.

            A ``product_type`` in *product_output* or *context* set to
            ``"RAW"`` causes this gate to **skip** (trivially pass).

        context:
            Optional context.  May contain ``product_type`` to override
            the product type detected from *product_output*.

        Returns
        -------
        QualityResult
            ``passed=True`` when all required sections are present and
            non-empty.  ``passed=False`` with a list of missing/empty
            sections when the check fails.
        """
        ctx = context or {}
        product_type = product_output.get("product_type") or ctx.get("product_type", "")

        # RAW products skip delivery-gate checks
        if product_type.upper() == "RAW":
            return QualityResult(
                gate_name="D1-ProductCompleteness",
                passed=True,
                score=1.0,
                details={
                    "skipped": True,
                    "reason": "RAW product type — delivery gates skipped",
                },
            )

        missing: list[str] = []
        empty: list[str] = []

        for section in self.required_sections:
            val = product_output.get(section)
            if val is None or section not in product_output:
                missing.append(section)
            elif isinstance(val, str) and not val.strip():
                empty.append(section)
            elif isinstance(val, (list, dict)) and len(val) == 0:
                empty.append(section)

        if not missing and not empty:
            return QualityResult(
                gate_name="D1-ProductCompleteness",
                passed=True,
                score=1.0,
                details={
                    "required_sections": list(self.required_sections),
                    "all_present": True,
                },
            )

        passed = self.action_on_failure != "block"
        return QualityResult(
            gate_name="D1-ProductCompleteness",
            passed=passed,
            score=0.0,
            flagged=True,
            details={
                "action": self.action_on_failure,
                "missing_sections": missing,
                "empty_sections": empty,
                "required_sections": list(self.required_sections),
                "error": (
                    f"Missing sections: {missing}; "
                    f"empty sections: {empty}"
                ),
            },
        )


# ---------------------------------------------------------------------------
# D2 — Format Integrity
# ---------------------------------------------------------------------------


class _HTMLValidator(html.parser.HTMLParser):
    """Minimal HTML validator — tracks tag balance.

    Python's :class:`html.parser.HTMLParser` never raises parse errors
    for malformed HTML (since Python 3.5).  This subclass tracks
    opening/closing tag balance using a stack so that mismatched or
    unclosed tags can be detected.
    """

    _SELF_CLOSING = frozenset({
        "br", "hr", "img", "input", "meta", "link", "area", "base",
        "col", "embed", "source", "track", "wbr",
    })

    def __init__(self) -> None:
        super().__init__()
        self._tag_stack: list[str] = []
        self.errors: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        # Void / self-closing elements are never expected to have a closing tag
        if tag.lower() not in self._SELF_CLOSING:
            self._tag_stack.append(tag.lower())

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        if tag_lower in self._SELF_CLOSING:
            return
        if self._tag_stack and self._tag_stack[-1] == tag_lower:
            self._tag_stack.pop()
        elif tag_lower in self._tag_stack:
            # Tag mismatch — close up to the matching open tag
            while self._tag_stack and self._tag_stack[-1] != tag_lower:
                mismatched = self._tag_stack.pop()
                self.errors.append(f"Unclosed tag <{mismatched}> closed by </{tag_lower}>")
            if self._tag_stack:
                self._tag_stack.pop()
        else:
            self.errors.append(f"Unexpected closing tag </{tag_lower}>")

    def is_valid(self) -> bool:
        """Return ``True`` when no tag-balance errors were found."""
        if self._tag_stack:
            for unclosed in self._tag_stack:
                self.errors.append(f"Unclosed tag <{unclosed}>")
        return len(self.errors) == 0


class D2FormatIntegrity:
    """Verify that the rendered output parses correctly for its format.

    For *html* output, attempts to parse with :class:`html.parser.HTMLParser`.
    For *json* output, attempts ``json.loads``.
    For *markdown* output, the check is trivially skipped (Markdown is
    always renderable).

    This gate runs at **output time** for PROCESSED products only.
    It is **skipped** for RAW products.

    Parameters
    ----------
    action_on_failure:
        What to do when the check fails.  One of ``"block"``, ``"fallback"``,
        ``"flag"``.  Defaults to ``"fallback"``.
    """

    gate_type: Literal["delivery"] = "delivery"

    def __init__(self, action_on_failure: str = "fallback") -> None:
        self.action_on_failure = action_on_failure

    def check(
        self,
        product_output: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> QualityResult:
        """Check that *product_output* renders to valid output.

        Parameters
        ----------
        product_output:
            The rendered product output dict.  Must contain a ``format``
            key (``"html"``, ``"json"``, ``"markdown"``, etc.) and
            a ``body`` key with the rendered string.

            A ``product_type`` in *product_output* or *context* set to
            ``"RAW"`` causes this gate to **skip** (trivially pass).

        context:
            Optional context.  May contain ``product_type`` to override
            the product type detected from *product_output*.

        Returns
        -------
        QualityResult
            ``passed=True`` when the output parses correctly for its
            format.  ``passed=False`` with a description of the parse
            error when the check fails.
        """
        ctx = context or {}
        product_type = product_output.get("product_type") or ctx.get("product_type", "")

        # RAW products skip delivery-gate checks
        if product_type.upper() == "RAW":
            return QualityResult(
                gate_name="D2-FormatIntegrity",
                passed=True,
                score=1.0,
                details={
                    "skipped": True,
                    "reason": "RAW product type — delivery gates skipped",
                },
            )

        output_format = product_output.get("format", "").lower()
        body = product_output.get("body", "")

        if not body:
            return QualityResult(
                gate_name="D2-FormatIntegrity",
                passed=False,
                score=0.0,
                flagged=True,
                details={
                    "action": self.action_on_failure,
                    "format": output_format,
                    "error": "Empty body — nothing to validate",
                },
            )

        if output_format == "html":
            return self._check_html(body)
        elif output_format == "json":
            return self._check_json(body)
        elif output_format == "markdown":
            # Markdown is trivially parseable — pass
            return QualityResult(
                gate_name="D2-FormatIntegrity",
                passed=True,
                score=1.0,
                details={
                    "format": "markdown",
                    "valid": True,
                    "note": "Markdown trivially valid",
                },
            )
        else:
            # Unknown format — skip with advisory note
            return QualityResult(
                gate_name="D2-FormatIntegrity",
                passed=True,
                score=1.0,
                details={
                    "format": output_format,
                    "valid": True,
                    "note": f"Unknown format '{output_format}' — skipped",
                },
            )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _check_html(self, body: str) -> QualityResult:
        """Validate *body* as HTML using tag-balance tracking."""
        parser = _HTMLValidator()
        parser.feed(body)
        parser.close()

        if not parser.is_valid():
            return QualityResult(
                gate_name="D2-FormatIntegrity",
                passed=self.action_on_failure != "block",
                score=0.0,
                flagged=True,
                details={
                    "action": self.action_on_failure,
                    "format": "html",
                    "valid": False,
                    "errors": parser.errors,
                    "error": "; ".join(parser.errors),
                },
            )

        return QualityResult(
            gate_name="D2-FormatIntegrity",
            passed=True,
            score=1.0,
            details={
                "format": "html",
                "valid": True,
            },
        )

    def _check_json(self, body: str) -> QualityResult:
        """Validate *body* as JSON."""
        try:
            json.loads(body)
        except json.JSONDecodeError as exc:
            return QualityResult(
                gate_name="D2-FormatIntegrity",
                passed=self.action_on_failure != "block",
                score=0.0,
                flagged=True,
                details={
                    "action": self.action_on_failure,
                    "format": "json",
                    "valid": False,
                    "error": f"JSON parse error: {exc}",
                },
            )

        return QualityResult(
            gate_name="D2-FormatIntegrity",
            passed=True,
            score=1.0,
            details={
                "format": "json",
                "valid": True,
            },
        )


# ---------------------------------------------------------------------------
# D3 — Freshness
# ---------------------------------------------------------------------------


class D3Freshness:
    """Check that all cited items are within a configured recency window.

    Compares each entry's ``collected_at`` date (from the product output)
    against the current UTC time minus the configured recency window.

    Items outside the window are flagged.  Behaviour on failure is
    configurable via *action_on_failure*.

    This gate runs at **output time** for PROCESSED products only.
    It is **skipped** for RAW products.

    Parameters
    ----------
    action_on_failure:
        What to do when the check fails.  One of ``"block"``, ``"fallback"``,
        ``"flag"``.  Defaults to ``"flag"``.
    recency_window_days:
        Number of days defining the recency window.  Items older than
        this are considered stale.  Defaults to 30.
    """

    gate_type: Literal["delivery"] = "delivery"

    def __init__(
        self,
        action_on_failure: str = "flag",
        recency_window_days: int = 30,
    ) -> None:
        self.action_on_failure = action_on_failure
        self.recency_window_days = recency_window_days

    def check(
        self,
        product_output: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> QualityResult:
        """Check that all entries in *product_output* are fresh.

        Parameters
        ----------
        product_output:
            The rendered product output dict.  Should contain an
            ``entries`` key with a list of entry dicts, each having
            a ``collected_at`` or ``date`` field.

            A ``product_type`` in *product_output* or *context* set to
            ``"RAW"`` causes this gate to **skip** (trivially pass).

        context:
            Optional context.  May contain ``product_type`` to override
            the product type detected from *product_output*.
            May also contain ``recency_window_days`` to override the
            configured window.

        Returns
        -------
        QualityResult
            ``passed=True`` when all entries are within the recency
            window.  ``passed=False`` with a list of stale entries
            when the check fails.
        """
        ctx = context or {}
        product_type = product_output.get("product_type") or ctx.get("product_type", "")

        # RAW products skip delivery-gate checks
        if product_type.upper() == "RAW":
            return QualityResult(
                gate_name="D3-Freshness",
                passed=True,
                score=1.0,
                details={
                    "skipped": True,
                    "reason": "RAW product type — delivery gates skipped",
                },
            )

        window_days = ctx.get(
            "recency_window_days",
            self.recency_window_days,
        )
        cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)

        entries = product_output.get("entries", [])
        stale_entries: list[dict[str, Any]] = []

        for entry in entries:
            raw_date = entry.get("collected_at") or entry.get("date") or ""
            if not raw_date:
                continue  # No date — cannot check, skip

            try:
                if isinstance(raw_date, str):
                    # Handle ISO-format strings with/without timezone
                    if raw_date.endswith("Z"):
                        raw_date = raw_date[:-1] + "+00:00"
                    entry_date = datetime.fromisoformat(raw_date)
                elif isinstance(raw_date, datetime):
                    entry_date = raw_date
                else:
                    continue

                # Make naive datetimes UTC-aware for comparison
                if entry_date.tzinfo is None:
                    entry_date = entry_date.replace(tzinfo=timezone.utc)

                if entry_date < cutoff:
                    stale_entries.append({
                        "title": entry.get("title", "(untitled)"),
                        "collected_at": entry.get("collected_at", str(raw_date)),
                        "age_days": (datetime.now(timezone.utc) - entry_date).days,
                    })
            except (ValueError, TypeError):
                # Unparseable date — skip
                continue

        if not stale_entries:
            return QualityResult(
                gate_name="D3-Freshness",
                passed=True,
                score=1.0,
                details={
                    "recency_window_days": window_days,
                    "cutoff": cutoff.isoformat(),
                    "stale_count": 0,
                    "total_entries": len(entries),
                },
            )

        passed = self.action_on_failure not in ("block",)
        return QualityResult(
            gate_name="D3-Freshness",
            passed=passed,
            score=0.0,
            flagged=True,
            details={
                "action": self.action_on_failure,
                "recency_window_days": window_days,
                "cutoff": cutoff.isoformat(),
                "stale_count": len(stale_entries),
                "total_entries": len(entries),
                "stale_entries": stale_entries,
                "error": f"{len(stale_entries)} / {len(entries)} entries are stale",
            },
        )


# ---------------------------------------------------------------------------
# Delivery gate orchestrator
# ---------------------------------------------------------------------------


def run_delivery_gates(
    product_output: dict[str, Any],
    context: dict[str, Any] | None = None,
    delivery_gate_configs: dict[str, dict[str, Any]] | None = None,
) -> dict[str, QualityResult]:
    """Run all configured delivery gates (D1-D3) on *product_output*.

    Parameters
    ----------
    product_output:
        Rendered product output dict to check.
    context:
        Optional context dict.  May contain ``product_type`` (``"RAW"``
        or ``"PROCESSED"``) to control which gates are applied.
    delivery_gate_configs:
        Optional dict mapping gate name (``"D1"``, ``"D2"``, ``"D3"``)
        to config dicts.  Each config may contain:

        - ``enabled`` — if ``False``, the gate is skipped
        - ``action_on_failure`` — ``"block"``, ``"fallback"``, or ``"flag"``

        When ``None``, all three gates run with their default settings.

    Returns
    -------
    dict[str, QualityResult]
        Mapping of ``gate_name`` → :class:`QualityResult`.
    """
    ctx = context or {}
    configs = delivery_gate_configs or {}

    gates: list[tuple[str, Any]] = [
        (
            "D1-ProductCompleteness",
            D1ProductCompleteness(
                action_on_failure=_resolve_dg_action(configs.get("D1", {}), "block"),
            ),
        ),
        (
            "D2-FormatIntegrity",
            D2FormatIntegrity(
                action_on_failure=_resolve_dg_action(configs.get("D2", {}), "fallback"),
            ),
        ),
        (
            "D3-Freshness",
            D3Freshness(
                action_on_failure=_resolve_dg_action(configs.get("D3", {}), "flag"),
            ),
        ),
    ]

    results: dict[str, QualityResult] = {}

    for gate_name, gate_instance in gates:
        dg_config = configs.get(gate_name.split("-")[0], {})
        enabled = dg_config.get("enabled", True) if dg_config else True

        if not enabled:
            results[gate_name] = QualityResult(
                gate_name=gate_name,
                passed=True,
                score=1.0,
                details={"skipped": True, "reason": "Gate disabled in config"},
            )
            continue

        results[gate_name] = gate_instance.check(product_output, ctx)

    return results


def _resolve_dg_action(
    config: dict[str, Any],
    default: str,
) -> str:
    """Extract *action_on_failure* from a delivery gate config dict."""
    return str(config.get("action_on_failure", default))


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
    gate_config: dict[str, QualityGateConfig] | None = None,
) -> dict[str, QualityResult]:
    """Run all quality gates (G0, G1, G2, G3) on *item*.

    G0 runs first (schema integrity), followed by G1-G3. G4 and G5
    are run separately in the processing pipeline.

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
    gate_config:
        Optional mapping of gate name → :class:`QualityGateConfig`.
        If provided, per-gate values (retries, action, threshold) are
        applied to matching gates.  When ``None`` or missing keys,
        defaults are used (backward compatible).

    Returns
    -------
    dict[str, QualityResult]
        Mapping of ``gate_name`` → :class:`QualityResult`.
    """
    ctx = context or {}

    # Validate gate_config type
    if gate_config is not None and not isinstance(gate_config, dict):
        logger.warning(
            "Invalid gate_config type '%s', ignoring", type(gate_config).__name__
        )
        gate_config = None

    source_config: dict[str, Any] | None = ctx.get("source_config")
    existing_entries: list[KBEntry] = ctx.get("existing_entries", [])
    topic_keywords: list[str] = ctx.get("topic_keywords", [])
    threshold: int = ctx.get("threshold", 30)

    # Resolve per-gate configs
    g0_config = gate_config.get("G0-SchemaIntegrity") if gate_config else None
    g1_config = gate_config.get("G1-SourceAuthority") if gate_config else None
    g2_config = gate_config.get("G2-Dedup") if gate_config else None
    g3_config = gate_config.get("G3-RelevanceScoring") if gate_config else None

    # G3: gate_config.threshold overrides context threshold
    if g3_config is not None and g3_config.threshold is not None:
        threshold = int(g3_config.threshold)

    g0 = G0SchemaIntegrity()
    g1 = G1SourceAuthority()
    g2 = G2Dedup()
    g3 = G3RelevanceScoring()

    results: dict[str, QualityResult] = {}

    # G0 runs FIRST — validates raw item schema before further processing
    results["G0-SchemaIntegrity"] = g0.check(item.to_dict(), ctx, g0_config)
    results["G1-SourceAuthority"] = g1.check(item, source_config, g1_config)
    results["G2-Dedup"] = g2.check(item, existing_entries, g2_config)
    results["G3-RelevanceScoring"] = g3.check(item, topic_keywords, threshold, g3_config)

    return results


# ---------------------------------------------------------------------------
# Cross-collection dedup & merge (F53)
# ---------------------------------------------------------------------------


def find_similar_items(query: str, threshold: float = 0.8) -> list[dict[str, Any]]:
    """Find items similar to *query* using SequenceMatcher from difflib.

    Searches all KB entries (up to 1000) and returns those whose
    title+content similarity ratio meets or exceeds *threshold*.

    Parameters
    ----------
    query:
        Text to match against KB entries (title + content combined).
    threshold:
        Minimum SequenceMatcher ratio (0.0–1.0) to consider similar.
        Default 0.8.

    Returns
    -------
    list[dict]
        Up to 20 results, sorted by similarity descending. Each entry:
        ``{"entry_id": str, "similarity": float, "title": str}``.
    """
    from difflib import SequenceMatcher

    from autoinfo.kb import KBStore

    store = KBStore()
    all_entries_result = store.search_knowledge_base(query="", limit=1000)
    entries: list[dict[str, Any]] = (
        all_entries_result.get("entries", [])
        if isinstance(all_entries_result, dict)
        else all_entries_result
    )

    similar: list[dict[str, Any]] = []
    query_lower = query.lower()

    for entry in entries:
        title = str(entry.get("title", ""))
        content = str(entry.get("content", ""))
        text = (content + " " + title).lower()
        similarity = SequenceMatcher(None, query_lower, text).ratio()

        if similarity >= threshold:
            similar.append({
                "entry_id": str(entry.get("entry_id", "")),
                "similarity": float(similarity),
                "title": title,
            })

    return sorted(similar, key=lambda x: x["similarity"], reverse=True)[:20]


def merge_items(item_ids: list[str], strategy: str = "simple") -> dict[str, Any]:
    """Merge multiple KB entries into one.

    Retrieves each entry by ID and combines their content according
    to *strategy*.  The merged result is returned as a dict for review —
    it is **not** automatically saved to the KB.

    Parameters
    ----------
    item_ids:
        List of KB entry IDs to merge.
    strategy:
        Merge strategy:

        - ``"simple"`` — concatenate content blocks with ``---`` separators
        - ``"title_first"`` — use first item's title as heading, then render
          each item as a subsection.

        Default ``"simple"``.

    Returns
    -------
    dict
        ``{status, entry, original_items, strategy_used}`` on success,
        or ``{error}`` when fewer than 2 items are found.
    """
    from datetime import datetime, timezone

    from autoinfo.kb import KBStore

    store = KBStore()

    items: list[dict[str, Any]] = []
    for eid in item_ids:
        entry = store.get_entry(eid)
        if entry:
            items.append(entry)

    if len(items) < 2:
        return {"error": "Need at least 2 items to merge"}

    if strategy == "simple":
        merged_content = "\n\n---\n\n".join(
            str(i.get("content", "")) for i in items
        )
    elif strategy == "title_first":
        merged_content = "# " + str(items[0].get("title", "")) + "\n\n"
        for idx, item in enumerate(items):
            title = str(item.get("title", f"Part {idx + 1}"))
            merged_content += f"## {title}\n\n"
            merged_content += str(item.get("content", "")) + "\n\n"
    else:
        merged_content = "\n\n---\n\n".join(
            str(i.get("content", "")) for i in items
        )

    merged_entry: dict[str, Any] = {
        "title": f"Merge of {len(items)} items",
        "content": merged_content,
        "merged_from": item_ids,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "status": "merged",
        "entry": merged_entry,
        "original_items": len(item_ids),
        "strategy_used": strategy,
    }
