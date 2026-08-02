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
>
> **Last updated:** 2026-08-02 (V1 completion audit — see "2026-08-02 V1 更新" section near end of document)

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
| **A1 Collection** | 🟢 `list_available_platforms` | 🟢 MCP tools auto-discovered | 🟢 `add_source`, `add_topic`, `add_schedule` | 🟢 `collect_sources`, `process_collection`, `batch_run` | 🟢 Cron health with heartbeat, missed-detection, alerts | 🟢 Source config is mutable |

| Lifecycle → | B3.1 Define | B3.2 Configure | B3.3 Monitor | B3.4 Iterate | B3.5 Scale |
|-------------|:---:|:---:|:---:|:---:|:---:|
| **A1 Collection** | 🟢 `add_domain`, `add_source` | 🟢 `activate_domain`, source health | 🟡 No collection pipeline dashboard | 🟢 Sources are editable | 🟡 No multi-source orchestration, no rate limiting |

#### A2 Extraction

| Lifecycle → | B1.1 Discover | B1.2 Trial | B1.3 Subscribe | B1.4 Consume | B1.5 Renew | B1.6 Churn |
|-------------|:---:|:---:|:---:|:---:|:---:|:---:|
| **A2 Extraction** | ⚪ | 🟢 Trial user gets processed content | ⚪ | 🟢 LLM extraction works | ⚪ | ⚪ |

| Lifecycle → | B2.1 Discover | B2.2 Connect | B2.3 Configure | B2.4 Operate | B2.5 Monitor | B2.6 Update |
|-------------|:---:|:---:|:---:|:---:|:---:|:---:|
| **A2 Extraction** | 🟢 `get_domain_schema`, `list_available_models` | 🟢 MCP tools | 🟢 Per-task LLM config, custom extraction fields | 🟢 `process_collection`, quality gates G0-G5 | 🟢 Async job_id polling with progress tracking | 🟢 Config via MCP tools |

| Lifecycle → | B3.1 Define | B3.2 Configure | B3.3 Monitor | B3.4 Iterate | B3.5 Scale |
|-------------|:---:|:---:|:---:|:---:|:---:|
| **A2 Extraction** | 🟢 Custom extraction field schema | 🟢 Per-domain LLM config | 🟡 No extraction quality dashboard | 🟢 Gates are configurable | 🟡 No batch processing batching |

#### A3 Knowledge Base

| Lifecycle → | B1.1 Discover | B1.2 Trial | B1.3 Subscribe | B1.4 Consume | B1.5 Renew | B1.6 Churn |
|-------------|:---:|:---:|:---:|:---:|:---:|:---:|
| **A3 Knowledge Base** | ⚪ | 🟡 KB is usable but no tenant isolation | ⚪ | 🟢 Search, Q&A, graph | ⚪ | 🟢 GDPR export and deletion MCP tools exist |

| Lifecycle → | B2.1 Discover | B2.2 Connect | B2.3 Configure | B2.4 Operate | B2.5 Monitor | B2.6 Update |
|-------------|:---:|:---:|:---:|:---:|:---:|:---:|
| **A3 Knowledge Base** | 🟢 KB tools listed | 🟢 Full KB tool set | 🟢 `reindex_kb`, `list_kb_tier` | 🟢 `create_kb_draft`, `search_kb`, `query_knowledge_graph` | 🟢 `compare_versions` registered, `merge_items` partially | 🟢 KB is mutable (soft-delete, restore) |

| Lifecycle → | B3.1 Define | B3.2 Configure | B3.3 Monitor | B3.4 Iterate | B3.5 Scale |
|-------------|:---:|:---:|:---:|:---:|:---:|
| **A3 Knowledge Base** | 🟢 Wiki is append-only per spec | 🟢 Promote/reject Draft CLI | 🟡 No KB quality dashboard | 🟢 Items can be flagged, deprecated | 🔴 No multi-tenant KB isolation |

#### A4 Products

| Lifecycle → | B1.1 Discover | B1.2 Trial | B1.3 Subscribe | B1.4 Consume | B1.5 Renew | B1.6 Churn |
|-------------|:---:|:---:|:---:|:---:|:---:|:---:|
| **A4 Products** | 🔴 No product catalog / storefront | 🔴 No trial product preview | 🟢 6 templates with free/premium/enterprise tiers, `check_access` gates delivery | 🟡 Products deliver but lifecycle is not tracked | 🔴 No renewal product regeneration | 🔴 No product archive on churn |

| Lifecycle → | B2.1 Discover | B2.2 Connect | B2.3 Configure | B2.4 Operate | B2.5 Monitor | B2.6 Update |
|-------------|:---:|:---:|:---:|:---:|:---:|:---:|
| **A4 Products** | 🟢 `list_products`, `get_product` MCP exists | 🟢 MCP tools | 🟢 Product templates exist (RAW, PROCESSED) | 🟡 Products are generated but lifecycle state machine is 0% implemented | 🔴 No product engagement metrics | 🟡 Template config is mutable via code |

| Lifecycle → | B3.1 Define | B3.2 Configure | B3.3 Monitor | B3.4 Iterate | B3.5 Scale |
|-------------|:---:|:---:|:---:|:---:|:---:|
| **A4 Products** | 🟢 Product types defined (RAW/PROCESSED) | 🟢 Free/premium/enterprise product templates with `check_access` gating | 🔴 No product delivery dashboard | 🔴 No A/B testing, no template iteration | 🔴 No product catalog scaling strategy |

#### A5 Delivery

| Lifecycle → | B1.1 Discover | B1.2 Trial | B1.3 Subscribe | B1.4 Consume | B1.5 Renew | B1.6 Churn |
|-------------|:---:|:---:|:---:|:---:|:---:|:---:|
| **A5 Delivery** | ⚪ | 🟢 Trial delivery works (same channels) | 🟡 Subscription→channel linking is disconnected | 🟡 Delivery works but no read tracking | 🟡 Renewal delivery continues | 🔴 No cancellation delivery receipt |

| Lifecycle → | B2.1 Discover | B2.2 Connect | B2.3 Configure | B2.4 Operate | B2.5 Monitor | B2.6 Update |
|-------------|:---:|:---:|:---:|:---:|:---:|:---:|
| **A5 Delivery** | 🟢 Delivery tools listed | 🟢 MCP tools | 🟢 `send_to_enduser`, channel config | 🟡 Delivery works, `query_delivery_log` exists | 🟢 `get_channel_health` MCP with 12 channels | 🟢 Config is mutable |

| Lifecycle → | B3.1 Define | B3.2 Configure | B3.3 Monitor | B3.4 Iterate | B3.5 Scale |
|-------------|:---:|:---:|:---:|:---:|:---:|:---:|
| **A5 Delivery** | 🟢 12 delivery channels | 🟢 Channel config via webhook/schedule | 🟡 No unified delivery dashboard | 🟢 Adapters are modular | 🟡 DeliveryLog with SLA tracking, `get_channel_health` checks all 12 channels, no auto-failover |

#### A6 Consumption

| Lifecycle → | B1.1 Discover | B1.2 Trial | B1.3 Subscribe | B1.4 Consume | B1.5 Renew | B1.6 Churn |
|-------------|:---:|:---:|:---:|:---:|:---:|:---:|
| **A6 Consumption** | ⚪ | ⚪ | ⚪ | 🟢 `ConsumptionEvent` + `ConsumptionStore` with auto-record on delivery (delivered/opened/clicked) | 🟡 Events auto-recorded, no renewal-specific analytics | 🔴 No churn analysis |

| Lifecycle → | B2.1 Discover | B2.2 Connect | B2.3 Configure | B2.4 Operate | B2.5 Monitor | B2.6 Update |
|-------------|:---:|:---:|:---:|:---:|:---:|:---:|
| **A6 Consumption** | ⚪ | ⚪ | ⚪ | 🟡 `ConsumptionStore` exists but no dedicated MCP tool for querying | 🔴 No engagement metrics dashboard | ⚪ |

| Lifecycle → | B3.1 Define | B3.2 Configure | B3.3 Monitor | B3.4 Iterate | B3.5 Scale |
|-------------|:---:|:---:|:---:|:---:|:---:|:---:|
| **A6 Consumption** | 🔴 No consumption KPIs defined | ⚪ | 🔴 No consumption dashboard | 🔴 No data-driven iteration loop | 🔴 No consumption-based scaling signals |

#### A7 Operations

| Lifecycle → | B1.1 Discover | B1.2 Trial | B1.3 Subscribe | B1.4 Consume | B1.5 Renew | B1.6 Churn |
|-------------|:---:|:---:|:---:|:---:|:---:|:---:|
| **A7 Operations** | ⚪ | ⚪ | 🟢 Billing/cost operations | ⚪ | ⚪ | 🟢 Soft-delete, retention, GDPR export |

| Lifecycle → | B2.1 Discover | B2.2 Connect | B2.3 Configure | B2.4 Operate | B2.5 Monitor | B2.6 Update |
|-------------|:---:|:---:|:---:|:---:|:---:|:---:|
| **A7 Operations** | 🟢 Diagnostics tools listed | 🟢 `diagnose_system` | 🟢 `set_budget_thresholds`, `set_gate_config` | 🟢 Cost metering, audit log, trace | 🟢 Prometheus metrics at `/metrics`, `get_prometheus_metrics` MCP, cron health heartbeat | 🟢 System is configurable at runtime |

| Lifecycle → | B3.1 Define | B3.2 Configure | B3.3 Monitor | B3.4 Iterate | B3.5 Scale |
|-------------|:---:|:---:|:---:|:---:|:---:|:---:|
| **A7 Operations** | 🟡 No RPO/RTO defined | 🟢 Config via MCP/CLI | 🟡 No live operations dashboard | 🟢 Backup/restore scripts exist (`backup-db.sh`, `restore-db.sh`, `make backup`) | 🔴 No horizontal scaling strategy, SQLite is single-node |

### Matrix Summary Statistics

| Metric | Count |
|--------|-------|
| Total cells | 119 (7×17 lifecycle stages) |
| 🟢 Fully delivered | 66 (55%) |
| 🟡 Partially delivered | 25 (21%) |
| 🔴 Not delivered | 24 (20%) |
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

#### CD-004: [RESOLVED] Cron Reliability & Backup
- **Description:** Cron scheduling exists (`add_schedule`, `run_schedules`). **Heartbeat tracking** (`_heartbeat_path`, `_load_heartbeat`, `_save_heartbeat`), **missed-schedule detection** (`health = "missed"`), and **email alerts for missed schedules** (`_send_missed_alerts`) are all implemented in `cli/cron.py`. `autoinfo cron health` CLI shows per-schedule health (ok/missed/error/unknown). `get_schedule_status` MCP tool is registered.
- **Affected Stages:** A1 (Collection), A7 (Operations)
- **Affected Users:** B2, B3
- **Evidence:** `cli/cron.py:135-751` — heartbeat file at `.autoinfo/cron-heartbeat.json`, `_update_heartbeat()` on each schedule run, `_send_missed_alerts()` for notifications. `get_schedule_status` MCP tool confirmed registered.
- **Status:** 🟢 Resolved — schedule monitoring, missed detection, and alerting all implemented.

#### CD-005: Admin Dashboard
- **Description:** No web-based admin console exists. The only dashboards are: CLI (`autoinfo status`, `autoinfo cost dashboard`) and MCP tools. No visual overview of system health, user activity, collection status, delivery metrics.
- **Affected Stages:** A7 (Operations)
- **Affected Users:** B3 (Director — no operations dashboard)
- **Existing Cross-Ref:** None (new)
- **Evidence:** No admin routes in FastAPI server. Web UI Dashboard (Bootstrap 5) exists but shows only collection stats/KB search — no admin functions.

#### CD-006: Unified Notification Framework
- **Description:** `notifications.py` IS implemented with `check_expiring_trials()` (3-day window reminders sent via email) and `notify_content_ready()` (post-generation hook for digest/report notifications). Budget alerts (`alerts.py`) exist separately with YAML persistence and DeliveryChannel dispatch. Templates are hardcoded strings (no template system). No notification preferences per user. No webhook for system events.
- **Affected Stages:** A7 (Operations), A5 (Delivery)
- **Affected Users:** B1 (End User — lifecycle notifications exist), B2 (Direct Agent — no agent alerts), B3 (Director — partial system alerting)
- **Existing Cross-Ref:** None (new)
- **Evidence:** `notifications.py:22-104` `check_expiring_trials()`, `notifications.py:107-178` `notify_content_ready()`. Both use `email_sender.send_notification()`. `alerts.py` handles budget alerts via DeliveryChannel. No template system, no user notification preferences.
- **Status:** 🟡 Partially — notifications exist but not unified, no template system, no user preferences.

#### CD-007: [RESOLVED] Delivery Channel Health Monitoring
- **Description:** `get_channel_health` MCP tool is implemented and registered. It checks health + latency for all 12 delivery channels (smtp, webhook, rest_api, file_export, discord, telegram, wechat_work, wechat_oa, dingtalk, feishu, rss, social_publish). Each channel adapter has `send()` and `validate_config()` methods. No automatic channel suspension on failure.
- **Affected Stages:** A5 (Delivery), A7 (Operations)
- **Affected Users:** B1, B2, B3
- **Evidence:** `_handle_get_channel_health` registered at `mcp/server.py:4112`. Registered as `Tool(name="get_channel_health")`. 12 delivery channels with `send()` and `validate_config()` methods.
- **Status:** 🟢 Resolved — channel health monitoring implemented. Remaining: auto-suspension on repeated failure (low priority).

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

#### CD-011: [RESOLVED] Consumption Tracking (Read Receipts / Engagement)
- **Description:** `consumption.py` IS implemented with `ConsumptionEvent` dataclass (delivered/opened/clicked) and `ConsumptionStore` (SQLite-backed). Auto-record on delivery from `output.py:1949-1951` and `output.py:2309-2311`. No dedicated MCP tool for querying consumption events yet (accessed via `ConsumptionStore.list_events()` programmatically). No engagement metrics dashboard.
- **Affected Stages:** A6 (Consumption)
- **Affected Users:** B1 (End User — consumption history tracked), B2 (Direct Agent — no MCP tool for querying), B3 (Director — no dashboard)
- **Existing Cross-Ref:** AUD-04, G8
- **Evidence:** `consumption.py` has `ConsumptionEvent` with `event_id`, `user_id`, `product_type`, `product_id`, `event_type`, `timestamp`, `metadata`. `ConsumptionStore` with `record_event()` and `list_events()`. Database at `.autoinfo/consumption.db`. Events auto-recorded in `output.py:1949` and `output.py:2309`.
- **Status:** 🟢 Resolved — core consumption tracking implemented. Remaining: MCP query tool, engagement dashboard (P2).

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

#### CD-014: [RESOLVED] Backup & Disaster Recovery
- **Description:** Automated backup and restore procedures ARE implemented. `scripts/backup-db.sh` creates timestamped `.autoinfo/backups/backup-<timestamp>.db` for all SQLite databases. `scripts/restore-db.sh` restores from backup. `Makefile` has `backup` target. Keeps last 7 backups. No RPO/RTO formally defined, no point-in-time recovery.
- **Affected Stages:** A7 (Operations)
- **Affected Users:** B3 (Director — basic DR plan exists)
- **Existing Cross-Ref:** None
- **Evidence:** `scripts/backup-db.sh`, `scripts/restore-db.sh`, `Makefile:10` `.PHONY: backup` running `scripts/backup-db.sh`. Backups stored in `.autoinfo/backups/`. RPO/RTO not formally documented.
- **Status:** 🟢 Resolved — automated backup and restore. Remaining: formal RPO/RTO definition (P3).

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

#### CD-018: [RESOLVED] Consumption Tracking MCP Tools
- **Description:** `delivery.md` specs consumption tracking (read receipts, open rates, engagement signals). `consumption.py` IS implemented with `ConsumptionEvent` (delivered/opened/clicked) and `ConsumptionStore` (SQLite-backed). Events auto-record on delivery from `output.py:1949-1951` and `output.py:2309-2311`. No dedicated MCP tool for querying consumption events yet (accessed programmatically via `ConsumptionStore.list_events()`). No engagement metrics dashboard.
- **Affected Stages:** A6 (Consumption)
- **Affected Users:** B2 (Direct Agent — no consumption MCP tool), B1 (End User — reading history auto-tracked)
- **Existing Cross-Ref:** AUD-04
- **Evidence:** `consumption.py` has `ConsumptionEvent` dataclass, `ConsumptionStore` with `record_event()` and `list_events()`. Database at `.autoinfo/consumption.db`. Auto-record in `output.py:1949` and `output.py:2309`. No MCP tool registered for querying.
- **Status:** 🟢 Resolved — core consumption tracking implemented. Remaining: MCP query tool (P2), engagement dashboard (P3).

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
- **Evidence:** 12 delivery channels registered (smtp, webhook, rest_api, file_export, discord, telegram, wechat_work, wechat_oa, dingtalk, feishu, rss, social_publish). `Subscription.channels` is `List[str]` with no validation against registry.

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

#### CD-024: [PARTIALLY RESOLVED] Subscription → Product Gating
- **Description:** Subscription gating IS implemented end-to-end. `check_access()` in `billing.py` gates by tier. ProductTemplate in `output.py:1218-1236` supports three tiers (free/premium/enterprise). 7 product templates defined: 5 free, 1 premium, 1 enterprise. Subscription model (`models.py:340`) has `tier`, `channels`, `domains`, `products`, `platform_limit`, `domain_limit` fields. What's missing: no end-user-facing "upgrade" flow that seamlessly transitions from free to paid (Stripe checkout exists but isn't linked to template gating in a self-service UX). No consumption-based tier graduation.
- **Affected Stages:** A4 (Products), A5 (Delivery)
- **Affected Users:** B1 (End User — no self-service upgrade), B3 (Director — cannot configure tier graduation)
- **Existing Cross-Ref:** AUD-01, A-01
- **Evidence:** `billing.py:548` `check_access()` works. `output.py:1334-1364` — 5 free + 1 premium + 1 enterprise templates. `Subscription` model at `models.py:340` has `tier`, `channels`, `domains`, `products`, `platform_limit`, `domain_limit`, `raw_access`, `processed_access`. Stripe checkout session creation + webhook processing exist in `billing.py`.
- **Status:** 🟡 Resolved — core gating infrastructure exists, templates are tiered. Remaining: self-service upgrade UX (P2), consumption-based graduation (P3).

#### CD-025: Payment Provider Abstraction Layer
- **Description:** Currently has Stripe-specific integration (`create_checkout_session` MCP, `POST /api/v1/webhook/stripe`, 3 webhook handlers). Need a **payment provider abstraction** so that Subscription model can work with any provider (WeChat Pay, Alipay, UnionPay, Stripe, etc.) without hardcoding. The Stripe implementation serves as a reference for the abstraction interface.
  - **V1 (v1.8.4) update:** Single-article payment IS now implemented — `create_checkout_session` supports `mode="payment"` for one-time article purchases, `check_access(article_id=...)` fast path verifies article entitlement grants (`billing.py`, `consumption.py` `article_entitlement` table). The `PaymentProvider` abstraction itself is still absent — Stripe remains the sole hardcoded provider. This gap stays open for the abstraction layer.
  - **V2+:** Define `PaymentProvider` ABC with common interface (create_checkout, handle_webhook, refund, query_status). Implement for target markets. The Stripe implementation already has the right patterns (webhook routing, status mapping, subscription activation, payment-mode branching).
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

#### CD-031: [MERGED INTO CD-024] Product Templates All Hardcoded to `free` (RESOLVED)
- **Description:** Originally reported that all product templates had `access_level="free"`. Updated findings: there are 7 templates — 5 free + 1 premium + 1 enterprise (`output.py:1334-1364`). `check_access()` IS implemented and active at `billing.py:548`. The remaining gap (self-service upgrade UX) is tracked under CD-024.
- **Affected Stages:** A4 (Products)
- **Affected Users:** B1 (End User — tiered product access works), B3 (Director — templates are tiered)
- **Existing Cross-Ref:** AUD-01 (merged with CD-024)
- **Evidence:** `output.py:1334-1364` — 5 free + 1 premium + 1 enterprise templates. `billing.py:548` (`check_access`). Templates: weekly-briefing(free), deep-dive(free), weekly-roundup(free), alert-stream(free), daily-quick-scan(free), premium-briefing(premium), executive-summary(enterprise).
- **Status:** 🟢 Resolved — templates are tiered, gating works. Merged into CD-024 for remaining items.

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

#### CD-040: [PARTIALLY RESOLVED] No End-User Consumption Loop
- **Description:** Core consumption tracking IS implemented (`ConsumptionEvent` + `ConsumptionStore`), but the consumption data is not yet used for feedback loops. Events are auto-recorded on delivery (delivered/opened/clicked) in `output.py`. No preference learning, no content adaptation based on engagement, no personalized ranking.
- **Affected Stages:** A6 (Consumption) → A1-A4 (feedback)
- **Affected Users:** B1 (End User — no personalized experience), B3 (Director — no data-driven optimization)
- **Evidence:** `consumption.py` has `ConsumptionEvent`, `ConsumptionStore`, `record_event()`, `list_events()`. Events auto-recorded at `output.py:1949-1951` and `output.py:2309-2311`. Database at `.autoinfo/consumption.db`. No MCP tool for querying events. No feedback loop to influence collection/extraction/delivery.
- **Status:** 🟡 Partially — data collection exists, feedback loop missing.

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

| Type | Count | Open | Resolved | IDs |
|------|-------|------|----------|-----|
| 🔴 Type 1: Never Designed | 16 | 12 | 4 | CD-001 to CD-016 |
| 🟡 Type 2: Spec'd Not Impl | 7 | 5 | 2 | CD-017 to CD-023 |
| 🟡 Type 3: Partially Impl | 8 | 6 | 2 (1 merged) | CD-024 to CD-031 |
| 🟢 Type 4: Spec Outdated | 5 | 2 | 3 | CD-032 to CD-036 |
| 🟠 Type 5: Architecture | 6 | 5 | 1 (partial) | CD-037 to CD-042 |
| **Total** | **42** | **30** | **12** | |

**Newly resolved gaps (this audit):**
| Gap | Old Status | New Status | Reason |
|-----|-----------|-----------|--------|
| CD-004 | 🔴 Never Designed | 🟢 Resolved | Cron heartbeat + missed-schedule detection + alerts + `get_schedule_status` MCP |
| CD-007 | 🟡 Spec'd Not Impl | 🟢 Resolved | `get_channel_health` MCP tool checks all 12 channels |
| CD-011 | 🔴 Never Designed | 🟢 Resolved | `ConsumptionEvent` + `ConsumptionStore` with auto-record on delivery |
| CD-014 | 🔴 Never Designed | 🟢 Resolved | `backup-db.sh`, `restore-db.sh`, `make backup` all operational |
| CD-018 | 🟡 Spec'd Not Impl | 🟢 Resolved | Core consumption tracking implemented (MCP query tool still pending P2) |
| CD-023 | 🟡 Spec'd Not Impl | 🟢 Resolved | `get_schedule_status` IS registered |
| CD-024 | 🟡 Partially Impl | 🟡 Partially Resolved | Templates tiered (5 free + 1 premium + 1 enterprise), Subscription has `channels`/`domains`/`products` fields; self-service upgrade UX missing |
| CD-031 | 🟡 Partially Impl | 🔗 Merged → CD-024 | All templates no longer hardcoded to `free`, merged into CD-024 |
| CD-031 (evidence) | — | 🟢 Resolved | 7 templates verified: 5 free + 1 premium + 1 enterprise |
| CD-032 | 🟢 Spec Outdated | ✅ Resolved | Audio output working, docs already updated |
| CD-033 | 🟢 Spec Outdated | ✅ Resolved | Agent-native JSON working, docs already updated |
| CD-035 | 🟢 Spec Outdated | ✅ Resolved | Source doc archived, no further action |
| CD-040 | 🟠 Architecture | 🟡 Partially Resolved | Consumption data collection exists, feedback loop missing |

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
- **P1 🟡**: Critical for V1 demo — demo-showable features (notifications, product lifecycle, channel health)
- **P2 🟢**: Important for product quality — can wait past V1 demo (UX polish, self-service upgrade, business metrics)
- **P3 ⚪**: V2+ scope — multi-tenant, auth, rate limiting, Stripe billing completion, scaling

### Priority Status Summary

| Priority | Originally | Resolved (this audit) | Remaining |
|----------|-----------|----------------------|-----------|
| P0 🔴 | 2 | 2 | 0 |
| P1 🟡 | 5 | 3 | 2 |
| P2 🟢 | 17 | 1 | 16 |
| P3 ⚪ | 8 | 0 | 8 |

### P1 🟡 — Must Fix for V1 Demo (Critical)

| ID | Gap | Reason | Effort |
|----|-----|--------|--------|
| CD-038 | Notification delivery for demo | Basic lifecycle notifications exist (trial reminder, content ready) but not a unified framework; adequate for demo | 1-2 days for unification |
| CD-020 | Subscription→channel linking | `Subscription.channels` is `List[str]` not validated against 11 registered channel adapters | 1 day |

### P2 🟢 — Worth Fixing (Important, Can Wait Past V1 Demo)

| ID | Gap | Reason | Effort |
|----|-----|--------|--------|
| CD-024 | Self-service upgrade UX | Core gating ✅, templates tiered ✅ (5 free + 1 premium + 1 enterprise). Remaining: self-service free→paid transition flow | 3-5 days |
| CD-040 | Consumption feedback loop | Data collection ✅ (ConsumptionEvent + ConsumptionStore). Remaining: use consumption data for personalization/ranking | 5-8 days |
| CD-005 | Admin dashboard | No visual operations view | 5-10 days |
| CD-006 | Notification framework unification | Notifications exist but scattered (notifications.py, alerts.py, cron.py); no central template system | 3-5 days |
| CD-008 | Product preview | No QA before delivery; demo can send directly | 2-3 days |
| CD-009 | Email templates | Lifecycle emails are plain text; adequate for demo | 2-3 days |
| CD-010 | Product catalog | End users can't discover products; demo via agent intro | 5-10 days |
| CD-012 | Retention & churn analysis | No business analytics | 5-10 days |
| CD-013 | Live ops dashboard | No real-time monitoring | 3-5 days |
| CD-015 | Scaling strategy | No path beyond single-node SQLite | 5-10 days |
| CD-017 | Product lifecycle MCP tools | Agent cannot manage product lifecycle; not needed for demo | 3-5 days |
| CD-019 | Quiet hours | Spec not implemented | 2-3 days |
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

| Step | Task | Effort | Outcome | Status |
|------|------|--------|---------|--------|
| 1.1 | Fix `expectations.md`: update status markers, add F58-F64 | 1 hr | Spec matches code reality | 🟡 Pending |
| 1.2 | Fix `delivery.md`: add product lifecycle, consumption, channel health, preview | 3 hr | Complete delivery spec | 🟡 Pending |
| 1.3 | Fix `operations.md`: add notifications, email templates, cron reliability, retention | 2 hr | Complete operations spec | 🟡 Pending |
| 1.4 | Fix `data-models.md`: add missing models | 1.5 hr | Complete data model spec | 🟡 Pending |
| 1.5 | Create `multi-tenancy-auth.md` | 3 hr | Auth & tenancy designed | 🟡 Pending |
| 1.6 | Create `ops-runbook.md` | 2 hr | Operational playbook | 🟡 Pending |
| 1.7 | Verify `README.md` (already updated for CD-032/033), update `AGENTS.md`, `CHANGELOG.md` | 1.5 hr | Doc trees consistent | 🟡 Pending |

### Phase 2: P0 Implementation — V1 Demo Foundation (Weeks 3-5) ✅ COMPLETED
**Focus:** Subscription model design + cron reliability — the two things that can break a demo.

| Step | Task | Effort | Outcome | Status |
|------|------|--------|---------|--------|
| 2.1 | Subscription model redesign: add `tier`, `channels`, `domains`, `products`, `platform_limit` fields; wire `check_access()` to real tier checks; create 1 premium template for demo | 2-3 days | Subscription model is correct by design; demo can show free vs premium access | 🟢 **Done** — Subscription model has `tier`/`channels`/`domains`/`products`/`platform_limit`/`domain_limit`/`raw_access`/`processed_access`; 7 templates tiered (5 free + 1 premium + 1 enterprise); `check_access()` gates delivery |
| 2.2 | Cron reliability: monitoring, failure detection, missed-schedule backfill | 2-3 days | Collection is reliable; demo pipeline won't break silently | 🟢 **Done** — heartbeat tracking, missed-schedule detection, email alerts, `get_schedule_status` MCP, `cron health` CLI |

### Phase 3: P1 Implementation — V1 Demo Hardening (Weeks 6-10) ✅ COMPLETED
**Focus:** Make the demo showable and reliable — consumption tracking, notifications, channel health, backup.

| Step | Task | Effort | Outcome | Status |
|------|------|--------|---------|--------|
| 3.1 | Consumption tracking foundation: `ConsumptionEvent` model + basic API (open tracking pixel/read receipt can wait V2) | 3-5 days | Demo can show "user consumed content" | 🟢 **Done** — `ConsumptionEvent` + `ConsumptionStore` with auto-record on delivery (delivered/opened/clicked) |
| 3.2 | Basic lifecycle notifications via existing email sender (trial reminder, content-ready notice) | 2-3 days | Users get key lifecycle communication | 🟢 **Done** — `notifications.py` with `check_expiring_trials()` and `notify_content_ready()` |
| 3.3 | Channel health monitoring: per-channel health endpoint + aggregate health MCP tool | 3-5 days | Demo delivery won't fail silently | 🟢 **Done** — `get_channel_health` MCP tool checks all 12 delivery channels with latency |
| 3.4 | Backup automation: SQLite backup cron + basic restore procedure | 2-3 days | Demo data is safe | 🟢 **Done** — `backup-db.sh`, `restore-db.sh`, `make backup`, keeps last 7 backups |

### Phase 4: P2 Implementation — Product Quality (Weeks 11-16)
**Focus:** Polish, UX, and operational quality — features that make the product professional but aren't demo-blocking.

| Step | Task | Effort | Outcome |
|------|------|--------|---------|
| 4.1 | Notifications framework unification: template engine + lifecycle event hooks (builds on Phase 3.2) | 3-5 days | Unified notification architecture |
| 4.2 | Product preview workflow | 2-3 days | QA before delivery |
| 4.3 | Email templates (welcome, trial-ending, digest-ready, cancellation) | 2-3 days | Professional lifecycle communication |
| 4.4 | Product lifecycle state machine + MCP tools | 3-5 days | Full product lifecycle management |
| 4.5 | Consumption MCP query tool + engagement APIs | 3-5 days | Agent-accessible engagement data |
| 4.6 | Admin dashboard | 5-10 days | Visual operations control |
| 4.7 | Product catalog / storefront | 5-10 days | End-user product discovery |
| 4.8 | Retention & churn analytics | 5-10 days | Business visibility |
| 4.9 | Live operations dashboard | 3-5 days | Real-time monitoring |
| 4.10 | Delivery schema enforcement | 3-5 days | Consistent product quality |
| 4.11 | Business metrics (MRR, LTV, churn) | 5-10 days | Business performance tracking |
| 4.12 | Subscription↔channel linking validation | 1 day | Channel config integrity |
| 4.13 | Feature flags | 3-5 days | Gradual rollout capability |
| 4.14 | Quiet hours implementation | 2-3 days | End-user preference |
| 4.15 | `merge_items` improvement — LLM conflict resolution | 2-3 days | Reliable KB merge |
| 4.16 | Identity anchor implementation | 3-5 days | Cross-platform identity |
| 4.17 | 03-Wiki code-level guarding | 1 day | Defense-in-depth |
| 4.18 | Self-service upgrade UX (free→paid) | 3-5 days | End-user upgrade flow |

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
| 5.9 | Consumption-based tier graduation (use event data for auto-promotion) | 5-8 days | Dynamic tier management |

---

## 2026-08-02 V1 更新

This section documents V1 feature completions (v1.8.1–v1.8.4, landed 2026-08-02) that were not previously cataloged as CD-NNN gaps. The 42-cell A1-A7 × B1/B2/B3 matrix tracks **pipeline stages × user lifecycle**, not individual features, so none of these additions flip any cell status. Where a feature arguably strengthens a cell, that is noted without changing the cell's 🟢/🟡/🔴 value.

### New features landed

| Feature | Code location | Summary |
|---------|---------------|---------|
| **A18 GDELT collector** | `collectors/gdelt.py` | GDELT DOC 2.0 news headline collector (artlist JSON, 1 req/5s free tier, 3-month default window). Headline-level only. |
| **A23 SSRN collector** | `collectors/ssrn.py` | SSRN HTML search-URL parser (no public REST/RSS — config-driven abstract-level only). |
| **A24 HuggingFace/Kaggle collector** | `collectors/huggingface.py` | Dual-provider handler (`provider` config key). HF Hub flat-list API + Kaggle env-gated (`KAGGLE_USERNAME`/`KAGGLE_KEY`). |
| **A25 Unpaywall/CORE collector** | `collectors/unpaywall.py` | Dual-provider OA fulltext-link collector. Unpaywall (free, email-gated) + CORE (v3, Bearer key). V1 scope: metadata + OA link only, no PDF download. |
| **E9 Source credibility score** | `quality.py` (`SOURCE_TIER_SCORE_MAP`), `models.py` (`KBEntry.source_score`), `kb.py` (persistence) | Deterministic `source_score` (0-100) from quality tier, persisted on KBEntry, surfaced in G1 gate details and search results. |
| **E11 RAW product variants** | `models.py` (`Product.variants`), `mcp/server.py` (`_handle_list_products`, `_handle_get_product`) | RAW product carries `variants: ["api_feed", "webhook", "bulk_export"]` field distinguishing the three RAW delivery modes. |
| **E12 Single-article payment** | `billing.py` (`create_checkout_session` `mode="payment"`, `check_access(article_id=...)`), `consumption.py` (`article_entitlement` table) | One-time article purchases via `mode="payment"` checkout; entitlement fast path in `check_access`. See CD-025 note above — abstraction layer still absent. |
| **E14 Content simplification** | `output/__init__.py` (`simplify_text`), `mcp/server.py` (`simplify_content` MCP tool) | CEFR-parameterized text rewrite (A1-C1) with original/simplified level classification and verification flag. |
| **C11 Podcast RSS publishing** | `delivery/rss.py` (`PodcastRSSDeliveryChannel`, `_build_podcast_rss`), `output/__init__.py` (`_maybe_persist_audio`) | RSS 2.0 delivery channel with `<enclosure>` + `itunes:*` namespace; audio output auto-persists MP3 to disk. |

### Cell-impact statement

**No matrix cell flips.** The 42-cell matrix (A1-A7 × B1/B2/B3) evaluates pipeline-stage completeness against user-lifecycle stages. The features above are enhancements within already-evaluated stages, not new stages or lifecycle transitions. Two cells arguably gained strength without changing status:

- **A4 Products (B2.4 Operate, B2.6 Update):** RAW product `variants` field (E11) makes the RAW/PROCESSED product model more expressive. The cells remain 🟡 (product lifecycle state machine still 0% implemented — CD-017/CD-022 open).
- **A5 Delivery (B3.1 Define, B3.5 Scale):** Podcast RSS channel (C11) adds a 12th delivery channel with audio persistence. The cells remain 🟢 (delivery channels were already 🟢; podcast RSS is an additive channel, not a structural change).

### Open CD gaps unaffected

All open CD gaps (CD-001..CD-042 minus the 12 already resolved/merged) remain open. V1 features were never cataloged as CD gaps, so none get closed by this update. The only gap whose note changed is **CD-025** (Payment Provider Abstraction) — its stale "V1: No payment integration needed" note was replaced to reflect that single-article payment (E12) is now implemented while the `PaymentProvider` ABC remains absent.

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

*End of Cross-Dimensional Catalog. 42 gaps cataloged across 5 types (12 resolved/merged after codebase reality check), with full priority matrix and implementation roadmap. Last updated 2026-08-02 (V1 completion audit). This is the keystone product definition document — start here, then navigate to the relevant spec in `docs/dev/specs/`.*
