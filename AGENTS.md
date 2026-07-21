# AutoInfo — Agent Guide

## What Is AutoInfo

AutoInfo is a **universal information tracking and knowledge base platform**.
You configure sources and topics; AutoInfo handles collection, LLM-based
structured extraction, summarization, and builds a queryable knowledge base.

**Key principle**: Domain-agnostic. The three demo domains (medical-research,
ai-commercial, language-learning) are configurations, not hardcoded features.
Users define their own domains.

## Agent Operating Model

AutoInfo is designed **agent-first**:

```
Director-user (human) ──NL──> Agent ──MCP tools──> AutoInfo MCP Server
                                ↑                           │
                                └──── structured JSON-RPC ───┘
```

1. **You (the agent)** connect to AutoInfo's MCP server over stdio or SSE
2. **All capabilities** are exposed as MCP tools (65 tools across 15 categories)
3. **CLI mirrors MCP** — `--domain X --topic Y` flags map 1:1 to tool parameters
4. **Human director** communicates intent to you in natural language; you translate to tool calls
5. **Human can also use CLI directly** as a fallback, but the primary interface is through you

## Project Structure

```
AutoInfo/
├── AGENTS.md                       # ← You are here
├── README.md                       # Project overview
├── pyproject.toml                  # Python packaging
├── Makefile                        # Build automation
├── .gitignore
├── docs/
│   └── dev/
│       ├── founder-expectations.md # Full spec (32 expectations, 13 tech decisions)
│       └── Hermes-KnowledgeBase-介绍.md  # KB pipeline reference model
├── .opencode/
│   └── skills/                     # Agent skill definitions
├── src/
│   └── autoinfo/
│       ├── cli/                     # 14 CLI command groups
│       ├── mcp/                     # MCP server (70+ tools)
│       ├── api/                     # REST API (FastAPI, port 8741)
│       ├── kb.py                    # Knowledge base pipeline (4-tier Hermes)
│       ├── collectors/              # Source handlers (PubMed, RSS, Web, Email, PDF)
│       ├── llm.py                   # LLM extraction engine
│       ├── output.py                # Output generation (digest, report, tutorial, export)
│       ├── cefr.py                  # CEFR classification (EN/ZH/JA)
│       ├── email_sender.py          # SMTP email sending
│       ├── keywords.py              # Keyword management
│       ├── qa.py                    # Q&A with LLM synthesis
│       └── quality.py               # Quality gates G1-G5
```

## Architecture Rules

These are hard constraints derived from `founder-expectations.md`.
Violating them produces incorrect behavior.

### KB Pipeline (Hermes Model)

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

### Quality Gates (Advisory, Not Blocking)

AutoInfo never discards collected content. Low-quality items are flagged,
hidden from default views, or demoted — never deleted.

| Gate | Priority |
|------|----------|
| G1: Source authority (tier check) | 🔴 P0 |
| G2: Dedup (URL + fuzzy title) | 🔴 P0 |
| G3: Relevance scoring (0-100) | 🔴 P0 |
| G4: Summary factual consistency | 🟡 P1 |
| G5: Translation accuracy | 🟡 P1 |

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

65 MCP tools organized by category:

| Category | Key Tools |
|----------|-----------|
| **System** | `health_check`, `diagnose_system`, `get_config`, `list_available_models` |
| **Discovery** | `list_domains`, `get_domain_schema`, `get_effective_llm_config`, `list_output_templates`, `activate_domain`, `deactivate_domain`, `get_domain_config` |
| **Source** | `add_source`, `add_sources`, `remove_source`, `test_source`, `list_sources`, `get_source_health` |
| **Topic** | `add_topic`, `remove_topic`, `list_topics`, `list_keywords` |
| **Collection** | `collect_sources`, `get_collection_progress`, `get_collection_status`, `process_collection`, `get_processing_progress`, `batch_run` |
| **KB** | `search_knowledge_base`, `get_kb_entry`, `list_summaries`, `get_summary`, `create_kb_draft`, `reject_kb_draft`, `list_kb_tier`, `reindex_kb`, `flag_for_knowledge_base`, `vector_search`, `faceted_search` |
| **Output** | `generate_digest`, `generate_report`, `generate_tutorial`, `generate_presentation`, `localize_content`, `export_kb` |
| **CEFR** | `classify_cefr` |
| **Keywords** | `list_keywords`, `manage_keyword` |
| **Email** | `send_email`, `get_email_config`, `set_email_config` |
| **Q&A** | `query_collected` |
| **Graph** | `query_knowledge_graph` |
| **Relations** | `link_items`, `get_item_relations` |
| **Monitor** | `get_collection_stats`, `get_collection_diff`, `get_source_health`, `rate_item`, `list_active_collections` |
| **Cron** | `list_schedules`, `add_schedule`, `remove_schedule`, `run_schedules`, `cron_install`, `cron_uninstall` |
| **Projects** | `list_projects`, `get_project_assets`, `archive_project` |
| **Config** | `get_effective_llm_config` |

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
3. `faceted_search(domain="medical-research", filters={"source_type": "pubmed", "relevance_min": 70})` → filtered *(requires AutoInfo ≥ v1.2)*
```
→ Ranked results from KB with source citations.

### "Export knowledge base to PDF"
```
1. `export_kb(domain="medical-research", format="pdf", topic="IVF breakthroughs")` → generates PDF report
```
→ PDF file written to `exports/medical-research/IVF-breakthroughs-report.pdf`

### "Manage keywords for a domain"
```
1. `list_keywords(domain="medical-research")` → view current keywords
2. `manage_keyword(domain="medical-research", action="add", keyword="CRISPR")` → add new keyword
3. `manage_keyword(domain="medical-research", action="remove", keyword="obsolete-term")` → remove keyword
```
→ Keywords updated for source filtering and topic matching.

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

Collection and processing can take 30-120 seconds depending on item count and LLM speed. Poll for progress:

1. Start collection: `collect_sources(domain="medical", topic="IVF", async=true)` → get `collection_id`
2. Poll every 5 seconds:
   ```
   while True:
       status = get_collection_progress(collection_id=collection_id)
       if status["is_complete"]:
           break
       sleep(5)
   ```
3. Start processing: `process_collection(domain="medical")` → get `processing_id`
4. Poll: `get_processing_progress(domain="medical")` → check `is_complete`
5. When done: `list_summaries(domain="medical")` to review results

## Status

| Component | Status |
|-----------|--------|
| Config system | ✅ LLM task config, per-task model, fallback chains, schema versioning |
| CLI | ✅ 14 command groups (init, doctor, collect, process, status, summaries, sources, topics, kb, output, cron, knowledge, cefr, email, keywords) |
| Collection | ✅ PubMed, RSS, Web (trafilatura+Playwright), scheduled via crond, crontab install/uninstall |
| LLM extraction | ✅ Custom extraction fields, TL;DR, key points, entities, G4 factual consistency |
| Quality gates | ✅ G1-G5 advisory gates (G4 factual consistency, G5 translation accuracy) |
| KB pipeline | ✅ 4-tier Hermes model (00-Inbox → 01-Raw → 02-Draft → 03-Wiki), git versioning + SHA tracking |
| Search | ✅ Hybrid (FTS5 keyword + sqlite-vec vector), faceted (7 filters) |
| Q&A | ✅ FTS5 + LLM synthesis with source citations |
| Output generation | ✅ Digest, report (Markdown/JSON/PDF), tutorial, presentation (Jinja2 + LLM) |
| Translation | ✅ LLM-based source→target |
| Knowledge graph | ✅ Entity extraction + relation discovery |
| REST API | ✅ FastAPI CRUD (port 8741, /api/v1/entries, /health, /dashboard) |
| Web UI Dashboard | ✅ Bootstrap 5, collection stats, KB search, source health |
| MCP server | ✅ 65 MCP tools across 15 categories |
| Obsidian wiki links | ✅ `[[wiki links]]` in KB Markdown files |
| CEFR classification | ✅ LLM-based EN/ZH/JA (language-learning domain) |
| Email sending | ✅ SMTP sender (digest delivery) |
| Multi-user foundation | ✅ user_id fields on entries (no auth/teams yet) |
| Export | ✅ Markdown, JSON, SQLite, PDF, CSV, GraphML |
| Schema versioning | ✅ DB schema version markers in SQLite |
| Demo domains | ✅ medical-research, ai-commercial, language-learning |
| Test suite | ✅ 1134 tests (35+ test files, 105 v1.2 integration tests) |

## References

- `docs/dev/founder-expectations.md` — Full specification (32 expectations, 13 technical decisions)
- `docs/dev/Hermes-KnowledgeBase-介绍.md` — Reference KB pipeline model
