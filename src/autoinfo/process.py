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
from autoinfo.keywords import KeywordState, KeywordsFile
from autoinfo.llm import LLMExtractor
from autoinfo.models import Item
from autoinfo.quality import G4FactualConsistency, G5TranslationAccuracy, QualityResult, run_quality_gates

logger = logging.getLogger(__name__)

# Minimal stop sets for keyword auto-discovery (Step e in processing pipeline)
_STOP_WORDS: frozenset[str] = frozenset({
    "the", "this", "that", "with", "from", "have", "been", "were",
    "their", "which", "about", "study", "also", "show", "shown",
    "using", "used", "may", "results", "result", "method", "methods",
    "however", "conclusion", "background", "objective", "aim",
})
_STOP_PHRASES: frozenset[str] = frozenset({"", "  ", "   "})


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------


def detect_language(text: str) -> str:
    """Auto-detect the language of *text* using ``langdetect``.

    Returns a language code (e.g. ``"en"``, ``"zh-cn"``) when confidence
    is ≥ 0.8 and text has ≥ 20 characters.  Returns ``"unknown"`` for
    short/noisy text or when detection fails.

    .. note::
        Non-blocking — returns ``"unknown"`` when ``langdetect`` is not
        installed or ``LangDetectException`` is raised.
    """
    if len(text.strip()) < 20:
        return "unknown"
    try:
        from langdetect import detect_langs, LangDetectException as _LDE
    except ImportError:
        logger.debug("langdetect not installed — language detection disabled")
        return "unknown"

    try:
        langs = detect_langs(text)
        if not langs:
            return "unknown"
        top = langs[0]
        if top.prob < 0.8:
            return "unknown"
        return top.lang
    except _LDE:
        return "unknown"


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
# CEFR classification helper (non-blocking, post-store)
# ---------------------------------------------------------------------------


def _update_index_cefr(entry_id: str, cefr_level: str) -> None:
    """Persist *cefr_level* on the SQLite index row for *entry_id*.

    Non-blocking: any failure is logged and swallowed.
    """
    try:
        from autoinfo.kb import KBStore

        store = KBStore()
        with store.index._connect() as conn:
            conn.execute(
                "UPDATE entries SET cefr = ? WHERE entry_id = ?",
                (cefr_level, entry_id),
            )
    except Exception as exc:
        logger.debug("Failed to update cefr in index for %s: %s", entry_id, exc)


def _classify_entry_cefr(
    entry: Any,
    item: Item,
    config: Config,
) -> None:
    """Run CEFR classification on *item* and store result in entry frontmatter.

    Called after ``store_entry()``.  Failures are logged but do **not**
    propagate — classification must never block entry creation.

    Steps
    -----
    1. Determine language from the item (detected language or config default).
    2. If the language is not in ``config.cefr.languages``, skip.
    3. Call ``classify_text()``.
    4. If a level was returned (not "unknown"), write it to the frontmatter
       of the entry's Markdown file as ``cefr: <level>``.
    """
    try:
        # Determine language: use detected language, or fall back to "en"
        lang = item.language or "en"
        # Normalize: langdetect returns "zh-cn" etc. — take the base
        lang = lang.split("-")[0] if lang else "en"

        # Check if language is configured for CEFR
        if lang not in config.cefr.languages:
            return

        # Build model config from the effective LLM config
        model_config: dict[str, Any] = {}
        if config.cefr.model:
            model_config["model"] = config.cefr.model
        elif config.llm.provider and config.llm.model:
            model_config["model"] = f"{config.llm.provider}/{config.llm.model}"
        if config.llm.api_key:
            model_config["api_key"] = config.llm.api_key
        if config.llm.base_url:
            model_config["base_url"] = config.llm.base_url

        # Classify the text (title + content, truncated)
        text_for_classification = f"{item.title}\n\n{item.content}"[:3000]
        from autoinfo.cefr import classify_text

        result = classify_text(
            text=text_for_classification,
            lang=lang,
            model_config=model_config,
        )

        cefr_level = result.get("cefr_level", "unknown")
        if cefr_level != "unknown":
            from autoinfo.kb import update_frontmatter_field

            update_frontmatter_field(
                file_path=entry.file_path,
                key="cefr",
                value=cefr_level,
            )
            _update_index_cefr(entry.entry_id, cefr_level)
            logger.debug(
                "CEFR classification for %s: %s (confidence=%.2f)",
                entry.entry_id,
                cefr_level,
                result.get("confidence", 0.0),
            )
    except Exception as exc:
        logger.debug(
            "CEFR classification skipped for item %s: %s",
            getattr(item, "id", "?"),
            exc,
        )


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
    check_translation: bool = False,
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
                           factual consistency when *check_factual* is set,
                           and optionally G5 translation accuracy when
                           *check_translation* is set)
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
    check_translation : bool, optional
        When ``True``, run the G5 translation accuracy gate after G4
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

            # Step b3: Optional G5 translation accuracy gate
            if check_translation:
                try:
                    g5_model = (
                        f"{proc_config.llm.provider}/{proc_config.llm.model}"
                        if proc_config and proc_config.llm.provider and proc_config.llm.model
                        else "openrouter/deepseek/deepseek-chat"
                    )
                    g5 = G5TranslationAccuracy(model=g5_model)
                    g5_result = g5.check(item, extraction)
                    quality_results["G5-TranslationAccuracy"] = g5_result
                except Exception as exc:
                    logger.warning(
                        "G5 translation check failed for item %s: %s", item.id, exc
                    )
                    g5_result = QualityResult(
                        gate_name="G5-TranslationAccuracy",
                        passed=False,
                        flagged=True,
                        details={
                            "faithful": None,
                            "explanation": str(exc),
                            "issues": [],
                        },
                    )
                    quality_results["G5-TranslationAccuracy"] = g5_result

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

            # Log G5 if it ran
            g5_result = quality_results.get("G5-TranslationAccuracy")
            if g5_result is not None:
                item_log["g5_flagged"] = g5_result.flagged
                item_log["g5_faithful"] = g5_result.details.get("faithful")

            # Step c0: Language detection (non-blocking)
            text_for_lang = f"{item.title} {item.content}"
            detected_lang = detect_language(text_for_lang)
            item.language = detected_lang
            item_log["language"] = detected_lang

            # Step c: KB storage — store all items (quality gates are
            # advisory). Duplicates get marked in their frontmatter.
            if g2 is not None and not g2.passed:
                item_log["status"] = "duplicate"
                item_log["detail"] = str(g2.details.get("matched_by", "unknown"))

            entry = kb_store.store_entry(item, extraction, quality_results)
            item_log["entry_id"] = entry.entry_id
            result.kb_entries_created += 1

            # Step c2: CEFR classification (non-blocking — only when enabled)
            if config is not None and config.cefr.enabled:
                _classify_entry_cefr(entry, item, config)

            # Step d: Knowledge graph — store entities & discover relations
            if extraction and extraction.entities:
                kg_result = kb_store.store_entities(
                    entry_id=entry.entry_id,
                    domain=domain,
                    entities=extraction.entities,
                )
                item_log["entities_indexed"] = kg_result["entities_indexed"]
                item_log["relations_discovered"] = kg_result["relations_discovered"]

            # Step e: Keyword auto-discovery — extract new keywords from LLM response
            discovered: list[str] = []
            if extraction:
                # Collect entity names as keyword candidates
                for entity in extraction.entities:
                    name = entity.get("name", "").strip().lower()
                    if name and len(name) > 1:
                        discovered.append(name)
                # Collect key-point phrases as keyword candidates
                for kp in extraction.key_points:
                    words = [w.strip().lower() for w in kp.split() if len(w.strip()) > 2]
                    # Use short phrases (2-4 words) as single keywords
                    for i in range(len(words)):
                        # Single words that aren't stop-word-ish
                        w = words[i]
                        if len(w) > 3 and w not in _STOP_WORDS:
                            discovered.append(w)
                    for n in (2, 3):
                        phrases = [" ".join(words[i:i + n]) for i in range(len(words) - n + 1)]
                        for p in phrases:
                            if p not in _STOP_PHRASES:
                                discovered.append(p)

            if discovered:
                kf = KeywordsFile()
                # Deduplicate and add
                seen: set[str] = set()
                for kw in discovered:
                    if kw not in seen:
                        seen.add(kw)
                        try:
                            kf.add_keyword(
                                domain=domain,
                                keyword=kw,
                                state=KeywordState.AUTO_ADDED,
                                source=f"auto-discovery:{item.source_name}",
                            )
                        except Exception:
                            logger.debug("Failed to add discovered keyword '%s':", kw, exc_info=True)
                item_log["keywords_discovered"] = len(seen)

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
    g5_count = sum(
        1 for log in result.per_item_logs if log.get("g5_flagged") is not None
    )
    logger.info(
        "Processing complete: %d items → %d passed G1-G3 → %d KB entries created "
        "(batch=%d, remaining=%d, g4_checked=%d, g5_checked=%d)",
        result.total_items,
        result.passed_gates,
        result.kb_entries_created,
        result.processed_count,
        result.remaining_count,
        g4_count,
        g5_count,
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
