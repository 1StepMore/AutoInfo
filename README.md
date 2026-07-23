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
- **Knowledge base (Hermes model)** — 4-tier pipeline: Inbox → Raw → Draft → Wiki (Markdown + SQLite), with git versioning and `[[wiki links]]`
- **KB import** — Import content from 4 formats (PDF, Markdown, HTML, JSON) directly into 01-Raw
- **Hybrid search** — FTS5 keyword + sqlite-vec vector embeddings, faceted filtering
- **REST API** — Full CRUD over HTTP (FastAPI, port 8741), no auth (localhost security)
- **Web UI Dashboard** — Bootstrap 5, collection stats, KB search, source health overview
- **CEFR classification** — LLM-based EN/ZH/JA reading level scoring for language learning
- **Output formats** — Markdown, JSON, PDF, **HTML** (digest/report via Jinja2, presentation via Reveal.js CDN)
- **Translation QA pipeline** — 5 lite quality gates, back-translation verification, multi-round refinement, terminology guardrails, composite quality scoring
- **Email sending** — SMTP-based digest delivery (manual and cron-scheduled)
- **Webhook push** — Per-item webhook notification on collected content
- **Quality gates G1-G5** — Source authority, dedup, relevance, factual consistency, translation accuracy (all advisory)
- **Agent-native** — 72 MCP tools. Agent operates, human directs.
- **BYOK** — Bring your own LLM keys. Multi-provider via LiteLLM/OpenRouter.
- **Domain-agnostic** — 3 demo domains (medical, AI commercial, language learning)

## Status

| Component | Status |
|-----------|--------|
| Config system | ✅ LLM task config, per-task model, fallback chains, schema versioning |
| CLI | ✅ 17 command groups (init, doctor, collect, process, status, summaries, sources, topics, domain, kb, output, cron, knowledge, cefr, email, keywords, clean) |
| Collection | ✅ PubMed, RSS, Web (trafilatura+Playwright), webhook (HMAC), email (IMAP), PDF (PyMuPDF), scheduled via crond |
| LLM extraction | ✅ Custom extraction fields, TL;DR, key points, entities, G4 factual consistency, token usage tracking |
| Translation QA pipeline | ✅ 5 lite quality gates, back-translation verification, terminology guardrails, composite scoring, translator-qa-skill |
| Quality gates | ✅ G1-G5 advisory gates (G4 factual consistency, G5 translation accuracy) |
| KB pipeline | ✅ 4-tier Hermes model (00-Inbox → 01-Raw → 02-Draft → 03-Wiki), git versioning + SHA tracking |
| KB import | ✅ 4 formats (PDF, Markdown, HTML, JSON) → 01-Raw via `import_kb` MCP tool |
| Search | ✅ Hybrid (FTS5 keyword + sqlite-vec vector), faceted (7 filters) |
| Q&A | ✅ FTS5 + LLM synthesis with source citations |
| Output generation | ✅ Digest, report (Markdown/JSON/PDF/HTML), tutorial, presentation (Jinja2 + LLM, Reveal.js CDN) |
| Translation | ✅ LLM-based source→target |
| Knowledge graph | ✅ Entity extraction + relation discovery |
| REST API | ✅ FastAPI CRUD (port 8741, /api/v1/entries, /health, /dashboard) |
| Web UI Dashboard | ✅ Bootstrap 5, collection stats, KB search, source health |
| MCP server | ✅ 72 tools across 16 categories |
| Domain management | ✅ `add_domain`/`remove_domain` MCP tools, `autoinfo domain` CLI (add/list/show/remove/activate/deactivate) |
| Webhook push | ✅ Per-item webhook notification on collection via `set_domain_webhooks`/`get_domain_webhooks` |
| Scheduled digest | ✅ Cron-based email digest delivery (SMTP + crontab schedule) |
| Agent alerting | ✅ Polling-based source health monitoring documented (agent-alerting.md) |
| Obsidian wiki links | ✅ `[[wiki links]]` in KB Markdown files |
| CEFR classification | ✅ LLM-based EN/ZH/JA (language-learning domain) |
| Email sending | ✅ SMTP sender (digest delivery) |
| Multi-user foundation | ✅ user_id fields on entries (no auth/teams yet) |
| Export | ✅ Markdown, JSON, SQLite, PDF, CSV, GraphML |
| Schema versioning | ✅ DB schema version markers in SQLite |
| Demo domains | ✅ medical-research, ai-commercial, language-learning |
| Test suite | ✅ 1134 tests (35+ test files, 105 v1.2 integration tests) |

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Initialize with demo domain
autoinfo init --demo medical-research

# Configure LLM key
export AUTOINFO_LLM_API_KEY="sk-..."

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
        ├── autoinfo summaries list | status | kb search
        ├── autoinfo output digest | report | tutorial | export
        ├── REST API (FastAPI, port 8741)
        └── MCP server (72 tools)
```

## CLI Commands (17 groups)

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
autoinfo domain add|list|show|remove|activate|deactivate  # Domain management
autoinfo kb search|create-draft|promote|reject-draft|list-tiers|reindex
autoinfo output digest|report|tutorial|presentation|export|translate|list-templates
autoinfo cron run|list-schedules|add-schedule|remove-schedule|install|uninstall
autoinfo cefr classify|batch        # CEFR text classification
autoinfo email send|config          # SMTP email sending
autoinfo keywords add|remove|list   # Keyword management
autoinfo knowledge graph            # Knowledge graph export
autoinfo clean                       # Clean temporary artifacts
```

## MCP Tools (72)

| Category | Tools |
|----------|-------|
| **System** | health_check, diagnose_system, get_config, list_available_models |
| **Discovery** | list_domains, list_available_platforms, get_domain_schema, get_effective_llm_config, list_output_templates, activate_domain, deactivate_domain, get_domain_config |
| **Domain** | add_domain, remove_domain |
| **Source** | add_source, add_sources, remove_source, test_source, list_sources, get_source_health |
| **Topic** | add_topic, remove_topic, list_topics, list_keywords, approve_keyword, reject_keyword, suggest_keywords |
| **Collection** | collect_sources, get_collection_progress, get_collection_status, process_collection, get_processing_progress, batch_run |
| **KB** | search_knowledge_base (hybrid), get_kb_entry, list_summaries, get_summary, create_kb_draft, reject_kb_draft, list_kb_tier, reindex_kb, flag_for_knowledge_base, vector_search, faceted_search |
| **KB Relations** | link_items, get_item_relations |
| **KB Versioning** | get_entry_history, restore_entry_version |
| **KB Monitor** | get_collection_stats, get_collection_diff |
| **KB Graph** | query_knowledge_graph |
| **Output** | list_output_templates, generate_digest, generate_report (Markdown/JSON/PDF/HTML), generate_tutorial, generate_presentation, localize_content |
| **Export/Import** | export_kb, import_kb |
| **CEFR** | classify_cefr |
| **Keywords** | approve_keyword, reject_keyword, suggest_keywords |
| **Email** | send_email_digest |
| **Q&A** | query_collected |
| **Custom Extraction** | extract_fields, get_extraction |
| **Cron** | list_schedules, add_schedule, remove_schedule, run_schedules |
| **Source Health** | get_source_health, rate_item |
| **Projects** | init_project, list_projects, get_project_assets, archive_project |
| **Monitor** | list_active_collections |
| **Webhooks** | set_domain_webhooks, get_domain_webhooks |

## Demo Domains

| Domain | Sources | Priority | Status |
|--------|---------|----------|--------|
| **Medical Research** | PubMed (REST API), arXiv, CrossRef, Unpaywall | 🔴 P0 | ✅ Implemented (4 curated sources) |
| **AI Commercial Intelligence** | TechCrunch RSS, ProductHunt API, Crunchbase, LMSYS | 🟡 P1 | ✅ Implemented (4 curated sources) |
| **Language Learning** | Project Gutenberg, BBC Learning English, news-in-levels, commonlit | 🟢 P2 | ✅ Implemented (4 curated sources) |

## Development

```bash
pip install -e ".[dev]"
make test        # pytest -v
make lint        # ruff check + mypy
```

## Known Limitations

AutoInfo v1.4 adds **user-defined domains** via CLI/MCP, **translation QA pipeline** (5 lite gates + back-translation verification + terminology guardrails), **HTML format output** (digest/report/presentation), **KB import** (4 formats → 01-Raw), **per-item webhook push**, and **cron-based email digest delivery** with **agent proactive alerting** documentation. v1.3 added ErrorCode centralization, MCP schema hardening, and LLM extraction resilience. The following items remain explicitly deferred:

| Feature | Status | Notes |
|---------|--------|-------|
| Config override system (~/.autoinfo/overrides/) | 📋 Planned | Per-project config layering |
| Multi-user / collaboration (auth, teams) | 📋 Planned | user_id fields in place; full auth v2 |

> See `docs/dev/founder-expectations.md` §14 for the full deferred-items catalog.

## License

MIT
