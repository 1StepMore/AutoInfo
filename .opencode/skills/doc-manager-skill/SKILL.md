---
name: doc-manager-skill
description: AutoInfo project documentation inventory, change-impact analysis, and doc-update workflow.
  Load this skill whenever code changes may affect project documentation.
author: AutoInfo
version: 1.0.0
---

# AutoInfo Documentation Manager Skill

## Purpose

This skill tells the agent:
1. **What documentation exists** in the AutoInfo project — a complete, categorized inventory
2. **Which docs are affected** when code changes — a code-to-doc dependency map
3. **How to update docs** correctly — the step-by-step workflow for each doc type
4. **What to verify** after doc updates — quality gates for documentation

Load this skill whenever you modify project code, add features, change configuration,
or if the user asks about project documentation.

---

## 1. Complete Document Inventory

All documentation files in the AutoInfo project, organized by audience and purpose.

### 1.1 User-Facing Docs (for humans using AutoInfo)

| File | Purpose | Criticality | Update Frequency |
|------|---------|-------------|-----------------|
| `README.md` (project root) | Project overview, feature list, quick start, architecture diagram, CLI table, MCP table, status table, limitations | 🔴 P0 — project front door | Every feature/CLI/MCP change |
| `CHANGELOG.md` (project root) | Version history — all additions, changes, fixes per version | 🔴 P0 — release notes | Every version/feature/fix |
| `pyproject.toml` | Python packaging metadata (version, deps, entry points) | 🔴 P0 — build system | Version bumps, dependency changes |
| `Makefile` | Build automation targets (install/test/lint/clean) | 🟡 P1 — dev convenience | When build workflow changes |

### 1.2 Agent-Facing Docs (for AI agents connecting to AutoInfo — operator skills)

| File | Purpose | Criticality | Update Frequency |
|------|---------|-------------|-----------------|
| `AGENTS.md` (project root) | Agent onboarding: operating model, architecture rules, MCP tool catalog, common patterns, LLM config, status table | 🔴 P0 — agent interface | Every MCP/CLI/rule change |
| `docs/skills/autoinfo-skill/SKILL.md` | Skill for operating AutoInfo via MCP tools | 🔴 P0 — operator skill | When MCP workflows change |
| `docs/skills/translator-qa-skill/SKILL.md` | Skill for translation QA pipeline | 🟡 P1 — operator skill | When translation QA changes |

### 1.3 Coding Agent Skills (for developing AutoInfo — consumed by the coding agent)

| File | Purpose | Criticality | Update Frequency |
|------|---------|-------------|-----------------|
| `.opencode/skills/doc-manager-skill/SKILL.md` | **This file** — documentation inventory, change-impact analysis, and doc-update workflow | 🔴 P0 — dev skill | When doc inventory or code structure changes |

### 1.4 Developer Docs (architecture and specification)

| File | Purpose | Criticality | Update Frequency |
|------|---------|-------------|-----------------|
| `docs/dev/founder-expectations.md` | Full project specification: 32 expectations, 13 technical decisions, design principles, 3 user types, deferred items catalog | 🔴 P0 — spec | Every architecture/feature change |
| `docs/dev/Hermes-KnowledgeBase-介绍.md` | KB pipeline reference model (4-tier: Inbox→Raw→Draft→Wiki) | 🟡 P1 — design reference | When KB pipeline changes |
| `docs/dev/agent-alerting.md` | Agent proactive alerting pattern — polling-based source health monitoring | 🟡 P1 — agent pattern | When health monitoring changes |

### 1.4 Validation Docs (testing and verification plans)

| File | Purpose | Criticality | Update Frequency |
|------|---------|-------------|-----------------|
| `docs/autoinfo-validation-master-plan.md` | Original validation plan (~40% feature coverage) | 🟠 P2 — legacy | Rarely (superseded by v2) |
| `docs/autoinfo-validation-master-plan-v2/README.md` | Validation plan v2 index: 100% coverage, 60 questions, 12 parts | 🟡 P1 — validation | When feature surface changes |
| `docs/autoinfo-validation-master-plan-v2/part-01-core-pipeline.md` | Core pipeline: init, collect, process, browse, status, doctor | 🟡 P1 | When core pipeline changes |
| `docs/autoinfo-validation-master-plan-v2/part-02-cli-full.md` | All 17 CLI commands with subcommand testing | 🟡 P1 | When CLI changes |
| `docs/autoinfo-validation-master-plan-v2/part-03-mcp-system-tools.md` | MCP system/discovery/domain/source/topic tools | 🟡 P1 | When MCP tools change |
| `docs/autoinfo-validation-master-plan-v2/part-04-mcp-kb-output.md` | MCP KB/search/output/cron/email/CEFR tools | 🟡 P1 | When MCP tools change |
| `docs/autoinfo-validation-master-plan-v2/part-05-quality-gates.md` | G1-G5 quality gates | 🟡 P1 | When quality gates change |
| `docs/autoinfo-validation-master-plan-v2/part-06-kb-pipeline.md` | KB 4-tier pipeline, import/export, versioning, graph | 🟡 P1 | When KB pipeline changes |
| `docs/autoinfo-validation-master-plan-v2/part-07-rest-api-webui.md` | REST API CRUD, Web UI dashboard | 🟡 P1 | When API/UI changes |
| `docs/autoinfo-validation-master-plan-v2/part-08-agent-e2e.md` | Real API E2E (PubMed/RSS/Web + LLM) | 🟡 P1 | When E2E flow changes |
| `docs/autoinfo-validation-master-plan-v2/part-09-async-cron-email.md` | Async jobs, cron, email, webhooks, alerting | 🟡 P1 | When async/cron/email changes |
| `docs/autoinfo-validation-master-plan-v2/part-10-error-boundary.md` | Error/boundary matrix across all layers | 🟡 P1 | When error handling changes |
| `docs/autoinfo-validation-master-plan-v2/part-11-production-validation.md` | Doctor diagnostics, MCP stdio, stress test, test suite | 🟡 P1 | When diagnostics/test changes |
| `docs/autoinfo-validation-master-plan-v2/part-12-final-verdict.md` | Summary verdict, production gap checklist | 🟡 P1 | When validation completes |

### 1.5 Configuration Docs (MCP connection configs)

| File | Purpose | Criticality |
|------|---------|-------------|
| `.cursor/mcp.json` | Cursor MCP connection config | 🟡 P1 |
| `.claude/claude_desktop_config.json` | Claude Desktop MCP connection config | 🟡 P1 |
| `.opencode/mcp.json` | OpenCode MCP connection config | 🟡 P1 |

---

## 2. Code-to-Doc Dependency Map

When you modify each code module below, the listed documentation files **must** be reviewed and updated.

### 2.1 CLI Module (`src/autoinfo/cli/`)

| Submodule | Docs to Update | What to Update |
|-----------|---------------|----------------|
| Any CLI file | `README.md` | CLI command table (verify 17 groups, add new groups, update descriptions) |
| Any CLI file | `AGENTS.md` | CLI command references in patterns, operating model |
| Any CLI file | `CHANGELOG.md` | Add entry under current version |
| New CLI group | `docs/autoinfo-validation-master-plan-v2/part-02-cli-full.md` | Add scenarios for new command group |
| CLI flag changes | `README.md`, `docs/dev/founder-expectations.md` | Update flag examples |

### 2.2 MCP Server (`src/autoinfo/mcp/`)

| Submodule | Docs to Update | What to Update |
|-----------|---------------|----------------|
| `server.py` — new tool | `AGENTS.md` | Tool Discovery table (category + tool name), tool count (currently 72) |
| `server.py` — new tool | `README.md` | MCP Tools table (category + tool name), tool count |
| `server.py` — new tool | `autoinfo-SKILL.md` | Tool Discovery table, Workflow sections if new workflow |
| `server.py` — new tool | `CHANGELOG.md` | Add entry |
| `server.py` — new tool | `docs/autoinfo-validation-master-plan-v2/` parts 03/04 | Add validation scenarios |
| `server.py` — tool param change | `AGENTS.md`, `README.md`, affected skills | Update parameter descriptions |
| `errors.py` — new ErrorCode | `docs/autoinfo-validation-master-plan-v2/part-10-error-boundary.md` | Add error code to boundary matrix |
| Tool count changes | `AGENTS.md`, `README.md`, `CHANGELOG.md` | Update "72 tools" / "65 tools" references |

### 2.3 KB Pipeline (`src/autoinfo/kb.py`)

| Change | Docs to Update | What to Update |
|--------|---------------|----------------|
| KB tier logic | `AGENTS.md` | Architecture Rules (KB Pipeline Hermes Model) |
| KB tier logic | `docs/dev/Hermes-KnowledgeBase-介绍.md` | Pipeline design details |
| KB tier logic | `docs/dev/founder-expectations.md` | KB pipeline expectations |
| KB tier logic | `README.md` | Status table (KB pipeline row) |
| KB entry schema | `docs/dev/founder-expectations.md` | Entry field specifications |
| KB search/index | `README.md`, `AGENTS.md` | Search features description |

### 2.4 REST API (`src/autoinfo/api/`)

| Change | Docs to Update | What to Update |
|--------|---------------|----------------|
| New endpoint | `README.md` | REST API section, API documentation |
| New endpoint | `AGENTS.md` | Common patterns (REST API usage) |
| New endpoint | `CHANGELOG.md` | Add entry |
| Endpoint behavior change | `docs/autoinfo-validation-master-plan-v2/part-07-rest-api-webui.md` | Update scenarios |
| API route handler | `README.md` | Verify port 8741, endpoint list |
| Dashboard UI | `README.md`, `AGENTS.md` | Web UI Dashboard description |

### 2.5 Collectors (`src/autoinfo/collectors/`)

| Change | Docs to Update | What to Update |
|--------|---------------|----------------|
| New collector type | `README.md` | Feature list (multi-source collection), demo domains table |
| New collector type | `CHANGELOG.md` | Add entry |
| New collector type | `docs/autoinfo-validation-master-plan-v2/part-01-core-pipeline.md` | Add collection scenarios |
| Collector config change | `docs/dev/founder-expectations.md` | Collection pipeline expectations |
| Demo source change | `README.md` | Demo Domains table (sources per domain) |

### 2.6 LLM Extraction (`src/autoinfo/llm.py`)

| Change | Docs to Update | What to Update |
|--------|---------------|----------------|
| Extraction fields | `AGENTS.md` | Common patterns (extraction, domain schema) |
| Extraction fields | `docs/dev/founder-expectations.md` | LLM extraction expectations |
| Model/provider config | `AGENTS.md` | LLM Configuration section |
| Model/provider config | `README.md` | Quick Start (LLM key), LLM Configuration info |
| Extraction behavior | `README.md` | Status table (LLM extraction row) |

### 2.7 Output Generation (`src/autoinfo/output.py`)

| Change | Docs to Update | What to Update |
|--------|---------------|----------------|
| New output format | `README.md` | Feature list, Output/MCP tool tables |
| New output format | `CHANGELOG.md` | Add entry |
| Output template change | `docs/autoinfo-validation-master-plan-v2/part-04-mcp-kb-output.md` | Update output scenarios |
| Tool parameter change | `autoinfo-SKILL.md` | Update workflow examples if workflow changes |

### 2.8 Quality Gates (`src/autoinfo/quality.py`)

| Change | Docs to Update | What to Update |
|--------|---------------|----------------|
| Gate logic change | `AGENTS.md` | Quality Gates table (advisory, not blocking) |
| Gate logic change | `README.md` | Quality gates feature description |
| Gate logic change | `docs/autoinfo-validation-master-plan-v2/part-05-quality-gates.md` | Update scenarios |
| New gate | `docs/dev/founder-expectations.md` | Quality expectations |
| New gate | `CHANGELOG.md` | Add entry |

### 2.9 Translation QA (`src/autoinfo/translation_qa.py`)

| Change | Docs to Update | What to Update |
|--------|---------------|----------------|
| Pipeline logic | `translator-qa-skill/SKILL.md` | Update workflow steps, thresholds, code examples |
| Pipeline logic | `docs/dev/founder-expectations.md` | Localization/translation expectations |
| Score calculation | `translator-qa-skill/SKILL.md` | Update score example, weights |
| New feature | `CHANGELOG.md` | Add entry |

### 2.10 Terminology (`src/autoinfo/terminology.py`)

| Change | Docs to Update | What to Update |
|--------|---------------|----------------|
| Loader logic | `translator-qa-skill/SKILL.md` | Update terminology loading example |
| Format change | `docs/dev/founder-expectations.md` | Terminology expectations |

### 2.11 CEFR (`src/autoinfo/cefr.py`)

| Change | Docs to Update | What to Update |
|--------|---------------|----------------|
| Classification logic | `README.md` | Feature list, CEFR description |
| Classification logic | `AGENTS.md` | Common patterns (CEFR classification) |
| New language | `README.md`, `CHANGELOG.md` | Update feature list, add changelog entry |

### 2.12 Email Sender (`src/autoinfo/email_sender.py`)

| Change | Docs to Update | What to Update |
|--------|---------------|----------------|
| Sending logic | `README.md` | Feature list, CLI table (email command group) |
| Config change | `docs/dev/agent-alerting.md` | Email digest delivery pattern |
| Config change | `docs/autoinfo-validation-master-plan-v2/part-09-async-cron-email.md` | Update scenarios |

### 2.13 Config (`src/autoinfo/config.py`)

| Change | Docs to Update | What to Update |
|--------|---------------|----------------|
| Config schema | `README.md` | Quick Start, LLM Configuration |
| Config schema | `AGENTS.md` | LLM Configuration section, architecture rules (DO NOT modify directly) |
| Config schema | `docs/dev/founder-expectations.md` | Config system expectations |
| New config field | `docs/autoinfo-validation-master-plan-v2/part-11-production-validation.md` | Update diagnostic scenarios |

### 2.14 Domain Management (`src/autoinfo/cli/domain.py`, MCP tools)

| Change | Docs to Update | What to Update |
|--------|---------------|----------------|
| Domain CRUD logic | `README.md` | Feature list, CLI table, MCP tools table |
| Domain CRUD logic | `AGENTS.md` | Architecture rules, common patterns |
| Domain CRUD logic | `autoinfo-SKILL.md` | Workflow examples (create custom domain) |
| Domain CRUD logic | `CHANGELOG.md` | Add entry |

### 2.15 Webhooks (`set_domain_webhooks`/`get_domain_webhooks`)

| Change | Docs to Update | What to Update |
|--------|---------------|----------------|
| Webhook logic | `README.md` | Feature list, MCP tools table |
| Webhook logic | `AGENTS.md` | Tool catalog |
| Webhook logic | `CHANGELOG.md` | Add entry |

### 2.16 Importer (`src/autoinfo/importer.py`)

| Change | Docs to Update | What to Update |
|--------|---------------|----------------|
| Import logic | `README.md` | Feature list (KB import) |
| Import logic | `CHANGELOG.md` | Add entry |
| New format | `docs/autoinfo-validation-master-plan-v2/part-06-kb-pipeline.md` | Update import scenarios |

### 2.17 Version Bumps / Release

| Change | Docs to Update | What to Update |
|--------|---------------|----------------|
| Version bump in `pyproject.toml` | `README.md` | Version references in Known Limitations |
| Version bump in `pyproject.toml` | `CHANGELOG.md` | Add version header and notes |
| Version bump in `pyproject.toml` | `docs/dev/founder-expectations.md` | Version references, gantt chart, status tables |
| Any release prep | All P0 docs | Comprehensive review of all docs for accuracy |

---

## 3. Doc Update Workflow

Follow this workflow whenever you make code changes that affect docs:

### Step 1: Identify Affected Docs

1. Use the Code-to-Doc Dependency Map (Section 2 above) to identify which docs are affected by your code change
2. **Read each affected doc** to understand its current state (do not rely on memory — docs drift)
3. If the change touches a code module NOT listed in Section 2, treat ALL P0 docs as potentially affected and scan each one

### Step 2: Apply Changes Per Doc Type

#### For `README.md`:
```
Affected sections to check:
- Features list → verify/add/remove bullet points
- Status table → update checkmarks and descriptions
- Quick Start → update commands if CLI changed
- Architecture diagram → update if pipeline changed
- CLI Commands table → verify 17 groups, update descriptions
- MCP Tools table → verify tool count (currently 72), update categories/tools
- Demo Domains table → update sources per domain
- Known Limitations → update deferred items, version references
```

#### For `AGENTS.md`:
```
Affected sections to check:
- Project Structure → update directory tree if new modules added
- Architecture Rules → update KB pipeline, collection pipeline, quality gates
- Agent Constraints → add/remove MUST NOT rules
- Tool Discovery Guidance → update tool tables (verify category + tool count)
- Common Patterns → update/add/remove patterns
- LLM Configuration → update if provider/model config changes
- Status table → verify against README.md (must match)
- References → add/remove reference links
```

#### For `CHANGELOG.md`:
```
Entry format:
## <new-version> (<date>)

### Added
- **<Feature name>** — <one-line description of what was added>

### Changed
- **<Component>** — <description of behavioral change>

### Fixed
- **<Component>** — <description of bug fix>

### Infrastructure
- <file/module added or changed>
```

#### For Skill Files (`autoinfo-SKILL.md`, `translator-qa-skill/SKILL.md`, `doc-manager-skill/SKILL.md`):
```
Affected sections:
- Tool Discovery tables → add/remove tools from categories
- Common Workflows → update step-by-step if workflow changed
- Important Constraints → update if rules changed
- Code examples → update examples to use new APIs
```

#### For Validation Plan v2 docs:
```
Update affected part files:
- Add new scenarios for new features
- Update expected results for changed behavior
- Keep the scenario format: exact command → expected result → PASS/FAIL
```

### Step 3: Update Quantitative References

Some numbers appear in multiple docs and must stay consistent:

| Reference | Check in | Current Value |
|-----------|----------|---------------|
| MCP tool count | `README.md`, `AGENTS.md`, `CHANGELOG.md` | 72 |
| MCP tool categories | `README.md`, `AGENTS.md`, `CHANGELOG.md` | 16 |
| CLI command groups | `README.md`, `AGENTS.md`, `CHANGELOG.md` | 17 |
| Test count | `README.md`, `AGENTS.md`, `autoinfo-validation-master-plan-v2/README.md` | 1134 |
| REST API port | `README.md`, `AGENTS.md` | 8741 |
| Demo domains count | `README.md`, `AGENTS.md` | 3 |

After any change that affects these numbers, update EVERY location they appear.

### Step 4: Verify Doc Consistency

After making doc changes, verify cross-doc consistency:

```
Cross-doc consistency checks:

1. `README.md` vs `AGENTS.md`:
   - Tool counts must match
   - CLI command group counts must match
   - Status table rows must match
   - Feature descriptions must agree

2. `CHANGELOG.md` vs all other docs:
   - Every "Added" feature in CHANGELOG must appear in README feature list
   - Every "Changed" component must be reflected in doc updates

3. Skills vs Code:
   - `autoinfo-SKILL.md` workflows must be achievable with actual MCP tools
   - `translator-qa-skill/SKILL.md` code examples must match actual API signatures
   - This `doc-manager-skill/SKILL.md` doc inventory and dependency map must be current

4. Validation plans vs Feature set:
   - Every feature in README must have validation scenarios
   - Every validation scenario must reference an existing feature
```

### Step 5: Run Verification

For every doc change, verify:

1. **No broken links** — Check that all relative file paths (`docs/...`, `src/...`) resolve correctly
2. **No stale numbers** — Verify all quantitative references (tool counts, version numbers, etc.)
3. **README renders correctly** — The README is displayed on GitHub, PyPI, and other surfaces
4. **AGENTS.md is agent-ready** — The agent guide is consumed by AI agents; verify it's parseable

---

## 4. Doc Quality Gates

These gates determine whether a doc update is complete:

### Gate D1: Completeness (P0)
- Every doc identified in the dependency map (Section 2) was reviewed
- Every quantitative reference was updated (Section 3, Step 3)
- No "TODO" or "stale" markers remain in updated docs

### Gate D2: Consistency (P0)
- Cross-doc consistency checks pass (Section 3, Step 4)
- No contradictory statements between README.md and AGENTS.md
- CHANGELOG.md entries match actual changes

### Gate D3: Accuracy (P1)
- Code examples in docs actually work (if not possible to run, at minimum the syntax is correct)
- Tool/function names match actual code
- Parameter names and types match actual signatures

### Gate D4: Freshness (P1)
- Known Limitations section in README.md is current
- Status table checkmarks are accurate
- Deferred items list reflects current reality

---

## 5. Common Doc-Update Scenarios

### Scenario A: Adding a new MCP tool

**When**: You add a new handler function in `src/autoinfo/mcp/server.py` and register it in the tool list.

**Docs to update**: `README.md` (MCP table), `AGENTS.md` (Tool Discovery table), `CHANGELOG.md`, `autoinfo-SKILL.md` (if it adds a new workflow category)

**Quantities to bump**: MCP tool count (currently 72), category count if new category

**Validation plan**: Add scenarios to the appropriate v2 part file (part-03 for system/domain/source/topic tools, part-04 for KB/output/cron/email/CEFR tools)

**Verify**: 
```
AGENTS.md MCP tool table → new tool appears in correct category
README.md MCP tool table → matches AGENTS.md exactly
autoinfo-SKILL.md → workflow updated if needed
CHANGELOG.md → "Added: MCP tool 'xxx'"
```

### Scenario B: Adding a new CLI command group

**When**: You add a new CLI module in `src/autoinfo/cli/` and register it in the CLI entry point.

**Docs to update**: `README.md` (CLI table, feature list), `AGENTS.md` (CLI references), `CHANGELOG.md`, `docs/autoinfo-validation-master-plan-v2/part-02-cli-full.md`

**Quantities to bump**: CLI command group count (currently 17)

**Verify**:
```
README.md CLI section → new command group listed with description
AGENTS.md → CLI references updated
CHANGELOG.md → entry under "Changed: CLI expanded from N to N+1 command groups"
Validation plan part-02 → new scenarios cover new command group
```

### Scenario C: Changing KB pipeline behavior

**When**: You modify `src/autoinfo/kb.py`, changing how the 4-tier pipeline works.

**Docs to update**: `AGENTS.md` (Architecture Rules — KB Pipeline), `docs/dev/Hermes-KnowledgeBase-介绍.md`, `docs/dev/founder-expectations.md`, `README.md` (Status table), `CHANGELOG.md`

**Critical**: The KB pipeline rules (01-Raw is sole entry point, agent cannot write to 03-Wiki, 03-Wiki is append-only) are **hard architecture constraints**. If these rules change, the update is a breaking change and must be clearly communicated in ALL docs.

**Verify**:
```
AGENTS.md Architecture Rules → KB Pipeline table matches new behavior
Hermes-KnowledgeBase-介绍.md → pipeline diagram and rules updated
founder-expectations.md → expectations reflect new pipeline
```

### Scenario D: Version release

**When**: Bumping version in `pyproject.toml` (e.g., 1.4 → 1.5).

**Docs to update**: ALL P0 docs, ALL P1 docs with version references, `CHANGELOG.md`

**Checklist**:
- [ ] `pyproject.toml` — `version = "1.5.0"`
- [ ] `CHANGELOG.md` — new version header with all changes documented
- [ ] `README.md` — Known Limitations version references, feature list updated
- [ ] `AGENTS.md` — Status table, tool counts, CLI counts verified
- [ ] `docs/dev/founder-expectations.md` — gantt chart, version references, status tables
- [ ] Cross-doc consistency verified
- [ ] All MCP/CLI tool counts match actual code inventory

### Scenario E: Adding a new code module

**When**: You add a new `.py` file to `src/autoinfo/`.

**Docs to check/update**:
- `README.md` — Feature list if the module adds a user-facing capability
- `AGENTS.md` — Project Structure tree, Architecture rules if new rules apply
- `CHANGELOG.md` — Infrastructure entry
- This `doc-manager-skill/SKILL.md` — Section 2 (Code-to-Doc Dependency Map) — add new mapping

**Critical**: When adding a new module, **also update this doc-manager-skill** to include the new module in Section 2. This keeps the dependency map complete.

---

## 6. Project Glossary

Terms that appear across docs and must be used consistently:

| Term | Definition | Used In |
|------|-----------|---------|
| Hermes model | 4-tier KB pipeline: 00-Inbox → 01-Raw → 02-Draft → 03-Wiki | AGENTS.md, Hermes doc, founder-expectations.md |
| G1-G5 | Quality gates: Source authority, Dedup, Relevance, Factual, Translation | AGENTS.md, README.md, quality.md |
| P0/P1/P2 | Priority levels used in status tables | README.md, AGENTS.md |
| 01-Raw | Sole entry point for all collected content | All KB-related docs |
| 03-Wiki | Append-only, human-promotion only | All KB-related docs |
| BYOK | Bring Your Own Keys (LLM provider) | README.md, founder-expectations.md |
| Agent-native | All capabilities as MCP tools; agent operates, human directs | AGENTS.md |
| LiteLLM | Underlying LLM provider abstraction layer | AGENTS.md, llm.py |
| FTS5 | Full-text search (SQLite FTS5 extension) | README.md, AGENTS.md |
| sqlite-vec | Vector embedding extension for SQLite | README.md |
| Domain-agnostic | Platform works for any domain, demo domains are configs | AGENTS.md, founder-expectations.md |
| MCP | Model Context Protocol (stdio transport) | All docs |

---

## 7. When to Load This Skill

Load this skill (`load_skills=["doc-manager-skill"]`) when:

- You are **adding a new feature** to any part of AutoInfo
- You are **modifying existing code** that affects CLI, MCP, KB, API, collectors, LLM, output, or config
- You are **bumping the project version** or preparing a release
- You are **adding a new code module** to `src/autoinfo/`
- You are **changing any architecture rule** (KB pipeline, collection pipeline, quality gates)
- The user asks **"what docs exist?"**, **"what needs updating?"**, or **"review the documentation"**
- You are **fixing a bug** that changes behavior visible to users or agents
- You **update MCP tool counts, CLI counts, or test counts**
- You **add or remove a demo domain** or change demo domain sources

**Do NOT load** this skill for:
- Trivial typo fixes in code comments
- Internal refactoring with no behavioral change
- Test-only changes (unless test count changes)
- Dependency version bumps with no behavior delta
