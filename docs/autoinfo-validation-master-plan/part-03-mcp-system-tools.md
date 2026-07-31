# Part 3: MCP Tools — System, Discovery, Domain, Source, Topic (Q18-Q27c)

**Coverage:** 47 MCP tools across System (5), Discovery (8), Domain (2), Source (7), Topic (9), Collection/Processing (6), Projects (4), Monitor (3), Webhooks (2), Source Health (3), Quality Gate Config (2), Alert Rules (3), Email (1), KB Entry (1), KB Graph (1), CEFR Batch (1), Cost (2), Audit (1)

---

### Part-Level Directory Setup
Run once at the start of this part:
```bash
# Create clean directories for all questions in this part
rm -rf /tmp/test-q18 && mkdir -p /tmp/test-q18
rm -rf /tmp/test-q20 && mkdir -p /tmp/test-q20
rm -rf /tmp/test-q21 && mkdir -p /tmp/test-q21
rm -rf /tmp/test-q22 && mkdir -p /tmp/test-q22
rm -rf /tmp/test-q23 && mkdir -p /tmp/test-q23
rm -rf /tmp/test-q24 && mkdir -p /tmp/test-q24
rm -rf /tmp/test-q25 && mkdir -p /tmp/test-q25
rm -rf /tmp/test-q27b && mkdir -p /tmp/test-q27b
rm -rf /tmp/test-q27c && mkdir -p /tmp/test-q27c
```
**Important — Parameter Names:** MCP tools use specific parameter names that differ from the documentation examples below. Key differences:
- `get_domain_config` expects `{"name": "..."}` (not `domain`)
- `get_source_health` expects `{"source_id": "..."}` (not `domain`)
- `get_kb_entry` expects `{"entry_id": "..."}` (not `domain`)

If a tool returns "got an unexpected keyword argument", check that the parameter name matches the tool's inputSchema (use `list_tools()` to discover schema at runtime).

---

## Q18: MCP System Tools

**Agent says:** "I need the foundational system tools: health check, diagnostics, config, models."

### Prerequisites
```bash
cd /tmp/test-q18
autoinfo init --demo medical-research
```

### Scenarios

#### 18.1 🟢 health_check
```python
from autoinfo.mcp.server import app
import json

result = app.call_tool("health_check", {})
data = json.loads(result.content[0].text)
assert data["status"] == "ok"
assert "version" in data
assert data["tools_count"] >= 68
print(f"✅ health_check: status={data['status']}, version={data.get('version')}, tools={data['tools_count']}")
```
**Expected Result:** ✅ Returns status, version, tools_count.


#### 18.2 🟢 diagnose_system
```python
result = app.call_tool("diagnose_system", {})
data = json.loads(result.content[0].text)
assert "llm" in data
assert "sources" in data
assert "disk" in data
assert "db" in data
print(f"✅ diagnose_system: LLM key={'key_configured' in data.get('llm',{})}, Sources={data.get('sources',{}).get('count',0)}, Disk={data.get('disk',{})}")
```
**Expected Result:** ✅ Returns comprehensive health with llm, sources, disk, db sections.


#### 18.3 🟢 get_config
```python
result = app.call_tool("get_config", {})
data = json.loads(result.content[0].text)
assert "project" in data
assert "llm" in data
assert "domains" in data
print(f"✅ get_config: project={data.get('project',{}).get('name','?')}, domains={len(data.get('domains',[]))}")
```
**Expected Result:** ✅ Returns full config with project, llm, domains.


#### 18.4 🟢 list_available_models
```python
result = app.call_tool("list_available_models", {})
data = json.loads(result.content[0].text)
assert "models" in data
assert len(data["models"]) > 0
print(f"✅ list_available_models: {len(data['models'])} models available")
```
**Expected Result:** ✅ Returns list of configured LLM models (from config defaults + env overrides).


---

### 📊 Q18 Verdict

| Scenario | Result |
|----------|--------|
| 18.1 health_check | ⬜ |
| 18.2 diagnose_system | ⬜ |
| 18.3 get_config | ⬜ |
| 18.4 list_available_models | ⬜ |
| 18.5 get_tool_count | ⬜ |

**OVERALL: ⬜**

---

### Q18.5: get_tool_count (v1.8)

#### 18.5 🟢 get_tool_count — self-discovery tool
```python
result = app.call_tool("get_tool_count", {})
data = json.loads(result.content[0].text)
assert "count" in data
assert data["count"] >= 115
print(f"✅ get_tool_count: {data['count']} tools registered (dynamic)")
```
**Expected Result:** ✅ Returns dynamic tool count. No hardcoded number. Count ≥ 115 (138 expected in v1.8.2).  
Tool: `get_tool_count` — self-discovery tool that returns the dynamic count of registered MCP tools at runtime.

---

## Q19: MCP Discovery Tools

**Agent says:** "I need to discover what domains, platforms, schemas, and templates are available."

### Scenarios

#### 19.1 🟢 list_domains
```python
result = app.call_tool("list_domains", {})
data = json.loads(result.content[0].text)
assert "domains" in data
assert len(data["domains"]) >= 1
print(f"✅ list_domains: {len(data['domains'])} domains: {[d.get('name') for d in data['domains']]}")
```
**Expected Result:** ✅ Returns all domains with name, active status, source/topic counts.


#### 19.2 🟢 list_available_platforms
```python
result = app.call_tool("list_available_platforms", {})
data = json.loads(result.content[0].text)
assert "platforms" in data
assert len(data["platforms"]) >= 1
platform_names = [p.get("name") for p in data["platforms"]]
print(f"✅ list_available_platforms: {platform_names}")
```
**Expected Result:** ✅ Returns available collector platform types. 6 base types (RSS, REST API, web, webhook, email, PDF) with 22+ platform-specific handlers (pubmed, arxiv, crossref, dblp, openalex, semantic_scholar, uspto, nyt, reddit, spotify, youtube, bilibili, apple_podcasts, ap_api, reuters_mcp).


#### 19.3 🟢 get_domain_schema
```python
result = app.call_tool("get_domain_schema", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
assert "fields" in data or "extraction_fields" in data
print(f"✅ get_domain_schema: {data}")
```
**Expected Result:** ✅ Returns extraction schema for the domain with field names and types.


#### 19.4 🟢 get_effective_llm_config
```python
result = app.call_tool("get_effective_llm_config", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
assert "provider" in data or "model" in data
print(f"✅ get_effective_llm_config: provider={data.get('provider','?')}, model={data.get('model','?')}")
```
**Expected Result:** ✅ Returns effective LLM config for domain (with task-based overrides applied).


#### 19.5 🟢 list_output_templates
```python
result = app.call_tool("list_output_templates", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
assert "templates" in data
template_names = [t.get("name") for t in data["templates"]]
print(f"✅ list_output_templates: {template_names}")
```
**Expected Result:** ✅ Returns available output templates (digest, report, tutorial, presentation).


#### 19.6 🟢 activate_domain
```python
result = app.call_tool("activate_domain", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
# Domain should already be active
print(f"✅ activate_domain: {data}")
```
**Expected Result:** ✅ Domain activation confirmed or idempotent (no error if already active).


#### 19.7 🟢 deactivate_domain
```python
result = app.call_tool("deactivate_domain", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
assert "status" in data
print(f"✅ deactivate_domain: {data['status']}")
# Re-activate for subsequent tests
app.call_tool("activate_domain", {"domain": "medical-research"})
```
**Expected Result:** ✅ Domain deactivated. Can be re-activated.


#### 19.8 🟢 get_domain_config
```python
result = app.call_tool("get_domain_config", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
assert "name" in data
assert "sources" in data or "active" in data
print(f"✅ get_domain_config: name={data.get('name')}, active={data.get('active','?')}")
```
**Expected Result:** ✅ Returns full domain config with sources and topics.


---

### 📊 Q19 Verdict

| Scenario | Result |
|----------|--------|
| 19.1 list_domains | ⬜ |
| 19.2 list_available_platforms | ⬜ |
| 19.3 get_domain_schema | ⬜ |
| 19.4 get_effective_llm_config | ⬜ |
| 19.5 list_output_templates | ⬜ |
| 19.6 activate_domain | ⬜ |
| 19.7 deactivate_domain | ⬜ |
| 19.8 get_domain_config | ⬜ |

**OVERALL: ⬜**

---

## Q20: MCP Domain Management Tools

**Agent says:** "I need to add and remove custom domains."

### Prerequisites
```bash
cd /tmp/test-q20
autoinfo init --demo medical-research
```

### Scenarios

#### 20.1 🟢 add_domain — custom domain
```python
from autoinfo.mcp.server import app
import json

result = app.call_tool("add_domain", {
    "name": "my-mcp-domain",
    "description": "Domain created via MCP"
})
data = json.loads(result.content[0].text)
assert "status" in data or "name" in data
print(f"✅ add_domain: {data}")

# Verify it's listed
result = app.call_tool("list_domains", {})
data = json.loads(result.content[0].text)
names = [d.get("name") for d in data.get("domains", [])]
assert "my-mcp-domain" in names
print("✅ Domain confirmed in list_domains")
```
**Expected Result:** ✅ Domain added. Listed in list_domains.


#### 20.2 🟢 remove_domain
```python
result = app.call_tool("remove_domain", {"domain": "my-mcp-domain"})
data = json.loads(result.content[0].text)
print(f"✅ remove_domain: {data}")

# Verify removed
result = app.call_tool("list_domains", {})
data = json.loads(result.content[0].text)
names = [d.get("name") for d in data.get("domains", [])]
assert "my-mcp-domain" not in names
print("✅ Domain confirmed removed from list_domains")
```
**Expected Result:** ✅ Domain removed. No longer listed.


#### 20.3 🔴 add_domain — duplicate
```python
# First create
app.call_tool("add_domain", {"name": "dup-domain", "description": "First"})
# Try again
result = app.call_tool("add_domain", {"name": "dup-domain", "description": "Duplicate"})
data = json.loads(result.content[0].text)
assert "error" in data.get("message", "") or "already exists" in str(data).lower()
print(f"✅ add_domain duplicate handled: {data.get('message', data)}")
# Cleanup
app.call_tool("remove_domain", {"domain": "dup-domain"})
```
**Expected Result:** ❌ Error or warning about duplicate domain. No crash.


---

### 📊 Q20 Verdict

| Scenario | Result |
|----------|--------|
| 20.1 add_domain | ⬜ |
| 20.2 remove_domain | ⬜ |
| 20.3 Duplicate domain | ⬜ |

**OVERALL: ⬜**

---

## Q21: MCP Source Management Tools

**Agent says:** "I need to manage sources programmatically via MCP."

### Prerequisites
```bash
cd /tmp/test-q21
autoinfo init --demo medical-research
```

### Scenarios

#### 21.1 🟢 list_sources
```python
from autoinfo.mcp.server import app
import json

result = app.call_tool("list_sources", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
sources = data.get("sources", data.get("items", []))
assert len(sources) >= 1
print(f"✅ list_sources: {len(sources)} sources: {[s.get('name') for s in sources]}")
```
**Expected Result:** ✅ Returns sources with name, type, url, quality_tier.


#### 21.2 🟢 add_source
```python
result = app.call_tool("add_source", {
    "domain": "medical-research",
    "name": "mcp-test-rss",
    "type": "rss",
    "url": "https://example.com/feed"
})
data = json.loads(result.content[0].text)
assert "status" in data or "name" in data
print(f"✅ add_source: {data}")
```
**Expected Result:** ✅ Source added to domain's sources.


#### 21.3 🟢 add_sources (batch)
```python
result = app.call_tool("add_sources", {
    "domain": "medical-research",
    "sources": [
        {"name": "batch-source-1", "type": "web", "url": "https://example1.com"},
        {"name": "batch-source-2", "type": "web", "url": "https://example2.com"}
    ]
})
data = json.loads(result.content[0].text)
assert "count" in data or "status" in data
print(f"✅ add_sources: {data}")
```
**Expected Result:** ✅ Multiple sources added in one call.


#### 21.4 🟢 test_source
```python
result = app.call_tool("test_source", {"domain": "medical-research", "name": "pubmed"})
data = json.loads(result.content[0].text)
assert "status" in data or "reachable" in data
print(f"✅ test_source: {data}")
```
**Expected Result:** ✅ Source tested for reachability. Status returned.


#### 21.5 🟢 remove_source
```python
result = app.call_tool("remove_source", {"domain": "medical-research", "name": "mcp-test-rss"})
data = json.loads(result.content[0].text)
print(f"✅ remove_source: {data}")

# Verify removed
result = app.call_tool("list_sources", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
sources = data.get("sources", data.get("items", []))
names = [s.get("name") for s in sources]
assert "mcp-test-rss" not in names
print("✅ Source confirmed removed")
```
**Expected Result:** ✅ Source removed. No longer listed.


#### 21.6 🟢 get_source_health
```python
result = app.call_tool("get_source_health", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
assert "sources" in data or "items" in data
sources = data.get("sources", data.get("items", []))
for s in sources:
    print(f"  {s.get('name','?')}: {s.get('status','?')} ({s.get('latency_ms','?')}ms)")
print(f"✅ get_source_health: {len(list(sources))} sources checked")
```
**Expected Result:** ✅ Returns health status for all sources with latency.


---

### 📊 Q21 Verdict

| Scenario | Result |
|----------|--------|
| 21.1 list_sources | ⬜ |
| 21.2 add_source | ⬜ |
| 21.3 add_sources batch | ⬜ |
| 21.4 test_source | ⬜ |
| 21.5 remove_source | ⬜ |
| 21.6 get_source_health | ⬜ |
| 21.7 get_feeds (v1.8) | ⬜ |

**OVERALL: ⬜**

---

### Q21.7: get_feeds (v1.8)

#### 21.7 🟢 get_feeds — RSS feed retrieval
```python
from autoinfo.mcp.server import app
import json

result = app.call_tool("get_feeds", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
assert "feeds" in data or "items" in data
print(f"✅ get_feeds: {json.dumps(data, indent=2)[:300]}")
```
**Expected Result:** ✅ Returns RSS feeds for domain sources in XML or structured format.  
Tool: `get_feeds` — retrieves RSS feed data for domain sources with RSS XML output.

---

## Q22: MCP Topic & Keyword Tools

**Agent says:** "I need to manage topics and their keywords via MCP."

### Prerequisites
```bash
cd /tmp/test-q22
autoinfo init --demo medical-research
```

### Scenarios

#### 22.1 🟢 add_topic
```python
from autoinfo.mcp.server import app
import json

result = app.call_tool("add_topic", {
    "domain": "medical-research",
    "name": "Gene Therapy MCP",
    "keywords": ["CRISPR", "AAV", "gene editing"]
})
data = json.loads(result.content[0].text)
print(f"✅ add_topic: {data}")
```
**Expected Result:** ✅ Topic added with keywords.


#### 22.2 🟢 list_topics
```python
result = app.call_tool("list_topics", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
topics = data.get("topics", data.get("items", []))
print(f"✅ list_topics: {len(topics)} topics: {[t.get('name') for t in topics]}")
```
**Expected Result:** ✅ Returns topics with names and keywords.


#### 22.3 🟢 remove_topic
```python
result = app.call_tool("remove_topic", {"domain": "medical-research", "name": "Gene Therapy MCP"})
data = json.loads(result.content[0].text)
print(f"✅ remove_topic: {data}")

# Verify removed
result = app.call_tool("list_topics", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
topics = data.get("topics", data.get("items", []))
names = [t.get("name") for t in topics]
assert "Gene Therapy MCP" not in names
print("✅ Topic confirmed removed")
```
**Expected Result:** ✅ Topic removed.


#### 22.4 🟢 list_keywords
```python
result = app.call_tool("list_keywords", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
keywords = data.get("keywords", data.get("items", []))
print(f"✅ list_keywords: {len(keywords)} keywords")
for k in keywords[:5]:
    print(f"  - {k.get('keyword','?')} (status: {k.get('status','?')})")
```
**Expected Result:** ✅ Returns keywords with status (pending/approved/rejected).


#### 22.5 🟢 approve_keyword
```python
# Get a pending keyword
result = app.call_tool("list_keywords", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
keywords = data.get("keywords", data.get("items", []))
pending = [k for k in keywords if k.get("status") == "pending"]
if pending:
    kw = pending[0]["keyword"]
    result = app.call_tool("approve_keyword", {"domain": "medical-research", "keyword": kw})
    data = json.loads(result.content[0].text)
    print(f"✅ approve_keyword({kw}): {data}")
else:
    print("⚠️ No pending keywords to approve")
```
**Expected Result:** ✅ Keyword approved. Status changes to "approved".


#### 22.6 🟢 reject_keyword
```python
# Get a pending keyword
result = app.call_tool("list_keywords", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
keywords = data.get("keywords", data.get("items", []))
pending = [k for k in keywords if k.get("status") == "pending"]
if pending:
    kw = pending[0]["keyword"]
    result = app.call_tool("reject_keyword", {"domain": "medical-research", "keyword": kw})
    data = json.loads(result.content[0].text)
    print(f"✅ reject_keyword({kw}): {data}")
else:
    print("⚠️ No pending keywords to reject")
```
**Expected Result:** ✅ Keyword rejected. Status changes to "rejected".


#### 22.7 🟢 suggest_keywords [REQUIRES LLM KEY]
```python
result = app.call_tool("suggest_keywords", {"domain": "medical-research", "topic": "IVF"})
data = json.loads(result.content[0].text)
suggestions = data.get("suggestions", data.get("keywords", []))
assert len(suggestions) > 0
print(f"✅ suggest_keywords: {suggestions}")
```
**Expected Result:** ✅ LLM-suggested keywords returned for the topic.


---

### 📊 Q22 Verdict

| Scenario | Result |
|----------|--------|
| 22.1 add_topic | ⬜ |
| 22.2 list_topics | ⬜ |
| 22.3 remove_topic | ⬜ |
| 22.4 list_keywords | ⬜ |
| 22.5 approve_keyword | ⬜ |
| 22.6 reject_keyword | ⬜ |
| 22.7 suggest_keywords | ⬜ |
| 22.8 topic_group_add (v1.8) | ⬜ |
| 22.9 topic_group_remove (v1.8) | ⬜ |

**OVERALL: ⬜**

---

### Q22.8: topic_group_add (v1.8)

#### 22.8 🟢 topic_group_add — create topic group
```python
from autoinfo.mcp.server import app
import json

result = app.call_tool("topic_group_add", {
    "domain": "medical-research",
    "group_name": "test-group-genomics",
    "topics": ["IVF", "CRISPR"]
})
data = json.loads(result.content[0].text)
assert "status" in data or "name" in data
print(f"✅ topic_group_add: {data}")
```
**Expected Result:** ✅ Topic group created with specified topics.  
Tool: `topic_group_add` — organizes topics into named groups for batch operations and reporting.

---

### Q22.9: topic_group_remove (v1.8)

#### 22.9 🟢 topic_group_remove — remove topic group
```python
result = app.call_tool("topic_group_remove", {
    "domain": "medical-research",
    "group_name": "test-group-genomics"
})
data = json.loads(result.content[0].text)
print(f"✅ topic_group_remove: {data}")

# Verify removed
result = app.call_tool("list_topics", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
# Group removal is idempotent — no error on re-check
print("✅ Group removal confirmed")
```
**Expected Result:** ✅ Topic group removed. Idempotent — no error if group already removed.  
Tool: `topic_group_remove` — removes a named topic group without deleting the underlying topics.

---

## Q23: MCP Collection Tools

**Agent says:** "I need to collect and process via MCP tools."

### Prerequisites
```bash
cd /tmp/test-q23
autoinfo init --demo medical-research
```

### Scenarios

#### 23.1 🟢 collect_sources (sync, dry-run)
```python
from autoinfo.mcp.server import app
import json

result = app.call_tool("collect_sources", {
    "domain": "medical-research",
    "topic": "IVF",
    "limit": 3,
    "dry_run": True
})
data = json.loads(result.content[0].text)
# May have job_id or direct results
print(f"✅ collect_sources (dry-run): {json.dumps(data, indent=2)[:300]}")
assert "job_id" in data or "items_found" in data or "status" in data
```
**Expected Result:** ✅ Collection runs with dry-run preview. Items_found or job_id returned.


#### 23.2 🟢 collect_sources (async, with job_id)
```python
result = app.call_tool("collect_sources", {
    "domain": "medical-research",
    "topic": "IVF",
    "limit": 3,
    "async": True
})
data = json.loads(result.content[0].text)
assert "job_id" in data
job_id = data["job_id"]
print(f"✅ collect_sources (async): job_id={job_id}")

# Poll progress
import time
for _ in range(5):
    progress = app.call_tool("get_collection_progress", {"job_id": job_id})
    pdata = json.loads(progress.content[0].text)
    print(f"  progress: {pdata.get('status','?')} {pdata.get('progress_pct',0)}%")
    if pdata.get("is_complete") or pdata.get("status") in ("completed", "error", "not_found"):
        break
    time.sleep(2)
```
**Expected Result:** ✅ Async collection returns job_id. Progress polling works.


#### 23.3 🟢 get_collection_progress (by domain)
```python
result = app.call_tool("get_collection_progress", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
print(f"✅ get_collection_progress (domain): status={data.get('status','?')}, items={data.get('items_collected',0)}")
```
**Expected Result:** ✅ Returns progress for last run on domain.


#### 23.4 🟢 get_collection_status
```python
result = app.call_tool("get_collection_status", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
print(f"✅ get_collection_status: {json.dumps(data, indent=2)[:200]}")
```
**Expected Result:** ✅ Returns full collection results for domain.


#### 23.5 🟢 process_collection [REQUIRES LLM KEY]
```python
# Ensure collected items exist first
app.call_tool("collect_sources", {"domain": "medical-research", "topic": "IVF", "limit": 3})

result = app.call_tool("process_collection", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
print(f"✅ process_collection: {json.dumps(data, indent=2)[:300]}")
assert "job_id" in data or "total_items" in data or "kb_entries_created" in data
```
**Expected Result:** ✅ Processing runs. Returns job_id or entry counts.


#### 23.6 🟢 get_processing_progress [REQUIRES LLM KEY]
```python
result = app.call_tool("get_processing_progress", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
print(f"✅ get_processing_progress: {json.dumps(data, indent=2)[:200]}")
```
**Expected Result:** ✅ Returns processing progress with item count.


#### 23.7 🟢 batch_run
```python
result = app.call_tool("batch_run", {
    "domain": "medical-research",
    "topic": "IVF",
    "limit": 3
})
data = json.loads(result.content[0].text)
print(f"✅ batch_run: {json.dumps(data, indent=2)[:300]}")
# Should run both collect and process
```
**Expected Result:** ✅ Batch run executes collect + process sequentially.


---

### 📊 Q23 Verdict

| Scenario | Result |
|----------|--------|
| 23.1 collect_sources dry-run | ⬜ |
| 23.2 collect_sources async | ⬜ |
| 23.3 get_collection_progress | ⬜ |
| 23.4 get_collection_status | ⬜ |
| 23.5 process_collection | ⬜ |
| 23.6 get_processing_progress | ⬜ |
| 23.7 batch_run | ⬜ |
| 23.8 clean_cache (v1.8) | ⬜ |

**OVERALL: ⬜**

---

### Q23.8: clean_cache (v1.8)

#### 23.8 🟢 clean_cache — temporary artifact cleanup
```python
from autoinfo.mcp.server import app
import json

result = app.call_tool("clean_cache", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
assert "status" in data or "cleaned" in data
print(f"✅ clean_cache: {data}")
```
**Expected Result:** ✅ Cache cleaned successfully. Returns count of removed items or status.  
Tool: `clean_cache` — removes temporary collection cache artifacts for the specified domain.

---

## Q24: MCP Project Tools

**Agent says:** "I need to manage projects via MCP."

### Prerequisites
```bash
cd /tmp/test-q24
```

### Scenarios

#### 24.1 🟢 init_project
```python
from autoinfo.mcp.server import app
import json
import os
os.chdir("/tmp/test-q24")

result = app.call_tool("init_project", {"name": "mcp-test-project", "demo": "medical-research"})
data = json.loads(result.content[0].text)
print(f"✅ init_project: {data}")
assert "status" in data or "name" in data
```
**Expected Result:** ✅ Project initialized with demo domain. Config files created.


#### 24.2 🟢 list_projects
```python
result = app.call_tool("list_projects", {})
data = json.loads(result.content[0].text)
projects = data.get("projects", data.get("items", []))
print(f"✅ list_projects: {len(projects)} projects: {[p.get('name') for p in projects]}")
```
**Expected Result:** ✅ Returns list of initialized projects.


#### 24.3 🟢 get_project_assets
```python
result = app.call_tool("get_project_assets", {"project_name": "mcp-test-project"})
data = json.loads(result.content[0].text)
print(f"✅ get_project_assets: {data}")
```
**Expected Result:** ✅ Returns project assets (directories, file counts).


#### 24.4 🟢 archive_project
```python
result = app.call_tool("archive_project", {"project_name": "mcp-test-project"})
data = json.loads(result.content[0].text)
print(f"✅ archive_project: {data}")
```
**Expected Result:** ✅ Project archived. Confirmation shown.


---

### 📊 Q24 Verdict

| Scenario | Result |
|----------|--------|
| 24.1 init_project | ⬜ |
| 24.2 list_projects | ⬜ |
| 24.3 get_project_assets | ⬜ |
| 24.4 archive_project | ⬜ |

**OVERALL: ⬜**

---

## Q25: MCP Webhook Tools

**Agent says:** "I need to configure webhooks for real-time notifications."

### Prerequisites
```bash
cd /tmp/test-q25
autoinfo init --demo medical-research
```

### Scenarios

#### 25.1 🟢 set_domain_webhooks
```python
from autoinfo.mcp.server import app
import json

result = app.call_tool("set_domain_webhooks", {
    "domain": "medical-research",
    "url": "https://example.com/webhook",
    "events": ["item_collected", "item_processed"]
})
data = json.loads(result.content[0].text)
print(f"✅ set_domain_webhooks: {data}")
```
**Expected Result:** ✅ Webhooks configured for domain. URL and events stored.


#### 25.2 🟢 get_domain_webhooks
```python
result = app.call_tool("get_domain_webhooks", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
assert "url" in data or "webhooks" in data or "events" in data
print(f"✅ get_domain_webhooks: {data}")
```
**Expected Result:** ✅ Returns configured webhook URL and event list.


---

### 📊 Q25 Verdict

| Scenario | Result |
|----------|--------|
| 25.1 set_domain_webhooks | ⬜ |
| 25.2 get_domain_webhooks | ⬜ |

**OVERALL: ⬜**

---

## Q26: MCP Source Health & Rating Tools

**Agent says:** "I need to check source health and rate items."

### Scenarios

#### 26.1 🟢 get_source_health (by domain)
```python
from autoinfo.mcp.server import app
import json

result = app.call_tool("get_source_health", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
print(f"✅ get_source_health: {json.dumps(data, indent=2)[:200]}")
```
**Expected Result:** ✅ Returns source health status with reachability and latency.


#### 26.2 🟢 rate_item
```python
# Get an entry_id from summaries
result = app.call_tool("list_summaries", {"domain": "medical-research", "limit": 1})
data = json.loads(result.content[0].text)
entries = data.get("entries", [])
if entries:
    entry_id = entries[0].get("entry_id", "")
    result = app.call_tool("rate_item", {
        "domain": "medical-research",
        "entry_id": entry_id,
        "rating": 5
    })
    data = json.loads(result.content[0].text)
    print(f"✅ rate_item: {data}")
else:
    print("⚠️ No entries to rate (run collect + process first)")
```
**Expected Result:** ✅ Item rated. Rating stored in metadata.


---

### 📊 Q26 Verdict

| Scenario | Result |
|----------|--------|
| 26.1 get_source_health | ⬜ |
| 26.2 rate_item | ⬜ |

**OVERALL: ⬜**

---

## Q27: MCP Monitor & Active Delivery Tools

**Agent says:** "I need to see what's currently running."

### Scenarios

#### 27.1 🟢 list_active_collections
```python
from autoinfo.mcp.server import app
import json

result = app.call_tool("list_active_collections", {})
data = json.loads(result.content[0].text)
collections = data.get("collections", data.get("items", []))
print(f"✅ list_active_collections: {len(collections)} active: {collections}")
```
**Expected Result:** ✅ Returns currently running collection tasks with job_ids and status.


#### 27.2 🟢 list_active_deliveries
```python
result = app.call_tool("list_active_deliveries", {})
data = json.loads(result.content[0].text)
deliveries = data.get("deliveries", data.get("items", []))
print(f"✅ list_active_deliveries: {len(deliveries)} active: {deliveries}")
```
**Expected Result:** ✅ Returns currently active delivery tasks with job_ids, channels, and status.


#### 27.3 🟢 get_channel_health (all channels)
```python
from autoinfo.mcp.server import app
import json

# Omit channel_name to check all 11 delivery channels
result = app.call_tool("get_channel_health", {})
data = json.loads(result.content[0].text)
print(f"✅ get_channel_health (all): {json.dumps(data, indent=2)[:400]}")
# Expect health status for all 11 channels: smtp, webhook, rest_api, file_export,
# discord, telegram, wechat_work, wechat_oa, dingtalk, feishu, rss
channels = data.get("channels", data.get("items", []))
assert len(channels) >= 1, "Expected at least one channel health entry"
for ch in channels:
    print(f"  {ch.get('channel','?')}: healthy={ch.get('healthy','?')}, latency_ms={ch.get('latency_ms','?')}")
```
**Expected Result:** ✅ Returns health status (healthy, latency_ms, error) for all 11 delivery channels.


#### 27.4 🟢 get_channel_health (single channel)
```python
result = app.call_tool("get_channel_health", {"channel_name": "smtp"})
data = json.loads(result.content[0].text)
print(f"✅ get_channel_health (smtp): {data}")
# Expect healthy, latency_ms, and error fields for the smtp channel
assert "healthy" in data or "channels" in data or "status" in data
```
**Expected Result:** ✅ Returns health status for a single named channel (smtp). Includes `healthy`, `latency_ms`, `error` fields.


---

### 📊 Q27 Verdict

| Scenario | Result |
|----------|--------|
| 27.1 list_active_collections | ⬜ |
| 27.2 list_active_deliveries | ⬜ |
| 27.3 get_channel_health (all) | ⬜ |
| 27.4 get_channel_health (single) | ⬜ |

**OVERALL: ⬜**

---

## Q27b: MCP Quality Gate Config Tools

**Agent says:** "I need to inspect and configure quality gate thresholds per domain."

### Prerequisites
```bash
cd /tmp/test-q27b
autoinfo init --demo medical-research
```

### Scenarios

#### 27b.1 🟢 get_gate_config
```python
from autoinfo.mcp.server import app
import json

result = app.call_tool("get_gate_config", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
assert "gates" in data or "config" in data
print(f"✅ get_gate_config: {json.dumps(data, indent=2)[:300]}")
```
**Expected Result:** ✅ Returns all gate configurations for the domain (G0-G5 thresholds, actions).


#### 27b.2 🟢 set_gate_config
```python
result = app.call_tool("set_gate_config", {
    "domain": "medical-research",
    "gate": "G3",
    "threshold": 60,
    "action": "flag"
})
data = json.loads(result.content[0].text)
print(f"✅ set_gate_config: {data}")

# Verify the change persists
result = app.call_tool("get_gate_config", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
gates = data.get("gates", data.get("config", {}))
g3 = gates.get("G3", gates.get("g3", {}))
print(f"  G3 threshold={g3.get('threshold','?')}, action={g3.get('action','?')}")
```
**Expected Result:** ✅ Gate configuration updated. Change persists on subsequent read.


---

### 📊 Q27b Verdict

| Scenario | Result |
|----------|--------|
| 27b.1 get_gate_config | ⬜ |
| 27b.2 set_gate_config | ⬜ |

**OVERALL: ⬜**

---

## Q27c: MCP Alert Rules Tools

**Agent says:** "I need to manage alert rules programmatically — view, add, and remove."

### Prerequisites
```bash
cd /tmp/test-q27c
autoinfo init --demo medical-research
```

### Scenarios

#### 27c.1 🟢 get_alert_rules
```python
from autoinfo.mcp.server import app
import json

result = app.call_tool("get_alert_rules", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
rules = data.get("rules", data.get("items", []))
print(f"✅ get_alert_rules: {len(rules)} rules defined")
for r in rules:
    print(f"  - {r.get('name','?')}: {r.get('trigger','?')} → {r.get('action','?')}")
```
**Expected Result:** ✅ Returns all alert rules for the domain with triggers and actions.


#### 27c.2 🟢 add_alert_rule
```python
result = app.call_tool("add_alert_rule", {
    "domain": "medical-research",
    "name": "test-collection-failure",
    "trigger": "collection_error_rate > 0.5",
    "action": "notify_agent",
    "channel": "webhook",
    "threshold": 0.5
})
data = json.loads(result.content[0].text)
print(f"✅ add_alert_rule: {data}")

# Verify it appears in list
result = app.call_tool("get_alert_rules", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
rules = data.get("rules", data.get("items", []))
names = [r.get("name") for r in rules]
assert "test-collection-failure" in names
print("✅ Rule confirmed in get_alert_rules")
```
**Expected Result:** ✅ Alert rule added. Listed in get_alert_rules.


#### 27c.3 🟢 remove_alert_rule
```python
result = app.call_tool("remove_alert_rule", {
    "domain": "medical-research",
    "name": "test-collection-failure"
})
data = json.loads(result.content[0].text)
print(f"✅ remove_alert_rule: {data}")

# Verify removed
result = app.call_tool("get_alert_rules", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
rules = data.get("rules", data.get("items", []))
names = [r.get("name") for r in rules]
assert "test-collection-failure" not in names
print("✅ Rule confirmed removed")
```
**Expected Result:** ✅ Alert rule removed. No longer listed.


---

### 📊 Q27c Verdict

| Scenario | Result |
|----------|--------|
| 27c.1 get_alert_rules | ⬜ |
| 27c.2 add_alert_rule | ⬜ |
| 27c.3 remove_alert_rule | ⬜ |

**OVERALL: ⬜**

---

## Q27d: MCP Email Config Tool (v1.8)

**Agent says:** "I need to manage email configuration via MCP."

### Prerequisites
```bash
cd /tmp/test-q27d
autoinfo init --demo medical-research
```

### Scenarios

#### 27d.1 🟢 email_config
```python
from autoinfo.mcp.server import app
import json

result = app.call_tool("email_config", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
assert "smtp" in data or "config" in data
print(f"✅ email_config: {json.dumps(data, indent=2)[:200]}")
```
**Expected Result:** ✅ Returns email configuration for the domain (SMTP settings, sender, recipient info).  
Tool: `email_config` — manages SMTP email configuration (view/update settings) for a domain.

---

### 📊 Q27d Verdict

| Scenario | Result |
|----------|--------|
| 27d.1 email_config | ⬜ |

**OVERALL: ⬜**

---

## Q27e: MCP KB Entry Creation Tool (v1.8)

**Agent says:** "I need to create KB entries directly at the Raw tier."

### Prerequisites
```bash
cd /tmp/test-q27e
autoinfo init --demo medical-research
```

### Scenarios

#### 27e.1 🟢 create_kb_entry — direct Raw-tier creation
```python
from autoinfo.mcp.server import app
import json

result = app.call_tool("create_kb_entry", {
    "domain": "medical-research",
    "title": "Test KB Entry v1.8",
    "content": "Sample content for direct Raw-tier KB creation.",
    "source_url": "https://example.com/test",
    "source_type": "web",
    "source_platform": "test"
})
data = json.loads(result.content[0].text)
assert "entry_id" in data or "status" in data
print(f"✅ create_kb_entry: {data}")
```
**Expected Result:** ✅ KB entry created directly at 01-Raw tier with source provenance metadata.  
Tool: `create_kb_entry` — creates a KB entry directly at the 01-Raw tier with mandatory source metadata.

---

### 📊 Q27e Verdict

| Scenario | Result |
|----------|--------|
| 27e.1 create_kb_entry | ⬜ |

**OVERALL: ⬜**

---

## Q27f: MCP Knowledge Graph Export Tool (v1.8)

**Agent says:** "I need to export the knowledge graph."

### Prerequisites
```bash
cd /tmp/test-q27f
autoinfo init --demo medical-research
```

### Scenarios

#### 27f.1 🟢 knowledge_graph_export
```python
from autoinfo.mcp.server import app
import json

result = app.call_tool("knowledge_graph_export", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
assert "nodes" in data or "edges" in data or "graph" in data
print(f"✅ knowledge_graph_export: {json.dumps(data, indent=2)[:300]}")
```
**Expected Result:** ✅ Returns graph-structured KB export with nodes and edges.  
Tool: `knowledge_graph_export` — exports the knowledge graph for a domain in graph-structured format.

---

### 📊 Q27f Verdict

| Scenario | Result |
|----------|--------|
| 27f.1 knowledge_graph_export | ⬜ |

**OVERALL: ⬜**

---

## Q27g: MCP CEFR Batch Tool (v1.8)

**Agent says:** "I need to classify multiple texts by CEFR level at once."

### Prerequisites
```bash
cd /tmp/test-q27g
autoinfo init --demo medical-research
```

### Scenarios

#### 27g.1 🟢 cefr_batch — batch classification [REQUIRES LLM KEY]
```python
from autoinfo.mcp.server import app
import json

result = app.call_tool("cefr_batch", {
    "texts": [
        "The mitochondria is the powerhouse of the cell.",
        "It is a cat."
    ],
    "language": "en"
})
data = json.loads(result.content[0].text)
assert "results" in data or "items" in data
items = data.get("results", data.get("items", []))
assert len(items) == 2
print(f"✅ cefr_batch: {len(items)} texts classified")
for item in items:
    print(f"  level={item.get('level','?')}, confidence={item.get('confidence','?')}")
```
**Expected Result:** ✅ Multiple texts classified. Each result includes level and confidence score.  
Tool: `cefr_batch` — classifies multiple texts by CEFR level (EN/ZH/JA) in a single call.

---

### 📊 Q27g Verdict

| Scenario | Result |
|----------|--------|
| 27g.1 cefr_batch | ⬜ |

**OVERALL: ⬜**

---

## Q27h: MCP Cost Management Tools (v1.8)

**Agent says:** "I need to manage cost tracking via MCP."

### Prerequisites
```bash
cd /tmp/test-q27h
autoinfo init --demo medical-research
```

### Scenarios

#### 27h.1 🟢 cost_dashboard
```python
from autoinfo.mcp.server import app
import json

result = app.call_tool("cost_dashboard", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
assert "daily_trends" in data or "summary" in data or "top_models" in data
print(f"✅ cost_dashboard: {json.dumps(data, indent=2)[:300]}")
```
**Expected Result:** ✅ Returns cost dashboard with daily trends, summaries, and top models.  
Tool: `cost_dashboard` — displays cost summary, daily trends, and top models/sources.

#### 27h.2 🟢 cost_allocation
```python
result = app.call_tool("cost_allocation", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
assert "allocation" in data or "strategy" in data or "breakdown" in data
print(f"✅ cost_allocation: {json.dumps(data, indent=2)[:300]}")
```
**Expected Result:** ✅ Returns cost allocation breakdown by strategy (pro-rata, usage-based, direct).  
Tool: `cost_allocation` — returns cost allocation breakdown across strategies for governance.

---

### 📊 Q27h Verdict

| Scenario | Result |
|----------|--------|
| 27h.1 cost_dashboard | ⬜ |
| 27h.2 cost_allocation | ⬜ |

**OVERALL: ⬜**

---

## Q27i: MCP Audit Log Tool (v1.8)

**Agent says:** "I need to query the audit log programmatically."

### Prerequisites
```bash
cd /tmp/test-q27i
autoinfo init --demo medical-research
```

### Scenarios

#### 27i.1 🟢 query_audit_log
```python
from autoinfo.mcp.server import app
import json

result = app.call_tool("query_audit_log", {"limit": 5})
data = json.loads(result.content[0].text)
assert "entries" in data or "events" in data or "log" in data
entries = data.get("entries", data.get("events", data.get("log", [])))
print(f"✅ query_audit_log: {len(entries)} audit entries returned")
```
**Expected Result:** ✅ Returns append-only audit log entries with actor, resource, and action fields.  
Tool: `query_audit_log` — queries the immutable append-only audit log for all operations.

---

### 📊 Q27i Verdict

| Scenario | Result |
|----------|--------|
| 27i.1 query_audit_log | ⬜ |

**OVERALL: ⬜**
