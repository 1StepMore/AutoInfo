# Part 8: Agent-as-User Real API Configuration & E2E Tests (Q49-Q53)

**Coverage:** Real PubMed/RSS/Web collection, real LLM processing, multi-domain, config override, self-healing

**Note:** These sections require real API endpoints (PubMed, RSS feeds) and a valid `AUTOINFO_LLM_API_KEY`.

---

## Q49: Real PubMed API Collection (no API key)

**Agent says:** "I want to configure real PubMed API and collect real medical papers."

### Prerequisites
```bash
cd /tmp && rm -rf test-q49 && mkdir test-q49 && cd test-q49
autoinfo init --demo medical-research
```

### Scenarios

#### 49.1 🟢 Collect real PubMed items (no API key needed)
```bash
autoinfo collect --domain medical-research --topic "IVF breakthroughs" --source pubmed --limit 3
```
**Expected Result:**
- ✅ Exit code 0
- ✅ Output shows "Items found: N" and "Items collected: N" (N ≥ 1, ≤ 3)
- ✅ Items cached to `collections/medical-research/pubmed/<date>/<id>.json`
- ✅ Cached JSON files have: `source_url`, `title`, `content` (or `abstract`), `source_type: "api"`, `source_platform: "pubmed"`, `collected_at`
- ✅ Real PubMed data present (PMID, authors, journal, publication date)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 49.2 🟢 Verify PubMed item structure
```bash
ls collections/medical-research/pubmed/*/*.json | head -3
python3 -c "
import json, glob
for f in sorted(glob.glob('collections/medical-research/pubmed/*/*.json'))[:1]:
    with open(f) as fh:
        item = json.load(fh)
    print(f'Title: {item.get(\"title\", \"?\")}')
    print(f'Source: {item.get(\"source_type\", \"?\")}/{item.get(\"source_platform\", \"?\")}')
    print(f'URL: {item.get(\"source_url\", \"?\")}')
    print(f'Has abstract: {bool(item.get(\"content\", \"\"))}')
    raw = item.get('raw_data', {})
    print(f'PMID: {raw.get(\"pmid\", \"?\")}')
    print(f'DOI: {raw.get(\"doi\", \"?\")}')
"
```
**Expected Result:** ✅ Items contain real PubMed metadata: PMID, DOI, authors, publication date.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q49 Verdict

| Scenario | Result |
|----------|--------|
| 49.1 PubMed collect | ⬜ |
| 49.2 Item structure | ⬜ |

**OVERALL: ⬜**

---

## Q50: Real RSS & Web Collection

**Agent says:** "I want to configure and collect from RSS feeds and web pages."

### Scenarios

#### 50.1 🟢 RSS feed collection (ai-commercial domain)
```bash
cd /tmp && rm -rf test-q50 && mkdir test-q50 && cd test-q50
autoinfo init --demo ai-commercial
autoinfo collect --domain ai-commercial --source techcrunch --limit 5
```
**Expected Result:**
- ✅ Exit code 0
- ✅ Items collected with `title`, `link`, `summary`, `published` date
- ✅ Items cached to `collections/ai-commercial/techcrunch/<date>/<id>.json`
- ✅ Each item has `source_type: "rss"`, `source_platform: "techcrunch"`
- ✅ Content is real article summaries (not empty)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 50.2 🟢 Web scraping (trafilatura + Playwright fallback)
```bash
# Add a web source via MCP tool
python3 -c "
from autoinfo.mcp.server import app
import json
result = app.call_tool('add_source', {
    'domain': 'medical-research',
    'name': 'who-health',
    'type': 'web',
    'url': 'https://www.who.int/health-topics',
    'quality_tier': 1
})
print(json.loads(result.content[0].text))
"

autoinfo collect --domain medical-research --source who-health --limit 3
```
**Expected Result:**
- ✅ Exit code 0
- ✅ Web page content extracted (title, body text)
- ✅ Item has `source_type: "web"`, `source_platform: "who-health"`
- ✅ Content is readable text (not raw HTML)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 50.3 🔴 Invalid source URL — graceful error
```bash
autoinfo sources add --name broken-source --type web --url https://this-domain-does-not-exist-12345.com --domain medical-research --quality-tier 3
autoinfo collect --domain medical-research --source broken-source --limit 3 2>&1
```
**Expected Result:**
- ❌ Handler reports error for broken source (connection error or timeout)
- ❌ No crash — error is logged
- ❌ Other sources continue if run together

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q50 Verdict

| Scenario | Result |
|----------|--------|
| 50.1 RSS collect | ⬜ |
| 50.2 Web scrape | ⬜ |
| 50.3 Invalid URL | ⬜ |

**OVERALL: ⬜**

---

## Q51: Real LLM Processing [REQUIRES LLM KEY]

**Agent says:** "I need to configure a real LLM API key, process collected items, and verify extraction."

### Prerequisites
```bash
cd /tmp && rm -rf test-q51 && mkdir test-q51 && cd test-q51
autoinfo init --demo medical-research
autoinfo collect --domain medical-research --topic "IVF breakthroughs" --source pubmed --limit 3
```

### Scenarios

#### 51.1 🟢 Doctor detects configured LLM key
```bash
export AUTOINFO_LLM_API_KEY="sk-or-v1-..."
autoinfo doctor --json | python3 -c "
import sys, json
data = json.load(sys.stdin)
llm = data.get('llm', {})
print(f'Key configured: {llm.get(\"key_configured\", False)}')
print(f'Provider: {llm.get(\"provider\", \"?\")}')
print(f'Model: {llm.get(\"model\", \"?\")}')
assert llm.get('key_configured') == True, 'LLM key not detected!'
print('✅ Doctor detects configured LLM')
"
```
**Expected Result:** ✅ `doctor --json` shows `llm.key_configured: true`.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 51.2 🟢 Process with real LLM — verify KB entries
```bash
autoinfo process --domain medical-research

# Verify KB entries exist
ls knowledge/medical-research/01-Raw/ivf-breakthroughs/

# Inspect entry for LLM extraction
head -40 knowledge/medical-research/01-Raw/ivf-breakthroughs/*.md | head -60
```
**Expected Result:**
- ✅ `process` exit code 0
- ✅ Per-item progress shown
- ✅ KB Markdown files exist at `knowledge/medical-research/01-Raw/ivf-breakthroughs/<date>-<slug>.md`
- ✅ YAML frontmatter includes all standard fields
- ✅ Body includes LLM-extracted: `## TL;DR` section, `## Key Points` list
- ✅ Extracted TL;DR is meaningful (not "No summary available")

**Actual Result:** _________ **PASS / FAIL:** _________

#### 51.3 🟢 Provider/model override
```bash
python3 -c "
import yaml
with open('.autoinfo/config.yaml') as f:
    cfg = yaml.safe_load(f)
if 'tasks' not in cfg.get('llm', {}):
    cfg['llm']['tasks'] = {}
cfg['llm']['tasks']['extraction'] = {
    'provider': 'openrouter',
    'model': 'deepseek/deepseek-chat',
    'max_tokens': 4000
}
with open('.autoinfo/config.yaml', 'w') as f:
    yaml.dump(cfg, f)
print('✅ Config updated: extraction task uses deepseek/deepseek-chat')
"

# Collect and process with overridden model
autoinfo collect --domain medical-research --topic "gene therapy CRISPR" --source pubmed --limit 2
autoinfo process --domain medical-research
ls knowledge/medical-research/01-Raw/gene-therapy-crispr/ 2>/dev/null && echo '✅ KB entries created with overridden model'
```
**Expected Result:** ✅ Process uses overridden model. KB entries created.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 51.4 🟢 Fallback chain — primary fails, fallback succeeds
```bash
python3 -c "
import yaml
with open('.autoinfo/config.yaml') as f:
    cfg = yaml.safe_load(f)
cfg['llm']['provider'] = 'nonexistent-provider'
cfg['llm']['model'] = 'fake/model'
cfg['llm']['fallback'] = [
    {'provider': 'openrouter', 'model': 'deepseek/deepseek-chat'}
]
with open('.autoinfo/config.yaml', 'w') as f:
    yaml.dump(cfg, f)
print('✅ Config: broken primary + fallback configured')
"

autoinfo process --domain medical-research 2>&1 | tail -10
ls knowledge/medical-research/01-Raw/ivf-breakthroughs/*.md 2>/dev/null && echo '✅ KB entries created via fallback'
```
**Expected Result:** ✅ Processing shows fallback activation in logs. KB entries still created via fallback.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 51.5 🔴 Missing/invalid LLM key — graceful failure
```bash
unset AUTOINFO_LLM_API_KEY
autoinfo process --domain medical-research 2>&1; echo 'EXIT:' $?
```
**Expected Result:** ❌ Exit code != 0. Error message about missing API key. No traceback. No crash/hang.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q51 Verdict

| Scenario | Result |
|----------|--------|
| 51.1 Doctor detects key | ⬜ |
| 51.2 Process real LLM | ⬜ |
| 51.3 Model override | ⬜ |
| 51.4 Fallback chain | ⬜ |
| 51.5 Missing key | ⬜ |

**OVERALL: ⬜**

---

## Q52: Full E2E Pipeline with Real APIs

**Agent says:** "I want the complete experience — init, collect, process, search, output, export."

### Scenarios

#### 52.1 🟢 Full E2E pipeline
```bash
cd /tmp && rm -rf test-e2e && mkdir test-e2e && cd test-e2e

# Phase 1: Init
echo '=== PHASE 1: INIT ==='
autoinfo init --demo medical-research

# Phase 2: Doctor
echo '=== PHASE 2: DOCTOR ==='
autoinfo doctor --json | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'Python: {d.get(\"python\",{}).get(\"version\",\"?\")} | Config: {d.get(\"config\",{}).get(\"valid\",False)} | LLM key: {d.get(\"llm\",{}).get(\"key_configured\",False)}')
"

# Phase 3: Collect real PubMed
echo '=== PHASE 3: COLLECT ==='
autoinfo collect --domain medical-research --topic "IVF breakthroughs" --source pubmed --limit 3

# Phase 4: Process with real LLM
echo '=== PHASE 4: PROCESS ==='
autoinfo process --domain medical-research

# Phase 5: Search KB
echo '=== PHASE 5: SEARCH ==='
autoinfo summaries list --domain medical-research --json | python3 -c "
import sys, json
data = json.load(sys.stdin)
entries = data.get('entries', [])
print(f'{len(entries)} KB entries')
for e in entries[:3]:
    print(f'  - {e.get(\"title\", \"?\")[:60]} | score={e.get(\"relevance_score\", \"?\")} | {e.get(\"tier\", \"?\")}')
"

# Phase 6: Generate digest
echo '=== PHASE 6: DIGEST ==='
autoinfo output digest --domain medical-research --period week
ls outputs/medical-research/digest/

# Phase 7: Export
echo '=== PHASE 7: EXPORT ==='
autoinfo output export --domain medical-research --format json
ls exports/medical-research/

echo '=== E2E COMPLETE ==='
```
**Expected Result:**
- ✅ Phase 1: Config files created with correct structure
- ✅ Phase 2: Doctor reports all green
- ✅ Phase 3: ≥1 PubMed items collected
- ✅ Phase 4: KB entries with LLM-extracted content
- ✅ Phase 5: Summaries list returns entries
- ✅ Phase 6: Digest generated (Markdown file)
- ✅ Phase 7: JSON export valid
- ✅ Every phase exit code 0

**Actual Result:** _________ **PASS / FAIL:** _________

#### 52.2 🟢 Multi-domain pipeline (medical + ai-commercial)
```bash
cd /tmp && rm -rf test-multi-e2e && mkdir test-multi-e2e && cd test-multi-e2e
autoinfo init --demo medical-research --demo ai-commercial

# Collect from both domains
echo '=== COLLECT BOTH ==='
autoinfo collect --domain medical-research --topic "cancer immunotherapy" --source pubmed --limit 3
autoinfo collect --domain ai-commercial --source techcrunch --limit 5

# Process both
echo '=== PROCESS BOTH ==='
autoinfo process --domain medical-research
autoinfo process --domain ai-commercial

# Verify both
echo '=== VERIFY ==='
autoinfo summaries list --domain medical-research --json | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Medical: {len(d.get(\"entries\",[]))} entries')"
autoinfo summaries list --domain ai-commercial --json | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'AI: {len(d.get(\"entries\",[]))} entries')"
```
**Expected Result:**
- ✅ Both init commands succeed
- ✅ Both domains have their own KB entries
- ✅ Medical: entries with PubMed metadata
- ✅ AI-commercial: entries with RSS metadata
- ✅ Both searchable independently

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q52 Verdict

| Scenario | Result |
|----------|--------|
| 52.1 Full E2E | ⬜ |
| 52.2 Multi-domain | ⬜ |

**OVERALL: ⬜**

---

## Q53: Agent Self-Healing & Diagnostics

**Agent says:** "I want to understand how to detect, diagnose, and recover from config issues."

### Scenarios

#### 53.1 🟢 Agent diagnoses missing LLM key
```bash
cd /tmp && rm -rf test-diag && mkdir test-diag && cd test-diag
autoinfo init --demo medical-research
unset AUTOINFO_LLM_API_KEY

autoinfo doctor --json | python3 -c "
import sys, json
d = json.load(sys.stdin)
llm = d.get('llm', {})
if not llm.get('key_configured'):
    print('❌ ISSUE: LLM API key not configured')
    print('🔧 FIX: export AUTOINFO_LLM_API_KEY=\"sk-...\" or set in config')
else:
    print('✅ LLM OK')
"
```
**Expected Result:** ✅ Doctor runs without crash. Agent can parse JSON to identify missing key.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 53.2 🟢 Agent diagnoses unreachable source URL
```bash
# Add a broken source
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

autoinfo doctor --json | python3 -c "
import sys, json
d = json.load(sys.stdin)
sources = d.get('sources', {}).get('results', [])
for s in sources:
    status = s.get('status', 'unknown')
    print(f'{s.get(\"name\", \"?\"):30s} status={status:10s} latency={s.get(\"latency_ms\", \"?\")}ms')
"
```
**Expected Result:** ✅ Doctor checks all sources. Broken source reports error/not ok. Working sources report ok.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 53.3 🟢 Agent self-heals (diagnose → fix → verify)
```bash
cd /tmp && rm -rf test-heal && mkdir test-heal && cd test-heal
autoinfo init --demo medical-research
unset AUTOINFO_LLM_API_KEY

# Diagnose
echo '=== DIAGNOSE ==='
autoinfo doctor --json | python3 -c "
import sys, json, os
d = json.load(sys.stdin)
issues = []
if not d.get('llm', {}).get('key_configured'):
    issues.append('llm_key')
if not d.get('config', {}).get('valid'):
    issues.append('config')
for issue in issues:
    print(f'ISSUE: {issue}')
print(f'ISSUES_COUNT={len(issues)}')
"

# Fix
echo '=== FIX ==='
export AUTOINFO_LLM_API_KEY="sk-or-v1-test-fix-key"

# Verify
echo '=== VERIFY ==='
autoinfo doctor --json | python3 -c "
import sys, json
d = json.load(sys.stdin)
fixed = d.get('llm', {}).get('key_configured', False)
print(f'LLM key fixed: {fixed}')
assert fixed, 'Self-heal failed'
print('✅ Self-heal successful')
"
```
**Expected Result:** ✅ Agent follows diagnose → fix → verify cycle. After fixing, doctor confirms resolution.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q53 Verdict

| Scenario | Result |
|----------|--------|
| 53.1 Diagnose missing key | ⬜ |
| 53.2 Diagnose broken source | ⬜ |
| 53.3 Self-heal cycle | ⬜ |

**OVERALL: ⬜**
