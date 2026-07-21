# AutoInfo v1.2 — Complete Gap-Fill Release

## TL;DR

> **Quick Summary**: Fill ALL remaining gaps between AutoInfo v1.1 and the full founder vision. 17 items across search, KB, API, output, scheduling, and multi-user foundation.
>
> **Deliverables**:
> - Vector/hybrid search (sqlite-vec + FTS5 fusion)
> - Faceted search (domain/tags/date/tier/type/lang filters)
> - Centralized keywords management system (`_keywords.yaml`)
> - KB native versioning with git SHA integration
> - REST API (FastAPI, full CRUD, port 8741)
> - Obsidian `[[wiki links]]` in KB Markdown
> - CEFR text classification (EN/ZH/JA)
> - PDF export format
> - Schema versioning / migration framework
> - Email auto-send (SMTP digest delivery)
> - Read-only Web UI dashboard
> - Multi-user foundation (user_id fields)
> - Crontab installer (`autoinfo cron install`)
> - `generate_report` MCP tool, `init --name` flag, report JSON format
>
> **Estimated Effort**: XL (17 implementation tasks + 4 final verification)
> **Parallel Execution**: YES — 5 waves + final verification
> **Critical Path**: Wave 1 foundation → Wave 2 search → Wave 3-4 KB/API → Wave 5 deploy → F1-F4

---

## Context

### Original Request
Fill ALL remaining gaps between the current v1.1 implementation and the full founder vision from `docs/dev/founder-expectations.md`. The gaps are cataloged in §14 of that document.

### Interview Summary
**Key Decisions**:
- **Scope**: All 13 §14 gaps + 4 minor findings = 17 items in one plan. Config override system SKIPPED (current `~/.autoinfo/` + env vars sufficient).
- **Vector search**: sqlite-vec (already in `pyproject.toml`). Simple weighted hybrid: `0.7*FTS5 + 0.3*cosine`. No reranking/cross-encoder.
- **REST API**: FastAPI, full CRUD (POST/DELETE included), port 8741, 127.0.0.1 only. ⚠️ No auth in v1.2 — localhost-only security assumption.
- **KB versioning**: Existing SQLite versioning + git auto-commit + git SHA stored in `entry_versions` metadata table.
- **CEFR**: LLM-based classification only (A1-C2). Languages: English, Chinese, Japanese. No `simplify_for_learning` in v1.2.
- **Scheduling**: `autoinfo cron install` adds POSIX crontab entry. No systemd/launchd/Windows.
- **Multi-user**: Foundation only — `user_id` field on entries, config-level data isolation. No auth, no teams.
- **Test strategy**: Tests-after (per-item, before next item starts). Agent-executed QA scenarios mandatory.
- **Keywords mgmt**: `_keywords.yaml` per domain with states (`verified`, `auto_added`, `deprecated`). MCP tools for approve/reject.
- **Web UI**: Read-only dashboard. Bootstrapped HTML/JS. No build toolchain.

### Research Findings
- KB versioning already exists (SQLite `entry_versions` table, 5-version auto-prune) — the gap is *enhancing* it with git integration
- `generate_report` MCP tool already exists in the MCP server — gap is verifying/improving it
- sqlite-vec in deps but not wired — needs extension loading + embedding pipeline
- FTS5 search is domain-filtered only — no tag/date/tier/type/language facets
- No FastAPI/uvicorn dependency currently
- 720+ existing tests provide regression safety net

### Metis Review
**Identified Gaps** (addressed):
- **§14 count**: User confirmed "all 13" (miscounted as 12). Web UI included despite §10.3 "Out" — user explicitly chose this.
- **6 unmentioned items**: All confirmed IN (faceted search, keywords mgmt, schema versioning, Obsidian links, PDF export, email auto-send).
- **4 minor findings**: Confirmed as generate_report MCP tool, init --name, report JSON format, crontab installer.
- **Versioning exists**: Gap is git integration enhancement, not greenfield build.
- **REST API scope**: Full CRUD + read-only web dashboard.
- **Auth risk**: REST API has no auth. Flagged as known limitation — binds to 127.0.0.1 only.

---

## Work Objectives

### Core Objective
Deliver AutoInfo v1.2 — a complete gap-fill release that satisfies ALL 32 founder expectations from `docs/dev/founder-expectations.md`, including features deferred from v1.1.

### Concrete Deliverables
- 17 implementation items across search, KB, API, output, scheduling, infrastructure
- All verified via agent-executed QA scenarios
- founder-expectations.md updated to show 32/32 expectations met

### Definition of Done
- All 17 items implemented with passing QA scenarios
- F1 Plan Compliance Audit (oracle): all "Must Have" verified, no "Must NOT Have" violations
- F2 Code Quality: tsc/pytest/lint pass
- F3 Manual QA: all scenarios executable end-to-end
- F4 Scope Fidelity: 1:1 alignment with gap list
- `git commit && git push`

### Must Have
- Vector search returns results ranked by hybrid score with `method: "hybrid"` in response
- REST API serves all CRUD endpoints on port 8741
- CEFR tags entries A1-C2 for EN/ZH/JA content
- `autoinfo cron install` creates a valid crontab entry
- `_keywords.yaml` created per domain with state management
- Web UI dashboard serves read-only entry browser

### Must NOT Have (Guardrails)
- NO auth/authentication on REST API (127.0.0.1 only)
- NO reranking or cross-encoders in vector search (sqlite-vec only, simple weighted sum)
- NO `simplify_for_learning` or text simplification (deferred to v1.3)
- NO systemd timer or Windows Task Scheduler support (POSIX crontab only)
- NO config override directory (`~/.autoinfo/overrides/` — decided against)
- NO full NLP pipeline for CEFR (LLM classification only)
- NO complex branching/merging in KB versioning
- NO merge/unmerge/hierarchy in keywords system

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: YES (720+ tests, pytest, CliRunner)
- **Automated tests**: Tests-after (per-item, before next item starts)
- **Framework**: pytest + CliRunner + curl for REST API + Python REPL for library code
- **QA policy**: Every task has ≥3 QA scenarios (happy path, failure case, edge case). Evidence saved to `.omo/evidence/task-{N}-*`.

### QA Tooling Per Item
- **REST API (FastAPI)**: `curl` — POST entry, GET entries, DELETE entry, verify status codes + response bodies
- **Vector search**: Python REPL — create embedding, search hybrid, compare FTS5-only vs hybrid results
- **CEFR**: Python REPL — classify known-level texts, verify A1-C2 mapping
- **Crontab**: `bash` — run `crontab -l` before/after `cron install`, verify entry added/removed
- **Keywords**: `pytest` or CLI — add keyword, approve, list, verify state transitions
- **Web UI**: Playwright — navigate, verify entry list renders, click entry → detail view
- **Email/PDF/Obsidian**: CLI + file inspection — run command, verify output file exists with expected content

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundation — 6 parallel tasks):
├── 1. FastAPI scaffold + base app (port 8741, health endpoint, CORS)
├── 2. sqlite-vec integration + embedding utilities
├── 3. Config schema updates for all new features
├── 4. DB schema versioning framework
├── 5. init --name flag
└── 6. Keywords _keywords.yaml schema + file management

Wave 2 (Search — 3 parallel tasks, depends on Wave 1):
├── 7. Vector search — embeddings on Raw creation + hybrid ranking
├── 8. Faceted search — tags/date/tier/type/lang filters
└── 9. Keywords management MCP tools + CLI (approve/reject/list)

Wave 3 (KB Enhancements — 4 parallel tasks):
├── 10. KB versioning git auto-commit + SHA tracking
├── 11. Obsidian [[wiki links]] in KB Markdown
├── 12. CEFR classification engine (EN/ZH/JA, A1-C2)
└── 13. Multi-user foundation (user_id fields, config isolation)

Wave 4 (Output & API — 5 parallel tasks):
├── 14. PDF export format
├── 15. Report format extension (JSON output)
├── 16. generate_report MCP tool registration
├── 17. REST API CRUD endpoints + integration tests
└── 18. Email auto-send (SMTP digest delivery)

Wave 5 (Deploy & Finalize — 3 tasks):
├── 19. Crontab installer (autoinfo cron install/uninstall)
├── 20. Web UI dashboard (read-only entry browser)
└── 21. Integration tests + validation

Wave FINAL (4 parallel reviews, sequential to all tasks):
├── F1. Plan Compliance Audit (oracle)
├── F2. Code Quality Review (unspecified-high)
├── F3. Real Manual QA (unspecified-high + playwright)
└── F4. Scope Fidelity Check (deep)
→ Present results → Get explicit user okay

Critical Path: 1 → 7 → 10 → 17 → 20 → F1-F4
Parallel Speedup: ~67% faster than sequential
Max Concurrent: 6 (Wave 1)
```

### Dependency Matrix
- **1-6**: None — 7, 12, 14, 17, 19, 20
- **7**: 2 (vector search needs vec utils) — 10, 17
- **8**: 3 (faceted needs config schema) — 17
- **9**: 6 (keywords needs file schema) — none
- **10**: 7 (versioning enhancement) — 17
- **12**: 3 (CEFR needs config) — none
- **17**: 1, 7, 8, 10 (REST depends on search + server base) — 20
- **19**: 3 (cron needs config) — none
- **20**: 17 (dashboard needs API) — F1-F4
- **21**: All above — F1-F4

---

## TODOs

- [x] 1. FastAPI scaffold + base application

  **What to do**:
  - Add `fastapi`, `uvicorn[standard]` to `pyproject.toml` dependencies
  - Create `src/autoinfo/api/` package with `__init__.py`, `server.py`
  - `server.py`: FastAPI app, `GET /health` → `{"status": "ok", "version": "...", "uptime_s": N}`, config loading from `.autoinfo/config.yaml`
  - Bind to `127.0.0.1:8741` by default, configurable via `config.yaml: rest_api.port`
  - CORS middleware: allow all origins (localhost-only security)
  - MCP tool: None for now (this is the infrastructure layer)
  - Do NOT add any data endpoints yet (Task 17 adds CRUD)

  **Must NOT do**:
  - No authentication/authorization middleware
  - No database models or ORM setup
  - No entry endpoints

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2-6)
  - **Blocks**: Task 17 (REST API endpoints), Task 20 (Web UI)
  - **Blocked By**: None

  **References**:
  - `src/autoinfo/mcp/server.py` — existing server pattern (port, config loading style)
  - `src/autoinfo/config.py` — config dataclasses (will add `RestAPIConfig`)
  - `pyproject.toml` — existing dependency list

  **Acceptance Criteria**:
  - [ ] `pip list | grep fastapi` shows fastapi installed
  - [ ] `python -c "from autoinfo.api.server import app; print(app.title)"` → no error
  - [ ] Server starts: `python -m autoinfo.api.server & sleep 2; curl -s http://127.0.0.1:8741/health` → `{"status": "ok"}`

  **QA Scenarios**:
  ```
  Scenario: Server starts and responds to health check
    Tool: Bash
    Preconditions: fastapi + uvicorn installed, no other server on :8741
    Steps:
      1. python -m autoinfo.api.server &
      2. sleep 2
      3. curl -s http://127.0.0.1:8741/health
    Expected Result: Response is a JSON object with `status: "ok"` and `version` string
    Failure Indicators: curl fails, connection refused, non-JSON response, missing version field
    Evidence: .omo/evidence/task-1-health.json

  Scenario: Server respects custom port from config
    Tool: Bash
    Preconditions: TEMP_CONFIG=.autoinfo/config.yaml.bak, modify rest_api.port=18741
    Steps:
      1. Modify config.yaml to set rest_api.port=18741
      2. python -m autoinfo.api.server &
      3. curl -s http://127.0.0.1:18741/health
      4. Restore config.yaml
    Expected Result: Health check succeeds on port 18741
    Evidence: .omo/evidence/task-1-custom-port.json

  Scenario: Server rejects non-localhost connections
    Tool: Bash
    Preconditions: Server running on :8741
    Steps:
      1. curl -s http://0.0.0.0:8741/health 2>&1 || true
    Expected Result: Connection refused or server not listening on 0.0.0.0
    Evidence: .omo/evidence/task-1-localhost-only.txt
  ```

  **Evidence to Capture**:
  - [ ] `.omo/evidence/task-1-health.json`
  - [ ] `.omo/evidence/task-1-custom-port.json`
  - [ ] `.omo/evidence/task-1-localhost-only.txt`

  **Commit**: YES
  - Message: `feat(api): scaffold FastAPI server with health endpoint`
  - Files: `pyproject.toml`, `src/autoinfo/api/*`
  - Pre-commit: `pip install -e ".[dev]" && python -c "from autoinfo.api.server import app"`

---

- [x] 2. sqlite-vec integration + embedding utilities

  **What to do**:
  - Ensure `sqlite-vec` is in `pyproject.toml` (verify or add if missing)
  - Create `src/autoinfo/embeddings.py` with:
    - `load_vec_extension(conn)` — loads sqlite-vec, graceful fallback if unavailable
    - `ensure_embedding_table(conn)` — creates `entry_embeddings` table (entry_id TEXT, embedding BLOB, model TEXT, created_at TEXT)
    - `generate_embedding(text, model_config)` — calls LLM embedding API (use configured `llm.tasks.embedding` model from config)
    - `cosine_similarity(a, b)` — numpy-based cosine for sqlite-vec fallback
    - `store_embedding(conn, entry_id, embedding, model)`
    - `search_embeddings(conn, query_embedding, limit)` — sqlite-vec KNN query
  - Graceful degradation: if sqlite-vec fails to load (`old SQLite`, missing extension), log warning and set `is_available = False`; all vector operations return empty results with `note: "vector unavailable"`
  - Test the extension loading in a throwaway script

  **Must NOT do**:
  - Do NOT integrate with KB pipeline yet (Task 7 does that)
  - Do NOT modify search_knowledge_base yet
  - No CLI/MCP changes

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3-6)
  - **Blocks**: Task 7 (vector search integration)
  - **Blocked By**: None

  **References**:
  - `pyproject.toml:51` — existing `sqlite-vec` entry
  - `src/autoinfo/kb.py` — existing SQLite connection patterns
  - `src/autoinfo/config.py` — `LLMConfig.tasks.embedding` for embedding model config
  - sqlite-vec docs: `https://github.com/asg017/sqlite-vec` for VEC0 syntax

  **Acceptance Criteria**:
  - [ ] `python -c "import sqlite_vec; print(sqlite_vec.__version__)"` → version string
  - [ ] `python -c "from autoinfo.embeddings import load_vec_extension; conn = __import__('sqlite3').connect(':memory:'); load_vec_extension(conn); conn.execute('SELECT vec_version()').fetchone()[0]"` → version string
  - [ ] `python -c "from autoinfo.embeddings import cosine_similarity; assert cosine_similarity([1,0,0], [1,0,0]) == 1.0; assert cosine_similarity([1,0], [0,1]) < 0.1"`

  **QA Scenarios**:
  ```
  Scenario: sqlite-vec extension loads successfully
    Tool: Bash
    Preconditions: sqlite-vec installed, system SQLite ≥ 3.41
    Steps:
      1. python3 -c "
         import sqlite3, sqlite_vec
         conn = sqlite3.connect(':memory:')
         conn.enable_load_extension(True)
         sqlite_vec.load(conn)
         result = conn.execute('SELECT vec_version()').fetchone()[0]
         print(f'vec_version: {result}')
         "
    Expected Result: Outputs `vec_version: v0.x.x` with no ImportError or sqlite3.OperationalError
    Evidence: .omo/evidence/task-2-vec-load.txt

  Scenario: Graceful degradation when sqlite-vec unavailable
    Tool: Bash
    Preconditions: Temporarily rename sqlite_vec.so/dll to simulate absence
    Steps:
      1. python3 -c "
         from autoinfo.embeddings import load_vec_extension
         import sqlite3
         conn = sqlite3.connect(':memory:')
         conn.enable_load_extension(True)
         # Simulate by catching the error
         try:
             load_vec_extension(conn)  # If extension not found, should log warning, not crash
         except Exception as e:
             print(f'Expected graceful handling needed: {e}')
         "
    Expected Result: System logs warning and continues. load_vec_extension does NOT crash the process.
    Evidence: .omo/evidence/task-2-graceful-degradation.txt

  Scenario: cosine_similarity returns correct values
    Tool: Bash
    Preconditions: embeddings.py exists with cosine_similarity function
    Steps:
      1. python3 -c "
         from autoinfo.embeddings import cosine_similarity
         assert abs(cosine_similarity([1,0,0], [1,0,0]) - 1.0) < 0.001, 'identical vectors'
         assert abs(cosine_similarity([1,0,0], [-1,0,0]) - (-1.0)) < 0.001, 'opposite vectors'
         assert abs(cosine_similarity([1,0], [0,1])) < 0.001, 'orthogonal vectors'
         print('All cosine_similarity tests passed')
         "
    Expected Result: "All cosine_similarity tests passed"
    Evidence: .omo/evidence/task-2-cosine.txt
  ```

  **Evidence to Capture**:
  - [ ] `.omo/evidence/task-2-vec-load.txt`
  - [ ] `.omo/evidence/task-2-graceful-degradation.txt`
  - [ ] `.omo/evidence/task-2-cosine.txt`

  **Commit**: YES (with Task 1 or grouped with Wave 1)
  - Message: `feat(embeddings): add sqlite-vec integration with graceful degradation`
  - Files: `pyproject.toml`, `src/autoinfo/embeddings.py`
  - Pre-commit: `python -c "from autoinfo.embeddings import cosine_similarity; cosine_similarity([1],[1])"`

---

- [x] 3. Config schema updates for v1.2 features

  **What to do**:
  - Add dataclasses to `src/autoinfo/config.py`:
    - `CEFRConfig`: `enabled: bool = False`, `languages: list[str] = field(default_factory=lambda: ["en", "zh", "ja"])`, `model: str = ""`
    - `EmailConfig`: `smtp_host: str = ""`, `smtp_port: int = 587`, `smtp_user: str = ""`, `smtp_pass: str = ""` (from env var), `from_addr: str = ""`, `to_addrs: list[str] = field(default_factory=list)`, `enabled: bool = False`
    - `RestAPIConfig`: `enabled: bool = True`, `port: int = 8741`, `host: str = "127.0.0.1"`
    - `VectorSearchConfig`: `enabled: bool = False`, `model: str = ""`, `hybrid_weight_fts5: float = 0.7`, `hybrid_weight_vector: float = 0.3`
    - `CronConfig`: `auto_install: bool = False`, `install_path: str = ""`
    - `MultiUserConfig`: `enabled: bool = False`, `default_user_id: str = "default"`
  - Add `AutoInfoConfig` fields: `cefr: CEFRConfig`, `email: EmailConfig`, `rest_api: RestAPIConfig`, `vector_search: VectorSearchConfig`, `cron: CronConfig`, `multi_user: MultiUserConfig`
  - Update `config_to_dict()`, `validate_config()`, default config template
  - Update `get_effective_llm_config()` if embedding task model is needed (should already work)

  **Must NOT do**:
  - Do NOT implement any feature logic (CEFR, email, etc.)
  - Do NOT modify existing config fields or break backward compat
  - All new configs must have sensible defaults (disabled by default)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1-2, 4-6)
  - **Blocks**: Task 8 (faceted search), Task 12 (CEFR), Task 17-20 (API, email, cron, multi-user)
  - **Blocked By**: None

  **References**:
  - `src/autoinfo/config.py` — existing dataclass patterns (LLMConfig, DomainConfig, SourceConfig)
  - `src/autoinfo/data/default_config.yaml` — existing default template
  - `src/autoinfo/config.py:config_to_dict()` — serialization pattern
  - `src/autoinfo/config.py:validate_config()` — validation pattern

  **Acceptance Criteria**:
  - [ ] `python -c "from autoinfo.config import AutoInfoConfig, CEFRConfig, EmailConfig, RestAPIConfig, VectorSearchConfig; c = AutoInfoConfig(); assert c.cefr.enabled == False; assert c.rest_api.port == 8741"`
  - [ ] `python -c "from autoinfo.config import config_to_dict; d = config_to_dict(AutoInfoConfig()); assert 'cefr' in d; assert 'rest_api' in d; assert 'email' in d"`
  - [ ] `autoinfo doctor` shows new config sections without error

  **QA Scenarios**:
  ```
  Scenario: New configs have correct defaults
    Tool: Bash
    Preconditions: Fresh AutoInfoConfig imported
    Steps:
      1. python3 -c "
         from autoinfo.config import AutoInfoConfig, config_to_dict
         c = AutoInfoConfig()
         assert c.cefr.enabled == False
         assert c.cefr.languages == ['en', 'zh', 'ja']
         assert c.rest_api.port == 8741
         assert c.rest_api.host == '127.0.0.1'
         assert c.rest_api.enabled == True
         assert c.vector_search.enabled == False
         assert c.multi_user.enabled == False
         d = config_to_dict(c)
         assert 'cefr' in d and 'rest_api' in d and 'email' in d and 'vector_search' in d and 'multi_user' in d
         print('All defaults passed')
         "
    Expected Result: "All defaults passed"
    Evidence: .omo/evidence/task-3-defaults.txt

  Scenario: doctor reports new config without error
    Tool: Bash
    Preconditions: Working .autoinfo/config.yaml
    Steps:
      1. autoinfo doctor --json
    Expected Result: Exit code 0, JSON output includes config sections, no KeyError or AttributeError
    Evidence: .omo/evidence/task-3-doctor.json
  ```

  **Evidence to Capture**:
  - [ ] `.omo/evidence/task-3-defaults.txt`
  - [ ] `.omo/evidence/task-3-doctor.json`

  **Commit**: YES (group with Wave 1)
  - Message: `feat(config): add CEFR, email, REST API, vector search, cron, and multi-user config schemas`
  - Files: `src/autoinfo/config.py`, `src/autoinfo/data/default_config.yaml`
  - Pre-commit: `python -c "from autoinfo.config import AutoInfoConfig; AutoInfoConfig()"`

---

- [x] 4. DB schema versioning framework

  **What to do**:
  - Create `src/autoinfo/schema.py` with:
    - `SCHEMA_VERSION = 1` constant
    - `ensure_schema_version_table(conn)` — creates `_schema_version` table (version INTEGER, applied_at TEXT, description TEXT)
    - `get_schema_version(conn)` → current version integer (0 if table missing)
    - `apply_migrations(conn, target_version)` — runs migration functions sequentially
    - Migration functions: `_migrate_v1(conn)` — initial schema, creates version record
    - `check_schema(conn)` — raises `SchemaVersionError` if version < expected
  - Integrate with `KBStore.__init__()`: call `check_schema()` on SQLite connection
  - Integrate with `autoinfo doctor`: show schema version in output
  - Each migration is a function in `schema.py` named `_migrate_v{N}` that takes a connection

  **Must NOT do**:
  - Do NOT add migration for existing schemas (they're already at the initial version)
  - No CLI command for schema management (doctor shows it, auto-migration handles it)
  - No rollback support in v1.2 (forward-only migrations)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1-3, 5-6)
  - **Blocks**: None (other tasks don't depend on it directly)
  - **Blocked By**: None

  **References**:
  - `src/autoinfo/kb.py:SQLiteIndex.__init__()` — existing SQLite init pattern
  - `src/autoinfo/doctor.py` — existing doctor output format
  - `src/autoinfo/kb.py` — `_init_db()` / `_init_fts5()` patterns

  **Acceptance Criteria**:
  - [ ] `python -c "from autoinfo.schema import SCHEMA_VERSION, get_schema_version, apply_migrations; conn = __import__('sqlite3').connect(':memory:'); apply_migrations(conn, SCHEMA_VERSION); assert get_schema_version(conn) == SCHEMA_VERSION"`
  - [ ] `autoinfo doctor --json | python -c "import sys,json; d=json.load(sys.stdin); assert 'schema_version' in d"`
  - [ ] KBStore opens without SchemaVersionError (existing DBs are version-compatible)

  **QA Scenarios**:
  ```
  Scenario: Schema version is tracked
    Tool: Bash
    Preconditions: Fresh in-memory SQLite
    Steps:
      1. python3 -c "
         import sqlite3
         from autoinfo.schema import SCHEMA_VERSION, get_schema_version, apply_migrations
         conn = sqlite3.connect(':memory:')
         assert get_schema_version(conn) == 0, 'no version yet'
         apply_migrations(conn, SCHEMA_VERSION)
         assert get_schema_version(conn) == SCHEMA_VERSION
         print(f'Schema version: {SCHEMA_VERSION}')
         "
    Expected Result: "Schema version: 1" (no errors)
    Evidence: .omo/evidence/task-4-schema-version.txt

  Scenario: doctor shows schema version
    Tool: Bash
    Preconditions: Working .autoinfo/config.yaml, existing autoinfo.db
    Steps:
      1. autoinfo doctor --json
      2. python3 -c "import sys,json; d=json.load(sys.stdin); print(f'schema: {d.get(\"schema_version\", \"missing\")}')"
    Expected Result: JSON output contains "schema_version" field with integer value
    Evidence: .omo/evidence/task-4-doctor-schema.json
  ```

  **Evidence to Capture**:
  - [ ] `.omo/evidence/task-4-schema-version.txt`
  - [ ] `.omo/evidence/task-4-doctor-schema.json`

  **Commit**: YES (group with Wave 1)
  - Message: `feat(schema): add DB schema versioning and migration framework`
  - Files: `src/autoinfo/schema.py`, `src/autoinfo/kb.py`, `src/autoinfo/doctor.py`
  - Pre-commit: `python -m pytest tests/ -x -k "test_schema or test_doctor" -q 2>/dev/null || true`

---

- [x] 5. init --name flag for project naming

  **What to do**:
  - Add `--name` / `-n` parameter to `autoinfo init` CLI in `src/autoinfo/cli/init.py`
  - When provided, stores `project_name: <name>` in the generated `.autoinfo/config.yaml`
  - If not provided, `project_name` is not written (config stays clean)
  - Interactive mode: prompt "Project name (optional):" before domain selection
  - Update `AutoInfoConfig` to include `project_name: str = ""`

  **Must NOT do**:
  - No directory structure changes (name is metadata only)
  - No renaming of existing projects
  - No validation beyond basic string check

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1-4, 6)
  - **Blocks**: None
  - **Blocked By**: None

  **References**:
  - `src/autoinfo/cli/init.py` — existing init command with `--demo` and interactive mode
  - `src/autoinfo/config.py` — `AutoInfoConfig` dataclass
  - `src/autoinfo/data/default_config.yaml` — default config template

  **Acceptance Criteria**:
  - [ ] `autoinfo init --name "IVF Research" --demo medical-research` → exits 0
  - [ ] `cat .autoinfo/config.yaml | grep project_name` → `project_name: "IVF Research"`
  - [ ] Without `--name`, config has no `project_name` key

  **QA Scenarios**:
  ```
  Scenario: init --name stores project name in config
    Tool: Bash
    Preconditions: Empty temp directory
    Steps:
      1. mkdir -p /tmp/test-init-name && cd /tmp/test-init-name
      2. autoinfo init --name "My Research Project" --demo medical-research
      3. grep 'project_name' .autoinfo/config.yaml
    Expected Result: grep finds "project_name: My Research Project" in config.yaml
    Evidence: .omo/evidence/task-5-init-name.txt

  Scenario: init without --name does not add project_name
    Tool: Bash
    Preconditions: Empty temp directory
    Steps:
      1. mkdir -p /tmp/test-init-no-name && cd /tmp/test-init-no-name
      2. autoinfo init --demo medical-research
      3. grep -c 'project_name' .autoinfo/config.yaml || echo 0
    Expected Result: grep finds 0 or no project_name key in config
    Evidence: .omo/evidence/task-5-no-name.txt
  ```

  **Evidence to Capture**:
  - [ ] `.omo/evidence/task-5-init-name.txt`
  - [ ] `.omo/evidence/task-5-no-name.txt`

  **Commit**: YES (group with Wave 1)
  - Message: `feat(init): add --name flag for optional project name metadata`
  - Files: `src/autoinfo/cli/init.py`, `src/autoinfo/config.py`, `src/autoinfo/data/default_config.yaml`
  - Pre-commit: `autoinfo init --help | grep -q --name`

---

- [x] 6. Keywords management system: _keywords.yaml schema + file management

  **What to do**:
  - Create `src/autoinfo/keywords.py` with:
    - `KeywordState` enum: `VERIFIED`, `AUTO_ADDED`, `DEPRECATED`
    - `KeywordEntry` dataclass: `keyword: str`, `state: KeywordState`, `aliases: list[str]`, `created_at: str`, `updated_at: str`, `source: str` (which LLM/source added it)
    - `KeywordsFile` class with:
      - `load(domain)` → reads `knowledge/<domain>/_keywords.yaml`
      - `save(domain, entries)` → writes YAML file
      - `create_if_missing(domain)` → creates file with empty `keywords: {}`
      - `add_keyword(domain, keyword, state="auto_added", aliases=None)` → adds entry
      - `approve_keyword(domain, keyword)` → moves `auto_added` → `verified`
      - `deprecate_keyword(domain, keyword)` → moves → `deprecated`
      - `list_keywords(domain, status=None)` → returns filtered entries
    - YAML schema: `keywords: {keyword: {state: "verified", aliases: [...], created_at: "...", updated_at: "...", source: "..."}}`
  - Integrate with KB pipeline: `process.py` calls `KeywordsFile.add_keyword()` when LLM extraction discovers new keywords
  - Integrate with `list_keywords` MCP tool to read from `_keywords.yaml` instead of (or in addition to) config

  **Must NOT do**:
  - No CLI for keywords management yet (Task 9 adds CLI + MCP tools)
  - No auto-merge, no synonym rings, no hierarchy
  - No UI for editing

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1-5)
  - **Blocks**: Task 9 (keywords MCP tools + CLI)
  - **Blocked By**: None

  **References**:
  - `src/autoinfo/kb.py` — KBStore file operations in `knowledge/<domain>/`
  - `src/autoinfo/quality.py:G3RelevanceScoring` — existing keyword usage
  - `src/autoinfo/config.py:TopicConfig` — existing keywords lists
  - `docs/dev/founder-expectations.md` §F20 — keywords system spec: "Managed status: verified, auto_added, merged, deprecated"

  **Acceptance Criteria**:
  - [ ] `python -c "from autoinfo.keywords import KeywordsFile; kf = KeywordsFile(); kf.create_if_missing('medical'); kf.add_keyword('medical', 'IVF', 'auto_added'); entries = kf.list_keywords('medical'); assert len(entries) > 0; assert entries[0].state == 'auto_added'"`
  - [ ] `kf.approve_keyword('medical', 'IVF')` → state changes to `verified`
  - [ ] YAML file is valid YAML after all operations

  **QA Scenarios**:
  ```
  Scenario: Keywords lifecycle: create → add → approve → list
    Tool: Bash / Python REPL
    Preconditions: Empty knowledge/medical/ directory
    Steps:
      1. python3 -c "
         import tempfile, os
         from autoinfo.keywords import KeywordsFile
         kf = KeywordsFile(base_dir=tempfile.mkdtemp())
         domain = 'test'
         kf.create_if_missing(domain)
         kf.add_keyword(domain, 'IVF breakthrough', 'auto_added', aliases=['IVF 2026'])
         kf.add_keyword(domain, 'embryo grading', 'auto_added')
         auto_added = kf.list_keywords(domain, status='auto_added')
         assert len(auto_added) == 2
         kf.approve_keyword(domain, 'IVF breakthrough')
         verified = kf.list_keywords(domain, status='verified')
         assert len(verified) == 1
         assert verified[0].keyword == 'IVF breakthrough'
         kf.deprecate_keyword(domain, 'embryo grading')
         deprecated = kf.list_keywords(domain, status='deprecated')
         assert len(deprecated) == 1
         print('Keywords lifecycle PASS')
         "
    Expected Result: "Keywords lifecycle PASS"
    Evidence: .omo/evidence/task-6-keywords-lifecycle.txt

  Scenario: YAML file is valid after operations
    Tool: Bash
    Preconditions: Same temp dir from lifecycle test
    Steps:
      1. python3 -c "
         import yaml
         with open(f'{tempdir}/knowledge/test/_keywords.yaml') as f:
             data = yaml.safe_load(f)
         assert 'keywords' in data
         assert 'IVF breakthrough' in data['keywords']
         assert data['keywords']['IVF breakthrough']['state'] == 'verified'
         print('YAML valid')
         "
    Expected Result: "YAML valid" — file is parseable and contains expected structure
    Evidence: .omo/evidence/task-6-keywords-yaml.txt
  ```

  **Evidence to Capture**:
  - [ ] `.omo/evidence/task-6-keywords-lifecycle.txt`
  - [ ] `.omo/evidence/task-6-keywords-yaml.txt`

  **Commit**: YES (group with Wave 1)
  - Message: `feat(keywords): add _keywords.yaml management system with state lifecycle`
  - Files: `src/autoinfo/keywords.py`, `src/autoinfo/process.py`
   - Pre-commit: `python -c "from autoinfo.keywords import KeywordsFile, KeywordState; print('OK')"`

---

- [x] 7. Vector search — embeddings on Raw creation + hybrid ranking

  **What to do**:
  - In `KBStore.store_entry()`: after creating a 01-Raw entry, if `vector_search.enabled` is True:
    - Generate embedding via `embeddings.generate_embedding(entry_text, config)`
    - Store via `embeddings.store_embedding(conn, entry_id, embedding, model_name)`
  - Modify `SQLiteIndex.search_fts5()` to also accept `mode="hybrid"` param:
    - When mode="hybrid": run FTS5 query + sqlite-vec KNN query, fuse scores using weighted sum
    - Add `method` field: `"fts5"`, `"hybrid"`, or `"vector"`
    - When vec unavailable: fall back to FTS5 with `note: "vector unavailable"`
  - Update `search_knowledge_base` MCP tool to accept `mode: str = "fts5"`

  **Must NOT do**: No reranking/cross-encoders, Raw-only embeddings

  **Agent**: `deep` | **Wave 2** (depends: Task 2) | **Blocks**: Task 10

  **References**: `kb.py:KBStore.store_entry()`, `kb.py:SQLiteIndex.search_fts5()`, `embeddings.py`

  **Acceptance**:
  - Entry created with vec enabled → `entry_embeddings` has row
  - `search_knowledge_base(mode="hybrid")` → method="hybrid", relevance_score
  - Vec unavailable → falls back to FTS5 gracefully

  **Commit**: `feat(search): add hybrid vector search with sqlite-vec`

---

- [x] 8. Faceted search — tag/date/tier/type/lang filters

  **What to do**: Extend `search_fts5()` with filter params: `filter_tags`, `filter_date_from/to`, `filter_quality_tier_min/max`, `filter_content_type`, `filter_language`. Build dynamic WHERE clauses. Update MCP tool schema + CLI flags.

  **Must NOT do**: No faceted counting, no custom field filters

  **Agent**: `unspecified-high` | **Wave 2** (parallel 7,9) | **Blocks**: Task 17

  **References**: `kb.py:search_fts5()`, `mcp/server.py`, `cli/kb.py`

  **QA**: `filter_language="en"` → all results en; `filter_tags=["ivf"] + filter_language="en"` composes

  **Commit**: `feat(search): add faceted search filters`

---

- [x] 9. Keywords management — MCP tools + CLI

  **What to do**: Add `approve_keyword`/`reject_keyword` MCP tools, `suggest_keywords` tool. New CLI group `autoinfo keywords {list,approve,reject}`. Wire into Typer app.

  **Agent**: `unspecified-high` | **Wave 2** | **Blocked By**: Task 6

  **Commit**: `feat(keywords): add MCP tools + CLI for keyword state management`

---

- [x] 10. KB versioning git auto-commit + SHA tracking

  **What to do**: Add `git_sha` to `entry_versions` table. After saving version, run `git add && git commit`. If git unavailable, skip gracefully. CLI: `autoinfo kb history` shows SHAs.

  **Agent**: `unspecified-high` | **Wave 3** | **Blocked By**: Task 7

  **Commit**: `feat(kb): add git auto-commit with SHA tracking`

---

- [x] 11. Obsidian [[wiki links]] in KB Markdown

  **What to do**: Scan entry body for wiki-link syntax. Append `## Linked References` section with `[[Title]]` links to other entries sharing tags. CLI: `autoinfo kb wiki-links --rebuild`.

  **Agent**: `quick` | **Wave 3** (parallel 10,12,13)

  **Commit**: `feat(kb): add Obsidian [[wiki links]]`

---

- [x] 12. CEFR classification (EN/ZH/JA, A1-C2)

  **What to do**: Create `cefr.py` with `classify_text(text, lang)` → `{cefr_level, confidence}` via LLM. Store in frontmatter. MCP + CLI. ZH/JA use approximated equivalents.

  **Must NOT do**: No simplification, no glossary (v1.3)

  **Agent**: `deep` | **Wave 3** | **Reference**: `process.py`, `config.py:CEFRConfig`

  **QA**: "cat sat on mat" → A1, "epistemological foundations" → C2

  **Commit**: `feat(cefr): add LLM-based CEFR classification`

---

- [x] 13. Multi-user foundation (user_id fields)

  **What to do**: Add optional `user_id` to entry frontmatter + SQLite. When `multi_user.enabled`, filter all KB operations by user_id. MCP tools accept optional user_id.

  **Must NOT do**: No auth, no teams

  **Agent**: `unspecified-high` | **Wave 3** | **Reference**: `config.py:MultiUserConfig`

  **Commit**: `feat(multi-user): add user_id data isolation`

---

- [x] 14. PDF export format

  **What to do**: Add `weasyprint` dep. Extend `export_kb(format="pdf")` to render Markdown→PDF. CLI: `autoinfo output export --format pdf`.

  **Agent**: `quick` | **Wave 4** (parallel 15-18)

  **Commit**: `feat(export): add PDF export format`

---

- [x] 15. Report JSON format extension

  **What to do**: Extend `generate_report(format="json")`. JSON body with title, entries, summary, metadata.

  **Agent**: `quick` | **Wave 4**

  **Commit**: `feat(output): add JSON report format`

---

- [x] 16. generate_report MCP tool registration

  **What to do**: Verify/Add `_handle_generate_report()` MCP handler following digest pattern. Accept `domain`, `format`, `period`.

  **Agent**: `quick` | **Wave 4**

  **Commit**: `feat(mcp): add generate_report tool`

---

- [x] 17. REST API CRUD endpoints (FastAPI)

  **What to do**: Build on Task 1. Routes in `routes.py`: `GET /entries`, `GET /entries/{id}`, `POST /entries`, `DELETE /entries/{id}`, `GET /search`. Pydantic schemas. Error handling (404/400/422).

  **Must NOT do**: No auth (127.0.0.1 only)

  **Agent**: `unspecified-high` | **Wave 4** | **Blocked By**: 1,7,8,10 | **Blocks**: 20

  **QA**: curl POST → 201 with id; curl GET nonexistent → 404; curl DELETE → 204

  **Commit**: `feat(api): add full CRUD REST API`

---

- [x] 18. Email auto-send — SMTP digest delivery

  **What to do**: Create `email_sender.py` with `send_digest()`. Stdlib smtplib. HTML+plaintext. CLI + MCP tool.

  **Agent**: `unspecified-high` | **Wave 4**

  **Commit**: `feat(email): add SMTP digest delivery`

---

- [x] 19. Crontab installer — `autoinfo cron install/uninstall`

  **What to do**: Add commands to `cli/cron.py`. Checks `which crontab`. Idempotent: marks lines with `# autoinfo-cron-managed`.

  **Agent**: `quick` | **Wave 5** | **Reference**: `cli/cron.py`

  **QA**: install → crontab has entry; uninstall → entry gone; no crond → error message

  **Commit**: `feat(cron): add cron install/uninstall`

---

- [x] 20. Web UI dashboard — read-only entry browser

  **What to do**: Single-page HTML/JS dashboard served by FastAPI. Bootstrap CDN. Entry list, search, detail view. CEFR badges. No build toolchain.

  **Agent**: `visual-engineering` | **Wave 5** | **Blocked By**: 17

  **QA** (Playwright): Navigate → entries render; search → results; click → detail

  **Commit**: `feat(ui): add read-only web dashboard`

---

- [x] 21. Integration tests for all v1.2 features

  **What to do**: Write integration tests covering all 17 features. Vector search, REST API CRUD, CEFR, email (mock SMTP), keywords lifecycle, cron, PDF, wiki links, multi-user, schema versioning, faceted search.

  **Agent**: `unspecified-high` | **Wave 5** | **Blocked By**: All tasks 1-20

  **Commit**: `test(v1.2): integration tests for all features`

---

## Final Verification Wave (MANDATORY)

- [x] F1. **Plan Compliance Audit** — `oracle` — **APPROVE**
  Read plan end-to-end. Verify "Must Have" exists, "Must NOT Have" absent. Check evidence.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | VERDICT`

- [x] F2. **Code Quality Review** — `unspecified-high` — **APPROVE**
  Lint + tests + style. No slop (commented code, unused imports, empty catches).
  Output: `Build [PASS/FAIL] | Tests [N/N] | VERDICT`

- [x] F3. **Real Manual QA** — `unspecified-high` (+playwright if UI) — **APPROVE**
  Execute ALL QA scenarios from clean state. Save to `.omo/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | VERDICT`

- [x] F4. **Scope Fidelity Check** — `deep` — **APPROVE**
  Verify every implementation matches spec exactly. No more, no less.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | VERDICT`

---

## Commit Strategy

| Tasks | Message |
|-------|---------|
| 1 | `feat(api): scaffold FastAPI server with health endpoint` |
| 2 | `feat(embeddings): add sqlite-vec integration` |
| 3 | `feat(config): add v1.2 feature config schemas` |
| 4 | `feat(schema): add DB schema versioning framework` |
| 5 | `feat(init): add --name flag for project metadata` |
| 6 | `feat(keywords): add _keywords.yaml management system` |
| 7 | `feat(search): add hybrid vector search` |
| 8 | `feat(search): add faceted search filters` |
| 9 | `feat(keywords): add MCP tools and CLI` |
| 10 | `feat(kb): add git auto-commit with SHA tracking` |
| 11 | `feat(kb): add Obsidian [[wiki links]]` |
| 12 | `feat(cefr): add LLM-based CEFR classification` |
| 13 | `feat(multi-user): add user_id data isolation` |
| 14 | `feat(export): add PDF export format` |
| 15 | `feat(output): add JSON report format` |
| 16 | `feat(mcp): add generate_report tool` |
| 17 | `feat(api): add full CRUD REST API` |
| 18 | `feat(email): add SMTP digest delivery` |
| 19 | `feat(cron): add cron install/uninstall` |
| 20 | `feat(ui): add read-only web dashboard` |
| 21 | `test(v1.2): integration tests` |
| F1-F4 | `chore(v1.2): final verification wave — all 4 pass` |

---

## Success Criteria

### Final Checklist
- [ ] All 21 tasks implemented with QA evidence
- [ ] F1 Plan Compliance: Must Have [N/N], Must NOT Have [N/N]
- [ ] F2 Code Quality: lint pass, tests pass
- [ ] F3 Manual QA: all scenarios pass
- [ ] F4 Scope Fidelity: 1:1 spec match
- [ ] founder-expectations.md updated: 32/32 expectations met
- [ ] `git commit && git push`
