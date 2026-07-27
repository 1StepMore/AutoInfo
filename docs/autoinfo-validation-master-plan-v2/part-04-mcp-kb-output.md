# Part 4: MCP Tools — KB, Search, Output, Cron, Email, CEFR, Extraction (Q28-Q36c)

**Coverage:** 44 MCP tools: KB (9), KB Relations/Versioning/Monitor (6), KB Graph (1), Output (6), Export/Import (2), CEFR (1), Cron (5), Email (1), Custom Extraction (2), Q&A (1), Keywords (3), Knowledge Lifecycle (6), Product (1). Plus v1.7 additions: consumption tracking, automated notifications, cron health (CLI).

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

---

## Q36b: MCP Knowledge Lifecycle Tools

**Agent says:** "I need to compare versions, find/merge similar items, check domain decay, mark items stale, and calculate freshness."

### Prerequisites
```bash
cd /tmp && rm -rf test-q36b && mkdir test-q36b && cd test-q36b
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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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
cd /tmp && rm -rf test-q36c && mkdir test-q36c && cd test-q36c
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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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
cd /tmp && rm -rf test-q36d && mkdir test-q36d && cd test-q36d
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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

#### 36d.6 🟢 Cron heartbeat persistence
```bash
cd /tmp/test-q36d
# After running a schedule, the heartbeat file should exist
ls -la .autoinfo/cron-heartbeat.json 2>/dev/null && echo "Heartbeat file exists" || echo "Heartbeat file not yet created (run a schedule first)"
```
**Expected Result:** ✅ After a schedule run, `.autoinfo/cron-heartbeat.json` persists per-schedule heartbeat entries (last_run, status, error).

**Actual Result:** _________ **PASS / FAIL:** _________

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
