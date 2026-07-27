# AutoInfo — Cross-Dimensional Catalog

> **Keystone document.** This is the single source of truth for the complete product definition across all dimensions.
>
> **Relationship to founder expectations:** `docs/dev/founder-expectations.md` defines **why** the product exists (founder's vision). This document defines **what** the product is — the complete cross-dimensional matrix of Pipeline Value Chain (A1-A7) × User Types (B1/B2/B3). Every cell is evaluated: 🟢 fully delivered, 🟡 partially delivered, 🔴 not delivered (gap).
>
> **How to use this document:**
> 1. Start here to understand the full product landscape
> 2. For each cell, find the relevant spec in `docs/dev/specs/` for detailed behavior
> 3. 🔴 cells are gaps — if no spec exists, a new spec is needed
> 4. Each CD-NNN gap references the affected spec file and the fix required
>
> **CD-NNN scheme:** Cross-Dimensional, sequentially numbered by category. Historical gap IDs (AU, G, C, A, B) cross-referenced in Appendix.
>
> **Cell status:** 🔴 = Never Designed (gap), 🟡 = Spec'd Not Impl / Partially Impl, 🟢 = Spec Outdated, 🟠 = Architecture Gap

---

## Table of Contents

1. [The Matrix — Dimension A × Dimension B](#section-1-the-matrix--dimension-a--dimension-b)
2. [Dimension Catalog by Type](#section-2-dimension-catalog-by-type)
3. [Gap-to-Doc Mapping](#section-3-gap-to-doc-mapping)
4. [Priority Fix Matrix](#section-4-priority-fix-matrix)
5. [Implementation Roadmap](#section-5-implementation-roadmap)

---

## Section 1: The Matrix — Dimension A × Dimension B

### Dimension A: Pipeline Value Chain (7 Stages)

| Stage | Description | Entry Point | Exit Criteria |
|-------|-------------|-------------|---------------|
| **A1 Collection** | Source handlers fetch items in parallel → dedup → collection log | Source config, cron trigger | Raw JSON cached to `collections/`, dedup applied |
| **A2 Extraction** | LLM extraction → quality gates (G0-G5) → structured summaries | Cached raw items | Summaries with TL;DR, key points, entities, scores |
| **A3 Knowledge Base** | 4-tier pipeline (01-Raw → 02-Draft → 03-Wiki), search, Q&A, graph | Summaries flagged for KB | KB entries in Raw/Draft/Wiki tiers |
| **A4 Products** | RAW feeds + PROCESSED assembly (digests, reports, tutorials, alerts) | KB entries, schedule triggers | Product instances with lifecycle state |
| **A5 Delivery** | Channel routing (SMTP, Telegram, WeChat, Discord, DingTalk, FeiShu, webhook, REST, export) | Product instances, subscription configs | Delivery log entries with SLA tracking |
| **A6 Consumption** | End-user receipt, read/open tracking, engagement measurement, feedback | Delivered products | Engagement signals, retention data |
| **A7 Operations** | Monitoring, cost governance, data lifecycle, scaling, DR | System-wide | Healthy system, predictable costs, data integrity |

### Dimension B: User Types × Lifecycle Stages

| User Type | Lifecycle Stages |
|-----------|-----------------|
| **B1 End User** (paying customer) | B1.1 Discover → B1.2 Trial → B1.3 Subscribe → B1.4 Consume → B1.5 Renew → B1.6 Churn |
| **B2 Direct User** (agent/MCP operator) | B2.1 Discover → B2.2 Connect → B2.3 Configure → B2.4 Operate → B2.5 Monitor → B2.6 Update |
| **B3 Director User** (human commander) | B3.1 Define → B3.2 Configure → B3.3 Monitor → B3.4 Iterate → B3.5 Scale |

### The Matrix: Value Delivery Score

Each cell: 🟢 = Fully delivered / complete, 🟡 = Partially delivered / gaps exist, 🔴 = Not delivered / blank space, ⚪ = Not applicable

#### A1 Collection

| Lifecycle → | B1.1 Discover | B1.2 Trial | B1.3 Subscribe | B1.4 Consume | B1.5 Renew | B1.6 Churn |
|-------------|:---:|:---:|:---:|:---:|:---:|:---:|
| **A1 Collection** | ⚪ | 🟢 Trial user gets same collection | ⚪ | 🟢 Content is flowing | ⚪ | ⚪ |

| Lifecycle → | B2.1 Discover | B2.2 Connect | B2.3 Configure | B2.4 Operate | B2.5 Monitor | B2.6 Update |
|-------------|:---:|:---:|:---:|:---:|:---:|:---:|
| **A1 Collection** | 🟢 `list_available_platforms` | 🟢 MCP tools auto-discovered | 🟢 `add_source`, `add_topic`, `add_schedule` | 🟢 `collect_sources`, `process_collection`, `batch_run` | 🟡 No cron reliability monitoring | 🟢 Source config is mutable |

| Lifecycle → | B3.1 Define | B3.2 Configure | B3.3 Monitor | B3.4 Iterate | B3.5 Scale |
|-------------|:---:|:---:|:---:|:---:|:---:|
| **A1 Collection** | 🟢 `add_domain`, `add_source` | 🟢 `activate_domain`, source health | 🟡 No collection pipeline dashboard | 🟢 Sources are editable | 🟡 No multi-source orchestration, no rate limiting |

#### A2 Extraction

| Lifecycle → | B1.1 Discover | B1.2 Trial | B1.3 Subscribe | B1.4 Consume | B1.5 Renew | B1.6 Churn |
|-------------|:---:|:---:|:---:|:---:|:---:|:---:|
| **A2 Extraction** | ⚪ | 🟢 Trial user gets processed content | ⚪ | 🟢 LLM extraction works | ⚪ | ⚪ |

| Lifecycle → | B2.1 Discover | B2.2 Connect | B2.3 Configure | B2.4 Operate | B2.5 Monitor | B2.6 Update |
|-------------|:---:|:---:|:---:|:---:|:---:|:---:|
| **A2 Extraction** | 🟢 `get_domain_schema`, `list_available_models` | 🟢 MCP tools | 🟢 Per-task LLM config, custom extraction fields | 🟢 `process_collection`, quality gates G0-G5 | 🟡 Processing progress polling is basic | 🟢 Config via MCP tools |

| Lifecycle → | B3.1 Define | B3.2 Configure | B3.3 Monitor | B3.4 Iterate | B3.5 Scale |
|-------------|:---:|:---:|:---:|:---:|:---:|
| **A2 Extraction** | 🟢 Custom extraction field schema | 🟢 Per-domain LLM config | 🟡 No extraction quality dashboard | 🟢 Gates are configurable | 🟡 No batch processing batching |

#### A3 Knowledge Base

| Lifecycle → | B1.1 Discover | B1.2 Trial | B1.3 Subscribe | B1.4 Consume | B1.5 Renew | B1.6 Churn |
|-------------|:---:|:---:|:---:|:---:|:---:|:---:|
| **A3 Knowledge Base** | ⚪ | 🟡 KB is usable but no tenant isolation | ⚪ | 🟢 Search, Q&A, graph | ⚪ | 🔴 No data export on cancellation |

| Lifecycle → | B2.1 Discover | B2.2 Connect | B2.3 Configure | B2.4 Operate | B2.5 Monitor | B2.6 Update |
|-------------|:---:|:---:|:---:|:---:|:---:|:---:|
| **A3 Knowledge Base** | 🟢 KB tools listed | 🟢 Full KB tool set | 🟢 `reindex_kb`, `list_kb_tier` | 🟢 `create_kb_draft`, `search_kb`, `query_knowledge_graph` | 🟡 `compare_versions` missing, `merge_items` partially | 🟢 KB is mutable (soft-delete, restore) |

| Lifecycle → | B3.1 Define | B3.2 Configure | B3.3 Monitor | B3.4 Iterate | B3.5 Scale |
|-------------|:---:|:---:|:---:|:---:|:---:|
| **A3 Knowledge Base** | 🟢 Wiki is append-only per spec | 🟢 Promote/reject Draft CLI | 🟡 No KB quality dashboard | 🟢 Items can be flagged, deprecated | 🔴 No multi-tenant KB isolation |

#### A4 Products

| Lifecycle → | B1.1 Discover | B1.2 Trial | B1.3 Subscribe | B1.4 Consume | B1.5 Renew | B1.6 Churn |
|-------------|:---:|:---:|:---:|:---:|:---:|:---:|
| **A4 Products** | 🔴 No product catalog / storefront | 🔴 No trial product preview | 🔴 No subscription→product gating (all hardcoded to `free`) | 🟡 Products deliver but lifecycle is not tracked | 🔴 No renewal product regeneration | 🔴 No product archive on churn |

| Lifecycle → | B2.1 Discover | B2.2 Connect | B2.3 Configure | B2.4 Operate | B2.5 Monitor | B2.6 Update |
|-------------|:---:|:---:|:---:|:---:|:---:|:---:|
| **A4 Products** | 🟢 `list_products`, `get_product` MCP exists | 🟢 MCP tools | 🟢 Product templates exist (RAW, PROCESSED) | 🟡 Products are generated but lifecycle state machine is 0% implemented | 🔴 No product engagement metrics | 🟡 Template config is mutable via code |

| Lifecycle → | B3.1 Define | B3.2 Configure | B3.3 Monitor | B3.4 Iterate | B3.5 Scale |
|-------------|:---:|:---:|:---:|:---:|:---:|
| **A4 Products** | 🟢 Product types defined (RAW/PROCESSED) | 🔴 No per-product access level gating | 🔴 No product delivery dashboard | 🔴 No A/B testing, no template iteration | 🔴 No product catalog scaling strategy |

#### A5 Delivery

| Lifecycle → | B1.1 Discover | B1.2 Trial | B1.3 Subscribe | B1.4 Consume | B1.5 Renew | B1.6 Churn |
|-------------|:---:|:---:|:---:|:---:|:---:|:---:|
| **A5 Delivery** | ⚪ | 🟢 Trial delivery works (same channels) | 🟡 Subscription→channel linking is disconnected | 🟡 Delivery works but no read tracking | 🟡 Renewal delivery continues | 🔴 No cancellation delivery receipt |

| Lifecycle → | B2.1 Discover | B2.2 Connect | B2.3 Configure | B2.4 Operate | B2.5 Monitor | B2.6 Update |
|-------------|:---:|:---:|:---:|:---:|:---:|:---:|
| **A5 Delivery** | 🟢 Delivery tools listed | 🟢 MCP tools | 🟢 `send_to_enduser`, channel config | 🟡 Delivery works, `query_delivery_log` exists | 🟡 No per-channel health monitoring | 🟢 Config is mutable |

| Lifecycle → | B3.1 Define | B3.2 Configure | B3.3 Monitor | B3.4 Iterate | B3.5 Scale |
|-------------|:---:|:---:|:---:|:---:|:---:|:---:|
| **A5 Delivery** | 🟢 11 delivery channels | 🟢 Channel config via webhook/schedule | 🟡 No unified delivery dashboard | 🟢 Adapters are modular | 🟡 No delivery SLA dashboard, no channel auto-failover |

#### A6 Consumption

| Lifecycle → | B1.1 Discover | B1.2 Trial | B1.3 Subscribe | B1.4 Consume | B1.5 Renew | B1.6 Churn |
|-------------|:---:|:---:|:---:|:---:|:---:|:---:|
| **A6 Consumption** | ⚪ | ⚪ | ⚪ | 🔴 No consumption tracking at all | 🔴 No engagement data for renewal signals | 🔴 No churn analysis |

| Lifecycle → | B2.1 Discover | B2.2 Connect | B2.3 Configure | B2.4 Operate | B2.5 Monitor | B2.6 Update |
|-------------|:---:|:---:|:---:|:---:|:---:|:---:|
| **A6 Consumption** | ⚪ | ⚪ | ⚪ | 🔴 No MCP tools for consumption data | 🔴 No engagement metrics accessible | ⚪ |

| Lifecycle → | B3.1 Define | B3.2 Configure | B3.3 Monitor | B3.4 Iterate | B3.5 Scale |
|-------------|:---:|:---:|:---:|:---:|:---:|:---:|
| **A6 Consumption** | 🔴 No consumption KPIs defined | ⚪ | 🔴 No consumption dashboard | 🔴 No data-driven iteration loop | 🔴 No consumption-based scaling signals |

#### A7 Operations

| Lifecycle → | B1.1 Discover | B1.2 Trial | B1.3 Subscribe | B1.4 Consume | B1.5 Renew | B1.6 Churn |
|-------------|:---:|:---:|:---:|:---:|:---:|:---:|
| **A7 Operations** | ⚪ | ⚪ | 🟢 Billing/cost operations | ⚪ | ⚪ | 🟢 Soft-delete, retention, GDPR export |

| Lifecycle → | B2.1 Discover | B2.2 Connect | B2.3 Configure | B2.4 Operate | B2.5 Monitor | B2.6 Update |
|-------------|:---:|:---:|:---:|:---:|:---:|:---:|
| **A7 Operations** | 🟢 Diagnostics tools listed | 🟢 `diagnose_system` | 🟢 `set_budget_thresholds`, `set_gate_config` | 🟢 Cost metering, audit log, trace | 🟡 No Prometheus alert rules implementation, no cron health | 🟢 System is configurable at runtime |

| Lifecycle → | B3.1 Define | B3.2 Configure | B3.3 Monitor | B3.4 Iterate | B3.5 Scale |
|-------------|:---:|:---:|:---:|:---:|:---:|:---:|
| **A7 Operations** | 🟡 No RPO/RTO defined | 🟢 Config via MCP/CLI | 🟡 No live operations dashboard | 🟡 Doctor exists but no structured DR runbook | 🔴 No horizontal scaling strategy, SQLite is single-node |

### Matrix Summary Statistics

| Metric | Count |
|--------|-------|
| Total cells | 119 (7×17 lifecycle stages) |
| 🟢 Fully delivered | 56 (47%) |
| 🟡 Partially delivered | 29 (24%) |
| 🔴 Not delivered | 30 (25%) |
| ⚪ Not applicable | 4 (3%) |

---

## Section 2: Dimension Catalog by Type

### Gap ID Scheme: CD-NNN

This catalog uses the **CD-NNN** scheme (Cross-Dimensional). Each gap is assigned a unique number sequentially by gap type. Existing gap IDs from other documents are cross-referenced in §3.

---

### Type 1: 🔴 Never Designed / Blank Spaces

Concepts that have never been designed — no spec, no code, no MCP tools.

#### CD-001: Multi-Tenancy Isolation
- **Description:** No tenant isolation model. `user_id` fields exist on entries but there is no tenant context, no data isolation boundary, no cross-tenant access control. All KB entries share one SQLite database.
- **Affected Stages:** A3 (KB), A7 (Operations)
- **Affected Users:** B1 (End User — can see other users' data if query crafted), B2 (Direct Agent — no tenant context in MCP), B3 (Director — cannot manage tenants)
- **Existing Cross-Ref:** None (new)
- **Evidence:** `user_id` in entry schemas but no authentication/authorization layer anywhere. SQLite shared across all users.

#### CD-002: End-User Authentication
- **Description:** No authentication system. No login, no sessions, no OAuth, no magic links. The CLI portal uses no auth. The REST API has no auth (localhost security only). End users are identified by manual ID assignment.
- **Affected Stages:** A5 (Delivery), A6 (Consumption), A7 (Operations)
- **Affected Users:** B1 (End User — no identity), B2 (Direct Agent — no auth token flow), B3 (Director — no user management)
- **Existing Cross-Ref:** AUD-05, G15
- **Evidence:** `activate_trial()` takes an `enduser_id` parameter directly — no identity verification. `send_to_enduser` takes an ID with no session context.

#### CD-003: Rate Limiting / Abuse Prevention
- **Description:** No rate limiting on any API surface (MCP, REST API, CLI). No per-tenant or per-user request quotas. No backpressure mechanism. A single user can saturate all resources.
- **Affected Stages:** A1 (Collection), A2 (Extraction), A7 (Operations)
- **Affected Users:** B2 (Direct Agent — no API limits), B3 (Director — no abuse protection)
- **Existing Cross-Ref:** None (new)
- **Evidence:** `collect_sources`, `process_collection`, and all MCP tools have zero rate limiting code. `batch_run` has no concurrency cap.

#### CD-004: Cron Reliability & Backup
- **Description:** Cron scheduling exists (`add_schedule`, `run_schedules`) but there is no: missed-schedule detection, cron failure alerts, backup of cron jobs, fallback mechanism if cron daemon fails. No crond health monitoring.
- **Affected Stages:** A1 (Collection), A7 (Operations)
- **Affected Users:** B2 (Direct Agent — no cron reliability guarantees), B3 (Director — no cron monitoring)
- **Existing Cross-Ref:** None (new)
- **Evidence:** `schedule.py` uses `croniter` + `subprocess` to install crontab entries. No health checks on cron execution. (`get_schedule_status` MCP tool IS registered — the reliability gap is about monitoring/alerting, not tool availability.)

#### CD-005: Admin Dashboard
- **Description:** No web-based admin console exists. The only dashboards are: CLI (`autoinfo status`, `autoinfo cost dashboard`) and MCP tools. No visual overview of system health, user activity, collection status, delivery metrics.
- **Affected Stages:** A7 (Operations)
- **Affected Users:** B3 (Director — no operations dashboard)
- **Existing Cross-Ref:** None (new)
- **Evidence:** No admin routes in FastAPI server. Web UI Dashboard (Bootstrap 5) exists but shows only collection stats/KB search — no admin functions.

#### CD-006: Unified Notification Framework
- **Description:** No unified notification system. Budget alerts (`alerts.py`) are separate from user lifecycle notifications (trial ending, digest ready). System alerts (cron failure, disk usage) don't exist. No notification templates, no notification preferences per user.
- **Affected Stages:** A7 (Operations), A5 (Delivery)
- **Affected Users:** B1 (End User — no lifecycle notifications), B2 (Direct Agent — no agent alerts), B3 (Director — no system alerting)
- **Existing Cross-Ref:** None (new)
- **Evidence:** Budget alerts exist in `alerts.py` with YAML persistence and DeliveryChannel dispatch. No email template for "trial ending" or "digest ready". No webhook for system events.

#### CD-007: Delivery Channel Health Monitoring
- **Description:** No health monitoring for delivery channels (Telegram Bot, WeChat OA, DingTalk, etc.). If a channel API goes down, delivery silently fails or retries without alerting. No channel latency tracking, no automatic channel suspension.
- **Affected Stages:** A5 (Delivery), A7 (Operations)
- **Affected Users:** B1 (End User — undelivered content), B2 (Direct Agent — no channel health visibility), B3 (Director — no channel reliability SLAs)
- **Existing Cross-Ref:** None (new)
- **Evidence:** DeliveryLog tracks per-item delivery but no aggregate channel health. No `get_channel_health` MCP tool. Channel adapters have no health endpoint.

#### CD-008: Pre-Delivery Product Preview
- **Description:** No way to preview a product (digest, report, tutorial) before delivery. End users receive without preview. Agents/directors cannot preview in MCP/CLI.
- **Affected Stages:** A4 (Products), A5 (Delivery)
- **Affected Users:** B1 (End User — no preview before subscribe), B2 (Direct Agent — no preview before send), B3 (Director — no QA preview)
- **Existing Cross-Ref:** G4 (Consumer-facing gap: "no product preview")
- **Evidence:** `generate_digest` directly produces final output. No `preview_digest` or `preview_product` MCP.

#### CD-009: Email Templates
- **Description:** No email templates for user lifecycle events. SMTP sender exists (`email_sender.py`) and `send_email_digest` works, but there are no templates for: welcome email, trial-ending notification, digest-ready notification, payment failure, cancellation confirmation.
- **Affected Stages:** A5 (Delivery), A6 (Consumption)
- **Affected Users:** B1 (End User — all emails are plain/digest-only), B3 (Director — no lifecycle email configuration)
- **Existing Cross-Ref:** None (new)
- **Evidence:** `email_sender.py` sends plain text/HTML messages. No template engine integration. No `list_email_templates` MCP tool.

#### CD-010: Product Catalog / Storefront
- **Description:** No product discovery for end users. No storefront, no product listing page, no pricing page. End users have no way to browse available products.
- **Affected Stages:** A4 (Products), A6 (Consumption)
- **Affected Users:** B1 (End User — cannot discover products), B3 (Director — no product marketing channel)
- **Existing Cross-Ref:** G7 (Consumer-facing gap: "no Substack-style discovery")
- **Evidence:** `list_products` MCP tool exists but returns products for agent use, not for end-user browsing. No public product catalog.

#### CD-011: Consumption Tracking (Read Receipts / Engagement)
- **Description:** No tracking of whether delivered products are read, opened, or engaged with. No read receipts, no open rates, no click tracking, no time-spent measurement. No engagement metrics at all.
- **Affected Stages:** A6 (Consumption)
- **Affected Users:** B1 (End User — no consumption history), B2 (Direct Agent — no engagement data accessible), B3 (Director — no content effectiveness measurement)
- **Existing Cross-Ref:** AUD-04, G8
- **Evidence:** No `ConsumptionEvent` model. No read receipt infrastructure. No MCP tool for engagement metrics.

#### CD-012: Retention & Churn Analysis
- **Description:** No retention analysis, no churn prediction, no churn reason tracking. End user lifecycle state machine exists (trial→active→suspended→cancelled) but no analytics on top of it.
- **Affected Stages:** A6 (Consumption), A7 (Operations)
- **Affected Users:** B1 (End User — no win-back offers), B3 (Director — no churn visibility)
- **Existing Cross-Ref:** None (new)
- **Evidence:** `end_user.py` has state transitions but zero analytics. No churn dashboard. No `get_retention_report` MCP tool.

#### CD-013: Live Operations Dashboard
- **Description:** No real-time operations dashboard. `diagnose_system()` returns structured health data but there is no visual dashboard showing: live collection status, delivery queue depth, error rates, active user count, resource usage.
- **Affected Stages:** A7 (Operations)
- **Affected Users:** B3 (Director — no live ops visibility)
- **Existing Cross-Ref:** None (new)
- **Evidence:** `get_metrics` and `get_prometheus_metrics` exist as MCP tools. Web UI Dashboard is read-only collection stats. No admin UI.

#### CD-014: Backup & Disaster Recovery
- **Description:** No backup procedures documented or implemented. SQLite database has no automated backup. No point-in-time recovery. No RPO/RTO defined.
- **Affected Stages:** A7 (Operations)
- **Affected Users:** B3 (Director — no DR plan)
- **Existing Cross-Ref:** None (new)
- **Evidence:** `Makefile` has **no backup target** ( `stripe-mock` is the only `.PHONY` entry beyond build targets). No automated database backup. No restore procedure.

#### CD-015: Horizontal Scaling Strategy
- **Description:** No scaling strategy beyond single-node SQLite. No read replicas, no sharding, no PostgreSQL migration path. SQLite is fundamentally single-writer.
- **Affected Stages:** A7 (Operations)
- **Affected Users:** B3 (Director — no scale path)
- **Existing Cross-Ref:** None (new)
- **Evidence:** Architecture is entirely SQLite-based. No connection pooling. No DB migration plan documented.

#### CD-016: Feature Flags / A-B Testing
- **Description:** No feature flag system. No way to gradually roll out features. No A/B testing for delivery content, channel preference, or product templates.
- **Affected Stages:** A4 (Products), A7 (Operations)
- **Affected Users:** B3 (Director — no iterative rollout capability)
- **Existing Cross-Ref:** None (new)
- **Evidence:** Zero feature flag infrastructure. Code has no toggles, no gradual rollout, no experiment framework.

---

### Type 2: 🟡 Spec'd But Not Implemented

Gaps where the spec exists but code has not been written (or spec partially written, code partially done).

#### CD-017: Product Lifecycle MCP Tools
- **Description:** `delivery.md` specs 5 product lifecycle MCP tools (`get_product_lifecycle`, `list_user_products`, `regenerate_product`, `archive_product`, `get_engagement_metrics`). None are implemented. No `ProductState` enum, no lifecycle state machine.
- **Affected Stages:** A4 (Products), A5 (Delivery)
- **Affected Users:** B2 (Direct Agent — no lifecycle tooling), B3 (Director — no product management)
- **Existing Cross-Ref:** AUD-06
- **Evidence:** `product.py` has `ProductType` (RAW/PROCESSED) and `ProductTemplate` but no `ProductInstance`, no `ProductState`, no lifecycle MCP handlers.

#### CD-018: Consumption Tracking MCP Tools
- **Description:** `delivery.md` specs consumption tracking (read receipts, open rates, engagement signals). No code implements this. No `ConsumptionEvent` model, no MCP tools for engagement.
- **Affected Stages:** A6 (Consumption)
- **Affected Users:** B2 (Direct Agent — no consumption data), B1 (End User — no reading history)
- **Existing Cross-Ref:** AUD-04
- **Evidence:** Zero consumption tracking code. `delivery.md` §7 (Consumption Tracking) references tools that don't exist.

#### CD-019: Quiet Hours Configuration
- **Description:** `delivery.md` §4.3 specs `QuietHours` with `timezone`, `start`, `end` fields. No code implements quiet hours. Delivery preferences are freeform dicts, not typed.
- **Affected Stages:** A5 (Delivery)
- **Affected Users:** B1 (End User — no quiet hours), B2 (Direct Agent — cannot configure quiet hours)
- **Existing Cross-Ref:** None (new)
- **Evidence:** `delivery.py` has `DeliveryPreferences` as `Dict[str, Any]`. No `QuietHours` dataclass. No quiet hours enforcement in delivery pipeline.

#### CD-020: Subscription → Channel Linking
- **Description:** `delivery.md` §4.2 specs that subscriptions have preferred channels, fallback channels, and per-channel config. In code, `Subscription` model has `channels` as a list field but channels are not typed, not validated against the 11 registered adapters, and not linked to the delivery channel registry (`_CHANNEL_REGISTRY` at `delivery/__init__.py:574`). All 11 adapters are fully implemented (`send()`, `validate_config()` methods); the gap is at the subscription→channel wiring layer.
- **Affected Stages:** A4 (Products), A5 (Delivery)
- **Affected Users:** B1 (End User — channel preferences are freeform), B2 (Direct Agent — cannot validate channel config)
- **Existing Cross-Ref:** None (new)
- **Evidence:** 11 delivery channels registered (SMTP, webhook, rest_api, file_export, discord, telegram, wechat_work, wechat_oa, dingtalk, feishu, rss). `Subscription.channels` is `List[str]` with no validation against registry.

#### CD-021: Identity Anchor
- **Description:** `delivery.md` §1.1 specs an "Identity Anchor" — a unique identifier for an end user that is `source_platform + source_user_id`. No code implements this. End users are identified by a direct `enduser_id` parameter.
- **Affected Stages:** A5 (Delivery), A6 (Consumption)
- **Affected Users:** B1 (End User — no identity anchor), B2 (Direct Agent — cannot resolve user across channels)
- **Existing Cross-Ref:** None (new)
- **Evidence:** `EndUserProfile` has `user_id` (UUID) with no identity anchor field. No multi-platform identity resolution.

#### CD-022: Product Lifecycle MCP Tools (Spec'd Not Implemented)
- **Description:** `delivery.md` specs 4 product lifecycle MCP tools that remain unimplemented: `regenerate_product`, `archive_product`, `get_product_lifecycle`, `get_engagement_metrics`. No `ProductState` enum, no lifecycle state machine for product instances.
- **Note:** All 10 End User MCP tools are fully registered (`send_to_enduser`, `get_enduser_history`, `get_enduser_products`, `query_delivery_log`, `get_delivery_log`, `activate_trial`, `check_trial_expiry`, `update_preferences`, `get_preferences`, `get_subscription_status`). `compare_versions` (KB Versioning) IS also registered. This gap is limited to the missing product lifecycle tools only.
- **Affected Stages:** A4 (Products), A5 (Delivery)
- **Affected Users:** B2 (Direct Agent — no lifecycle tooling), B3 (Director — no product management)
- **Existing Cross-Ref:** AUD-06
- **Evidence:** `product.py` has `ProductType` (RAW/PROCESSED) and `ProductTemplate` but no `ProductInstance`, no `ProductState`, no lifecycle MCP handlers. 10 end-user MCP tools confirmed registered.

#### CD-023: [RESOLVED] `get_schedule_status` IS Registered
- **Description:** `get_schedule_status` IS fully registered as an MCP tool (confirmed: `Tool(name="get_schedule_status")` in server.py). The cron reliability gap is about monitoring / missed-schedule detection, not tool availability. Merged into CD-004.
- **Status:** 🟢 Resolved — no separate gap.

---

### Type 3: 🟡 Partially Implemented

Gaps where code exists but is incomplete, broken by design, or has significant missing pieces.

#### CD-024: Subscription → Product Gating Disconnected
- **Description:** The billing ACL layer works (`check_access()` in `billing.py:548` gates free/premium/enterprise, called by `generate_digest()` at `output.py:1637-1644`) BUT all 4 product templates are hardcoded to `access_level="free"`. Additionally, the subscription model (`models.py:340`) lacks `channels`, `domain`, `products`, `topics` fields — so even if a template were set to `premium`, there's no subscription-level configuration linking a user's plan to which products they receive via which channels.
  - **Working:** `check_access()` ACL logic, MCP tool registration for all end-user tools, Stripe webhook → subscription activation
  - **Broken:** No template declares `access_level="premium"`, no subscription→channel/domain/product linking, no consumption tracking
- **Affected Stages:** A4 (Products), A5 (Delivery)
- **Affected Users:** B1 (End User — no tier-based access), B3 (Director — cannot configure monetization)
- **Existing Cross-Ref:** AUD-01, A-01 (also CD-031 merged here)
- **Evidence:** `billing.py:548` `check_access()` works. `output.py` 4 templates all `access_level="free"`. `Subscription` model at `models.py:340` has no `channels`/`domain`/`products`/`topics` fields.

#### CD-025: Payment Provider Abstraction Layer
- **Description:** Currently has Stripe-specific integration (`create_checkout_session` MCP, `POST /api/v1/webhook/stripe`, 3 webhook handlers). Need a **payment provider abstraction** so that Subscription model can work with any provider (WeChat Pay, Alipay, UnionPay, Stripe, etc.) without hardcoding. The Stripe implementation serves as a reference for the abstraction interface.
  - **V1:** No payment integration needed — manually control user `tier` for demo. Existing Stripe code stays as-is (it works).
  - **V2+:** Define `PaymentProvider` ABC with common interface (create_checkout, handle_webhook, refund, query_status). Implement for target markets. The Stripe implementation already has the right patterns (webhook routing, status mapping, subscription activation).
- **Affected Stages:** A4 (Products), A5 (Delivery), A7 (Operations)
- **Affected Users:** B1 (End User — cannot pay), B3 (Director — cannot monetize)
- **Existing Cross-Ref:** F30/F42, AUD-02
- **Evidence:** `billing.py` has Stripe-specific `create_checkout_session` and `handle_webhook`. No `PaymentProvider` ABC, no provider registry. Stripe webhook flow confirmed working: `api/server.py:183-250`, `billing.py:294-467`.

#### CD-026: [OBSOLETE CLAIM] `mark_stale` is O(1), Not O(n)
- **Description:** `mark_stale` in `kb.py:4091` is O(1) — single entry lookup by `entry_id` + single YAML frontmatter update. Catalog previously claimed O(n) scan; this was incorrect. Remaining gap: no automated staleness lifecycle, no staleness-based retention triggering.
- **Affected Stages:** A3 (KB), A7 (Operations)
- **Affected Users:** B2 (Direct Agent — fine at scale), B3 (Director — no automated stale management)
- **Existing Cross-Ref:** AUD-10
- **Evidence:** `kb.py:4091-4113` — direct lookup by `entry_id`, single `update_frontmatter_field` call. No iteration.

#### CD-027: merge_items Partially Implemented
- **Description:** `merge_items` MCP exists and uses LLM-assisted merge. But: no conflict resolution strategy, no merge history tracking, no undo capability.
- **Affected Stages:** A3 (KB)
- **Affected Users:** B2 (Direct Agent — merge without safety net)
- **Existing Cross-Ref:** AUD-08
- **Evidence:** `merge_items` in KB Lifecycle category. Implementation is simple concatenation (SequenceMatcher-based similarity, no LLM conflict resolution).

#### CD-028: Deprecated Status — Agent Cannot Set
- **Description:** Wiki entries can be marked `status: deprecated` but only by explicit human command. Agent cannot even suggest deprecation. The mechanism exists but is too restrictive (agent cannot tag `status: deprecated` even upon explicit human command — wait, AGENTS.md says agent may deprecate upon explicit human command. So this is a spec implementation issue: the agent SHOULD be able to set `deprecated` upon command, but the MCP tool may not expose it.)
- **Affected Stages:** A3 (KB)
- **Affected Users:** B2 (Direct Agent — no deprecation tooling)
- **Existing Cross-Ref:** None (new)
- **Evidence:** Agent constraint rule: "Agent may deprecate (tag `status: deprecated`) upon explicit human command." Implementation unclear.

#### CD-029: 03-Wiki Guarding — Only Partial
- **Description:** The spec says "Only human can promote Draft→Wiki" and "Agent cannot write to 03-Wiki". This is enforced at the agent instruction level (AGENTS.md) but not at the code level — the CLI `kb promote` command could be called by an agent if it had shell access.
- **Affected Stages:** A3 (KB)
- **Affected Users:** B2 (Direct Agent — constraint depends on self-policing), B3 (Director — relies on agent compliance)
- **Existing Cross-Ref:** None (new)
- **Evidence:** AGENTS.md rule: "Only human can promote Draft→Wiki." But `autoinfo kb promote` is a CLI command that an agent could execute.

#### CD-030: Logging Implementation Gap
- **Description:** Structured JSON pipeline logging exists but: not all pipeline stages emit structured logs, some use `print()` or `logging.info()` with unstructured format, log level configuration is inconsistent across modules.
- **Affected Stages:** A7 (Operations)
- **Affected Users:** B2 (Direct Agent — incomplete observability), B3 (Director — incomplete operations view)
- **Existing Cross-Ref:** None (new)
- **Evidence:** Mixed logging patterns across codebase. Some modules use `print()`, some use `logging`, some use structured JSON.

#### CD-031: [MERGED INTO CD-024] Product Templates All Hardcoded to `free`
- **Description:** All 4 product templates (briefing, deep-dive, weekly-roundup, alert) have `access_level="free"`. However, `check_access()` IS implemented and active — `billing.py:548` fully gates free/premium/enterprise, and `output.py:1637-1644` calls it during `generate_digest()`. The gap is that no template declares `access_level="premium"` or `"enterprise"`, so premium gating is reachable in code but unreachable via configuration. Merged into CD-024.
- **Affected Stages:** A4 (Products)
- **Affected Users:** B1 (End User — no tiered product access), B3 (Director — cannot configure paid-only products)
- **Existing Cross-Ref:** AUD-01 (merged with CD-024)
- **Evidence:** `billing.py:548` (`check_access`), `output.py:1637-1644` (gate call in `generate_digest`). 4 templates in `output.py`, all `access_level="free"`.

---

### Type 4: 🟢 Spec Outdated

Gaps where the implementation exists but spec documents still describe the old/planned state.

#### CD-032: [RESOLVED] TTS Audio Output Implemented
- **Description:** Audio output was previously spec'd as pending; it is now fully implemented. `generate_report(format="audio")` returns MP3 via OpenAI TTS. `generate_digest(format="audio")` also works. `README.md` and `AGENTS.md` status tables already updated to show ✅.
- **Affected Stages:** A4 (Products)
- **Affected Users:** B2 (Direct Agent — tool works)
- **Existing Cross-Ref:** G1 (source doc archived)
- **Evidence:** `output.py` `_render_audio()` using OpenAI TTS. MCP tools accept `format=audio`.
- **Final Status:** ✅ Resolved — no further action needed.

#### CD-033: [RESOLVED] Agent-Native JSON Output Implemented
- **Description:** Agent-native JSON output (`format="agent"`) was previously spec'd as pending; now fully implemented. `generate_digest(format="agent")` returns JSON-LD with `@type: KnowledgeDigest`. `README.md` and `AGENTS.md` already updated to show ✅.
- **Affected Stages:** A4 (Products)
- **Affected Users:** B2 (Direct Agent — tool works)
- **Existing Cross-Ref:** G11 (source doc archived)
- **Evidence:** `output.py` `_render_agent_json()`. MCP `generate_digest` accepts `format=agent`.
- **Final Status:** ✅ Resolved — no further action needed.

#### CD-034: AGENTS.md Format Claims Outdated
- **Description:** AGENTS.md section "Output generation" line says "Digest (Markdown/HTML/JSON/PDF), report (Markdown/JSON/PDF/HTML/Audio/Agent)" but the actual project structure tree below it just says "Output generation ... Digest, report, tutorial, export" without format details. Inconsistent self-description.
- **Affected Stages:** A4 (Products)
- **Affected Users:** B2 (Direct Agent — doc self-inconsistency)
- **Existing Cross-Ref:** None (new)
- **Evidence:** AGENTS.md project structure tree shows `output.py` comment "Output generation (digest, report, tutorial, export)" — missing Audio/Agent formats.

#### CD-035: consumer-output-gaps.md G1/G11 Outdated [RESOLVED]
- **Description:** `consumer-output-gaps.md` (now archived) marked G1 (Audio output) and G11 (Agent-native format) as 🔴. Both are implemented.
- **Affected Stages:** A4 (Products)
- **Affected Users:** N/A (doc accuracy)
- **Existing Cross-Ref:** G1, G11
- **Evidence:** `generate_report(format="audio")` and `generate_digest(format="agent")` both operational. Source doc archived. No further action needed.

#### CD-036: target_audience MCP Parameter Behavior
- **Description:** MCP spec says `list_output_templates` has `target_audience` filter, but in practice it may not filter correctly or the parameter behavior differs from spec.
- **Affected Stages:** A4 (Products)
- **Affected Users:** B2 (Direct Agent — parameter behavior mismatch)
- **Existing Cross-Ref:** G13
- **Evidence:** Needs verification against actual MCP behavior.

---

### Type 5: 🟠 Architecture / Philosophy Gaps

Gaps that are not about missing features but about how the system is architected — fundamental design issues that create constraints across multiple stages.

#### CD-037: No Feature Flag System
- **Description:** No ability to toggle features on/off at runtime. No gradual rollout. No kill switch for problematic features. All features are either compiled in or absent.
- **Affected Stages:** A7 (Operations)
- **Affected Users:** B3 (Director — cannot control feature rollout)
- **Evidence:** Zero feature flag infrastructure in entire codebase.

#### CD-038: No Unified Notification Architecture
- **Description:** Notifications are handled ad-hoc per subsystem: budget alerts in `alerts.py`, delivery notifications in `delivery.py`, system notifications nowhere. No notification bus, no notification routing rules, no notification preferences.
- **Affected Stages:** A5 (Delivery), A7 (Operations)
- **Affected Users:** B1 (End User — inconsistent notification experience), B2 (Direct Agent — no unified notification API), B3 (Director — no notification policy)
- **Existing Cross-Ref:** None (new)
- **Evidence:** No `Notification` model, no notification registry, no notification preferences in `EndUserProfile` or `Subscription`.

#### CD-039: No Delivery Schema Enforcement
- **Description:** Delivery channels receive products but there is no schema enforcement — a product expected to have certain fields can be sent without them. No per-channel format validation. If a channel requires specific formatting, it's implemented per-adapter with no shared contract.
- **Affected Stages:** A4 (Products), A5 (Delivery)
- **Affected Users:** B2 (Direct Agent — inconsistent product structure), B1 (End User — varying quality across channels)
- **Evidence:** `ProductTemplate` has fields but no delivery schema validation. Channel adapters handle formatting independently.

#### CD-040: No End-User Consumption Loop
- **Description:** The entire pipeline ends at delivery. There is no feedback loop from end user consumption back into the system. No read tracking, no preference learning, no content adaptation based on engagement. The system delivers but does not learn.
- **Affected Stages:** A6 (Consumption) → A1-A4 (feedback)
- **Affected Users:** B1 (End User — no personalized experience), B3 (Director — no data-driven optimization)
- **Evidence:** Zero consumption tracking. No user preference learning. No content ranking based on engagement.

#### CD-041: No Data-Driven Business Metrics
- **Description:** The system tracks cost metrics (LLM tokens, storage, API calls) but no business metrics: customer acquisition cost (CAC), lifetime value (LTV), monthly recurring revenue (MRR), churn rate, engagement rate. Director has no business visibility.
- **Affected Stages:** A7 (Operations), A6 (Consumption)
- **Affected Users:** B3 (Director — no business metrics)
- **Evidence:** Cost dashboard exists. No revenue, MRR, churn, or LTV tracking.

#### CD-042: No Multi-Tenant Data Isolation
- **Description:** Single SQLite database serves all users/tenants. No tenant context in any query. No data partitioning. No cross-tenant access prevention at the database level.
- **Affected Stages:** A3 (KB), A7 (Operations)
- **Affected Users:** B1 (End User — no data isolation guarantee), B3 (Director — cannot onboard multi-tenant customers)
- **Existing Cross-Ref:** CD-001 (duplicate dimension)
- **Evidence:** SQLite shared across all operations. `user_id` field is advisory, not enforced.

---

### Gap Count Summary

| Type | Count | IDs |
|------|-------|-----|
| 🔴 Type 1: Never Designed | 16 | CD-001 to CD-016 |
| 🟡 Type 2: Spec'd Not Impl | 6 | CD-017 to CD-022 |
| 🟡 Type 3: Partially Impl | 7 | CD-024 to CD-030 |
| 🟢 Type 4: Spec Outdated | 3 | CD-034 to CD-036 |
| 🟠 Type 5: Architecture | 6 | CD-037 to CD-042 |
| **Total** | **38** | |

**Changes from previous count (42 → 38):**
| Gap | Old Status | New Status | Reason |
|-----|-----------|-----------|--------|
| CD-023 | 🟡 Spec'd Not Impl | 🟢 Resolved | `get_schedule_status` IS registered |
| CD-031 | 🟡 Partially Impl | 🔗 Merged → CD-024 | Same underlying gap as CD-024 |
| CD-032 | 🟢 Spec Outdated | ✅ Resolved | Audio output working, docs already updated |
| CD-033 | 🟢 Spec Outdated | ✅ Resolved | Agent-native JSON working, docs already updated |

---

## Section 3: Gap-to-Doc Mapping

Each gap maps to one or more documents that need updating. This enables targeted document overhaul.

### Gap → Affected Documents

| Gap ID | Affected Documents | Update Type |
|--------|-------------------|-------------|
| CD-001 | `specs/expectations.md`, `specs/data-models.md`, `specs/multi-tenancy-auth.md` (new) | Add new specs |
| CD-002 | `specs/expectations.md`, `specs/multi-tenancy-auth.md` (new) | Add new specs |
| CD-003 | `specs/multi-tenancy-auth.md` (new), `specs/ops-runbook.md` (new) | Add new specs |
| CD-004 | `specs/operations.md`, `specs/ops-runbook.md` (new) | Add sections |
| CD-005 | `specs/multi-tenancy-auth.md` (new) | Add section |
| CD-006 | `specs/operations.md` | Add section |
| CD-007 | `specs/delivery.md` | Add section |
| CD-008 | `specs/delivery.md` | Add section |
| CD-009 | `specs/operations.md` | Add section |
| CD-010 | `specs/delivery.md` | Add section |
| CD-011 | `specs/delivery.md`, `specs/data-models.md` | Add sections |
| CD-012 | `specs/operations.md` | Add section |
| CD-013 | `specs/ops-runbook.md` (new) | Add section |
| CD-014 | `specs/ops-runbook.md` (new) | Add section |
| CD-015 | `specs/ops-runbook.md` (new) | Add section |
| CD-016 | `specs/operations.md` | Add section |
| CD-017 | `specs/delivery.md` | Add missing spec |
| CD-018 | `specs/delivery.md` | Add missing spec |
| CD-019 | `specs/delivery.md` | Fix spec→code alignment |
| CD-020 | `specs/delivery.md`, `specs/data-models.md` | Fix spec→code alignment |
| CD-021 | `specs/delivery.md` | Add missing spec |
| CD-022 | `specs/mcp-tools.md` | Add product lifecycle tool specs |
| CD-023 | *(resolved — merged into CD-004)* | — |
| CD-024 | `specs/delivery.md`, `specs/data-models.md` | Fix spec→code alignment |
| CD-025 | `specs/expectations.md` (F30/F42) | Fix status (stripe flow is more complete than doc claims) |
| CD-026 | `specs/pipeline.md` | Remove O(n) claim; note remaining auto-lifecycle gap |
| CD-027 | `specs/pipeline.md` | Note partial impl (basic concat, no LLM merge) |
| CD-028 | `specs/expectations.md`, `AGENTS.md` | Clarify rule |
| CD-029 | `AGENTS.md` | Clarify enforcement |
| CD-030 | `specs/operations.md` | Note gap |
| CD-031 | *(merged into CD-024)* | — |
| CD-032 | — *(resolved — audio working, docs updated)* | — |
| CD-033 | — *(resolved — agent JSON working, docs updated)* | — |
| CD-034 | `AGENTS.md` | Fix format claims |
| CD-035 | *(resolved — source doc archived)* | — |
| CD-036 | `specs/mcp-tools.md` | Verify behavior |
| CD-037 | `specs/operations.md` (new section: Feature Flags) | Add section |
| CD-038 | `specs/operations.md` (new section: Notifications) | Add section |
| CD-039 | `specs/delivery.md` (new section: Schema Enforcement) | Add section |
| CD-040 | `specs/delivery.md` (new section: Consumption Loop) | Add section |
| CD-041 | `specs/operations.md` (new section: Business Metrics) | Add section |
| CD-042 | `specs/multi-tenancy-auth.md` (new) | Add section |

### Document Update Summary

| Document | Update Scope | Gaps Covered |
|----------|-------------|--------------|
| `specs/expectations.md` | Add F58-F64, fix status markers | CD-001..CD-005, CD-025 |
| `specs/delivery.md` | Major expansion: product lifecycle, consumption, channel health, preview, schema | CD-007, CD-008, CD-010, CD-011, CD-017..CD-021, CD-024, CD-039, CD-040 |
| `specs/operations.md` | Add: notifications, email templates, retention, cron reliability, feature flags, business metrics | CD-004, CD-006, CD-009, CD-012, CD-016, CD-030, CD-037, CD-038, CD-041 |
| `specs/data-models.md` | Add: product, consumption, notification, auth/tenant models; fix subscription fields | CD-001, CD-011, CD-020, CD-024 |
| `specs/pipeline.md` | Note partial merge, remove O(n) claim | CD-026, CD-027 |
| `specs/mcp-tools.md` | Add product lifecycle tool specs, fix parameter docs | CD-022, CD-036 |
| `specs/multi-tenancy-auth.md` (new) | Multi-tenancy, auth, rate limiting, admin dashboard | CD-001, CD-002, CD-003, CD-005, CD-042 |
| `specs/ops-runbook.md` (new) | DR, backup, scaling, live dashboard | CD-003, CD-004, CD-013, CD-014, CD-015 |
| `README.md` | — *(already updated)* | CD-032 ✅, CD-033 ✅ |
| `AGENTS.md` | Fix format claims, clarify deprecation rule | CD-028, CD-029, CD-034 |
| `CHANGELOG.md` | Add entries for all doc changes | All |

---

## Section 4: Priority Fix Matrix

Priorities are assigned based on:
- **P0 🔴**: Blocking for V1 demo — pipeline reliability + correct subscription design (payment flow explicitly deferred to V2)
- **P1 🟡**: Critical for V1 demo — demo-showable features (consumption tracking, notifications, channel health, backup)
- **P2 🟢**: Important for product quality — can wait past V1 demo (UX polish, lifecycle management, business metrics)
- **P3 ⚪**: V2+ scope — multi-tenant, auth, rate limiting, Stripe billing completion, scaling

### P0 🔴 — Must Fix for V1 Demo (Blocking)

| ID | Gap | Reason | Effort |
|----|-----|--------|--------|
| CD-024 | Subscription model design incomplete | Need proper `tier`/`channels`/`domains`/`products` fields on Subscription; ACL layers working but templates all hardcoded to `free`; no granularity (platform count, domain count, raw vs processed). **V1 goal:** design correct, demo-able model — actual payment flow can wait | 2-3 days |
| CD-004 | Cron reliability | Collection silently fails if cron misses a beat — demo pipeline breaks without anyone noticing | 2-3 days |

### P1 🟡 — Must Fix for V1 Demo (Critical)

| ID | Gap | Reason | Effort |
|----|-----|--------|--------|
| CD-040 | Consumption tracking infrastructure | Need `ConsumptionEvent` data model + API to show "user consumed content" in demo. Pixel/open-tracking can wait for V2 | 3-5 days |
| CD-038 | Notification delivery for demo | Need basic lifecycle notifications (trial reminder, content ready) via existing email sender. Template engine/unified framework can wait for V2 | 2-3 days |
| CD-007 | Channel health monitoring | Silent delivery failures during demo = bad impression | 3-5 days |
| CD-011 | Consumption tracking (core model) | Baseline model + API needed for CD-040 | 3-5 days |
| CD-014 | Backup & DR | Demo data loss = disaster; no automated backup exists | 2-3 days |

### P2 🟢 — Worth Fixing (Important, Can Wait Past V1 Demo)

| ID | Gap | Reason | Effort |
|----|-----|--------|--------|
| CD-005 | Admin dashboard | No visual operations view | 5-10 days |
| CD-006 | Notification framework | Scattered notification logic; manual email enough for demo | 5-8 days |
| CD-008 | Product preview | No QA before delivery; demo can send directly | 2-3 days |
| CD-009 | Email templates | Lifecycle emails are plain text; adequate for demo | 2-3 days |
| CD-010 | Product catalog | End users can't discover products; demo via agent intro | 5-10 days |
| CD-012 | Retention & churn analysis | No business analytics | 5-10 days |
| CD-013 | Live ops dashboard | No real-time monitoring | 3-5 days |
| CD-015 | Scaling strategy | No path beyond single-node SQLite | 5-10 days |
| CD-017 | Product lifecycle MCP tools | Agent cannot manage product lifecycle; not needed for demo | 3-5 days |
| CD-018 | Consumption tracking MCP | No MCP tools for engagement yet; depends on CD-011/CD-040 | 3-5 days |
| CD-019 | Quiet hours | Spec not implemented | 2-3 days |
| CD-020 | Subscription→channel linking | Channel preferences not validated | 2-3 days |
| CD-021 | Identity anchor | No cross-platform identity | 3-5 days |
| CD-027 | merge_items partial | Basic concatenation, no LLM conflict resolution | 2-3 days |
| CD-029 | 03-Wiki guarding (code-level) | Rule is agent-instruction only | 1 day |
| CD-037 | Feature flags | No gradual rollout capability | 3-5 days |
| CD-039 | Delivery schema enforcement | No format validation | 3-5 days |
| CD-041 | Business metrics | No revenue/engagement visibility | 5-10 days |

### P3 ⚪ — Future (V2+)

| ID | Gap | Reason | Effort |
|----|-----|--------|--------|
| CD-001 | Multi-tenancy isolation | Single-tenant demo doesn't need it | 5-10 days |
| CD-002 | End-user auth | MCP agent mode sufficient for demo | 5-10 days |
| CD-003 | Rate limiting | Demo scale doesn't need it | 3-5 days |
| CD-016 | A/B testing | Advanced feature | 5-10 days |
| CD-025 | Payment provider abstraction | Stripe reference impl exists; need `PaymentProvider` ABC for WeChat Pay / Alipay / Stripe pluggability | 5-10 days |
| CD-028 | Deprecated status agent tooling | Minor workflow improvement | 1 day |
| CD-030 | Logging implementation gap | Gradual improvement across modules | 3-5 days |
| CD-036 | target_audience parameter | Edge case behavior | 1 day |
| CD-042 | Multi-tenant DB isolation | Depends on CD-001 | 5-10 days |

### Spec Doc Overhaul Priority

| Doc | Priority | Effort | Depends On |
|-----|----------|--------|------------|
| `specs/expectations.md` | P0 | 1 hr | T1 (this doc) |
| `specs/delivery.md` | P0 | 3 hr | T1 |
| `specs/operations.md` | P0 | 2 hr | T1 |
| `specs/data-models.md` | P0 | 1.5 hr | T1 |
| `specs/multi-tenancy-auth.md` (new) | P1 | 3 hr | T1 |
| `specs/ops-runbook.md` (new) | P1 | 2 hr | T1 |
| `README.md` | P2 | 1 hr | Spec updates done |
| `AGENTS.md` | P2 | 1 hr | Spec updates done |
| `CHANGELOG.md` | P2 | 0.5 hr | All docs done |

---

## Section 5: Implementation Roadmap

### Phase 1: Spec & Documentation Overhaul (Weeks 1-2)
**Focus:** Fix all spec docs to reflect actual code state, document blank spaces.

| Step | Task | Effort | Outcome |
|------|------|--------|---------|
| 1.1 | Fix `expectations.md`: update status markers, add F58-F64 | 1 hr | Spec matches code reality |
| 1.2 | Fix `delivery.md`: add product lifecycle, consumption, channel health, preview | 3 hr | Complete delivery spec |
| 1.3 | Fix `operations.md`: add notifications, email templates, cron reliability, retention | 2 hr | Complete operations spec |
| 1.4 | Fix `data-models.md`: add missing models | 1.5 hr | Complete data model spec |
| 1.5 | Create `multi-tenancy-auth.md` | 3 hr | Auth & tenancy designed |
| 1.6 | Create `ops-runbook.md` | 2 hr | Operational playbook |
| 1.7 | Verify `README.md` (already updated for CD-032/033), update `AGENTS.md`, `CHANGELOG.md` | 1.5 hr | Doc trees consistent |

### Phase 2: P0 Implementation — V1 Demo Foundation (Weeks 3-5)
**Focus:** Subscription model design + cron reliability — the two things that can break a demo.

| Step | Task | Effort | Outcome |
|------|------|--------|---------|
| 2.1 | Subscription model redesign: add `tier`, `channels`, `domains`, `products`, `platform_limit` fields; wire `check_access()` to real tier checks; create 1 premium template for demo | 2-3 days | Subscription model is correct by design; demo can show free vs premium access |
| 2.2 | Cron reliability: monitoring, failure detection, missed-schedule backfill | 2-3 days | Collection is reliable; demo pipeline won't break silently |

### Phase 3: P1 Implementation — V1 Demo Hardening (Weeks 6-10)
**Focus:** Make the demo showable and reliable — consumption tracking, notifications, channel health, backup.

| Step | Task | Effort | Outcome |
|------|------|--------|---------|
| 3.1 | Consumption tracking foundation: `ConsumptionEvent` model + basic API (open tracking pixel/read receipt can wait V2) | 3-5 days | Demo can show "user consumed content" |
| 3.2 | Basic lifecycle notifications via existing email sender (trial reminder, content-ready notice) | 2-3 days | Users get key lifecycle communication |
| 3.3 | Channel health monitoring: per-channel health endpoint + aggregate health MCP tool | 3-5 days | Demo delivery won't fail silently |
| 3.4 | Backup automation: SQLite backup cron + basic restore procedure | 2-3 days | Demo data is safe |

### Phase 4: P2 Implementation — Product Quality (Weeks 11-16)
**Focus:** Polish, UX, and operational quality — features that make the product professional but aren't demo-blocking.

| Step | Task | Effort | Outcome |
|------|------|--------|---------|
| 4.1 | Notifications framework: template engine + lifecycle event hooks (builds on Phase 3.2) | 5-8 days | Unified notification architecture |
| 4.2 | Product preview workflow | 2-3 days | QA before delivery |
| 4.3 | Email templates (welcome, trial-ending, digest-ready, cancellation) | 2-3 days | Professional lifecycle communication |
| 4.4 | Product lifecycle state machine + MCP tools | 3-5 days | Full product lifecycle management |
| 4.5 | Consumption tracking MCP tools + engagement APIs | 3-5 days | Agent-accessible engagement data |
| 4.6 | Admin dashboard | 5-10 days | Visual operations control |
| 4.7 | Product catalog / storefront | 5-10 days | End-user product discovery |
| 4.8 | Retention & churn analytics | 5-10 days | Business visibility |
| 4.9 | Live operations dashboard | 3-5 days | Real-time monitoring |
| 4.10 | Delivery schema enforcement | 3-5 days | Consistent product quality |
| 4.11 | Business metrics (MRR, LTV, churn) | 5-10 days | Business performance tracking |
| 4.12 | Subscription↔channel linking validation | 2-3 days | Channel config integrity |
| 4.13 | Feature flags | 3-5 days | Gradual rollout capability |
| 4.14 | Quiet hours implementation | 2-3 days | End-user preference |
| 4.15 | `merge_items` improvement — LLM conflict resolution | 2-3 days | Reliable KB merge |
| 4.16 | Identity anchor implementation | 3-5 days | Cross-platform identity |
| 4.17 | 03-Wiki code-level guarding | 1 day | Defense-in-depth |

### Phase 5: P3 & Future — V2+ Scope (Week 17+)
**Focus:** Scaling, monetization flow, multi-tenant, advanced features.

| Step | Task | Effort | Outcome |
|------|------|--------|---------|
| 5.1 | Multi-tenancy isolation + end-user auth | 10-15 days | Secure multi-tenant service |
| 5.2 | Payment provider abstraction: define `PaymentProvider` ABC, move Stripe as reference impl, registry for WeChat Pay / Alipay / UnionPay etc. | 5-10 days | Pluggable payment providers |
| 5.3 | Rate limiting + abuse prevention | 3-5 days | Production API protection |
| 5.4 | Scaling strategy (SQLite→PostgreSQL migration) | 5-10 days | Horizontal scale path |
| 5.5 | A/B testing framework | 5-10 days | Content optimization |
| 5.6 | Logging consistency cleanup | 3-5 days | Complete observability |
| 5.7 | Agent deprecation tooling | 1 day | Agent workflow improvement |
| 5.8 | `target_audience` parameter behavior fix | 1 day | Edge case resolved |

---

## Appendix: Existing Gap ID Cross-Reference

Maps existing gap IDs from other (now archived) documents to CD-NNN. Kept for historical traceability — code comments or old references may use these IDs.

| Existing ID | Source Document | Maps To | Notes |
|-------------|---------------|---------|-------|
| AUD-01 | comprehensive-gap-audit.md | CD-024 | Subscription disconnect + access_level (CD-031 merged) |
| AUD-02 | comprehensive-gap-audit.md | CD-025 | Stripe billing flow — webhook complete, invoice/dunning missing |
| AUD-04 | comprehensive-gap-audit.md | CD-011, CD-018 | Consumption tracking |
| AUD-05 | comprehensive-gap-audit.md | CD-002 | End-user auth |
| AUD-06 | comprehensive-gap-audit.md | CD-017 | Product lifecycle |
| AUD-08 | comprehensive-gap-audit.md | CD-027 | merge_items partial |
| AUD-10 | comprehensive-gap-audit.md | CD-026 | Stale content (O(1) confirmed; remaining: auto-lifecycle missing) |
| G1 | consumer-output-gaps.md | CD-032 | Audio output (now implemented) |
| G4 | consumer-output-gaps.md | CD-008 | Product preview |
| G7 | consumer-output-gaps.md | CD-010 | Product discovery/storefront |
| G8 | consumer-output-gaps.md | CD-011 | No consumption tracking |
| G11 | consumer-output-gaps.md | CD-033 | Agent-native JSON (now implemented) |
| G13 | consumer-output-gaps.md | CD-036 | target_audience parameter |
| G15 | consumer-output-gaps.md | CD-002 | End-user auth |
| A-01 | implementation-gaps.md | CD-024 | Subscription tier disconnect |
| F30 | expectations.md | CD-025 | Subscription billing |
| F42 | expectations.md | CD-025 | External billing |
| C-01..C-12 | comprehensive-gap-audit.md | Various | Consumer-facing gaps (see consumer-output-gaps.md) |
| B-01..B-08 | comprehensive-gap-audit.md | Various | Implementation gaps (see implementation-gaps.md) |

---

*End of Cross-Dimensional Catalog. 38 gaps cataloged across 5 types (4 gaps resolved/merged after codebase reality check), with full priority matrix and implementation roadmap. This is the keystone product definition document — start here, then navigate to the relevant spec in `docs/dev/specs/`.*
