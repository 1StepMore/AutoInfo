# AutoInfo

**Universal information tracking and knowledge base platform.**

Configure sources and topics. AutoInfo handles the rest: automated collection,
LLM-based structured extraction, summarization, and a queryable knowledge base.

> "AutoInfo is your information assistant — not helping you search, but
> automating the entire pipeline from collection to knowledge curation."
>
> Domain-agnostic. Agent-native. BYOK.

## Features

- **Multi-source collection** — 30 collector handlers (RSS, REST APIs, web, webhook, email, PDF, PubMed, Semantic Scholar, DBLP, OpenAlex, USPTO, NYT, Yahoo Finance, Quandl, Reddit, Spotify, YouTube, Bilibili, Apple Podcasts, AP API, Reuters MCP, SSRN, GDELT, HuggingFace/Kaggle, Unpaywall/CORE, HackerNews, AKShare, SEC EDGAR, edX sitemap) with `fetch_depth: fulltext` and live per-source progress.
- **4-tier knowledge base** — 00-Inbox (deprecated) → 01-Raw (sole entry) → 02-Draft → 03-Wiki (append-only), with git versioning, `[[wiki links]]`, 4 import formats (PDF/Markdown/HTML/JSON).
- **Hybrid search & Q&A** — FTS5 keyword + sqlite-vec vector embeddings, faceted filters (incl. `filter_custom_fields` on custom_fields JSON), cross-domain search, and FTS5+LLM Q&A with source citations.
- **LLM extraction & quality gates** — configurable extraction fields, TL;DR/key points/entities/relevance, G0-G7 gates (G0/G4 hard, G1-G3/G5/G7 soft) + D1-D3 delivery gates, translation QA, and CEFR (EN/ZH/JA).
- **Product generation** — 8 product families (incl. premium-briefing, enterprise-briefing, magazine-digest) across Markdown/HTML/JSON/PDF/Audio/Agent/EPUB/MOBI/Audiobook/Video; digest, report, tutorial, presentation, export.
- **Delivery & end users** — 13 delivery channels (SMTP, webhook, REST, file export, Discord, Telegram, WeChat Work/OA, DingTalk, FeiShu, RSS, social publish, push) with retry/fallback, cron schedules, per-user lifecycle/subscription, portal, and delivery logs.
- **Cost, audit & observability** — per-domain/per-user cost metering and allocation, budget alerts, append-only audit log, per-item trace IDs, structured pipeline logs, Prometheus metrics, and `doctor` diagnostics.
- **Agent-native surfaces** — 149 MCP tools across 35 categories, 31 CLI groups, REST API (port 8741), read-only MCP mode (4 tools), and 182 validation scenarios (86 functional + 96 regression) that execute real MCP/CLI/REST calls with per-step traces.
- **Data lifecycle & compliance** — source ToS classification/tier controls, soft-delete + restore + 30-day cleanup, tier-based retention, GDPR export/delete, and append-only knowledge lifecycle (TTL/freshness/decay, versioned re-collection).
- **BYOK & LLM governance** — multi-provider via LiteLLM, per-task model routing, fallback chains, per-provider concurrency limiting with 429/5xx backoff, and a single documented default (`openrouter` + `deepseek/deepseek-chat`).

> The per-component status table below is the single source of truth for feature coverage; these bullets are a thematic index.

## Status

| Component | Status |
|-----------|--------|
| Config system | ✅ LLM task config, per-task model, fallback chains, schema versioning |
| CLI | ✅ 31 command groups (doctor, collect, process, status, summaries, sources, topics, topic-group, domain, audit, kb, output, cron, knowledge, cefr, email, keywords, clean, cost, billing, enduser, portal, trace, import-kb, query-collected, alert-rules, agent-callback, validate, validation, serve, mvp) |
| Collection | ✅ 30 collector handlers (PubMed, Semantic Scholar, DBLP, OpenAlex, USPTO, NYT, Yahoo Finance, Quandl, RSS, Web, webhook, email, PDF, Reddit, Spotify, YouTube, Bilibili, Apple Podcasts, plus paid AP API and Reuters MCP, plus SSRN, GDELT, HuggingFace/Kaggle, Unpaywall/CORE, HackerNews, AKShare, SEC EDGAR, edX sitemap), scheduled via crond; `fetch_depth: fulltext` threading (unpaywall/rss/youtube/gdelt, 8000-char cap) |
| LLM extraction | ✅ Custom extraction fields, TL;DR, key points, entities, G4 factual consistency, token usage tracking |
| Translation QA pipeline | ✅ 5 lite quality gates, back-translation verification, terminology guardrails, composite scoring, translator-qa-skill |
| Quality gates | ✅ 7 hard/soft (G0-G7: G0/G4 hard, G1-G3/G5/G7 soft) + 3 delivery gates (D1-D3) + per-domain config |
| KB pipeline | ✅ 4-tier KB pipeline (00-Inbox → 01-Raw → 02-Draft → 03-Wiki; note: 00-Inbox is scaffolded but deprecated — 01-Raw is the sole entry point), git versioning + SHA tracking |
| KB import | ✅ 4 formats (PDF, Markdown, HTML, JSON) → 01-Raw via `import_kb` MCP tool |
| Search | ✅ Hybrid (FTS5 keyword + sqlite-vec vector), faceted (7 filters + `filter_custom_fields` on custom_fields JSON) |
| Q&A | ✅ FTS5 + LLM synthesis with source citations |
| Output generation | ✅ Digest (Markdown/HTML/JSON/Agent/Audio/EPUB/Audiobook), report (Markdown/JSON/HTML/Audio/Agent/Video/EPUB/Audiobook), tutorial (Markdown), presentation (Markdown), export (Markdown/JSON/SQLite/PDF/RSS/CSV/GraphML/Agent/Bundle/Sitemap/EPUB; MOBI 🟡 requires calibre, not CI-covered) (Jinja2 + LLM, Reveal.js CDN, ebooklib EPUB3 + calibre MOBI); 8 product templates incl. premium-briefing/enterprise-briefing/magazine-digest (editorial intro + personality feature story, #313) + per-product LLM synthesis |
| Agent-native JSON output | ✅ `format="agent"` returns JSON-LD (`@type: KnowledgeDigest`) for LLM re-consumption |
| Audio output | ✅ TTS-rendered digest/report as MP3 (OpenAI TTS) via `format='audio'`; `format='audiobook'` = chaptered MP3 + ZIP (ID3v2.3 CHAP/CTOC via mutagen) |
| Video output | ✅ HyperFrames HTML+GSAP→MP4 (`report format="video"`): TTS narration + themed scene compositions, 36+8 themes, 6 layouts with adjacent-scene diversity; MCP `generate_report`/`generate_cross_domain_report` expose `video` |
| Translation | ✅ LLM-based source→target |
| Knowledge graph | ✅ Entity extraction + relation discovery |
| REST API | ✅ FastAPI CRUD (port 8741, /api/v1/entries, /health, /dashboard) |
| Web UI Dashboard | ✅ Bootstrap 5, collection stats, KB search, source health |
| MCP server | ✅ 149 tools across 35 categories |
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
| End user portal | 🟡 CLI-based self-service: preferences (untyped JSON) + history; REST API portal surfaces typed preferences (content_preference, QuietHours, identity_anchor) via merge with legacy; no typed preference editor or product archive in portal CLI |
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
| Cross-collection dedup & merge | 🟡 URL dedup + cross-source similarity (find_similar_items); no LLM-assisted merge (merge_items in quality.py has only simple/title_first strategies) |
| Enhanced diagnostics | ✅ `doctor --verbose` with health score, error rates, latency p95/p99. |
| Prometheus metrics | ✅ `http://localhost:8741/metrics` endpoint (configurable). |
| Multi-user foundation | 🟡 Advisory user_id fields only (MultiUserConfig enabled=False); no auth/teams/RBAC |
| Export | ✅ Markdown, JSON, SQLite, PDF, CSV, GraphML |
| Schema versioning | ✅ DB schema version markers in SQLite |
| Subscription tiers | ✅ Free/Premium/Enterprise tiers with per-tier channels, domains, products, platform limits |
| Access control | ✅ `check_access()` fast path — free always allowed, premium/enterprise require active paid subscription (G15) |
| Consumption tracking | 🟡 `ConsumptionEvent` auto-record on delivery (SQLite store) exists; no consumption feedback loop |
| Automated notifications | 🟡 Trial-ending reminders + content-ready notifications; no unified notification bus (F63) |
| Channel health monitoring | 🟡 `get_channel_health` MCP tool exists (health + latency); no auto-suspend of unhealthy channels |
| Cron health monitoring | 🟡 Heartbeat tracking + missed-schedule detection (cli/cron.py); no backfill/execution history |
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
| Demo domains | ✅ 21 demo domains (medical-research, ai-commercial, financial-intelligence, tech-ai-developer, language-learning, online-video, financial-news, online-education, legal-compliance, general-news, gaming, b2b, retail, plus english/french/hindi/italian/korean/portuguese/russian/spanish-learning) |
| Delivery schedules | ✅ add_delivery_schedule, list_delivery_schedules, remove_delivery_schedule MCP tools, cron-integrated |

| Validation scenarios | ✅ 182 scenarios (86 functional + 96 regression in `src/autoinfo/mcp/scenarios/regression/`, `regression: true` key, recursive-glob auto-load) |
| Validation execution | ✅ Per-step `timeout_seconds`; per-step `recovery_steps` + partial-pass (`min_passing`/`pass_ratio`); per-step trace (step_index/duration/arguments/trace_id + llm_meta); root-cause report (`## Blockers` / `## Per-step trace` / `## Regression failures`) |
| Regression flywheel | ✅ `src/autoinfo/mcp/scenarios/regression/` (96 regression scenarios) + `coverage_audit.py` "Regression scenarios: N" metric + `.github/ISSUE_TEMPLATE/bug_report.md` mandatory 回归场景 field |

| Validation delivery | ✅ `scripts/validation_delivery.py` builds 01-RAW/02-PROCESSED/03-KB/04-MATRIX/06-REJECTED + validation-report.md + manifest.json (per-file authenticity + D1-D3 gates + UX metrics UX_OK/completion_rate ≥ 0.8) + 01-QA-GATES/ gate reports (per-product `gate-report-<product>.{md,json}` + `gate-reports-index.json`) |
| End-user coverage matrix (E8) | ✅ `scripts/coverage_matrix.py` + `docs/dev/specs/end-user-matrix.yaml`; surfaced as 04-MATRIX + coverage-gaps.json |
| End-user journey validation | ✅ `enduser-journey.yaml` scenario + UX metrics; error-boundary asserts `actionable` field |
| LLM timeout + parallel processing | ✅ `LLMConfig.timeout` (default 120.0) threaded through LLM calls; `AUTOINFO_PROCESS_WORKERS` ThreadPoolExecutor (default 5, env-clamped cap 16, probe-gated); post-extraction gates G3/G4/G5/CEFR concurrent per item (`AUTOINFO_SUBTASK_CAP` default 4); CEFR outside `_STORAGE_LOCK`; MCP `asyncio.to_thread` offload (14 sync LLM handlers) |
| LLM fallback chain | ✅ Shared `llm.call_with_fallback` — every LLM call site (extraction + 17 standalone) walks `[primary] + config.llm.fallback`; an empty `provider` inherits the primary provider, an empty `api_key` inherits the primary key only on the same gateway (a cross-endpoint fallback needs its own explicit `${ENV}` key); first successful model wins; per-provider shared rate limiting (`AUTOINFO_LLM_MAX_CONCURRENCY`, default 4) + jittered 429/5xx backoff on every chain entry and all fan-out paths |
| Dead-source detection | ✅ Semantic Scholar 429 → `SourceFailure` (fail-fast); arXiv rss/bio → rss/q-bio fix |
| CLI module entry | ✅ `python -m autoinfo.cli` runs the same Typer app; `collect` live per-source progress printer |
| Test suite | ✅ ~6583 tests collected (incl. validation wave E1-E9 scenarios + regression suite + #141-#164 regression guards + kb-curation wave + hermetic config-seam fixes + llm-concurrency wave + baseline-aware coverage-gate tests + security-assertion group + 2026-09-04 concierge wave + unified-envelope conformance + director-only discovery gating + recoverability wave + category×pyramid ledger / N-run history + REST/build/vendor surface parity + AX metrics gate (M-05 keyless deterministic product-token gate) + #351 year-assertion tuning / #356 real-product scanner + release-scope gate (#406); order-dependency fixes landed 2026-08-12) |

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
autoinfo output digest --domain medical-research --period weekly
autoinfo output export --domain medical-research --format json
```

## TLDR — Agent-User / Agent-Tester (5 Seconds)

AutoInfo is agent-first: every capability is an MCP tool. Connect your agent
(Cursor / OpenCode / Claude Desktop configs are committed in-repo; or run
`python -m autoinfo.mcp.server` manually), then:

1. **Health** — `health_check()` → `{status, version, tools_count}`
2. **Discover** — `list_domains()` → `get_domain_schema("<domain>")` → `list_available_models()`

3. **Validate** — `list_validation_scenarios()` (182 scenarios: 86 functional + 96 regression) → `run_validation_scenario(scenario="system-health")`


Validation is the fastest way to prove the system works: each scenario makes
real MCP / CLI / REST calls and asserts on the `{success, data}` envelope.
Env-gated steps report `unconfigured` (never silently skipped); `llm_assert`
steps run a real model call. Every step carries a per-step execution trace
(step_index/duration/arguments/trace_id + llm_meta), and failing runs surface
a root-cause report (`## Blockers` / `## Per-step trace` / `## Regression
failures`). No LLM key yet? The 16 LLM-required tools return
`LLM_NOT_CONFIGURED` — set `AUTOINFO_LLM_API_KEY` or call `configure_llm()`.

Non-MCP testers can smoke-test over REST instead:

```bash
curl http://localhost:8741/health
curl http://localhost:8741/api/v1/entries?limit=5
```

## Run the AutoInfo MCP server

AutoInfo ships an MCP server (`python -m autoinfo.mcp.server`) that exposes
149 tools over stdio. Editor configs are already committed for Cursor
(`.cursor/mcp.json`), OpenCode (`.opencode/mcp.json`), and Claude Desktop
(`.claude/claude_desktop_config.json`). They all run
`python -m autoinfo.mcp.server` and pass `AUTOINFO_LLM_API_KEY` through from
your environment.

### 1. Install the package

The configs invoke bare `python`, so the `autoinfo` package must be
importable by whatever interpreter `python` resolves to on your PATH. From
the repo root:

```bash
pip install -e .
```

If you work inside a virtualenv, install into that interpreter instead:

```bash
.venv/bin/pip install -e .
# or, with uv
uv pip install -e .
```

Then verify the module resolves before wiring up the editor:

```bash
python -c "import autoinfo; print(autoinfo.__file__)"
```

If `python -m autoinfo.mcp.server` later fails with
`No module named autoinfo`, the package was installed into a different
interpreter than the one `python` points at. Activate the right environment
or adjust PATH so the editor finds the same `python`.

### 2. Provide the LLM API key

AutoInfo reads its LLM key from the `AUTOINFO_LLM_API_KEY` environment
variable. Export it in the shell that launches your editor, so the editor
process inherits it (not just your terminal session):

```bash
export AUTOINFO_LLM_API_KEY="sk-..."
```

AutoInfo does not load `.env` files automatically. The key has to be
present in the environment of whatever process spawns the MCP server. For
the full catalog of environment variables each source and feature expects,
see [`docs/dev/required-api-keys.md`](docs/dev/required-api-keys.md).

### 3. What the `${...}` placeholder in the configs means

Both `.cursor/mcp.json` and `.opencode/mcp.json` contain:

```json
"env": { "AUTOINFO_LLM_API_KEY": "${AUTOINFO_LLM_API_KEY}" }
```

The `${AUTOINFO_LLM_API_KEY}` is a placeholder that the editor (Cursor,
OpenCode, or Claude Desktop) interpolates from its own process environment
when it spawns the MCP server. AutoInfo never sees or expands this token
itself, and it is not shell variable expansion done by `python`. If the
variable is unset in the editor's environment, the server starts with an
empty key and every LLM-required tool returns `LLM_NOT_CONFIGURED` until
you fix it.

The same lookup rule applies to `"command": "python"`: the editor runs
whatever `python` is on PATH at launch time. If you installed `autoinfo`
into a virtualenv, make sure that virtualenv's `python` is the one the
editor finds. Either activate the virtualenv before launching the editor,
or change the config to point at the absolute interpreter path (for
example `/home/you/.venv/bin/python`).

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
         └── MCP server (149 tools)
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python ≥ 3.11 |
| CLI | typer (31 command groups) |
| REST API | FastAPI + uvicorn (port 8741) |
| MCP server | mcp (Model Context Protocol) — 149 tools over stdio |
| LLM layer | LiteLLM — multi-provider (OpenRouter, OpenAI-compatible, Ollama, Azure) via BYOK |
| Storage | SQLite + FTS5 (keyword search) + sqlite-vec (vector embeddings) |
| KB files | Markdown + python-frontmatter, git-versioned |
| Collection | httpx, feedparser (RSS), trafilatura + lxml + beautifulsoup4 (web), Playwright (browser, optional), PyMuPDF (PDF, optional) |
| Output & templates | Jinja2, weasyprint (PDF, optional), edge-tts (TTS audio, optional), Reveal.js (presentations, CDN) |
| Web UI | Bootstrap 5 (built-in dashboard) |
| Billing | Stripe |
| Scheduling | croniter + crond |
| Config | PyYAML |
| Language detection | langdetect |
| Rate limiting | pyrate-limiter |
| Utilities | python-dateutil |
| Testing | pytest + pytest-asyncio + pytest-vcr + pytest-timeout |
| Lint & type checking | ruff + mypy (strict) |
| Secret scanning | gitleaks v8.18.4 pre-commit hook + local `no-credential-url` guard (blocks token-authenticated GitHub URLs of the `https://<token>@` form and `ghp_`/`github_pat_` PAT prefixes in staged files) + the same pinned gitleaks release in CI (`.github/workflows/ci.yml` lint job, PR/push commit range) |

Optional extras: `pip install "autoinfo[web]"` (Playwright),
`"autoinfo[pdf]"` (PyMuPDF + weasyprint), `"autoinfo[tts]"` (edge-tts),
`"autoinfo[video]"` (Pillow), `"autoinfo[ebook]"` (ebooklib + mutagen),
`"autoinfo[akshare]"` (AKShare), or `"autoinfo[all]"` for everything
(`all` already includes every extra above plus `dev`).

## CLI Commands (31 groups)

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
autoinfo topic-group add|remove     # Topic grouping (MCP topic_group_add/remove parity)
autoinfo domain add|list|show|remove|activate|deactivate|import|init <name> [--seed]  # Domain management (import --from-demo supports all 21 demo domains; init --seed writes extract_fields into the seeded sources.yaml)
autoinfo audit query                # Query immutable audit log
autoinfo kb search|create-draft|promote|reject-draft|list-tiers|reindex
autoinfo output digest|report|tutorial|presentation|export|translate|list-templates  # digest/report accept --product; report accepts --type --domains
autoinfo cron run|list-schedules|add-schedule|remove-schedule|install|uninstall|health  # health = heartbeat + missed-schedule detection
autoinfo cefr classify|batch        # CEFR text classification
autoinfo email send-digest --user-id <id>|config  # SMTP email sending (--user-id for content_preference filtering)
autoinfo keywords list|approve|reject|suggest  # Keyword management
autoinfo knowledge graph            # Knowledge graph export
autoinfo clean                       # Clean temporary artifacts
autoinfo cost dashboard|allocation  # Cost tracking & allocation
autoinfo billing summary|create-free  # Billing & usage overview; create-free provisions a free-tier user (--user-id)
autoinfo enduser create|get|update|delete|list  # End-user profile management
autoinfo portal preferences|history # End-user self-service portal
autoinfo trace <trace_id>           # Per-item pipeline trace
autoinfo import-kb --file <f>       # Import entries into 01-Raw (MCP import_kb parity)
autoinfo query-collected <query>    # Q&A over collected content (MCP query_collected parity)
autoinfo alert-rules add|list|remove  # Alert rule management (MCP parity)
autoinfo agent-callback add|list|remove  # Agent push callbacks (MCP parity)
autoinfo serve --agent               # Read-only MCP server over stdio (4 read-only tools)
autoinfo mvp init|list               # Concierge MVP pilots: provision pilot users + first product
```

## MCP Tools (149)

| Category | Tools |
|----------|-------|
| **System** | health_check, diagnose_system, get_config, list_available_models, get_tool_count, configure_llm, test_llm_connection |
| **Discovery** | list_domains, list_available_platforms, get_domain_schema, get_effective_llm_config, list_output_templates, activate_domain, deactivate_domain, get_domain_config |
| **Domain** | add_domain, remove_domain |
| **Source** | add_source (idempotent), add_sources (batch), remove_source, test_source (with extract_fields + tier warnings), list_sources, get_source_health, get_feeds |
| **Topic** | add_topic, remove_topic, list_topics, topic_group_add, topic_group_remove, list_keywords, approve_keyword, reject_keyword, suggest_keywords |
| **Collection** | collect_sources (with dry_run, domain-less), get_collection_progress, get_collection_status, process_collection (with batch, check_factual, check_translation), get_processing_progress, batch_run, clean_cache |
| **KB** | search_knowledge_base (hybrid, cross-domain, faceted `filter_custom_fields` on custom_fields JSON), get_kb_entry, list_summaries, get_summary, create_kb_entry, create_kb_draft (from Raw only), reject_kb_draft, promote_kb_draft (agent promotion Draft→Wiki), promote_pending, demote_kb_wiki, force_promote, list_kb_tier (01-Raw/02-Draft/03-Wiki), reindex_kb, flag_for_knowledge_base |
| **KB Relations** | link_items, get_item_relations |
| **KB Versioning** | get_entry_history, restore_entry_version |
| **KB Monitor** | get_collection_stats, get_collection_diff |
| **KB Graph** | query_knowledge_graph, knowledge_graph_export |
| **Output** | list_output_templates, generate_digest (md/html/json/agent, `product=` premium-briefing/magazine-digest/...), generate_report (md/json/html/audio/agent/video/epub/audiobook, `product=` premium-briefing/enterprise-briefing/...), generate_cross_domain_report, generate_tutorial (md/agent), generate_presentation (md/agent), localize_content, export_kb (md/json/sqlite/pdf/csv/graphml/agent/bundle) |
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
| **End User** | enduser_create, enduser_get, enduser_update, enduser_delete, enduser_list, send_to_enduser, get_enduser_history, get_enduser_products, query_delivery_log, get_delivery_log, activate_trial, check_trial_expiry, update_preferences, get_preferences, get_subscription_status |
| **Cost** | get_billing_summary, get_budget_thresholds, set_budget_thresholds, create_checkout_session, get_enduser_usage, get_enduser_invoice, cost_dashboard, cost_allocation |
| **Data Privacy** | soft_delete_entry (with purge flag), restore_entry, export_user_data, delete_user_data |
| **Knowledge Lifecycle** | compare_versions, find_similar_items, merge_items, get_domain_decay, mark_stale, calculate_freshness_score, recommend_content, simplify_content |
| **Observability** | trace_item, get_metrics, get_prometheus_metrics, diagnose_system |
| **Agent Callbacks** | set_agent_callback, list_agent_callbacks, remove_agent_callback |
| **Delivery Schedule** | add_delivery_schedule, list_delivery_schedules, remove_delivery_schedule |
| **Validation** | list_validation_scenarios, run_validation_scenario, run_all_validation_scenarios, get_coverage_report, get_run_decisions |

## Demo Domains

| Domain | Sources | Priority | Status |
|--------|---------|----------|--------|
| **Medical Research** | PubMed (REST API), Semantic Scholar, arXiv, CrossRef, DBLP, OpenAlex, USPTO | 🔴 P0 | ✅ Implemented (7 curated sources) |
| **AI Commercial Intelligence** | TechCrunch RSS, ProductHunt RSS, Crunchbase, 36kr | 🟡 P1 | ✅ Implemented (4 curated sources) |
| **Financial/Business Intelligence** | Alpha Vantage, FRED, Finnhub, SEC EDGAR, Twelve Data, World Bank Data, Quandl/Nasdaq Data Link, CNBC Investing, TheStreet, MarketWatch Markets (DJ) | 🟡 P1 | ✅ Implemented (10 curated sources; WSJ Markets disabled) |
| **Tech/AI/Developer** | GitHub Trending, HackerNews API, Substack RSS (tech) — Pragmatic Engineer, Stack Exchange, ProductHunt, Reddit, Bilibili (B站), HN Algolia API, GitHub Blog, hnrss, Ars Technica, TechCrunch AI, InfoQ 中文, Lobsters, 掘金 (Juejin), 量子位 (QbitAI) | 🟡 P1 | ✅ Implemented (16 curated sources; Spotify AI Podcasts GFW-blocked, disabled) |
| **Language Learning** | Project Gutenberg, news-in-levels, commonlit | 🟢 P2 | ✅ Implemented (3 curated sources) |
| **Online Video / OTT** | Variety, Hollywood Reporter, Netflix Tech Blog, Pitchfork, Billboard, Bilibili (popular), TheWrap, The Verge, ComingSoon | 🟡 P1 | ✅ Implemented (9 curated sources; YouTube/Apple Music GFW-blocked/dead, disabled) |
| **Financial News** | CNBC, Seeking Alpha, Microsoft Newsroom, WSJ RSS, MW RSS | 🟡 P1 | ✅ Implemented (5 curated sources; 5 dead/GFW feeds disabled) |
| **Online Education** | Coursera Blog, EdSurge, Open Culture, Coursera, arXiv (cs.CY), Inside Higher Ed | 🟢 P2 | ✅ Implemented (6 curated sources; Class Central/Khan/dedao/ncpssd/wanfang GFW-blocked/dead, disabled) |
| **Legal Compliance** | SCOTUSblog, Oyez, GDPR.eu, court.gov, 澎湃新闻 (The Paper) | 🟢 P2 | ✅ Implemented (5 curated sources; IAPP/Law.com 404, disabled) |
| **General News** | Guardian Open Platform, AP API, 知乎日报, 界面新闻 (Jiemian), Wired, France24, NPR, Ars Technica, The Verge, Engadget, SpaceNews, 人民网 (People's Daily), CGTN, 新浪娱乐 (Sina) | 🟢 P2 | ✅ Implemented (14 curated sources; GDELT/Google News/NYT/Medium/Atlantic/Time/Mastodon/Bluesky/wechat2rss GFW-blocked or throttled, disabled) |
| **Gaming** | IGN RSS, GamesIndustry.biz, 机核网 gcores, GameSpot, PC Gamer, Eurogamer, Rock Paper Shotgun, Gematsu | 🟢 P2 | ✅ Implemented (8 curated sources; Polygon/游研社-via-GoogleNews disabled) |
| **B2B / Enterprise** | ProductHunt, TechCrunch, Crunchbase News, HackerNews, SaaStr, B2B News Network, MarTech | 🟢 P2 | ✅ Implemented (7 curated sources; a16z feed 404, disabled) |
| **Retail / E-commerce** | Retail Dive, Modern Retail, Shopify News, Digiday, RetailWire | 🟢 P2 | ✅ Implemented (5 curated sources; 亿邦-via-GoogleNews disabled) |
| **English Learning** | Duolingo Blog (RSS), NPR News (RSS) | 🟢 P2 | ✅ Implemented (2 curated sources) |
| **French Learning** | France24 (RSS), Le Figaro (RSS) | 🟢 P2 | ✅ Implemented (2 curated sources) |
| **Hindi Learning** | Aaj Tak (RSS), BBC Hindi (RSS), NDTV Khabar (RSS), Amar Ujala (RSS) | 🟢 P2 | ✅ Implemented (4 curated sources) |
| **Italian Learning** | ANSA Cronaca, TGCOM24, Il Post | 🟢 P2 | ✅ Implemented (3 curated sources) |
| **Korean Learning** | Donga, Khan | 🟢 P2 | ✅ Implemented (2 curated sources) |
| **Portuguese Learning** | Observador (RSS), G1 Globo (RSS), Folha de S.Paulo (RSS), Público (RSS) | 🟢 P2 | ✅ Implemented (4 curated sources) |
| **Russian Learning** | TASS (RSS), RT News (RSS), Interfax (RSS) | 🟢 P2 | ✅ Implemented (3 curated sources) |
| **Spanish Learning** | 20 Minutos (RSS), El País (RSS), El Mundo (RSS), BBC Mundo (RSS) | 🟢 P2 | ✅ Implemented (4 curated sources) |

## Development

```bash
pip install -e ".[dev]"
make test        # pytest -v
make lint        # ruff check + mypy
```

## Known Limitations

| Feature | Status | Notes |
|---------|--------|-------|
| Config override system (~/.autoinfo/overrides/) | 📋 Planned | Per-project config layering |
| Multi-user / collaboration (auth, teams) | 📋 Planned | `user_id` fields in place; full auth v2 (see `docs/dev/specs/multi-tenancy-auth.md`, #165) |

- **MOBI** requires calibre; CI and nightly do not install it, so the success path is not automatically exercised (see `docs/known-limitations/demo-quality-residuals.md`).
- **`tools/list` omits `outputSchema`** by design: the canonical envelope is documented once (ADR 0010); per-tool schemas are a follow-up (#581/#588).
- **REST API has no auth** and binds `127.0.0.1` by default — do not expose it to untrusted networks.

> The historical wave-by-wave scenario-count chronicle moved to
> `docs/archive/readme-known-limitations-chronicle.md`.
> See `docs/dev/founder-expectations.md` §14 for the full deferred-items catalog.
> Cross-dimensional catalog (keystone product matrix): `docs/dev/cross-dimensional-catalog.md` (126 cells = 7×18 lifecycle stages; 42 is the catalogued gap count, 5 gap types across A1-A7 Pipeline × B1/B2/B3 Users).
> Some high-value sources (Bloomberg, Reuters Eikon, WSJ) remain blocked by cost/policy — see `docs/known-limitations/blocked-sources.md`.

## License

MIT
