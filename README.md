# AutoInfo

**Universal information tracking and knowledge base platform.**

Configure sources and topics. AutoInfo handles the rest: automated collection,
LLM-based structured extraction, summarization, and a queryable knowledge base.

> "AutoInfo is your information assistant — not helping you search, but
> automating the entire pipeline from collection to knowledge curation."
>
> Domain-agnostic. Agent-native. BYOK.

## Features

- **Multi-source collection** — RSS, REST APIs (PubMed E-utilities), web pages (trafilatura + Playwright), webhook (HMAC), email (IMAP), PDF (PyMuPDF)
- **Domain management** — Add, remove, list, activate/deactivate domains via CLI and MCP tools
- **LLM-powered extraction** — TL;DR, key points, entity extraction, relevance scoring, custom field extraction
- **Knowledge base (4-tier pipeline)** — 4-tier pipeline: Inbox → Raw → Draft → Wiki (Markdown + SQLite), with git versioning and `[[wiki links]]`
- **KB import** — Import content from 4 formats (PDF, Markdown, HTML, JSON) directly into 01-Raw
- **Hybrid search** — FTS5 keyword + sqlite-vec vector embeddings, faceted filtering
- **REST API** — Full CRUD over HTTP (FastAPI, port 8741), no auth (localhost security)
- **Web UI Dashboard** — Bootstrap 5, collection stats, KB search, source health overview
- **CEFR classification** — LLM-based EN/ZH/JA reading level scoring for language learning
- **Output formats** — Markdown, JSON, PDF, **HTML** (digest/report via Jinja2 + LLM, presentation via Reveal.js CDN)
- **Translation QA pipeline** — 5 lite quality gates, back-translation verification, multi-round refinement, terminology guardrails, composite quality scoring
- **Email sending** — SMTP-based digest delivery (manual and cron-scheduled)
- **Webhook push** — Per-item webhook notification on collected content
- **Quality gates** — 6 hard/soft gates (G0-G5: G0/G4 hard, G1-G3/G5 soft) + 3 delivery gates (D1-D3). Retry-first, block-last philosophy.
- **Product delivery** — Two product types: RAW (API feeds, webhook streams, bulk export) and PROCESSED (scheduled digests, thematic reports, alert streams via SMTP/webhook)
- **Multi-channel delivery** — 13 delivery channels: SMTP, Webhook, REST API, File Export, Discord, Telegram, WeChat Work, WeChat OA, DingTalk, FeiShu, RSS, Social Publish, Push. Email as mandatory fallback. Per-channel rate limiting and message formatting.
- **End user lifecycle management** — EndUserProfile + Subscription CRUD. Lifecycle state machine: trial → active → suspended → cancelled. Configurable trial and grace periods, transition hooks.
- **Delivery reliability** — Per-subscription delivery log with SLA tracking (P0 ≤5min, P1 ≤30min, P2 ≤2hr). Retry chain with fallback. Never silently drop products.
- **End user self-service portal** — CLI-based portal for delivery preference management, product archive access, delivery history browsing.
- **Immutable audit logging** — Append-only audit log for all operations (MCP, CLI, pipeline). Queryable via MCP tool and CLI. Full actor/resource/action tracking.
- **Structured pipeline logging** — JSON structured logging per pipeline event with daily rotation. Configurable log levels per stage. Filter and tail via CLI.
- **Per-item traceability** — UUID trace_id propagated from collection through delivery. CLI displays full item journey: sources, gates, KB entries, delivery status.
- **Cost governance** — Internal cost metering (LLM tokens, storage, API calls) with per-domain/per-user allocation. Cost dashboard with daily trends, top models, budget alerts. CLI and MCP tools.
- **Budget alerts & cost control** — Threshold-based alerts (absolute, rate-based, projected overrun). Auto-remediation actions per alert. Configurable via MCP tools.
- **Source ToS compliance** — Source classification (Open/Licensed/Restricted/Sensitive) with per-tier output controls. Attribution in generated outputs. Compliance checkpoint at G1 gate.
- **Data deletion & retention** — Soft-delete with restore within retention window. Retention by subscription tier. 30-day auto-cleanup. GDPR-compliant data export. Permanent purge only via explicit flag.
- **Knowledge lifecycle management** — Per-domain TTL & freshness scoring. Versioned re-collection with structured diff. Stale content handling (demoted in search, excluded from digests). Domain decay metrics with proactive agent alerts. Cross-collection dedup & merge with LLM assistance.
- **Operational observability** — Enhanced diagnostics (`doctor --verbose`) with composite health score (0-100). Prometheus metrics export. Per-domain error rates, latency p95/p99, LLM spend summaries.
- **Agent-native** — 139 MCP tools across 34 categories. Agent operates, human directs.
- **Self-discovering tool count** — `get_tool_count` MCP tool returns dynamic tool count, no more hardcoded numbers
- **LLM configuration tool** — `configure_llm` MCP tool for agent-oriented BYOK setup (provider, model, api_key, base_url)
- **Agent-oriented error responses** — Unified dual-format error responses (flat + envelope) for backward-compatible consumer migration
- **Cross-domain search** — `search_knowledge_base()` searches all active domains when domain is omitted
- **Domain-less collection** — `collect_sources()` collects from all active domains when no domain specified
- **Agent-native tutorial/presentation/export** — Tutorial, presentation, and KB export support `format="agent"` for JSON-LD output
- **Persistent job state** — Collection/processing job state survives server restarts via SQLite-backed storage
- **Persistent agent callbacks** — Agent callback registration persists across restarts via SQLite
- **Batch CEFR classification** — `cefr_batch` MCP tool for classifying multiple texts at once
- **Audit log MCP tool** — `query_audit_log` MCP tool for programmatic audit log access
- **Knowledge graph export** — `knowledge_graph_export` MCP tool for graph-structured KB export
- **Cost dashboards & allocation MCP tools** — `cost_dashboard` and `cost_allocation` MCP tools for cost governance
- **RSS feed MCP tool** — `get_feeds` MCP tool for RSS feed retrieval with RSS XML output
- **Hard-delete purge** — `soft_delete_entry(entry_id, purge=True)` for permanent entry removal
- **Fine-grained process control** — `process_collection()` exposes `check_factual` and `check_translation` flags
- **Topic grouping** — `topic_group_add`/`topic_group_remove` MCP tools for organizing topics into groups
- **Email config MCP tool** — `email_config` MCP tool for email configuration management
- **Cache cleanup MCP tool** — `clean_cache` MCP tool for temporary artifact cleanup
- **BYOK** — Bring your own LLM keys. Multi-provider via LiteLLM/OpenRouter.
- **Domain-agnostic** — 9 demo domains (medical, AI commercial, financial/business intelligence, tech/AI/developer, language learning, online video, financial news, online education, legal compliance). Any field with paying customers.
- **Subscription-ready** — Stripe integration with webhook endpoint (signature verification), stripe-mock dev setup, freemium gating, and usage metering
- **Subscription tiers** — Free, Premium, and Enterprise tiers with per-tier channels, domains, products, and platform limits on the Subscription model
- **Access control** — `check_access()` fast path gates content by tier (free always allowed, premium/enterprise require active paid subscription). Freemium gating (G15).
- **Consumption tracking** — `ConsumptionEvent` auto-record on digest/report delivery (view/open/click events) with SQLite-backed store
- **Automated notifications** — Trial-ending reminders (3-day window) and content-ready notifications dispatched to end users
- **Channel health monitoring** — `get_channel_health` MCP tool checks all 13 delivery channels (smtp, webhook, rest_api, file_export, discord, telegram, wechat_work, wechat_oa, dingtalk, feishu, rss, social_publish, push) with latency and error status
- **Cron health monitoring** — `autoinfo cron health` CLI with heartbeat tracking and missed-schedule detection
- **SQLite backup** — `make backup` target plus `scripts/backup-db.sh` and `scripts/restore-db.sh` for automated KB and user-store backups (keeps last 7)
- **16 new collectors** — DBLP, NYT, OpenAlex, Reddit, Spotify, YouTube, Bilibili, Apple Podcasts, Semantic Scholar, USPTO, plus paid AP API and Reuters MCP handlers (v1.6), plus SSRN, GDELT, HuggingFace/Kaggle, and Unpaywall/CORE (v1.8.1). 26 total collector handlers across all source types.
- **Bundle export** — `export_kb(format="bundle")` creates a ZIP archive containing JSON data, Markdown summary, YAML metadata, and a weasyprint-rendered PDF report (with graceful fallback)
- **Cross-domain reports & digests** — `generate_report()` and `generate_digest()` accept a `domains` parameter for multi-domain synthesis. New MCP tool `generate_cross_domain_report` for cross-domain analysis.
- **Specialized report types** — `report_type` parameter: `industry`, `competitive`, `trend`, `daily-briefing` — each with customized section structure and LLM prompts
- **Delivery schedule automation** — `add_delivery_schedule` MCP tool for cron-based periodic output generation + delivery. Integrates with `autoinfo cron run`.
- **Content simplification (E14)** — `simplify_content` MCP tool rewrites text to a target CEFR reading level (A1-C1) using LLM, with original/simplified level classification and verification flag
- **Single-article payment (E12)** — `create_checkout_session` supports `mode="payment"` for one-time article purchases; `check_access(article_id=...)` fast path verifies article entitlement grants
- **Source credibility score (E9)** — Deterministic `source_score` (0-100) derived from quality tier, persisted on KBEntry, surfaced in search results and G1 gate details
- **RAW product variants (E11)** — RAW product carries `variants: ["api_feed", "webhook", "bulk_export"]` field distinguishing the three RAW delivery modes
- **Podcast RSS publishing (C11)** — RSS 2.0 delivery channel with `<enclosure>` + `itunes:*` namespace for podcast feed generation; audio output auto-persists MP3 to disk
- **Validated source types** — `VALID_SOURCE_TYPES` frozenset (25 types) as single source of truth for source type validation across MCP and CLI

## Status

| Component | Status |
|-----------|--------|
| Config system | ✅ LLM task config, per-task model, fallback chains, schema versioning |
| CLI | ✅ 23 command groups (init, doctor, collect, process, status, summaries, sources, topics, domain, audit, kb, output, cron, knowledge, cefr, email, keywords, clean, cost, billing, enduser, portal, trace) |
| Collection | ✅ 26 collector handlers (PubMed, arXiv, Semantic Scholar, CrossRef, DBLP, OpenAlex, USPTO, NYT, RSS, Web, webhook, email, PDF, Reddit, Spotify, YouTube, Bilibili, Apple Podcasts, plus paid AP API and Reuters MCP, plus SSRN, GDELT, HuggingFace/Kaggle, Unpaywall/CORE), scheduled via crond |
| LLM extraction | ✅ Custom extraction fields, TL;DR, key points, entities, G4 factual consistency, token usage tracking |
| Translation QA pipeline | ✅ 5 lite quality gates, back-translation verification, terminology guardrails, composite scoring, translator-qa-skill |
| Quality gates | ✅ 6 hard/soft (G0-G5: G0/G4 hard, G1-G3/G5 soft) + 3 delivery gates (D1-D3) + per-domain config |
| KB pipeline | ✅ 4-tier KB pipeline (00-Inbox → 01-Raw → 02-Draft → 03-Wiki; note: 00-Inbox is scaffolded but deprecated — 01-Raw is the sole entry point), git versioning + SHA tracking |
| KB import | ✅ 4 formats (PDF, Markdown, HTML, JSON) → 01-Raw via `import_kb` MCP tool |
| Search | ✅ Hybrid (FTS5 keyword + sqlite-vec vector), faceted (7 filters) |
| Q&A | ✅ FTS5 + LLM synthesis with source citations |
| Output generation | ✅ Digest (Markdown/HTML/JSON/PDF), report (Markdown/JSON/HTML/Audio/Agent), tutorial (Markdown), presentation (Markdown) (Jinja2 + LLM, Reveal.js CDN) |
| Agent-native JSON output | ✅ `format="agent"` returns JSON-LD (`@type: KnowledgeDigest`) for LLM re-consumption |
| Audio output | ✅ TTS-rendered digest/report as MP3 (OpenAI TTS) via `format='audio'` |
| Translation | ✅ LLM-based source→target |
| Knowledge graph | ✅ Entity extraction + relation discovery |
| REST API | ✅ FastAPI CRUD (port 8741, /api/v1/entries, /health, /dashboard) |
| Web UI Dashboard | ✅ Bootstrap 5, collection stats, KB search, source health |
| MCP server | ✅ 139 tools across 34 categories |
| Domain management | ✅ `add_domain`/`remove_domain` MCP tools, `autoinfo domain` CLI (add/list/show/remove/activate/deactivate) |
| Webhook push | ✅ Per-item webhook notification on collection via `set_domain_webhooks`/`get_domain_webhooks` |
| Scheduled digest | ✅ Cron-based email digest delivery (SMTP + crontab schedule) |
| Agent alerting | ✅ Config-based alert rules with YAML persistence, check & dispatch via DeliveryChannel |
| Obsidian wiki links | ✅ `[[wiki links]]` in KB Markdown files |
| CEFR classification | ✅ LLM-based EN/ZH/JA (language-learning domain) |
| Email sending | ✅ SMTP sender (digest delivery) |
| Multi-channel delivery | ✅ 13 channels: SMTP, Webhook, REST API, File Export, Discord, Telegram, WeChat Work, WeChat OA, DingTalk, FeiShu, RSS, Social Publish, Push. Email as fallback. |
| End user lifecycle | ✅ Profile + Subscription CRUD. State machine: trial→active→suspended→cancelled. |
| Delivery reliability | ✅ Per-subscription DeliveryLog with SLA tracking, retry chain, fallback channels. |
| End user portal | ✅ CLI-based self-service: preferences, history, product archive. |
| Immutable audit log | ✅ Append-only audit log for all operations. MCP + CLI query with full filters. |
| Structured pipeline logging | ✅ JSON structured logging per pipeline event with daily rotation. |
| Per-item traceability | ✅ UUID trace_id from collection through delivery. CLI trace command. |
| Cost metering | ✅ LLM tokens, storage, API calls per domain/per user. Append-only cost log. |
| Cost allocation | ✅ Pro-rata, usage-based, and direct allocation strategies. |
| Cost dashboard | ✅ CLI + MCP dashboard with daily trends, top models, top sources. |
| Budget alerts | ✅ Threshold-based alerts with auto-remediation actions. |
| Source ToS compliance | ✅ Source classification (Open/Licensed/Restricted/Sensitive) with per-tier output controls, G1 compliance gate, D2 delivery gate, and attribution templates |
| Data deletion & retention | ✅ Soft-delete, restore, GDPR export, 30-day auto-cleanup, tier-based retention. |
| Per-domain TTL | ✅ Configurable freshness per domain: medical 180d, AI 30d, financial 7d, general 90d. |
| Versioned re-collection | ✅ Version tracking with structured diff between versions. |
| Stale content handling | ✅ Search demotion, digest exclusion, never deleted. |
| Domain decay metrics | ✅ Staleness ratio, avg TTL, decay grade (Green/Yellow/Red). |
| Cross-collection dedup & merge | ✅ URL dedup, cross-source similarity, LLM-assisted merge. |
| Enhanced diagnostics | ✅ `doctor --verbose` with health score, error rates, latency p95/p99. |
| Prometheus metrics | ✅ `http://localhost:8741/metrics` endpoint (configurable). |
| Multi-user foundation | ✅ user_id fields on entries (no auth/teams yet) |
| Export | ✅ Markdown, JSON, SQLite, PDF, CSV, GraphML |
| Schema versioning | ✅ DB schema version markers in SQLite |
| Subscription tiers | ✅ Free/Premium/Enterprise tiers with per-tier channels, domains, products, platform limits |
| Access control | ✅ `check_access()` fast path — free always allowed, premium/enterprise require active paid subscription (G15) |
| Consumption tracking | ✅ `ConsumptionEvent` auto-record on digest/report delivery (view/open/click), SQLite-backed store |
| Automated notifications | ✅ Trial-ending reminders (3-day window) + content-ready notifications to end users |
| Channel health monitoring | ✅ `get_channel_health` MCP tool — health + latency for all 13 delivery channels |
| Cron health monitoring | ✅ `autoinfo cron health` CLI — heartbeat tracking + missed-schedule detection |
| SQLite backup | ✅ `make backup` + `scripts/backup-db.sh` / `scripts/restore-db.sh` (keeps last 7 backups) |
| Job state persistence | ✅ SQLite-backed collection/processing job state survives restarts |
| Agent callback persistence | ✅ SQLite-backed agent callback registration survives restarts |
| Cross-domain search | ✅ search_knowledge_base searches all active domains when domain omitted |
| Domain-less collection | ✅ collect_sources collects from all domains when domain omitted |
| Hard-delete purge | ✅ soft_delete_entry purge flag for permanent removal |
| Fine-grained process control | ✅ process_collection check_factual/check_translation flags |
| Batch CEFR | ✅ cefr_batch MCP tool for multi-text classification |
| Audit log MCP | ✅ query_audit_log MCP tool for programmatic audit access |
| Knowledge graph export | ✅ knowledge_graph_export MCP tool |
| RSS feed MCP | ✅ get_feeds MCP tool with RSS XML format |
| Cache cleanup | ✅ clean_cache MCP tool |
| Topic grouping | ✅ topic_group_add/topic_group_remove MCP tools |
| Email config MCP | ✅ email_config MCP tool |
| Cost dashboard MCP | ✅ cost_dashboard MCP tool |
| Cost allocation MCP | ✅ cost_allocation MCP tool |
| Demo domains | ✅ medical-research, ai-commercial, financial-intelligence, tech-ai-developer, language-learning, online-video, financial-news, online-education, legal-compliance |
| Delivery schedules | ✅ add_delivery_schedule, list_delivery_schedules, remove_delivery_schedule MCP tools, cron-integrated |
| Test suite | ✅ ~2747 tests (approx; includes new collector + E12/E14/E9/C11 tests; 1 collection error pre-existing) |

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Initialize with demo domain
autoinfo init --demo medical-research

# Configure LLM key
export AUTOINFO_LLM_API_KEY="sk-..."
# See docs/dev/required-api-keys.md for the full list of API keys and environment variables

# Collect, process, and search
autoinfo collect --domain medical-research --topic "IVF breakthroughs" --limit 5
autoinfo process --domain medical-research
autoinfo kb search --query "embryo" --domain medical-research

# Generate output
autoinfo output digest --domain medical-research --period week
autoinfo output export --domain medical-research --format json
```

## Architecture

```
Sources (RSS/API/Web)
        │
        ▼
   autoinfo collect ───→ collections/ (raw JSON cache)
        │
        ▼
   autoinfo process
        │
   ├── LLMExtractor (custom fields, entities, G4)
   ├── Quality Gates (G1-G5)
   └── KBStore (4-tier)
        │
        ▼
   knowledge/{Raw|Draft|Wiki}/ ───→ Markdown + SQLite + FTS5 + vector embeddings
        │
        ├── Product Pipeline (RAW + PROCESSED)
        │     ├── RAW feeds (API, webhook, bulk export)
        │     └── PROCESSED (digests, reports, alerts, tutorials)
        │
        ├── Delivery Channels (SMTP, webhook, REST API, export)
        ├── autoinfo summaries list | status | kb search
        ├── autoinfo output digest | report | tutorial | export
        ├── REST API (FastAPI, port 8741)
         ├── autoinfo audit | trace | cost | enduser | portal  # v1.6 new
         └── MCP server (139 tools)
```

## CLI Commands (23 groups)

```bash
autoinfo init --name <project>      # Initialize project
autoinfo init --demo <domain>       # Initialize with demo domain
autoinfo doctor                      # System health check
autoinfo collect --domain <d> ...   # Collect from sources
autoinfo process --domain <d> ...   # LLM extraction + storage
autoinfo status                      # Collection stats
autoinfo summaries list|flag|show   # Browse summaries
autoinfo sources add|list|remove|test  # Source management
autoinfo topics add|list|remove     # Topic management
autoinfo domain add|list|show|remove|activate|deactivate|import  # Domain management (import --from-demo supports all 9 demo domains)
autoinfo audit query                # Query immutable audit log
autoinfo kb search|create-draft|promote|reject-draft|list-tiers|reindex
autoinfo output digest|report|tutorial|presentation|export|translate|list-templates  # report accepts --type --domains
autoinfo cron run|list-schedules|add-schedule|remove-schedule|install|uninstall|health  # health = heartbeat + missed-schedule detection
autoinfo cefr classify|batch        # CEFR text classification
autoinfo email send|config          # SMTP email sending
autoinfo keywords add|remove|list   # Keyword management
autoinfo knowledge graph            # Knowledge graph export
autoinfo clean                       # Clean temporary artifacts
autoinfo cost dashboard|allocation  # Cost tracking & allocation
autoinfo billing summary|usage|invoice  # Billing & usage overview
autoinfo enduser create|get|update|delete|list  # End-user profile management
autoinfo portal preferences|history # End-user self-service portal
autoinfo trace <trace_id>           # Per-item pipeline trace
```

## MCP Tools (139)

| Category | Tools |
|----------|-------|
| **System** | health_check, diagnose_system, get_config, list_available_models, get_tool_count, configure_llm |
| **Discovery** | list_domains, list_available_platforms, get_domain_schema, get_effective_llm_config, list_output_templates, activate_domain, deactivate_domain, get_domain_config |
| **Domain** | add_domain, remove_domain |
| **Source** | add_source (idempotent), add_sources (batch), remove_source, test_source (with extract_fields + tier warnings), list_sources, get_source_health, get_feeds |
| **Topic** | add_topic, remove_topic, list_topics, topic_group_add, topic_group_remove, list_keywords, approve_keyword, reject_keyword, suggest_keywords |
| **Collection** | collect_sources (with dry_run, domain-less), get_collection_progress, get_collection_status, process_collection (with batch, check_factual, check_translation), get_processing_progress, batch_run, clean_cache |
| **KB** | search_knowledge_base (hybrid, cross-domain), get_kb_entry, list_summaries, get_summary, create_kb_entry, create_kb_draft (from Raw only), reject_kb_draft, list_kb_tier, reindex_kb, flag_for_knowledge_base |
| **KB Relations** | link_items, get_item_relations |
| **KB Versioning** | get_entry_history, restore_entry_version |
| **KB Monitor** | get_collection_stats, get_collection_diff |
| **KB Graph** | query_knowledge_graph, knowledge_graph_export |
| **Output** | list_output_templates, generate_digest (md/html/json/agent), generate_report (md/json/pdf/html/audio/agent), generate_cross_domain_report, generate_tutorial (md/agent), generate_presentation (md/agent), localize_content, export_kb (md/json/sqlite/pdf/csv/graphml/agent/bundle) |
| **Export/Import** | export_kb, import_kb |
| **CEFR** | classify_cefr (EN/ZH/JA), cefr_batch |
| **Keywords** | approve_keyword, reject_keyword, suggest_keywords |
| **Email** | send_email_digest, email_config |
| **Audit** | query_audit_log |
| **Q&A** | query_collected (FTS5 + LLM synthesis with source citations) |
| **Custom Extraction** | extract_fields, get_extraction |
| **Cron** | list_schedules, add_schedule, remove_schedule, run_schedules, get_schedule_status |
| **Source Health** | get_source_health, rate_item |
| **Projects** | init_project, list_projects, get_project_assets, archive_project |
| **Monitor** | list_active_collections, list_active_deliveries, get_channel_health (health + latency for all 13 delivery channels) |
| **Webhooks** | set_domain_webhooks, get_domain_webhooks |
| **Quality Gate Config** | get_gate_config, set_gate_config |
| **Product** | list_products, get_product |
| **Alert Rules** | add_alert_rule, get_alert_rules, remove_alert_rule |
| **End User** | send_to_enduser, get_enduser_history, get_enduser_products, query_delivery_log, get_delivery_log, activate_trial, check_trial_expiry, update_preferences, get_preferences, get_subscription_status |
| **Cost** | get_billing_summary, get_budget_thresholds, set_budget_thresholds, create_checkout_session, get_enduser_usage, get_enduser_invoice, cost_dashboard, cost_allocation |
| **Data Privacy** | soft_delete_entry (with purge flag), restore_entry, export_user_data, delete_user_data |
| **Knowledge Lifecycle** | compare_versions, find_similar_items, merge_items, get_domain_decay, mark_stale, calculate_freshness_score, recommend_content, simplify_content |
| **Observability** | trace_item, get_metrics, get_prometheus_metrics, diagnose_system |
| **Agent Callbacks** | set_agent_callback, list_agent_callbacks, remove_agent_callback |
| **Delivery Schedule** | add_delivery_schedule, list_delivery_schedules, remove_delivery_schedule |

## Demo Domains

| Domain | Sources | Priority | Status |
|--------|---------|----------|--------|
| **Medical Research** | PubMed (REST API), Semantic Scholar, arXiv, CrossRef, DBLP, OpenAlex, USPTO | 🔴 P0 | ✅ Implemented (7 curated sources) |
| **AI Commercial Intelligence** | TechCrunch RSS, ProductHunt RSS, Crunchbase, 36kr | 🟡 P1 | ✅ Implemented (4 curated sources) |
| **Financial/Business Intelligence** | Alpha Vantage, FRED, SEC EDGAR, Twelve Data, World Bank Data | 🟡 P1 | ✅ Implemented (5 curated sources) |
| **Tech/AI/Developer** | GitHub Trending, HackerNews API, Substack RSS (tech), Stack Exchange, ProductHunt, Reddit, Spotify AI Podcasts, Bilibili | 🟡 P1 | ✅ Implemented (8 curated sources) |
| **Language Learning** | Project Gutenberg, news-in-levels, commonlit | 🟢 P2 | ✅ Implemented (3 curated sources) |
| **Online Video / OTT** | YouTube, Bilibili, Apple Podcasts, Spotify | 🟡 P1 | ✅ Implemented (4 curated sources) |
| **Financial News** | NYT, Alpha Vantage, FRED, SEC EDGAR, Twelve Data, World Bank Data | 🟡 P1 | ✅ Implemented (6 curated sources) |
| **Online Education** | OpenAlex, Semantic Scholar, arXiv, DBLP, Stack Exchange, Project Gutenberg | 🟢 P2 | ✅ Implemented (6 curated sources) |
| **Legal Compliance** | USPTO, Semantic Scholar, webhook, email (IMAP) | 🟢 P2 | ✅ Implemented (4 curated sources) |

## Development

```bash
pip install -e ".[dev]"
make test        # pytest -v
make lint        # ruff check + mypy
```

## Known Limitations

AutoInfo v1.8.1 integrates **Phase 4 enhancements**: cross-domain reports, specialized report types, bundle export, delivery schedule automation, 16 new collectors, and the `recommend_content` MCP tool (139 total). v1.8 adds **agent-oriented enhancements**: 18 new MCP tools (133→139 including Phase 4), dynamic tool count via self-discovery, unified dual-format error responses, cross-domain search, domain-less collection, agent-native format for tutorial/presentation/export, persistent job state and agent callbacks (SQLite-backed), hard-delete purge flag, fine-grained process control flags, batch CEFR, audit log MCP, knowledge graph export, RSS feed MCP, cache cleanup, topic grouping, email config MCP, cost dashboard/allocation MCP tools, CLI help text fixes, and `<!-- agent: ... -->` metadata blocks on all spec docs. v1.7 added **subscription tier gating** (Free/Premium/Enterprise...). v1.6 added end-to-end commercial delivery (end user profiles, multi-channel delivery, delivery reliability with SLA tracking, self-service portal), cost governance (internal metering, allocation, dashboard, budget alerts), operational observability (structured pipeline logging, per-item traceability, enhanced diagnostics, Prometheus metrics), data privacy (source ToS compliance, soft-delete & GDPR retention, immutable audit logging), and knowledge lifecycle management (per-domain TTL, versioned re-collection, stale handling, decay metrics, cross-collection dedup & merge). v1.5 added commercial scope, product types, production-grade quality gates, and product architecture. v1.4 added user-defined domains, translation QA pipeline, HTML format output, KB import, webhook push, and cron-based email digest delivery. v1.3 added ErrorCode centralization, MCP schema hardening, and LLM extraction resilience. The following items remain explicitly deferred:

| Feature | Status | Notes |
|---------|--------|-------|
| Config override system (~/.autoinfo/overrides/) | 📋 Planned | Per-project config layering |
| Multi-user / collaboration (auth, teams) | 📋 Planned | user_id fields in place; full auth v2 |
| Subscription-ready billing (G14-G16) | ✅ Implemented | Stripe webhook endpoint (signature verification), stripe-mock dev setup, freemium gating, usage-based billing. Full Stripe lifecycle from checkout to webhook event dispatch. |

> See `docs/dev/founder-expectations.md` §14 for the full deferred-items catalog.
> Cross-dimensional catalog (keystone product matrix): `docs/dev/cross-dimensional-catalog.md` (42 cells, 5 gap types across A1-A7 Pipeline × B1/B2/B3 Users).
> Some high-value sources (Bloomberg, Reuters Eikon, WSJ) remain blocked by cost/policy — see `docs/known-limitations/blocked-sources.md`.

## License

MIT
