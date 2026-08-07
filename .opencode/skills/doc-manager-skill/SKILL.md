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
| `docs/known-limitations/blocked-sources.md` | Catalog of high-value sources blocked by cost/policy/technical limits, with alternative recommendations | 🟡 P1 — limitations reference | When new sources are evaluated or blocked |
| `docs/dev/specs/delivery.md` (C11) | Podcast RSS publishing (C11) is documented in the delivery spec: RSS 2.0 channel with `<enclosure>` + `itunes:*` namespace, MP3 persistence (the standalone `docs/podcast-publishing.md` runbook was removed 2026-08-05; content covered by the spec + cross-dimensional-catalog C11) | 🟡 P1 — feature doc | When podcast/delivery features change |

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

> All spec content was extracted from `docs/dev/founder-expectations.md` (2108 lines pre-split) into standalone spec files under `docs/dev/specs/` on 2026-07-26. See `docs/archive/founder-expectations-pre-split.md` for the exact pre-split backup. The current `founder-expectations.md` is a **446-line simplified index** with stubs + cross-references. The dedicated spec files below are the source truth for each topic.

| File | Purpose | Criticality | Update Frequency |
|------|---------|-------------|-----------------|
| `docs/dev/founder-expectations.md` | **Index document** (446 lines) — §1-2 kept, §10-14 kept, all other sections → stubs → spec files. Full backup: `docs/archive/founder-expectations-pre-split.md` (2108 lines). | 🔴 P0 — spec anchor | When high-level scope/status changes |
| `docs/dev/specs/expectations.md` | **Expectation Catalog — F01 to F57** (873 lines). All 57 expectations across 12 phases with UX Detail tables and status markers. | 🔴 P0 — extracted spec | When expectations/status change |
| `docs/dev/specs/quality-gates.md` | G0-G5 quality gates, D1-D3 delivery gates: gate catalog, philosophy, retry strategies, configuration model, testing strategy | 🔴 P0 — extracted spec | When quality gate logic changes |
| `docs/dev/specs/pipeline.md` | Collection pipeline, KB pipeline (4-tier), LLM config, processing & LLM extraction, import pipeline, CEFR, cross-collection dedup & merge, performance targets | 🔴 P0 — extracted spec | When pipeline logic changes |
| `docs/dev/specs/delivery.md` | Output generation, delivery channels (13-channel matrix), error recovery & resilience, end user lifecycle (UserProfile/Subscription/DeliveryLog) | 🔴 P0 — extracted spec | When delivery/end-user logic changes |
| `docs/dev/specs/operations.md` | Cost governance, data privacy & compliance, knowledge lifecycle (TTL, versioning, decay), observability (logging, metrics, diagnostics) | 🔴 P0 — extracted spec | When operations features change |
| `docs/dev/specs/market-positioning.md` | Priority matrix, competitive landscape, target user personas, WTP comparison, pricing benchmarks, content/regional strategy, market trends | 🔴 P0 — extracted spec | When market/positioning changes |
| `docs/dev/specs/mcp-tools.md` | Complete MCP tool inventory table (142 tools across 35 categories) | 🔴 P0 — extracted spec | When MCP tools change |
| `docs/dev/specs/data-models.md` | Consolidated data model schemas: Item, ExtractionResult, UserProfile, Subscription, DeliveryLog, CostLog, AuditLog, SystemHealth | 🟡 P1 — reference | When data models change |
| `docs/archive/kb-pipeline-reference.md` | KB pipeline reference model (4-tier: Inbox→Raw→Draft→Wiki) | 🟡 P1 — design reference (archived) | Rarely — only when archived doc reference changes |
| `docs/dev/agent-alerting.md` | Agent proactive alerting pattern — polling-based source health monitoring | 🟡 P1 — agent pattern | When health monitoring changes |
| `docs/dev/director-user-guide.md` | Human-Agent interaction lifecycle: role definitions, communication patterns, operation model for the Director User (756 lines) | 🔴 P0 — human interface | When agent interaction model changes |
| `docs/dev/cross-dimensional-catalog.md` | **Keystone product matrix** (A1-A7 Pipeline × B1/B2/B3 Users, 42 cells, 5 gap types, 780 lines). Cross-references all gaps to spec files. | 🔴 P0 — product keystone | When product scope or gap status changes |
| `docs/dev/specs/user-lifecycle-definition.md` | Foundational spec defining three user types (B1 End User, B2 Direct User, B3 Director User) and their complete lifecycles (453 lines) | 🔴 P0 — foundational spec | When user model changes |
| `docs/dev/specs/ops-runbook.md` | Operations runbook: backup, disaster recovery, monitoring, scaling, agent quick reference with MCP tool mappings (1027 lines) | 🟡 P1 — operations guide | When operations procedures change |
| `docs/dev/specs/multi-tenancy-auth.md` | Multi-tenancy, authentication, rate limiting, admin dashboard — architectural design (deferred until SSE transport, 769 lines) | 🟠 P2 — deferred spec | When auth/multi-tenancy is implemented |
| `docs/dev/new-domain-guide.md` | Guide for creating new domains: domain schema, source configuration, topic setup, demo domain import | 🟡 P1 — onboarding guide | When domain config/demo domains change |
 | `docs/dev/enduser-coverage-matrix.md` | End-user feature coverage matrix (99-dimension, updated 2026-08-04) — keystone reference like cross-dimensional-catalog | 🔴 P0 — keystone | When feature surface changes |
 | `docs/dev/enduser-capabilities-guide.md` | End-user capabilities & how-to guide — raw-data gathering (30 collectors/29 source types/13 demo domains) + processed-data generation (digest/report/tutorial/presentation/export/translate/CEFR/simplify) with verified CLI + MCP workflows | 🟡 P1 — user guide | When CLI/MCP workflows or capabilities change |
| `docs/dev/required-api-keys.md` | Full catalog of environment variables and API keys required by AutoInfo (referenced by AGENTS.md and README) | 🟡 P1 — reference | When env vars / API keys change |
| `docs/dev/mcp-usage-examples.md` | Full worked MCP tool workflow examples — step-by-step patterns for all common operations (referenced by AGENTS.md) | 🟡 P1 — reference | When MCP workflows change |

### 1.5 Validation Docs (testing and verification plans)

> **Active validation method (2026-08-03+):** the **MCP-native validation toolset** — `list_validation_scenarios` / `run_validation_scenario` tools execute Agent-native validation scenarios through the MCP surface (plus real CLI subprocess and REST HTTP steps). Scenario authoring contract: `docs/dev/validation-scenario-contract.md`. Scenario library: `src/autoinfo/mcp/scenarios/` (57 YAML files covering 142/142 MCP tools, all 28 CLI groups, 8 REST endpoints; 52 functional + 5 regression in `scenarios/regression/`). Executor features: per-step `timeout_seconds`, `recovery_steps` + partial-pass (`min_passing`/`pass_ratio`), per-step execution trace + root-cause report, and recursive-glob auto-load of the regression subdirectory. When the feature surface changes, add/update scenarios in `src/autoinfo/mcp/scenarios/` per the contract — do NOT update archived part files.
>
> **Archived 2026-08-03, deleted 2026-08-04.** The validation plan v2 suite (README, part-01..part-15, 24 YAML scenarios, runner script) was superseded by the MCP-native validation toolset and has been removed. The `tier1-baseline4-report.md` baseline report is retained at `docs/archive/tier1-baseline4-report.md` (see §1.7).

| File | Purpose | Criticality | Update Frequency |
|------|---------|-------------|-----------------|
| `docs/dev/validation-scenario-contract.md` | Scenario authoring contract for the MCP-native validation toolset (schema, semantics, coverage audit, report sections) | 🔴 P0 — active validation | When scenario schema/semantics change |
| `src/autoinfo/mcp/scenarios/*.yaml` | Active Agent-native validation scenario library (57 files: 52 functional + 5 regression in `scenarios/regression/`) | 🔴 P0 — active validation | When feature surface changes |
| `src/autoinfo/mcp/validation.py` | Scenario loader + executor (llm_assert, cli/http steps, unconfigured semantics, per-step timeout, recovery_steps, partial-pass, per-step trace) | 🔴 P0 — active validation | When executor logic changes |
| `docs/dev/specs/end-user-matrix.yaml` + `scripts/coverage_matrix.py` | E8 end-user coverage matrix source + generator (surfaced as 04-MATRIX in validation delivery) | 🟡 P1 — E8 matrix | When end-user feature surface changes |
| `scripts/validation_report.py`, `scripts/validation_delivery.py` | Validation report emitter (Verdicts / Regression failures / Blockers / Per-step trace) + delivery packaging (01-RAW…04-MATRIX, manifest.json with per-file authenticity + D1-D3 gates + UX metrics) | 🟡 P1 — validation tooling | When report/packaging format changes |

### 1.6 Configuration Docs (MCP connection configs)

| File | Purpose | Criticality |
|------|---------|-------------|
| `.cursor/mcp.json` | Cursor MCP connection config | 🟡 P1 |
| `.claude/claude_desktop_config.json` | Claude Desktop MCP connection config | 🟡 P1 |
| `.opencode/mcp.json` | OpenCode MCP connection config | 🟡 P1 |

### 1.7 Archive Docs (superseded or historical)

> Archive docs under `docs/archive/` are historical records. They are retained for reference but are NOT authoritative — the active spec files in `docs/dev/specs/` supersede them. Update only when archiving new docs or when referenced paths change.

| File | Purpose | Criticality | Notes |
|------|---------|-------------|-------|
| `docs/archive/founder-expectations-pre-split.md` | Pre-split backup of original founder-expectations.md (2108 lines before 2026-07-26 restructure) | 🟠 P2 — historical | Superseded by `docs/dev/specs/` |
| `docs/archive/kb-pipeline-reference.md` | KB pipeline reference model (4-tier: Inbox→Raw→Draft→Wiki) | 🟠 P2 — historical | Superseded by `docs/dev/specs/pipeline.md` |
| `docs/archive/end-user-sla.md` | End-user SLA design | 🟠 P2 — historical | Superseded by `docs/dev/specs/delivery.md` |
| `docs/archive/tier1-baseline4-report.md` | Tier 1 baseline validation report (retained from the deleted validation-suite v2) | 🟠 P2 — historical | Superseded by MCP-native validation tools |
| `docs/dev/enduser-coverage-matrix.md` | End-user feature coverage matrix (99-dimension, updated 2026-08-04) — keystone reference | 🔴 P0 — keystone | When feature surface changes |
| `docs/archive/reports/` | Historical report drafts | 🟠 P2 — historical | Non-documentation artifacts |

> **Agent note**: Do NOT update archive docs during normal code changes. Only update when: (1) archiving a new doc (move from active → archive), (2) correcting an archival path reference, or (3) the user explicitly asks you to modify archive content.

---

## 2. Code-to-Doc Dependency Map

When you modify each code module below, the listed documentation files **must** be reviewed and updated.

### 2.1 CLI Module (`src/autoinfo/cli/`)

| Submodule | Docs to Update | What to Update |
|-----------|---------------|----------------|
| Any CLI file | `README.md` | CLI command table (verify 28 groups, add new groups, update descriptions) |
| Any CLI file | `AGENTS.md` | CLI command references in patterns, operating model |
| Any CLI file | `CHANGELOG.md` | Add entry under current version |
| New CLI group | `src/autoinfo/mcp/scenarios/` (per `docs/dev/validation-scenario-contract.md`) | Add scenarios for new command group |
| M6 parity groups (topic-group, import-kb, query-collected, alert-rules, agent-callback, keywords suggest) | `README.md`, `AGENTS.md`, `docs/dev/cli-mcp-rest-parity.md` | 28 CLI groups mirroring MCP tool params; parity matrix |
| CLI flag changes | `README.md` | Update flag examples |

### 2.2 MCP Server (`src/autoinfo/mcp/`)
 
 | Submodule | Docs to Update | What to Update |
 |-----------|---------------|----------------|
| `server.py` — new tool | `AGENTS.md` | Tool Discovery table (category + tool name), tool count (currently 142) |
| `server.py` — new tool | `README.md` | MCP Tools table (category + tool name), tool count |
| `server.py` — new tool | `docs/skills/autoinfo-skill/SKILL.md` | Tool Discovery table, Workflow sections if new workflow |
| `server.py` — new tool | `CHANGELOG.md` | Add entry |
| `server.py` — new tool | `docs/dev/specs/mcp-tools.md` | Add tool to inventory table |
| `server.py` — new param change | `AGENTS.md`, `README.md`, affected skills | Update parameter descriptions |
| `server.py` — cross-domain/domain-less | `AGENTS.md`, `README.md` | Cross-domain search + domain-less collection feature descriptions |
| `server.py` — hard-delete purge flag | `AGENTS.md`, `README.md`, `src/autoinfo/mcp/scenarios/` (per `docs/dev/validation-scenario-contract.md`) | Hard-delete purge flag description |
| `server.py` — process_collection flags | `AGENTS.md`, `README.md` | check_factual/check_translation flag descriptions |
| `errors.py` — new ErrorCode | `src/autoinfo/mcp/scenarios/` (per `docs/dev/validation-scenario-contract.md`) | Add error code to boundary matrix |
| `errors.py` — 3 new ErrorCodes (AuthRequired, RateLimited, SessionExpired) | `docs/dev/specs/quality-gates.md`, `src/autoinfo/mcp/scenarios/` (per `docs/dev/validation-scenario-contract.md`) | Add error codes to error response spec and boundary matrix |
| `agent_callback.py` — SQLite persistence | `AGENTS.md`, `README.md`, `CHANGELOG.md` | Persistent agent callbacks feature description |
| `agent_outbox` (SQLite push outbox) | `AGENTS.md`, `README.md`, `CHANGELOG.md`, `docs/skills/autoinfo-skill/SKILL.md` | Durable outbox enqueues `{event, payload, schema_version, trace_id, product_id}` before delivery; failed rows requeued at process start; never blocks callers |
| `validation.py` — new validation tools | `AGENTS.md`, `README.md`, `docs/skills/autoinfo-skill/SKILL.md`, `CHANGELOG.md`, `docs/dev/specs/mcp-tools.md`, `docs/dev/validation-scenario-contract.md` | Add "Validation" category row with `list_validation_scenarios` / `run_validation_scenario`; update tool count; update scenario library in `src/autoinfo/mcp/scenarios/` |
| Tool count changes | `AGENTS.md`, `README.md`, `CHANGELOG.md`, `docs/dev/specs/mcp-tools.md` | Update "142 tools" / "35 categories" references |

### 2.3 KB Pipeline (`src/autoinfo/kb.py`)

| Change | Docs to Update | What to Update |
|--------|---------------|----------------|
| KB tier logic | `AGENTS.md` | Architecture Rules (KB Pipeline) |
| KB tier logic | `docs/archive/kb-pipeline-reference.md` | Pipeline design details (archived) |
| KB tier logic | `docs/dev/specs/pipeline.md` | KB pipeline section |
| KB tier logic | `README.md` | Status table (KB pipeline row) |
| KB entry schema | `docs/dev/specs/data-models.md` | KB entry schema |
| KB search/index | `README.md`, `AGENTS.md`, `docs/dev/specs/pipeline.md` | Search features description |

### 2.4 REST API (`src/autoinfo/api/`)

| Change | Docs to Update | What to Update |
|--------|---------------|----------------|
| New endpoint | `README.md` | REST API section, API documentation |
| New endpoint | `AGENTS.md` | Common patterns (REST API usage) |
| New endpoint | `CHANGELOG.md` | Add entry |
| Endpoint behavior change | `src/autoinfo/mcp/scenarios/` (per `docs/dev/validation-scenario-contract.md`) | Update scenarios |
| API route handler | `README.md` | Verify port 8741, endpoint list |
| Dashboard UI | `README.md`, `AGENTS.md` | Web UI Dashboard description |

### 2.5 Collectors (`src/autoinfo/collectors/`)

| Change | Docs to Update | What to Update |
|--------|---------------|----------------|
| New collector type | `README.md` | Feature list (multi-source collection), demo domains table |
| New collector type | `CHANGELOG.md` | Add entry |
| New collector type | `src/autoinfo/mcp/scenarios/` (per `docs/dev/validation-scenario-contract.md`) | Add collection scenarios |
| Collector config change | `docs/dev/specs/pipeline.md` | Collection pipeline specification |
| Demo source change | `README.md` | Demo Domains table (sources per domain) |
| New collector handler file | `README.md` | Feature list (multi-source collection), Status table (Collection row — handler count), demo domains table |
| New collector handler file | `CHANGELOG.md` | Add entry |

### 2.6 LLM Extraction (`src/autoinfo/llm.py`)

| Change | Docs to Update | What to Update |
|--------|---------------|----------------|
| Extraction fields | `AGENTS.md` | Common patterns (extraction, domain schema) |
| Extraction fields | `docs/dev/specs/pipeline.md` | LLM extraction specification |
| Model/provider config | `AGENTS.md` | LLM Configuration section |
| Model/provider config | `README.md` | Quick Start (LLM key), LLM Configuration info |
| Extraction behavior | `README.md` | Status table (LLM extraction row) |

### 2.7 Output Generation (`src/autoinfo/output.py`)

| Change | Docs to Update | What to Update |
|--------|---------------|----------------|
| New output format | `README.md` | Feature list, Output/MCP tool tables |
| New output format | `CHANGELOG.md` | Add entry |
| Output template change | `src/autoinfo/mcp/scenarios/` (per `docs/dev/validation-scenario-contract.md`) | Update output scenarios |
| Tool parameter change | `docs/skills/autoinfo-skill/SKILL.md` | Update workflow examples if workflow changes |

### 2.8 Quality Gates (`src/autoinfo/quality.py`)

| Change | Docs to Update | What to Update |
|--------|---------------|----------------|
| Gate logic change | `AGENTS.md` | Quality Gates table (advisory, not blocking) |
| Gate logic change | `README.md` | Quality gates feature description |
| Gate logic change | `src/autoinfo/mcp/scenarios/` (per `docs/dev/validation-scenario-contract.md`) | Update scenarios |
| New gate | `docs/dev/specs/quality-gates.md` | Quality gate specification |
| New gate | `CHANGELOG.md` | Add entry |

### 2.9 Translation QA (`src/autoinfo/translation_qa.py`)

| Change | Docs to Update | What to Update |
|--------|---------------|----------------|
| Pipeline logic | `docs/skills/translator-qa-skill/SKILL.md` | Update workflow steps, thresholds, code examples |
| Pipeline logic | `docs/dev/specs/pipeline.md` | Processing/extraction specification |
| Score calculation | `docs/skills/translator-qa-skill/SKILL.md` | Update score example, weights |
| New feature | `CHANGELOG.md` | Add entry |

### 2.10 Terminology (`src/autoinfo/terminology.py`)

| Change | Docs to Update | What to Update |
|--------|---------------|----------------|
| Loader logic | `docs/skills/translator-qa-skill/SKILL.md` | Update terminology loading example |
| Format change | `docs/dev/specs/pipeline.md` | Terminology/custom extraction specification |

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
| Config change | `src/autoinfo/mcp/scenarios/` (per `docs/dev/validation-scenario-contract.md`) | Update scenarios |

### 2.13 Config (`src/autoinfo/config.py`)

| Change | Docs to Update | What to Update |
|--------|---------------|----------------|
| Config schema | `README.md` | Quick Start, LLM Configuration |
| Config schema | `AGENTS.md` | LLM Configuration section, architecture rules (DO NOT modify directly) |
| Config schema | `docs/dev/founder-expectations.md` | Config system expectations |
| New config field | `src/autoinfo/mcp/scenarios/` (per `docs/dev/validation-scenario-contract.md`) | Update diagnostic scenarios |

### 2.14 Domain Management (`src/autoinfo/cli/domain.py`, MCP tools)

| Change | Docs to Update | What to Update |
|--------|---------------|----------------|
| Domain CRUD logic | `README.md` | Feature list, CLI table, MCP tools table |
| Domain CRUD logic | `AGENTS.md` | Architecture rules, common patterns |
| Domain CRUD logic | `docs/skills/autoinfo-skill/SKILL.md` | Workflow examples (create custom domain) |
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
| New format | `src/autoinfo/mcp/scenarios/` (per `docs/dev/validation-scenario-contract.md`) | Update import scenarios |

### 2.17 Version Bumps / Release

| Change | Docs to Update | What to Update |
|--------|---------------|----------------|
| Version bump in `pyproject.toml` | `README.md` | Version references in Known Limitations |
| Version bump in `pyproject.toml` | `CHANGELOG.md` | Add version header and notes |
| Version bump in `pyproject.toml` | `docs/dev/specs/expectations.md` (status markers), `docs/dev/founder-expectations.md` (top-level index status table) | Version references, status tables |
| Any release prep | All P0 docs | Comprehensive review of all docs for accuracy |

### 2.18 Alerts (`src/autoinfo/alerts.py`)

| Change | Docs to Update | What to Update |
|--------|---------------|----------------|
| Alert rule CRUD/logic | `README.md` | Feature list, MCP tools table (Alert Rules category) |
| Alert rule CRUD/logic | `AGENTS.md` | Status table (agent alerting row), Tool Discovery table |
| Alert rule CRUD/logic | `CHANGELOG.md` | Add entry |
| Alert dispatch logic | `docs/dev/agent-alerting.md` | Update alerting pattern (was polling-based, now config-based) |

### 2.19 Delivery Channel (`src/autoinfo/delivery.py`)

| Change | Docs to Update | What to Update |
|--------|---------------|----------------|
| Channel logic | `README.md` | Feature list (product delivery), Architecture diagram |
| Channel logic | `AGENTS.md` | Quality Gates section (D1-D3), Status table |
| Channel logic | `CHANGELOG.md` | Add entry |
| New channel type | `README.md`, `AGENTS.md` | Update delivery channel listing |
| Channel health check method | `README.md` | Feature list (channel health monitoring), MCP tools table (Monitor category — `get_channel_health`) |
| Channel health check method | `AGENTS.md` | Status table (channel health monitoring row), Tool Discovery table |
| Channel health check method | `CHANGELOG.md` | Add entry |
| Channel health check method | `src/autoinfo/mcp/scenarios/` (per `docs/dev/validation-scenario-contract.md`) | Add `get_channel_health` scenarios |

### 2.20 Consumption Tracking (`src/autoinfo/consumption.py`)

| Change | Docs to Update | What to Update |
|--------|---------------|----------------|
| ConsumptionEvent logic | `README.md` | Feature list (consumption tracking), Status table (consumption tracking row) |
| ConsumptionEvent logic | `AGENTS.md` | Status table (consumption tracking row) |
| ConsumptionEvent logic | `CHANGELOG.md` | Add entry |
| Auto-record on delivery | `src/autoinfo/mcp/scenarios/` (per `docs/dev/validation-scenario-contract.md`) | Add consumption tracking scenarios (Q36d) |
| New store schema | `docs/dev/specs/data-models.md` | ConsumptionEvent schema (if spec updates allowed) |

### 2.21 Notifications (`src/autoinfo/notifications.py`)

| Change | Docs to Update | What to Update |
|--------|---------------|----------------|
| Notification logic | `README.md` | Feature list (automated notifications), Status table (automated notifications row) |
| Notification logic | `AGENTS.md` | Status table (automated notifications row) |
| Notification logic | `CHANGELOG.md` | Add entry |
| Trial-ending / content-ready | `src/autoinfo/mcp/scenarios/` (per `docs/dev/validation-scenario-contract.md`) | Add notification scenarios (Q36d) |

### 2.22 Backup & Restore Scripts (`scripts/backup-db.sh`, `scripts/restore-db.sh`)

| Change | Docs to Update | What to Update |
|--------|---------------|----------------|
| Backup logic | `README.md` | Feature list (SQLite backup), Status table (SQLite backup row) |
| Backup logic | `AGENTS.md` | Status table (SQLite backup row) |
| Backup logic | `CHANGELOG.md` | Add entry |
| Backup target | `Makefile` | `backup` target |
| Backup verification | `src/autoinfo/mcp/scenarios/` (per `docs/dev/validation-scenario-contract.md`) | Add backup verification scenarios (60.16, 60.17) |
| Coverage audit (`scripts/coverage_audit.py`) | `AGENTS.md`, `README.md`, `CHANGELOG.md` | Update validation coverage statistics when MCP tools or scenarios change; includes the "Regression scenarios: N (issues: ...)" metric |

### 2.23 Subscription Tier Gating (`src/autoinfo/billing.py` — `check_access`, `src/autoinfo/models.py` — Subscription fields)

| Change | Docs to Update | What to Update |
|--------|---------------|----------------|
| `check_access` fast path | `README.md` | Feature list (access control), Status table (access control row) |
| `check_access` fast path | `AGENTS.md` | Status table (access control row) |
| `check_access` fast path | `CHANGELOG.md` | Add entry |
| Subscription tier/channels/domains/products fields | `README.md` | Feature list (subscription tiers), Status table (subscription tiers row) |
| Subscription tier/channels/domains/products fields | `AGENTS.md` | Status table (subscription tiers row) |
| Access control verification | `src/autoinfo/mcp/scenarios/` (per `docs/dev/validation-scenario-contract.md`) | Add `check_access` scenario (60.18) |

### 2.24 Delivery Schedule (`src/autoinfo/delivery/scheduler.py`)

| Change | Docs to Update | What to Update |
|--------|---------------|----------------|
| Delivery schedule CRUD | `README.md` | Feature list (delivery schedule automation), MCP tools table (Delivery Schedule category), Status table (delivery schedules row) |
| Delivery schedule CRUD | `AGENTS.md` | Tool Discovery table (Delivery Schedule category), Status table (delivery schedules row), Common Patterns (delivery schedule setup) |
| Delivery schedule CRUD | `CHANGELOG.md` | Add entry |
| Cron integration | `src/autoinfo/mcp/scenarios/` (per `docs/dev/validation-scenario-contract.md`) | Add delivery schedule scenarios |
| Add/remove/list schedules | `docs/dev/specs/delivery.md` | Delivery schedule specification |

### 2.25 Output Generation — Phase 4 Features (`src/autoinfo/output.py`)

| Submodule | Docs to Update | What to Update |
|-----------|---------------|----------------|
| Bundle export (`export_kb format="bundle"`) | `README.md` | Feature list (bundle export), MCP tools table (export_kb bundle format), Status table |
| Bundle export (`export_kb format="bundle"`) | `AGENTS.md` | Tool Discovery table (Output/Export category), Common Patterns (export examples) |
| Bundle export (`export_kb format="bundle"`) | `CHANGELOG.md` | Add entry |
| Cross-domain report/digest (`generate_report`, `generate_digest`, `generate_cross_domain_report` with `domains` parameter) | `README.md` | Feature list (cross-domain reports & digests), MCP tools table (Output category — `generate_cross_domain_report`) |
| Cross-domain report/digest | `AGENTS.md` | Tool Discovery table (Output category), Common Patterns (cross-domain report generation) |
| Cross-domain report/digest | `CHANGELOG.md` | Add entry |
| Report type/audience (`report_type`: industry, competitive, trend, daily-briefing; `target_audience`) | `README.md` | Feature list (specialized report types), MCP tools table (report_type parameter) |
| Report type/audience | `AGENTS.md` | Common Patterns (specialized report generation) |
| Report type/audience | `CHANGELOG.md` | Add entry |
| New output features | `docs/dev/specs/delivery.md` | Output generation specification |

### 2.26 Cross-Document Interface Docs (global references)

These documentation files span multiple code modules and must be checked whenever their related areas change.

| Doc | Related Code Modules | What to Update |
|-----|---------------------|----------------|
| `docs/dev/director-user-guide.md` | `AGENTS.md`, agent interaction model, MCP tool workflows, any CLI change | Role definitions (B1/B2/B3 tables), communication patterns, workflow examples, agent constraints |
| `docs/dev/cross-dimensional-catalog.md` | **Any feature addition or scope change** — catalog maps A1-A7 pipeline × B1/B2/B3 users | Cell status (🟢/🟡/🔴/🟠) per feature, gap-to-spec mapping, execution roadmap, priority matrix |
| `docs/dev/specs/user-lifecycle-definition.md` | End user lifecycle (`delivery.py`, `consumption.py`, `notifications.py`, `billing.py`), user-facing MCP tools | User type definitions, lifecycle stages, cross-user interaction model |
| `docs/dev/specs/ops-runbook.md` | Backup scripts (`scripts/backup-db.sh`, `scripts/restore-db.sh`), monitoring (`diagnose_system`, `get_metrics`), cron health, channel health | Agent quick reference table, MCP tool mappings, human-intervention procedures |
| `docs/dev/specs/multi-tenancy-auth.md` | Auth/MCP server (`server.py` when SSE transport added), `errors.py`, `quality.py` | Auth model specification, rate limiting config, admin dashboard requirements |
| `docs/known-limitations/blocked-sources.md` | Collector evaluation, new source types (`collectors/`), demo domain configuration | Source table with block reason, alternative recommendations, workaround status |

### 2.27 Validation Engine & Regression Flywheel (`src/autoinfo/mcp/validation.py`, `scenarios/`, `scripts/validation_*.py`, `scripts/coverage_matrix.py`)

| Change | Docs to Update | What to Update |
|--------|---------------|----------------|
| New scenario schema field (e.g. `timeout_seconds`, `recovery_steps`, `min_passing`/`pass_ratio`, `regression`/`regression_issue`, `collect_artifacts`, `error_actionable`) | `docs/dev/validation-scenario-contract.md`, this skill (§1.5), `AGENTS.md`, `README.md` | Document field in schema + semantics; bump scenario/tool counts if the surface changed |
| New regression scenario in `scenarios/regression/` | `docs/dev/validation-scenario-contract.md` (inventory), `AGENTS.md`, `README.md`, `CHANGELOG.md` | Add to regression inventory (with `regression_issue`); update "57 scenarios (52 functional + 5 regression)" counts |
| Report/packaging format change (`scripts/validation_report.py`, `scripts/validation_delivery.py`) | `AGENTS.md`, `README.md`, `docs/dev/validation-scenario-contract.md` (report sections) | Update Verdicts / Regression failures / Blockers / Per-step trace + 01-RAW…04-MATRIX packaging + manifest authenticity/D1-D3/UX metrics descriptions |
| E8 matrix change (`scripts/coverage_matrix.py`, `docs/dev/specs/end-user-matrix.yaml`) | `README.md`, `AGENTS.md`, `docs/dev/enduser-coverage-matrix.md` | Update 04-MATRIX / coverage-gaps / Oracle R8 descriptions |
| `.github/ISSUE_TEMPLATE/bug_report.md` regression field | `AGENTS.md`, `README.md` | Keep the mandatory 回归场景 field described in the regression-flywheel row |

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
- CLI Commands table → verify 28 groups, update descriptions
- MCP Tools table → verify tool count (currently 142), update categories/tools
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

#### For Skill Files (`docs/skills/autoinfo-skill/SKILL.md`, `docs/skills/translator-qa-skill/SKILL.md`, `doc-manager-skill/SKILL.md`):
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
| MCP tool count | `README.md`, `AGENTS.md`, `CHANGELOG.md`, `docs/dev/specs/mcp-tools.md` | 142 |
| MCP tool categories | `README.md`, `AGENTS.md`, `CHANGELOG.md`, `docs/dev/specs/mcp-tools.md` | 35 |
| LLM-required tools | `README.md`, `AGENTS.md` | 14 (return `LLM_NOT_CONFIGURED` when unset) |
| CLI command groups | `README.md`, `AGENTS.md`, `CHANGELOG.md` | 28 |
| Source types | `README.md`, `AGENTS.md`, `docs/dev/specs/pipeline.md` | 29 (`VALID_SOURCE_TYPES` frozenset) |
| Collector handlers | `README.md`, `AGENTS.md` | 30 |
| Output product templates | `README.md`, `AGENTS.md`, `CHANGELOG.md` | 8 (digest, report, tutorial, presentation, premium-briefing, column, magazine-digest, enterprise-briefing) |
| Validation scenarios | `README.md`, `AGENTS.md`, `docs/dev/validation-scenario-contract.md`, `src/autoinfo/mcp/scenarios/` | 57 (52 functional + 5 regression in `scenarios/regression/`) |
| Test count | `README.md`, `AGENTS.md` | ~3239 |
| REST API port | `README.md`, `AGENTS.md` | 8741 |
| Demo domains count | `README.md`, `AGENTS.md` | 13 |
| Demo domain names | `README.md` | medical-research, ai-commercial, financial-intelligence, tech-ai-developer, language-learning, online-video, financial-news, online-education, legal-compliance, general-news, gaming, b2b, retail |
| Delivery channels (health-checked) | `README.md`, `AGENTS.md` | 13 (smtp, webhook, rest_api, file_export, discord, telegram, wechat_work, wechat_oa, dingtalk, feishu, rss, social_publish, push) |
| Subscription tiers | `README.md`, `AGENTS.md` | 3 (free, premium, enterprise) |
| Director-user guide line count | `docs/dev/director-user-guide.md` | 756 |
| Cross-dimensional catalog line count | `docs/dev/cross-dimensional-catalog.md` | 780 |
| Ops runbook line count | `docs/dev/specs/ops-runbook.md` | 1027 |

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
   - `docs/skills/autoinfo-skill/SKILL.md` workflows must be achievable with actual MCP tools
   - `docs/skills/translator-qa-skill/SKILL.md` code examples must match actual API signatures
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

**Docs to update**: `README.md` (MCP table), `AGENTS.md` (Tool Discovery table), `CHANGELOG.md`, `docs/skills/autoinfo-skill/SKILL.md` (if it adds a new workflow category)

**Quantities to bump**: MCP tool count (currently 142), category count if new category

**Validation plan**: Add/update MCP validation scenarios in `src/autoinfo/mcp/scenarios/` per `docs/dev/validation-scenario-contract.md` (do NOT update archived part files)

**Verify**: 
```
AGENTS.md MCP tool table → new tool appears in correct category
README.md MCP tool table → matches AGENTS.md exactly
docs/skills/autoinfo-skill/SKILL.md → workflow updated if needed
CHANGELOG.md → "Added: MCP tool 'xxx'"
```

### Scenario B: Adding a new CLI command group

**When**: You add a new CLI module in `src/autoinfo/cli/` and register it in the CLI entry point.

**Docs to update**: `README.md` (CLI table, feature list), `AGENTS.md` (CLI references), `CHANGELOG.md`, `src/autoinfo/mcp/scenarios/` (per `docs/dev/validation-scenario-contract.md`)

**Quantities to bump**: CLI command group count (currently 28)

**Verify**:
```
README.md CLI section → new command group listed with description
AGENTS.md → CLI references updated
CHANGELOG.md → entry under "Changed: CLI expanded from N to N+1 command groups"
MCP validation scenarios → new scenarios cover new command group (add/update in `src/autoinfo/mcp/scenarios/` per `docs/dev/validation-scenario-contract.md`)
```

### Scenario C: Changing KB pipeline behavior

**When**: You modify `src/autoinfo/kb.py`, changing how the 4-tier pipeline works.

**Docs to update**: `AGENTS.md` (Architecture Rules — KB Pipeline), `docs/archive/kb-pipeline-reference.md`, `docs/dev/specs/pipeline.md`, `README.md` (Status table), `CHANGELOG.md`

**Critical**: The KB pipeline rules (01-Raw is sole entry point, agent cannot write to 03-Wiki, 03-Wiki is append-only) are **hard architecture constraints**. If these rules change, the update is a breaking change and must be clearly communicated in ALL docs.

**Verify**:
```
AGENTS.md Architecture Rules → KB Pipeline table matches new behavior
docs/archive/kb-pipeline-reference.md → pipeline diagram and rules updated (archived doc — update only if referenced path changes)
pipeline.md spec → pipeline behavior reflects new design
```

### Scenario D: Version release

**When**: Bumping version in `pyproject.toml` (e.g., 1.4 → 1.5).

**Docs to update**: ALL P0 docs, ALL P1 docs with version references, `CHANGELOG.md`

**Checklist**:
- [ ] `pyproject.toml` — `version = "1.5.0"`
- [ ] `CHANGELOG.md` — new version header with all changes documented
- [ ] `README.md` — Known Limitations version references, feature list updated
- [ ] `AGENTS.md` — Status table, tool counts, CLI counts verified
- [ ] `docs/dev/founder-expectations.md` (index §11), `docs/dev/specs/expectations.md` (status markers) — version references, status tables
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

### Scenario F: Adding a new feature or changing product scope

**When**: You add a user-facing feature, change scope, or implement a previously-deferred capability.

**Docs to update**: `docs/dev/cross-dimensional-catalog.md` (keystone product matrix — mandatory), all P0 docs affected by the change, `CHANGELOG.md`

**Critical**: The cross-dimensional catalog (`docs/dev/cross-dimensional-catalog.md`) is the **keystone product matrix** mapping A1-A7 pipeline stages × B1/B2/B3 user types. Every feature addition or scope change MUST update:
- Cell status (🟢/🟡/🔴/🟠) for affected cells
- Gap-to-spec mapping (§3) if gap status changes
- Priority fix matrix (§4) if priorities shift
- Implementation roadmap (§5) if timeline changes

**Verify**:
```
docs/dev/cross-dimensional-catalog.md → affected cells updated with correct status
README.md → feature list matches new scope
AGENTS.md → status table, tool counts match
CHANGELOG.md → entry added
All P0 docs reviewed for scope references
```

### Scenario G: Updating the Director User Guide

**When**: You change the agent interaction model, add/remove agent constraints, modify the operating model, or change user role definitions.

**Docs to update**: `docs/dev/director-user-guide.md`, `AGENTS.md` (must stay in sync)

**What to update**:
- Role definition tables (B1/B2/B3) if user model changes
- Communication patterns and workflow examples
- Agent constraints (MUST NOT / MUST rules)
- Operating model descriptions

**Verify**:
```
docs/dev/director-user-guide.md → role tables match AGENTS.md
AGENTS.md → agent constraints match director-user-guide.md
agent interaction model → consistent across both docs
```

### Scenario H: Updating operations procedures

**When**: You change backup scripts, monitoring tools, diagnostics, channel health checks, or cron health.

**Docs to update**: `docs/dev/specs/ops-runbook.md`, `README.md` (feature list), `CHANGELOG.md`, `src/autoinfo/mcp/scenarios/` (per `docs/dev/validation-scenario-contract.md`)

**What to update**:
- Agent quick reference table (MCP tool mappings)
- Human-intervention procedures
- Monitoring and health check descriptions

**Verify**:
```
docs/dev/specs/ops-runbook.md → MCP tool references match actual tools
README.md → feature list and status table updated
```

### Scenario I: Adding delivery schedule tools

**When**: You add `add_delivery_schedule`, `list_delivery_schedules`, or `remove_delivery_schedule` MCP tools in `src/autoinfo/delivery/scheduler.py`.

**Docs to update**: `README.md` (MCP tools table — Delivery Schedule category, feature list), `AGENTS.md` (Tool Discovery table, Common Patterns — delivery schedule setup), `CHANGELOG.md`, `docs/dev/specs/delivery.md` (delivery schedule specification)

**Quantities to bump**: MCP tool count (currently 142), category count if new category

**Checklist**:
- [ ] `README.md` — MCP tools table: Delivery Schedule category with tool names
- [ ] `README.md` — Feature list: delivery schedule automation entry
- [ ] `README.md` — Status table: delivery schedules row
- [ ] `AGENTS.md` — Tool Discovery table: Delivery Schedule category
- [ ] `AGENTS.md` — Common Patterns: delivery schedule setup workflow example
- [ ] `AGENTS.md` — Status table: delivery schedules row
- [ ] `CHANGELOG.md` — entry under "Added" for delivery schedule tools
- [ ] `docs/dev/specs/delivery.md` — delivery schedule specification updated
- [ ] MCP validation scenarios — add delivery schedule scenarios in `src/autoinfo/mcp/scenarios/` per `docs/dev/validation-scenario-contract.md`
- [ ] Cross-doc consistency: README.md and AGENTS.md tool counts match

### Scenario J: Adding cross-domain features

**When**: You add cross-domain report/digest generation (e.g., `generate_cross_domain_report`, multi-domain parameters on `generate_report` or `generate_digest`).

**Docs to update**: `README.md` (feature list, MCP tools table — Output category), `AGENTS.md` (Tool Discovery table, Common Patterns — cross-domain report), `CHANGELOG.md`, `docs/dev/specs/delivery.md` (output generation specification)

**Quantities to bump**: MCP tool count if new tool added (currently 142)

**Checklist**:
- [ ] `README.md` — Feature list: cross-domain reports & digests entry
- [ ] `README.md` — MCP tools table: `generate_cross_domain_report` in Output category
- [ ] `README.md` — Status table: verify output generation row reflects cross-domain capability
- [ ] `AGENTS.md` — Tool Discovery table: `generate_cross_domain_report` added
- [ ] `AGENTS.md` — Common Patterns: cross-domain report generation example
- [ ] `CHANGELOG.md` — entry under "Added" for cross-domain report features
- [ ] `docs/dev/specs/delivery.md` — output generation specification updated for cross-domain
- [ ] `docs/dev/cross-dimensional-catalog.md` — cross-domain cells updated if gap status changes
- [ ] Cross-doc consistency: cross-domain feature described consistently across all P0 docs

---

## 6. Project Glossary

Terms that appear across docs and must be used consistently:

| Term | Definition | Used In |
|------|-----------|---------|
| KB pipeline (4-tier) | 4-tier KB pipeline: 01-Raw → 02-Draft → 03-Wiki (00-Inbox deprecated) | AGENTS.md, docs/archive/kb-pipeline-reference.md, docs/dev/specs/pipeline.md |
| G1-G5 | Quality gates: Source authority, Dedup, Relevance, Factual, Translation | AGENTS.md, README.md, src/autoinfo/quality.py |
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
| ConsumptionEvent | Auto-recorded event (view/open/click) on product delivery, SQLite-backed | README.md, consumption.py |
| check_access | Freemium gating fast path (free/premium/enterprise) — G15 | README.md, billing.py |
| Channel health | Per-channel health check (healthy, latency_ms, error) for all 13 delivery channels | README.md, AGENTS.md |
| Cron heartbeat | Per-schedule heartbeat JSON for missed-schedule detection | README.md, cli/cron.py |
| Subscription tiers | Free, Premium, Enterprise — per-tier channels, domains, products, platform limits | README.md, AGENTS.md, models.py |
| Cross-dimensional catalog (CD-NNN) | Keystone product matrix (A1-A7 Pipeline × B1/B2/B3 Users). CD-NNN = Cross-Dimensional sequential gap ID (e.g., CD-001). | docs/dev/cross-dimensional-catalog.md, docs/dev/specs/ |
| Director User (B3) | Human commander who gives high-level intent in NL; agent executes via MCP tools | AGENTS.md, docs/dev/director-user-guide.md, docs/dev/specs/user-lifecycle-definition.md |
| Direct User (B2) | AI agent that translates NL into MCP tool calls; operates AutoInfo on behalf of Director User | AGENTS.md, docs/dev/director-user-guide.md, docs/dev/specs/user-lifecycle-definition.md |
| End User (B1) | Paying customer who consumes knowledge products (digests, reports, data feeds) | docs/dev/director-user-guide.md, docs/dev/specs/user-lifecycle-definition.md, docs/dev/specs/delivery.md |
| Keystone document | The single source of truth for product definition across all dimensions; all other docs derive from it | docs/dev/cross-dimensional-catalog.md |
| Four-tier KB pipeline | 01-Raw (sole entry) → 02-Draft (agent processes) → 03-Wiki (human promotes, append-only) | AGENTS.md, docs/archive/kb-pipeline-reference.md, docs/dev/specs/pipeline.md |

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
