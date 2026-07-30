"""Recommendation engine — content-based via KB search.

Provides:
- RecommendationEngine ABC
- ScoredItem dataclass
- ContentBasedEngine (FTS5 + vector + freshness scoring)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import logging
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ScoredItem:
    """A recommended item with relevance score and reason."""

    entry_id: str
    title: str
    score: float
    reason: str
    source_url: str = ""
    domain: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class RecommendationEngine(ABC):
    """Abstract recommendation engine."""

    @abstractmethod
    def recommend(
        self,
        user_id: str,
        query: str = "",
        domain: Optional[str] = None,
        limit: int = 10,
    ) -> list[ScoredItem]:
        """Return scored recommendations.

        Args:
            user_id: User identifier
            query: Search/recommendation query
            domain: Domain filter (optional)
            limit: Maximum results

        Returns:
            List of ScoredItem, ordered by score descending
        """
        ...


class ContentBasedEngine(RecommendationEngine):
    """Content-based recommendation using KB search.

    Scores items by:
    - FTS5 keyword relevance (weight: 0.4)
    - Vector similarity (weight: 0.3)
    - Freshness recency (weight: 0.2)
    - Domain match bonus (weight: 0.1)
    """

    # Scoring weights
    WEIGHT_KEYWORD: float = 0.4
    WEIGHT_VECTOR: float = 0.3
    WEIGHT_FRESHNESS: float = 0.2
    WEIGHT_DOMAIN: float = 0.1

    # Freshness: items newer than this get max freshness score
    FRESHNESS_DAYS: int = 30

    def __init__(self) -> None:
        self._kb_store = None  # Lazy-loaded KBStore

    def _get_kb(self):
        """Lazy-load KBStore."""
        if self._kb_store is None:
            try:
                from autoinfo.kb import KBStore

                self._kb_store = KBStore()
            except Exception as exc:
                logger.warning("Failed to load KBStore: %s", exc)
                self._kb_store = None
        return self._kb_store

    def recommend(
        self,
        user_id: str,
        query: str = "",
        domain: Optional[str] = None,
        limit: int = 10,
    ) -> list[ScoredItem]:
        """Return scored recommendations using FTS5 + vector dual search.

        Scoring breakdown:
        - Keyword (FTS5 hit): weight 0.4
        - Vector similarity: weight 0.3
        - Freshness recency: weight 0.2
        - Domain match: weight 0.1
        """
        kb = self._get_kb()
        if kb is None:
            logger.warning("KB not available — returning empty recommendations")
            return []

        try:
            # If query is empty/short, return recent items
            if not query or len(query.strip()) < 3:
                return self._recommend_recent(kb, domain, limit)

            dom = domain or ""

            # --- Run dual search: FTS5 + vector --------------------------------
            fts5_result = kb.search_knowledge_base(
                query=query,
                domain=dom,
                limit=limit * 2,
                mode="fts5",
            )
            vec_result = kb.search_knowledge_base(
                query=query,
                domain=dom,
                limit=limit * 2,
                mode="vector",
            )

            # --- Dedup entries from both search paths --------------------------
            all_entries: dict[str, dict[str, Any]] = {}  # entry_id → entry dict
            fts5_ids: set[str] = set()
            vec_ids: set[str] = set()

            for entry in fts5_result.get("entries", []):
                eid = str(entry.get("entry_id", ""))
                if eid:
                    all_entries[eid] = entry
                    fts5_ids.add(eid)

            for entry in vec_result.get("entries", []):
                eid = str(entry.get("entry_id", ""))
                if eid:
                    if eid not in all_entries:
                        all_entries[eid] = entry
                    vec_ids.add(eid)

            # --- Weighted scoring: keyword 0.4 + vector 0.3 + freshness 0.2 + domain 0.1 -
            scored: list[ScoredItem] = []
            for eid, entry in all_entries.items():
                kw_score = 1.0 if eid in fts5_ids else 0.0
                vec_score = 1.0 if eid in vec_ids else 0.0
                fresh_score = self._freshness_score(entry)
                item_domain = str(entry.get("domain", ""))
                dom_score = 1.0 if (dom and item_domain and dom.lower() in item_domain.lower()) else 0.0

                composite = (
                    kw_score * self.WEIGHT_KEYWORD * 100
                    + vec_score * self.WEIGHT_VECTOR * 100
                    + fresh_score * self.WEIGHT_FRESHNESS * 100
                    + dom_score * self.WEIGHT_DOMAIN * 100
                )
                composite = round(min(composite, 100.0), 2)

                scored.append(
                    ScoredItem(
                        entry_id=eid,
                        title=str(entry.get("title", "")),
                        score=composite,
                        reason=self._generate_reason(entry, composite),
                        source_url=str(entry.get("source_url", "")),
                        domain=str(entry.get("domain", dom)),
                    )
                )

            # Sort by score descending and limit
            scored.sort(key=lambda x: x.score, reverse=True)
            return scored[:limit]

        except Exception as exc:
            logger.error("Recommendation failed: %s", exc)
            return []

    def _calculate_score(
        self,
        item: dict[str, Any],
        query: str,
        domain: str,
    ) -> float:
        """Calculate weighted relevance score for an item.

        Items are dicts from KBStore.search_knowledge_base() with fields:
        entry_id, title, relevance_score, freshness_score, collected_at, etc.
        """
        score = 0.0

        # Keyword relevance (from FTS5 rank)
        keyword_score = item.get("relevance_score", None)
        if keyword_score is not None:
            try:
                # relevance_score is typically 0-1 or 0-100
                raw = float(keyword_score)
                if raw <= 1.0:
                    score += raw * self.WEIGHT_KEYWORD * 100
                else:
                    score += (raw / 100.0) * self.WEIGHT_KEYWORD * 100
            except (ValueError, TypeError):
                score += 50.0 * self.WEIGHT_KEYWORD

        # Freshness score (already computed by KBStore)
        freshness = item.get("freshness_score", None)
        if freshness is not None:
            try:
                score += float(freshness) * self.WEIGHT_FRESHNESS * 100
            except (ValueError, TypeError):
                score += 50.0 * self.WEIGHT_FRESHNESS
        else:
            score += 50.0 * self.WEIGHT_FRESHNESS

        # Domain match bonus
        item_domain = str(item.get("domain", ""))
        if domain and item_domain and domain.lower() in item_domain.lower():
            score += 10.0 * self.WEIGHT_DOMAIN

        return min(score, 100.0)  # Cap at 100

    def _freshness_score(self, item: dict[str, Any]) -> float:
        """Calculate freshness score (0-1). Newer = higher."""
        collected_at = item.get("collected_at", None)
        if not collected_at:
            return 0.5  # Default middle score

        try:
            from dateutil import parser

            dt = parser.parse(str(collected_at))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            days_old = (now - dt).days
            if days_old < 0:
                return 1.0  # Future-dated = max
            return max(0.0, 1.0 - (days_old / self.FRESHNESS_DAYS))
        except Exception:
            return 0.5

    def _generate_reason(self, item: dict[str, Any], score: float) -> str:
        """Generate human-readable recommendation reason."""
        title = str(item.get("title", ""))
        title_short = title[:50] if title else ""

        if score >= 80:
            return f"Highly relevant: {title_short}" if title_short else "Highly relevant content"
        elif score >= 60:
            return f"Related content: {title_short}" if title_short else "Related content"
        elif score >= 40:
            return f"Similar topic: {title_short}" if title_short else "Similar topic"
        else:
            domain_str = f" in {item.get('domain', '')}" if item.get("domain") else ""
            return f"Recently added{domain_str}"

    def _recommend_recent(
        self,
        kb: Any,
        domain: Optional[str] = None,
        limit: int = 10,
    ) -> list[ScoredItem]:
        """Return recent items when no query is given."""
        try:
            result = kb.search_knowledge_base(
                query="",
                domain=domain or "",
                limit=limit,
            )
            entries: list[dict[str, Any]] = result.get("entries", []) if isinstance(result, dict) else []

            scored: list[ScoredItem] = []
            for item in entries:
                # Get the freshness_score computed by KBStore, or compute our own
                fresh = item.get("freshness_score", None)
                if fresh is not None:
                    score = float(fresh) * 100
                else:
                    score = self._freshness_score(item) * 100
                scored.append(
                    ScoredItem(
                        entry_id=str(item.get("entry_id", "") or item.get("id", "")),
                        title=str(item.get("title", "")),
                        score=round(score, 2),
                        reason="Recently added content",
                        source_url=str(item.get("source_url", "")),
                        domain=str(item.get("domain", domain or "")),
                    )
                )
            return scored[:limit]
        except Exception as exc:
            logger.error("Recent items fetch failed: %s", exc)
            return []
