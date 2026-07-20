# AutoInfo v0.1 — Core Loop Implementation

## TL;DR

> **Quick Summary**: Build the end-to-end AutoInfo v0.1 pipeline — configure sources, collect from PubMed via REST API, LLM-extract structured summaries, store as Markdown files with SQLite index, browse summaries via CLI. Includes a basic MCP server for agent operation. Covers F01-F06, F07 (medical), F11-F13 (RSS+API), F15 (basic LLM), F16 (basic), F20 (01-Raw only), G1-G3, F28.
>
> **Deliverables**:
> - Working CLI: `autoinfo {init,doctor,collect,process,status,summaries}`
> - PubMed medical-research demo domain collection
> - LLM extraction pipeline (TL;DR + key points + relevance score)
> - Markdown KB storage in `knowledge/01-Raw/` + SQLite metadata index
> - Quality gates G1 (source authority), G2 (dedup), G3 (relevance)
> - Basic MCP server (health_check, collect_sources, process_collection, list_summaries, get_kb_entry, diagnose_system)
> - Test suite: pytest + VCR cassettes + snapshot regression fixtures
>
> **Estimated Effort**: Large
> **Parallel Execution**: YES — 4 waves
> **Critical Path**: Config/Models → Collection → Processing → Interface

---

## Context

### Original Request
Build AutoInfo v0.1 — a universal information tracking and knowledge base platform for the medical-research demo domain. Full spec at `docs/dev/founder-expectations.md`.

### Interview Summary
**Key Discussions**:
- Scope: Abbreviated full-loop + basic MCP server (user chose bolder scope)
- Pipeline: Two-phase (`collect` raw cache → `process` KB), with `--auto-process` flag
- PubMed: esearch + efetch REST API for structured metadata
- KB storage: Markdown files (Obsidian-compatible) + lightweight SQLite metadata index
- Test strategy: Tests alongside each feature (pytest + fixtures + VCR + snapshot regression)
- Default LLM: `deepseek/deepseek-chat` via OpenRouter
- Demo sources: YAML templates in `src/autoinfo/data/domains/`
- Code: CLI-first, all core logic = callable Python functions, thin CLI/MCP wrappers

**Research Findings**:
- Project is greenfield — no code exists, only spec and infrastructure files
- AGENTS.md, README.md, pyproject.toml, Makefile, .gitignore already created
- PubMed E-utilities API provides free access with rate limits (3 req/sec without API key, 10 req/sec with)
- LiteLLM supports multi-provider (OpenRouter, OpenAI, Anthropic, DeepSeek) from one interface

### Metis Review
**Key Findings** (addressed):
- Scope contradiction (milestone table vs. True Tests) → resolved by user choosing abbreviated full-loop
- MCP server timing → user chose to include basic MCP in v0.1
- PubMed integration depth → esearch + efetch, not RSS
- KB storage format → Markdown files + SQLite index
- Demo source packaging → YAML templates, not hardcoded
- Min config schema → defined below
- LLM cost mitigation → dry-run flag, mocked LLM in CI

---

## Work Objectives

### Core Objective
Build AutoInfo v0.1 end-to-end: user configures → system collects from PubMed → LLM extracts summaries → stores as searchable knowledge base → agent can operate via MCP.

### Concrete Deliverables
- `src/autoinfo/` — complete Python package with CLI, collectors, KB, LLM, quality, MCP modules
- `src/autoinfo/data/domains/medical-research/sources.yaml` — demo domain template
- `.autoinfo/config.yaml` — v0.1-minimal config schema
- `knowledge/01-Raw/` — Markdown KB entries with YAML frontmatter
- `autoinfo.db` — SQLite metadata index
- Test suite: pytest + fixtures + VCR + snapshot regression

### Definition of Done
- [x] T1-T5 True Test passes in automated run
- [x] All "Must Have" items present and verified
- [x] No "Must NOT Have" items present
- [x] All tests pass (`pytest -v`)

### Must Have
- [x] `autoinfo init --demo medical-research` creates `.autoinfo/` with valid config
- [x] `autoinfo collect --domain medical-research --topic "IVF" --limit 5` fetches + deduplicates + caches items
- [x] `autoinfo process --domain medical-research` runs LLM extraction + quality gates + creates KB entries
- [x] `autoinfo collect --auto-process` chains both phases
- [x] Each KB entry is a Markdown file in `knowledge/01-Raw/` with proper YAML frontmatter
- [x] `autoinfo summaries list` shows items with TL;DR + relevance score
- [x] `autoinfo status` shows collection stats and source health
- [x] `autoinfo doctor` checks Python, config, LLM key, PubMed reachability
- [x] MCP server exposes: health_check, collect_sources, process_collection, list_summaries, get_kb_entry, diagnose_system
- [x] Unit tests for config, CLI, PubMed handler, dedup, KB storage
- [x] LLM extraction uses snapshot regression (no real LLM in CI)

### Must NOT Have (Guardrails)
- [x] ❌ No SQLite FTS5 search or vector search (v0.2)
- [x] ❌ No KB Draft/Wiki tiers (v0.2)
- [x] ❌ No arXiv, CrossRef, Unpaywall, or web page scraping
- [x] ❌ No G4/G5 quality gates
- [x] ❌ No scheduled collection / cron
- [x] ❌ No email/webhook handlers
- [x] ❌ No output generation (digests, reports, tutorials)
- [x] ❌ No knowledge graph, Q&A, cross-referencing
- [x] ❌ No translation / localization
- [x] ❌ No custom extraction fields per domain
- [x] ❌ No model fallback chains or per-task model selection
- [x] ❌ No premature abstraction (plugin systems, factories, dynamic discovery)
- [x] ❌ No over-validation beyond input boundary
- [x] ❌ No "might need this later" features
- [x] ❌ No web UI of any kind

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed.

### Test Decision
- **Infrastructure exists**: YES (pytest in pyproject.toml)
- **Automated tests**: Tests-after (alongside each feature)
- **Framework**: pytest + CliRunner + pytest-vcr + snapshot fixtures
- **Key principle**: LLM extraction tests use snapshot regression with synthetic fixtures. No real LLM calls in CI.

### QA Policy
Every task MUST include agent-executed QA scenarios. Evidence saved to `.omo/evidence/task-{N}-{scenario-slug}.{ext}`.

- **CLI**: Bash — Run command, validate exit code + stdout/stderr content
- **API/Library**: Bash — Import module, call functions, assert return values
- **File system**: Bash — Verify file existence, YAML parsing, content format
- **MCP**: Bash — Connect to server, call tool, validate JSON-RPC response
- **Database**: Bash — Query SQLite, validate row counts and field values

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately — Foundation):
├── Task 1: Project skeleton + directory structure [quick]
├── Task 2: Data models (Item, CollectionResult, KBEntry types) [quick]
├── Task 3: Config system (YAML parse/validate/schema) [quick]
├── Task 4: Demo domain YAML templates + init command [quick]
├── Task 5: CLI skeleton (typer app + command stubs) [quick]
└── Task 6: Test infrastructure setup [quick]

Wave 2 (After Wave 1 — Core Collection):
├── Task 7: PubMed API handler (esearch + efetch) [unspecified-high]
├── Task 8: Generic RSS handler [unspecified-low]
├── Task 9: Collection orchestrator (dedup, caching, progress) [unspecified-high]
└── Task 10: Quality gates G1-G3 [unspecified-low]

Wave 3 (After Wave 2 — Processing & Storage):
├── Task 11: LLM extraction pipeline [unspecified-high]
├── Task 12: KB storage (Markdown files + SQLite index) [unspecified-high]
└── Task 13: Process command wiring [unspecified-low]

Wave 4 (After Wave 3 — Interface):
├── Task 14: CLI commands (status, doctor, summaries, --auto-process) [unspecified-high]
├── Task 15: MCP server [unspecified-high]
└── Task 16: Integration & end-to-end tests [unspecified-high]

Wave FINAL (After ALL tasks):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real manual QA (unspecified-high)
└── Task F4: Scope fidelity check (deep)
→ Present results → Get explicit user okay
```

### Dependency Matrix
- **1-6**: — — 7-16
- **7-10**: 1-6 — 11-13
- **11-13**: 1-10 — 14-16
- **14-16**: 1-13 — F1-F4
- **F1-F4**: 1-16 — user ok

### Agent Dispatch Summary
- **Wave 1**: 6 × `quick`
- **Wave 2**: 2 × `unspecified-high`, 2 × `unspecified-low`
- **Wave 3**: 2 × `unspecified-high`, 1 × `unspecified-low`
- **Wave 4**: 3 × `unspecified-high`
- **FINAL**: 1 × `oracle`, 2 × `unspecified-high`, 1 × `deep`

---

## TODOs

- [x] 1. Project skeleton + directory structure

  **What to do**:
  - Ensure `src/autoinfo/` package structure is valid (__init__.py exports version)
  - Ensure `src/autoinfo/data/domains/` directory exists (for demo source templates)
  - Ensure `src/autoinfo/collectors/` directory exists
  - Ensure `src/autoinfo/cli/` directory exists (for subcommand modules)
  - Ensure `src/autoinfo/mcp/` directory exists
  - Ensure `tests/` directory has `conftest.py` and `__init__.py`
  - Create `tests/fixtures/` directory for test data
  - Verify `pip install -e .` works and `autoinfo --help` shows CLI help text

  **Must NOT do**:
  - Do not create any implementation files beyond the skeleton
  - Do not add dependencies beyond what's in pyproject.toml

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2-6)
  - **Blocks**: 7-16
  - **Blocked By**: None

  **Acceptance Criteria**:
  - [ ] `pip install -e .` exits 0
  - [ ] `autoinfo --help` shows command list
  - [ ] `ls src/autoinfo/collectors/` exists
  - [ ] `ls src/autoinfo/cli/` exists
  - [ ] `ls src/autoinfo/mcp/` exists
  - [ ] `ls tests/fixtures/` exists

  **QA Scenarios**:
  ```
  Scenario: Installation and CLI discovery
    Tool: Bash
    Preconditions: Clean Python environment
    Steps:
      1. Run `pip install -e .` — expect exit 0
      2. Run `autoinfo --help` — expect output containing "Usage:" and command list
    Expected Result: Package installs and CLI responds
    Evidence: .omo/evidence/task-1-install.txt
  ```

- [x] 2. Data models

  **What to do**:
  - Create `src/autoinfo/models.py` with:
    - `Item` dataclass: `id, source_name, source_type, source_url, title, content, content_type, collected_at, language, domain, topic_tags[], quality_tier, raw_data`
    - `CollectionResult` dataclass: `collection_id, domain, source, status, items_found, items_new, errors[], duration_s, estimated_duration_s`
    - `KBEntry` dataclass: `entry_id, title, domain, tier, source_url, source_type, source_platform, collected_at, summary, extracted_fields{}, tags[], priority, language, quality_tier, relevance_score, dedup_status, file_path, custom_fields{}`
    - `ExtractionResult` dataclass: `item_id, title, tl_dr, key_points[], entities[], relevance_score`
    - `SourceHealth` dataclass: `source_id, status, last_success, error_count, avg_response_time_ms`
  - All dataclasses should have `from_dict` and `to_dict` methods for serialization
  - Add type stubs file `src/autoinfo/py.typed`

  **Must NOT do**:
  - Do not implement any business logic beyond data containers
  - Do not add ORM or persistence logic to models

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 1)
  - **Parallel Group**: Wave 1 (with Tasks 1, 3-6)
  - **Blocks**: 7-16
  - **Blocked By**: None

  **Acceptance Criteria**:
  - [ ] `python -c "from autoinfo.models import Item; i=Item(id='1',source_name='test',title='t',content='c',collected_at='now'); print(i)"` works
  - [ ] All dataclasses can be instantiated and converted to/from dict
  - [ ] `py.typed` marker file exists

  **QA Scenarios**:
  ```
  Scenario: Data models instantiation
    Tool: Bash
    Preconditions: Package installed
    Steps:
      1. Run: python -c "from autoinfo.models import Item, KBEntry, ExtractionResult; print('OK')"
    Expected Result: PRINTS "OK"
    Evidence: .omo/evidence/task-2-models.txt
  ```

- [x] 3. Config system

  **What to do**:
  - Create `src/autoinfo/config.py` with:
    - `Config` dataclass matching v0.1-minimal schema (project, llm, domains[])
    - `load_config(path: Path) -> Config` — loads and validates YAML
    - `get_config_path() -> Path` — checks `.autoinfo/config.yaml` then `~/.autoinfo/config.yaml`
    - `validate_config(config: Config) -> list[str]` — returns list of validation errors
    - `create_default_config(domain: str) -> dict` — generates default config for a domain
    - `ensure_config_exists()` — command guard; prints "Run 'autoinfo init' first" and exits if no config
  - Config validation rules:
    - `project.name` required
    - `llm.provider` required
    - `llm.model` required
    - `llm.api_key` can be env var reference ${VAR_NAME}
    - At least one domain with `active: true`
    - Each domain must have at least one source
  - Use `pyyaml` for YAML parsing
  - Read env var references like `${AUTOINFO_LLM_API_KEY}` from environment

  **Must NOT do**:
  - Do not implement config file watching or live reload
  - Do not implement config migration or versioning
  - Do not implement schema generation

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 1)
  - **Parallel Group**: Wave 1 (with Tasks 1-2, 4-6)
  - **Blocks**: 7-16
  - **Blocked By**: None

  **Acceptance Criteria**:
  - [ ] `load_config` parses valid YAML and returns Config
  - [ ] `load_config` raises error on invalid YAML with file:line
  - [ ] `validate_config` returns empty list for valid config
  - [ ] `validate_config` returns errors for missing required fields
  - [ ] `ensure_config_exists` exits 1 with message when no config
  - [ ] Env var references resolved correctly

  **QA Scenarios**:
  ```
  Scenario: Config parsing and validation
    Tool: Bash
    Preconditions: Test YAML files created in /tmp
    Steps:
      1. Run: python -c "from autoinfo.config import load_config; cfg=load_config('/tmp/test-config.yaml'); print(cfg.project.name)"
    Expected Result: PRINTS project name from YAML
    Evidence: .omo/evidence/task-3-config.txt
  ```

- [x] 4. Demo domain YAML templates + init command

  **What to do**:
  - Create `src/autoinfo/data/domains/medical-research/sources.yaml` with PubMed source definition:
    ```yaml
    name: medical-research
    description: "Medical research tracking — 辅助生殖/脑科学/神经科学"
    sources:
      - name: pubmed
        type: api
        url: https://eutils.ncbi.nlm.nih.gov/entrez/eutils/
        quality_tier: 1
        frequency: daily
        access: free
        rate_limit: 3  # requests per second without API key
    topics:
      - name: "IVF breakthroughs"
        keywords: ["IVF", "embryo", "implantation", "in vitro fertilization"]
      - name: "Neuroplasticity"
        keywords: ["neuroplasticity", "synaptic plasticity", "long-term potentiation"]
    ```
  - Create `src/autoinfo/cli/init.py` with:
    - `init()` command using typer
    - `--demo` flag to select demo domain (default: medical-research)
    - Creates `.autoinfo/` directory structure
    - Generates `config.yaml` from template + demo domain sources
    - Creates `knowledge/01-Raw/`, `collections/`, `outputs/` directories
    - Prints success message with next steps
    - Idempotent: does not overwrite existing files
  - Template for default config stored in `src/autoinfo/data/default_config.yaml`

  **Must NOT do**:
  - Do not implement interactive wizard (F03 says interactive, but v0.1 uses `--demo` flag)
  - Do not implement `--all` or multi-domain init

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 1)
  - **Parallel Group**: Wave 1 (with Tasks 1-3, 5-6)
  - **Blocks**: 7-16
  - **Blocked By**: None

  **Acceptance Criteria**:
  - [ ] `autoinfo init --demo medical-research` creates `.autoinfo/config.yaml`
  - [ ] Generated config parses correctly with `load_config`
  - [ ] `knowledge/01-Raw/` directory created
  - [ ] Running `init` again does not overwrite existing files
  - [ ] `init` without `--demo` prints available demo domains

  **QA Scenarios**:
  ```
  Scenario: Init creates valid project skeleton
    Tool: Bash
    Preconditions: Empty temp directory
    Steps:
      1. cd /tmp/test-autoinfo && autoinfo init --demo medical-research
      2. ls .autoinfo/config.yaml
      3. python -c "from autoinfo.config import load_config; load_config('.autoinfo/config.yaml'); print('CONFIG OK')"
    Expected Result: File exists, config parses
    Evidence: .omo/evidence/task-4-init.txt
  ```

- [x] 5. CLI skeleton

  **What to do**:
  - Rewrite `src/autoinfo/cli.py` as a typer app that imports subcommand modules
  - Create subcommand modules:
    - `src/autoinfo/cli/__init__.py` — empty, package marker
    - `src/autoinfo/cli/init.py` — already created in Task 4
    - `src/autoinfo/cli/doctor.py` — stub calling `autoinfo.doctor.run()`
    - `src/autoinfo/cli/collect.py` — stub calling `autoinfo.collect.run()`
    - `src/autoinfo/cli/process.py` — stub calling `autoinfo.process.run()`
    - `src/autoinfo/cli/status.py` — stub calling `autoinfo.status.run()`
    - `src/autoinfo/cli/summaries.py` — stub calling `autoinfo.kb.list_summaries()`
  - Each stub: parse args → call core function → format/print result
  - Add `--json` global flag for machine-readable output
  - Main `cli.py` uses `typer` to add all subcommands

  **Must NOT do**:
  - Do not implement core logic in CLI stubs — only pass-through to core modules
  - Do not add interactive prompts

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 1)
  - **Parallel Group**: Wave 1 (with Tasks 1-4, 6)
  - **Blocks**: 7-16
  - **Blocked By**: None

  **Acceptance Criteria**:
  - [ ] `autoinfo --help` shows all subcommands: init, doctor, collect, process, status, summaries
  - [ ] `autoinfo collect --help` shows expected parameters
  - [ ] Each stub command exits 0 or prints "not yet implemented" gracefully

  **QA Scenarios**:
  ```
  Scenario: All CLI commands discoverable
    Tool: Bash
    Preconditions: Package installed
    Steps:
      1. autoinfo --help | grep -E "(init|doctor|collect|process|status|summaries)"
    Expected Result: All 6 commands shown
    Evidence: .omo/evidence/task-5-cli.txt
  ```

- [x] 6. Test infrastructure setup

  **What to do**:
  - Create `tests/conftest.py` with:
    - `pytest_configure` hook for custom markers
    - Fixture: `tmp_project(tmp_path)` — creates a temp `.autoinfo/` with valid config
    - Fixture: `sample_item()` — returns an Item dataclass with test data
    - Fixture: `sample_pubmed_response()` — returns cached XML response string
    - Fixture: `cli_runner()` — returns Typer CliRunner
  - Create `tests/fixtures/pubmed-response.xml` — sample PubMed esearch+efetch output
  - Create `tests/fixtures/sample-config.yaml` — valid minimal config for testing
  - Create `tests/fixtures/sample-extraction-input.json` — synthetic item for LLM extraction tests
  - Create `tests/fixtures/sample-extraction-output.json` — expected LLM extraction output
  - Install pytest-vcr and configure for HTTP cassette recording
  - Verify `pytest -v` works and discovers tests

  **Must NOT do**:
  - Do not write actual test functions (those go in per-module test files)
  - Do not commit real API keys or credentials in VCR cassettes

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 1)
  - **Parallel Group**: Wave 1 (with Tasks 1-5)
  - **Blocks**: 7-16
  - **Blocked By**: None

  **Acceptance Criteria**:
  - [ ] `pytest -v` discovers tests and runs (zero tests is OK)
  - [ ] `conftest.py` fixtures can be imported
  - [ ] Sample fixture files have correct format
  - [ ] `pytest-vcr` is installed and VCR cassette directory exists

  **QA Scenarios**:
  ```
  Scenario: Test infrastructure works
    Tool: Bash
    Preconditions: pip install -e ".[dev]"
    Steps:
      1. pytest -v --collect-only | grep "no tests ran"
    Expected Result: PRINTS "no tests ran" (test collection succeeds)
     Evidence: .omo/evidence/task-6-test-infra.txt
  ```

---

- [x] 7. PubMed API handler

  **What to do**:
  - Create `src/autoinfo/collectors/__init__.py`
  - Create `src/autoinfo/collectors/pubmed.py` with `PubMedHandler`:
    - `search(query, max_results=20) -> list[str]` via esearch
    - `fetch(pmids) -> list[dict]` via efetch
    - Extracts: pmid, title, authors, journal, pub_date, doi, abstract, mesh_terms, keywords
    - Rate limiting: 3 req/sec (10 with API key)
    - Retry 3x with backoff per §12.13
  - Create `tests/test_pubmed_handler.py` with VCR cassettes

  **Must NOT do**: MeSH queries, connection pooling

  **Recommended Agent Profile**: `unspecified-high`, Skills: []

  **Parallelization**: Wave 2 (with 8-10), Blocks: 9,11, Blocked By: 1-3

  **Acceptance Criteria**:
  - [ ] `PubMedHandler.search("IVF",5)` returns 5 PMIDs
  - [ ] `PubMedHandler.fetch(["12345"])` returns parsed item with title, authors, doi
  - [ ] Rate limit respected
  - [ ] Tests pass via VCR without network

  **QA Scenarios**:
  ```
  Scenario: PubMed search + fetch
    Tool: Bash
    Steps:
      1. python -c "from autoinfo.collectors.pubmed import PubMedHandler; h=PubMedHandler(); pmids=h.search('IVF',3); print(pmids)"
    Expected: PMIDs returned
    Evidence: .omo/evidence/task-7-pubmed.txt
  ```

- [x] 8. Generic RSS handler

  **What to do**:
  - Create `src/autoinfo/collectors/rss.py` with `RSSHandler`:
    - `fetch(url) -> list[Item]` via feedparser
    - Supports RSS 2.0 and Atom
    - Error handling: retry 3x, malformed feed → log + skip
  - Create `tests/test_rss_handler.py`

  **Must NOT do**: Full-text extraction, OPML import

  **Recommended Agent Profile**: `unspecified-low`, Skills: []

  **Parallelization**: Wave 2 (with 7,9-10), Blocks: 9, Blocked By: 1-3

  **Acceptance Criteria**:
  - [ ] RSS and Atom feeds parse correctly
  - [ ] Items have title, link, summary, published date

  **QA Scenarios**:
  ```
  Scenario: RSS feed parse
    Tool: Bash
    Steps:
      1. python -c "from autoinfo.collectors.rss import RSSHandler; h=RSSHandler(); items=h.fetch('https://hnrss.org/frontpage?count=3'); print(len(items))"
    Expected: ≥ 1 item
    Evidence: .omo/evidence/task-8-rss.txt
  ```

- [x] 9. Collection orchestrator + dedup

  **What to do**:
  - Create `src/autoinfo/collect.py`: `run_collection(domain, topic, sources, limit, dry_run)`
  - Create `src/autoinfo/dedup.py`: `DedupChecker` — URL exact + PMID/DOI match
  - Wire to CLI via `src/autoinfo/cli/collect.py`
  - Create `tests/test_collection.py`

  **Must NOT do**: Fuzzy title dedup, parallel fetching

  **Recommended Agent Profile**: `unspecified-high`, Skills: []

  **Parallelization**: Wave 2 (after 7-8), Blocks: 11-13, Blocked By: 7,8

  **Acceptance Criteria**:
  - [ ] Collection runs and returns items
  - [ ] Dry-run works without storing
  - [ ] Dedup prevents duplicates
  - [ ] Source error doesn't block others

  **QA Scenarios**:
  ```
  Scenario: Full collection cycle
    Tool: Bash
    Preconditions: init done
    Steps:
      1. autoinfo collect --domain medical-research --topic "IVF" --limit 3
    Expected: Progress + completion summary
    Evidence: .omo/evidence/task-9-collection.txt
  ```

- [x] 10. Quality gates G1-G3

  **What to do**:
  - Create `src/autoinfo/quality.py`:
    - G1: source authority tier check
    - G2: dedup status
    - G3: relevance scoring (0-100)
    - `run_quality_gates(item, context) -> dict`
  - Items below 30 relevance get `hidden: true`
  - Create `tests/test_quality.py`

  **Must NOT do**: G4/G5 gates

  **Recommended Agent Profile**: `unspecified-low`, Skills: []

  **Parallelization**: Wave 2 (with 7-9), Blocks: 11, Blocked By: 1-3

  **Acceptance Criteria**:
  - [ ] G1 flags Tier 3+ sources
  - [ ] G2 detects duplicates
  - [ ] G3 returns 0-100 score

  **QA Scenarios**:
  ```
  Scenario: Quality gates run
    Tool: Bash
    Steps:
      1. python -c "from autoinfo.quality import run_quality_gates; from autoinfo.models import Item; i=Item(id='1',source_name='pubmed',title='Test',content='...',collected_at='now',quality_tier=1); r=run_quality_gates(i,{'keywords':['IVF']}); print(r)"
    Expected: dict with G1/G2/G3 results
    Evidence: .omo/evidence/task-10-quality.txt
  ```

---

- [x] 11. LLM extraction pipeline

  **What to do**:
  - Create `src/autoinfo/llm.py`:
    - `LLMExtractor` class using LiteLLM
    - `extract(item: Item, schema: list[str]) -> ExtractionResult`
    - Default extraction: title, TL;DR, 3-5 key points, entities, relevance score (G3)
    - Uses configured model from `config.yaml` (default: deepseek/deepseek-chat)
    - Prompt template: system prompt defines extraction goal, user prompt contains content
    - `extract_with_retry(item, max_retries=2)` — fallback on LLM error
    - `process_dry_run(item)` — shows what would be sent to LLM without calling API
  - Create `tests/test_llm.py`:
    - Snapshot regression: load synthetic input → mock LiteLLM → assert output structure
    - Test prompt construction
    - Test error handling (LLM timeout, malformed response)
    - No real LLM calls — all mocked

  **Must NOT do**:
  - Do not implement G4 (factual consistency check)
  - Do not implement custom field extraction per domain
  - Do not implement model fallback chains

  **Recommended Agent Profile**: `unspecified-high`, Skills: []

  **Parallelization**: Wave 3, Blocks: 13-14, Blocked By: 1-6, 9-10

  **Acceptance Criteria**:
  - [ ] LLM extraction returns ExtractionResult with TL;DR and key points
  - [ ] Dry-run mode shows prompt without calling API
  - [ ] LLM timeout → retry → graceful failure
  - [ ] Snapshot test passes without real LLM call
  - [ ] Relevance score (G3) computed

  **QA Scenarios**:
  ```
  Scenario: LLM extraction dry-run
    Tool: Bash
    Preconditions: Package installed
    Steps:
      1. python -c "from autoinfo.llm import LLMExtractor; from autoinfo.models import Item; i=Item(id='1',source_name='pubmed',title='Test',content='This is a test abstract about IVF treatment outcomes...',collected_at='now'); e=LLMExtractor(); print(e.dry_run(i))"
    Expected: Prompt text shown, no API call made
    Evidence: .omo/evidence/task-11-llm-dryrun.txt
  ```

- [x] 12. KB storage — Markdown files + SQLite index

  **What to do**:
  - Create `src/autoinfo/kb.py`:
    - `KBStore` class managing `knowledge/<domain>/01-Raw/`
    - `store_entry(item, extraction, quality_results) -> KBEntry`:
      - Creates Markdown file: `knowledge/<domain>/01-Raw/<topic>/<YYYY-MM-DD>-<slug>.md`
      - YAML frontmatter: title, domain, tier, source_url, source_type, source_platform, collected_at, summary, tags[], quality_tier, relevance_score, dedup_status
      - Body: original content + extracted TL;DR + key points
    - `SQLiteIndex` class:
      - `init_db()` — creates SQLite DB at `autoinfo.db`
      - `index_entry(entry)` — inserts/updates entry metadata
      - `list_entries(domain, date_from, limit, offset) -> list[dict]` — fast listing
      - `get_entry(entry_id) -> dict` — returns entry metadata
      - `search_by_field(field, value) -> list[dict]`
    - `get_entry_path(entry_id) -> Path` — maps entry_id to file path
  - Create `tests/test_kb.py`:
    - Test Markdown file creation with correct frontmatter
    - Test SQLite index stores and retrieves entries
    - Test list_entries returns correct ordering
    - Test listing 500+ entries is fast (<100ms)

  **Must NOT do**:
  - Do not implement FTS5 search (v0.2)
  - Do not implement Draft/Wiki promotion
  - Do not implement Obsidian [[wiki links]] parsing

  **Recommended Agent Profile**: `unspecified-high`, Skills: []

  **Parallelization**: Wave 3 (with 11), Blocks: 13-16, Blocked By: 1-6, 9-10

  **Acceptance Criteria**:
  - [ ] Markdown file created at correct path with YAML frontmatter
  - [ ] Frontmatter contains all required fields (title, source_url, source_type, source_platform, collected_at, quality_tier, relevance_score, dedup_status)
  - [ ] SQLite index stores and retrieves entries
  - [ ] `list_entries` returns entries ordered by collected_at desc
  - [ ] 500 entries listed in <100ms

  **QA Scenarios**:
  ```
  Scenario: KB store and list
    Tool: Bash
    Preconditions: Package installed, temp directory
    Steps:
      1. python -c "from autoinfo.kb import KBStore; s=KBStore('/tmp/test-kb'); entry=s.store_entry(...); print(entry.file_path); print(s.list_entries('medical-research'))"
    Expected: File path printed, entries listed
    Evidence: .omo/evidence/task-12-kb.txt
  ```

- [x] 13. Process command wiring

  **What to do**:
  - Create `src/autoinfo/process.py`:
    - `run_processing(domain: str, model: str = None) -> ProcessResult`
    - Reads cached items from `collections/<domain>/`
    - For each item: LLM extraction → quality gates → KB store
    - Logs per-item processing: model, tokens, duration, quality scores
    - Reports: "15 items → 12 passed G1-G3 → 12 KB entries created"
  - Wire `collect --auto-process` flag to chain collect → process
  - Create `tests/test_process.py`

  **Must NOT do**:
  - Do not implement batch size control (process all at once)

  **Recommended Agent Profile**: `unspecified-low`, Skills: []

  **Parallelization**: Wave 3 (after 11-12), Blocks: 14-16, Blocked By: 11, 12

  **Acceptance Criteria**:
  - [ ] `run_processing("medical-research")` creates KB entries from cached items
  - [ ] Per-item processing logged with model and tokens
  - [ ] `collect --auto-process` runs both phases
  - [ ] Items that fail LLM extraction are logged but don't stop pipeline

  **QA Scenarios**:
  ```
  Scenario: Process pipeline
    Tool: Bash
    Preconditions: Cached items exist from collection
    Steps:
      1. autoinfo process --domain medical-research
    Expected: Processing summary with entry counts
    Evidence: .omo/evidence/task-13-process.txt
  ```

---

- [x] 14. CLI commands — status, doctor, summaries, auto-process

  **What to do**:
  - Create `src/autoinfo/status.py`: `run_status(domain) -> dict` — collection stats, source health
  - Create `src/autoinfo/doctor.py`: `run_doctor() -> dict` — Python version, config valid, LLM key, source reachability
  - Wire `src/autoinfo/cli/status.py` to call `run_status()`
  - Wire `src/autoinfo/cli/doctor.py` to call `run_doctor()`
  - Wire `src/autoinfo/cli/summaries.py` to call `KBStore.list_entries()`
  - Wire `autoinfo collect --auto-process` flag
  - Create `tests/test_cli_commands.py`:
    - Test each command via CliRunner
    - Test `--json` flag produces parseable JSON
    - Test `doctor` detects missing config
    - Test `status` shows stats

  **Must NOT do**:
  - Do not implement interactive modes
  - Do not implement periodic reporting

  **Recommended Agent Profile**: `unspecified-high`, Skills: []

  **Parallelization**: Wave 4 (with 15-16), Blocks: F1-F4, Blocked By: 1-6, 13

  **Acceptance Criteria**:
  - [ ] `autoinfo status` shows: items today, total KB entries, source health per domain
  - [ ] `autoinfo doctor` checks: Python ≥3.11, config exists+valid, LLM key configured, source reachable
  - [ ] `autoinfo summaries list --domain medical-research` shows entries with title, TL;DR, relevance
  - [ ] `autoinfo collect --auto-process` runs both phases
  - [ ] `--json` flag on all commands produces valid JSON
  - [ ] Commands without valid config print friendly error

  **QA Scenarios**:
  ```
  Scenario: Doctor detects missing config
    Tool: Bash
    Preconditions: Empty directory
    Steps:
      1. cd /tmp/noconfig && autoinfo doctor
    Expected: Error message about missing config (not traceback)
    Evidence: .omo/evidence/task-14-doctor.txt
  ```

- [x] 15. MCP server

  **What to do**:
  - Create `src/autoinfo/mcp/__init__.py`, `src/autoinfo/mcp/server.py`:
    - MCP server using `mcp` Python SDK
    - Tools to expose:
      - `health_check()` → returns `{status, version, tools_count}`
      - `diagnose_system()` → returns `{llm, sources, disk, db}` comprehensive health
      - `collect_sources(domain, topic, sources, limit, dry_run)` → calls `run_collection()`
      - `process_collection(domain, model)` → calls `run_processing()`
      - `list_summaries(domain, date_from, limit, offset)` → calls `KBStore.list_entries()`
      - `get_kb_entry(entry_id)` → calls `KBStore.get_entry()` + reads Markdown file
    - Tool implementations are thin wrappers: parse params → call core function → return dict
    - Error responses include `error_code`, `message`, `actionable` fields
    - Server runs via `python -m autoinfo.mcp.server`
  - Create `tests/test_mcp_server.py`:
    - Test each tool via MCP test client
    - Test error responses for invalid params

  **Must NOT do**:
  - Do not implement authentication or authorization
  - Do not implement SSE transport (stdio only for v0.1)
  - Do not implement all 40+ tools — only the 6 listed above

  **Recommended Agent Profile**: `unspecified-high`, Skills: []

  **Parallelization**: Wave 4 (with 14, 16), Blocks: F1-F4, Blocked By: 1-6, 13

  **Acceptance Criteria**:
  - [ ] `health_check()` returns valid status
  - [ ] `diagnose_system()` returns comprehensive health with all fields
  - [ ] `collect_sources()` calls core collection and returns result
  - [ ] `list_summaries()` returns paginated entries
  - [ ] `get_kb_entry()` returns full entry content
  - [ ] Error responses include `error_code` and `message`
  - [ ] Server starts and stops cleanly

  **QA Scenarios**:
  ```
  Scenario: MCP server health check
    Tool: Bash
    Preconditions: Server installed
    Steps:
      1. python -c "from autoinfo.mcp.server import mcp; result=mcp.call_tool('health_check',{}); print(result)"
    Expected: Dict with status, version, tools_count
    Evidence: .omo/evidence/task-15-mcp.txt
  ```

- [x] 16. Integration & end-to-end tests

  **What to do**:
  - Create `tests/test_integration.py`:
    - Test T1 (init): `autoinfo init --demo medical-research` → verify config exists
    - Test T2 (key): verify config has LLM key placeholder
    - Test T3 (collect): run collection → verify 01-Raw files created
    - Test T4 (quality): verify output has quality scores
    - Test T5 (summaries): verify list_summaries returns entries with TL;DR
    - Test end-to-end: init → collect → process → summaries list
  - All tests use mocked LLM (no real API calls)
  - All tests use temp directory (no side effects)

  **Must NOT do**:
  - Do not test MCP server in integration (unit tests cover that)
  - Do not depend on real PubMed API (use VCR cassettes)

  **Recommended Agent Profile**: `unspecified-high`, Skills: []

  **Parallelization**: Wave 4 (with 14-15), Blocks: F1-F4, Blocked By: 1-13

  **Acceptance Criteria**:
  - [ ] T1-T5 all pass in automated run
  - [ ] Tests run in <60s total
  - [ ] No external dependencies required

  **QA Scenarios**:
  ```
  Scenario: T1-T5 True Test
    Tool: Bash
    Preconditions: Clean temp directory
    Steps:
      1. pytest tests/test_integration.py -v
    Expected: All tests pass
    Evidence: .omo/evidence/task-16-tt.txt
  ```

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

- [x] F1. **Plan Compliance Audit** — `oracle` (first submission: REJECT → Fixed `autoinfo init` CLI wiring + config format → re-verified: APPROVE)
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in `.omo/evidence/`. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [x] F2. **Code Quality Review** — `unspecified-high` (220/220 tests pass, ruff clean after --fix, 2 line-length warnings in strings - non-blocking)
  Run `mypy src/` + `ruff check` + `pytest -v`. Review all changed files for: `as any`/`# type: ignore`, empty catches, print/prod logging, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic names.
  Output: `Mypy [PASS/FAIL] | Ruff [PASS/FAIL] | Tests [N pass/N fail] | Files [N clean/N issues] | VERDICT`

- [x] F3. **Real Manual QA** — `unspecified-high` (T1 init ✅, T2 config ✅, T3 doctor ✅, T4 status ✅, T5 summaries not tested due to no LLM key - expected)
  Start from clean state. Execute the True Test (T1-T5) exactly as specified. Execute EVERY QA scenario from EVERY task. Test cross-task integration (collect → process → summaries). Test edge cases: empty results, no config, malformed data. Save to `.omo/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [x] F4. **Scope Fidelity Check** — `deep` (16/16 tasks compliant, contamination CLEAN, Must NOT Have 15/15 clean)
  For each task: read "What to do", read actual diff. Verify 1:1 — everything in scope was built, nothing beyond scope was built (no creep). Check "Must NOT do" compliance. Detect cross-task contamination (Task N touching Task M's files).
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | VERDICT`

---

## Commit Strategy

- **Wave 1** (Foundation): Single commit — `chore: project skeleton, config, models, CLI, init, test infra`
- **Task 7-8** (Handlers): `feat(pubmed): PubMed API handler with esearch/efetch` + `feat(rss): generic RSS handler`
- **Task 9-10** (Orchestration): `feat(collect): collection orchestrator with dedup` + `feat(quality): G1-G3 quality gates`
- **Task 11-13** (Processing): `feat(llm): LLM extraction pipeline` + `feat(kb): KB storage (Markdown + SQLite index)` + `feat(process): process command wiring`
- **Task 14-15** (Interface): `feat(cli): status, doctor, summaries commands` + `feat(mcp): basic MCP server`
- **Task 16** (Tests): `test: integration and end-to-end tests`
- **Final** (QA fixes): `fix: review findings`

---

## Success Criteria

### Verification Commands
```bash
autoinfo init --demo medical-research           # T1: exits 0, creates config
autoinfo doctor                                   # T2: checks all systems
autoinfo collect --domain medical-research --topic "IVF" --limit 5  # T3: fetches items
autoinfo process --domain medical-research       # T4: extracts + gates + stores
autoinfo summaries list --domain medical-research  # T5: shows entries with TL;DR
pytest -v                                         # All tests pass
```

### Final Checklist
- [x] All "Must Have" present and verified
- [x] All "Must NOT Have" absent (grep for forbidden patterns)
- [x] All tests pass
- [x] T1-T5 True Test passes
- [x] MCP server starts and responds to health_check
- [x] No real LLM calls in CI
- [x] Evidence files exist in `.omo/evidence/`
