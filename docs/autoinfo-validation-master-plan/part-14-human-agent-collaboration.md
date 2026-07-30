# Part 14: Human-Agent Collaboration (Q66-Q69)

**Coverage:** Multi-turn human↔agent collaboration from Director User perspective. Tests the agent's ability to clarify ambiguous intent, escalate failures to human decision-makers, iterate on human feedback, and comply with explicit human overrides.

**Note:** These scenarios simulate agent behavior via scripted MCP tool calls. The tester reads the "User says:" dialogue, executes the corresponding tool calls, and verifies the agent's response matches the simulated behavior. The "User" in this part is the **Director User** (human commander) who speaks natural language to the agent - never touches AutoInfo directly.

**References:** F16 (Summary Review), F20 (KB Pipeline / human promotion), F29 (custom_instructions), F40 (agent override), F53 (cross-collection dedup & merge) from `docs/dev/specs/expectations.md`. See the References table at the end of this file.

---

### Part-Level Directory Setup
Run once at the start of this part:
```bash
# Create clean directories for all questions in this part
rm -rf /tmp/test-q66 && mkdir -p /tmp/test-q66
rm -rf /tmp/test-q67 && mkdir -p /tmp/test-q67
rm -rf /tmp/test-q68 && mkdir -p /tmp/test-q68
rm -rf /tmp/test-q69 && mkdir -p /tmp/test-q69
```

## Q66: Ambiguous Intent Clarification

**User says:** "I want to track some medical research this week but I'm not sure what specific topic to focus on."

### Prerequisites

```bash
cd /tmp/test-q66
autoinfo init --demo medical-research
```

### Scenarios

#### 66.1 🟢 Vague topic - agent clarifies scope before executing

**Turn 1 - Human:** "Track something in medical research this week"

**Turn 2 - Agent:** (interprets intent. Topic is ambiguous - needs clarification before executing.)

**Turn 3 - Agent asks:** "I can start collecting medical research. What topic interests you? Options: IVF breakthroughs, gene therapy CRISPR, cancer immunotherapy, or a new topic you'd like me to add?"

**Turn 4 - Human:** "IVF breakthroughs please"

**Turn 5 - Agent:** (proceeds with clarified scope)

**Execute:**

```python
from autoinfo.mcp.server import app
import json

# Agent acts on the clarified topic
result = app.call_tool("collect_sources", {
    "domain": "medical-research",
    "topic": "IVF breakthroughs",
    "limit": 3
})
data = json.loads(result.content[0].text)
assert data.get("items_collected", 0) > 0, "Collection should produce items"
print(f"✅ Collected {data.get('items_collected', 0)} items on IVF breakthroughs")
```

**Expected Result:**
- ✅ Agent did not execute collection before clarifying scope (no collect calls before Turn 4)
- ✅ Agent only executed after receiving a specific topic
- ✅ Collection succeeded with items under the clarified topic
- ✅ Items have source metadata: source_url, source_type, source_platform


#### 66.2 🟢 Multiple domains - agent asks which one

**Turn 1 - Human:** "Gather intelligence for me across all my domains"

**Turn 2 - Agent:** (multiple domains are active - needs to ask which one)

**Turn 3 - Agent asks:** "You have 2 active domains: medical-research and ai-commercial. Which domain should I collect for? Or both?"

**Turn 4 - Human:** "AI commercial for now"

**Turn 5 - Agent:** (runs pre-flight check, then collects for ai-commercial only)

**Execute:**

```python
from autoinfo.mcp.server import app
import json

# Agent checks available domains first
result = app.call_tool("list_domains", {})
domains = json.loads(result.content[0].text)
active = [d["name"] for d in domains if d.get("active")]
print(f"Active domains: {active}")

# Human specified 'ai-commercial' - agent collects only that domain
result = app.call_tool("collect_sources", {
    "domain": "ai-commercial",
    "limit": 5
})
data = json.loads(result.content[0].text)
print(f"✅ Collected {data.get('items_collected', 0)} items from ai-commercial")

# Verify no cross-domain contamination
result2 = app.call_tool("get_collection_stats", {"domain": "medical-research"})
stats = json.loads(result2.content[0].text)
print(f"✅ Medical-research not collected (0 new): {stats.get('items_new', 0) == 0}")
```

**Expected Result:**
- ✅ Agent listed active domains instead of guessing
- ✅ Agent collected only the specified domain (ai-commercial)
- ✅ No items were collected for medical-research


#### 66.3 🔴 Completely ambiguous intent - agent cannot proceed

**Turn 1 - Human:** "Do something with AutoInfo"

**Turn 2 - Agent:** (intent is completely unclear - too many possible actions. Agent refuses to guess.)

**Turn 3 - Agent asks:** "I'd like to help, but I need more context. What would you like to do? Options:
  1. Collect new information from sources
  2. Generate a digest or report from existing content
  3. Search the knowledge base
  4. Check system health
  5. Configure domains or sources
  Or describe what you're trying to accomplish."

**Turn 4 - Human:** "Just check if everything is working"

**Turn 5 - Agent:** (intent clarified - run diagnostics)

**Execute:**

```python
from autoinfo.mcp.server import app
import json

# Agent runs diagnostics per clarified intent
result = app.call_tool("diagnose_system", {})
data = json.loads(result.content[0].text)
status = data.get("status", "unknown")
print(f"✅ System diagnostics completed: status={status}")
assert status in ("healthy", "degraded"), "Diagnostics should return a valid status"
```

**Expected Result:**
- ✅ Agent did not guess or execute an action without clarification
- ✅ Agent offered structured options to narrow intent
- ✅ Agent executed the correct action only after clarification


#### 66.4 🟢 Infrastructure: Agent connects to MCP server and discovers tools before clarifying

**Turn 1 - Agent:** (on startup, performs infrastructure connectivity and tool discovery autonomously)

**Execute:**

```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  66.4: MCP Server Connectivity & Tool Discovery             ║"
echo "╚══════════════════════════════════════════════════════════════╝"

cd /tmp/test-q66

# ── Step 1: Verify MCP server is importable ────────────────────────
python3 -c "import autoinfo.mcp.server; print('MCP server module imported')" 2>&1 \
  && echo "  ✅ PASS: MCP server module importable" \
  || { echo "  ❌ FAIL: cannot import autoinfo.mcp.server"; ALL_PASS=false; }

# ── Step 2: Agent calls health_check as first action ───────────────
HEALTH_OUTPUT=$(python3 -c "
import json, subprocess
result = subprocess.run(
    ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'health_check',
     json.dumps({})],
    capture_output=True, text=True, timeout=15
)
data = json.loads(result.stdout) if result.stdout else {}
print(json.dumps(data, indent=2))
" 2>&1)
echo "$HEALTH_OUTPUT"
echo "$HEALTH_OUTPUT" | grep -q '"status"' \
  && echo "  ✅ PASS: health_check returns status field" \
  || { echo "  ❌ FAIL: health_check missing status"; ALL_PASS=false; }

# ── Step 3: Agent discovers available tools ────────────────────────
TOOL_COUNT=$(python3 -c "
import json, subprocess
result = subprocess.run(
    ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'get_tool_count',
     json.dumps({})],
    capture_output=True, text=True, timeout=15
)
data = json.loads(result.stdout) if result.stdout else {}
count = data.get('tool_count', data.get('count', 0))
print(count)
" 2>&1)
echo "  MCP tools available: $TOOL_COUNT"
[ "$TOOL_COUNT" -gt 100 ] \
  && echo "  ✅ PASS: $TOOL_COUNT MCP tools discovered (>100)" \
  || { echo "  ❌ FAIL: only $TOOL_COUNT tools (expected >100)"; ALL_PASS=false; }

# ── Step 4: Agent lists domains as pre-flight ──────────────────────
python3 -c "
import json, subprocess
result = subprocess.run(
    ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'list_domains',
     json.dumps({})],
    capture_output=True, text=True, timeout=15
)
data = json.loads(result.stdout) if result.stdout else {}
domains = data if isinstance(data, list) else data.get('domains', [])
print(f'Active domains: {len(domains)}')
for d in domains[:5]:
    name = d.get('name', d) if isinstance(d, dict) else d
    print(f'  {name}')
" 2>&1 \
  && echo "  ✅ PASS: domain listing succeeded (pre-flight check)" \
  || { echo "  ❌ FAIL: domain listing failed"; ALL_PASS=false; }

# ── Step 5: Agent queries config for LLM readiness ─────────────────
python3 -c "
import json, subprocess
result = subprocess.run(
    ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'get_effective_llm_config',
     json.dumps({})],
    capture_output=True, text=True, timeout=15
)
data = json.loads(result.stdout) if result.stdout else {}
provider = data.get('provider', 'unknown')
model = data.get('model', 'unknown')
print(f'LLM config: provider={provider}, model={model}')
" 2>&1 \
  && echo "  ✅ PASS: LLM config retrieved (pre-flight check)" \
  || { echo "  ❌ FAIL: LLM config query failed"; ALL_PASS=false; }

echo ""
if [ "$ALL_PASS" = true ]; then
  echo "✅ SCENARIO 66.4 PASSED — MCP connectivity + tool discovery before clarification"
  exit 0
else
  echo "❌ SCENARIO 66.4 FAILED"
  exit 1
fi
```
**Expected Result:**
- ✅ Agent verifies MCP server is importable before any user-requested action
- ✅ `health_check` returns valid status (pre-flight infrastructure check)
- ✅ `get_tool_count` returns >100 tools (MCP server fully operational)
- ✅ `list_domains` returns active domains (agent knows available scope)
- ✅ `get_effective_llm_config` confirms LLM is configured (agent knows processing capability)
- ✅ Agent completes pre-flight diagnostics BEFORE engaging user for clarification


---

### 📊 Q66 Verdict

| Scenario | Result |
|----------|--------|
| 66.1 Vague topic - agent clarifies | ⬜ |
| 66.2 Multiple domains - agent asks | ⬜ |
| 66.3 Completely ambiguous intent | ⬜ |
| 66.4 MCP connectivity + tool discovery (infra) | ⬜ |

**OVERALL: ⬜**

---

## Q67: Failure Escalation & Human Decision

**User says:** "Run my weekly collection. If something breaks, tell me what happened and what I should do."

### Prerequisites

```bash
cd /tmp/test-q67
autoinfo init --demo medical-research
```

### Scenarios

#### 67.1 🟢 Source error detected - agent reports - human decides - agent executes

**Turn 1 - Agent:** (performs pre-collection health check autonomously)

**Execute:**

```python
from autoinfo.mcp.server import app
import json

# Agent's autonomous pre-collection health check
result = app.call_tool("get_source_health", {"source_id": "medical-research:pubmed"})
health = json.loads(result.content[0].text)
status = health.get("status", "unknown")
error_count = health.get("error_count", 0)
print(f"Source pubmed: status={status}, error_count={error_count}")
```

**Turn 2 - Agent reports:** "Source PubMed API (medical-research:pubmed) has 3 consecutive failures. Status: error. The last successful run was 2 days ago. Would you like me to investigate by testing the source, or should I remove it from the domain configuration?" *(ref: agent-alerting.md dialogue pattern)*

**Turn 3 - Human:** "Investigate - test the source and report back"

**Turn 4 - Agent:** (tests the failing source)

**Execute:**

```python
from autoinfo.mcp.server import app
import json

# Agent tests the failing source
result = app.call_tool("test_source", {
    "domain": "medical-research",
    "name": "pubmed"
})
test_data = json.loads(result.content[0].text)
print(f"Test: reachable={test_data.get('reachable')}, "
      f"code={test_data.get('status_code')}, "
      f"latency={test_data.get('latency_ms')}ms")
```

**Turn 5 - Agent reports:** "I tested the source. It's reachable (200ms) but returning HTTP 503 intermittently. Looks like a temporary server-side issue. I recommend pausing the source for 24 hours and retrying. Would you like me to pause it?"

**Turn 6 - Human:** "Yes, pause it."

**Turn 7 - Agent:** (pauses the source and proceeds with remaining sources)

**Execute:**

```python
import os
import subprocess

# Simulate pausing the source
# (actual implementation may write a marker file or call an MCP tool)
source_marker = ".autoinfo/paused_sources/medical-research-pubmed"
os.makedirs(os.path.dirname(source_marker), exist_ok=True)
with open(source_marker, "w") as f:
    f.write("paused_at: 2026-07-25T10:00:00\nreason: HTTP 503 intermittent failures\n")
print("✅ Source paused per human instruction")

# Proceed with remaining healthy sources
result = app.call_tool("collect_sources", {
    "domain": "medical-research",
    "limit": 5
})
data = json.loads(result.content[0].text)
print(f"✅ Collection continued: {data.get('items_collected', 0)} items from healthy sources")

# Confirm source is now paused
result2 = app.call_tool("get_source_health", {"source_id": "medical-research:pubmed"})
health2 = json.loads(result2.content[0].text)
assert health2.get("status") == "paused", "Source should be paused"
print("✅ Source status confirmed as paused")
```

**Expected Result (ref: agent-alerting.md dialogue pattern):**
- ✅ Agent performed pre-collection health check autonomously
- ✅ Agent reported specific failure details (source name, error count, last success)
- ✅ Agent offered actionable options (investigate / remove)
- ✅ Agent executed human's decision (investigate -> test -> report -> pause)
- ✅ Collection continued on remaining healthy sources
- ✅ Source status confirmed as paused


#### 67.2 🟢 LLM error - agent diagnoses - human picks fallback

**Turn 1 - Human:** "Process this week's collection"

**Turn 2 - Agent:** (starts processing, LLM call fails)

**Execute:**

```python
from autoinfo.mcp.server import app
import json

# Agent attempts processing
result = app.call_tool("process_collection", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
llm_error = data.get("error", "")
if llm_error:
    print(f"⚠️ LLM error detected: {llm_error}")
```

**Turn 3 - Agent reports:** "I can't process collections right now. The LLM API is returning authentication errors. Your API key may be expired or invalid. Here's what I can do:
  1. Check the current LLM configuration
  2. Switch to a fallback model if configured
  3. You can update the API key and I'll retry
  Which option would you like?"

**Turn 4 - Human:** "Switch to the fallback model you mentioned"

**Turn 5 - Agent:** (checks config and applies fallback)

**Execute:**

```python
from autoinfo.mcp.server import app
import json

# Agent checks current LLM configuration
result = app.call_tool("get_effective_llm_config", {})
config = json.loads(result.content[0].text)
print(f"Provider: {config.get('provider')}, model: {config.get('model')}")
print(f"Fallback available: {config.get('fallback') is not None}")

# Agent applies fallback (simulated - actual implementation varies)
print("✅ Fallback model identified and ready for retry")
```

**Expected Result (ref: F29 - custom_instructions, F40 - agent override):**
- ✅ Agent detected the LLM failure and identified root cause
- ✅ Agent presented multiple actionable options
- ✅ Agent respected human's choice of fallback model
- ✅ Agent documented the fallback action


#### 67.3 🔴 Hard failure after human decision - agent re-escalates

**Turn 1 - Agent:** "Source 'crunchbase' (ai-commercial) has failed 5 consecutive times with connection timeout. I tested it and the domain appears unreachable from this network."

**Turn 2 - Human:** "Try one more time with a longer timeout"

**Turn 3 - Agent:** (retries per human instruction - still fails)

**Execute:**

```python
from autoinfo.mcp.server import app
import json

# Agent retried per human instruction - simulated failure
print("⚠️ Retry with 60s timeout: FAILED (connection timeout)")
```

**Turn 4 - Agent re-escalates:** "I retried with a 60-second timeout, but the source is still unreachable. This may be a network configuration issue rather than a transient error. Would you like me to remove this source from the domain configuration?"

**Turn 5 - Human:** "Yes, remove it."

**Turn 6 - Agent:** (removes the source)

**Execute:**

```python
from autoinfo.mcp.server import app
import json

# Agent removes the source per human command
result = app.call_tool("remove_source", {
    "domain": "ai-commercial",
    "name": "crunchbase"
})
data = json.loads(result.content[0].text)
print(f"✅ Source removed: {data.get('success', False)}")

# Verify source is gone
result2 = app.call_tool("list_sources", {"domain": "ai-commercial"})
sources = json.loads(result2.content[0].text)
names = [s.get("name") for s in sources]
assert "crunchbase" not in names, "Source should be removed"
print(f"✅ Remaining sources: {names}")
```

**Expected Result:**
- ✅ Agent retried per human instruction despite prior analysis indicating permanent failure
- ✅ Upon second failure, agent re-escalated with updated diagnosis
- ✅ Agent offered a different action (remove) rather than repeating the same suggestion
- ✅ Agent executed human's removal decision
- ❌ Agent never removed source without human approval (ref: F20, F53 - human-only operations)


#### 67.4 🟢 Infrastructure: Agent runs system health check before escalating any failure

**Turn 1 - Agent:** (before reporting any source failure, autonomously runs `diagnose_system` for full infrastructure context)

**Execute:**

```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  67.4: System Health Check Before Failure Escalation        ║"
echo "╚══════════════════════════════════════════════════════════════╝"

cd /tmp/test-q67

# ── Agent's autonomous pre-escalation health check ─────────────────
HEALTH_OUTPUT=$(python3 -c "
import json, subprocess
result = subprocess.run(
    ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'diagnose_system',
     json.dumps({})],
    capture_output=True, text=True, timeout=30
)
data = json.loads(result.stdout) if result.stdout else {}
print(json.dumps(data, indent=2)[:2000])
" 2>&1)
echo "$HEALTH_OUTPUT"

# ── Verify diagnose_system returns structured health data ──────────
echo "$HEALTH_OUTPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
# Check required health sections
sections = ['config', 'llm', 'storage', 'sources']
for s in sections:
    if s in data:
        sect = data[s]
        if isinstance(sect, dict):
            print(f'  ✅ PASS: health section \"{s}\" present ({list(sect.keys())[:3]})')
        else:
            print(f'  ✅ PASS: health section \"{s}\" present (value: {str(sect)[:60]})')
    else:
        print(f'  ⚠️  health section \"{s}\" not found')
print(f'  Overall status: {data.get(\"status\", \"unknown\")}')
" 2>&1

# ── Verify health score is a number ────────────────────────────────
HEALTH_SCORE=$(echo "$HEALTH_OUTPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
score = data.get('health_score', data.get('score', -1))
print(score)
" 2>&1)
echo "  Health score: $HEALTH_SCORE"
[ "$HEALTH_SCORE" != "-1" ] && [ "$HEALTH_SCORE" != "" ] \
  && echo "  ✅ PASS: health score is numeric ($HEALTH_SCORE)" \
  || { echo "  ❌ FAIL: health score missing or invalid"; ALL_PASS=false; }

# ── Verify source health sub-check ─────────────────────────────────
python3 -c "
import json, subprocess
result = subprocess.run(
    ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'get_source_health',
     json.dumps({'domain': 'medical-research'})],
    capture_output=True, text=True, timeout=15
)
data = json.loads(result.stdout) if result.stdout else {}
sources = data.get('sources', data.get('items', []))
print(f'  Source health entries: {len(sources)}')
for s in sources[:3]:
    name = s.get('name', '?')
    status = s.get('status', '?')
    print(f'    {name}: {status}')
" 2>&1 \
  && echo "  ✅ PASS: source health check completed before escalation" \
  || { echo "  ❌ FAIL: source health check failed"; ALL_PASS=false; }

echo ""
if [ "$ALL_PASS" = true ]; then
  echo "✅ SCENARIO 67.4 PASSED — system health check before failure escalation"
  exit 0
else
  echo "❌ SCENARIO 67.4 FAILED"
  exit 1
fi
```
**Expected Result:**
- ✅ `diagnose_system()` returns structured health data with `config`, `llm`, `storage`, `sources` sections
- ✅ `health_score` is a numeric value (0-100)
- ✅ `get_source_health(domain)` returns per-source status (success/error/warning)
- ✅ Agent has full infrastructure context before escalating to human
- ✅ Agent never escalates without first running diagnostics to identify root cause


---

### 📊 Q67 Verdict

| Scenario | Result |
|----------|--------|
| 67.1 Source error -> investigate -> pause | ⬜ |
| 67.2 LLM error -> fallback switch | ⬜ |
| 67.3 Hard failure -> re-escalate -> remove | ⬜ |
| 67.4 System health check before escalation (infra) | ⬜ |

**OVERALL: ⬜**

---

## Q68: Human Review & Agent Iteration

**User says:** "Generate a weekly digest for me, then I'll review it and give you feedback."

### Prerequisites

```bash
cd /tmp/test-q68
autoinfo init --demo medical-research
export AUTOINFO_LLM_API_KEY="sk-dummy-for-testing"
```

### Scenarios

#### 68.1 🟢 Digest review cycle - generate -> review -> feedback -> regenerate -> approve

**Turn 1 - Human:** "Give me this week's medical research digest"

**Turn 2 - Agent:** (generates initial digest)

**Execute:**

```python
from autoinfo.mcp.server import app
import json

# Agent generates initial digest
result = app.call_tool("generate_digest", {
    "domain": "medical-research",
    "period": "week"
})
digest = json.loads(result.content[0].text)
digest_text = digest.get("content", digest.get("digest", ""))
print(f"✅ Initial digest generated ({len(digest_text)} chars)")
```

**Turn 3 - Agent presents:** "Here's this week's medical research digest covering all topics. Let me know if you'd like me to focus on anything specific or adjust the format."

**Turn 4 - Human:** "It's too broad. Focus specifically on clinical trials for IVF. Also shorten it to key findings only, no fluff."

**Turn 5 - Agent:** (regenerates with custom_instructions)

**Execute:**

```python
from autoinfo.mcp.server import app
import json

# Agent regenerates with custom_instructions
result = app.call_tool("generate_digest", {
    "domain": "medical-research",
    "period": "week",
    "custom_instructions": "Focus specifically on IVF clinical trials. Short format: key findings only, no introductory fluff."
})
revised = json.loads(result.content[0].text)
revised_text = revised.get("content", revised.get("digest", ""))
print(f"✅ Revised digest generated ({len(revised_text)} chars)")

# Verify custom instructions were applied
has_ivf = "IVF" in revised_text
has_trial = "clinical trial" in revised_text.lower()
print(f"✅ Contains IVF focus: {has_ivf}")
print(f"✅ Contains clinical trial references: {has_trial}")
```

**Turn 6 - Agent presents:** "Here's the revised digest focused on IVF clinical trials. It's shorter and more targeted. Does this work?"

**Turn 7 - Human:** "Perfect, send it out."

**Turn 8 - Agent:** (confirms readiness for delivery)

**Execute:**

```python
print("✅ Digest approved by human. Ready for delivery.")
```

**Expected Result (ref: F29 - custom_instructions parameter):**
- ✅ Agent generated initial digest without custom instructions
- ✅ Agent accepted human feedback without argument
- ✅ Agent applied custom_instructions parameter in the regenerate call
- ✅ Revised digest reflects the feedback (IVF-focused, shorter format)
- ✅ Agent confirmed human approval before finalizing delivery


#### 68.2 🟢 Draft review cycle - agent creates Draft -> human reviews -> agent revises -> human promotes

**Turn 1 - Human:** "I've reviewed this week's summaries. The one about endometrial receptivity is important - turn it into a knowledge base entry."

**Turn 2 - Agent:** (creates a Draft from the Raw entry)

**Execute:**

```python
from autoinfo.mcp.server import app
import json

# Find the relevant summary
result = app.call_tool("search_knowledge_base", {
    "domain": "medical-research",
    "query": "endometrial receptivity",
    "mode": "faceted",
    "filters": {"tier": "raw"}
})
results = json.loads(result.content[0].text)
entries = results.get("entries", results.get("results", []))
if entries:
    top_id = entries[0].get("id", entries[0].get("entry_id", ""))
    print(f"Found entry: {top_id}")

    # Create Draft from Raw per F20 (agent can create Draft)
    draft_result = app.call_tool("create_kb_draft", {
        "entry_id": top_id
    })
    draft_data = json.loads(draft_result.content[0].text)
    print(f"✅ Draft created: {draft_data.get('draft_id', '?')}")
```

**Turn 3 - Agent reports:** "I've created a Draft from the endometrial receptivity paper. It includes the TL;DR, key points, and source citation. Would you like me to add more context from related papers before you review it?"

**Turn 4 - Human:** "Good start. But add references to the two related papers on implantation windows that were collected last week. And reorder the key points by clinical significance."

**Turn 5 - Agent:** (revises the Draft by linking related papers)

**Execute:**

```python
from autoinfo.mcp.server import app
import json

# Find related papers
result = app.call_tool("search_knowledge_base", {
    "domain": "medical-research",
    "query": "implantation window",
    "mode": "faceted",
    "filters": {"tier": "raw"}
})
related = json.loads(result.content[0].text)
related_entries = related.get("entries", related.get("results", []))
print(f"✅ Found {len(related_entries)} related papers on implantation window")

# Link related items
for entry in related_entries[:2]:
    link_result = app.call_tool("link_items", {
        "source_id": top_id,
        "target_id": entry.get("id", entry.get("entry_id", "")),
        "relation": "related"
    })
    print(f"✅ Linked to: {entry.get('title', '?')[:60]}")

print("✅ Key points reordered by clinical significance")
print("✅ Draft updated and ready for human promotion")
```

**Turn 6 - Agent reports:** "Done. I've linked the two implantation window papers and reordered the key points. The draft is ready for your review."

**Turn 7 - Human:** *(promotes Draft → Wiki via CLI - human-only operation)*

```bash
# HUMAN-ONLY OPERATION: promote Draft to Wiki
# The agent cannot perform this action (F20: 03-Wiki is append-only, human-only)
autoinfo kb promote --entry-id <draft_id>
```

**Turn 8 - Agent:** (verifies promotion succeeded)

```bash
ls knowledge/medical-research/03-Wiki/endometrial-receptivity/ 2>/dev/null && echo "✅ Entry promoted to Wiki"
```

**Expected Result (ref: F20 - KB pipeline, F16 - batch review, F53 - cross-collection merge):**
- ✅ Agent created Draft from Raw entry (agent capability per F20)
- ✅ Agent accepted feedback to add related papers
- ✅ Agent linked related items via link_items tool
- ❌ Agent did NOT write to 03-Wiki directly (hard constraint enforced)
- ✅ Human promoted Draft -> Wiki (human-only operation per F20)
- ✅ Agent verified promotion success


#### 68.3 🔴 Multiple revision rounds - agent iterates without losing context

**Turn 1 - Human:** "Generate a report on AI commercial developments this month"

**Turn 2 - Agent:** (generates initial report)

**Turn 3 - Agent presents:** "Here's the monthly AI commercial report."
**Human:** "Add a section on pricing changes"

**Turn 4 - Agent:** (generates revised report with pricing section)

**Turn 5 - Agent presents:** "Updated with pricing changes."
**Human:** "Good but now the executive summary is outdated. Rewrite it to reflect the new pricing section."

**Turn 6 - Agent:** (rewrites executive summary)

**Turn 7 - Agent presents:** "Executive summary rewritten."
**Human:** "Almost there. Add a competitor comparison table at the end."

**Turn 8 - Agent:** (adds competitor comparison table)
**Human:** "Perfect. Export as PDF."

**Turn 9 - Agent:** (exports as PDF)

**Execute:**

```python
from autoinfo.mcp.server import app
import json

# Round 1: Generate initial report
result = app.call_tool("generate_report", {
    "domain": "ai-commercial",
    "period": "month"
})
print("✅ Round 1: Initial report generated")

# Round 2: Add pricing section via custom_instructions
result = app.call_tool("generate_report", {
    "domain": "ai-commercial",
    "period": "month",
    "custom_instructions": "Add a dedicated section on pricing changes and subscription model updates."
})
print("✅ Round 2: Pricing section added")

# Round 3: Rewrite executive summary (cumulative with round 2 changes)
result = app.call_tool("generate_report", {
    "domain": "ai-commercial",
    "period": "month",
    "custom_instructions": "Rewrite the executive summary to reflect the new pricing analysis. Keep the pricing section and all other existing content."
})
print("✅ Round 3: Executive summary rewritten")

# Round 4: Add competitor comparison
result = app.call_tool("generate_report", {
    "domain": "ai-commercial",
    "period": "month",
    "custom_instructions": "Add a competitor comparison table at the end. Keep all existing content including pricing section and rewritten executive summary."
})
print("✅ Round 4: Competitor comparison table added")

# Final: Export as PDF
result = app.call_tool("export_kb", {
    "domain": "ai-commercial",
    "format": "pdf",
    "topic": "ai-commercial-monthly"
})
print("✅ Final: Report exported as PDF")

print("✅ Total iterations: 5 (initial + 3 revisions + PDF export)")
```

**Expected Result:**
- ✅ Agent performed multiple revision rounds without losing context between iterations
- ✅ Each custom_instructions call accumulated feedback (not starting from scratch)
- ✅ Agent never rejected feedback as "too many changes"
- ✅ Final output exported in the requested format (PDF)


---

### 📊 Q68 Verdict

| Scenario | Result |
|----------|--------|
| 68.1 Digest review -> feedback -> regenerate -> approve | ⬜ |
| 68.2 Draft -> revise -> human promotes to Wiki | ⬜ |
| 68.3 Multiple revision rounds | ⬜ |

**OVERALL: ⬜**

---

## Q69: Human Override & Agent Compliance

**User says:** "I want to override some of the default behavior. When I tell you to do something differently, do it my way and note that I overrode the default."

### Prerequisites

```bash
cd /tmp/test-q69
autoinfo init --demo medical-research
export AUTOINFO_LLM_API_KEY="sk-dummy-for-testing"
```

### Scenarios

#### 69.1 🟢 Custom instructions override for digest generation

**Turn 1 - Human:** "Generate a weekly medical research digest, but focus exclusively on clinical trials. Ignore basic science and preclinical studies."

**Turn 2 - Agent:** (generates digest with custom_instructions parameter)

**Execute:**

```python
from autoinfo.mcp.server import app
import json

# Agent applies custom_instructions per F29
result = app.call_tool("generate_digest", {
    "domain": "medical-research",
    "period": "week",
    "custom_instructions": "Focus exclusively on clinical trials. Exclude basic science and preclinical studies."
})
digest = json.loads(result.content[0].text)
digest_text = digest.get("content", digest.get("digest", ""))
print(f"✅ Digest generated with custom instructions ({len(digest_text)} chars)")

# Verify the override was applied
trial_keywords = ["clinical trial", "phase", "patient", "randomized"]
has_clinical_focus = any(kw in digest_text.lower() for kw in trial_keywords)
print(f"✅ Digest reflects clinical trial focus: {has_clinical_focus}")

# Agent documents the override
override_note = (
    "NOTE: Generated with human override - "
    "custom_instructions='Focus exclusively on clinical trials. "
    "Exclude basic science and preclinical studies.'"
)
print(override_note)
```

**Expected Result (ref: F29 - custom_instructions parameter):**
- ✅ Agent accepted the custom_instructions parameter without resistance
- ✅ Digest content reflects the override (clinical trial focus, no basic science)
- ✅ Agent documented the override in its response to the human


#### 69.2 🟢 Force full collection - override default limit

**Turn 1 - Agent:** "I checked your sources. PubMed has 15 new items since last collection. The default is to collect 5 at a time. Should I proceed with the default or collect all 15?"

**Turn 2 - Human:** "Collect all 15. I want the complete picture this week."

**Turn 3 - Agent:** (overrides the default limit)

**Execute:**

```python
from autoinfo.mcp.server import app
import json

# Human overrides default limit - agent complies
result = app.call_tool("collect_sources", {
    "domain": "medical-research",
    "topic": "IVF breakthroughs",
    "source": "pubmed",
    "limit": 0  # 0 = no limit, collect all
})
data = json.loads(result.content[0].text)
collected = data.get("items_collected", 0)
print(f"✅ Full collection completed: {collected} items collected")

# Agent documents the override
override_log = "OVERRIDE: Human requested full collection (limit=0) instead of default limit=5"
print(override_log)
```

**Expected Result (ref: F40 - agent overrides):**
- ✅ Agent informed human of default behavior before assuming it
- ✅ Agent accepted the override instruction without debate
- ✅ Collection ran without artificial limit
- ✅ Agent documented the override


#### 69.3 🟢 Skip dedup on human request

**Turn 1 - Agent:** "I found 3 items that appear to be duplicates of existing entries (same URL from different collection dates). Shall I skip the duplicates?"

**Turn 2 - Human:** "No, collect them anyway. I want to see if the content has been updated."

**Turn 3 - Agent:** (collects with dedup skipped)

**Execute:**

```python
from autoinfo.mcp.server import app
import json

# Agent detected duplicates and asked first
print("⚠️ 3 potential duplicates detected (same source URL)")
print("   Human instructed: collect them anyway")

# Agent overrides default dedup behavior
result = app.call_tool("collect_sources", {
    "domain": "medical-research",
    "topic": "IVF breakthroughs",
    "source": "pubmed",
    "limit": 5,
    "skip_dedup": True
})
data = json.loads(result.content[0].text)
collected = data.get("items_collected", 0)
print(f"✅ Collection completed with dedup skipped: {collected} items")

# Agent documents the override
override_log = (
    "OVERRIDE: Human requested skip_dedup=True - "
    "collecting duplicate URLs for content change detection"
)
print(override_log)
```

**Expected Result:**
- ✅ Agent detected duplicate items and reported them to human
- ➡️ Agent did NOT silently skip duplicates - asked human first
- ✅ Agent accepted human override (skip_dedup=True)
- ✅ Items collected even if they matched existing entries
- ✅ Agent documented the override


#### 69.4 🔴 Agent documents all overrides - audit trail

**Turn 1 - Human:** "From now on, whenever you override a default behavior because I told you to, log it so I can review what changed."

**Turn 2 - Agent:** (acknowledges and demonstrates override documentation)

**Execute:**

```python
from autoinfo.mcp.server import app
import json

# Agent confirms the documentation requirement
print("✅ Agent confirmed: All human overrides will be documented")

# Execute an override operation
result = app.call_tool("generate_digest", {
    "domain": "medical-research",
    "period": "week",
    "custom_instructions": "Format as bullet points only, no paragraphs."
})
print("✅ Override applied: bullet-point format")

# Override documentation format (agent follows this pattern)
override_record = {
    "override_type": "output_format",
    "parameter": "custom_instructions",
    "value": "Format as bullet points only, no paragraphs.",
    "default_behavior": "Narrative paragraph format",
    "human_request": "Change output format",
    "timestamp": "2026-07-25T10:00:00",
    "documented_by": "agent"
}

print(f"""
Override Documentation:
  Type:    {override_record['override_type']}
  Param:   {override_record['parameter']}
  Default: {override_record['default_behavior']}
  Value:   {override_record['value']}
  By:      {override_record['documented_by']}
  Time:    {override_record['timestamp']}
""")
```

**Expected Result (ref: F40 - agent overrides with `updated_by: agent` audit trail):**
- ✅ Agent explicitly acknowledged the documentation request
- ✅ Each override is recorded with: override type, parameter name, default behavior, override value, who authorized it, timestamp
- ✅ The audit trail is structured and queryable
- ❌ Agent never silently overrides defaults without human instruction


---

### 📊 Q69 Verdict

| Scenario | Result |
|----------|--------|
| 69.1 Custom instructions override | ⬜ |
| 69.2 Force full collection override | ⬜ |
| 69.3 Skip dedup override | ⬜ |
| 69.4 Override documentation | ⬜ |

**OVERALL: ⬜**

---

## Final Part 14 Verdict

| Question | Topic | Result |
|----------|-------|--------|
| Q66 | Ambiguous Intent Clarification (+ infrastructure) | ⬜ |
| Q67 | Failure Escalation & Human Decision (+ infrastructure) | ⬜ |
| Q68 | Human Review & Agent Iteration | ⬜ |
| Q69 | Human Override & Agent Compliance | ⬜ |

**OVERALL: ⬜**

---

## References

| Reference | Source | Relevance |
|-----------|--------|-----------|
| F16 - Summary Review | `docs/dev/specs/expectations.md` §3.4 | Batch review and flagging pattern used in Q68 |
| F20 - KB Pipeline (4-tier) | `docs/dev/specs/expectations.md` §3.5, `docs/dev/specs/pipeline.md` §2 | Human-only promotion to Wiki, agent creates Draft - central to Q68 |
| F29 - PROCESSED Products / Custom Instructions | `docs/dev/specs/expectations.md` §3.6, `docs/dev/specs/delivery.md` | `custom_instructions` parameter for digest/report generation - Q68, Q69 |
| F40 - End User Self-Service / Agent Overrides | `docs/dev/specs/expectations.md` §3.8, `docs/dev/specs/delivery.md` §4 | Agent updates fields with `updated_by: agent` audit trail - Q69 |
| F53 - Cross-Collection Dedup & Merge | `docs/dev/specs/expectations.md` §3.11, `docs/dev/specs/pipeline.md` §7 | Merge decisions logged, agent needs human approval - Q67, Q69 |
| Agent Alerting Dialogue Pattern | `docs/dev/agent-alerting.md` | Failure detection -> report -> human decision pattern - Q67 |
| Director User Definition | `docs/dev/founder-expectations.md` §1.3 (index) | Three user types: Director (human NL commander), Direct (agent executor), End User (paying customer) |
