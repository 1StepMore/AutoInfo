# Part 9: Async Operations, Cron, Email & Webhooks (Q54-Q58)

**Coverage:** Async job_id polling, cron schedules, email digests, webhooks, agent alerting

---

### Part-Level Directory Setup
Run once at the start of this part:
```bash
# Create clean directories for all questions in this part
rm -rf /tmp/test-q54 && mkdir -p /tmp/test-q54
```

## Q54: Async Collection with job_id Polling

**Agent says:** "I need to start long-running collection in async mode and poll for progress."

### Prerequisites
```bash
cd /tmp/test-q54
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


#### 54.3 🟢 Poll collection by domain (legacy method)
```python
progress = app.call_tool("get_collection_progress", {"domain": "medical-research"})
pdata = json.loads(progress.content[0].text)
print(f"✅ Legacy polling: domain=medical-research, status={pdata.get('status','?')}, items={pdata.get('items_collected',0)}")
```
**Expected Result:** ✅ Legacy domain-based polling still works.


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


#### 55.3 🟢 Run schedules manually
```python
result = app.call_tool("run_schedules", {})
data = json.loads(result.content[0].text)
print(f"✅ run_schedules: {json.dumps(data, indent=2)[:200]}")
```
**Expected Result:** ✅ All schedules executed. Collection started.


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


#### 55.6 🟢 Cron heartbeat JSON persists after schedule runs
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
TEST_DIR="/tmp/test-q55-hb"

rm -rf "$TEST_DIR" && mkdir -p "$TEST_DIR" && cd "$TEST_DIR"

# Init project
autoinfo init --demo medical-research > /dev/null 2>&1 \
  && echo "  ✅ PASS: project initialized" \
  || { echo "  ❌ FAIL: init failed"; ALL_PASS=false; }

# Add schedule
SCHED_OUTPUT=$(autoinfo cron add-schedule \
  --name "heartbeat-test" \
  --expression "* * * * *" \
  --domain "medical-research" 2>&1)
echo "$SCHED_OUTPUT" | grep -q "added" \
  && echo "  ✅ PASS: schedule 'heartbeat-test' added" \
  || { echo "  ❌ FAIL: add-schedule failed: $SCHED_OUTPUT"; ALL_PASS=false; }

# Run schedules to populate heartbeat
RUN_OUTPUT=$(autoinfo cron run 2>&1)
RUN_EXIT=$?
echo "$RUN_OUTPUT"
[ "$RUN_EXIT" -eq 0 ] \
  && echo "  ✅ PASS: cron run exit 0" \
  || echo "  ⚠️ WARN: cron run exited $RUN_EXIT (collection may have failed, heartbeat still written)"

# Verify heartbeat file exists
HB_FILE=".autoinfo/cron-heartbeat.json"
[ -f "$HB_FILE" ] \
  && echo "  ✅ PASS: heartbeat file $HB_FILE exists" \
  || { echo "  ❌ FAIL: heartbeat file missing"; ALL_PASS=false; }

# Validate heartbeat JSON structure and content
python3 - "$HB_FILE" << 'PYEOF'
import json, sys
hb_path = sys.argv[1]
with open(hb_path) as f:
    hb = json.load(f)
schedules = hb.get("schedules", {})
assert "heartbeat-test" in schedules, f"schedule heartbeat-test not found in: {list(schedules.keys())}"
entry = schedules["heartbeat-test"]
assert "last_run_at" in entry, f"missing last_run_at in entry: {entry}"
assert entry.get("status") in ("ok", "error"), f"unexpected status: {entry.get('status')}"
print(f'  ✅ PASS: heartbeat valid — schedule=heartbeat-test, status={entry["status"]}, last_run_at={entry["last_run_at"]}')
PYEOF
PY_EXIT=$?
[ "$PY_EXIT" -eq 0 ] \
  && echo "  ✅ PASS: heartbeat JSON validates" \
  || { echo "  ❌ FAIL: heartbeat JSON validation failed (exit $PY_EXIT)"; ALL_PASS=false; }

# --- Verdict ---
if [ "$ALL_PASS" = true ]; then
  echo ""; echo "✅ SCENARIO 55.6 PASSED — heartbeat persists after schedule runs"
  exit 0
else
  echo ""; echo "❌ SCENARIO 55.6 FAILED"
  exit 1
fi
```
**Expected Result:**
- ✅ `.autoinfo/cron-heartbeat.json` created after `autoinfo cron run`
- ✅ Heartbeat JSON contains schedule entry with `last_run_at` and `status` fields
- ✅ Status is either `ok` or `error` (both mean heartbeat was written)


#### 55.7 🟢 Missed schedule detected by autoinfo cron health
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
TEST_DIR="/tmp/test-q55-missed"

rm -rf "$TEST_DIR" && mkdir -p "$TEST_DIR" && cd "$TEST_DIR"

# Init and add schedule
autoinfo init --demo medical-research > /dev/null 2>&1
autoinfo cron add-schedule --name "miss-test" --expression "* * * * *" --domain "medical-research" 2>&1 > /dev/null

# Run once to create initial heartbeat
autoinfo cron run 2>&1 > /dev/null || true

# Manipulate heartbeat: set last_run_at to 2 hours ago
# This simulates a schedule that should have run again but didn't
python3 << 'PYEOF'
import json
from datetime import datetime, timezone, timedelta

two_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
hb_path = ".autoinfo/cron-heartbeat.json"

with open(hb_path) as f:
    hb = json.load(f)

schedule_name = None
for name in hb.get("schedules", {}):
    schedule_name = name
    # Only change last_run_at, keep status as-is
    hb["schedules"][name]["last_run_at"] = two_hours_ago
    break

if not schedule_name:
    print("  ❌ No schedule found in heartbeat")
    exit(1)

with open(hb_path, "w") as f:
    json.dump(hb, f, indent=2)
print(f"  ✅ Heartbeat backdated: {schedule_name} last_run_at = {two_hours_ago}")
PYEOF
MANIP_EXIT=$?
[ "$MANIP_EXIT" -eq 0 ] \
  && echo "  ✅ PASS: heartbeat manipulated" \
  || { echo "  ❌ FAIL: cannot manipulate heartbeat"; ALL_PASS=false; }

# Run health — should detect the schedule as "missed"
HEALTH_OUTPUT=$(autoinfo cron health 2>&1)
echo "$HEALTH_OUTPUT"
echo "$HEALTH_OUTPUT" | grep -qi "missed" \
  && echo "  ✅ PASS: health reports 'missed'" \
  || { echo "  ❌ FAIL: health did NOT detect missed schedule"; ALL_PASS=false; }

# Verify via JSON output
HEALTH_JSON=$(autoinfo cron health --json 2>&1)
echo "$HEALTH_JSON" | python3 -c "
import json, sys
data = json.load(sys.stdin)
schedules = data.get('schedules', [])
missed = [s for s in schedules if s.get('health') == 'missed']
assert len(missed) > 0, f'No missed schedules. Health values: {[s.get(\"health\") for s in schedules]}'
assert data.get('missed_count', 0) > 0, f'missed_count is {data.get(\"missed_count\")}'
print(f'  ✅ PASS: {len(missed)} missed schedule(s), missed_count={data[\"missed_count\"]}')
" && echo "  ✅ PASS: JSON health confirms missed" \
  || { echo "  ❌ FAIL: JSON health validation failed"; ALL_PASS=false; }

# --- Verdict ---
if [ "$ALL_PASS" = true ]; then
  echo ""; echo "✅ SCENARIO 55.7 PASSED — missed schedule detected"
  exit 0
else
  echo ""; echo "❌ SCENARIO 55.7 FAILED"
  exit 1
fi
```
**Expected Result:**
- ✅ `autoinfo cron health` reports schedule as `missed` after heartbeat timestamp manipulation
- ✅ `autoinfo cron health --json` returns `missed_count > 0`
- ✅ JSON output contains schedule entries with `health: "missed"`


#### 55.8 🟢 Backfill missed schedules catches up
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
TEST_DIR="/tmp/test-q55-backfill"

rm -rf "$TEST_DIR" && mkdir -p "$TEST_DIR" && cd "$TEST_DIR"

# Init and add schedule
autoinfo init --demo medical-research > /dev/null 2>&1
autoinfo cron add-schedule --name "backfill-test" --expression "* * * * *" --domain "medical-research" 2>&1 > /dev/null

# Run once to create heartbeat
autoinfo cron run 2>&1 > /dev/null || true

# Simulate missed schedule by backdating heartbeat to 2 hours ago
python3 << 'PYEOF'
import json
from datetime import datetime, timezone, timedelta
two_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
with open(".autoinfo/cron-heartbeat.json") as f:
    hb = json.load(f)
for name in hb.get("schedules", {}):
    hb["schedules"][name]["last_run_at"] = two_hours_ago
    break
with open(".autoinfo/cron-heartbeat.json", "w") as f:
    json.dump(hb, f, indent=2)
print("  ✅ Heartbeat backdated to simulate miss")
PYEOF
MANIP_EXIT=$?
[ "$MANIP_EXIT" -eq 0 ] \
  && echo "  ✅ PASS: heartbeat manipulated" \
  || { echo "  ❌ FAIL: manipulation failed"; ALL_PASS=false; }

# --- Pre-backfill: verify health shows missed ---
BEFORE=$(autoinfo cron health --json 2>&1)
echo "$BEFORE" | python3 -c "
import json, sys
data = json.load(sys.stdin)
missed = [s for s in data.get('schedules', []) if s.get('health') == 'missed']
assert len(missed) > 0, 'expected missed BEFORE backfill'
print(f'  ✅ PASS: pre-backfill health shows {len(missed)} missed')
" && echo "  ✅ PASS: pre-backfill health confirms missed" \
  || { echo "  ❌ FAIL: pre-backfill health did not show missed"; ALL_PASS=false; }

# --- Backfill: run cron again to catch up ---
echo "--- Running backfill (autoinfo cron run) ---"
RUN_OUTPUT=$(autoinfo cron run 2>&1)
echo "$RUN_OUTPUT"
echo "$RUN_OUTPUT" | grep -qiE "executed|ran|✓" \
  && echo "  ✅ PASS: backfill run triggered execution" \
  || echo "  ⚠️ WARN: backfill output unclear (may still be ok)"

# --- Post-backfill: verify health is clean ---
AFTER=$(autoinfo cron health --json 2>&1)
echo "$AFTER" | python3 -c "
import json, sys
data = json.load(sys.stdin)
schedules = data.get('schedules', [])
missed = [s for s in schedules if s.get('health') == 'missed']
error_scheds = [s for s in schedules if s.get('health') == 'error']
assert len(missed) == 0, f'still {len(missed)} missed after backfill'
if error_scheds:
    print(f'  ⚠️ Note: {len(error_scheds)} schedule(s) in error state (collection may have failed)')
for s in schedules:
    assert s.get('health') in ('ok', 'unknown'), f'schedule {s.get(\"schedule_id\")} health is {s.get(\"health\")}'
print(f'  ✅ PASS: no missed schedules after backfill')
" && echo "  ✅ PASS: post-backfill health clean" \
  || { echo "  ❌ FAIL: post-backfill health still shows issues"; ALL_PASS=false; }

# --- Verdict ---
if [ "$ALL_PASS" = true ]; then
  echo ""; echo "✅ SCENARIO 55.8 PASSED — backfill catches up missed schedules"
  exit 0
else
  echo ""; echo "❌ SCENARIO 55.8 FAILED"
  exit 1
fi
```
**Expected Result:**
- ✅ Before backfill: health reports schedule as `missed`
- ✅ After `autoinfo cron run` (backfill): schedule executes and catches up
- ✅ After backfill: health no longer reports `missed` for that schedule


#### 55.9 🟢 get_schedule_status returns accurate last_run details
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
TEST_DIR="/tmp/test-q55-status"

rm -rf "$TEST_DIR" && mkdir -p "$TEST_DIR" && cd "$TEST_DIR"

# Init and add schedule
autoinfo init --demo medical-research > /dev/null 2>&1
autoinfo cron add-schedule --name "status-test" --expression "0 8 * * 1" --domain "medical-research" 2>&1 > /dev/null

# Run schedules to populate heartbeat with real last_run data
autoinfo cron run 2>&1 > /dev/null || true

# Call get_schedule_status via CLI: autoinfo cron health --json
STATUS_OUTPUT=$(autoinfo cron health --json 2>&1)
echo "$STATUS_OUTPUT"

echo "$STATUS_OUTPUT" | python3 << 'PYEOF'
import json, sys
from datetime import datetime

data = json.load(sys.stdin)
schedules = data.get("schedules", [])
assert len(schedules) > 0, "no schedules in output"

s = schedules[0]

# --- Required fields ---
fields = ["schedule_id", "domain", "cron_expr", "is_active", "last_run", "next_run", "schedule_type", "health"]
for f in fields:
    assert f in s, f"missing field: {f}"
print("  ✅ PASS: all required fields present")

# --- Value checks ---
assert s["schedule_id"] == "status-test", f'wrong id: {s["schedule_id"]}'
assert s["domain"] == "medical-research", f'wrong domain: {s["domain"]}'
assert s["cron_expr"] == "0 8 * * 1", f'wrong cron: {s["cron_expr"]}'
assert s["is_active"] is True, f"is_active should be True, got {s['is_active']}"
assert s["schedule_type"] == "collection", f'wrong type: {s["schedule_type"]}'
print(f'  ✅ PASS: schedule_id={s["schedule_id"]}, domain={s["domain"]}, cron={s["cron_expr"]}')

# --- last_run validation ---
assert s["last_run"] is not None and s["last_run"] != "", "last_run is empty"
try:
    dt = datetime.fromisoformat(s["last_run"])
    print(f'  ✅ PASS: last_run={s["last_run"]} (valid ISO-8601)')
except ValueError:
    assert False, f'last_run is not valid ISO-8601: {s["last_run"]}'

# --- health field ---
assert s["health"] in ("ok", "error", "unknown"), f'health has unexpected value: {s["health"]}'
print(f'  ✅ PASS: health={s["health"]}')

print(f"  ✅ get_schedule_status returns accurate, complete details")
PYEOF
PY_EXIT=$?
[ "$PY_EXIT" -eq 0 ] \
  && echo "  ✅ PASS: get_schedule_status details are accurate" \
  || { echo "  ❌ FAIL: get_schedule_status validation failed (exit $PY_EXIT)"; ALL_PASS=false; }

# --- Verdict ---
if [ "$ALL_PASS" = true ]; then
  echo ""; echo "✅ SCENARIO 55.9 PASSED — get_schedule_status returns accurate details"
  exit 0
else
  echo ""; echo "❌ SCENARIO 55.9 FAILED"
  exit 1
fi
```
**Expected Result:**
- ✅ `autoinfo cron health --json` returns all required fields: `schedule_id`, `domain`, `cron_expr`, `is_active`, `last_run`, `next_run`, `schedule_type`, `health`
- ✅ `last_run` is a valid ISO-8601 datetime string
- ✅ `is_active` is `True`, `cron_expr` matches what was configured
- ✅ `health` field is one of `ok`, `error`, or `unknown`


---

### 📊 Q55 Verdict

| Scenario | Result |
|----------|--------|
| 55.1 Add schedule | ⬜ |
| 55.2 List schedules | ⬜ |
| 55.3 Run schedules | ⬜ |
| 55.4 Remove schedule | ⬜ |
| 55.5 CLI cron commands | ⬜ |
| 55.6 Heartbeat JSON persists | ⬜ |
| 55.7 Missed schedule detected | ⬜ |
| 55.8 Backfill catches up | ⬜ |
| 55.9 get_schedule_status details | ⬜ |

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


#### 56.3 🟢 Send email digest via CLI [REQUIRES SMTP CONFIG]
```bash
autoinfo email send --to user@example.com --subject "Weekly Digest" --domain medical-research --period week
```
**Expected Result:** ✅ Email sent confirmation via CLI.


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


#### 57.2 🟢 Get domain webhooks
```python
result = app.call_tool("get_domain_webhooks", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
assert "url" in data or "webhooks" in data
print(f"✅ get_domain_webhooks: url={data.get('url','?')}, events={data.get('events',[])}")
```
**Expected Result:** ✅ Returns configured webhook URL and event list.


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


---

### 📊 Q58 Verdict

| Scenario | Result |
|----------|--------|
| 58.1 batch_run MCP | ⬜ |
| 58.2 Async batch | ⬜ |

**OVERALL: ⬜**
