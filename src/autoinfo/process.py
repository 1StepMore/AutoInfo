"""Processing pipeline — LLM extraction → quality gates → KB storage.

Reads cached items from ``collections/<domain>/``, runs LLM extraction,
applies quality gates (G1-G3), and stores results in the knowledge base.

Typical usage::

    >>> from autoinfo.process import run_processing
    >>> result = run_processing("medical-research")
    >>> print(f"{result.kb_entries_created} entries created")
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from autoinfo.config import Config, get_config_path, load_config
from autoinfo.kb import KBStore
from autoinfo.llm import LLMExtractor
from autoinfo.models import Item
from autoinfo.quality import run_quality_gates

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@dataclass
class ProcessResult:
    """Aggregate result of a processing run.

    Parameters
    ----------
    domain : str
        Domain that was processed.
    total_items : int
        Total number of cached items loaded.
    passed_gates : int
        Number of items that passed all quality gates (G2 + G3).
    kb_entries_created : int
        Number of KB entries actually written.
    errors : list[dict]
        Per-item error details.
    duration_s : float
        Wall-clock duration of the run.
    per_item_logs : list[dict]
        Log entry for each processed item (model, duration, scores).
    """

    domain: str
    total_items: int = 0
    passed_gates: int = 0
    kb_entries_created: int = 0
    errors: list[dict] = field(default_factory=list)
    duration_s: float = 0.0
    per_item_logs: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Cache loading
# ---------------------------------------------------------------------------


def load_cached_items(domain: str, base_path: str | Path = "collections") -> list[Item]:
    """Read cached items from ``collections/<domain>/<source>/<date>/<id>.json``.

    Parameters
    ----------
    domain : str
        Domain to load cached items for.
    base_path : str | Path, optional
        Root path for the collections directory (defaults to ``"collections"``).
        Useful for testing with temporary directories.

    Returns
    -------
    list[Item]
        Deserialized items (empty list when no cache directory exists).
    """
    items: list[Item] = []
    base_dir = Path(base_path) / domain

    if not base_dir.is_dir():
        logger.info("No cached items found for domain '%s'", domain)
        return items

    for source_dir in sorted(base_dir.iterdir()):
        if not source_dir.is_dir() or source_dir.name.startswith("_"):
            continue
        for date_dir in sorted(source_dir.iterdir()):
            if not date_dir.is_dir():
                continue
            for json_file in sorted(date_dir.glob("*.json")):
                try:
                    data = json.loads(json_file.read_text(encoding="utf-8"))
                    items.append(Item.from_dict(data))
                except (json.JSONDecodeError, KeyError, TypeError) as exc:
                    logger.warning(
                        "Skipping malformed cache file %s: %s", json_file, exc
                    )

    logger.info("Loaded %d cached items for domain '%s'", len(items), domain)
    return items


# ---------------------------------------------------------------------------
# Processing pipeline
# ---------------------------------------------------------------------------


def _build_config_with_model(
    config: Config | None,
    model: str | None,
) -> Config | None:
    """Return a *config* copy with the LLM model overridden.

    When *model* contains a ``/`` it is treated as ``provider/model``;
    otherwise only the model name is replaced and the provider is kept
    from the original config (or left empty).
    """
    if model is None:
        return config

    from copy import deepcopy

    if config is not None:
        cfg = deepcopy(config)
    else:
        # Minimal config so LLMExtractor can resolve the model string
        from autoinfo.config import LLMConfig

        cfg = Config(llm=LLMConfig())

    if "/" in model:
        provider, model_name = model.split("/", 1)
        cfg.llm.provider = provider
        cfg.llm.model = model_name
    else:
        cfg.llm.model = model

    return cfg


def run_processing(
    domain: str,
    model: str | None = None,
    topic: str | None = None,
) -> ProcessResult:
    """Main processing pipeline.

    Steps
    -----
    1. Load cached items from ``collections/<domain>/``.
    2. For each item:
       a. LLM extraction  (call :meth:`LLMExtractor.extract`)
       b. Quality gates   (call :func:`run_quality_gates`)
       c. KB storage      (call :meth:`KBStore.store_entry`)
       d. Per-item log    (model, duration, scores, …)
    3. Return a :class:`ProcessResult` with summary stats.

    If an individual item fails at any step the pipeline **continues**
    to the next item — a single failure does not abort the run.

    Parameters
    ----------
    domain : str
        Domain to process (e.g. ``"medical-research"``).
    model : str, optional
        LLM model override (e.g. ``"deepseek/deepseek-chat"`` or
        ``"gpt-4o-mini"``).  When *model* contains a ``/`` it is parsed
        as ``provider/model``; otherwise the provider from the config is
        kept.
    topic : str, optional
        Topic name used to resolve keywords for the G3 relevance gate.
        When omitted the gate scores without keywords (always passes).

    Returns
    -------
    ProcessResult
        Aggregate result with per-item logs.
    """
    start_time = time.time()

    # -- Load configuration -------------------------------------------------
    config_path = get_config_path()
    config: Config | None = None
    if config_path is not None:
        config = load_config(config_path)

    # -- Load cached items --------------------------------------------------
    cached_items = load_cached_items(domain)
    result = ProcessResult(domain=domain, total_items=len(cached_items))

    if not cached_items:
        result.duration_s = round(time.time() - start_time, 3)
        logger.info("No items to process for domain '%s'", domain)
        return result

    # -- Initialise components ----------------------------------------------
    proc_config = _build_config_with_model(config, model)
    extractor = LLMExtractor(config=proc_config)
    kb_store = KBStore()

    # Load existing entries for G2 dedup checking
    existing_entries = kb_store.list_entries(domain, limit=10000)

    # Resolve topic keywords from domain config (for G3)
    topic_keywords: list[str] = []
    if config and topic:
        for d in config.domains:
            if d.name == domain:
                for t in d.topics:
                    if t.name == topic:
                        topic_keywords = t.keywords
                        break

    # -- Process each item --------------------------------------------------
    for item in cached_items:
        item_start = time.time()
        item_log: dict[str, Any] = {
            "item_id": item.id,
            "title": item.title,
            "status": "ok",
        }

        try:
            # Step a: LLM extraction
            extraction = extractor.extract(item)
            item_log["tl_dr_length"] = len(extraction.tl_dr)
            item_log["key_points_count"] = len(extraction.key_points)
            item_log["relevance_score"] = extraction.relevance_score

            # Step b: Quality gates (G1, G2, G3)
            quality_results = run_quality_gates(
                item,
                context={
                    "existing_entries": existing_entries,
                    "topic_keywords": topic_keywords,
                },
            )

            g1 = quality_results.get("G1-SourceAuthority")
            g2 = quality_results.get("G2-Dedup")
            g3 = quality_results.get("G3-RelevanceScoring")

            item_log["g1_flagged"] = g1.flagged if g1 else False
            item_log["g2_passed"] = g2.passed if g2 else True
            item_log["g3_passed"] = g3.passed if g3 else True
            item_log["g3_score"] = g3.score if g3 else 0.0

            # Count how many gates passed (G1 always passes, G2+G3 matter)
            gates_passed = 0
            if g2 is not None and g2.passed:
                gates_passed += 1
            if g3 is not None and g3.passed:
                gates_passed += 1
            # G1 is advisory-only — always counted as passed
            if g1 is not None and g1.passed:
                gates_passed += 1

            # Step c: KB storage — store all items (quality gates are
            # advisory). Duplicates get marked in their frontmatter.
            if g2 is not None and not g2.passed:
                item_log["status"] = "duplicate"
                item_log["detail"] = str(g2.details.get("matched_by", "unknown"))

            entry = kb_store.store_entry(item, extraction, quality_results)
            item_log["entry_id"] = entry.entry_id
            result.kb_entries_created += 1

            # Track items that passed all gates
            if gates_passed == 3:
                result.passed_gates += 1

        except Exception as exc:
            logger.error("Processing failed for item %s: %s", item.id, exc)
            item_log["status"] = "error"
            item_log["error"] = str(exc)
            result.errors.append({"item_id": item.id, "error": str(exc)})

        item_log["duration_s"] = round(time.time() - item_start, 3)
        result.per_item_logs.append(item_log)

    result.duration_s = round(time.time() - start_time, 3)

    # -- Summary ------------------------------------------------------------
    logger.info(
        "Processing complete: %d items → %d passed G1-G3 → %d KB entries created",
        result.total_items,
        result.passed_gates,
        result.kb_entries_created,
    )

    return result
