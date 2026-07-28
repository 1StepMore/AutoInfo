# AutoInfo Agent-Oriented Design Gap Analysis

**Date**: 2026-07-28
**Method**: Codebase audit of `src/autoinfo/mcp/server.py`, CLI modules, REST API routes, README, AGENTS.md, and 115 MCP tool catalog across 32 categories.

## Overall Verdict

AutoInfo is **fundamentally agent-oriented** (~85% of features accessible via MCP). However, 16 gaps across 4 severity tiers deviate from the "agent-native" principle declared in `founder-expectations.md §1.2`.

---

## 🔴 Critical Gaps (Core Principle Violations)

### 1. No MCP Tool to Create KB Entries from Scratch

| Interface | What | Evidence |
|-----------|------|----------|
| REST API | `POST /api/v1/entries` creates KB entries from arbitrary POST body | `api/routes.py:210` |
| MCP | ❌ No equivalent. `create_kb_draft` requires existing Raw entry ID. No `ingest_entry` / `store_entry` / `create_entry` tool. | server.py — entire tool list |
| **Impact** | KB pipeline is **move-only** for agents. They can promote Raw→Draft inside the pipeline but cannot inject external data. | — |

### 2. 11 README Features Have Zero MCP Tool Coverage

| # | README Feature | README Line | MCP Tool? | Evidence |
|---|----------------|-------------|-----------|----------|
| 1 | Translation QA pipeline | 25 | ❌ None | `localize_content` translates but does NOT run the 5 QA gates |
| 2 | Immutable audit log | 34 | ❌ **Doc falsely claims MCP tool exists** | `audit.py:183` has `query_audit_log` CLI function; no MCP tool |
| 3 | Structured pipeline logging | 35 | ❌ None | CLI-only. `trace_item` is per-item, not log query. |
| 4 | End-user self-service portal | 33 | ❌ None | CLI-only. `get_preferences` partial coverage. |
| 5 | Consumption tracking | 49 | ❌ None | `ConsumptionEvent` auto-records but no query MCP tool |
| 6 | Automated notifications | 50 | ❌ None | Trial-ending / content-ready notifications not agent-triggerable |
| 7 | Source ToS compliance | 39 | ❌ Partial | No `get_compliance_status`, `get_source_tos` tools |
| 8 | Access control | 48 | ❌ None | `check_access()` internal-only |
| 9 | Cron health monitoring | 52 | ❌ None | CLI-only: `autoinfo cron health` |
| 10 | SQLite backup | 53 | ❌ None | CLI/scripts only: `make backup`, `scripts/backup-db.sh` |
| 11 | Subscription tier CRUD | 47 | ❌ Partial | `get_subscription_status` reads, but no tool to **define** tier limits |

### 3. Job State Is In-Memory Only (Volatile)

```python
# server.py:100,118
_collection_state: dict[str, Any] = {}
_job_state: dict[str, dict[str, Any]] = {}
```

- Agent starts `collect_sources(domain="medical")` → receives `job_id`
- MCP server restarts → **both dicts wiped**
- Agent calls `get_collection_progress(job_id=...)` → handler returns `{"is_complete": True, "status": "not_found"}` at L476 — **silently lies** to the agent that the job completed

### 4. Agent Callbacks Are In-Memory Only (Volatile)

```python
# agent_callback.py:29
_callbacks: dict[str, dict[str, Any]] = {}
```

- `set_agent_callback(url="...", events=["new_digest"])` → OK
- Server restart → **all callbacks lost silently**
- `notify_agent()` (L94) is fire-and-forget — HTTP POST failures are logged but never retried

### 5. Zero Authentication / Rate Limiting

- Search `auth`, `authenticate`, `rate.*limit`, `throttle`, `quota`, `429`, `token.*bucket` in `src/autoinfo/mcp/`: **zero results**
- Any process connecting to MCP stdio has full unauthenticated access
- No "agent identity" concept → no audit trail per-agent, no side-effect isolation

### 6. Inconsistent Error Response Structures

Two formats **coexist**. Agents must parse both:

```python
# Flat old format (server.py:4101)
{"error_code": "NotFound", "message": "...", "actionable": true}

# Envelope new format (server.py:4110)
{"success": false, "error": {"code": "NotFound", "message": "...", "actionable": true}}
```

**10 tools bypass the envelope entirely** (L6961, 6963, 6967, 6971, 6973, 6975, 6977, 6979, 6989, 7009) — they return raw `list[TextContent]` without any structured envelope.

Additionally, `ErrorCode` defines 18 values but has **NO** auth error code, **NO** rate-limit error code, **NO** session/continuity error code.

### 7. 18 CLI Subcommands Have Zero MCP Coverage

| # | CLI Command | File | Impact |
|---|-------------|------|--------|
| 1 | `autoinfo kb promote` | `cli/kb.py:229` | Intentional (human-only gate) |
| 2 | `autoinfo kb wiki-links` | `cli/kb.py:163` | No rebuild tool |
| 3 | `autoinfo topics group add` | `cli/topics.py:175` | No topic group management |
| 4 | `autoinfo topics group remove` | `cli/topics.py:205` | Same |
| 5 | `autoinfo cron install` | `cli/cron.py:814` | System crontab install |
| 6 | `autoinfo cron uninstall` | `cli/cron.py:837` | System crontab remove |
| 7 | `autoinfo cefr batch` | `cli/cefr.py:38` | Only single-text `classify_cefr` exists |
| 8 | `autoinfo email config` | `cli/email.py:130` | No SMTP config tool |
| 9 | `autoinfo knowledge graph export` | `cli/knowledge.py:166` | `query_knowledge_graph` queries but doesn't export to file |
| 10 | `autoinfo clean` | `cli/clean.py:59` | No cache cleanup tool |
| 11 | `autoinfo cost dashboard` | `cli/cost.py:18` | No cost aggregation tool |
| 12 | `autoinfo cost allocation` | `cli/cost.py:108` | No cost allocation tool |
| 13 | `autoinfo enduser create` | `cli/enduser.py:33` | No user profile CRUD |
| 14 | `autoinfo enduser get` | `cli/enduser.py:71` | Same |
| 15 | `autoinfo enduser update` | `cli/enduser.py:89` | Same |
| 16 | `autoinfo enduser delete` | `cli/enduser.py:135` | Same |
| 17 | `autoinfo enduser list` | `cli/enduser.py:153` | Same |
| 18 | `autoinfo audit query` | `cli/audit.py:22` | No audit log query tool |

---

## 🟡 Medium Gaps

### 8. Agent-Native Output Format Only for Digest and Report

| Output Type | Supports `format="agent"`? | Evidence |
|-------------|---------------------------|----------|
| `generate_digest` | ✅ Yes | `output.py:1861` calls `_render_agent_json()` |
| `generate_report` | ✅ Yes | `output.py:2196` builds entries + calls `_render_agent_json()` |
| `generate_tutorial` | ❌ **No** | `output.py:3079` — only allows `"markdown"`. No agent path. |
| `generate_presentation` | ❌ **No** | `output.py:3270` — only markdown/html/mkslides. No agent path. |
| `export_kb` | ❌ **No** | Formats: json, markdown, sqlite, pdf, csv, graphml. No agent. |

### 9. BUG: `generate_tutorial` MCP Schema Over-Promises

```python
# server.py:5302-5306 — MCP schema claims html/json support
"enum": ["markdown", "html", "json"],

# output.py:3079 — Actual implementation only accepts markdown
if format != "markdown":
    raise ValueError(f"Unsupported output format: {format!r}")
```

An agent following the MCP schema gets a runtime error.

### 10. REST API Has 4 Agent-Blind Operations

| REST Endpoint | File:Line | MCP? | Gap |
|---------------|-----------|------|-----|
| `POST /api/v1/entries` | routes.py:210 | ❌ None | **Create-from-scratch** — agents cannot inject content |
| `GET /api/v1/entries` (domain-less) | routes.py:165 | ❌ Partial | MCP needs domain; REST lists cross-domain |
| `DELETE /api/v1/entries/{id}` | routes.py:241 | ❌ Different | REST hard-deletes; MCP only soft-deletes |
| `GET /api/v1/feeds` | routes.py:319 | ❌ None | Simplified RAW feed format |

### 11. `tools_count` Hardcoded and Stale

```python
# server.py:133 — health_check returns
"tools_count": 112,   # ← Stale. Actual: 115.
```

Comment at `list_tools()` L4139 says "Declares 30 available tools" — 85 fewer than actual.

---

## 🟢 Minor Gaps

### 12. `sources add` Limited to 3 Types

MCP `add_source` only supports 3 types (api, rss, web) while CLI supports 6 (+ webhook, email, pdf).

### 13. CLI Help Text Does Not List `"agent"` Format

```bash
autoinfo output digest --help    # Shows "markdown, html, json" — no "agent"
autoinfo output report --help    # Shows "markdown or json" — no "agent"
```

Both CLI commands **do** support `format="agent"`, but the help text doesn't expose it.

### 14. No Domain-Less `collect_sources`

CLI `autoinfo collect --all` collects from all domains. MCP `collect_sources` requires a domain parameter, forcing agents to loop.

### 15. `process_collection` Does Not Expose Gate Flags

CLI `autoinfo process --check-factual --check-translation` controls G4/G5 gating. MCP `process_collection` has no such parameters.

### 16. No Tool Count Self-Discovery

Agents cannot ask the MCP server to report its tool count. `health_check`'s hardcoded `112` is untrustworthy. Agents must count `tools/list` responses or trust stale metadata.

---

## ✅ By Design (Not Gaps)

| CLI Command | MCP Equivalent | Reason |
|-------------|----------------|--------|
| `autoinfo kb promote` | ❌ None | Intentional — human-only Draft→Wiki gate |
| `autoinfo init` | `init_project` ✅ | Different name, same function |
| `autoinfo doctor` | `diagnose_system` ✅ | AGENTS.md says "Use MCP tool instead" |
| Web UI Dashboard | Human-only UI | Underlying data available via MCP |
| Portal HTML pages | Human-only UI | Underlying data available via MCP |
| Stripe webhook | Inbound HTTP | Not an agent operation (triggered by Stripe) |

---

# Appendix B: Documentation Audit — Which Docs Are NOT 100% Agent-Oriented

**Date**: 2026-07-28  
**Method**: Read all 47 `*.md` files under `docs/`. Classified by: (a) primary interface referenced — MCP vs CLI vs none, (b) assumed reader — agent vs human, (c) presence of agent-specific workflow instructions.

## Class A: 100% Agent-Oriented ✅

These docs are written for agents, reference MCP tools as primary interface, and include agent workflow patterns:

| Doc | Why It's Agent-Oriented |
|-----|------------------------|
| `docs/dev/director-user-guide.md` (756 lines) | "You direct. The agent executes." MCP tools throughout. B1/B2/B3 model with agent as primary operator (B2). |
| `docs/dev/founder-expectations.md` (471 lines) | §1.2: "Agent-native" as design principle. §1.3: B2 Direct User = agent. "All capabilities exposed as MCP tools first. CLI is fallback." |
| `docs/dev/cross-dimensional-catalog.md` (765 lines) | B2 Direct User as primary execution layer. MCP tools referenced in every B2 cell. CD matrix evaluates tool coverage per pipeline stage. |
| `docs/dev/agent-alerting.md` (129 lines) | "Agents should proactively monitor... Agent polls, agent decides, agent reports." Full MCP tool reference with input/output tables. |
| `docs/dev/specs/mcp-tools.md` (45 lines) | Pure MCP catalog — 114 tools across 32 categories. No CLI mentioned. |
| `docs/dev/specs/expectations.md` (1186 lines) | Explicit "Agent perspective" column in F01-F04 tables. References B2/B3 user model throughout. |
| `docs/dev/specs/user-lifecycle-definition.md` (453 lines) | §3: "B2 Direct User (AI Agent) — Interacts via: MCP tools (114 tools across 32 categories)" |
| `docs/dev/specs/quality-gates.md` (120 lines) | References `process_collection()`, `generate_digest()` as MCP tool triggers. Pipeline as agent execution flow. |
| `docs/dev/specs/operations.md` (909 lines) | §1.4 lists all cost MCP tools with input/output. Agent-facing. |
| `docs/skills/autoinfo-skill/SKILL.md` (305 lines) | Agent operating AutoInfo via MCP. "You translate human intent into MCP tool calls." |
| `docs/skills/translator-qa-skill/SKILL.md` (369 lines) | Agent translation workflow via MCP tools (`localize_content`, LLM config). |
| `docs/autoinfo-validation-master-plan/*` (16 files) | README says "Agent-Oriented". Self-Executing Assert Pattern designed for agents. "How to Use This Plan (Agent-Oriented)". |

## Class B: NOT 100% Agent-Oriented 🟡/🔴

### Level 1 — Spec/Reference docs with human-oriented framing 🟡

These are spec documents that contain correct technical information but present it through a human-CLI lens rather than an MCP-tool lens:

| Doc | Why NOT 100% |
|-----|-------------|
| **`docs/dev/specs/pipeline.md`** (480 lines) | **CLI-first flow diagrams.** Two-Phase Flow (§1.3) shows `autoinfo collect --domain X` and `autoinfo process --domain X` as the primary interface. No MCP tool equivalents in the core pipeline visualization. An agent reading this sees CLI commands, not `collect_sources()` / `process_collection()` tool calls. |
| **`docs/dev/specs/delivery.md`** (1211 lines) | **Ambiguous "User" — could be human.** §1.2: "User calls generate_<product>(domain, topic, period, template, output_format)" — this describes a Python function call, not an MCP tool. No mention of how an agent accesses these capabilities. The delivery pipeline diagram doesn't reference MCP. |

### Level 2 — Human-only infrastructure/sysadmin docs 🔴

| Doc | Why NOT 100% |
|-----|-------------|
| **`docs/dev/specs/ops-runbook.md`** (1003 lines) | **Full sysadmin manual — zero agent consideration.** Bash scripts (`autoinfo-backup`), crontab entries (`/etc/cron.d/autoinfo-backup`), manual SQLite restore procedures, DR plans. All assumes a human sysadmin running shell commands. No MCP tools for backup/restore/DR exist (confirmed gap #10 in main analysis). |
| **`docs/dev/specs/multi-tenancy-auth.md`** (714 lines) | **Human-facing admin dashboard spec.** §4 describes admin dashboard UI (charts, tables, human navigation). Auth/rate-limiting are REST-API-oriented. Status is "Never Designed" — but even the spec frames everything for human administrators, not agents. |
| **`docs/dev/specs/market-positioning.md`** (387 lines) | **Pure business doc.** Competitive landscape, pricing, target personas. Zero mention of MCP, agents, or tool interfaces. Written for a human product manager. |

### Level 3 — Archived docs (historical/audit, not agent-facing) 🔴

| Doc | Why NOT 100% |
|-----|-------------|
| `docs/archive/founder-expectations-pre-split.md` (2112 lines) | Pre-split historical version. Human-readable founder vision, not agent-oriented. |
| `docs/archive/reality-assessment.md` (262 lines) | Human-facing assessment. CLI commands as evidence. Written for human review. |
| `docs/archive/comprehensive-gap-audit.md` (1076 lines) | Human-facing audit report. Written by Sisyphus for human consumption. |
| `docs/archive/consumer-output-gaps.md` (266 lines) | Human-facing gap analysis with market research. For product/business stakeholders. |
| `docs/archive/implementation-gaps.md` (195 lines) | Human-facing implementation gap audit. |
| `docs/archive/gap-analysis-v1.6.md` (232 lines) | Deprecated gap analysis. Human-facing. |
| `docs/archive/kb-pipeline-reference.md` (249 lines) | Chinese-language historical reference about Obsidian KB workflow. Pre-dates AutoInfo MCP architecture. |
| `docs/archive/user-authorization-matrix.md` | Archived auth matrix. |
| `docs/archive/end-user-sla.md` | Archived SLA document. |
| `docs/archive/end-user-onboarding.md` | Archived onboarding doc. |
| `docs/archive/autoinfo-validation-master-plan.md` | Old validation plan (v1, deprecated). For human testers. |
| `docs/archive/reports/global-content-paid-research-report-trae.md` | Market research report. |
| `docs/archive/reports/综合报告-资讯付费与AI触达研究.md` | Market research report (Chinese). |
| `docs/archive/reports/资讯付费调研报告-2026-hermes.md` | Market research report (Chinese). |

### Level 4 — Neutral reference (no orientation) ⚪

| Doc | Why Neutral |
|-----|-------------|
| **`docs/dev/specs/data-models.md`** (635 lines) | Pure schema definitions — Python dataclasses, YAML frontmatter, SQLite schemas. No agent or human orientation. Could be consumed by either. |

## Summary

| Category | Agent-Oriented ✅ | Not 100% 🟡/🔴 | Neutral ⚪ |
|----------|:-:|:-:|:-:|
| `docs/dev/` (4 files) | 4 | — | — |
| `docs/dev/specs/` (11 files) | 5 | 5 (pipeline, delivery, ops-runbook, multi-tenancy-auth, market-positioning) | 1 (data-models) |
| `docs/skills/` (2 files) | 2 | — | — |
| `docs/archive/` (14 files) | — | 14 | — |
| `docs/autoinfo-validation-master-plan/` (16 files) | 16 | — | — |
| **Total (47 files)** | **27** | **19** | **1** |

**Bottom line**: 27/47 docs (57%) are agent-oriented. 19/47 (40%) are not — but 14 of those are archive docs (historical, knowningly outdated). The 5 non-archive docs that need remediation are:

1. 🔴 `docs/dev/specs/ops-runbook.md` — Add MCP tool interface (backup/restore/DR tools)
2. 🟡 `docs/dev/specs/pipeline.md` — Add MCP tool aliases to flow diagrams
3. 🟡 `docs/dev/specs/delivery.md` — Clarify "User" → agent/MCP tool interface
4. 🔴 `docs/dev/specs/multi-tenancy-auth.md` — Add agent identity/auth perspective
5. 🔴 `docs/dev/specs/market-positioning.md` — Add agent-oriented value proposition