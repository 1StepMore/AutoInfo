"""Data models for AutoInfo.

Pure dataclasses with serialization methods — no business logic, no persistence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Item:
    """A single collected item from any source."""

    id: str
    source_name: str
    source_type: str
    source_url: str
    title: str
    content: str
    content_type: str = "text"
    collected_at: str = ""
    language: str = "en"
    domain: str = ""
    topic_tags: list[str] = field(default_factory=list)
    quality_tier: int = 1
    raw_data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Item:
        return cls(**data)


@dataclass
class CollectionResult:
    """Result of a collection run against one or more sources."""

    collection_id: str
    domain: str
    source: str = ""
    status: str = ""
    items_found: int = 0
    items_new: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)
    duration_s: float = 0.0
    estimated_duration_s: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CollectionResult:
        return cls(**data)


@dataclass
class KBEntry:
    """An entry in the knowledge base pipeline (01-Raw / 02-Draft / 03-Wiki)."""

    entry_id: str
    title: str
    domain: str
    tier: str = "01-Raw"
    source_url: str = ""
    source_type: str = ""
    source_platform: str = ""
    collected_at: str = ""
    summary: str = ""
    extracted_fields: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    priority: int = 3
    language: str = "en"
    quality_tier: int = 1
    relevance_score: float = 0.0
    dedup_status: str = "unique"
    file_path: str = ""
    custom_fields: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KBEntry:
        return cls(**data)


@dataclass
class ExtractionResult:
    """Structured extraction output from LLM processing."""

    item_id: str
    title: str = ""
    tl_dr: str = ""
    key_points: list[str] = field(default_factory=list)
    entities: list[dict[str, Any]] = field(default_factory=list)
    relevance_score: float = 0.0
    custom_fields: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExtractionResult:
        return cls(**data)


@dataclass
class SourceHealth:
    """Health status for a single source."""

    source_id: str
    status: str = "unknown"
    last_success: str = ""
    error_count: int = 0
    avg_response_time_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SourceHealth:
        return cls(**data)


@dataclass
class ItemRelation:
    """A link between two KB entries."""

    relation_id: str
    item_a_id: str
    item_b_id: str
    relation_type: str = "related"
    created_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ItemRelation:
        return cls(**data)


@dataclass
class CollectionStats:
    """Aggregated collection statistics across a period."""

    period: str = "daily"
    date_from: str = ""
    date_to: str = ""
    total_items: int = 0
    new_items: int = 0
    duplicate_items: int = 0
    domains: dict[str, int] = field(default_factory=dict)
    sources: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
