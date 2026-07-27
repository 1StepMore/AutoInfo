# End User Delivery SLA Reference

**Purpose**: Defines the delivery service level agreements for End User products.
This is the internal SLA reference for operators (agent and human) — not a
legally binding contract template.

References: F39 in `expectations.md`, `delivery.md` §4.5.

## SLA Targets by Product Priority

| Priority | Product Types | Target: First Delivery Attempt | Monitoring |
|----------|--------------|-------------------------------|------------|
| **P0** | Digests, real-time alerts, critical notifications | ≤5 minutes from generation | Alert on miss, retry immediately |
| **P1** | Reports, exports, scheduled summaries | ≤30 minutes from generation | Alert on miss, retry within window |
| **P2** | Bulk exports, historical archives, batch processing | ≤2 hours from generation | Track, no immediate alert |

## Delivery Attempt Lifecycle

```
Product Generated
    │
    ▼
Queue for Delivery (timestamp: queued_at)
    │
    ├── Primary Channel Attempt (timestamp: attempted_at)
    │   ├── Success → confirmed_at set, DeliveryLog updated
    │   ├── Hard Bounce → mark channel inactive, try fallback
    │   └── Soft Bounce → retry 3× with exponential backoff
    │                      (5min → 15min → 1hr)
    │
    ├── Fallback Channel Attempt (if primary failed)
    │   ├── Success → confirmed_at set, DeliveryLog updated
    │   └── Fail → queue for next delivery window
    │
    └── All Channels Failed
        ├── Queue product for next scheduled window
        ├── Alert operator (agent/human)
        └── Never silently drop
```

## Retry Strategy

| Bounce Type | Definition | Action |
|-------------|-----------|--------|
| **Hard bounce** | Invalid address/channel ID, user blocked bot, email rejected | Mark channel inactive immediately. Try fallback channel. Alert operator and End User. |
| **Soft bounce** | Temporary failure (inbox full, rate limited, channel temporarily unavailable) | Retry 3× with exponential backoff: 5min → 15min → 1hr. After 3 consecutive soft bounces → treat as hard bounce. |

## Channel-Specific SLA Details

| Channel | Delivery Confirmation Method | Failure Detection | SLA Exposure |
|---------|---------------------------|-------------------|--------------|
| **Email (SMTP)** | SMTP delivery receipt / bounce notification | Immediate bounce, or 30min timeout | Full P0-P2 |
| **Telegram** | API response with `message_id` | API error or timeout (10s) | Full P0-P2 |
| **WeChat OA** | API response | API error | P1-P2 (P0 best-effort) |
| **WeChat Work** | API response | API error | P1-P2 (P0 best-effort) |
| **DingTalk** | API response | API error | P1-P2 (P0 best-effort) |
| **Discord** | API response with `message_id` | API error or timeout (10s) | Full P0-P2 |

## SLA Miss Handling

| Miss Type | Action |
|-----------|--------|
| **Single P0 miss** | Alert operator immediately. Auto-retry with escalation (try all channels). |
| **Repeated P0 misses** (3+ in 24h) | Escalate to Director User. Review channel health, consider failover to alternative channel. |
| **Single P1 miss** | Alert operator. Retry within SLA window. |
| **Sustained P1 degradation** (>10% miss rate over 7d) | Escalate to Director User. Review infrastructure. |
| **P2 miss** | Log only. Alert operator if persistent. |

## Delivery Log Schema

Each delivery attempt records:

| Field | Type | Description |
|-------|------|-------------|
| `delivery_log_id` | UUID | Unique delivery attempt identifier |
| `subscription_id` | UUID | Target subscription |
| `product_id` | UUID | Delivered product |
| `channel` | string | Delivery channel used |
| `status` | enum | `queued` → `sent` → `delivered` → `failed` → `bounced` |
| `attempted_at` | ISO datetime | When delivery was attempted |
| `confirmed_at` | ISO datetime | When delivery was confirmed (null if not yet) |
| `error_message` | string | Error details on failure |
| `retry_count` | int | Number of retries for this attempt (0-3) |
| `trace_id` | UUID | Link to pipeline trace for full item journey |

## SLA Tracking Per Subscription

The system tracks per-subscription SLA compliance:

```
subscription_sla:
  subscription_id: "sub_xxx"
  period: "2026-07"
  total_deliveries: 142
  sla_misses: 3
  sla_compliance_pct: 97.9
  p0_misses: 1
  p1_misses: 2
  p2_misses: 0
  avg_delivery_latency_ms: 18000
  p95_delivery_latency_ms: 45000
  p99_delivery_latency_ms: 120000
  last_sla_breach: "2026-07-25T14:32:00Z"
```

Operator can query via `get_delivery_log(subscription_id, period)`.

## Fallback Chain

When the primary channel fails, the system tries channels in this order:

1. **Primary** (End User's preferred channel)
2. **Alternate push channel** (if configured: Telegram, WeChat, DingTalk, Discord)
3. **Email** (always available as mandatory fallback)

If all channels fail:
- Product is queued for the next delivery window
- Operator is alerted via `trace_item(trace_id)`
- End User is notified on next successful delivery

## References

- `docs/dev/specs/expectations.md` — F39 (Delivery Reliability & Logging)
- `docs/dev/specs/delivery.md` §4.5 — Delivery SLA tracking details
- `docs/dev/end-user-onboarding.md` — Full End User lifecycle guide
- `docs/dev/user-authorization-matrix.md` — Authorization boundaries
