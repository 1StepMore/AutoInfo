# AutoInfo — Comprehensive Gap Audit

> **Date:** 2026-07-26
> **Method:** Systematic cross-reference of 57 expectations (F01-F57), 3 user types × lifecycle stages, MCP tool schema, AGENTS.md claims, 5 spec files, and 3 market research reports
> **Updated:** 2026-07-27 — Added §11 (Market-Report Matrix Coverage Analysis & Scope Boundaries) with unified end-user definition, 48-scenario coverage analysis, and director-user scope clarifications
> **Auditor:** Sisyphus (orchestration agent)

---

## Executive Summary

AutoInfo v1.6 delivers **55/57 expectations implemented** (✅), with F30/F42 (subscription billing) partially implemented (🟡). However, the detailed audit reveals **8 categories of residual gaps** beyond the known subscription/KB pipeline gaps. A market-report matrix coverage analysis (§11) finds 29/48 (60%) user-information scenarios fully covered, 6/48 (13%) partially covered, and 13/48 (27%) missing — with scope boundaries clarified by the director user.

| Gap Category | Count | Severity | Status |
|-------------|-------|----------|--------|
| Consumer-facing output gaps (G1-G16) | 3 critical, 13 medium/small | 🔴/🟡 | Documented in `consumer-output-gaps.md` |
| MCP tool registration gaps | 9 missing tools | 🟡 | Not registered in MCP schema |
| Doc-code mismatches (AGENTS.md vs reality) | 7 | 🟡/🟢 | Format claims, schema omissions |
| Expectations status staleness | 17 stale statuses | 🟢 | Pre-split doc not updated for v1.6 |
| Director-Agent collaborative pattern gaps | 1 | 🟡 | No push model for agent delivery |
| KB pipeline partial gaps | 3 | 🟡 | `compare_versions` missing, etc. |
| Monetization pipeline | 1 | 🔴 | No full Stripe billing flow |
| Audio/visual format gaps | 2 | 🔴/🟡 | TTS exists; no video pipeline (§11.6 MG-1) |

---

## Section 1: Three User Types × Lifecycle Coverage

### 1.1 End User (Paying Customer) — Lifecycle Coverage

> **Unified end-user definition** (binding for all docs in this audit): "End User" refers collectively to all paying customer types — individual consumer, creator, publisher, enterprise buyer, institutional buyer, platform operator, and content licensor — plus their authorized agent delegates. AutoInfo treats all end users uniformly with a single lifecycle model (discover → trial → subscribe → consume → renew → churn). **No demographic or persona-based segmentation is applied.** The system is a general-purpose solution; downstream persona variation (researchers vs clinicians, executives vs students) is handled at the content level via domain/topic configuration and `target_audience` parameter, not via differentiated end-user profiles.
>
> Three operating modes define how the end user interacts with AutoInfo:
> - **B1 End User (Direct Consumer)**: The paying customer consumes products directly via email, chat, RSS, or portal.
> - **B2 Direct User (Agent Operator)**: An AI agent operates AutoInfo on behalf of the end user via MCP tools.
> - **B3 Director User (Human Commander)**: A human operator defines domains, configures sources, and monitors the system.
>
> The lifecycle table below documents coverage for a unified "end user" across all B1/B2/B3 modes.

| Lifecycle Stage | Spec Reference | Status | Evidence | Gap |
|----------------|---------------|--------|----------|-----|
| **Trial** (registration → trial) | F36, F38 | ✅ | `end_user.py`, `activate_trial()` MCP | — |
| **Active** (subscription active) | F38 | ✅ | State machine: trial→active→suspended→cancelled | — |
| **Product delivery** (multi-channel) | F37 | ✅ | 10 channels: SMTP, Telegram, Discord, WeChat OA, WeChat Work, DingTalk, FeiShu, Webhook, REST API, File Export | No RSS delivery channel |
| **Delivery reliability** | F39 | ✅ | `DeliveryLog` with SLA, retry chain, fallback | No per-delivery MCP query tool |
| **Suspended** (payment grace) | F38 | ✅ | 7-day grace, reminders on D1/D3/D7 | — |
| **Cancelled** | F38 | ✅ | Re-activation within 90 days | — |
| **Self-service portal** | F40 | 🟡 | CLI portal exists (`autoinfo portal`) | No web UI, no magic-link auth |
| **Billing/payment** | F30, F42 | 🟡 | Stripe webhook endpoint exists, `stripe-mock` dev setup | No complete payment flow, no invoice generation |
| **Usage metering** | F42 | 🟢 | CostMeter tracks LLM/storage/API | Not linked to overage billing |
| **Cost transparency** | F43 | ✅ | CLI dashboard, per-domain/per-user allocation | — |

**End User Lifecycle Gaps:**
1. 🔴 G14: No complete monetization pipeline (Stripe exists but flow incomplete)
2. 🟡 No web-based self-service portal (CLI only)
3. 🟡 Usage metering not linked to billing
4. 🟢 G7: No Substack-style newsletter recipient segmentation

### 1.2 Direct User (Agent — MCP Operator) — Lifecycle Coverage

| Lifecycle Stage | Spec Reference | Status | Evidence | Gap |
|----------------|---------------|--------|----------|-----|
| **Connect & discover** | F02, F05 | ✅ | stdio/SSE MCP, 114 tools auto-discovered | — |
| **Configure** (sources, topics) | F08, F09 | ✅ | `add_source` (idempotent), `add_topic`, `list_domains` | `add_sources` batch lacks dry-run |
| **Collect** | F11, F14 | ✅ | `collect_sources` (with dry_run), `process_collection`, `batch_run` | — |
| **Curate** (review, QA, rate) | F16-F18 | ✅ | `list_summaries`, `query_collected`, `rate_item` | — |
| **KB build** | F20-F22 | ✅ | `search_kb`, `get_kb_entry`, `create_kb_draft`, `query_knowledge_graph` | `compare_versions` missing (F50) |
| **Output generate** | F24-F26 | ✅ | `generate_digest/report/tutorial/presentation`, `export_kb` | Format gaps (PDF, HTML for tutorials) |
| **Deliver** | F27-F29 | ✅ | `send_email_digest`, `set_domain_webhooks`, `add_schedule` | No `get_schedule_status` MCP |
| **Cost manage** | F41-F45 | ✅ | `get_billing_summary`, `set_budget_thresholds`, cost dashboard | — |
| **Privacy manage** | F46-F48 | ✅ | `soft_delete_entry`, `restore_entry`, `export_user_data`, `query_audit_log` | — |
| **Monitor & trace** | F54-F57 | ✅ | `diagnose_system`, `trace_item`, `get_metrics` | — |
| **Agent push/subscribe** | — | ❌ | No webhook-for-agent | G6/G12: Agent cannot subscribe to events |

**Direct User Lifecycle Gaps:**
1. 🟡 G6/G12: No agent subscription/push mode (pull-only)
2. 🟡 9 MCP tools specified but not registered (see §3)
3. 🟢 `add_sources` batch lacks dry-run and per-source validation
4. 🟢 `suggest_keywords` returns raw text, not structured response

### 1.3 Director User (Human Commander) — Lifecycle Coverage

| Lifecycle Stage | Spec Reference | Status | Evidence | Gap |
|----------------|---------------|--------|----------|-----|
| **Intention → agent** | AGENTS.md §3 | ✅ | Natural language communication | — |
| **Setup** (install, init, keys) | F01-F06 | ✅ | `pip install`, `autoinfo init`, `autoinfo doctor` | Version mismatch (v1.3.0 vs v1.5.0) |
| **Configure** (domains, sources) | F07-F10b | ✅ | CLI: `domain`, `sources`, `topics` | No `topics group` CLI command |
| **Collect & process** | F11-F15 | ✅ | CLI: `collect`, `process` | No `--force-full` flag |
| **Review & curate** | F16-F19 | ✅ | CLI: `summaries list|show|flag|rate` | — |
| **KB maintain** | F20-F23 | ✅ | CLI: `kb promote|reject|search|list-tiers` | — |
| **Output & deliver** | F24-F29 | ✅ | CLI: `output digest|report|tutorial|presentation|export` | — |
| **Monitor** | F31-F32 | ✅ | CLI: `status`, `sources health` | — |
| **Operate** (cost, audit, trace) | F41-F57 | ✅ | CLI: `cost`, `billing`, `audit`, `trace` | — |

**Director User Lifecycle Gaps:** None significant. This is the best-covered role.

### 1.4 Cross-Dimensional Summary: Pipeline × User × Lifecycle

The companion document [`cross-dimensional-gap-catalog.md`](./cross-dimensional-gap-catalog.md) introduces a **Cross-Dimensional Gap Catalog** (42 gaps, CD-001 to CD-042) that analyzes AutoInfo through two intersecting dimensions:

- **Dimension A — Pipeline Value Chain (7 stages):** A1 Collection → A2 Extraction → A3 Knowledge Base → A4 Products → A5 Delivery → A6 Consumption → A7 Operations
- **Dimension B — 3 User Types × Lifecycle Stages:** B1 End User (6 stages: Discover→Trial→Subscribe→Consume→Renew→Churn), B2 Direct User/Agent (6 stages: Discover→Connect→Configure→Operate→Monitor→Update), B3 Director User (5 stages: Define→Configure→Monitor→Iterate→Scale)

The resulting **119-cell matrix** (7 pipeline stages × 17 lifecycle stages) tells a nuanced story:

| Metric | Count | Percentage |
|--------|-------|------------|
| 🟢 Fully delivered | 56 | 47% |
| 🟡 Partially delivered | 29 | 24% |
| 🔴 Not delivered / blank space | 30 | 25% |
| ⚪ Not applicable | 4 | 3% |

**Condensed matrix — per pipeline stage:**

| Stage | B1 End User | B2 Direct Agent | B3 Director | Health |
|-------|:-----------:|:---------------:|:-----------:|:------:|
| **A1 Collection** | 🟢 (mostly N/A) | 🟢 (5/6 green) | 🟢 (3/5 green) | 🟢 Strong |
| **A2 Extraction** | 🟢 (mostly N/A) | 🟢 (5/6 green) | 🟢 (3/5 green) | 🟢 Strong |
| **A3 Knowledge Base** | 🟡 (1 red: B1.6 Churn—no data export) | 🟡 (1 yellow: compare_versions) | 🟡 (1 red: no multi-tenant isolation) | 🟡 Mixed |
| **A4 Products** | 🔴 (4/4 applicable cells red) | 🟡 (2 red: product lifecycle + engagement) | 🔴 (4/5 red: gating, dashboard, A/B, scaling) | 🔴 Critical |
| **A5 Delivery** | 🟡 (B1.6 Churn red—no cancellation receipt) | 🟡 (1 yellow: channel health) | 🟡 (2 yellow: dashboard + SLA) | 🟡 Mixed |
| **A6 Consumption** | 🔴 (3/3 applicable cells red) | 🔴 (2 applicable cells—all red) | 🔴 (3 applicable cells—all red) | 🔴 Blank (100% red) |
| **A7 Operations** | 🟢 (mostly N/A) | 🟢 (mostly green) | 🟡 (1 red: no horizontal scaling) | 🟡 Mixed |

**Key findings from the cross-dimensional analysis:**

1. **A1-A3 deliver strong base pipeline** — Collection, extraction, and KB are well-built for all three user types. Gap concentration is at scale (multi-tenant, monitoring) rather than core functionality.

2. **A4 Products is the monetization gap** — All 4 product templates are hardcoded `access_level="free"`. No product lifecycle state machine, no instance tracking, no subscription→product gating. The freemium infrastructure exists but has nothing to gate.

3. **A6 Consumption is a blank space** — Zero consumption tracking, zero engagement metrics, zero read receipts, zero churn analysis. The entire feedback loop from delivery back to the pipeline does not exist.

4. **B3 Director has the most unmet needs at scale** — Monitoring dashboards, A/B testing, scaling strategy, backup/DR — all absent. The Director can operate today but cannot grow.

5. **B1 End User lifecycle beyond "deliver" is unbuilt** — Discovery, trial preview, subscription upgrade, churn data export, self-service billing — all red cells.

**Gap distribution by type** (from catalog, cross-referenced in §9):

| Type | Count | IDs |
|------|-------|-----|
| 🔴 Type 1: Never Designed / Blank Spaces | 16 | CD-001 to CD-016 |
| 🟡 Type 2: Spec'd But Not Implemented | 7 | CD-017 to CD-023 |
| 🟡 Type 3: Partially Implemented | 8 | CD-024 to CD-031 |
| 🟢 Type 4: Spec Outdated (code newer than docs) | 5 | CD-032 to CD-036 |
| 🟠 Type 5: Architecture / Philosophy Gaps | 6 | CD-037 to CD-042 |
| **Total** | **42** | Cross-referenced with all existing gap ID schemes |

**The critical insight**: AutoInfo v1.6 delivers strong pipelines in A1-A3 (Collection, Extraction, KB) and A5 (Delivery channels), but has **near-zero delivery** in A4 (Product lifecycle/gating) and **completely blank** in A6 (Consumption tracking). The system can collect, extract, and deliver — but cannot monetize, measure engagement, or learn from usage.

> **Full matrix**: See [`cross-dimensional-gap-catalog.md` §1](./cross-dimensional-gap-catalog.md#section-1-the-matrix--dimension-a--dimension-b) for the complete 119-cell matrix with per-cell annotations.
> **Full gap catalog**: See [`cross-dimensional-gap-catalog.md` §2](./cross-dimensional-gap-catalog.md#section-2-gap-catalog-by-type) for all 42 CD-NNN gaps with detailed descriptions, evidence, and cross-references.

---

## Section 2: 57 Expectations — Current Status & Gaps

### 2.1 Status Summary

| Count | Status | Meaning |
|-------|--------|---------|
| 55 | ✅ Fully Implemented | Code exists, MCP registered, tests pass |
| 2 | 🟡 Partially Implemented | F30 (Subscription/Billing — Stripe exists, flow incomplete), F42 (External Billing — deferred) |
| 0 | ❌ Not Implemented | All expectations have at least partial implementation |
| 0 | ⚪ Deferred | All deferred items (multi-user, mobile, etc.) tracked in §10.3 |

### 2.2 Expectations with Residual Gaps

| ID | Expectation | Official Status | Real Status | Gap Description |
|----|------------|----------------|-------------|-----------------|
| F04 | LLM Configuration | 🟡 | ✅ (v1.6) | Fallback chain wired, per-task model config works |
| F10 | Multi-language | 🔄 | ✅ (v1.6) | Translation QA pipeline, CEFR, glossaries all implemented |
| F13 | Source Handlers | 🟡 | ✅ (v1.6) | 6 handlers: RSS, API, Web, Webhook, Email, PDF |
| F20 | KB Pipeline | 🟡 | ✅ (v1.6) | 4-tier pipeline complete; `create_kb_draft` MCP exists |
| F26 | Export & Interop | 🟡 | ✅ (v1.6) | 6 formats; GraphML missing from MCP schema |
| F27 | Product Delivery | 🟡 | ✅ (v1.6) | 10 channels; RSS delivery channel missing |
| F28 | RAW Product Generation | 🟡 | ✅ (v1.6) | API feeds, webhook streams, bulk export all work |
| F29 | PROCESSED Product Generation | 🟡 | ✅ (v1.6) | Digest, report, tutorial, presentation, alerts all work |
| F30 | Subscription & Billing | ❌ | 🟡 (v1.6) | Stripe webhook endpoint exists; full billing lifecycle deferred |
| F33 | Handler Isolation | 🟡 | ✅ (v1.6) | Each handler is independent; no BaseHandler ABC yet |
| F42 | External Billing Model | ❌ | 🟡 (v1.6) | CostMeter works; Stripe integration partially done |
| F50 | Versioned Re-collection | 🟡 | 🟡 | `get_entry_history` + `restore_entry_version` done; `compare_versions` missing |

### 2.3 Expectations Status Updates Needed

The following expectations have **stale status markers** in `founder-expectations-pre-split.md` that need updating:

| Expectation | Pre-Split Status | Actual Status (v1.6) |
|------------|-----------------|---------------------|
| F04 | 🟡 | ✅ |
| F10 | 🔄 | ✅ |
| F13 | 🟡 | ✅ |
| F20 | 🟡 | ✅ |
| F26 | 🟡 | ✅ |
| F27 | 🟡 | ✅ |
| F28 | 🟡 | ✅ |
| F29 | 🟡 | ✅ |
| F33 | 🟡 | ✅ |
| F36-F40 | ❌ | ✅ (all implemented in v1.6) |
| F41-F45 | ❌ | ✅ (all implemented in v1.6) |
| F46-F48 | ❌ | ✅ (all implemented in v1.6) |
| F49-F53 | 🟡 | ✅ (all implemented in v1.6) |
| F54-F57 | ❌ | ✅ (all implemented in v1.6) |
| F30 | ❌ | 🟡 (Stripe webhook done, full flow deferred) |
| F42 | ❌ | 🟡 (CostMeter done, Stripe billing deferred) |

---

## Section 3: MCP Tool Registration Gaps

Tools specified in AGENTS.md or expectations but **not registered** in MCP schema:

| # | Missing Tool | Expectation | Backend Status | Priority |
|---|-------------|------------|---------------|----------|
| 1 | `compare_versions` | F50 | Backend exists (`kb.py`) but MCP tool missing | 🟡 Medium |
| 2 | `get_schedule_status` | F14 | `cron.py` exists but no MCP tool | 🟡 Medium |
| 3 | `get_delivery_log` | F39 | `delivery_log.py` exists but no MCP tool | 🟡 Medium |
| 4 | `send_to_enduser` | F36 | `end_user.py` + delivery channels exist but no unified MCP | 🟡 Medium |
| 5 | `activate_trial` | F36 | `end_user.py` has `activate_trial` but no MCP wrapper | 🟡 Medium |
| 6 | `check_trial_expiry` | F36 | `end_user.py` has `check_trial_expiry` but no MCP wrapper | 🟡 Medium |
| 7 | `update_preferences` | F37 | `end_user.py` has preferences model but no MCP tool | 🟡 Medium |
| 8 | `get_enduser_products` | F40 | Not queried via MCP (CLI only) | 🟢 Low |
| 9 | `query_delivery_log` | F39 | `DeliveryLog` exists but not queryable via MCP | 🟢 Low |

---

## Section 4: Doc-Code Mismatches (AGENTS.md & MCP Schema)

| Location | Claim | Actual | Risk |
|----------|-------|--------|------|
| AGENTS.md MCP table | Tutorial: Markdown/HTML/JSON | ❌ Only Markdown (`output.py:2695`) | Medium — agents get false expectations |
| AGENTS.md MCP table | Report: Markdown/HTML/JSON/PDF | ❌ Only Markdown + JSON (no PDF, no HTML) | Medium — schema lies |
| AGENTS.md MCP table | Presentation: Markdown/HTML | ❌ Only Markdown | Medium — schema lies |
| AGENTS.md MCP export | Export formats: Markdown/JSON/SQLite/PDF/CSV/GraphML | ⚠️ GraphML missing from MCP `export_kb` enum | Low — MCP schema omission |
| AGENTS.md export | RSS feed as product output | ⚠️ `export_kb` supports `format="rss"` but hidden from MCP enum | Medium — feature invisible |
| AGENTS.md status | "Audio output — 🔜 TTS pending" | ✅ Actually implemented for digest/report as MP3 | Low — stale status |
| AGENTS.md status | "Agent-native JSON — 🔜 spec defined, impl pending" | ✅ `format="agent"` implemented | Low — stale status |

---

## Section 5: Consumer Output Gaps (G1-G16 Cross-Reference)

From `consumer-output-gaps.md` — verified against current codebase:

| Rank | Gap | Severity | AutoInfo Status | Market Evidence |
|:----:|-----|----------|----------------|-----------------|
| 1 | G1: **No audio output** | 🔴 Critical | ❌ No TTS pipeline | 14% preference, 42% WTP for podcast |
| 2 | G11: **No agent-native format** | 🔴 Critical | 🔜 `format="agent"` spec defined, impl done? (need verify) | Fastest-growing channel (+3pp/y) |
| 3 | G14: **No monetization pipeline** | 🔴 Critical | 🟡 Stripe webhook exists, flow incomplete | Project survival — no revenue yet |
| 4 | G8: `target_audience` not in MCP | 🟡 Medium | ❌ Tutorial/Presentation only | Role-aware output demand |
| 5 | G12: **No agent subscription mode** | 🟡 Medium | ❌ Pull-only MCP | Perplexity Comet / ChatGPT Tasks pattern |
| 6 | G15: **No freemium gating** | 🟡 Medium | ❌ No `access_level` on ProductTemplate | Free-to-premium funnel |
| 7 | G5: **RSS not a delivery channel** | 🟡 Medium | ❌ No `RSSDeliveryChannel` | 400M+ podcasts use RSS |
| 8 | G6: **Agent delivery pull-only** | 🟡 Medium | ❌ No webhook-for-agent | Complements G12 |
| 9 | G9: **No role-aware digest/report** | 🟡 Medium | ❌ `target_audience` missing from digest/report | Persona demand unserved |
| 10-16 | G2, G3, G4, G7, G10, G13, G16 | 🟡/🟢 | Various | Deferred or low-effort |

---

## Section 6: KB Pipeline Specific Gaps

From `AGENTS.md` KB pipeline rules and F20 specification:

| KB Rule | Status | Evidence | Gap |
|---------|--------|----------|-----|
| 01-Raw is sole entry point | ✅ | All collected items → 01-Raw | — |
| Agent cannot create Draft from outside | ✅ | `create_kb_draft(raw_ids=[...])` requires Raw IDs | — |
| Agent cannot write 03-Wiki | ✅ | Only human `kb promote` writes Wiki | — |
| 03-Wiki is append-only | ✅ | Once promoted, stays | — |
| Source metadata mandatory | ✅ | `source_url`, `source_type`, `source_platform` enforced | — |
| Agent can tag Wiki deprecated | ✅ | Explicit human command required | — |
| Version tracking | 🟡 | `get_entry_history` + `restore_entry_version` exist | ❌ `compare_versions` MCP missing |
| Cross-collection dedup & merge | ✅ | `find_similar_items` + `merge_items` MCP tools exist | — |
| Stale content handling | ✅ | `is_stale` flag, search demotion, digest exclusion | — |
| Domain decay metrics | ✅ | `get_domain_decay()` MCP tool, Green/Yellow/Red grade | — |

**KB Pipeline Residual Gaps:**
1. 🟡 `compare_versions` MCP tool not registered (F50)
2. 🟢 No `batch_flag` MCP tool for bulk KB promotion
3. 🟢 No `bulk_promote` flow for Draft→Wiki

---

## Section 7: Priority Fix Roadmap

> **Cross-Reference**: This roadmap aligns with the [Cross-Dimensional Gap Catalog §5 Implementation Roadmap](./cross-dimensional-gap-catalog.md#section-5-implementation-roadmap), which organizes work into 5 phases (Spec Overhaul → P0 Implementation → P1 → P2 → P3/Future). The Waves below map to the equivalent phases. Each Wave item is now cross-referenced with CD-NNN gap IDs for traceability.

### Wave 0: Documentation (This Document) — Maps to Phase 1 (Spec Overhaul)
- [x] Create comprehensive gap audit — covers CD-001 to CD-042
- [x] Cross-dimensional reconciliation with `cross-dimensional-gap-catalog.md` (§1.4, §9, §10)

### Wave 1: Fix Expectations Statuses & Spec Accuracy (1-2 hours) — Maps to Phase 1, Steps 1.1-1.4
- [ ] Update `founder-expectations-pre-split.md` — all stale statuses (§2.3) — **CD-032, CD-033** (spec says 🔜, code has ✅)
- [ ] Update `founder-expectations.md` index if needed
- [ ] Fix AGENTS.md doc-code mismatches (§4) — **CD-034** (format claims outdated), **CD-028** (deprecation rule clarity), **CD-029** (Wiki guarding enforcement description)

### Wave 2: Register Missing MCP Tools & Fix Partial Implementations (4-6 hours) — Maps to Phase 2 (P0) + Phase 3 (P1)
- [ ] Register `compare_versions` (F50) — **CD-022** (spec'd not registered)
- [ ] Register `get_schedule_status` (F14) — **CD-004, CD-023** (cron reliability)
- [ ] Register `get_delivery_log` (F39) — **CD-022** (spec'd not registered)
- [ ] Register `send_to_enduser` (F36) — **CD-022** (spec'd not registered)
- [ ] Register `activate_trial` (F36) — **CD-022** (spec'd not registered), partially covers **CD-025**
- [ ] Register `check_trial_expiry` (F36) — **CD-022, CD-025** (trial auto-expiry)
- [ ] Register `update_preferences` (F37) — **CD-022**, partially covers **CD-019, CD-020**

### Wave 3: Fix SPEC Documentation Gaps (2-3 hours) — Maps to Phase 1, Steps 1.2-1.6
- [ ] Update `expectations.md` spec file with current statuses — **CD-032, CD-033** (status staleness)
- [ ] Update `delivery.md` with actual channel capabilities and missing specs — **CD-007** (channel health), **CD-008** (product preview), **CD-009** (email templates), **CD-017** (product lifecycle), **CD-018** (consumption tracking), **CD-019** (quiet hours), **CD-020** (channel linking), **CD-024** (subscription disconnect), **CD-031** (access_level dead code)
- [ ] Fix `mcp-tools.md` to match 114 tools reality — **CD-022, CD-023, CD-036**
- [ ] Fix format claims in `output.md` or AGENTS.md — **CD-034**

### Wave 4: Consumer-Facing & Monetization Gaps (Deferred → Now Mapped to Phase 2-4)
> Previously marked "Deferred". Now mapped to concrete CD-NNN gaps with priorities from the cross-dimensional catalog.

| Gap | Priority | CD-NNN | Cross-Dimensional Context |
|-----|----------|--------|--------------------------|
| Complete monetization pipeline (Stripe) | 🔴 P0 | **CD-024, CD-025** | Phase 2, Steps 2.1-2.2: Subscription model unification + Stripe billing flow. Blocks A4 Products and A5 Delivery monetization across all B1 End User lifecycle stages. |
| Audio output (TTS pipeline) | 🟢 Already done | **CD-032** | Phase 1, Step 1.7: Spec fix — audio IS implemented; docs say it's not. `consumption-output-gaps.md` G1 status needs update. |
| Agent push/subscription mode | 🟡 P1 | **CD-008** | Phase 3, Step 3.6: Product preview workflow. Matches B2 Direct Agent lifecycle gap at A5 Delivery stage. |
| RSS delivery channel | 🟡 P1 | **CD-008** | Phase 3: Delivery channel expansion. Part of B1 End User consumption pattern gap. |
| Role-aware digest/report (`target_audience`) | 🟢 P2 | **CD-036** | Phase 3: MCP parameter behavior alignment. Low complexity fix. |
| Freemium gating (all products hardcoded `free`) | 🔴 P0 | **CD-031, CD-024** | Phase 2, Step 2.1: Part of subscription model unification. Current state: `access_level` field exists but has zero effect. |
| Subscription-to-product mapping (C7) | 🔴 P0 | **CD-024, CD-020** | Phase 2, Step 2.1: Subscriptions must control which products users get. |
| Consumption tracking infrastructure | 🔴 P0 | **CD-011, CD-018** | Phase 2, Step 2.5: Foundation for all A6 Consumption gap fixes. |
| Email lifecycle templates | 🟡 P1 | **CD-009** | Phase 3, Step 3.7: Welcome, trial-ending, digest-ready, cancellation emails. |
| 03-Wiki guarding at code level | 🟡 P1 | **CD-029** | Phase 3: Move from agent-instruction-level to code-level enforcement. |

> **Full implementation roadmap**: See [`cross-dimensional-gap-catalog.md` §5](./cross-dimensional-gap-catalog.md#section-5-implementation-roadmap) for 5-phase plan with milestones, effort estimates, and step-level task breakdown.

---

## Section 7: End-User Subscription Value & Customization Gaps (First-Principles Analysis)

*Analysis from first principles: What value does the end-user actually receive? What do they pay for? What can they customize? How does the tier model connect to value delivery?*

### 7.1 Value Chain Map: What the End-User Gets

```
Collector → Extractor → KB → Products → Delivery → End-User
  (raw)      (LLM)    (curated) (digest/    (6 channels)
                             report/...)
```

At each link, the user receives:
1. **Collection**: Auto-configured sources fetch relevant content automatically
2. **Extraction**: LLM produces TL;DR, key points, entities, custom fields
3. **KB**: Structured, versioned, searchable knowledge in 4 tiers
4. **Products**: Digest, report, tutorial, presentation (Markdown/HTML/JSON/PDF/Audio)
5. **Delivery**: SMTP email, 6 chat adapters, REST API, file export, webhook

**First-principles question**: What does paying more get you? Answer: **Nothing today — because there's no working tier differentiation.**

### 7.2 The Tier Model: Three Layers That Don't Connect

AutoInfo has **three independent tier-like concepts** with zero cross-references:

| Layer | Field | Type | Default | Used By |
|-------|-------|------|---------|---------|
| **User tier** | `UserProfile.tier` | Freeform string | `"free"` | CLI hints "free/pro/enterprise" but no enum |
| **Subscription plan** | `Subscription.plan` + `price_monthly` | Freeform string + unused float | `"free"` / `0.0` | No code reads these fields |
| **Product access_level** | `ProductTemplate.access_level` | `Literal["free","premium","enterprise"]` | `"free"` | `billing.check_access()` — but all 4 product templates are hardcoded `"free"` |

**Finding T1.1**: These three layers exist in separate files (`models.py:316`, `models.py:340`, `output.py:1154`) and **no code in the entire codebase links them together**. `UserProfile.tier` is never mapped to `ProductTemplate.access_level`. `Subscription.price_monthly` is declared but never read. The tier ladder exists as dead code.

### 7.3 Pricing: What Would the User Pay?

**No pricing model exists in the codebase.** The only prices defined are internal cost estimates:

```python
# cost.py — internal unit costs, NOT customer-facing prices
_DEFAULT_UNIT_PRICES = {
    "llm_tokens": 0.00001,       # $0.01 per 1k tokens
    "storage_mb": 0.10,           # $0.10 per MB/month
    "api_calls": 0.005,           # $0.005 per API call
}
```

**Finding T2.1**: There is no `PricingPlan`, `ProductCatalog`, or `Price` model. The entire pricing intelligence lives inside Stripe's price objects — meaning there's no way to audit, test, or configure pricing without hitting the Stripe API. A local/offline deployment cannot charge users because the pricing data exists only in Stripe's cloud.

**Finding T2.2**: `Subscription.price_monthly` (`models.py:350`) is a float field declared on the dataclass but:
- Not in the DB schema (`user_store.py:46-112` — SQLite table has no `price_monthly` column)
- Not written by any code
- Not read by any code
- Not sent to Stripe (Stripe prices are created in Stripe dashboard, not synced)

### 7.4 Subscription State Machine vs Actual Value Delivery

```
Spec (delivery.md §5.1)          Implementation (user_store.py:619-631)
┌────────────────────┐           ┌──────────────────────┐
│ Created ─→ Generated │           │ trial ─→ active       │
│ ─→ Delivered ─→      │           │   ↕        ↕         │
│ Consumed ─→ Aged ─→ │           │ suspended ←┘         │
│ Archived              │           │   ↕                  │
└────────────────────┘           │ cancelled             │
                                 └──────────────────────┘
```

**Finding T3.1**: The spec describes a 6-state product lifecycle (Created→Generated→Delivered→Consumed→Aged→Archived). The implementation has a 4-state user lifecycle (trial→active→suspended→cancelled). **These are orthogonal concepts** — the product lifecycle tracks individual products, the user lifecycle tracks the user's billing status. The product lifecycle does not exist in code.

**Finding T3.2**: No auto-expiry enforcement. `check_trial_expiry()` must be called manually by an operator. Trial users never auto-convert or auto-block.

### 7.5 Feature Gating: What Premium Unlocks (Today: Nothing)

`billing.check_access()` (`billing.py:548`):

| access_level | Gate Logic | Product Templates Using It |
|-------------|-----------|---------------------------|
| `"free"` | Always allowed | ✅ digest, report, tutorial, presentation |
| `"premium"` | User must have active Stripe subscription | ❌ **Zero** |
| `"enterprise"` | String-match `"enterprise"` in tier/plan | ❌ **Zero** |

**Finding T4.1**: Freemium gating infrastructure exists (`check_access()`, `ProductTemplate.access_level`) but **no product is gated behind premium or enterprise**. The gate has nothing to guard.

**Finding T4.2**: Tier differentiation is impossible because:
- No feature flags (`Subscription.features` is an empty dict with no code reading it)
- No quota limits ("free gets 1 domain, pro gets 5" — nothing enforces this)
- No content restrictions ("premium gets full-text, free gets summary" — not implemented)
- No delivery channel restrictions ("email for all, Discord only for premium" — not implemented)

### 7.6 Subscription-to-Product Mapping: Missing

**Spec** (`delivery.md §4.1`) says `Subscription` should have:
```
domain, topics, products, channels, schedule, last_delivered_at
```

**Implementation** has:
```python
# models.py:340 — Subscription dataclass
subscription_id, user_id, plan, status, start_date, end_date,
auto_renew, price_monthly (unused), currency, features (empty dict),
created_at, updated_at
```

**Finding T5.1**: Subscriptions don't actually control what content you get. A subscription record exists, but it doesn't specify which domains, topics, products, or channels the user subscribes to. The subscription is a billing artifact, not a content entitlement.

**Finding T5.2**: There is no `ProductInstance` model — no tracking of "this digest was delivered to this user on this date." Delivery log records raw delivery events but doesn't model the product→subscription relationship.

### 7.7 End-User Customization: What Can the User Configure?

**Schema-free preferences** (`UserProfile.preferences` — freeform dict):

| Key | Type | Read By | Notes |
|-----|------|---------|-------|
| `format` | string | output generators | "markdown", "html", etc. |
| `delivery_channel` | string | `send_to_enduser` | Channel fallback |
| `timezone` | string | output generators | e.g. "UTC" |
| `max_items` | int | digest generator | Max KB entries per digest |
| `target_audience` | string | output generators | Validated vs `_VALID_AUDIENCES` |

**Valid audiences**: `researcher`, `clinician`, `executive`, `student`
Each maps to a tone/prompt tweak in the LLM generation:
- `researcher` → technical depth
- `clinician` → practical application
- `executive` → strategic summary
- `student` → foundational explanation

**Delivery preferences** (`UserProfile.delivery_preferences` — freeform dict):
| Key | Type | Read By | Notes |
|-----|------|---------|-------|
| `channel` | string | `send_to_enduser` handler | Fallback delivery channel |

**Finding T6.1**: Preferences have **no schema enforcement**. Any key can be written via `update_preferences()`, but only these 5+1 keys are ever read. Misspellings are silent.

**Finding T6.2**: `DeliveryPreferences` and `Preferences` are two separate dicts on the same model with no clear distinction documented. The spec (`delivery.md §4.1`) defines typed dataclasses (`DeliveryPreferences`, `ChannelConfig`, `QuietHours`) that are completely replaced by these freeform dicts.

**Finding T6.3**: Custom instructions are free-text strings appended to LLM prompts. There is no validation, no templating, no permission check ("can this user inject arbitrary instructions?"). A premium user and a free user have the same prompt injection capability.

### 7.8 Gap Catalog: Subscription Value & Customization

#### Critical Design Gaps (C1-C13)

| ID | Gap | Root Cause | Impact | Fix Priority |
|----|-----|-----------|--------|-------------|
| **C1** | **No pricing model** — no price definition for free/premium/enterprise tiers | Pricing lives exclusively in Stripe | Cannot charge anyone without Stripe; local deployments cannot monetize | 🔴 P0 |
| **C2** | **No feature flag system** — `Subscription.features` is empty dict, read by nothing | Tier differentiation was never implemented | All users get the same service regardless of tier | 🔴 P0 |
| **C3** | **`tier` is freeform string** — CLI hints "free/pro/enterprise" but no enum, no validation | Early design shortcut | Tier means nothing; `check_access("enterprise")` uses fragile string matching | 🟡 P1 |
| **C4** | **`plan` on Subscription is also freeform** — same problem | Same shortcut | Plan means nothing | 🟡 P1 |
| **C5** | **No connection between `price_monthly` and billing** — Stripe has the only pricing data | Stripe-first architecture | Cannot audit pricing locally; test environments have no prices | 🔴 P0 |
| **C6** | **All product templates hardcoded `"free"`** — premium/enterprise gating is dead code | Feature incomplete | Freemium gating exists but nothing is gated | 🟡 P1 |
| **C7** | **No subscription-to-product mapping** — subscriptions don't control what you get | Under-specified | Subscriptions are billing artifacts, not content entitlements | 🔴 P0 |
| **C8** | **No self-service upgrade/downgrade** — only CLI/MCP operator tools | No end-user portal | End-user cannot subscribe themselves | 🟡 P1 |
| **C9** | **Preferences have no schema** — any key works, only 5 are read | Flexible design, no guardrails | Hard to discover; silent misspellings | 🟢 P2 |
| **C10** | **No trial auto-expiry** — operator must manually call check | Missing cron integration | Trial users never auto-convert or auto-block | 🟡 P1 |
| **C11** | **Two separate preference dicts** — `preferences` vs `delivery_preferences`, no distinction | Organic growth | Confusing API; unclear which to use for what | 🟢 P2 |
| **C12** | **G15 gating only covers digest and report** — tutorial and presentation have no access check | Incomplete implementation | Inconsistent gating; premium-gated tutorials bypassable | 🟡 P1 |
| **C13** | **No data retention by tier** — spec says retention varies by tier, no logic links tier to retention | Unimplemented | Cannot offer longer retention as a premium feature | 🟢 P2 |

#### Spec→Implementation Gaps (A1-A24)

| ID | Spec'd Feature | Status | Detail |
|----|---------------|--------|--------|
| A1 | `DeliveryPreferences` typed dataclass | 🟡 | Replaced by freeform dict |
| A2 | `ChannelConfig` typed dataclass | 🟡 | Not typed |
| A3 | `QuietHours` dataclass (start/end/timezone/only_urgent) | 🔴 | **Not implemented anywhere** |
| A4 | `UserProfile.identity_anchor` field | 🟢 | Deferred — low impact |
| A5 | `UserStatus` enum (TRIAL/ACTIVE/SUSPENDED/CANCELLED) | 🟢 | String-only — low impact |
| A6 | `SubscriptionStatus` enum (ACTIVE/PAUSED/CANCELLED) | 🟢 | String-only — low impact |
| A7 | Subscription domain/topics/products/channels/schedule | 🔴 | **Not in model** — subscriptions don't control content |
| A8-A14 | 7 MCP tools: create/get/update/list/get_subscription/update_subscription/deactivate | 🟡-🔴 | CLI exists but no MCP tools for user CRUD |
| A15 | `send_test_delivery` MCP tool | 🟢 | Missing but low impact |
| A16 | Quiet hours enforcement in `deliver_with_retry` | 🟡 | Not implemented |
| A17 | Product lifecycle states (Created→Generated→...→Archived) | 🔴 | **Not implemented** — no product state machine |
| A18 | Product instance tracking (product_instances table) | 🔴 | **Not implemented** — no product→user mapping |
| A19 | Consumption tracking (read receipts, open rates) | 🟡 | Not implemented |
| A20 | Engagement/churn signals (portal login frequency) | 🟡 | Not implemented |
| A21 | Product archive search (FTS5 on product metadata) | 🟡 | Not implemented |
| A22 | Bulk export via `export_kb(user_id=…)` | 🟡 | Not implemented |
| A23 | Agent Push delivery channel | 🟢 | Not implemented |
| A24 | RSS Feed delivery channel | 🟢 | Not implemented |

#### Unplanned Additions (B1-B9)

| ID | Feature | Good? | Notes |
|----|---------|-------|-------|
| B1 | Full Stripe integration (checkout, webhooks, status mapping) | ✅ | Beyond spec scope — works but pricing lives only in Stripe |
| B2 | `grace_period_days` field | ❌ | Declared, never used |
| B3 | `last_login_at` field | ❌ | Declared, never auto-updated |
| B4 | `metadata` freeform dict | ✅ | Useful extension |
| B5 | Stripe billing fields (stripe_customer_id, subscription_id) | ✅ | Necessary for Stripe integration |
| B6 | `price_monthly`, `currency`, `features` on Subscription | ❌ | Dead fields — declared, never read |
| B7 | CostMeter end-user usage/invoice generation | ✅ | Useful metering infrastructure |
| B8 | Budget thresholds & alerts | ✅ | Operational value |
| B9 | Billing summary (usage + subscription) | ✅ | Useful dashboard tool |

### 7.9 First-Principles Assessment: Value Delivery Score

For each value link, assess actual value delivery to a paying end-user:

| Value Link | What User Expects | What They Get | Grade |
|-----------|-------------------|---------------|-------|
| **Source config** | Configure what topics/sources matter | ✅ Full topic/source management | A |
| **Auto-collection** | Content arrives without manual effort | ✅ Cron scheduling, multi-source | A |
| **LLM extraction** | Structured, accurate summaries | ✅ TL;DR, key points, entities, custom fields | A |
| **Knowledge curation** | Build a personal knowledge base | ✅ 4-tier KB with versioning, search, graph | A |
| **Product generation** | Get insights in desired format | ✅ Digest/report/tutorial/presentation | A |
| **Delivery** | Content reaches me where I am | ✅ 6 chat adapters + email + REST | A |
| **Subscription tier** | Pay more, get more | ❌ **No differentiation** | F |
| **Pricing clarity** | Know what I'll pay | ❌ **No pricing model** | F |
| **Self-service** | Manage my own account | ❌ **Operator-only CRUD** | D |
| **Customization** | Tailor content to my needs | 🟡 Schema-free prefs, 5 keys read | C |
| **Quiet hours** | Don't disturb me at night | ❌ **Not implemented** | F |
| **Usage visibility** | See what I'm consuming | 🟡 Cost dashboard exists but not end-user facing | D |
| **Retention** | My data stays as long as I pay | 🟡 Soft-delete (30d) exists, tier-based not | C |

**Overall Value Delivery Grade: C+** — Strong core pipeline, minimal monetization maturity.

### 7.10 Root Cause: Architectural Gap

The fundamental problem is not missing features — it's that the **subscription model was designed as an afterthought**:

1. `UserProfile` was a simple user record (v1.0-v1.5)
2. `Subscription` was added as a separate concern (v1.6) 
3. `ProductTemplate.access_level` was added independently (v1.6)
4. `billing.check_access()` was added as a bridge — but nothing calls it with `"premium"` or `"enterprise"` because no product template uses those values

The layers don't compose because they were built by different people at different times without a unified tier/value model.

**Fix requires**: A unified `PricingTier` enum, a feature-flag system mapped to tiers, a product-template overhaul to assign access_levels, and a pricing catalog (local or Stripe-backed) that the code can read and enforce.

---

## Section 8: KB Pipeline State Machine & Transition Gaps (First-Principles Analysis)

*Analysis from first principles: What are all the states an entry can be in? What transitions are allowed? Who can do what? Where does the implementation violate the spec?*

### 8.1 Complete State Machine Diagram

```
                                    ┌──────────────┐
                                    │  00-Inbox    │  ← DEPRECATED — scaffold only
                                    │  (extinct)   │     no writes possible
                                    └──────────────┘

  Collection ──→ ┌──────────────┐   create_kb_draft()   ┌──────────────┐
  Import ───────→│   01-Raw     │───────────────────────→│   02-Draft    │
                 │  [active]    │                        │  [active]     │
                 └──┬───────┬───┘                        └──┬────┬───────┘
                    │       │                               │    │
               mark_stale()│                          promote│   │reject_kb_draft()
                    │       │(soft/delete)                   │    │(back_to_raw/archive)
                    ▼       ▼                               ▼    ▼
              [stale]  [deleted=1]                    [03-Wiki]  [01-Raw/archived]
                    │       │                          [active]
                    │       │                             │
               restore───restore()                    mark_stale()  soft_delete_entry()
                    │       │                             │          (NO GUARD!)
                    ▼       ▼                             ▼          ▼
              [active]  [active]                      [stale]    [deleted=1]
                                                           │          │
                                                      unmark_stale? restore_entry?
                                                      (NOT IMPL)     (NO GUARD!)
                                                           │          │
                                                           ▼          ▼
                                                      stuck ⚠️   [active/stale]
```

### 8.2 State Dimensions (3 Orthogonal Axes)

An entry's complete state is defined by **three independent dimensions**:

| Axis | Values | Persisted Where | Set By |
|------|--------|----------------|--------|
| **Tier** | `01-Raw`, `02-Draft`, `03-Wiki` | Directory path + SQLite column | `store_entry()`, `create_kb_draft()`, `promote_kb_draft()` |
| **Status** | `active`, `stale`, ~~`deprecated`~~, ~~`archived`~~ | YAML frontmatter only | `mark_stale()`, frontmatter edit |
| **Deleted flag** | `0` (active), `1` (soft-deleted) | SQLite `deleted` column | `soft_delete_entry()`, `restore_entry()` |

**Total logical states**: 3 tiers × 3 status values × 2 deleted flags = **18 theoretical states**
**Implemented**: 3 tiers × 2 status values (no deprecated) × 2 deleted flags = **12 states**
**Valid/accessible**: ~9 (some combinations like "0 deleted + stale" work, "1 deleted + stale" is ambiguous)

### 8.3 All Valid States

| ID | Tier | YAML Status | SQLite Deleted | Reachable? | How to Reach |
|----|------|-------------|----------------|-----------|-------------|
| S1 | 01-Raw | `active` | 0 | ✅ | `store_entry()` during collection/import |
| S2 | 01-Raw | `stale` | 0 | ✅ | `mark_stale()` on S1 |
| S3 | 01-Raw | `active` | 1 | ✅ | `soft_delete_entry()` on S1 |
| S4 | 01-Raw | `stale` | 1 | ✅ | `soft_delete_entry()` on S2 |
| S5 | 02-Draft | `active` | 0 | ✅ | `create_kb_draft()` from S1 |
| S6 | 02-Draft | `stale` | 0 | ✅ | `mark_stale()` on S5 |
| S7 | 02-Draft | `active` | 1 | ✅ | `soft_delete_entry()` on S5 |
| S8 | 02-Draft | `stale` | 1 | ✅ | `soft_delete_entry()` on S6 |
| S9 | 03-Wiki | `active` | 0 | ✅ | `promote_kb_draft()` from S5 |
| S10 | 03-Wiki | `stale` | 0 | ✅ | `mark_stale()` on S9 |
| S11 | 03-Wiki | `active` | 1 | ✅ | `soft_delete_entry()` on S9 (⚠️ GAP) |
| S12 | 03-Wiki | `stale` | 1 | ✅ | `soft_delete_entry()` on S10 (⚠️ GAP) |
| — | Any | `deprecated` | 0 | ❌ | **Not implemented** |
| — | Any | `archived` | 0 | ❌ | Not implemented (only `reject_kb_draft(action="archive")` creates archived drafts, not a general state) |

### 8.4 Transition Table (Complete)

```
FROM              → TO              TRIGGER                              ACTOR       GUARD?
─────────────────────────────────────────────────────────────────────────────────────
[external]        → 01-Raw/active   store_entry(tier="01-Raw")           Agent/Human ✅ _ensure_not_wiki()
01-Raw/active     → 02-Draft/active create_kb_draft(raw_ids=[...])       Agent/Human ✅ verifies raw_ids are 01-Raw
02-Draft/active   → 03-Wiki/active  promote_kb_draft(draft_id)           Human(CLI)  ❌ NO ACTOR CHECK
02-Draft/active   → 01-Raw/active   reject_kb_draft(action="back_to_raw")Agent/Human ✅ checks tier=02-Draft
02-Draft/active   → _archive/       reject_kb_draft(action="archive")    Agent/Human ✅ checks tier=02-Draft
Any/active        → Any/stale       mark_stale(entry_id)                 Agent/Human ❌ NO TIER CHECK (intentional)
Any/stale         → Any/active      [manual YAML edit only]              Human       ❌ no programmatic way
Any/*             → Any/deleted=1   soft_delete_entry(entry_id)          Agent/Human ❌ NO TIER CHECK (P0 GAP)
Any/deleted=1     → Any/deleted=0   restore_entry(entry_id)              Agent/Human ❌ NO TIER CHECK (P0 GAP)
Any/active        → ∅ (permanent)   delete_entry(entry_id)               Agent/Human ❌ NO TIER CHECK (P0 GAP)
01-Raw/active     → 01-Raw/active   re-collect (newer version)           Agent       ✅ version backup + supersedes
02-Draft/active   → (none)          find_similar_items() + merge_items() Agent/Human ❌ merge_items() returns dict, doesn't save
03-Wiki/active    → 03-Wiki/deprecated [spec allows; NOT IMPLEMENTED]    Agent(cmd)  ❌ missing entirely (P1 GAP)
```

### 8.5 Actor Permissions Matrix

| Operation | Agent | Human | Enforcement | Notes |
|-----------|-------|-------|-------------|-------|
| Write 01-Raw (store_entry) | ✅ | ✅ | `_ensure_not_wiki()` prevents 03-Wiki writes | No 00-Inbox guard |
| Create Draft (create_kb_draft) | ✅ | ✅ | Must originate from Raw | ✅ Correct |
| Promote Draft→Wiki (promote_kb_draft) | ❌ (spec) ✅ (code) | ✅ | **No actor check** 🔴 P0 | MCP tool + CLI both call same function |
| Reject Draft (reject_kb_draft) | ✅ | ✅ | Tier check (02-Draft only) | ✅ Correct |
| Soft-delete (soft_delete_entry) | ⚠️ (spec says no for Wiki) | ✅ | **No tier check** 🔴 P0 | Agent can delete Wiki entries |
| Hard-delete (delete_entry) | ⚠️ (spec says no for Wiki) | ✅ | **No tier check** 🔴 P0 | Agent can permanently delete Wiki entries |
| Restore (restore_entry) | ⚠️ (spec implication: no) | ✅ | **No tier check** 🟡 P2 | Agent can restore Wiki entries from deletion |
| Mark stale (mark_stale) | ✅ | ✅ | No restriction | Intentional — any tier can be stale |
| Mark deprecated | ✅ (on human cmd) | ✅ | **Not implemented** 🟡 P1 | Code doesn't exist |
| Search/read | ✅ | ✅ | Same for all | No access-level filtering |
| Merge (merge_items) | ✅ | ✅ | Returns unsaved dict | Merge doesn't modify KB |
| Version history (get_entry_history) | ✅ | ✅ | Read-only | ✅ Correct |
| Restore version (restore_entry_version) | ✅ | ✅ | Write operation | ✅ Correct (writes new entry, doesn't mutate old) |

### 8.6 Gap Catalog: KB Pipeline State Machine

#### 🔴 P0: Architectural Violations

| GAP | Description | Code Evidence | Fix |
|-----|-------------|--------------|-----|
| **GAP-1** | **03-Wiki delete guard missing** — Agent can hard/soft-delete Wiki entries, violating "03-Wiki is append-only; agent cannot demote or delete" | `delete_entry()` (kb.py:2640) and `soft_delete_entry()` (kb.py:3638) have no tier check. Both accept any entry_id. | Add `_ensure_not_wiki(entry)` guard at top of both functions. Return PermissionError if tier=03-Wiki. |
| **GAP-2** | **Promote has no actor check** — Agent can call `promote_kb_draft()` via MCP tool, bypassing human-only rule | `promote_kb_draft()` (kb.py:2939) is a public Python method. MCP tool `create_kb_draft` handler calls it directly (server.py:2941). No authentication, no caller verification. | Route promotes through a human-only channel (e.g., require a confirmation token, or only allow via CLI with a `--confirm` flag, or add an `actor` parameter validated against service identity) |

#### 🟡 P1: Missing Functionality

| GAP | Description | Code Evidence | Fix |
|-----|-------------|--------------|-----|
| **GAP-3** | **`deprecated` status not implemented** — Spec (F20) and AGENTS.md allow agent to tag `status: deprecated` on human command. KBEntry model declares it. No code sets it. | `models.py:190` — KBEntry docstring lists `"active", "deprecated", "archived"` as valid statuses. `kb.py` has no `deprecate_entry()` function. No MCP tool. No CLI. | Implement `deprecate_entry(entry_id, reason)` that sets frontmatter status: deprecated. Add search/digest filtering for deprecated. |
| **GAP-4** | **merge_items doesn't save to KB** — Spec (F53): "Original entries marked `status: superseded` with `superseded_by: new_uuid`." Code returns a dict for review — never saves. | `quality.py:2789` — `merge_items()` returns `{"merged": {...}, "changes": {...}}`. Never calls `store_entry()`. Never sets `supersedes`/`superseded_by`. | After merge, call `store_entry()` with merged content at Draft tier. Mark originals as superseded with `superseded_by` link. |
| **GAP-8** | **Stale state is O(n) disk-read** — `mark_stale()` only writes YAML frontmatter. `get_active_entries()` reads every frontmatter file from disk to check `status: stale`. No SQLite index for stale flag. | `kb.py:4122` — `get_active_entries()` iterates all entries, parses YAML, filters on `status != 'stale'`. | Add `stale` column to SQLite `entries` table. Sync on `mark_stale()`. Filter at query level. |
| **GAP-12** | **G15 gating incomplete** — `check_access()` only called for digest and report generation. Tutorial and presentation skip the gate entirely. | `output.py:1637` (digest checks), `output.py:1922` (report checks). Tutorial (line 2695) and presentation (line 2993) have no access check. | Add `check_access()` at entry points for tutorial and presentation generation. |

#### 🟡 P2: Functional Gaps

| GAP | Description | Code Evidence | Fix |
|-----|-------------|--------------|-----|
| **GAP-5** | **find_similar_items algorithm mismatch** — Spec: "TF-IDF cosine > 0.85, sentence-level Jaccard > 0.7". Code: `difflib.SequenceMatcher` on whole text. | `quality.py:2738` — `find_similar_items()` uses `SequenceMatcher(None, text1, text2).ratio()` | Replace with sklearn TfidfVectorizer + cosine similarity for title, sentence-level Jaccard for content. |
| **GAP-6** | **No `unmark_stale()` or `undeprecate()`** — State changes should be reversible programmatically | `kb.py:4091` — `mark_stale()` is one-way. No reverse function. Frontmatter YAML can be manually edited but no API. | Implement `unmark_stale()`. Implement `undeprecate()` if deprecate is added. |
| **GAP-13** | **Merge trust boundary not enforced** — Merge output is Draft tier by convention, but no code prevents someone from storing it directly at Wiki tier | Convention only — `merge_items()` returns dict, caller decides what to do with it. `_ensure_not_wiki()` blocks direct Wiki writes but doesn't know about merge provenance. | Tag merge output with metadata flag `generated_by: merge`. Optionally enforce `_ensure_not_wiki()` at store time. |
| **GAP-14** | **restore_entry has no tier restriction** — Agent can restore deleted Wiki entries, effectively undoing a human's deletion | `kb.py:3692` — `restore_entry()` clears `deleted` flag. No check on entry tier. | Add tier check: agent cannot restore 03-Wiki entries. |

#### 🟢 P3: Low-Risk Issues

| GAP | Description | Code Evidence | Fix |
|-----|-------------|--------------|-----|
| **GAP-7** | **No 00-Inbox write guard** — 00-Inbox is deprecated but has no `_ensure_not_inbox()` guard | `kb.py:2157` only has `_ensure_not_wiki()`. `store_entry()` writes to any path. | Add `_ensure_not_inbox()` guard. Minor — no code currently writes to 00-Inbox. |
| **GAP-9** | **Stale demotion is runtime-only, not persisted** — `search_knowledge_base` computes freshness at query time from `include_stale` flag | `kb.py:3299` — freshness_score computed inline. `is_stale` not read from DB. | Persist stale flag to SQLite. Use it in search queries. |
| **GAP-10** | **Fragile path detection in `_ensure_not_wiki`** — String match on `"/03-Wiki/"` — fails on symlinks, case-insensitive FS, double slashes | `kb.py:2157` — `if "/03-Wiki/" in str(file_path)` | Normalize path with `Path.resolve()` before checking. Compare on `Path(entry.tier == "03-Wiki")` instead. |
| **GAP-11** | **Git commit silently fails** — `_git_commit_and_get_sha()` returns `""` on failure but no code checks the return value | `kb.py` — multiple calls to `_git_commit_and_get_sha()` but return value not validated | Log warning on git failure. Optionally provide `--no-git` mode to suppress errors. |

### 8.7 Spec vs Implementation: Rule-by-Rule Verification

| # | Spec Rule | Source | Implementation | Verdict |
|---|-----------|--------|---------------|---------|
| R1 | 01-Raw is sole entry point | F20, AGENTS.md | `store_entry()` writes to tier path. Collection always → 01-Raw. Import → 01-Raw. | ✅ **Pass** |
| R2 | Agent cannot create Draft from outside — must come from 01-Raw | F20, AGENTS.md | `create_kb_draft(raw_ids=[...])` validates each raw_id has tier=01-Raw. | ✅ **Pass** |
| R3 | Agent cannot write to 03-Wiki | AGENTS.md | `_ensure_not_wiki()` in `store_entry()` throws `PermissionError`. | ✅ **Pass** |
| R4 | 03-Wiki is append-only — once promoted, stays | AGENTS.md | No code promotes from Wiki to lower tier. Version backup on re-collect preserves history. | ✅ **Pass** (for promotion direction) |
| R5 | Agent cannot demote or delete Wiki entries — only human can | F20, AGENTS.md | `soft_delete_entry()` + `delete_entry()` have **no tier check**. Agent can delete any tier. | ❌ **FAIL (P0)** |
| R6 | Agent may deprecate (tag `status: deprecated`) on explicit human command | F20, AGENTS.md | **No deprecation code exists.** KBEntry model declares it but nothing sets it. | ❌ **FAIL (P1)** |
| R7 | Source metadata mandatory (source_url, source_type, source_platform) | F20, AGENTS.md | `store_entry()` sets all three from collected item fields. | ✅ **Pass** |
| R8 | Merged entries are Draft-tier, require human promotion to Wiki | F53, expectations.md | `merge_items()` returns unsaved dict (not saved to KB at any tier). Convention: caller uses Draft. | 🟡 **Partial** (not saved, but can't accidentally be Wiki) |
| R9 | Original entries marked `status: superseded` with `superseded_by` | F53, expectations.md | **Not implemented.** `merge_items()` doesn't touch originals. `supersedes` field only set during re-collection. | ❌ **FAIL (P1)** |
| R10 | find_similar_items: TF-IDF cosine >0.85, sentence-level Jaccard >0.7 | F53, expectations.md | `difflib.SequenceMatcher` on whole text. No TF-IDF, no Jaccard, no threshold constants. | ❌ **FAIL (P2)** |
| R11 | Every KB write is a git commit | pipeline.md §2.4 | `_git_commit_and_get_sha()` called but silently fails (returns `""` if git unavailable). | 🟡 **Soft fail** |
| R12 | Stale entries demoted in search, excluded from digests | F49, expectations.md | `search_knowledge_base(include_stale=False)` re-ranks by freshness. `get_active_entries()` filters `status != 'stale'`. | ✅ **Pass** |
| R13 | 00-Inbox deprecated — no writes | F20, AGENTS.md | No code writes to 00-Inbox. No `_ensure_not_inbox()` guard. | 🟡 **Pass (no guard)** |

### 8.8 First-Principles Assessment: KB Pipeline Integrity Score

| Principle | Expectation | Actual | Grade |
|-----------|------------|--------|-------|
| **Provenance** | Every entry has traceable origin | ✅ Source metadata mandatory, UUID traceable | A |
| **Immutability** | Wiki entries survive errors and misuse | ❌ Agent can delete Wiki entries; no immutable storage guarantee | D |
| **Append-only** | State progresses forward (Raw→Draft→Wiki) | ✅ No demotion path exists in code (reverse promotion is not coded) | A |
| **Human oversight** | Human gates Draft→Wiki promotion | ❌ No actor check on promote; agent can promote | D |
| **State completeness** | All specified states are real | ❌ `deprecated` missing. `superseded` only during re-collection. | C |
| **State reversibility** | State changes can be undone | ❌ `mark_stale()` irreversible. `soft_delete()` reversible but no tier guard. | D |
| **Guarding** | Valid transitions enforced, invalid guarded | ❌ 3 PO violations (delete Wiki, promote as agent, restore Wiki) | D |
| **Search integrity** | Stale/deleted content handled correctly | ✅ Stale demoted in search. Deleted excluded. | A |
| **Versioning** | Historical versions recoverable | ✅ Git SHA tracking + restore_entry_version | A |
| **Lifecycle management** | TTL, decay, merge, deprecation all work | 🟡 TTL exists. Decay metrics exist. Merge + deprecation incomplete. | C |

**Overall KB Pipeline Integrity Grade: C+** — Strong provenance and versioning, critically weak guarding and state machine enforcement.

### 8.9 Root Cause: Architecture vs Implementation Origin

The KB pipeline is **well-specified** but the **guarding abstractions** were never built:

1. **No `EntryPermission` layer** — The only guard is `_ensure_not_wiki()`, a single function that checks string path containment. There's no permission model, no actor-aware routing, no tier-based access control.

2. **Spec written after implementation** — The state machine rules were documented in `expectations.md` and `AGENTS.md` after the code was written. Several rules (no agent delete Wiki, deprecation) describe aspirational behavior that was never implemented.

3. **Two-tier enforcement model** — The KB has exactly one guard (`_ensure_not_wiki`) that blocks direct writes to 03-Wiki. But:
   - Delete operations bypass this guard entirely
   - Promote operations have no guard at all
   - Restore operations have no guard
   - The guard itself is a fragile string match

4. **`merge_items` outsourced to caller** — The merge workflow returns a dict instead of saving to KB, because the merge code lives in `quality.py` (a different module from `kb.py`) and doesn't have access to the store. This architectural separation creates the implementation gap.

**Fix requires**: A systematic `KBGuard` layer that checks every write/delete/promote/restore operation against a permission matrix (tier × actor × operation). The `_ensure_not_wiki()` pattern should be generalized to `enforce(operation, entry, actor)`.

---

## Section 9: Gap ID Cross-Reference — Existing Schemes → CD-NNN

> **Source**: Cross-referenced with [`cross-dimensional-gap-catalog.md` §Appendix](./cross-dimensional-gap-catalog.md#appendix-existing-gap-id-cross-reference) which defines the reverse mapping (CD-NNN → existing IDs).

This section provides the **forward mapping** from all existing gap ID schemes used in this document (and related documents) to the unified Cross-Dimensional CD-NNN scheme. This enables full traceability: each existing gap can be located in the cross-dimensional matrix and prioritized in the implementation roadmap.

### 9.1 Consumer Output Gaps (G1-G16) → CD-NNN

From `consumer-output-gaps.md`:

| Existing ID | Description | CD-NNN | Type | Notes |
|-------------|-------------|--------|------|-------|
| **G1** | No audio output | **CD-032** | 🟢 Spec Outdated | Audio IS implemented (`render_audio()` via OpenAI TTS); `consumer-output-gaps.md` status is stale |
| **G2** | Low-effort consumer gap | — | 🟡 | Minor, not mapped to CD catalog |
| **G3** | Low-effort consumer gap | — | 🟡 | Minor, not mapped to CD catalog |
| **G4** | No product preview before delivery | **CD-008** | 🔴 Never Designed | Pre-delivery product preview for QA; affects B1/B2/B3 at A4-A5 stages |
| **G5** | RSS not a delivery channel | **CD-008** | 🔴 Never Designed | RSS delivery channel absent; relates to B1 End User consumption |
| **G6** | Agent delivery pull-only (no webhook-for-agent) | **CD-008** | 🔴 Never Designed | Agent cannot subscribe to events; relates to B2 Direct Agent at A5 Delivery |
| **G7** | No Substack-style newsletter recipient segmentation / product catalog | **CD-010** | 🔴 Never Designed | Product catalog/storefront; affects B1 Discover + B3 Director |
| **G8** | No consumption tracking / `target_audience` not in MCP | **CD-011** | 🔴 Never Designed | No engagement tracking; core A6 Consumption gap |
| **G9** | No role-aware digest/report | — | 🟡 | Related to `target_audience`; partially addressed by preferences |
| **G10** | Low-effort consumer gap | — | 🟡 | Minor, not mapped to CD catalog |
| **G11** | No agent-native format | **CD-033** | 🟢 Spec Outdated | Agent-native JSON (`format="agent"`) IS implemented; `consumer-output-gaps.md` status stale |
| **G12** | No agent subscription mode (push vs pull) | **CD-008** | 🔴 Never Designed | Agent push/subscribe pattern; relates to B2 at A5 Delivery |
| **G13** | `target_audience` MCP parameter behavior mismatch | **CD-036** | 🟢 Spec Outdated | Parameter behavior needs verification against actual MCP |
| **G14** | No monetization pipeline | **CD-024, CD-025** | 🟡 Partially Impl | Subscription disconnect + Stripe billing flow incomplete; blocks A4-A5 monetization |
| **G15** | No freemium gating | **CD-024, CD-031** | 🟡 Partially Impl | All product templates `access_level="free"`; gating infrastructure exists but dead |
| **G16** | Low-effort consumer gap | — | 🟡 | Minor, not mapped to CD catalog |

### 9.2 Subscription Value & Customization Gaps (C1-C13) → CD-NNN

From this document, §7.8 (End-User Subscription Value — Critical Design Gaps):

| Existing ID | Description | CD-NNN | Type | Notes |
|-------------|-------------|--------|------|-------|
| **C1** | No pricing model — price definition lives exclusively in Stripe | **CD-024, CD-025** | 🟡 Partially Impl | Subscription disconnect + Stripe incomplete |
| **C2** | No feature flag system — `Subscription.features` is empty dict, read by nothing | **CD-037** | 🟠 Architecture | Feature flag system absent; affects A7 Operations |
| **C3** | `tier` is freeform string — no enum, no validation | **CD-024** | 🟡 Partially Impl | Part of subscription model disconnect |
| **C4** | `plan` on Subscription is also freeform — same problem | **CD-024** | 🟡 Partially Impl | Part of subscription model disconnect |
| **C5** | No connection between `price_monthly` and billing — Stripe has only pricing data | **CD-024, CD-025** | 🟡 Partially Impl | Subscription disconnect + Stripe incomplete |
| **C6** | All product templates hardcoded `"free"` — premium/enterprise gating is dead code | **CD-031** | 🟡 Partially Impl | Product templates access_level dead code |
| **C7** | No subscription-to-product mapping — subscriptions don't control what you get | **CD-024** | 🟡 Partially Impl | Core subscription disconnect |
| **C8** | No self-service upgrade/downgrade — only CLI/MCP operator tools | **CD-024, CD-002** | 🔴 Never Designed | Requires end-user auth (CD-002) |
| **C9** | Preferences have no schema — any key works, only 5 are read | **CD-019** | 🟡 Spec'd Not Impl | Quiet hours + typed preferences spec vs freeform dict reality |
| **C10** | No trial auto-expiry — operator must manually call `check_trial_expiry()` | **CD-025** | 🟡 Partially Impl | Part of Stripe billing flow incompleteness |
| **C11** | Two separate preference dicts — `preferences` vs `delivery_preferences`, no distinction | **CD-019** | 🟡 Spec'd Not Impl | Preferences spec→implementation gap |
| **C12** | G15 gating only covers digest and report — tutorial and presentation have no access check | **CD-031** | 🟡 Partially Impl | Incomplete gating; tutorial/presentation skip `check_access()` |
| **C13** | No data retention by tier — spec says retention varies by tier, no logic links tier to retention | **CD-024** | 🟡 Partially Impl | Part of subscription disconnect |

### 9.3 Spec→Implementation Gaps (A1-A24) → CD-NNN

From this document, §7.8 (Spec→Implementation Gaps):

| Existing ID | Description | CD-NNN | Type | Notes |
|-------------|-------------|--------|------|-------|
| **A1** | `DeliveryPreferences` typed dataclass → replaced by freeform dict | **CD-019** | 🟡 Spec'd Not Impl | Quiet hours / typed prefs |
| **A2** | `ChannelConfig` typed dataclass → not typed | **CD-020** | 🟡 Spec'd Not Impl | Subscription→channel linking |
| **A3** | `QuietHours` dataclass (start/end/timezone/only_urgent) → not implemented anywhere | **CD-019** | 🟡 Spec'd Not Impl | Core QuietHours gap |
| **A4** | `UserProfile.identity_anchor` field → deferred, low impact | **CD-021** | 🟡 Spec'd Not Impl | Identity anchor spec'd but not in code |
| **A5** | `UserStatus` enum → string-only, low impact | — | 🟢 | Minor, not mapped |
| **A6** | `SubscriptionStatus` enum → string-only, low impact | — | 🟢 | Minor, not mapped |
| **A7** | Subscription domain/topics/products/channels/schedule → not in model | **CD-024** | 🟡 Partially Impl | Core subscription disconnect |
| **A8-A14** | 7 MCP tools for user CRUD: `create_user`, `get_user`, `update_user`, `list_users`, `get_subscription`, `update_subscription`, `deactivate_subscription` | **CD-022** | 🟡 Spec'd Not Impl | Spec'd delivery MCP tools not registered |
| **A15** | `send_test_delivery` MCP tool → missing but low impact | — | 🟢 | Minor, not mapped |
| **A16** | Quiet hours enforcement in `deliver_with_retry` → not implemented | **CD-019** | 🟡 Spec'd Not Impl | Part of QuietHours gap |
| **A17** | Product lifecycle states (Created→Generated→...→Archived) → not implemented | **CD-017** | 🟡 Spec'd Not Impl | Product lifecycle state machine missing |
| **A18** | Product instance tracking (`product_instances` table) → not implemented | **CD-017** | 🟡 Spec'd Not Impl | No product→user mapping |
| **A19** | Consumption tracking (read receipts, open rates) → not implemented | **CD-011, CD-018** | 🔴 Never Designed | Core A6 Consumption gap |
| **A20** | Engagement/churn signals (portal login frequency) → not implemented | **CD-012** | 🔴 Never Designed | Retention & churn analysis |
| **A21** | Product archive search (FTS5 on product metadata) → not implemented | — | 🟢 | Minor, not mapped |
| **A22** | Bulk export via `export_kb(user_id=…)` → not implemented | — | 🟢 | Minor, not mapped |
| **A23** | Agent Push delivery channel → not implemented | **CD-008** | 🔴 Never Designed | Agent subscription mode |
| **A24** | RSS Feed delivery channel → not implemented | **CD-008** | 🔴 Never Designed | RSS channel gap |

### 9.4 Unplanned Additions (B1-B9) → CD-NNN

From this document, §7.8 (Unplanned Additions):

| Existing ID | Description | CD-NNN | Type | Notes |
|-------------|-------------|--------|------|-------|
| **B1** | Full Stripe integration (checkout, webhooks, status mapping) — beyond spec scope | **CD-025** | 🟡 Partially Impl | Works but pricing lives only in Stripe |
| **B2** | `grace_period_days` field → declared, never used | — | 🟢 | Minor dead code |
| **B3** | `last_login_at` field → declared, never auto-updated | — | 🟢 | Minor dead code |
| **B4** | `metadata` freeform dict → useful extension | — | 🟢 | Low-priority, not mapped |
| **B5** | Stripe billing fields (stripe_customer_id, subscription_id) → necessary | **CD-025** | 🟡 Partially Impl | Part of Stripe integration |
| **B6** | `price_monthly`, `currency`, `features` on Subscription → dead fields | **CD-024** | 🟡 Partially Impl | Part of subscription disconnect |
| **B7** | CostMeter end-user usage/invoice generation → useful metering | — | 🟢 | Minor |
| **B8** | Budget thresholds & alerts → operational value | — | 🟢 | Minor |
| **B9** | Billing summary (usage + subscription) → useful dashboard | — | 🟢 | Minor |

### 9.5 KB Pipeline State Machine Gaps (GAP-1 to GAP-14) → CD-NNN

From this document, §8.6 (Gap Catalog: KB Pipeline State Machine):

| Existing ID | Description | CD-NNN | Type | Notes |
|-------------|-------------|--------|------|-------|
| **GAP-1** | 03-Wiki delete guard missing — Agent can hard/soft-delete Wiki entries | **CD-029** | 🟡 Partially Impl | 03-Wiki guarding is agent-instruction only |
| **GAP-2** | Promote has no actor check — Agent can call `promote_kb_draft()` via MCP | **CD-029** | 🟡 Partially Impl | 03-Wiki guarding — no code-level enforcement |
| **GAP-3** | `deprecated` status not implemented — no code sets it | **CD-028** | 🟡 Partially Impl | Agent deprecation tooling missing |
| **GAP-4** | `merge_items` doesn't save to KB — returns dict, never calls `store_entry()` | **CD-027** | 🟡 Partially Impl | Merge partially implemented |
| **GAP-5** | `find_similar_items` algorithm mismatch — uses `SequenceMatcher`, not TF-IDF | **CD-027** | 🟡 Partially Impl | Related to merge implementation gap |
| **GAP-6** | No `unmark_stale()` or `undeprecate()` — state changes should be reversible | **CD-026** | 🟡 Partially Impl | Stale content handling — no reverse transition |
| **GAP-7** | No 00-Inbox write guard — deprecated tier has no protective guard | — | 🟢 | P3 low-risk; 00-Inbox already extinct |
| **GAP-8** | Stale state is O(n) disk-read — `get_active_entries()` scans all frontmatter | **CD-026** | 🟡 Partially Impl | Stale content O(n) performance issue |
| **GAP-9** | Stale demotion is runtime-only — `freshness_score` computed at query time, not persisted | **CD-026** | 🟡 Partially Impl | Stale flag not in SQLite |
| **GAP-10** | Fragile path detection in `_ensure_not_wiki` — string match on `"/03-Wiki/"` | **CD-029** | 🟡 Partially Impl | Guarding implementation is fragile |
| **GAP-11** | Git commit silently fails — `_git_commit_and_get_sha()` returns `""` on failure, unchecked | — | 🟢 | P3 low-risk |
| **GAP-12** | G15 gating incomplete — `check_access()` only for digest/report, not tutorial/presentation | **CD-031** | 🟡 Partially Impl | Matches C12 — incomplete gating |
| **GAP-13** | Merge trust boundary not enforced — merge output is Draft tier by convention only | **CD-027** | 🟡 Partially Impl | Merge provenance not tracked |
| **GAP-14** | `restore_entry` has no tier restriction — Agent can restore deleted Wiki entries | **CD-029** | 🟡 Partially Impl | 03-Wiki guarding gap |

### 9.6 Cross-Cutting Gaps (F, AUD) → CD-NNN

| Existing ID | Source | CD-NNN | Type | Notes |
|-------------|--------|--------|------|-------|
| **F30** | `expectations.md` — Subscription & Billing | **CD-025** | 🟡 Partially Impl | Stripe billing flow incomplete |
| **F42** | `expectations.md` — External Billing Model | **CD-025** | 🟡 Partially Impl | Same as F30 — Stripe integration |
| **F50** | `expectations.md` — Versioned Re-collection | **CD-022** | 🟡 Spec'd Not Impl | `compare_versions` MCP not registered |
| **AUD-01** | `comprehensive-gap-audit.md` — Subscription layers disconnected | **CD-024, CD-031** | 🟡 Partially Impl | Core monetization gap |
| **AUD-02** | `comprehensive-gap-audit.md` — Stripe billing flow | **CD-025** | 🟡 Partially Impl | Payment flow incomplete |
| **AUD-03** | `comprehensive-gap-audit.md` — No trial auto-expiry | **CD-025** | 🟡 Partially Impl | Matches C10 |
| **AUD-04** | `comprehensive-gap-audit.md` — No consumption tracking | **CD-011, CD-018** | 🔴 Never Designed | Core A6 gap |
| **AUD-05** | `comprehensive-gap-audit.md` — No end-user auth | **CD-002** | 🔴 Never Designed | Core auth/identity gap |
| **AUD-06** | `comprehensive-gap-audit.md` — Product lifecycle missing | **CD-017** | 🟡 Spec'd Not Impl | Product state machine |
| **AUD-07** | `comprehensive-gap-audit.md` — Quiet hours not implemented | **CD-019** | 🟡 Spec'd Not Impl | Matches A3, A16 |
| **AUD-08** | `comprehensive-gap-audit.md` — merge_items partially implemented | **CD-027** | 🟡 Partially Impl | Matches GAP-4 |
| **AUD-09** | `comprehensive-gap-audit.md` — Deprecated status not implemented | **CD-028** | 🟡 Partially Impl | Matches GAP-3 |
| **AUD-10** | `comprehensive-gap-audit.md` — Stale content O(n) | **CD-026** | 🟡 Partially Impl | Matches GAP-8 |

### 9.7 Cross-Reference Coverage Statistics

| Source Document | Gap Prefix | Count | Mapped to CD-NNN | Unmapped (minor/P3) |
|-----------------|-----------|-------|-------------------|---------------------|
| `consumer-output-gaps.md` | G1-G16 | 16 | 14 mapped | 3 (G2, G3, G16) |
| This document — Critical Design Gaps | C1-C13 | 13 | 13 mapped | 0 |
| This document — Spec→Impl Gaps | A1-A24 | 24 | 19 mapped | 5 (A5, A6, A15, A21, A22) |
| This document — Unplanned Additions | B1-B9 | 9 | 4 mapped | 5 (B2, B3, B4, B7, B8, B9) |
| This document — KB Pipeline Gaps | GAP-1 to GAP-14 | 14 | 12 mapped | 2 (GAP-7, GAP-11) |
| `expectations.md` | F30, F42, F50 | 3 | 3 mapped | 0 |
| Cross-cutting audit IDs | AUD-01 to AUD-10 | 10 | 10 mapped | 0 |
| **Total** | | **89** | **75 mapped (84%)** | **14 unmapped (16%)** |

> **Note**: Unmapped gaps are all P3/low-priority items (minor dead code, low-impact fields, P3-grade edge cases) that do not warrant cross-dimensional catalog entries. All P0, P1, and P2 gaps are fully cross-referenced.

---

## Section 10: Gap Coverage Heatmap — Pipeline Stage × User Type × Lifecycle

This heatmap visualizes where gaps concentrate across the **7 pipeline stages (A1-A7)** and **3 user-type lifecycle progressions (B1-B3)**. Each cell represents the gap density at that intersection point.

### 10.1 Color Legend

| Color | Meaning | Symbol |
|-------|---------|--------|
| **Green** | Fully delivered — no significant gaps | 🟢 |
| **Amber** | Partial delivery — 1-2 gaps exist, workarounds available | 🟡 |
| **Red** | Not delivered — multiple gaps, no workaround, blocks value | 🔴 |
| **Gray** | Not applicable — this user type doesn't use this pipeline stage | ⚪ |

### 10.2 Heatmap: B1 End User (Paying Customer)

| Pipeline Stage | B1.1 Discover | B1.2 Trial | B1.3 Subscribe | B1.4 Consume | B1.5 Renew | B1.6 Churn |
|---------------|:---:|:---:|:---:|:---:|:---:|:---:|
| **A1 Collection** | ⚪ | 🟢 | ⚪ | 🟢 | ⚪ | ⚪ |
| **A2 Extraction** | ⚪ | 🟢 | ⚪ | 🟢 | ⚪ | ⚪ |
| **A3 Knowledge Base** | ⚪ | 🟡 (no tenant isolation) | ⚪ | 🟢 | ⚪ | 🔴 **CD-001** (no data export on churn) |
| **A4 Products** | 🔴 **CD-010** (no catalog) | 🔴 **CD-008** (no trial preview) | 🔴 **CD-024** (no subscription→product gating) | 🟡 (delivers but no lifecycle tracking) | 🔴 **CD-012, CD-024** (no renewal product regen) | 🔴 **CD-017** (no product archive on churn) |
| **A5 Delivery** | ⚪ | 🟢 (same channels as paid) | 🟡 **CD-020** (channel linking disconnected) | 🟡 (delivers but no read tracking) | 🟡 (continues, no renewal logic) | 🔴 **CD-009** (no cancellation receipt) |
| **A6 Consumption** | ⚪ | ⚪ | ⚪ | 🔴 **CD-011** (no tracking) | 🔴 **CD-011, CD-012** (no engagement data) | 🔴 **CD-012** (no churn analysis) |
| **A7 Operations** | ⚪ | ⚪ | 🟢 (billing ops) | ⚪ | ⚪ | 🟢 (soft-delete/GDPR) |

**B1 End User Heatmap Summary**: **7 green, 5 amber, 6 red, 11 gray cells** in the B1 row. Worst at A4 Products (4/4 applicable red) and A6 Consumption (3/3 red). The core user journey breaks at Discover (no catalog) and Subscribe (gating doesn't work).

### 10.3 Heatmap: B2 Direct User (Agent / MCP Operator)

| Pipeline Stage | B2.1 Discover | B2.2 Connect | B2.3 Configure | B2.4 Operate | B2.5 Monitor | B2.6 Update |
|---------------|:---:|:---:|:---:|:---:|:---:|:---:|
| **A1 Collection** | 🟢 `list_available_platforms` | 🟢 MCP auto-discovered | 🟢 `add_source`, `add_schedule` | 🟢 `collect_sources`, `batch_run` | 🟡 **CD-004** (no cron reliability monitoring) | 🟢 source config mutable |
| **A2 Extraction** | 🟢 `get_domain_schema`, `list_models` | 🟢 MCP tools | 🟢 per-task LLM config | 🟢 `process_collection`, quality gates | 🟡 (basic progress polling) | 🟢 config via MCP |
| **A3 Knowledge Base** | 🟢 KB tools listed | 🟢 full KB tool set | 🟢 `reindex_kb` | 🟢 `create_kb_draft`, `search_kb` | 🟡 **CD-022, CD-027** (`compare_versions`, merge partial) | 🟢 mutable (soft-delete/restore) |
| **A4 Products** | 🟢 `list_products`, `get_product` | 🟢 MCP tools | 🟢 product templates exist | 🟡 **CD-017** (lifecycle state machine 0% implemented) | 🔴 **CD-018** (no engagement metrics) | 🟡 config mutable via code |
| **A5 Delivery** | 🟢 delivery tools listed | 🟢 MCP tools | 🟢 `send_to_enduser`, channel config | 🟡 `query_delivery_log` exists | 🟡 **CD-007** (no per-channel health monitoring) | 🟢 config mutable |
| **A6 Consumption** | ⚪ | ⚪ | ⚪ | 🔴 **CD-011, CD-018** (no MCP tools for consumption data) | 🔴 **CD-011** (no engagement metrics accessible) | ⚪ |
| **A7 Operations** | 🟢 diagnostics tools | 🟢 `diagnose_system` | 🟢 budget thresholds, gate config | 🟢 cost metering, audit, trace | 🟡 **CD-030, CD-023** (no Prometheus alert rules, cron health) | 🟢 configurable at runtime |

**B2 Direct User Heatmap Summary**: **21 green, 8 amber, 3 red, 5 gray cells**. Best-covered user type. Gaps concentrate at A6 Consumption (2/2 applicable red), A4 Monitor (engagement metrics), and A5 Monitor (channel health).

### 10.4 Heatmap: B3 Director User (Human Commander)

| Pipeline Stage | B3.1 Define | B3.2 Configure | B3.3 Monitor | B3.4 Iterate | B3.5 Scale |
|---------------|:---:|:---:|:---:|:---:|:---:|
| **A1 Collection** | 🟢 `add_domain`, `add_source` | 🟢 `activate_domain`, source health | 🟡 **CD-013** (no collection pipeline dashboard) | 🟢 sources editable | 🟡 **CD-003, CD-004** (no rate limiting / multi-source orchestration) |
| **A2 Extraction** | 🟢 custom extraction schema | 🟢 per-domain LLM config | 🟡 (no extraction quality dashboard) | 🟢 gates configurable | 🟡 (no batch processing batching) |
| **A3 Knowledge Base** | 🟢 Wiki append-only per spec | 🟢 promote/reject Draft CLI | 🟡 (no KB quality dashboard) | 🟢 items flaggable, deprecatable | 🔴 **CD-001, CD-042** (no multi-tenant KB isolation) |
| **A4 Products** | 🟢 product types defined (RAW/PROCESSED) | 🔴 **CD-031** (no per-product access level gating) | 🔴 **CD-013, CD-017** (no product delivery dashboard) | 🔴 **CD-016** (no A/B testing, no template iteration) | 🔴 **CD-015** (no product catalog scaling strategy) |
| **A5 Delivery** | 🟢 10 delivery channels | 🟢 channel config via webhook/schedule | 🟡 **CD-007, CD-013** (no unified delivery dashboard) | 🟢 adapters modular | 🟡 **CD-007, CD-015** (no SLA dashboard, no channel auto-failover) |
| **A6 Consumption** | 🔴 **CD-041** (no consumption KPIs defined) | ⚪ | 🔴 **CD-011, CD-013** (no consumption dashboard) | 🔴 **CD-040** (no data-driven iteration loop) | 🔴 **CD-041** (no consumption-based scaling signals) |
| **A7 Operations** | 🟡 **CD-014** (no RPO/RTO defined) | 🟢 config via MCP/CLI | 🟡 **CD-013** (no live operations dashboard) | 🟡 **CD-014** (doctor exists, no structured DR runbook) | 🔴 **CD-015** (no horizontal scaling, SQLite single-node) |

**B3 Director User Heatmap Summary**: **9 green, 10 amber, 7 red, 1 gray cell**. This is the **most gap-dense user type at scale**. The Director can operate today but cannot scale. A4 Products and A6 Consumption are near-total red zones.

### 10.5 Aggregate Heatmap by Pipeline Stage

| Pipeline Stage | Green | Amber | Red | Gray | **Health Score** |
|---------------|:-----:|:-----:|:---:|:----:|:----------------:|
| **A1 Collection** | 8 | 3 | 0 | 6 | 🟢 **89% delivered** (14/17 applicable cells green/amber) |
| **A2 Extraction** | 8 | 3 | 0 | 6 | 🟢 **89% delivered** |
| **A3 Knowledge Base** | 7 | 3 | 1 | 6 | 🟡 **76% delivered** (1 red: no multi-tenant isolation at scale) |
| **A4 Products** | 3 | 3 | 7 | 4 | 🔴 **35% delivered** (7/13 applicable cells red) |
| **A5 Delivery** | 6 | 5 | 1 | 5 | 🟡 **76% delivered** (1 red: no cancellation receipt for B1.6) |
| **A6 Consumption** | 0 | 0 | 8 | 9 | 🔴 **0% delivered** — zero green cells, all applicable are red |
| **A7 Operations** | 5 | 4 | 2 | 6 | 🟡 **71% delivered** (2 red: scaling + DR at scale) |
| **TOTAL** | 37 | 21 | 19 | 42 | Overall: **62% fully/partially delivered** |

### 10.6 Critical Heat Zones (Priority Action)

| Zone | Cells Affected | Gaps | Priority | Action |
|------|---------------|------|----------|--------|
| **🔥 A6 Consumption (all users)** | B1.4, B1.5, B1.6, B2.4, B2.5, B3.1, B3.3, B3.4, B3.5 | CD-011, CD-012, CD-018, CD-040, CD-041 | 🔴 P0 | Build consumption tracking foundation. This is the **most critical blank space** — without it, there is no feedback loop for product iteration, no engagement data for retention, and no business metrics. |
| **🔥 A4 Products — B1 End User lifecycle** | B1.1, B1.2, B1.3, B1.5, B1.6 | CD-008, CD-010, CD-017, CD-024, CD-031 | 🔴 P0 | Unify subscription→product gating. Build product catalog. Implement product lifecycle state machine. Without this, monetization model doesn't function. |
| **🔥 A4 Products — B3 Director scale** | B3.2, B3.3, B3.4, B3.5 | CD-013, CD-016, CD-017, CD-031 | 🔴 P0 | Build product delivery dashboard. Enable A/B testing. Implement scaling strategy for product catalog. |
| **🟡 A3 Knowledge Base — B3 Scale** | B3.5 | CD-001, CD-042 | 🟡 P1 | Multi-tenant KB isolation. Single SQLite is a scaling bottleneck for multi-customer deployments. |
| **🟡 A5 Delivery — B1 Churn** | B1.6 | CD-009 | 🟡 P1 | Cancellation receipt + churn data export. End-of-lifecycle UX gaps. |
| **🟡 A7 Operations — B2/B3 Monitor** | B2.5, B3.3 | CD-007, CD-013, CD-023, CD-030 | 🟡 P1 | Channel health monitoring, live ops dashboard, cron health, logging consistency. |

> **Heatmap interpretation guide**: See [`cross-dimensional-gap-catalog.md` §4](./cross-dimensional-gap-catalog.md#section-4-priority-fix-matrix) for the priority matrix that assigns P0/P1/P2/P3 to each CD-NNN gap, and §5 for the phased implementation roadmap.

---

## Section 11: Market-Report Matrix Coverage Analysis & Scope Boundaries

> **Date**: 2026-07-27
> **Method**: Cross-reference of 48 user-information scenarios extracted from 3 market reports (Reuters Institute Digital News Report 2026, Reuters Institute Journalism Media and Technology Trends 2026, Global Information Payment Research Report 2024-2026) mapped to AutoInfo's D1 (user type) × D2 (lifecycle) dimensions.
> **Status**: Delivered to and clarified by director user. Scope boundaries below are binding.

### 11.1 Scenarios Identified

48 distinct scenarios were extracted from the 3 market reports and mapped against AutoInfo's capability matrix. Each scenario represents a real-world "user with information need" pattern that the platform should support:

| Source Report | Scenarios Extracted |
|--------------|-------------------|
| Reuters Institute Digital News Report 2026 | 22 |
| Reuters Institute Journalism Media and Technology Trends 2026 | 14 |
| Global Information Payment Research Report 2024-2026 | 12 |
| **Total (deduplicated)** | **48** |

### 11.2 Coverage Summary

| Coverage Level | Count | Percentage |
|---------------|-------|------------|
| 🟢 Fully covered | 29 | 60% |
| 🟡 Partially covered | 6 | 13% |
| 🔴 Not covered / missing | 13 | 27% |
| **Total** | **48** | **100%** |

**Effective coverage**: 35/48 (73%) at least partially addressed. 13/48 (27%) represent genuine gaps where no AutoInfo capability maps to the user scenario.

### 11.3 Root-Cause Analysis of Missing Scenarios

The 13 missing scenarios fall into 4 root-cause categories:

| Root Cause Category | Count | Missing Scenarios |
|--------------------|-------|------------------|
| **1. No video/audio format pipeline** — Market reports show strong user demand for audio (14% preference, 42% WTP for news podcast) and video (72% watch news video in US, short video dominates Chinese market). AutoInfo is text-only. | 4 | End-user consumes short-video summaries; End-user listens to audio digest; Creator produces video digest; Publisher distributes via video format |
| **2. Business model diversity unaddressed** — Reports document diverse monetization models (agent revenue share, token/credit economy, effectiveness-based pricing, API licensing, bundled content, human-review premium) that AutoInfo cannot support without a working tier/pricing model. These are acknowledged but not solutioned. | 5 | Enterprise buyer negotiates flat-fee bulk data license; Publisher opts into agent revenue-share pool; Institutional buyer pays per-seat for team access; Platform operator embeds AutoInfo as white-label; Content licensor negotiates per-API-call usage billing |
| **3. Consumption/engagement feedback loop absent** — No tracking of what end users actually read, engage with, or churn from. | 3 | Publisher measures newsletter open-rate to optimize timing; Director monitors per-topic consumption to adjust domain strategy; Platform operator detects engagement drop to prevent churn |
| **4. Agent-mediated discovery unbuilt** — No product catalog or storefront that agents can discover and subscribe to on behalf of end users. | 1 | Agent discovers and subscribes to products on behalf of end-user |

### 11.4 Scope Boundaries (Per Director-User Clarification)

The following scope decisions are binding for all gap analysis and implementation planning:

| Scope Decision | Status | Rationale |
|---------------|--------|-----------|
| **Unified end-user model** — All customer types (individual consumer, creator, publisher, enterprise buyer, institutional buyer, platform operator, content licensor) share the single "end user" lifecycle. Agent delegates are included. | ✅ Adopted | AutoInfo is a general solution. Persona differentiation is handled by domain/topic configuration and `target_audience` output parameter, not by user profile segmentation. |
| **Video is a confirmed gap** | 🔴 Documented as MG-1 | Requires TTS + video generation pipeline; high engineering cost. Tracked as future data format gap in §11.6. No implementation planned. |
| **Business model diversity acknowledged** | 🟡 Listed as gaps (MG-3), no solution built | The 5 missing business-model scenarios are documented as gaps in §11.3 category 2. AutoInfo's architecture supports plug-in pricing conceptually but the code has no differentiation. |
| **User segmentation / demographics / accessibility** | 🚫 Explicitly out of scope | No demographic persona logic will be added. AutoInfo treats all end users identically regardless of age, location, role, ability, or accessibility need. Accessibility (screen reader, font size, color contrast) is deferred to the delivery channel's own capabilities. |
| **Agent-as-operator (B2)** | ✅ Confirmed correct | The B2 Direct User (Agent) model — where an AI agent operates AutoInfo on behalf of the end user — is the intended operating model. No change needed. |

### 11.5 Heatmap Impact

The 13 missing scenarios reinforce the existing heatmap (§10) assessment with market-evidence weight:

| Cell | Previous Verdict | Updated Verdict | Change |
|------|----------------|-----------------|--------|
| A4 Products — B1.1 Discover | 🔴 CD-010 (no catalog) | 🔴 Expanded — no agent-discoverable product catalog either (scenario #4: agent-mediated discovery missing) | Confirmed, market-evidence weighted |
| A5 Delivery — B1.4 Consume | 🟡 delivers but no read tracking | 🔴 Expanded — format gaps (no video/audio) are delivery failures for 4 scenarios | 🔻 Downgraded (market evidence of demand) |
| A6 Consumption — All cells | 🔴 0% delivered | 🔴 Confirmed — all 3 engagement-feedback scenarios impossible | Confirmed |
| A4 Products — B3.2 Configure | 🔴 CD-031 (no per-product gating) | 🔴 Expanded — business model diversity adds 5 more missing configurations | Confirmed, market-evidence weighted |

**Overall stance unchanged**: A6 Consumption remains 0% delivered, A4 Products remains critically weak. The matrix analysis validates the existing assessment with independent market data.

### 11.6 Tracked Future Gaps (Informative)

| Gap ID | Description | Source | Priority |
|--------|-------------|--------|----------|
| **MG-1** | **Video format pipeline** — No ability to collect, process, or deliver video content. Affects short-video summaries, video digests, and publisher video distribution. | Market reports: 72% US watch news video, 75.7% paid learning sessions are video, short video dominates Chinese market. | 🟡 P2 (confirmed gap, no immediate solution) |
| **MG-2** | **Audio format expansion** — Existing TTS covers digest/report MP3. No podcast feed (RSS with enclosures), no audio-first products, no audio-only subscription tier. | 14% preference, 42% WTP for news podcast. 400M+ podcasts distributed via RSS. | 🟡 P2 (partial foundation exists in TTS) |
| **MG-3** | **Business model plug-in** — No architecture for agent revenue share, token/credit economy, effectiveness-based pricing, API licensing, or bundled content. All 5 missing scenarios from category 2 are blocked by missing pricing model. | 5 distinct monetization variants in market reports. All blocked by C1/CD-024/CD-025. | 🔴 P0 (blocked by prerequisite: pricing model) |

> **Note**: These tracked gaps are informative only. No implementation is planned until the pricing/subscription gating foundation (CD-024/CD-025/CD-031) is fully built. See [`cross-dimensional-gap-catalog.md` §5](./cross-dimensional-gap-catalog.md#section-5-implementation-roadmap) for the phased roadmap.

---

## References

- `../dev/cross-dimensional-catalog.md` — Cross-Dimensional Gap Catalog (42 CD-NNN gaps, 119-cell matrix, priority matrix, 5-phase roadmap)
- `../dev/founder-expectations.md` — Expectations index
- `./founder-expectations-pre-split.md` — Full 57 expectations (2108 lines)
- `../dev/specs/expectations.md` — Extracted expectations catalog
- `./consumer-output-gaps.md` — 16 consumer-facing gaps (G1-G16)
- `./implementation-gaps.md` — Feature-level implementation audit
- `../dev/specs/mcp-tools.md` — MCP tool specifications (114 tools)
- `AGENTS.md` — Agent operating model + status claims
- `../dev/specs/delivery.md` — End-user lifecycle, delivery channels, product lifecycle spec
- `../dev/specs/pipeline.md` — KB pipeline rules, collection pipeline spec
