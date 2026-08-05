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
steps:
  - name: "human readable step name"   # required
    kind: mcp                         # optional: mcp (default) | cli | http
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
  failed), `failed` (any step failed).
- summary: `{passed, failed, unconfigured, total}`.

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
   `enduser_create`), use clearly-safe test data and clean up within the same scenario
   (e.g. `enduser_create` → `enduser_delete`, `add_source` → `remove_source`).
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
declarations in `src/autoinfo/mcp/server.py` (141 tools) against `kind: mcp` steps in
the scenario library.

## Scenario inventory (as of 2026-08-05)

47 scenario files in `src/autoinfo/mcp/scenarios/`:

- **System/Discovery**: system-health, discovery, meta-validation
- **Errors**: error-boundary
- **Domain/Source/Topic/Keyword**: domain-management, source-management,
  topic-management, keyword-management
- **Collection/Processing/Cron**: collection, collectors-e2e, processing,
  cron-schedules, collection-monitor
- **KB**: kb-access, kb-draft, kb-versioning, kb-graph, kb-import-export,
  kb-lifecycle, kb-extraction
- **Output**: output-digest-report, output-ebook, output-tutorial-presentation,
  output-simplify-recommend, output-discovery, output-column
- **Delivery/End-user/Cost**: delivery-channels, delivery-schedules,
  enduser-lifecycle, enduser-preferences, cost-budget, products-billing
- **Privacy/Lifecycle/Observability**: data-privacy, observability,
  agent-callbacks, webhooks-alerts, quality-gate-config, projects-config
- **LLM-gated**: llm-gated (classify_cefr, suggest_keywords, cefr_batch)
- **CLI**: cli-core, cli-content, cli-ops, cli-extra, cli-llm
- **REST**: rest-api
- **M7 additions**: sources-gap-closure (3 new source-type registrations),
  output-column (report_type=column, LLM-gated), sources-a6-keyed
  (FRED/Finnhub, env-gated)

Coverage: 141/141 MCP tools (100%), all 28 CLI command groups, 8 REST API endpoints,
plus collector platform reachability probes (collectors-e2e) and G4/G5 gate flags
(processing, LLM-gated).
Status profile (no LLM key): 36 passed / 0 failed / 8 unconfigured (LLM-gated) at
44 scenarios; the 3 M7 additions (sources-gap-closure passed, output-column +
sources-a6-keyed unconfigured without keys) bring the full 47-scenario profile to
37 passed / 0 failed / 10 unconfigured when no BYOK keys are set.
