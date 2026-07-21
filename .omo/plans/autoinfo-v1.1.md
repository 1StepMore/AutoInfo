# AutoInfo v1.1 — Full Gap-Fill Release

## TL;DR

> **Quick Summary**: Close all 18 remaining gaps across AutoInfo's pipeline, MCP tools, source handlers, and domain configuration — producing a complete v1.1 release that fulfills every non-deferred expectation from the founder's spec.
>
> **Deliverables**:
> - G5 translation accuracy quality gate + Draft→Wiki promote pipeline closure
> - 6 new MCP tools (collection progress, collection status, domain lifecycle, keywords, tutorial/presentation)
> - 3 new source handlers (webhook, email/IMAP, PDF)
> - 7 curated demo sources (arXiv, CrossRef, Unpaywall, Crunchbase, LMSYS, news-in-levels, commonlit)
> - Language auto-detection, KB frontmatter expansion, topic tooling
> - Init dirs, interactive init wizard, --all collect flag, KG export CLI
> - README honesty update with explicit Known Limitations section
>
> **Estimated Effort**: Large — 18 gaps across 4 waves (~15-25 days)
> **Parallel Execution**: YES — 4 waves + final verification
> **Critical Path**: Task 1 → Task 2 → Task 5-10 → F1-F4

---

## Context

### Original Request
Fill ALL remaining gaps from the founder-expectations.md audit. The v1.0 implementation passed 25/50 expectations fully, 23 PARTIAL, 2 FAIL. This plan addresses all 18 non-deferred gaps.

### Interview Summary
**Key Decisions**:
- **Single release**: All 18 gaps as one v1.1 release (not split into v1.2/v1.3)
- **7 items deferred**: Hybrid/vector search, REST API, Obsidian [[wiki links]], CEFR classification, config override system, schema versioning/migration, CSV/PDF/GraphML export formats
- **Implement missing MCP tools**: Not just fix the README — build them
- **Tests-after**: Write tests after implementation (~50-100 new tests expected)
- **README "Known Limitations"**: Add transparency section
- **No time budget**: Full quality, vibecoding pace

### Research Findings
- **G5 is ~0.5d**: Direct pattern-match from G4FactualConsistency (quality.py:282-428). Same class structure, different LLM prompt and response format.
- **Draft→Wiki promote missing entirely**: KBStore.promote_kb_draft() doesn't exist — must add method + replace CLI stub.
- **Init is trivial**: Just add 3 subdirs to `_REQUIRED_SUBDIRS` (cli/init.py:25).
- **MCP tools follow if/elif pattern**: server.py uses if/elif chain in call_tool(), not dict dispatch.
- **Source handlers follow class pattern**: collectors/ has pubmed.py, rss.py, web.py, web_playwright.py as reference.

### Metis Review
**Identified Gaps** (addressed):
- Initial scope was ambiguous across 3 release bands → resolved: single v1.1
- Test strategy undecided → resolved: tests-after
- Test ratio target → resolved: follow existing pattern (~50-100 new tests)
- Missing MCP tool vs README fix → resolved: implement them

---

## Work Objectives

### Core Objective
Deliver a complete v1.1 release by closing all 18 remaining gaps across pipeline, MCP tools, sources, handlers, and documentation — producing the first fully-spec-compliant AutoInfo release.

### Concrete Deliverables
- G5TranslationAccuracy class in quality.py
- KBStore.promote_kb_draft() method + `autoinfo kb promote` CLI command
- 03-Wiki append-only guard enforcement in KBStore
- Init directory structure includes 00-Inbox, 02-Draft, 03-Wiki
- Interactive init wizard (domain selection, optional --demo simplification)
- Expanded KB frontmatter: author, source_ids, status, related_concepts, linked_entries
- 6 new MCP tools: get_collection_progress, get_collection_status, activate_domain/deactivate_domain/get_domain_config, list_keywords, generate_tutorial, generate_presentation
- `autoinfo collect --all` flag
- Language auto-detection on Item.language
- test_source with extract_fields preview in output
- Quality tier warnings on add_source MCP tool
- list_keywords MCP + CLI + topic grouping + multi-language keywords + topic scoring
- 7 new curated demo sources
- 3 new source handlers: webhook, email (IMAP), PDF
- Knowledge graph export CLI (`autoinfo knowledge graph`)
- README Known Limitations section + updated quality gate status

### Definition of Done
- [ ] `bun test` passes with 0 failures (720+ existing + ~50-100 new)
- [ ] `autoinfo init --demo medical-research` creates knowledge/00-Inbox, knowledge/02-Draft, knowledge/03-Wiki
- [ ] `autoinfo kb promote --entry-id X` promotes a Draft to 03-Wiki successfully
- [ ] All 6 new MCP tools respond to calls without UnknownTool
- [ ] `autoinfo collect --all` collects all active domains
- [ ] G5 runs on translated items and flags mismatches
- [ ] Webhook source handler accepts POST and creates Item
- [ ] README Known Limitations section lists deferred items honestly

### Must Have
- G5TranslationAccuracy gate implemented (pattern-match G4)
- KBStore.promote_kb_draft() + CLI promote replacing stub
- All 6 missing MCP tools implemented (not stubbed)
- Init creates all 4 KB tiers
- Language auto-detection on item processing
- Every new feature covered by tests-after
- 03-Wiki append-only: KBStore refuses agent writes to 03-Wiki

### Must NOT Have (Guardrails)
- **NO promote as MCP tool** — F20 spec says promote is human-only, CLI-only
- **NO hybrid/vector search** — deferred to v1.3+
- **NO REST API** — deferred indefinitely
- **NO Obsidian [[wiki links]]** — deferred
- **NO CEFR classification** — deferred
- **NO config override system** — deferred
- **NO schema versioning/migration** — deferred
- **NO CSV/PDF/GraphML export formats** — deferred
- **NO breaking changes** to existing G1-G4 quality gate behavior
- **NO agent writes to 03-Wiki** — append-only enforced at KBStore level

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES (pytest, 720+ existing tests)
- **Automated tests**: Tests-after (write tests after each implementation)
- **Framework**: pytest via `make test`
- **Coverage target**: ~50-100 new tests across all 18 gaps

### QA Policy
Every task MUST include agent-executed QA scenarios. Evidence saved to `.omo/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Python modules**: Use Bash (`python -c "import ..."`) or pytest
- **CLI commands**: Use Bash (`autoinfo <cmd> ...`) with stdout/stderr capture
- **MCP tools**: Start server in background, send JSON-RPC via Bash
- **Source handlers**: Test with sample data, verify Item creation

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundation — pipeline closure, 5 tasks):
├── Task 1: G5TranslationAccuracy quality gate
├── Task 2: KBStore.promote_kb_draft() + CLI + append-only guards
├── Task 3: Init dirs + interactive init wizard
├── Task 4: KB frontmatter field expansion
├── Task 5: Language auto-detection

Wave 2 (MCP Tools — all parallel, 7 tasks):
├── Task 6: get_collection_progress MCP tool
├── Task 7: get_collection_status MCP tool
├── Task 8: activate_domain/deactivate_domain/get_domain_config MCP tools
├── Task 9: list_keywords MCP tool + topic grouping + multi-language scoring
├── Task 10: generate_tutorial + generate_presentation MCP tools
├── Task 11: --all flag on collect CLI
├── Task 12: test_source extract_fields + quality tier warnings

Wave 3 (Sources & Handlers, 5 tasks):
├── Task 13: 7 curated demo sources
├── Task 14: Webhook source handler
├── Task 15: Email (IMAP) source handler
├── Task 16: PDF source handler
├── Task 17: Knowledge graph export CLI

Wave 4 (Integration, 1 task):
├── Task 18: README update + Known Limitations section

Wave FINAL (After ALL tasks — 4 parallel reviews):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real manual QA (unspecified-high)
└── Task F4: Scope fidelity check (deep)

Critical Path: Task 1 → Task 2 → Task 6-10 → F1-F4 → explicit user okay
Parallel Speedup: ~60% faster than sequential
Max Concurrent: 7 (Wave 2)
```

### Dependency Matrix

- **1-5**: — — 6-10, 11, 12
- **6-10**: 1, 2 — 13, 14-17, 18
- **11**: 1 — 13, 18
- **12**: 1 — 13, 18
- **13**: 6-12 — 14-17, 18
- **14-17**: 13 — F1-F4
- **18**: 6-17 — F1-F4
- **F1-F4**: All tasks — user okay

---

## TODOs

- [x] 1. G5TranslationAccuracy quality gate

  **What to do**:
  - Create `G5TranslationAccuracy` class in `src/autoinfo/quality.py` (pattern-match `G4FactualConsistency` at lines 282-428)
  - Same class structure: `SYSTEM_PROMPT`, `__init__(model)`, `check(source_text, translated_text) -> QualityResult`
  - Different LLM prompt: "Compare the source text with its translation. Determine if the translation faithfully represents the source content, preserving meaning, tone, and factual claims. Answer ONLY with JSON: {\"faithful\": bool, \"explanation\": str, \"issues\": [str]}"
  - Register G5 in `run_quality_gates()` orchestrator (quality.py:435-475) — optional, only runs with `--check-translation` flag
  - Wire into process.py: add `check_translation: bool = False` parameter to `run_processing()`, pass to quality gate check
  - Add `--check-translation` CLI flag to `autoinfo process`
  - Update docstring in quality.py line 9-10 to reflect G5 is now implemented
  - Write tests: 1 unit test (G5 class check), 1 integration test (process with `--check-translation`)

  **Must NOT do**:
  - Do not change G1-G4 behavior
  - Do not make G5 required (must remain optional/advisory)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Python implementation following an exact existing pattern (G4 → G5). Requires understanding of LLM pipeline, quality gate architecture, and CLI wiring.
  - **Skills**: [] (no special skills needed beyond Python + LiteLLM familiarity)

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Tasks 6-10, 11, 12 (new MCP tools and CLI flags that may call into quality gates)
  - **Blocked By**: None (foundation task)

  **References**:
  - `src/autoinfo/quality.py:282-428` — G4FactualConsistency class (exact pattern to copy for G5)
  - `src/autoinfo/quality.py:435-475` — run_quality_gates() orchestrator (add G5 here)
  - `src/autoinfo/process.py:27` — existing G4 import line (add G5 import)
  - `src/autoinfo/process.py` — run_processing() function (add `check_translation` param)

  **Acceptance Criteria**:
  - [ ] G5TranslationAccuracy class exists in quality.py with check(source_text, translated_text) method
  - [ ] `python -c "from autoinfo.quality import G5TranslationAccuracy; g5=G5TranslationAccuracy(); r=g5.check('Hello world', 'Bonjour le monde'); print(r)"` runs without error
  - [ ] `autoinfo process --help` shows `--check-translation` flag
  - [ ] `pytest tests/ -k "g5"` passes

  **QA Scenarios**:
  ```
  Scenario: G5 detects faithful translation
    Tool: Bash (python -c)
    Preconditions: None
    Steps:
      1. Create G5 instance
      2. Call check("Hello world", "Bonjour le monde")
    Expected Result: QualityResult with passed=True, flagged=False
    Evidence: .omo/evidence/task-1-g5-faithful.txt

  Scenario: G5 detects unfaithful translation
    Tool: Bash (python -c)
    Preconditions: None
    Steps:
      1. Create G5 instance
      2. Call check("The patient recovered fully", "The patient died")
    Expected Result: QualityResult with flagged=True, details.issues non-empty
    Evidence: .omo/evidence/task-1-g5-unfaithful.txt
  ```

  **Evidence to Capture**:
  - [ ] evidence/task-1-g5-faithful.txt
  - [ ] evidence/task-1-g5-unfaithful.txt

  **Commit**: YES
  - Message: `feat(quality): add G5 translation accuracy gate`
  - Files: `src/autoinfo/quality.py`, `src/autoinfo/process.py`, `src/autoinfo/cli/process.py`, `tests/`
  - Pre-commit: `make test`

- [x] 2. KBStore.promote_kb_draft() + CLI replacement + 03-Wiki append-only guards

  **What to do**:
  - Add `KBStore.promote_kb_draft(draft_id: str, ...) -> dict[str, Any]` method to `src/autoinfo/kb.py` (pattern-match `reject_kb_draft` at lines 1674-1809)
  - Method: fetch Draft entry, validate tier is 02-Draft, move file from 02-Draft/ to 03-Wiki/ (same topic/dir), update SQLite tier to 03-Wiki, mark as `human_promoted=True`, set `promoted_at` timestamp
  - Add 03-Wiki append-only guards: `KBStore._ensure_not_wiki(path)` called before any write/create operation on a path that targets 03-Wiki — raise `PermissionError("03-Wiki is append-only. Only promote_kb_draft() can write here.")`
  - Replace CLI stub at `src/autoinfo/cli/kb.py:150-157` with real implementation calling `KBStore().promote_kb_draft(entry_id)`
  - No MCP tool for promote (per F20 spec: human-only, CLI-only)
  - Update `autoinfo kb --help` to show promote as available
  - Write tests: 1 unit test (promote method), 1 integration test (CLI promote), 1 negative test (promote non-Draft), 1 negative test (agent writing to 03-Wiki)

  **Must NOT do**:
  - Do NOT add MCP tool for promote
  - Do NOT allow agent to write to 03-Wiki via any other path

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Core pipeline feature with file system operations, SQLite updates, and append-only enforcement. Follows existing reject_kb_draft pattern.
  - **Skills**: [] (no special skills needed)

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Tasks 6-10 (new MCP tools may interact with KB tiers)
  - **Blocked By**: None (foundation task)

  **References**:
  - `src/autoinfo/kb.py:1674-1809` — reject_kb_draft (exact pattern for promote)
  - `src/autoinfo/cli/kb.py:150-157` — promote CLI stub to replace
  - `src/autoinfo/kb.py:1842-1903` — flag_for_knowledge_base (another reference for tier operations)

  **Acceptance Criteria**:
  - [ ] KBStore.promote_kb_draft() method exists and moves file from 02-Draft to 03-Wiki
  - [ ] `autoinfo kb promote --entry-id <draft-id>` exits 0 and file exists in 03-Wiki/
  - [ ] `autoinfo kb promote --entry-id <non-draft-id>` exits non-zero with clear error
  - [ ] Agent writing to 03-Wiki via KBStore raises PermissionError
  - [ ] `pytest tests/ -k "promote"` passes

  **QA Scenarios**:
  ```
  Scenario: Promote Draft entry to Wiki
    Tool: Bash
    Preconditions: Existing Draft entry in KB
    Steps:
      1. autoinfo kb promote --entry-id medical-draft-test-001
      2. ls knowledge/medical-research/03-Wiki/general/
    Expected Result: File moved from 02-Draft to 03-Wiki, exit code 0
    Evidence: .omo/evidence/task-2-promote-success.txt

  Scenario: Promote non-Draft entry fails
    Tool: Bash
    Preconditions: Existing Raw entry
    Steps:
      1. autoinfo kb promote --entry-id medical-raw-test-001
    Expected Result: Error message about invalid tier, exit non-zero
    Evidence: .omo/evidence/task-2-promote-fail.txt
  ```

  **Evidence to Capture**:
  - [ ] evidence/task-2-promote-success.txt
  - [ ] evidence/task-2-promote-fail.txt

  **Commit**: YES (groups with Task 1)
  - Message: `feat(kb): add promote_kb_draft() + 03-Wiki append-only guards`
  - Files: `src/autoinfo/kb.py`, `src/autoinfo/cli/kb.py`, `tests/`
  - Pre-commit: `make test`

- [x] 3. Init directory structure + interactive init wizard

  **What to do**:
  - Add `"knowledge/00-Inbox"`, `"knowledge/02-Draft"`, `"knowledge/03-Wiki"` to `_REQUIRED_SUBDIRS` in `src/autoinfo/cli/init.py:25`
  - Create interactive init wizard: when `autoinfo init` is run without `--demo`, present interactive prompts:
    - "Select a demo domain:" with numbered list (from `_list_demo_domains()`)
    - "Confirm LLM provider [default: openrouter]:" 
    - "Set AUTOINFO_LLM_API_KEY [optional]:" 
  - Add `--interactive` flag to `init` command (default True when no --demo)
  - Keep `--demo` flag behavior unchanged (non-interactive, single command)
  - Write tests: 1 test verifying dirs created, 1 test for non-demo flow

  **Must NOT do**:
  - Do not change existing `--demo` flag behavior
  - Do not require LLM key to complete init

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Small, well-scoped change to a single file with a clear existing pattern.

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 4, 5)
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 4, 5)
  - **Blocks**: None (trivial, no downstream deps)
  - **Blocked By**: None

  **References**:
  - `src/autoinfo/cli/init.py:25` — _REQUIRED_SUBDIRS to extend
  - `src/autoinfo/cli/init.py:127-203` — init() command function (add --interactive)

  **Acceptance Criteria**:
  - [ ] `autoinfo init --demo medical-research` creates 00-Inbox, 02-Draft, 03-Wiki
  - [ ] `autoinfo init --interactive` shows domain selection prompt
  - [ ] `pytest tests/ -k "init"` passes

  **QA Scenarios**:
  ```
  Scenario: Init creates all KB tier dirs
    Tool: Bash
    Preconditions: Empty temp directory
    Steps:
      1. autoinfo init --demo medical-research
      2. ls .autoinfo/knowledge/
    Expected Result: Shows 01-Raw, 02-Draft, 03-Wiki, 00-Inbox directories
    Evidence: .omo/evidence/task-3-init-dirs.txt
  ```

  **Evidence to Capture**:
  - [ ] evidence/task-3-init-dirs.txt

  **Commit**: YES (groups with Tasks 1, 2)
  - Message: `feat(cli): add 00-Inbox/02-Draft/03-Wiki dirs + interactive init wizard`
  - Files: `src/autoinfo/cli/init.py`, `tests/`
  - Pre-commit: `make test`

- [x] 4. KB frontmatter field expansion

  **What to do**:
  - Expand `_build_frontmatter()` in `src/autoinfo/kb.py` to include: `author`, `source_ids`, `status`, `related_concepts`, `linked_entries`
  - Update `KBEntry` dataclass in `src/autoinfo/models.py` if fields are missing
  - Ensure `create_kb_draft()` populates these new fields (even if empty defaults)
  - Update `SQLiteIndex` schema if needed (add columns or store in `custom_fields` JSON)
  - Update `get_entry()` and `search_fts5()` to return new fields
  - Backwards compatibility: existing Raw entries without new fields should render empty/false defaults
  - Write tests: 1 test verifying frontmatter YAML, 1 test for backwards compatibility

  **Must NOT do**:
  - Do not break existing entries that lack new fields
  - Do not change tier=01-Raw frontmatter (only Draft+ tier)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-low`
    - Reason: Data model expansion across kb.py, models.py. Low complexity but requires care for backwards compat.

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 3, 5)
  - **Parallel Group**: Wave 1 (with Tasks 3, 5)
  - **Blocks**: None directly (but tasks 6-10 may benefit from richer entry data)
  - **Blocked By**: None

  **References**:
  - `src/autoinfo/kb.py` — _build_frontmatter() function location
  - `src/autoinfo/models.py` — KBEntry dataclass definition
  - `src/autoinfo/kb.py` — SQLiteIndex class

  **Acceptance Criteria**:
  - [ ] New Draft entry has author, source_ids, status, related_concepts, linked_entries in YAML frontmatter
  - [ ] Existing entries without new fields still load correctly
  - [ ] `pytest tests/ -k "frontmatter"` passes

  **QA Scenarios**:
  ```
  Scenario: Draft entry has expanded frontmatter
    Tool: Bash
    Preconditions: Processed item exists in domain
    Steps:
      1. autoinfo kb create-draft --raw-ids <id> --title "Test Draft"
      2. head -20 knowledge/*/02-Draft/*/test-draft*.md | grep -E "author|source_ids|status|related|linked"
    Expected Result: All 5 new fields present in YAML frontmatter
    Evidence: .omo/evidence/task-4-frontmatter.txt
  ```

  **Evidence to Capture**:
  - [ ] evidence/task-4-frontmatter.txt

  **Commit**: YES (groups with Tasks 1, 2, 3)
  - Message: `feat(kb): expand frontmatter with author, source_ids, status, related_concepts, linked_entries`
  - Files: `src/autoinfo/kb.py`, `src/autoinfo/models.py`, `tests/`
  - Pre-commit: `make test`

- [x] 5. Language auto-detection

  **What to do**:
  - Implement language detection for `Item.language` field in `src/autoinfo/models.py` or `process.py`
  - Use `langdetect` or `fasttext` library (add to pyproject.toml if needed, prefer `langdetect` for simplicity)
  - Auto-detect from item content (title + content text) during processing
  - If detection confidence < 0.8 (or language is None), leave as "unknown"
  - Store detected language in Item.language and KBEntry.language
  - Update KBStore to persist language field
  - Write tests: 1 test with English content, 1 test with Chinese content, 1 test with short content (low confidence)

  **Must NOT do**:
  - Do not require language detection to succeed for processing to continue
  - Do not add a heavy ML dependency (prefer lightweight langdetect)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Requires library evaluation, pyproject.toml update, and integration across models/process/kb.

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 3, 4)
  - **Parallel Group**: Wave 1
  - **Blocks**: None (language is metadata, not blocking)
  - **Blocked By**: None

  **References**:
  - `src/autoinfo/models.py` — Item dataclass (language field exists?)
  - `src/autoinfo/process.py` — run_processing() where items are processed
  - `src/autoinfo/kb.py` — KBStore entry creation

  **Acceptance Criteria**:
  - [ ] `python -c "from autoinfo.models import Item; i=Item(title='hello', content='world', ...); print(i.language)"` shows detected language
  - [ ] Processed English item has language="en"
  - [ ] `pytest tests/ -k "language"` passes

  **QA Scenarios**:
  ```
  Scenario: English content detected as en
    Tool: Bash (python -c)
    Preconditions: None
    Steps:
      1. python -c "from autoinfo.process import detect_language; print(detect_language('Hello world, this is an article about IVF treatment'))"
    Expected Result: "en" or "english"
    Evidence: .omo/evidence/task-5-lang-en.txt

  Scenario: Chinese content detected as zh
    Tool: Bash (python -c)
    Preconditions: None
    Steps:
      1. python -c "from autoinfo.process import detect_language; print(detect_language('这是一篇关于试管婴儿的文章'))"
    Expected Result: "zh" or "zh-cn"
    Evidence: .omo/evidence/task-5-lang-zh.txt
  ```

  **Evidence to Capture**:
  - [ ] evidence/task-5-lang-en.txt
  - [ ] evidence/task-5-lang-zh.txt

  **Commit**: YES (groups with Tasks 1-4)
  - Message: `feat(process): add language auto-detection for Items`
  - Files: `src/autoinfo/models.py`, `src/autoinfo/process.py`, `src/autoinfo/kb.py`, `pyproject.toml`, `tests/`
  - Pre-commit: `make test`

- [x] 6. get_collection_progress MCP tool

  **What to do**:
  - Add `_handle_get_collection_progress()` handler function in `src/autoinfo/mcp/server.py` (pattern-match `_handle_collect_sources` at line 164)
  - Track collection state: add a module-level `_collection_state: dict[str, Any]` dict storing active collection runs keyed by domain
  - Update `_handle_collect_sources()` to write state before/after collection
  - Register tool in `list_tools()` list with inputSchema: `{"domain": {"type": "string"}}`
  - Add elif branch in `call_tool()` dispatch for `"get_collection_progress"`
  - Return: `{"domain": str, "status": "running"|"completed"|"idle", "progress_pct": float, "items_collected": int, "errors": int}`
  - Write tests: 1 unit test for handler, 1 integration test for tool dispatch

  **Must NOT do**:
  - Do not add persistent progress tracking (in-memory only for v1.1)
  - Do not block collection for tracking

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: MCP tool with runtime state tracking. Requires understanding of existing tool pattern.

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 7, 8, 9, 10, 11, 12)
  - **Parallel Group**: Wave 2 (MCP Tools — 7 parallel tasks)
  - **Blocks**: None
  - **Blocked By**: Tasks 1, 2 (foundation)

  **References**:
  - `src/autoinfo/mcp/server.py:164-168` — _handle_collect_sources (existing handler pattern)
  - `src/autoinfo/mcp/server.py:2520-2663` — call_tool() if/elif dispatch pattern
  - `src/autoinfo/mcp/server.py:2400-2517` — list_tools() Tool registration pattern

  **Acceptance Criteria**:
  - [ ] `get_collection_progress` tool registered and returns valid response
  - [ ] In-memory state tracked during collection run
  - [ ] `pytest tests/ -k "mcp_collection_progress"` passes

  **QA Scenarios**:
  ```
  Scenario: get_collection_progress returns idle state
    Tool: Bash (MCP server test)
    Preconditions: No collection running
    Steps:
      1. python -c "from autoinfo.mcp.server import _handle_get_collection_progress; print(_handle_get_collection_progress())"
    Expected Result: {"domain": "", "status": "idle", ...}
    Evidence: .omo/evidence/task-6-progress-idle.txt
  ```

  **Evidence to Capture**:
  - [ ] evidence/task-6-progress-idle.txt

  **Commit**: YES (groups with Tasks 7-12)
  - Message: `feat(mcp): add get_collection_progress MCP tool`
  - Files: `src/autoinfo/mcp/server.py`, `tests/`
  - Pre-commit: `make test`

- [x] 7. get_collection_status MCP tool

  **What to do**:
  - Add `_handle_get_collection_status()` handler in `src/autoinfo/mcp/server.py`
  - Same state-tracking mechanism as Task 6, but returns full results: last collection time, items per source, error count, duration
  - Register tool in `list_tools()` with inputSchema: `{"domain": {"type": "string"}, "source": {"type": "string", "optional": true}}`
  - Add elif in `call_tool()` for `"get_collection_status"`
  - Could be folded with Task 6 if similar enough, but keep separate per user request to implement all missing tools
  - Write tests: 1 unit test, 1 integration test for tool dispatch

  **Must NOT do**:
  - Do not duplicate Task 6 state — share the same _collection_state dict

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: MCP tool, similar pattern to Task 6.

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 6, 8, 9, 10, 11, 12)
  - **Parallel Group**: Wave 2
  - **Blocks**: None
  - **Blocked By**: Tasks 1, 2

  **References**:
  - Same as Task 6 (server.py patterns)

  **Acceptance Criteria**:
  - [ ] `get_collection_status` tool registered and returns valid response
  - [ ] Results include last collection time, items per source, errors
  - [ ] `pytest tests/ -k "mcp_collection_status"` passes

  **QA Scenarios**:
  ```
  Scenario: get_collection_status returns collection results
    Tool: Bash (MCP server test)
    Preconditions: Completed collection run
    Steps:
      1. python -c "from autoinfo.mcp.server import _handle_get_collection_status; print(_handle_get_collection_status(domain='medical-research'))"
    Expected Result: Dict with domain, sources, items_collected, duration_s
    Evidence: .omo/evidence/task-7-status-result.txt
  ```

  **Evidence to Capture**:
  - [ ] evidence/task-7-status-result.txt

  **Commit**: YES (groups with Tasks 6-12)
  - Message: `feat(mcp): add get_collection_status MCP tool`
  - Files: `src/autoinfo/mcp/server.py`, `tests/`
  - Pre-commit: `make test`

- [x] 8. activate_domain / deactivate_domain / get_domain_config MCP tools

  **What to do**:
  - Add 3 handler functions in `src/autoinfo/mcp/server.py`:
    - `_handle_activate_domain(name: str)` — sets domain.active = True, saves config
    - `_handle_deactivate_domain(name: str)` — sets domain.active = False, saves config
    - `_handle_get_domain_config(name: str)` — returns full domain config object as dict
  - Follow `_handle_list_domains()` pattern (line 219) for config access
  - Register all 3 tools in `list_tools()` with appropriate inputSchema
  - Add 3 elif branches in `call_tool()` dispatch
  - Write tests: 1 per tool (3 total), 1 integration test for dispatch

  **Must NOT do**:
  - Do not delete domains — only active/inactive toggle
  - Do not allow renaming domains via MCP

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 3 MCP tools sharing config read/write pattern.

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 6, 7, 9, 10, 11, 12)
  - **Parallel Group**: Wave 2
  - **Blocks**: None
  - **Blocked By**: Tasks 1, 2

  **References**:
  - `src/autoinfo/mcp/server.py:219-234` — _handle_list_domains (config access pattern)
  - `src/autoinfo/mcp/server.py:72-83` — _load_config / _save_config helpers
  - `src/autoinfo/mcp/server.py:86-91` — _find_domain helper

  **Acceptance Criteria**:
  - [ ] `activate_domain("medical-research")` returns success
  - [ ] `deactivate_domain("medical-research")` returns success, domain inactive
  - [ ] `get_domain_config("medical-research")` returns domain object with all fields
  - [ ] `pytest tests/ -k "mcp_domain_lifecycle"` passes

  **QA Scenarios**:
  ```
  Scenario: Activate and deactivate domain via MCP
    Tool: Bash (MCP server test)
    Preconditions: Domain exists
    Steps:
      1. python -c "from autoinfo.mcp.server import _handle_activate_domain; print(_handle_activate_domain('medical-research'))"
      2. python -c "from autoinfo.mcp.server import _handle_deactivate_domain; print(_handle_deactivate_domain('medical-research'))"
    Expected Result: Both return {"status": "ok"} or similar
    Evidence: .omo/evidence/task-8-domain-lifecycle.txt
  ```

  **Evidence to Capture**:
  - [ ] evidence/task-8-domain-lifecycle.txt

  **Commit**: YES (groups with Tasks 6-12)
  - Message: `feat(mcp): add activate_domain/deactivate_domain/get_domain_config MCP tools`
  - Files: `src/autoinfo/mcp/server.py`, `tests/`
  - Pre-commit: `make test`

- [x] 9. list_keywords MCP tool + topic grouping / multi-language keywords / topic scoring

  **What to do**:
  - Add `_handle_list_keywords(domain: str, topic: str | None = None)` handler in `src/autoinfo/mcp/server.py`
  - Add `list_keywords` to CLI (`autoinfo topics keywords --domain X --topic Y`)
  - Add topic grouping: `Topic.group` field in `config.py` (optional string, e.g. "academic", "news", "social")
  - Add multi-language keywords: `Topic.keywords` can include tuples like `{"en": ["IVF"], "zh": ["试管婴儿"]}`
  - Add topic scoring: `Topic.relevance_threshold` field (per-topic override of G3 threshold)
  - Update config schema and config.yaml template
  - Update `G3RelevanceScoring` to support multi-language keyword matching
  - Register tool in `list_tools()`, add elif in `call_tool()`
  - Write tests: 1 for MCP tool, 1 for CLI, 1 for topic grouping

  **Must NOT do**:
  - Do not break existing single-language keyword configs
  - Do not require grouping for topics to function

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Cross-cutting change across MCP, CLI, config, and quality gates. Significant integration surface.

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 6, 7, 8, 10, 11, 12)
  - **Parallel Group**: Wave 2
  - **Blocks**: None
  - **Blocked By**: Tasks 1, 2

  **References**:
  - `src/autoinfo/mcp/server.py:219-234` — _handle_list_domains (pattern for list_keywords)
  - `src/autoinfo/config.py` — Topic dataclass (add group, relevance_threshold)
  - `src/autoinfo/quality.py:198-274` — G3RelevanceScoring (update for multi-language)
  - `src/autoinfo/cli/topics.py` — CLI topics command group (add keywords subcommand)

  **Acceptance Criteria**:
  - [ ] `list_keywords` MCP tool returns keywords per domain/topic
  - [ ] `autoinfo topics keywords --domain medical` shows keywords
  - [ ] Topic grouping works in config: topics with group field
  - [ ] Multi-language keywords match content in Chinese/English
  - [ ] `pytest tests/ -k "keywords"` passes

  **QA Scenarios**:
  ```
  Scenario: list_keywords returns keywords for domain
    Tool: Bash (MCP server test)
    Preconditions: Domain with topics configured
    Steps:
      1. python -c "from autoinfo.mcp.server import _handle_list_keywords; print(_handle_list_keywords(domain='medical-research'))"
    Expected Result: Dict with domain, topics, and keywords per topic
    Evidence: .omo/evidence/task-9-keywords.txt
  ```

  **Evidence to Capture**:
  - [ ] evidence/task-9-keywords.txt

  **Commit**: YES (groups with Tasks 6-12)
  - Message: `feat(mcp): add list_keywords MCP tool + topic grouping + multi-language keywords`
  - Files: `src/autoinfo/mcp/server.py`, `src/autoinfo/cli/topics.py`, `src/autoinfo/config.py`, `src/autoinfo/quality.py`, `tests/`
  - Pre-commit: `make test`

- [x] 10. generate_tutorial + generate_presentation MCP tools

  **What to do**:
  - Add 2 handler functions in `src/autoinfo/mcp/server.py`:
    - `_handle_generate_tutorial(domain, topic, format)` — calls existing CLI `autoinfo output tutorial` internally
    - `_handle_generate_presentation(domain, topic, slides)` — calls existing CLI `autoinfo output presentation`
  - The output module already has tutorial and presentation generation (per README) — these MCP tools just wrap the existing functionality
  - Register both in `list_tools()` with appropriate inputSchema
  - Add 2 elif branches in `call_tool()` dispatch
  - Write tests: 1 per tool, verify they return TextContent with output paths

  **Must NOT do**:
  - Do not reimplement tutorial/presentation generation — wrap existing functionality
  - Do not break existing CLI output commands

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Thin wrappers around existing CLI functionality. Low complexity.

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 6, 7, 8, 9, 11, 12)
  - **Parallel Group**: Wave 2
  - **Blocks**: None
  - **Blocked By**: Tasks 1, 2

  **References**:
  - `src/autoinfo/mcp/server.py:164-168` — _handle_collect_sources (pattern for wrapping CLI functions)
  - `src/autoinfo/output.py` — tutorial/presentation generation functions
  - `src/autoinfo/cli/output.py` — CLI output commands

  **Acceptance Criteria**:
  - [ ] `generate_tutorial(domain="medical-research")` returns output path
  - [ ] `generate_presentation(domain="medical-research", slides=5)` returns output path
  - [ ] `pytest tests/ -k "mcp_output"` passes

  **QA Scenarios**:
  ```
  Scenario: generate_tutorial MCP tool works
    Tool: Bash (MCP server test)
    Preconditions: Processed items exist
    Steps:
      1. python -c "from autoinfo.mcp.server import _handle_generate_tutorial; print(_handle_generate_tutorial(domain='medical-research'))"
    Expected Result: Dict with status, output_path
    Evidence: .omo/evidence/task-10-tutorial.txt
  ```

  **Evidence to Capture**:
  - [ ] evidence/task-10-tutorial.txt

  **Commit**: YES (groups with Tasks 6-12)
  - Message: `feat(mcp): add generate_tutorial and generate_presentation MCP tools`
  - Files: `src/autoinfo/mcp/server.py`, `tests/`
  - Pre-commit: `make test`

- [x] 11. --all flag on collect CLI

  **What to do**:
  - Add `--all` / `-A` flag to `autoinfo collect` command in `src/autoinfo/cli/collect.py`
  - When `--all` is True: iterate all active domains in config, run collection for each
  - When `--all` is True: `--domain` flag is ignored (error if both provided?)
  - Add `--topic` support with --all (applies same topic across all domains)
  - Add `--limit` support with --all (applies same limit across all domains)
  - Write tests: 1 for --all flag parsing, 1 for multi-domain collection dispatch

  **Must NOT do**:
  - Do not allow `--all` AND `--domain` simultaneously (error)
  - Do not change existing single-domain collect behavior

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single CLI flag addition. Clear impact, well-scoped.

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 6-10, 12)
  - **Parallel Group**: Wave 2
  - **Blocks**: None
  - **Blocked By**: Task 1 (quality gates foundation, optional but good to have first)

  **References**:
  - `src/autoinfo/cli/collect.py` — collect command definition
  - `src/autoinfo/collect.py` — run_collection function

  **Acceptance Criteria**:
  - [ ] `autoinfo collect --all --limit 1` exits 0 and collects from all active domains
  - [ ] `autoinfo collect --all --domain medical` exits non-zero with clear error
  - [ ] `pytest tests/ -k "collect_all"` passes

  **QA Scenarios**:
  ```
  Scenario: --all flag collects all active domains
    Tool: Bash
    Preconditions: Multiple active domains in config
    Steps:
      1. autoinfo collect --all --limit 1
    Expected Result: Collection runs for each active domain, exit 0
    Evidence: .omo/evidence/task-11-collect-all.txt
  ```

  **Evidence to Capture**:
  - [ ] evidence/task-11-collect-all.txt

  **Commit**: YES (groups with Tasks 6-12)
  - Message: `feat(cli): add --all flag to collect command`
  - Files: `src/autoinfo/cli/collect.py`, `tests/`
  - Pre-commit: `make test`

- [x] 12. test_source with suggested extract_fields + quality tier warnings on add_source

  **What to do**:
  - Update `_handle_test_source()` in `src/autoinfo/mcp/server.py` to return `suggested_extract_fields` in the response — based on source type (PubMed → pmid, doi, authors; RSS → title, pub_date; Web → description, author)
  - Update `_handle_add_source()` in `src/autoinfo/mcp/server.py` to check `quality_tier` of the source being added
  - If tier >= 3, include advisory warning in the response: `"warning": "Quality tier 3+ source — content may have lower authority."`
  - Update test_source CLI command similarly
  - Write tests: 1 for extract_fields suggestion, 1 for tier warning

  **Must NOT do**:
  - Do not block adding tier 3+ sources — just warn
  - Do not change existing add_source behavior

  **Recommended Agent Profile**:
  - **Category**: `unspecified-low`
    - Reason: Small enhancements to existing MCP handlers.

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 6-11)
  - **Parallel Group**: Wave 2
  - **Blocks**: None
  - **Blocked By**: Task 1

  **References**:
  - `src/autoinfo/mcp/server.py` — _handle_test_source and _handle_add_source function locations
  - `src/autoinfo/cli/sources.py` — CLI test_source command
  - `src/autoinfo/quality.py:45-98` — G1SourceAuthority tier definitions

  **Acceptance Criteria**:
  - [ ] test_source response includes `suggested_extract_fields`
  - [ ] add_source returns warning for tier 3+ sources
  - [ ] `pytest tests/ -k "source_warnings"` passes

  **QA Scenarios**:
  ```
  Scenario: test_source returns extract_fields suggestions
    Tool: Bash (MCP server test)
    Preconditions: None
    Steps:
      1. python -c "from autoinfo.mcp.server import _handle_test_source; print(_handle_test_source(url='https://example.com/rss', type='rss'))"
    Expected Result: Response includes suggested_extract_fields with title, pub_date
    Evidence: .omo/evidence/task-12-test-source-fields.txt
  ```

  **Evidence to Capture**:
  - [ ] evidence/task-12-test-source-fields.txt

  **Commit**: YES (groups with Tasks 6-12)
  - Message: `feat(mcp): add extract_fields suggestion + quality tier warnings to source tools`
  - Files: `src/autoinfo/mcp/server.py`, `src/autoinfo/cli/sources.py`, `tests/`
  - Pre-commit: `make test`

- [x] 13. 7 curated demo sources

  **What to do**:
  - Add 7 new curated sources to the demo domain data files in `src/autoinfo/data/domains/`:
    - **medical-research**: arXiv (RSS, tier 2), CrossRef (API, tier 2), Unpaywall (API, tier 2)
    - **ai-commercial**: Crunchbase (RSS, tier 2), LMSYS (RSS + Web, tier 2)
    - **language-learning**: news-in-levels (RSS + Web, tier 2), commonlit (RSS, tier 2)
  - For each source: add to the appropriate `sources.yaml` files with name, type, url, quality_tier
  - For API-based sources (CrossRef, Unpaywall): add handler-level config hints (rate limits, API key optional)
  - Create any missing source templates
  - Test: verify sources appear in `autoinfo sources list --domain medical-research`

  **Must NOT do**:
  - Do not create new source handler implementations for these — use existing RSS/API/web handlers
  - Do not break existing demo sources

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Configuration changes to existing YAML files.

  **Parallelization**:
  - **Can Run In Parallel**: NO (sequential with Tasks 14-17 due to source handler pattern)
  - **Blocks**: Tasks 14-17 (source handlers may need these configured for testing)
  - **Blocked By**: None

  **References**:
  - `src/autoinfo/data/domains/medical-research/sources.yaml` — existing source config
  - `src/autoinfo/data/domains/ai-commercial/sources.yaml` — existing source config
  - `src/autoinfo/data/domains/language-learning/sources.yaml` — existing source config
  - arXiv: `https://rss.arxiv.org/rss/` 
  - CrossRef: `https://api.crossref.org/works`
  - Crunchbase: `https://news.crunchbase.com/feed/`

  **Acceptance Criteria**:
  - [ ] `autoinfo sources list --domain medical-research` shows arXiv, CrossRef, Unpaywall
  - [ ] `autoinfo sources list --domain ai-commercial` shows Crunchbase, LMSYS
  - [ ] `autoinfo sources list --domain language-learning` shows news-in-levels, commonlit
  - [ ] `pytest tests/ -k "curated_sources"` passes

  **QA Scenarios**:
  ```
  Scenario: New curated sources appear in source list
    Tool: Bash
    Preconditions: Domain initialized
    Steps:
      1. autoinfo init --demo medical-research
      2. autoinfo sources list --domain medical-research
    Expected Result: Lists existing + new sources (arXiv, CrossRef, Unpaywall)
    Evidence: .omo/evidence/task-13-curated-sources.txt
  ```

  **Evidence to Capture**:
  - [ ] evidence/task-13-curated-sources.txt

  **Commit**: YES
  - Message: `feat(config): add 7 curated demo sources`
  - Files: `src/autoinfo/data/domains/medical-research/sources.yaml`, `src/autoinfo/data/domains/ai-commercial/sources.yaml`, `src/autoinfo/data/domains/language-learning/sources.yaml`
  - Pre-commit: `make test`

- [x] 14. Webhook source handler

  **What to do**:
  - Create `src/autoinfo/collectors/webhook.py` implementing webhook receiver handler
  - Follow existing collector patterns (`rss.py`, `web.py` as reference)
  - Handler accepts POST payload (JSON), validates required fields (title, content, source_url), creates Item
  - Support HMAC signature verification (optional `secret` config)
  - Support rate limiting (optional `max_requests_per_minute` config)
  - Register handler in collector registry (`__init__.py` or `collect.py` dispatch)
  - Add webhook source type to config schema if needed
  - Write tests: 1 for valid payload, 1 for invalid payload, 1 for HMAC verification

  **Must NOT do**:
  - Do not implement webhook server — this is a message handler, not an HTTP server
  - Do not persist raw payloads beyond item creation

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: New source handler following existing patterns but with different protocol.

  **Parallelization**:
  - **Can Run In Parallel**: NO (sequential with Tasks 15, 16 — share source handler pattern)
  - **Blocks**: None
  - **Blocked By**: Task 13 (sources to configure handlers against)

  **References**:
  - `src/autoinfo/collectors/rss.py` — existing RSS handler (pattern reference)
  - `src/autoinfo/collectors/web.py` — existing web handler (pattern reference)
  - `src/autoinfo/collectors/__init__.py` — collector registry
  - `src/autoinfo/collect.py` — dispatch to handlers

  **Acceptance Criteria**:
  - [ ] Webhook handler creates valid Item from JSON payload
  - [ ] Invalid payload raises appropriate error
  - [ ] HMAC verification works with valid/invalid signatures
  - [ ] `pytest tests/ -k "webhook"` passes

  **QA Scenarios**:
  ```
  Scenario: Webhook handler creates Item from valid payload
    Tool: Bash (python -c)
    Preconditions: None
    Steps:
      1. python -c "from autoinfo.collectors.webhook import WebhookHandler; h=WebhookHandler(); item=h.handle({'title': 'Test', 'content': 'Body', 'source_url': 'https://example.com/hook'}); print(item.title)"
    Expected Result: "Test"
    Evidence: .omo/evidence/task-14-webhook-item.txt
  ```

  **Evidence to Capture**:
  - [ ] evidence/task-14-webhook-item.txt

  **Commit**: YES (groups with Tasks 15, 16)
  - Message: `feat(collectors): add webhook source handler`
  - Files: `src/autoinfo/collectors/webhook.py`, `src/autoinfo/collectors/__init__.py`, `tests/`
  - Pre-commit: `make test`

- [x] 15. Email (IMAP) source handler

  **What to do**:
  - Create `src/autoinfo/collectors/email_imap.py` implementing IMAP email handler
  - Use `imaplib` from stdlib (no external dependency needed)
  - Handler fetches emails from configured IMAP mailbox, extracts: subject → title, body → content, from → author
  - Support IMAP config: host, port, username, password, mailbox (default "INBOX")
  - Support date filter (only fetch emails since last collection)
  - Support attachment handling (skip or extract text from common formats)
  - Register handler in collector registry
  - Add email_imap source type to config schema
  - Write tests: 1 for connection config validation, 1 for email parsing (mock IMAP), 1 for error handling

  **Must NOT do**:
  - Do not use external email libraries (stdlib imaplib is sufficient)
  - Do not store email credentials in code (use config or env vars)
  - Do not implement SMTP sending

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: New source handler using stdlib IMAP. Network I/O with config parsing.

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 16)
  - **Parallel Group**: Wave 3 (with Tasks 14, 16)
  - **Blocks**: None
  - **Blocked By**: Task 13

  **References**:
  - `src/autoinfo/collectors/rss.py` — existing handler pattern
  - Python stdlib `imaplib` — IMAP protocol library
  - `src/autoinfo/models.py` — Item dataclass (fields to populate)

  **Acceptance Criteria**:
  - [ ] Email handler parses IMAP config and validates fields
  - [ ] Mock IMAP connection produces valid Item with title/content/author
  - [ ] `pytest tests/ -k "email_handler"` passes

  **QA Scenarios**:
  ```
  Scenario: Email handler validates config
    Tool: Bash (python -c)
    Preconditions: None
    Steps:
      1. python -c "from autoinfo.collectors.email_imap import EmailHandler; h=EmailHandler(); print(h.validate_config({'host': 'imap.example.com'}))"
    Expected Result: Valid or appropriate error message
    Evidence: .omo/evidence/task-15-email-config.txt
  ```

  **Evidence to Capture**:
  - [ ] evidence/task-15-email-config.txt

  **Commit**: YES (groups with Tasks 14, 16)
  - Message: `feat(collectors): add email (IMAP) source handler`
  - Files: `src/autoinfo/collectors/email_imap.py`, `src/autoinfo/collectors/__init__.py`, `src/autoinfo/config.py`, `tests/`
  - Pre-commit: `make test`

- [x] 16. PDF source handler

  **What to do**:
  - Create `src/autoinfo/collectors/pdf.py` implementing PDF file handler
  - Use `PyMuPDF` (fitz) or `pdfplumber` as PDF extraction library (add to optional dependency)
  - Handler takes file path (local) or URL (download + parse), extracts text content
  - Support metadata extraction: title, author, subject, keywords from PDF metadata
  - Support chunking for large PDFs (split into multiple Items by page or section)
  - Register handler in collector registry
  - Add pdf source type to config schema
  - Write tests: 1 for text extraction from PDF, 1 for metadata parsing, 1 for URL download + parse

  **Must NOT do**:
  - Do not add PDF generation capability
  - Do not make PyMuPDF a hard dependency (optional/extras)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: New source handler with external library dependency. Text extraction and chunking.

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 15)
  - **Parallel Group**: Wave 3 (with Tasks 14, 15)
  - **Blocks**: None
  - **Blocked By**: Task 13

  **References**:
  - `src/autoinfo/collectors/web.py` — existing web handler (URL download pattern)
  - `src/autoinfo/models.py` — Item dataclass
  - PyMuPDF docs: `https://pymupdf.readthedocs.io/`

  **Acceptance Criteria**:
  - [ ] PDF handler extracts text from PDF file
  - [ ] PDF handler extracts metadata (title, author)
  - [ ] PDF handler downloads PDF from URL
  - [ ] `pytest tests/ -k "pdf_handler"` passes

  **QA Scenarios**:
  ```
  Scenario: PDF handler extracts text from file
    Tool: Bash (python -c)
    Preconditions: Test PDF file exists
    Steps:
      1. python -c "from autoinfo.collectors.pdf import PDFHandler; h=PDFHandler(); items=h.extract('/tmp/test.pdf'); print(len(items), items[0].title)"
    Expected Result: At least one Item with extracted content
    Evidence: .omo/evidence/task-16-pdf-extract.txt
  ```

  **Evidence to Capture**:
  - [ ] evidence/task-16-pdf-extract.txt

  **Commit**: YES (groups with Tasks 14, 15)
  - Message: `feat(collectors): add PDF source handler`
  - Files: `src/autoinfo/collectors/pdf.py`, `src/autoinfo/collectors/__init__.py`, `pyproject.toml`, `tests/`
  - Pre-commit: `make test`

- [x] 17. Knowledge graph export CLI

  **What to do**:
  - Add `autoinfo knowledge graph export` CLI command in `src/autoinfo/cli/knowledge.py` (or add to existing kb.py)
  - Export knowledge graph data (entities + relations from KB) to a file format
  - Support `--format` flag: `json` (default), `graphml`, `csv`
  - Support `--domain` filter
  - Use existing `query_knowledge_graph()` / `get_item_relations()` from MCP server as data source
  - Write tests: 1 for JSON export, 1 for domain filter

  **Must NOT do**:
  - Do not make graph export a blocking operation for large KBs (stream if needed, but v1.1 can be simple)
  - Do not reimplement KG query — reuse existing functions

  **Recommended Agent Profile**:
  - **Category**: `unspecified-low`
    - Reason: CLI wrapper around existing KG query functionality. Low complexity.

  **Parallelization**:
  - **Can Run In Parallel**: NO (needs KB with KG data)
  - **Blocks**: None
  - **Blocked By**: Task 13 (needs processed data for meaningful export)

  **References**:
  - `src/autoinfo/mcp/server.py` — query_knowledge_graph handler
  - `src/autoinfo/cli/kb.py` — existing KB CLI commands (pattern for new command)
  - `src/autoinfo/output.py` — existing export functions (pattern reference)

  **Acceptance Criteria**:
  - [ ] `autoinfo knowledge graph export --domain medical --format json` produces JSON file
  - [ ] Exported JSON contains entities and relations
  - [ ] `pytest tests/ -k "kg_export"` passes

  **QA Scenarios**:
  ```
  Scenario: Knowledge graph export to JSON
    Tool: Bash
    Preconditions: Processed items with entities exist
    Steps:
      1. autoinfo knowledge graph export --domain medical-research --format json --output /tmp/kg.json
      2. python -c "import json; d=json.load(open('/tmp/kg.json')); print(len(d.get('entities',[])), len(d.get('relations',[])))"
    Expected Result: Non-zero entity and relation counts
    Evidence: .omo/evidence/task-17-kg-export.txt
  ```

  **Evidence to Capture**:
  - [ ] evidence/task-17-kg-export.txt

  **Commit**: YES
  - Message: `feat(cli): add knowledge graph export CLI command`
  - Files: `src/autoinfo/cli/knowledge.py`, `tests/`
  - Pre-commit: `make test`

- [x] 18. README update: Known Limitations + quality gate status correction

  **What to do**:
  - Add "Known Limitations" section at the end of README.md listing:
    - G5 translation accuracy gate — implemented but advisory only
    - Draft→Wiki promote — human-only, CLI-only (not MCP)
    - 7 deferred items: hybrid/vector search, REST API, Obsidian [[wiki links]], CEFR classification, config override system, schema versioning/migration, CSV/PDF/GraphML export — planned for future releases
  - Fix the Status table (README.md:32): change "G1-G5 all functional" badge to note these are advisory gates
  - Update MCP tool table (README.md MCP Tools section) to reflect the 6 new tools: get_collection_progress, get_collection_status, activate_domain, deactivate_domain, get_domain_config, list_keywords, generate_tutorial, generate_presentation
  - Add a note: "56 MCP tools (was 50 in v1.0) — 6 new MCP tool areas in v1.1"
  - Update any stale version/status information

  **Must NOT do**:
  - Do not remove or downplay existing features in the README
  - Do not make the README seem incomplete — frame limitations as "planned for future releases"

  **Recommended Agent Profile**:
  - **Category**: `writing`
    - Reason: Documentation update requiring accurate technical writing.

  **Parallelization**:
  - **Can Run In Parallel**: NO (must reflect actual implementation state)
  - **Blocks**: None
  - **Blocked By**: All tasks 1-17 (to accurately reflect v1.1 state)

  **References**:
  - `README.md` — entire file (line-by-line update needed)
  - `CHANGELOG.md` — add v1.1 entry

  **Acceptance Criteria**:
  - [ ] README has "Known Limitations" section listing deferred items
  - [ ] Status table says "G1-G5 advisory" instead of "all functional"
  - [ ] MCP tool count updated to 56 (50 + 6 new)
  - [ ] README accurately reflects v1.1 implementation state

  **QA Scenarios**:
  ```
  Scenario: README Known Limitations section present
    Tool: Bash (grep)
    Preconditions: None
    Steps:
      1. grep -c "Known Limitations" README.md
    Expected Result: 1 (section exists)
    Evidence: .omo/evidence/task-18-readme-limitations.txt

  Scenario: MCP tool count updated
    Tool: Bash (grep)
    Preconditions: None
    Steps:
      1. grep -oP '\d+ MCP tools' README.md
    Expected Result: Shows updated count (e.g., "56 MCP tools")
    Evidence: .omo/evidence/task-18-readme-toolcount.txt
  ```

  **Evidence to Capture**:
  - [ ] evidence/task-18-readme-limitations.txt
  - [ ] evidence/task-18-readme-toolcount.txt

  **Commit**: YES
  - Message: `docs(readme): add Known Limitations section + update v1.1 status`
  - Files: `README.md`, `CHANGELOG.md`
  - Pre-commit: `grep "Known Limitations" README.md`

---

## Final Verification Wave

- [x] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, run command, check output). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in .omo/evidence/. Compare deliverables against the 18 identified gaps.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [x] F2. **Code Quality Review** — `unspecified-high`
  Run `ruff check` + `make test`. Review all changed files for: `as any`/`@ts-ignore`, empty catches, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic names.
  Output: `Lint [PASS/FAIL] | Tests [N pass/N fail] | Files [N clean/N issues] | VERDICT`

- [x] F3. **Real Manual QA** — `unspecified-high`
  Start from clean `autoinfo init --demo medical-research`. Execute EVERY QA scenario from EVERY task — follow exact steps, capture evidence. Test cross-task integration (e.g., G5 → process → KB store). Test edge cases. Save to `.omo/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Evidence [N files] | VERDICT`

- [x] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff (git log/diff). Verify 1:1 — everything in spec was built (no missing), nothing beyond spec was built (no creep). Check "Must NOT do" compliance. Detect cross-task contamination.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

- **1-5**: `feat(quality): add G5 translation accuracy gate` + `feat(kb): add promote_kb_draft()` + `feat(cli): init dirs + wizard` + `feat(kb): frontmatter expansion` + `feat(process): language auto-detection`
- **6-12**: (per MCP tool or tool group)
- **13**: `feat(config): add 7 curated demo sources`
- **14-16**: `feat(collectors): add webhook/email/PDF source handlers`
- **17**: `feat(cli): add knowledge graph export`
- **18**: `docs(readme): add Known Limitations section`
- **F1-F4**: Squash as `chore(release): v1.1 gap-fill completion`

---

## Success Criteria

### Verification Commands
```bash
make test  # Expected: 770+ tests passing, 0 failures
autoinfo init --demo medical-research && ls .autoinfo/knowledge/  # Expected: 00-Inbox 01-Raw 02-Draft 03-Wiki
autoinfo kb promote --help  # Expected: promote command available
autoinfo collect --all --limit 1  # Expected: collects across all active domains
autoinfo process --check-translation --domain medical-research  # Expected: G5 runs on translated items
```

### Final Checklist
- [ ] All 18 gaps closed with verified implementations
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent (no promote MCP tool, no 03-Wiki agent writes)
- [ ] All 720+ pre-existing tests pass + ~50-100 new tests pass
- [ ] README has Known Limitations section listing 7 deferred items
- [ ] All QA scenario evidence captured in .omo/evidence/
