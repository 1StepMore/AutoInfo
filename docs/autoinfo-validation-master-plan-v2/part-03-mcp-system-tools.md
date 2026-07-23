# Part 3: MCP Tools — System, Discovery, Domain, Source, Topic (Q18-Q27)

**Coverage:** 30 MCP tools across System (4), Discovery (8), Domain (2), Source (6), Topic (7), Collection/Processing (5), Projects (4), Monitor (1), Webhooks (2), Source Health (3)

---

## Q18: MCP System Tools

**Agent says:** "I need the foundational system tools: health check, diagnostics, config, models."

### Prerequisites
```bash
cd /tmp && rm -rf test-q18 && mkdir test-q18 && cd test-q18
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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

#### 18.4 🟢 list_available_models
```python
result = app.call_tool("list_available_models", {})
data = json.loads(result.content[0].text)
assert "models" in data
assert len(data["models"]) > 0
print(f"✅ list_available_models: {len(data['models'])} models available")
```
**Expected Result:** ✅ Returns list of configured LLM models (from config defaults + env overrides).

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q18 Verdict

| Scenario | Result |
|----------|--------|
| 18.1 health_check | ⬜ |
| 18.2 diagnose_system | ⬜ |
| 18.3 get_config | ⬜ |
| 18.4 list_available_models | ⬜ |

**OVERALL: ⬜**

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

**Actual Result:** _________ **PASS / FAIL:** _________

#### 19.2 🟢 list_available_platforms
```python
result = app.call_tool("list_available_platforms", {})
data = json.loads(result.content[0].text)
assert "platforms" in data
assert len(data["platforms"]) >= 1
platform_names = [p.get("name") for p in data["platforms"]]
print(f"✅ list_available_platforms: {platform_names}")
```
**Expected Result:** ✅ Returns available collector platform types (pubmed, rss, web, webhook, email, pdf).

**Actual Result:** _________ **PASS / FAIL:** _________

#### 19.3 🟢 get_domain_schema
```python
result = app.call_tool("get_domain_schema", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
assert "fields" in data or "extraction_fields" in data
print(f"✅ get_domain_schema: {data}")
```
**Expected Result:** ✅ Returns extraction schema for the domain with field names and types.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 19.4 🟢 get_effective_llm_config
```python
result = app.call_tool("get_effective_llm_config", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
assert "provider" in data or "model" in data
print(f"✅ get_effective_llm_config: provider={data.get('provider','?')}, model={data.get('model','?')}")
```
**Expected Result:** ✅ Returns effective LLM config for domain (with task-based overrides applied).

**Actual Result:** _________ **PASS / FAIL:** _________

#### 19.5 🟢 list_output_templates
```python
result = app.call_tool("list_output_templates", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
assert "templates" in data
template_names = [t.get("name") for t in data["templates"]]
print(f"✅ list_output_templates: {template_names}")
```
**Expected Result:** ✅ Returns available output templates (digest, report, tutorial, presentation).

**Actual Result:** _________ **PASS / FAIL:** _________

#### 19.6 🟢 activate_domain
```python
result = app.call_tool("activate_domain", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
# Domain should already be active
print(f"✅ activate_domain: {data}")
```
**Expected Result:** ✅ Domain activation confirmed or idempotent (no error if already active).

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

#### 19.8 🟢 get_domain_config
```python
result = app.call_tool("get_domain_config", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
assert "name" in data
assert "sources" in data or "active" in data
print(f"✅ get_domain_config: name={data.get('name')}, active={data.get('active','?')}")
```
**Expected Result:** ✅ Returns full domain config with sources and topics.

**Actual Result:** _________ **PASS / FAIL:** _________

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
cd /tmp && rm -rf test-q20 && mkdir test-q20 && cd test-q20
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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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
cd /tmp && rm -rf test-q21 && mkdir test-q21 && cd test-q21
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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

#### 21.4 🟢 test_source
```python
result = app.call_tool("test_source", {"domain": "medical-research", "name": "pubmed"})
data = json.loads(result.content[0].text)
assert "status" in data or "reachable" in data
print(f"✅ test_source: {data}")
```
**Expected Result:** ✅ Source tested for reachability. Status returned.

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**OVERALL: ⬜**

---

## Q22: MCP Topic & Keyword Tools

**Agent says:** "I need to manage topics and their keywords via MCP."

### Prerequisites
```bash
cd /tmp && rm -rf test-q22 && mkdir test-q22 && cd test-q22
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

**Actual Result:** _________ **PASS / FAIL:** _________

#### 22.2 🟢 list_topics
```python
result = app.call_tool("list_topics", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
topics = data.get("topics", data.get("items", []))
print(f"✅ list_topics: {len(topics)} topics: {[t.get('name') for t in topics]}")
```
**Expected Result:** ✅ Returns topics with names and keywords.

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

#### 22.7 🟢 suggest_keywords [REQUIRES LLM KEY]
```python
result = app.call_tool("suggest_keywords", {"domain": "medical-research", "topic": "IVF"})
data = json.loads(result.content[0].text)
suggestions = data.get("suggestions", data.get("keywords", []))
assert len(suggestions) > 0
print(f"✅ suggest_keywords: {suggestions}")
```
**Expected Result:** ✅ LLM-suggested keywords returned for the topic.

**Actual Result:** _________ **PASS / FAIL:** _________

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

**OVERALL: ⬜**

---

## Q23: MCP Collection Tools

**Agent says:** "I need to collect and process via MCP tools."

### Prerequisites
```bash
cd /tmp && rm -rf test-q23 && mkdir test-q23 && cd test-q23
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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

#### 23.3 🟢 get_collection_progress (by domain)
```python
result = app.call_tool("get_collection_progress", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
print(f"✅ get_collection_progress (domain): status={data.get('status','?')}, items={data.get('items_collected',0)}")
```
**Expected Result:** ✅ Returns progress for last run on domain.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 23.4 🟢 get_collection_status
```python
result = app.call_tool("get_collection_status", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
print(f"✅ get_collection_status: {json.dumps(data, indent=2)[:200]}")
```
**Expected Result:** ✅ Returns full collection results for domain.

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

#### 23.6 🟢 get_processing_progress [REQUIRES LLM KEY]
```python
result = app.call_tool("get_processing_progress", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
print(f"✅ get_processing_progress: {json.dumps(data, indent=2)[:200]}")
```
**Expected Result:** ✅ Returns processing progress with item count.

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**OVERALL: ⬜**

---

## Q24: MCP Project Tools

**Agent says:** "I need to manage projects via MCP."

### Prerequisites
```bash
cd /tmp && rm -rf test-q24 && mkdir test-q24 && cd test-q24
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

**Actual Result:** _________ **PASS / FAIL:** _________

#### 24.2 🟢 list_projects
```python
result = app.call_tool("list_projects", {})
data = json.loads(result.content[0].text)
projects = data.get("projects", data.get("items", []))
print(f"✅ list_projects: {len(projects)} projects: {[p.get('name') for p in projects]}")
```
**Expected Result:** ✅ Returns list of initialized projects.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 24.3 🟢 get_project_assets
```python
result = app.call_tool("get_project_assets", {"project_name": "mcp-test-project"})
data = json.loads(result.content[0].text)
print(f"✅ get_project_assets: {data}")
```
**Expected Result:** ✅ Returns project assets (directories, file counts).

**Actual Result:** _________ **PASS / FAIL:** _________

#### 24.4 🟢 archive_project
```python
result = app.call_tool("archive_project", {"project_name": "mcp-test-project"})
data = json.loads(result.content[0].text)
print(f"✅ archive_project: {data}")
```
**Expected Result:** ✅ Project archived. Confirmation shown.

**Actual Result:** _________ **PASS / FAIL:** _________

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
cd /tmp && rm -rf test-q25 && mkdir test-q25 && cd test-q25
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

**Actual Result:** _________ **PASS / FAIL:** _________

#### 25.2 🟢 get_domain_webhooks
```python
result = app.call_tool("get_domain_webhooks", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
assert "url" in data or "webhooks" in data or "events" in data
print(f"✅ get_domain_webhooks: {data}")
```
**Expected Result:** ✅ Returns configured webhook URL and event list.

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q26 Verdict

| Scenario | Result |
|----------|--------|
| 26.1 get_source_health | ⬜ |
| 26.2 rate_item | ⬜ |

**OVERALL: ⬜**

---

## Q27: MCP Monitor Tool

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

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q27 Verdict

| Scenario | Result |
|----------|--------|
| 27.1 list_active_collections | ⬜ |

**OVERALL: ⬜**
