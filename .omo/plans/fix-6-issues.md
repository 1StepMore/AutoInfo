# Fix 6 GitHub Issues (#4–#9) — AGENTS.md + ErrorCode + MCP Tooling

## TL;DR

> **Quick Summary**: Fix 6 verified GitHub issues spanning documentation staleness (AGENTS.md), technical debt (47 fragmented error_code strings), MCP schema gaps (missing default/required/enum), missing functionality (init_project tool), and incomplete documentation (discovery flow, common patterns).
>
> **Deliverables**:
> - `src/autoinfo/mcp/errors.py` — new ErrorCode enum + ErrorResponse TypedDict
> - `src/autoinfo/mcp/server.py` — refactored 47 error_code strings → ErrorCode, 4 bare-"error" handlers fixed, 5+ schema fixes, new `init_project` tool
> - `src/autoinfo/mcp/routes.py` — aligned ErrorResponse to use ErrorCode
> - `AGENTS.md` — fully rewritten Status section, Tool Discovery table, Discovery flow, Common Patterns (10+ patterns)
> - 9 test files — updated assertions for ErrorCode refactor
>
> **Estimated Effort**: Medium
> **Parallel Execution**: YES — 3 waves
> **Critical Path**: Task 1 (errors.py) → Task 5 (error_code refactor) → Task 6 (verification)

---

## Context

### Original Request

The user identified 6 GitHub issues after completing the v1.2 release. All 6 were independently verified as real gaps against the codebase:

| # | Priority | Title | Type |
|:--|:---------|:------|:-----|
| #4 | **P0** | AGENTS.md says "Greenfield project" (stale since v0.1) | Documentation |
| #5 | P1 | Centralized ErrorCode system (47 scattered strings, inconsistent shapes) | Refactoring |
| #6 | P1 | MCP missing `init_project` tool (agent cannot bootstrap project) | New feature |
| #7 | P2 | Discovery flow missing `health_check` first step | Documentation |
| #8 | P2 | MCP input schema missing default/required/enum/description | Bug fix |
| #9 | P3 | Common Patterns list too few (3 patterns, needs 10+) | Documentation |

### Interview Summary

**Key Decisions**:
- **ErrorCode location**: New `src/autoinfo/mcp/errors.py` module (not inline in server.py)
- **init_project approach**: Full MCP tool wrapping CLI `_run_init()` — domain param only, idempotent (skips if .autoinfo/ exists), non-interactive
- **Test strategy**: Tests-after. All 9 affected test files updated in same wave as error_code refactoring
- **Backwards compatibility**: ErrorCode enum values MUST match current string literals exactly (e.g., `ErrorCode.NOT_FOUND = "NotFound"`)

**Metis Review** (key findings incorporated):
- 4 handlers use bare `"error"` key (not just 1): `_handle_list_domains`, `_handle_list_available_models`, `_handle_list_projects`, `_handle_list_active_collections`
- 4 dynamic `type(exc).__name__` cases in server.py → replaced with `ErrorCode.INTERNAL_ERROR`
- 20+ unique error_code string values cataloged for enum membership
- Wave restructured: Wave 1 = non-test-breaking changes only; Wave 2 = error refactor + test updates together
- `test_mcp_v2.py:136` asserts `"error" in result` — must update to `"error_code"` in same wave as handler fix

---

## Work Objectives

### Core Objective
Fix all 6 GitHub issues (#4–#9) across documentation, error handling infrastructure, MCP tooling, and schema completeness, ensuring backward compatibility of error strings.

### Concrete Deliverables
- `src/autoinfo/mcp/errors.py` — `ErrorCode(str, Enum)` with all current string values, `ErrorResponse` TypedDict
- `src/autoinfo/mcp/server.py` — all 47 error_code strings → enum refs, 4 bare-"error" handlers fixed, 5+ schema fixes, `init_project` tool
- `src/autoinfo/api/routes.py` — `ErrorResponse.error_code` uses `ErrorCode` type hint
- `AGENTS.md` — updated Status section, tool counts, directory tree, Discovery flow, Common Patterns (10+)
- `tests/` — 9 test files updated with new error_code assertions

### Definition of Done
- [ ] `pytest -v tests/` — all 825+ tests pass, 0 failures
- [ ] `grep '"error": str(exc)' src/autoinfo/mcp/server.py` — 0 results (all 4 handlers fixed)
- [ ] `grep 'error_code.*=' src/autoinfo/mcp/errors.py` — `ErrorCode` enum with all 20+ values
- [ ] `grep 'Greenfield' AGENTS.md` — 0 results (status updated)
- [ ] `grep 'health_check' AGENTS.md` — appears before `list_domains` in discovery flow
- [ ] Count of common patterns in AGENTS.md >= 10

### Must Have
- ErrorCode enum preserves exact current string values (backwards compat)
- All 4 bare-"error" handlers fixed (not just `_handle_list_domains`)
- init_project MCP tool is idempotent (safe to call when .autoinfo/ exists)
- init_project MCP tool is non-interactive (domain param only)
- `test_mcp_v2.py:136` updated with `"error_code"` assertion in SAME task as handler fix
- AGENTS.md Status section no longer says "Greenfield project"
- AGENTS.md Discovery flow starts with `health_check()`
- AGENTS.md Common Patterns has 10+ patterns total
- Fix 5 crash-risk tools (handler optional param but schema no default)

### Must NOT Have (Guardrails)
- ⛔ No changing error_code string values (exact preservation required)
- ⛔ No refactoring error handling patterns beyond enum conversion
- ⛔ No new try/except blocks in existing code
- ⛔ No README.md changes (issue #4 targets AGENTS.md specifically)
- ⛔ No tool schema "improvements" beyond the specific gaps identified
- ⛔ No interactive prompts in init_project MCP tool
- ⛔ No reorganizing AGENTS.md structure (fix specific sections only)
- ⛔ No writing to 03-Wiki or other KB pipeline operations

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed.

### Test Decision
- **Infrastructure exists**: YES (pytest, 825+ existing tests)
- **Automated tests**: Tests-after (update existing tests, add new tests for new code)
- **Framework**: pytest (existing)
- **Tests-after approach**: Each implementation task includes test updates + new test cases

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.omo/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Library/Module**: Bash (pytest) — Import, call functions, assert values
- **MCP Tools**: Bash (call_tool or direct handler invocation) — Verify response shape
- **Documentation**: Bash (grep) — Verify specific patterns absent/present
- **Integration**: Bash (pytest full suite) — All tests pass

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately — non-test-breaking, 4 parallel):
├── Task 1: errors.py module + unit tests
├── Task 2: MCP schema fixes (default/required/enum/description)
├── Task 3: init_project MCP tool + tests
└── Task 4: Comprehensive AGENTS.md rewrite (#4, #7, #9, #6 docs)

Wave 2 (After Wave 1, depends on Task 1 — error refactor):
├── Task 5: Refactor error_code strings + fix 4 "error" handlers + update test files + align routes.py

Wave 3 (After Wave 2 — integration verification):
└── Task 6: Full test suite run + QA scenario verification

Wave FINAL (After ALL tasks — 4 parallel reviews):
├── F1: Plan compliance audit (oracle)
├── F2: Code quality review (unspecified-high)
├── F3: Real manual QA (unspecified-high)
└── F4: Scope fidelity check (deep)
-> Present results -> Get explicit user okay

Critical Path: Task 1 → Task 5 → Task 6 → F1-F4 → user okay
Parallel Speedup: ~60% faster than sequential
Max Concurrent: 4 (Wave 1)
```

### Dependency Matrix

- **1**: - → 5, 2
- **2**: - → none
- **3**: - → none
- **4**: - → none
- **5**: 1 → 6
- **6**: 5 → F1-F4

### Agent Dispatch Summary

- **Wave 1**: **4** — T1 → `deep`, T2 → `deep`, T3 → `deep`, T4 → `deep`
- **Wave 2**: **1** — T5 → `deep` (high-risk, needs thoroughness)
- **Wave 3**: **1** — T6 → `unspecified-high`
- **FINAL**: **4** — F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

> **FORMAT**: Bare-number labels (`1.`, `2.`). Final Wave uses `F1.`, `F2.`. Never `T1.` or `Task 1.`.
> **A task WITHOUT QA Scenarios is INCOMPLETE.**

- [x] 1. Create `src/autoinfo/mcp/errors.py` with ErrorCode enum + ErrorResponse TypedDict

  **What to do**:
  - Create new file `src/autoinfo/mcp/errors.py` with:
    - `ErrorCode(str, Enum)` class enumerating ALL current error_code string values:
      - `NOT_FOUND = "NotFound"`, `DOMAIN_NOT_FOUND = "DomainNotFound"`, `VALIDATION_ERROR = "ValidationError"`, `INVALID_SOURCE_ID = "InvalidSourceId"`, `SOURCE_NOT_FOUND = "SourceNotFound"`, `TIMEOUT = "Timeout"`, `TOPIC_NOT_FOUND = "TopicNotFound"`, `KEYWORD_NOT_FOUND = "KeywordNotFound"`, `EMAIL_NOT_ENABLED = "EmailNotEnabled"`, `EMAIL_SEND_FAILED = "EmailSendFailed"`, `INVALID_CRON_EXPRESSION = "InvalidCronExpression"`, `SCHEDULE_ALREADY_EXISTS = "ScheduleAlreadyExists"`, `SCHEDULE_NOT_FOUND = "ScheduleNotFound"`, `NOT_PUBLISHED = "NotPublished"`, `COLLECTION_FAILED = "CollectionFailed"`, `PROCESSING_FAILED = "ProcessingFailed"`, `INVALID_SECTION = "InvalidSection"`, `UNKNOWN_TOOL = "UnknownTool"`, `INTERNAL_ERROR = "InternalError"`
    - `ErrorResponse` TypedDict with `error_code: ErrorCode`, `message: str`, `actionable: bool`
    - Helper function `error_dict(exc: Exception | ErrorCode, message: str = "", actionable: bool = True) -> dict[str, Any]`
    - Helper function `error_response(...) -> list[TextContent]`
    - Ensure `from __future__ import annotations` and proper typing
  - Re-export `ErrorCode` and `ErrorResponse` in `src/autoinfo/mcp/__init__.py`
  - Write unit tests:
    - `tests/test_errors.py`:
      - Test every enum value matches expected string
      - Test `error_dict()` returns correct shape (no `"error"` key, only `"error_code"`)
      - Test `error_response()` returns `list[TextContent]` with valid JSON
      - Test `INTERNAL_ERROR` for unknown exception types

  **Must NOT do**:
  - Do NOT change any string values (must match exactly for backwards compat)
  - Do NOT add any error_code values not already in the codebase
  - Do NOT modify server.py yet (handled in Task 5)

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Need systematic catalog of all 20+ error_code values from server.py
  - **Skills evaluated but omitted**: none

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3, 4)
  - **Blocks**: Task 5
  - **Blocked By**: None (can start immediately)

  **References**:
  - `docs/dev/founder-expectations.md` — Contains v1.2 spec (especially §2.5 error handling requirements)
  - `src/autoinfo/mcp/server.py:2120-2148` — Current `_error_dict()` and `_error_response()` helpers — these are the patterns to formalize
  - `src/autoinfo/mcp/__init__.py` — Currently empty (just docstring) — needs re-export

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY)**:
  \`\`\`
  Scenario: ErrorCode enum values correct
    Tool: Bash (pytest)
    Preconditions: errors.py exists
    Steps:
      1. python -c "from src.autoinfo.mcp.errors import ErrorCode; assert ErrorCode.NOT_FOUND.value == 'NotFound'"
      2. python -c "from src.autoinfo.mcp.errors import ErrorCode; assert ErrorCode.VALIDATION_ERROR.value == 'ValidationError'"
      3. python -c "from src.autoinfo.mcp.errors import ErrorCode; assert ErrorCode.INTERNAL_ERROR.value == 'InternalError'"
    Expected Result: All assertions pass
    Evidence: .omo/evidence/task-1-enum-values.txt

  Scenario: ErrorResponse shape is correct
    Tool: Bash (pytest)
    Preconditions: errors.py exists
    Steps:
      1. python -c "from src.autoinfo.mcp.errors import error_dict, ErrorCode; d = error_dict(ErrorCode.NOT_FOUND, 'test msg'); assert 'error_code' in d and 'message' in d and 'actionable' in d; assert 'error' not in d"
    Expected Result: dict has error_code/message/actionable, no bare "error" key
    Evidence: .omo/evidence/task-1-error-dict-shape.txt

  Scenario: Unit tests pass
    Tool: Bash (pytest)
    Preconditions: errors.py and test_errors.py exist
    Steps:
      1. pytest tests/test_errors.py -v
    Expected Result: All tests pass
    Evidence: .omo/evidence/task-1-tests.txt
  \`\`\`

  **Evidence to Capture:**
  - [ ] .omo/evidence/task-1-enum-values.txt
  - [ ] .omo/evidence/task-1-error-dict-shape.txt
  - [ ] .omo/evidence/task-1-tests.txt

  **Commit**: NO (groups with Task 5)
  - Message: `refactor(mcp): add ErrorCode enum and ErrorResponse helpers`
  - Files: `src/autoinfo/mcp/errors.py`, `src/autoinfo/mcp/__init__.py`, `tests/test_errors.py`

---

- [x] 2. Fix MCP input schemas — add missing default/required/enum/description (#8)

  **What to do**:
  - In `src/autoinfo/mcp/server.py`, fix the 64 tool definitions in `list_tools()`:
    - **5 crash-risk tools**: Add `"default"` where handler has an optional param:
      - `get_effective_llm_config.task`: add `"default": null` (since `task: str | None = None`)
      - `get_collection_progress.domain`: add `"default": ""`
      - `list_output_templates.domain`: add `"default": ""`
      - `archive_project.reason`: add `"default": ""`
      - `get_config.section`: add `"default": ""`
    - **5 tools missing `"required"` array entirely**: Add `"required": []` to the 5 tools above (since all their params are optional)
    - **7 other tools missing `"required"`**: Check every tool definition; any with `"properties"` but no `"required"` gets `"required": [...]` or `"required": []`
    - **~12 params missing `"enum"`**: Where description text lists valid values (e.g., `"Source type (api, rss, web)"`), add `"enum": ["api", "rss", "web"]` to the schema. Search for patterns like `"description": "... (x, y, z)"` in tool definitions
    - **`add_sources` nested fields**: Add `"description"` to `name`, `url`, `type`, `domain` in the `items.properties` of the `sources` array parameter
  - Do NOT touch handler logic — schema-only changes
  - Verify with: read each tool's inputSchema to confirm fixes

  **Must NOT do**:
  - Do NOT change tool handler implementations (no behavior changes)
  - Do NOT add schema fixes for tools not listed in the gaps
  - Do NOT change parameter names or types

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Systematic search-and-replace across 64 tool definitions; high attention to detail needed
  - **Skills evaluated but omitted**: none

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3, 4)
  - **Blocks**: None
  - **Blocked By**: None

  **References**:
  - `src/autoinfo/mcp/server.py:2201-2216` — `get_effective_llm_config` (first crash-risk tool, missing required + default)
  - `src/autoinfo/mcp/server.py:2536-2550` — `get_collection_progress` (second crash-risk tool)
  - `src/autoinfo/mcp/server.py:3022-3036` — `list_output_templates` (third crash-risk tool)
  - `src/autoinfo/mcp/server.py:3436-3450` — `archive_project` (fourth crash-risk tool)
  - `src/autoinfo/mcp/server.py:3492-3508` — `get_config` (fifth crash-risk tool)
  - `src/autoinfo/mcp/server.py:2280-2340` — `add_sources` (nested fields missing descriptions)

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY)**:
  \`\`\`
  Scenario: 5 crash-risk tools now have default
    Tool: Bash
    Preconditions: server.py modified
    Steps:
      1. python -c "
    from src.autoinfo.mcp.server import list_tools
    tools = {t.name: t for t in await list_tools() if t.inputSchema.get('properties')}
    for name in ['get_effective_llm_config', 'get_collection_progress', 'list_output_templates', 'archive_project', 'get_config']:
        props = tools[name].inputSchema['properties']
        for pname, pschema in props.items():
            assert 'default' in pschema or pschema.get('required', False), f'{name}.{pname} missing default'
    "
    Expected Result: No assertion errors (all 5 tools have defaults)
    Evidence: .omo/evidence/task-2-defaults.txt

  Scenario: Tools with params have "required" array
    Tool: Bash
    Preconditions: server.py modified
    Steps:
      1. python -c "
    from src.autoinfo.mcp.server import list_tools
    for t in await list_tools():
        props = t.inputSchema.get('properties', {})
        if props:
            assert 'required' in t.inputSchema, f'{t.name} missing required array'
    "
    Expected Result: No assertion errors
    Evidence: .omo/evidence/task-2-required.txt

  Scenario: add_sources nested fields have description
    Tool: Bash (grep)
    Preconditions: server.py modified
    Steps:
      1. grep -A2 '\"name\":' src/autoinfo/mcp/server.py | grep 'description' | head -4
      2. grep -A2 '\"url\":'  src/autoinfo/mcp/server.py | grep 'description' | head -4
    Expected Result: Both name and url in add_sources items have descriptions
    Evidence: .omo/evidence/task-2-descriptions.txt
  \`\`\`

  **Evidence to Capture:**
  - [ ] .omo/evidence/task-2-defaults.txt
  - [ ] .omo/evidence/task-2-required.txt
  - [ ] .omo/evidence/task-2-descriptions.txt

  **Commit**: YES (standalone)
  - Message: `fix(mcp): add default/required/enum/description to tool schemas (#8)`
  - Files: `src/autoinfo/mcp/server.py`

---

- [x] 3. Implement `init_project` MCP tool (#6)

  **What to do**:
  - In `src/autoinfo/mcp/server.py`, add:
    - **Tool definition** in `list_tools()`:
      \`\`\`python
      Tool(
          name="init_project",
          description="Initialize AutoInfo project skeleton (creates .autoinfo/ directory, config, demo domain). Idempotent — safe to call when already initialized.",
          inputSchema={
              "type": "object",
              "properties": {
                  "domain": {
                      "type": "string",
                      "description": "Demo domain name (e.g. medical-research, ai-commercial, language-learning)",
                      "enum": ["medical-research", "ai-commercial", "language-learning"],
                  },
                  "project_name": {
                      "type": "string",
                      "description": "Optional human-friendly project name",
                      "default": "",
                  },
                  "dry_run": {
                      "type": "boolean",
                      "description": "Preview what would be created without writing files",
                      "default": False,
                  },
              },
              "required": ["domain"],
          },
      )
      \`\`\`
    - **Handler function** `_handle_init_project(domain: str, project_name: str = "", dry_run: bool = False)`:
      - Import `from autoinfo.cli.init import _run_init, _ensure_dir` (lazy, inside handler)
      - Determine `.autoinfo/` path as `Path.cwd() / ".autoinfo"`
      - If `.autoinfo/config.yaml` already exists AND not dry_run: return success with `"status": "skipped"` + `"message": "Already initialized"`
      - If `dry_run`: call `_run_init(domain, Path.cwd() / ".autoinfo")` captured within a dry-run-aware wrapper
      - If not dry_run: create dir if needed, call `_run_init`, return success dict
      - Catch exceptions: return error with `ErrorCode.INTERNAL_ERROR`
    - **Handler registration** in `call_tool()` dispatch: Add `"init_project": _handle_init_project`
  - Write tests:
    - `tests/test_mcp_init_project.py`:
      - Test tool exists in `list_tools()` output
      - Test calling init_project with valid domain (in temp dir) → creates .autoinfo/
      - Test calling init_project twice → second call returns "skipped" status
      - Test calling with invalid domain → returns error gracefully (not typer.Exit)
      - Test calling with dry_run=True → no files created

  **Must NOT do**:
  - Do NOT make the tool interactive (no prompts, no typer calls)
  - Do NOT overwrite existing .autoinfo/ files
  - Do NOT expose `project_dir` parameter (run in CWD only)
  - Do NOT modify `_run_init()` itself unless absolutely necessary

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Need to understand CLI init.py internals and wrap correctly for MCP
  - **Skills evaluated but omitted**: none

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 4)
  - **Blocks**: None
  - **Blocked By**: None

  **References**:
  - `src/autoinfo/cli/init.py:143-181` — `_run_init()` function to wrap
  - `src/autoinfo/cli/init.py:27-34` — `_REQUIRED_SUBDIRS` list
  - `src/autoinfo/cli/init.py:184-271` — CLI `init()` command (not wrapped directly, but shows entry points)
  - `src/autoinfo/mcp/server.py:2155-2160` — Server setup pattern
  - Existing handlers in server.py for error handling pattern (e.g., try/except with error_response)
  - `AGENTS.md:105` — Current "Do not run init" constraint (will be updated in Task 4)

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY)**:
  \`\`\`
  Scenario: init_project creates .autoinfo/ in temp directory
    Tool: Bash
    Preconditions: A temporary empty directory
    Steps:
      1. mkdir -p /tmp/test-init && cd /tmp/test-init
      2. python -c "
    import asyncio
    from src.autoinfo.mcp.server import call_tool
    result = asyncio.run(call_tool('init_project', {'domain': 'medical-research'}))
    assert result
    "
      3. ls /tmp/test-init/.autoinfo/config.yaml
    Expected Result: .autoinfo/config.yaml exists
    Evidence: .omo/evidence/task-3-init-created.txt

  Scenario: init_project is idempotent (second call returns skipped)
    Tool: Bash
    Preconditions: .autoinfo/ already initialized
    Steps:
      1. python -c "
    import asyncio, json
    from src.autoinfo.mcp.server import call_tool
    result = asyncio.run(call_tool('init_project', {'domain': 'medical-research'}))
    data = json.loads(result[0].text)
    assert data.get('status') == 'skipped', f'Expected skipped, got {data}'
    "
    Expected Result: status is "skipped"
    Evidence: .omo/evidence/task-3-init-idempotent.txt

  Scenario: init_project with dry_run creates nothing
    Tool: Bash
    Preconditions: A clean temp directory
    Steps:
      1. mkdir -p /tmp/test-dryrun && cd /tmp/test-dryrun
      2. python -c "
    import asyncio
    from src.autoinfo.mcp.server import call_tool
    result = asyncio.run(call_tool('init_project', {'domain': 'medical-research', 'dry_run': True}))
    "
      3. test ! -d /tmp/test-dryrun/.autoinfo
    Expected Result: .autoinfo/ does NOT exist
    Evidence: .omo/evidence/task-3-init-dryrun.txt

  Scenario: Tests pass
    Tool: Bash (pytest)
    Preconditions: Test file created
    Steps:
      1. pytest tests/test_mcp_init_project.py -v
    Expected Result: All tests pass
    Evidence: .omo/evidence/task-3-tests.txt
  \`\`\`

  **Evidence to Capture:**
  - [ ] .omo/evidence/task-3-init-created.txt
  - [ ] .omo/evidence/task-3-init-idempotent.txt
  - [ ] .omo/evidence/task-3-init-dryrun.txt
  - [ ] .omo/evidence/task-3-tests.txt

  **Commit**: YES (standalone)
  - Message: `feat(mcp): add init_project MCP tool (#6)`
  - Files: `src/autoinfo/mcp/server.py`, `tests/test_mcp_init_project.py`, `AGENTS.md` (constraints update — or bundled with Task 4)

---

- [x] 4. Comprehensive AGENTS.md rewrite — fix #4, #7, #9, + #6 documentation

  **What to do**:
  Fix ALL documentation issues in `AGENTS.md`:

  **Issue #4 (P0) — Greenfield status**:
  - Replace the "Status" section (lines 159-163):
    - Remove "**Greenfield project**. No code has been written yet."
    - Replace with status table matching README.md (list all v1.2 components)
    - Update "35+ tools across 10 categories" → "70+ MCP tools across 12 categories" (line 24, 116)
    - Update directory tree (line 44): remove `src/` → "Implementation (to be built)". Replace with the actual tree showing `src/autoinfo/{cli,mcp,api,kb,collectors,extraction,output,cefr,email}` sub-packages
    - Update Tool Discovery table (lines 118-128) to include all categories: CEFR, Keywords, Email, Graph, Relations, Monitor, Cron, Projects

  **Issue #7 (P2) — Discovery flow**:
  - Replace discovery flow (lines 130-134) with:
    \`\`\`
    **Discovery flow**:
    1. Call `health_check()` first to verify server is alive and get version info
    2. Use MCP protocol `tools/list` for auto-discovery of all available tools
    3. Call `list_domains()` to see available domains
    4. Call `get_domain_schema(domain)` to see extraction fields for your domain
    5. Call `list_available_models()` to see configured LLM models
    6. Call `list_output_templates(domain)` to see output types for your domain
    \`\`\`

  **Issue #9 (P3) — Common Patterns**:
  - Replace the Common Patterns section (lines 136-157) with **10+ patterns**:
    1. "Track a new topic" (existing, keep)
    2. "What changed since last week?" (existing, keep)
    3. "Check system health" (existing, keep)
    4. "Initialise a project" (new — init_project workflow)
    5. "Save an article to the knowledge base" (new — flag → create-draft → user promotes)
    6. "Set up and run a cron schedule" (new — add-schedule → install → verify)
    7. "Generate and send a digest email" (new — generate_digest → send_email)
    8. "Classify content by CEFR level" (new — classify_cefr on text)
    9. "Search with hybrid or vector mode" (new — search_knowledge_base with mode param)
    10. "Export knowledge base to PDF" (new — export_kb with format=pdf)
    11. "Manage keywords for a domain" (new — list_keywords → manage_keyword to approve/reject)
    12. "Use the REST API" (new — start FastAPI server → curl endpoints)
    Each pattern: tool call sequence + expected output

  **#6 documentation**:
  - Update AGENTS.md "Agent Constraints" table (line 105): Change "Do not run `init`" to "Run `init_project` MCP tool instead of CLI `init` for agent workflows. CLI `init` remains available for humans."

  **Must NOT do**:
  - Do NOT reorganize AGENTS.md structure (fix specific sections only)
  - Do NOT change README.md (not in scope)

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Touches all sections of AGENTS.md; needs comprehensive but focused rewrite
  - **Skills evaluated but omitted**: none

  **Parallelization**:
  - **Can Run In Parallel**: YES (single-file changes don't conflict because no other task touches AGENTS.md)
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 3)
  - **Blocks**: None
  - **Blocked By**: None

  **References**:
  - `AGENTS.md:1-168` — The ENTIRE file to update
  - `README.md` — Source of truth for tool counts, categories, and features
  - `src/autoinfo/mcp/server.py:2160+` — Actual list_tools() output (verify tool category counts)
  - `docs/dev/founder-expectations.md` — Spec reference for deferred features

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY)**:
  \`\`\`
  Scenario: No "Greenfield" in AGENTS.md
    Tool: Bash (grep)
    Steps:
      1. grep -ci 'greenfield' AGENTS.md
    Expected Result: 0 (case-insensitive)
    Evidence: .omo/evidence/task-4-no-greenfield.txt

  Scenario: health_check appears before list_domains in discovery flow
    Tool: Bash (grep with context)
    Steps:
      1. grep -n 'health_check\|list_domains' AGENTS.md | head -10
    Expected Result: health_check line number < list_domains line number
    Evidence: .omo/evidence/task-4-discovery-flow.txt

  Scenario: At least 10 common patterns
    Tool: Bash (grep)
    Steps:
      1. grep -c '^### "' AGENTS.md
    Expected Result: >= 10
    Evidence: .omo/evidence/task-4-pattern-count.txt

  Scenario: Tool count updated (no "35+ tools")
    Tool: Bash (grep)
    Steps:
      1. grep -c '35+ tools' AGENTS.md
    Expected Result: 0
    Evidence: .omo/evidence/task-4-tool-count.txt

  Scenario: "Do not run init" updated to reference init_project
    Tool: Bash (grep)
    Steps:
      1. grep 'init_project' AGENTS.md | head -3
    Expected Result: At least 1 mention (updated constraint)
    Evidence: .omo/evidence/task-4-init-constraint.txt
  \`\`\`

  **Evidence to Capture:**
  - [ ] .omo/evidence/task-4-no-greenfield.txt
  - [ ] .omo/evidence/task-4-discovery-flow.txt
  - [ ] .omo/evidence/task-4-pattern-count.txt
  - [ ] .omo/evidence/task-4-tool-count.txt
  - [ ] .omo/evidence/task-4-init-constraint.txt

  **Commit**: YES (standalone)
  - Message: `docs: comprehensive AGENTS.md update for v1.2 (#4, #7, #9)`
  - Files: `AGENTS.md`

- [x] 5. Refactor error_code strings to ErrorCode enum + fix 4 bare-"error" handlers + update tests + align routes.py

  **What to do**:

  **Part A — Refactor server.py error_code strings (47 occurrences → ErrorCode enum)**:
  - Import `ErrorCode`, `error_dict`, `error_response` from `.errors` in server.py
  - Replace ALL literal `"error_code": "SomeString"` dictionary entries with `"error_code": ErrorCode.SOME_STRING.value` (or just `ErrorCode.SOME_STRING` if the consumer handles enum)
  - Specific replacements:
    - `"error_code": "NotFound"` → `ErrorCode.NOT_FOUND`
    - `"error_code": "DomainNotFound"` → `ErrorCode.DOMAIN_NOT_FOUND`
    - `"error_code": "ValidationError"` → `ErrorCode.VALIDATION_ERROR`
    - `"error_code": "InvalidSourceId"` → `ErrorCode.INVALID_SOURCE_ID`
    - `"error_code": "SourceNotFound"` → `ErrorCode.SOURCE_NOT_FOUND`
    - `"error_code": "Timeout"` → `ErrorCode.TIMEOUT`
    - `"error_code": "TopicNotFound"` → `ErrorCode.TOPIC_NOT_FOUND`
    - `"error_code": "KeywordNotFound"` → `ErrorCode.KEYWORD_NOT_FOUND`
    - `"error_code": "EmailNotEnabled"` → `ErrorCode.EMAIL_NOT_ENABLED`
    - `"error_code": "EmailSendFailed"` → `ErrorCode.EMAIL_SEND_FAILED`
    - `"error_code": "InvalidCronExpression"` → `ErrorCode.INVALID_CRON_EXPRESSION`
    - `"error_code": "ScheduleAlreadyExists"` → `ErrorCode.SCHEDULE_ALREADY_EXISTS`
    - `"error_code": "ScheduleNotFound"` → `ErrorCode.SCHEDULE_NOT_FOUND`
    - `"error_code": "NotPublished"` → `ErrorCode.NOT_PUBLISHED`
    - `"error_code": "CollectionFailed"` → `ErrorCode.COLLECTION_FAILED`
    - `"error_code": "ProcessingFailed"` → `ErrorCode.PROCESSING_FAILED`
    - `"error_code": "InvalidSection"` → `ErrorCode.INVALID_SECTION`
    - `"error_code": "UnknownTool"` → `ErrorCode.UNKNOWN_TOOL`
  - **4 dynamic `type(exc).__name__` cases** (lines 678, 789, 1428, 2123, 2143): Replace with `ErrorCode.INTERNAL_ERROR` and log the original exception type
  - **Inline dict-building pattern** → refactor to use `error_dict()` helper where it simplifies code

  **Part B — Fix 4 handlers using bare `"error"` key**:
  - `_handle_list_domains` (line 349): Change `"error": str(exc)` → `"error_code": ErrorCode.INTERNAL_ERROR`
  - `_handle_list_available_models` (line 523): Same fix
  - `_handle_list_projects` (line 1886): Same fix
  - `_handle_list_active_collections` (line 2050): Same fix

  **Part C — Align `_error_dict` and `_error_response`** (lines 2120-2148):
  - These already have consistent shapes (3 fields), but the inline dicts in handlers bypass them
  - Unify: refactor the inline `{"error_code": ..., "message": ..., "actionable": ...}` dicts through the helpers OR leave as is since they match the shape
  - Decision: Keep helpers, add inline comments referencing them for new error returns

  **Part D — Update test_mcp_v2.py:136**:
  - Change `assert "error" in result` → `assert "error_code" in result`
  - This test is for `_handle_list_domains` error path

  **Part E — Update ALL 9 test files**:
  - Find and update all 9 test files that reference `error_code` string literals
  - Specific files to update: `test_mcp_server.py`, `test_mcp_v2.py`, `test_mcp_full.py`, `test_v1_2_integration.py`, plus 5 more
  - Update assertions to use `ErrorCode` enum values where appropriate
  - Update any test that compares error_code strings to use the enum directly

  **Part F — Align routes.py ErrorResponse**:
  - `src/autoinfo/api/routes.py:81`: Change `ErrorResponse.error_code: str = "unknown"` to use `ErrorCode` type hint
  - Import `ErrorCode` from `autoinfo.mcp.errors`
  - Either: `error_code: ErrorCode = ErrorCode.UNKNOWN` (if such value exists) or just add type hint: `error_code: ErrorCode | str = "unknown"`

  **Must NOT do**:
  - Do NOT change the actual string values (exception: `"error"` → `"error_code"` key rename)
  - Do NOT add error handling to new code paths
  - Do NOT break the `add_sources` per-source error handling pattern (line 669 checks `"error_code" in result` on individual sources within a batch response)

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: High-risk refactoring across multiple files; every replacement must preserve semantics
  - **Skills evaluated but omitted**: none

  **Parallelization**:
  - **Can Run In Parallel**: NO (single large refactor touching many files)
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 6
  - **Blocked By**: Task 1 (needs ErrorCode enum)

  **References**:
  - `src/autoinfo/mcp/errors.py` — The ErrorCode enum (created in Task 1)
  - `src/autoinfo/mcp/server.py:349` — `_handle_list_domains` ("error" key location)
  - `src/autoinfo/mcp/server.py:523` — `_handle_list_available_models` ("error" key)
  - `src/autoinfo/mcp/server.py:1886` — `_handle_list_projects` ("error" key)
  - `src/autoinfo/mcp/server.py:2050` — `_handle_list_active_collections` ("error" key)
  - `src/autoinfo/mcp/server.py:2120-2148` — `_error_dict()` + `_error_response()` helpers
  - `src/autoinfo/mcp/server.py:669` — `add_sources` per-source error handling pattern (MUST preserve)
  - `src/autoinfo/api/routes.py:81` — FastAPI ErrorResponse model
  - `tests/test_mcp_v2.py:136` — Test asserting "error" key (will break)
  - All 9 test files: `test_mcp_server.py`, `test_mcp_v2.py`, `test_mcp_full.py`, `test_v1_2_integration.py`, plus find remaining 5 via `grep -l 'error_code' tests/`

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY)**:
  \`\`\`
  Scenario: No bare "error" key handlers remain
    Tool: Bash (grep)
    Steps:
      1. grep -n '"error": str(exc)' src/autoinfo/mcp/server.py
    Expected Result: 0 matches (all 4 handlers fixed)
    Evidence: .omo/evidence/task-5-no-bare-error.txt

  Scenario: No hardcoded error_code strings remain
    Tool: Bash (grep)
    Steps:
      1. grep -n '"error_code": "[A-Z]' src/autoinfo/mcp/server.py | grep -v 'ErrorCode\.' | grep -v '#'
    Expected Result: 0 matches (all are now ErrorCode enum refs)
    Evidence: .omo/evidence/task-5-enum-only.txt

  Scenario: test_mcp_v2.py:136 updated
    Tool: Bash (grep)
    Steps:
      1. grep 'assert.*error.*in.*result' tests/test_mcp_v2.py
    Expected Result: Line 136 now says error_code (not bare "error")
    Evidence: .omo/evidence/task-5-test-assertion.txt

  Scenario: routes.py ErrorResponse aligned
    Tool: Bash
    Steps:
      1. grep 'error_code' src/autoinfo/api/routes.py
    Expected Result: References ErrorCode enum (not standalone string)
    Evidence: .omo/evidence/task-5-routes-errorcode.txt

  Scenario: All tests pass after refactor
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/ -x --tb=short -q
    Expected Result: All tests pass (no failures)
    Evidence: .omo/evidence/task-5-tests-pass.txt
  \`\`\`

  **Evidence to Capture:**
  - [ ] .omo/evidence/task-5-no-bare-error.txt
  - [ ] .omo/evidence/task-5-enum-only.txt
  - [ ] .omo/evidence/task-5-test-assertion.txt
  - [ ] .omo/evidence/task-5-routes-errorcode.txt
  - [ ] .omo/evidence/task-5-tests-pass.txt

  **Commit**: YES (combined with Task 1)
  - Message: `refactor(mcp): centralize error codes with ErrorCode enum (#5)`
  - Files: `src/autoinfo/mcp/server.py`, `src/autoinfo/mcp/errors.py`, `src/autoinfo/mcp/__init__.py`, `src/autoinfo/api/routes.py`, `tests/test_errors.py`, all 9 test files
  - Pre-commit: `pytest tests/ -x --tb=short -q`

---

- [x] 6. Integration verification — full test suite + QA scenario execution

  **What to do**:
  - Run `pytest -v tests/` — verify ALL 825+ tests pass with 0 failures
  - Verify ALL QA scenarios from Tasks 1-5 executed and evidence files exist
  - Run specific cross-task integration checks:
    - `init_project` called → AGENTS.md constraint mentions init_project
    - ErrorCode enum used by both server.py AND routes.py
    - `list_tools()` returns correct schemas after Task 2 fixes
    - `_handle_list_domains` error response now has `"error_code"` (not `"error"`)
  - Run full git diff to verify no scope creep
  - Report consolidated results

  **Must NOT do**:
  - Do NOT modify code beyond what's needed to pass tests
  - Do NOT add new features beyond the 6 issues scope
  - Do NOT commit in this task (verification only)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Integration-level verification across all 6 fixes

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3 (final verification)
  - **Blocks**: F1-F4
  - **Blocked By**: Task 5

  **References**:
  - `.omo/evidence/` — All evidence files from Tasks 1-5
  - `AGENTS.md` — Verification of all document changes
  - `src/autoinfo/mcp/server.py` — Verification of error_code refactor + schemas + init_project
  - `src/autoinfo/mcp/errors.py` — Verification of ErrorCode enum
  - `src/autoinfo/api/routes.py` — Verification of ErrorResponse alignment

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY)**:
  \`\`\`
  Scenario: Full test suite passes
    Tool: Bash (pytest)
    Steps:
      1. pytest -v tests/ --tb=short 2>&1 | tail -20
    Expected Result: "passed" with 0 failures, 0 errors
    Evidence: .omo/evidence/task-6-full-tests.txt

  Scenario: All evidence files exist
    Tool: Bash (ls)
    Steps:
      1. find .omo/evidence/ -type f | sort
    Expected Result: All expected evidence files present (at least 1 per task)
    Evidence: .omo/evidence/task-6-evidence-list.txt

  Scenario: git diff shows no scope creep
    Tool: Bash (git)
    Steps:
      1. git diff --stat HEAD
    Expected Result: Only files in the plan scope are changed
    Evidence: .omo/evidence/task-6-diff-stat.txt

  Scenario: Cross-task integration — init_project tool callable
    Tool: Bash
    Steps:
      1. python -c "import asyncio; from src.autoinfo.mcp.server import list_tools; tools = asyncio.run(list_tools()); names = [t.name for t in tools]; assert 'init_project' in names, f'Missing: {names}'"
    Expected Result: init_project in tool list
    Evidence: .omo/evidence/task-6-init-in-tools.txt
  \`\`\`

  **Evidence to Capture:**
  - [ ] .omo/evidence/task-6-full-tests.txt
  - [ ] .omo/evidence/task-6-evidence-list.txt
  - [ ] .omo/evidence/task-6-diff-stat.txt
  - [ ] .omo/evidence/task-6-init-in-tools.txt

  **Commit**: NO (verification only)

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.

- [x] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, grep pattern, run test). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in .omo/evidence/. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [x] F2. **Code Quality Review** — `unspecified-high`
  Run `pytest -v tests/` + review changed files for: `as any`/`@ts-ignore` (not applicable for Python), empty except blocks, commented-out code, unused imports, excessive complexity. Check AI slop.
  Output: `Tests [N pass/N fail] | Files [N clean/N issues] | VERDICT`

- [x] F3. **Real Manual QA** — `unspecified-high`
  Start from clean state. Execute EVERY QA scenario from EVERY task — follow exact steps, capture evidence. Test cross-task integration (error_code propagation from MCP to routes.py). Test edge cases: init_project when .autoinfo/ exists, error handlers with missing config. Save to `.omo/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | VERDICT`

- [x] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff (git log/diff). Verify 1:1 — everything in spec was built (no missing), nothing beyond spec was built (no creep). Check "Must NOT do" compliance. Detect cross-task contamination.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | VERDICT`

---

## Commit Strategy

- **1-3**: `refactor(mcp): create ErrorCode enum with ...`
- **4**: `docs: comprehensive AGENTS.md update for v1.2`
- **2+5 merged**: `fix(mcp): add schema defaults/required/enum + refactor error_codes`
- **3**: `feat(mcp): add init_project tool`
- **6**: `test: update test assertions for ErrorCode refactor`

---

## Success Criteria

### Verification Commands
```bash
pytest -v tests/                           # All 825+ tests pass
grep -r '"error": str(exc)' src/autoinfo/mcp/server.py  # 0 results
grep 'Greenfield' AGENTS.md                # 0 results
grep 'health_check' AGENTS.md              # appears before list_domains
grep -c '### "' AGENTS.md                  # 10+ common patterns
grep 'error_code =' src/autoinfo/mcp/errors.py  # ErrorCode enum exists
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] All tests pass
- [ ] 0 bare "error" key handlers remain
- [ ] 0 "Greenfield" references in AGENTS.md
- [ ] AGENTS.md has 10+ common patterns
