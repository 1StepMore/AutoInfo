"""Collector contract for source-specific collectors.

Defines the one enforced interface every collector implements:

* :class:`CollectorContext` — the normalized input bundle (source config,
  topic, keywords, limit, URL, query, PMIDs, payload, settings).
* :class:`Collector` — an ABC whose single abstract member is
  :meth:`Collector.fetch_items`, returning ``list[Item]``.

Source-specific mechanics (a vendor's ``fetch(query=..., limit=...)``,
``search()`` + ``fetch(pmids)``, RSS ``fetch(url)``, …) stay on the handler as
implementation detail.  The pipeline only ever calls ``fetch_items(ctx)``, so
the contract is uniform and enforced by ``abc`` + mypy instead of by
attribute sniffing.

``BaseHandler`` remains as an alias of :class:`Collector` so existing imports
and subclasses keep working.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from autoinfo.config import SourceConfig
from autoinfo.models import Item


class SourceFailure(Exception):  # noqa: N818 - deliberately not "*Error": the name matches the
    # "dead source detection" feature terminology (per-source status="error"
    # + source_failed marker) used across collectors, collect.py, and docs.
    """Raised by collector handlers to signal an explicit source failure.

    Unlike a silent empty result, a ``SourceFailure`` carries a structured
    ``reason`` that the collection pipeline surfaces in per-source results
    (``status="error"`` + ``source_failed`` marker) and logs, so dead,
    retired, or unreachable sources are detectable instead of looking like
    a legitimate "0 items found".
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class CollectorContext:
    """Everything a collector needs to run one fetch, in normalized form.

    All fields are defaulted so tests (and callers that only care about one
    dimension) can build a minimal context.

    Attributes
    ----------
    source_config:
        The full :class:`SourceConfig` for this source.  ``None`` when a
        collector is exercised in isolation; handlers that need the source
        name / URL / settings must tolerate ``None``.
    topic:
        The requested topic string (empty means "no topic given").
    keywords:
        Domain/topic keywords used to build search queries where a collector
        accepts one.  Also used by PubMed as a fallback query when *topic* is
        empty.
    limit:
        Maximum number of items to return.  ``None`` means "use the
        handler's own default" — **handlers must distinguish that from
        ``0``**, which is an explicit zero-item request.
    url:
        The resolved fetch URL for URL-driven collectors (RSS/Web/PDF/API).
        Empty when the source has no URL.
    query:
        A pre-resolved free-text query (source ``settings.query``); empty
        when unset.  Collectors that build their query from *topic* /
        *keywords* use this only as a fallback.
    pmids:
        Explicit identifier list for identifier-driven collectors (PubMed).
        Empty means "search using topic/keywords first".
    payload:
        Push-based input (webhook/receiver payloads).  Empty for pull
        collection.
    settings:
        The source's ``settings`` dict (a copy, with ``fetch_depth``
        injected where the pipeline builds one).  Never the shared mutable
        config dict.
    """

    source_config: SourceConfig | None = None
    topic: str = ""
    keywords: list[str] = field(default_factory=list)
    limit: int | None = None
    url: str = ""
    query: str = ""
    pmids: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)
    settings: dict[str, Any] = field(default_factory=dict)

    @property
    def source_name(self) -> str:
        """Source name from :attr:`source_config` (``""`` when absent)."""
        return getattr(self.source_config, "name", "") or ""

    @property
    def source_type(self) -> str:
        """Source type from :attr:`source_config` (``""`` when absent)."""
        return getattr(self.source_config, "type", "") or ""

    def resolved_limit(self, default: int) -> int:
        """Return *default* when :attr:`limit` is ``None``, else the limit.

        ``limit=0`` must survive as ``0`` (explicit empty request) rather
        than being coerced to *default*.
        """
        return default if self.limit is None else self.limit


class Collector(ABC):
    """Abstract base class for all source collectors.

    Concrete subclasses implement exactly one method:
    :meth:`fetch_items`, which returns normalized
    :class:`Item <autoinfo.models.Item>` instances.

    Subclasses may expose additional source-specific methods (``fetch``,
    ``search``, ``collect``, ``handle``, ``to_item``) — those are
    implementation detail and are not part of the pipeline contract.
    """

    source_name: str = "base"

    #: 该源是否要求「平台应用/接口审核通过」才可正当采集。
    #: 子类声明式覆盖（如 Bilibili 反爬 + 需应用审核 → True）。
    #: 采集分发处（``collect._collect_from_source``）会消费它：声明为 True
    #: 且未获显式确认（``SourceConfig.app_review_ack`` 或环境变量
    #: ``AUTOINFO_APP_REVIEW_ACK=1``）时，该源**被跳过**而不是照常采。
    #: 对应委托人的硬约束「不做违法采集」。
    REQUIRES_APP_REVIEW: bool = False

    def requires_app_review(self) -> bool:
        """Whether this handler's platform requires app/interface review.

        Instance method so the dispatch point can call it on any handler
        uniformly.  Subclasses may override either the class attribute
        (:attr:`REQUIRES_APP_REVIEW`) or this method.
        """
        return bool(self.REQUIRES_APP_REVIEW)

    @abstractmethod
    def fetch_items(self, ctx: CollectorContext) -> list[Item]:
        """Fetch items from the source described by *ctx*.

        This is the **only** pipeline-facing contract.  Implementations must
        return :class:`Item <autoinfo.models.Item>` instances (converting
        raw dict payloads via their own ``to_item()`` where they produce
        dicts) and must honour ``ctx.limit`` — ``None`` means "handler
        default", ``0`` means "return no items".
        """
        ...


#: Backwards-compatible alias — existing handlers import ``BaseHandler``.
#: New code should use :class:`Collector` (the enforced contract).
BaseHandler = Collector
