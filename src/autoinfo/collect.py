"""Collection orchestrator — coordinates source handlers and deduplication.

This is the core entry point for ``autoinfo collect``.  It reads domain
configuration, dispatches the appropriate source handlers (PubMed, RSS),
applies deduplication, and caches collected items to disk.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from autoinfo.config import Config, SourceConfig, get_config_path, load_config
from autoinfo.dedup import DedupChecker
from autoinfo.models import CollectionResult, Item, KBEntry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_collection(
    domain: str,
    topic: str = "",
    sources: list[str] | None = None,
    limit: int = 20,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Execute a full collection run for a domain.

    Parameters
    ----------
    domain : str
        Domain name to collect for (e.g. ``"medical-research"``).
    topic : str
        Optional topic filter (keyword used as search query for PubMed).
    sources : list[str] | None
        Optional list of source names to restrict collection to.
        When ``None``, all sources for the domain are collected.
    limit : int
        Maximum items to fetch per source (default 20).
    dry_run : bool
        When ``True``, return estimated counts without any storage
        operations (default ``False``).

    Returns
    -------
    dict
        Aggregate collection results with the following keys::

            {
                "collection_id": str,
                "domain": str,
                "total_found": int,
                "total_new": int,
                "duration_s": float,
                "per_source": [CollectionResult, ...],
                "dry_run": bool,
            }

    Raises
    ------
    FileNotFoundError
        If no configuration file is found.
    ValueError
        If *domain* is not found in config, or has no active sources.
    """
    start_time = time.time()
    collection_id = _make_collection_id()

    # -- Load configuration ------------------------------------------------
    config_path = get_config_path()
    if config_path is None:
        raise FileNotFoundError(
            "No configuration found. Run 'autoinfo init' first."
        )
    config = load_config(config_path)

    domain_config = _find_domain(config, domain)
    if domain_config is None:
        raise ValueError(f"Domain '{domain}' not found in configuration.")

    # -- Determine which sources to collect --------------------------------
    source_configs = _resolve_sources(domain_config.sources, sources)
    if not source_configs:
        raise ValueError(
            f"No active sources found for domain '{domain}'"
            + (f" matching: {sources}" if sources else "")
        )

    # -- Load existing KB entries for dedup --------------------------------
    checker = DedupChecker()
    existing_entries = checker.load_existing(domain)

    # -- Per-source collection ---------------------------------------------
    per_source: list[CollectionResult] = []

    for src_cfg in source_configs:
        logger.info(
            "Collecting from source '%s' (type=%s) ...",
            src_cfg.name,
            src_cfg.type,
        )

        src_result = _collect_from_source(
            source_config=src_cfg,
            domain=domain,
            topic=topic,
            limit=limit,
            dry_run=dry_run,
            existing_entries=existing_entries,
            collection_id=collection_id,
            checker=checker,
        )
        per_source.append(src_result)

    # -- Aggregate totals --------------------------------------------------
    total_found = sum(r.items_found for r in per_source)
    total_new = sum(r.items_new for r in per_source)
    elapsed = time.time() - start_time

    return {
        "collection_id": collection_id,
        "domain": domain,
        "total_found": total_found,
        "total_new": total_new,
        "duration_s": round(elapsed, 3),
        "per_source": [r.to_dict() for r in per_source],
        "dry_run": dry_run,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _find_domain(config: Config, domain: str) -> Any | None:
    """Find a domain config by name (checks active domains first)."""
    for d in config.domains:
        if d.name == domain and d.active:
            return d
    # Fallback: allow inactive if explicitly specified (user asked for it)
    for d in config.domains:
        if d.name == domain:
            return d
    return None


def _resolve_sources(
    all_sources: list[SourceConfig],
    requested: list[str] | None,
) -> list[SourceConfig]:
    """Filter the source list to only those requested (or all if ``None``)."""
    if not requested:
        return list(all_sources)

    requested_set = set(requested)
    return [s for s in all_sources if s.name in requested_set]


def _make_collection_id() -> str:
    """Generate a unique collection run identifier."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    short = uuid.uuid4().hex[:8]
    return f"col-{ts}-{short}"


def _collect_from_source(
    source_config: SourceConfig,
    domain: str,
    topic: str,
    limit: int,
    dry_run: bool,
    existing_entries: list[KBEntry],
    collection_id: str,
    checker: DedupChecker,
) -> CollectionResult:
    """Fetch items from a single source, deduplicate, and optionally cache."""
    src_start = time.time()
    errors: list[dict[str, Any]] = []

    # -- Determine and instantiate handler ---------------------------------
    try:
        handler = _build_handler(source_config)
    except ValueError as exc:
        logger.warning("Skipping source '%s': %s", source_config.name, exc)
        skipped_duration = round(time.time() - src_start, 3)
        _log_run(
            domain=domain,
            source_name=source_config.name,
            collection_id=collection_id,
            items_found=0,
            items_new=0,
            status="skipped",
            errors=[{"message": str(exc)}],
            duration_s=skipped_duration,
        )
        return CollectionResult(
            collection_id=collection_id,
            domain=domain,
            source=source_config.name,
            status="skipped",
            items_found=0,
            items_new=0,
            errors=[{"message": str(exc)}],
            duration_s=skipped_duration,
        )

    # -- Fetch items -------------------------------------------------------
    try:
        items = _fetch_items(handler, source_config, topic, limit)
    except Exception as exc:
        logger.error("Fetch failed for source '%s': %s", source_config.name, exc)
        error_duration = round(time.time() - src_start, 3)
        _log_run(
            domain=domain,
            source_name=source_config.name,
            collection_id=collection_id,
            items_found=0,
            items_new=0,
            status="error",
            errors=[{"message": f"Fetch failed: {exc}"}],
            duration_s=error_duration,
        )
        return CollectionResult(
            collection_id=collection_id,
            domain=domain,
            source=source_config.name,
            status="error",
            items_found=0,
            items_new=0,
            errors=[{"message": f"Fetch failed: {exc}"}],
            duration_s=error_duration,
        )

    items_found = len(items)

    # -- Apply dedup -------------------------------------------------------
    new_items: list[Item] = []
    for item in items:
        verdict = checker.check(item, existing_entries)
        if not verdict["is_duplicate"]:
            new_items.append(item)

    items_new = len(new_items)

    elapsed = round(time.time() - src_start, 3)

    # -- Cache (only if not dry_run) ---------------------------------------
    if not dry_run and new_items:
        _cache_items(new_items, domain, source_config.name)
        _log_run(
            domain, source_config.name, collection_id,
            items_found, items_new,
            status="success",
            duration_s=elapsed,
        )

    return CollectionResult(
        collection_id=collection_id,
        domain=domain,
        source=source_config.name,
        status="success" if not errors else "partial",
        items_found=items_found,
        items_new=items_new,
        errors=errors,
        duration_s=elapsed,
        estimated_duration_s=elapsed,
    )


def _build_handler(source_config: SourceConfig) -> Any:
    """Build the appropriate handler for a source configuration.

    Returns a handler instance with a common interface:

    * ``PubMedHandler`` — ``search(query, max_results)`` / ``fetch(pmids)``
      / ``to_item(article)``
    * ``RSSHandler`` — ``fetch(url) -> list[Item]``
    * ``WebHandler`` — ``fetch(url) -> list[Item]``

    Raises ``ValueError`` if the source type is unknown or unsupported.
    """
    name = (source_config.name or "").lower()
    stype = (source_config.type or "").lower()

    if stype == "api" and "pubmed" in name:
        from autoinfo.collectors.pubmed import PubMedHandler

        return PubMedHandler()

    if stype == "rss":
        from autoinfo.collectors.rss import RSSHandler

        return RSSHandler(source_name=source_config.name)

    if stype == "web":
        from autoinfo.collectors.web import WebHandler

        return WebHandler(source_name=source_config.name)

    if stype == "api":
        raise ValueError(
            f"Unsupported API source '{source_config.name}'. "
            f"Only 'pubmed' API sources are supported currently."
        )

    raise ValueError(
        f"Unknown source type '{source_config.type}' for source "
        f"'{source_config.name}'. Supported types: api (pubmed), rss, web."
    )


def _fetch_items(
    handler: Any,
    source_config: SourceConfig,
    topic: str,
    limit: int,
) -> list[Item]:
    """Fetch items from a handler.

    Dispatches based on handler type:
    * ``PubMedHandler`` — uses ``search()`` + ``fetch()`` + ``to_item()``
    * ``RSSHandler`` — uses ``fetch(url)`` directly
    * ``WebHandler`` — uses ``fetch(url)`` directly
    """
    # -- PubMed handler path -----------------------------------------------
    if hasattr(handler, "search") and hasattr(handler, "fetch"):
        query = topic if topic else source_config.name
        pmids = handler.search(query, max_results=limit)
        if not pmids:
            return []
        articles = handler.fetch(pmids)
        return [handler.to_item(a) for a in articles]

    # -- RSS handler path --------------------------------------------------
    if hasattr(handler, "fetch"):
        url = source_config.url
        if not url:
            logger.warning("RSS source '%s' has no URL configured", source_config.name)
            return []
        items = handler.fetch(url)
        # Apply limit
        return items[:limit]

    raise TypeError(f"Handler for '{source_config.name}' has no usable fetch method")


def _cache_items(
    items: list[Item],
    domain: str,
    source_name: str,
) -> None:
    """Write deduplicated items to ``collections/<domain>/<source>/<date>/<id>.json``."""
    today = date.today().isoformat()
    base_dir = Path("collections") / domain / source_name / today
    base_dir.mkdir(parents=True, exist_ok=True)

    for item in items:
        file_path = base_dir / f"{item.id}.json"
        # Avoid overwriting existing cached files (idempotent)
        if file_path.exists():
            continue
        with open(file_path, "w", encoding="utf-8") as fh:
            json.dump(item.to_dict(), fh, ensure_ascii=False, indent=2)


def _log_run(
    domain: str,
    source_name: str,
    collection_id: str,
    items_found: int,
    items_new: int,
    status: str = "success",
    errors: list[dict[str, Any]] | None = None,
    duration_s: float = 0.0,
) -> None:
    """Append a run entry to ``collections/<domain>/<source>/_runs.json``.

    Parameters
    ----------
    status:
        Run outcome: ``"success"``, ``"error"``, or ``"skipped"``.
    errors:
        Optional list of error dicts (only meaningful when status != success).
    duration_s:
        Wall-clock duration of the collection run in seconds.
    """
    runs_dir = Path("collections") / domain / source_name
    runs_dir.mkdir(parents=True, exist_ok=True)
    runs_path = runs_dir / "_runs.json"

    entry: dict[str, Any] = {
        "collection_id": collection_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "items_found": items_found,
        "items_new": items_new,
        "errors": errors or [],
        "duration_ms": round(duration_s * 1000, 1),
    }

    if runs_path.exists():
        try:
            with open(runs_path, "r", encoding="utf-8") as fh:
                runs: list[dict[str, Any]] = json.load(fh)
        except (json.JSONDecodeError, FileNotFoundError):
            runs = []
    else:
        runs = []

    runs.append(entry)

    with open(runs_path, "w", encoding="utf-8") as fh:
        json.dump(runs, fh, ensure_ascii=False, indent=2)


def list_active_collections() -> list[dict[str, Any]]:
    """Return a list of active/in-progress collection runs.

    Reads the latest runs from ``collections/_runs.json`` and returns
    any that do not have a terminal status (``completed``, ``failed``).
    Falls back to returning the 5 most recent runs if no active run
    is found.
    """
    runs_path = Path("collections") / "_runs.json"
    if not runs_path.is_file():
        return []

    try:
        with open(runs_path, "r", encoding="utf-8") as fh:
            runs: list[dict[str, Any]] = json.load(fh)
    except (json.JSONDecodeError, FileNotFoundError):
        return []

    terminal_statuses = frozenset({"completed", "failed", "cancelled"})
    active = [r for r in runs if r.get("status", "") not in terminal_statuses]
    if active:
        return sorted(active, key=lambda x: x.get("timestamp", ""), reverse=True)

    # No active runs — return the 5 most recent for visibility
    recent = sorted(runs, key=lambda x: x.get("timestamp", ""), reverse=True)
    return recent[:5]
