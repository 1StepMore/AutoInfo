# AutoInfo Launch Validation Framework (D1-D5)

> **Keystone validation document.** The reusable pre-launch validation TEMPLATE for AutoInfo. This document is the test specification, written FIRST. Other agents collect evidence in parallel that is graded against it. Each version reuses this template unchanged and records its own evidence in a versioned run report.
>
> **Purpose:** Define what "launch-ready" means for a given version across five dimensions: D1 data-layer definitions, D2 authenticity, D3 readability (human and agent tracks), D4 requirement awareness at onboarding, D5 validation meta-coverage. Provide the grading rules, binary acceptance criteria, evidence requirements, the SUSPECT table, and the re-runnable evidence catalog.
>
> **Status:** Template (living document). Ratified for reuse across versions. Per-version evidence lives in the run report, never in this template.
>
> **Date:** 2026-08-05
>
> **Change process:** Any change to a dimension definition, an acceptance criterion, a grading rule, or the SUSPECT table requires director-user (B3) approval. New suspects are appended; a suspect is only cleared with written B3 sign-off and the investigation recorded in §2. Per-version evidence is appended to the run report, not to this template.
>
> **Relationship to other docs:**
> - `docs/dev/validation-scenario-contract.md` defines how scenarios are authored and executed (real process execution, never mocked). This framework defines what is graded; the contract defines how evidence is produced.
> - `docs/dev/cross-dimensional-catalog.md` is the keystone product matrix. D1 maps its A4 product types to the two data layers.
> - `docs/dev/specs/user-lifecycle-definition.md` defines B1/B2/B3 and the escalation principle. D4 and D5 grade the requirement-awareness and agent-as-tester responsibilities against it.
> - `src/autoinfo/output/__init__.py` and `docs/dev/specs/delivery.md` define the RAW/PROCESSED product split.
> - `docs/dev/required-api-keys.md` is the requirement inventory that D4 grades against.
> - `README.md` and `AGENTS.md` carry the feature baseline numbers (141 tools, 28 CLI groups, 13 channels, output formats) that D5 counts.

## Table of Contents

1. [§0 How to Use and Per-Version Reuse](#0-how-to-use-and-per-version-reuse)
2. [§1 D1 Data-Layer Definitions](#1-d1-data-layer-definitions)
3. [§2 D2 Authenticity](#2-d2-authenticity)
4. [§3 D3 Readability Dual-Track](#3-d3-readability-dual-track)
5. [§4 D4 Requirement Awareness at Onboarding and Setup](#4-d4-requirement-awareness-at-onboarding-and-setup)
6. [§5 D5 Validation Meta-Dimension](#5-d5-validation-meta-dimension)
7. [§6 Grading and Report Template](#6-grading-and-report-template)
8. [Appendix: Evidence Catalog](#appendix-evidence-catalog)

---

## §0 How to Use and Per-Version Reuse

### When to run

- **Pre-launch**, for every version that is being shipped to end users.
- **Pre-major-release**, always. A major release runs all five dimensions with the full evidence catalog. A minor or patch release runs the deltas: changed modules keep their dimension evidence, the SUSPECT table is re-scanned, and D5 coverage is re-audited.

### Who runs what

- **B2 (agent-as-tester)** executes the evidence catalog, collects artifacts, fills the evidence tables, and drafts the verdicts. The agent is the operator and the test harness.
- **B3 (human director)** reviews the run report, adjudicates RISK verdicts, and signs off on open SUSPECT items. B3 intervenes only on critical errors or blocked evidence (for example an expired source key that prevents a real-fetch proof).
- **B1-responsible angle**: every dimension is also graded from the perspective of the paying end user (B1). D3 has an explicit human track, D4 checks whether missing requirements reach the right human decision maker, and D5(c) grades whether the validation plan itself covers the B1 consumption path, not just B2 operations.

### Baseline rules

- **No-keys baseline rule.** Every version run starts with NO BYOK keys set, producing the honest baseline profile (current known profile: 37 passed / 0 failed / 10 unconfigured at 47 scenarios; the 10 env-gated scenarios need `AUTOINFO_LLM_API_KEY` (9) and `FRED_API_KEY` + `FINNHUB_API_KEY` (1)). Record the no-keys profile first, then set keys and re-run. A scenario that reports `unconfigured` without keys is expected, but `unconfigured` is never a pass (see grading legend).
- **Real-surface evidence rule.** Evidence must come from the real MCP surface (stdio), real CLI subprocesses, or real REST HTTP calls. Unit-test output, mocked stores, and seeded fixtures are not evidence.
- **No-mock rule.** The runtime paths must be free of simulated data. Anything that looks like a mock, placeholder, fixture, or sample in a runtime path must be recorded on the SUSPECT table in §2 and investigated. Tests/ and docs/ are excluded from the scan; runtime code is not.

### Grading legend

| Grade | Meaning |
|-------|---------|
| **PASS** | All binary acceptance criteria in the dimension hold, with real evidence on record. |
| **FAIL** | At least one binary acceptance criterion is false. |
| **RISK** | Criteria hold, but evidence is partial, indirect, or time-limited; or a SUSPECT item is open. |
| **`unconfigured`** | A check could not run because a required key is missing. Recorded as a known limit, NEVER a pass. It is re-run once the key is configured. |

### Deliverable pointer

Each version produces one run report built from the §6 skeleton, stored alongside this template, for example `docs/dev/validation-reports/launch-validation-<version>.md` (created per version). The report contains the per-dimension verdict tables, the blocker list, the executive summary, and the pointer to the raw evidence artifacts. This template itself is never overwritten by a run.

---

## §1 D1 Data-Layer Definitions

### Definition (director's definition, binding)

- **Raw data** = the original data collected from channels: papers, news, and other original reports. It is the unmodified collected material, exactly as fetched from the source.
- **Process data** = data derived from raw: commercially-safe processed versions of raw data (raw that is not commercially usable gets processed), daily briefings, reports, and analysis digests.

The mapping to shipped product types is one-to-one:

| Data layer | Shipped product types | Variants / formats |
|------------|----------------------|--------------------|
| **Raw data** | RAW product | `variants: ["api_feed", "webhook", "bulk_export"]` (RAW product variants, E11, `README.md`) |
| **Process data** | PROCESSED product: digest, report, tutorial, presentation, alert | digest 7 formats (markdown/html/json/agent/audio/epub/audiobook), report 8 (incl. video; note: video is missing from the MCP schema enum at `src/autoinfo/mcp/server.py:7586-7589`), tutorial 2 (markdown/agent), presentation 4 (markdown/html/mkslides/agent) |

Citations: the product split is enforced in `src/autoinfo/output/__init__.py` (`product_type` of `"PROCESSED"` or `"RAW"`, RAW skips all delivery gates, see `src/autoinfo/output/__init__.py:191,2317,2360-2362,2765,2816-2818`); the user consumption model (B1) is defined in `docs/dev/specs/user-lifecycle-definition.md`.

### Binary acceptance criteria

1. **Every shipped product type maps to exactly one data layer.** A product is RAW or PROCESSED, never both and never neither. Verify per product: list every product visible via `list_products` / `get_product` and assert each carries a single `product_type` consistent with its content.
2. **Every process artifact traces to >= 1 raw entry.** A digest, report, tutorial, or presentation must cite at least one underlying 01-Raw entry through the provenance path 01-Raw → 02-Draft → 03-Wiki. An artifact whose content cannot be traced to a raw entry fails.
3. **B1 `content_preference` (`raw_only` / `processed_only` / `both`) is honored.** The preference is set via `update_preferences` and read via `get_preferences` (End User tool category); the delivered product set must respect it. Verify a `raw_only` end user never receives a PROCESSED artifact they did not opt into, and a `processed_only` end user never receives RAW feeds they did not opt into.

### Evidence requirements

- `list_products` and `get_product` reads showing each product type and its data-layer classification, with real output attached to the report.
- Provenance walk for at least one process artifact: trace its content from the artifact back through a KB tier (01-Raw → 02-Draft → 03-Wiki) to the collected raw item, using `get_kb_entry` and the KB tier listing (`list_kb_tier`).
- Preference test: create or update a B1 profile with each of the three preference values and show the delivered product set honors it.

### Per-version reuse note

This section is **reuse**-stable across versions: the definition, the acceptance criteria, and the evidence requirements do not change. Per version you only re-run the evidence: list the shipped products, trace a sample artifact, re-test the three preference values. If a new product type or a new data layer appears, that is a template-level change requiring B3 approval, not a per-version evidence change.

---

## §2 D2 Authenticity

### Principle

**All raw AND process data must be genuinely collectible and producible. Nothing is simulated.** Raw data must be fetchable through real network calls from real configured sources. Process data must be producible from real raw data through the real pipeline. A demo domain is a configuration, not a fake data store.

### Evidence types

**(a) Real-fetch proof.** Collectors make real network calls; there are no seeded stores in the runtime path. Demo domains are config-only, defined under `src/autoinfo/data/domains/` (13 domains, each a directory of source/topic config), and produce data only by actually fetching. Evidence: run `collect_sources` against a real configured source and attach the raw JSON cache plus the collection log; assert the items carry real `source_url`, `source_type`, and `source_platform`.

**(b) No-simulated-layer scan.** Runtime paths (`src/`, excluding `tests/` and docs) must be free of mock/fixture/sample markers: no seeded fixtures, no hardcoded fake data served as real output, no simulation shims. Evidence: a grep scan of runtime paths for markers such as `mock`, `fixture`, `sample`, `placeholder`, `example.com`, `sk_test` and a written disposition for every hit (real usage vs suspect).

**(c) SUSPECT-list handling.** Every hit that is not obviously benign is entered in the table below with an investigation and a verdict. The table is PRE-SEEDED with 4 confirmed suspects from the current codebase. A suspect is not automatically a FAIL: it gets a verdict of PASS (benign, documented), FAIL (violates authenticity), or RISK (open, needs B3 adjudication).

### SUSPECT table template (pre-seeded with 4 confirmed suspects)

| # | Item | Source reference | Investigation | Verdict | Risk |
|---|------|------------------|---------------|---------|------|
| S1 | Stripe billing defaults to stripe-mock when no `STRIPE_API_KEY` is set, connecting to `http://localhost:12111` with the fake key `sk_test_mock` | `src/autoinfo/billing.py:3-12,146-166` | Confirm whether a product billing path with no Stripe key silently produces fake charges, or fails closed with a clear error. If billing is exercised only in dev with an explicit mock base URL, the default mode must still never present fake charges as real | open (investigate) | medium |
| S2 | Sitemap export hardcodes `https://example.com` as the index/base URL when no `--base-url` is passed | `src/autoinfo/output/seo.py:19`, `src/autoinfo/output/__init__.py:1069`, `src/autoinfo/cli/output.py:310-330` | Confirm whether the shipped sitemap carries `example.com` URLs (a real-product defect: wrong host in delivered artifact) or whether production callers always pass a real base URL. If a shipped sitemap can contain `example.com`, this is a FAIL on real producibility | open (investigate) | high |
| S3 | Video output generates placeholder slide images when Pillow is missing | `src/autoinfo/output/video.py:109-110,176-193` (presentation-only path) | Confirm whether the placeholder path is reachable in a shipped video product (then the artifact contains fake slides) or only used as a graceful degradation with a logged warning. Presentation-only scope limits blast radius | open (investigate) | low |
| S4 | Validation scenarios write real KB entries with an `example.com` `source_url` when run | `src/autoinfo/mcp/scenarios/kb-draft.yaml:13`; engine `src/autoinfo/mcp/validation.py:30` ("real process execution, never mocked") | Confirm whether the scenario cleans up its KB writes after execution, and whether an `example.com` URL pollutes the real KB tier (01-Raw is the sole entry point; a simulated URL in real KB data violates D1 criterion 2). If cleanup is missing, scenario runs contaminate the real store | open (investigate) | medium |

### Binary acceptance criteria per suspect

| # | Criterion |
|---|-----------|
| S1 | PASS only if: with no `STRIPE_API_KEY`, billing either (a) fails with an explicit configuration error before any fake charge can be recorded, or (b) connects only to an explicitly configured mock base URL that is never presented as a real charge path in production. Any path that silently records `sk_test_mock` charges as real = FAIL. |
| S2 | PASS only if no shipped sitemap can contain `https://example.com`: either production callers always pass a real base URL, or the default is rejected. A shipped artifact containing `example.com` = FAIL. |
| S3 | PASS only if the placeholder image path cannot appear in a delivered video artifact, or the artifact is clearly flagged and the warning is logged. Placeholder slides delivered as a real video = FAIL. |
| S4 | PASS only if running the full scenario library leaves the real KB tiers clean (no `example.com` entries, no orphaned raw/draft writes) or the scenario cleans up after itself. Persistent contamination of the real store = FAIL. |

### Per-version reuse note

The SUSPECT table is the **reuse**-stable core of D2: the four rows above stay open for every version until each is investigated and given a written verdict with B3 sign-off. Per version you re-run evidence types (a) and (b), and you append NEW suspects found by the no-simulated-layer scan. Clearing an old suspect is a template-level event (B3 sign-off); adding a new one is routine per-version work.

---

## §3 D3 Readability Dual-Track

### Principle

Content must be readable on TWO tracks, because there are two end users:

- **(a) Human track:** real raw-based content with a real reading experience and real formatting for humans. This matters most for process data, which is the refined information service (digests, reports, briefings) a paying human consumes.
- **(b) Agent track:** BOTH raw and process data must be consumable by an agent, because in the AutoInfo operating model the agent is the actual end user of the MCP surface. An agent must be able to read, parse, and re-use raw items and process artifacts without human transcription.

### Evidence requirements

**Human track**

- Rendered artifacts: generate a digest and a report in markdown, html, and pdf, attach the rendered files, and note which LLM/template produced them.
- Template quality: read the Jinja2 templates referenced by the output generators and confirm the structure (headings, citations, tables, attribution per source ToS) renders cleanly.
- Empty-KB vs populated variance: generate the same artifact on an empty KB (no raw entries) and on a populated KB; the empty-KB artifact must be an honest "no content" state, not a fabricated page, and the populated one must show real content.

**Agent track**

- `format="agent"` output: generate digest/tutorial/presentation/export agent JSON-LD and validate each against its schema in `docs/schemas/` (`knowledge-digest-v1.json`, `knowledge-tutorial-v1.json`, `knowledge-presentation-v1.json`, `knowledge-base-export-v1.json`). The `@context` and `@type` are const-pinned in the JSON Schema (`docs/schemas/*-v1.json`), so validation must pass without modification.
- Agent-native output inventory: enumerate which tools accept `format="agent"` (digest, report, tutorial, presentation, export) and confirm each returns the JSON-LD envelope.
- Error envelope: when the LLM is unconfigured, the 14 LLM-required tools return the `LLM_NOT_CONFIGURED` error code (`src/autoinfo/mcp/server.py:9695`, dispatch gate at `server.py:9860`), so an agent always gets a parseable, actionable failure instead of a raw auth error.

### Acceptance criteria per track per data layer

| Track | Data layer | Acceptance criteria |
|-------|-----------|---------------------|
| Human | Raw | Raw items are presented as readable records with complete source provenance (`source_url`, `source_type`, `source_platform`); a human can read a raw item directly from the KB tier |
| Human | Process | Process artifacts (digest/report/briefing) render cleanly in markdown/html/pdf with real content from real raw entries; empty-KB state is honest, never fabricated |
| Agent | Raw | Raw items are machine-readable: structured fields parse without loss, and agent-format exports of raw KB data validate against the JSON-LD schema |
| Agent | Process | Agent-format process artifacts validate against their schemas with `@context`/`@type` const-pinned; an agent can consume digest/tutorial/presentation/export JSON-LD directly |

### Per-version reuse note

The dual-track definition and the 4-cell criteria matrix are **reuse**-stable. Per version you re-generate the evidence: render the artifacts, run the empty-vs-populated variance check, re-validate the agent JSON-LD against the const-pinned schemas. When the output format inventory changes (a format is added or dropped), re-run the inventory count; format counts are version evidence, the track structure is not.

---

## §4 D4 Requirement Awareness at Onboarding and Setup

### Requirement inventory

Every requirement the system needs to operate, cataloged in `docs/dev/required-api-keys.md` (31 `AUTOINFO_*` environment variables, plus provider keys):

| Requirement class | Examples | Where documented |
|-------------------|----------|------------------|
| LLM key | `AUTOINFO_LLM_API_KEY` | `docs/dev/required-api-keys.md`, `configure_llm` tool |
| Platform keys per source type | e.g. `AUTOINFO_AP_API_KEY` (AP API), `FRED_API_KEY` + `FINNHUB_API_KEY` (financial), YouTube, Spotify, NYT, etc. | `docs/dev/required-api-keys.md`; collectors warn at collect time (e.g. AP API logs "AP API key not configured (set AUTOINFO_AP_API_KEY)") |
| Delivery tokens | SMTP credentials and per-channel tokens (webhook, telegram, discord, etc.) | `docs/dev/required-api-keys.md`, `email_config` tool |

### Detection capability (current state)

- **At onboarding:** `init_project` (`src/autoinfo/mcp/server.py:3325`) returns a FIXED 3-item `next_steps` (configure_llm / collect_sources / process_collection, `server.py:3406,3442`). There is NO platform-key prompt: onboarding surfaces the LLM key but not per-source keys or delivery tokens.
- **At runtime:** `diagnose_system` phase detection (`_detect_phase`, `src/autoinfo/mcp/server.py:273-307`) checks ONLY the LLM key and the source count, yielding phases `uninitialized` / `llm_unconfigured` / `no_sources` / `ready_to_collect` / `operational`. Missing platform keys do not change the phase.
- **Via error envelope:** the 14 LLM-required tools return `LLM_NOT_CONFIGURED` when no LLM key is set (dispatch gate `src/autoinfo/mcp/server.py:9860`). Platform keys surface only as collect-time log warnings, which is detection at collect time, not at onboarding.

### The prompt-target question (THE question for this dimension)

**WHO is prompted when a requirement is missing: the end user (B2 agent-as-user) or the director user (B3 human behind the agent)?**

The user model in `docs/dev/specs/user-lifecycle-definition.md` is: B1 End User (including the "Agent delegate" type), B2 Direct User = the AI agent operator who drives the 141 MCP tools, B3 Director = the human manager who intervenes ONLY on critical errors (e.g. a source API key expired, disk full). Escalation principle: B2 operates, B3 intervenes on exceptions.

By that principle, a missing requirement is a B3 obligation when it is a key only the human can supply (BYOK), but the error currently surfaces only to the B2 agent. The assessment method below records, per requirement, whether the detection reaches the actor who can fix it.

### Detection matrix (current-state assessment method)

| Requirement | Detected at onboarding | Detected at collect time | Doc-only | Prompt-target (current) | Correct prompt-target (per B3-intervenes-on-exceptions) | Gap |
|-------------|:---:|:---:|:---:|:---:|:---:|:---:|
| LLM key (`AUTOINFO_LLM_API_KEY`) | yes (`init_project` next_steps, phase `llm_unconfigured`) | yes (LLM tools return `LLM_NOT_CONFIGURED`) | yes | B2 (error envelope) | B2 detects, B3 supplies the key | B3 has no direct onboarding prompt; escalation is implicit |
| Platform keys (per source type, e.g. AP, FRED/Finnhub) | no | partial (collect-time log warning) | yes | B2 (log line) | B3 (only B3 owns the API key contract) | No onboarding prompt; collect-time warning only |
| Delivery tokens (SMTP/channel) | no | no | yes | none (silent until delivery fails) | B3 | Undetected until a delivery attempt fails |

**How to classify completeness:** a requirement is "fully detected" only if it has at least one detection surface that fires BEFORE the point of failure and reaches the correct prompt-target. "Correct" means: B3 is prompted (directly or via B2 escalation) for anything only the human can supply, and B2 is prompted for anything the agent can self-heal. A requirement that is doc-only is detected, but at the weakest level (the agent must read the doc to learn it). A requirement with no surface at all is undetected.

### Binary acceptance criteria

1. Every requirement in the inventory has at least one detection surface (onboarding, collect-time, runtime error envelope, or doc). Zero is FAIL.
2. No missing requirement is silently passed: for each requirement, the absence of the key produces either a clear error (`LLM_NOT_CONFIGURED` style), an `unconfigured` scenario result, or an explicit log warning. Silent success with a missing requirement is FAIL.
3. The prompt-target is recorded per requirement and is consistent with the escalation principle: any requirement that only the B3 human can satisfy (source API keys, SMTP credentials) must have a path that reaches B3, not only a log line a B2 agent may or may not surface.
4. `init_project` next_steps reflect the requirement state of the project: if platform keys are missing for configured sources, the onboarding output either lists them or points to `docs/dev/required-api-keys.md`.

### Per-version reuse note

The requirement inventory and the detection matrix are **reuse**-stable in structure: per version you re-populate the matrix (which requirements exist, which surfaces fire, who is prompted) and re-check the four criteria. The current-state findings above are version evidence, not permanent facts: the matrix is the tool for measuring whether a version improved detection (for example, if onboarding starts prompting for platform keys, that cell flips to "yes"). The prompt-target question stays open until the matrix shows every B3-owned requirement reaching B3.

---

## §5 D5 Validation Meta-Dimension

Three sub-angles grade the validation system itself.

### (a) Agent-as-tester discovery

Can an agent enumerate coverage and features without a human? Evidence:

- `list_validation_scenarios` MCP tool (`src/autoinfo/mcp/server.py:5478`) returns the 47-scenario inventory with names and categories.
- `get_tool_count` returns the live MCP tool count (141, self-discovering).
- MCP `tools/list` (protocol-level) returns the full tool catalog.
- `scripts/coverage_audit.py` cross-checks the 141 tool declarations (`Tool(name=...)` in `src/autoinfo/mcp/server.py:6232`) against `kind: mcp` steps in the scenario library and reports covered vs missing.
- `run_validation_scenario` (`server.py:5485`, engine `run_scenario` at `src/autoinfo/mcp/validation.py:510`) executes any scenario for a fresh verdict.

### (b) Validation-plan coverage

Coverage matrix template. Rows are the feature inventory; columns are scenario coverage:

| Feature inventory row | Inventory source | Coverage target | Covered by scenario(s) | Coverage % | Verdict |
|----------------------|------------------|-----------------|------------------------|:---:|:---:|
| MCP tools (141) | `list_tools()` `src/autoinfo/mcp/server.py:6232` | 141/141 | all tools appear as `kind: mcp` steps | (per version) | |
| CLI command groups (28) | `src/autoinfo/cli/__init__.py` | 28/28 | cli-core, cli-content, cli-ops, cli-extra, cli-llm scenarios | | |
| REST endpoints (8) | REST API server | 8/8 | rest-api scenario | | |
| Output formats | digest 7 / report 8 / tutorial 2 / presentation 4 / export 12 | each format exercised | output-* scenarios | | |
| Delivery channels (13) | `_CHANNEL_REGISTRY` `src/autoinfo/delivery/__init__.py:652` | 13/13 | delivery-channels scenario | | |
| Collector reachability (30) | `src/autoinfo/collectors/` | reachability probe | collectors-e2e scenario | | |
| Error envelope (27 ErrorCodes) | `src/autoinfo/mcp/errors.py` | boundary matrix | error-boundary scenario | | |

The acceptance target for this sub-angle is the `coverage_audit` result 141/141 with zero MISSING tools, plus the CLI 28/28 and REST 8/8 claims verified per version. The scenario contract (`docs/dev/validation-scenario-contract.md`) documents the current 141/141 / 28 / 8 coverage and the no-key baseline profile (37 pass / 0 fail / 10 unconfigured).

### (c) End-user-responsible angle

Validate every feature from the B1/end-user-responsible perspective, not just B2-operational. A feature "works" for the agent (tool returns `{success, data}`) is not the same as a feature "works" for the paying end user. For each feature inventory row, ask the B1 question and grade it:

| B1 question | Example evidence |
|-------------|------------------|
| Does the feature serve a B1 lifecycle stage (discover, trial, subscribe, consume, renew, churn)? | delivery-channels, enduser-lifecycle, products-billing scenarios |
| Does the feature produce something a B1 human can actually consume and read? | D3 human track evidence (rendered md/html/pdf) |
| Does the feature respect the B1 subscription/tier and preference contract? | `check_access` gating, `content_preference`, enduser-preferences scenario |
| Is the failure mode something a B1 user would see as a clean error, not a silent drop? | error-boundary, delivery reliability evidence |

### Binary acceptance criteria

1. An agent can enumerate coverage and features using only MCP tools (`list_validation_scenarios`, `get_tool_count`, `tools/list`) and the audit script, with no human help. False = FAIL.
2. `scripts/coverage_audit.py` reports 141/141 covered with zero MISSING tools. Any missing tool = FAIL.
3. Every feature inventory row maps to at least one scenario or one evidence artifact in the run report. A row with neither = FAIL.
4. For every feature, the B1-responsible question is answered in the report, not only the B2-operational one. A feature graded only at the `{success, data}` level = RISK.

### Per-version reuse note

The three sub-angles, the coverage matrix template, and the four criteria are **reuse**-stable: the structure does not change per version. Per version you re-run the audit, re-fill the coverage matrix, and re-answer the B1 questions. When the inventory grows (a new tool, a new channel), the matrix rows grow with it; when it shrinks, rows are removed. The reuse discipline: update rows and numbers, never the criteria.

---

## §6 Grading and Report Template

### Per-dimension verdict table skeleton

| Dimension | Verdict | Blockers | Evidence artifacts | Notes |
|-----------|:---:|----------|--------------------|-------|
| D1 Data-layer definitions | | | | |
| D2 Authenticity | | | | |
| D3 Readability (human) | | | | |
| D3 Readability (agent) | | | | |
| D4 Requirement awareness | | | | |
| D5 Validation meta-coverage | | | | |
| **Overall launch verdict** | | | | |

Verdict values are PASS / FAIL / RISK only, plus `unconfigured` noted per check where a key was missing at run time. An overall FAIL or RISK in any dimension blocks launch sign-off.

### Blocker-list format

The blocker list contains FINDINGS ONLY. No auto-fix, no remediation code, no suggested patch. A blocker entry records what was observed, where, and why it violates a binary criterion:

```
- [B-NNN] Dimension: <D1..D5> | Criterion: <1..4>
  Finding: <what was observed, with the exact command and output or artifact path>
  Source: <file:line or MCP tool call>
  Criterion violated: <quote the criterion text>
  Severity: <blocker / major / minor>
```

The director (B3) decides remediation. The agent grades; the human disposes.

### Executive-summary skeleton

```
# Launch Validation Run Report <version> (<date>)

Run by: <B2 agent-as-tester> | Reviewed by: <B3 director>
Baseline (no keys): <X passed / Y failed / Z unconfigured at N scenarios>
Keys configured: <yes/no, which>

## Verdicts
- D1: <verdict>
- D2: <verdict> (<n> suspects open)
- D3: <verdict> (human: <v>, agent: <v>)
- D4: <verdict> (<n> requirements undetected)
- D5: <verdict> (coverage <a>/141)

## Executive summary
<3-6 sentences: what was validated, what passed, what blocks launch>

## Blockers
<blocker list per the format above>

## Appendix pointer
<list of evidence artifacts and the commands that produced them, per the Evidence Catalog>
```

### Bilingual note

The run report is written in English, matching repo doc conventions. The director communicates in Chinese; a Chinese-language summary of the verdicts, blockers, and executive summary can be produced on request. The English report remains the source of truth.

---

## Appendix: Evidence Catalog

Re-runnable commands per version, run from the project root (`/mnt/d/贯维/AutoInfo`). Each produces the artifact named; attach it to the run report.

| # | Check | Command | Produces | Dimension |
|---|-------|---------|----------|-----------|
| A1 | Scenario coverage audit | `python3 scripts/coverage_audit.py` | covered/missing tool list, 141/141 target | D5 |
| A2 | Scenario inventory dump | `autoinfo mcp` client or MCP `list_validation_scenarios` | 47-scenario JSON/YAML inventory | D5, D0 baseline |
| A3 | Scenario run harness | `run_validation_scenario(scenario="<name>")` via MCP, or the executor directly with a real dispatch | per-scenario status (passed/failed/unconfigured) | D0, D4 |
| A4 | Onboarding dry run | `init_project(dry_run=true)` or inspect `init_project` next_steps response | the 3-item next_steps + any platform-key prompts | D4 |
| A5 | System phase | `diagnose_system()` | health_score + phase (uninitialized/llm_unconfigured/no_sources/ready_to_collect/operational) | D4 |
| A6 | Agent-format generation + schema validation | generate digest/tutorial/presentation/export with `format="agent"`, then `python3 -m jsonschema -i <artifact.json> docs/schemas/<schema>-v1.json` | validated JSON-LD, const-pinned `@context`/`@type` | D3 (agent track) |
| A7 | REST smoke | `curl http://localhost:8741/health` and `curl http://localhost:8741/api/v1/entries?limit=5` | envelope JSON | D0, D5 |
| A8 | Git cleanliness | `git status --porcelain` | list of untracked/modified files, confirming no runtime artifacts or pre-existing changes are swept into the run | D0 |
| A9 | No-simulated-layer scan | grep over `src/` excluding `tests/` for `mock`, `fixture`, `sample`, `placeholder`, `example.com`, `sk_test` | hit list with dispositions, feeding the SUSPECT table | D2 |
| A10 | Real-fetch proof | `collect_sources(domain=<d>, dry_run=false)` on a real configured source, then read the raw JSON cache | raw items with real `source_url`/`source_type`/`source_platform` | D1, D2 |
| A11 | Rendered artifacts | generate digest/report in markdown, html, pdf; and a tutorial/presentation; attach files | rendered output artifacts | D3 (human track) |
| A12 | B1 preference test | `update_preferences` / `get_preferences` for `raw_only` / `processed_only` / `both` | preference honored in delivered product set | D1 |

Run order: A8 (cleanliness) → A1/A2 (coverage baseline) → A9 (suspect scan) → A5/A4 (requirement state) → A10/A11/A6/A12 (per-dimension evidence) → A3/A7 (execution confirmation). Record the no-keys baseline first, then set keys and re-run the env-gated checks; `unconfigured` results are recorded, never passed.
