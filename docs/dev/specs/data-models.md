# Data Models Reference

> Consolidated data model schemas referenced across all spec files. Source truth for these schemas lives in `src/autoinfo/`.

---

## 1. Collection & Pipeline Models

```python
@dataclass
class Item:
    """A single collected item before KB storage."""
    source_url: str
    source_type: str                  # "pubmed" | "rss" | "web" | "email" | "pdf"
    source_platform: str              # e.g. "pubmed", "arxiv", "hn"
    title: str
    content: str                      # main body text
    content_hash: str                 # SHA256(content) — dedup key
    author: str | None = None
    published: datetime | None = None
    collected_at: datetime = field(default_factory=datetime.now)
    raw_metadata: dict = field(default_factory=dict)  # source-specific (DOI, PMID, URL)
    topics: list[str] = field(default_factory=list)   # matched topic names
    relevance_score: float = 0.0      # populated by G3
    quality_flags: list[str] = field(default_factory=list)
```

```python
@dataclass
class ExtractionResult:
    """Structured output from LLM extraction."""
    tl_dr: str                         # One-sentence summary
    key_points: list[str]             # 3-5 bullet points
    entities: dict[str, list[str]]    # Extracted entities by type
    custom_fields: dict               # Domain-specific fields
    quality_score: float = 0.0        # 0-100, from G4/G5
    facts: list[str] = field(default_factory=list)    # verifiable claims (for G4)
    translation: str | None = None    # Translated text (if language != source)
```

---

## 2. KB Entry Schema

Stored as Markdown with YAML frontmatter:

```yaml
---
id: "raw_abc123"
source_url: "https://..."
source_type: "pubmed"
source_platform: "pubmed"
collected_at: "2026-07-26T10:00:00"
topics: ["IVF breakthroughs"]
content_sha: "abc123def456"
trace_id: "trc_abc123"
version: 1
relevance_score: 85
status: "active"       # "active" | "deleted" | "stale"
tier: "01-raw"         # "01-raw" | "02-draft" | "03-wiki"
---
```

---

## 3. Delivery Models

```python
@dataclass
class DeliveryResult:
    success: bool
    channel: str
    recipient: str
    delivered_at: datetime
    attempt_count: int = 1
    error: str | None = None
    receipt_id: str | None = None

@dataclass
class RetryConfig:
    max_retries: int = 3
    backoff_base: float = 5.0
    backoff_max: float = 300.0
    retryable_statuses: list[int] = field(default_factory=lambda: [408, 429, 500, 502, 503, 504])

@dataclass
class DeliveryLog:
    id: str                          # "dlog_{uuid8}"
    subscription_id: str             # FK to Subscription
    product_id: str | None           # FK to Product (if applicable)
    channel: str
    recipient: str
    success: bool
    attempt_count: int
    delivered_at: datetime
    error: str | None = None
    trace_id: str = ""
```

---

## 4. End User Models

```python
class UserStatus(Enum):
    TRIAL = "trial"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"

class SubscriptionStatus(Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    CANCELLED = "cancelled"

@dataclass
class UserProfile:
    id: str                          # "usr_{uuid8}"
    name: str
    email: str
    delivery_preferences: DeliveryPreferences
    status: UserStatus
    created_at: datetime
    updated_at: datetime
    identity_anchor: str             # "native" | "oauth_provider:{provider}:{sub}"

@dataclass
class DeliveryPreferences:
    channels: dict[str, list[ChannelConfig]]
    quiet_hours: QuietHours | None = None
    max_daily_digests: int = 1
    preferred_format: str = "markdown"

@dataclass
class ChannelConfig:
    channel_type: str
    recipient: str
    enabled: bool = True

@dataclass
class QuietHours:
    start: str                       # "22:00"
    end: str                         # "07:00"
    timezone: str = "UTC"
    only_urgent: bool = False

@dataclass
class Subscription:
    id: str                          # "sub_{uuid8}"
    user_id: str                     # FK to UserProfile
    domain: str
    topics: list[str]
    products: list[str]
    channels: list[str]
    schedule: str                    # Cron expression
    status: SubscriptionStatus
    created_at: datetime
    updated_at: datetime
    last_delivered_at: datetime | None = None
```

---

## 5. Operations Models

```python
@dataclass
class CostLog:
    id: str                          # "cost_{uuid8}"
    category: str                    # "llm" | "storage" | "api" | "delivery"
    domain: str
    user_id: str | None = None
    trace_id: str = ""
    amount: float
    currency: str = "USD"
    metadata: dict = field(default_factory=dict)
    recorded_at: datetime = field(default_factory=datetime.now)

@dataclass
class AuditLog:
    id: str                          # "audit_{uuid8}"
    action: str                      # "soft_delete" | "restore" | "promote" | "merge"
    entity_type: str                 # "kb_entry" | "user" | "subscription"
    entity_id: str
    operator: str                    # "agent" | "human:{name}"
    details: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class SysConfig:
    """Global system configuration (not domain-specific)."""
    llm: LLMConfig = field(default_factory=LLMConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)

@dataclass
class DecayMetrics:
    domain: str
    staleness_ratio: float
    avg_ttl_remaining_days: float
    decay_grade: str                 # "Green" | "Yellow" | "Red"

@dataclass
class SystemHealth:
    status: str                      # "healthy" | "degraded" | "unhealthy"
    llm_key_configured: bool
    llm_last_call_success: bool | None
    disk_usage_percent: float
    db_connected: bool
    db_size_mb: float
    active_collections: int
    active_cron_jobs: int
    slowest_source: str | None
    error_rate_last_24h: float
    overall_health_score: int        # 0-100
```
