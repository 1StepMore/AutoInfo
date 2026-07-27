# Operations: Cost, Data Privacy, Knowledge Lifecycle, Observability

> Extracted from `founder-expectations.md §§12.16-12.19`. References: F28-F29 (Cost), F30-F31 (Data), F36-F39 (Lifecycle), F40-F44 (Observability).

---

## 1. Cost Governance & Metering (§12.16)

### 1.1 Cost Categories

| Category | Tracked Values | Unit | Precision |
|----------|---------------|------|-----------|
| **LLM Tokens** | model, prompt_tokens, completion_tokens, cost | tokens → USD | per API call |
| **Storage** | KB entry count, total bytes, git objects | bytes → MB | daily snapshot |
| **API Calls** | MCP tool invocations, external API requests | count | per call |
| **Delivery** | Channel usage per delivery | count | per delivery |

### 1.2 Cost Log Schema

```python
@dataclass
class CostLog:
    id: str                          # "cost_{uuid8}"
    category: str                    # "llm" | "storage" | "api" | "delivery"
    domain: str
    user_id: str | None = None       # For per-user allocation
    trace_id: str = ""               # Link to pipeline trace
    amount: float
    currency: str = "USD"
    metadata: dict = field(default_factory=dict)
    recorded_at: datetime = field(default_factory=datetime.now)
```

### 1.3 Cost Allocation Strategies

| Strategy | Description | v1 Implementation |
|----------|-------------|-------------------|
| **Pro-rata** | Split costs evenly across all active users | Default for shared LLM calls. `total_cost / active_users`. |
| **Usage-based** | Attribute costs to the user who triggered the action | Per-user extraction, per-user delivery. Direct attribution. |
| **Direct allocation** | Attribute costs to the domain + task that consumed them | LLM costs → `{domain}/{task_type}` tag; storage → `{domain}/{tier}` tag. Default for all pipeline costs. |

**Direct allocation detail**: Every LLM call records `domain` and `task_type` (e.g., `extraction`, `g4_factual_check`, `relevance_scoring`). Storage costs record `domain` and `tier`. This enables domain-level cost reporting without user attribution.

### 1.4 Cost Dashboard & Alerts

**MCP Tools**:

| Tool | Description |
|------|-------------|
| `get_cost_report(domain, period)` | Aggregate costs by category and domain for period |
| `get_billing_summary(user_id, period)` | Per-user billing summary |
| `set_budget_alert(domain, threshold_amount, period)` | Trigger alert when cost exceeds threshold |
| `get_budget_alerts(domain)` | List active budget alerts for domain |
| `get_cost_allocation(domain, period, strategy)` | Show cost breakdown by allocation strategy |

**Budget alerts**: When a domain's cost exceeds configured threshold within a period, an alert is generated via the Alert Rules system. Auto-remediation actions can be configured (e.g., pause collection, switch to cheaper model).

---

## 2. Data Privacy & Compliance (§12.17)

### 2.1 Soft Delete & Restore

```python
@dataclass
class AuditLog:
    id: str                          # "audit_{uuid8}"
    action: str                      # "soft_delete" | "restore" | "promote" | "merge" | "collect" | ...
    entity_type: str                 # "kb_entry" | "user" | "subscription"
    entity_id: str
    operator: str                    # "agent" | "human:{name}"
    details: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
```

- **Soft delete**: KB entries get `status: deleted` in frontmatter; git commit records the change. No data lost.
- **Restore**: Revert the status field; git `revert` on the commit.
- **Hard delete** (GDPR): After 30-day soft-delete window, entries can be permanently removed (git filter-branch or new clone without the history).
- **Audit log is append-only**: Immutable record of all data-modifying operations.

### 2.2 Data Export (GDPR)

`export_user_data(user_id)` gathers:
- User profile and delivery preferences
- Subscription history
- Delivery logs (metadata — not product content)
- No KB entries are included in user data export (KB is domain-owned, not user-owned)

### 2.3 Retention & TTL

| Data Type | Retention | Cleanup |
|-----------|-----------|---------|
| Soft-deleted entries | 30 days | Auto-permanent-delete after 30d |
| Delivery logs | 90 days | Auto-purge after 90d |
| Cost logs | 1 year | Archive after 1 year |
| Collection cache | 7 days | Auto-clean after 7d |
| KB entries (active) | Indefinite | User-configurable TTL per domain |

### 2.4 MCP Data Privacy Tools

| Tool | Description |
|------|-------------|
| `soft_delete_entry(entry_id, reason)` | Mark entry as deleted; log to audit |
| `restore_entry(entry_id)` | Restore soft-deleted entry |
| `export_user_data(user_id)` | Gather all user data for GDPR export |
| `delete_user_data(user_id, confirm)` | GDPR delete (requires confirmation) |
| `query_audit_log(entity_type, entity_id, limit)` | Browse immutable audit trail |

---

## 3. Knowledge Lifecycle (§12.18)

### 3.1 Per-Domain TTL

Each domain has a configurable TTL (time-to-live) for its entries:

```yaml
# domain config
lifecycle:
  default_ttl_days: 90              # Entries older than 90 days are "stale"
  stale_action: demote              # "demote" | "exclude" | "flag"
  auto_refresh: false               # If true, auto-re-collect stale topics
```

**Stale marking**: An entry is marked `stale: true` in frontmatter when its `collected_at` exceeds TTL. This is a flag, not a deletion — stale entries remain searchable but are:

- **Demoted** in search results (lower ranking)
- **Excluded** from digest generation (unless explicitly requested)
- **Never automatically deleted**

### 3.2 Domain Decay Metrics

```python
@dataclass
class DecayMetrics:
    domain: str
    staleness_ratio: float           # stale_entries / total_entries (0-1)
    avg_ttl_remaining_days: float    # Average days until entries go stale
    decay_grade: str                 # "Green" (< 0.2), "Yellow" (0.2-0.5), "Red" (> 0.5)
```

Calculated periodically (or on-demand via MCP tool). Used to suggest source additions or collection schedule changes.

### 3.3 Versioned Re-Collection

When re-collecting a source that was previously collected:

1. New collection creates a new set of Items (new `collected_at`, new `content_hash`)
2. Each KB entry has a `version` field in frontmatter (integer, starts at 1)
3. If content changed (different `content_sha`), a new version is created alongside the old (old preserved in git)
4. `get_entry_history(entry_id)` returns all versions
5. `compare_versions(entry_id, v1, v2)` returns structured diff (added/removed/modified sections)

### 3.4 Cross-Collection Dedup & Merge

| Level | Method | Scope | Cost |
|-------|--------|-------|------|
| 1 | URL exact match | All items in collection cache | O(1) |
| 2 | PMID/DOI/arXiv ID match | All KB tiers + cache | O(1) |
| 3 | Fuzzy title similarity (Levenshtein, threshold 0.85) | Items within configurable window | O(n) |
| 4 | Cross-source semantic similarity (LLM) | Level 3 flagged candidates | 1 LLM call per pair |

**Merge rule**: Level 4 LLM decides whether to merge (combine source URLs + metadata) or keep separate.

### 3.5 MCP Lifecycle Tools

| Tool | Description |
|------|-------------|
| `set_ttl(domain, ttl_days)` | Configure per-domain entry TTL |
| `compare_versions(entry_id, v1, v2)` | Structured diff between versions |
| `find_similar_items(entry_id, threshold)` | Semantic similarity search across KB |
| `merge_items(target_id, source_ids)` | LLM-assisted merge of duplicate entries |
| `refresh_staleness(domain)` | Re-scan and update stale flags for domain |
| `get_domain_decay(domain)` | Return decay metrics object |

---

## 4. Observability (§12.19)

### 4.1 Structured Pipeline Logging

Every pipeline event (collection, processing, delivery, gate failure) logs a structured JSON line:

```json
{
  "timestamp": "2026-07-26T10:00:00.000Z",
  "level": "INFO",
  "event": "collection.completed",
  "trace_id": "trc_abc123",
  "domain": "medical-research",
  "source": "pubmed",
  "items_count": 15,
  "duration_ms": 3200
}
```

Logging destinations: stdout (default), file, or external log aggregator (configurable).

### 4.2 Traceability

Every item has a `trace_id` set at Item construction (line 1 of the pipeline). This UUID follows the item through:

```
Collection → Processing (KB write) → Product generation → Delivery (DeliveryLog)
     ↑           ↑                      ↑                     ↑
trace_id    trace_id in KB          trace_id in          trace_id in
assigned    entry frontmatter       product metadata     delivery log
```

MCP tool: `trace_item(trace_id)` returns full pipeline timeline for an item.

### 4.3 Prometheus Metrics

Available at `http://localhost:8741/metrics` (configurable port):

| Metric | Type | Labels |
|--------|------|--------|
| `autoinfo_collections_total` | Counter | domain, source, status |
| `autoinfo_collection_duration_seconds` | Histogram | domain, source |
| `autoinfo_processing_total` | Counter | domain, task_type |
| `autoinfo_processing_duration_seconds` | Histogram | domain, task_type |
| `autoinfo_llm_tokens_total` | Counter | domain, model, task_type |
| `autoinfo_llm_cost_total` | Counter | domain, model |
| `autoinfo_deliveries_total` | Counter | domain, channel, success |
| `autoinfo_delivery_duration_seconds` | Histogram | domain, channel |
| `autoinfo_gate_failures_total` | Counter | domain, gate, action |
| `autoinfo_kb_entries_total` | Gauge | domain, tier |
| `autoinfo_staleness_ratio` | Gauge | domain |

### 4.4 Diagnostics

`diagnose_system()` MCP tool returns comprehensive health data:

```python
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
    slowest_source: str | None       # Source with highest avg collection time
    error_rate_last_24h: float
    overall_health_score: int        # 0-100
```

### 4.5 MCP Observability Tools

| Tool | Description |
|------|-------------|
| `trace_item(trace_id)` | Full pipeline timeline for a single item |
| `get_pipeline_logs(domain, event_type, level, since)` | Filtered pipeline log viewer |
| `get_metrics(metric_name, domain, since)` | Query Prometheus metrics |
| `diagnose_system()` | Comprehensive system health check |
