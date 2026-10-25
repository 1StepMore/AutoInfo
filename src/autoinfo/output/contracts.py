"""Output contract types and JSON-LD literals.

Extracted verbatim from ``output/__init__.py`` (#582 phase 3). This module has
NO ``autoinfo.*`` import by design: it is the leaf every other ``output``
module can depend on without creating a cycle.

The JSON-LD constants are serialized output contracts — their key order is
part of the wire format. Never rebuild them programmatically.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from autoinfo.quality import QualityResult

_JSONLD_DIGEST: dict[str, str] = {
    "@context": "https://autoinfo.ai/schemas/knowledge-digest-v1",
    "@type": "KnowledgeDigest",
}

_PRODUCT_ANALYSIS_FIELDS: tuple[str, ...] = (
    "implications",
    "risks",
    "action_required",
    "key_metrics",
)

_JSONLD_TUTORIAL: dict[str, str] = {
    "@context": "https://autoinfo.ai/schemas/knowledge-tutorial-v1",
    "@type": "KnowledgeTutorial",
}

_JSONLD_PRESENTATION: dict[str, str] = {
    "@context": "https://autoinfo.ai/schemas/knowledge-presentation-v1",
    "@type": "KnowledgePresentation",
}

_JSONLD_BASE_EXPORT: dict[str, str] = {
    "@context": "https://autoinfo.ai/schemas/knowledge-base-export-v1",
    "@type": "KnowledgeBaseExport",
}


@dataclass
class DeliveryOutput:
    """Output from a product generation run, extended with delivery gate results.

    When :func:`generate_digest` or :func:`generate_report` is called with
    *delivery_gate_configs* explicitly provided, the function returns a
    :class:`DeliveryOutput` instead of a plain ``str``.  Existing callers
    that do not pass *delivery_gate_configs* continue to receive a plain
    ``str`` (backward compatible).
    """

    output: str
    gate_results: dict[str, "QualityResult"] = field(default_factory=dict)
    delivery_blocked: bool = False
    delivery_format: str = ""
    warnings: list[str] = field(default_factory=list)


class StaleSourceError(ValueError):
    """Raised when freshness filtering removes all candidate entries for a
    digest/report, so the product would be an empty shell.

    Subclasses :class:`ValueError` so the CLI and MCP layers (which catch
    ``ValueError`` around ``generate_digest`` / ``generate_report``) surface a
    clean, actionable error instead of silently producing a product with no
    content (backup issue #52).
    """


class _DeliveryGatesBypass:
    """Sentinel type for explicitly bypassing delivery-gate resolution."""


_DELIVERY_GATES_BYPASS: Final = _DeliveryGatesBypass()


@dataclass
class ReportSection:
    """A single themed section within a report."""

    title: str
    content: str
    items: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ReportData:
    """Full report data passed to the Jinja2 template."""

    title: str
    generated_at: str
    domain: str
    collection_id: str = ""
    executive_summary: str = ""
    key_findings: list[dict[str, Any]] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    implications: list[str] = field(default_factory=list)
    risks: list[dict[str, Any]] = field(default_factory=list)
    action_required: list[str] = field(default_factory=list)
    key_metrics: list[dict[str, Any]] = field(default_factory=list)
    sections: list[ReportSection] = field(default_factory=list)
    references: list[dict[str, Any]] = field(default_factory=list)
    appendices: list[dict[str, Any]] = field(default_factory=list)
    grouping_degradation_marker: str = ""
