# Part 9: Async Operations, Cron, Email & Webhooks (Q54-Q58)

**Coverage:** Async job_id polling, cron schedules, email digests, webhooks, agent alerting

---

## Q54: Async Collection with job_id Polling

**Agent says:** "I need to start long-running collection in async mode and poll for progress."

### Prerequisites
```bash
cd /tmp && rm -rf test-q54 && mkdir test-q54 && cd test-q54
autoinfo init --demo medical-research
```

### Scenarios

#### 54.1 🟢 Async collection returns job_id immediately
```python
from autoinfo.mcp.server import app
import json
import time

# Start async collection
result = app.call_tool("collect_sources", {
    "domain": "medical-research",
    "topic": "IVF",
    "limit": 5,
    "async": True
})
data = json.loads(result.content[0].text)
assert "job_id" in data, f"Expected job_id in response: {data}"
job_id = data["job_id"]
print(f"✅ Async collect: job_id={job_id}")
```
**Expected Result:** ✅ Async call returns immediately with job_id (not blocking).

**Actual Result:** _________ **PASS / FAIL:** _________

#### 54.2 🟢 Poll progress using job_id
```python
# Poll for completion
max_polls = 10
for i in range(max_polls):
    progress = app.call_tool("get_collection_progress", {"job_id": job_id})
    pdata = json.loads(progress.content[0].text)
    status = pdata.get("status", "?")
    progress_pct = pdata.get("progress_pct", 0)
    items = pdata.get("items_collected", 0)
    is_complete = pdata.get("is_complete", False)
    
    print(f"  Poll {i+1}: status={status}, progress={progress_pct}%, items={items}, complete={is_complete}")
    
    if is_complete or status in ("completed", "error", "not_found"):
        break
    time.sleep(2)

print(f"✅ Async polling completed: status={status}")
```
**Expected Result:** ✅ Progress polling returns status, progress_pct, items_collected, is_complete.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 54.3 🟢 Poll collection by domain (legacy method)
```python
progress = app.call_tool("get_collection_progress", {"domain": "medical-research"})
pdata = json.loads(progress.content[0].text)
print(f"✅ Legacy polling: domain=medical-research, status={pdata.get('status','?')}, items={pdata.get('items_collected',0)}")
```
**Expected Result:** ✅ Legacy domain-based polling still works.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 54.4 🟢 Async process_collection with job_id [REQUIRES LLM KEY]
```python
# Start async processing
result = app.call_tool("process_collection", {
    "domain": "medical-research",
    "async": True
})
data = json.loads(result.content[0].text)
process_job_id = data.get("job_id", "")
if process_job_id:
    print(f"✅ Async process: job_id={process_job_id}")
    
    # Poll for completion
    for i in range(10):
        progress = app.call_tool("get_processing_progress", {"job_id": process_job_id})
        pdata = json.loads(progress.content[0].text)
        status = pdata.get("status", "?")
        items = pdata.get("items_processed", pdata.get("total_items", 0))
        is_complete = pdata.get("is_complete", False)
        
        print(f"  Poll {i+1}: status={status}, items={items}, complete={is_complete}")
        
        if is_complete or status in ("completed", "error"):
            break
        time.sleep(2)
else:
    print("⚠️ No job_id returned (sync mode default)")
```
**Expected Result:** ✅ Async processing returns job_id, progress polling works.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q54 Verdict

| Scenario | Result |
|----------|--------|
| 54.1 Async collect job_id | ⬜ |
| 54.2 Poll by job_id | ⬜ |
| 54.3 Legacy domain poll | ⬜ |
| 54.4 Async process | ⬜ |

**OVERALL: ⬜**

---

## Q55: Cron Schedules

**User says:** "I want automatic collection on a schedule."

### Scenarios

#### 55.1 🟢 Add schedule (collection)
```python
from autoinfo.mcp.server import app
import json

result = app.call_tool("add_schedule", {
    "domain": "medical-research",
    "topic": "IVF",
    "cron": "0 8 * * 1"  # Every Monday at 8 AM
})
data = json.loads(result.content[0].text)
print(f"✅ add_schedule: {data}")
assert "id" in data or "schedule_id" in data or "status" in data
```
**Expected Result:** ✅ Schedule added. ID returned.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 55.2 🟢 List schedules
```python
result = app.call_tool("list_schedules", {})
data = json.loads(result.content[0].text)
schedules = data.get("schedules", data.get("items", []))
print(f"✅ list_schedules: {len(schedules)} schedules")
for s in schedules:
    print(f"  id={s.get('id','?')}: {s.get('domain','?')}/{s.get('topic','?')} cron={s.get('cron','?')}")
```
**Expected Result:** ✅ Returns all schedules with domain, topic, cron.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 55.3 🟢 Run schedules manually
```python
result = app.call_tool("run_schedules", {})
data = json.loads(result.content[0].text)
print(f"✅ run_schedules: {json.dumps(data, indent=2)[:200]}")
```
**Expected Result:** ✅ All schedules executed. Collection started.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 55.4 🟢 Remove schedule
```python
# Get schedule ID
result = app.call_tool("list_schedules", {})
data = json.loads(result.content[0].text)
schedules = data.get("schedules", data.get("items", []))
if schedules:
    sched_id = schedules[0].get("id", schedules[0].get("schedule_id", ""))
    result = app.call_tool("remove_schedule", {"schedule_id": sched_id})
    data = json.loads(result.content[0].text)
    print(f"✅ remove_schedule: {data}")
    
    # Verify removed
    verify = app.call_tool("list_schedules", {})
    vdata = json.loads(verify.content[0].text)
    remaining = len(vdata.get("schedules", vdata.get("items", [])))
    print(f"  Schedules remaining: {remaining}")
else:
    print("⚠️ No schedules to remove")
```
**Expected Result:** ✅ Schedule removed. No longer in list.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 55.5 🟢 CLI cron commands
```bash
cd /tmp && rm -rf test-cron-cli && mkdir test-cron-cli && cd test-cron-cli
autoinfo init --demo medical-research

# Add schedule via CLI
autoinfo cron add-schedule --domain medical-research --topic "IVF" --cron "0 8 * * 1"

# List via CLI
autoinfo cron list-schedules

# Run via CLI
autoinfo cron run-schedules
```
**Expected Result:** ✅ Add, list, and run-schedules all work via CLI.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q55 Verdict

| Scenario | Result |
|----------|--------|
| 55.1 Add schedule | ⬜ |
| 55.2 List schedules | ⬜ |
| 55.3 Run schedules | ⬜ |
| 55.4 Remove schedule | ⬜ |
| 55.5 CLI cron commands | ⬜ |

**OVERALL: ⬜**

---

## Q56: Email Digests

**User says:** "I want to receive periodic email digests of my knowledge base."

### Scenarios

#### 56.1 🟢 Configure email settings [REQUIRES SMTP CONFIG]
```bash
cd /tmp && rm -rf test-email && mkdir test-email && cd test-email
autoinfo init --demo medical-research

# Show current email config
autoinfo email config
```
**Expected Result:** ✅ Shows email config (SMTP server, port, sender). May be empty if not configured.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 56.2 🟢 Send email digest via MCP [REQUIRES SMTP CONFIG]
```python
from autoinfo.mcp.server import app
import json

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

#### 56.3 🟢 Send email digest via CLI [REQUIRES SMTP CONFIG]
```bash
autoinfo email send --to user@example.com --subject "Weekly Digest" --domain medical-research --period week
```
**Expected Result:** ✅ Email sent confirmation via CLI.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q56 Verdict

| Scenario | Result |
|----------|--------|
| 56.1 Email config | ⬜ |
| 56.2 Send via MCP | ⬜ |
| 56.3 Send via CLI | ⬜ |

**OVERALL: ⬜**

---

## Q57: Webhooks & Agent Alerting

**User says:** "I want real-time notifications when new items are collected."

### Scenarios

#### 57.1 🟢 Set domain webhooks
```python
from autoinfo.mcp.server import app
import json

result = app.call_tool("set_domain_webhooks", {
    "domain": "medical-research",
    "url": "https://example.com/webhook",
    "events": ["item_collected"]
})
data = json.loads(result.content[0].text)
print(f"✅ set_domain_webhooks: {data}")
```
**Expected Result:** ✅ Webhooks configured for domain.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 57.2 🟢 Get domain webhooks
```python
result = app.call_tool("get_domain_webhooks", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
assert "url" in data or "webhooks" in data
print(f"✅ get_domain_webhooks: url={data.get('url','?')}, events={data.get('events',[])}")
```
**Expected Result:** ✅ Returns configured webhook URL and event list.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 57.3 🟢 Agent alerting — source health monitoring
```python
# Agent checks source health proactively
result = app.call_tool("get_source_health", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
sources = data.get("sources", data.get("items", []))

print(f"✅ Source health monitoring:")
unhealthy = []
for s in sources:
    status = s.get("status", "unknown")
    latency = s.get("latency_ms", "N/A")
    name = s.get("name", "?")
    print(f"  {name}: status={status}, latency={latency}ms")
    if status != "ok":
        unhealthy.append(name)

if unhealthy:
    print(f"  ⚠️ Unhealthy sources: {unhealthy}")
else:
    print(f"  ✅ All sources healthy")
```
**Expected Result:** ✅ Source health returned with per-source status and latency. Alerts can be generated for unhealthy sources.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 57.4 🟢 Agent proactive alerting flow (documented pattern)
```python
# Agent polls source health, checks for issues, and reports
import time

def check_and_alert(domain):
    """Proactive source health check (as documented in agent-alerting.md)."""
    result = app.call_tool("get_source_health", {"domain": domain})
    data = json.loads(result.content[0].text)
    sources = data.get("sources", data.get("items", []))
    
    alerts = []
    for s in sources:
        if s.get("status") != "ok":
            alerts.append({
                "source": s.get("name"),
                "issue": f"Status: {s.get('status')}, latency: {s.get('latency_ms')}ms",
                "action": "Check source URL or network connectivity"
            })
    
    return {
        "domain": domain,
        "total_sources": len(sources),
        "healthy": len(sources) - len(alerts),
        "alerts": alerts
    }

report = check_and_alert("medical-research")
print(f"✅ Agent alerting report: {json.dumps(report, indent=2)}")
```
**Expected Result:** ✅ Agent can implement proactive alerting flow as documented in docs/dev/agent-alerting.md.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q57 Verdict

| Scenario | Result |
|----------|--------|
| 57.1 Set webhooks | ⬜ |
| 57.2 Get webhooks | ⬜ |
| 57.3 Source health | ⬜ |
| 57.4 Agent alerting | ⬜ |

**OVERALL: ⬜**

---

## Q58: Batch Run (Collect + Process)

**User says:** "I want to run collection and processing in one batch command."

### Scenarios

#### 58.1 🟢 batch_run via MCP
```python
from autoinfo.mcp.server import app
import json

result = app.call_tool("batch_run", {
    "domain": "medical-research",
    "topic": "IVF",
    "limit": 3
})
data = json.loads(result.content[0].text)
print(f"✅ batch_run: {json.dumps(data, indent=2)[:300]}")
# Should include both collection and processing results
assert "job_id" in data or "collection" in data or "processing" in data or "status" in data
```
**Expected Result:** ✅ batch_run executes collect + process. Returns combined results.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 58.2 🟢 batch_run with async flag
```python
result = app.call_tool("batch_run", {
    "domain": "medical-research",
    "topic": "IVF",
    "limit": 3,
    "async": True
})
data = json.loads(result.content[0].text)
if "job_id" in data:
    print(f"✅ batch_run (async): job_id={data['job_id']}")
else:
    print(f"✅ batch_run (sync): {json.dumps(data, indent=2)[:200]}")
```
**Expected Result:** ✅ Async batch_run returns job_id for progress polling.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q58 Verdict

| Scenario | Result |
|----------|--------|
| 58.1 batch_run MCP | ⬜ |
| 58.2 Async batch | ⬜ |

**OVERALL: ⬜**
