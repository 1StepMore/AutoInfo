"""Source labelling and drift filtering for output generation.

Extracted from ``output/__init__.py`` (#582 phase 3). ``_get_domain_source_configs``
stays hub-resident (tests patch it through ``autoinfo.output``), so it is read
through a function-local hub import.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from autoinfo.config import SourceConfig

logger = logging.getLogger("autoinfo.output")


_DEMO_DOMAINS_DIR = Path(__file__).resolve().parent.parent / "data" / "domains"


_REF_LANG_LEARNING_DOMAINS: frozenset[str] = frozenset(
    {
        "language-learning",
        "english-learning",
        "french-learning",
        "spanish-learning",
        "hindi-learning",
        "korean-learning",
        "portuguese-learning",
        "russian-learning",
        "italian-learning",
    }
)


def _is_lang_learning_domain(domain: str) -> bool:
    """True when *domain* is a language-learning umbrella or sub-domain."""
    return domain in _REF_LANG_LEARNING_DOMAINS


_GENERIC_PLATFORMS = frozenset({"", "rss", "web", "api"})


_MATCHABLE_SOURCE_TYPES = frozenset({"rss", "web", "webhook", "api", "pdf"})


def _is_source_active_in_config(entry: dict[str, Any], domain: str) -> bool:
    """True when *entry*'s source identity exists in the domain's CURRENT
    config source list (selection-time source-drift filter, #119).

    An entry's source identity is established by EITHER:

    - HOST match: the entry's ``source_url`` host against each configured
      ``SourceConfig.url`` host via :func:`_host_matches_source` (exact or
      subdomain — ``arxiv.org`` ⊂ ``rss.arxiv.org``); OR
    - PLATFORM match: ``source_platform`` against a configured source's
      ``name``/``type`` — ONLY when the platform is non-generic.  Pre-#323
      entries carry generic ``source_platform='rss'/'web'/'api'``
      (:data:`_GENERIC_PLATFORMS`); a generic platform alone never matches
      and never false-drops an entry whose host matches.

    FAIL-OPEN: when the config is missing/unreadable,
    :func:`_get_domain_source_configs` returns ``[]`` — the helper returns
    ``True`` (keep everything, preserve today's output), never drops
    everything.  Deterministic — no LLM.
    """
    source_url = str(entry.get("source_url") or "").strip()
    platform = str(entry.get("source_platform") or "").strip()
    from autoinfo.output import _get_domain_source_configs

    configs = _get_domain_source_configs(domain)
    if not configs:
        return True
    url_host = ""
    if source_url:
        try:
            url_host = urlsplit(source_url).hostname or ""
        except ValueError:
            url_host = ""
    for sc in configs:
        sc_url = str(sc.url or "").strip()
        if url_host and sc_url:
            try:
                sc_host = urlsplit(sc_url).hostname or ""
            except ValueError:
                sc_host = ""
            if sc_host and _host_matches_source(url_host, sc_host):
                return True
        if platform and platform.lower() not in _GENERIC_PLATFORMS:
            if platform.lower() == str(sc.name or "").strip().lower():
                return True
            if platform.lower() == str(sc.type or "").strip().lower():
                return True
    return False


def _filter_drifted_entries(entries: list[dict[str, Any]], domain: str) -> list[dict[str, Any]]:
    """Selection-time source-drift filter over an entry list (digest /
    presentation paths, #119).

    Entries whose source identity is absent from the domain's current config
    source list are excluded at selection time — the KB entries themselves are
    never deleted/archived (Wiki append-only).  FAIL-OPEN: an unreadable config
    (``[]`` from :func:`_get_domain_source_configs`) excludes nothing.  Logs
    one ``logger.info`` per excluded source name with the dropped count.
    """
    kept: list[dict[str, Any]] = []
    dropped_by_source: dict[str, int] = {}
    for entry in entries:
        if not isinstance(entry, dict) or _is_source_active_in_config(entry, domain):
            kept.append(entry)
            continue
        source_name = _derive_source_label(entry, domain) or str(
            entry.get("source_platform") or entry.get("source_url") or "unknown"
        )
        dropped_by_source[source_name] = dropped_by_source.get(source_name, 0) + 1
    for source_name, count in sorted(dropped_by_source.items()):
        logger.info(
            "Excluded %d drifted entr%s from source '%s' absent from domain "
            "'%s' config (selection-time source-drift filter)",
            count,
            "y" if count == 1 else "ies",
            source_name,
            domain,
        )
    return kept


def _host_matches_source(entry_host: str, sc_host: str) -> bool:
    """True when an entry's URL host belongs to a configured source host.

    Issue #325 data layer: RSS feed URLs are often on a different host than
    the article links they carry (arXiv articles on ``arxiv.org`` vs the
    ``rss.arxiv.org`` feed), so exact-equality host matching leaves stale
    pre-#323 entries stuck on the generic ``(RSS)`` label.  Match when the
    hosts are equal or one is a subdomain of the other (``arxiv.org`` ⊂
    ``rss.arxiv.org``).  A bare substring match is rejected (``evil-arxiv.org``
    must not match ``arxiv.org``).  Pure stdlib (urllib.parse only — no
    tldextract dependency).
    """
    eh = (entry_host or "").lower().rstrip(".").lstrip("www1.").lstrip("www.")
    sh = (sc_host or "").lower().rstrip(".").lstrip("www1.").lstrip("www.")
    if not eh or not sh:
        return False
    if eh == sh:
        return True
    # Subdomain of each other (arXiv articles on arxiv.org vs the
    # rss.arxiv.org feed host) — never a bare substring (evil-arxiv.org
    # must not match arxiv.org).
    if eh.endswith("." + sh) or sh.endswith("." + eh):
        return True
    return False


def _derive_source_label(
    entry: dict[str, Any],
    domain: str,
    *,
    source_configs: list["SourceConfig"] | None = None,
) -> str:
    """Derive a specific source name for *entry* when its stored
    ``source_platform`` is a generic placeholder (``rss``/``web``/``api`` or
    empty) — issue #325.

    Pre-#323 KB entries carry ``source_platform='rss'`` even for real sources
    (TechCrunch, arXiv, 36Kr, …), so the References section rendered the
    generic ``(RSS)`` label.  The #323 collector fix only affects newly
    collected items; this re-derivation recovers the specific source name for
    existing entries by matching the entry's ``source_url`` host against the
    domain's configured source URLs.

    Returns the derived source identifier (a source config ``name``) when a
    match is found, otherwise returns the entry's stored ``source_platform``
    unchanged.  Matching is deterministic — no LLM.
    """
    platform = str(entry.get("source_platform") or "").strip()
    if platform.lower() not in _GENERIC_PLATFORMS:
        return platform
    source_url = str(entry.get("source_url") or "").strip()
    if not source_url:
        return platform
    try:
        url_host = urlsplit(source_url).hostname or ""
    except ValueError:
        return platform
    if not url_host:
        return platform
    if source_configs is None:
        from autoinfo.output import _get_domain_source_configs

        configs = _get_domain_source_configs(domain)
    else:
        configs = source_configs
    for sc in configs:
        if sc.type not in _MATCHABLE_SOURCE_TYPES:
            continue
        sc_url = str(sc.url or "").strip()
        if not sc_url:
            continue
        try:
            sc_host = urlsplit(sc_url).hostname or ""
        except ValueError:
            continue
        # Host match (issue #325 data layer): exact or subdomain (arXiv
        # articles on arxiv.org vs the rss.arxiv.org feed host) — never a
        # bare substring.
        if _host_matches_source(url_host, sc_host):
            return sc.name.strip() or platform
        # Feed-host mismatch (issue #325 WSJ blind spot): the article links
        # live on a DIFFERENT host than the feed (WSJ feed on feeds.a.dj.com,
        # articles on www.wsj.com / online.wsj.com — no subdomain relation).
        # A source can declare its article hosts via settings.article_hosts;
        # an entry whose URL host matches one derives the source name.
        declared_hosts = (sc.settings or {}).get("article_hosts") or []
        for declared in declared_hosts:
            try:
                declared_host = urlsplit(str(declared)).hostname or ""
            except ValueError:
                continue
            if declared_host and _host_matches_source(url_host, declared_host):
                return sc.name.strip() or platform
    return platform


def _label_entries(entries: list[dict[str, Any]], domain: str) -> list[dict[str, Any]]:
    """Enrich each entry with a derived ``source_label`` (issue #325).

    Adds ``source_label = _derive_source_label(entry, entry.get("domain",
    domain))`` to every entry so every render surface (markdown entry table,
    magazine byline/clusters, json/agent formats) shows the specific source
    name instead of the generic ``(RSS)`` label for stale pre-#323 entries.
    Per-entry own domain is used for cross-domain products.  Returns the
    enriched list (entries are dicts, mutated in place).
    """
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        entry["source_label"] = _derive_source_label(entry, str(entry.get("domain") or domain))
    return entries
