"""Base handler abstract class for source-specific collectors.

Provides :class:`BaseHandler`, an abstract base class that all source
handlers must subclass.  Each handler implements :meth:`fetch` with its
own signature; the ABC contract ensures a common programming interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

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


class BaseHandler(ABC):
    """Abstract base class for all source handlers.

    Concrete subclasses must implement :meth:`fetch`.  The method
    signature varies by handler type — see each subclass for details.

    All handlers share a :attr:`source_name` identifier used when
    populating :class:`Item` metadata.
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
    def fetch(self, *args: Any, **kwargs: Any) -> list[Item] | list[dict[str, Any]]:
        """Fetch items from the source.

        Parameters (varies by handler type)
        -----------------------------------
        * RSS/Web/PDF: ``fetch(url: str) -> list[Item]``
        * PubMed: ``fetch(pmids: list[str]) -> list[dict]``
          (use :meth:`to_item` to convert dicts to ``Item``)
        * Email: ``collect(config: dict) -> list[Item]``
        * Webhook: ``handle(payload: dict, config: dict) -> Item``

        Returns
        -------
        list[Item] | list[dict[str, Any]]
            Zero or more collected items — :class:`Item` instances for the
            handlers that build them directly, or raw ``dict`` payloads for
            the handlers that expose :meth:`to_item` for the conversion.
        """
        ...
