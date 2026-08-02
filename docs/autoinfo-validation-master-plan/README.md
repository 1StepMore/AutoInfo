# AutoInfo Master Validation Plan v2 — 100% Feature Coverage

**For:** OpenCode, Claude Code, Cline, Hermes Agent — any AI agent validating AutoInfo
**Date:** 2026-07-27 (initial); 2026-08-02 updates appended (question count reconciled with part-12 rollup, test count refreshed, new scenarios noted)
**Baseline:** AutoInfo v1.8 — ~2747 test functions across 103 files (approximation; was 2537 at v1.8 baseline, grew with v1.8.1/v1.8.4 collector + E12/E14/E9/C11 tests), 23 CLI command groups, 139 MCP tools (34 categories), KB pipeline (4 tiers), 26 collector handlers, 10 output/export formats, REST API, Web UI, domain management, webhook push, cron digest, CEFR classification, translation QA, multi-channel delivery (13 channels), end user lifecycle, cost governance, audit logging, structured pipeline logging, per-item traceability, knowledge lifecycle (TTL, versioned re-collection, decay metrics, cross-collection dedup & merge), Prometheus metrics, subscription tier gating (Free/Premium/Enterprise), consumption tracking, automated notifications, channel health monitoring, cron health monitoring, SQLite backup/restore

> **Spec references**: See `docs/dev/specs/` for the full specification (11 files). See also `docs/dev/cross-dimensional-catalog.md` (keystone product matrix, supersedes gap audit docs). See `docs/archive/` for superseded/one-time historical docs including `reality-assessment.md` (archived).

---

## Purpose

Replace the original `docs/archive/autoinfo-validation-master-plan.md` (~40% coverage) with a comprehensive plan covering **100% of AutoInfo's feature surface**. Every CLI command, MCP tool, KB tier, quality gate, search mode, output format, API endpoint, async operation, and integration point has explicit scenarios.

---

## How to Use This Plan (Agent-Oriented)

> Each scenario now uses the **Self-Executing Assert Pattern** (defined below) — a self-contained bash wrapper that executes commands, checks per-assertion grep/test conditions, and returns a single `exit 0`/`exit 1` verdict. See the [Self-Executing Assert Pattern](#self-executing-assert-pattern) section for the full spec and a worked example.

### Execution Loop

For each **question** (Q1, Q2, ...) in any part file:

```
STEP 1: Run the part-level directory setup (once per part file)
STEP 2: For each scenario N.M:
          a. Run the command in the bash/code block
          b. Check expected results (exit code, output, files)
          c. Update the Q verdict table: replace ⬜ → ✅ or ❌
STEP 3: Compute OVERALL per-question verdict
```

### Agent Assertion Pattern

Every scenario follows this structure:

```markdown
#### N.M 🟢/🔴 Description
```bash
<command to execute>
```
**Expected Result:**
- ✅ <binary-observable-assertion-1>
- ✅ <binary-observable-assertion-2>
```

**As an agent, for each scenario you must:**
1. Execute the command block
2. For each `✅` bullet: verify that assertion holds → PASS, or it fails → FAIL
3. For each `❌` bullet: verify that the error/absence holds → PASS, or it doesn't → FAIL
4. Record the verdict in the Q's verdict table

### Verdict Table Convention

Each question has a verdict table:
```
| Scenario | Result |
|----------|--------|
| 1.1 Happy path init | ⬜ |
```
Replace `⬜` with:
- `✅`  — all expected results match
- `❌`  — one or more expected results do NOT match
- `⚠️`  — partial pass (some checks pass, some fail)
- `➖`  — skipped (document reason in notes)

Each question also has `**OVERALL: ⬜**` — set to the aggregate of all scenarios.

### Part-Level Directory Setup

Each part file now has a `### Part-Level Directory Setup` block right after the Part heading. Run this ONCE at the start of the part to create clean working directories for all questions.

**Do NOT skip this step** — each question's individual setup now assumes the directory already exists and only runs `cd /tmp/test-qN`.

### LLM-Dependent Sections

Sections marked `[REQUIRES LLM KEY]` need a real LLM API key. If unavailable:
- Mark those scenarios as `➖ SKIP` in the verdict table
- Note the reason: "No LLM key available"
- Continue with the remaining scenarios

The same applies to `[REQUIRES SMTP]` sections.

### Final Deliverable

After executing all 15 parts, produce a summary verdict table in `part-12-final-verdict.md` covering every Q with ✅/❌/⚠️/➖ per question and an overall project verdict.

**Improvement over v1**: v2 adds:
- All 22 CLI commands with per-subcommand scenarios (was 6/17 in v1, expanded from 17 in v1.4)
- All 139 MCP tools with parameter validation (was 8/72 in v1, expanded from 72 in v1.4)
- 4-tier KB pipeline: 00-Inbox → 01-Raw → 02-Draft → 03-Wiki (was only 01-Raw)
- Quality gates G1-G5 (was G1-G3 only)
- All search modes: FTS5, vector, hybrid, faceted, Q&A, knowledge graph
- REST API + Web UI dashboard
- All output formats: digest, report (MD/JSON/PDF/HTML), tutorial, presentation, export, localize
- Cron schedules, email sending, webhooks
- CEFR classification
- Keywords lifecycle
- Async job_id polling pattern
- Custom extraction
- KB import/export/versioning/relations
- Agent alerting / source health monitoring
- Error/boundary matrix across every layer
- Knowledge lifecycle (TTL, versioning, decay, dedup/merge)
- End User MCP tools (trial, preferences, subscription, history, delivery log)
- Cost governance (billing, budgets, checkout, usage, invoices)
- Data privacy MCP (GDPR export, right to erasure)
- Agent callback subscription pattern (register/list/remove callbacks)
- Observability MCP (trace_item, get_metrics, get_prometheus_metrics)
- Quality Gate Config and Alert Rules management

---

## Self-Executing Assert Pattern

Each scenario in this validation plan can be executed as a **self-contained bash script** that:
1. Runs the command under test
2. Checks each expected-result assertion with `grep`/`test`
3. Emits a single `exit 0` (PASS) or `exit 1` (FAIL) verdict

This makes scenarios **agent-verifiable**: agents execute the script and check `$?` — no human interpretation needed.

### Bash Wrapper Template

```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

# ── Execute command ──────────────────────────────────────────
OUTPUT=$(<command> 2>&1)
EXIT_CODE=$?

# ── Per-assertion checks ──────────────────────────────────────
echo "$OUTPUT" | grep -q "expected pattern 1" \
  && echo "  ✅ PASS: description 1" \
  || { echo "  ❌ FAIL: description 1"; ALL_PASS=false; }

echo "$OUTPUT" | grep -q "expected pattern 2" \
  && echo "  ✅ PASS: description 2" \
  || { echo "  ❌ FAIL: description 2"; ALL_PASS=false; }

[ "$EXIT_CODE" -eq 0 ] \
  && echo "  ✅ PASS: exit code 0" \
  || { echo "  ❌ FAIL: exit code $EXIT_CODE (expected 0)"; ALL_PASS=false; }

# ── Filesystem assertions (when applicable) ──────────────────
[ -f "/tmp/test-q1/.autoinfo/config.yaml" ] \
  && echo "  ✅ PASS: config.yaml created" \
  || { echo "  ❌ FAIL: config.yaml missing"; ALL_PASS=false; }

# ── Verdict ───────────────────────────────────────────────────
if [ "$ALL_PASS" = true ]; then
  echo ""
  echo "✅ SCENARIO PASSED"
  exit 0
else
  echo ""
  echo "❌ SCENARIO FAILED"
  exit 1
fi
```

### Assertion Patterns Reference

| Check Type | grep/test Pattern | Use Case |
|-----------|-------------------|----------|
| String in stdout | `echo "$OUTPUT" \| grep -q "text"` | CLI output contains expected text |
| String absent | `! echo "$OUTPUT" \| grep -q "text"` | Error message should NOT appear |
| Regex match | `echo "$OUTPUT" \| grep -qP "regex"` | Structured output pattern validation |
| Exit code zero | `[ "$EXIT_CODE" -eq 0 ]` | Command succeeds |
| Exit code non-zero | `[ "$EXIT_CODE" -ne 0 ]` | Command expected to fail |
| File exists | `[ -f "path" ]` | Config/KB/file artifact created |
| Directory exists | `[ -d "path" ]` | Output/KB directory created |
| File non-empty | `[ -s "path" ]` | Collection cache has content |
| JSON key present | `echo "$OUTPUT" \| python3 -c "import sys,json; json.load(sys.stdin)['key']"` | JSON output contains expected key |

### Worked Example: Init Scenario from Part 01

This is Scenario 1.1 from `part-01-core-pipeline.md`, wrapped as a self-executing assert script:

```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
TEST_DIR="/tmp/test-q1"
DOMAIN="medical-research"

# ── Setup ─────────────────────────────────────────────────────
rm -rf "$TEST_DIR"
mkdir -p "$TEST_DIR"

# ── Execute: autoinfo init ────────────────────────────────────
cd "$TEST_DIR"
OUTPUT=$(autoinfo init --demo "$DOMAIN" 2>&1)
EXIT_CODE=$?

# ── Assertions ────────────────────────────────────────────────
echo "$OUTPUT" | grep -q "AutoInfo project initialized" \
  && echo "  ✅ PASS: init success message" \
  || { echo "  ❌ FAIL: no init success message"; ALL_PASS=false; }

echo "$OUTPUT" | grep -qi "$DOMAIN" \
  && echo "  ✅ PASS: domain name appears in output" \
  || { echo "  ❌ FAIL: domain not in output"; ALL_PASS=false; }

[ "$EXIT_CODE" -eq 0 ] \
  && echo "  ✅ PASS: exit code 0" \
  || { echo "  ❌ FAIL: exit code $EXIT_CODE (expected 0)"; ALL_PASS=false; }

[ -f "$TEST_DIR/.autoinfo/config.yaml" ] \
  && echo "  ✅ PASS: config.yaml created" \
  || { echo "  ❌ FAIL: config.yaml missing"; ALL_PASS=false; }

[ -s "$TEST_DIR/.autoinfo/config.yaml" ] \
  && grep -q "medical-research" "$TEST_DIR/.autoinfo/config.yaml" \
  && echo "  ✅ PASS: domain sources embedded in config.yaml" \
  || { echo "  ❌ FAIL: domain sources not in config.yaml"; ALL_PASS=false; }

# ── Verdict ───────────────────────────────────────────────────
if [ "$ALL_PASS" = true ]; then
  echo ""
  echo "✅ SCENARIO 1.1 PASSED — init $DOMAIN"
  exit 0
else
  echo ""
  echo "❌ SCENARIO 1.1 FAILED — init $DOMAIN"
  exit 1
fi
```

### Agent Usage

Agents executing this plan should:
1. **Convert** each scenario's command + expected results into a self-contained script using the template above
2. **Execute** the script with `bash scenario-N.M.sh`
3. **Check** `$?` — 0 means all assertions passed, non-zero means at least one failed
4. **Record** the verdict in the Q verdict table: `✅` for exit 0, `❌` for exit 1

This pattern eliminates ambiguous "looks good" verdicts — every assertion is binary and machine-checkable.

---

## Table of Contents

| Part | File | Questions | Coverage |
|------|------|-----------|----------|
| 0 | `README.md` | — | Index, prerequisites, common patterns |
| 1 | `part-01-core-pipeline.md` | Q1-Q6b | Init → Collect (9 demo domains) → Process → Browse → Status → Doctor |
| 2 | `part-02-cli-full.md` | Q7-Q20 | All 22 CLI commands with subcommand testing |
| 3 | `part-03-mcp-system-tools.md` | Q21-Q27i | MCP: System, Discovery, Domain, Source, Topic, Collection, Projects, Monitor, Webhooks, Source Health, Quality Gate Config, Alert Rules, Email, KB Entry, KB Graph, CEFR, Cost, Audit |
| 4 | `part-04-mcp-kb-output.md` | Q28-Q36c | MCP: KB (all tiers), Search, Output, Cron, Email, CEFR, Knowledge Lifecycle, Product |
| 5 | `part-05-quality-gates.md` | Q37-Q41 | G1 source authority, G2 dedup, G3 relevance, G4 factual, G5 translation |
| 6 | `part-06-kb-pipeline.md` | Q42-Q46 | KB 4-tier (Inbox→Raw→Draft→Wiki), import/export, versioning, relations, graph |
| 7 | `part-07-rest-api-webui.md` | Q47-Q48 | REST API CRUD (FastAPI port 8741), Web UI dashboard |
| 8 | `part-08-agent-e2e.md` | Q49-Q53 | Real API E2E (PubMed/RSS/Web + real LLM), multi-domain, config override |
| 9 | `part-09-async-cron-email.md` | Q54-Q58 | Async job_id polling, cron schedules, email digests, webhooks, agent alerting |
| 10 | `part-10-error-boundary.md` | Q59 | Comprehensive error/boundary matrix (all layers) |
| 11 | `part-11-production-validation.md` | Q60 | Doctor diagnostics, MCP stdio, stress test, test suite, observability |
| 12 | `part-12-final-verdict.md` | — | Summary verdict, production gap checklist, sign-off criteria |
| 13 | `part-13-enduser-lifecycle.md` | Q61-Q65h | End User lifecycle: profile & subscription CRUD, state machine, multi-channel delivery (19 scenarios in Q63), product delivery SLA, self-service portal, data privacy, End User MCP (8 tools), Cost/Billing (6 tools), GDPR MCP tools, Stripe webhook billing lifecycle, Consumption tracking, Cost & Usage E2E (Q65h) |
| 14 | `part-14-human-agent-collaboration.md` | Q66-Q69 | Human-Agent collaboration: ambiguous intent clarification, failure escalation, human review & iteration, human override & compliance |
| 15 | `part-15-cross-dimension-e2e.md` | Q70-Q71b | Cross-dimension E2E journey spanning Director User → Direct User (Agent) → End User, Agent Callbacks |

**Total: 98 questions (per part-12 rollup) across 15 part files + verdict.** Note: the Table of Contents above lists 76 top-level question IDs (Q1-Q72); the part-12 final-verdict rollup counts 98 when including sub-question variants (Q6b, Q27b-Q27i, Q36b-Q36e, Q41a-Q41c, Q65b-Q65h, Q71b) that carry independent verdict rows. The 98 figure is the authoritative total used in the part-12 sign-off criteria.

---

## Verdict Legend

| Symbol | Meaning |
|--------|---------|
| ✅ PASS | All scenarios in this section match expected results |
| ❌ FAIL | One or more scenarios did NOT match expected results |
| ⚠️ PARTIAL | Some scenarios pass, some fail (list which ones) |
| ➖ SKIP | Scenarios intentionally skipped (reason documented) |

---

## Prerequisites

```bash
# 1. Install the package with dev dependencies
pip install -e ".[dev]"

# 2. Verify test infrastructure
pytest --collect-only -q  # Should collect ~2747 tests without errors (approximation; was 2183+ at v1.4, 2537 at v1.8 baseline)

# 3. Set minimum env vars
export AUTOINFO_LLM_API_KEY="sk-dummy-for-testing"

# 4. Verify CLI works
autoinfo --help  # Should show 23 command groups
```

### LLM-Dependent Sections

Some sections require a real LLM API key. These are marked **[REQUIRES LLM KEY]**.
These sections typically involve `process`, `G4`, `G5`, `cefr`, `generate_*` tools, and `query_collected`.
For sections requiring SMTP config, a working SMTP server is needed.

### Common Helper Functions

Many scenarios use these Python snippets for validation:

```python
# Verify JSON output
import sys, json
data = json.load(sys.stdin)
assert "expected_key" in data

# Verify exit code + output
import subprocess
r = subprocess.run(["autoinfo", "doctor", "--json"], capture_output=True, text=True)
assert r.returncode == 0
data = json.loads(r.stdout)
```

### Common CLI Flags

All CLI commands support these **global flags**:
- `--json` — JSON output mode (structured data for agent consumption)
- `--help` — Show help for any command/subcommand

---

## Target vs. Covered Feature Matrix

| Feature Area | Existing v1 | v2 Target | Status |
|-------------|-------------|-----------|--------|
| CLI commands tested | 6/17 (35%) | 23/23 (100%) | 📝 Part 2 |
| MCP tools tested | 8/72 (11%) | 139/139 (100%) | 📝 Parts 3-4 |
| KB tiers tested | 1/4 (01-Raw only) | 4/4 (Inbox→Raw→Draft→Wiki) | 📝 Part 6 |
| Quality gates tested | 3/5 (G1-G3) | 5/5 (G1-G5) | 📝 Part 5 |
| Search modes tested | 1 (summaries list) | FTS5 (currently only FTS5 implemented; vector/hybrid/faceted/Q&A/graph planned) | 📝 Part 6 |
| REST API | 0% | 100% (all endpoints) | 📝 Part 7 |
| Web UI | 0% | 100% (dashboard) | 📝 Part 7 |
| Output formats | 0% | 100% (digest/report/tutorial/presentation/export/localize) | 📝 Part 4 |
| Cron/schedules | 0% | 100% | 📝 Part 9 |
| Email sending | 0% | 100% | 📝 Part 9 |
| CEFR classification | 0% | 100% | 📝 Part 4 |
| Keywords lifecycle | 0% | 100% | 📝 Part 4 |
| Webhooks | 0% | 100% | 📝 Part 9 |
| Domain management | 0% | 100% | 📝 Part 3 |
| Async job_id polling | 0% | 100% | 📝 Part 9 |
| Custom extraction | 0% | 100% | 📝 Part 4 |
| KB import/export | 0% | 100% | 📝 Part 6 |
| KB versioning/relations | 0% | 100% | 📝 Part 6 |
| E2E real API tests | Q20-Q23 | Full expansion | 📝 Part 8 |

---

## Quick Reference: Important Paths

| Resource | Path Pattern |
|----------|-------------|
| Config | `.autoinfo/config.yaml` |
| Sources | `.autoinfo/config.yaml` → `domains[].sources` (embedded per domain; no standalone sources.yaml) |
| Collection cache | `collections/<domain>/<source>/<date>/<id>.json` |
| KB 01-Raw files | `knowledge/<domain>/01-Raw/<topic>/<date>-<slug>.md` |
| KB 02-Draft files | `knowledge/<domain>/02-Draft/<topic>/<date>-<slug>.md` |
| KB 03-Wiki files | `knowledge/<domain>/03-Wiki/<topic>/<date>-<slug>.md` |
| SQLite index | `autoinfo.db` (in project root) |
| Outputs | `outputs/<domain>/<type>/<filename>` |
| Exports | `exports/<domain>/<topic>/<filename>` |
| REST API | `http://127.0.0.1:8741/api/v1/...` |
| Web UI | `http://127.0.0.1:8741/dashboard` |
| MCP server | `python -m autoinfo.mcp.server` (stdio) |
| Archives | `docs/archive/` — superseded/one-time docs |

---

## File Organization

```
docs/autoinfo-validation-master-plan/
├── README.md              ← You are here
├── part-01-core-pipeline.md
├── part-02-cli-full.md
├── part-03-mcp-system-tools.md
├── part-04-mcp-kb-output.md
├── part-05-quality-gates.md
├── part-06-kb-pipeline.md
├── part-07-rest-api-webui.md
├── part-08-agent-e2e.md
├── part-09-async-cron-email.md
├── part-10-error-boundary.md
├── part-11-production-validation.md
├── part-12-final-verdict.md
├── part-13-enduser-lifecycle.md
├── part-14-human-agent-collaboration.md
└── part-15-cross-dimension-e2e.md
```

---

## Next Steps

1. Start with **Part 1** (core pipeline) to validate the foundational workflow
2. Proceed to **Part 2** (full CLI) to verify every command surface
3. Then **Parts 3-4** (MCP) to validate the agent-facing interface
4. Continue with remaining parts in any order (they have no interdependencies)
5. End with **Part 12** (final verdict) to produce the overall PASS/FAIL summary
