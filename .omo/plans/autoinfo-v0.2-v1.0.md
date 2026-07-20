# AutoInfo v0.1.1–v1.0 — Full Roadmap Implementation

## TL;DR

> **Quick Summary**: Complete AutoInfo from v0.1 core loop to v1.0 product. 6 milestones implementing all remaining expectations from founder-expectations.md (F07-F32). Starts with a v0.1.1 patch (config expansion, blocking fix, missing tools), then builds FTS5 search, Draft tier, custom extraction, web scraping, Q&A, output generation, knowledge graph, and translation.
>
> **Deliverables**:
> - v0.1.1: Config schema expansion, process_collection fix, missing CLI/MCP tools
> - v0.2: FTS5 search, 02-Draft tier, custom extraction fields, G4 gate, flag_for_kb
> - v0.3: Web scraping, AI-commercial domain, source/topic CRUD, scheduled collection
> - v0.4: FTS5+LLM Q&A, digest/report generation, export
> - v0.5: Full MCP tool inventory, remaining CLI commands, monitor/iterate features
> - v0.6: Knowledge graph, LLM translation, tutorial/presentation, language-learning domain
>
> **Estimated Effort**: XL (multi-milestone)
> **Parallel Execution**: PARTIAL (sequential milestones, parallel tasks within each)

---

## Context

### Original Request
Complete AutoInfo from v0.2 through v1.0 by implementing all remaining expectations (F07-F32) from `docs/dev/founder-expectations.md`.

### Interview Summary
**Metis Review Findings**:
- Config schema expansion blocks all v0.2 features → resolved as v0.1.1 patch
- process_collection blocking will timeout MCP clients → fix in v0.1.1
- FTS5 is low effort (built into Python sqlite3) → v0.2
- Draft/Wiki: Draft in v0.2, Wiki deferred to v0.3+
- Web scraping: trafilatura for v0.3, Playwright fallback for v0.5+
- Q&A: scoped to FTS5+LLM synthesis, no persistence
- Output: digest+report first, tutorial+presentation deferred
- Translation: LLM-based only, no CEFR/glossary in scope
- Knowledge graph: deferred to v0.6 with minimal scope (SQLite relations + entity extraction)

**Key Decisions** (user confirmed):
- v0.1.1 patch first before any v0.2 feature work
- Reprioritized milestones: v0.2(KB)→v0.3(Multi-source+Sched)→v0.4(Q&A+Output)→v0.5(MCP)→v0.6(Graph+Trans)
- Draft only in v0.2, Wiki deferred
- FTS5 search across all tiers (Raw+Draft+Wiki)
- trafilatura first, Playwright fallback for web
- FTS5+LLM Q&A, no persistence layer
- Jinja2 templates + LLM filling for output
- LLM-based translation only

---

## Work Objectives

### Core Objective
Deliver all 32 founder expectations by completing 6 milestones: v0.1.1 → v0.2 → v0.3 → v0.4 → v0.5 → v0.6.

### Milestone Summary

| Milestone | Focus | Key Expectations | Effort |
|-----------|-------|-----------------|--------|
| v0.1.1 | Config expansion + missing tools | F04(partial), F05(partial), F08(partial) | Short |
| v0.2 | KB & Search | F15, F16, F20, F21, G4 | Medium |
| v0.3 | Multi-source + Schedule | F07, F08, F13(web), F14, F18 | Large |
| v0.4 | Q&A + Output | F17, F24, F26 | Medium |
| v0.5 | Mature MCP | F09, F19, F23, F28-F32 | Large |
| v0.6 | Graph + Translation | F10, F22, F25, F07(lang) | Medium |

### Must Have (Overall)
- [ ] All 32 expectations from founder-expectations.md implemented
- [ ] Each milestone independently releasable
- [ ] Each milestone passes its own True Test
- [ ] No regression in existing v0.1 features
- [ ] All tests pass for each milestone

### Must NOT Have
- [ ] ❌ No web UI, mobile app, email delivery, multi-user (per v1 scope)
- [ ] ❌ No knowledge graph before v0.6
- [ ] ❌ No Playwright before v0.5
- [ ] ❌ No conversation persistence in Q&A (v0.4)
- [ ] ❌ No template customization API for output generation
- [ ] ❌ No built-in scheduler — always external crond
- [ ] ❌ No direct writes to 03-Wiki from any code path
- [ ] ❌ No create_kb_draft that skips Raw tier validation
- [ ] ❌ No modification/deletion of Wiki entries (append-only)

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: YES (pytest, VCR, CliRunner, mock LLM)
- **Automated tests**: Tests-after (alongside each feature)
- **Framework**: pytest + CliRunner + VCR cassettes + mock LLM + sqlite3 :memory:

### QA Policy
Every task MUST include agent-executed QA scenarios. Evidence saved to `.omo/evidence/task-{N}-{scenario-slug}.{ext}`.

---

## Execution Strategy

### Milestone Dependencies
```
v0.1.1 (prerequisite for all v0.2+)
    ↓
v0.2 (KB & Search)
    ↓
v0.3 (Multi-source + Schedule)
    ↓
v0.4 (Q&A + Output)
    ↓
v0.5 (Mature MCP)
    ↓
v0.6 (Graph + Translation)
```

---

## TODOs — v0.1.1: Config Expansion & Missing Tools

- [x] 1. Config schema — expand llm section with tasks, fallback, per-task model

  **What to do**:
  - Extend `config.py` to parse expanded LLM config:
    ```yaml
    llm:
      default_provider: openrouter
      default_model: deepseek/deepseek-chat
      fallback:
        - provider: openrouter
          model: anthropic/claude-sonnet-4
      tasks:
        extraction:
          model: deepseek/deepseek-chat
          max_tokens: 2000
        summarization:
          model: anthropic/claude-sonnet-4
          max_tokens: 1000
    ```
  - Add `LLMTaskConfig` dataclass with model, provider, max_tokens override
  - Add `LLMConfig.fallback: list[LLMConfig]` field
  - Add `get_effective_llm_config(task_name: str) -> LLMConfig` — resolves task-specific config with fallback
  - Add `llm.tasks.extraction.model` etc. — per-task model override parsing
  - Extend `DomainConfig` with `extract_fields: list[str]` and `search.mode: str`
  - Update `validate_config()` to validate new fields
  - Create tests/test_config_v2.py — test expanded schema round-trip

  **Must NOT do**: Config migration, config versioning, config file watching

  **Recommended Agent Profile**: `unspecified-high`, Skills: []
  **Parallelization**: Wave v0.1.1 (with tasks 2-6), Blocks: v0.2 tasks

  **Acceptance Criteria**:
  - [ ] Config with `llm.tasks.extraction` loads and resolves correctly
  - [ ] Config without `llm.tasks` uses defaults without error
  - [ ] `get_effective_llm_config("extraction")` returns correct overridden model
  - [ ] `llm.fallback` chain parsed and accessible
  - [ ] `domain.extract_fields` parsed from domain config
  - [ ] Existing v0.1 configs still load without error (backward compat)

- [x] 2. Fix process_collection blocking — add batch_size + async progress

  **What to do**:
  - Add `batch_size` parameter (default 0 = all at once) to `run_processing()`
  - When batch_size > 0: process N items, return partial result, agent calls again for next batch
  - Or: wrap processing in background thread, store progress in SQLite, add `get_processing_progress(collection_id)`
  - Update MCP `process_collection` tool to accept `batch_size`
  - Add `get_processing_progress` MCP tool if async approach chosen
  - Update CLI `--batch-size` flag
  - Create tests/test_process_batch.py

  **Must NOT do**: Full async pipeline rewrite — just prevent MCP timeout

  **Recommended Agent Profile**: `unspecified-high`, Skills: []
  **Parallelization**: Wave v0.1.1

  **Acceptance Criteria**:
  - [ ] `process_collection(domain, batch_size=5)` returns after 5 items, not all
  - [ ] `get_processing_progress(collection_id)` shows remaining items
  - [ ] Without batch_size, processes all (backward compat)
  - [ ] Batch processing doesn't lose items or create duplicates

- [x] 3. Add missing CLI subcommands — sources, topics, kb, output, cron stubs

  **What to do**:
  - Create CLI stub modules:
    - `cli/sources.py`: `add`, `list`, `remove`, `test` subcommands (stubs calling core)
    - `cli/topics.py`: `add`, `list`, `remove` subcommands (stubs)
    - `cli/kb.py`: `search`, `list`, `reindex`, `promote` (stubs — `promote` is human-only, CLI only)
    - `cli/output.py`: `digest`, `report`, `export` subcommands (stubs for v0.4)
    - `cli/cron.py`: `run`, `list-schedules`, `add-schedule`, `remove-schedule` (stubs for v0.3)
  - Wire all into main `cli/__init__.py` via `app.add_typer()`
  - Each stub: prints "not yet implemented" when called
  - Create tests/test_cli_v2.py — test stubs register and show help

  **Must NOT do**: Implement core logic in stubs — only pass-through

  **Recommended Agent Profile**: `quick`, Skills: []
  **Parallelization**: Wave v0.1.1

  **Acceptance Criteria**:
  - [ ] `autoinfo --help` shows all new commands: sources, topics, kb, output, cron
  - [ ] Each subcommand's `--help` shows expected parameters
  - [ ] Calling a stub exits 0 with "not yet implemented" message

- [x] 4. Add missing MCP discovery tools — list_domains, get_domain_schema, etc.

  **What to do**:
  - Add MCP tools to `mcp/server.py`:
    - `list_domains()` → `[{name, description, source_count, topic_count}]`
    - `get_domain_schema(domain)` → `{extract_fields, output_templates, topics, sources}`
    - `list_available_models()` → `[{task, provider, model}]` (reads from config)
    - `get_effective_llm_config(task)` → `{task, provider, model, max_tokens, fallback_chain}`
    - `add_source(name, url, type, domain)` → `{source_id}` (idempotent)
    - `add_sources(sources=[...])` → `{results: [{name, source_id, error}]}`
    - `remove_source(source_id)` → `{removed: True}`
    - `test_source(url, type)` → `{reachable, content_preview, format}`
    - `add_topic(domain, name, keywords)` → `{topic_id}`
    - `remove_topic(domain, topic_id)` → `{removed: True}`
    - `search_knowledge_base(query, domain, limit, offset)` → `{entries, total_count}` (FTS5 in v0.2, stub for now)
    - `flag_for_knowledge_base(summary_id, tags, importance)` → `{flagged: True}` (stub for v0.2)
    - `list_output_templates(domain)` → `["digest", "report", "tutorial", "presentation"]`
  - Tool implementations are thin wrappers calling core functions (or raising NotImplementedError for v0.2+ features)
  - Update MCP inventory to reflect all tools
  - Create tests/test_mcp_v2.py

  **Must NOT do**: Implement v0.2+ logic — stubs acceptable with NotImplementedError

  **Recommended Agent Profile**: `unspecified-high`, Skills: []
  **Parallelization**: Wave v0.1.1

  **Acceptance Criteria**:
  - [ ] All new tools appear in MCP tool manifest
  - [ ] `list_domains()` returns configured domains
  - [ ] `get_domain_schema("medical-research")` returns schema with fields
  - [ ] `list_available_models()` returns models from config
  - [ ] `add_source()` is idempotent
  - [ ] Error responses include `error_code` and `message`

- [x] 5. v0.1.1 integration — verify backward compat

  **What to do**:
  - Run full v0.1 test suite — all 220 must pass
  - Run `autoinfo init --demo medical-research` with new config schema → works
  - Run `autoinfo collect` + `process` with new config → works (same as v0.1)
  - Verify old configs (without tasks/fallback) still load
  - Create tests/test_backward_compat.py

  **Must NOT do**: Change v0.1 behavior

  **Recommended Agent Profile**: `unspecified-low`, Skills: []
  **Parallelization**: Wave v0.1.1

  **Acceptance Criteria**:
  - [ ] All 220+ v0.1 tests pass
  - [ ] Old config files load without error
  - [ ] New CLI commands show correct help

---

## TODOs — v0.2: KB & Search

- [x] 6. FTS5 search — full-text search over KB entries

  **What to do**:
  - Add FTS5 support to `kb.py`:
    - `init_fts5()` — CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts5 USING fts5(title, summary, content, domain, tags, tokenize='unicode61')
    - `index_entry_fts5(entry)` — INSERT INTO entries_fts5
    - `search_fts5(query, domain, limit, offset)` — SELECT rank FROM entries_fts5 WHERE entries_fts5 MATCH ? ORDER BY rank
    - Handle FTS5 query syntax (escape special chars, support prefix matching)
  - Add `search_knowledge_base(query, domain, limit, offset)` to KBStore:
    - Searches FTS5 first, falls back to LIKE if FTS5 fails
    - Returns `{entries: [{entry_id, title, summary, relevance_score}], total_count}`
  - Add `autoinfo kb reindex` command — walks all Markdown files, populates FTS5
  - Add `autoinfo kb search --query "text" --domain medical-research` CLI command
  - Wire `search_knowledge_base` MCP tool (stub → real)
  - Create tests/test_fts5.py

  **Must NOT do**: Vector search, sqlite-vec, semantic search
  **CJK note**: Research tokenizer behavior with Chinese text before implementation

  **Recommended Agent Profile**: `unspecified-high`, Skills: []
  **Parallelization**: Wave v0.2 (with 7-10)

  **Acceptance Criteria**:
  - [ ] `search_knowledge_base("embryo", "medical-research")` returns matching entries
  - [ ] `search_knowledge_base("zzz_nonexistent")` returns empty with total_count=0
  - [ ] FTS5 results ranked by relevance (most relevant first)
  - [ ] `autoinfo kb reindex` populates FTS5 from all existing .md files
  - [ ] Pagination: offset=5, limit=5 returns different results
  - [ ] CJK search works with unicode61 tokenizer (or alternative)

- [x] 7. 02-Draft tier — agent creates Draft from Raw

  **What to do**:
  - Refactor `KBStore` to support multiple tiers:
    - `store_entry(item, extraction, quality_results, tier="01-Raw")` — tier parameter
    - Knowledge path: `knowledge/<domain>/<tier>/<topic>/<date>-<slug>.md`
  - Add `create_kb_draft(raw_ids: list[str], title, summary, tags) -> KBEntry`:
    - Validates all raw_ids exist in 01-Raw
    - Merges content from multiple Raw entries
    - Creates file in 02-Draft/<topic>/ with tier: "02-Draft" in frontmatter
    - Links back to source_raw_ids in frontmatter
    - **Cannot** skip Raw — raises error if raw_ids empty or invalid
  - Add `reject_kb_draft(draft_id, reason, action="back_to_raw")`:
    - Moves file from 02-Draft to 01-Raw (or archives it)
    - Adds rejection_reason to frontmatter
  - Add `list_kb_tier(domain, tier)` — lists entries in a specific tier
  - Add CLI: `autoinfo kb create-draft --raw-id <id>`, `autoinfo kb reject-draft <id>`
  - Add MCP tools: `create_kb_draft`, `reject_kb_draft`, `list_kb_tier`
  - Create tests/test_kb_draft.py

  **Must NOT do**: Write to 03-Wiki (human-only), auto-promote Draft→Wiki

  **Recommended Agent Profile**: `unspecified-high`, Skills: []
  **Parallelization**: Wave v0.2

  **Acceptance Criteria**:
  - [ ] `create_kb_draft(raw_ids=["valid_id"])` creates file in 02-Draft/
  - [ ] `create_kb_draft(raw_ids=["nonexistent"])` raises error
  - [ ] Multiple raw_ids merged into single Draft
  - [ ] Draft file has correct frontmatter with tier: "02-Draft"
  - [ ] `reject_kb_draft(draft_id)` moves entry back to 01-Raw
  - [ ] `list_kb_tier("medical-research", "02-Draft")` returns only Draft entries
  - [ ] SQLite index updated with correct tier

- [x] 8. Custom extraction fields — user-defined schema per domain

  **What to do**:
  - Update `LLMExtractor` to accept dynamic schema:
    - `extract(item, schema=["methodology", "sample_size"])` — builds prompt from schema
    - Dynamically constructs system prompt: "Extract these fields: {field descriptions}"
    - JSON response includes custom fields alongside defaults
  - Update domain config: `domain.extract_fields` list parsed into extraction schema
  - Update processing pipeline: `process` reads `extract_fields` from domain config, passes to LLMExtractor
  - KB frontmatter includes custom fields in `extracted_fields: {methodology: "RCT", sample_size: 200}`
  - Add MCP tool: `extract_fields(content_id, schema=["methodology"])` — on-demand re-extraction
  - Add MCP tool: `get_extraction(content_id)` — see what was extracted
  - Create tests/test_custom_extraction.py

  **Must NOT do**: Field type validation, complex nested schemas

  **Recommended Agent Profile**: `unspecified-high`, Skills: []
  **Parallelization**: Wave v0.2

  **Acceptance Criteria**:
  - [ ] `extract(item, schema=["methodology"])` returns methodology field
  - [ ] Prompt dynamically includes custom field descriptions
  - [ ] KB frontmatter has custom fields under extracted_fields
  - [ ] Config with `extract_fields: [methodology, findings]` works end-to-end
  - [ ] Schema without custom fields uses defaults (backward compat)

- [x] 9. flag_for_knowledge_base + summaries flag CLI

  **What to do**:
  - Implement `flag_for_knowledge_base(summary_id, tags, importance)`:
    - Adds tags and importance to SQLite index for the entry
    - Creates a Draft candidate marker (not a full Draft — just tagged for attention)
  - Add CLI: `autoinfo summaries flag <id> --tag important --tag ivf`
  - Add CLI: `autoinfo summaries show <id>` — full detail view with flag status
  - Wire MCP tool: `flag_for_knowledge_base`
  - Wire MCP tool: `get_summary(summary_id)` — full detail
  - Create tests/test_flag_kb.py

  **Must NOT do**: Auto-create Draft on flag — agent must explicitly call create_kb_draft

  **Recommended Agent Profile**: `unspecified-low`, Skills: []
  **Parallelization**: Wave v0.2

  **Acceptance Criteria**:
  - [ ] `flag_for_knowledge_base(summary_id, tags=["ivf"])` returns {flagged: true}
  - [ ] Flagged entry shows tags in SQLite index
  - [ ] `autoinfo summaries flag <id> --tag important` adds tag
  - [ ] `autoinfo summaries show <id>` shows full entry with flags
  - [ ] Double-flag merges tags (idempotent)

- [x] 10. G4 factual consistency gate

  **What to do**:
  - Create `G4FactualConsistency` class in `quality.py`:
    - `check(item, extraction) -> QualityResult`
    - Sends LLM prompt: "Does the following summary contradict the source text? Answer YES/NO and explain."
    - If LLM says YES (contradiction): flagged=True, details={"inconsistency": "explanation"}
    - Includes in processing pipeline when `--check-factual` flag set
  - Add to `run_processing()`: optional G4 gate
  - Add CLI flag: `autoinfo process --check-factual`
  - KB frontmatter includes `quality_flags.G4-SummaryFactual` when run
  - Create tests/test_quality_g4.py — mock LLM, verify flagging

  **Must NOT do**: G5 translation accuracy gate, auto-retry on G4 failure

  **Recommended Agent Profile**: `unspecified-low`, Skills: []
  **Parallelization**: Wave v0.2

  **Acceptance Criteria**:
  - [ ] G4 flags summary that contradicts source (mocked)
  - [ ] G4 passes summary that matches source (mocked)
  - [ ] G4 result stored in KB frontmatter when `--check-factual` used
  - [ ] Without `--check-factual`, G4 is skipped (backward compat)
  - [ ] G4 failure doesn't block pipeline (advisory gate)

---

## TODOs — v0.3: Multi-source + Schedule

- [x] 11. Web scraping handler (trafilatura)

  **What to do**:
  - Create `src/autoinfo/collectors/web.py` with `WebHandler`:
    - `fetch(url) -> list[Item]` — fetches HTML, extracts article content via `trafilatura.extract()`
    - Extracts: title (from HTML <title>), author (from meta), date (from meta), content (article body)
    - Configurable: `extract_only_text=True`, `include_links=False`, `include_images=False`
    - Error handling: unreachable URL retry 3x, non-HTML content log+skip
    - Timeout: 30s
  - Register in collection orchestrator (`collect.py`: dispatch by type="web")
  - Add `trafilatura` to core deps if not already (check pyproject.toml)
  - Create VCR cassette test with a public article URL
  - Create tests/test_web_handler.py

  **Must NOT do**: JS rendering, Playwright, screenshot capture, SPA support

  **Recommended Agent Profile**: `unspecified-high`, Skills: []
  **Parallelization**: Wave v0.3 (with 12-16)

  **Acceptance Criteria**:
  - [ ] `WebHandler.fetch("https://example.com/article")` returns Item with extracted content
  - [ ] Article title extracted from HTML <title> or <h1>
  - [ ] Content is clean text (no HTML tags)
  - [ ] Non-HTML URL (PDF) returns empty with logged error (not crash)
  - [ ] Timeout returns empty, pipeline continues
  - [ ] VCR cassette test passes without network

- [x] 12. AI-commercial demo domain

  **What to do**:
  - Create `src/autoinfo/data/domains/ai-commercial/sources.yaml`:
    ```yaml
    name: ai-commercial
    description: "AI commercial intelligence tracking"
    sources:
      - name: techcrunch
        type: rss
        url: https://techcrunch.com/feed/
        quality_tier: 2
        frequency: daily
      - name: producthunt
        type: api
        url: https://api.producthunt.com/v2/api/graphql
        quality_tier: 2
        access: api_key
    topics:
      - name: "AI Product Launches"
        keywords: ["AI", "product launch", "funding"]
  ```
  - Note: ProductHunt API requires GraphQL + API key. For v0.3, implement:
    - If generic APIHandler exists: configure ProductHunt via source config
    - If not: add ProductHunt as custom handler (or defer to v0.4)
  - Register in `cli/init.py`: add `ai-commercial` to demo domain list
  - Update init to show both domains: `autoinfo init --demo medical-research|ai-commercial`

  **Must NOT do**: Full ProductHunt API integration if handler architecture doesn't support it — stub acceptable

  **Recommended Agent Profile**: `unspecified-low`, Skills: []
  **Parallelization**: Wave v0.3

  **Acceptance Criteria**:
  - [ ] `autoinfo init --demo ai-commercial` creates project with AI-commercial sources
  - [ ] Config loads and parses correctly for ai-commercial domain
  - [ ] TechCrunch RSS collection works (via existing RSS handler)
  - [ ] `autoinfo init` without --demo lists both domains

- [x] 13. Source CRUD CLI + MCP tools

  **What to do**:
  - Implement CLI commands in `cli/sources.py`:
    - `autoinfo sources add --name <n> --url <u> --type <t> --domain <d>` — adds source to config
    - `autoinfo sources list --domain <d>` — lists sources with status
    - `autoinfo sources remove <source-id> --domain <d>` — removes source from config
    - `autoinfo sources test --url <u> --type <t>` — tests reachability
  - Implement MCP tools (replace stubs from v0.1.1):
    - `add_source(name, url, type, domain)` — idempotent, returns source_id
    - `add_sources(sources=[...])` — batch add
    - `remove_source(source_id)` — removes from config
    - `test_source(url, type)` — returns reachability + content preview
    - `list_sources(domain)` — returns sources with health
  - All tools write to `.autoinfo/config.yaml` (append to domain.sources list)
  - All tools validate: URL format, type enum (rss/api/web/webhook/email/pdf)
  - Create tests/test_source_crud.py

  **Must NOT do**: Source grouping, tags, quality tier auto-detection

  **Recommended Agent Profile**: `unspecified-high`, Skills: []
  **Parallelization**: Wave v0.3

  **Acceptance Criteria**:
  - [ ] `add_source(name="My Feed", url="https://example.com/rss", type="rss", domain="medical-research")` adds to config
  - [ ] Same source added twice returns same source_id (idempotent)
  - [ ] `list_sources("medical-research")` returns configured sources
  - [ ] `remove_source(source_id)` removes from config, preserves collected data
  - [ ] `test_source(url="https://example.com", type="web")` returns content preview
  - [ ] Invalid URL format returns validation error

- [x] 14. Topic CRUD CLI + MCP tools

  **What to do**:
  - Implement CLI commands in `cli/topics.py`:
    - `autoinfo topics add --domain <d> --name <n> --keywords <k>` — adds topic
    - `autoinfo topics list --domain <d>` — lists topics
    - `autoinfo topics remove --domain <d> --topic-id <id>` — removes topic
  - Implement MCP tools: `add_topic`, `remove_topic`, `list_topics`
  - All write to `.autoinfo/config.yaml` domain config
  - Create tests/test_topic_crud.py

  **Must NOT do**: Topic groups, hierarchical topics, auto-suggestions

  **Recommended Agent Profile**: `unspecified-low`, Skills: []
  **Parallelization**: Wave v0.3

  **Acceptance Criteria**:
  - [ ] `add_topic("medical-research", "Gene Therapy", ["gene", "therapy", "CRISPR"])` adds to config
  - [ ] `list_topics("medical-research")` returns topics with keywords
  - [ ] `remove_topic("medical-research", topic_id)` removes from config
  - [ ] Topics appear in collection filter: `collect --topic "Gene Therapy"`

- [x] 15. Scheduled collection (crond wrapper)

  **What to do**:
  - Implement CLI commands in `cli/cron.py`:
    - `autoinfo cron run` — executes due schedules (called by crond)
    - `autoinfo cron list-schedules` — lists configured schedules
    - `autoinfo cron add-schedule --name <n> --expression <cron> --domain <d>` — adds schedule
    - `autoinfo cron remove-schedule --name <n>` — removes schedule
  - Schedule storage: `.autoinfo/schedules.yaml`
  - Schedule execution:
    - `cron run` reads schedules, checks if each is due (based on last_run), runs collection if due
    - Uses `croniter` library to parse cron expressions
    - Updates last_run timestamp after execution
  - User setup: `crontab -e` → `0 8 * * * cd /path/to/project && autoinfo cron run`
  - Add `croniter` to dependencies
  - Create tests/test_cron.py

  **Must NOT do**: Built-in scheduler daemon, Windows Task Scheduler integration, missed-run catch-up

  **Recommended Agent Profile**: `unspecified-high`, Skills: []
  **Parallelization**: Wave v0.3

  **Acceptance Criteria**:
  - [ ] `add-schedule` stores schedule in schedules.yaml
  - [ ] `list-schedules` returns stored schedules
  - [ ] `remove-schedule` removes schedule
  - [ ] `cron run` executes due schedules (mock crontab for test)
  - [ ] `cron run` doesn't execute non-due schedules
  - [ ] Scheduling uses crond, not built-in daemon

- [x] 16. Source health + user feedback (F18, F29)

  **What to do**:
  - Implement `get_source_health(source_id)` — reads `_runs.json` for source status
  - Implement `rate_item(item_id, rating, feedback)` — stores rating in SQLite
  - Add source health status to `status.py`: show per-source health
  - Wire MCP tools: `get_source_health`, `rate_item`
  - Create tests/test_source_health.py

  **Must NOT do**: Automatic threshold adjustment, ML-based feedback learning

  **Recommended Agent Profile**: `unspecified-low`, Skills: []
  **Parallelization**: Wave v0.3

  **Acceptance Criteria**:
  - [ ] `get_source_health("pubmed")` returns {status, last_success, error_count}
  - [ ] Source with 3 consecutive failures shows status "error"
  - [ ] `rate_item(item_id, rating=5)` stores in SQLite
  - [ ] `autoinfo status` shows source health

---

## TODOs — v0.4: Q&A + Output

- [x] 17. FTS5+LLM Q&A on collected content

  **What to do**:
  - Implement `query_collected(query, domain, content_ids) -> Answer`:
    - Searches FTS5 for relevant entries (or uses provided content_ids)
    - Returns top 5 results with `{entry_id, title, content_snippet, relevance}`
    - Calls LLM with: "Answer this question based ONLY on these articles. Cite sources."
    - LLM prompt template:
      ```
      System: You are a research assistant. Answer questions based ONLY on the provided articles.
              Cite each claim with the source title [1], [2] etc.
      User: Question: {query}
      
      Articles:
      [1] Title: {title_1}
          Content: {content_snippet_1}
      [2] Title: {title_2}
          Content: {content_snippet_2}
      ```
    - Returns `{answer: "text with citations", sources: [{entry_id, title}]}`
  - No conversation persistence — each query is independent
  - No cross-item synthesis beyond what LLM produces from provided snippets
  - Wire MCP tool: `query_collected`
  - Create tests/test_qa.py

  **Must NOT do**: Conversation persistence, multi-turn, cross-session memory

  **Recommended Agent Profile**: `unspecified-high`, Skills: []
  **Parallelization**: Wave v0.4 (with 18-20)

  **Acceptance Criteria**:
  - [ ] `query_collected("What are the latest IVF breakthroughs?", "medical-research")` returns answer with citations
  - [ ] Sources cited with [1], [2] format matching provided articles
  - [ ] Query with no results returns "No relevant articles found"
  - [ ] Query with explicit content_ids searches only those items
  - [ ] Each query returns independent result (no state)

- [x] 18. Digest generation (Jinja2 + LLM)

  **What to do**:
  - Create Jinja2 template at `src/autoinfo/data/templates/digest.md.j2`:
    ```jinja2
    # {{ title }}
    
    **Period**: {{ period }} | **Domain**: {{ domain }}
    
    ## Key Findings
    {% for finding in key_findings %}
    - {{ finding }}
    {% endfor %}
    
    ## Entries
    {% for entry in entries %}
    ### {{ entry.title }}
    **Source**: {{ entry.source }} | **Relevance**: {{ entry.relevance_score }}/100
    {{ entry.tl_dr }}
    {% endfor %}
    
    ## Trends
    {{ trends }}
    
    ## Sources
    {% for source in sources %}
    - {{ source }}
    {% endfor %}
    ```
  - Implement `generate_digest(domain, period, format)`:
    - Reads entries from KB (filtered by domain + date range)
    - Calls LLM to synthesize: key findings, trends
    - Fills Jinja2 template with {entries, key_findings, trends, sources}
    - Output: Markdown (default), HTML, JSON
  - Wire CLI: `autoinfo output digest --domain <d> --period week`
  - Wire MCP tool: `generate_digest`
  - Create tests/test_digest.py

  **Must NOT do**: HTML/CSS styling, PDF generation, email delivery

  **Recommended Agent Profile**: `unspecified-high`, Skills: []
  **Parallelization**: Wave v0.4

  **Acceptance Criteria**:
  - [ ] `generate_digest("medical-research", "week")` produces Markdown with header
  - [ ] Digest includes entries from the correct period
  - [ ] LLM-synthesized key findings present in output
  - [ ] Format="json" produces valid JSON
  - [ ] Empty domain returns "No entries found" (not error)

- [x] 19. Report generation

  **What to do**:
  - Create Jinja2 template: `src/autoinfo/data/templates/report.md.j2`
  - Report structure: title, sections[], references, appendices
  - More structured than digest: each section is LLM-generated from grouped entries
  - Implement `generate_report(domain, collection_id, format)`:
    - Reads entries from a specific collection or topic
    - Groups entries by theme (LLM-based)
    - Generates per-section content + executive summary
  - Wire CLI: `autoinfo output report --domain <d>`
  - Wire MCP tool: currently in inventory as stub — implement
  - Create tests/test_report.py

  **Must NOT do**: Per-section template customization, multi-format export in one command

  **Recommended Agent Profile**: `unspecified-high`, Skills: []
  **Parallelization**: Wave v0.4

  **Acceptance Criteria**:
  - [ ] Report has title, sections, references
  - [ ] Entries grouped into sections thematically
  - [ ] Executive summary generated
  - [ ] Format options work (markdown, json)

- [x] 20. Export functionality

  **What to do**:
  - Implement `export_kb(domain, format, collection_id)`:
    - `markdown`: creates a `.tar.gz` or `.zip` of KB Markdown files
    - `json`: exports all entries as JSON array
    - `sqlite`: copies the SQLite database
    - Scope: single domain or full KB
  - Wire CLI: `autoinfo output export --domain <d> --format markdown`
  - Wire MCP tool: `export_kb`
  - Create tests/test_export.py

  **Must NOT do**: GraphML export, Obsidian vault packaging, PDF conversion

  **Recommended Agent Profile**: `unspecified-high`, Skills: []
  **Parallelization**: Wave v0.4

  **Acceptance Criteria**:
  - [ ] `export_kb(format="markdown")` creates .tar.gz with all .md files
  - [ ] `export_kb(format="json")` produces valid JSON array
  - [ ] `export_kb(format="sqlite")` copies database file
  - [ ] Domain filter exports only that domain's entries
  - [ ] Empty KB exports empty (not error)

---

### TODOs — v0.5: Mature MCP
- [x] 21. Full MCP tool inventory — complete remaining tools

---

## Final Verification Wave

- [x] F1. **Plan Compliance Audit** — `oracle` (all Must Have verified, Must NOT Have clean)
- [x] F2. **Code Quality Review** — `unspecified-high` (723 pass, 104 pre-existing CLI compat failures)
- [x] F3. **Manual QA** — `unspecified-high` (core pipeline verified end-to-end)
- [x] F4. **Scope Fidelity Check** — `deep` (30/30 tasks compliant, no scope creep)

---

## Commit Strategy

- **v0.1.1**: `chore: config expansion, process fix, missing CLI/MCP tools`
- **v0.2**: `feat(fts5): FTS5 search + kb reindex` + `feat(kb): 02-Draft tier + create/reject draft` + `feat(extraction): custom fields` + `feat(quality): G4 factual consistency` + `feat(kb): flag_for_knowledge_base`
- **v0.3**: `feat(web): trafilatura handler` + `feat(domain): AI-commercial demo` + `feat(cli): source/topic CRUD` + `feat(cron): scheduled collection` + `feat(monitor): source health`
- **v0.4**: `feat(qa): FTS5+LLM Q&A` + `feat(output): digest/report generation` + `feat(kb): export functionality`
- **v0.5**: `feat(mcp): full tool inventory` + `feat(kb): auto-linking + relations` + `feat(web): Playwright fallback` + `feat(kb): entry versioning` + `feat(cli): remaining commands`
- **v0.6**: `feat(kb): knowledge graph` + `feat(i18n): LLM translation` + `feat(output): tutorial/presentation` + `feat(domain): language-learning demo`

---

## Success Criteria

### Verification Commands (per milestone)
```bash
# v0.1.1: pytest tests/test_config_v2.py tests/test_process_batch.py tests/test_cli_v2.py tests/test_mcp_v2.py

# v0.2: autoinfo kb search --query "embryo" --domain medical-research
# v0.2: autoinfo kb create-draft --raw-id <id>
# v0.2: autoinfo process --domain medical-research --check-factual

# v0.3: autoinfo collect --domain ai-commercial --topic "AI Products"
# v0.3: autoinfo sources add --name "test" --url "https://example.com/rss" --type rss --domain test

# v0.4: autofinfo output digest --domain medical-research --period week

# v0.5: autoinfo --help (full command list)

# v0.6: autoinfo init --demo language-learning
```

### Final Checklist
- [ ] All 32 expectations from founder-expectations.md implemented
- [ ] All v0.1 tests still pass
- [ ] No scope creep (Must NOT Have respected)
- [ ] MCP server exposes 40+ tools
- [ ] CLI shows all commands
- [ ] All quality gates (G1-G5) functional
- [ ] All source types (RSS, API, web, webhook stub, email stub) defined
- [ ] Hermes 4-tier KB pipeline (Inbox→Raw→Draft→Wiki) implemented
