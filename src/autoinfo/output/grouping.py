"""Extracted from :mod:`autoinfo.output` (#582 phase 1).

Hub-level helpers are imported inside each function at call time so
``autoinfo.output.<name>`` monkeypatch seams keep working after the move.
"""

from __future__ import annotations

import concurrent.futures
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from autoinfo.llm import LLMExtractor

logger = logging.getLogger("autoinfo.output")


def _reset_grouping_degraded() -> None:
    """Reset the module-level grouping-degradation flag before a grouping run."""
    import autoinfo.output as _hub  # noqa: PLC0415

    _hub._grouping_degraded = False


def _grouping_degradation_marker(reason: str) -> str:
    """Return the pinned "grouped by source" honesty marker (issue #120, C4).

    The rendered annotation is a single constant string for every degradation
    path; *reason* (``llm_failure``/``timeout``/``chaos``/``no_groups``/
    ``entry_level``) is accepted for symmetry with the structured log so the
    marker helper and the log event stay on the same vocabulary, but the
    marker itself does not change.  The marker is placed as a leading line of
    the sections block in the rendered markdown (report, digest, column).
    """
    from autoinfo.output import _GROUPING_DEGRADATION_MARKER

    return _GROUPING_DEGRADATION_MARKER


def _log_grouping_degraded(reason: str, grouping: str, detail: str) -> None:
    """Structured ``event="grouping_degraded"`` warning (issue #120, C4).

    Emitted on EVERY silent-hop degradation path so operators can observe that
    a product shipped with a non-semantic grouping without having to diff the
    rendered output.  ``reason`` is one of ``llm_failure``/``timeout``/
    ``chaos``/``no_groups``/``entry_level``; ``grouping`` is the kind actually
    rendered (``source_type``/``keyword``/``general``/``entry_level``).

    Also records the degradation on the module-level flag so the report path
    (which renders via :class:`ReportData`) can annotate its output even when
    the grouping happened inside a worker batch thread.
    """
    import autoinfo.output as _hub  # noqa: PLC0415

    _hub._grouping_degraded = True
    logger.warning(
        "grouping_degraded event=%r reason=%r grouping=%r %s",
        "grouping_degraded",
        reason,
        grouping,
        detail,
    )


def _deterministic_grouping_kind(groups: list[dict[str, Any]] | None) -> str:
    """Classify the grouping kind ``_deterministic_grouping`` produced.

    Returns ``"keyword"`` when any group name matches a keyword classifier
    spelling (title-cased topic keyword), ``"source_type"`` when every group
    maps through ``_SOURCE_TYPE_THEME_LABEL``-derived labels OR through a
    single-source heading (issue #167 — a group named after its actual
    source, e.g. "PubMed"), and ``"general"`` otherwise (a single
    catch-all).  Used to annotate the structured degradation log with the
    grouping actually rendered.
    """
    from autoinfo.output import _SOURCE_TYPE_THEME_LABELS
    from autoinfo.output.sources import _derive_source_label as _derive_source_label

    if not groups:
        return "general"
    map_values = {v.lower() for v in _SOURCE_TYPE_THEME_LABELS.values()}
    source_type_hits = 0
    for g in groups:
        theme = str(g.get("theme") or "").strip()
        if not theme:
            continue
        key = theme.lower()
        if key == "general":
            return "general"
        if key == "additional topics":
            continue
        if key in map_values:
            source_type_hits += 1
            continue
        # Issue #167: a single-source heading names the source itself (e.g.
        # "PubMed"); verify every entry in the group derives that label.
        entries = g.get("entries") or []
        if entries:
            labels = {
                str(_derive_source_label(e, str(e.get("domain") or "")))
                for e in entries
                if isinstance(e, dict)
            }
            if labels and theme in labels:
                source_type_hits += 1
                continue
        return "keyword"
    if source_type_hits:
        return "source_type"
    return "general"


def _single_general_group(groups: list[dict[str, Any]] | None) -> bool:
    """True when *groups* is exactly one "General" catch-all group (the
    0/1-group no-meaningful-topic collapse)."""
    return bool(
        groups
        and len(groups) == 1
        and str(groups[0].get("theme") or "").strip().lower() == "general"
    )


def _group_by_theme(
    extractor: LLMExtractor,
    entries: list[dict[str, Any]],
    domain: str = "",
    domains: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Group KB entries by theme using the LLM.

    Parameters
    ----------
    extractor : LLMExtractor
        LLM extractor instance for making API calls.
    entries : list[dict[str, Any]]
        List of entry dicts, each with ``entry_id``, ``title``, ``summary``,
        ``source_url``, ``source_type``, ``source_platform``.
    domain : str, optional
        Domain name for domain-specific theme guidance. If provided, the
        prompt includes themed suggestions relevant to the domain. An empty
        string (default) uses generic guidance.
    domains : list[str], optional
        Optional list of domain names for cross-domain synthesis. When
        provided, the grouping prompt includes an instruction to connect
        themes across domains.

    Returns
    -------
    list[dict[str, Any]]
        List of dicts::

            [
                {
                    "theme": "IVF Treatment Outcomes",
                    "description": "...",
                    "entries": [...],
                },
            ]

    Entries are grouped in batches of at most ``_GROUPING_BATCH_SIZE`` so the
    LLM prompt stays small enough to return reliable JSON even for long entry
    lists; resulting themes are then merged across batches by normalized
    name.  When the LLM fails or collapses a batch, a deterministic keyword /
    source-type / domain heuristic is used instead, so the entries never
    collapse into a single ``"General"`` group while more than one distinct
    topic is detectable.
    """
    from autoinfo.output import _GROUPING_BATCH_SIZE, _GROUPING_TARGET_RANGE, _run_grouping_batches

    if not entries:
        return []

    from autoinfo.output import fault_inject

    _reset_grouping_degraded()

    try:
        fault_inject.maybe_fault("group")
    except Exception as fault_exc:
        groups = _deterministic_grouping(entries, domain=domain)
        if groups is not None:
            # Issue #9 (reopened): the deterministic fallback may carry
            # keyword-derived generic themes — run the same blocklist/synonym
            # pass the LLM-grouping path uses so the fault-inject path cannot
            # leak ``### New`` / ``### Year`` labels either.
            grouping = _deterministic_grouping_kind(groups)
            _log_grouping_degraded(
                "timeout" if isinstance(fault_exc, TimeoutError) else "llm_failure",
                grouping,
                f"fault-inject {type(fault_exc).__name__} at seam 'group'; "
                f"deterministic fallback produced {len(groups)} groups",
            )
            return _merge_theme_groups(groups, target_count=_GROUPING_TARGET_RANGE)
        _log_grouping_degraded(
            "timeout" if isinstance(fault_exc, TimeoutError) else "llm_failure",
            "general",
            f"fault-inject {type(fault_exc).__name__} at seam 'group'; "
            "no distinct topics detectable, single General group",
        )
        return [
            {
                "theme": "General",
                "description": "Overview of the tracked developments this period.",
                "entries": list(entries),
            }
        ]

    batch_size = _GROUPING_BATCH_SIZE
    batches = [entries[i : i + batch_size] for i in range(0, len(entries), batch_size)]

    merged = _merge_theme_groups(
        _run_grouping_batches(extractor, batches, domain=domain, domains=domains)
    )

    # -- Chaos guard (issue #106) -------------------------------------------
    # The LLM sometimes returns an unwieldy burst of mostly garbage themes
    # (many single-entry groups). A large group count or surplus of
    # single-entry groups produces an oversized/disordered synthesis prompt
    # downstream (report/column), which the extractor cannot parse → repeated
    # retries → timeout / 0-byte output. Treat such results as unreliable and
    # fall back to deterministic grouping (same sanitization as the ==1-group /
    # no-group fallback paths).
    if len(merged) > 20 or sum(1 for g in merged if len(g.get("entries", [])) <= 1) > 6:
        logger.warning(
            "LLM grouping produced %d themes (%d single-entry) — exceeded "
            "chaos thresholds, falling back to deterministic grouping",
            len(merged),
            sum(1 for g in merged if len(g.get("entries", [])) <= 1),
        )
        deterministic = _deterministic_grouping(entries, domain=domain)
        if deterministic is not None:
            _log_grouping_degraded(
                "chaos",
                _deterministic_grouping_kind(deterministic),
                f"LLM grouping produced {len(merged)} themes "
                f"({sum(1 for g in merged if len(g.get('entries', [])) <= 1)} "
                "single-entry), chaos guard fell back to deterministic "
                f"grouping with {len(deterministic)} groups",
            )
            merged = _merge_theme_groups(deterministic, target_count=_GROUPING_TARGET_RANGE)
        else:
            _log_grouping_degraded(
                "chaos",
                "general",
                "no distinct topics detectable after chaos fallback, single General group",
            )

    return _ensure_all_entries_grouped(merged, entries)


def _run_grouping_batches(
    extractor: LLMExtractor,
    batches: list[list[dict[str, Any]]],
    domain: str = "",
    domains: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Run the per-batch LLM grouping calls with a bounded thread pool.

    Batches are processed concurrently (bounded by ``_GROUPING_MAX_WORKERS``
    workers) while ``_group_batch_by_theme`` results are collected by index,
    so the final grouping list preserves the exact sequential batch order.
    Each LLM call inside still routes through :func:`call_with_fallback` and
    its shared per-provider semaphore, so per-provider concurrency stays
    bounded regardless of the pool width.

    Per-batch error behavior is identical to the sequential loop: a batch
    that fails (or whose LLM call raises) falls back to deterministic
    grouping inside ``_group_batch_by_theme``; if one ever raised, the first
    failing batch's exception surfaces in batch order after the pool has
    finished, exactly as the sequential ``for`` loop would.
    """
    from autoinfo.output import _GROUPING_MAX_WORKERS

    workers = min(len(batches), _GROUPING_MAX_WORKERS)
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        per_batch = list(
            pool.map(
                lambda batch: _group_batch_by_theme(
                    extractor, batch, domain=domain, domains=domains
                ),
                batches,
            )
        )
    return [g for batch_result in per_batch for g in batch_result]


def _group_batch_by_theme(
    extractor: LLMExtractor,
    entries: list[dict[str, Any]],
    domain: str = "",
    domains: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Group a single batch of entries (at most ``_GROUPING_BATCH_SIZE``).

    Uses the LLM (with an anti-collapse retry) and maps the returned entry
    IDs back to entry objects.  Falls back to a deterministic keyword /
    source-type / domain grouping when the LLM fails or collapses the batch.
    """
    from autoinfo.output import _GROUPING_TARGET_RANGE, _llm_group_batch

    groups_raw = _llm_group_batch(extractor, entries, domain=domain, domains=domains)
    if not groups_raw:
        groups = _deterministic_grouping(entries, domain=domain)
        if groups is not None:
            _log_grouping_degraded(
                "llm_failure",
                _deterministic_grouping_kind(groups),
                f"LLM returned no groups for a {len(entries)}-entry batch; "
                f"deterministic fallback produced {len(groups)} groups",
            )
            return _merge_theme_groups(groups, target_count=_GROUPING_TARGET_RANGE)
        _log_grouping_degraded(
            "no_groups",
            "general",
            f"no distinct topics detectable for a {len(entries)}-entry batch, single General group",
        )
        return [
            {
                "theme": "General",
                # #338: never surface the internal "All N entries included in
                # this report" counting line to end users.
                "description": "Overview of the tracked developments this period.",
                "entries": list(entries),
            }
        ]

    entry_map: dict[str, dict[str, Any]] = {
        e.get("entry_id", ""): e for e in entries if e.get("entry_id")
    }

    result: list[dict[str, Any]] = []
    for g in groups_raw:
        group_entries = [entry_map[eid] for eid in g.get("entry_ids", []) if eid in entry_map]
        if group_entries:
            result.append(
                {
                    "theme": g.get("theme", "Untitled"),
                    "description": g.get("description", ""),
                    "entries": group_entries,
                }
            )

    # -- Coverage guard -----------------------------------------------------
    # The LLM sometimes returns parseable JSON whose entry_ids do not match
    # the actual entry IDs, which would dump every entry into a single
    # catch-all.  If the LLM groups cover fewer than half the batch, treat
    # the result as unreliable and fall back to deterministic grouping.
    matched_count = sum(len(g["entries"]) for g in result)
    if matched_count < max(1, len(entries) // 2):
        logger.warning(
            "LLM groups matched only %d/%d entries, falling back to deterministic grouping",
            matched_count,
            len(entries),
        )
        groups = _deterministic_grouping(entries, domain=domain)
        if groups is not None:
            _log_grouping_degraded(
                "llm_failure",
                _deterministic_grouping_kind(groups),
                f"LLM groups matched only {matched_count}/{len(entries)} "
                f"entries; deterministic fallback produced {len(groups)} groups",
            )
            return _merge_theme_groups(groups, target_count=_GROUPING_TARGET_RANGE)
        _log_grouping_degraded(
            "no_groups",
            "general",
            f"LLM groups matched only "
            f"{matched_count}/{len(entries)} entries and no distinct topics "
            "were detectable, single General group",
        )
        return [
            {
                "theme": "General",
                "description": "Overview of the tracked developments this period.",
                "entries": list(entries),
            }
        ]

    # Ensure no entry is left out (ungrouped entries go into a catch-all)
    grouped_ids: set[str] = {
        e.get("entry_id", "") for g in result for e in g["entries"] if e.get("entry_id")
    }
    ungrouped = [e for e in entries if e.get("entry_id", "") not in grouped_ids]
    if ungrouped:
        result.append(
            {
                "theme": "Additional Topics",
                # #338: the previous "N entry(ies) not covered by other themes."
                # count line leaked internal grouping mechanics to end users.
                "description": "Other notable developments across the tracked sources.",
                "entries": ungrouped,
            }
        )

    return result


def _llm_group_batch(
    extractor: LLMExtractor,
    entries: list[dict[str, Any]],
    domain: str = "",
    domains: list[str] | None = None,
) -> list[dict[str, Any]] | None:
    """Ask the LLM to group a single batch of entries into themes.

    Returns the raw parsed ``groups`` list (each object carries ``theme``,
    ``description`` and ``entry_ids``) or ``None`` when the LLM fails or
    repeatedly collapses the batch into a single theme.
    """
    from autoinfo.output import _llm_json_extract

    entry_summaries_parts: list[str] = []
    for e in entries:
        entry_domain = e.get("domain", domain)
        entry_summaries_parts.append(
            f"- [{e.get('entry_id', '?')}] [{entry_domain}] "
            f"{e.get('title', '?')}: {e.get('summary', '(no summary)')}"
        )
    entry_summaries = "\n".join(entry_summaries_parts)

    cross_domain_instruction = ""
    if domains and len(domains) >= 2:
        cross_domain_instruction = (
            f"You are synthesizing information from {len(domains)} domains: "
            f"{', '.join(domains)}. Present a cohesive view that connects "
            "findings across domains. Each entry is annotated with its "
            "source domain in [brackets]. Create themes that bridge or "
            "contrast findings from different domains where applicable.\n\n"
        )

    prompt = (
        cross_domain_instruction
        + "Group the following knowledge base entries into 3\u20135 themes. "
        "Each entry goes into exactly one theme. Do NOT use catch-all names "
        'like "General" or "Additional". '
        "Give each theme a SHORT SEMANTIC title: a concise noun phrase "
        "(2-6 words) naming the theme (e.g. 'Funding & M&A Momentum', "
        "'Reproductive Health Outcomes'). Never use a raw keyword list, "
        "concatenated entry titles, or separator-dumped keywords (no '/' or "
        "'&'-joined keyword strings). Titles must be unique and "
        "descriptive.\n\n"
        'Return JSON: {"groups": [{"theme": str, "entry_ids": [str]}]}\n\n'
        f"Entries:\n{entry_summaries}"
    )

    try:
        groups_raw = _llm_json_extract(extractor, prompt, "groups")
    except Exception as exc:
        logger.warning("Thematic grouping via LLM failed: %s", exc)
        groups_raw = None

    # -- Anti-collapse retry ------------------------------------------------
    # If the LLM returned only 1 group (or none), retry with a stricter
    # prompt that explicitly demands multiple distinct themes.
    if groups_raw and len(groups_raw) <= 1:
        logger.warning(
            "LLM returned only %d theme group(s), retrying with stricter prompt",
            len(groups_raw),
        )
        retry_prompt = (
            cross_domain_instruction + "STRICT RETRY: You previously grouped entries into a single "
            "theme. Re-read the entries below and identify at least "
            "2\u20133 DISTINCT themes. Do NOT use catch-all themes like "
            '"General", "Miscellaneous", or "Other". Each entry must '
            "be assigned to the most specific theme that describes its "
            "content. "
            "Give each theme a SHORT SEMANTIC title: a concise noun phrase "
            "(2-6 words) naming the theme (e.g. 'Funding & M&A Momentum', "
            "'Reproductive Health Outcomes'). Never use a raw keyword list, "
            "concatenated entry titles, or separator-dumped keywords (no '/' or "
            "'&'-joined keyword strings). Titles must be unique and "
            "descriptive.\n\n"
            'Return JSON: {"groups": [{"theme": str, "entry_ids": [str]}]}\n\n'
            f"Entries:\n{entry_summaries}"
        )
        try:
            groups_raw = _llm_json_extract(extractor, retry_prompt, "groups")
        except Exception as exc:
            logger.warning("Strict retry failed: %s", exc)
            groups_raw = None

        # If retry STILL produced only 1 group, treat as failure → fallback
        if groups_raw and len(groups_raw) <= 1:
            logger.warning(
                "Strict retry returned only %d group(s), falling back to deterministic grouping",
                len(groups_raw),
            )
            groups_raw = None

    result: list[dict[str, Any]] | None = groups_raw
    return result


def _SOURCE_TYPE_THEME_LABEL(source_type: str) -> str:  # noqa: N802 (paired with _SOURCE_TYPE_THEME_LABELS map)
    """Human-readable section title for a deterministic source-type group.

    The chaos-guard fallback (issue #106) groups by ``source_type`` when the
    LLM theme grouping is unreliable; using the bare machine name
    (``HACKERNEWS`` / ``RSS`` / ``API``) as the section title leaks an
    internal label into the delivered product (issue #113). Map known
    source types to a domain-neutral, user-facing label; unknown types keep
    a title-cased fallback.
    """
    from autoinfo.output import _SOURCE_TYPE_THEME_LABELS

    key = (source_type or "").strip().lower()
    if key in _SOURCE_TYPE_THEME_LABELS:
        return _SOURCE_TYPE_THEME_LABELS[key]
    # Unknown type: humanize the machine name (e.g. "api" -> "API",
    # "hnrss" -> "Hnrss", "unknown" -> "Other Sources").
    if key == "unknown":
        return "Other Sources"
    _s = source_type.strip()
    return _s.upper() if len(_s) <= 6 else _s.title()


def _source_group_heading(
    source_type: str, group_entries: list[dict[str, Any]], domain: str
) -> str:
    """Section heading for a deterministic source-type group (issue #167).

    When the whole group maps to ONE user-facing source (every entry derives
    the same source label), the heading is that source's name — a heading
    that IS the source can never misrepresent its content (e.g. pubmed IVF
    papers must not sit under "Platform & API News").  Mixed-platform groups
    fall back to the provenance-neutral ``_SOURCE_TYPE_THEME_LABEL``.
    """
    from autoinfo.output.entries import _platform_name as _platform_name
    from autoinfo.output.sources import _GENERIC_PLATFORMS as _GENERIC_PLATFORMS
    from autoinfo.output.sources import _derive_source_label as _derive_source_label

    labels: set[str] = set()
    for e in group_entries:
        if not isinstance(e, dict):
            continue
        # Prefer the stamped user-facing label; fall back to the deterministic
        # host/source-config matcher or the humanized platform name; skip
        # generic platforms and empties.
        label = str(e.get("source_label") or "").strip()
        if not label:
            platform = str(e.get("source_platform") or "").strip()
            if platform.lower() not in _GENERIC_PLATFORMS:
                label = _platform_name(platform)
        if not label:
            label = _derive_source_label(e, domain)
            if label.lower() in _GENERIC_PLATFORMS:
                label = ""  # derived back to a generic platform -> not specific
        if label:
            labels.add(label)
    if len(labels) == 1:
        # Humanize the single source label (pubmed -> PubMed, techcrunch ->
        # techcrunch) so the heading reads as a clean user-facing source name.
        return _platform_name(next(iter(labels)))
    return _SOURCE_TYPE_THEME_LABEL(source_type)


def _deterministic_grouping(
    entries: list[dict[str, Any]],
    domain: str = "",
) -> list[dict[str, Any]] | None:
    """Group entries deterministically without the LLM.

    Splits by ``source_type`` (existing fallback), then by ``domain``, and
    finally by a keyword classifier built from the domain's ``_keywords.yaml``
    when the simpler splits still collapse to a single group.  Returns
    ``None`` only when fewer than two distinct topics are detectable, so the
    caller can decide on a last-resort group.
    """
    from collections import defaultdict

    # 1. Split by source_type
    source_groups: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in entries:
        st = (e.get("source_type") or "").strip() or "unknown"
        source_groups[st].append(e)

    if len(source_groups) >= 2:
        return [
            {
                # Issue #167: name the actual source when the group is a
                # single platform, else a provenance-neutral label.
                "theme": _source_group_heading(st, es, domain),
                # #338: user-facing lead, no internal "N entries from" count.
                "description": f"Updates and analysis from {st} sources.",
                "entries": es,
            }
            for st, es in sorted(source_groups.items())
        ]

    # 2. Split by domain
    domain_groups: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in entries:
        d = (e.get("domain") or "").strip() or "Unknown"
        domain_groups[d].append(e)

    if len(domain_groups) >= 2:
        return [
            {
                "theme": (d.replace("-", " ").title() if d != "Unknown" else "Other Sources"),
                # #338: user-facing lead, no internal "N entries from" count.
                "description": (
                    f"Developments across {d if d and d != 'Unknown' else 'other sources'}."
                ),
                "entries": es,
            }
            for d, es in sorted(domain_groups.items())
        ]

    # 3. Keyword classifier (from knowledge/<domain>/_keywords.yaml) — this
    #    replaces the old "General" dump when the entries are all from one
    #    source_type and one domain but still cover distinct topics.
    keyword_groups = _keyword_group_entries(entries, domain=domain)
    if keyword_groups is not None:
        return keyword_groups

    # Only a single distinct topic is detectable.
    return None


def _keyword_group_entries(
    entries: list[dict[str, Any]],
    domain: str = "",
) -> list[dict[str, Any]] | None:
    """Group entries by keyword topics from the domain's ``_keywords.yaml``.

    Loads topic keywords from ``knowledge/<domain>/_keywords.yaml`` (when
    present) and maps each entry's title/summary to the longest keyword it
    contains.  Returns a list of groups, or ``None`` when fewer than two
    distinct keyword topics are detectable so the caller can fall back to
    source-type / domain grouping.

    Issue #9 (reopened 2026-08-25): the generic-theme-label blocklist
    (``_GENERIC_THEME_LABELS``) historically lived ONLY in
    :func:`_merge_theme_groups`, which the deterministic-fallback callers of
    this function bypass (the fault-inject path in :func:`_group_by_theme`
    and :func:`_deterministic_column_sections` on the digest path).  The
    keyword classifier can therefore produce bare generic themes
    (``### New`` / ``### Year`` / ``### User`` ...) from auto-discovery
    noise keywords.  Sanitize at THIS boundary by running the result
    through :func:`_merge_theme_groups` before returning, so no caller can
    surface a generic theme; groups whose normalized theme is a bare
    generic word are dropped and their entries folded into the nearest
    surviving group or ``Additional Topics`` (no entry is ever lost).
    """
    from collections import defaultdict

    from autoinfo.output import (
        _STRUCTURAL_THEME_LABELS,
        _THEME_SYNONYMS,
        _keyword_topic_labels,
        _load_keyword_topics,
    )

    topics = _load_keyword_topics(domain)
    if not topics:
        return None

    # Normalize once, keep the original spelling for display, and match the
    # most specific (longest) keyword first.
    norm_topics: list[tuple[str, str]] = []
    for t in topics:
        nt = _normalize_text(t)
        if len(nt) >= 3:
            norm_topics.append((nt, t))
    if not norm_topics:
        return None
    norm_topics.sort(key=lambda pair: len(pair[0]), reverse=True)

    groups: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in entries:
        text = _normalize_text(f"{e.get('title', '')} {e.get('summary', '')}")
        best = _match_keyword(text, norm_topics)
        groups[best if best else "__unmatched__"].append(e)

    keyword_names = [name for name in groups if name != "__unmatched__"]
    if not keyword_names:
        return None
    if len(keyword_names) == 1 and not groups.get("__unmatched__"):
        return None

    # #120 (C5): resolve each keyword group to a user-facing label instead of
    # a bare ``name.title()`` keyword word.  Resolution order: (a) the domain
    # config's TopicConfig group/name, (b) the curated synonym map, (c) fold
    # into Additional Topics.  Entries are reassigned, never dropped.
    topic_labels = _keyword_topic_labels(domain)
    result: list[dict[str, Any]] = []
    resolved_names: list[str] = []
    folded: list[dict[str, Any]] = []
    for name, es in groups.items():
        if name == "__unmatched__":
            continue
        label = topic_labels.get(name)
        if not label and name in _THEME_SYNONYMS:
            label = _THEME_SYNONYMS[name].title()
        if not label:
            folded.extend(es)
            continue
        resolved_names.append(name)
        result.append(
            {
                "theme": label,
                # #338: the old "N entries related to '<kw>'." description exposed
                # the internal keyword-search/counting to end users — use a
                # user-facing section lead instead.
                "description": f"Key developments and analysis on {label}.",
                "entries": es,
            }
        )

    if not resolved_names:
        return None
    if len(resolved_names) == 1 and not groups.get("__unmatched__") and not folded:
        return None

    unmatched = groups.get("__unmatched__", []) + folded
    if unmatched:
        result.append(
            {
                "theme": "Additional Topics",
                # #338: no internal "N entry(ies) not matched to a topic keyword."
                # count line in the delivered product.
                "description": "Other notable developments across the tracked sources.",
                "entries": unmatched,
            }
        )

    # Issue #9 (reopened): the generic-label blocklist must hold on EVERY
    # caller of this function, not just the ``_merge_theme_groups`` path the
    # LLM-grouping flow reaches.  Reuse the single source of truth for the
    # blocklist + synonym + near-dup passes.  The ``None`` contract is
    # preserved: when every keyword theme is generic (blocklist-stripped) or
    # structural (catch-all only), the classifier found no meaningful topic —
    # return ``None`` so the caller's source-type / domain fallback engages.
    sanitized = _merge_theme_groups(result)
    meaningful = [
        g for g in sanitized if _normalize_theme_text(g["theme"]) not in _STRUCTURAL_THEME_LABELS
    ]
    if not meaningful:
        return None
    return sanitized


def _load_keyword_topics(domain: str) -> list[str]:
    """Load non-deprecated topic keywords for *domain*.

    Reads ``knowledge/<domain>/_keywords.yaml`` (auto-discovery keywords)
    and MERGES the demo-domain seed ``src/autoinfo/data/domains/<domain>/
    sources.yaml`` ``topics[*].keywords`` into the result (issue #9).

    The merge is UNCONDITIONAL — not a fallback-when-empty: the runtime
    keyword table can hold 80+ usable topics that still never match English
    titles (auto-discovery noise — CJK tokens + ASCII n-gram fragments), so a
    "fallback only when none usable" branch would silently no-op on exactly
    the domains that need the curated English seed.  Seed keywords absent
    from the runtime table are appended (deduped); entries that already exist
    are not duplicated.
    """

    if not domain:
        return []
    topics: list[str] = []
    path = Path("knowledge") / domain / "_keywords.yaml"
    if path.is_file():
        try:
            raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            logger.warning("Failed to read keyword file %s: %s", path, exc)
            raw = {}
        kw_map: dict[str, Any] = raw.get("keywords", {}) or {}
        for keyword, data in kw_map.items():
            if isinstance(data, dict) and data.get("state") == "deprecated":
                continue
            topics.append(keyword)

    seen = set(topics)
    for seed_keyword in _seed_topic_keywords(domain):
        if seed_keyword not in seen:
            seen.add(seed_keyword)
            topics.append(seed_keyword)
    return topics


def _seed_topic_keywords(domain: str) -> list[str]:
    """Curated English topic keywords from the demo-domain seed (issue #9).

    Reads ``topics[*].keywords`` from ``src/autoinfo/data/domains/<domain>/
    sources.yaml`` — the same seed ``init`` uses to scaffold a domain.  An
    absent/unreadable seed yields ``[]`` so the runtime keyword table alone
    drives grouping.
    """
    from autoinfo.output.sources import _DEMO_DOMAINS_DIR as _DEMO_DOMAINS_DIR

    seed_path = _DEMO_DOMAINS_DIR / domain / "sources.yaml"
    if not seed_path.is_file():
        return []
    try:
        with open(seed_path, encoding="utf-8") as f:
            seed = yaml.safe_load(f) or {}
    except Exception:
        return []
    keywords: list[str] = []
    for topic in seed.get("topics") or []:
        for kw in topic.get("keywords") or []:
            if isinstance(kw, str) and kw.strip():
                keywords.append(kw.strip())
    return keywords


def _keyword_topic_labels(domain: str) -> dict[str, str]:
    """Map normalized keyword -> user-facing section label (#120, C5).

    Keyword-group headers must never render as bare ``name.title()`` words
    ("Apple", "Policy").  Label sources, in priority order:

    1. the domain's CURRENT ``TopicConfig`` (``group`` if set else ``name``,
       keyed by every topic keyword plus the ``name``/``group`` themselves,
       all normalized) — reads the live config, never a hardcoded list;
    2. the demo-domain seed ``topics`` (the same seed
       :func:`_load_keyword_topics` merges) via ``setdefault`` — config wins;
    3. ``{}`` — FAIL-OPEN: missing/unreadable config or absent domain falls
       back to the seed alone; a missing seed yields an empty map and the
       caller folds keyword groups into ``Additional Topics``.
    """
    from autoinfo.output import get_config_path, load_config
    from autoinfo.output.sources import _DEMO_DOMAINS_DIR as _DEMO_DOMAINS_DIR

    labels: dict[str, str] = {}

    config_path = get_config_path()
    if config_path is not None and config_path.is_file():
        try:
            config = load_config(config_path)
        except Exception:
            config = None
        if config is not None:
            for d in config.domains:
                if d.name == domain:
                    for t in d.topics:
                        label = (t.group or t.name or "").strip()
                        if not label:
                            continue
                        for key in [t.name, t.group] if t.group else [t.name]:
                            nk = _normalize_text(key)
                            if nk:
                                labels[nk] = label
                        for kw in t.keywords:
                            nk = _normalize_text(str(kw))
                            if nk:
                                labels[nk] = label
                    break

    seed_path = _DEMO_DOMAINS_DIR / domain / "sources.yaml"
    if seed_path.is_file():
        try:
            with open(seed_path, encoding="utf-8") as f:
                seed = yaml.safe_load(f) or {}
        except Exception:
            seed = {}
        for topic in seed.get("topics") or []:
            label = (str(topic.get("group") or "") or str(topic.get("name") or "")).strip()
            if not label:
                continue
            for key in (
                [str(topic.get("name"))]
                if not str(topic.get("group") or "").strip()
                else [str(topic.get("name")), str(topic.get("group"))]
            ):
                nk = _normalize_text(key)
                if nk:
                    labels.setdefault(nk, label)
            for kw in topic.get("keywords") or []:
                nk = _normalize_text(str(kw))
                if nk:
                    labels.setdefault(nk, label)

    return labels


def _match_keyword(
    text: str,
    norm_topics: list[tuple[str, str]],
) -> str:
    """Return the longest normalized topic keyword found in *text*.

    Matches on normalized (lower-cased, punctuation-stripped) text with word
    boundaries so short keywords do not match inside unrelated words.
    """
    for nt, _original in norm_topics:
        if re.search(r"(?:^|\s)" + re.escape(nt) + r"(?=\s|$)", text):
            return nt
    return ""


def _normalize_text(value: str) -> str:
    """Lower-case *value*, strip punctuation and collapse whitespace."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.lower())).strip()


def _normalize_theme_text(value: str) -> str:
    """Normalize a theme name for exact-name merging across batches.

    Applies the ``_THEME_SYNONYMS`` map first (so synonym spellings collapse
    onto one canonical key, e.g. ``Year``/``The Year``) and then the shared
    punctuation/whitespace normalization.  Used for both the exact-name pass
    and the Jaccard near-dup pass in :func:`_merge_theme_groups`, so synonym
    variants merge BEFORE the generic-label blocklist runs.
    """
    from autoinfo.output import _THEME_SYNONYMS

    text = _THEME_SYNONYMS.get(str(value).strip().lower(), str(value))
    return _normalize_text(text)


def _merge_theme_groups(
    groups: list[dict[str, Any]],
    target_count: tuple[int, int] | None = None,
) -> list[dict[str, Any]]:
    """Merge groups that share the same normalized theme name.

    Entries are deduplicated by ``entry_id`` when merging so the same entry
    is never reported under a theme twice.

    ``target_count`` is a degraded-path-only nudge: when set and the merged
    count exceeds the upper bound, the most-similar near-duplicate themes are
    merged until the count lands within ``[min, max]`` (or no similar pair
    remains) — entries are reassigned, never dropped, and the count is never
    forced up.  When ``None`` (LLM happy path) the behavior is byte-identical
    to the pre-nudge code.
    """
    from collections import defaultdict

    from autoinfo.output import _GENERIC_THEME_LABELS

    by_name: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for g in groups:
        theme = (g.get("theme") or "").strip() or "Untitled"
        key = _normalize_theme_text(theme) or theme.strip().lower()
        by_name[key].append(g)

    result: list[dict[str, Any]] = []
    for merged in by_name.values():
        theme = merged[0]["theme"]
        description = next((g["description"] for g in merged if g.get("description")), "")
        seen: set[str] = set()
        entries: list[dict[str, Any]] = []
        for g in merged:
            for e in g["entries"]:
                eid = e.get("entry_id", "")
                if eid and eid in seen:
                    continue
                if eid:
                    seen.add(eid)
                entries.append(e)
        result.append(
            {
                "theme": theme,
                "description": description,
                "entries": entries,
            }
        )

    # -- Near-duplicate theme merge pass ------------------------------------
    # The exact-name pass above merges themes that normalize to the same
    # string, but near-duplicates (case, "&" vs "and", word order) still
    # slip through and surface as duplicate report sections.  Merge pairs
    # whose normalized token sets have Jaccard similarity >= 0.6 with one
    # set a subset of the other; keep the longest original title and
    # deduplicate entries by ``entry_id``.
    pending = list(result)
    final: list[dict[str, Any]] = []
    while pending:
        group = pending.pop(0)
        group_tokens = set(_normalize_theme_text(group["theme"]).split())
        rest: list[dict[str, Any]] = []
        for other in pending:
            other_tokens = set(_normalize_theme_text(other["theme"]).split())
            union = group_tokens | other_tokens
            if (
                group_tokens
                and other_tokens
                and len(group_tokens & other_tokens) / len(union) >= 0.6
                and (group_tokens <= other_tokens or other_tokens <= group_tokens)
            ):
                # Absorb *other* into *group*: keep the longest original
                # title, prefer the first non-empty description, dedupe ids.
                if len(str(other["theme"])) > len(str(group["theme"])):
                    group["theme"] = other["theme"]
                if not group.get("description") and other.get("description"):
                    group["description"] = other["description"]
                seen = {e.get("entry_id", "") for e in group["entries"] if e.get("entry_id")}
                for e in other["entries"]:
                    eid = e.get("entry_id", "")
                    if eid and eid in seen:
                        continue
                    if eid:
                        seen.add(eid)
                    group["entries"].append(e)
                group_tokens = set(_normalize_theme_text(group["theme"]).split())
            else:
                rest.append(other)
        final.append(group)
        pending = rest

    # -- Generic-label blocklist pass (issue #9) ----------------------------
    # After the exact-name and near-dup passes, drop any group whose
    # normalized theme is a bare generic word (``new`` / ``year`` /
    # ``user`` / ... — produced by auto-discovery keyword fragments).  Each
    # dropped group's entries are reassigned to the nearest surviving group
    # (by Jaccard on normalized tokens) or to "Additional Topics", so no
    # entry is ever lost.  "General" / "Additional Topics" are structural
    # catch-alls and deliberately exempt.
    survivors = [g for g in final if _normalize_theme_text(g["theme"]) not in _GENERIC_THEME_LABELS]
    blocklisted = [g for g in final if _normalize_theme_text(g["theme"]) in _GENERIC_THEME_LABELS]
    if not blocklisted:
        return _apply_grouping_target(survivors, target_count)

    by_norm: dict[str, dict[str, Any]] = {}
    for g in survivors:
        nt = _normalize_theme_text(g["theme"])
        by_norm.setdefault(nt, g)
    survivor_pairs: list[tuple[set[str], dict[str, Any]]] = []
    for g in survivors:
        survivor_pairs.append(
            (
                set(_normalize_theme_text(g["theme"]).split()),
                g,
            )
        )

    for g in blocklisted:
        g_tokens = set(_normalize_theme_text(g["theme"]).split())
        best: dict[str, Any] | None = None
        best_score = 0.0
        for tokens, candidate in survivor_pairs:
            if not tokens:
                continue
            union = g_tokens | tokens
            if not union:
                continue
            score = len(g_tokens & tokens) / len(union)
            if score > best_score:
                best_score = score
                best = candidate
        target = best if best_score >= 0.3 else None
        if target is None:
            target = next(
                (c for c in survivors if c["theme"] == "Additional Topics"),
                None,
            )
        if target is None:
            survivors.append(
                {
                    "theme": "Additional Topics",
                    "description": "Other notable developments across the tracked sources.",
                    "entries": [],
                }
            )
            target = survivors[-1]
        seen = {e.get("entry_id", "") for e in target["entries"] if e.get("entry_id")}
        for e in g["entries"]:
            eid = e.get("entry_id", "")
            if eid and eid in seen:
                continue
            if eid:
                seen.add(eid)
            target["entries"].append(e)
    return _apply_grouping_target(survivors, target_count)


def _apply_grouping_target(
    groups: list[dict[str, Any]],
    target_count: tuple[int, int] | None,
) -> list[dict[str, Any]]:
    """Nudge *groups* toward the ``[min, max]`` count on the degraded path.

    Optional: with ``target_count=None`` (LLM happy path) returns *groups*
    unchanged, so the pre-nudge behavior is byte-identical.  When set and the
    group count exceeds ``max``, repeatedly merge the most-similar pair of
    near-duplicate themes (by Jaccard on normalized tokens) until the count
    is within range or no similar pair remains.  Entries are reassigned into
    the merged group (deduped by ``entry_id``) — never dropped — and the
    count is never forced upward below ``min``.
    """
    from autoinfo.output import _GROUPING_TARGET_MIN_SIMILARITY

    if target_count is None or len(groups) <= target_count[1]:
        return groups

    pending = list(groups)
    while len(pending) > target_count[1]:
        best_pair: tuple[int, int, float] | None = None
        for i in range(len(pending)):
            i_tokens = set(_normalize_theme_text(pending[i]["theme"]).split())
            if not i_tokens:
                continue
            for j in range(i + 1, len(pending)):
                j_tokens = set(_normalize_theme_text(pending[j]["theme"]).split())
                if not j_tokens:
                    continue
                union = i_tokens | j_tokens
                if not union:
                    continue
                score = len(i_tokens & j_tokens) / len(union)
                if best_pair is None or score > best_pair[2]:
                    best_pair = (i, j, score)

        if best_pair is None or best_pair[2] < _GROUPING_TARGET_MIN_SIMILARITY:
            break

        i, j, _score = best_pair
        if len(str(pending[j]["theme"])) > len(str(pending[i]["theme"])):
            pending[i]["theme"] = pending[j]["theme"]
        if not pending[i].get("description") and pending[j].get("description"):
            pending[i]["description"] = pending[j]["description"]
        seen = {e.get("entry_id", "") for e in pending[i]["entries"] if e.get("entry_id")}
        for e in pending[j]["entries"]:
            eid = e.get("entry_id", "")
            if eid and eid in seen:
                continue
            if eid:
                seen.add(eid)
            pending[i]["entries"].append(e)
        del pending[j]

    return pending


def _ensure_all_entries_grouped(
    groups: list[dict[str, Any]],
    entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Guarantee every input entry appears in some group."""
    if not groups:
        return [
            {
                "theme": "General",
                # #338: no internal "All N entries included in this report."
                "description": "Overview of the tracked developments this period.",
                "entries": list(entries),
            }
        ]

    grouped_ids: set[str] = {
        e.get("entry_id", "") for g in groups for e in g["entries"] if e.get("entry_id")
    }
    missing = [e for e in entries if not (e.get("entry_id", "") and e["entry_id"] in grouped_ids)]
    if missing:
        if len(groups) >= 2:
            groups.append(
                {
                    "theme": "Additional Topics",
                    # #338: no internal "N entry(ies) not covered by other themes."
                    "description": "Other notable developments across the tracked sources.",
                    "entries": missing,
                }
            )
        else:
            groups[0]["entries"].extend(missing)
    return groups
