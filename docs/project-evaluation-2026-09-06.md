# AutoInfo Project Evaluation

**Date**: 2026-09-06
**Scope**: Full codebase scan across agent-orientation, robustness, code quality, infrastructure, security, architecture, scalability, and documentation.
**Scale**: 1–10 per dimension | **10** = exceptional | **7** = strong | **5** = adequate | **<5** = concerning

---

## Scorecard

| Dimension | Score | Key Strength | Key Weakness |
|-----------|-------|-------------|--------------|
| Agent-Orientation | **9/10** | 146 MCP tools, unified error envelope, 138 validation scenarios, editor configs in-repo | server.py 12K monolith, constraints documentation-only |
| Robustness | **8/10** | Fallback chain on all paths, rate limiting, G0-G5 hard/soft gates, schema migrations | output/__init__.py 13K god module, no circuit breaker |
| Bugs & Code Quality | **7/10** | Zero TODO/FIXME, 4,926 tests, no eval/SQL injection, parameterized queries | 863 lint errors, 17-18 pre-existing test failures, two god modules |
| Infrastructure for Vibe Coding | **8/10** | Changed-files CI gates, baseline-aware coverage, doc drift guard, regression flywheel | Release workflow disconnected, full-tree lint not enforced |
| Documentation | **9/10** | 7 ADRs, 12 specs, acceptance framework, drift guard in CI | None significant |
| Security | **7/10** | Triple-layer secret scanning, BYOK, parameterized SQL, HMAC webhooks | No dependency scanning, no REST auth, no prompt injection defense |
| Architecture | **6/10** | Clean subsystem separation, config dataclasses, extensible collectors | Two 12K+ god modules, no module splitting |
| Scalability | **7/10** | Thread pools, per-provider rate limits, hybrid search | SQLite single-writer, no config caching |

**Overall: 7.6/10**

---

## Detailed Findings

### 1. Agent-Orientation (9/10)

**Strengths**:
- 146 MCP tools across 35 categories — every system capability is agent-callable.
- Unified error envelope (`errors.py`, 26 error codes): `{success, error: {code, message, actionable}}`.
- 138 validation scenarios (65 functional + 73 regression) executable via MCP tools.
- Read-only MCP mode (`autoinfo serve --agent`) for safe agent operation.
- Agent callback system with persistent SQLite storage.
- CLI ↔ MCP parity (31 command groups mirror MCP tools).
- Editor configs committed in-repo (Cursor, OpenCode, Claude Desktop).
- Self-discovering tool count via `get_tool_count`.

**Weaknesses**:
- `server.py` (12,236 lines) is a single-file monolith containing all 146 tool implementations.
- MCP runs over stdio only — no SSE transport for remote agent connections.
- Agent constraints (MUST NOT table in AGENTS.md) are documentation-only, not enforced in code.

**Key Files**: `src/autoinfo/mcp/server.py`, `src/autoinfo/mcp/errors.py`, `src/autoinfo/mcp/scenarios/`

---

### 2. Robustness (8/10)

**Strengths**:
- LLM fallback chain on ALL call paths (extraction, quality gates, translation QA, output generation, keywords, Q&A, CEFR). Shared `llm.call_with_fallback` walks `[primary] + config.llm.fallback`.
- Per-provider rate limiting via `threading.Semaphore` keyed by `(provider, base_url)`. Default concurrency 4, env-overridable.
- Jittered exponential backoff on HTTP 429/5xx: 3 attempts, base 1.0s × 2, cap 8s, ±25% jitter. Non-retryable 4xx surface immediately.
- Quality gates G0-G5 with hard/soft split: G0/G4 hard (3× retry → block), G1-G3/G5 soft (configurable thresholds).
- Dead-source detection (Semantic Scholar 429 → SourceFailure, fail-fast).
- Thread pool bounded: `AUTOINFO_PROCESS_WORKERS` (default 5, cap 16), `AUTOINFO_SUBTASK_CAP` (default 4).
- SQLite busy timeout and storage lock retry with exponential backoff.
- Schema versioning with forward-only migrations.
- pytest-timeout 180s per test — hung tests fail in 3 minutes.

**Weaknesses**:
- `output/__init__.py` (13,165 lines) is a fragility risk — one file handles all output formats.
- No circuit breaker pattern for persistently failing external sources.
- Config reloaded from disk on every MCP tool call (no in-memory cache).
- Agent constraints not enforced in code.

**Key Files**: `src/autoinfo/llm.py`, `src/autoinfo/quality.py`, `src/autoinfo/schema.py`, `src/autoinfo/process.py`

---

### 3. Bugs & Code Quality (7/10)

**Strengths**:
- Zero TODO/FIXME/HACK comments in `src/` (only false positives: "HACKERNEWS", "chapter_XXX.mp3").
- 4,926 tests across 280 test files (test-to-source ratio >2:1).
- Extensive use of dataclasses for structured types.
- basedpyright strict mode. Type hints pervasive. ~70 warnings (all informational, zero errors) on `llm.py`.
- No `eval()`/`exec()` calls. No bare `except: pass` blocks. No SQL injection (parameterized queries throughout).

**Weaknesses**:
- `server.py` (12,236 lines) and `output/__init__.py` (13,165 lines) are both well above the 250 LOC ceiling.
- 863 pre-existing ruff lint errors (E402×70, N806×27, F841×18, etc.). `server.py` has 214 suppressed errors from a direct commit bypassing PR gates.
- 17-18 documented pre-existing test failures in `tests/TRIAGE.md` (env/config-dependent).
- mypy strict mode with `ignore_missing_imports = true` — strictness undermined by ignoring untyped third-party libs.

**Key Metrics**:
| Metric | Value |
|--------|-------|
| Source files | 134 |
| Test files | 280 |
| Tests collected | 4,926 |
| Largest file | `output/__init__.py` (13,165 lines) |
| TODO/FIXME/HACK in src/ | 0 |
| Pre-existing lint errors | 863 |
| Pre-existing test failures | 17-18 |
| eval()/exec() usage | 0 |

---

### 4. Infrastructure for Continuous Vibe Coding (8/10)

**Strengths**:
- 5 GitHub Actions workflows with changed-files-only design:
  - `ci.yml`: Lint (ruff changed-files + E9/F gate), Mypy (changed-files, strict), Test (fast subset, Py3.12), Scenario portability
  - `coverage.yml`: Baseline-aware changed-modules coverage gate (no-regression vs merge-base, 60% floor for new modules)
  - `guard.yml`: Doc drift guard (bans stale strings in docs/README/AGENTS)
  - `nightly.yml`: Full-suite at 02:00 with all extras
  - `pr-title-check.yml`: Conventional Commits regex gate
- Pre-commit hooks: ruff v0.9.10 (fix + format), pre-commit-hooks v5.0.0 (8 hooks), gitleaks v8.18.4, local credential-URL guard.
- 138 validation scenarios executable as acceptance tests.
- Regression flywheel — every bug must ship a regression scenario.
- Coverage gate is baseline-aware (prevents dragging down existing module coverage).
- TRIAGE.md — honest pre-existing failure ledger.

**Weaknesses**:
- `release-please.yml` removed from `.github/workflows/` (upstream repo suspended). Release automation config-ready but not wired.
- Full-tree lint not enforced — only changed-files ruff + E9/F gate. 863 pre-existing errors tolerated.
- No `make format` or `make hooks-install` Makefile targets.
- Suite runtime ~10 min (fast subset), ~18 min (coverage double-run).
- Python version matrix inconsistency: CI uses 3.11 (mypy) and 3.12 (test), local venv is 3.14.4.

**Key Files**: `.github/workflows/{ci,coverage,guard,nightly,pr-title-check}.yml`, `.pre-commit-config.yaml`, `tests/TRIAGE.md`

---

### 5. Documentation (9/10)

| Doc | Lines | Purpose |
|-----|-------|---------|
| AGENTS.md | 368 | Agent operating manual — architecture rules, MUST NOT table, LLM config semantics |
| README.md | 498 | Exhaustive Status table, MCP tool catalog, 21 demo domains, tech stack |
| CONTRIBUTING.md | 361 | Human onboarding, DCO, CC, regression-scenario mandate, AI-disclosure policy |
| GOVERNANCE.md | 212 | Branch protection, label taxonomy, release management |
| docs/dev/specs/ | 12 files | Full spec library (expectations, quality-gates, pipeline, delivery, operations, market, mcp-tools, data-models, user-lifecycle, multi-tenancy, ops-runbook) |
| docs/adr/ | 7+ ADRs | Architecture Decision Records with "why" index |
| docs/dev/acceptance-framework.md | AC1-AC9 | Top-level validation charter |
| docs/dev/validation-scenario-contract.md | 768 lines | Authoring + execution how-to |
| docs/glossary.md | Ubiquitous Language | Authoritative definitions |

The drift guard (`guard.yml`) actively prevents docs from lying about counts/features. This is a unique strength.

---

### 6. Security (7/10)

| Area | Assessment |
|------|------------|
| API key handling | ✅ Env vars, `${...}` placeholder interpolation, BYOK principle. `configure_llm()` stores env var reference, never raw keys. |
| Secret scanning | ✅ gitleaks v8.18.4 pre-commit + CI + local credential-URL guard. Three layers. |
| SQL injection | ✅ Parameterized queries throughout (`?` placeholders). |
| eval()/exec() | ✅ Zero usage in src/. |
| Webhook security | ✅ HMAC signature verification on inbound webhooks. |
| Hardcoded secrets | ✅ No hardcoded API keys found in source. |
| Input validation | ✅ MCP tools validate parameters, return typed errors. `VALID_SOURCE_TYPES` frozenset as single source of truth. |
| Missing | ⚠️ No dependency vulnerability scanning (no pip-audit, no Dependabot config, no lockfile). |
| Missing | ⚠️ No auth on REST API (port 8741). |
| Missing | ⚠️ No LLM prompt injection defense (user content flows into extraction prompts). |

---

### 7. Architecture & Modularity (6/10)

| Aspect | Assessment |
|--------|------------|
| Module organization | 🟡 134 source files healthy, but 2 god modules dominate. |
| Separation of concerns | ✅ CLI/MCP/API cleanly separated. Collectors/LLM/KB/Output/Quality are distinct subsystems. |
| Dependency direction | ✅ Core modules don't import from CLI or MCP. |
| Configuration | ✅ Dataclass-based config with YAML serialization, env var resolution, validation. |
| Extensibility | ✅ New collectors via handler function + `_build_handler` registration. New domains are config-only. |
| God modules | ❌ `server.py` (12K lines, 146 tools) and `output/__init__.py` (13K lines, all formats) need splitting. |
| Circular imports | ✅ No circular imports detected. |

---

### 8. Scalability & Performance (7/10)

| Aspect | Assessment |
|--------|------------|
| Concurrency | ✅ ThreadPoolExecutor (5 workers, cap 16), per-provider semaphores, asyncio.to_thread for MCP handlers. |
| LLM rate limiting | ✅ Per-provider shared rate limiting with jittered backoff. |
| Storage | 🟡 SQLite is single-writer. `_STORAGE_LOCK` serializes all KB operations. Fine for single-server; won't scale to distributed. |
| Caching | 🟡 Config reloaded from disk on every MCP tool call. No in-memory cache with TTL. |
| Search | ✅ FTS5 keyword + sqlite-vec vector embeddings. Hybrid search with faceted filtering. |
| Collection | ✅ Parallel source fetching via ThreadPoolExecutor. Dedup (URL → DOI → fuzzy title → semantic). |

---

## Pain Points (Prioritized)

### P0 — Blocking / Structural Debt

#### 1. Two God Modules Need Decomposition
- `src/autoinfo/mcp/server.py` — 12,236 lines, all 146 tool implementations in one file.
  - **Impact**: Every future feature or bugfix touches this file. Contributors can't reason about blast radius. Merge conflicts are guaranteed.
  - **Fix**: Split by category into `src/autoinfo/mcp/tools/{system,discovery,kb,output,...}.py`.

- `src/autoinfo/output/__init__.py` — 13,165 lines handling all output formats.
  - **Impact**: A change in video output can break EPUB rendering. No developer can hold this file in context.
  - **Fix**: Split into `src/autoinfo/output/{digest,report,video,audio,ebook,...}.py`.

#### 2. Release Pipeline Disconnected
- `release-please.yml` removed from `.github/workflows/` when upstream repo (1StepMore) was suspended.
- Config is intact (`release-please-config.json`, manifest at 1.11.0, ADR-0007, version annotation in `_version.py`) but not wired.
- `tests/test_release_workflow.py` carries 3 `@pytest.mark.skip` tests proving the gap.
- **Impact**: No automated release PRs, no CHANGELOG generation, no PyPI publish. Version bumps require hand-editing.
- **Fix**: Restore `release-please.yml` workflow file to `.github/workflows/`.

---

### P1 — Quality & Correctness

#### 3. 863 Pre-existing Lint Errors
- `server.py` alone has 214 suppressed errors from a direct commit bypassing PR gates.
- CI uses changed-files-only gating + per-file ignores to tolerate these. `make lint` locally fails on them.
- **Impact**: New contributors can't distinguish their errors from legacy debt. Local lint is unreliable.
- **Fix**: Dedicated cleanup sweep. Consider `ruff check --fix` with targeted suppressions for genuinely unfixable lines.

#### 4. 17-18 Documented Pre-existing Test Failures
- `tests/TRIAGE.md` lists env/config-dependent base failures.
- **Impact**: "CI red" doesn't always mean regression. Requires context to interpret.
- **Fix**: Either fix the root causes or mark as permanent skips with clear annotations.

#### 5. Agent Constraints Not Enforced in Code
- The "MUST NOT" table in AGENTS.md (no demoting Wiki entries, no running `init_project`, etc.) is documentation-only.
- **Impact**: Agent misbehavior detected late. No guardrails preventing costly mistakes.
- **Fix**: Add runtime guards in MCP tool handlers (e.g., `promote_kb_draft` checks admission before proceeding, `delete_user_data` requires explicit confirmation).

---

### P2 — Developer Experience

#### 6. No Dependency Vulnerability Scanning
- No `pip-audit`, no Dependabot config, no lockfile. Dependencies are floors (`>=`), not pins.
- **Impact**: Supply chain risk is unmonitored. Known CVEs in transitive deps won't be caught.
- **Fix**: Add `pip-audit` to CI. Consider Dependabot or Renovate for automated dependency updates.

#### 7. Config Reloaded From Disk on Every MCP Tool Call
- `_load_config()` reads `.autoinfo/config.yaml` on each invocation. No in-memory cache.
- **Impact**: Slow under high-frequency agent operation. Repeated disk I/O.
- **Fix**: Add TTL-based in-memory cache (e.g., 5-second TTL, invalidate on write operations).

#### 8. No `make format` or `make hooks-install` Targets
- ruff format exists via pre-commit but there's no Makefile target. `pre-commit install` must be remembered manually.
- **Fix**: Add `format:` and `hooks-install:` targets to Makefile.

#### 9. Python Version Matrix Inconsistency
- CI uses 3.11 (mypy) and 3.12 (test). Local venv is 3.14.4. `conftest.py` has typer-on-Py3.14 skip workarounds.
- **Impact**: Typer compatibility issues on 3.14 are masked, not fixed.
- **Fix**: Standardize on 3.12 across CI. Address typer compatibility on 3.14 or bump minimum to 3.12.

---

### P3 — Operational Gaps

#### 10. REST API Has No Authentication
- Port 8741 is open, no auth middleware. README says "localhost security" but this won't hold for shared environments.
- **Impact**: Anyone on the network can read/write KB entries, trigger collections, or modify config.
- **Fix**: Add optional API key or token-based auth middleware.

#### 11. No Circuit Breaker for External Sources
- PubMed, Semantic Scholar, etc. that fail persistently are reported via `get_source_health` but not automatically throttled.
- **Impact**: Wasted LLM tokens and time retrying sources that are down.
- **Fix**: Add circuit breaker pattern (open after N failures, half-open after cooldown).

#### 12. No LLM Prompt Injection Defense
- User-supplied content (collected articles) flows into LLM extraction prompts. No sanitization or instruction-following isolation.
- **Impact**: Malicious article content could manipulate LLM extraction behavior.
- **Fix**: Add input sanitization layer. Consider prompt hardening (delimiter tokens, instruction priming).

---

## Pain Points Summary Table

| Priority | Pain Point | Effort | Impact |
|----------|-----------|--------|--------|
| **P0** | server.py 12K monolith | High (refactor) | Unblocks all future work |
| **P0** | output/__init__.py 13K monolith | High (refactor) | Prevents output regressions |
| **P0** | Release pipeline disconnected | Low (restore workflow) | Enables automated releases |
| **P1** | 863 lint errors | Medium (cleanup sweep) | Developer confidence |
| **P1** | 17-18 pre-existing test failures | Medium (fix or skip-permanently) | CI signal clarity |
| **P1** | Agent constraints not in code | Medium (add guards) | Prevents costly agent mistakes |
| **P2** | No dependency scanning | Low (add pip-audit/Dependabot) | Supply chain safety |
| **P2** | Config disk reload every call | Low (add TTL cache) | Agent throughput |
| **P2** | Missing Makefile targets | Low (add 2 targets) | DX polish |
| **P3** | REST API no auth | Medium (add middleware) | Security posture |
| **P3** | No circuit breaker | Medium (add pattern) | Cost efficiency |
| **P3** | No prompt injection defense | High (architectural) | Safety |
