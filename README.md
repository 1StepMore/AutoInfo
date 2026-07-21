# AutoInfo

**Universal information tracking and knowledge base platform.**

Configure sources and topics. AutoInfo handles the rest: automated collection,
LLM-based structured extraction, summarization, and a queryable knowledge base.

> "AutoInfo is your information assistant — not helping you search, but
> automating the entire pipeline from collection to knowledge curation."
>
> Domain-agnostic. Agent-native. BYOK.

## Features

- **Multi-source collection** — RSS, REST APIs (PubMed E-utilities), web pages (trafilatura + Playwright)
- **LLM-powered extraction** — TL;DR, key points, entity extraction, relevance scoring, custom field extraction
- **Knowledge base (Hermes model)** — 4-tier pipeline: Inbox → Raw → Draft → Wiki (Markdown + SQLite)
- **Full-text search** — FTS5 with CJK support across all KB tiers
- **Quality gates G1-G5** — Source authority, dedup, relevance, factual consistency (advisory)
- **Agent-native** — 56 MCP tools. Agent operates, human directs.
- **BYOK** — Bring your own LLM keys. Multi-provider via LiteLLM/OpenRouter.
- **Domain-agnostic** — 3 demo domains (medical, AI commercial, language learning)

## Status

| Component | Status |
|-----------|--------|
| Config system | ✅ LLM task config, per-task model, fallback chains |
| CLI | ✅ 12 command groups (init, doctor, collect, process, status, summaries, sources, topics, kb, output, cron, knowledge) |
| Collection | ✅ PubMed, RSS, Web (trafilatura+Playwright), scheduled via crond |
| LLM extraction | ✅ Custom extraction fields, TL;DR, key points, entities, G4 factual consistency |
| Quality gates | ✅ G1-G5 advisory gates (G4 factual consistency, G5 translation accuracy) |
| KB pipeline | ✅ 4-tier Hermes model (00-Inbox → 01-Raw → 02-Draft → 03-Wiki) |
| Search | ✅ FTS5 across all tiers |
| Q&A | ✅ FTS5 + LLM synthesis with source citations |
| Output generation | ✅ Digest, report, tutorial, presentation (Jinja2 + LLM) |
| Translation | ✅ LLM-based source→target |
| Knowledge graph | ✅ Entity extraction + relation discovery |
| MCP server | ✅ 56 MCP tool areas across 12 categories (6 new in v1.1) |
| Export | ✅ Markdown, JSON, SQLite |
| Demo domains | ✅ medical-research, ai-commercial, language-learning |
| Test suite | ✅ 720+ tests |

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
   knowledge/{Raw|Draft|Wiki}/ ───→ Markdown + SQLite + FTS5
        │
        ├── autoinfo summaries list | status | kb search
        ├── autoinfo output digest | report | tutorial | export
        └── MCP server (56 tools)
```

## CLI Commands (12 groups)

```bash
autoinfo init --demo <domain>       # Initialize project
autoinfo doctor                      # System health check
autoinfo collect --domain <d> ...   # Collect from sources
autoinfo process --domain <d> ...   # LLM extraction + storage
autoinfo status                      # Collection stats
autoinfo summaries list|flag|show   # Browse summaries
autoinfo sources add|list|remove|test  # Source management
autoinfo topics add|list|remove     # Topic management
autoinfo kb search|create-draft|reject-draft|list-tiers|reindex
autoinfo output digest|report|tutorial|presentation|export|translate|list-templates
autoinfo cron run|list-schedules|add-schedule|remove-schedule
```

## MCP Tools (56)

| Category | Tools |
|----------|-------|
| **System** | health_check, diagnose_system, get_config, list_available_models |
| **Discovery** | list_domains, get_domain_schema, get_effective_llm_config, list_output_templates, activate_domain, deactivate_domain, get_domain_config |
| **Source** | add_source, add_sources, remove_source, test_source, list_sources, get_source_health |
| **Topic** | add_topic, remove_topic, list_topics, list_keywords |
| **Collection** | collect_sources, get_collection_progress, get_collection_status, process_collection, get_processing_progress, batch_run |
| **KB** | search_knowledge_base, get_kb_entry, list_summaries, get_summary, create_kb_draft, reject_kb_draft, list_kb_tier, reindex_kb, flag_for_knowledge_base |
| **Output** | generate_digest, generate_report, generate_tutorial, generate_presentation, localize_content, export_kb |
| **Q&A** | query_collected |
| **Graph** | query_knowledge_graph |
| **Relations** | link_items, get_item_relations |
| **Monitor** | get_collection_stats, get_collection_diff, get_source_health, rate_item, list_active_collections |
| **Cron** | list_schedules, add_schedule, remove_schedule, run_schedules |
| **Projects** | list_projects, get_project_assets, archive_project |

## Demo Domains

| Domain | Sources | Priority | Status |
|--------|---------|----------|--------|
| **Medical Research** | PubMed (REST API) | 🔴 P0 | ✅ Implemented |
| **AI Commercial Intelligence** | TechCrunch RSS, ProductHunt API | 🟡 P1 | ✅ Implemented |
| **Language Learning** | Project Gutenberg, BBC Learning English | 🟢 P2 | ✅ Implemented |

## Development

```bash
pip install -e ".[dev]"
make test        # pytest -v
make lint        # ruff check + mypy
```

## Known Limitations

AutoInfo v1.1 closes most gaps identified in the founder's spec. The following items are explicitly deferred to future releases:

| Feature | Status | Notes |
|---------|--------|-------|
| Vector/hybrid search (FTS5 + embeddings) | 📋 Planned | sqlite-vec in pyproject.toml, not yet wired |
| REST API | 📋 Planned | Read-only KB access via HTTP |
| Obsidian [[wiki links]] | 📋 Planned | KB native wiki-link support |
| CEFR text classification | 📋 Planned | Language-learning domain feature |
| Config override system (~/.autoinfo/overrides/) | 📋 Planned | Per-project config layering |
| Schema versioning / migration tool | 📋 Planned | DB schema version markers |
| CSV/PDF/GraphML export formats | 📋 Planned | Currently supports JSON + Markdown + SQLite |

> These features are tracked for v1.2+ releases. See `docs/dev/founder-expectations.md` for the full specification.

## License

MIT
