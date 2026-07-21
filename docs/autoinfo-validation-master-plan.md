# AutoInfo Master Validation Plan

## Result-Oriented · User-Centric · All Scenarios & Boundaries

**For:** OpenCode, Claude Code, Cline, Hermes Agent — any AI agent validating AutoInfo
**Date:** 2026-07-20
**Strategy:** Every section asks a user question → executes scenarios → reports a binary verdict
**Current Baseline:** v1.3 full feature set — 1134 tests, 14 CLI command groups, 65 MCP tools across 15 categories, FastAPI REST API, Bootstrap 5 Web UI

---

## How to Use This Plan

```yaml
1. Pick a USER QUESTION from the table of contents
2. Read the scenarios under it
3. Execute each scenario (CLI, MCP, or Python)
4. Record the ACTUAL RESULT
5. Compare ACTUAL vs EXPECTED
6. Report the VERDICT at the end of the section
```

The plan is designed so that any AI agent can execute it independently and report: **"✅ All PASS"** or **"❌ These N items FAILED"**.

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

Before running validation, ensure:

```bash
# 1. Install the package with dev dependencies
pip install -e ".[dev]"

# 2. Verify test infrastructure
pytest --collect-only -q  # Should collect 800+ tests without errors

# 3. Set minimum env vars
export AUTOINFO_LLM_API_KEY="sk-dummy-for-testing"

# 4. Verify CLI works
autoinfo --help  # Should show 14 command groups
```

---

## Table of Contents

### Part 1: Core Pipeline Journeys
- **Q1:** Can I initialize a project and configure sources?
- **Q2:** Can I collect from PubMed and RSS sources?
- **Q3:** Can I process collected items (LLM extraction + quality gates + KB storage)?
- **Q4:** Can I browse summaries, status, and health?

### Part 2: CLI Surface Mastery
- **Q5:** Does every CLI command work correctly? (6 commands)
- **Q6:** Does CLI handle edge cases gracefully?

### Part 3: MCP Surface Mastery
- **Q7:** Does every MCP tool work correctly? (6 tools)

### Part 4: Agent-as-User Real API Configuration & E2E Tests
- **Q20:** Can an agent configure real info platform APIs and run E2E collection tests?
- **Q21:** Can an agent configure real LLM APIs and run E2E processing tests?
- **Q22:** Can an agent execute the full pipeline with real APIs end-to-end?
- **Q23:** Can an agent detect, diagnose, and recover from real API configuration issues?

### Part 5: Quality Gate Validation
- **Q8:** Does each quality gate (G1-G3) pass/fail correctly?
- **Q9:** Are quality gates advisory (never block/discard)?

### Part 6: KB Storage & Search
- **Q10:** Are KB entries stored as correct Markdown files?
- **Q11:** Does SQLite metadata index work correctly?
- **Q12:** Is dedup working (URL + PMID/DOI)?

### Part 7: Error & Boundary Matrix
- **Q13:** What happens with missing/corrupt/empty inputs?
- **Q14:** What happens with missing config/env vars?
- **Q15:** What happens with network errors (PubMed timeout)?
- **Q16:** What happens with LLM errors (timeout, malformed response)?

### Part 8: Production Validation
- **Q17:** Does `autoinfo doctor` detect all system issues?
- **Q18:** Does the MCP server work via stdio process?
- **Q19:** Can the full pipeline run without crashes?

### Part 9: Final Verdict
- Overall PASS/FAIL summary
- Production gap checklist
- Sign-off criteria

---

# Part 1: Core Pipeline Journeys

---

## Q1: Can I initialize a project and configure sources?

**User says:** "I want to start tracking medical research. Give me a working project."

**Why this matters:** This is the first command a new user runs. If `init` fails, nothing else works.

### Prerequisites
```bash
cd /tmp && rm -rf test-autoinfo && mkdir test-autoinfo && cd test-autoinfo
```

### Scenarios

#### 1.1 🟢 Happy Path — Init with demo domain
```bash
autoinfo init --demo medical-research
```
**Expected Result:**
- ✅ Exit code 0
- ✅ `.autoinfo/config.yaml` created
- ✅ `.autoinfo/sources.yaml` created
- ✅ `knowledge/01-Raw/`, `collections/`, `outputs/` directories created
- ✅ Success message printed with next steps

**Actual Result:** _________ **PASS / FAIL:** _________

#### 1.2 🟢 Config is valid and parseable
```bash
python3 -c "
from autoinfo.config import load_config
cfg = load_config('.autoinfo/config.yaml')
print(f'Project: {cfg.project.name}')
print(f'LLM: {cfg.llm.provider}/{cfg.llm.model}')
print(f'Domains: {[d.name for d in cfg.domains]}')
for d in cfg.domains:
    print(f'  {d.name}: sources={[s.name for s in d.sources]}, topics={[t.name for t in d.topics]}')
"
```
**Expected Result:**
- ✅ Config parses without error
- ✅ `cfg.project.name` is non-empty
- ✅ `cfg.llm.provider` == "openrouter"
- ✅ `cfg.llm.model` == "deepseek/deepseek-chat"
- ✅ At least one domain active with `pubmed` source and topics

**Actual Result:** _________ **PASS / FAIL:** _________

#### 1.3 🟢 Init is idempotent — second run doesn't overwrite
```bash
autoinfo init --demo medical-research
```
**Expected Result:** ✅ Exit code 0. Prints "SKIP" for existing files. No overwrite.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 1.4 🟢 Init without --demo lists available domains
```bash
autoinfo init
```
**Expected Result:** ✅ Prints available demo domains (medical-research). Exit code 0.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 1.5 🔴 Init with unknown domain
```bash
autoinfo init --demo nonexistent-domain
```
**Expected Result:** ❌ Exit code != 0. Error message mentions unknown domain.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q1 Verdict

| Scenario | Result |
|----------|--------|
| 1.1 Happy path init | ⬜ |
| 1.2 Config is valid | ⬜ |
| 1.3 Idempotent | ⬜ |
| 1.4 List domains | ⬜ |
| 1.5 Unknown domain | ⬜ |

**OVERALL: ⬜** (✅ if all pass, ❌ if any fail)

---

## Q2: Can I collect from PubMed and RSS sources?

**User says:** "I configured my project. Now fetch some medical papers on IVF."

**Why this matters:** Collection is core functionality. PubMed handler is the primary source.

### Prerequisites
```bash
cd /tmp && rm -rf test-collect && mkdir test-collect && cd test-collect
autoinfo init --demo medical-research
```

### Scenarios

#### 2.1 🟢 Happy Path — Collect from PubMed
```bash
autoinfo collect --domain medical-research --topic "IVF" --limit 3
```
**Expected Result:**
- ✅ Exit code 0
- ✅ Progress shown per source
- ✅ Completion summary with item counts
- ✅ Items cached to `collections/medical-research/pubmed/<date>/<id>.json`

**Actual Result:** _________ **PASS / FAIL:** _________

#### 2.2 🟢 Dry-run returns estimates without storing
```bash
autoinfo collect --domain medical-research --topic "IVF" --limit 3 --dry-run
```
**Expected Result:**
- ✅ Exit code 0
- ✅ Output shows estimated item counts
- ✅ No files created in `collections/` directory

**Actual Result:** _________ **PASS / FAIL:** _________

#### 2.3 🟢 Collection with source filter
```bash
autoinfo collect --domain medical-research --topic "IVF" --source pubmed --limit 3
```
**Expected Result:** ✅ Only PubMed handler runs. Items collected successfully.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 2.4 🟢 Empty results handled gracefully
```bash
autoinfo collect --domain medical-research --topic "zzzzzznonexistent" --limit 3
```
**Expected Result:** ✅ Exit code 0. Message: "No new items for medical-research." (Not an error.)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 2.5 🟢 RSS feed collection
```bash
autoinfo collect --domain custom-rss --source demo-rss --limit 3
```
This test requires a configured RSS source. If no RSS source is configured, skip this test.
**Expected Result:** ✅ RSS items collected with title, link, summary.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 2.6 🔴 Collection with missing config
```bash
cd /tmp/empty-dir && autoinfo collect --domain medical-research
```
**Expected Result:** ❌ Exit code != 0. "Run 'autoinfo init' first" error message.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q2 Verdict

| Scenario | Result |
|----------|--------|
| 2.1 PubMed collect | ⬜ |
| 2.2 Dry-run | ⬜ |
| 2.3 Source filter | ⬜ |
| 2.4 Empty results | ⬜ |
| 2.5 RSS collect | ⬜ |
| 2.6 Missing config | ⬜ |

**OVERALL: ⬜**

---

## Q3: Can I process collected items (LLM extraction + quality gates + KB storage)?

**User says:** "I collected some papers. Now extract structured summaries and store them."

**Why this matters:** The processing pipeline (LLM extraction → quality gates → KB storage) is the core value-add of AutoInfo.

### Prerequisites
```bash
cd /tmp && rm -rf test-process && mkdir test-process && cd test-process
autoinfo init --demo medical-research
autoinfo collect --domain medical-research --topic "IVF" --limit 3
```

### Scenarios

#### 3.1 🟢 Happy Path — Process cached items
```bash
autoinfo process --domain medical-research
```
**Expected Result:**
- ✅ Exit code 0
- ✅ Per-item progress shown
- ✅ Summary: "N items → N passed G1-G3 → N KB entries created"
- ✅ Markdown files created in `knowledge/medical-research/01-Raw/ivf/`

**Actual Result:** _________ **PASS / FAIL:** _________

#### 3.2 🟢 KB entries have correct YAML frontmatter
```bash
head -20 knowledge/medical-research/01-Raw/ivf/*.md
```
**Expected Result:**
- ✅ YAML frontmatter with: title, domain, tier, source_url, source_type, source_platform, collected_at, summary, tags, quality_tier, relevance_score, dedup_status
- ✅ Body contains original content + extracted TL;DR + key points

**Actual Result:** _________ **PASS / FAIL:** _________

#### 3.3 🟢 Collect + process in one step
```bash
cd /tmp && rm -rf test-autoprocess && mkdir test-autoprocess && cd test-autoprocess
autoinfo init --demo medical-research
autoinfo collect --domain medical-research --topic "IVF" --limit 3 --auto-process
```
**Expected Result:**
- ✅ Both phases run
- ✅ Combined summary printed
- ✅ KB entries created

**Actual Result:** _________ **PASS / FAIL:** _________

#### 3.4 🟢 Processing with empty cache
```bash
cd /tmp/empty-process && autoinfo init --demo medical-research
autoinfo process --domain medical-research
```
**Expected Result:** ✅ Exit code 0. Message: no cached items found, nothing to process.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q3 Verdict

| Scenario | Result |
|----------|--------|
| 3.1 Happy path process | ⬜ |
| 3.2 KB frontmatter | ⬜ |
| 3.3 Auto-process | ⬜ |
| 3.4 Empty cache | ⬜ |

**OVERALL: ⬜**

---

## Q4: Can I browse summaries, status, and health?

**User says:** "I processed some papers. Now show me what I have."

### Prerequisites
```bash
cd /tmp && rm -rf test-browse && mkdir test-browse && cd test-browse
autoinfo init --demo medical-research
autoinfo collect --domain medical-research --topic "IVF" --limit 3
autoinfo process --domain medical-research
```

### Scenarios

#### 4.1 🟢 Summaries list shows entries with TL;DR
```bash
autoinfo summaries list --domain medical-research
```
**Expected Result:**
- ✅ Exit code 0
- ✅ Shows entries with title, TL;DR (summary), relevance score, date
- ✅ Pagination works with --limit and --offset

**Actual Result:** _________ **PASS / FAIL:** _________

#### 4.2 🟢 Summaries list with JSON output
```bash
autoinfo summaries list --domain medical-research --json
```
**Expected Result:** ✅ Valid JSON with entries array. Each entry has title, summary, relevance_score, collected_at.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 4.3 🟢 Status shows collection stats
```bash
autoinfo status
```
**Expected Result:**
- ✅ Shows items collected today
- ✅ Shows total KB entries per domain
- ✅ Shows source health per source

**Actual Result:** _________ **PASS / FAIL:** _________

#### 4.4 🟢 Doctor checks all systems
```bash
autoinfo doctor
```
**Expected Result:**
- ✅ Checks Python version (≥3.11)
- ✅ Checks config exists and valid
- ✅ Reports LLM key status
- ✅ Checks source reachability
- ✅ No crashes, friendly output

**Actual Result:** _________ **PASS / FAIL:** _________

#### 4.5 🟢 Doctor with JSON output
```bash
autoinfo doctor --json
```
**Expected Result:** ✅ Valid JSON with python/config/llm/sources sections.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q4 Verdict

| Scenario | Result |
|----------|--------|
| 4.1 Summaries list | ⬜ |
| 4.2 Summaries JSON | ⬜ |
| 4.3 Status | ⬜ |
| 4.4 Doctor | ⬜ |
| 4.5 Doctor JSON | ⬜ |

**OVERALL: ⬜**

---

# Part 2: CLI Surface Mastery

---

## Q5: Does every CLI command work correctly? (6 commands)

**User says:** "I prefer using the terminal. I need all 6 CLI commands to work."

### 5.1 🟢 Main help + version
```bash
autoinfo --help
```
**Expected Result:** ✅ Shows all 14 command groups (init, doctor, collect, process, status, summaries, sources, topics, kb, output, cron, knowledge, cefr, email). `--json` global flag present.

**Actual Result:** _________ **PASS / FAIL:** _________

### 5.2 🟢 Each command's help works
```bash
for cmd in init doctor collect process status summaries; do autoinfo $cmd --help; done
```
**Expected Result:** ✅ Every command has help output. No crashes. Parameters documented.

**Actual Result:** _________ **PASS / FAIL:** _________

### 5.3 🟢 `init` — project skeleton creation
```bash
autoinfo init --demo medical-research
```
**Expected Result:** ✅ Creates .autoinfo/ with config, sources, directories. Idempotent. Lists domains when no --demo.

**Actual Result:** _________ **PASS / FAIL:** _________

### 5.4 🟢 `doctor` — health check
```bash
autoinfo doctor; autoinfo doctor --json
```
**Expected Result:** ✅ Runs all checks. Human-readable + JSON output.

**Actual Result:** _________ **PASS / FAIL:** _________

### 5.5 🟢 `collect` — source collection
```bash
autoinfo collect --help
```
**Expected Result:** ✅ Shows --domain (required), --topic, --source, --limit, --dry-run, --auto-process, --json.

**Actual Result:** _________ **PASS / FAIL:** _________

### 5.6 🟢 `process` — LLM processing
```bash
autoinfo process --help
```
**Expected Result:** ✅ Shows --domain (required), --model, --json.

**Actual Result:** _________ **PASS / FAIL:** _________

### 5.7 🟢 `status` — collection overview
```bash
autoinfo status --help
```
**Expected Result:** ✅ Shows --domain, --json.

**Actual Result:** _________ **PASS / FAIL:** _________

### 5.8 🟢 `summaries` — browse summaries
```bash
autoinfo summaries --help
```
**Expected Result:** ✅ Shows list subcommand with --domain, --date-from, --limit, --offset, --json.

**Actual Result:** _________ **PASS / FAIL:** _________

### 5.9 🟢 `--json` on all output commands
```bash
autoinfo status --json 2>/dev/null | python3 -c "import sys,json; json.load(sys.stdin); print('VALID JSON')"
autoinfo doctor --json 2>/dev/null | python3 -c "import sys,json; json.load(sys.stdin); print('VALID JSON')"
```
**Expected Result:** ✅ Both produce valid JSON.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q5 Verdict

| Scenario | Result |
|----------|--------|
| 5.1 Main help | ⬜ |
| 5.2 Per-command help | ⬜ |
| 5.3 init | ⬜ |
| 5.4 doctor | ⬜ |
| 5.5 collect help | ⬜ |
| 5.6 process help | ⬜ |
| 5.7 status help | ⬜ |
| 5.8 summaries help | ⬜ |
| 5.9 --json output | ⬜ |

**OVERALL: ⬜**

---

## Q6: Does CLI handle edge cases gracefully?

**User says:** "What if I pass wrong arguments?"

### 6.1 🔴 Missing required --domain on collect
```bash
autoinfo collect
```
**Expected Result:** ❌ Error or help shown. Mentions --domain is required.

**Actual Result:** _________ **PASS / FAIL:** _________

### 6.2 🔴 Unknown argument
```bash
autoinfo collect --domain medical --nonexistent-flag
```
**Expected Result:** ❌ Error: "No such option". Does NOT crash with traceback.

**Actual Result:** _________ **PASS / FAIL:** _________

### 6.3 🟢 Commands without config print friendly error
```bash
cd /tmp/noconfig && autoinfo collect --domain medical-research
cd /tmp/noconfig && autoinfo process --domain medical-research
```
**Expected Result:** ❌ Friendly error: "Run 'autoinfo init' first" or similar. NOT a traceback.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q6 Verdict

| Scenario | Result |
|----------|--------|
| 6.1 Missing --domain | ⬜ |
| 6.2 Unknown argument | ⬜ |
| 6.3 No config error | ⬜ |

**OVERALL: ⬜**

---

# Part 3: MCP Surface Mastery

---

## Q7: Does every MCP tool work correctly? (65 tools)

**User says:** "I'm connecting via MCP protocol. I need all 65 tools to work as documented."

**Why this matters:** MCP is the primary integration surface for AI agents. Broken tools break automation.

### 7.1 🟢 Server starts and lists tools
```python
from autoinfo.mcp.server import app
import json

# Check tools are registered
tools = app.list_tools()()
tool_names = [t.name for t in tools]
assert len(tools) > 6  # 65 tools in v1.3
expected_tools = ["health_check", "diagnose_system", "collect_sources", "process_collection",
                  "list_summaries", "get_kb_entry", "generate_report", "classify_cefr",
                  "vector_search", "faceted_search", "send_email_digest", "init_project"]
missing = [t for t in expected_tools if t not in tool_names]
assert len(missing) == 0, f"Missing tools: {missing}"
print(f"ALL {len(tools)} TOOLS PRESENT")
```
**Expected Result:** ✅ 65 tools registered with correct names, including v1.2 additions (generate_report, classify_cefr, vector_search, faceted_search) and v1.3 addition (init_project).

**Actual Result:** _________ **PASS / FAIL:** _________

### 7.2 🟢 health_check
```python
result = app.call_tool("health_check", {})
data = json.loads(result.content[0].text)
assert data["status"] == "ok"
assert "version" in data
assert data["tools_count"] > 6  # 65 in v1.3
```
**Expected Result:** ✅ Returns status, version, tools_count.

**Actual Result:** _________ **PASS / FAIL:** _________

### 7.3 🟢 diagnose_system
```python
result = app.call_tool("diagnose_system", {})
data = json.loads(result.content[0].text)
assert "llm" in data
assert "sources" in data
assert "disk" in data or "db" in data
```
**Expected Result:** ✅ Returns comprehensive health with at least 3 of 4 sections (llm, sources, disk, db).

**Actual Result:** _________ **PASS / FAIL:** _________

### 7.4 🟢 collect_sources
```python
result = app.call_tool("collect_sources", {"domain": "medical-research", "topic": "IVF", "limit": 3, "dry_run": True})
data = json.loads(result.content[0].text)
assert "collection_id" in data or "status" in data or "items_found" in data
```
**Expected Result:** ✅ Returns collection result with item count or status.

**Actual Result:** _________ **PASS / FAIL:** _________

### 7.5 🟢 process_collection
```python
result = app.call_tool("process_collection", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
assert "total_items" in data or "status" in data or "kb_entries_created" in data
```
**Expected Result:** ✅ Returns processing result with item/entry counts.

**Actual Result:** _________ **PASS / FAIL:** _________

### 7.6 🟢 list_summaries and get_kb_entry
Requires processed items. If no items, this test is informational.
```python
result = app.call_tool("list_summaries", {"domain": "medical-research", "limit": 5})
data = json.loads(result.content[0].text)
assert "entries" in data or "total_count" in data
```
**Expected Result:** ✅ Returns entries/total_count. Handles empty domain gracefully.

**Actual Result:** _________ **PASS / FAIL:** _________

### 7.7 🔴 MCP error responses
```python
# Test with missing required param
result = app.call_tool("collect_sources", {})
data = json.loads(result.content[0].text)
assert "error_code" in data or "message" in data
```
**Expected Result:** ❌ Error response has `error_code`, `message`, `actionable` fields. No Python traceback leaked.

**Actual Result:** _________ **PASS / FAIL:** _________

### 7.8 🔴 Unknown tool name
```python
try:
    result = app.call_tool("nonexistent_tool", {})
    print("Received response (not crash)")
except Exception as e:
    print(f"Handled error: {e}")
```
**Expected Result:** ❌ Does NOT crash. Returns error or raises handled exception.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q7 Verdict

| Scenario | Result |
|----------|--------|
| 7.1 Server starts, 6 tools | ⬜ |
| 7.2 health_check | ⬜ |
| 7.3 diagnose_system | ⬜ |
| 7.4 collect_sources | ⬜ |
| 7.5 process_collection | ⬜ |
| 7.6 list_summaries | ⬜ |
| 7.7 Error responses | ⬜ |
| 7.8 Unknown tool | ⬜ |

**OVERALL: ⬜**

---

# Part 4: Agent-as-User Real API Configuration & E2E Tests

---

## Q20: Can an agent configure real info platform APIs and run E2E collection tests?

**Agent says:** "I want to configure real PubMed, RSS, and web source APIs — then collect real items from them. No mocks."

**Why this matters:** AutoInfo's primary value is collecting from real APIs. Every validation plan before Part 4 used cached/mocked data. Part 4 validates the actual HTTP and LLM integrations that make AutoInfo useful.

**Prerequisite mindset:** The validating agent acts as a user — configuring, running, and interpreting results from real endpoints. The agent must set env vars, create/update config files, run CLI commands, and inspect outputs using the shell and filesystem tools.

### Scenarios

#### 20.1 🟢 PubMed API — Configure and collect real papers (no API key)

This tests the free PubMed E-utilities tier (3 req/s without API key).

```bash
cd /tmp && rm -rf test-pubmed-real && mkdir test-pubmed-real && cd test-pubmed-real

# Step 1: Init project
autoinfo init --demo medical-research

# Step 2: Verify config loads PubMed source
python3 -c "
from autoinfo.config import load_config
cfg = load_config('.autoinfo/config.yaml')
for d in cfg.domains:
    if d.name == 'medical-research':
        for s in d.sources:
            if 'pubmed' in s.name.lower():
                print(f'PubMed source found: {s.name} → {s.url}')
"

# Step 3: Collect real PubMed items (no API key needed, rate-limited to 3/s)
autoinfo collect --domain medical-research --topic "IVF breakthroughs" --source pubmed --limit 3
```

**Expected Result:**
- ✅ `autoinfo init` creates valid project with PubMed source configured (base URL: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/`)
- ✅ `autoinfo collect` exit code 0
- ✅ Output shows "Items found: N" and "Items collected: N" (N ≥ 1, ≤ 3)
- ✅ Items cached to `collections/medical-research/pubmed/<date>/<id>.json`
- ✅ Cached JSON files have: `source_url`, `title`, `content` (or `abstract`), `source_type: "api"`, `source_platform: "pubmed"`, `collected_at`
- ✅ Raw cache files contain real PubMed data (PMID, authors, journal, publication date)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 20.2 🟢 PubMed API — Configure with API key for higher rate limits

```bash
# Step 1: Set PubMed API key (higher rate limit: 10 req/s)
export AUTOINFO_PUBMED_API_KEY="your-ncbi-api-key"

# Step 2: Collect larger batch
autoinfo collect --domain medical-research --topic "COVID-19 mRNA vaccine" --source pubmed --limit 10
```

**Expected Result:**
- ✅ Exit code 0, all 10 items collected without rate-limit errors (HTTP 429)
- ✅ Collection completes faster than without API key (lower latency)
- ✅ Items include `pmid`, `doi` in `raw_data` for dedup

**Actual Result:** _________ **PASS / FAIL:** _________

#### 20.3 🟢 RSS feed — Configure and collect real items

Tests the RSS handler against a live feed (TechCrunch or arXiv).

```bash
cd /tmp && rm -rf test-rss-real && mkdir test-rss-real && cd test-rss-real
autoinfo init --demo ai-commercial

# Collect from TechCrunch RSS (no API key needed)
autoinfo collect --domain ai-commercial --source techcrunch --limit 5
```

**Expected Result:**
- ✅ Exit code 0
- ✅ Items collected with `title`, `link`, `summary`, `published` date
- ✅ Items cached to `collections/ai-commercial/techcrunch/<date>/<id>.json`
- ✅ Each item has `source_type: "rss"`, `source_platform: "techcrunch"`
- ✅ Content is real TechCrunch article summaries (not empty)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 20.4 🟢 Web scraping — Configure and collect from a real web page

Tests the web handler (trafilatura + Playwright fallback) against a real page.

```bash
# Add a web source manually (e.g., WHO public health page)
mkdir -p .autoinfo
cat >> .autoinfo/sources.yaml << 'SOURCES'
sources:
  - name: who-health
    type: web
    url: https://www.who.int/health-topics
    quality_tier: 1
    topics:
      - global health
SOURCES

autoinfo collect --domain medical-research --source who-health --limit 3
```

**Expected Result:**
- ✅ Exit code 0
- ✅ Web page content extracted (title, body text, publication date if available)
- ✅ Item has `source_type: "web"`, `source_platform: "who-health"`
- ✅ Content is readable text (not raw HTML or empty)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 20.5 🔴 Invalid source URL — Graceful error

```bash
# Step 1: Add a broken source
cat >> .autoinfo/sources.yaml << 'SOURCES'
sources:
  - name: broken-source
    type: web
    url: https://this-domain-does-not-exist-12345.com/rss
    quality_tier: 3
SOURCES

# Step 2: Try to collect
autoinfo collect --domain medical-research --source broken-source --limit 3
```

**Expected Result:**
- ❌ Handler reports error for broken source (connection error or timeout)
- ❌ No crash — error is logged, other sources continue if run together
- ❌ `autoinfo doctor` flags source as unreachable

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q20 Verdict

| Scenario | Result |
|----------|--------|
| 20.1 PubMed collect (no API key) | ⬜ |
| 20.2 PubMed collect (with API key) | ⬜ |
| 20.3 RSS feed collect | ⬜ |
| 20.4 Web scraping | ⬜ |
| 20.5 Invalid source URL | ⬜ |

**OVERALL: ⬜**

---

## Q21: Can an agent configure real LLM APIs and run E2E processing tests?

**Agent says:** "I need to configure a real LLM API key, process collected items, and verify extraction results."

**Why this matters:** LLM extraction is AutoInfo's core differentiator. Without real LLM API integration validation, the pipeline is untested in production conditions.

**Prerequisite:** Q20 scenarios must have collected real items from PubMed/RSS. If not, run Q20.1 and Q20.3 first.

### Scenarios

#### 21.1 🟢 Configure valid LLM API key — doctor detects it

```bash
cd /tmp && rm -rf test-llm-real && mkdir test-llm-real && cd test-llm-real
autoinfo init --demo medical-research

# Set LLM API key (use your actual key — OpenRouter, OpenAI, or any LiteLLM provider)
export AUTOINFO_LLM_API_KEY="sk-or-v1-..."

# Verify doctor detects the key
autoinfo doctor --json | python3 -c "
import sys, json
data = json.load(sys.stdin)
llm = data.get('llm', {})
print(f'Python: {data.get(\"python\", {}).get(\"version\", \"?\")}')
print(f'Config valid: {data.get(\"config\", {}).get(\"valid\", False)}')
print(f'LLM key configured: {llm.get(\"key_configured\", False)}')
print(f'LLM provider: {llm.get(\"provider\", \"?\")}')
print(f'LLM model: {llm.get(\"model\", \"?\")}')
assert llm.get('key_configured') == True, 'LLM key not detected!'
assert data.get('config', {}).get('valid') == True, 'Config invalid!'
print('✅ Doctor detects configured LLM')
"
```

**Expected Result:**
- ✅ `doctor --json` output shows `llm.key_configured: true`
- ✅ `llm.provider` matches config (default: `openrouter`)
- ✅ `llm.model` matches config (default: `deepseek/deepseek-chat`)
- ✅ No errors reported by doctor

**Actual Result:** _________ **PASS / FAIL:** _________

#### 21.2 🟢 Process real collected items with real LLM — verify KB entries

```bash
# Step 1: Collect real items first
autoinfo collect --domain medical-research --topic "IVF breakthroughs" --source pubmed --limit 3

# Step 2: Process with real LLM
autoinfo process --domain medical-research

# Step 3: Verify KB entries exist with LLM-extracted content
ls knowledge/medical-research/01-Raw/ivf-breakthroughs/

# Step 4: Inspect a KB entry for LLM extraction quality
head -30 knowledge/medical-research/01-Raw/ivf-breakthroughs/*.md | head -60
```

**Expected Result:**
- ✅ `process` exit code 0
- ✅ Progress shows each item being processed by LLM
- ✅ Summary: "N items → N passed G1-G3 → N KB entries created"
- ✅ KB Markdown files exist at `knowledge/medical-research/01-Raw/ivf-breakthroughs/<date>-<slug>.md`
- ✅ YAML frontmatter includes: `title`, `domain`, `tier: 01-Raw`, `source_url`, `source_type`, `source_platform`, `collected_at`, `quality_tier`, `relevance_score`, `dedup_status`
- ✅ Body includes LLM-extracted fields: `## TL;DR` section, `## Key Points` list, entity extraction
- ✅ Extracted TL;DR is meaningful (not "No summary available" or empty)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 21.3 🟢 Provider/model override — process with different LLM

Tests the per-task model override and fallback chain.

```bash
# Step 1: Modify config for per-task override
python3 -c "
import yaml
with open('.autoinfo/config.yaml') as f:
    cfg = yaml.safe_load(f)
if 'tasks' not in cfg['llm']:
    cfg['llm']['tasks'] = {}
cfg['llm']['tasks']['extraction'] = {
    'provider': 'openai',
    'model': 'gpt-4o-mini',
    'max_tokens': 4000
}
with open('.autoinfo/config.yaml', 'w') as f:
    yaml.dump(cfg, f)
print('Config updated: extraction task uses gpt-4o-mini')
"

# Step 2: Collect more items
autoinfo collect --domain medical-research --topic "gene therapy CRISPR" --source pubmed --limit 3

# Step 3: Process with overridden model
autoinfo process --domain medical-research

# Step 4: Verify entries created
ls knowledge/medical-research/01-Raw/gene-therapy-crispr/
```

**Expected Result:**
- ✅ Config update succeeds without validation errors
- ✅ Process uses gpt-4o-mini for extraction (visible in log/progress)
- ✅ KB entries created with LLM-extracted content
- ✅ Entries show different model behavior (shorter responses if gpt-4o-mini is more concise)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 21.4 🟢 Fallback chain — primary model fails, fallback succeeds

Tests the `llm.fallback` mechanism.

```bash
# Step 1: Configure a fallback chain
python3 -c "
import yaml
with open('.autoinfo/config.yaml') as f:
    cfg = yaml.safe_load(f)
# Break the primary provider intentionally
cfg['llm']['provider'] = 'nonexistent-provider'
cfg['llm']['model'] = 'fake/model'
cfg['llm']['fallback'] = [
    {'provider': 'openrouter', 'model': 'deepseek/deepseek-chat'}
]
with open('.autoinfo/config.yaml', 'w') as f:
    yaml.dump(cfg, f)
print('Config updated: broken primary + working fallback')
"

# Step 2: Process (should fallback to working provider)
autoinfo collect --domain medical-research --topic "CRISPR" --source pubmed --limit 2
autoinfo process --domain medical-research

# Step 3: Verify processing still worked
ls knowledge/medical-research/01-Raw/crispr/ 2>/dev/null && echo 'KB entries created via fallback'
```

**Expected Result:**
- ✅ Processing logs show fallback activation (warning about primary failure)
- ✅ KB entries still created (fallback succeeded)
- ✅ Process completes with exit code 0

**Actual Result:** _________ **PASS / FAIL:** _________

#### 21.5 🔴 Missing/invalid LLM API key — graceful failure

```bash
# Step 1: Unset the key and try to process
unset AUTOINFO_LLM_API_KEY

# Step 2: Create config without key
python3 -c "
import yaml
with open('.autoinfo/config.yaml') as f:
    cfg = yaml.safe_load(f)
cfg['llm']['api_key'] = ''  # empty key
with open('.autoinfo/config.yaml', 'w') as f:
    yaml.dump(cfg, f)
"

# Step 3: Try processing (should get clear error, not crash)
autoinfo process --domain medical-research 2>&1; echo 'EXIT:' $?
```

**Expected Result:**
- ❌ Exit code != 0
- ❌ Error message mentions missing/invalid API key
- ❌ No Python traceback — user-friendly error
- ❌ Does NOT crash or hang

**Actual Result:** _________ **PASS / FAIL:** _________

#### 21.6 🔴 LLM API timeout — pipeline continues with next item

Tests that a single-item LLM failure doesn't kill the whole pipeline.

```python
# Real-world: Point to a very slow/broken endpoint
# Expected behavior: per-item timeout, continue with next item
python3 "
from autoinfo.llm import LLMExtractor
from autoinfo.models import Item
from unittest.mock import patch
import time

# Simulate processing 3 items where the 2nd times out
extractor = LLMExtractor()
items = [
    Item(id='a', title='Good item', content='Real content', collected_at='2026-07-21'),
    Item(id='b', title='Bad item', content='Causes timeout', collected_at='2026-07-21'),
    Item(id='c', title='Good item 2', content='More real content', collected_at='2026-07-21'),
]

# Mock only the middle item to fail
call_count = [0]
original_extract = extractor.extract_with_retry

def mock_extract(item, **kw):
    if item.id == 'b':
        raise Exception('LLM API timeout simulated')
    return original_extract(item, **kw)

extractor.extract_with_retry = mock_extract

results = []
for item in items:
    try:
        result = extractor.extract_with_retry(item)
        results.append(('ok', result))
    except Exception as e:
        results.append(('fail', str(e)))

print(f'Results: {len(results)}/{len(items)} processed')
for status, r in results:
    print(f'  {status}: {r}')
assert results[0][0] == 'ok', 'First item should succeed'
assert results[1][0] == 'fail', 'Second item should fail'
assert results[2][0] == 'ok', 'Third item should succeed'
print('✅ Item-level isolation confirmed')
"
```

**Expected Result:**
- ✅ Item-level isolation: failing the 2nd item doesn't prevent 3rd from processing
- ✅ Failed item returns default ExtractionResult (empty fields)
- ✅ Pipeline continues gracefully

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q21 Verdict

| Scenario | Result |
|----------|--------|
| 21.1 Doctor detects LLM key | ⬜ |
| 21.2 Process with real LLM | ⬜ |
| 21.3 Provider/model override | ⬜ |
| 21.4 Fallback chain | ⬜ |
| 21.5 Missing/invalid key | ⬜ |
| 21.6 LLM timeout isolation | ⬜ |

**OVERALL: ⬜**

---

## Q22: Can an agent execute the full pipeline with real APIs end-to-end?

**Agent says:** "I want the complete experience — init a project, configure both info and LLM APIs, collect real items, process with a real LLM, search the KB, generate output, and export. No shortcuts."

**Why this matters:** This is the workflow a real user follows. If any step fails, the user's trust breaks.

### Scenarios

#### 22.1 🟢 Full E2E pipeline — init → configure → collect (real PubMed) → process (real LLM) → search → output → export

```bash
cd /tmp && rm -rf test-e2e-real && mkdir test-e2e-real && cd test-e2e-real

# Phase 1: Init
echo '=== PHASE 1: INIT ==='
autoinfo init --demo medical-research
ls -la .autoinfo/

# Phase 2: Set LLM key (from env)
echo "LLM key: ${AUTOINFO_LLM_API_KEY:0:8}..."

# Phase 3: Doctor check
echo '=== PHASE 3: DOCTOR ==='
autoinfo doctor --json | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'Python: {d.get(\"python\",{}).get(\"version\",\"?\")} | Config: {d.get(\"config\",{}).get(\"valid\",False)} | LLM key: {d.get(\"llm\",{}).get(\"key_configured\",False)} | Sources: {len(d.get(\"sources\",{}).get(\"results\",[]))}'
assert d.get('config',{}).get('valid'), 'Config invalid'
print('✅ Doctor OK')
"

# Phase 4: Collect real PubMed items
echo '=== PHASE 4: COLLECT ==='
autoinfo collect --domain medical-research --topic "IVF breakthroughs" --source pubmed --limit 3
ls collections/medical-research/pubmed/*/ || echo 'No collections dir'

# Phase 5: Process with real LLM
echo '=== PHASE 5: PROCESS ==='
autoinfo process --domain medical-research
ls knowledge/medical-research/01-Raw/

# Phase 6: Search KB
echo '=== PHASE 6: SEARCH ==='
autoinfo summaries list --domain medical-research --json | python3 -c "
import sys, json
data = json.load(sys.stdin)
entries = data.get('entries', [])
print(f'{len(entries)} KB entries')
for e in entries:
    print(f'  - {e.get(\"title\", \"?\")[:60]} | score={e.get(\"relevance_score\", \"?\")} | {e.get(\"tier\", \"?\")}')
assert len(entries) >= 1, 'No KB entries found!'
print('✅ KB search works')
"

# Phase 7: Generate output
echo '=== PHASE 7: OUTPUT ==='
autoinfo output digest --domain medical-research --period week
ls outputs/medical-research/digest/

# Phase 8: Export KB
echo '=== PHASE 8: EXPORT ==='
autoinfo output export --domain medical-research --format json
ls outputs/medical-research/export/
```

**Expected Result:**
- ✅ Phase 1: `.autoinfo/config.yaml`, `.autoinfo/sources.yaml`, `knowledge/`, `collections/`, `outputs/` all created
- ✅ Phase 3: Doctor reports all green (Python ≥3.11, config valid, LLM key configured, sources configured)
- ✅ Phase 4: ≥1 PubMed items collected with real metadata
- ✅ Phase 5: All collected items processed into KB entries with LLM-extracted TL;DR and key points
- ✅ Phase 6: `summaries list --json` returns ≥1 entry with correct fields
- ✅ Phase 7: Digest generated (Markdown file with real content summaries)
- ✅ Phase 8: JSON export valid and contains KB entries
- ✅ Every phase exit code 0

**Actual Result:** _________ **PASS / FAIL:** _________

#### 22.2 🟢 Multi-domain pipeline — two domains, each with real APIs

```bash
cd /tmp && rm -rf test-multidomain && mkdir test-multidomain && cd test-multidomain

# Init with both medical and AI commercial demo domains
autoinfo init --demo medical-research --demo ai-commercial

# Ensure LLM key is set
export AUTOINFO_LLM_API_KEY="sk-or-v1-..."

# Collect from both domains in parallel
echo '=== COLLECT MEDICAL ==='
autoinfo collect --domain medical-research --topic "cancer immunotherapy" --source pubmed --limit 3 &
PID1=$!
echo '=== COLLECT AI ==='
autoinfo collect --domain ai-commercial --source techcrunch --limit 5 &
PID2=$!
wait $PID1 $PID2

# Process both domains
echo '=== PROCESS MEDICAL ==='
autoinfo process --domain medical-research
echo '=== PROCESS AI ==='
autoinfo process --domain ai-commercial

# Verify both domains have KB entries
echo '=== VERIFY MEDICAL ==='
autoinfo summaries list --domain medical-research --json | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Medical: {len(d.get(\"entries\",[]))} entries')"
echo '=== VERIFY AI ==='
autoinfo summaries list --domain ai-commercial --json | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'AI: {len(d.get(\"entries\",[]))} entries')"
```

**Expected Result:**
- ✅ Both init commands succeed (multi-demo init)
- ✅ Both collection processes run in parallel without conflict
- ✅ Medical domain: KB entries with PubMed source metadata
- ✅ AI domain: KB entries with RSS source metadata (TechCrunch summaries)
- ✅ Both domains searchable independently
- ✅ Total KB entries ≥ 4 (3 medical + 5 AI, minus dedup)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 22.3 🟢 Auto-process mode with real APIs

```bash
cd /tmp && rm -rf test-autoprocess-real && mkdir test-autoprocess-real && cd test-autoprocess-real
autoinfo init --demo medical-research
export AUTOINFO_LLM_API_KEY="sk-or-v1-..."

# Collect + process in one step
autoinfo collect --domain medical-research --topic "stem cell therapy" --source pubmed --limit 3 --auto-process

# Verify both phases completed
ls collections/medical-research/pubmed/*/ 2>/dev/null
ls knowledge/medical-research/01-Raw/stem-cell-therapy/ 2>/dev/null
echo 'Items collected:' $(find collections/medical-research -name '*.json' 2>/dev/null | wc -l)
echo 'KB entries:' $(find knowledge/medical-research/01-Raw -name '*.md' 2>/dev/null | wc -l)
```

**Expected Result:**
- ✅ Exit code 0
- ✅ Combined summary: both collection and processing results shown
- ✅ Both `collections/` (raw JSON) and `knowledge/` (KB Markdown) directories populated
- ✅ KB entries created in `01-Raw/stem-cell-therapy/` subdirectory

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q22 Verdict

| Scenario | Result |
|----------|--------|
| 22.1 Full E2E pipeline | ⬜ |
| 22.2 Multi-domain pipeline | ⬜ |
| 22.3 Auto-process mode | ⬜ |

**OVERALL: ⬜**

---

## Q23: Can an agent detect, diagnose, and recover from real API configuration issues?

**Agent says:** "I want to understand how an agent (acting as a user) can identify API configuration problems, report them, and fix them."

**Why this matters:** Real-world agents don't have a human holding their hand. They must diagnose issues from doctor output, config inspection, and error messages, then self-heal configuration problems.

### Scenarios

#### 23.1 🟢 Agent diagnoses missing LLM API key

```bash
cd /tmp && rm -rf test-diag-nokey && mkdir test-diag-nokey && cd test-diag-nokey
autoinfo init --demo medical-research

# Unset the key
unset AUTOINFO_LLM_API_KEY

# Run doctor
autoinfo doctor --json > /tmp/doctor_output.json 2>&1

# Agent reads and interprets doctor output
python3 -c "
import json
with open('/tmp/doctor_output.json') as f:
    d = json.load(f)
print('=== Doctor Results ===')
print(f'Python: {d.get(\"python\", {}).get(\"ok\", False)}')
print(f'Config: {d.get(\"config\", {}).get(\"valid\", False)}')
llm = d.get('llm', {})
print(f'LLM key configured: {llm.get(\"key_configured\", False)}')
print(f'LLM provider: {llm.get(\"provider\", \"?\")}')
print(f'LLM model: {llm.get(\"model\", \"?\")}')

# Agent decision tree
if not llm.get('key_configured'):
    print('❌ ISSUE: LLM API key not configured')
    print('🔧 FIX: export AUTOINFO_LLM_API_KEY=\"sk-...\" or edit .autoinfo/config.yaml')
else:
    print('✅ LLM OK')
"
```

**Expected Result:**
- ✅ Doctor runs without crash (even without API key)
- ✅ AI agent can parse `doctor --json` to identify missing API key
- ✅ Agent reports clear, actionable diagnosis: "LLM API key not configured" + fix instruction
- ✅ LLM key status is `false`, other checks still pass

**Actual Result:** _________ **PASS / FAIL:** _________

#### 23.2 🟢 Agent diagnoses unreachable source URLs

```bash
cd /tmp && rm -rf test-diag-source && mkdir test-diag-source && cd test-diag-source
autoinfo init --demo medical-research

# Add a deliberately broken source
python3 -c "
import yaml
with open('.autoinfo/sources.yaml') as f:
    cfg = yaml.safe_load(f) or {'sources': []}
cfg['sources'].append({
    'name': 'broken-source',
    'type': 'web',
    'url': 'https://this-domain-does-not-exist-99999.com',
    'quality_tier': 3
})
with open('.autoinfo/sources.yaml', 'w') as f:
    yaml.dump(cfg, f)
"

# Run doctor with source reachability check
autoinfo doctor --json > /tmp/doctor_source.json 2>&1

# Agent interprets source health
python3 -c "
import json
with open('/tmp/doctor_source.json') as f:
    d = json.load(f)
sources = d.get('sources', {}).get('results', [])
print('=== Source Health ===')
for s in sources:
    status = s.get('status', 'unknown')
    latency = s.get('latency_ms', 'N/A')
    print(f'{s.get(\"name\", \"?\"):30s} status={status:10s} latency={latency}ms')
"
```

**Expected Result:**
- ✅ Doctor checks all configured sources via HEAD request (10s timeout)
- ✅ Working sources report `status: ok` with reasonable latency
- ✅ Broken source reports `status: error` or timeout
- ✅ Agent can parse JSON to diagnose which source(s) are broken
- ✅ Agent can report: "Source 'broken-source' unreachable" + the URL and error

**Actual Result:** _________ **PASS / FAIL:** _________

#### 23.3 🟢 Agent diagnoses and fixes config validation errors

```bash
cd /tmp && rm -rf test-diag-config && mkdir test-diag-config && cd test-diag-config
autoinfo init --demo medical-research

# Corrupt the config
python3 -c "
import yaml
with open('.autoinfo/config.yaml') as f:
    cfg = yaml.safe_load(f)
cfg['project']['name'] = ''  # invalid: empty name
cfg['llm']['model'] = ''     # invalid: empty model
with open('.autoinfo/config.yaml', 'w') as f:
    yaml.dump(cfg, f)
print('Config corrupted: empty project name and model')
"

# Agent runs doctor and parses config validation errors
autoinfo doctor --json 2>&1 | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    config = data.get('config', {})
    print(f'Config valid: {config.get(\"valid\", False)}')
    errors = config.get('errors', [])
    if errors:
        print(f'Errors ({len(errors)}):')
        for e in errors:
            print(f'  ❌ {e}')
    else:
        print('No config errors detected')
except Exception as e:
    data = sys.stdin.read()
    print(f'Could not parse JSON: {e}')
    print(data[:200])
"
```

**Expected Result:**
- ✅ Doctor detects config validation errors (empty name, empty model)
- ✅ Error messages are user-friendly, not tracebacks
- ✅ Agent can parse errors and construct fix actions
- ✅ After fixing (setting name + model), doctor reports config valid

**Actual Result:** _________ **PASS / FAIL:** _________

#### 23.4 🟢 Agent self-heals — reads diagnosis and fixes config programmatically

```bash
cd /tmp && rm -rf test-self-heal && mkdir test-self-heal && cd test-self-heal
autoinfo init --demo medical-research

# Simulate a bad config
unset AUTOINFO_LLM_API_KEY

# Agent: diagnose → fix → verify
echo '=== DIAGNOSE ==='
autoinfo doctor --json | python3 -c "
import sys, json
d = json.load(sys.stdin)
issues = []

# Check LLM key
if not d.get('llm', {}).get('key_configured'):
    issues.append(('llm_key', 'AUTOINFO_LLM_API_KEY not set'))

# Check config
if not d.get('config', {}).get('valid'):
    issues.append(('config', 'Config validation failed'))

for issue, detail in issues:
    print(f'ISSUE: {issue} — {detail}')

import os
os.system('echo \"ISSUES_COUNT=' + str(len(issues)) + '\" >> /tmp/heal_check.txt')
"

echo '=== FIX ==='
export AUTOINFO_LLM_API_KEY="sk-or-v1-test-fix-key"

echo '=== VERIFY ==='
autoinfo doctor --json | python3 -c "
import sys, json
d = json.load(sys.stdin)
fixed = d.get('llm', {}).get('key_configured', False)
print(f'LLM key fixed: {fixed}')
assert fixed, 'Self-heal failed — LLM key still not detected'
print('✅ Self-heal successful')
"
```

**Expected Result:**
- ✅ Agent follows diagnose → fix → verify cycle
- ✅ After fixing (setting env var), doctor confirms resolution
- ✅ No manual human intervention needed
- ✅ Fix can be automated (set env var + re-run doctor)

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q23 Verdict

| Scenario | Result |
|----------|--------|
| 23.1 Diagnose missing LLM key | ⬜ |
| 23.2 Diagnose unreachable source | ⬜ |
| 23.3 Diagnose config validation | ⬜ |
| 23.4 Self-heal cycle | ⬜ |

**OVERALL: ⬜**

---

# Part 5: Quality Gate Validation

---

## Q8: Does each quality gate (G1-G3) pass/fail correctly?

**User says:** "I need each quality gate to work correctly — passing good content and flagging bad content."

### 8.1 🟢 G1 source authority — flags Tier 3+ sources
```python
from autoinfo.quality import G1SourceAuthority
from autoinfo.models import Item

item = Item(id="1", source_name="blog", title="Test", content="test", collected_at="now", quality_tier=3)
result = G1SourceAuthority().check(item, {"quality_tier": 3})
assert result.flagged == True
assert "warning" in result.details.get("warning", "")
```
**Expected Result:** ✅ Items from Tier 3+ sources are flagged (advisory, not blocked).

**Actual Result:** _________ **PASS / FAIL:** _________

### 8.2 🟢 G1 passes Tier 1 sources unflagged
```python
item = Item(id="2", source_name="pubmed", title="Test", content="test", collected_at="now", quality_tier=1)
result = G1SourceAuthority().check(item, {"quality_tier": 1})
assert result.flagged == False
```
**Expected Result:** ✅ Tier 1 sources pass unflagged.

**Actual Result:** _________ **PASS / FAIL:** _________

### 8.3 🟢 G2 dedup detects URL duplicates
```python
from autoinfo.dedup import DedupChecker
checker = DedupChecker()
item = Item(id="3", source_name="pubmed", source_url="https://example.com/dup", title="Duplicate", content="same", collected_at="now")
existing = [{"source_url": "https://example.com/dup"}]
result = checker.check(item, existing)
assert result["is_duplicate"] == True
assert result["matched_by"] == "url"
```
**Expected Result:** ✅ URL exact match correctly identified.

**Actual Result:** _________ **PASS / FAIL:** _________

### 8.4 🟢 G3 relevance scoring (0-100)
```python
from autoinfo.quality import G3RelevanceScoring
item = Item(id="4", title="IVF treatment outcomes in 2026", content="This paper discusses IVF embryo implantation success rates...", collected_at="now")
result = G3RelevanceScoring().check(item, ["IVF", "embryo", "implantation"])
assert 0 <= result.score <= 100
```
**Expected Result:** ✅ Score is within 0-100 range. Higher keyword overlap = higher score.

**Actual Result:** _________ **PASS / FAIL:** _________

### 8.5 🟢 Items below 30 relevance are flagged hidden
```python
item = Item(id="5", title="Unrelated topic", content="cooking recipes", collected_at="now")
result = G3RelevanceScoring().check(item, ["IVF", "embryo", "implantation"])
assert result.score < 30 or result.flagged == (result.score < 30)
```
**Expected Result:** ✅ Items below threshold have `hidden: true` in details.

**Actual Result:** _________ **PASS / FAIL:** _________

### 8.6 🟢 All gates run via orchestrator
```python
from autoinfo.quality import run_quality_gates
item = Item(id="6", source_name="pubmed", title="Test", content="IVF test content about embryos", collected_at="now", quality_tier=1)
context = {"source_config": {"quality_tier": 1}, "topic_keywords": ["IVF", "embryo"]}
results = run_quality_gates(item, context)
assert "G1" in results
assert "G3" in results
```
**Expected Result:** ✅ `run_quality_gates()` returns results for all active gates.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q8 Verdict

| Scenario | Result |
|----------|--------|
| 8.1 G1 flags Tier 3+ | ⬜ |
| 8.2 G1 passes Tier 1 | ⬜ |
| 8.3 G2 URL dedup | ⬜ |
| 8.4 G3 relevance 0-100 | ⬜ |
| 8.5 G3 hidden threshold | ⬜ |
| 8.6 All gates via orchestrator | ⬜ |

**OVERALL: ⬜**

---

## Q9: Are quality gates advisory (never block/discard)?

**User says:** "If an item fails a quality gate, is it still stored? I don't want to lose content."

### 9.1 🟢 Advisory principle — all items stored regardless of gate results
```python
from autoinfo.quality import run_quality_gates
from autoinfo.models import Item
item = Item(id="7", source_name="unknown-blog", title="Low quality", content="spam content", collected_at="now", quality_tier=4)
results = run_quality_gates(item, {"source_config": {"quality_tier": 4}, "topic_keywords": ["test"]})
# All gates should pass (advisory) — flagging but not failing
for gate_name, result in results.items():
    assert result.passed == True  # or acceptable to pass with flags
```
**Expected Result:** ✅ All gates pass (advisory). Item is flagged but not discarded.

**Actual Result:** _________ **PASS / FAIL:** _________

### 9.2 🟢 KBStore stores flagged items
```python
from autoinfo.kb import KBStore
from pathlib import Path
import tempfile
with tempfile.TemporaryDirectory() as td:
    store = KBStore(Path(td) / "knowledge")
    item = Item(id="8", source_name="blog", title="Test", content="test", collected_at="now", quality_tier=4)
    entry = store.store_entry(item)
    assert entry.file_path != ""
    assert Path(entry.file_path).exists()
```
**Expected Result:** ✅ Flagged items are still stored as KB entries. File exists on disk.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q9 Verdict

| Scenario | Result |
|----------|--------|
| 9.1 Gates are advisory | ⬜ |
| 9.2 Flagged stored | ⬜ |

**OVERALL: ⬜**

---

# Part 6: KB Storage & Search

---

## Q10: Are KB entries stored as correct Markdown files?

**User says:** "I want my knowledge base as Markdown files I can open in Obsidian."

### 10.1 🟢 Markdown file created at correct path
```python
from autoinfo.kb import KBStore
from pathlib import Path
import tempfile
with tempfile.TemporaryDirectory() as td:
    store = KBStore(Path(td) / "knowledge")
    item = Item(id="9", source_name="pubmed", title="IVF Research 2026", content="Abstract...", collected_at="2026-07-20", domain="medical-research", topic_tags=["ivf"])
    entry = store.store_entry(item)
    assert "knowledge/medical-research/01-Raw/ivf/" in entry.file_path
    assert entry.file_path.endswith(".md")
    assert Path(entry.file_path).exists()
```
**Expected Result:** ✅ File at `knowledge/<domain>/01-Raw/<topic>/<YYYY-MM-DD>-<slug>.md`.

**Actual Result:** _________ **PASS / FAIL:** _________

### 10.2 🟢 YAML frontmatter has all required fields
```python
import yaml, re
with open(entry.file_path) as f:
    content = f.read()
match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
assert match
frontmatter = yaml.safe_load(match.group(1))
assert "title" in frontmatter
assert "source_url" in frontmatter
assert "source_type" in frontmatter
assert "source_platform" in frontmatter
assert "collected_at" in frontmatter
assert "quality_tier" in frontmatter
```
**Expected Result:** ✅ All required frontmatter fields present.

**Actual Result:** _________ **PASS / FAIL:** _________

### 10.3 🟢 Body contains original content + extracted fields
```python
with open(entry.file_path) as f:
    content = f.read()
assert "IVF Research 2026" in content  # title
```
**Expected Result:** ✅ Body contains original item content.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q10 Verdict

| Scenario | Result |
|----------|--------|
| 10.1 Correct file path | ⬜ |
| 10.2 Frontmatter fields | ⬜ |
| 10.3 Body content | ⬜ |

**OVERALL: ⬜**

---

## Q11: Does SQLite metadata index work correctly?

**User says:** "I need fast listing of my knowledge base entries."

### 11.1 🟢 SQLite index stores and retrieves entries
```python
from autoinfo.kb import SQLiteIndex
from pathlib import Path
import tempfile
with tempfile.TemporaryDirectory() as td:
    index = SQLiteIndex(Path(td) / "autoinfo.db")
    index.init_db()
    from autoinfo.models import KBEntry
    entry = KBEntry(entry_id="test-1", title="Test Entry", domain="medical-research", source_url="https://example.com", source_type="api", source_platform="pubmed", collected_at="2026-07-20")
    index.index_entry(entry)
    retrieved = index.get_entry("test-1")
    assert retrieved["title"] == "Test Entry"
```
**Expected Result:** ✅ Entry stored and retrieved with correct fields.

**Actual Result:** _________ **PASS / FAIL:** _________

### 11.2 🟢 list_entries returns paginated results
```python
with tempfile.TemporaryDirectory() as td:
    index = SQLiteIndex(Path(td) / "autoinfo.db")
    index.init_db()
    # Add 5 entries
    for i in range(5):
        entry = KBEntry(entry_id=f"test-{i}", title=f"Entry {i}", domain="medical-research", source_url=f"https://example.com/{i}", source_type="api", source_platform="pubmed", collected_at="2026-07-20")
        index.index_entry(entry)
    page1 = index.list_entries("medical-research", limit=2, offset=0)
    assert len(page1) == 2
    page2 = index.list_entries("medical-research", limit=2, offset=2)
    assert len(page2) == 2
```
**Expected Result:** ✅ Pagination returns correct slices.

**Actual Result:** _________ **PASS / FAIL:** _________

### 11.3 🟢 list_entries orders by collected_at desc
```python
with tempfile.TemporaryDirectory() as td:
    index = SQLiteIndex(Path(td) / "autoinfo.db")
    index.init_db()
    dates = ["2026-07-19", "2026-07-20", "2026-07-18"]
    for i, d in enumerate(dates):
        entry = KBEntry(entry_id=f"date-{i}", title=f"Entry {i}", domain="medical-research", source_url=f"https://example.com/{i}", source_type="api", source_platform="pubmed", collected_at=d)
        index.index_entry(entry)
    results = index.list_entries("medical-research")
    assert results[0]["collected_at"] >= results[1]["collected_at"]
```
**Expected Result:** ✅ Most recent entries first.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q11 Verdict

| Scenario | Result |
|----------|--------|
| 11.1 Store/retrieve | ⬜ |
| 11.2 Pagination | ⬜ |
| 11.3 Ordering | ⬜ |

**OVERALL: ⬜**

---

## Q12: Is dedup working (URL + PMID/DOI)?

**User says:** "I don't want duplicate articles in my knowledge base."

### 12.1 🟢 URL exact match dedup
```python
from autoinfo.dedup import DedupChecker
checker = DedupChecker()
item = Item(id="dup-1", source_name="pubmed", source_url="https://doi.org/10.1234/test", title="Dup Article", content="same content", collected_at="now")
existing = [{"source_url": "https://doi.org/10.1234/test"}]
result = checker.check(item, existing)
assert result["is_duplicate"] == True
```
**Expected Result:** ✅ Same URL → duplicate.

**Actual Result:** _________ **PASS / FAIL:** _________

### 12.2 🟢 PMID match dedup (from raw_data)
```python
item = Item(id="dup-2", source_name="pubmed", source_url="https://example.com/a", title="Dup by PMID", content="content", collected_at="now", raw_data={"pmid": "12345678"})
existing = [{"raw_data": {"pmid": "12345678"}}]
# Adjust for actual DedupChecker API
result = checker.check(item, existing, check_pmid=True)
```
**Expected Result:** ✅ Same PMID → duplicate.

**Actual Result:** _________ **PASS / FAIL:** _________

### 12.3 🟢 Unique items pass dedup
```python
item = Item(id="unique-1", source_name="pubmed", source_url="https://doi.org/10.9999/unique", title="Unique Article", content="different", collected_at="now")
existing = [{"source_url": "https://doi.org/10.1234/other"}]
result = checker.check(item, existing)
assert result["is_duplicate"] == False
```
**Expected Result:** ✅ Different URL → unique, not duplicate.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q12 Verdict

| Scenario | Result |
|----------|--------|
| 12.1 URL dedup | ⬜ |
| 12.2 PMID dedup | ⬜ |
| 12.3 Unique passes | ⬜ |

**OVERALL: ⬜**

---

# Part 7: Error & Boundary Matrix

---

## Q13: What happens with missing/corrupt/empty inputs?

**User says:** "What if I pass wrong arguments? What if config is corrupted?"

### 13.1 🔴 Missing project base directory
```bash
autoinfo status --domain nonexistent
```
**Expected Result:** ❌ Domain may not exist. Error message mentions domain not found. No traceback.

**Actual Result:** _________ **PASS / FAIL:** _________

### 13.2 🔴 Empty project name in config
```yaml
# Create config with empty project name
mkdir -p /tmp/bad-config/.autoinfo
cat > /tmp/bad-config/.autoinfo/config.yaml << 'EOF'
project:
  name: ""
llm:
  provider: openrouter
  model: deepseek/deepseek-chat
  api_key: ${AUTOINFO_LLM_API_KEY}
domains: []
EOF
```
```bash
cd /tmp/bad-config && autoinfo doctor
```
**Expected Result:** ❌ Doctor reports config validation error. No crash.

**Actual Result:** _________ **PASS / FAIL:** _________

### 13.3 🔴 Invalid YAML config
```bash
mkdir -p /tmp/broken-yaml/.autoinfo
echo "invalid: yaml: :::: broken" > /tmp/broken-yaml/.autoinfo/config.yaml
cd /tmp/broken-yaml && autoinfo doctor
```
**Expected Result:** ❌ Doctor reports YAML parsing error with file path and line number. No crash.

**Actual Result:** _________ **PASS / FAIL:** _________

### 13.4 🟢 List summaries with empty domain
```bash
cd /tmp/test-autoinfo && autoinfo summaries list --domain nonexistent
```
**Expected Result:** ✅ Graceful output: no entries found for domain "nonexistent". Not a crash.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q13 Verdict

| Scenario | Result |
|----------|--------|
| 13.1 Nonexistent domain | ⬜ |
| 13.2 Invalid config | ⬜ |
| 13.3 Broken YAML | ⬜ |
| 13.4 Empty summaries | ⬜ |

**OVERALL: ⬜**

---

## Q14: What happens with missing config/env vars?

**User says:** "What if I run commands without setting up anything?"

### 14.1 🔴 Missing LLM API key
```bash
unset AUTOINFO_LLM_API_KEY
autoinfo doctor  # Should still work, just report LLM as not configured
```
**Expected Result:** ✅ Doctor reports "LLM: no API key configured". Other checks still pass. No crash.

**Actual Result:** _________ **PASS / FAIL:** _________

### 14.2 🔴 Missing config directory
```bash
cd /tmp/nonexistent && autoinfo doctor
```
**Expected Result:** ✅ Doctor reports config not found. No crash.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q14 Verdict

| Scenario | Result |
|----------|--------|
| 14.1 No LLM key | ⬜ |
| 14.2 No config | ⬜ |

**OVERALL: ⬜**

---

## Q15: What happens with network errors (PubMed timeout)?

**User says:** "What if PubMed is down when I try to collect?"

### 15.1 🟢 PubMed handler retries on timeout
```python
from unittest.mock import patch
from autoinfo.collectors.pubmed import PubMedHandler

with patch("httpx.get") as mock_get:
    mock_get.side_effect = [Exception("timeout"), Exception("timeout"), MagicMock(status_code=200, text="...")]
    handler = PubMedHandler()
    # Should retry 3 times then succeed
    result = handler.search("IVF", max_results=3)
```
**Expected Result:** ✅ Handler retries 3x with backoff. Succeeds on third attempt.

**Actual Result:** _________ **PASS / FAIL:** _________

### 15.2 🟢 Handler returns empty on permanent error (crash one source, continue others)
```python
from autoinfo.collect import run_collection
# With mocked PubMed that fails
# Collection should still complete for other sources
```
**Expected Result:** ✅ Collection orchestrator logs error for failing source, continues with other sources.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q15 Verdict

| Scenario | Result |
|----------|--------|
| 15.1 PubMed retry | ⬜ |
| 15.2 Source error isolation | ⬜ |

**OVERALL: ⬜**

---

## Q16: What happens with LLM errors?

**User says:** "What if the LLM API times out or returns bad data?"

### 16.1 🔴 LLM timeout — retry then graceful failure
```python
from unittest.mock import patch
from autoinfo.llm import LLMExtractor
from autoinfo.models import Item

with patch("autoinfo.llm.litellm.completion") as mock_completion:
    mock_completion.side_effect = Exception("LLM API timeout")
    extractor = LLMExtractor()
    item = Item(id="err-1", title="Test", content="test", collected_at="now")
    result = extractor.extract_with_retry(item, max_retries=2)
    assert result is not None  # returns default/empty result, doesn't crash
```
**Expected Result:** ✅ Extraction returns default ExtractionResult (empty fields) on error. Does NOT crash pipeline.

**Actual Result:** _________ **PASS / FAIL:** _________

### 16.2 🟢 Process pipeline continues on LLM failure (item-level isolation)
```python
# Processing should continue with next item even if one LLM call fails
```
**Expected Result:** ✅ Single-item LLM failure does not stop the entire pipeline.

**Actual Result:** _________ **PASS / FAIL:** _________

### 16.3 🟢 Malformed JSON response handled gracefully
```python
from autoinfo.llm import LLMExtractor
with patch("autoinfo.llm.litellm.completion") as mock:
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "not valid json at all"
    mock.return_value = mock_response
    extractor = LLMExtractor()
    item = Item(id="err-2", title="Test", content="test", collected_at="now")
    result = extractor.extract(item)
    assert result is not None  # returns default, doesn't crash
```
**Expected Result:** ✅ Malformed JSON returns default ExtractionResult. Doesn't crash.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q16 Verdict

| Scenario | Result |
|----------|--------|
| 16.1 LLM timeout retry | ⬜ |
| 16.2 Item-level isolation | ⬜ |
| 16.3 Malformed JSON | ⬜ |

**OVERALL: ⬜**

---

# Part 8: Production Validation

---

## Q17: Does `autoinfo doctor` detect all system issues?

**User says:** "I want to verify my setup is correct before running anything."

### 17.1 🟢 Doctor runs in fresh project
```bash
cd /tmp && rm -rf test-doctor && mkdir test-doctor && cd test-doctor
autoinfo init --demo medical-research
autoinfo doctor
```
**Expected Result:** ✅ Checks all 4 areas (Python, Config, LLM, Sources). Human-readable output.

**Actual Result:** _________ **PASS / FAIL:** _________

### 17.2 🟢 Doctor detects missing Python version
**Expected Result:** ✅ If Python < 3.11, doctor reports version error. If >= 3.11, passes.

**Actual Result:** _________ **PASS / FAIL:** _________

### 17.3 🟢 Existing test suite passes
```bash
cd /path/to/AutoInfo && pytest -v --tb=short
```
**Expected Result:** ✅ 200+ tests pass. 0 failures.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q17 Verdict

| Scenario | Result |
|----------|--------|
| 17.1 Doctor in fresh project | ⬜ |
| 17.2 Python version check | ⬜ |
| 17.3 Test suite | ⬜ |

**OVERALL: ⬜**

---

## Q18: Does the MCP server work via stdio process?

**User says:** "In production, MCP runs as a separate process. Does the stdio protocol work?"

### 18.1 🟢 MCP server starts and responds
```bash
echo '{"jsonrpc":"2.0","id":1,"method":"ping","params":{}}' | timeout 5 python3 -m autoinfo.mcp.server 2>/dev/null
```
**Expected Result:** ✅ Server starts. Responds to JSON-RPC ping. Exit code 0.

**Actual Result:** _________ **PASS / FAIL:** _________

### 18.2 🔴 MCP server rejects invalid JSON-RPC
```bash
echo 'invalid json' | timeout 5 python3 -m autoinfo.mcp.server 2>/dev/null; echo "Exit: $?"
```
**Expected Result:** ❌ Server does NOT crash. Returns JSON-RPC error response. No Python traceback.

**Actual Result:** _________ **PASS / FAIL:** _________

### 18.3 🟢 MCP server has correct entry point
**Expected Result:** ✅ `python -m autoinfo.mcp.server` works from anywhere. Module structure correct.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q18 Verdict

| Scenario | Result |
|----------|--------|
| 18.1 Server starts | ⬜ |
| 18.2 Invalid JSON-RPC | ⬜ |
| 18.3 Entry point | ⬜ |

**OVERALL: ⬜**

---

## Q19: Can the full pipeline run without crashes?

**User says:** "Can I run the entire init → collect → process → summaries flow without errors?"

### 19.1 🟢 3 consecutive pipeline runs — no crash
```bash
for i in $(seq 1 3); do
    cd /tmp && rm -rf "stress-test-$i" && mkdir "stress-test-$i" && cd "stress-test-$i"
    autoinfo init --demo medical-research
    autoinfo collect --domain medical-research --topic "IVF" --limit 2
    autoinfo process --domain medical-research
    echo "Run $i: $?"
done
```
**Expected Result:** ✅ All 3 runs complete (exit 0 or expected). No crash, no file handle leak.

**Actual Result:** _________ **PASS / FAIL:** _________

### 19.2 🟢 KB search works after pipeline
```bash
autoinfo summaries list --domain medical-research --json
```
**Expected Result:** ✅ Valid JSON output with entries.

**Actual Result:** _________ **PASS / FAIL:** _________

### 19.3 🟢 Autoinfo imports cleanly
```bash
python3 -c "import autoinfo; print(f'AutoInfo v{autoinfo.__version__}')"
```
**Expected Result:** ✅ Package imports without error. Version string present.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q19 Verdict

| Scenario | Result |
|----------|--------|
| 19.1 3 consecutive runs | ⬜ |
| 19.2 KB after pipeline | ⬜ |
| 19.3 Import cleanly | ⬜ |

**OVERALL: ⬜**

---

# Part 9: Final Verdict

---

## Overall PASS/FAIL Summary

| Part | Section | Verdict |
|------|---------|---------|
| 1 | Core Pipeline Journeys (Q1-Q4) | ⬜ |
| 2 | CLI Surface Mastery (Q5-Q6) | ⬜ |
| 3 | MCP Surface Mastery (Q7) | ⬜ |
| 4 | Agent-as-User Real API Configuration & E2E Tests (Q20-Q23) | ⬜ |
| 5 | Quality Gate Validation (Q8-Q9) | ⬜ |
| 6 | KB Storage & Search (Q10-Q12) | ⬜ |
| 7 | Error & Boundary Matrix (Q13-Q16) | ⬜ |
| 8 | Production Validation (Q17-Q19) | ⬜ |

**GRAND TOTAL: ⬜ / 23 Questions**

**OVERALL VERDICT: ⬜**

---

## Production Gap Checklist

| Criteria | Status | Notes |
|----------|--------|-------|
| All 6 MCP tools respond correctly | ⬜ | Q7 |
| All 6 CLI commands work | ⬜ | Q5 |
| `init` creates valid project | ⬜ | Q1 |
| PubMed collection works (real API, no mock) | ⬜ | Q20 |
| RSS collection works (real API, no mock) | ⬜ | Q20 |
| LLM key configured and detected by doctor | ⬜ | Q21 |
| LLM extraction processes real items into KB entries | ⬜ | Q21 |
| Full E2E pipeline (init→collect→process→search→output) with real APIs | ⬜ | Q22 |
| Multi-domain pipeline with different source types (API + RSS) | ⬜ | Q22 |
| Agent can diagnose missing/misconfigured APIs | ⬜ | Q23 |
| Agent can self-heal configuration issues | ⬜ | Q23 |
| Dedup prevents duplicates | ⬜ | Q12 |
| Quality gates are advisory (no content loss) | ⬜ | Q9 |
| MCP server stdio transport works | ⬜ | Q18 |
| Error cases handled gracefully | ⬜ | Q13-Q16 |
| Test suite passes (200+) | ⬜ | Q17 |

---

## Sign-off Criteria

| Level | Requirements | Met? |
|-------|-------------|------|
| **CI Gate** | All 23 questions answered. No P0 failures (crash, data loss). | ⬜ |
| **Release Candidate** | CI Gate + Q1-Q7 + Q20-Q23 all PASS + all production gaps addressed | ⬜ |
| **Production Deploy** | Release Candidate + Q17-Q19 all PASS + no outstanding P0/P1 issues | ⬜ |

---

*Plan generated: 2026-07-20*
*Based on: AutoInfo v0.1 codebase — 220 tests, 6 CLI commands, 6 MCP tools, Hermes KB pipeline*
