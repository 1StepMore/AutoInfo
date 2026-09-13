<!-- doc-type: plan -->
<!-- status: completed -->

# Agent-Oriented Gap Register — AutoInfo

> **Status**: revised-after-review (high-accuracy review complete)
> **Intent**: clear
> **Review required**: true — receipts below
> **Spine**: stage×level coverage guarantee (A1–A7 × B1/B2/B3 lifecycle; F01–F72)
> **Layers**: Pillars (Toolability / Recoverability / Traceability) × Axes (stage×user, category×pyramid) × AX metrics
> **Scope**: Full. No MVP reduction. Every gap is derived from real evidence in this repo.

## Review receipts

| Cycle | Reviewer | Verdict | Key defects | Disposition |
|---|---|---|---|---|
| 1 | **Momus** (native) | **FAIL** | 11 register IDs had no todo (incl. S0 T-A-06); spine arithmetic contradiction; non-mechanizable acceptance; severity miscount; evidence inaccuracies | Fixed (T23–T31; spine reconciled; thresholds pinned; summary recomputed) |
| 1 | **Oracle** (independent) | **NEEDS-WORK** | `--resume-from` does not exist; S0 inflation; AX metrics unmapped; wave overlaps; omitted areas (privacy, tenancy, vendor-agnosticism, REST, build/release) | Fixed (R-A-01 re-scoped; severities recomputed; metrics mapped; waves re-derived; T-A-07/08/09 + T-S-10/11/12 added) |
| 2 | **Momus** | **CONDITIONAL** | 8 of 9 cycle-1 defects closed; category-count evidence verbatim count contested | Fixed: category wording made count-agnostic ("20+ ad-hoc") |
| 2 | **Oracle** | **NEEDS-WORK** | (a) spine provenance wrong — root spec defines only 16 stages (B3.1–B3.3), B3.4/B3.5 are catalog-only; (b) plan adds 3 new MCP tools yet hardcodes 146/146; (c) T-B-02 S1 vs T-A-02 S0 inconsistency; (d) M-04 pillar/axis blank | All fixed in this revision: (a) provenance stated as 18 = 16 ratified + 2 catalog, T-A-07 ratifies them; (b) tool count made dynamic; (c) T-B-02 raised to S0; (d) M-04 marked explicit cross-cutting |
| 3 | **Momus** (ses_f69a6c282ffe3uebxjGY0UbMJq) | **CONDITIONAL** | 7/7 round-2 items CLOSED; residuals: Todo 22 hardcoded "→146"; T-A-07's root-spec ratification had no owning todo | Fixed: Todo 22 now dynamic; `user-lifecycle-definition.md` added to Todo 5 |
| 3 | **Oracle** (ses_f69a6b8dbffeKfi9W0ODCB5nJP) | **NEEDS-WORK** | 7/7 CLOSED; residuals: scenario count hardcoded (F1 "138/138", Todo 12 "all 138"); new scenarios not required to be tagged; intra-W1 23→5 inversion; VT-04 conflated gaps with cells | All fixed: counts dynamic; stage/level + pyramid tags required for new scenarios; Todo 23 QA re-sequenced; VT-04 reframed; guardrail extended |

Read-only reviewers; no product code was edited. Verification table (both reviewers concur): `outputSchema` 0/146 **VERIFIED**; `pipeline_stage`/`user_level` absent, 0/138 tagged **VERIFIED**; 138 = 65 + 73 **VERIFIED**; `error_message_audit.py` false-GREEN vs real `str(exc)` sites **VERIFIED**; `diff_scenario_runs` misclassification **VERIFIED**; README "Known Limitations" mid-sentence **VERIFIED**; `server.py` docstring "30 tools / 7 categories" **VERIFIED**; 89/146 tools lack CLI reference; global `--json` only kb/sources/status **VERIFIED**; 5 dead ErrorCodes **VERIFIED**. Corrections applied: coverage matrix is **13 domains** (not 16); `end-user-matrix.yaml` is the **hand-authored spec** (generated output is `matrix-report.md`); categories are **20+ ad-hoc** values (exact count method-dependent); current KB is **4-tier** (00-Inbox deprecated); `name`/`domain` param split is **14/55** (user_id/end_user_id 21/11 stays); `project-evaluation-2026-09-06.md` is under `docs/`.

---

## 1. Purpose & reading contract

This is a **gap register**, not a backlog of opinions. Each row names the pillar and axis it belongs to, the real evidence, the current state, and the decision-complete required outcome. Executable remediation lives in `## Todos`; closure lives in `## Final verification wave`.

The **spine** is the original claim under audit:

> *"Validation scenarios perfectly reflect all real scenarios in every stage for every level of users, aligned with project status, so agent-testers can test with automation and accuracy."*

The methodology's 3 pillars, the category×pyramid axis, and AX metrics are layered onto that spine — they widen what "reflected" and "accurate" must mean; they do not replace the stage×level commitment.

### 1.1 The two coverage axes (kept distinct)

| Axis | Name | Cells | Source of truth |
|---|---|---|---|
| **A** | stage×user | 7 pipeline stages (A1–A7) × **18 lifecycle stages** = **126**; plus **72** expectation rows F01–F72 | Root spec `docs/dev/specs/user-lifecycle-definition.md` defines **16** stages (B1.1–B1.7, B2.1–B2.6, B3.1–B3.3); catalog `docs/dev/cross-dimensional-catalog.md` adds **B3.4 Iterate / B3.5 Scale** and omits **B1.7 Reactivate** (17 columns). **Spine = the 18-stage union** → **T-A-07**; `docs/dev/specs/expectations.md` |
| **B** | category×pyramid | 5 categories (happy_path, edge_case, failure, agent_interaction, performance) × 4 layers (unit, component, e2e, red_team) = **20** | methodology `agent-oriented-design-mindset.md` §4 |

**Spine decision (resolves both review cycles):** the cell-set is **126** (7 × 18) = the root spec's **16** ratified stages (B1.1–B1.7, B2.1–B2.6, B3.1–B3.3) **plus** the catalog's two forward-looking stages (**B3.4 Iterate, B3.5 Scale**). B1.7 exists in the root spec but is missing from the catalog matrix; B3.4/B3.5 exist only in the catalog and are not yet ratified. **T-A-07** therefore requires ratifying B3.4/B3.5 into `user-lifecycle-definition.md` **and** adding the B1.7 column to the catalog, so both documents agree at 18. Until that lands, the 18-stage union (126 cells) is authoritative for coverage. No acceptance may hard-code 119 nor claim the root spec already contains 18 stages.

**Counts are dynamic (tools and scenarios):** Todos 5, 12, and 20 add three MCP tools (`get_coverage_report`, `run_all_validation_scenarios`, `get_run_decisions`), taking the declared count from **146 → 149**; Todos 9, 10, 19, 30, and 31 add scenarios beyond the **138** baseline. Every count-based acceptance is therefore expressed as **"100 % of the live source"** (`_full_tool_list()` for tools; the loader / `list_validation_scenarios` for scenarios), never a hard-coded integer; the doc-consistency check reads the live counts.

### 1.2 Pillars (methodology §1.2)

| Pillar | Definition | The register question |
|---|---|---|
| **P1 Toolability** | clear, machine-readable interfaces | Can an agent discover, invoke, and parse every capability without a human? |
| **P2 Recoverability** | resume / retry / rollback gracefully | Can an agent recover from partial failure at every stage? |
| **P3 Traceability** | every action observable and auditable | Can an agent (or director) reconstruct what happened and trust the verdict? |

### 1.3 Severity scale

| Sev | Meaning |
|---|---|
| **S0** | Breaks the coverage guarantee itself; a false claim of coverage/verdict correctness is possible |
| **S1** | High: materially degrades agent operation or verdict accuracy |
| **S2** | Medium: friction / ambiguity / drift, workaround exists |

Severity is applied strictly against the S0 definition. Envelope/raw-exception/tooling gaps are S1 unless they cause a false coverage or verdict claim.

---

## 2. The spine — stage×user guarantee, current state

### 2.1 Definition of the spine

For every one of the 126 stage×user cells, the project must answer, from machine-readable data: designed? implemented? validated by a scenario? If not validated, is it in exactly one committed state (out-of-scope / blocked-with-record / documented-limit)? Is unclassified state exactly **zero** (AC4 criterion 1)?

### 2.2 Reality of the spine

| Spine component | State | Evidence |
|---|---|---|
| Scenario→stage metadata | **Absent** | `src/autoinfo/mcp/validation.py::load_scenarios` accepts no `pipeline_stage`/`user_level`; 0/138 scenarios carry one |
| Scenario→user-level metadata | **Absent** | same |
| Coverage metric | **Tool-centric, not stage/user-centric** | `scripts/coverage_audit.py` reports 146/146 MCP tools (baseline; grows to 149 after Todos 5/12/20); nothing reports A×B cells |
| Stage mapping | **Prose-only, ID-colliding** | `docs/dev/validation-scenario-contract.md` §2.5 uses rows `A1–A4, B1–B7, …` colliding with keystone `A1–A7` / `B1–B3` |
| Coverage surfaces | **Two, disagreeing** | `docs/dev/enduser-coverage-matrix.md` (hand-maintained, 99 items, 13 domains) vs `docs/dev/specs/end-user-matrix.yaml` (hand-authored spec; generated output `matrix-report.md`, 8×8×13) |
| Matrix completeness | **50.4% green** | `cross-dimensional-catalog.md`: 60/119 green, 17 red, 42 catalogued CD entries (the catalog's own open/resolved split is internally inconsistent — capture via T-A-02; do not restate a number) |
| User levels implemented | **Partial** | F58–F69 not implemented; `docs/dev/specs/multi-tenancy-auth.md` "Never Designed — spec only, zero implementation" |

### 2.3 Known-empty / thin spine cells (must be closed or committed)

| Spine cell | State |
|---|---|
| A6 Consumption | 1 scenario (`enduser-journey.yaml`, 2 steps) |
| B2.6 Report | `user-lifecycle-definition.md`: "❌ No structured reporting mechanism exists. This is a gap." |
| B3.2 Monitor / B3.3 Intervene | no dedicated scenario |
| B1.7 Reactivate | in root spec; **absent from keystone catalog matrix** (T-A-07) |
| F65–F72 (B1/B2/B3 lifecycle gaps) | expectations exist; no scenario |
| A3 × B1.5 (config modification) | F67 ❌ |
| A1 × B1.1 / A4 × B1.3 (discovery/onboarding) | F65/F66 ❌ |
| Payment chain (B1.2 Subscribe) | explicitly V2-deferred (`acceptance-framework.md` §6) |

---

## 3. Register — P1 Toolability

### 3A. Axis A — stage×user

| ID | Gap | Sev | Evidence | Required outcome |
|---|---|---|---|---|
| T-A-01 | Scenario schema cannot express stage/user → spine unmeasurable | S0 | `src/autoinfo/mcp/validation.py` (loader); 0/138 tagged | Add `pipeline_stage` (A1–A7) + `user_level` (B1.1–B1.7, B2.1–B2.6, B3.1–B3.5) to schema; backfill 138; loader validates enum membership |
| T-A-02 | Empty/thin cells have no committed state | S0 | §2.3 | Emit a stage×user coverage report over **126** cells + 72 expectations, classifying each implemented-validated / blocked / out-of-scope; **zero unclassified** |
| T-A-03 | Coverage metric is tool-centric | S1 | `scripts/coverage_audit.py` | Add stage×user coverage rate; AC3/AC9 cite it |
| T-A-04 | Taxonomy IDs collide | S1 | `validation-scenario-contract.md` §2.5 | Rename evidence rows to `EV-A1…EV-I6`; guard test: no evidence ID equals a keystone ID |
| T-A-05 | Two disagreeing coverage surfaces | S1 | `enduser-coverage-matrix.md` (99 items / **13** domains) vs `end-user-matrix.yaml` (8×8×13) | Generate the 99-item view from `end-user-matrix.yaml` (13-domain basis); delete hand-maintained duplication |
| T-A-06 | Unimplemented user levels presented inside "every level" | S0 | F58–F69; `multi-tenancy-auth.md` | Classify each as out-of-scope/blocked with recorded rationale; the guarantee must name the committed boundary |
| T-A-07 | Spine provenance: root spec 16 stages, catalog 17, neither is 18 | S1 | Root spec defines B3.1–B3.3 only; catalog matrix omits B1.7 and adds B3.4/B3.5 (`cross-dimensional-catalog.md`) | Ratify B3.4/B3.5 into `user-lifecycle-definition.md`; add the B1.7 column to the catalog → both agree at 18 (126 cells); fix `AGENTS.md`/`README.md` "42 cells" mislabel |
| T-A-08 | Data-privacy / export-delete lifecycle unvalidated per user level | S1 | `soft_delete_entry`/`restore_entry`/`export_user_data`/`delete_user_data`; `data-privacy.yaml` exists but no per-level coverage | Add per-user-level privacy/export/delete scenarios (soft-delete→restore window→purge; GDPR export; retention by tier) |
| T-A-09 | Multi-tenant isolation is an unenforced security boundary | S1 | `multi-tenancy-auth.md` "No implementation exists"; `user_id` advisory only; stdio-trusted assumption | Record the committed boundary (stdio-trusted for v1) AND add a scenario/guard asserting no cross-user read/write on the agent surface |

### 3B. Axis B — category×pyramid

| ID | Gap | Sev | Evidence | Required outcome |
|---|---|---|---|---|
| T-B-01 | No fixed scenario category taxonomy | S1 | scenarios use 20+ ad-hoc `category` values (not the fixed 5-value taxonomy; exact count is method-dependent — enumerate in Todo 8) | Adopt `happy_path/edge_case/failure/agent_interaction/performance`; migrate |
| T-B-02 | No category×pyramid coverage report | S0 | none exists | Emit 20-cell category×pyramid coverage; fail on unclassified |
| T-B-03 | Red-team / adversarial layer absent | S1 | no injection/exfiltration scenarios; `project-evaluation-2026-09-06.md` P3 "No LLM Prompt Injection Defense" | Add a red_team layer (injection, prompt-escape, exfiltration, tool-argument abuse) |
| T-B-04 | Agent-interaction scenarios absent | S1 | no tool-selection / multi-turn-context scenario | Add `agent-tool-selection` + `agent-multiturn-context` scenarios |
| T-B-05 | Performance scenarios absent | S1 | no concurrency/token-budget/latency scenario | Add concurrency, token-budget, latency scenarios with pinned thresholds (Todo 10) |
| T-B-06 | Unit/foundation layer not represented as scenarios | S2 | `tests/` has unit tests, not scenario-library entries | Decide and document the boundary (schema/prompt unit checks in `tests/`, behavioral in scenarios) |

### 3C. Pillar-native — tool surface

| ID | Gap | Sev | Evidence | Required outcome |
|---|---|---|---|---|
| T-S-01 | `outputSchema` on 0/146 tools | S1 | `src/autoinfo/mcp/server.py` `_full_tool_list()`; `mcp.types.Tool` supports it | Declare return schemas for every tool; test enforces presence |
| T-S-02 | Envelope not unified | S1 | `health_check` flat (handler ~L258; exemption ~L11664); **66–68** handler functions emit flat `error_code` dicts (count method-dependent — enumerate in Todo 14) | All tools return `{success,data}` / `{success,error:{code,message,actionable}}`; test asserts zero hybrid shapes |
| T-S-03 | Param naming inconsistent for same entity | S1 | `user_id` 21 tools vs `end_user_id` 11 (**verified**); domain identity `name` 14 tools (4 domain-management) vs `domain` 55 | Canonical names + aliases with deprecation; test forbids both spellings on one entity |
| T-S-04 | Schemas under-constrained / under-documented | S1 | 104/146 zero-enum; 36 descriptions <10 words; 4 tools >8 params (verified by `scripts/tool_desc_audit.py`) | Enums for finite params; descriptions ≥40 words with "when to use"; split over-8-param tools |
| T-S-05 | ErrorCode inconsistency + dead codes | S2 | 28 CamelCase values vs 2 SCREAMING_SNAKE (`DIRECTOR_ONLY`, `READ_ONLY_SERVER`); 5 never emitted (`RATE_LIMITED`, `AUTH_REQUIRED`, `SESSION_EXPIRED`, `NO_CACHED_ITEMS`, `PROCESSING_FAILED`) | One casing convention; implement or remove unused codes; RATE_LIMITED path emits Retry-After guidance |
| T-S-06 | Raw exception leakage | S1 | direct `error_response(..., str(exc))` sites (`collect_sources` ~L573, `configure_llm` ~L4728, `remove_agent_callback` ~L6678, `recommend_content` ~L6796, dispatch ~L12173) | Every failure message carries remediation; no `str(exc)` payloads |
| T-S-07 | CLI/MCP parity claim false | S1 | global `--json` read only in `cli/kb.py`, `cli/sources.py`, `cli/status.py`; 89/146 tools have no CLI name reference (**verified**); `report_type`↔`--type` drift | Honor global `--json` everywhere; derive parity in CI; fix param drift |
| T-S-08 | Director-only tools exposed in `list_tools()` | S2 | `demote_kb_wiki`, `force_promote` (require `actor` ∈ `AUTOINFO_DIRECTOR_ACTORS`) | Hide or mark director-only in discovery (AC1.3 enforcement) |
| T-S-09 | Prose/raw-text payloads | S2 | `health_check`; `get_prometheus_metrics` (`metrics_text`); `get_feeds(format=rss)` (`content`) | Wrap text payloads with machine-readable metadata; document exceptions |
| T-S-10 | REST/HTTP surface not covered by Toolability parity/coverage | S1 | parity covers MCP+CLI only; FastAPI REST + `kind: http` scenarios exist but no surface-coverage gap row | Extend the parity/coverage matrix to REST; assert all 8 endpoints have scenario or artifact |
| T-S-11 | Build/release surface unvalidated | S2 | no scenario/check for `pip install -e .`, packaging, release-please | Add a build/release validation scenario or CI gate (methodology acid test: build from `AGENTS.md`) |
| T-S-12 | Model/vendor agnosticism not validated as a contract | S1 | `AGENTS.md` #194/#195 invariant; no register row or scenario asserts it | Add a scenario asserting no hardcoded vendor/model in battery/blindspots; judgment resolution config-first |

---

## 4. Register — P2 Recoverability

### 4A. Axis A — stage×user

| ID | Gap | Sev | Evidence | Required outcome |
|---|---|---|---|---|
| R-A-01 | Checkpoint/resume/rollback unverified at every stage; `--resume-from` does not exist | S1 | `grep -rin resume src/ scripts/` → 0 hits (verified); no scenario exercises resume across A1–A7 | **Re-scoped**: build checkpoint/resume (the flag is capability-absent, not merely unverified); then prove it per stage via real calls |
| R-A-02 | No per-user-level partial-success guarantee | S1 | scenario `min_passing`/`pass_ratio` only at scenario granularity | Define what partial success means for a B1 delivery and a B2 pipeline run; validate it |

### 4B. Axis B — category×pyramid

| ID | Gap | Sev | Evidence | Required outcome |
|---|---|---|---|---|
| R-B-01 | No failure-at-step-N checkpoint/resume scenario | S1 | `fault-injection.yaml`, `collect-failure-recovery.yaml`, `llm-failure-recovery.yaml` exist; no mid-pipeline network-failure resume | Add the methodology §4.2 Category-3 scenario: fail at step 3/5 → resume → complete |
| R-B-02 | No idempotency/rollback scenarios | S1 | no scenario proves retry safety across churn/reactivate/retry | Add idempotency + rollback scenarios for destructive/retryable operations |

### 4C. Pillar-native — harness recoverability

| ID | Gap | Sev | Evidence | Required outcome |
|---|---|---|---|---|
| R-S-01 | Per-step `timeout_seconds` is a silent no-op | S1 | zero `.py` references; only scenario-level `timeout` (~L1431) + MCP param; README advertises per-step timeouts | Wire per-step timeout; test a hanging step is cut at its own budget |
| R-S-02 | Step-level `collect_artifacts` silently ignored | S1 | contract §1.2 says per-step; `_execute_scenario` reads scenario-level (~L1655) | Support step-level (overrides scenario default); reject unknown placement explicitly |
| R-S-03 | `recovery_steps` do not re-evaluate | S2 | contract §1.2 "then re-evaluate" vs §1.3 "reported as recovered" | Make contract and engine agree (recovered-only); update §1.2 |
| R-S-04 | Timeout cancellation not universal | S1 | `asyncio.wait_for` cannot cancel `asyncio.to_thread` (CLI/HTTP workers may continue) | Kill workers on timeout for all step kinds; test no orphan process/request |
| R-S-05 | No aggregate run-and-save | S1 | `server.py::_handle_run_validation_scenario` saves one run dir per scenario; `scripts/validation_report.py` expects `scenarios[]` | Add a suite-level run + single persisted run consumed by the report |
| R-S-06 | Whole-scenario `unconfigured` blocks partial | S2 | any unconfigured step forces `unconfigured` even if threshold met (~L1635) | Define whether unconfigured blocks partial; document and test |
| R-S-07 | Leak guard silently no-ops | S2 | `_scan_autoinfo_test_leaks` returns `[]` on any exception (~L1216) | Fail loud or surface the swallowed error |

---

## 5. Register — P3 Traceability

### 5A. Axis A — stage×user

| ID | Gap | Sev | Evidence | Required outcome |
|---|---|---|---|---|
| TR-A-01 | No session-level correlation across a lifecycle run | S1 | scenarios carry only a per-run `trace_id` (~L1417) | Emit a session/action correlation ID spanning A1–A7 for a B2 run; expose via a query tool |
| TR-A-02 | B2.6 structured reporting absent → no decision trail | S1 | `user-lifecycle-definition.md` B2.6 "❌ No structured reporting mechanism" | Implement structured run reports (what ran, verdicts, anomalies) — also spine cell B2.6 |

### 5B. Axis B — category×pyramid

| ID | Gap | Sev | Evidence | Required outcome |
|---|---|---|---|---|
| TR-B-01 | No category×pyramid result ledger | S1 | results are per-scenario, not aggregated by category/layer | Persist and expose category×pyramid pass history |
| TR-B-02 | No N-run pass-rate history | S1 | suite is single-run; `acceptance-framework.md` AC9 backlog item (1) admits this | Track pass-rate over N runs; gate hard 5/5, soft 4/5 as the doc specifies |

### 5C. Pillar-native — harness traceability

| ID | Gap | Sev | Evidence | Required outcome |
|---|---|---|---|---|
| TR-S-01 | `diff_scenario_runs` misclassifies results | S0 | empirically reproduced: persistent failures → `new_failures`; `unchanged` double-counted (~L140–169) | Correct classification; regression tests for same-status runs |
| TR-S-02 | "Root-cause report" is a blocker list | S1 | `scripts/validation_report.py` `## Blockers` = failing steps + truncated detail | Produce a real causal report (dedup, classification, first-cause) or rename the claim |
| TR-S-03 | Recovery/cleanup `step_index` collisions | S2 | recovery inherits primary index (~L1204); cleanup restarts at 1 (~L1681) | Unique step identity in traces |
| TR-S-04 | Duplicate scenario names allowed | S2 | `run_scenario` `next(...)` takes first (~L1419) | Loader enforces unique `name`; test rejects duplicates |
| TR-S-05 | `regression:true ⇒ regression_issue` unenforced | S2 | loader imposes no requirement | Enforce at load; fail on missing issue |
| TR-S-06 | `list_scenarios` omits `regression_issue` | S2 | `validation.py` ~L901 | Surface issue in listing so bug→scenario links are auditable |

---

## 6. AX metrics register

Each metric is mapped to a pillar and axis (resolves the review's "flat list" defect) and carries a pinned target and gate.

| ID | Metric | Pillar | Axis | Target | Current | Gate |
|---|---|---|---|---|---|---|
| M-01 | Task completion rate | Toolability | B | >95% | not measured | CI fails below threshold |
| M-02 | Tool-call accuracy | Toolability | B | >98% | not measured | CI fails below threshold |
| M-03 | Recovery success rate | Recoverability | B | >99% | not measured | CI fails below threshold |
| M-04 | Documentation freshness | All (cross-cutting — doc Principle 5) | All (cross-cutting) | 100% | drift present (§7) | consistency checker in CI |
| M-05 | Token efficiency | Recoverability | B | ≤ baseline tokens/task, regression ≤10% | not measured | report + 10% regression gate |
| M-06 | Error recovery time | Recoverability | A | <30s | not measured | CI fails on breach |

---

## 7. Cross-cutting — Verifiable Truth / documentation integrity

Methodology Principle 5 and §5.3 acid test #3 ("never act on stale data") make these violations.

| ID | Gap | Sev | Evidence | Required outcome |
|---|---|---|---|---|
| VT-01 | Coverage matrix is hand-maintained | S1 | `docs/dev/enduser-coverage-matrix.md` L18 self-declares not generated | Generate it from `end-user-matrix.yaml` |
| VT-02 | README "Known Limitations" starts mid-sentence | S2 | `README.md` L485 | Repair the section |
| VT-03 | Scenario count drift | S1 | README 72 vs 73; `.opencode/skills/validation-runner-skill/SKILL.md` 137 (65+72); `acceptance-framework.md` 116 and 138 in one paragraph | Single source; CI check |
| VT-04 | "42 cells" mislabels the gap count as cells | S1 | `AGENTS.md`/`README.md` say "42 cells"; the catalog's 42 is its CD **gap** count and its matrix is 119 cells | Correct to "42 gaps / 119 cells → 126 after T-A-07"; the two numbers are not competing cell counts |
| VT-05 | Tool/category count drift | S1 | `server.py` docstring L4 "30 tools / 7 categories"; README MCP table does not enumerate 8 tools present in code (verify in Todo 3); spec lists 146 | Generate counts; CI check against `_full_tool_list()` |
| VT-06 | Stale archived reference contradicts current design | S2 | `docs/archive/kb-pipeline-reference.md` "agent must not write Wiki" vs current agent-promotes design | Fix or quarantine the citation |
| VT-07 | Methodology doc §9 states stale facts | S2 | `agent-oriented-design-mindset.md` §9: "40+ tools", "Inbox→Raw→Draft→Wiki" vs **4-tier** (00-Inbox deprecated), "G1–G5" vs G0–G5; also claims `--resume-from` which does not exist | Correct the reference-implementation facts |
| VT-08 | Audit scripts false-GREEN | S0 | `scripts/error_message_audit.py` reports 0 raw sites while real `error_response(..., str(exc))` sites exist; positional message args unscanned | Fix detection; test that plants a raw site and expects failure |

---

## 8. Severity summary (recomputed after review)

Counts reconcile to **62** register IDs (T-A-01..09, T-B-01..06, T-S-01..12, R-A-01..02, R-B-01..02, R-S-01..07, TR-A-01..02, TR-B-01..02, TR-S-01..06, M-01..06, VT-01..08).

| Sev | Count | IDs |
|---|---|---|
| **S0** | 6 | T-A-01, T-A-02, T-A-06, T-B-02, TR-S-01, VT-08 |
| **S1** | 39 | T-A-03, T-A-04, T-A-05, T-A-07, T-A-08, T-A-09; T-B-01, T-B-03, T-B-04, T-B-05; T-S-01, T-S-02, T-S-03, T-S-04, T-S-06, T-S-07, T-S-10, T-S-12; R-A-01, R-A-02, R-B-01, R-B-02, R-S-01, R-S-02, R-S-04, R-S-05; TR-A-01, TR-A-02, TR-B-01, TR-B-02, TR-S-02; M-01, M-02, M-03, M-04; VT-01, VT-03, VT-04, VT-05 |
| **S2** | 17 | T-B-06; T-S-05, T-S-08, T-S-09, T-S-11; R-S-03, R-S-06, R-S-07; TR-S-03, TR-S-04, TR-S-05, TR-S-06; M-05, M-06; VT-02, VT-06, VT-07 |

Priority rule: **S0 first**, then S1 items that unblock measurement (T-A-01, T-A-02, T-B-02, R-S-01, TR-S-01, VT-08) before coverage expansion.

---

## 9. Fix sequencing (dependency-correct, by todo)

| Wave | Purpose | Todos |
|---|---|---|
| **W0 Truth** | stop the suite from lying | 1, 2, 3 |
| **W1 Schema** | make coverage measurable (23 commits dispositions before 5 consumes them) | 4, 23, 5, 6, 7, 8 |
| **W2 Harness** | recoverable + clean scenario layer | 9, 11, 12, 13, 24, 26, 27 |
| **W3 Tool contract** | agent-native surface | 14, 15, 16, 17, 18, 25, 29 |
| **W4 Coverage** | close the axes | 10, 19, 20, 28, 30, 31 |
| **W5 Metrics** | gate the AX targets | 21 |
| **W6 Docs** | documentation integrity | 22 |

Dependency notes: every todo's `Register:` IDs appear exactly in its wave; no todo spans waves. W4 depends on W1 (schema) and W2 (harness) having completed.

---

## Todos

- [x] 1. Fix the regression flywheel classifier so persistent failures are not reported as new failures
  - Files: `src/autoinfo/mcp/validation.py` (`diff_scenario_runs` ~L116–169)
  - Change: correct same-status handling; make `unchanged` counted once; add unit tests for (passed→passed), (failed→failed), (unconfigured→unconfigured), (failed→unconfigured)
  - Acceptance: two identical runs of `{failed, unconfigured}` produce `new_failures=[]` and `unchanged=2`
  - QA: run the new unit tests; reproduce the pre-fix bug in a temporary test and show it now passes
  - Commit: `fix(validation): correct diff_scenario_runs classification`
  - Register: TR-S-01

- [x] 2. Fix `error_message_audit.py` false-GREEN and eliminate raw exception leakage
  - Files: `scripts/error_message_audit.py`, `src/autoinfo/mcp/server.py` (sites `collect_sources` ~L573, `configure_llm` ~L4728, `remove_agent_callback` ~L6678, `recommend_content` ~L6796, dispatch ~L12173; enumerate all first)
  - Change: audit scans positional message args and `_error_dict`; replace every `str(exc)` in `error_response` with `_error_from_exc(exc, context)`; add a planted-violation test
  - Acceptance: audit reports `raw_exception_sites==0` and exits non-zero when a raw site is planted
  - QA: `python3 scripts/error_message_audit.py` + planted-violation test
  - Commit: `fix(mcp): detect and remove raw exception leakage in error responses`
  - Register: T-S-06, VT-08

- [x] 3. Correct all stale counts and the broken README section; wire a consistency checker into CI
  - Files: `README.md` (Known Limitations L483–494; MCP tools table), `AGENTS.md`, `src/autoinfo/mcp/server.py` docstring L4, `.opencode/skills/validation-runner-skill/SKILL.md`
  - Change: single source for scenario/tool/category counts; fix "42 cells"; regenerate tool table; extend `scripts/doc_inventory.py --check` to cover server docstring, pytest collected count, tool-table completeness (beyond README↔AGENTS)
  - Acceptance: checker fails on a planted mismatch in each checked surface; README/AGENTS/server-docstring agree with the live `_full_tool_list()` count (baseline 146; 149 after Todos 5/12/20) and loader (138 = 65 + 73)
  - QA: `python3 scripts/doc_inventory.py --check`; plant one wrong count per surface and show failure
  - Commit: `docs: correct counts and enforce doc/code consistency in CI`
  - Register: VT-02, VT-03, VT-04, VT-05

- [x] 4. Add `pipeline_stage` + `user_level` to the scenario schema and backfill all scenarios (baseline 138)
  - Files: `src/autoinfo/mcp/validation.py` (`load_scenarios`, `list_scenarios`), `docs/dev/validation-scenario-contract.md` §1.2, all `src/autoinfo/mcp/scenarios/**/*.yaml`
  - Change: enum-validated `pipeline_stage ∈ A1..A7`, `user_level ∈ {B1.1..B1.7, B2.1..B2.6, B3.1..B3.5}`; backfill; loader rejects unknown values
  - Acceptance: 100 % of scenarios (live loader count; baseline 138, grows with Todos 9/10/19/30/31) expose stage/level; `pipeline_stage`/`user_level` are **required** so newly added scenarios must be tagged; an invalid tag fails to load
  - QA: enumerate tags; assert 138 tagged and zero invalid
  - Commit: `feat(validation): add pipeline_stage and user_level metadata`
  - Register: T-A-01

- [x] 5. Build the stage×user coverage report with zero-unclassified enforcement, and reconcile the 126-cell spine
  - Files: new `scripts/stage_user_coverage.py`; `src/autoinfo/mcp/server.py` (new tool `get_coverage_report`); `docs/dev/specs/user-lifecycle-definition.md`; `docs/dev/cross-dimensional-catalog.md`; `docs/dev/acceptance-framework.md`
  - Change: enumerate **126** cells (7 × 18 lifecycle stages) + 72 expectation rows; classify each; ratify B3.4/B3.5 into `user-lifecycle-definition.md` and add the B1.7 column to the catalog (both agree at 18); exit non-zero on unclassified
  - Acceptance: report classifies 100% of 126 + 72; catalog has 18 lifecycle columns
  - QA: run script and assert zero unclassified; inject an unclassified cell and one missing B1.7 column and show non-zero exit
  - Commit: `feat(validation): 126-cell stage-by-user coverage report`
  - Register: T-A-02, T-A-03, T-A-07

- [x] 6. Rename the evidence-matrix IDs to stop colliding with keystone A/B IDs
  - Files: `docs/dev/validation-scenario-contract.md` §2.5 and cross-references in `docs/dev/*.md`
  - Change: `A1–I6` → `EV-A1–EV-I6`; add a guard test that no evidence ID equals a keystone stage/user ID
  - Acceptance: guard test passes; grep finds zero plain `A<digit>`/`B<digit>` evidence IDs
  - QA: guard test + grep
  - Commit: `docs: namespace evidence-matrix IDs to EV-*`
  - Register: T-A-04

- [x] 7. Reconcile the two coverage surfaces into one generated source of truth
  - Files: `docs/dev/enduser-coverage-matrix.md`, `docs/dev/specs/end-user-matrix.yaml`, `scripts/coverage_matrix.py`
  - Change: generate the 99-item view from `end-user-matrix.yaml` on a **13-domain** basis; delete hand-maintained duplication; CI fails on divergence
  - Acceptance: one generator; rendered view matches spec; drift fails CI
  - QA: regenerate and diff; plant drift and show failure
  - Commit: `docs: generate coverage matrix from single source`
  - Register: T-A-05, VT-01

- [x] 8. Adopt the fixed scenario category taxonomy and add a category×pyramid coverage report
  - Files: scenario YAML `category` values, `src/autoinfo/mcp/validation.py`, new `scripts/category_pyramid_coverage.py`
  - Change: migrate categories to the 5-value taxonomy; add `pyramid_layer`; report 20 cells with zero-unclassified
  - Acceptance: 100 % of scenarios (live count; baseline 138) categorized and carrying `pyramid_layer` (required for new scenarios); all 20 cells classified
  - QA: run script; assert no unknown category/layer
  - Commit: `feat(validation): category×pyramid taxonomy and coverage report`
  - Register: T-B-01, T-B-02

- [x] 9. Add the red-team adversarial scenario layer
  - Files: new `src/autoinfo/mcp/scenarios/redteam-*.yaml`; `docs/dev/validation-scenario-contract.md`
  - Change: injection, prompt-escape, exfiltration, tool-argument-abuse scenarios with real assertions and a documented mutation mechanism (how the build is made deliberately vulnerable for the RED proof)
  - Acceptance: ≥4 red_team scenarios execute; the vulnerable mutation fails and the fixed build passes
  - QA: run them; apply the documented mutation and show RED, then revert and show GREEN
  - Commit: `test(validation): red-team adversarial scenario layer`
  - Register: T-B-03

- [x] 10. Add agent-interaction and performance scenarios with pinned thresholds
  - Files: new `src/autoinfo/mcp/scenarios/agent-tool-selection.yaml`, `agent-multiturn-context.yaml`, `perf-concurrency.yaml`, `perf-token-budget.yaml`, `perf-latency.yaml`
  - Change: thresholds — tool selection ≥98% over 20 trials; multi-turn retention 100% over 5 turns; 10 concurrent runs wall time <2× single; token budget flagged at 90%; p95 latency digest ≤120s, report ≤300s (documented domain scope)
  - Acceptance: each scenario asserts its pinned threshold
  - QA: run the scenarios; record artifacts
  - Commit: `test(validation): agent-interaction and performance scenarios`
  - Register: T-B-04, T-B-05

- [x] 11. Wire per-step `timeout_seconds` and support step-level `collect_artifacts`
  - Files: `src/autoinfo/mcp/validation.py` (`_execute_step`, `_execute_step_timed`, `_execute_scenario`), `docs/dev/validation-scenario-contract.md` §1.2/§1.3
  - Change: read step-level `timeout_seconds`; support step-level `collect_artifacts` (overrides scenario default); reject unknown placement with an error, never silently ignore
  - Acceptance: a step with `timeout_seconds: 1` is cut at 1s; step-level `collect_artifacts` is honored
  - QA: two targeted tests
  - Commit: `fix(validation): honor per-step timeout and artifact level`
  - Register: R-S-01, R-S-02

- [x] 12. Add suite-level aggregate run-and-save consumed by the report
  - Files: `src/autoinfo/mcp/server.py` (new `run_all_validation_scenarios`), `src/autoinfo/mcp/validation.py` (`save_scenario_results`), `scripts/validation_report.py`
  - Change: one invocation runs the full live scenario set (baseline 138, grows with Todos 9/10/19/30/31) and persists a single run with `scenarios[]`
  - Acceptance: `validation_report.py` consumes one aggregate run without external scripting
  - QA: run aggregate, generate report, verify all scenarios appear
  - Commit: `feat(validation): aggregate suite run persisted as one run`
  - Register: R-S-05

- [x] 13. Enforce loader invariants: unique names, `regression_issue`, min/pass exclusivity
  - Files: `src/autoinfo/mcp/validation.py` (`load_scenarios`, `list_scenarios`)
  - Change: reject duplicate `name`; require `regression_issue` when `regression: true`; reject both `min_passing` and `pass_ratio`; surface `regression_issue` in `list_scenarios`
  - Acceptance: each violation fails load with a clear message
  - QA: three negative tests + one positive
  - Commit: `fix(validation): enforce scenario load invariants`
  - Register: TR-S-04, TR-S-05, TR-S-06

- [x] 14. Implement the unified response envelope for all declared tools
  - Files: `src/autoinfo/mcp/server.py` (`_handle_health_check`, all flat `error_code` handler functions — enumerate all 66–68 first, dispatcher)
  - Change: every response is `{success,data}` or `{success,error:{code,message,actionable}}`; remove hybrid wrapping
  - Acceptance: a test iterates all handlers and asserts zero flat/hybrid shapes
  - QA: run the test; sample `health_check` and 3 previously-flat handlers
  - Commit: `refactor(mcp): enforce unified envelope across all tools`
  - Register: T-S-02

- [x] 15. Declare `outputSchema` for all tools and normalize params/enums/descriptions
  - Files: `src/autoinfo/mcp/server.py` `_full_tool_list()`
  - Change: add `outputSchema`; canonicalize `user_id`/`end_user_id` and `name`/`domain` with aliases; add enums to finite params; expand <40-word descriptions; split >8-param tools
  - Acceptance: test asserts `outputSchema` on 100 % of declared tools (dynamic; baseline 146, 149 after Todos 5/12/20); 0 zero-enum finite params; 0 descriptions <40 words; 0 tools >8 params
  - QA: extend `scripts/tool_desc_audit.py` floors and run
  - Commit: `feat(mcp): output schemas and normalized tool contracts`
  - Register: T-S-01, T-S-03, T-S-04

- [x] 16. Normalize ErrorCode casing and retire dead codes
  - Files: `src/autoinfo/mcp/errors.py`
  - Change: one casing convention; implement or remove `AUTH_REQUIRED`, `NO_CACHED_ITEMS`, `PROCESSING_FAILED`, `RATE_LIMITED`, `SESSION_EXPIRED`; emit Retry-After guidance on rate limiting
  - Acceptance: no SCREAMING_SNAKE outliers; every code emitted or removed
  - QA: enum test + emission grep
  - Commit: `refactor(mcp): normalize error codes`
  - Register: T-S-05

- [x] 17. Fix CLI/MCP parity: honor global `--json`, derive parity in CI, fix param drift
  - Files: `src/autoinfo/cli/__init__.py` and all `src/autoinfo/cli/*.py`; `docs/dev/cli-mcp-rest-parity.md`
  - Change: global `--json` emits the MCP envelope in every data-returning group; parity test flags tools without a CLI path and diverging params
  - Acceptance: `autoinfo --json <group> <cmd>` returns valid JSON for every data-returning command; parity report has no unexplained drift
  - QA: loop all groups with `--json` and parse; run parity test
  - Commit: `fix(cli): global --json envelope parity with MCP`
  - Register: T-S-07

- [x] 18. Gate director-only tools at discovery and code level
  - Files: `src/autoinfo/mcp/server.py` (`list_tools`, `demote_kb_wiki`, `force_promote`, `remove_domain`, `soft_delete_entry`)
  - Change: hide or mark director-only; enforce `AUTOINFO_DIRECTOR_ACTORS` at code level
  - Acceptance: `list_tools` does not present unusable director-only tools; bypass attempt fails
  - QA: non-director test
  - Commit: `fix(mcp): gate director-only tools in discovery`
  - Register: T-S-08

- [x] 19. Add recoverability scenarios: checkpoint/resume, rollback, idempotency
  - Files: new `src/autoinfo/mcp/scenarios/recover-*.yaml`; implement checkpoint/resume where absent
  - Change: failure-at-step-N resume; rollback of partial writes; idempotent retry; `--resume-from` CLI/MCP support
  - Acceptance: resume completes from checkpoint; rollback leaves no partial state; retry side-effect-free; `--resume-from` exists and is exercised
  - QA: run scenarios; inspect real artifacts before/after
  - Commit: `feat: checkpoint/resume + recoverability scenarios`
  - Register: R-A-01, R-A-02, R-B-01, R-B-02

- [x] 20. Add session-level traceability and the B2.6 structured run report
  - Files: `src/autoinfo/mcp/validation.py`; new MCP tool `get_run_decisions`; `src/autoinfo/output/`
  - Change: correlate all actions in a run/session with one ID; expose the decision trail; implement F69/B2.6
  - Acceptance: one ID reconstructs the full action sequence; a structured run report exists
  - QA: run a lifecycle scenario; query the trail and report
  - Commit: `feat(traceability): session correlation and B2.6 run reporting`
  - Register: TR-A-01, TR-A-02

- [x] 21. Instrument and gate the six AX metrics
  - Files: new `scripts/ax_metrics.py`, `src/autoinfo/mcp/validation.py`, CI workflow
  - Change: measure M-01..M-06 with the pinned targets in §6; gate in CI
  - Acceptance: report emits all six; CI fails below threshold
  - QA: run report; breach a threshold and show failure
  - Commit: `feat(metrics): AX verification metrics and gates`
  - Register: M-01, M-02, M-03, M-04, M-05, M-06

- [x] 22. Repair remaining documentation integrity items
  - Files: `docs/archive/kb-pipeline-reference.md` (or its citations), `D:\贯维\Vibe\methodology\agent-oriented-design-mindset.md` §9
  - Change: quarantine the superseded promotion rule; correct stale reference facts (40+ tools → the live `_full_tool_list()` count; 4-tier; G0–G5; remove `--resume-from` claim unless implemented); add to the consistency checker
  - Acceptance: no current doc cites the superseded rule; methodology §9 matches reality
  - QA: consistency checker + grep
  - Commit: `docs: repair superseded and stale references`
  - Register: VT-06, VT-07

- [x] 23. Classify every unimplemented user level with a committed disposition
  - Files: `docs/dev/specs/expectations.md`, `docs/dev/cross-dimensional-catalog.md`, `docs/dev/specs/multi-tenancy-auth.md`
  - Change: for F58–F69 and B3 stages, record exactly one state (out-of-scope / blocked-with-record / documented-limit) and the rationale; feed T-A-02's report
  - Acceptance: zero unclassified levels; each has a recorded rationale
  - QA: spot-check 5 dispositions against the catalog/expectations files; the Todo 5 coverage report (runs immediately after, intra-W1) must show them classified
  - Commit: `docs: commit dispositions for unimplemented user levels`
  - Register: T-A-06

- [x] 24. Define the unit/foundation layer boundary
  - Files: `docs/dev/validation-scenario-contract.md`, `tests/` README or a new `docs/dev/testing-layers.md`
  - Change: document which checks live in `tests/` (schema/prompt units) vs scenario library (behavioral), and how the validation pyramid maps to them
  - Acceptance: the 4 layers (unit/component/e2e/red_team) each have a named home
  - QA: doc review + a link-check that every layer is referenced
  - Commit: `docs: define validation pyramid layer boundaries`
  - Register: T-B-06

- [x] 25. Wrap raw-text payloads with machine-readable metadata
  - Files: `src/autoinfo/mcp/server.py` (`_handle_health_check`, `_handle_get_prometheus_metrics`, `_handle_get_feeds`)
  - Change: return structured metadata alongside text (e.g. `{format, content_type, length, content}`); document any intentional exception in ADR-0005
  - Acceptance: no tool returns an unlabelled raw-text payload
  - QA: iterate text-format tools and assert metadata keys
  - Commit: `refactor(mcp): structured metadata for text payloads`
  - Register: T-S-09

- [x] 26. Align recovery re-evaluation, unconfigured-vs-partial, and leak-guard failure semantics
  - Files: `src/autoinfo/mcp/validation.py` (`_execute_step_with_recovery`, `_execute_scenario`, `_scan_autoinfo_test_leaks`), `docs/dev/validation-scenario-contract.md` §1.2/§1.3
  - Change: contract §1.2 states recovered-only (matching §1.3); decide and test whether an `unconfigured` step blocks partial-pass; make the leak guard fail loud
  - Acceptance: contract and engine agree on all three; tests cover each
  - QA: three targeted tests
  - Commit: `fix(validation): recovery/partial/leak semantics`
  - Register: R-S-03, R-S-06, R-S-07

- [x] 27. Make timeout cancellation universal across step kinds
  - Files: `src/autoinfo/mcp/validation.py` (`_run_cli_step`, `_run_http_step`, `_execute_step_timed`)
  - Change: ensure timed-out CLI/HTTP workers are actually killed/closed (not left running via `asyncio.to_thread`)
  - Acceptance: after a timeout, no orphan subprocess or open HTTP request remains
  - QA: timeout tests for mcp, cli, and http kinds; assert process/request cleanup
  - Commit: `fix(validation): universal timeout cancellation`
  - Register: R-S-04

- [x] 28. Persist category×pyramid result ledger and N-run pass-rate history
  - Files: `src/autoinfo/mcp/validation.py`, `scripts/validation_report.py`
  - Change: aggregate and persist results by category and pyramid layer; track pass-rate over N runs (hard 5/5, soft 4/5)
  - Acceptance: report shows per-cell pass history and N-run rates
  - QA: run the suite twice; verify ledger accumulates
  - Commit: `feat(validation): category×pyramid ledger and N-run history`
  - Register: TR-B-01, TR-B-02

- [x] 29. Replace the blocker list with a real causal report and unique step identity
  - Files: `scripts/validation_report.py`, `src/autoinfo/mcp/validation.py` (recovery/cleanup step indices)
  - Change: dedup + classify failures, identify first-cause, and give recovery/cleanup steps unique identities
  - Acceptance: report attributes each failure to a cause class; trace has no duplicate `step_index`
  - QA: run a failing scenario; inspect the report and trace
  - Commit: `feat(validation): causal report and unique step identity`
  - Register: TR-S-02, TR-S-03

- [x] 30. Extend Toolability to REST, build/release, and model/vendor agnosticism
  - Files: `docs/dev/cli-mcp-rest-parity.md`, parity script, new `src/autoinfo/mcp/scenarios/surface-*.yaml`
  - Change: add REST to the parity/coverage matrix (all 8 endpoints have scenario or artifact); add build/release validation (`pip install -e .`, packaging); add a vendor/model-agnosticism scenario asserting no hardcoded vendor/model and config-first judgment resolution
  - Acceptance: REST coverage complete; build check passes; vendor-agnosticism scenario passes
  - QA: run parity + build check + scenario
  - Commit: `feat(validation): REST/build/vendor-agnostic surface coverage`
  - Register: T-S-10, T-S-11, T-S-12

- [x] 31. Add data-privacy and multi-tenant isolation coverage
  - Files: new `src/autoinfo/mcp/scenarios/privacy-*.yaml`, `tenancy-*.yaml`; `docs/dev/specs/multi-tenancy-auth.md`
  - Change: per-user-level soft-delete→restore→purge, GDPR export, tier retention scenarios; and a guard scenario asserting no cross-user read/write on the agent surface (recording the stdio-trusted v1 boundary)
  - Acceptance: privacy lifecycle scenarios pass; cross-tenant access attempt is rejected
  - QA: run scenarios; attempt a cross-user read and show rejection
  - Commit: `test(validation): privacy and tenancy isolation coverage`
  - Register: T-A-08, T-A-09

- [x] 32. Make count-pinning tests derive from live sources (discovered during W1)
  - Files: `tests/mcp/test_readonly_server.py`, `tests/validation/test_scenario_outcome_audit.py`, `tests/validation/test_tool_desc_audit.py`, `tests/validation/test_tool_similarity_audit.py`, `tests/validation/test_validation_coverage.py`
  - Change: replace hard-coded counts (tool count 147, scenario count 138, step total 484, `147/147`) with values derived from live sources (`_full_tool_list()`, `load_scenarios()`), so the plan's own additions (Todos 9/10/12/19/20/30/31) cannot break them
  - Acceptance: the listed tests pass; adding or removing a tool/scenario no longer requires editing these tests
  - QA: run the listed tests; temporarily assert `len(_full_tool_list())+1` in one test, observe it fail for the right reason, restore; resync the doc test count so `doc_inventory.py --check` exits 0
  - Commit: `test(validation): derive counts from live sources`
  - Register: VT-05

- [x] 33. Fix test regressions from the category migration and the new coverage tool (discovered during W2)
  - Files: `tests/validation/test_error_message_audit.py`, `tests/validation/test_validation_delivery.py`
  - Change: `test_all_error_sites_parsed` / `test_call_site_kind_breakdown` pin stale counts (116/76; live 117/77 after `get_coverage_report` added an error site) — assert structural invariants derived from the parsed result (no `_error_dict`; kinds sum to total; required kinds present) instead of exact numbers. `test_enduser_journey_scenario_loads` pins the pre-migration category `enduser` — assert the scenario loads and its `category` is one of the 5-value taxonomy (or assert by `name`), not the old value.
  - Acceptance: `tests/validation` is green; no exact error-site count is hard-coded
  - QA: run the three tests; resync the documented test count so `doc_inventory.py --check` exits 0
  - Commit: `test(validation): derive error-site counts; align journey category`
  - Register: VT-05, T-B-01

- [x] 34. Fix `_normalize_param_aliases` breaking generic `(name, arguments)` handlers (discovered during W4)
  - Files: `src/autoinfo/mcp/server.py` (`_normalize_param_aliases` ~11932)
  - Change: for handlers whose signature is the generic `(name, arguments)` form, `_handler_accepts(tool_name, "user_id")` is False, so the alias is collapsed onto `end_user_id` and handlers that read `arguments["user_id"]` (e.g. `export_user_data`, `delete_user_data(purge=True)`) raise KeyError → canonical `ValidationError`. Make alias normalization a no-op (or resolve to the canonical `user_id`) when the handler takes the generic signature, so both spellings still reach the handler intact. Cover the same class for the `domain`/`name` aliases.
  - Acceptance: MCP `export_user_data` and `delete_user_data(purge=True)` succeed; `data-privacy.yaml` passes 6/6; alias regression tests pass; existing MCP tests stay green
  - QA: dispatch both tools with `user_id` and `end_user_id`; run `data-privacy` scenario; `doc_inventory.py --check` exit 0
  - Commit: `fix(mcp): keep user_id alias for generic handlers`
  - Register: T-S-03

---

## Final verification wave

- [x] F1. Verify the spine is measurable: `get_coverage_report` classifies 100% of the **126** stage×user cells + 72 expectations with zero unclassified; `list_validation_scenarios` exposes stage/level for 100 % of the live scenario count (baseline 138); the keystone catalog and the root spec both define 18 lifecycle stages.
  - Evidence: report + listing dump + catalog diff; a planted unclassified cell and a missing B1.7 column each yield non-zero exit.

- [x] F2. Verify the suite cannot lie: `diff_scenario_runs` classifies two identical failing runs correctly; stage×user and category×pyramid reports fail on injected gaps; `error_message_audit.py` fails on a planted raw-exception site.
  - Evidence: four RED→GREEN runs.

- [x] F3. Verify the agent-native surface: 100 % of declared tools (dynamic; 146 baseline, 149 after Todos 5/12/20) return the canonical envelope, expose `outputSchema`, carry normalized params/enums; CLI parity + REST coverage complete; `list_tools` hides director-only tools.
  - Evidence: envelope test, schema test, audit floors, parity report, REST matrix, non-director test.

- [x] F4. Verify recoverability and traceability: per-step timeout cuts a hanging step with no orphan worker; a mid-pipeline failure resumes from checkpoint; one correlation ID reconstructs a full lifecycle run; the aggregate run feeds `validation_report.py`.
  - Evidence: targeted runs + artifacts + report.

- [x] F5. Verify AX metrics are gated: all six metrics emitted and CI fails when any threshold is breached.
  - Evidence: metric report + intentionally breached run.

- [x] F6. Verify documentation integrity: consistency checker passes across README/AGENTS/server-docstring/tool-list/scenario-counts/pytest-count; no current doc cites the superseded promotion rule.
  - Evidence: `scripts/doc_inventory.py --check` output + grep.

- [x] F7. Verify the review-added coverage: privacy/export-delete, multi-tenant isolation, REST, build/release, and model/vendor agnosticism each have a passing scenario or an explicit committed disposition.
  - Evidence: scenario results + dispositions in the coverage report.

---

## Must NOT have

- No re-architecture of the collection pipeline or KB tiers; gaps are about measurement, contract, recovery, and traceability.
- No hidden regeneration-and-select ("best of N") to make coverage look green.
- No marking a red cell `unconfigured` to avoid work — unclassified stays zero; blocked/out-of-scope carries a recorded rationale.
- No hand-maintained replacement for any generated inventory.
- No new user-facing feature beyond what the spine/methodology require.
- No acceptance criterion or doc fact hard-codes a count the plan's own work changes: tools are **dynamic via `_full_tool_list()`**, scenarios are **dynamic via the live loader**, and the authoritative spine is **126** (never a hard-coded 119, 138, or 146).

---

## Outcome (promoted 2026-09-14)

**Shipped**: commit `2e1052d` ("feat(validation): close agent-oriented gap register") delivered the 62-gap register across 7 waves (W0 Truth, W1 Schema, W2 Harness, W3 Tool contract, W4 Coverage, W5 Metrics, W6 Docs). Concrete results:

- **Scenario library 138 to 159** (86 functional + 73 regression): new red-team, agent-interaction, performance, recoverability, privacy, tenancy, and REST/build/vendor surface layers.
- **Scenario schema**: required `pipeline_stage` / `user_level` / `category` / `pyramid_layer`; a 126-cell stage-by-user coverage report and a 20-cell category-by-pyramid report, both with zero-unclassified gates.
- **Agent-native surface**: the canonical `{success,data}` / `{success,error:{...}}` envelope on every tool, `outputSchema` on 100% of declared tools, param/alias and ErrorCode normalization, CLI `--json` / REST / build / vendor parity, and director-only tool gating.
- **Honest harness**: the `diff_scenario_runs` classification fix, the `error_message_audit.py` truth gate (0 raw sites), per-step timeouts, universal cancellation, checkpoint/resume (`--resume-from`), an aggregate suite run, and session traceability plus `get_run_decisions`.
- **AX metrics**: M-01..M-06 instrumented in `scripts/ax_metrics.py` and gated in CI.
- **Documentation integrity**: stale counts corrected, the broken README "Known Limitations" section repaired, and `scripts/doc_inventory.py --check` extended.

**Reconciliation (plan body vs commit/ledger counts)**:

The wave table in §9 sequences **31** todos (1-31). Three more were discovered mid-flight and appended: 32 (count-pinning tests derive from live sources), 33 (category-migration test regressions), and 34 (`_normalize_param_aliases` generic-handler fix). That is **34** numbered todos. The commit message and the orchestrator ledger report **41** tasks, which is 34 numbered todos plus the 7-item final verification wave (F1-F7).

F1-F7 are the **final verification wave**, separate from the W0-W6 build sequence. The plan marks each `[x]` but the plan body never contains the literal string `APPROVE` (grep: 0 hits). The literal verdict lives outside the plan: commit `2e1052d`'s message states "41/41 tasks, F1-F7 APPROVE", and the orchestrator ledger `.omo/boulder.json` (work `agent-oriented-gap-register-b8b283f0`) tracks the final-wave task sessions. This separation is by design. The plan is the decomposition; the verdict is recorded by the orchestrator. Together, the plan body plus the commit message are the in-repo record.

**Lessons backfilled where**:

- `docs/adr/0005-unified-success-error-envelope.md`: canonical envelope decision extended to all tools.
- `docs/dev/validation-scenario-contract.md`: required `pipeline_stage`/`user_level`, per-step timeout semantics, and recovery/partial-pass/leak-guard rules.
- `docs/dev/testing-layers.md` (new): unit/component/e2e/red_team layer boundaries.
- `docs/dev/cli-mcp-rest-parity.md`: REST and build/release coverage.
- `docs/dev/cross-dimensional-catalog.md` and `docs/dev/specs/user-lifecycle-definition.md`: 18-stage spine reconciled (B3.4/B3.5 ratified, B1.7 column added).
- `README.md` and `AGENTS.md`: counts synced to live sources, consistency checker extended in `scripts/doc_inventory.py`.
- `.opencode/skills/validation-runner-skill/SKILL.md` and `.opencode/skills/doc-manager-skill/SKILL.md`: scenario-count and doc-count facts synced.

**Residuals**: none claimed. The wave's own "Must NOT have" constraints held: no re-architecture of the collection pipeline or KB tiers, no best-of-N regeneration, no red cell marked `unconfigured` to avoid work, and no hard-coded count that the work itself changes.
