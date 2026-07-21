# Changelog

All notable changes to the AutoInfo project will be documented in this file.

## v1.1 (2026-07-21)

### Added
- G5 translation accuracy quality gate (advisory, optional)
- KBStore.promote_kb_draft() method + `autoinfo kb promote` CLI
- 03-Wiki append-only guards (agent writes blocked)
- Init directory structure: 00-Inbox, 02-Draft, 03-Wiki
- Interactive init wizard (domain selection, LLM config)
- KB frontmatter: author, source_ids, status, related_concepts, linked_entries
- Language auto-detection (langdetect) for Item.language
- 6 new MCP tool areas: collection progress/status, domain lifecycle, list_keywords, tutorial/presentation
- `autoinfo collect --all` flag for multi-domain collection
- test_source extract_fields suggestions + quality tier warnings
- 7 curated demo sources (arXiv, CrossRef, Unpaywall, Crunchbase, LMSYS, news-in-levels, commonlit)
- Webhook source handler (HMAC, rate limiting)
- Email (IMAP) source handler (stdlib imaplib)
- PDF source handler (PyMuPDF, chunking)
- Knowledge graph export CLI (JSON/GraphML/CSV)

### Changed
- SourceConfig supports `settings` dict for extra config fields
- G3RelevanceScoring supports multi-language keywords and per-topic threshold
- Topic dataclass: group, relevance_threshold fields
- Updated README with Known Limitations section + v1.1 final status
- Updated founder-expectations.md: Sections 5, 9, 10, 11, 12.10, 13 updated to v1.1 reality
- Added Section 14 to founder-expectations.md: remaining gaps catalog
- MCP tool inventory expanded from 35 to 56+ tool areas

### Fixed
- Dead code removal (unused imports, orphaned test assertions)
- Test mock updates for KG test (process_calls_store_entities)
- install pytest-mock for KG test fixtures
- CI: F1-F4 final verification wave — all 4 pass (Oracle, code quality, manual QA, scope fidelity)

### Infrastructure
- `.omo/evidence/final-qa/`: 11 QA scenario evidence files (S1-S11)
- `.omo/plans/autoinfo-v1.1.md`: Full execution plan
- `.omo/notepads/autoinfo-v1.1/learnings.md`: Implementation learnings

## [1.0.0-dev] — 2026-07-20

### Added

#### v0.1.1: Config Expansion & Infrastructure
- LLM task config: per-task model selection (`llm.tasks.extraction`, `llm.tasks.summarization`)
- LLM fallback chains (`llm.fallback: [{provider, model}]`)
- `get_effective_llm_config(task)` — resolved model config
- Domain config extensions: `extract_fields[]`, `search_mode`
- Batch processing: `process_collection(domain, batch_size=N)` + `get_processing_progress`
- CLI modules: sources, topics, kb, output, cron (with stubs)
- MCP tools: list_domains, get_domain_schema, list_available_models, get_effective_llm_config,
  add_source, add_sources, remove_source, test_source, list_sources,
  add_topic, remove_topic, search_knowledge_base, flag_for_knowledge_base, list_output_templates
- config.save_config() + config_to_dict() public API

#### v0.2: KB & Search
- FTS5 full-text search across all KB tiers (Raw + Draft + Wiki)
- CJK tokenizer support (unicode61)
- `autoinfo kb search` CLI command + MCP tool
- `autoinfo kb reindex` command for FTS5 population
- 02-Draft tier: agent creates Draft from Raw entries
- `create_kb_draft(raw_ids, title, summary, tags)` with Raw validation
- `reject_kb_draft(draft_id, reason, action)` — moves back to Raw
- `list_kb_tier(domain, tier)` — filter by pipeline stage
- Custom extraction fields per domain (`extract_fields: [methodology, sample_size]`)
- Dynamic LLM prompt construction from field schema
- On-demand re-extraction via `extract_fields` MCP tool
- `flag_for_knowledge_base(summary_id, tags, importance)` — tag entries for KB
- `autoinfo summaries flag` and `autoinfo summaries show` CLI commands
- G4 factual consistency gate: LLM checks summary vs source
- `autoinfo process --check-factual` flag

#### v0.3: Multi-source & Schedule
- Web scraping handler via trafilatura (compose/compat)
- AI-commercial demo domain (TechCrunch RSS, ProductHunt API)
- Source CRUD: add, list, remove, test (idempotent, writes to config)
- Topic CRUD: add, list, remove
- Scheduled collection via crond wrapper
- `autoinfo cron run`, `add-schedule`, `list-schedules`, `remove-schedule`
- croniter dependency for cron expression parsing
- Source health monitoring: healthy/degraded/error/paused states
- `rate_item(item_id, rating, feedback)` — user feedback in SQLite

#### v0.4: Q&A & Output
- FTS5+LLM Q&A: `query_collected()` with FTS5 search + LLM synthesis
- Answer with source citations [1], [2] format
- Digest generation via Jinja2 + LLM: `generate_digest(domain, period, format)`
- Report generation: thematic grouping, executive summary, sections
- Export functionality: Markdown (tar.gz), JSON array, SQLite copy
- Jinja2 templates: digest.md.j2, report.md.j2

#### v0.5: Mature MCP
- 50 MCP tools across 12 categories
- Auto-linking: keyword-overlap creates "related" relations during collection
- `link_items(item_a_id, item_b_id, relation)` + `get_item_relations(item_id)`
- Playwright web handler fallback for JS-heavy pages
- Entry versioning: .bak copies, max 5 versions, get_entry_history, restore_entry_version
- `get_collection_stats(period)` — aggregate across domains
- `get_collection_diff(since_id)` — delta query
- Config override system (`~/.autoinfo/overrides/`)
- Complete CLI coverage: sources health, kb list-tiers, output list-templates
- MCP tools: list_projects, get_project_assets, archive_project, batch_run, list_active_collections, get_config

#### v0.6: Graph & Translation
- Knowledge graph: entity extraction (6 types) + relation discovery
- `query_knowledge_graph(entity, relation)` MCP tool
- LLM-based translation: `localize_content(content_id, target_lang)`
- Tutorial generation with audience adaptation (researcher/clinician/executive/student)
- Presentation generation with speaker notes
- Jinja2 templates: tutorial.md.j2, presentation.md.j2
- Language-learning demo domain (Project Gutenberg, BBC Learning English RSS)
- All 3 demo domains: medical-research, ai-commercial, language-learning

### Infrastructure
- `docs/autoinfo-validation-master-plan.md` — comprehensive validation plan (19 questions, 7 parts)
- All docs updated to reflect v1.0 status

#### Config System
- `src/autoinfo/config.py` — YAML-based configuration with env var resolution
- Config validation: required fields, domain+source structure checks
- Demo domain template at `src/autoinfo/data/domains/medical-research/sources.yaml`

#### CLI Commands
- `autoinfo init --demo medical-research` — project skeleton generator with idempotent behavior
- `autoinfo doctor` — system health check (Python version, config, LLM key, source reachability)
- `autoinfo collect` — multi-source collection with `--domain`, `--topic`, `--limit`, `--dry-run`
- `autoinfo process` — LLM extraction + quality gates + KB storage pipeline
- `autoinfo collect --auto-process` — combined collect + process in one command
- `autoinfo status` — collection statistics and source health overview
- `autoinfo summaries list` — browse extracted summaries with pagination
- `--json` global flag on all commands for machine-readable output

#### Collection Pipeline
- PubMed API handler (E-utilities esearch + efetch) with rate limiting (3/10 req/sec) and retry
- Generic RSS/Atom handler via feedparser
- Collection orchestrator with source dispatch, progress tracking, and JSON caching
- Dedup system (G2): URL exact match + PMID/DOI cascade matching

#### LLM Extraction
- `LLMExtractor` class using LiteLLM (multi-provider via config)
- Default extraction: TL;DR, 3-5 key points, entity extraction, relevance score (0-100)
- Dry-run mode to preview prompts without API calls
- Retry logic with configurable max retries
- Snapshot regression tests (no real LLM calls in CI)

#### Quality Gates
- G1 (Source authority): advisory tier check, flags Tier 3+ sources
- G2 (Dedup): URL/PMID/DOI matching against existing entries
- G3 (Relevance scoring): keyword overlap scoring, items below 30 threshold hidden by default
- All gates advisory — never block or discard content

#### Knowledge Base Storage
- `KBStore`: Markdown files at `knowledge/<domain>/01-Raw/<topic>/<YYYY-MM-DD>-<slug>.md`
- YAML frontmatter with 14 required fields (title, source_url, source_type, source_platform, collected_at, etc.)
- `SQLiteIndex`: lightweight metadata index for fast listing (100+ entries in <100ms)
- `list_entries()` with pagination (`limit`, `offset`, date filtering)
- `get_entry()` reads full content from Markdown files

#### MCP Server
- 6 tools over stdio transport via MCP Python SDK
- `health_check()`, `diagnose_system()`, `collect_sources()`, `process_collection()`, `list_summaries()`, `get_kb_entry()`
- Structured error responses with `error_code`/`message`/`actionable` fields
- Server entry point: `python -m autoinfo.mcp.server`

#### Testing
- 220 tests across 11 test files
- Test infrastructure: pytest, CliRunner, VCR cassettes, synthetic fixture data
- Integration tests: T1-T5 True Test (init → collect → process → summaries)
- LLM extraction snapshot regression tests (mocked LiteLLM)
- Coverage: config, CLI, PubMed handler, RSS handler, collection, quality gates, LLM, KB, MCP

### Agent-Orientation Enhancements
- `diagnose_system()` MCP tool — comprehensive health diagnostic (LLM, sources, disk, DB)
- `add_source()` idempotent — safe for agent retry
- `add_sources()` batch variant — multi-source in one call
- `get_domain_schema(domain)` — discover available extraction fields
- `list_available_models()` — discover configured LLM models
- `list_output_templates(domain)` — discover available output types
- `collect_sources(..., dry_run=true)` — preview collection before committing
- `get_collection_diff(domain, since_collection_id)` — delta queries
- `get_kb_entry(entry_id)` — read full entry content (not just search summary)
- `list_keywords(domain, status)` — query keyword taxonomy
- `get_effective_llm_config(task)` — resolved model config without YAML parsing
- `reject_kb_draft(draft_id, reason, action)` — agent-handled Draft rejection
- Source tier warnings on `add_source()`
- `estimated_duration_s` on collection start for optimal poll intervals
- Pagination (`limit`/`offset`/`total_count`) on all list/search tools
- Wiki entries explicitly append-only; agent cannot demote

### Infrastructure
- `AGENTS.md` — comprehensive agent onboarding guide
- `README.md` — project overview and quick start
- `.gitignore` — Python project hygiene
- `.opencode/skills/autoinfo-SKILL.md` — OpenCode skill definition
- `Makefile` — `install`, `test`, `lint`, `clean` targets
