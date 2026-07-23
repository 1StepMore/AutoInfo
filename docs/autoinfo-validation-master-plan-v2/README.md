# AutoInfo Master Validation Plan v2 — 100% Feature Coverage

**For:** OpenCode, Claude Code, Cline, Hermes Agent — any AI agent validating AutoInfo
**Date:** 2026-07-23
**Baseline:** AutoInfo v1.4 — 1134 tests, 17 CLI command groups, 72 MCP tools (16 categories), Hermes KB pipeline (4 tiers), 6 collector types, 6 output/export formats, REST API, Web UI, domain management, webhook push, cron digest, CEFR classification, translation QA

---

## Purpose

Replace the original `autoinfo-validation-master-plan.md` (~40% coverage) with a comprehensive plan covering **100% of AutoInfo's feature surface**. Every CLI command, MCP tool, KB tier, quality gate, search mode, output format, API endpoint, async operation, and integration point has explicit scenarios.

---

## How to Use This Plan

```yaml
1. Pick a FEATURE AREA from the table of contents
2. Read ALL scenarios under it
3. Execute each scenario (CLI, MCP, Python, or curl)
4. Record ACTUAL RESULT for each step
5. Compare ACTUAL vs EXPECTED
6. Report VERDICT at the end of the section
```

**Output checking rule**: Every scenario specifies:
- The **exact command/tool** to run (including all arguments)
- The **expected exit code / response shape / file artifact**
- An **explicit PASS/FAIL check** (binary observable)

**Improvement over v1**: v2 adds:
- All 17 CLI commands with per-subcommand scenarios (was 6/17)
- All 72 MCP tools with parameter validation (was 8/72)
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

---

## Table of Contents

| Part | File | Questions | Coverage |
|------|------|-----------|----------|
| 0 | `README.md` | — | Index, prerequisites, common patterns |
| 1 | `part-01-core-pipeline.md` | Q1-Q6 | Init → Collect → Process → Browse → Status → Doctor |
| 2 | `part-02-cli-full.md` | Q7-Q20 | All 17 CLI commands with subcommand testing |
| 3 | `part-03-mcp-system-tools.md` | Q21-Q27 | MCP: System, Discovery, Domain, Source, Topic tools |
| 4 | `part-04-mcp-kb-output.md` | Q28-Q36 | MCP: KB (all tiers), Search, Output, Cron, Email, CEFR |
| 5 | `part-05-quality-gates.md` | Q37-Q41 | G1 source authority, G2 dedup, G3 relevance, G4 factual, G5 translation |
| 6 | `part-06-kb-pipeline.md` | Q42-Q46 | KB 4-tier (Inbox→Raw→Draft→Wiki), import/export, versioning, relations, graph |
| 7 | `part-07-rest-api-webui.md` | Q47-Q48 | REST API CRUD (FastAPI port 8741), Web UI dashboard |
| 8 | `part-08-agent-e2e.md` | Q49-Q53 | Real API E2E (PubMed/RSS/Web + real LLM), multi-domain, config override |
| 9 | `part-09-async-cron-email.md` | Q54-Q58 | Async job_id polling, cron schedules, email digests, webhooks, agent alerting |
| 10 | `part-10-error-boundary.md` | Q59 | Comprehensive error/boundary matrix (all layers) |
| 11 | `part-11-production-validation.md` | Q60 | Doctor diagnostics, MCP stdio, stress test, test suite |
| 12 | `part-12-final-verdict.md` | — | Summary verdict, production gap checklist, sign-off criteria |

**Total: 60 questions, 12 part files + verdict**

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
pytest --collect-only -q  # Should collect 1134+ tests without errors

# 3. Set minimum env vars
export AUTOINFO_LLM_API_KEY="sk-dummy-for-testing"

# 4. Verify CLI works
autoinfo --help  # Should show 17 command groups
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
| CLI commands tested | 6/17 (35%) | 17/17 (100%) | 📝 Part 2 |
| MCP tools tested | 8/72 (11%) | 72/72 (100%) | 📝 Parts 3-4 |
| KB tiers tested | 1/4 (01-Raw only) | 4/4 (Inbox→Raw→Draft→Wiki) | 📝 Part 6 |
| Quality gates tested | 3/5 (G1-G3) | 5/5 (G1-G5) | 📝 Part 5 |
| Search modes tested | 1 (summaries list) | 6 (FTS5, vector, hybrid, faceted, Q&A, graph) | 📝 Part 6 |
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
| Sources | `.autoinfo/sources.yaml` |
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

---

## File Organization

```
docs/autoinfo-validation-master-plan-v2/
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
└── part-12-final-verdict.md
```

---

## Next Steps

1. Start with **Part 1** (core pipeline) to validate the foundational workflow
2. Proceed to **Part 2** (full CLI) to verify every command surface
3. Then **Parts 3-4** (MCP) to validate the agent-facing interface
4. Continue with remaining parts in any order (they have no interdependencies)
5. End with **Part 12** (final verdict) to produce the overall PASS/FAIL summary
