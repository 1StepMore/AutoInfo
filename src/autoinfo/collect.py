"""Collection orchestrator — coordinates source handlers and deduplication.

This is the core entry point for ``autoinfo collect``.  It reads domain
configuration, dispatches the appropriate source handlers (PubMed, RSS),
applies deduplication, and caches collected items to disk.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import threading
import time
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, NamedTuple

import httpx

from autoinfo.alerts import check_alerts, check_source_alerts, check_source_credentials
from autoinfo.checkpoint import (
    RUN_COMPLETE,
    RUN_PARTIAL,
    RUN_RUNNING,
    STEP_COMPLETED,
    CheckpointStore,
    PipelineCheckpoint,
    StepCheckpoint,
    make_signature,
)
from autoinfo.collectors.base import Collector, CollectorContext, SourceFailure
from autoinfo.collectors.registry import (
    build_collector,
    handler_settings,
    registered_source_types,
)
from autoinfo.collectors.robots import RobotsDisallowed
from autoinfo.config import Config, SourceConfig, get_config_path, load_config
from autoinfo.cost import CostMeter
from autoinfo.dedup import DedupChecker
from autoinfo.defaults import COLLECTIONS_DIR
from autoinfo.models import CollectionResult, Item, KBEntry

logger = logging.getLogger(__name__)
from autoinfo.logging import get_pipeline_logger  # noqa: E402

plog = get_pipeline_logger("collect")

#: Checkpoint namespace for a collection run (per-source resume cursor).
_COLLECT_PIPELINE = "collect"


# ---------------------------------------------------------------------------
# Collection-layer domain topic guard (#332-B)
#
# Prevents dirty data entering the raw cache at collection time: e.g.
# ai-commercial digests drifting in financial/regulatory/macro items
# (贝达药业, 华能, SEC 8-K, 财报 …) or financial-intelligence SEC 8-K/10-Q
# pure-metadata dilution.  The product-layer guards (#319, D-governance) can
# only see what was already collected; this keeps noise out at 入库时 so
# every downstream product is clean by construction.
# ---------------------------------------------------------------------------

# Per-domain "surface" keyword → drop the item when it appears in the
# item's title/summary.  Deliberately surface markers (company names /
# form numbers), NOT broad health terms — e.g. "clinical trial" legitimately
# appears in AI-commercial content ("AI drug discovery").
#
# The bare form numbers ("8-K", "10-K", "10-Q") are required because real
# SEC EDGAR titles are `8-K Apple Inc. (2025-01-15)` — the "SEC 8-K" /
# "8-K filing" phrasings never appear in them, so without the bare forms the
# guard silently misses 8-K/10-K at collection time (#332-B).
_DOMAIN_NOISE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "ai-commercial": (
        "贝达药业",
        "华能",
        "株冶",
        "平安好医生",
        "DURAVYU",
        "SEC 8-K",
        "SEC 8K",
        "8-K",
        "10-K",
        "10-Q",
        "10Q",
        "财报",
        "年度报告",
    ),
    "financial-intelligence": (
        "SEC 8-K",
        "SEC 8K",
        "8-K",
        "10-K",
        "10-Q",
        "10Q",
        "8-K filing",
    ),
}

# URL-path noise per domain (#137): drop items whose source URL path is a
# known out-of-domain section BEFORE they enter the raw cache.  Unlike the
# keyword guard above (title+content substring), this is a URL-PATH-level
# check, so legitimate company news (FTC suits, earnings, strategy) that
# merely mentions a brand is never caught.  TheStreet /deals/ /shopping/
# sections are consumer-retail deals, out-of-domain for financial products.
_DOMAIN_NOISE_URL_SUBSTRINGS: dict[str, tuple[str, ...]] = {
    "financial-intelligence": (
        "/deals/",
        "/shopping/",
    ),
}


def _item_matches_domain_noise(item: Item, domain: str) -> bool:
    """True when the item's title+summary matches a surface noise keyword
    for *domain* (#332-B), or its source URL path is a known out-of-domain
    section (#137).  Deterministic substring match, no LLM."""
    keywords = _DOMAIN_NOISE_KEYWORDS.get(domain)
    if keywords:
        haystack = f"{item.title}\n{item.content}".casefold()
        if any(str(kw).casefold() in haystack for kw in keywords):
            return True
    url_substrings = _DOMAIN_NOISE_URL_SUBSTRINGS.get(domain)
    if url_substrings:
        url = str(item.source_url or "").casefold()
        if any(sub.casefold() in url for sub in url_substrings):
            return True
    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_collection(
    domain: str,
    topic: str = "",
    sources: list[str] | None = None,
    limit: int = 20,
    dry_run: bool = False,
    force_full: bool = False,
    progress_cb: Callable[[CollectionResult], None] | None = None,
    resume_from: str | None = None,
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
    progress_cb : Callable[[CollectionResult], None] | None
        Optional callback invoked with each per-source ``CollectionResult``
        as soon as that source finishes. CLI-only, human-facing progress
        reporting — the MCP surface never passes one (its results are
        polled asynchronously; see docs/dev/cli-mcp-rest-parity.md).
    resume_from : str | None
        Optional checkpoint/resume mode for a long collection run
        (R-A-01).  When set, per-source completion is checkpointed to
        ``collections/<domain>/_checkpoint/collect.json`` and the run skips
        work already recorded:

        * ``"auto"`` — load the checkpoint and skip every source already
          recorded ``completed`` (the interrupted run's cursor).
        * ``"start"`` — run every source but enable checkpointing (a fresh
          run that can be resumed on the next invocation).
        * ``"<source-name>"`` — start at that source, skipping the sources
          declared before it.

        Sources that errored during a prior run are **not** marked completed
        and are therefore retried on resume.  ``None`` (default) keeps the
        legacy behaviour byte-identical and writes no checkpoint.

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
                "unknown_sources": [str, ...],  # requested names not in config
                "resumed_skipped": [str, ...],  # sources skipped by resume
                "dry_run": bool,
            }

    Raises
    ------
    FileNotFoundError
        If no configuration file is found.
    ValueError
        If *domain* is not found in config, or has no active sources, or
        *resume_from* names a source that is not part of this run.
    """
    start_time = time.time()
    collection_id = _make_collection_id()

    # -- Load configuration ------------------------------------------------
    config_path = get_config_path()
    if config_path is None:
        raise FileNotFoundError("No configuration found. Run 'autoinfo init' first.")
    config = load_config(config_path)

    domain_config = _find_domain(config, domain)
    if domain_config is None:
        raise ValueError(f"Domain '{domain}' not found in configuration.")

    # -- Resolve topic keywords for relevance filtering (#177) --------------
    keywords = _resolve_topic_keywords(domain_config, topic)

    # -- Determine which sources to collect --------------------------------
    source_configs, unknown_sources = _resolve_sources(domain_config.sources, sources)
    if not source_configs:
        if sources:
            available = ", ".join(s.name for s in domain_config.sources) or "(none)"
            raise ValueError(
                f"Unknown source(s) for domain '{domain}': "
                f"{', '.join(unknown_sources)}. Available sources: {available}"
            )
        raise ValueError(f"No active sources found for domain '{domain}'")

    # -- Load existing KB entries for dedup --------------------------------
    checker = DedupChecker()
    # Cross-domain: scan every domain's 01-Raw so the SECOND domain's copy of
    # a shared event is skipped (backup issue #109).
    existing_entries = checker.load_all_domains_entries()

    # -- Checkpoint/resume setup (R-A-01) ----------------------------------
    # Opt-in only: ``resume_from`` must be set, so a legacy run writes no
    # checkpoint file and behaves byte-identically to before.
    cp_store = CheckpointStore()
    cp: PipelineCheckpoint | None = None
    skip_sources: set[str] = set()
    source_names = [s.name for s in source_configs]
    if resume_from:
        signature = make_signature(domain=domain, topic=topic, sources=source_names, limit=limit)
        cp = cp_store.load(domain, _COLLECT_PIPELINE)
        if resume_from == "auto":
            if cp is not None and cp.signature == signature:
                skip_sources = set(cp.completed_steps())
            else:
                # No usable checkpoint — start fresh but keep checkpointing.
                cp = None
        elif resume_from != "start":
            if resume_from not in source_names:
                raise ValueError(
                    f"Cannot resume from unknown source '{resume_from}'. "
                    f"Available sources: {', '.join(source_names)}"
                )
            skip_sources = set(source_names[: source_names.index(resume_from)])
        if cp is None or cp.signature != signature:
            cp = PipelineCheckpoint(
                domain=domain,
                pipeline=_COLLECT_PIPELINE,
                signature=signature,
                steps=[StepCheckpoint(name=n) for n in source_names],
            )
        cp.status = RUN_RUNNING
        cp_store.save(cp)

    # -- Per-source collection ---------------------------------------------
    per_source: list[CollectionResult] = []
    all_new_items: list[Item] = []
    resumed_skipped: list[str] = []

    for src_cfg in source_configs:
        if src_cfg.name in skip_sources:
            plog.info(
                "Skipping completed source (resume)",
                source_type=src_cfg.type,
                extra={"source_name": src_cfg.name},
                trace_id=collection_id,
            )
            resumed_skipped.append(src_cfg.name)
            continue

        plog.info(
            "Collecting from source",
            source_type=src_cfg.type,
            extra={"source_name": src_cfg.name},
            trace_id=collection_id,
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
            new_items_collector=all_new_items,
            force_full=force_full,
            keywords=keywords,
        )
        per_source.append(src_result)
        if progress_cb is not None:
            progress_cb(src_result)

        # Mark a source completed only on a real fetch success; an errored
        # source stays pending so the next resume retries it.
        if cp is not None and src_result.status in ("success", "partial"):
            cp.mark(src_cfg.name, STEP_COMPLETED)
            cp_store.save(cp)

    if cp is not None:
        pending = [s.name for s in cp.steps if s.status not in (STEP_COMPLETED,)]
        cp.status = RUN_COMPLETE if not pending else RUN_PARTIAL
        cp_store.save(cp)

    # -- Aggregate totals --------------------------------------------------
    total_found = sum(r.items_found for r in per_source)
    total_new = sum(r.items_new for r in per_source)
    elapsed = time.time() - start_time

    # -- Fire webhooks (fire-and-forget) -----------------------------------
    if not dry_run and domain_config.webhook_urls and all_new_items:
        _fire_webhooks_sync(domain, all_new_items, domain_config.webhook_urls)

    # -- Check alert rules (fire-and-forget) --------------------------------
    if not dry_run and all_new_items:
        for _item in all_new_items:
            try:
                check_alerts(_item, domain)
            except Exception:
                logger.exception("Alert check failed for item '%s'", _item.id)

    # -- B3 escalation: missing source credentials reach operators ----------
    # A configured source that requires a key with no key configured is a
    # blocking issue only the B3 human can resolve (user-lifecycle-definition
    # §4.1). Push a `source_requires_key` agent-callback event and evaluate
    # source_credential_missing alert rules through the delivery channels.
    if not dry_run:
        try:
            missing = check_source_credentials(domain)
            if missing:
                from autoinfo.agent_callback import notify_source_requires_key

                for cred in missing:
                    notify_source_requires_key(
                        source=cred["source"],
                        source_type=cred["source_type"],
                        key_ref=cred["key_ref"],
                        domain=domain,
                    )
                check_source_alerts(domain, missing)
        except Exception:
            logger.exception("Source credential check failed for domain '%s'", domain)

    return {
        "collection_id": collection_id,
        "domain": domain,
        "total_found": total_found,
        "total_new": total_new,
        "items_filtered": sum(r.items_filtered for r in per_source),
        "items_duplicate": sum(r.items_duplicate for r in per_source),
        "duration_s": round(elapsed, 3),
        "per_source": [r.to_dict() for r in per_source],
        "unknown_sources": unknown_sources,
        "resumed_skipped": resumed_skipped,
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
) -> tuple[list[SourceConfig], list[str]]:
    """Filter the source list to only those requested (or all if ``None``).

    Returns ``(resolved, unknown)`` where *unknown* lists the requested
    source names that are not present in *all_sources* — they are never
    silently dropped (issue #296).  When *requested* is ``None``/empty,
    *unknown* is empty and all sources are returned.

    ``enabled: false`` sources are always excluded, whether requested by
    name or collected as part of the default set (issues #6/#7 — disabled
    feeds must not be fetched).
    """
    active = [s for s in all_sources if bool(s.settings.get("enabled", True))]
    if not requested:
        return active, []

    requested_set = set(requested)
    resolved = [s for s in active if s.name in requested_set]
    known_names = {s.name for s in all_sources}
    unknown = [name for name in requested if name not in known_names]
    return resolved, unknown


def _make_collection_id() -> str:
    """Generate a unique collection run identifier."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    short = uuid.uuid4().hex[:8]
    return f"col-{ts}-{short}"


def _resolve_topic_keywords(domain_config: Any, topic: str) -> list[str]:
    """Resolve the keyword list used for topic-relevance filtering (#177).

    When *topic* names a configured topic, only that topic's keywords apply;
    otherwise the union of all domain topics' keywords is used (order-
    preserving, deduplicated). Returns ``[]`` when nothing is configured —
    callers must then skip filtering so keyword-less domains behave exactly
    as before the filter existed.
    """
    topics = getattr(domain_config, "topics", [])
    candidates = [t for t in topics if t.name == topic] if topic else []
    if not candidates:
        candidates = list(topics)
    keywords: list[str] = []
    for t in candidates:
        for kw in getattr(t, "keywords", []) or []:
            if kw and kw not in keywords:
                keywords.append(kw)
    return keywords


# ---------------------------------------------------------------------------
# Topic-keyword relevance filter (#177) — source-type aware
# ---------------------------------------------------------------------------
# The filter exists to keep cross-disciplinary *search platforms* on-domain
# (OpenAlex/CrossRef/Semantic Scholar returning "Loot Crates" for a medical
# query).  Curated niche feeds (publication RSS like retail-dive/techcrunch,
# provider APIs like pubmed) are topical by construction — the source itself
# is the relevance signal — so filtering them drops real items (the #177
# over-filtering regression).  Classification mirrors the name-based
# dispatch in ``_build_handler``.
CROSS_DISCIPLINARY_SOURCE_TYPES: frozenset[str] = frozenset(
    {
        "openalex",
        "dblp",
        "web",
    }
)
# Generic ``api`` handlers whose NAME marks a cross-disciplinary platform.
# (Deep-imported alongside ``_build_handler``: Semantic Scholar, CrossRef.)
CROSS_DISCIPLINARY_API_NAME_MARKERS: tuple[str, ...] = ("semantic", "crossref")
# Token-level word splitter for partial-word matching ("retail" -> "retailer",
# "gene" -> "gene-editing").
_WORD_RE = re.compile(r"[a-z0-9]+")


def _is_cross_disciplinary_source(source_config: SourceConfig) -> bool:
    """Return True when *source_config* is a cross-disciplinary search platform.

    Such platforms execute a broad query over a cross-topic corpus, so an
    item's on-domain-ness can only be judged by topic keywords (#177).
    Everything else — curated publication RSS, provider APIs (pubmed, uspto,
    coursera), site-scoped Google News feeds — is topical by construction
    and is never keyword-filtered.
    """
    stype = (source_config.type or "").lower()
    if stype in CROSS_DISCIPLINARY_SOURCE_TYPES:
        return True
    if stype == "api":
        name = (source_config.name or "").lower()
        if any(marker in name for marker in CROSS_DISCIPLINARY_API_NAME_MARKERS):
            return True
    # Google News search RSS: unscoped feeds (news.google.com/rss,
    # /search?q=...) return cross-topic headlines; site-scoped queries
    # (q=site:...) are effectively curated per-site feeds.
    if stype == "rss":
        url = (source_config.url or "").lower()
        if "news.google.com/rss" in url and "q=site:" not in url:
            return True
    return False


def _keyword_matches(keyword: str, text: str) -> bool:
    """Return True when every word of *keyword* appears in *text*.

    Matching is case-insensitive, token-level, partial-word aware: a word
    matches when it occurs at a word boundary as a prefix of a longer token
    — "retail" matches "retailers", "gene" matches "gene-editing" — so
    inflected/hyphenated forms of a keyword count even though a naive
    substring match would miss them.
    """
    words = _WORD_RE.findall(keyword.lower())
    if not words:
        return False
    return all(re.search(rf"(?<![a-z0-9]){re.escape(w)}", text) is not None for w in words)


def _matches_keywords(
    item: Item,
    keywords: list[str] | None,
    min_keywords: int = 1,
) -> bool:
    """Return True when at least *min_keywords* topic keywords match *item*.

    A keyword matches when every one of its words appears (partial-word
    aware) in title or content.  The *min_keywords* floor (default 1)
    requires that many distinct keywords to match, tolerating a single
    loose phrase while still rejecting keyword-less items.  An empty
    keyword list keeps every item so keyword-less domains never lose data.
    """
    if not keywords:
        return True
    text = f"{item.title or ''} {item.content or ''}".lower()
    matched = 0
    for kw in keywords:
        if kw and _keyword_matches(kw, text):
            matched += 1
            if matched >= min_keywords:
                return True
    return False


def _collect_from_source(
    source_config: SourceConfig,
    domain: str,
    topic: str,
    limit: int,
    dry_run: bool,
    existing_entries: list[KBEntry],
    collection_id: str,
    checker: DedupChecker,
    new_items_collector: list[Item] | None = None,
    force_full: bool = False,
    keywords: list[str] | None = None,
) -> CollectionResult:
    """Fetch items from a single source, deduplicate, and optionally cache."""
    src_start = time.time()
    errors: list[dict[str, Any]] = []

    # -- Determine and instantiate handler ---------------------------------
    try:
        handler = _build_handler(source_config)
    except ValueError as exc:
        plog.warning(
            "Skipping source",
            source_type=source_config.type,
            extra={"source_name": source_config.name, "error": str(exc)},
        )
        skipped_duration = round(time.time() - src_start, 3)
        if not dry_run:
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

    # -- App-review gate (fail-closed) --------------------------------------
    # 委托人的硬约束「不做违法采集」的机器强制点。
    # 源声明 requires_app_review（配置或 handler）且未获显式确认 → **跳过**，
    # 而不是照常采集。以前这个声明零消费者（yaml 那键掉进 settings 无人读）。
    app_review_reason = _app_review_block_reason(source_config, handler)
    if app_review_reason:
        plog.warning(
            "Skipping source: app review required and not acknowledged",
            source_type=source_config.type,
            extra={
                "source_name": source_config.name,
                "reason": app_review_reason,
                "override": "set app_review_ack: true on the source, or AUTOINFO_APP_REVIEW_ACK=1",
            },
        )
        gate_duration = round(time.time() - src_start, 3)
        if not dry_run:
            _log_run(
                domain=domain,
                source_name=source_config.name,
                collection_id=collection_id,
                items_found=0,
                items_new=0,
                status="skipped",
                errors=[{"message": app_review_reason, "app_review_required": True}],
                duration_s=gate_duration,
            )
        return CollectionResult(
            collection_id=collection_id,
            domain=domain,
            source=source_config.name,
            status="skipped",
            items_found=0,
            items_new=0,
            errors=[{"message": app_review_reason, "app_review_required": True}],
            duration_s=gate_duration,
        )

    # -- Fetch items -------------------------------------------------------
    try:
        items = _fetch_items(handler, source_config, topic, limit, keywords)
    except SourceFailure as exc:
        plog.error(
            "Source failed",
            source_type=source_config.type,
            extra={"source_name": source_config.name, "reason": exc.reason},
        )
        error_duration = round(time.time() - src_start, 3)
        error_dict = {
            "message": str(exc),
            "source_failed": True,
            "reason": exc.reason,
        }
        if not dry_run:
            _log_run(
                domain=domain,
                source_name=source_config.name,
                collection_id=collection_id,
                items_found=0,
                items_new=0,
                status="error",
                errors=[error_dict],
                duration_s=error_duration,
            )
        return CollectionResult(
            collection_id=collection_id,
            domain=domain,
            source=source_config.name,
            status="error",
            items_found=0,
            items_new=0,
            errors=[error_dict],
            source_failed=True,
            duration_s=error_duration,
        )
    except RobotsDisallowed as exc:
        # robots.txt forbids the source URL — a policy outcome, not an
        # error: record it as "skipped" (mirrors the skipped path above).
        plog.warning(
            "Skipping source",
            source_type=source_config.type,
            extra={
                "source_name": source_config.name,
                "error": str(exc),
                "robots_disallowed": True,
            },
        )
        robots_duration = round(time.time() - src_start, 3)
        robots_dict = {
            "message": str(exc),
            "robots_disallowed": True,
        }
        if not dry_run:
            _log_run(
                domain=domain,
                source_name=source_config.name,
                collection_id=collection_id,
                items_found=0,
                items_new=0,
                status="skipped",
                errors=[robots_dict],
                duration_s=robots_duration,
            )
        return CollectionResult(
            collection_id=collection_id,
            domain=domain,
            source=source_config.name,
            status="skipped",
            items_found=0,
            items_new=0,
            errors=[robots_dict],
            duration_s=robots_duration,
        )
    except Exception as exc:
        plog.error(
            "Fetch failed for source",
            source_type=source_config.type,
            extra={"source_name": source_config.name, "error": str(exc)},
        )
        error_duration = round(time.time() - src_start, 3)
        error_dict = {
            "message": f"Fetch failed: {exc}",
            "source_failed": True,
            "reason": str(exc),
        }
        if not dry_run:
            _log_run(
                domain=domain,
                source_name=source_config.name,
                collection_id=collection_id,
                items_found=0,
                items_new=0,
                status="error",
                errors=[error_dict],
                duration_s=error_duration,
            )
        return CollectionResult(
            collection_id=collection_id,
            domain=domain,
            source=source_config.name,
            status="error",
            items_found=0,
            items_new=0,
            errors=[error_dict],
            source_failed=True,
            duration_s=error_duration,
        )

    items_found = len(items)

    # -- Topic-keyword relevance filter (#177) ------------------------------
    # Curated sources skip the filter entirely (topical by construction),
    # so they keep every item and report 0 filtered — the #177 regression fix.
    kept_items: list[Item] = []
    items_filtered = 0
    if _is_cross_disciplinary_source(source_config):
        for item in items:
            if _matches_keywords(item, keywords):
                kept_items.append(item)
            else:
                items_filtered += 1
    else:
        kept_items = items
    if items_filtered:
        plog.info(
            "Relevance filter dropped items",
            source_type=source_config.type,
            extra={
                "source_name": source_config.name,
                "items_found": items_found,
                "items_filtered": items_filtered,
                "items_kept": len(kept_items),
            },
        )
    items = kept_items

    # Ensure every item carries the correct domain and source quality tier
    for item in items:
        item.domain = domain
        item.quality_tier = source_config.quality_tier

    # Log API call cost (non-blocking — failures are swallowed)
    try:
        CostMeter().log_api_call(
            source_type=source_config.type,
            domain=domain,
            item_id="",
        )
    except Exception:
        logger.debug("CostMeter log_api_call skipped", exc_info=True)

    # -- Build source_url lookup for version bumping (F50) -----------------
    url_to_existing: dict[str, KBEntry] = {}
    for entry in existing_entries:
        if entry.source_url:
            existing_for_url = url_to_existing.get(entry.source_url)
            if existing_for_url is None or entry.version > existing_for_url.version:
                url_to_existing[entry.source_url] = entry

    # -- Apply dedup + version bumping -------------------------------------
    new_items: list[Item] = []
    for item in items:
        existing = url_to_existing.get(item.source_url) if item.source_url else None
        if existing is not None:
            # Re-collection of same URL — version bump
            item.version = existing.version + 1
            item.previous_version = existing.version
            item.supersedes = existing.entry_id
            new_items.append(item)
            plog.info(
                "Version bump on re-collection",
                item_id=item.id,
                source_type=source_config.type,
                extra={
                    "source_url": item.source_url,
                    "new_version": item.version,
                    "previous_version": existing.version,
                    "supersedes": existing.entry_id,
                },
            )
        elif force_full:
            new_items.append(item)
        else:
            verdict = checker.check(item, existing_entries)
            if not verdict["is_duplicate"]:
                new_items.append(item)

    items_new = len(new_items)

    # -- Collection-layer domain topic guard (#332-B) ------------------------
    # Drop items matching the domain's surface noise keywords (ai-commercial:
    # 贝达药业/华能/SEC 8-K/财报; financial: SEC 8-K/10-Q metadata dilutions)
    # BEFORE they enter the raw cache, so no downstream product can pick them up.
    if domain in _DOMAIN_NOISE_KEYWORDS:
        pre = len(new_items)
        new_items = [item for item in new_items if not _item_matches_domain_noise(item, domain)]
        dropped_noise = pre - len(new_items)
        if dropped_noise:
            plog.info(
                "Dropped domain-noise items at collection",
                extra={
                    "domain": domain,
                    "count": dropped_noise,
                },
            )
        items_new = len(new_items)

    # -- Assign trace_id to each new item ----------------------------------
    trace_ids: list[str] = []
    for item in new_items:
        if not item.trace_id:
            item.trace_id = str(uuid.uuid4())
        trace_ids.append(item.trace_id)
        plog.info(
            "Item collected",
            item_id=item.id,
            source_type=source_config.type,
            trace_id=item.trace_id,
            extra={
                "source_name": source_config.name,
                "domain": domain,
                "title": item.title,
            },
        )

    elapsed = round(time.time() - src_start, 3)

    # -- Cache (only if not dry_run) ---------------------------------------
    items_duplicate = 0
    if not dry_run and new_items:
        cache_result = _cache_items(new_items, domain, source_config.name)
        items_new = cache_result.written
        items_duplicate = cache_result.skipped_duplicate
        if new_items_collector is not None:
            new_items_collector.extend(new_items)
        _log_run(
            domain,
            source_config.name,
            collection_id,
            items_found,
            items_new,
            status="success",
            duration_s=elapsed,
            trace_ids=trace_ids,
            items_filtered=items_filtered,
            items_duplicate=items_duplicate,
        )

    return CollectionResult(
        collection_id=collection_id,
        domain=domain,
        source=source_config.name,
        status="success" if not errors else "partial",
        items_found=items_found,
        items_new=items_new,
        items_filtered=items_filtered,
        items_duplicate=items_duplicate,
        errors=errors,
        duration_s=elapsed,
        estimated_duration_s=elapsed,
    )


def _handler_settings(source_config: SourceConfig) -> dict[str, Any]:
    """Build the ``config=`` dict passed to settings-based collectors.

    Thin alias for :func:`autoinfo.collectors.registry.handler_settings`
    (kept because tests and callers reference this name).
    """
    return handler_settings(source_config)


def _env_truthy(name: str) -> bool:
    """Read a boolean-ish environment variable (``1/true/yes/on``)."""
    return str(os.environ.get(name, "")).strip().lower() in {"1", "true", "yes", "on"}


def _app_review_block_reason(source_config: SourceConfig, handler: Any) -> str | None:
    """App-review gate.  Return a block reason, or ``None`` to allow collection.

    The owner's hard constraint ("no unlawful collection") needs a machine
    enforcement point, not a self-declared flag nobody reads.  Before this,
    ``requires_app_review`` existed only as a staticmethod on the Bilibili
    handler plus a YAML key that fell into ``settings`` — zero consumers either
    way.

    Fail-closed: a source that declares it needs platform app/interface review
    is **skipped** unless explicitly acknowledged, via either

    * ``app_review_ack: true`` on that source in ``sources.yaml`` (per-source,
      recorded in the config), or
    * ``AUTOINFO_APP_REVIEW_ACK=1`` in the environment (global, explicit).

    A missing/broken declaration never *opens* the gate — an exception while
    probing the handler is treated as "declared" only if the config says so;
    otherwise the source is allowed (it never claimed to need review).
    """
    declared = bool(getattr(source_config, "requires_app_review", False))
    if not declared:
        try:
            declared = bool(handler.requires_app_review())
        except Exception:  # pragma: no cover - defensive; handlers may not implement it
            declared = False
    if not declared:
        return None

    if bool(getattr(source_config, "app_review_ack", False)) or _env_truthy(
        "AUTOINFO_APP_REVIEW_ACK"
    ):
        return None

    return (
        f"source '{source_config.name}' requires platform app/interface review "
        f"but no acknowledgement is recorded — skipped (fail-closed)"
    )


def _build_handler(source_config: SourceConfig) -> Collector:
    """Build the collector for *source_config* via the registry.

    This is a thin lookup: :func:`autoinfo.collectors.registry.build_collector`
    owns the ``source_type`` (and, for ``api``, source-name) resolution.
    Nothing per-source lives here — adding a collector means adding one class
    plus one registry registration.

    Raises ``ValueError`` when the source type has no buildable collector
    (unknown type, or a forward-declared / push-only type such as ``webhook``).
    """
    collector = build_collector(source_config)
    if collector is None:
        supported = ", ".join(sorted(registered_source_types()))
        raise ValueError(
            f"Unknown source type '{source_config.type}' for source "
            f"'{source_config.name}'. Supported types: {supported}."
        )
    return collector


def _fetch_items(
    handler: Collector,
    source_config: SourceConfig,
    topic: str,
    limit: int,
    keywords: list[str] | None = None,
) -> list[Item]:
    """Fetch items from *handler* through the uniform collector contract.

    Builds a :class:`~autoinfo.collectors.base.CollectorContext` from the
    collection inputs and makes exactly one ``handler.fetch_items(ctx)`` call.
    All source-specific behavior (guards, query resolution, slicing, dict ->
    ``Item`` normalization) lives in the collector.
    """
    ctx = CollectorContext(
        source_config=source_config,
        topic=topic or "",
        keywords=list(keywords or []),
        limit=limit,
        url=source_config.url or "",
        query=(source_config.settings or {}).get("query", "") or "",
        settings=handler_settings(source_config),
    )
    return handler.fetch_items(ctx)


class CacheWriteResult(NamedTuple):
    written: int
    skipped_duplicate: int


def _cache_items(
    items: list[Item],
    domain: str,
    source_name: str,
) -> CacheWriteResult:
    """Write deduplicated items to ``collections/<domain>/<source>/<date>/<id>.json``."""
    today = date.today().isoformat()
    base_dir = Path(COLLECTIONS_DIR) / domain / source_name / today
    base_dir.mkdir(parents=True, exist_ok=True)

    # Issue #139: cross-date URL dedup.  Each date directory is independent,
    # so the same article URL re-collected on a later day would previously be
    # written as a NEW file in the new date dir — inflating raw counts and
    # re-appearing in later digests.  Build a URL set spanning ALL prior date
    # dirs of this source; an item whose URL is already cached is skipped
    # (the newest copy wins; the older file stays for provenance).
    seen_urls: set[str] = set()
    source_root = Path(COLLECTIONS_DIR) / domain / source_name
    if source_root.is_dir():
        for prior_file in source_root.rglob("*.json"):
            if prior_file.parent.name == today:
                continue
            try:
                with open(prior_file, encoding="utf-8") as fh:
                    data = json.load(fh)
                    # Issue #160: prior-dir scans also pick up the list-shaped
                    # _runs.json (collection history) — only dict item files
                    # carry source_url; a list must be skipped, not crash.
                    if isinstance(data, dict):
                        seen_urls.add(str(data.get("source_url") or ""))
            except (json.JSONDecodeError, OSError):
                continue

    written = 0
    skipped_duplicate = 0
    for item in items:
        # Cross-date duplicate (same URL collected on an earlier day) — skip;
        # the earlier file already carries it and downstream counts stay unique.
        if item.source_url and item.source_url in seen_urls:
            skipped_duplicate += 1
            continue
        safe_id = str(item.id).replace("/", "_") if item.id else item.id
        file_path = base_dir / f"{safe_id}.json"
        # Avoid overwriting existing cached files (idempotent)
        if file_path.exists():
            skipped_duplicate += 1
            continue
        with open(file_path, "w", encoding="utf-8") as fh:
            json.dump(item.to_dict(), fh, ensure_ascii=False, indent=2)
        written += 1

    return CacheWriteResult(written=written, skipped_duplicate=skipped_duplicate)


# ---------------------------------------------------------------------------
# Webhook push
# ---------------------------------------------------------------------------


def _build_webhook_payload(domain: str, item: Item) -> dict[str, Any]:
    """Build the JSON payload for a webhook POST."""
    import uuid as _uuid

    return {
        "item_id": item.id or str(_uuid.uuid4()),
        "trace_id": item.trace_id,
        "title": item.title,
        "url": item.source_url,
        "source": item.source_name,
        "source_type": item.source_type,
        "domain": domain,
        "topic": item.topic_tags,
        "content": item.content,
        "collected_at": item.collected_at,
        "extracted": {
            "summary": item.raw_data.get("summary", ""),
            "key_points": item.raw_data.get("key_points", []),
            "entities": item.raw_data.get("entities", []),
        },
    }


async def _post_webhook(
    client: httpx.AsyncClient,
    url: str,
    payload: dict[str, Any],
    retries: int = 3,
) -> None:
    """POST *payload* to *url* with exponential backoff retry.

    Retries on 5xx and network errors only.  2xx and 4xx are terminal.
    """
    for attempt in range(retries):
        try:
            resp = await client.post(url, json=payload)
            if resp.status_code < 500:
                return  # 2xx or 4xx — terminal
            await asyncio.sleep(2**attempt)  # 2s, 4s, 8s
        except (httpx.TimeoutException, httpx.NetworkError):
            if attempt == retries - 1:
                plog.error(
                    "Webhook failed after retries",
                    extra={"retries": retries, "url": url},
                )
            await asyncio.sleep(2**attempt)


async def _fire_webhooks(
    domain: str,
    new_items: list[Item],
    webhook_urls: list[str],
) -> None:
    """Fire-and-forget webhook POST for each new item.

    All items are sent to all configured webhooks concurrently.
    Exceptions are logged and never propagated.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        tasks: list[asyncio.Task[None]] = []
        for item in new_items:
            payload = _build_webhook_payload(domain, item)
            for url in webhook_urls:
                tasks.append(asyncio.create_task(_post_webhook(client, url, payload)))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


def _fire_webhooks_sync(
    domain: str,
    new_items: list[Item],
    webhook_urls: list[str],
) -> None:
    """Synchronous fire-and-forget entry point.

    Runs the async webhook fire in a daemon thread so collection is
    never blocked even when called from an already-running event loop.
    """
    if not webhook_urls or not new_items:
        return

    def _run() -> None:
        try:
            asyncio.run(_fire_webhooks(domain, new_items, webhook_urls))
        except Exception:
            logger.exception("Webhook fire failed for domain '%s'", domain)

    t = threading.Thread(target=_run, daemon=True)
    t.start()


def _log_run(
    domain: str,
    source_name: str,
    collection_id: str,
    items_found: int,
    items_new: int,
    status: str = "success",
    errors: list[dict[str, Any]] | None = None,
    duration_s: float = 0.0,
    trace_ids: list[str] | None = None,
    items_filtered: int = 0,
    items_duplicate: int = 0,
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
    runs_dir = Path(COLLECTIONS_DIR) / domain / source_name
    runs_dir.mkdir(parents=True, exist_ok=True)
    runs_path = runs_dir / "_runs.json"

    entry: dict[str, Any] = {
        "collection_id": collection_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "items_found": items_found,
        "items_new": items_new,
        "items_filtered": items_filtered,
        "items_duplicate": items_duplicate,
        "errors": errors or [],
        "duration_ms": round(duration_s * 1000, 1),
    }
    if trace_ids:
        entry["trace_ids"] = trace_ids

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
    runs_path = Path(COLLECTIONS_DIR) / "_runs.json"
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
