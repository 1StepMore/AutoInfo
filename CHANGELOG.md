# Changelog

All notable changes to the AutoInfo project will be documented in this file.

## [0.1.0-dev] — 2026-07-20

### Added

#### Foundation
- Project skeleton with Python packaging (`pyproject.toml`, `Makefile`, `.gitignore`)
- Agent-facing infrastructure: `AGENTS.md`, `.opencode/skills/autoinfo-SKILL.md`
- `docs/dev/founder-expectations.md` — full specification (32 expectations, 13 technical decisions)
- Hermes 4-level KB pipeline model documented

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
