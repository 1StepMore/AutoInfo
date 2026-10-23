"""Collector registry — the single ``source_type -> Collector`` mapping.

Replaces the two per-source ``if/elif`` chains that used to live in
``collect.py``.  Adding a collector is now:

1. write a :class:`~autoinfo.collectors.base.Collector` subclass implementing
   ``fetch_items(ctx)``; and
2. add one :class:`CollectorRegistration` to :data:`_REGISTRY`.

Nothing else in the pipeline changes — ``build_collector`` is the only lookup
point.

Type-level dispatch is ordered: registrations carrying a ``name_contains``
predicate are tried first (in registration order) and the wildcard
registration (``name_contains=None``) is the fallback.  This is how the
``api`` type expresses its three name-selected implementations (PubMed /
Semantic Scholar / USPTO) plus the generic :class:`HttpApiHandler` without a
single ``if`` branch in the collection orchestrator.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from autoinfo.collectors.base import Collector
from autoinfo.config import SourceConfig


def handler_settings(source_config: SourceConfig) -> dict[str, Any]:
    """Build the ``config=`` dict passed to settings-based collectors.

    Copies the source's ``settings`` (never mutating the shared
    ``SourceConfig``) and injects the per-source ``fetch_depth``, so any
    settings-based handler can branch on content depth (``fulltext`` vs
    ``abstract``) without receiving the full ``SourceConfig``.  Handlers
    that do not read ``fetch_depth`` are unaffected — the key is inert.
    """
    settings = dict(source_config.settings or {})
    settings["fetch_depth"] = source_config.fetch_depth
    return settings


@dataclass(frozen=True)
class CollectorRegistration:
    """One ``source_type`` entry in the collector registry.

    Attributes
    ----------
    source_type:
        Lower-case source type this registration answers for (a value from
        :data:`autoinfo.config.VALID_SOURCE_TYPES`).
    factory:
        Callable taking the :class:`SourceConfig` and returning a
        :class:`Collector` instance.  Factories are cheap (no network).
    name_contains:
        Optional lower-case name predicate.  When set, the registration only
        matches sources whose *name* contains this substring.  ``None`` marks
        the wildcard/fallback registration for that source type.
    """

    source_type: str
    factory: Callable[[SourceConfig], Collector]
    name_contains: str | None = None


def _pubmed(config: SourceConfig) -> Collector:
    from autoinfo.collectors.pubmed import PubMedHandler

    return PubMedHandler(source_config=config)


def _semantic_scholar(config: SourceConfig) -> Collector:
    from autoinfo.collectors.semantic_scholar import SemanticScholarHandler

    return SemanticScholarHandler(source_config=config)


def _uspto(config: SourceConfig) -> Collector:
    from autoinfo.collectors.uspto import USPTOHandler

    return USPTOHandler(source_config=config)


def _http_api(config: SourceConfig) -> Collector:
    from autoinfo.collectors.http_api import HttpApiHandler

    return HttpApiHandler(config)


def _dblp(config: SourceConfig) -> Collector:
    from autoinfo.collectors.dblp import DBLPHandler

    return DBLPHandler(source_config=config)


def _nyt(config: SourceConfig) -> Collector:
    from autoinfo.collectors.nyt import NYTHandler

    return NYTHandler(config=handler_settings(config))


def _openalex(config: SourceConfig) -> Collector:
    from autoinfo.collectors.openalex import OpenAlexHandler

    return OpenAlexHandler(config=handler_settings(config))


def _ap_api(config: SourceConfig) -> Collector:
    from autoinfo.collectors.ap_api import APAPIHandler

    return APAPIHandler(source_config=config)


def _reuters_mcp(config: SourceConfig) -> Collector:
    from autoinfo.collectors.reuters_mcp import ReutersMCPHandler

    return ReutersMCPHandler(source_config=config)


def _reddit(config: SourceConfig) -> Collector:
    from autoinfo.collectors.reddit import RedditHandler

    return RedditHandler(config=handler_settings(config))


def _spotify(config: SourceConfig) -> Collector:
    from autoinfo.collectors.spotify import SpotifyHandler

    return SpotifyHandler(config=handler_settings(config))


def _youtube(config: SourceConfig) -> Collector:
    from autoinfo.collectors.youtube import YouTubeHandler

    return YouTubeHandler(config=handler_settings(config))


def _bilibili(config: SourceConfig) -> Collector:
    from autoinfo.collectors.bilibili import BilibiliHandler

    return BilibiliHandler(config=handler_settings(config))


def _apple_podcasts(config: SourceConfig) -> Collector:
    from autoinfo.collectors.apple_podcasts import ApplePodcastsHandler

    return ApplePodcastsHandler(config=handler_settings(config))


def _unpaywall(config: SourceConfig) -> Collector:
    from autoinfo.collectors.unpaywall import UnpaywallHandler

    return UnpaywallHandler(config=handler_settings(config))


def _gdelt(config: SourceConfig) -> Collector:
    from autoinfo.collectors.gdelt import GDELTHandler

    return GDELTHandler(config=handler_settings(config))


def _yahoo_finance(config: SourceConfig) -> Collector:
    from autoinfo.collectors.yahoo_finance import YahooFinanceHandler

    return YahooFinanceHandler(source_name=config.name)


def _quandl(config: SourceConfig) -> Collector:
    from autoinfo.collectors.quandl import QuandlHandler

    return QuandlHandler(source_config=config)


def _huggingface(config: SourceConfig) -> Collector:
    from autoinfo.collectors.huggingface import HuggingFaceHandler

    provider = "kaggle" if (config.type or "").lower() == "kaggle" else "huggingface"
    return HuggingFaceHandler(config={**handler_settings(config), "provider": provider})


def _rss(config: SourceConfig) -> Collector:
    from autoinfo.collectors.rss import RSSHandler

    return RSSHandler(source_name=config.name, fetch_depth=config.fetch_depth)


def _web(config: SourceConfig) -> Collector:
    from autoinfo.collectors.web import WebHandler

    return WebHandler(source_name=config.name)


def _email(config: SourceConfig) -> Collector:
    from autoinfo.collectors.email_imap import EmailHandler

    return EmailHandler(source_name=config.name)


def _pdf(config: SourceConfig) -> Collector:
    from autoinfo.collectors.pdf import PDFHandler

    return PDFHandler(source_name=config.name)


def _ssrn(config: SourceConfig) -> Collector:
    from autoinfo.collectors.ssrn import SSRNHandler

    return SSRNHandler(config=handler_settings(config))


def _hackernews(config: SourceConfig) -> Collector:
    from autoinfo.collectors.hackernews import HackerNewsHandler

    return HackerNewsHandler(config)


def _akshare(config: SourceConfig) -> Collector:
    from autoinfo.collectors.akshare import AKShareHandler

    return AKShareHandler(config=handler_settings(config))


def _sec_edgar(config: SourceConfig) -> Collector:
    from autoinfo.collectors.sec_edgar import SecEdgarHandler

    return SecEdgarHandler(config=handler_settings(config))


def _edx_sitemap(config: SourceConfig) -> Collector:
    from autoinfo.collectors.edx_sitemap import EdxSitemapHandler

    return EdxSitemapHandler(config=handler_settings(config))


def _reg(
    source_type: str,
    factory: Callable[[SourceConfig], Collector],
    name_contains: str | None = None,
) -> CollectorRegistration:
    return CollectorRegistration(source_type, factory, name_contains)


#: Ordered registrations per source type.  Predicate entries first, the
#: wildcard (``name_contains=None``) last.  ``webhook`` is deliberately
#: absent: it is push-only (payloads arrive via the receiver), so there is
#: nothing to build for pull collection.
_REGISTRY: dict[str, tuple[CollectorRegistration, ...]] = {
    "api": (
        _reg("api", _pubmed, "pubmed"),
        _reg("api", _semantic_scholar, "semantic"),
        _reg("api", _uspto, "uspto"),
        _reg("api", _http_api),
    ),
    "akshare": (_reg("akshare", _akshare),),
    "ap_api": (_reg("ap_api", _ap_api),),
    "apple_podcasts": (_reg("apple_podcasts", _apple_podcasts),),
    "bilibili": (_reg("bilibili", _bilibili),),
    "dblp": (_reg("dblp", _dblp),),
    "edx_sitemap": (_reg("edx_sitemap", _edx_sitemap),),
    "email": (_reg("email", _email),),
    "email_imap": (_reg("email_imap", _email),),
    "gdelt": (_reg("gdelt", _gdelt),),
    "hackernews": (_reg("hackernews", _hackernews),),
    "huggingface": (_reg("huggingface", _huggingface),),
    "kaggle": (_reg("kaggle", _huggingface),),
    "nyt": (_reg("nyt", _nyt),),
    "openalex": (_reg("openalex", _openalex),),
    "pdf": (_reg("pdf", _pdf),),
    "quandl": (_reg("quandl", _quandl),),
    "reddit": (_reg("reddit", _reddit),),
    "reuters_mcp": (_reg("reuters_mcp", _reuters_mcp),),
    "rss": (_reg("rss", _rss),),
    "sec_edgar": (_reg("sec_edgar", _sec_edgar),),
    "spotify": (_reg("spotify", _spotify),),
    "ssrn": (_reg("ssrn", _ssrn),),
    "unpaywall": (_reg("unpaywall", _unpaywall),),
    "web": (_reg("web", _web),),
    "yahoo_finance": (_reg("yahoo_finance", _yahoo_finance),),
    "youtube": (_reg("youtube", _youtube),),
}

#: Source types accepted as configuration values but not buildable for pull
#: collection.  Kept explicit (never silently inferred) so the parity test
#: can distinguish "known non-buildable" from "forgotten registration".
NON_BUILDABLE_SOURCE_TYPES: frozenset[str] = frozenset(
    {
        # Inbound push: payloads arrive via the webhook receiver.
        "webhook",
        # Forward-declared in VALID_SOURCE_TYPES; no pull collector yet.
        "core",
    }
)


def build_collector(source_config: SourceConfig) -> Collector | None:
    """Return a collector for *source_config*, or ``None`` when unbuildable.

    Resolution order per source type: registrations with a matching
    ``name_contains`` predicate (registration order), then the wildcard
    registration.  ``None`` means "this type is accepted as configuration but
    has no pull collector" (e.g. ``webhook``, ``core``).
    """
    stype = (source_config.type or "").lower()
    registrations = _REGISTRY.get(stype)
    if not registrations:
        return None

    name = (source_config.name or "").lower()
    wildcard: CollectorRegistration | None = None
    for registration in registrations:
        if registration.name_contains is None:
            wildcard = registration
        elif registration.name_contains in name:
            return registration.factory(source_config)
    return wildcard.factory(source_config) if wildcard is not None else None


def registered_source_types() -> set[str]:
    """Return every source type that has at least one registration."""
    return set(_REGISTRY)


def registrations_for(source_type: str) -> tuple[CollectorRegistration, ...]:
    """Return the ordered registrations for *source_type* (empty if none)."""
    return _REGISTRY.get(source_type.lower(), ())


def register_collector(registration: CollectorRegistration, *, prepend: bool = True) -> None:
    """Add *registration* to the registry (used by tests and plugins).

    ``prepend=True`` puts it ahead of existing registrations for that type,
    which is what a boundary test needs to prove resolution order.
    """
    existing = _REGISTRY.get(registration.source_type, ())
    ordered = (registration,) + existing if prepend else existing + (registration,)
    _REGISTRY[registration.source_type] = ordered


def unregister_collector(registration: CollectorRegistration) -> None:
    """Remove *registration* from the registry, restoring the prior shape."""
    existing = _REGISTRY.get(registration.source_type, ())
    remaining = tuple(r for r in existing if r is not registration)
    if remaining:
        _REGISTRY[registration.source_type] = remaining
    else:
        _REGISTRY.pop(registration.source_type, None)
