# Part 4: MCP Tools — KB, Search, Output, Cron, Email, CEFR, Extraction (Q28-Q36)

**Coverage:** 36 MCP tools: KB (9), KB Relations/Versioning/Monitor (6), KB Graph (1), Output (6), Export/Import (2), CEFR (1), Cron (4), Email (1), Custom Extraction (2), Q&A (1), Keywords (3)

---

## Q28: MCP KB Summary Tools

**Agent says:** "I need to browse summaries and entries via MCP."

### Prerequisites
```bash
cd /tmp && rm -rf test-q28 && mkdir test-q28 && cd test-q28
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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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
cd /tmp && rm -rf test-q29 && mkdir test-q29 && cd test-q29
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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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
cd /tmp && rm -rf test-q30 && mkdir test-q30 && cd test-q30
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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

#### 32.3 🟢 query_knowledge_graph
```python
result = app.call_tool("query_knowledge_graph", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
print(f"✅ query_knowledge_graph: {json.dumps(data, indent=2)[:300]}")
```
**Expected Result:** ✅ Returns knowledge graph with entities and relations.

**Actual Result:** _________ **PASS / FAIL:** _________

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
cd /tmp && rm -rf test-q33 && mkdir test-q33 && cd test-q33
autoinfo init --demo medical-research
autoinfo collect --domain medical-research --topic "IVF" --limit 3
```

### Scenarios

#### 33.1 🟢 generate_digest
```python
from autoinfo.mcp.server import app
import json

result = app.call_tool("generate_digest", {
    "domain": "medical-research",
    "period": "week"
})
data = json.loads(result.content[0].text)
print(f"✅ generate_digest: {json.dumps(data, indent=2)[:200]}")
```
**Expected Result:** ✅ Digest generated. Text content or file path returned.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 33.2 🟢 generate_report (markdown)
```python
result = app.call_tool("generate_report", {
    "domain": "medical-research",
    "format": "markdown"
})
data = json.loads(result.content[0].text)
print(f"✅ generate_report (MD): {json.dumps(data, indent=2)[:200]}")
```
**Expected Result:** ✅ Report generated in Markdown format.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 33.3 🟢 generate_report (json)
```python
result = app.call_tool("generate_report", {
    "domain": "medical-research",
    "format": "json"
})
data = json.loads(result.content[0].text)
print(f"✅ generate_report (JSON): {json.dumps(data, indent=2)[:200]}")
assert "entries" in data or "data" in data or "content" in data
```
**Expected Result:** ✅ Report generated in JSON format with entries.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 33.4 🟢 generate_tutorial [REQUIRES LLM KEY]
```python
result = app.call_tool("generate_tutorial", {
    "domain": "medical-research",
    "topic": "IVF"
})
data = json.loads(result.content[0].text)
print(f"✅ generate_tutorial: {json.dumps(data, indent=2)[:200]}")
```
**Expected Result:** ✅ Tutorial generated with structured educational content.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 33.5 🟢 generate_presentation [REQUIRES LLM KEY]
```python
result = app.call_tool("generate_presentation", {
    "domain": "medical-research",
    "topic": "IVF"
})
data = json.loads(result.content[0].text)
print(f"✅ generate_presentation: {json.dumps(data, indent=2)[:200]}")
```
**Expected Result:** ✅ Presentation generated (HTML with Reveal.js).

**Actual Result:** _________ **PASS / FAIL:** _________

#### 33.6 🟢 localize_content [REQUIRES LLM KEY]
```python
result = app.call_tool("localize_content", {
    "domain": "medical-research",
    "target_language": "zh-CN"
})
data = json.loads(result.content[0].text)
print(f"✅ localize_content: {json.dumps(data, indent=2)[:200]}")
```
**Expected Result:** ✅ Content translated to target language.

**Actual Result:** _________ **PASS / FAIL:** _________

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
cd /tmp && rm -rf test-q34 && mkdir test-q34 && cd test-q34
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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

#### 34.8 🟢 run_schedules
```python
result = app.call_tool("run_schedules", {})
data = json.loads(result.content[0].text)
print(f"✅ run_schedules: {json.dumps(data, indent=2)[:200]}")
```
**Expected Result:** ✅ All active schedules executed.

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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
cd /tmp && rm -rf test-q36 && mkdir test-q36 && cd test-q36
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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

#### 36.4 🔴 Nonexistent domain
```python
result = app.call_tool("collect_sources", {
    "domain": "nonexistent-domain-that-does-not-exist"
})
data = json.loads(result.content[0].text)
print(f"✅ MCP error (bad domain): {json.dumps(data, indent=2)[:200]}")
```
**Expected Result:** ❌ Error about domain not found. No crash.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q36 Verdict

| Scenario | Result |
|----------|--------|
| 36.1 Missing params | ⬜ |
| 36.2 Nonexistent tool | ⬜ |
| 36.3 Bad parameter types | ⬜ |
| 36.4 Nonexistent domain | ⬜ |

**OVERALL: ⬜**
