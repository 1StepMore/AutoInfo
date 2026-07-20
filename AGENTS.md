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
2. **All capabilities** are exposed as MCP tools (35+ tools across 10 categories)
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
└── src/                            # Implementation (to be built)
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
| **Do not run `init`** | Init is a human operation. You connect to an already-initialized MCP server. |
| **Do not manage API keys** | Keys are configured in env vars or config. You don't store, generate, or transmit keys. |
| **Do not write to 03-Wiki** | Only human can promote Draft→Wiki. |
| **Do not create Draft from outside** | Draft must come from 01-Raw. |
| **Do not demote Wiki entries** | Wiki is append-only. Tag `deprecated` only upon human command. |
| **Do not delete source or domain config** | Human decides what sources/domains to remove. |
| **Do not modify `.autoinfo/config.yaml` directly** | Use MCP tools (`add_source`, `add_topic`). |
| **Do not run `autoinfo doctor`** | Use `diagnose_system()` MCP tool instead — returns structured health data. |

## Tool Discovery Guidance

35+ MCP tools organized by category:

| Category | Key Tools |
|----------|-----------|
| **System** | `health_check`, `diagnose_system`, `get_config`, `list_available_models` |
| **Domain** | `list_domains`, `get_domain_schema`, `activate_domain` |
| **Source** | `add_source` (idempotent), `add_sources` (batch), `test_source`, `get_source_health` |
| **Topic** | `list_topics`, `add_topic`, `list_keywords` |
| **Collection** | `collect_sources` (with `dry_run=true`), `get_collection_progress`, `get_collection_diff` |
| **Summary** | `list_summaries`, `flag_for_knowledge_base`, `rate_item` |
| **KB** | `search_knowledge_base`, `get_kb_entry`, `create_kb_draft`, `list_kb_tier` |
| **Output** | `generate_digest`, `generate_tutorial`, `list_output_templates` |
| **Config** | `get_effective_llm_config` |

**Discovery flow**:
1. Call `list_domains()` to see available domains
2. Call `get_domain_schema(domain)` to see available extraction fields
3. Call `list_available_models()` to see configured LLM models
4. Call `list_output_templates(domain)` to see output types

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

## Status

**Greenfield project**. No code has been written yet. This file describes what
will exist once the MCP server is implemented. Currently, connecting to the
MCP server will fail because the server doesn't exist yet.

## References

- `docs/dev/founder-expectations.md` — Full specification (32 expectations, 13 technical decisions)
- `docs/dev/Hermes-KnowledgeBase-介绍.md` — Reference KB pipeline model
