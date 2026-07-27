# AutoInfo — Implementation Gap Audit

> **Date:** 2026-07-26
> **Method:** Cross-reference AGENTS.md, founder-expectations.md, and MCP tool schema against actual code
> **Scope:** F01-F57 expectations, MCP tool coverage, CLI-CLAIMED vs ACTUAL capabilities
>
> **Correction (2026-07-26):** This doc was generated 2026-07-26 and corrected 2026-07-26 after code verification. Items AU6, AU7, AU8, AU9, AU10, AU13, AU14, AU15 were found to be already implemented in the v1.6 gap audit fix plan. AU11 remains partial (`get_entry_history` exists, `compare_versions` missing). See annotations below.

---

## Executive Summary

Audited 57 expectations + 2 additional claimed capabilities. Results:

| Status | Count | |
|--------|:-----:|---|
| ✅ Fully Implemented | 19 | Health check, CEFR, source health, rate_item, KB search, entry history, stale handling, budget alerts, domain decay, cross-collection dedup, per-domain TTL, LLM fallback, relation types, soft-delete restore, etc. |
| 🟡 Partially Implemented | 9 | Some tests pass but missing edge cases, coverage gaps |
| ❌ Not Implemented | 12 | Includes expectations with no code, no tests, no MCP tools |
| ⚪ Deferred / Not Needed | 2 | Multi-user auth (F38-F40 pushed to v2+), CLI async flow (legacy) |
| ❓ Not Assessed | 15 | Model classes, dedup, etc. (detailed gap analysis in `docs/archive/gap-analysis-v1.6.md`) |

> **Note:** This audit supersedes the deprecated `docs/archive/gap-analysis-v1.6.md` which covered F01-F57 at a lower granularity. This document covers new analysis including MCP-CLAIMED vs ACTUAL capability gaps.

---

## Section 1: ✅ Fully Implemented (19)

These capabilities work correctly as documented — code exists, tests pass, MCP tools registered.

| # | Capability | Evidence |
|---|-----------|----------|
| 1 | **`health_check`** | MCP tool registered, returns `{"status": "ok"}` |
| 2 | **`list_available_models`** | List LLM models from config |
| 3 | **`CEFR classification`** | `cefr.py` + MCP tool, classifies EN/ZH/JA |
| 4 | **`get_source_health`** | Source health metrics per source |
| 5 | **`rate_item`** | Manual relevance/quality rating |
| 6 | **`search_knowledge_base`** | Hybrid + Vector + Faceted search modes |
| 7 | **`get_kb_entry`** | Single KB entry retrieval |
| 8 | **`list_summaries`** | Summary listing by domain/topic |
| 9 | **`list_kb_tier`** | List entries by KB tier |
| 10 | **`reindex_kb`** | Rebuild vector index |
| 11 | **`classify_cefr`** | MCP tool + backend |

---

## Section 2: 🟡 Partially Implemented (9)

These capabilities exist but are incomplete — missing edge cases, MCP tool wiring, or test coverage.

| # | Capability | What's Missing |
|---|-----------|---------------|
| 1 | **`process_collection` async** | CLI `process --async` flag exists but MCP `_handle_process_collection` not wired for async returning `job_id`. Code reads cached raws in blocking fashion. |
| 2 | **Bulk `add_source`** | `add_source` works for single. MCP `add_sources` exists (`server.py:297`) but only iterates`add_source` in a loop — no batch validation, no dry-run flag. |
| 3 | **`suggest_keywords` MCP tool** | `keywords.py` has `suggest_keywords()` using LLM but MCP schema `_handle_suggest_keywords` at `server.py:1985` returns raw text without structured keyword response model. |
| 4 | **`get_effective_llm_config`** | MCP tool exists but returns flat config; doesn't show fallback chain resolution or per-model override hierarchy. |
| 5 | **`get_collection_progress`/`get_processing_progress`** | Both support `job_id` polling for async flows, but legacy domain-only path (`domain="medical"`) still works. Not all tools expose `async=true` flag. |
| 6 | **`get_entry_history`/`restore_entry_version`** | Versioning tools exist but there's no `compare_versions` MCP tool. Git SHA tracking works but diff generation unbounded — no `--short` flag. |
| 7 | **`flag_for_knowledge_base`** | Promotes Raw → Draft pipeline. But no `batch_flag` MCP tool. No `bulk_promote` flow. |
| 8 | **Digest delivery with cron** | `add_schedule` + `send_email_digest` exists. But `get_schedule_status` or `get_delivery_log` MCP tools are missing. Scheduled digest status is hidden. |
| 9 | **`authorize_end_user` / subscription flow** | EndUserProfile + Subscription models exist (`end_user.py`, `subscription.py`). MCP tools exist. But no payment integration, no trial expiration enforcement, no subscription gating in output delivery. |

---

## Section 3: ❌ Not Yet Implemented (12)

### 3A: No MCP Tool Registered (7)

These backend capabilities exist but are inaccessible via MCP — breaking the agent-first architecture.

| # | Capability | Backend Code | MCP Tool Missing | Impact |
|---|-----------|-------------|-----------------|--------|
| AU1 | **RSS feed product output** | `output.py:324-331` (`export_kb` supports `format="rss"`) | Not in `list_output_templates`; MCP schema enum excludes `"rss"` | Agent cannot request RSS feed |
| AU2 | **Webhook push with HMAC verification** | `webhooks.py:67-89` (HMAC SHA256) | No `register_webhook_secret` or `verify_webhook_signature` tool | Agent cannot validate webhooks |
| AU3 | **Digest delivery via cron** | `cron.py` + `email_sender.py` | No `get_schedule_status`, `list_active_deliveries`, `get_delivery_log` tools | Agent cannot monitor delivery |
| AU4 | **Trial period management** | `end_user.py:318` (`TRIAL_DAYS`) | No `activate_trial`, `extend_trial`, `check_trial_expiry` tools | Agent cannot manage free trials |
| AU5 | **RSS feed delivery** | None (no `RSSDeliveryChannel`) | Not registered | Agent cannot add RSS as delivery channel |
| AU11 | **Versioned re-collection with bump** (F50) ⚠️ PARTIAL | `get_entry_history` + `restore_entry_version` exist | `compare_versions` MCP tool still missing | Agent can view history but cannot diff versions. Moved to Wave 2. |
| AU12 | **Prometheus metrics scraping** | `api/server.py` exposes `/metrics` | No MCP tool for metrics retrieval | Agent cannot fetch metrics through MCP |

### 3B: No Backend Implementation (5)

These capabilities don't exist at all — no code, no tests, no MCP tools.

| # | Capability | Expectation | Reason |
|---|-----------|------------|--------|
| AU16 | **End-user portal self-service** | F38-F40: Portal access | CLI `autoinfo enduser` exists but no MCP tool for self-service actions (view history, modify preferences). |
| AU17 | **End-user preference profile** | F37: User profiles | `EndUserProfile` exists but no `get_output_preferences`, `update_preferences` MCP tools. |
| AU18 | **Consumer output personalization** | Consumer demand | `generate_digest`/`generate_report` have no `target_audience` parameter (only Tutorial/Presentation do). No role-aware filtering. |
| AU19 | **Billing/payment integration** | F42 (deferred v2+) | No Stripe, Alipay, WeChat Pay integration. `Subscription` model exists but payment fields are stubs. |
| AU20 | **End-user notification delivery** | F36 delivery chain | No `send_to_enduser` MCP tool. End-user delivery requires human CLI intervention. |

---

## Section 4: ⚪ Deemed Not Needed (2)

| # | Capability | Decision | Alternative |
|---|-----------|----------|-------------|
| DN1 | **Multi-user auth/teams** | F38-F40 pushed to v2+ | Agent operates via `user_id` field on entries; no auth enforcement |
| DN2 | **CLI `init` for agent workflows** | MCP `init_project` preferred | AGENTS.md instructs agents to use `init_project` MCP tool; CLI `init` for humans only |

---

## Section 5: CLI-CLAIMED vs ACTUAL (AGENTS.md Mismatches)

AGENTS.md claims capabilities that don't match reality.

| AGENTS.md Claim | Actual State | Risk |
|----------------|-------------|------|
| "114 tools across 32 categories" | ✅ Count verified from MCP schema | Low |
| "**Digest**: Markdown/HTML/JSON" | ✅ All 3 supported | None |
| "**Tutorial**: Markdown/HTML/JSON" | ❌ Only markdown. `output.py:2695`: "only markdown is currently supported" | Medium — MCP schema lies to agent |
| "**Report**: Markdown/HTML/JSON/PDF" | ❌ Only markdown and JSON. PDF not implemented for reports (only for `export_kb`) | Medium — schema mismatch |
| "**Presentation**: Markdown/HTML" | ❌ Only markdown. `_generate_presentation` returns only markdown | Medium — schema mismatch |
| "**Export**: Markdown, JSON, SQLite, PDF, CSV, GraphML" | ⚠️ `export_kb()` supports: markdown, json, sqlite, pdf, csv, graphml — but MCP enum only lists `markdown, json, sqlite, pdf, csv` (missing `graphml`) | Low — MCP schema omission |
| "**RSS** as delivery channel" | ❌ No `RSSDeliveryChannel` class. `export_kb` supports RSS format but it's hidden from MCP schema | Medium — feature invisibility |
| "**Push notifications** (APNS/FCM)" | ❌ No push notification framework | Medium — claimed but absent |
| "**Stale content handling**" (listed in status table) | ✅ DONE (corrected): `kb.py:3133-3227` — `is_stale` flag, search demotion, `include_stale` param | None — was inaccurate, now verified |
| "**Versioned re-collection**" (listed in status table) | ⚠️ PARTIAL: `get_entry_history` + `restore_entry_version` exist; `compare_versions` still missing | Low — mostly works, one tool gap |
| "**Domain decay metrics**" (listed in status table) | ✅ DONE (corrected): `kb.py:3601` `get_domain_decay()`, MCP tool at `server.py:4239` | None — was inaccurate, now verified |
| "**Cross-collection dedup & merge**" (listed in status table) | ✅ DONE (corrected): `find_similar_items` + `merge_items` MCP tools at `server.py:3294/3322` | None — was inaccurate, now verified |

---

## Section 6: MCP Tool Schema Gaps

Tools in AGENTS.md that don't exist in MCP schema:

| Tool Category | Missing Tool | AGENTS.md Claim |
|--------------|------------|----------------|
| KB Relations | ~~No `merge_items`~~ ✅ EXISTS (`server.py:3294`) | "KB merge" (for dedup) — corrected |
| KB Relations | ~~No `find_similar_items`~~ ✅ EXISTS (`server.py:3322`) | "Cross-collection dedup & merge" — corrected |
| KB Versioning | No `compare_versions` | "Versioned re-collection" — still missing (AU11 partial) |
| KB Monitor | ~~No `get_domain_decay`~~ ✅ EXISTS (`server.py:4239`) | "Domain decay metrics" — corrected |
| Quality Gate Config | No `get_gate_config` (✅ EXISTS) | Already found |
| Cron | No `get_schedule_status` | "Digest delivery via cron" |
| Delivery | No `get_delivery_log` | "Digest delivery via cron" |
| End User | No `send_to_enduser` | "End-user notification delivery" |
| End User | No `update_preferences` | "End-user preference profile" |
| End User | No `activate_trial` | "Trial period management" |
| End User | No `check_trial_expiry` | "Trial period management" |
| Keywords | No structured `suggest_keywords` return | "suggest_keywords" (returns raw text) |

---

## Section 7: Priority Fix Roadmap

### Wave 1: Documentation Accuracy (1 hour)
- [ ] Fix AGENTS.md format claims (tutorial, report, presentation — only markdown supported)
- [ ] Fix AGENTS.md status table (stale content, versioned re-collection, domain decay, dedup & merge)
- [ ] Add `graphml` to MCP export format enum
- [ ] Add `rss` to MCP export format enum

### Wave 2: MCP Tool Registration (4-6 hours)
- [x] ~~Register `find_similar_items` + `merge_items` (F53)~~ ✅ DONE (`server.py:3294/3322`)
- [ ] Register `compare_versions` (F50) — still missing (AU11 partial)
- [x] ~~Register `get_domain_decay` (F52)~~ ✅ DONE (`server.py:4239`)
- [ ] Register `get_schedule_status`, `get_delivery_log`
- [ ] Register `send_to_enduser`, `activate_trial`, `check_trial_expiry`
- [x] ~~Register `mark_stale`, `list_stale` (F51)~~ ✅ DONE (stale handling in `kb.py:3133-3227`)

### Wave 3: Backend Implementation (1-2 weeks)
- [x] ~~F04: Wire LLM fallback chain into `_call_llm()`~~ ✅ DONE (`llm.py:274-305`)
- [x] ~~F19: Define `RELATION_TYPES` enum~~ ✅ DONE (`kb.py:39-54`, 11 types)
- [x] ~~F47: Soft-delete + restore + GDPR export~~ ✅ DONE (`kb.py:3457/3511`, MCP `server.py:5376/5387`)
- [x] ~~F49: `ttl_days` in `DomainConfig` + freshness scoring~~ ✅ DONE (`config.py:97`)
- [ ] F50: Automatic version bump + `compare_versions` backend — still missing (AU11)
- [x] ~~F51: Stale content marking + search demotion + digest exclusion~~ ✅ DONE (`kb.py:3133-3227`)
- [x] ~~F52: Decay metrics computation + grade (Green/Yellow/Red)~~ ✅ DONE (`kb.py:3601`)
- [x] ~~F53: TF-IDF similarity + LLM-assisted merge~~ ✅ DONE (`quality.py` + MCP tools)
- [x] ~~F45: Cost/budget triggers in alert rules~~ ✅ DONE (`server.py:2801/2843`)
- [ ] F37: End-user preference profile MCP tools

### Wave 4: Consumer-Facing Gaps (deferred from gap audit)
- [ ] Audio output (TTS pipeline)
- [ ] Agent-native output format
- [ ] Monetization pipeline (Stripe)
- [ ] Role-aware digest/report (`target_audience`)
- [ ] Delivery channel expansion (RSS, Push)

---

## References

- `docs/dev/specs/expectations.md` — Full F01-F57 expectation catalog
- `docs/dev/specs/mcp-tools.md` — MCP tool specifications
- `docs/dev/specs/quality-gates.md` — G0-G5, D1-D3 gate specifications
- `docs/dev/specs/pipeline.md` — Pipeline specifications
- `docs/dev/specs/delivery.md` — Delivery channel specifications
- `docs/archive/gap-analysis-v1.6.md` — DEPRECATED predecessor (2026-07-25)
- `docs/dev/consumer-output-gaps.md` — Consumer-facing output gap analysis (2026-07-26)
- `AGENTS.md` — Agent operating model + capability claims
- `src/autoinfo/mcp/server.py` — MCP tool registry (114 tools)
- `src/autoinfo/output.py` — Output generation (3289 lines)
- `src/autoinfo/delivery/__init__.py` — Delivery channel ABC + channels
