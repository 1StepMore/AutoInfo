# AutoInfo — Agent Guide

## What Is AutoInfo

AutoInfo is a **universal information tracking and knowledge base platform**.
You configure sources and topics; AutoInfo handles collection, LLM-based
structured extraction, summarization, and builds a queryable knowledge base.

**Key principle**: Domain-agnostic. The five demo domains (medical-research,
ai-commercial, financial-intelligence, tech-ai-developer, language-learning) are configurations, not hardcoded features.
Users define their own domains.

## Agent Operating Model

AutoInfo is designed **agent-first**:

```
Director-user (human) ──NL──> Agent ──MCP tools──> AutoInfo MCP Server
                                ↑                           │
                                └──── structured JSON-RPC ───┘
```

1. **You (the agent)** connect to AutoInfo's MCP server over stdio or SSE
2. **All capabilities** are exposed as MCP tools (132 tools across 32 categories)
3. **CLI mirrors MCP** — `--domain X --topic Y` flags map 1:1 to tool parameters
4. **Human director** communicates intent to you in natural language; you translate to tool calls
5. **Human can also use CLI directly** as a fallback, but the primary interface is through you

## Quick Start (5 Seconds)

Connect your AI agent to AutoInfo immediately:

**Cursor**: `.cursor/mcp.json` is already committed to the repo -- restart Cursor
and the `autoinfo` MCP server is ready to use.

**Claude Desktop**: Copy `.claude/claude_desktop_config.json` from this repo to
`claude_desktop_config.json` in your Claude config directory:
- **Linux**: `~/.config/Claude/claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

**OpenCode**: `.opencode/mcp.json` is already committed -- OpenCode discovers it
automatically via project-level configuration.

**Manual (any platform)**:
```bash
python -m autoinfo.mcp.server
```

## Project Structure

```
AutoInfo/
├── AGENTS.md                       # ← You are here
├── README.md                       # Project overview
├── pyproject.toml                  # Python packaging
├── Makefile                        # Build automation
├── .gitignore
├── docs/
│   ├── dev/
│   │   ├── founder-expectations.md # Index doc (simplified; full content in specs/)
│   │   ├── specs/                  # Extracted spec files (2026-07-26 restructuring)
│   │   │   ├── expectations.md     # F01-F57 expectation catalog (57 expectations, 12 phases)
│   │   │   ├── quality-gates.md    # G0-G5, D1-D3 gate catalog & configuration + testing strategy
│   │   │   ├── pipeline.md         # Collection pipeline, KB pipeline, LLM config, extraction, search, performance targets
│   │   │   ├── delivery.md         # Output generation, delivery channels, end user lifecycle
│   │   │   ├── operations.md       # Cost, data privacy, knowledge lifecycle, observability
│   │   │   ├── market-positioning.md # Priority matrix, competitive landscape, pricing, personas
│   │   │   ├── mcp-tools.md        # 132 MCP tools across 32 categories
│   │   │   ├── data-models.md      # Consolidated data model schemas
│   │   │   ├── multi-tenancy-auth.md    # Multi-tenancy and authorization spec
│   │   │   └── ops-runbook.md           # Operations runbook spec
│   │   ├── cross-dimensional-catalog.md # Cross-dimensional catalog — keystone product matrix (A1-A7 × B1/B2/B3, supersedes archived gap docs)
│   │   ├── archive/                  # Archived/historical docs
│   │   ├── kb-pipeline-reference.md  # KB pipeline reference model (archived)
│   │   ├── director-user-guide.md    # Human-Agent interaction lifecycle
│   │   └── consumer-output-gaps.md    # Consumer-facing output gap analysis (archived)
│   └── skills/                     # AutoInfo operator skills (for agent-users of AutoInfo)
│       ├── autoinfo-skill/SKILL.md # Operating AutoInfo via MCP tools
│       └── translator-qa-skill/    # Translation QA workflow
├── .opencode/
│   └── skills/                     # Coding agent skills (for developing AutoInfo)
├── src/
│   └── autoinfo/
│       ├── cli/                     # 23 CLI command groups
│       ├── mcp/                     # MCP server (132 tools)
│       ├── api/                     # REST API (FastAPI, port 8741)
│       ├── kb.py                    # Knowledge base pipeline (4-tier KB pipeline)
│       ├── collectors/              # Source handlers (PubMed, RSS, Web, Email, PDF)
│       ├── llm.py                   # LLM extraction engine
│       ├── output.py                # Output generation (digest, report, tutorial, export)
│       ├── cefr.py                  # CEFR classification (EN/ZH/JA)
│       ├── email_sender.py          # SMTP email sending
│       ├── keywords.py              # Keyword management
│       ├── quality.py               # Quality gates G0-G5, D1-D3 delivery gates
│       ├── delivery.py              # Delivery channel abstraction (SMTP, webhook, REST, export)
│       ├── alerts.py                # Alert rule CRUD, YAML persistence, check & dispatch
│       ├── qa.py                    # Q&A with LLM synthesis
│       └── ...
```

## Architecture Rules

These are hard constraints derived from `founder-expectations.md`.
Violating them produces incorrect behavior.

### KB Pipeline

```
Collected Item → 01-Raw → 02-Draft → 03-Wiki
     ↑             ↑          ↑           ↑
  Auto-ingest    Sole       Agent can   Only human
                 entry      process &   can promote
                 point      create      Draft → Wiki
```

| Rule | Why |
|------|-----|
| **01-Raw is the sole entry point** for all collected content | Every collected item must have complete source provenance. No skipping. |
| **Agent cannot create Draft from outside** — only from 01-Raw | Prevents garbage entries. Raw→Draft→Wiki is sequential. |
| **Agent cannot write to 03-Wiki** | Only human promotes Draft→Wiki. Wiki entries are permanently reviewed. |
| **03-Wiki is append-only** | Once promoted, entries stay. Agent cannot demote or delete Wiki entries. Only human can. Agent may deprecate (tag `status: deprecated`) upon explicit human command. |
| **Source metadata is mandatory** | Every Raw entry must have `source_url`, `source_type`, `source_platform`. |

### Collection Pipeline

Two phases, separable in time:

```
Phase 1 — Fetch:     autoinfo collect --domain medical
  → Source handlers fetch items in parallel
  → Raw JSON cached to collections/
  → Dedup (URL → DOI → fuzzy title → semantic)
  → Collection log written

Phase 2 — Process:   autoinfo process --domain medical [--model deepseek-chat]
  → Reads cached raw items
  → LLM extraction (configurable model per task)
  → Quality gates (G1-G5)
  → Creates 01-Raw KB entries
```

### Quality Gates (Production-Grade)

Production-grade quality with hard/soft split and retry-first, block-last philosophy.
G0 (Schema Integrity) and G4 (Factual Consistency) are **hard gates** — they retry
up to 3 times with escalating context, then block on failure. G1-G3 and G5 are
**soft gates** with configurable thresholds and actions (archive/flag/pass).
3 delivery gates (D1-D3) check product completeness, format integrity, and
freshness at output time.

| Gate | Type | Priority | Action on Failure |
|------|------|----------|-------------------|
| G0: Schema integrity | 🔴 Hard | 🔴 P0 | 3× retry → block (item written to `_failed/`) |
| G1: Source authority (tier check) | 🟡 Soft | 🔴 P0 | Configurable: archive/flag/pass |
| G2: Dedup (URL + fuzzy title) | 🟡 Soft | 🔴 P0 | Configurable: archive/flag/pass |
| G3: Relevance scoring (0-100) | 🟡 Soft | 🔴 P0 | Configurable: archive/flag/pass (below threshold) |
| G4: Factual consistency | 🔴 Hard | 🟡 P1 | 3× retry with escalating context → block |
| G5: Translation accuracy | 🟡 Soft | 🟡 P1 | Configurable: archive/flag/pass |
| D1: Product completeness | 🔴 Hard | 🔴 P0 | Blocks delivery |
| D2: Format integrity | 🔴 Hard | 🔴 P0 | Blocks delivery |
| D3: Freshness | 🟡 Soft | 🟡 P1 | Configurable threshold |

## Agent Constraints (MUST NOT)

| Action | Reason |
|--------|--------|
| **Run `init_project` MCP tool** | Use `init_project` MCP tool for agent workflows instead of CLI `init`. CLI `init` remains available for humans. |
| **Do not manage API keys** | Keys are configured in env vars or config. You don't store, generate, or transmit keys. |
| **Do not write to 03-Wiki** | Only human can promote Draft→Wiki. |
| **Do not create Draft from outside** | Draft must come from 01-Raw. |
| **Do not demote Wiki entries** | Wiki is append-only. Tag `deprecated` only upon human command. |
| **Do not delete source or domain config** | Human decides what sources/domains to remove. |
| **Do not modify `.autoinfo/config.yaml` directly** | Use MCP tools (`add_source`, `add_topic`). |
| **Do not run `autoinfo doctor`** | Use `diagnose_system()` MCP tool instead — returns structured health data. |

## Tool Discovery Guidance

132 MCP tools across 32 categories:

| Category | Key Tools |
|----------|-----------|
| **System** | `health_check`, `diagnose_system`, `get_config`, `list_available_models`, `get_tool_count` |
| **Discovery** | `list_domains`, `list_available_platforms`, `get_domain_schema`, `get_effective_llm_config`, `list_output_templates`, `activate_domain`, `deactivate_domain`, `get_domain_config` |
| **Domain** | `add_domain`, `remove_domain` |
| **Source** | `add_source` (idempotent), `add_sources` (batch), `remove_source`, `test_source`, `list_sources`, `get_source_health`, `get_feeds` |
| **Topic** | `add_topic`, `remove_topic`, `list_topics`, `list_keywords`, `approve_keyword`, `reject_keyword`, `suggest_keywords`, `topic_group_add`, `topic_group_remove` |
| **Collection** | `collect_sources` (with dry_run, domain-less), `get_collection_progress`, `get_collection_status`, `process_collection` (with batch, check_factual, check_translation), `get_processing_progress`, `batch_run`, `clean_cache` |
| **KB** | `search_knowledge_base` (hybrid, cross-domain), `get_kb_entry`, `list_summaries`, `get_summary`, `create_kb_entry`, `create_kb_draft`, `reject_kb_draft`, `list_kb_tier`, `reindex_kb`, `flag_for_knowledge_base` |
| **KB Relations** | `link_items`, `get_item_relations` |
| **KB Versioning** | `get_entry_history`, `restore_entry_version` |
| **KB Monitor** | `get_collection_stats`, `get_collection_diff` |
| **KB Graph** | `query_knowledge_graph`, `knowledge_graph_export` |
| **Output** | `list_output_templates`, `generate_digest` (format=md/html/json/agent), `generate_report` (format=md/json/pdf/html/audio/agent), `generate_tutorial` (format=md/agent), `generate_presentation` (format=md/agent), `localize_content` |
| **Export/Import** | `export_kb` (format=md/json/sqlite/pdf/csv/graphml/agent), `import_kb` |
| **CEFR** | `classify_cefr`, `cefr_batch` |
| **Keywords** | `approve_keyword`, `reject_keyword`, `suggest_keywords` |
| **Email** | `send_email_digest`, `email_config` |
| **Q&A** | `query_collected` |
| **Custom Extraction** | `extract_fields`, `get_extraction` |
| **Cron** | `list_schedules`, `add_schedule`, `remove_schedule`, `run_schedules`, `get_schedule_status` |
| **Source Health** | `get_source_health`, `rate_item` |
| **Projects** | `init_project`, `list_projects`, `get_project_assets`, `archive_project` |
| **Monitor** | `list_active_collections`, `list_active_deliveries`, `get_channel_health` |
| **Webhooks** | `set_domain_webhooks`, `get_domain_webhooks` |
| **Quality Gate Config** | `get_gate_config`, `set_gate_config` |
| **Product** | `list_products`, `get_product` |
| **Alert Rules** | `add_alert_rule`, `get_alert_rules`, `remove_alert_rule` |
| **End User** | `send_to_enduser`, `get_enduser_history`, `get_enduser_products`, `query_delivery_log`, `get_delivery_log`, `activate_trial`, `check_trial_expiry`, `update_preferences`, `get_preferences`, `get_subscription_status` |
| **Cost** | `get_billing_summary`, `get_budget_thresholds`, `set_budget_thresholds`, `create_checkout_session`, `get_enduser_usage`, `get_enduser_invoice`, `cost_dashboard`, `cost_allocation` |
| **Data Privacy** | `soft_delete_entry` (with purge flag), `restore_entry`, `export_user_data`, `delete_user_data` |
| **Knowledge Lifecycle** | `compare_versions`, `find_similar_items`, `merge_items`, `get_domain_decay`, `mark_stale`, `calculate_freshness_score` |
| **Observability** | `trace_item`, `get_metrics`, `get_prometheus_metrics`, `diagnose_system` |
| **Agent Callbacks** | `set_agent_callback`, `list_agent_callbacks`, `remove_agent_callback` |
| **Audit** | `query_audit_log` |

**Discovery flow**:
1. Call `health_check()` first to verify server is alive and get version info
2. Use MCP protocol `tools/list` for auto-discovery of all available tools
3. Call `list_domains()` to see available domains
4. Call `get_domain_schema(domain)` to see extraction fields for your domain
5. Call `list_available_models()` to see configured LLM models
6. Call `list_output_templates(domain)` to see output types for your domain

## Common Patterns

### "Track a new topic in medical research"
```
1. `add_topic(domain="medical-research", name="IVF breakthroughs", keywords=["IVF", "embryo"])`
2. `collect_sources(domain="medical-research", topic="IVF breakthroughs", dry_run=true)` → preview
3. `collect_sources(domain="medical-research", topic="IVF breakthroughs")` → actual collection
4. `process_collection(domain="medical-research")` → LLM extraction
5. `list_summaries(domain="medical-research", topic="IVF")` → review results
6. `flag_for_knowledge_base(summary_id, tags=["ivf", "breakthrough"])` → promote to KB
```

### "What changed since last week?"
```
1. `get_collection_stats(period="week")` → overview
2. `get_collection_diff(domain="medical-research", since_collection_id="...")` → new items
```

### "Check system health"
```
1. `diagnose_system()` → comprehensive health (LLM key, sources, disk, DB)
```

### "Create a custom domain"
```
1. `add_domain(name="my-custom-domain", description="My custom domain")` → domain created
2. `list_available_platforms()` → discover supported source types
3. `add_source(domain="my-custom-domain", name="my-rss", type="rss", url="https://example.com/feed")` → source added
4. `add_topic(domain="my-custom-domain", name="My Topic", keywords=["keyword1", "keyword2"])` → topic configured
5. `collect_sources(domain="my-custom-domain")` → collect from all sources
```
→ Custom domain with sources and topics fully configured.

### "Initialise a project"
```
1. `health_check()` → verify server availability
2. `init_project(name="my-project", demo="medical-research")` → scaffold project structure *(requires AutoInfo ≥ v1.3)*
3. `list_domains()` → confirm demo domain is active
```
→ Project initialised with demo domain, sources, and topics configured.

### "Save an article to the knowledge base"
```
1. `flag_for_knowledge_base(summary_id="sum_123", tags=["important", "review"])` → promote summary
2. `create_kb_draft(summary_id="sum_123")` → agent creates Draft from Raw
3. (User promotes Draft → Wiki via CLI `autoinfo kb promote`)
```
→ Summary flagged, Draft created, awaiting human promotion to Wiki.

### "Set up and run a cron schedule"
```
1. `add_schedule(domain="medical-research", cron="0 8 * * 1", topic="IVF breakthroughs")` → schedule created *(requires AutoInfo ≥ v1.2)*
2. `cron_install()` → install crontab entries *(requires AutoInfo ≥ v1.2)*
3. `list_schedules()` → verify active schedules
4. `run_schedules()` → manual trigger for immediate collection
```
→ Scheduled collection runs every Monday at 8 AM.

### "Generate and send a digest email"
```
1. `generate_digest(domain="medical-research", period="week")` → digest Markdown
2. `send_email(to="user@example.com", subject="Weekly Digest", body=digest)` → email sent via SMTP *(requires AutoInfo ≥ v1.2)*
```
→ Weekly digest generated and delivered to inbox.

### "Classify content by CEFR level"
```
1. `classify_cefr(text="The mitochondria is the powerhouse of the cell.", language="en")` → returns CEFR level *(requires AutoInfo ≥ v1.2)*
```
→ Returns `{"level": "B2", "confidence": 0.87, "features": ["academic vocabulary", "complex structure"]}`

### "Search with hybrid or vector mode"
```
1. `search_knowledge_base(domain="medical-research", query="embryo development", mode="hybrid")` → FTS5 + vector
2. `search_knowledge_base(domain="medical-research", query="embryo development", mode="vector")` → semantic only *(requires AutoInfo ≥ v1.2)*
3. `search_knowledge_base(domain="medical-research", mode="faceted", filters={"source_type": "pubmed", "relevance_min": 70})` → filtered *(requires AutoInfo ≥ v1.2)*
```
→ Ranked results from KB with source citations.

### "Export knowledge base to PDF"
```
1. `export_kb(domain="medical-research", format="pdf", topic="IVF breakthroughs")` → generates PDF report
```
→ PDF file written to `exports/medical-research/IVF-breakthroughs-report.pdf`

### "Manage keywords for a domain"
```
1. `list_keywords(domain="medical-research")` → view current keywords and pending candidates
2. `suggest_keywords(domain="medical-research", topic="IVF breakthroughs")` → LLM suggests new keyword candidates
3. `approve_keyword(keyword_id="kw_123")` → accept a suggested keyword into the active set
4. `reject_keyword(keyword_id="kw_456")` → reject a suggested or obsolete keyword
```
→ Keywords curated for source filtering and topic matching. Use the CLI (`autoinfo keywords add|remove|list`) for direct add/remove outside the suggest-then-approve workflow.

### "Generate agent-native JSON output"
```
1. `generate_digest(domain="medical-research", period="week", format="agent")` → returns structured JSON-LD optimized for LLM re-consumption
```
→ Returns `{"@type": "KnowledgeDigest", "entries": [{uuid, title, tl_dr, source_url, confidence_score, entities, key_points}], "trends": [...], "metadata": {entry_count, quality_gates}}`. Agent can re-synthesize, cache, or combine with other data.

### "Subscribe to agent push delivery"
```
1. `set_agent_callback(url="https://my-agent.example.com/callback", events=["new_digest", "new_report"])` → register callback
2. AutoInfo pushes structured JSON when a matching product is generated
3. Agent receives `{callback_event: "new_digest", product: {...}}` via HTTP POST
```
→ Agent subscription pattern: register once, receive pushes without polling. *(requires AutoInfo ≥ v1.7)*

### "Generate and deliver a digest email"  
```
1. `generate_digest(domain="medical-research", period="week", format="html")` → digest HTML
2. `send_email_digest(domain="medical-research", period="week", recipients=["user@example.com"])` → sends via SMTP
```
→ Digest generated as HTML and emailed to subscribers.

### "Use the REST API"
```
1. Start the FastAPI server: `uvicorn autoinfo.api.server:app --port 8741`
2. `curl http://localhost:8741/health` → {"status": "ok"}
3. `curl http://localhost:8741/api/v1/entries?domain=medical-research` → paginated entries
4. `curl -X POST http://localhost:8741/api/v1/search -H "Content-Type: application/json" -d '{"query": "embryo"}'`
```
→ Full KB CRUD over HTTP, no auth required (localhost security).

## LLM Configuration

AutoInfo uses LiteLLM under the hood. Standard OpenAI-format providers work.

| Config | Default | Notes |
|--------|---------|-------|
| provider | openrouter | Use "openai" for OpenAI-compatible endpoints |
| model | deepseek/deepseek-chat | Any LiteLLM-supported model |
| base_url | (none) | Required for non-OpenRouter endpoints |
| api_key | ${AUTOINFO_LLM_API_KEY} | Set via env var or config |

**Precedence** (highest to lowest):
1. MCP tool parameter (e.g. `init_project(llm_provider="openai")`)
2. Config file `.autoinfo/config.yaml` → `llm.provider`, `llm.model`
3. Environment variable `AUTOINFO_LLM_API_KEY`
4. Default values (openrouter/deepseek/deepseek-chat)

**Custom endpoint example** (e.g. OpenCode Go, Ollama, Azure):
1. Set `provider` to `"openai"`
2. Set `base_url` to your endpoint (e.g. `http://localhost:11434/v1`)
3. Set `api_key` via env var or config
4. Set `model` to your model name

### "Monitor long-running collection or processing"

Collection and processing now return a `job_id` for progress polling:

1. Start collection: `collect_sources(domain="medical", topic="IVF", async=true)` → returns `{..., "job_id": "uuid-xxx"}`
2. Poll every 5 seconds:
   ```
   while True:
       status = get_collection_progress(job_id="uuid-xxx")
       if status["is_complete"]:
           break
       sleep(5)
   ```
3. Start processing: `process_collection(domain="medical")` → returns `{..., "job_id": "uuid-yyy"}`
4. Poll: `get_processing_progress(job_id="uuid-yyy")` → check `status["is_complete"]`
5. When done: `list_summaries(domain="medical")` to review results

**Legacy**: `get_collection_progress(domain="medical")` and `get_processing_progress(domain="medical")` still work for simple single-domain usage without job_id.

## Status

| Component | Status |
|-----------|--------|
| Config system | ✅ LLM task config, per-task model, fallback chains, schema versioning |
| CLI | ✅ 23 command groups (init, doctor, collect, process, status, summaries, sources, topics, domain, audit, kb, output, cron, knowledge, cefr, email, keywords, clean, cost, billing, enduser, portal, trace) |
| Collection | ✅ PubMed, RSS, Web (trafilatura+Playwright), webhook (HMAC), email (IMAP), PDF (PyMuPDF), scheduled via crond |
| LLM extraction | ✅ Custom extraction fields, TL;DR, key points, entities, G4 factual consistency, token usage tracking |
| Translation QA pipeline | ✅ 5 lite quality gates, back-translation verification, terminology guardrails, composite scoring, translator-qa-skill |
| Quality gates | ✅ 6 hard/soft (G0-G5: G0/G4 hard, G1-G3/G5 soft) + 3 delivery gates (D1-D3) + per-domain config |
| KB pipeline | ✅ 4-tier KB pipeline (00-Inbox → 01-Raw → 02-Draft → 03-Wiki; note: 00-Inbox is scaffolded but deprecated — 01-Raw is the sole entry point), git versioning + SHA tracking |
| KB import | ✅ 4 formats (PDF, Markdown, HTML, JSON) → 01-Raw via `import_kb` MCP tool |
| Search | ✅ Hybrid (FTS5 keyword + sqlite-vec vector), faceted (7 filters) |
| Q&A | ✅ FTS5 + LLM synthesis with source citations |
| Output generation | ✅ Digest (Markdown/HTML/JSON/PDF), report (Markdown/JSON/HTML/Audio/Agent), tutorial (Markdown), presentation (Markdown) (Jinja2 + LLM, Reveal.js CDN) |
| Agent-native JSON output | ✅ `format="agent"` returns JSON-LD (`@type: KnowledgeDigest`) for LLM re-consumption |
| Audio output | ✅ TTS-rendered digest/report as MP3 (OpenAI TTS) |
| Translation | ✅ LLM-based source→target |
| Knowledge graph | ✅ Entity extraction + relation discovery |
| REST API | ✅ FastAPI CRUD (port 8741, /api/v1/entries, /health, /dashboard) |
| Web UI Dashboard | ✅ Bootstrap 5, collection stats, KB search, source health |
| MCP server | ✅ 132 tools across 32 categories |
| Domain management | ✅ `add_domain`/`remove_domain` MCP tools, `autoinfo domain` CLI (add/list/show/remove/activate/deactivate) |
| Webhook push | ✅ Per-item webhook notification on collection via `set_domain_webhooks`/`get_domain_webhooks` |
| Scheduled digest | ✅ Cron-based email digest delivery (SMTP + crontab schedule) |
| Agent alerting | ✅ Config-based alert rules with YAML persistence, check & dispatch via DeliveryChannel |
| Obsidian wiki links | ✅ `[[wiki links]]` in KB Markdown files |
| CEFR classification | ✅ LLM-based EN/ZH/JA (language-learning domain) |
| Email sending | ✅ SMTP sender (digest delivery) |
| Multi-channel delivery | ✅ 6 adapters: Telegram, WeChat OA, WeChat Work, DingTalk, FeiShu, Discord |
| End user lifecycle | ✅ Profile + Subscription CRUD. State machine: trial→active→suspended→cancelled |
| Delivery reliability | ✅ Per-subscription DeliveryLog with SLA tracking, retry chain |
| End user portal | ✅ CLI-based self-service: preferences, history, product archive |
| Immutable audit log | ✅ Append-only audit log with MCP + CLI query |
| Structured pipeline logging | ✅ JSON structured logging per pipeline event |
| Per-item traceability | ✅ UUID trace_id from collection through delivery, CLI trace |
| Cost metering | ✅ LLM tokens, storage, API calls per domain/user |
| Cost allocation | ✅ Pro-rata, usage-based, direct allocation strategies |
| Cost dashboard | ✅ CLI + MCP dashboard with daily trends, top models, budgets |
| Budget alerts | ✅ Threshold-based alerts with auto-remediation |
| Source ToS compliance | ✅ Source classification tiers, per-tier output controls |
| Data deletion & retention | ✅ Soft-delete, restore, GDPR export, 30-day auto-cleanup |
| Per-domain TTL | ✅ Configurable freshness per domain with stale marking |
| Versioned re-collection | ✅ Version tracking with structured diff between versions |
| Stale content handling | ✅ Search demotion, digest exclusion, never deleted |
| Domain decay metrics | ✅ Staleness ratio, avg TTL, decay grade (Green/Yellow/Red) |
| Cross-collection dedup & merge | ✅ URL dedup, cross-source similarity, LLM-assisted merge |
| Enhanced diagnostics | ✅ `doctor --verbose` with health score, error rates, latency |
| Prometheus metrics | ✅ `http://localhost:8741/metrics` endpoint (configurable) |
| Multi-user foundation | ✅ user_id fields on entries (no auth/teams yet) |
| Export | ✅ Markdown, JSON, SQLite, PDF, CSV, GraphML |
| Schema versioning | ✅ DB schema version markers in SQLite |
| Subscription tiers | ✅ Free/Premium/Enterprise tiers with per-tier channels, domains, products, platform limits |
| Access control | ✅ `check_access()` fast path — free always allowed, premium/enterprise require active paid subscription (G15) |
| Consumption tracking | ✅ `ConsumptionEvent` auto-record on digest/report delivery (view/open/click), SQLite-backed store |
| Automated notifications | ✅ Trial-ending reminders (3-day window) + content-ready notifications to end users |
| Channel health monitoring | ✅ `get_channel_health` MCP tool — health + latency for all 11 delivery channels |
| Cron health monitoring | ✅ `autoinfo cron health` CLI — heartbeat tracking + missed-schedule detection |
| SQLite backup | ✅ `make backup` + `scripts/backup-db.sh` / `scripts/restore-db.sh` (keeps last 7 backups) |
| Job state persistence | ✅ SQLite-backed collection/processing job state survives restarts |
| Agent callback persistence | ✅ SQLite-backed agent callback registration survives restarts |
| Cross-domain search | ✅ search_knowledge_base searches all domains when domain omitted |
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
| Demo domains | ✅ medical-research, ai-commercial, financial-intelligence, tech-ai-developer, language-learning |
| Test suite | ✅ 1612 tests (1 collection error pre-existing) |

## References

- `docs/dev/founder-expectations.md` — D3 index (simplified after split; see `docs/archive/founder-expectations-pre-split.md` for full original)
- `docs/dev/specs/` — Extracted spec files (11 files: expectations.md, quality-gates.md, pipeline.md, delivery.md, operations.md, market-positioning.md, mcp-tools.md, data-models.md, user-lifecycle-definition.md, multi-tenancy-auth.md, ops-runbook.md)
- `docs/archive/kb-pipeline-reference.md` — Reference KB pipeline model (archived)
- `docs/dev/cross-dimensional-catalog.md` — **Keystone**: A1-A7 Pipeline × B1/B2/B3 Users (42 cells, 5 gap types). Supersedes the archived gap docs below.
- `docs/archive/comprehensive-gap-audit.md` — Comprehensive gap audit (archived)
- `docs/archive/consumer-output-gaps.md` — Consumer-facing output gap analysis (archived)
- `docs/archive/implementation-gaps.md` — Feature-level implementation gap audit (archived)
- `docs/archive/reality-assessment.md` — Reality assessment (archived)
