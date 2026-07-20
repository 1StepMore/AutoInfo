"""Quality gates G1-G3 for the AutoInfo pipeline.

Runs advisory checks on collected items: source authority (G1),
dedup status (G2), and relevance scoring (G3).

G4 (factual consistency) and G5 (translation accuracy) are not yet
implemented — they will be added in a future release.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from autoinfo.models import Item, KBEntry

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

    Future enhancement:
        LLM-based semantic scoring will be added in a later version.
        The current implementation is purely lexical and serves as a
        reasonable heuristic for v0.1.
    """

    def check(
        self,
        item: Item,
        topic_keywords: list[str],
        threshold: int = 30,
    ) -> QualityResult:
        """Score *item* relevance against *topic_keywords*.

        Parameters
        ----------
        item:
            The collected item to score.
        topic_keywords:
            List of keywords that define the topic (e.g. ``["IVF", "embryo"]``).
        threshold:
            Minimum score (0-100) below which the item is flagged as hidden.
            Defaults to 30.

        Returns
        -------
        QualityResult
            Contains the relevance ``score`` (0-100). Items below threshold
            have ``flagged=True`` and ``details["hidden"] = True``.
        """
        if not topic_keywords:
            return QualityResult(
                gate_name="G3-RelevanceScoring",
                passed=True,
                score=100.0,
                details={"hidden": False, "reason": "no keywords to match against"},
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
