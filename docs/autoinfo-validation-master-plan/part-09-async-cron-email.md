# Part 9: Async Operations, Cron, Email & Webhooks (Q54-Q58)

**Coverage:** Async job_id polling, cron schedules, email digests, webhooks, agent alerting

---

### Part-Level Directory Setup
Run once at the start of this part:
```bash
# Create clean directories for all questions in this part
rm -rf /tmp/test-q54 && mkdir -p /tmp/test-q54
rm -rf /tmp/test-q56a && mkdir -p /tmp/test-q56a
rm -rf /tmp/test-q56b && mkdir -p /tmp/test-q56b
rm -rf /tmp/test-q56b-empty && mkdir -p /tmp/test-q56b-empty
rm -rf /tmp/test-q57a && mkdir -p /tmp/test-q57a
rm -rf /tmp/test-q57b && mkdir -p /tmp/test-q57b
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
autoinfo cron add-schedule --name "IVF-schedule" --expression "0 8 * * 1" --domain medical-research

# List via CLI
autoinfo cron list-schedules

# Run via CLI
autoinfo cron run
```
**Expected Result:** ✅ Add, list, and run all work via CLI.


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
autoinfo email send-digest --domain medical-research --period weekly
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

## Q56a: Email Delivery Channel (C6 — SMTP)

**User says:** "I need to verify email delivery works end-to-end, including graceful handling when SMTP is not configured."

### Scenarios

#### 56a.1 🟢 Email config shows SMTP settings (even if unconfigured)
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
TEST_DIR="/tmp/test-q56a"
rm -rf "$TEST_DIR" && mkdir -p "$TEST_DIR" && cd "$TEST_DIR"
autoinfo init --demo medical-research 2>&1 > /dev/null

OUTPUT=$(autoinfo email config 2>&1)
EXIT_CODE=$?

echo "$OUTPUT" | grep -qi "smtp\|server\|port\|sender\|config" \
  && echo "  ✅ PASS: email config shows SMTP-related fields" \
  || { echo "  ❌ FAIL: email config missing SMTP fields"; ALL_PASS=false; }

[ "$EXIT_CODE" -eq 0 ] \
  && echo "  ✅ PASS: exit code 0" \
  || { echo "  ❌ FAIL: exit code $EXIT_CODE"; ALL_PASS=false; }

if [ "$ALL_PASS" = true ]; then echo "✅ SCENARIO 56a.1 PASSED"; exit 0; else echo "❌ SCENARIO 56a.1 FAILED"; exit 1; fi
```
**Expected Result:** ✅ Shows SMTP config fields (server, port, sender). Fields may be empty. Exit code 0.

#### 56a.2 🟢 Email send-digest without SMTP config — graceful error
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
TEST_DIR="/tmp/test-q56a"
cd "$TEST_DIR"

OUTPUT=$(autoinfo email send-digest --domain medical-research --period weekly 2>&1) || true
EXIT_CODE=$?

echo "$OUTPUT" | grep -qi "smtp\|config\|not configured\|missing\|error" \
  && echo "  ✅ PASS: graceful error message about missing SMTP config" \
  || { echo "  ❌ FAIL: no SMTP-related error message"; ALL_PASS=false; }

echo "$OUTPUT" | grep -vq "Traceback" \
  && echo "  ✅ PASS: no Python traceback" \
  || { echo "  ❌ FAIL: traceback in output"; ALL_PASS=false; }

if [ "$ALL_PASS" = true ]; then echo "✅ SCENARIO 56a.2 PASSED — graceful SMTP error"; exit 0; else echo "❌ SCENARIO 56a.2 FAILED"; exit 1; fi
```
**Expected Result:** ❌ Graceful error about SMTP not configured. No Python traceback. User-friendly message.

#### 56a.3 🟢 Email send with CC/BCC parameters accepted
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
TEST_DIR="/tmp/test-q56a"
cd "$TEST_DIR"
autoinfo collect --domain medical-research --limit 1 2>&1 > /dev/null || true

# Test that send-digest CLI accepts --cc and --bcc flags
OUTPUT=$(autoinfo email send-digest --domain medical-research --period weekly --cc "cc@example.com" --bcc "bcc@example.com" 2>&1) || true

echo "$OUTPUT" | grep -vq "No such option" \
  && echo "  ✅ PASS: --cc/--bcc flags accepted (no 'No such option' error)" \
  || { echo "  ❌ FAIL: --cc/--bcc flag rejected as unknown"; ALL_PASS=false; }

echo "$OUTPUT" | grep -vq "Traceback" \
  && echo "  ✅ PASS: no Python traceback" \
  || { echo "  ❌ FAIL: traceback in output"; ALL_PASS=false; }

if [ "$ALL_PASS" = true ]; then echo "✅ SCENARIO 56a.3 PASSED"; exit 0; else echo "❌ SCENARIO 56a.3 FAILED"; exit 1; fi
```
**Expected Result:** ✅ CLI accepts --cc and --bcc flags. No "No such option" error. Fails gracefully if SMTP unconfigured.
> **2026-08-02 finding**: `autoinfo email send-digest` currently has NO `--cc`/`--bcc` options — the CLI rejects them with "No such option" (exit 2). This is a documented CLI limitation (send-digest supports only `--domain`/`--period`), tracked separately from the SMTP E2E task. Scenario recorded as ❌ (feature gap, no code change in this env-gated task).

#### 56a.4 🟢 Real SMTP E2E send — env-gated (`SMTP_HOST`/`SMTP_USER`/`SMTP_PASS`)

> **[REQUIRES SMTP] + env-gated (C6)**: This scenario performs a **real SMTP round-trip** — configure `email.*` from env vars, generate a digest, and send it over the wire. It must **never** hardcode credentials: values come exclusively from `SMTP_HOST`/`SMTP_USER`/`SMTP_PASS` (optional `SMTP_PORT`, default 587). When the vars are absent the scenario **exits 0 with an explicit SKIPPED message — it is NOT a failure** (unvalidated, not broken).

```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
TEST_DIR="/tmp/test-q56a"
cd "$TEST_DIR"

# ── Env gate: real SMTP E2E requires credentials ────────────────
if [ -z "${SMTP_HOST:-}" ] || [ -z "${SMTP_USER:-}" ] || [ -z "${SMTP_PASS:-}" ]; then
  echo "  ➖ SKIPPED: SMTP credentials not set (SMTP_HOST/SMTP_USER/SMTP_PASS env-gated)"
  echo "  ➖ SKIPPED: provide Mailtrap/Resend free-tier or Gmail app-password credentials,"
  echo "  ➖ SKIPPED: then re-run. Expected — not a failure."
  echo "✅ SCENARIO 56a.4 SKIPPED (env-gated, no credentials)"
  exit 0
fi

# ── Configure SMTP from env only (never hardcode credentials) ────
autoinfo email config \
  --smtp-server "$SMTP_HOST" \
  --smtp-port "${SMTP_PORT:-587}" \
  --username "$SMTP_USER" \
  --password "$SMTP_PASS" \
  --enable 2>&1 > /dev/null

# ── Actual E2E: generate + send digest over SMTP ────────────────
OUTPUT=$(autoinfo email send-digest --domain medical-research --period weekly 2>&1)
EXIT_CODE=$?

echo "$OUTPUT" | grep -qi "sent" \
  && echo "  ✅ PASS: digest sent successfully" \
  || { echo "  ❌ FAIL: no success message in output"; ALL_PASS=false; }

[ "$EXIT_CODE" -eq 0 ] \
  && echo "  ✅ PASS: exit code 0" \
  || { echo "  ❌ FAIL: exit code $EXIT_CODE (expected 0)"; ALL_PASS=false; }

if [ "$ALL_PASS" = true ]; then echo "✅ SCENARIO 56a.4 PASSED — SMTP E2E round-trip"; exit 0; else echo "❌ SCENARIO 56a.4 FAILED"; exit 1; fi
```
**Expected Result:**
- ✅ With `SMTP_HOST`/`SMTP_USER`/`SMTP_PASS` set: `email send-digest` connects, authenticates, and sends a real digest → output contains "sent", exit 0.
- ➖ Without credentials: explicit SKIPPED message, **exit 0** (env-gated by design — SKIPPED, not FAIL).
- ⛔ Never store, generate, or transmit SMTP credentials in docs/scenarios — env-only.

### 📊 Q56a Verdict

| Scenario | Result |
|----------|--------|
| 56a.1 Email config show | ✅ |
| 56a.2 Send without SMTP | ✅ |
| 56a.3 CC/BCC flags | ❌ |
| 56a.4 Real SMTP E2E (env-gated) | ➖ SKIPPED — SMTP_HOST/SMTP_USER/SMTP_PASS not set (expected, not a failure) |

**OVERALL: ⚠️** — 56a.1/56a.2 pass; 56a.3 blocked by missing `--cc/--bcc` CLI options (feature gap, out of scope); 56a.4 env-gated SKIPPED pending real SMTP credentials. Provide `SMTP_HOST`/`SMTP_USER`/`SMTP_PASS` (Mailtrap/Resend free tier) and re-run 56a.4 to reach ✅.

---

## Q56b: RSS Feed Channel (C7)

**User says:** "I need the RSS feed channel to produce valid RSS 2.0 XML from my knowledge base."

### Scenarios

#### 56b.1 🟢 RSS feed generated from KB entries
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
TEST_DIR="/tmp/test-q56b"
rm -rf "$TEST_DIR" && mkdir -p "$TEST_DIR" && cd "$TEST_DIR"
autoinfo init --demo medical-research 2>&1 > /dev/null
autoinfo collect --domain medical-research --limit 2 2>&1 > /dev/null || true

OUTPUT=$(autoinfo output export --domain medical-research --format rss 2>&1)
EXIT_CODE=$?

# Find RSS file
RSS_FILE=$(echo "$OUTPUT" | grep -oP '(?:written to|path:\s*|^)\K(?:.*autoinfo-rss.*\.xml)' | head -1)
if [ -z "$RSS_FILE" ]; then
    RSS_FILE=$(ls -t exports/medical-research/autoinfo-rss-*.xml 2>/dev/null | head -1)
fi

[ -n "$RSS_FILE" ] \
  && echo "  ✅ PASS: RSS file identified: $RSS_FILE" \
  || { echo "  ❌ FAIL: no RSS export file found"; ALL_PASS=false; }

[ -f "$RSS_FILE" ] && [ -s "$RSS_FILE" ] \
  && echo "  ✅ PASS: RSS file is non-empty" \
  || { echo "  ❌ FAIL: RSS file empty or missing"; ALL_PASS=false; }

if [ "$ALL_PASS" = true ]; then echo "✅ SCENARIO 56b.1 PASSED"; exit 0; else echo "❌ SCENARIO 56b.1 FAILED"; exit 1; fi
```
**Expected Result:** ✅ RSS XML file written to `exports/medical-research/autoinfo-rss-*.xml`. File non-empty.

#### 56b.2 🟢 RSS feed XML validates as RSS 2.0
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
TEST_DIR="/tmp/test-q56b"
cd "$TEST_DIR"

RSS_FILE=$(ls -t exports/medical-research/autoinfo-rss-*.xml 2>/dev/null | head -1)
if [ -z "$RSS_FILE" ]; then
    echo "  ❌ FAIL: no RSS file to validate"
    exit 1
fi

python3 -c "
import xml.etree.ElementTree as ET
tree = ET.parse('$RSS_FILE')
root = tree.getroot()
assert root.tag == 'rss', f'Expected <rss> root, got <{root.tag}>'
assert root.get('version') == '2.0', f'Expected version=2.0, got {root.get(\"version\")}'
channel = root.find('channel')
assert channel is not None, 'Missing <channel> element'
# Check required RSS channel elements
for elem_name in ['title', 'link', 'description']:
    e = channel.find(elem_name)
    assert e is not None, f'Missing <channel><{elem_name}>'
    assert e.text, f'<channel><{elem_name}> is empty'
print(f'  channel title: {channel.find(\"title\").text[:60]}')
items = channel.findall('item')
assert len(items) >= 1, 'Expected at least 1 <item> entry'
print(f'  ✅ PASS: valid RSS 2.0 with {len(items)} <item> entries')
for i, item in enumerate(items[:3]):
    for elem_name in ['title', 'link', 'description', 'guid']:
        e = item.find(elem_name)
        assert e is not None, f'<item> {i} missing <{elem_name}>'
    print(f'    item {i}: title={item.find(\"title\").text[:40]}')
" 2>&1 || { echo "  ❌ FAIL: RSS XML validation failed"; ALL_PASS=false; }

[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 56b.2 PASSED — valid RSS 2.0 XML" && exit 0
echo "❌ SCENARIO 56b.2 FAILED" && exit 1
```
**Expected Result:** ✅ Valid RSS 2.0 XML. `<rss version="2.0">` root, `<channel>` with title/link/description, `<item>` with title/link/description/guid.

#### 56b.3 🟢 RSS feed with no KB entries — graceful empty feed
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
TEST_DIR="/tmp/test-q56b-empty"
rm -rf "$TEST_DIR" && mkdir -p "$TEST_DIR" && cd "$TEST_DIR"
autoinfo init --demo medical-research 2>&1 > /dev/null

# Export RSS without collecting (KB is empty)
OUTPUT=$(autoinfo output export --domain medical-research --format rss 2>&1) || true
EXIT_CODE=$?

echo "$OUTPUT" | grep -vq "Traceback" \
  && echo "  ✅ PASS: no Python traceback on empty KB" \
  || { echo "  ❌ FAIL: traceback on empty KB RSS export"; ALL_PASS=false; }

echo "$OUTPUT" | grep -qi "rss\|written to\|export" \
  && echo "  ✅ PASS: RSS export produced output (possibly empty feed)" \
  || { echo "  ❌ FAIL: RSS export produced no output"; ALL_PASS=false; }

if [ "$ALL_PASS" = true ]; then echo "✅ SCENARIO 56b.3 PASSED — graceful empty RSS"; exit 0; else echo "❌ SCENARIO 56b.3 FAILED"; exit 1; fi
```
**Expected Result:** ✅ RSS export with empty KB does not crash. Produces output (possibly empty feed). No traceback.

### 📊 Q56b Verdict

| Scenario | Result |
|----------|--------|
| 56b.1 RSS feed generated | ⬜ |
| 56b.2 RSS XML validation | ⬜ |
| 56b.3 Empty KB RSS | ⬜ |

**OVERALL: ⬜**

---

## Q57a: Multi-Channel Delivery (C8)

**User says:** "I need to verify multi-channel delivery health and channel listing works."

### Scenarios

#### 57a.1 🟢 Channel health check via MCP (all 11 channels)
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
TEST_DIR="/tmp/test-q57a"
rm -rf "$TEST_DIR" && mkdir -p "$TEST_DIR" && cd "$TEST_DIR"
autoinfo init --demo medical-research 2>&1 > /dev/null

python3 -c "
import json
from autoinfo.mcp.server import app
result = app.call_tool('get_channel_health', {})
data = json.loads(result.content[0].text)
channels = data.get('channels', data.get('items', []))
print(f'  channel count: {len(channels)}')
expected_channels = ['smtp', 'webhook', 'rest_api', 'file_export', 'discord', 'telegram', 'wechat_work', 'wechat_oa', 'dingtalk', 'feishu', 'rss']
found = {c.get('name', c.get('channel', '?')) for c in channels}
for ch in expected_channels:
    if ch in found:
        print(f'    ✅ {ch}: present')
    else:
        print(f'    ⚠️ {ch}: not in health check')
# At minimum smtp and webhook should be present
assert 'smtp' in found or 'webhook' in found, 'No core channels in health check'
print(f'  ✅ PASS: channel health check returned {len(channels)} channels')
" 2>&1 || { echo "  ❌ FAIL: channel health check failed"; ALL_PASS=false; }

[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 57a.1 PASSED" && exit 0
echo "❌ SCENARIO 57a.1 FAILED" && exit 1
```
**Expected Result:** ✅ `get_channel_health` returns channels with health status. Core channels (smtp, webhook) present.

#### 57a.2 🟢 Multi-channel delivery list via MCP
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
TEST_DIR="/tmp/test-q57a"
cd "$TEST_DIR"

python3 -c "
import json
from autoinfo.mcp.server import app
result = app.call_tool('list_active_deliveries', {})
data = json.loads(result.content[0].text)
deliveries = data.get('deliveries', data.get('items', []))
print(f'  active deliveries: {len(deliveries)}')
print(f'  ✅ PASS: list_active_deliveries works (count={len(deliveries)})')
" 2>&1 || { echo "  ❌ FAIL: list_active_deliveries failed"; ALL_PASS=false; }

python3 -c "
import json
from autoinfo.mcp.server import app
result = app.call_tool('list_delivery_schedules', {})
data = json.loads(result.content[0].text)
schedules = data.get('schedules', data.get('items', []))
print(f'  delivery schedules: {len(schedules)}')
print(f'  ✅ PASS: list_delivery_schedules works (count={len(schedules)})')
" 2>&1 || { echo "  ❌ FAIL: list_delivery_schedules failed"; ALL_PASS=false; }

[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 57a.2 PASSED" && exit 0
echo "❌ SCENARIO 57a.2 FAILED" && exit 1
```
**Expected Result:** ✅ `list_active_deliveries` and `list_delivery_schedules` return results without error.

#### 57a.3 🟢 Delivery schedule add/list/remove lifecycle
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
TEST_DIR="/tmp/test-q57a"
cd "$TEST_DIR"

# Add delivery schedule
OUTPUT=$(autoinfo cron add-delivery --name "daily-digest-test" --domain medical-research --expression "0 8 * * *" --output-type digest --channel email 2>&1) || true
EXIT_CODE=$?

echo "$OUTPUT" | grep -qi "added\|created" \
  && echo "  ✅ PASS: delivery schedule added" \
  || { echo "  ❌ FAIL: add-delivery failed: $OUTPUT"; ALL_PASS=false; }

# List delivery schedules
LIST_OUT=$(autoinfo cron list-deliveries 2>&1) || true
echo "$LIST_OUT" | grep -qi "daily-digest-test" \
  && echo "  ✅ PASS: delivery schedule appears in list" \
  || { echo "  ❌ FAIL: delivery schedule not in list"; ALL_PASS=false; }

# Remove delivery schedule
REMOVE_OUT=$(autoinfo cron remove-delivery --name "daily-digest-test" 2>&1) || true
echo "$REMOVE_OUT" | grep -qi "removed\|deleted" \
  && echo "  ✅ PASS: delivery schedule removed" \
  || echo "  ⚠️ WARN: remove-delivery confirmation unclear"

if [ "$ALL_PASS" = true ]; then echo "✅ SCENARIO 57a.3 PASSED"; exit 0; else echo "❌ SCENARIO 57a.3 FAILED"; exit 1; fi
```
**Expected Result:** ✅ Delivery schedule add → list → remove lifecycle works. Schedule appears in list-deliveries.

### 📊 Q57a Verdict

| Scenario | Result |
|----------|--------|
| 57a.1 Channel health | ⬜ |
| 57a.2 List deliveries | ⬜ |
| 57a.3 Delivery schedule lifecycle | ⬜ |

**OVERALL: ⬜**

---

## Q57b: Webhook Push Channel (C9)

**User says:** "I need to verify webhook push works with proper HMAC validation."

### Scenarios

#### 57b.1 🟢 Webhook set with HMAC secret
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
TEST_DIR="/tmp/test-q57b"
rm -rf "$TEST_DIR" && mkdir -p "$TEST_DIR" && cd "$TEST_DIR"
autoinfo init --demo medical-research 2>&1 > /dev/null

python3 -c "
import json
from autoinfo.mcp.server import app
result = app.call_tool('set_domain_webhooks', {
    'domain': 'medical-research',
    'webhook_urls': ['https://example.com/webhook'],
    'events': ['item_collected'],
    'hmac_secret': 'test-secret-abc123'
})
data = json.loads(result.content[0].text)
print(f'  set result: {json.dumps(data)[:200]}')
# Verify webhook was configured
r2 = app.call_tool('get_domain_webhooks', {'domain': 'medical-research'})
d2 = json.loads(r2.content[0].text)
urls = d2.get('webhook_urls', d2.get('urls', []))
assert len(urls) >= 1, 'No webhook URLs configured'
print(f'  ✅ PASS: webhook with HMAC secret set (urls={len(urls)})')
" 2>&1 || { echo "  ❌ FAIL: webhook HMAC set failed"; ALL_PASS=false; }

[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 57b.1 PASSED" && exit 0
echo "❌ SCENARIO 57b.1 FAILED" && exit 1
```
**Expected Result:** ✅ Webhook set with HMAC secret. `get_domain_webhooks` returns configured URL.

#### 57b.2 🟢 Webhook multiple events configuration
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
TEST_DIR="/tmp/test-q57b"
cd "$TEST_DIR"

python3 -c "
import json
from autoinfo.mcp.server import app
result = app.call_tool('set_domain_webhooks', {
    'domain': 'medical-research',
    'webhook_urls': ['https://example.com/webhook'],
    'events': ['item_collected', 'item_processed', 'quality_failed']
})
data = json.loads(result.content[0].text)
print(f'  set multi-event result: {json.dumps(data)[:200]}')
r2 = app.call_tool('get_domain_webhooks', {'domain': 'medical-research'})
d2 = json.loads(r2.content[0].text)
events = d2.get('events', [])
print(f'  configured events: {events}')
assert 'item_collected' in events, 'item_collected event not configured'
assert len(events) >= 1, 'No events configured'
print(f'  ✅ PASS: {len(events)} webhook events configured')
" 2>&1 || { echo "  ❌ FAIL: webhook multi-event config failed"; ALL_PASS=false; }

[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 57b.2 PASSED" && exit 0
echo "❌ SCENARIO 57b.2 FAILED" && exit 1
```
**Expected Result:** ✅ Multiple webhook events (item_collected, item_processed, quality_failed) configured via `set_domain_webhooks`.

#### 57b.3 🟢 Webhook removal clears configuration
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
TEST_DIR="/tmp/test-q57b"
cd "$TEST_DIR"

python3 -c "
import json
from autoinfo.mcp.server import app
# Clear webhooks
result = app.call_tool('set_domain_webhooks', {
    'domain': 'medical-research',
    'webhook_urls': [],
    'events': []
})
data = json.loads(result.content[0].text)
print(f'  clear result: {json.dumps(data)[:200]}')
r2 = app.call_tool('get_domain_webhooks', {'domain': 'medical-research'})
d2 = json.loads(r2.content[0].text)
urls = d2.get('webhook_urls', d2.get('urls', []))
events = d2.get('events', [])
assert len(urls) == 0, f'URLs not cleared: {urls}'
assert len(events) == 0, f'Events not cleared: {events}'
print(f'  ✅ PASS: webhooks cleared (urls={urls}, events={events})')
" 2>&1 || { echo "  ❌ FAIL: webhook removal failed"; ALL_PASS=false; }

[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 57b.3 PASSED" && exit 0
echo "❌ SCENARIO 57b.3 FAILED" && exit 1
```
**Expected Result:** ✅ Webhooks cleared by passing empty arrays. `get_domain_webhooks` returns no URLs or events after clear.

### 📊 Q57b Verdict

| Scenario | Result |
|----------|--------|
| 57b.1 Webhook HMAC set | ⬜ |
| 57b.2 Multi-event config | ⬜ |
| 57b.3 Webhook removal | ⬜ |

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
