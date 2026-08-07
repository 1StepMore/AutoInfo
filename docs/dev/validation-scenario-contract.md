# Agent-Native Validation — Scenario Authoring Contract

This document defines the exact contract for authoring validation scenario YAML files
in `src/autoinfo/mcp/scenarios/`. It is the canonical reference for the Agent-native
validation toolset (`list_validation_scenarios` / `run_validation_scenario`).

## Purpose

Validation must be **real**: scenarios execute through the MCP surface (plus real CLI
subprocesses and real HTTP requests), never mocked. Every step makes an actual call and
asserts on the standard `{success, data}` envelope. LLM-dependent steps run a real model
call via `llm_assert`. When required environment variables (BYOK keys) are missing, the
scenario reports `unconfigured` — it is never silently skipped and never fake-passed.

## Execution context

Scenarios run from the **project root** (`/mnt/d/贯维/AutoInfo`) where `.autoinfo/config.yaml`
exists and the `medical-research` domain is configured with 5 sources, 3 topics, and
populated `knowledge/medical-research/01-Raw/` data. This is the REAL operation context.
Do NOT write "empty state" assertions — tools return real data here.

## Scenario file schema

```yaml
name: kebab-case-unique-id          # required
description: "human readable"       # required
category: <one of: system|discovery|source|topic|collection|kb|output|delivery|
                    enduser|cost|privacy|lifecycle|observability|quality|cli|http|errors>
requires_env: []                    # optional list of env var names; if ANY missing
                                    # the WHOLE scenario reports status=unconfigured
                                    # (Director User BYOK obligation — never skipped)
requires_http: []                   # optional list of URLs (e.g. http://127.0.0.1:8741/health);
                                    # if ANY URL is unreachable the scenario reports
                                    # status=unconfigured with a reason instead of
                                    # failing (env preconditions are not code defects,
                                    # #157).  Used for REST-server-gated scenarios.
cleanup_steps:                      # optional list of steps (same schema as `steps`)
                                    # run AFTER the main steps on pass AND on fail
                                    # (best-effort); reported under `cleanup` and
                                    # never influence the scenario status.  Use for
                                    # removing state the scenario created.
min_passing: 5                      # optional int: minimum number of main steps that
                                    # must pass for the scenario to be `passed`; lets
                                    # a scenario degrade gracefully when a subset of
                                    # steps legitimately cannot all run (partial-pass).
pass_ratio: 0.8                     # optional float (0.0-1.0): alternative partial-pass
                                    # policy — fraction of main steps that must pass.
                                    # Only one of min_passing / pass_ratio should be
                                    # set; when neither is set, ALL steps must pass.
regression: true                    # optional bool: marks this scenario as a
                                    # regression scenario.  True for files placed in
                                    # the scenarios/regression/ subdirectory (auto-
                                    # loaded via recursive glob).  Regression
                                    # scenarios are reported with a "(regression)"
                                    # suffix in verdicts and a dedicated
                                    # `## Regression failures` report section.
regression_issue: "#NNN"            # optional (required when regression: true): the
                                    # issue/PR number this scenario guards against
                                    # regressing, e.g. "#119".
steps:
  - name: "human readable step name"   # required
    kind: mcp                         # optional: mcp (default) | cli | http
    timeout_seconds: 30               # optional int: per-step wall-clock budget; a
                                      # step exceeding it fails fast instead of
                                      # hanging the whole run (default: no timeout).
    recovery_steps:                   # optional list of steps (same schema as this
                                      # step); run AFTER this step's primary failure
                                      # in an attempt to recover, then re-evaluate.
    collect_artifacts:                # optional list of output artifacts to persist
                                      # for post-run inspection (e.g. file paths the
                                      # step wrote); used on output scenarios.
    # --- for kind=mcp ---
    tool: add_source                  # required: real MCP tool name
    arguments: {...}                  # required: real args the handler accepts
    # --- for kind=cli ---
    command: "autoinfo sources list"  # required: shell command, real subprocess
    # --- for kind=http ---
    method: GET                       # required
    url: "http://127.0.0.1:8741/health"   # required (REST server must be running)
    http_options: {}                  # optional: httpx kwargs (headers, json, params)
    # --- expect (all optional) ---
    expect:
      success: true                   # optional, default true
      # mcp envelope assertions:
      data_has: ["domains"]           # keys that must exist in envelope.data (dict)
      error_code: "UnknownTool"       # when success expected False: envelope.error.code
      error_actionable: false         # when success expected False: envelope.error.actionable must equal this boolean (asserts the remediation hint)
      # cli assertions:
      exit_code: 0                    # expected subprocess returncode
      stdout_has: ["substring"]       # substrings that must appear in stdout
      stderr_has: ["substring"]       # substrings that must appear in stderr
      # http assertions:
      status_code: 200                # expected HTTP status
      json_has: ["status"]            # keys that must exist in response JSON body
      # LLM semantic assertion (REAL model call — never mocked):
      llm_assert: "NL assertion the LLM judges against the tool output"  # optional
```

## Semantics

- **`success`**: envelope `{success: bool}`. For cli: exit_code==0 ⇒ success=True.
  For http: 2xx/3xx ⇒ success=True.
- **`requires_env`**: if any listed env var is unset, the scenario returns
  `status: unconfigured` with per-step unconfigured results. This is the CORRECT
  behavior — the Director User must provide BYOK keys during onboarding. Never write
  scenarios that silently skip; use requires_env to surface unconfigured.
- **`requires_http`**: if any listed URL is unreachable, the scenario returns
  `status: unconfigured` (not failed) with a reason per precondition. REST-server
  and network-gated scenarios use this so a missing local server (e.g. uvicorn on
  port 8741) or an offline service does not pollute the failed count — env
  preconditions are not code defects (#157).
- **`cleanup_steps`**: optional top-level list using the same step schema as
  `steps`. The executor runs them after the main steps **regardless of the main
  outcome** (pass or fail) — so scenario-created state is removed even when a
  middle step failed. Each cleanup step is a real call (mcp/cli/http, same as
  `steps`) and is asserted the same way, but cleanup results are reported under
  `cleanup: {summary, steps}` in the result envelope and **never influence the
  scenario status**. When `requires_env` is missing, nothing ran, so cleanup is
  skipped. Scenarios that create persistent state MUST clean up after
  themselves in `cleanup_steps` (verify-before-delete provenance checks are
  strongly recommended so real user data is never touched).
- **`timeout_seconds`** (per step, optional): a wall-clock budget in seconds. A
  step that exceeds its budget is marked failed with a timeout reason and the
  executor moves on — a runaway step can no longer hang the whole scenario run.
- **`recovery_steps`** (per step, optional): a list of steps using the same step
  schema, run **after the primary step fails** in an attempt to recover. Each
  recovery step is a real call and is asserted the same way as a regular step.
  If the recovery steps pass, the step is reported as recovered (the failure is
  still recorded in the per-step trace); if they fail, the step fails. Recovery
  results are reported under the step's `recovery` key in the per-step trace and
  never inflate the pass count on their own.
- **`min_passing` / `pass_ratio`** (top-level, optional): partial-pass policy.
  `min_passing` (int) declares the minimum number of main steps that must pass;
  `pass_ratio` (float 0.0-1.0) declares the fraction of main steps that must
  pass. Set at most one. When neither is set, ALL main steps must pass. A
  scenario whose passed count meets the policy is `passed` even when some steps
  failed; failed steps still surface in the report. Use for scenarios where a
  subset of steps is legitimately environment-dependent.
- **`regression` / `regression_issue`** (top-level, optional): marks a
  regression scenario guarding a specific bug. `regression: true` requires
  `regression_issue: "#NNN"`. Files in the `scenarios/regression/` subdirectory
  are auto-loaded via recursive glob and conventionally set both fields. In
  reports, regression scenarios appear with a "(regression)" suffix in the
  verdicts table and a dedicated `## Regression failures` section lists any
  regression scenario that failed (root cause + the guarded issue).
- **`collect_artifacts`** (per step, optional): a list of artifact references the
  step produced (e.g. written file paths). Output scenarios use it so generated
  digests/reports/exports persist for post-run inspection in validation delivery.
- **`llm_assert`**: when present and the step's structural assertions passed, the
  executor makes a REAL LiteLLM call (model from config) to judge the tool output
  against the NL assertion. If no LLM key → step reports `unconfigured`. Add
  `requires_env: [AUTOINFO_LLM_API_KEY]` at scenario level for LLM-dependent scenarios.
- **`kind: cli`**: real subprocess via `subprocess.run(command, shell=True)`. The
  command MUST work from project root. Use `autoinfo ...` (installed console script).
- **`kind: http`**: real HTTP request via httpx. The REST server must be running
  (`uvicorn autoinfo.api.server:app --port 8741`) for these to pass.

## Status aggregation

- scenario status: `passed` (no failed), `unconfigured` (any step unconfigured, none
  failed), `failed` (any step failed). With a partial-pass policy (`min_passing` /
  `pass_ratio`), `passed` also applies when the passed-step count meets the policy
  despite some failed steps.
- summary: `{passed, failed, unconfigured, total}`.

## Per-step trace and report sections

- Every executed step is recorded with `step_index`, `duration`, `arguments`,
  `trace_id`, and (for LLM steps) `llm_meta` (model, tokens, duration), so a
  failing run can be reconstructed exactly.
- The validation report (`scripts/validation_report.py`) emits:
  - **Verdicts** — per-scenario result table (regression scenarios carry a
    "(regression)" suffix).
  - **Executive summary** — aggregate pass/fail/unconfigured counts.
  - **`## Regression failures`** — every failed regression scenario with its
    guarded issue number.
  - **`## Blockers`** — root-cause analysis for each failed scenario, including
    the failing step's details from the per-step trace.
  - **`## Per-step trace`** — full step-by-step execution trace.
  - **Appendix pointer** — link to the raw results.

## Authoring rules (MANDATORY)

1. **Verify every step before finalizing**: run the scenario via the MCP tool
   `run_validation_scenario(scenario="NAME")` (or call the executor directly with a
   real dispatch) from project root. Adjust assertions to match REAL responses.
2. **Real tool signatures**: read `src/autoinfo/mcp/server.py` `call_tool()` dispatch
   and the handler `def _handle_X(...)` signature for exact argument names. Some tools
   require `domain`, some don't take it (e.g. `get_source_health` takes `source_id`).
   VERIFY each.
3. **No mocks, no compromise**: every assertion must be checkable against real
   tool/LLM/HTTP responses. If a tool needs an env var, gate the scenario with
   `requires_env` (unconfigured is honest; a fabricated pass is not).
4. **No destructive or state-corrupting side effects**: prefer idempotent reads
   (`list_*`, `get_*`, `search_*`). For mutating tools (`add_*`, `create_*`,
   `enduser_create`), use clearly-safe test data and clean up within the same
   scenario (e.g. `enduser_create` → `enduser_delete`, `add_source` →
   `remove_source`). For state that must survive to the last step (e.g. a KB
   entry created in step 1 and rejected in step 5), declare `cleanup_steps`
   so the state is removed even when a middle step fails. The `kb-draft`
   scenario is the reference pattern: fully self-contained steps operating
   only on the scenario's own deterministic entry ids, plus a `cleanup_steps`
   CLI step that verifies provenance markers before purging.
5. **Coverage**: every implemented MCP tool must appear as a `kind: mcp` step in at
   least one scenario. Track coverage with the audit script (see below).
6. **YAML validity**: scenarios must load via `load_scenarios()` with no errors.
7. Keep 2-6 steps per scenario. Split large tool lists into multiple scenario files.
8. Category should match the MCP category from the inventory where possible.

## Coverage audit

Run after writing scenarios:
```bash
python3 scripts/coverage_audit.py   # reports covered/missing MCP tools
```
Every tool must disappear from the MISSING list. The audit counts `Tool(name=...)`
declarations in `src/autoinfo/mcp/server.py` (142 tools) against `kind: mcp` steps in
the scenario library. The audit also prints a `Regression scenarios: N (issues: ...)`
metric — every scenario in `scenarios/regression/` must carry `regression: true` and
a `regression_issue`, and the audit lists any that don't.

## Scenario inventory (as of 2026-08-07)

59 scenario files in `src/autoinfo/mcp/scenarios/` (54 functional flat in `scenarios/`
+ 5 regression in `scenarios/regression/`):

- **System/Discovery**: system-health, discovery, meta-validation
- **Errors**: error-boundary
- **Domain/Source/Topic/Keyword**: domain-management, source-management,
  topic-management, keyword-management
- **Collection/Processing/Cron**: collection, collectors-e2e, processing,
  cron-schedules, collection-monitor
- **KB**: kb-access, kb-draft, kb-versioning, kb-graph, kb-import-export,
  kb-lifecycle, kb-extraction, kb-promote (E8: Draft→Wiki promotion end to end)
- **Output**: output-digest-report, output-ebook, output-tutorial-presentation,
  output-simplify-recommend, output-discovery, output-column
- **M7 additions**: sources-gap-closure (3 new source-type registrations),
  output-column (report_type=column, LLM-gated), sources-a6-keyed
  (FRED/Finnhub, env-gated)
- **2026-08-07 additions (#156)**: output-premium-products (premium-briefing /
  magazine-digest / enterprise-briefing via `product_template`, LLM-gated),
  sources-coverage (academic + all 27 source platforms; completes products 8/8,
  formats 7/7, sources 27/27 in the E8 matrix)
- **Delivery/End-user/Cost**: delivery-channels, delivery-schedules,
  enduser-lifecycle, enduser-preferences, cost-budget, products-billing,
  enduser-journey (E8: full B1 lifecycle with UX metrics)
- **Privacy/Lifecycle/Observability**: data-privacy, observability,
  agent-callbacks, webhooks-alerts, quality-gate-config, projects-config
- **LLM-gated**: llm-gated (classify_cefr, suggest_keywords, cefr_batch)
- **CLI**: cli-core, cli-content, cli-ops, cli-extra, cli-llm
- **REST**: rest-api
- **Regression (scenarios/regression/)**: regression-collect-int-id (#104),
  regression-llm-key-resolution (#119), regression-period-enum (#126),
  regression-report-structure (#121), regression-source-301 (#135). Each carries
  `regression: true` + `regression_issue`, is auto-loaded via recursive glob, and
  appears with a "(regression)" suffix in verdicts plus a `## Regression failures`
  report section.

Coverage: 142/142 MCP tools (100%), all 28 CLI command groups, 8 REST API endpoints,
plus collector platform reachability probes (collectors-e2e) and G4/G5 gate flags
(processing, LLM-gated).
Status profile depends on BYOK keys: LLM-gated and env-gated scenarios
(requires_env) report `unconfigured` without the keys (never silently skipped);
partial-pass scenarios (`min_passing`/`pass_ratio`) can pass with a degraded step
set. Run `run_validation_scenario` per scenario or `scripts/coverage_audit.py` for
the aggregate regression metric.
