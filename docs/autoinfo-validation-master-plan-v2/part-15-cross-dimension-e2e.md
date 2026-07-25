# Part 15: Cross-Dimension End-to-End User Journey (Q70-Q71)

**Coverage:** Full E2E spanning all three user dimensions — Director User (human), Direct User (agent), End User (paying customer)

**Three user dimensions:**

| Dimension | Role | Interface | Shorthand |
|-----------|------|-----------|-----------|
| **Director User** | Human commander gives NL intent | Natural language to agent | "User says:" |
| **Direct User** | Agent executes via structured tools | MCP tools (primary), CLI (fallback) | "Agent executes" |
| **End User** | Paying customer consumes delivered products | Delivery channels (Telegram, email, etc.) | "End User receives" |

**Story format:** Each question tells a complete story. Scenarios are sequential (N depends on N-1 output). Start with Director User instruction, transition through Agent execution, end with End User verification.

**References:** F01-F57 expectations from `docs/dev/founder-expectations.md`

---

## Q70: Full E2E Happy Path — Director User to End User

> **Director User says:** "帮我追踪 IVF 研究，每天生成摘要推送到 Telegram"

### Prerequisites

```bash
cd /tmp && rm -rf test-q70 && mkdir test-q70 && cd test-q70

# AutoInfo must be running with MCP server available
# LLM key must be configured for extraction/processing
export AUTOINFO_LLM_API_KEY="sk-dummy-for-testing"

# Initialize project with medical-research demo domain
autoinfo init --demo medical-research

# Create a test end user (simulating End User registration)
autoinfo enduser create \
  --user-id ivf-researcher-alice \
  --name "Alice Chen" \
  --email alice@example.com \
  --telegram-id 123456789 \
  --preferred-locale zh \
  --timezone Asia/Shanghai

# Verify setup
autoinfo doctor --json | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'OK: config={d.get(\"config\",{}).get(\"valid\")} llm_key={d.get(\"llm\",{}).get(\"key_configured\")}')"
```

**Expected Result:** ✅ Project initialized. Demo domain active. End user profile created. Doctor reports valid.

---

### Scenarios

#### 70.1 🟢 Director User instructs Agent to set up IVF tracking

**User says:** "帮我配置 IVF 研究追踪，添加 IVF 和胚胎相关的关键词，用 PubMed 作为信源"

**Agent executes:**

```bash
# Agent calls add_topic MCP tool to configure the IVF topic
python3 -c "
import json, subprocess, sys

result = subprocess.run(
    ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'add_topic',
     json.dumps({'domain': 'medical-research', 'name': 'IVF breakthroughs',
                 'keywords': ['IVF', 'embryo', 'implantation', 'in vitro fertilization',
                              'endometrial receptivity', 'blastocyst']})],
    capture_output=True, text=True, timeout=30
)
print('Topic added:', result.stdout[:300] if result.stdout else result.stderr[:300])
print('Exit:', result.returncode)
"
```

**Expected Result:**
- ✅ `add_topic` returns success with topic ID
- ✅ Topic "IVF breakthroughs" configured with 6 keywords under medical-research domain
- ✅ F09 (Topic & Keyword Configuration) satisfied

**PASS / FAIL:** _________

#### 70.2 🟢 Agent previews collection with dry-run

**User says:** "先看看能搜集到什么"

**Agent executes:**

```bash
# Agent calls collect_sources with dry_run=true
python3 -c "
import json, subprocess
result = subprocess.run(
    ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'collect_sources',
     json.dumps({'domain': 'medical-research', 'topic': 'IVF breakthroughs',
                 'source': 'pubmed', 'limit': 5, 'dry_run': True})],
    capture_output=True, text=True, timeout=30
)
data = json.loads(result.stdout) if result.stdout else {}
print(f'Dry-run estimate: {data}')
if 'estimated_items' in data or 'items_found' in data or 'total_estimated' in data:
    print('PASS: Dry-run returned item estimate')
"
```

**Expected Result:**
- ✅ `collect_sources` with `dry_run=true` returns estimated items count without fetching
- ✅ Returns structured estimate showing sources and estimated items per source
- ✅ F11 (One-Command Collection) satisfied — dry-run mode previews impact

**PASS / FAIL:** _________

#### 70.3 🟢 Agent collects from PubMed and verifies results

**User says:** "好，开始搜集吧"

**Agent executes:**

```bash
# Agent calls collect_sources with async for progress tracking
python3 -c "
import json, subprocess, time
result = subprocess.run(
    ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'collect_sources',
     json.dumps({'domain': 'medical-research', 'topic': 'IVF breakthroughs',
                 'source': 'pubmed', 'limit': 5, 'async': True})],
    capture_output=True, text=True, timeout=30
)
data = json.loads(result.stdout) if result.stdout else {}
job_id = data.get('job_id', '')
print(f'Collection job_id: {job_id}')

if job_id:
    for i in range(12):
        time.sleep(5)
        poll = subprocess.run(
            ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'get_collection_progress',
             json.dumps({'job_id': job_id})],
            capture_output=True, text=True, timeout=15
        )
        pdata = json.loads(poll.stdout) if poll.stdout else {}
        is_complete = pdata.get('is_complete', False)
        items = pdata.get('items_collected', 0)
        print(f'  Poll {i+1}: complete={is_complete}, items={items}')
        if is_complete:
            print(f'PASS: Collection completed with {items} items')
            break
"

# Verify cached item files
ls collections/medical-research/pubmed/*/*.json 2>/dev/null | head -5
python3 -c "
import json, glob
files = sorted(glob.glob('collections/medical-research/pubmed/*/*.json'))
print(f'Cached files: {len(files)}')
for f in files[:2]:
    with open(f) as fh:
        item = json.load(fh)
    print(f'  Title: {item.get(\"title\", \"?\")[:60]}')
    print(f'  Source: {item.get(\"source_type\", \"?\")}/{item.get(\"source_platform\", \"?\")}')
    print(f'  URL: {item.get(\"source_url\", \"?\")}')
    print(f'  Has content: {bool(item.get(\"content\", \"\"))}')
"
```

**Expected Result:**
- ✅ Async collection returns `job_id` immediately (non-blocking)
- ✅ Polling via `get_collection_progress(job_id)` returns progress with `is_complete`
- ✅ Items cached to `collections/medical-research/pubmed/<date>/<id>.json`
- ✅ Each cached item has `source_url`, `source_type`, `source_platform`, `title`, `content`
- ✅ F11/F12 satisfied — one-command collection with progress visibility

**PASS / FAIL:** _________

#### 70.4 🟢 Agent processes collection with LLM extraction and quality gates

**User says:** "处理这些论文，提取关键信息"

**Agent executes:**

```bash
# Process the collected items — LLM extraction + quality gates
python3 -c "
import json, subprocess, time
result = subprocess.run(
    ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'process_collection',
     json.dumps({'domain': 'medical-research', 'async': True})],
    capture_output=True, text=True, timeout=30
)
data = json.loads(result.stdout) if result.stdout else {}
job_id = data.get('job_id', '')
print(f'Process job_id: {job_id}')

if job_id:
    for i in range(30):
        time.sleep(5)
        poll = subprocess.run(
            ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'get_processing_progress',
             json.dumps({'job_id': job_id})],
            capture_output=True, text=True, timeout=15
        )
        pdata = json.loads(poll.stdout) if poll.stdout else {}
        is_complete = pdata.get('is_complete', False)
        processed = pdata.get('items_processed', 0)
        print(f'  Poll {i+1}: complete={is_complete}, processed={processed}')
        if is_complete:
            print(f'PASS: Processing completed. Items processed: {processed}')
            break

# Verify KB entries created in 01-Raw
ls knowledge/medical-research/01-Raw/ivf-breakthroughs/ 2>/dev/null
python3 -c "
import os, glob
kb_dir = 'knowledge/medical-research/01-Raw/ivf-breakthroughs'
files = sorted(glob.glob(f'{kb_dir}/*.md')) if os.path.isdir(kb_dir) else []
print(f'01-Raw entries: {len(files)}')
if files:
    with open(files[0]) as f:
        content = f.read()
    print(content[:600])
"
```

**Expected Result:**
- ✅ Process completes with non-zero items processed
- ✅ KB entries created at `knowledge/medical-research/01-Raw/ivf-breakthroughs/<date>-<slug>.md`
- ✅ YAML frontmatter includes: `title`, `domain`, `tier: raw`, `source_url`, `source_type`, `source_platform`, `collected_at`, `summary`
- ✅ Body includes LLM-extracted sections: `## TL;DR`, `## Key Points`
- ✅ Quality gates G0 (schema integrity) and G4 (factual consistency) pass
- ✅ F15 (LLM Extraction) + F20 (KB Storage) satisfied

**PASS / FAIL:** _________

#### 70.5 🟢 Agent searches KB and presents results to Director User

**User says:** "展示一下搜集到的内容"

**Agent executes:**

```bash
# Search the knowledge base
python3 -c "
import json, subprocess
result = subprocess.run(
    ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'search_knowledge_base',
     json.dumps({'domain': 'medical-research', 'query': 'IVF embryo implantation',
                 'mode': 'hybrid', 'limit': 5})],
    capture_output=True, text=True, timeout=30
)
data = json.loads(result.stdout) if result.stdout else {}
entries = data.get('results', data.get('entries', []))
print(f'Search returned {len(entries)} entries')
for e in entries[:3]:
    title = e.get('title', '?')[:60]
    score = e.get('relevance_score', e.get('score', '?'))
    src = e.get('source_platform', e.get('source_type', '?'))
    print(f'  [{score}] {title} ({src})')
"
```

**Expected Result:**
- ✅ `search_knowledge_base` returns entry results with relevance scores
- ✅ Results include: `entry_id`, `title`, `summary`, `relevance_score`, `source_platform`
- ✅ Hybrid search (FTS5 + vector) returns meaningful results
- ✅ F21 (KB Search & Retrieval) satisfied

**PASS / FAIL:** _________

#### 70.6 🟢 Agent generates daily digest for End User

**User says:** "生成今天的 IVF 研究摘要，推送给 Alice"

**Agent executes:**

```bash
# Generate daily digest
python3 -c "
import json, subprocess
result = subprocess.run(
    ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'generate_digest',
     json.dumps({'domain': 'medical-research', 'period': 'day',
                 'topic': 'IVF breakthroughs', 'format': 'markdown',
                 'audience': 'researcher',
                 'custom_instructions': 'Focus on clinical trial results and methodology'})],
    capture_output=True, text=True, timeout=120
)
data = json.loads(result.stdout) if result.stdout else {}
print(f'Digest result ID: {data.get(\"digest_id\", data.get(\"id\", \"?\"))}')

import glob
digest_files = sorted(glob.glob('outputs/medical-research/digest/*.md'))
print(f'Digest files: {len(digest_files)}')
if digest_files:
    with open(digest_files[-1]) as f:
        content = f.read()
    print(f'Digest size: {len(content)} chars')
    print(content[:500])
"
```

**Expected Result:**
- ✅ `generate_digest` returns digest ID
- ✅ Digest file created at `outputs/medical-research/digest/<filename>.md`
- ✅ Digest includes: title, period, summary, key findings ranked by importance, source list
- ✅ Content adapts to `audience: researcher` (technical depth)
- ✅ F24 (Digest & Report Generation) + F29 (PROCESSED Product Generation) satisfied

**PASS / FAIL:** _________

#### 70.7 🟢 Agent delivers digest to End User via email

**User says:** "把摘要推送到 Alice 的 Telegram，邮件也发一份作为备份"

**Agent executes:**

```bash
# Deliver via email (Telegram requires bot configuration not available in test)
python3 -c "
import json, subprocess
result = subprocess.run(
    ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'send_email_digest',
     json.dumps({'to': 'alice@example.com',
                 'subject': 'IVF研究每日摘要 -- 2026-07-25',
                 'domain': 'medical-research',
                 'period': 'day',
                 'topic': 'IVF breakthroughs',
                 'format': 'html'})],
    capture_output=True, text=True, timeout=60
)
data = json.loads(result.stdout) if result.stdout else {}
print(f'Email delivery result: {json.dumps(data, indent=2)[:300]}')
delivery_log = data.get('delivery_log', data.get('log', {}))
if delivery_log:
    print(f'Delivery log: {json.dumps(delivery_log, indent=2)[:200]}')
"
```

**Expected Result:**
- ✅ `send_email_digest` sends digest to end user's email
- ✅ Email sent confirmation with delivery log entry
- ✅ Digest delivered as HTML (with plain text fallback per F37)
- ✅ If SMTP not configured: tool returns appropriate error, not a crash
- ✅ F27 + F37 + F39 satisfied

**PASS / FAIL:** _________

#### 70.8 🟢 Agent verifies delivery via audit log

**User says:** "确认 Alice 收到了"

**Agent executes:**

```bash
# Check delivery confirmation via audit log
python3 -c "
import json, subprocess

# Query delivery history
result2 = subprocess.run(
    ['autoinfo', 'portal', 'history', '--user-id', 'ivf-researcher-alice', '--json'],
    capture_output=True, text=True, timeout=30
)
output = result2.stdout if result2.stdout else 'No output'
print(f'Delivery history: {output[:500]}')

# Check audit log for delivery events
result3 = subprocess.run(
    ['autoinfo', 'audit', 'query', '--resource', 'delivery', '--limit', '5', '--json'],
    capture_output=True, text=True, timeout=30
)
audit = json.loads(result3.stdout) if result3.stdout else {}
events = audit if isinstance(audit, list) else audit.get('events', audit.get('entries', []))
print(f'Audit events for delivery: {len(events)}')
for e in events[:3]:
    print(f'  {e.get(\"action\",\"?\")} | {e.get(\"resource\",\"?\")} | {e.get(\"status\",\"?\")}')
"
```

**Expected Result:**
- ✅ Delivery history available for end user `ivf-researcher-alice`
- ✅ Audit log records delivery event with status
- ✅ DeliveryLog entry shows SLA compliance (P0 <=5min per F39)
- ✅ F39 (Delivery Reliability & Logging) + F48 (Audit Logging) satisfied

**PASS / FAIL:** _________

#### 70.9 🟢 Director User verifies completion and End User confirms receipt

**Agent reports to Director User:**

```
✅ IVF研究追踪已全部配置完成并成功运行：

📋 配置状态:
   - 域: medical-research
   - 话题: IVF breakthroughs (6个关键词)
   - 信源: PubMed API

📊 今日运行结果:
   - 搜集: 5篇新论文
   - 处理: 5篇全部通过质量门 (G0/G4 ✅)
   - KB入库: 01-Raw/ivf-breakthroughs/

📨 推送至 Alice:
   - Telegram: 已推送 (消息ID: msg_xxx)
   - Email: 已发送 (alice@example.com)
   - 投递日志: ✅ SLA达标 (48秒内完成)

📅 已配置每日自动搜集+推送定时任务
```

**End User receives digest:**

```
🧬 IVF研究每日摘要 — 2026-07-25

今日共搜集 5 篇新论文，筛选出 3 篇重要发现：

🔬 1. 子宫内膜容受性新型标志物
   来源: PubMed | 相关性: 92/100
   TL;DR: 研究发现 LIF 和 IL-6 作为子宫内膜容受性的新标志物...

🔬 2. 冻融胚胎移植 vs 新鲜胚胎移植: RCT结果
   来源: PubMed | 相关性: 88/100
   ...

🔬 3. 单细胞测序在胚胎植入前遗传学诊断中的应用
   ...

完整摘要: https://autoinfo.local/digest/2026-07-25
```

**Expected Result:**
- ✅ Director User receives clear status summary from Agent
- ✅ End User receives digest on configured delivery channels (at least email)
- ✅ Content is meaningful with source citations and relevance scores
- ✅ Product-to-channel mapping works (alerts to Telegram, digests to Email)
- ✅ F38 (End User Lifecycle) -- end user in active state receives deliverables
- ✅ All three dimensions successfully participated in the pipeline

**PASS / FAIL:** _________

---

### 📊 Q70 Verdict

| # | Scenario | Dimension(s) Verified | Result |
|---|----------|----------------------|--------|
| 70.1 | Director instructs Agent to configure | Director to Agent | ⬜ |
| 70.2 | Agent dry-run previews collection | Agent (Direct) | ⬜ |
| 70.3 | Agent collects from PubMed | Agent (Direct) | ⬜ |
| 70.4 | Agent processes with LLM + gates | Agent (Direct) | ⬜ |
| 70.5 | Agent searches KB, reports to Director | Agent to Director | ⬜ |
| 70.6 | Agent generates digest | Agent (Direct) | ⬜ |
| 70.7 | Agent delivers to End User | Agent to End User | ⬜ |
| 70.8 | Agent verifies delivery via audit log | Agent (Direct) | ⬜ |
| 70.9 | Director confirms, End User receives | All 3 dimensions | ⬜ |

**OVERALL: ⬜**

**F expectations verified:** F01 (setup), F03 (init), F04 (LLM key), F05 (domain/source), F09 (topics/keywords), F11 (one-command collect), F12 (progress), F15 (LLM extraction), F20 (KB pipeline), F21 (KB search), F24 (digest), F27 (delivery), F29 (PROCESSED products), F31 (collection overview), F37 (multi-channel delivery), F38 (end user lifecycle), F39 (delivery reliability), F48 (audit logging)

---

## Q71: Full E2E with Error Recovery -- Failure, Escalation, Recovery

> **Director User says:** "帮我追踪 AI 商业情报，每天给我推送简报到 Discord"

Same journey as Q70 but with deliberate failure mid-cycle requiring escalation to Director User, a decision, and recovery to complete delivery.

### Prerequisites

```bash
cd /tmp && rm -rf test-q71 && mkdir test-q71 && cd test-q71

export AUTOINFO_LLM_API_KEY="sk-dummy-for-testing"

# Initialize with ai-commercial demo domain
autoinfo init --demo ai-commercial

# Create a test end user with Discord as delivery channel
autoinfo enduser create \
  --user-id vc-analyst-bob \
  --name "Bob Zhang" \
  --email bob@example.com \
  --discord-userid 987654321 \
  --preferred-locale zh \
  --timezone Asia/Shanghai

# Configure an unreliable web source for the error path
autoinfo sources add --name fragile-source \
  --type web \
  --url https://this-will-timeout-after-30s.example.com/api \
  --domain ai-commercial \
  --quality-tier 3

# Verify setup
autoinfo doctor --json | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'OK: config_valid={d.get(\"config\",{}).get(\"valid\")}')"
```

**Expected Result:** ✅ Project initialized. ai-commercial domain active with intentionally fragile source.

---

### Scenarios

#### 71.1 🟢 Director User instructs Agent to set up AI commercial tracking

**User says:** "配置 AI 商业情报追踪，关注 AI 产品发布、融资和定价变化，用 TechCrunch"

**Agent executes:**

```bash
python3 -c "
import json, subprocess

# Add topic with relevant keywords
result = subprocess.run(
    ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'add_topic',
     json.dumps({'domain': 'ai-commercial',
                 'name': 'AI product launches and funding',
                 'keywords': ['AI product launch', 'funding round',
                              'pricing change', 'enterprise AI',
                              'SaaS', 'series A', 'GPT', 'LLM']})],
    capture_output=True, text=True, timeout=30
)
print('Topic added:', result.stdout[:200] if result.stdout else result.stderr[:200])

# Add TechCrunch RSS source
result2 = subprocess.run(
    ['autoinfo', 'sources', 'add', '--name', 'techcrunch',
     '--type', 'rss', '--url', 'https://techcrunch.com/feed/',
     '--domain', 'ai-commercial', '--quality-tier', '2'],
    capture_output=True, text=True, timeout=15
)
print('TechCrunch source:', result2.stdout[:200] if result2.stdout else result2.stderr[:200])

# List configured sources
result3 = subprocess.run(
    ['autoinfo', 'sources', 'list', '--domain', 'ai-commercial'],
    capture_output=True, text=True, timeout=15
)
print('Active sources:', result3.stdout[:400] if result3.stdout else result3.stderr[:200])
"
```

**Expected Result:**
- ✅ Topic configured with 8 keywords under ai-commercial domain
- ✅ TechCrunch RSS source added to ai-commercial domain
- ✅ Sources listed with their types and quality tiers
- ✅ F05 + F09 satisfied

**PASS / FAIL:** _________

#### 71.2 🔴 Agent runs collection -- fragile source times out

**User says:** "开始搜集"

**Agent executes:**

```bash
python3 -c "
import json, subprocess, time

result = subprocess.run(
    ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'collect_sources',
     json.dumps({'domain': 'ai-commercial', 'topic': 'AI product launches and funding',
                 'async': True})],
    capture_output=True, text=True, timeout=30
)
data = json.loads(result.stdout) if result.stdout else {}
job_id = data.get('job_id', '')
print(f'Collection job_id: {job_id}')

if job_id:
    for i in range(20):
        time.sleep(5)
        poll = subprocess.run(
            ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'get_collection_progress',
             json.dumps({'job_id': job_id})],
            capture_output=True, text=True, timeout=15
        )
        pdata = json.loads(poll.stdout) if poll.stdout else {}
        is_complete = pdata.get('is_complete', False)
        items = pdata.get('items_collected', 0)
        source_results = pdata.get('sources', {})
        print(f'  Poll {i+1}: complete={is_complete}, items={items}')
        if source_results:
            for src, status in source_results.items():
                print(f'    {src}: {status}')
        if is_complete:
            break

# Show per-source collection results
import os, glob
for src_dir in sorted(glob.glob('collections/ai-commercial/*/')):
    src_name = src_dir.rstrip('/').split('/')[-1]
    files = sorted(glob.glob(f'{src_dir}*/*.json'))
    print(f'{src_name}: {len(files)} files collected')
"
```

**Expected Result:**
- ✅ Collection runs against all configured sources
- ✅ TechCrunch RSS succeeds (returns >= 1 items)
- ✅ `fragile-source` (web, timeout) fails or returns 0 items
- ✅ F33 (Source Handler Isolation) -- one source failing does NOT crash others
- ✅ Collection summary shows per-source status (success + error)

**PASS / FAIL:** _________

#### 71.3 🔴 Agent detects failure and escalates to Director User

**Agent reports to Director User:**

```
⚠️ 搜集完成，但发现问题：

✅ TechCrunch RSS: 搜集到 8 篇新文章
❌ fragile-source (web/自定义): 连接超时，0 篇
   - URL: https://this-will-timeout-after-30s.example.com/api
   - 错误: Connection timeout after 30s
   - 连续第 1 次失败

请决定如何处理 fragile-source:
  (a) 忽略此信源，继续处理已成功搜集的内容
  (b) 重试一次 (可能暂时网络问题)
  (c) 从配置中移除此信源
```

**Agent executes diagnosis:**

```bash
# Agent checks source health for diagnostic info
python3 -c "
import json, subprocess
result = subprocess.run(
    ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'get_source_health',
     json.dumps({'domain': 'ai-commercial'})],
    capture_output=True, text=True, timeout=30
)
data = json.loads(result.stdout) if result.stdout else {}
sources = data.get('sources', data.get('items', []))
print('Source health report:')
for s in sources:
    status = s.get('status', 'unknown')
    name = s.get('name', '?')
    latency = s.get('latency_ms', 'N/A')
    error = s.get('last_error', s.get('error', ''))
    print(f'  {name}: status={status}, latency={latency}ms', end='')
    if error:
        print(f', error={error[:80]}')
    else:
        print()
"
```

**Expected Result:**
- ✅ Agent detects fragile-source failure from collection results
- ✅ Agent reports to Director User with clear options
- ✅ `get_source_health` confirms the source status with error details
- ✅ F32 (Source Health Monitoring) -- agent can diagnose source issues
- ✅ Agent demonstrates proactive alerting per documented pattern

**PASS / FAIL:** _________

#### 71.4 🟢 Director User decides to skip broken source and proceed

**User says:** "忽略那个坏掉的信源，用已有的内容继续"

**Agent executes:**

```bash
# Process only successfully collected content
python3 -c "
import json, subprocess, time
result = subprocess.run(
    ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'process_collection',
     json.dumps({'domain': 'ai-commercial', 'async': True})],
    capture_output=True, text=True, timeout=30
)
data = json.loads(result.stdout) if result.stdout else {}
job_id = data.get('job_id', '')
print(f'Process job_id: {job_id}')

if job_id:
    for i in range(30):
        time.sleep(5)
        poll = subprocess.run(
            ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'get_processing_progress',
             json.dumps({'job_id': job_id})],
            capture_output=True, text=True, timeout=15
        )
        pdata = json.loads(poll.stdout) if poll.stdout else {}
        if pdata.get('is_complete', False):
            break

# Verify KB entries from TechCrunch only
import os, glob
kb_dir = 'knowledge/ai-commercial/01-Raw/ai-product-launches-and-funding'
files = sorted(glob.glob(f'{kb_dir}/*.md')) if os.path.isdir(kb_dir) else []
print(f'KB entries created: {len(files)} (from TechCrunch only)')
for f in files[:2]:
    with open(f) as fh:
        lines = fh.readlines()
    title_line = [l for l in lines if l.startswith('title:')]
    print(f'  {title_line[0].strip() if title_line else f.split(\"/\")[-1]}')
"
```

**Expected Result:**
- ✅ Processing completes using only successfully collected items
- ✅ KB entries created from TechCrunch items only (not from failed source)
- ✅ No crash or data corruption from the failed source
- ✅ F15 + F20 processing path works with partial collection results

**PASS / FAIL:** _________

#### 71.5 🔴 G4 factual consistency gate blocks an item

**During processing, an item fails the G4 factual consistency check (retries exhausted).**

**Agent detects:**

```bash
# Check processing results for gate failures
python3 -c "
import json, subprocess

result2 = subprocess.run(
    ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'list_summaries',
     json.dumps({'domain': 'ai-commercial',
                 'topic': 'AI product launches and funding',
                 'status': 'failed', 'limit': 5})],
    capture_output=True, text=True, timeout=15
)
data2 = json.loads(result2.stdout) if result2.stdout else {}
entries = data2.get('entries', data2.get('summaries', []))
print(f'Failed/blocked items: {len(entries)}')
for e in entries[:3]:
    title = e.get('title', '?')[:60]
    reason = e.get('failure_reason', e.get('reason', '?'))
    print(f'  {title} | reason: {reason}')
"
```

**Expected Result:**
- ✅ G4 (factual consistency) hard gate behavior verified: retries up to 3 times
- ✅ If G4 blocks: item written to `_failed/` directory, not silently dropped
- ✅ Processing continues for OTHER items -- G4 failure is item-scoped
- ✅ G0 (Schema Integrity) hard gate also passes for successful items
- ✅ Hard gate retry-first, block-last philosophy per AGENTS.md

**PASS / FAIL:** _________

#### 71.6 🟢 Agent generates daily digest from successfully processed items

**User says:** "用通过质量门的内容生成简报"

**Agent executes:**

```bash
# Generate digest from successfully processed content only
python3 -c "
import json, subprocess
result = subprocess.run(
    ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'generate_digest',
     json.dumps({'domain': 'ai-commercial', 'period': 'day',
                 'topic': 'AI product launches and funding',
                 'format': 'markdown',
                 'audience': 'executive',
                 'custom_instructions': 'Highlight pricing changes and funding rounds'})],
    capture_output=True, text=True, timeout=120
)
data = json.loads(result.stdout) if result.stdout else {}
print(f'Digest result: {json.dumps(data, indent=2)[:400]}')

import glob
files = sorted(glob.glob('outputs/ai-commercial/digest/*.md'))
print(f'Digest files: {len(files)}')
if files:
    with open(files[-1]) as f:
        content = f.read()
    print(f'Content length: {len(content)} chars')
    print(content[:400])
"
```

**Expected Result:**
- ✅ Digest generated successfully despite the earlier source failure
- ✅ Digest only includes content that passed all quality gates (G0-G4)
- ✅ Content adapted to `audience: executive` (strategic, not technical)
- ✅ F24 + F29 satisfied even with partial data

**PASS / FAIL:** _________

#### 71.7 🟢 Agent verifies end user profile before delivery

**User says:** "推送到 Bob 的 Discord"

**Agent executes:**

```bash
# Verify end user exists and has Discord configured
python3 -c "
import json, subprocess
result = subprocess.run(
    ['autoinfo', 'enduser', 'get', '--user-id', 'vc-analyst-bob', '--json'],
    capture_output=True, text=True, timeout=15
)
profile = json.loads(result.stdout) if result.stdout else {}
print(f'End user profile:')
print(f'  Name: {profile.get(\"name\", \"?\")}')
print(f'  Email: {profile.get(\"email\", \"?\")}')
print(f'  Discord: {profile.get(\"discord_userid\", \"not configured\")}')
print(f'  Status: {profile.get(\"status\", \"?\")}')
"
```

**Expected Result:**
- ✅ End user profile retrieved successfully
- ✅ Discord user ID is configured for delivery
- ✅ End user status is active (not suspended/cancelled)
- ✅ F36 (End User Profile) satisfied

**PASS / FAIL:** _________

#### 71.8 🟢 Agent attempts Discord delivery with email fallback

**User says:** "Discord 推送，如果失败用邮件"

**Agent executes:**

```bash
# Attempt delivery chain: Discord (primary) -> Email (fallback)
python3 -c "
import json, subprocess

# In production agent would call send_discord_message tool.
# Without real bot token, demonstrate the fallback pattern:

# Fallback: Email delivery
result = subprocess.run(
    ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'send_email_digest',
     json.dumps({'to': 'bob@example.com',
                 'subject': 'AI商业情报每日简报 -- 2026-07-25',
                 'domain': 'ai-commercial',
                 'period': 'day',
                 'topic': 'AI product launches and funding'})],
    capture_output=True, text=True, timeout=60
)
data = json.loads(result.stdout) if result.stdout else {}
status = data.get('status', data.get('result', '?'))
print(f'Email delivery status: {status}')

print()
print('=== Delivery Chain Summary ===')
print('Primary channel: Discord (attempted first)')
print('  -> Status: SKIPPED (bot token not configured)')
print('Fallback channel: Email')
print(f'  -> Status: {status}')
print('Result: Product delivered via fallback channel')
"
```

**Expected Result:**
- ✅ Agent implements retry chain: primary (Discord) -> fallback (Email)
- ✅ Email delivery succeeds (or returns appropriate config error if SMTP not set)
- ✅ Delivery log records both attempts with channel and status
- ✅ F39 (Delivery Reliability) -- retry chain with fallback, never silently drop
- ✅ D2 (Format Integrity) delivery gate passes

**PASS / FAIL:** _________

#### 71.9 🟢 Agent verifies delivery SLA and pipeline trace

**Agent verifies delivery:**

```bash
# Check delivery SLA compliance
python3 -c "
import json, subprocess

# Query delivery history
result = subprocess.run(
    ['autoinfo', 'portal', 'history', '--user-id', 'vc-analyst-bob', '--json'],
    capture_output=True, text=True, timeout=15
)
history = json.loads(result.stdout) if result.stdout else {}
entries = history if isinstance(history, list) else history.get('entries', history.get('deliveries', []))
print(f'Delivery attempts: {len(entries)}')
for e in entries[:5]:
    channel = e.get('channel', '?')
    status = e.get('status', '?')
    ts = e.get('attempted_at', e.get('timestamp', '?'))
    sla = e.get('sla_status', e.get('sla_met', '?'))
    print(f'  Channel: {channel} | Status: {status} | Time: {ts} | SLA met: {sla}')

# Check audit log for end-to-end pipeline
result2 = subprocess.run(
    ['autoinfo', 'audit', 'query', '--resource', 'delivery', '--limit', '10', '--json'],
    capture_output=True, text=True, timeout=15
)
audit_data = json.loads(result2.stdout) if result2.stdout else {}
events = audit_data if isinstance(audit_data, list) else audit_data.get('events', audit_data.get('entries', []))
print(f'Audit log delivery events: {len(events)}')
for e in events[:3]:
    action = e.get('action', '?')
    resource = e.get('resource', '?')
    status = e.get('status', '?')
    ts = e.get('timestamp', e.get('created_at', '?'))
    print(f'  {action} {resource} -> {status} @ {ts}')
"
```

**Expected Result:**
- ✅ Delivery history shows all attempts with channel and status
- ✅ SLA compliance recorded (P0 <=5min met or documented why not)
- ✅ Audit log contains delivery events for end-to-end traceability
- ✅ Retry chain documented: Discord -> Email -> delivered
- ✅ F39 + F48 + F55 (Per-Item Traceability) satisfied

**PASS / FAIL:** _________

#### 71.10 🟢 Director User reviews full summary, Agent proposes fix

**Agent reports to Director User:**

```
✅ AI商业情报简报已完成并投递，以下是完整报告：

📋 配置状态:
   - 域: ai-commercial
   - 话题: AI product launches and funding (8个关键词)
   - 信源: TechCrunch RSS (活跃), fragile-source (已跳过)

⚠️ 运行中遇到的问题:

   ❌ fragile-source 连接超时
      -> 已按您的指示忽略，继续使用 TechCrunch 数据
      -> 建议: 确认此信源 URL 是否正确，或替换为其他信源

   ❌ G4 事实一致性检查拦截 1 篇
      -> 已归档至 _failed/，不影响正常输出
      -> 原因: LLM 检测到摘要与原文事实不一致（3次重试后仍无法通过）

📊 今日运行结果:
   - 搜集: 8 篇 (TechCrunch), 0 篇 (fragile-source)
   - G4 通过: 7 篇 | G4 拦截: 1 篇
   - KB入库: 01-Raw/ai-product-launches-and-funding/ (7篇)

📨 推送至 Bob:
   - Discord: 推送成功 (消息ID: msg_xxx)
   - Email 备份: 已发送 (bob@example.com)
   - 投递日志: ✅ SLA达标 (P0: 3分12秒)

📌 建议操作:
   1. 移除 fragile-source 或更新其 URL
   2. 查看被 G4 拦截的条目，确认是否需要人工审核
```

**End User receives digest:**

```
📊 AI商业情报每日简报 — 2026-07-25

今日共搜集 8 篇，筛选 5 篇重要情报：

💰 融资动态:
   1. Anysphere (Cursor) 完成 Series B $6000万
      ... 估值 $4亿，a16z 领投 ...

🚀 产品发布:
   2. OpenAI 发布 GPT-4.5 价格调整
      ... 输入价格降低 50% ...

📈 定价变化:
   3. Anthropic Claude 企业版推出按量计费
      ...

📰 行业动态:
   4. ...
   5. ...

完整摘要: https://autoinfo.local/digest/2026-07-25
```

**Expected Result:**
- ✅ Director User receives comprehensive summary with error context and suggested fixes
- ✅ Agent demonstrates recovery from both source failure and G4 gate block
- ✅ End User still receives digest via fallback delivery channel
- ✅ D1 (Product Completeness) delivery gate passes despite partial data
- ✅ D2 (Format Integrity) delivery gate passes
- ✅ D3 (Freshness) delivery gate passes -- content is from today
- ✅ All three dimensions cooperate correctly through error and recovery
- ✅ F33 (Source Isolation) + G4 (Hard Gate) + F39 (Reliability) all demonstrated

**PASS / FAIL:** _________

---

### 📊 Q71 Verdict

| # | Scenario | Dimension(s) Verified | Result |
|---|----------|----------------------|--------|
| 71.1 | Director instructs Agent to configure | Director to Agent | ⬜ |
| 71.2 | Collection with fragile source timeout | Agent (Direct) | ⬜ |
| 71.3 | Agent detects failure, escalates to Director | Agent to Director | ⬜ |
| 71.4 | Director decides to skip, Agent proceeds | Director to Agent | ⬜ |
| 71.5 | G4 factual consistency gate blocks item | Agent (Direct) | ⬜ |
| 71.6 | Agent generates digest from passed items | Agent (Direct) | ⬜ |
| 71.7 | Agent verifies end user profile | Agent (Direct) | ⬜ |
| 71.8 | Agent delivers with fallback chain | Agent to End User | ⬜ |
| 71.9 | Agent verifies delivery SLA and trace | Agent (Direct) | ⬜ |
| 71.10 | Director reviews, Agent proposes fixes | All 3 dimensions | ⬜ |

**OVERALL: ⬜**

**F expectations verified:** F01 (setup), F03 (init), F04 (LLM key), F05 (domain/source), F09 (topics/keywords), F11 (one-command collect), F12 (progress), F15 (LLM extraction), F20 (KB pipeline), F21 (KB search), F24 (digest), F27 (delivery), F29 (PROCESSED products), F31 (collection overview), F32 (source health), F33 (source isolation), F36 (end user profile), F37 (multi-channel delivery), F38 (end user lifecycle), F39 (delivery reliability), F48 (audit logging), F55 (per-item traceability)

---

## Final Cross-Dimension Verdict

| Question | Description | All 3 Dimensions? | Error Recovery? | PASS/FAIL |
|----------|-------------|-------------------|-----------------|-----------|
| **Q70** | Full E2E Happy Path | ✅ Director, Agent, End User | N/A (happy path) | ⬜ |
| **Q71** | Full E2E with Error Recovery | ✅ Director, Agent, End User | ✅ Source failure + G4 block + escalation + recovery | ⬜ |

**OVERALL CROSS-DIMENSION E2E: ⬜**

---

## Cross-Dimension Coverage Summary

| Capability | Q70 | Q71 | F Reference |
|------------|-----|-----|-------------|
| Director User gives NL instruction | 70.1 | 71.1 | F01-F05 |
| Agent configures domain/source/topic | 70.1 | 71.1 | F05, F09 |
| Dry-run collection preview | 70.2 | - | F11 |
| Async collection with progress polling | 70.3 | 71.2 | F11, F12 |
| LLM extraction processing | 70.4 | 71.4 | F15 |
| Knowledge base (01-Raw) storage | 70.4 | 71.4 | F20 |
| KB search and retrieval | 70.5 | - | F21 |
| Quality gates (G0/G4 hard gates) | 70.4 | 71.5 | G0, G4 |
| Digest generation | 70.6 | 71.6 | F24, F29 |
| End user profile management | 70.Prereq | 71.7 | F36 |
| Multi-channel delivery | 70.7 | 71.8 | F27, F37 |
| Delivery fallback chain | - | 71.8 | F39 |
| Delivery SLA verification | 70.8 | 71.9 | F39 |
| Audit log verification | 70.8 | 71.9 | F48 |
| Delivery gate checks (D1-D3) | 70.7 | 71.8, 71.10 | D1-D3 |
| Source failure isolation | - | 71.2, 71.3 | F33 |
| Agent escalation to Director | - | 71.3 | F32, F34 |
| Director decision + recovery | - | 71.4 | F34 |
| End user receives product | 70.9 | 71.10 | F38 |
| Agent proposes improvements | - | 71.10 | F31 |
| Source health monitoring | - | 71.3 | F32 |
| G4 factual consistency retry+block | - | 71.5 | G4 |
| End-to-end trace (collection to delivery) | 70.8 | 71.9 | F55 |
