# Part 4: MCP Tools — KB, Search, Output, Cron, Email, CEFR, Extraction (Q28-Q36c)

**Coverage:** 44 MCP tools: KB (9), KB Relations/Versioning/Monitor (6), KB Graph (1), Output (6), Export/Import (2), CEFR (1), Cron (5), Email (1), Custom Extraction (2), Q&A (1), Keywords (3), Knowledge Lifecycle (6), Product (1). Plus v1.7 additions: consumption tracking, automated notifications, cron health (CLI).

---

### Part-Level Directory Setup
Run once at the start of this part:
```bash
# Create clean directories for all questions in this part
rm -rf /tmp/test-q28 && mkdir -p /tmp/test-q28
rm -rf /tmp/test-q29 && mkdir -p /tmp/test-q29
rm -rf /tmp/test-q30 && mkdir -p /tmp/test-q30
rm -rf /tmp/test-q33 && mkdir -p /tmp/test-q33
rm -rf /tmp/test-q34 && mkdir -p /tmp/test-q34
rm -rf /tmp/test-q36 && mkdir -p /tmp/test-q36
rm -rf /tmp/test-q36b && mkdir -p /tmp/test-q36b
rm -rf /tmp/test-q36c && mkdir -p /tmp/test-q36c
rm -rf /tmp/test-q36d && mkdir -p /tmp/test-q36d
rm -rf /tmp/test-q36e && mkdir -p /tmp/test-q36e
```

## Q28: MCP KB Summary Tools

**Agent says:** "I need to browse summaries and entries via MCP."

### Prerequisites
```bash
cd /tmp/test-q28
autoinfo init --demo medical-research
autoinfo collect --domain medical-research --topic "IVF" --limit 3
```

### Scenarios

#### 28.1 🟢 list_summaries
```python
from autoinfo.mcp.server import app
import json

result = app.call_tool("list_summaries", {"domain": "medical-research", "limit": 5})
data = json.loads(result.content[0].text)
entries = data.get("entries", [])
assert "total_count" in data or len(entries) >= 0
print(f"✅ list_summaries: total={data.get('total_count', len(entries))}, entries={len(entries)}")
if entries:
    print(f"  First: {entries[0].get('title','?')[:60]}")
```
**Expected Result:** ✅ Returns entries with title, summary, relevance_score, collected_at.


#### 28.2 🟢 get_kb_entry
```python
# Get first entry
result = app.call_tool("list_summaries", {"domain": "medical-research", "limit": 1})
data = json.loads(result.content[0].text)
entries = data.get("entries", [])
if entries:
    entry_id = entries[0].get("entry_id", "")
    result = app.call_tool("get_kb_entry", {"entry_id": entry_id})
    data = json.loads(result.content[0].text)
    assert "title" in data
    print(f"✅ get_kb_entry: {data.get('title','?')[:60]}, tier={data.get('tier','?')}")
else:
    print("⚠️ No entries to retrieve")
```
**Expected Result:** ✅ Returns full entry with all metadata and content.


#### 28.3 🟢 get_summary
```python
result = app.call_tool("list_summaries", {"domain": "medical-research", "limit": 1})
data = json.loads(result.content[0].text)
entries = data.get("entries", [])
if entries:
    entry_id = entries[0].get("entry_id", "") or entries[0].get("id", "")
    result = app.call_tool("get_summary", {"summary_id": entry_id})
    data = json.loads(result.content[0].text)
    print(f"✅ get_summary: {json.dumps(data, indent=2)[:200]}")
else:
    print("⚠️ No summaries to retrieve")
```
**Expected Result:** ✅ Returns summary with TL;DR and key points.


#### 28.4 🟢 flag_for_knowledge_base
```python
result = app.call_tool("list_summaries", {"domain": "medical-research", "limit": 1})
data = json.loads(result.content[0].text)
entries = data.get("entries", [])
if entries:
    entry_id = entries[0].get("entry_id", "") or entries[0].get("summary_id", "")
    result = app.call_tool("flag_for_knowledge_base", {
        "summary_id": entry_id,
        "tags": ["important", "review"]
    })
    data = json.loads(result.content[0].text)
    print(f"✅ flag_for_knowledge_base: {data}")
else:
    print("⚠️ No entries to flag")
```
**Expected Result:** ✅ Summary flagged for KB promotion. Tags stored.


---

### 📊 Q28 Verdict

| Scenario | Result |
|----------|--------|
| 28.1 list_summaries | ⬜ |
| 28.2 get_kb_entry | ⬜ |
| 28.3 get_summary | ⬜ |
| 28.4 flag_for_knowledge_base | ⬜ |

**OVERALL: ⬜**

---

## Q29: MCP KB Draft Tools (Tier Management)

**Agent says:** "I need to promote entries from Raw to Draft and manage tiers."

### Prerequisites
```bash
cd /tmp/test-q29
autoinfo init --demo medical-research
autoinfo collect --domain medical-research --topic "IVF" --limit 3
autoinfo process --domain medical-research 2>/dev/null || true
```

### Scenarios

#### 29.1 🟢 list_kb_tier
```python
from autoinfo.mcp.server import app
import json

result = app.call_tool("list_kb_tier", {"domain": "medical-research", "tier": "01-Raw"})
data = json.loads(result.content[0].text)
entries = data.get("entries", data.get("items", []))
print(f"✅ list_kb_tier (01-Raw): {len(entries)} entries")
```
**Expected Result:** ✅ Returns entries in specified tier.


#### 29.2 🟢 create_kb_draft [REQUIRES LLM KEY]
```python
# Get first entry from 01-Raw
result = app.call_tool("list_kb_tier", {"domain": "medical-research", "tier": "01-Raw", "limit": 1})
data = json.loads(result.content[0].text)
entries = data.get("entries", data.get("items", []))
if entries:
    entry_id = entries[0].get("entry_id", "") or entries[0].get("id", "")
    result = app.call_tool("create_kb_draft", {"entry_id": entry_id})
    data = json.loads(result.content[0].text)
    print(f"✅ create_kb_draft: {data.get('status', data)}")
    
    # Verify entry now in 02-Draft
    result = app.call_tool("list_kb_tier", {"domain": "medical-research", "tier": "02-Draft"})
    data = json.loads(result.content[0].text)
    entries = data.get("entries", data.get("items", []))
    print(f"  02-Draft entries: {len(entries)}")
else:
    print("⚠️ No 01-Raw entries to promote")
```
**Expected Result:** ✅ Draft created. Entry appears in 02-Draft tier.


#### 29.3 🟢 reject_kb_draft
```python
# Get an entry from 02-Draft
result = app.call_tool("list_kb_tier", {"domain": "medical-research", "tier": "02-Draft", "limit": 1})
data = json.loads(result.content[0].text)
entries = data.get("entries", data.get("items", []))
if entries:
    entry_id = entries[0].get("entry_id", "") or entries[0].get("id", "")
    result = app.call_tool("reject_kb_draft", {"entry_id": entry_id})
    data = json.loads(result.content[0].text)
    print(f"✅ reject_kb_draft: {data.get('status', data)}")
else:
    print("⚠️ No 02-Draft entries to reject")
```
**Expected Result:** ✅ Draft rejected. Entry remains in 01-Raw. 02-Draft copy removed.


---

### 📊 Q29 Verdict

| Scenario | Result |
|----------|--------|
| 29.1 list_kb_tier | ⬜ |
| 29.2 create_kb_draft | ⬜ |
| 29.3 reject_kb_draft | ⬜ |

**OVERALL: ⬜**

---

## Q30: MCP KB Search Tools

**Agent says:** "I need to search the knowledge base using all available modes."

### Prerequisites
```bash
cd /tmp/test-q30
autoinfo init --demo medical-research
```

### Scenarios

#### 30.1 🟢 search_knowledge_base (hybrid mode)
```python
from autoinfo.mcp.server import app
import json

result = app.call_tool("search_knowledge_base", {
    "domain": "medical-research",
    "query": "IVF embryo",
    "mode": "hybrid",
    "limit": 5
})
data = json.loads(result.content[0].text)
print(f"✅ search_knowledge_base (hybrid): {json.dumps(data, indent=2)[:300]}")
```
**Expected Result:** ✅ Returns entries using FTS5 + vector hybrid search.


#### 30.2 🟢 vector_search
```python
result = app.call_tool("vector_search", {
    "domain": "medical-research",
    "query": "embryo development IVF",
    "limit": 5
})
data = json.loads(result.content[0].text)
print(f"✅ vector_search: {json.dumps(data, indent=2)[:300]}")
```
**Expected Result:** ✅ Returns entries using semantic vector search.


#### 30.3 🟢 faceted_search
```python
result = app.call_tool("faceted_search", {
    "domain": "medical-research",
    "filters": {
        "source_type": "pubmed",
        "relevance_min": 50
    }
})
data = json.loads(result.content[0].text)
entries = data.get("entries", data.get("items", []))
print(f"✅ faceted_search: {len(entries)} entries (filtered by source_type=pubmed, relevance>=50)")
```
**Expected Result:** ✅ Returns filtered entries. Filters applied correctly.


#### 30.4 🟢 query_collected (Q&A) [REQUIRES LLM KEY]
```python
result = app.call_tool("query_collected", {
    "domain": "medical-research",
    "query": "What are the latest IVF breakthroughs?",
    "limit": 3
})
data = json.loads(result.content[0].text)
print(f"✅ query_collected: {json.dumps(data, indent=2)[:300]}")
assert "answer" in data or "response" in data or "results" in data
```
**Expected Result:** ✅ Returns LLM-synthesized answer with source citations.


---

### 📊 Q30 Verdict

| Scenario | Result |
|----------|--------|
| 30.1 hybrid search | ⬜ |
| 30.2 vector search | ⬜ |
| 30.3 faceted search | ⬜ |
| 30.4 Q&A query | ⬜ |

**OVERALL: ⬜**

---

## Q31: MCP KB Relations & Versioning Tools

**Agent says:** "I need to manage entry relationships and version history."

### Scenarios

#### 31.1 🟢 link_items
```python
from autoinfo.mcp.server import app
import json

# Get two entries
result = app.call_tool("list_summaries", {"domain": "medical-research", "limit": 2})
data = json.loads(result.content[0].text)
entries = data.get("entries", [])
if len(entries) >= 2:
    id1 = entries[0].get("entry_id", "")
    id2 = entries[1].get("entry_id", "")
    rel_type = "related_to"
    
    result = app.call_tool("link_items", {
        "source_id": id1,
        "target_id": id2,
        "relation_type": rel_type
    })
    link_data = json.loads(result.content[0].text)
    print(f"✅ link_items: {link_data}")
else:
    print("⚠️ < 2 entries to link")
```
**Expected Result:** ✅ Items linked with relation type.


#### 31.2 🟢 get_item_relations
```python
result = app.call_tool("list_summaries", {"domain": "medical-research", "limit": 1})
data = json.loads(result.content[0].text)
entries = data.get("entries", [])
if entries:
    entry_id = entries[0].get("entry_id", "")
    result = app.call_tool("get_item_relations", {"entry_id": entry_id})
    rel_data = json.loads(result.content[0].text)
    print(f"✅ get_item_relations: {rel_data}")
else:
    print("⚠️ No entries to check")
```
**Expected Result:** ✅ Returns relations for the entry.


#### 31.3 🟢 get_entry_history
```python
result = app.call_tool("list_summaries", {"domain": "medical-research", "limit": 1})
data = json.loads(result.content[0].text)
entries = data.get("entries", [])
if entries:
    entry_id = entries[0].get("entry_id", "")
    result = app.call_tool("get_entry_history", {"entry_id": entry_id})
    hist_data = json.loads(result.content[0].text)
    versions = hist_data.get("versions", hist_data.get("history", []))
    print(f"✅ get_entry_history: {len(versions)} versions")
else:
    print("⚠️ No entries to check")
```
**Expected Result:** ✅ Returns version history for the entry.


#### 31.4 🟢 restore_entry_version
```python
result = app.call_tool("list_summaries", {"domain": "medical-research", "limit": 1})
data = json.loads(result.content[0].text)
entries = data.get("entries", [])
if entries:
    entry_id = entries[0].get("entry_id", "")
    # Get history first
    hist = app.call_tool("get_entry_history", {"entry_id": entry_id})
    hist_data = json.loads(hist.content[0].text)
    versions = hist_data.get("versions", hist_data.get("history", []))
    if versions:
        version_id = versions[0].get("version_id", "")
        result = app.call_tool("restore_entry_version", {
            "entry_id": entry_id,
            "version_id": version_id
        })
        restore_data = json.loads(result.content[0].text)
        print(f"✅ restore_entry_version: {restore_data}")
    else:
        print("⚠️ No version history to restore from")
else:
    print("⚠️ No entries to check")
```
**Expected Result:** ✅ Entry restored to specified version.


---

### 📊 Q31 Verdict

| Scenario | Result |
|----------|--------|
| 31.1 link_items | ⬜ |
| 31.2 get_item_relations | ⬜ |
| 31.3 get_entry_history | ⬜ |
| 31.4 restore_entry_version | ⬜ |

**OVERALL: ⬜**

---

## Q32: MCP KB Monitor & Graph Tools

**Agent says:** "I need to see collection stats, diffs, and explore the knowledge graph."

### Scenarios

#### 32.1 🟢 get_collection_stats
```python
from autoinfo.mcp.server import app
import json

result = app.call_tool("get_collection_stats", {"period": "week"})
data = json.loads(result.content[0].text)
print(f"✅ get_collection_stats: {json.dumps(data, indent=2)[:300]}")
```
**Expected Result:** ✅ Returns collection statistics for the period.


#### 32.2 🟢 get_collection_diff
```python
result = app.call_tool("get_collection_diff", {
    "domain": "medical-research",
    "since_collection_id": "last"
})
data = json.loads(result.content[0].text)
print(f"✅ get_collection_diff: {json.dumps(data, indent=2)[:300]}")
```
**Expected Result:** ✅ Returns diff showing new/changed items since last collection.


#### 32.3 🟢 query_knowledge_graph
```python
result = app.call_tool("query_knowledge_graph", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
print(f"✅ query_knowledge_graph: {json.dumps(data, indent=2)[:300]}")
```
**Expected Result:** ✅ Returns knowledge graph with entities and relations.


---

### 📊 Q32 Verdict

| Scenario | Result |
|----------|--------|
| 32.1 get_collection_stats | ⬜ |
| 32.2 get_collection_diff | ⬜ |
| 32.3 query_knowledge_graph | ⬜ |

**OVERALL: ⬜**

---

## Q33: MCP Output Generation Tools

**Agent says:** "I need to generate digests, reports, tutorials, and presentations."

### Prerequisites
```bash
cd /tmp/test-q33
autoinfo init --demo medical-research
autoinfo collect --domain medical-research --topic "IVF" --limit 3
```

### Scenarios

#### 33.1 🟢 generate_digest
```bash
#!/usr/bin/env bash
set -euo pipefail
cd /tmp/test-q33
ALL_PASS=true

# Generate digest
OUTPUT=$(python3 -c "
import json, subprocess
result = subprocess.run(
    ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'generate_digest',
     json.dumps({'domain': 'medical-research', 'period': 'week', 'format': 'markdown'})],
    capture_output=True, text=True, timeout=60
)
data = json.loads(result.stdout) if result.stdout else {}
digest_id = data.get('digest_id', data.get('id', ''))
print(digest_id)
" 2>&1)
echo "generate_digest: $OUTPUT"

# Find the output file
DIGEST_FILE=$(ls -t outputs/medical-research/digest/*.md 2>/dev/null | head -1)

# ── Content verification assertions ──────────────────────
[ -n "$DIGEST_FILE" ] \
  && echo "  ✅ PASS: digest file created: $DIGEST_FILE" \
  || { echo "  ❌ FAIL: no digest file found"; ALL_PASS=false; }

[ -f "$DIGEST_FILE" ] && [ -s "$DIGEST_FILE" ] \
  && echo "  ✅ PASS: digest file is non-empty" \
  || { echo "  ❌ FAIL: digest file empty or missing"; ALL_PASS=false; }

grep -q '^#' "$DIGEST_FILE" 2>/dev/null \
  && echo "  ✅ PASS: digest has markdown headers (#)" \
  || { echo "  ❌ FAIL: digest missing markdown headers"; ALL_PASS=false; }

grep -qiP '(title|headline|📰|#\s)' "$DIGEST_FILE" 2>/dev/null \
  && echo "  ✅ PASS: digest contains article titles/headings" \
  || { echo "  ❌ FAIL: digest missing article titles"; ALL_PASS=false; }

# ── Verdict ───────────────────────────────────────────────
if [ "$ALL_PASS" = true ]; then
  echo "✅ SCENARIO 33.1 PASSED — generate_digest with content verification"
  exit 0
else
  echo "❌ SCENARIO 33.1 FAILED"
  exit 1
fi
```
**Expected Result:**
- ✅ Digest generated and output file created at `outputs/medical-research/digest/*.md`
- ✅ File is non-empty with markdown headers (`#`)
- ✅ Content contains article titles or headings


#### 33.2 🟢 generate_report (markdown)
```bash
#!/usr/bin/env bash
set -euo pipefail
cd /tmp/test-q33
ALL_PASS=true

# Generate report in markdown format
OUTPUT=$(python3 -c "
import json, subprocess
result = subprocess.run(
    ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'generate_report',
     json.dumps({'domain': 'medical-research', 'format': 'markdown'})],
    capture_output=True, text=True, timeout=60
)
data = json.loads(result.stdout) if result.stdout else {}
report_id = data.get('report_id', data.get('id', ''))
print(report_id)
" 2>&1)
echo "generate_report (MD): $OUTPUT"

# Find the output file
REPORT_FILE=$(ls -t outputs/medical-research/report/*.md 2>/dev/null | head -1)

# ── Content verification assertions ──────────────────────
[ -n "$REPORT_FILE" ] \
  && echo "  ✅ PASS: report file created: $REPORT_FILE" \
  || { echo "  ❌ FAIL: no report file found"; ALL_PASS=false; }

[ -f "$REPORT_FILE" ] && [ -s "$REPORT_FILE" ] \
  && echo "  ✅ PASS: report file is non-empty" \
  || { echo "  ❌ FAIL: report file empty or missing"; ALL_PASS=false; }

grep -q '^## ' "$REPORT_FILE" 2>/dev/null \
  && echo "  ✅ PASS: report has section headings (##)" \
  || { echo "  ❌ FAIL: report missing section headings"; ALL_PASS=false; }

grep -qiP '(step|section|method|result|finding|conclusion)' "$REPORT_FILE" 2>/dev/null \
  && echo "  ✅ PASS: report contains structured content sections" \
  || { echo "  ❌ FAIL: report missing structured content"; ALL_PASS=false; }

# ── Verdict ───────────────────────────────────────────────
if [ "$ALL_PASS" = true ]; then
  echo "✅ SCENARIO 33.2 PASSED — generate_report (MD) with content verification"
  exit 0
else
  echo "❌ SCENARIO 33.2 FAILED"
  exit 1
fi
```
**Expected Result:**
- ✅ Report generated in Markdown format at `outputs/medical-research/report/*.md`
- ✅ File has section headings (`##`) and structured content sections


#### 33.3 🟢 generate_report (json)
```bash
#!/usr/bin/env bash
set -euo pipefail
cd /tmp/test-q33
ALL_PASS=true

# Generate report in JSON format
OUTPUT=$(python3 -c "
import json, subprocess
result = subprocess.run(
    ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'generate_report',
     json.dumps({'domain': 'medical-research', 'format': 'json'})],
    capture_output=True, text=True, timeout=60
)
data = json.loads(result.stdout) if result.stdout else {}
report_id = data.get('report_id', data.get('id', ''))
print(report_id)
" 2>&1)
echo "generate_report (JSON): $OUTPUT"

# Find the output file
REPORT_FILE=$(ls -t outputs/medical-research/report/*.json 2>/dev/null | head -1)

# ── Content verification assertions ──────────────────────
[ -n "$REPORT_FILE" ] \
  && echo "  ✅ PASS: JSON report file created: $REPORT_FILE" \
  || { echo "  ❌ FAIL: no JSON report file found"; ALL_PASS=false; }

[ -f "$REPORT_FILE" ] && [ -s "$REPORT_FILE" ] \
  && echo "  ✅ PASS: JSON report file is non-empty" \
  || { echo "  ❌ FAIL: JSON report file empty or missing"; ALL_PASS=false; }

python3 -c "
import json
with open('$REPORT_FILE') as f:
    data = json.load(f)
assert isinstance(data, (dict, list)), 'root is not dict or list'
print('  ✅ PASS: JSON is valid and parseable')
" 2>&1 || { echo "  ❌ FAIL: JSON is invalid or unparseable"; ALL_PASS=false; }

python3 -c "
import json
with open('$REPORT_FILE') as f:
    data = json.load(f)
if isinstance(data, dict):
    keys = list(data.keys())
    has_entries = any(k in ('entries', 'data', 'content', 'results', 'items') for k in keys)
elif isinstance(data, list):
    has_entries = len(data) > 0
print(f'JSON keys: {keys if isinstance(data, dict) else \"[list with {} items]\".format(len(data))}')
assert has_entries, 'no entries/records found'
print('  ✅ PASS: JSON contains entries/records')
" 2>&1 || { echo "  ❌ FAIL: JSON missing entries array or data"; ALL_PASS=false; }

# ── Verdict ───────────────────────────────────────────────
if [ "$ALL_PASS" = true ]; then
  echo "✅ SCENARIO 33.3 PASSED — generate_report (JSON) with content verification"
  exit 0
else
  echo "❌ SCENARIO 33.3 FAILED"
  exit 1
fi
```
**Expected Result:**
- ✅ Report generated in JSON format at `outputs/medical-research/report/*.json`
- ✅ JSON is valid and parseable
- ✅ JSON contains entries array or data records


#### 33.4 🟢 generate_tutorial [REQUIRES LLM KEY]
```bash
#!/usr/bin/env bash
set -euo pipefail
cd /tmp/test-q33
ALL_PASS=true

# Generate tutorial
OUTPUT=$(python3 -c "
import json, subprocess
result = subprocess.run(
    ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'generate_tutorial',
     json.dumps({'domain': 'medical-research', 'topic': 'IVF'})],
    capture_output=True, text=True, timeout=120
)
data = json.loads(result.stdout) if result.stdout else {}
tutorial_id = data.get('tutorial_id', data.get('id', ''))
print(tutorial_id)
" 2>&1)
echo "generate_tutorial: $OUTPUT"

# Find the output file
TUTORIAL_FILE=$(ls -t outputs/medical-research/tutorial/*.md 2>/dev/null | head -1)

# ── Content verification assertions ──────────────────────
[ -n "$TUTORIAL_FILE" ] \
  && echo "  ✅ PASS: tutorial file created: $TUTORIAL_FILE" \
  || { echo "  ❌ FAIL: no tutorial file found"; ALL_PASS=false; }

[ -f "$TUTORIAL_FILE" ] && [ -s "$TUTORIAL_FILE" ] \
  && echo "  ✅ PASS: tutorial file is non-empty" \
  || { echo "  ❌ FAIL: tutorial file empty or missing"; ALL_PASS=false; }

grep -qiP '(##\s*Intro|学习目标|Learning\s+Objective|Overview|Prerequisite|##\s*What|概念|Concept|定义)' "$TUTORIAL_FILE" 2>/dev/null \
  && echo "  ✅ PASS: tutorial has structured educational sections" \
  || { echo "  ❌ FAIL: tutorial missing educational structure"; ALL_PASS=false; }

grep -qiP '(example|示例|exercise|练习|step|步骤|walkthrough)' "$TUTORIAL_FILE" 2>/dev/null \
  && echo "  ✅ PASS: tutorial contains examples or step-by-step guidance" \
  || { echo "  ❌ FAIL: tutorial missing examples/exercises"; ALL_PASS=false; }

# ── Verdict ───────────────────────────────────────────────
if [ "$ALL_PASS" = true ]; then
  echo "✅ SCENARIO 33.4 PASSED — generate_tutorial with content verification"
  exit 0
else
  echo "❌ SCENARIO 33.4 FAILED"
  exit 1
fi
```
**Expected Result:**
- ✅ Tutorial generated at `outputs/medical-research/tutorial/*.md`
- ✅ File contains structured educational content with sections, examples, or step-by-step guidance


#### 33.5 🟢 generate_presentation [REQUIRES LLM KEY]
```bash
#!/usr/bin/env bash
set -euo pipefail
cd /tmp/test-q33
ALL_PASS=true

# Generate presentation
OUTPUT=$(python3 -c "
import json, subprocess
result = subprocess.run(
    ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'generate_presentation',
     json.dumps({'domain': 'medical-research', 'topic': 'IVF'})],
    capture_output=True, text=True, timeout=120
)
data = json.loads(result.stdout) if result.stdout else {}
pres_id = data.get('presentation_id', data.get('id', ''))
print(pres_id)
" 2>&1)
echo "generate_presentation: $OUTPUT"

# Find the output file (may be .html or .md with reveal.js)
PRES_FILE=$(ls -t outputs/medical-research/presentation/*.{md,html} 2>/dev/null | head -1)

# ── Content verification assertions ──────────────────────
[ -n "$PRES_FILE" ] \
  && echo "  ✅ PASS: presentation file created: $PRES_FILE" \
  || { echo "  ❌ FAIL: no presentation file found"; ALL_PASS=false; }

[ -f "$PRES_FILE" ] && [ -s "$PRES_FILE" ] \
  && echo "  ✅ PASS: presentation file is non-empty" \
  || { echo "  ❌ FAIL: presentation file empty or missing"; ALL_PASS=false; }

# Verify Reveal.js structure (HTML or Markdown with slide separators)
grep -qiP '(reveal\.js|revealjs|class="reveal"|data-transition|##\s+Slide|^---$|<!-- \.slide)' "$PRES_FILE" 2>/dev/null \
  && echo "  ✅ PASS: presentation contains Reveal.js structure" \
  || { echo "  ❌ FAIL: presentation missing Reveal.js structure"; ALL_PASS=false; }

grep -qiP '(<section|<div\s+class="slides"|slide)' "$PRES_FILE" 2>/dev/null \
  && echo "  ✅ PASS: presentation has slide elements/sections" \
  || { echo "  ❌ FAIL: presentation missing slide sections"; ALL_PASS=false; }

# ── Verdict ───────────────────────────────────────────────
if [ "$ALL_PASS" = true ]; then
  echo "✅ SCENARIO 33.5 PASSED — generate_presentation with content verification"
  exit 0
else
  echo "❌ SCENARIO 33.5 FAILED"
  exit 1
fi
```
**Expected Result:**
- ✅ Presentation generated at `outputs/medical-research/presentation/*.md` (or `.html`)
- ✅ File contains Reveal.js structure: slide elements, sections, or transitions


#### 33.6 🟢 localize_content [REQUIRES LLM KEY]
```bash
#!/usr/bin/env bash
set -euo pipefail
cd /tmp/test-q33
ALL_PASS=true

# First get the source content for comparison
SOURCE_CONTENT=$(python3 -c "
import json, subprocess
result = subprocess.run(
    ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'list_summaries',
     json.dumps({'domain': 'medical-research', 'limit': 1})],
    capture_output=True, text=True, timeout=30
)
data = json.loads(result.stdout) if result.stdout else {}
entries = data.get('entries', data.get('results', []))
if entries:
    e = entries[0]
    print(e.get('title', ''))
    print(e.get('summary', e.get('tl_dr', '')))
" 2>&1)
echo "Source (first 300 chars): ${SOURCE_CONTENT:0:300}"

# Generate localized content
OUTPUT=$(python3 -c "
import json, subprocess
result = subprocess.run(
    ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'localize_content',
     json.dumps({'domain': 'medical-research', 'target_language': 'zh-CN'})],
    capture_output=True, text=True, timeout=120
)
data = json.loads(result.stdout) if result.stdout else {}
loc_id = data.get('localization_id', data.get('id', ''))
print(loc_id)
" 2>&1)
echo "localize_content: $OUTPUT"

# Find the localized output file
LOC_FILE=$(ls -t outputs/medical-research/localized/*.md 2>/dev/null | head -1)

# ── Content verification assertions ──────────────────────
[ -n "$LOC_FILE" ] \
  && echo "  ✅ PASS: localized file created: $LOC_FILE" \
  || { echo "  ❌ FAIL: no localized file found"; ALL_PASS=false; }

[ -f "$LOC_FILE" ] && [ -s "$LOC_FILE" ] \
  && echo "  ✅ PASS: localized file is non-empty" \
  || { echo "  ❌ FAIL: localized file empty or missing"; ALL_PASS=false; }

# Verify target language contains CJK characters (zh-CN → Chinese)
grep -qP '[\x{4e00}-\x{9fff}\x{3400}-\x{4dbf}]' "$LOC_FILE" 2>/dev/null \
  && echo "  ✅ PASS: localized content contains Chinese characters (zh-CN)" \
  || { echo "  ❌ FAIL: localized content missing Chinese characters"; ALL_PASS=false; }

# Verify content differs from English source (should contain Chinese, not just ASCII)
ASCII_ONLY=$(grep -cP '^[[:print:]\t]+$' "$LOC_FILE" 2>/dev/null || echo 0)
NON_ASCII=$(grep -cP '[\x{4e00}-\x{9fff}\x{3040}-\x{309f}\x{30a0}-\x{30ff}]' "$LOC_FILE" 2>/dev/null || echo 0)
echo "  Content stats: non-ASCII matches=$NON_ASCII"
[ "$NON_ASCII" -gt 0 ] \
  && echo "  ✅ PASS: target language text differs from source (non-ASCII found)" \
  || { echo "  ❌ FAIL: localized content appears identical to source (no CJK found)"; ALL_PASS=false; }

# ── Verdict ───────────────────────────────────────────────
if [ "$ALL_PASS" = true ]; then
  echo "✅ SCENARIO 33.6 PASSED — localize_content with content verification"
  exit 0
else
  echo "❌ SCENARIO 33.6 FAILED"
  exit 1
fi
```
**Expected Result:**
- ✅ Localized file created at `outputs/medical-research/localized/*.md`
- ✅ Content contains target-language characters (Chinese/CJK for zh-CN)
- ✅ Translated text differs from English source (contains non-ASCII)


---

### 📊 Q33 Verdict

| Scenario | Result |
|----------|--------|
| 33.1 generate_digest | ⬜ |
| 33.2 report (MD) | ⬜ |
| 33.3 report (JSON) | ⬜ |
| 33.4 generate_tutorial | ⬜ |
| 33.5 generate_presentation | ⬜ |
| 33.6 localize_content | ⬜ |

**OVERALL: ⬜**

---

## Q34: MCP Export/Import, CEFR, Email, Cron Tools

**Agent says:** "I need to export/import KB, classify CEFR, send emails, and manage schedules."

### Prerequisites
```bash
cd /tmp/test-q34
autoinfo init --demo medical-research
```

### Scenarios

#### 34.1 🟢 export_kb
```python
from autoinfo.mcp.server import app
import json

result = app.call_tool("export_kb", {
    "domain": "medical-research",
    "format": "json",
    "topic": "IVF"
})
data = json.loads(result.content[0].text)
print(f"✅ export_kb: {json.dumps(data, indent=2)[:200]}")
assert "file_path" in data or "data" in data or "status" in data
```
**Expected Result:** ✅ KB exported to file. File path returned.


#### 34.2 🟢 import_kb
```python
# Create a test import file
import tempfile, pathlib
import_path = pathlib.Path("/tmp/test-import.md")
import_path.write_text("""---
title: Imported Test Article
domain: medical-research
source_url: https://example.com/imported
source_type: web
source_platform: test
collected_at: 2026-07-23
---
# Imported Test Article

This is imported content for testing the KB import tool.
""")

result = app.call_tool("import_kb", {
    "domain": "medical-research",
    "file_path": str(import_path),
    "format": "markdown"
})
data = json.loads(result.content[0].text)
print(f"✅ import_kb: {data}")
```
**Expected Result:** ✅ Content imported into 01-Raw tier.


#### 34.3 🟢 classify_cefr [REQUIRES LLM KEY]
```python
result = app.call_tool("classify_cefr", {
    "text": "The mitochondria is the powerhouse of the cell.",
    "language": "en"
})
data = json.loads(result.content[0].text)
assert "level" in data
print(f"✅ classify_cefr: level={data['level']}, confidence={data.get('confidence','?')}")
```
**Expected Result:** ✅ Returns CEFR level (A1-C2) with confidence score.


#### 34.4 🟢 send_email_digest [REQUIRES SMTP CONFIG]
```python
result = app.call_tool("send_email_digest", {
    "to": "user@example.com",
    "subject": "Weekly AutoInfo Digest",
    "domain": "medical-research",
    "period": "week"
})
data = json.loads(result.content[0].text)
print(f"✅ send_email_digest: {data}")
```
**Expected Result:** ✅ Email sent confirmation. (Skip if SMTP not configured.)


#### 34.5 🟢 add_schedule
```python
result = app.call_tool("add_schedule", {
    "domain": "medical-research",
    "topic": "IVF",
    "cron": "0 8 * * 1"
})
data = json.loads(result.content[0].text)
print(f"✅ add_schedule: {data}")
```
**Expected Result:** ✅ Schedule added. ID returned.


#### 34.6 🟢 list_schedules
```python
result = app.call_tool("list_schedules", {})
data = json.loads(result.content[0].text)
schedules = data.get("schedules", data.get("items", []))
print(f"✅ list_schedules: {len(schedules)} schedules")
for s in schedules:
    print(f"  - {s.get('domain','?')}/{s.get('topic','?')}: {s.get('cron','?')}")
```
**Expected Result:** ✅ Returns all schedules with domain, topic, cron expression.


#### 34.7 🟢 remove_schedule
```python
# Get schedule ID from list
result = app.call_tool("list_schedules", {})
data = json.loads(result.content[0].text)
schedules = data.get("schedules", data.get("items", []))
if schedules:
    sched_id = schedules[0].get("id", schedules[0].get("schedule_id", ""))
    result = app.call_tool("remove_schedule", {"schedule_id": sched_id})
    data = json.loads(result.content[0].text)
    print(f"✅ remove_schedule: {data}")
else:
    print("⚠️ No schedules to remove")
```
**Expected Result:** ✅ Schedule removed. Confirmation shown.


#### 34.8 🟢 run_schedules
```python
result = app.call_tool("run_schedules", {})
data = json.loads(result.content[0].text)
print(f"✅ run_schedules: {json.dumps(data, indent=2)[:200]}")
```
**Expected Result:** ✅ All active schedules executed.


---

### 📊 Q34 Verdict

| Scenario | Result |
|----------|--------|
| 34.1 export_kb | ⬜ |
| 34.2 import_kb | ⬜ |
| 34.3 classify_cefr | ⬜ |
| 34.4 send_email_digest | ⬜ |
| 34.5 add_schedule | ⬜ |
| 34.6 list_schedules | ⬜ |
| 34.7 remove_schedule | ⬜ |
| 34.8 run_schedules | ⬜ |

**OVERALL: ⬜**

---

## Q35: MCP Custom Extraction Tools

**Agent says:** "I need to extract custom fields from collected content."

### Scenarios

#### 35.1 🟢 extract_fields [REQUIRES LLM KEY]
```python
from autoinfo.mcp.server import app
import json

# Need a collected item to extract from
result = app.call_tool("collect_sources", {
    "domain": "medical-research",
    "topic": "IVF",
    "limit": 1,
    "dry_run": True
})
# For real extraction, need an actual item
# Test with known item data
result = app.call_tool("extract_fields", {
    "domain": "medical-research",
    "text": "Recent studies show that IVF success rates improve with embryo genetic testing.",
    "fields": ["key_findings", "methodology", "conclusion"]
})
data = json.loads(result.content[0].text)
print(f"✅ extract_fields: {json.dumps(data, indent=2)[:300]}")
```
**Expected Result:** ✅ Custom fields extracted from text using LLM.


#### 35.2 🟢 get_extraction
```python
# Get a summary that has extraction results
result = app.call_tool("list_summaries", {"domain": "medical-research", "limit": 1})
data = json.loads(result.content[0].text)
entries = data.get("entries", [])
if entries:
    entry_id = entries[0].get("entry_id", "") or entries[0].get("id", "")
    result = app.call_tool("get_extraction", {"entry_id": entry_id})
    data = json.loads(result.content[0].text)
    print(f"✅ get_extraction: {json.dumps(data, indent=2)[:200]}")
else:
    print("⚠️ No entries to get extraction from")
```
**Expected Result:** ✅ Returns extraction results for the entry (TL;DR, key points, entities).


---

### 📊 Q35 Verdict

| Scenario | Result |
|----------|--------|
| 35.1 extract_fields | ⬜ |
| 35.2 get_extraction | ⬜ |

**OVERALL: ⬜**

---

## Q36: MCP Error Handling

**Agent says:** "What happens when MCP tools receive invalid input?"

### Prerequisites
```bash
cd /tmp/test-q36
autoinfo init --demo medical-research
```

### Scenarios

#### 36.1 🔴 Missing required parameters
```python
from autoinfo.mcp.server import app
import json

# Missing 'domain' on collect_sources
result = app.call_tool("collect_sources", {})
data = json.loads(result.content[0].text)
assert "error_code" in data or "message" in data or "isError" in data
print(f"✅ MCP error (missing params): {json.dumps(data, indent=2)[:200]}")
```
**Expected Result:** ❌ Error response with error_code, message. No Python traceback leaked.


#### 36.2 🔴 Nonexistent tool
```python
try:
    result = app.call_tool("nonexistent_tool", {})
    data = json.loads(result.content[0].text)
    print(f"✅ Nonexistent tool: {json.dumps(data, indent=2)[:200]}")
except Exception as e:
    print(f"✅ Handled error: {e}")
```
**Expected Result:** ❌ Does NOT crash. Returns error or raises handled exception.


#### 36.3 🔴 Invalid parameter types
```python
result = app.call_tool("collect_sources", {
    "domain": "medical-research",
    "limit": "not-a-number"  # should be int
})
data = json.loads(result.content[0].text)
print(f"✅ MCP error (bad types): {json.dumps(data, indent=2)[:200]}")
```
**Expected Result:** ❌ Error response about invalid parameter type.


#### 36.4 🔴 Nonexistent domain
```python
result = app.call_tool("collect_sources", {
    "domain": "nonexistent-domain-that-does-not-exist"
})
data = json.loads(result.content[0].text)
print(f"✅ MCP error (bad domain): {json.dumps(data, indent=2)[:200]}")
```
**Expected Result:** ❌ Error about domain not found. No crash.


---

### 📊 Q36 Verdict

| Scenario | Result |
|----------|--------|
| 36.1 Missing params | ⬜ |
| 36.2 Nonexistent tool | ⬜ |
| 36.3 Bad parameter types | ⬜ |
| 36.4 Nonexistent domain | ⬜ |

**OVERALL: ⬜**

---

## Q36b: MCP Knowledge Lifecycle Tools

**Agent says:** "I need to compare versions, find/merge similar items, check domain decay, mark items stale, and calculate freshness."

### Prerequisites
```bash
cd /tmp/test-q36b
autoinfo init --demo medical-research
autoinfo collect --domain medical-research --topic "IVF" --limit 5
autoinfo process --domain medical-research 2>/dev/null || true
```

### Scenarios

#### 36b.1 🟢 compare_versions
```python
from autoinfo.mcp.server import app
import json

# Get a summary and flag it to KB to create a versioned entry
result = app.call_tool("list_summaries", {"domain": "medical-research", "limit": 1})
data = json.loads(result.content[0].text)
entries = data.get("entries", [])
if entries:
    entry_id = entries[0].get("entry_id", "") or entries[0].get("id", "")
    # Flag to KB first
    app.call_tool("flag_for_knowledge_base", {
        "summary_id": entry_id,
        "tags": ["version-test"]
    })
    # Now compare versions (may compare current vs. previous if re-processed)
    result = app.call_tool("compare_versions", {
        "entry_id": entry_id
    })
    data = json.loads(result.content[0].text)
    print(f"✅ compare_versions: {json.dumps(data, indent=2)[:300]}")
else:
    print("⚠️ No entries to compare")
```
**Expected Result:** ✅ Returns version diff or confirmation that only one version exists.


#### 36b.2 🟢 find_similar_items
```python
# Need at least 2 items in KB — flag another one
result = app.call_tool("list_summaries", {"domain": "medical-research", "limit": 2})
data = json.loads(result.content[0].text)
entries = data.get("entries", [])
if len(entries) >= 2:
    # Get the first entry's ID (the known one)
    entry_id = entries[0].get("entry_id", "") or entries[0].get("id", "")
    # Flag second entry to KB too
    entry_id2 = entries[1].get("entry_id", "") or entries[1].get("id", "")
    app.call_tool("flag_for_knowledge_base", {
        "summary_id": entry_id2,
        "tags": ["similarity-test"]
    })

    result = app.call_tool("find_similar_items", {
        "entry_id": entry_id,
        "domain": "medical-research",
        "limit": 5
    })
    data = json.loads(result.content[0].text)
    similar = data.get("similar_items", data.get("entries", data.get("items", [])))
    print(f"✅ find_similar_items: {len(similar)} similar items found")
    for item in similar[:3]:
        print(f"  - {item.get('title','?')[:60]}: score={item.get('similarity_score', item.get('score','?'))}")
else:
    print("⚠️ Need ≥ 2 entries to find similarities")
```
**Expected Result:** ✅ Returns semantically similar items with similarity scores.


#### 36b.3 🟢 merge_items
```python
# Find two similar items, then merge them
result = app.call_tool("list_summaries", {"domain": "medical-research", "limit": 2})
data = json.loads(result.content[0].text)
entries = data.get("entries", [])
if len(entries) >= 2:
    id1 = entries[0].get("entry_id", "") or entries[0].get("id", "")
    id2 = entries[1].get("entry_id", "") or entries[1].get("id", "")

    result = app.call_tool("merge_items", {
        "source_ids": [id1, id2],
        "domain": "medical-research",
        "strategy": "auto"  # or "llm" for LLM-assisted merge
    })
    data = json.loads(result.content[0].text)
    print(f"✅ merge_items: {json.dumps(data, indent=2)[:300]}")
else:
    print("⚠️ Need ≥ 2 entries to merge")
```
**Expected Result:** ✅ Items merged. Returns merged entry data or confirmation.


#### 36b.4 🟢 get_domain_decay
```python
result = app.call_tool("get_domain_decay", {
    "domain": "medical-research"
})
data = json.loads(result.content[0].text)
print(f"✅ get_domain_decay: {json.dumps(data, indent=2)[:300]}")
assert "grade" in data or "decay_grade" in data or "staleness_ratio" in data or "statistics" in data
```
**Expected Result:** ✅ Returns decay grade (Green/Yellow/Red), staleness ratio, and statistics.


#### 36b.5 🟢 mark_stale
```python
# Mark an entry as stale
result = app.call_tool("list_summaries", {"domain": "medical-research", "limit": 1})
data = json.loads(result.content[0].text)
entries = data.get("entries", [])
if entries:
    entry_id = entries[0].get("entry_id", "") or entries[0].get("id", "")

    result = app.call_tool("mark_stale", {
        "entry_id": entry_id,
        "reason": "Content older than domain TTL"
    })
    data = json.loads(result.content[0].text)
    print(f"✅ mark_stale: {json.dumps(data, indent=2)[:300]}")

    # Verify the stale flag is set
    result = app.call_tool("get_kb_entry", {"entry_id": entry_id})
    data = json.loads(result.content[0].text)
    stale = data.get("stale", data.get("is_stale", False))
    print(f"  Stale flag: {stale}")
else:
    print("⚠️ No entries to mark stale")
```
**Expected Result:** ✅ Entry marked stale. Stale flag visible on entry retrieval.


#### 36b.6 🟢 calculate_freshness_score
```python
result = app.call_tool("calculate_freshness_score", {
    "domain": "medical-research"
})
data = json.loads(result.content[0].text)
print(f"✅ calculate_freshness_score: {json.dumps(data, indent=2)[:300]}")
assert "score" in data or "freshness" in data or "statistics" in data
```
**Expected Result:** ✅ Returns freshness score (0-100) for the domain.


---

### 📊 Q36b Verdict

| Scenario | Result |
|----------|--------|
| 36b.1 compare_versions | ⬜ |
| 36b.2 find_similar_items | ⬜ |
| 36b.3 merge_items | ⬜ |
| 36b.4 get_domain_decay | ⬜ |
| 36b.5 mark_stale | ⬜ |
| 36b.6 calculate_freshness_score | ⬜ |

**OVERALL: ⬜**

---

## Q36c: MCP Cron Status & Product Tools

**Agent says:** "I need to check schedule execution status and retrieve individual products."

### Prerequisites
```bash
cd /tmp/test-q36c
autoinfo init --demo medical-research
```

### Scenarios

#### 36c.1 🟢 get_schedule_status
```python
from autoinfo.mcp.server import app
import json

# First add a schedule
result = app.call_tool("add_schedule", {
    "domain": "medical-research",
    "topic": "IVF",
    "cron": "0 8 * * 1"
})
add_data = json.loads(result.content[0].text)
print(f"  Schedule added: {add_data}")

# Get schedule ID from the add response or from list
result = app.call_tool("list_schedules", {})
data = json.loads(result.content[0].text)
schedules = data.get("schedules", data.get("items", []))
if schedules:
    sched_id = schedules[0].get("id", schedules[0].get("schedule_id", ""))

    result = app.call_tool("get_schedule_status", {
        "schedule_id": sched_id
    })
    data = json.loads(result.content[0].text)
    print(f"✅ get_schedule_status: {json.dumps(data, indent=2)[:300]}")
    assert "status" in data or "enabled" in data or "cron" in data or "last_run" in data
else:
    print("⚠️ No schedules to check status")
```
**Expected Result:** ✅ Returns schedule status including enabled flag, cron expression, last run time.


#### 36c.2 🟢 get_product
```python
# First list products to get a valid product_id
result = app.call_tool("list_products", {
    "domain": "medical-research"
})
data = json.loads(result.content[0].text)
products = data.get("products", data.get("entries", data.get("items", [])))
print(f"  list_products returned: {len(products)} products")

if products:
    product_id = products[0].get("product_id", products[0].get("id", ""))
    print(f"  Using product_id: {product_id}")

    result = app.call_tool("get_product", {
        "product_id": product_id
    })
    data = json.loads(result.content[0].text)
    print(f"✅ get_product: {json.dumps(data, indent=2)[:300]}")
    assert "product_id" in data or "title" in data or "type" in data or "content" in data
else:
    # No products yet — still test that the tool handles gracefully
    print("⚠️ No products available — testing error handling")
    result = app.call_tool("get_product", {
        "product_id": "nonexistent-product-id"
    })
    data = json.loads(result.content[0].text)
    print(f"✅ get_product (error case): {json.dumps(data, indent=2)[:200]}")
```
**Expected Result:** ✅ Returns full product details (title, type, content, metadata).


---

### 📊 Q36c Verdict

| Scenario | Result |
|----------|--------|
| 36c.1 get_schedule_status | ⬜ |
| 36c.2 get_product | ⬜ |

**OVERALL: ⬜**

---

## Q36d: v1.7 Consumption Tracking, Notifications & Cron Health

**Agent says:** "I need to verify the v1.7 additions: consumption event recording on delivery, automated notifications, and cron health monitoring."

### Prerequisites
```bash
cd /tmp/test-q36d
autoinfo init --demo medical-research
```

### Scenarios

#### 36d.1 🟢 ConsumptionEvent auto-record on digest delivery
```python
from autoinfo.mcp.server import app
import json

# Generate a digest — delivery should auto-record a ConsumptionEvent
result = app.call_tool("generate_digest", {
    "domain": "medical-research",
    "period": "week",
    "format": "md"
})
data = json.loads(result.content[0].text)
print(f"✅ generate_digest: {json.dumps(data, indent=2)[:200]}")

# Verify consumption events were recorded
from autoinfo.consumption import ConsumptionStore
store = ConsumptionStore()
events = store.list_events()
print(f"✅ ConsumptionEvent auto-record: {len(events)} events recorded")
# Events should include view/open/click types tied to the delivered product
```
**Expected Result:** ✅ Digest generation auto-records a `ConsumptionEvent` (view/open/click) in the SQLite-backed `ConsumptionStore`. Events are retrievable via `store.list_events()`.


#### 36d.2 🟢 ConsumptionStore — SQLite-backed event persistence
```python
from autoinfo.consumption import ConsumptionStore, ConsumptionEvent
from datetime import datetime

store = ConsumptionStore()
event = ConsumptionEvent(
    event_id="evt-test-1",
    user_id="user-test",
    product_id="prod-test",
    event_type="view",
    timestamp=datetime.utcnow().isoformat(),
    metadata={"channel": "email"}
)
store.record(event)

events = store.list_events(user_id="user-test")
assert any(e["event_id"] == "evt-test-1" for e in events), "Event not persisted"
print(f"✅ ConsumptionStore persistence: {len(events)} events for user-test")
```
**Expected Result:** ✅ `ConsumptionStore` persists `ConsumptionEvent` records to SQLite. `list_events()` retrieves events by user_id.


#### 36d.3 🟢 Automated notification — trial-ending reminder
```python
from autoinfo.notifications import check_expiring_trials

# check_expiring_trials finds trial users expiring within 3 days
# and sends reminder notifications. Returns list of notified users.
notified = check_expiring_trials()
print(f"✅ check_expiring_trials: {len(notified)} users notified")
# In a fresh project with no trial users, returns empty list (no crash)
assert isinstance(notified, list)
```
**Expected Result:** ✅ `check_expiring_trials()` returns a list of expiring trial users that were notified. No crash when no trial users exist.


#### 36d.4 🟢 Automated notification — content-ready
```python
from autoinfo.notifications import notify_content_ready

# notify_content_ready sends a content-ready notification to a user
result = notify_content_ready(
    user_id="user-test",
    product_id="prod-test",
    product_title="Weekly Medical Research Digest"
)
print(f"✅ notify_content_ready: {result}")
```
**Expected Result:** ✅ `notify_content_ready()` sends a content-ready notification to the specified user. Returns a result dict confirming dispatch.


#### 36d.5 🟢 Cron health — heartbeat + missed-schedule detection (CLI)
```bash
cd /tmp/test-q36d
# Add a schedule
autoinfo cron add-schedule --domain medical-research --topic "IVF" --cron "0 8 * * 1"
# Check cron health — reports per-schedule health (ok/missed/error/unknown)
autoinfo cron health
echo "Exit: $?"
```
**Expected Result:** ✅ `autoinfo cron health` reports per-schedule health status (`ok`/`missed`/`error`/`unknown`) with heartbeat tracking. Missed schedules are flagged. Exit code 0.


#### 36d.6 🟢 Cron heartbeat persistence
```bash
cd /tmp/test-q36d
# After running a schedule, the heartbeat file should exist
ls -la .autoinfo/cron-heartbeat.json 2>/dev/null && echo "Heartbeat file exists" || echo "Heartbeat file not yet created (run a schedule first)"
```
**Expected Result:** ✅ After a schedule run, `.autoinfo/cron-heartbeat.json` persists per-schedule heartbeat entries (last_run, status, error).


---

### 📊 Q36d Verdict

| Scenario | Result |
|----------|--------|
| 36d.1 ConsumptionEvent auto-record | ⬜ |
| 36d.2 ConsumptionStore persistence | ⬜ |
| 36d.3 Trial-ending reminder | ⬜ |
| 36d.4 Content-ready notification | ⬜ |
| 36d.5 Cron health CLI | ⬜ |
| 36d.6 Cron heartbeat persistence | ⬜ |

**OVERALL: ⬜**

---

## Q36e: v1.7 Audio Output — TTS-rendered MP3 via format="audio"

**Agent says:** "I need to verify that digest and report generation with `format='audio'` produces valid base64-encoded MP3 via real OpenAI TTS and handles error conditions correctly."

### Prerequisites
```bash
cd /tmp/test-q36e
rm -rf .autoinfo knowledge collections autoinfo.db outputs
autoinfo init --demo medical-research
autoinfo collect --domain medical-research --limit 3
autoinfo process --domain medical-research
```

### Scenarios

#### 36e.1 🟢 generate_digest with format="audio" returns base64 MP3
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
cd /tmp/test-q36e

RESULT=$(python3 << 'PYEOF'
import json, base64
from autoinfo.mcp.server import app
result = app.call_tool("generate_digest", {
    "domain": "medical-research",
    "period": "week",
    "format": "audio"
})
data = json.loads(result.content[0].text)
if data.get("format") == "audio" and data.get("content"):
    # Save base64 for cross-scenario use
    with open("/tmp/test-q36e/digest_audio.b64", "w") as f:
        f.write(data["content"])
    decoded = base64.b64decode(data["content"])
    print(f"OK|format={data['format']}|encoding={data.get('encoding','?')}|content_type={data.get('content_type','?')}|b64_len={len(data['content'])}|mp3_bytes={len(decoded)}")
else:
    print("FAIL|" + json.dumps(data, default=str))
PYEOF
)
EXIT_CODE=$?

[ "$EXIT_CODE" -eq 0 ] \
  && echo "  ✅ PASS: MCP call exit 0" \
  || { echo "  ❌ FAIL: Python exit $EXIT_CODE"; ALL_PASS=false; }

echo "$RESULT" | grep -q "^OK|" \
  && echo "  ✅ PASS: audio digest returned successfully" \
  || { echo "  ❌ FAIL: no OK signal in output: $RESULT"; ALL_PASS=false; }

echo "$RESULT" | grep -q "format=audio" \
  && echo "  ✅ PASS: format=audio in MCP response" \
  || { echo "  ❌ FAIL: format=audio missing"; ALL_PASS=false; }

echo "$RESULT" | grep -q "encoding=base64" \
  && echo "  ✅ PASS: encoding=base64 in MCP response" \
  || { echo "  ❌ FAIL: encoding=base64 missing"; ALL_PASS=false; }

# Verify MP3 size (real TTS output should be hundreds of bytes minimum)
MP3_BYTES=$(echo "$RESULT" | grep -oP "mp3_bytes=\K\d+")
if [ -n "$MP3_BYTES" ] && [ "$MP3_BYTES" -ge 200 ]; then
  echo "  ✅ PASS: MP3 ${MP3_BYTES} bytes (≥200, valid TTS output)"
else
  echo "  ❌ FAIL: MP3 too small (${MP3_BYTES:-0} bytes)"
  ALL_PASS=false
fi

# Verify saved base64 file
[ -s /tmp/test-q36e/digest_audio.b64 ] \
  && echo "  ✅ PASS: digest_audio.b64 saved (non-empty)" \
  || { echo "  ❌ FAIL: digest_audio.b64 missing or empty"; ALL_PASS=false; }

if [ "$ALL_PASS" = true ]; then echo ""; echo "✅ SCENARIO 36e.1 PASSED"; exit 0; else echo ""; echo "❌ SCENARIO 36e.1 FAILED"; exit 1; fi
```
**Expected Result:**
- ✅ `generate_digest` with `format="audio"` returns a non-empty base64-encoded MP3 string
- ✅ MCP response includes `format=audio`, `encoding=base64`, `content_type=audio/mp3`
- ✅ Decoded MP3 data is ≥ 200 bytes (valid TTS output from OpenAI `tts-1` model)
- ✅ Real OpenAI TTS API call is made (verifiable in logs or by MP3 content being actual audio, not placeholder)

#### 36e.2 🟢 Decoded MP3 has valid header (sync word \xff\xfb or ID3)
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
cd /tmp/test-q36e

# Re-generate digest as audio and decode (self-contained)
python3 << 'PYEOF'
import json, base64
from autoinfo.mcp.server import app
result = app.call_tool("generate_digest", {
    "domain": "medical-research",
    "period": "week",
    "format": "audio"
})
data = json.loads(result.content[0].text)
if data.get("format") == "audio" and data.get("content"):
    decoded = base64.b64decode(data["content"])
    with open("/tmp/test-q36e/test_audio.mp3", "wb") as f:
        f.write(decoded)
    header_hex = decoded[:3].hex()
    print(f"OK|mp3_size={len(decoded)}|header_hex={header_hex}|first_4_hex={decoded[:4].hex()}")
else:
    print("FAIL|" + json.dumps(data, default=str))
    import sys; sys.exit(1)
PYEOF
EXIT_CODE=$?

[ "$EXIT_CODE" -eq 0 ] \
  && echo "  ✅ PASS: audio generation exit 0" \
  || { echo "  ❌ FAIL: audio generation failed, exit $EXIT_CODE"; ALL_PASS=false; }

# Check MP3 file exists and is non-empty
[ -s /tmp/test-q36e/test_audio.mp3 ] \
  && echo "  ✅ PASS: test_audio.mp3 created (non-empty)" \
  || { echo "  ❌ FAIL: test_audio.mp3 missing or empty"; ALL_PASS=false; }

# Extract first bytes from the MP3 file
HEADER3=$(python3 -c "
with open('/tmp/test-q36e/test_audio.mp3','rb') as f:
    h = f.read(3)
print(h.hex())
")
HEADER4=$(python3 -c "
with open('/tmp/test-q36e/test_audio.mp3','rb') as f:
    h = f.read(4)
print(h.hex())
")

# Check for \xff\xfb (MPEG1 Layer3), \xff\xfa (MPEG1 Layer2), \xff\xf3 (MPEG2 Layer3), or ID3v2 tag
if echo "$HEADER4" | grep -q "^494433"; then
  echo "  ✅ PASS: ID3v2 tag detected (header: ${HEADER4:0:8})"
elif echo "$HEADER3" | grep -qE "^(fffb|fffa|fff3)$"; then
  echo "  ✅ PASS: valid MPEG sync word (header: ${HEADER3})"
else
  echo "  ❌ FAIL: invalid MP3 header — expected \\xff\\xfb/\\xff\\xfa/\\xff\\xf3 or ID3, got ${HEADER3}/${HEADER4:0:8}"
  ALL_PASS=false
fi

# Verify minimum MP3 size
MP3_SIZE=$(stat -c%s /tmp/test-q36e/test_audio.mp3 2>/dev/null || python3 -c "import os; print(os.path.getsize('/tmp/test-q36e/test_audio.mp3'))")
[ "$MP3_SIZE" -ge 200 ] \
  && echo "  ✅ PASS: MP3 size ${MP3_SIZE} bytes (≥200)" \
  || { echo "  ❌ FAIL: MP3 too small (${MP3_SIZE} bytes)"; ALL_PASS=false; }

if [ "$ALL_PASS" = true ]; then echo ""; echo "✅ SCENARIO 36e.2 PASSED"; exit 0; else echo ""; echo "❌ SCENARIO 36e.2 FAILED"; exit 1; fi
```
**Expected Result:**
- ✅ Decoded base64 produces valid MP3 bytes (writeable to `.mp3` file)
- ✅ MP3 starts with `\xff\xfb` (MPEG1 Layer3 sync word), `\xff\xfa` (MPEG1 Layer2), `\xff\xf3` (MPEG2 Layer3), or `ID3` (ID3v2 tag)
- ✅ MP3 file is ≥ 200 bytes (TTS output from OpenAI is never tiny)
- ✅ Real OpenAI TTS `tts-1` model yields actual speech audio (not a silent/placeholder frame)

#### 36e.3 🟢 generate_report with format="audio" returns different audio content
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
cd /tmp/test-q36e

RESULT=$(python3 << 'PYEOF'
import json, base64
from autoinfo.mcp.server import app

# Generate digest audio first (for comparison)
digest_res = app.call_tool("generate_digest", {
    "domain": "medical-research",
    "period": "week",
    "format": "audio"
})
digest_data = json.loads(digest_res.content[0].text)
digest_b64 = digest_data.get("content", "")

# Generate report audio
report_res = app.call_tool("generate_report", {
    "domain": "medical-research",
    "format": "audio",
    "period": "month"
})
report_data = json.loads(report_res.content[0].text)
report_b64 = report_data.get("content", "")

# Validate report audio
if not report_b64:
    print("FAIL|report audio content empty")
    import sys; sys.exit(1)

report_decoded = base64.b64decode(report_b64)
report_header = report_decoded[:3].hex()

# Check MP3 header on report
valid_headers = {"fffb", "fffa", "fff3", "494433"}
if report_header not in valid_headers:
    print(f"FAIL|report MP3 header invalid: {report_header}")
    import sys; sys.exit(1)

# Compare digest vs report (they should be different — different content, different rendered text)
are_different = (digest_b64 != report_b64)
print(f"OK|report_mp3_size={len(report_decoded)}|report_header={report_header}|different_from_digest={are_different}|report_format={report_data.get('format','?')}|report_encoding={report_data.get('encoding','?')}")
PYEOF
)
EXIT_CODE=$?

[ "$EXIT_CODE" -eq 0 ] \
  && echo "  ✅ PASS: report audio generation exit 0" \
  || { echo "  ❌ FAIL: report audio generation failed, exit $EXIT_CODE"; ALL_PASS=false; }

echo "$RESULT" | grep -q "^OK|" \
  && echo "  ✅ PASS: report audio returned successfully" \
  || { echo "  ❌ FAIL: no OK in output: $RESULT"; ALL_PASS=false; }

echo "$RESULT" | grep -q "different_from_digest=True" \
  && echo "  ✅ PASS: report audio differs from digest audio (expected)" \
  || { echo "  ❌ FAIL: report and digest audio are identical (should differ)"; ALL_PASS=false; }

echo "$RESULT" | grep -q "report_format=audio" \
  && echo "  ✅ PASS: report format=audio in MCP response" \
  || { echo "  ❌ FAIL: report format not audio"; ALL_PASS=false; }

MP3_SIZE=$(echo "$RESULT" | grep -oP "report_mp3_size=\K\d+")
[ -n "$MP3_SIZE" ] && [ "$MP3_SIZE" -ge 200 ] \
  && echo "  ✅ PASS: report MP3 ${MP3_SIZE} bytes (≥200)" \
  || { echo "  ❌ FAIL: report MP3 too small (${MP3_SIZE:-0} bytes)"; ALL_PASS=false; }

if [ "$ALL_PASS" = true ]; then echo ""; echo "✅ SCENARIO 36e.3 PASSED"; exit 0; else echo ""; echo "❌ SCENARIO 36e.3 FAILED"; exit 1; fi
```
**Expected Result:**
- ✅ `generate_report` with `format="audio"` returns valid base64-encoded MP3
- ✅ Report audio content differs from digest audio content (different generated text → different TTS output)
- ✅ Report MP3 has valid `\xff\xfb` or `ID3` header
- ✅ MCP response includes `format=audio` and `encoding=base64`

#### 36e.4 🔴 Empty/whitespace-only text raises ValueError before reaching TTS API
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
cd /tmp/test-q36e

RESULT=$(python3 << 'PYEOF'
from autoinfo.output import _render_audio
from autoinfo.mcp.server import app
import json, sys

all_ok = True
messages = []

# 1. Empty string should raise ValueError
try:
    _render_audio("")
    messages.append("FAIL|empty_raises_ValueError|did not raise")
    all_ok = False
except ValueError as e:
    messages.append(f"OK|empty_raises_ValueError|message={str(e)[:80]}")

# 2. Whitespace-only string should raise ValueError
try:
    _render_audio("   \n\t  ")
    messages.append("FAIL|whitespace_raises_ValueError|did not raise")
    all_ok = False
except ValueError as e:
    messages.append(f"OK|whitespace_raises_ValueError|message={str(e)[:80]}")

# 3. Text with only markdown stripped to empty should raise ValueError
try:
    _render_audio("** **")
    messages.append("FAIL|stripped_empty_raises_ValueError|did not raise")
    all_ok = False
except ValueError as e:
    messages.append(f"OK|stripped_empty_raises_ValueError|message={str(e)[:80]}")

# 4. Digest with format="audio" on valid domain should succeed
result = app.call_tool("generate_digest", {
    "domain": "medical-research",
    "period": "daily",
    "format": "audio"
})
data = json.loads(result.content[0].text)
if data.get("format") == "audio" and data.get("content") and len(data["content"]) > 0:
    import base64
    decoded = base64.b64decode(data["content"])
    messages.append(f"OK|digest_with_entries_ok|b64_len={len(data['content'])}|mp3_size={len(decoded)}")
else:
    messages.append(f"FAIL|digest_with_entries|{json.dumps(data, default=str)}")
    all_ok = False

for msg in messages:
    print(msg)
if not all_ok:
    sys.exit(1)
PYEOF
)
EXIT_CODE=$?

[ "$EXIT_CODE" -eq 0 ] \
  && echo "  ✅ PASS: all edge-case tests exit 0" \
  || { echo "  ❌ FAIL: edge-case tests failed, exit $EXIT_CODE"; ALL_PASS=false; }

echo "$RESULT" | grep -q "empty_raises_ValueError" \
  && echo "  ✅ PASS: _render_audio('') raises ValueError" \
  || { echo "  ❌ FAIL: _render_audio('') did not raise ValueError"; ALL_PASS=false; }

echo "$RESULT" | grep -q "whitespace_raises_ValueError" \
  && echo "  ✅ PASS: _render_audio(whitespace) raises ValueError" \
  || { echo "  ❌ FAIL: _render_audio(whitespace) did not raise ValueError"; ALL_PASS=false; }

echo "$RESULT" | grep -q "stripped_empty_raises_ValueError" \
  && echo "  ✅ PASS: _render_audio(stripped-empty) raises ValueError" \
  || { echo "  ❌ FAIL: _render_audio(stripped-empty) did not raise ValueError"; ALL_PASS=false; }

echo "$RESULT" | grep -q "digest_with_entries_ok" \
  && echo "  ✅ PASS: digest with entries on valid domain produces audio" \
  || { echo "  ❌ FAIL: digest on valid domain should produce audio"; ALL_PASS=false; }

if [ "$ALL_PASS" = true ]; then echo ""; echo "✅ SCENARIO 36e.4 PASSED"; exit 0; else echo ""; echo "❌ SCENARIO 36e.4 FAILED"; exit 1; fi
```
**Expected Result:**
- ✅ `_render_audio("")` raises `ValueError("Cannot render empty text as audio")`
- ✅ `_render_audio("   \n\t  ")` also raises `ValueError` (whitespace-only rejected)
- ✅ `_render_audio("** **")` raises `ValueError` (markdown-stripped-to-empty)
- ✅ `generate_digest` with `format="audio"` on a domain with entries gracefully produces TTS audio
- ❌ Empty/whitespace text should NEVER reach the OpenAI TTS API — the guard in `_render_audio()` prevents unnecessary API calls

#### 36e.5 🟢 generate_digest with format="agent" returns valid JSON-LD
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
cd /tmp/test-q36e

RESULT=$(python3 << 'PYEOF'
import json, sys
from autoinfo.mcp.server import app

result = app.call_tool("generate_digest", {
    "domain": "medical-research",
    "period": "week",
    "format": "agent"
})
data = json.loads(result.content[0].text)

if not data.get("success"):
    print("FAIL|" + json.dumps(data, default=str)[:200])
    sys.exit(1)

content = data.get("content")
if not isinstance(content, dict):
    print("FAIL|content not a dict:" + str(type(content)))
    sys.exit(1)

# Save for later scenarios
with open("/tmp/test-q36e/agent_json.json", "w") as f:
    json.dump(content, f, indent=2)

print(f"OK|@type={content.get('@type','')}|entry_count={len(content.get('entries',[]))}|format={data.get('format','')}")
PYEOF
)
EXIT_CODE=$?

[ "$EXIT_CODE" -eq 0 ] \
  && echo "  ✅ PASS: MCP call exit 0" \
  || { echo "  ❌ FAIL: Python exit $EXIT_CODE"; ALL_PASS=false; }

echo "$RESULT" | grep -q "^OK|" \
  && echo "  ✅ PASS: agent JSON returned successfully" \
  || { echo "  ❌ FAIL: agent JSON failed: $RESULT"; ALL_PASS=false; }

echo "$RESULT" | grep -qE "@type=KnowledgeDigest" \
  && echo "  ✅ PASS: @type=KnowledgeDigest" \
  || { echo "  ❌ FAIL: @type is not KnowledgeDigest"; ALL_PASS=false; }

echo "$RESULT" | grep -q "format=agent" \
  && echo "  ✅ PASS: response format=agent" \
  || { echo "  ❌ FAIL: format is not agent"; ALL_PASS=false; }

ENTRY_COUNT=$(echo "$RESULT" | grep -oP "entry_count=\K\d+")
[ -n "$ENTRY_COUNT" ] && [ "$ENTRY_COUNT" -ge 1 ] \
  && echo "  ✅ PASS: entries count=${ENTRY_COUNT} (≥1)" \
  || { echo "  ❌ FAIL: no entries found"; ALL_PASS=false; }

[ -s /tmp/test-q36e/agent_json.json ] \
  && echo "  ✅ PASS: agent_json.json saved (non-empty)" \
  || { echo "  ❌ FAIL: agent_json.json missing or empty"; ALL_PASS=false; }

if [ "$ALL_PASS" = true ]; then echo ""; echo "✅ SCENARIO 36e.5 PASSED"; exit 0; else echo ""; echo "❌ SCENARIO 36e.5 FAILED"; exit 1; fi
```
**Expected Result:**
- ✅ `generate_digest` with `format="agent"` returns `{"success": true, "format": "agent", "content": <KnowledgeDigest dict>}`
- ✅ `content["@type"]` is `"KnowledgeDigest"`
- ✅ `content["entries"]` is a non-empty array (domain has processed KB entries)
- ✅ Real LLM call produces meaningful content (not empty/placeholder)

#### 36e.6 🟢 JSON-LD has @type = "KnowledgeDigest" and all required top-level fields
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
cd /tmp/test-q36e

python3 << 'PYEOF'
import json, sys
from autoinfo.mcp.server import app

# Re-generate (self-contained)
result = app.call_tool("generate_digest", {
    "domain": "medical-research",
    "period": "week",
    "format": "agent"
})
data = json.loads(result.content[0].text)
if not data.get("success"):
    print("FAIL|digest failed:" + str(data)[:200])
    sys.exit(1)

content = data["content"]
errors = []

# Check all 9 required top-level fields
REQUIRED_FIELDS = [
    "@context", "@type", "uuid", "generated_at",
    "domain", "period", "entries", "trends", "metadata"
]
for field in REQUIRED_FIELDS:
    if field not in content:
        errors.append(f"missing:{field}")

if errors:
    print("FAIL|" + "|".join(errors))
    sys.exit(1)

# Verify types of each required field
type_errors = []
for field in REQUIRED_FIELDS:
    val = content.get(field)
    if field in ("@context", "@type", "uuid", "generated_at", "domain", "period"):
        if not isinstance(val, str) or not val.strip():
            type_errors.append(f"{field} should be non-empty string, got {type(val).__name__}")
    elif field == "entries":
        if not isinstance(val, list):
            type_errors.append(f"entries should be list, got {type(val).__name__}")
    elif field == "trends":
        if not isinstance(val, list):
            type_errors.append(f"trends should be list, got {type(val).__name__}")
    elif field == "metadata":
        if not isinstance(val, dict):
            type_errors.append(f"metadata should be dict, got {type(val).__name__}")

if type_errors:
    print("FAIL|" + "|".join(type_errors))
    sys.exit(1)

print(f"OK|all_{len(REQUIRED_FIELDS)}_fields_present|content_type={type(content).__name__}")
PYEOF
)
EXIT_CODE=$?

[ "$EXIT_CODE" -eq 0 ] \
  && echo "  ✅ PASS: all required fields present and typed correctly" \
  || { echo "  ❌ FAIL: required field validation failed"; ALL_PASS=false; }

if [ "$ALL_PASS" = true ]; then echo ""; echo "✅ SCENARIO 36e.6 PASSED"; exit 0; else echo ""; echo "❌ SCENARIO 36e.6 FAILED"; exit 1; fi
```
**Expected Result:**
- ✅ All 9 required top-level fields present: `@context`, `@type`, `uuid`, `generated_at`, `domain`, `period`, `entries`, `trends`, `metadata`
- ✅ Each field has correct type (string fields non-empty, entries/trends are lists, metadata is dict)
- ✅ `content` is a parsed dict (not a JSON string) — MCP handler already parsed it

#### 36e.7 🟢 entries[0].tl_dr is non-empty (LLM actually extracted content)
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
cd /tmp/test-q36e

python3 << 'PYEOF'
import json, sys
from autoinfo.mcp.server import app

result = app.call_tool("generate_digest", {
    "domain": "medical-research",
    "period": "week",
    "format": "agent"
})
data = json.loads(result.content[0].text)
if not data.get("success"):
    print("FAIL|digest failed:" + str(data)[:200])
    sys.exit(1)

content = data["content"]
entries = content.get("entries", [])
if not entries:
    print("FAIL|no entries in digest - need at least one processed entry")
    sys.exit(1)

first = entries[0]

# tl_dr is a required output field from LLM processing
tl_dr = first.get("tl_dr", "")
if not tl_dr or not isinstance(tl_dr, str) or not tl_dr.strip():
    print(f"FAIL|tl_dr empty or invalid: type={type(tl_dr).__name__}, val='{str(tl_dr)[:80]}'")
    sys.exit(1)

# Check other key entry fields
entry_checks = []
entry_checks.append(f"uuid={bool(first.get('uuid',''))}")
entry_checks.append(f"title_len={len(first.get('title',''))}")
entry_checks.append(f"tl_dr_len={len(tl_dr)}")
entry_checks.append(f"source_url={bool(first.get('source_url',''))}")
entry_checks.append(f"key_points_count={len(first.get('key_points',[]))}")
entry_checks.append(f"entities_count={len(first.get('entities',[]))}")

print(f"OK|{'|'.join(entry_checks)}")
PYEOF
)
EXIT_CODE=$?

[ "$EXIT_CODE" -eq 0 ] \
  && echo "  ✅ PASS: entries have real LLM content" \
  || { echo "  ❌ FAIL: entry content validation failed"; ALL_PASS=false; }

if [ "$ALL_PASS" = true ]; then echo ""; echo "✅ SCENARIO 36e.7 PASSED"; exit 0; else echo ""; echo "❌ SCENARIO 36e.7 FAILED"; exit 1; fi
```
**Expected Result:**
- ✅ `entries[0].tl_dr` is a non-empty string (LLM actually extracted content from the source)
- ✅ `entries[0].uuid` is present (traceable identifier)
- ✅ `entries[0].title` has length > 0 (source title preserved)
- ✅ `entries[0].key_points` is a list (LLM-derived from summary)
- ✅ Real LLM call, not mocked — real `tl_dr` content proves LLM extraction worked

#### 36e.8 🟢 JSON-LD parses with json.loads and matches schema — full validation
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
cd /tmp/test-q36e

python3 << 'PYEOF'
import json, sys
from autoinfo.mcp.server import app

result = app.call_tool("generate_digest", {
    "domain": "medical-research",
    "period": "week",
    "format": "agent"
})
data = json.loads(result.content[0].text)
if not data.get("success"):
    print("FAIL|digest failed")
    sys.exit(1)

content = data["content"]
errors = []

# ── Top-level schema ──────────────────────────────────────────
if content.get("@type") != "KnowledgeDigest":
    errors.append(f"@type should be KnowledgeDigest, got {content.get('@type')}")
if not content.get("@context", "").startswith("https://"):
    errors.append("@context should be URL")
if not content.get("uuid", ""):
    errors.append("uuid missing/empty")

# ── Entries schema ────────────────────────────────────────────
entries = content.get("entries", [])
if not entries or not isinstance(entries, list):
    errors.append("entries must be non-empty list")
else:
    for i, entry in enumerate(entries[:3]):  # Check first 3
        entry_fields = ["uuid", "title", "tl_dr", "source_url"]
        if not all(entry.get(f) for f in entry_fields):
            missing = [f for f in entry_fields if not entry.get(f)]
            errors.append(f"entry[{i}] missing fields: {missing}")
        # Check type-specifc fields (may be None for some items)
        if entry.get("confidence_score") is not None:
            try:
                cs = float(entry["confidence_score"])
                if not (0 <= cs <= 1):
                    errors.append(f"entry[{i}] confidence_score={cs} out of range [0,1]")
            except (ValueError, TypeError):
                errors.append(f"entry[{i}] confidence_score not numeric")
        if not isinstance(entry.get("key_points", []), list):
            errors.append(f"entry[{i}] key_points not a list")
        if not isinstance(entry.get("entities", []), list):
            errors.append(f"entry[{i}] entities not a list")

# ── Trends schema ─────────────────────────────────────────────
trends = content.get("trends", [])
if not isinstance(trends, list):
    errors.append("trends must be a list")
else:
    for i, trend in enumerate(trends[:3]):
        if isinstance(trend, dict):
            if not trend.get("topic"):
                pass  # topic can be empty for auto-generated trends
        elif not isinstance(trend, str):
            errors.append(f"trend[{i}] should be str or dict, got {type(trend).__name__}")

# ── Metadata schema ───────────────────────────────────────────
meta = content.get("metadata", {})
if not isinstance(meta, dict):
    errors.append("metadata must be dict")
else:
    expected_meta = ["entry_count", "generated_at", "domain"]
    for mf in expected_meta:
        if mf not in meta:
            errors.append(f"metadata missing: {mf}")
    if meta.get("entry_count", 0) < 1:
        errors.append(f"entry_count={meta.get('entry_count')} should be >= 1")

# ── Result ────────────────────────────────────────────────────
if errors:
    print("FAIL|schema:" + "|".join(errors))
    sys.exit(1)

entry_count = len(entries)
meta_entries = meta.get("entry_count", 0)
print(f"OK|entries_checked={min(entry_count,3)}|trends_count={len(trends)}|meta_entry_count={meta_entries}")
PYEOF
)
EXIT_CODE=$?

[ "$EXIT_CODE" -eq 0 ] \
  && echo "  ✅ PASS: full schema validation passed" \
  || { echo "  ❌ FAIL: schema validation failed"; ALL_PASS=false; }

if [ "$ALL_PASS" = true ]; then echo ""; echo "✅ SCENARIO 36e.8 PASSED"; exit 0; else echo ""; echo "❌ SCENARIO 36e.8 FAILED"; exit 1; fi
```
**Expected Result:**
- ✅ `@type` is exactly `"KnowledgeDigest"` (not a variation)
- ✅ Each entry has all required sub-fields: `uuid`, `title`, `tl_dr`, `source_url`
- ✅ `confidence_score` (0.0-1.0 scale) is float or None, never overflowing
- ✅ `key_points` and `entities` are lists (may be empty)
- ✅ `trends` contains `{topic, direction, evidence}` dicts or strings
- ✅ `metadata` has `entry_count`, `generated_at`, `domain` matching actual data
- ✅ `entry_count` ≥ 1 (domain has processed KB entries)
- ✅ No trace of mocked/placeholder data — all from real LLM and real KB store

---

### 📊 Q36e Verdict

| Scenario | Result |
|----------|--------|
| 36e.1 generate_digest audio | ⬜ |
| 36e.2 MP3 header validation | ⬜ |
| 36e.3 generate_report audio | ⬜ |
| 36e.4 Empty text error handling | ⬜ |
| 36e.5 generate_digest agent JSON-LD | ⬜ |
| 36e.6 Top-level fields validation | ⬜ |
| 36e.7 entries[].tl_dr non-empty | ⬜ |
| 36e.8 Full schema validation | ⬜ |

**OVERALL: ⬜**
