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
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from autoinfo.config import Config, get_config_path, load_config
from autoinfo.kb import KBStore
from autoinfo.llm import LLMExtractor
from autoinfo.models import Item
from autoinfo.quality import G4FactualConsistency, QualityResult, run_quality_gates

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
    processed_count : int
        Number of items processed in this run (batch or full).
    remaining_count : int
        Number of items not yet processed (0 when batch is complete).
    is_complete : bool
        True when all cached items have been processed.
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
    processed_count: int = 0
    remaining_count: int = 0
    is_complete: bool = True
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
# SQLite progress tracking (for batch processing)
# ---------------------------------------------------------------------------


def _get_progress_db_path() -> Path:
    """Return the path to the shared SQLite database used by ``KBStore``."""
    return Path("knowledge").resolve().parent / "autoinfo.db"


def _init_progress_table(conn: sqlite3.Connection) -> None:
    """Create the ``processing_progress`` table if it does not exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS processing_progress (
            domain                  TEXT PRIMARY KEY,
            last_processed_index    INTEGER NOT NULL DEFAULT 0,
            total_items             INTEGER NOT NULL DEFAULT 0
        )
    """)


def _read_progress(domain: str) -> dict:
    """Read the persisted processing progress for *domain*.

    Returns
    -------
    dict
        Keys: ``last_processed_index`` (int), ``total_items`` (int).
        Returns zeroed values when no progress row exists.
    """
    db_path = _get_progress_db_path()
    # If the db does not exist yet there is no progress
    if not db_path.is_file():
        return {"last_processed_index": 0, "total_items": 0}
    try:
        with sqlite3.connect(str(db_path)) as conn:
            _init_progress_table(conn)
            row = conn.execute(
                "SELECT last_processed_index, total_items FROM processing_progress WHERE domain = ?",
                (domain,),
            ).fetchone()
            if row is not None:
                return {"last_processed_index": row[0], "total_items": row[1]}
    except sqlite3.OperationalError:
        logger.warning("Could not read processing progress for '%s'", domain)
    return {"last_processed_index": 0, "total_items": 0}


def _write_progress(domain: str, last_processed_index: int, total_items: int) -> None:
    """Persist the current processing progress for *domain*."""
    db_path = _get_progress_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sqlite3.connect(str(db_path)) as conn:
            _init_progress_table(conn)
            conn.execute(
                """INSERT OR REPLACE INTO processing_progress
                   (domain, last_processed_index, total_items)
                   VALUES (?, ?, ?)""",
                (domain, last_processed_index, total_items),
            )
    except sqlite3.OperationalError as exc:
        logger.warning("Could not write processing progress: %s", exc)


def _reset_progress(domain: str) -> None:
    """Delete the progress row for *domain* (forces a full re-process)."""
    db_path = _get_progress_db_path()
    if not db_path.is_file():
        return
    try:
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute(
                "DELETE FROM processing_progress WHERE domain = ?",
                (domain,),
            )
    except sqlite3.OperationalError:
        pass


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
    batch_size: int = 0,
    check_factual: bool = False,
) -> ProcessResult:
    """Main processing pipeline.

    Steps
    -----
    1. Load cached items from ``collections/<domain>/``.
    2. If *batch_size* > 0, read SQLite progress to determine the starting
       index and only process up to *batch_size* items.
    3. For each item:
       a. LLM extraction  (call :meth:`LLMExtractor.extract`)
       b. Quality gates   (call :func:`run_quality_gates`; optionally G4
                          factual consistency when *check_factual* is set)
       c. KB storage      (call :meth:`KBStore.store_entry`)
       d. Per-item log    (model, duration, scores, flags, …)
    4. When *batch_size* > 0, persist the updated progress index.
    5. Return a :class:`ProcessResult` with summary stats (including
       ``processed_count``, ``remaining_count``, ``is_complete``).

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
    batch_size : int, optional
        Max number of items to process in this run.  When 0 (default)
        all cached items are processed.  When > 0, progress is tracked
        in SQLite and subsequent calls pick up where the last call
        stopped.
    check_factual : bool, optional
        When ``True``, run the G4 factual consistency gate after G1-G3
        (requires an LLM call per item).  Defaults to ``False``.

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
    total_items = len(cached_items)

    # -- Determine which items to process (batch vs full) --------------------
    new_index = 0
    if batch_size > 0:
        progress = _read_progress(domain)
        start_index: int = progress["last_processed_index"]  # type: ignore[assignment]
        persisted_total: int = progress["total_items"]  # type: ignore[assignment]

        # If the cache grew (new items collected), restart from 0 so nothing
        # is missed.  If it shrank, also reset to avoid an out-of-range slice.
        if persisted_total != total_items:
            start_index = 0

        items_slice = cached_items[start_index : start_index + batch_size]
        processed_count = len(items_slice)
        new_index = start_index + processed_count
        remaining_count = total_items - new_index
        is_complete = new_index >= total_items
    else:
        items_slice = cached_items
        processed_count = total_items
        remaining_count = 0
        is_complete = True

    result = ProcessResult(
        domain=domain,
        total_items=total_items,
        processed_count=processed_count,
        remaining_count=remaining_count,
        is_complete=is_complete,
    )

    if not items_slice:
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

    # Resolve custom extract_fields from domain config
    extract_fields: list[str] | None = None
    if config:
        for d in config.domains:
            if d.name == domain and d.extract_fields:
                extract_fields = d.extract_fields
                break

    # -- Process each item --------------------------------------------------
    for item in items_slice:
        item_start = time.time()
        item_log: dict[str, Any] = {
            "item_id": item.id,
            "title": item.title,
            "status": "ok",
        }

        try:
            # Step a: LLM extraction (with custom schema if configured)
            extraction = extractor.extract(item, schema=extract_fields)
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

            # Step b2: Optional G4 factual consistency gate
            if check_factual and extraction.tl_dr:
                try:
                    g4_provider = (
                        proc_config.llm.provider
                        if proc_config and proc_config.llm.provider
                        else "openrouter"
                    )
                    g4_model_name = (
                        proc_config.llm.model
                        if proc_config and proc_config.llm.model
                        else "deepseek/deepseek-chat"
                    )
                    g4_model = f"{g4_provider}/{g4_model_name}"
                    g4 = G4FactualConsistency(model=g4_model)
                    g4_result = g4.check(item, extraction)
                    quality_results["G4-SummaryFactual"] = g4_result
                except Exception as exc:
                    logger.warning(
                        "G4 factual check failed for item %s: %s", item.id, exc
                    )
                    g4_result = QualityResult(
                        gate_name="G4-SummaryFactual",
                        passed=False,
                        flagged=True,
                        details={
                            "contradiction": None,
                            "explanation": str(exc),
                        },
                    )
                    quality_results["G4-SummaryFactual"] = g4_result

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

            # Log G4 if it ran
            g4_result = quality_results.get("G4-SummaryFactual")
            if g4_result is not None:
                item_log["g4_flagged"] = g4_result.flagged
                item_log["g4_contradiction"] = g4_result.details.get("contradiction")

            # Step c: KB storage — store all items (quality gates are
            # advisory). Duplicates get marked in their frontmatter.
            if g2 is not None and not g2.passed:
                item_log["status"] = "duplicate"
                item_log["detail"] = str(g2.details.get("matched_by", "unknown"))

            entry = kb_store.store_entry(item, extraction, quality_results)
            item_log["entry_id"] = entry.entry_id
            result.kb_entries_created += 1

            # Step d: Knowledge graph — store entities & discover relations
            if extraction and extraction.entities:
                kg_result = kb_store.store_entities(
                    entry_id=entry.entry_id,
                    domain=domain,
                    entities=extraction.entities,
                )
                item_log["entities_indexed"] = kg_result["entities_indexed"]
                item_log["relations_discovered"] = kg_result["relations_discovered"]

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

    # -- Persist progress (batch mode only) ---------------------------------
    if batch_size > 0:
        _write_progress(domain, new_index, total_items)

    result.duration_s = round(time.time() - start_time, 3)

    # -- Summary ------------------------------------------------------------
    g4_count = sum(
        1 for log in result.per_item_logs if log.get("g4_flagged") is not None
    )
    logger.info(
        "Processing complete: %d items → %d passed G1-G3 → %d KB entries created "
        "(batch=%d, remaining=%d, g4_checked=%d)",
        result.total_items,
        result.passed_gates,
        result.kb_entries_created,
        result.processed_count,
        result.remaining_count,
        g4_count,
    )

    return result


def get_processing_progress(domain: str) -> dict:
    """Return the current processing progress for *domain*.

    Parameters
    ----------
    domain : str
        Domain to query.

    Returns
    -------
    dict
        Keys: ``total_items``, ``processed_count``, ``remaining_count``,
        ``is_complete``.  When no progress has been recorded or all items
        are done, ``is_complete`` is ``True``.
    """
    progress = _read_progress(domain)
    total = progress["total_items"]
    processed = progress["last_processed_index"]
    remaining = total - processed
    is_complete = total == 0 or processed >= total
    return {
        "total_items": total,
        "processed_count": processed,
        "remaining_count": remaining,
        "is_complete": is_complete,
    }
