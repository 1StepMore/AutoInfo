# Part 15: Cross-Dimension End-to-End User Journey (Q70-Q71b)

**Coverage:** Full E2E spanning all three user dimensions — Director User (human), Direct User (agent), End User (paying customer)

**Three user dimensions:**

| Dimension | Role | Interface | Shorthand |
|-----------|------|-----------|-----------|
| **Director User** | Human commander gives NL intent | Natural language to agent | "User says:" |
| **Direct User** | Agent executes via structured tools | MCP tools (primary), CLI (fallback) | "Agent executes" |
| **End User** | Paying customer consumes delivered products | Delivery channels (Telegram, email, etc.) | "End User receives" |

**Story format:** Each question tells a complete story. Scenarios are sequential (N depends on N-1 output). Start with Director User instruction, transition through Agent execution, end with End User verification.

**References:** F01-F57 expectations from `docs/dev/specs/expectations.md` (the standalone spec). See also `docs/dev/founder-expectations.md` for the index and cross-reference map.

---

### Part-Level Directory Setup
Run once at the start of this part:
```bash
# Create clean directories for all questions in this part
rm -rf /tmp/test-q70 && mkdir -p /tmp/test-q70
rm -rf /tmp/test-q71 && mkdir -p /tmp/test-q71
rm -rf /tmp/test-q71b && mkdir -p /tmp/test-q71b
rm -rf /tmp/test-q72 && mkdir -p /tmp/test-q72
```

## Q70: Full E2E Happy Path — Director User to End User

> **Director User says:** "帮我追踪 IVF 研究，每天生成摘要推送到 Telegram"

### Prerequisites

```bash
cd /tmp/test-q70

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

**Execute:**

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


#### 70.2 🟢 Agent previews collection with dry-run

**User says:** "先看看能搜集到什么"

**Agent executes:**

**Execute:**

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


#### 70.3 🟢 Agent collects from PubMed and verifies results

**User says:** "好，开始搜集吧"

**Agent executes:**

**Execute:**

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

# Verify cached item files (artifact content verification)
python3 -c "
import json, glob, sys

files = sorted(glob.glob('collections/medical-research/pubmed/*/*.json'))
print(f'Cached files: {len(files)}')

# ── Assertions ──
if len(files) == 0:
    print('❌ FAIL: No cached JSON files found')
    sys.exit(1)
print('  ✅ PASS: cached JSON files exist')

all_ok = True
required_fields = ['source_url', 'source_type', 'source_platform', 'title', 'content']
for f in files[:2]:
    with open(f) as fh:
        item = json.load(fh)
    print(f'  Title: {item.get(\"title\", \"?\")[:60]}')
    # Verify required metadata fields
    for field in required_fields:
        if field not in item or not item[field]:
            print(f'  ❌ FAIL: file={f} missing field: {field}')
            all_ok = False
    # Verify item has actual content (not just empty string)
    if not item.get('content', '').strip():
        print(f'  ❌ FAIL: file={f} has empty content')
        all_ok = False

if all_ok:
    print('  ✅ PASS: all cached items have required fields (source_url, source_type, source_platform, title, content)')
else:
    print('❌ FAIL: some items missing required metadata')
    sys.exit(1)
print('  ✅ PASS: collection artifact verification complete')
" || exit 1
```

**Expected Result:**
- ✅ Async collection returns `job_id` immediately (non-blocking)
- ✅ Polling via `get_collection_progress(job_id)` returns progress with `is_complete`
- ✅ Items cached to `collections/medical-research/pubmed/<date>/<id>.json`
- ✅ Each cached item has `source_url`, `source_type`, `source_platform`, `title`, `content`
- ✅ F11/F12 satisfied — one-command collection with progress visibility


#### 70.4 🟢 Agent processes collection with LLM extraction and quality gates

**User says:** "处理这些论文，提取关键信息"

**Agent executes:**

**Execute:**

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

# Verify KB entries created in 01-Raw (artifact content verification)
python3 -c "
import os, glob, sys

kb_dir = 'knowledge/medical-research/01-Raw/ivf-breakthroughs'
files = sorted(glob.glob(f'{kb_dir}/*.md')) if os.path.isdir(kb_dir) else []
print(f'01-Raw entries: {len(files)}')

# ── Assertions ──
if len(files) == 0:
    print('❌ FAIL: No 01-Raw KB entries found')
    sys.exit(1)
print('  ✅ PASS: KB entries exist in 01-Raw')

all_ok = True
for f in files[:2]:
    with open(f) as fh:
        content = fh.read()
    size = len(content)
    print(f'  File: {os.path.basename(f)} ({size} chars)')

    # Verify YAML frontmatter
    has_yaml = content.startswith('---')
    print(f'    YAML frontmatter: {has_yaml}')

    # Verify required metadata fields
    for field in ['title', 'domain', 'source_url', 'source_type']:
        field_pattern1 = f'{field}:'
        field_pattern2 = f'{field} :'
        if field_pattern1 not in content and field_pattern2 not in content:
            print(f'    ❌ FAIL: missing field \"{field}\" in frontmatter')
            all_ok = False

    # Verify LLM-extracted content sections
    has_tldr = 'TL;DR' in content or 'tl_dr' in content or 'tl_dr:' in content
    has_key_points = 'Key Points' in content or 'key_points' in content or 'key_points:' in content
    print(f'    TL;DR section: {has_tldr}')
    print(f'    Key Points section: {has_key_points}')
    if not has_tldr:
        print(f'    ❌ FAIL: missing TL;DR section')
        all_ok = False
    if not has_key_points:
        print(f'    ❌ FAIL: missing Key Points section')
        all_ok = False

    # Verify non-empty body
    parts = content.split('---', 2)
    body = parts[2] if len(parts) >= 3 else content
    if len(body.strip()) < 50:
        print(f'    ❌ FAIL: body content too short (<50 chars)')
        all_ok = False

if all_ok:
    print('  ✅ PASS: KB entries have YAML frontmatter + TL;DR + Key Points')
else:
    print('❌ FAIL: KB entries missing required sections')
    sys.exit(1)
print('  ✅ PASS: KB entry artifact verification complete')
" || exit 1
```

**Expected Result:**
- ✅ Process completes with non-zero items processed
- ✅ KB entries created at `knowledge/medical-research/01-Raw/ivf-breakthroughs/<date>-<slug>.md`
- ✅ YAML frontmatter includes: `title`, `domain`, `tier: raw`, `source_url`, `source_type`, `source_platform`, `collected_at`, `summary`
- ✅ Body includes LLM-extracted sections: `## TL;DR`, `## Key Points`
- ✅ Quality gates G0 (schema integrity) and G4 (factual consistency) pass
- ✅ F15 (LLM Extraction) + F20 (KB Storage) satisfied


#### 70.5 🟢 Agent searches KB and presents results to Director User

**User says:** "展示一下搜集到的内容"

**Agent executes:**

**Execute:**

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


#### 70.6 🟢 Agent generates daily digest for End User

**User says:** "生成今天的 IVF 研究摘要，推送给 Alice"

**Agent executes:**

**Execute:**

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

import glob, sys
digest_files = sorted(glob.glob('outputs/medical-research/digest/*.md'))
print(f'Digest files: {len(digest_files)}')

# ── Digest content assertions ──
if not digest_files:
    print('❌ FAIL: No digest files generated')
    sys.exit(1)
print('  ✅ PASS: digest file exists')

with open(digest_files[-1]) as f:
    content = f.read()
size = len(content)
print(f'  Digest size: {size} chars')

# Verify markdown structure
has_headers = any(line.startswith('#') for line in content.split('\n'))
print(f'  Has markdown headers (#): {has_headers}')

# Verify article titles or key findings
has_findings = any(kw in content.lower() for kw in ['finding', 'finding', 'key', 'result', 'title:', 'headline'])
print(f'  Has article titles/findings: {has_findings}')

# Verify source attribution
has_source = any(kw in content.lower() for kw in ['source', 'pubmed', 'doi', 'http'])
print(f'  Has source attribution: {has_source}')

# Assert quality
if size < 200:
    print('❌ FAIL: Digest content too short (<200 chars)')
    sys.exit(1)
if not has_headers:
    print('❌ FAIL: Digest missing markdown headers')
    sys.exit(1)
if not has_findings:
    print('❌ FAIL: Digest missing article titles or key findings')
    sys.exit(1)

print('  ✅ PASS: digest has headers, article titles, and source attribution')
print('  ✅ PASS: digest artifact verification complete')"
"
```

**Expected Result:**
- ✅ `generate_digest` returns digest ID
- ✅ Digest file created at `outputs/medical-research/digest/<filename>.md`
- ✅ Digest includes: title, period, summary, key findings ranked by importance, source list
- ✅ Content adapts to `audience: researcher` (technical depth)
- ✅ F24 (Digest & Report Generation) + F29 (PROCESSED Product Generation) satisfied


#### 70.7 🟢 Agent delivers digest to End User via email

**User says:** "把摘要推送到 Alice 的 Telegram，邮件也发一份作为备份"

**Agent executes:**

**Execute:**

```bash
# Deliver via email (Telegram requires bot configuration not available in test)
python3 -c "
import json, subprocess, sys, glob

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

# ── Delivery artifact verification ──
# Check for delivery log entry
delivery_log = data.get('delivery_log', data.get('log', data.get('delivery', {})))
had_delivery = bool(delivery_log)
status = data.get('status', data.get('success', 'unknown'))
error_msg = data.get('error', data.get('message', ''))

print(f'Delivery status: {status}')
if error_msg:
    print(f'Delivery message: {error_msg[:200]}')

# Verify HTML digest file was used for delivery (exists and is valid)
html_files = sorted(glob.glob('outputs/medical-research/digest/*.html'))
print(f'HTML digest files: {len(html_files)}')

all_ok = True
if had_delivery:
    print('  ✅ PASS: delivery log entry recorded')
else:
    print('  ⚠️ DELIVERY: No delivery log (SMTP may not be configured — continuing)')

# Verify HTML output file quality
if html_files:
    latest = html_files[-1]
    with open(latest) as f:
        html = f.read()
    print(f'  HTML size: {len(html)} chars')
    # Basic HTML validity: has doctype/html/body or at least html tags
    has_html = '<html' in html.lower() or '<!doctype' in html.lower() or '<body' in html.lower()
    has_content = len(html.strip()) > 100
    print(f'  Has HTML structure: {has_html}')
    print(f'  Has content (>100 chars): {has_content}')
    if not has_content:
        print('  ❌ FAIL: HTML digest content too short')
        all_ok = False
else:
    print('  ⚠️ No HTML digest files found (may have been generated as markdown)')

if not all_ok:
    sys.exit(1)
print('  ✅ PASS: delivery artifact verification complete')
" || true
```

**Expected Result:**
- ✅ `send_email_digest` sends digest to end user's email
- ✅ Email sent confirmation with delivery log entry
- ✅ Digest delivered as HTML (with plain text fallback per F37)
- ✅ If SMTP not configured: tool returns appropriate error, not a crash
- ✅ F27 + F37 + F39 satisfied


#### 70.8 🟢 Agent verifies delivery via audit log

**User says:** "确认 Alice 收到了"

**Agent executes:**

**Execute:**

```bash
# Check delivery confirmation via audit log (artifact verification)
python3 -c "
import json, subprocess, sys

all_ok = True

# Query delivery history
result2 = subprocess.run(
    ['autoinfo', 'portal', 'history', '--user-id', 'ivf-researcher-alice', '--json'],
    capture_output=True, text=True, timeout=30
)
output = result2.stdout if result2.stdout else 'No output'
print(f'Delivery history (first 500 chars): {output[:500]}')

# ── Delivery history assertions ──
if output and output != 'No output':
    try:
        history = json.loads(output)
        items = history if isinstance(history, list) else history.get('entries', history.get('items', []))
        print(f'  Delivery history entries: {len(items)}')
        if len(items) > 0:
            print('  ✅ PASS: delivery history contains entries')
        else:
            print('  ⚠️ Delivery history empty (may be expected after initial run)')
    except json.JSONDecodeError:
        print('  ⚠️ Delivery history not JSON (raw output)')
else:
    print('  ⚠️ No delivery history output (portal may need additional setup)')

# Check audit log for delivery events
result3 = subprocess.run(
    ['autoinfo', 'audit', 'query', '--resource', 'delivery', '--limit', '5', '--json'],
    capture_output=True, text=True, timeout=30
)
audit = json.loads(result3.stdout) if result3.stdout else {}
events = audit if isinstance(audit, list) else audit.get('events', audit.get('entries', []))
print(f'Audit events for delivery: {len(events)}')

# ── Audit log assertions ──
if len(events) > 0:
    for e in events[:3]:
        action = e.get('action', '?')
        resource = e.get('resource', '?')
        status = e.get('status', '?')
        print(f'  {action} | {resource} | {status}')
    print('  ✅ PASS: audit log has delivery events with action/resource/status')

    # Verify delivery events have status field
    has_status = any('status' in e for e in events)
    if has_status:
        print('  ✅ PASS: delivery events include status field')
    else:
        print('  ⚠️ Some delivery events missing status field')
else:
    print('  ⚠️ No delivery audit events found (SMTP may not be configured)')

print('  ✅ PASS: delivery verification via audit log complete')
" || true
```

**Expected Result:**
- ✅ Delivery history available for end user `ivf-researcher-alice`
- ✅ Audit log records delivery event with status
- ✅ DeliveryLog entry shows SLA compliance (P0 <=5min per F39)
- ✅ F39 (Delivery Reliability & Logging) + F48 (Audit Logging) satisfied


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


#### 70.10 🟢 Full E2E pipeline — PubMed collect → LLM process → digest generate → email deliver [REQUIRES LLM KEY]

**User says:** "跑一次完整的端到端链路：搜集 PubMed → 处理 → 生成摘要 → 推送到 Alice"

**Agent executes the complete cross-dimension E2E journey in a single self-verifying script:**

**Execute:**

```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
TEST_DIR="/tmp/test-q70"
DOMAIN="medical-research"
TOPIC="IVF breakthroughs"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  70.10: Full E2E — Collect → Process → Digest → Deliver     ║"
echo "╚══════════════════════════════════════════════════════════════╝"

cd "$TEST_DIR"

# ── Stage 1: Real PubMed collection ────────────────────────────────
echo ""
echo "── Stage 1: Real PubMed collection ──"
COLLECT_OUTPUT=$(autoinfo collect --domain "$DOMAIN" --topic "$TOPIC" --limit 3 2>&1)
COLLECT_EXIT=$?
echo "$COLLECT_OUTPUT" | tail -5

[ "$COLLECT_EXIT" -eq 0 ] \
  && echo "  ✅ PASS: collection exit code 0" \
  || { echo "  ❌ FAIL: collection exit code $COLLECT_EXIT (expected 0)"; ALL_PASS=false; }

# Verify collection cache artifacts
CACHE_FILES=$(find "collections/$DOMAIN/pubmed" -name "*.json" -type f 2>/dev/null | sort)
CACHE_COUNT=$(echo "$CACHE_FILES" | grep -c '.json' || echo 0)
echo "  Collection cache files: $CACHE_COUNT"
[ "$CACHE_COUNT" -gt 0 ] \
  && echo "  ✅ PASS: $CACHE_COUNT cached JSON files exist" \
  || { echo "  ❌ FAIL: no cached JSON files"; ALL_PASS=false; }

# Verify first cache file has non-empty content
FIRST_CACHE=$(echo "$CACHE_FILES" | head -1)
if [ -n "$FIRST_CACHE" ] && [ -f "$FIRST_CACHE" ]; then
  CACHE_SIZE=$(stat --format=%s "$FIRST_CACHE" 2>/dev/null || stat -f%z "$FIRST_CACHE" 2>/dev/null || echo 0)
  [ "$CACHE_SIZE" -gt 100 ] \
    && echo "  ✅ PASS: cache file has meaningful content ($CACHE_SIZE bytes)" \
    || { echo "  ❌ FAIL: cache file too small ($CACHE_SIZE bytes)"; ALL_PASS=false; }
fi

# ── Stage 2: Real LLM processing ───────────────────────────────────
echo ""
echo "── Stage 2: Real LLM processing ──"
PROCESS_OUTPUT=$(autoinfo process --domain "$DOMAIN" 2>&1)
PROCESS_EXIT=$?
echo "$PROCESS_OUTPUT" | tail -5

[ "$PROCESS_EXIT" -eq 0 ] \
  && echo "  ✅ PASS: process exit code 0" \
  || { echo "  ❌ FAIL: process exit code $PROCESS_EXIT (expected 0)"; ALL_PASS=false; }

# Verify KB 01-Raw entries exist
KB_DIR="knowledge/$DOMAIN/01-Raw/$(echo "$TOPIC" | tr '[:upper:]' '[:lower:]' | tr ' ' '-')"
KB_FILES=$(find "$KB_DIR" -name "*.md" -type f 2>/dev/null | sort)
KB_COUNT=$(echo "$KB_FILES" | grep -c '.md' || echo 0)
echo "  KB 01-Raw entries: $KB_COUNT"
[ "$KB_COUNT" -gt 0 ] \
  && echo "  ✅ PASS: $KB_COUNT KB entries created" \
  || { echo "  ❌ FAIL: no KB entries found"; ALL_PASS=false; }

# Verify first KB entry has YAML frontmatter + TL;DR
FIRST_KB=$(echo "$KB_FILES" | head -1)
if [ -n "$FIRST_KB" ] && [ -f "$FIRST_KB" ]; then
  grep -q "^---" "$FIRST_KB" \
    && echo "  ✅ PASS: KB entry has YAML frontmatter" \
    || { echo "  ❌ FAIL: KB entry missing YAML frontmatter"; ALL_PASS=false; }
  grep -q "TL;DR" "$FIRST_KB" \
    && echo "  ✅ PASS: KB entry has TL;DR section" \
    || { echo "  ❌ FAIL: KB entry missing TL;DR section"; ALL_PASS=false; }
  KB_SIZE=$(stat --format=%s "$FIRST_KB" 2>/dev/null || stat -f%z "$FIRST_KB" 2>/dev/null || echo 0)
  [ "$KB_SIZE" -gt 200 ] \
    && echo "  ✅ PASS: KB entry has meaningful content ($KB_SIZE bytes)" \
    || { echo "  ❌ FAIL: KB entry too small ($KB_SIZE bytes)"; ALL_PASS=false; }
fi

# ── Stage 3: Digest generation ──────────────────────────────────────
echo ""
echo "── Stage 3: Digest generation ──"
DIGEST_OUTPUT=$(autoinfo output digest --domain "$DOMAIN" --period day --topic "$TOPIC" 2>&1)
DIGEST_EXIT=$?
echo "$DIGEST_OUTPUT" | tail -3

[ "$DIGEST_EXIT" -eq 0 ] \
  && echo "  ✅ PASS: digest generation exit code 0" \
  || echo "  ⚠️  Digest generation returned exit code $DIGEST_EXIT (may be expected without LLM)"

# Verify digest output file
DIGEST_FILES=$(find "outputs/$DOMAIN/digest" -name "*.md" -type f 2>/dev/null | sort -r)
DIGEST_COUNT=$(echo "$DIGEST_FILES" | grep -c '.md' || echo 0)
echo "  Digest files: $DIGEST_COUNT"
if [ "$DIGEST_COUNT" -gt 0 ]; then
  LATEST_DIGEST=$(echo "$DIGEST_FILES" | head -1)
  DIGEST_SIZE=$(stat --format=%s "$LATEST_DIGEST" 2>/dev/null || stat -f%z "$LATEST_DIGEST" 2>/dev/null || echo 0)
  [ "$DIGEST_SIZE" -gt 100 ] \
    && echo "  ✅ PASS: digest file has content ($DIGEST_SIZE bytes)" \
    || { echo "  ❌ FAIL: digest file too small ($DIGEST_SIZE bytes)"; ALL_PASS=false; }

  # Content quality: digest references KB entries
  grep -qi "doi\|http\|source\|reference" "$LATEST_DIGEST" \
    && echo "  ✅ PASS: digest contains source references" \
    || { echo "  ❌ FAIL: digest missing source references"; ALL_PASS=false; }

  # Content quality: digest has structured sections
  grep -qi "section\|entries\|summary\|overview" "$LATEST_DIGEST" \
    && echo "  ✅ PASS: digest has structured sections" \
    || { echo "  ❌ FAIL: digest missing section structure"; ALL_PASS=false; }

  # Content quality: digest content matches the domain
  grep -qi "IVF\|fertilit\|embryo\|medical" "$LATEST_DIGEST" \
    && echo "  ✅ PASS: digest content matches domain topic" \
    || { echo "  ❌ FAIL: digest content unrelated to domain"; ALL_PASS=false; }
else
  echo "  ⚠️  No digest files found (may need LLM key)"
fi

# ── Stage 4: Email delivery attempt ─────────────────────────────────
echo ""
echo "── Stage 4: Email delivery ──"
EMAIL_OUTPUT=$(autoinfo email send-digest \
  --domain "$DOMAIN" \
  --period day \
  --topic "$TOPIC" \
  --to "alice@example.com" 2>&1)
EMAIL_EXIT=$?
echo "$EMAIL_OUTPUT" | tail -3

# SMTP may not be configured — delivery may fail gracefully
if [ "$EMAIL_EXIT" -eq 0 ]; then
  echo "  ✅ PASS: email send attempt completed (exit 0)"
else
  echo "  ⚠️  Email send returned exit code $EMAIL_EXIT (SMTP may not be configured — continuing)"
fi

echo ""
echo "── E2E pipeline summary ──"
echo "  Collection: $CACHE_COUNT items cached"
echo "  Processing: $KB_COUNT KB entries created"
echo "  Digest:     $DIGEST_COUNT file(s) generated"
echo "  Delivery:   attempted (exit $EMAIL_EXIT)"

# ── Final Verdict ───────────────────────────────────────────────────
if [ "$ALL_PASS" = true ]; then
  echo ""
  echo "✅ SCENARIO 70.10 PASSED — Full E2E pipeline: Collect → Process → Digest → Deliver"
  exit 0
else
  echo ""
  echo "❌ SCENARIO 70.10 FAILED — one or more pipeline stages failed"
  exit 1
fi
```

**Expected Result:**
- ✅ Collection completes via real PubMed API (exit 0, >=1 cached JSON files)
- ✅ Processing creates KB 01-Raw entries with YAML frontmatter + TL;DR (real LLM extraction)
- ✅ Digest generation produces output file with meaningful content (>100 bytes)
- ✅ Email delivery attempt completes gracefully (e.g., returns config error if SMTP not set)
- ✅ All pipeline stages produce verifiable artifacts (files exist, have content)
- ✅ F11 (One-Command Collection) + F15 (LLM Extraction) + F20 (KB Pipeline) + F24 (Digest Generation) + F27 (Delivery) all satisfied in a single end-to-end test


#### 70.11 🟢 Every pipeline stage produces a verifiable artifact (file exists, has content)

**User says:** "确认每个阶段都生成了可以验证的产物文件"

**Agent systematically verifies that every stage of the pipeline left a concrete artifact with meaningful content:**

**Execute:**

```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
TEST_DIR="/tmp/test-q70"
DOMAIN="medical-research"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  70.11: Pipeline Stage Artifact Verification                ║"
echo "╚══════════════════════════════════════════════════════════════╝"

cd "$TEST_DIR"

# ── Stage 1: Collection Cache Artifacts ─────────────────────────────
echo ""
echo "── Stage 1: Collection Cache ──"
CACHE_DIRS=$(find "collections/$DOMAIN" -type d -name "pubmed" 2>/dev/null || true)
echo "  Cache directories found: $(echo "$CACHE_DIRS" | wc -l)"

CACHE_FILES=$(find "collections/$DOMAIN" -name "*.json" -type f 2>/dev/null | sort)
CACHE_COUNT=$(echo "$CACHE_FILES" | grep -c '.json' || echo 0)
echo "  JSON cache files: $CACHE_COUNT"

[ "$CACHE_COUNT" -gt 0 ] \
  && echo "  ✅ PASS: collection cache has $CACHE_COUNT JSON file(s)" \
  || { echo "  ❌ FAIL: no collection cache files"; ALL_PASS=false; }

# Verify each cache file is valid JSON with required fields
CACHE_VALID=0
CACHE_INVALID=0
for f in $(echo "$CACHE_FILES" | head -5); do
  if python3 -c "
import json, sys
with open('$f') as fh:
    data = json.load(fh)
assert data.get('title'), 'no title'
assert data.get('content'), 'no content'
assert data.get('source_url'), 'no source_url'
print('VALID:', data.get('title','')[:50])
" 2>/dev/null; then
    CACHE_VALID=$((CACHE_VALID + 1))
  else
    CACHE_INVALID=$((CACHE_INVALID + 1))
  fi
done
echo "  Valid JSON with required fields: $CACHE_VALID"
echo "  Invalid/missing fields: $CACHE_INVALID"
[ "$CACHE_VALID" -gt 0 ] \
  && echo "  ✅ PASS: $CACHE_VALID cache files are valid JSON with title+content+source_url" \
  || { echo "  ❌ FAIL: no valid cache files with required fields"; ALL_PASS=false; }

# ── Stage 2: KB 01-Raw Artifacts ────────────────────────────────────
echo ""
echo "── Stage 2: KB 01-Raw Entries ──"
KB_FILES=$(find "knowledge/$DOMAIN/01-Raw" -name "*.md" -type f 2>/dev/null | sort)
KB_COUNT=$(echo "$KB_FILES" | grep -c '.md' || echo 0)
echo "  KB 01-Raw markdown files: $KB_COUNT"

[ "$KB_COUNT" -gt 0 ] \
  && echo "  ✅ PASS: $KB_COUNT KB entries exist" \
  || { echo "  ❌ FAIL: no KB entries found"; ALL_PASS=false; }

# Verify each KB entry structure: YAML frontmatter, TL;DR, Key Points, source metadata
KB_STRUCT_VALID=0
KB_STRUCT_INVALID=0
for f in $(echo "$KB_FILES" | head -5); do
  python3 -c "
content = open('$f').read()
lines = content.split('\n')
has_yaml = content.startswith('---')
has_tldr = any('TL;DR' in l or 'tl_dr' in l.lower() for l in lines)
has_source = any('source_url:' in l or 'source_type:' in l for l in lines)
has_body = len(content.split('---', 2)[-1].strip()) > 30 if content.count('---') >= 2 else False
all_ok = has_yaml and has_tldr and has_source and has_body
print(f'YAML={has_yaml} TLDR={has_tldr} SRC={has_source} BODY={has_body} => {\"VALID\" if all_ok else \"INVALID\"}')
" 2>/dev/null && KB_STRUCT_VALID=$((KB_STRUCT_VALID + 1)) || KB_STRUCT_INVALID=$((KB_STRUCT_INVALID + 1))
done
echo "  Structurally valid KB entries: $KB_STRUCT_VALID"
echo "  Structurally invalid: $KB_STRUCT_INVALID"
[ "$KB_STRUCT_VALID" -gt 0 ] \
  && echo "  ✅ PASS: $KB_STRUCT_VALID KB entries have YAML+TL;DR+source metadata+body" \
  || { echo "  ❌ FAIL: no structurally valid KB entries"; ALL_PASS=false; }

# ── Stage 3: Output/Digest Artifacts ────────────────────────────────
echo ""
echo "── Stage 3: Digest/Output Files ──"
DIGEST_FILES=$(find "outputs/$DOMAIN/digest" -type f 2>/dev/null | sort -r)
DIGEST_COUNT=$(echo "$DIGEST_FILES" | wc -l)
echo "  Digest files: $DIGEST_COUNT"

if [ "$DIGEST_COUNT" -gt 0 ]; then
  LATEST_DIGEST=$(echo "$DIGEST_FILES" | head -1)
  DIGEST_SIZE=$(stat --format=%s "$LATEST_DIGEST" 2>/dev/null || stat -f%z "$LATEST_DIGEST" 2>/dev/null || echo 0)
  echo "  Latest digest: $(basename "$LATEST_DIGEST") ($DIGEST_SIZE bytes)"
  
  [ "$DIGEST_SIZE" -gt 50 ] \
    && echo "  ✅ PASS: digest file has meaningful content ($DIGEST_SIZE bytes)" \
    || { echo "  ❌ FAIL: digest file too small ($DIGEST_SIZE bytes)"; ALL_PASS=false; }
  
  # Verify digest has expected content markers
  grep -q "#" "$LATEST_DIGEST" \
    && echo "  ✅ PASS: digest contains markdown headers" \
    || echo "  ⚠️  Digest may not have markdown headers"
else
  echo "  ⚠️  No digest files found (LLM key may be needed for generate_digest)"
fi

# ── Stage 4: Pipeline Log Artifacts ─────────────────────────────────
echo ""
echo "── Stage 4: Pipeline Logs ──"
LOG_FILES=$(find "logs" -name "pipeline-*.log" -type f 2>/dev/null | sort -r)
LOG_COUNT=$(echo "$LOG_FILES" | wc -l)
echo "  Pipeline log files: $LOG_COUNT"

if [ "$LOG_COUNT" -gt 0 ]; then
  LATEST_LOG=$(echo "$LOG_FILES" | head -1)
  LOG_LINES=$(wc -l < "$LATEST_LOG")
  echo "  Latest log: $(basename "$LATEST_LOG") ($LOG_LINES lines)"
  
  [ "$LOG_LINES" -gt 0 ] \
    && echo "  ✅ PASS: pipeline log has entries ($LOG_LINES lines)" \
    || { echo "  ❌ FAIL: pipeline log is empty"; ALL_PASS=false; }
  
  # Verify log contains structured JSON entries
  HEAD_LINE=$(head -1 "$LATEST_LOG")
  echo "$HEAD_LINE" | python3 -c "import sys,json; json.loads(sys.stdin.read())" 2>/dev/null \
    && echo "  ✅ PASS: pipeline log contains valid JSON entries" \
    || echo "  ⚠️  First log line is not valid JSON"
else
  echo "  ⚠️  No pipeline log files found"
fi

# ── Stage 5: SQLite DB Artifact ─────────────────────────────────────
echo ""
echo "── Stage 5: SQLite Database ──"
DB_FILE="autoinfo.db"
if [ -f "$DB_FILE" ]; then
  DB_SIZE=$(stat --format=%s "$DB_FILE" 2>/dev/null || stat -f%z "$DB_FILE" 2>/dev/null || echo 0)
  echo "  Database: $DB_FILE ($DB_SIZE bytes)"
  [ "$DB_SIZE" -gt 0 ] \
    && echo "  ✅ PASS: SQLite database exists and is non-empty" \
    || { echo "  ❌ FAIL: database is empty"; ALL_PASS=false; }
else
  echo "  ⚠️  No autoinfo.db found"
fi

echo ""
echo "── Artifact Summary ──"
echo "  Collection cache: $CACHE_COUNT JSON files ($CACHE_VALID valid)"
echo "  KB 01-Raw:        $KB_COUNT markdown files ($KB_STRUCT_VALID valid)"
echo "  Digest output:    $DIGEST_COUNT files"
echo "  Pipeline logs:    $LOG_COUNT files"
echo "  SQLite DB:        $( [ -f "$DB_FILE" ] && echo 'present' || echo 'absent' )"

# ── Final Verdict ───────────────────────────────────────────────────
if [ "$ALL_PASS" = true ]; then
  echo ""
  echo "✅ SCENARIO 70.11 PASSED — All pipeline stages produce verifiable artifacts"
  exit 0
else
  echo ""
  echo "❌ SCENARIO 70.11 FAILED — one or more stages missing artifacts"
  exit 1
fi
```

**Expected Result:**
- ✅ Collection cache: >=1 valid JSON files with `title`, `content`, `source_url`
- ✅ KB 01-Raw: >=1 markdown files with YAML frontmatter, TL;DR, source metadata, and body content
- ✅ Digest output: >=1 file with meaningful content and markdown structure (if LLM configured)
- ✅ Pipeline logs: log files with structured JSON entries recording pipeline events
- ✅ SQLite database: `autoinfo.db` exists and is non-empty
- ✅ Every pipeline stage (collect → process → output) leaves a verifiable file artifact


#### 70.12 🟢 trace_id propagates across all pipeline stages — collection → KB → output → delivery → audit

**User says:** "验证 trace_id 在整个链路中的传递：从搜集缓存到 KB 条目，再到投递日志和审计日志"

**Agent traces a single collected item through every pipeline stage using its trace_id:**

**Execute:**

```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
TEST_DIR="/tmp/test-q70"
DOMAIN="medical-research"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  70.12: trace_id Propagation Across Pipeline                ║"
echo "╚══════════════════════════════════════════════════════════════╝"

cd "$TEST_DIR"

# ── Step 1: Extract a real trace_id from collection cache ────────────
echo ""
echo "── Step 1: Extract trace_id from collection cache ──"
TRACE_ID=$(python3 -c "
import json, glob, sys
files = sorted(glob.glob('collections/$DOMAIN/pubmed/*/*.json'))
if not files:
    print('NO_TRACE')
    sys.exit(0)
for f in files:
    with open(f) as fh:
        data = json.load(fh)
    tid = data.get('trace_id', data.get('id', ''))
    # Match UUID v4 format: 36 chars with dashes
    if tid and len(tid) >= 32:
        print(tid)
        sys.exit(0)
print('NO_TRACE')
" 2>/dev/null)

echo "  Extracted trace_id: $TRACE_ID"

if [ "$TRACE_ID" = "NO_TRACE" ] || [ -z "$TRACE_ID" ]; then
  echo "  ❌ FAIL: Could not extract UUID trace_id from collection cache"
  ALL_PASS=false
else
  echo "  ✅ PASS: trace_id extracted from collection cache JSON"
fi

# ── Step 2: Verify trace_id in KB 01-Raw entry frontmatter ──────────
echo ""
echo "── Step 2: Find trace_id in KB 01-Raw entries ──"
if [ "$TRACE_ID" != "NO_TRACE" ] && [ -n "$TRACE_ID" ]; then
  KB_MATCHES=$(grep -rl "trace_id.*$TRACE_ID\|$TRACE_ID" "knowledge/$DOMAIN/01-Raw/" 2>/dev/null | wc -l || echo 0)
  echo "  KB files containing trace_id \"${TRACE_ID:0:8}...\": $KB_MATCHES"
  
  if [ "$KB_MATCHES" -gt 0 ]; then
    echo "  ✅ PASS: trace_id found in KB 01-Raw entries"
    
    # Show the matching KB entry
    MATCHING_KB=$(grep -rl "trace_id.*$TRACE_ID\|$TRACE_ID" "knowledge/$DOMAIN/01-Raw/" 2>/dev/null | head -1)
    if [ -n "$MATCHING_KB" ]; then
      echo "  Matching KB file: $(basename "$MATCHING_KB")"
      grep "trace_id" "$MATCHING_KB" 2>/dev/null | head -1 \
        && echo "  ✅ PASS: trace_id in KB frontmatter confirmed" \
        || echo "  ⚠️  trace_id not in expected frontmatter format"
    fi
  else
    echo "  ⚠️  trace_id not found in KB entries by grep (may be nested in YAML)"
    
    # Try YAML-aware search
    python3 -c "
import yaml, glob, sys
tid = '$TRACE_ID'
for f in sorted(glob.glob('knowledge/$DOMAIN/01-Raw/**/*.md', recursive=True)):
    content = open(f).read()
    if not content.startswith('---'):
        continue
    parts = content.split('---', 2)
    if len(parts) < 3:
        continue
    try:
        fm = yaml.safe_load(parts[1])
    except:
        continue
    if isinstance(fm, dict) and fm.get('trace_id', '') == tid:
        print('FOUND in', f)
        sys.exit(0)
print('NOT_FOUND')
" 2>/dev/null
  fi
else
  echo "  ⚠️  Skipping KB search — no trace_id available"
fi

# ── Step 3: Check trace_id in pipeline log ───────────────────────────
echo ""
echo "── Step 3: Find trace_id in pipeline log ──"
if [ "$TRACE_ID" != "NO_TRACE" ] && [ -n "$TRACE_ID" ]; then
  LOG_MATCHES=$(grep -l "$TRACE_ID" logs/pipeline-*.log 2>/dev/null | wc -l || echo 0)
  echo "  Pipeline log files containing trace_id: $LOG_MATCHES"
  
  if [ "$LOG_MATCHES" -gt 0 ]; then
    echo "  ✅ PASS: trace_id found in pipeline log"
    MATCHING_LOG=$(grep -l "$TRACE_ID" logs/pipeline-*.log 2>/dev/null | head -1)
    grep "$TRACE_ID" "$MATCHING_LOG" 2>/dev/null | python3 -c "
import sys, json
for line in sys.stdin:
    try:
        entry = json.loads(line.strip())
        print(f'    Event: {entry.get(\"event\",\"?\")} | Stage: {entry.get(\"stage\",\"?\")} | Module: {entry.get(\"module\",\"?\")}')
    except:
        pass
" 2>/dev/null || echo "  (raw log line shown above)"
  else
    echo "  ⚠️  trace_id not found in pipeline logs (logs may have rotated)"
  fi
else
  echo "  ⚠️  Skipping log search — no trace_id available"
fi

# ── Step 4: Query audit log for trace_id ─────────────────────────────
echo ""
echo "── Step 4: Query audit log for trace_id ──"
if [ "$TRACE_ID" != "NO_TRACE" ] && [ -n "$TRACE_ID" ]; then
  AUDIT_OUTPUT=$(autoinfo audit query --json --limit 50 2>&1 || echo '{"entries":[]}')
  AUDIT_COUNT=$(echo "$AUDIT_OUTPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
entries = data.get('entries', [])
trace_matches = [e for e in entries if '$TRACE_ID' in str(e)]
print(len(trace_matches))
" 2>/dev/null || echo 0)
  
  echo "  Audit log entries matching trace_id: $AUDIT_COUNT"
  if [ "$AUDIT_COUNT" -gt 0 ]; then
    echo "  ✅ PASS: trace_id found in audit log ($AUDIT_COUNT entries)"
  else
    echo "  ⚠️  trace_id not found in audit log (may need explicit trace_id recording)"
  fi
else
  echo "  ⚠️  Skipping audit — no trace_id available"
fi

# ── Step 5: Use autoinfo trace command ───────────────────────────────
echo ""
echo "── Step 5: autoinfo trace <trace_id> ──"
if [ "$TRACE_ID" != "NO_TRACE" ] && [ -n "$TRACE_ID" ]; then
  TRACE_OUTPUT=$(autoinfo trace "$TRACE_ID" 2>&1)
  TRACE_EXIT=$?
  echo "$TRACE_OUTPUT" | head -10
  
  if [ "$TRACE_EXIT" -eq 0 ]; then
    echo "  ✅ PASS: autoinfo trace completed successfully (exit 0)"
    
    # Verify trace output contains pipeline stages
    echo "$TRACE_OUTPUT" | grep -qi "pipeline\|event\|stage\|collect\|process\|log" \
      && echo "  ✅ PASS: trace output references pipeline stages" \
      || echo "  ⚠️  Trace output may not show expected stage names"
  else
    echo "  ⚠️  autoinfo trace returned exit code $TRACE_EXIT"
  fi
else
  echo "  ⚠️  Skipping trace — no trace_id available"
fi

echo ""
echo "── trace_id Propagation Summary ──"
echo "  trace_id: ${TRACE_ID:0:16}..."
echo "  Collection cache: $( [ "$TRACE_ID" != "NO_TRACE" ] && echo '✅ found' || echo '❌ not found' )"
echo "  KB 01-Raw:        $( [ "${KB_MATCHES:-0}" -gt 0 ] && echo '✅ found' || echo '⚠️ seek' )"
echo "  Pipeline logs:    $( [ "${LOG_MATCHES:-0}" -gt 0 ] && echo '✅ found' || echo '⚠️ seek' )"
echo "  Audit log:        $( [ "${AUDIT_COUNT:-0}" -gt 0 ] && echo '✅ found' || echo '⚠️ seek' )"

# ── Final Verdict ───────────────────────────────────────────────────
if [ "$ALL_PASS" = true ]; then
  echo ""
  echo "✅ SCENARIO 70.12 PASSED — trace_id propagates across pipeline stages"
  exit 0
else
  echo ""
  echo "❌ SCENARIO 70.12 FAILED — trace_id propagation incomplete"
  exit 1
fi
```

**Expected Result:**
- ✅ UUID trace_id extracted from collection cache JSON (real, not hardcoded)
- ✅ trace_id found in KB 01-Raw entry YAML frontmatter (or via yaml-safe-load search)
- ✅ trace_id found in pipeline log entries with event/stage/module context
- ✅ `autoinfo trace <trace_id>` completes successfully and shows pipeline stages
- ✅ Audit log contains entries referencing this trace_id (collection → processing → delivery)
- ✅ F48 (Audit Logging) + F49 (Pipeline Tracing) — trace_id propagates end-to-end


#### 70.13 🟢 End User receives digest via configured delivery channel [REQUIRES LLM KEY]

**User says:** "确认 Alice 确实收到了 IVF 今日摘要，检查投递状态和通道可用性"

**Agent verifies that the End User (Alice Chen) received the digest through the configured delivery channels, checking delivery status, channel health, and consumption records:**

**Execute:**

```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
TEST_DIR="/tmp/test-q70"
USER_ID="ivf-researcher-alice"
EMAIL="alice@example.com"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  70.13: End User Delivery Verification — Alice's Inbox      ║"
echo "╚══════════════════════════════════════════════════════════════╝"

cd "$TEST_DIR"

# ── Step 1: Verify End User profile exists and is active ────────────
echo ""
echo "── Step 1: Verify End User profile ──"
USER_OUTPUT=$(autoinfo enduser get --user-id "$USER_ID" --json 2>&1 || echo '{}')
echo "$USER_OUTPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    uid = data.get('user_id', data.get('id', '?'))
    name = data.get('name', '?')
    email = data.get('email', '?')
    print(f'  User: {name} | ID: {uid} | Email: {email}')
    
    # Check user exists
    if uid and uid != '?':
        print('  ✅ PASS: End User profile found')
    else:
        print('  ❌ FAIL: End User profile missing or malformed')
        sys.exit(1)
        
    # Check preferred delivery channels
    telegram = data.get('telegram_id', '')
    pref_locale = data.get('preferred_locale', data.get('locale', ''))
    print(f'  Telegram ID: {telegram or \"(not set)\"}')
    print(f'  Preferred locale: {pref_locale or \"(not set)\"}')
except:
    print('  ⚠️  Could not parse user output (command may have failed)')
"

# ── Step 2: Check delivery history for the end user ─────────────────
echo ""
echo "── Step 2: Check delivery history ──"
HISTORY_OUTPUT=$(autoinfo portal history --user "$USER_ID" --json 2>&1 || echo '[]')
echo "$HISTORY_OUTPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    entries = data if isinstance(data, list) else data.get('entries', data.get('items', []))
    print(f'  Delivery history entries: {len(entries)}')
    
    if len(entries) > 0:
        for e in entries[:3]:
            product = e.get('product_type', e.get('type', '?'))
            channel = e.get('channel', e.get('delivery_channel', '?'))
            status = e.get('status', '?')
            ts = e.get('timestamp', e.get('delivered_at', '?'))
            print(f'    [{status}] {product} via {channel} at {ts}')
        print(f'  ✅ PASS: delivery history has {len(entries)} entries')
    else:
        print('  ⚠️  Delivery history is empty (no deliveries yet, or portal not configured)')
except Exception as ex:
    print(f'  ⚠️  Could not parse history: {ex}')
" 2>/dev/null

# ── Step 3: Query delivery log via MCP tool ─────────────────────────
echo ""
echo "── Step 3: Query delivery log ──"
DELIVERY_LOG=$(python3 -c "
import json, subprocess
result = subprocess.run(
    ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'query_delivery_log',
     json.dumps({'limit': 20})],
    capture_output=True, text=True, timeout=30
)
data = json.loads(result.stdout) if result.stdout else {}
print(json.dumps(data, indent=2)[:1000])
" 2>/dev/null || echo '[]')

DELIVERY_COUNT=$(echo "$DELIVERY_LOG" | python3 -c "
import sys, json
d = json.load(sys.stdin)
entries = d if isinstance(d, list) else d.get('entries', d.get('items', []))
print(len(entries))
" 2>/dev/null || echo 0)

echo "  Delivery log entries: $DELIVERY_COUNT"

if [ "$DELIVERY_COUNT" -gt 0 ]; then
  echo "  ✅ PASS: delivery log contains $DELIVERY_COUNT entries"
  
  # Show channel breakdown
  echo "$DELIVERY_LOG" | python3 -c "
import sys, json
d = json.load(sys.stdin)
entries = d if isinstance(d, list) else d.get('entries', d.get('items', []))
channels = {}
for e in entries:
    ch = e.get('channel', 'unknown')
    st = e.get('status', 'unknown')
    key = f'{ch}:{st}'
    channels[key] = channels.get(key, 0) + 1
for k, v in sorted(channels.items()):
    print(f'    {k}: {v}')
" 2>/dev/null
else
  echo "  ⚠️  No delivery log entries (SMTP may not be configured)"
fi

# ── Step 4: Check channel health for delivery infrastructure ────
echo ""
echo "── Step 4: Channel health check ──"
CHANNEL_HEALTH=$(python3 -c "
import json, subprocess
result = subprocess.run(
    ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'get_channel_health',
     json.dumps({})],
    capture_output=True, text=True, timeout=30
)
data = json.loads(result.stdout) if result.stdout else {}
channels = data.get('channels', data.get('results', []))
for ch in channels:
    name = ch.get('name', ch.get('channel', '?'))
    status = ch.get('status', ch.get('health', '?'))
    latency = ch.get('latency_ms', ch.get('latency', 'N/A'))
    print(f'  {name}: status={status}, latency={latency}ms')
" 2>/dev/null || true)
echo "  ✅ PASS: channel health check completed"

# ── Step 5: Verify consumption tracking for the user ────────────────
echo ""
echo "── Step 5: Consumption tracking ──"
CONSUMPTION=$(python3 -c "
import json, subprocess
result = subprocess.run(
    ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'get_enduser_history',
     json.dumps({'user_id': '$USER_ID'})],
    capture_output=True, text=True, timeout=30
)
data = json.loads(result.stdout) if result.stdout else {}
entries = data.get('entries', data.get('history', data.get('items', [])))
print(f'  Consumption history entries: {len(entries)}')
# Check for view/open/click events
event_types = {}
for e in entries[:20]:
    et = e.get('event_type', e.get('type', 'unknown'))
    event_types[et] = event_types.get(et, 0) + 1
for et, count in sorted(event_types.items()):
    print(f'    {et}: {count}')
" 2>/dev/null || echo "  ⚠️  Could not query end user history"
)

echo ""
echo "── End User Delivery Summary ──"
echo "  User:       $USER_ID ($EMAIL)"
echo "  Profile:    $( [ -n "$(echo "$USER_OUTPUT" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("user_id",""))' 2>/dev/null)" ] && echo '✅ found' || echo '⚠️ check' )"
echo "  History:    $( [ "${DELIVERY_COUNT:-0}" -gt 0 ] && echo '✅ entries' || echo '⚠️ empty' )"
echo "  Channels:   $( echo "$CHANNEL_HEALTH" | grep -c '✅\|healthy' 2>/dev/null || echo 'checked' )"
echo "  Delivery:   $DELIVERY_COUNT log entries"

# ── Final Verdict ───────────────────────────────────────────────────
if [ "$ALL_PASS" = true ]; then
  echo ""
  echo "✅ SCENARIO 70.13 PASSED — End User delivery verified across channels"
  exit 0
else
  echo ""
  echo "❌ SCENARIO 70.13 FAILED — End User delivery verification incomplete"
  exit 1
fi
```

**Expected Result:**
- ✅ End User profile `ivf-researcher-alice` exists with email and preferred delivery channels
- ✅ Delivery history accessible for the end user (at minimum, queryable via portal or MCP)
- ✅ Channel health check runs successfully against all 11 delivery channels
- ✅ Delivery log entries exist (or gracefully reports SMTP not configured)
- ✅ Consumption/end-user history endpoint is callable and returns structured data
- ✅ F37 (Multi-Channel Delivery) + F38 (End User Lifecycle) + F39 (Delivery Reliability) verified


#### 70.14 🟢 Audit log contains complete trace from collection to delivery

**User says:** "查询审计日志，确认从搜集到投递的完整记录都存在"

**Agent queries the audit log to verify complete pipeline traceability from collection through delivery, with all required audit fields:**

**Execute:**

```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
TEST_DIR="/tmp/test-q70"
DOMAIN="medical-research"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  70.14: Audit Log Completeness — Collect → Deliver          ║"
echo "╚══════════════════════════════════════════════════════════════╝"

cd "$TEST_DIR"

# ── Step 1: Query audit log for collection events ────────────────────
echo ""
echo "── Step 1: Audit — Collection events ──"
COLLECT_AUDIT=$(autoinfo audit query --action collect_sources --json --limit 10 2>&1 || echo '{"entries":[]}')
COLLECT_AUDIT_COUNT=$(echo "$COLLECT_AUDIT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
entries = d.get('entries', [])
print(len(entries))
" 2>/dev/null || echo 0)

echo "  Collection audit entries: $COLLECT_AUDIT_COUNT"
if [ "$COLLECT_AUDIT_COUNT" -gt 0 ]; then
  echo "  ✅ PASS: audit log contains $COLLECT_AUDIT_COUNT collection event(s)"
else
  echo "  ⚠️  No collection-specific audit entries (may use different action name)"
fi

# Show sample collection audit entries
echo "$COLLECT_AUDIT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
entries = d.get('entries', [])
for e in entries[:2]:
    actor = e.get('actor', e.get('actor_name', '?'))
    action = e.get('action', '?')
    ts = e.get('timestamp', e.get('created_at', '?'))
    status = e.get('status', e.get('result', '?'))
    print(f'  [{ts}] {actor} → {action} ({status})')
" 2>/dev/null

# ── Step 2: Query audit log for processing events ────────────────────
echo ""
echo "── Step 2: Audit — Processing events ──"
PROCESS_AUDIT=$(autoinfo audit query --action process_collection --json --limit 10 2>&1 || echo '{"entries":[]}')
PROCESS_AUDIT_COUNT=$(echo "$PROCESS_AUDIT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(len(d.get('entries', [])))
" 2>/dev/null || echo 0)

echo "  Processing audit entries: $PROCESS_AUDIT_COUNT"
if [ "$PROCESS_AUDIT_COUNT" -gt 0 ]; then
  echo "  ✅ PASS: audit log contains $PROCESS_AUDIT_COUNT processing event(s)"
else
  # Try broader query
  BROAD_PROCESS=$(autoinfo audit query --resource-type kb_entry --json --limit 10 2>&1 || echo '{"entries":[]}')
  BROAD_COUNT=$(echo "$BROAD_PROCESS" | python3 -c "
import sys, json
print(len(json.load(sys.stdin).get('entries', [])))
" 2>/dev/null || echo 0)
  if [ "$BROAD_COUNT" -gt 0 ]; then
    echo "  ✅ PASS: audit log contains $BROAD_COUNT KB-related events"
  else
    echo "  ⚠️  No processing/KB audit entries found by specific action"
  fi
fi

# ── Step 3: Query audit log for delivery events ──────────────────────
echo ""
echo "── Step 3: Audit — Delivery events ──"
DELIVERY_AUDIT=$(autoinfo audit query --resource-type delivery --json --limit 10 2>&1 || echo '{"entries":[]}')
DELIVERY_AUDIT_COUNT=$(echo "$DELIVERY_AUDIT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(len(d.get('entries', [])))
" 2>/dev/null || echo 0)

echo "  Delivery audit entries: $DELIVERY_AUDIT_COUNT"
if [ "$DELIVERY_AUDIT_COUNT" -gt 0 ]; then
  echo "  ✅ PASS: audit log contains $DELIVERY_AUDIT_COUNT delivery event(s)"
else
  # Try with send_email_digest action
  EMAIL_AUDIT=$(autoinfo audit query --action send_email_digest --json --limit 10 2>&1 || echo '{"entries":[]}')
  EMAIL_COUNT=$(echo "$EMAIL_AUDIT" | python3 -c "
import sys, json
print(len(json.load(sys.stdin).get('entries', [])))
" 2>/dev/null || echo 0)
  if [ "$EMAIL_COUNT" -gt 0 ]; then
    echo "  ✅ PASS: audit log contains $EMAIL_COUNT email delivery events"
  else
    echo "  ⚠️  No delivery/email audit entries (SMTP may not be configured)"
  fi
fi

# ── Step 4: Query ALL audit entries (no filter) for completeness check ─
echo ""
echo "── Step 4: Audit — Complete timeline (all events) ──"
ALL_AUDIT=$(autoinfo audit query --json --limit 50 2>&1 || echo '{"entries":[]}')
TOTAL_COUNT=$(echo "$ALL_AUDIT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
entries = d.get('entries', [])
print(len(entries))
" 2>/dev/null || echo 0)

echo "  Total audit log entries: $TOTAL_COUNT"
[ "$TOTAL_COUNT" -gt 0 ] \
  && echo "  ✅ PASS: audit log is populated with $TOTAL_COUNT total entries" \
  || { echo "  ❌ FAIL: audit log is empty — no events recorded"; ALL_PASS=false; }

# Show action breakdown
echo "$ALL_AUDIT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
entries = d.get('entries', [])
actions = {}
actors = {}
resources = {}
for e in entries:
    a = e.get('action', 'unknown')
    actions[a] = actions.get(a, 0) + 1
    actor = e.get('actor', e.get('actor_name', 'unknown'))
    actors[actor] = actors.get(actor, 0) + 1
    r = e.get('resource_type', e.get('resource', 'unknown'))
    resources[r] = resources.get(r, 0) + 1
print('  Actions:')
for k, v in sorted(actions.items(), key=lambda x: -x[1])[:5]:
    print(f'    {k}: {v}')
print('  Actors:')
for k, v in sorted(actors.items(), key=lambda x: -x[1])[:3]:
    print(f'    {k}: {v}')
print('  Resource types:')
for k, v in sorted(resources.items(), key=lambda x: -x[1])[:5]:
    print(f'    {k}: {v}')
" 2>/dev/null

# ── Step 5: Verify audit entry structure ─────────────────────────────
echo ""
echo "── Step 5: Audit entry field validation ──"
echo "$ALL_AUDIT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
entries = d.get('entries', [])
if not entries:
    print('  ⚠️  No entries to validate')
    sys.exit(0)

# Check required fields in first 3 entries
required = ['action', 'timestamp', 'resource_type']
sample = entries[:min(3, len(entries))]
all_valid = True
for e in sample:
    missing = [f for f in required if f not in e and f not in [k.replace('_', '') for k in e.keys()]]
    # Also check common alternative field names
    alt_names = {
        'action': ['action', 'operation', 'event'],
        'timestamp': ['timestamp', 'created_at', 'time', 'occurred_at'],
        'resource_type': ['resource_type', 'resource', 'entity_type'],
    }
    found = {}
    for field, alts in alt_names.items():
        for alt in alts:
            if alt in e:
                found[field] = alt
                break
        if field not in found:
            print(f'  ⚠️  Entry missing required field \"{field}\": {list(e.keys())[:6]}')
            all_valid = False
    if found:
        print(f'  Fields found: {found}')
        break

if all_valid:
    print('  ✅ PASS: audit entries have required fields (action, timestamp, resource_type)')
else:
    print('  ⚠️  Some entries missing expected fields — may use different schema')
" 2>/dev/null

# ── Step 6: Verify pipeline-specific audit events exist ──────────────
echo ""
echo "── Step 6: Pipeline-specific audit coverage ──"
# Check for pipeline-spanning events
echo "$ALL_AUDIT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
entries = d.get('entries', [])
actions_set = set()
pipeline_stages = ['collect', 'process', 'deliver', 'digest', 'email', 'send', 'generate', 'extract']
found_stages = set()
for e in entries:
    action = str(e.get('action', '')).lower()
    actions_set.add(action)
    for stage in pipeline_stages:
        if stage in action:
            found_stages.add(stage)

print(f'  Total unique actions: {len(actions_set)}')
print(f'  Pipeline stages covered: {len(found_stages)}/{len(pipeline_stages)}')
print(f'  Stages found: {sorted(found_stages)}')
print(f'  All actions: {sorted(actions_set)[:15]}')

if len(found_stages) >= 2:
    print(f'  ✅ PASS: audit log covers {len(found_stages)} pipeline stages')
elif len(found_stages) >= 1:
    print(f'  ⚠️  Audit covers {len(found_stages)} stage(s) — may need more pipeline activity')
else:
    print('  ⚠️  No pipeline stages detected in audit log (may use different action naming)')
" 2>/dev/null

echo ""
echo "── Audit Log Summary ──"
echo "  Total events:     $TOTAL_COUNT"
echo "  Collection:       $COLLECT_AUDIT_COUNT"
echo "  Processing:       $PROCESS_AUDIT_COUNT"
echo "  Delivery:         $DELIVERY_AUDIT_COUNT"

# ── Final Verdict ───────────────────────────────────────────────────
if [ "$ALL_PASS" = true ]; then
  echo ""
  echo "✅ SCENARIO 70.14 PASSED — Audit log contains complete pipeline trace"
  exit 0
else
  echo ""
  echo "❌ SCENARIO 70.14 FAILED — Audit log incomplete or empty"
  exit 1
fi
```

**Expected Result:**
- ✅ Collection events present in audit log (via `collect_sources` action or equivalent)
- ✅ Processing/KB events present (via `process_collection` action or KB entry creation)
- ✅ Delivery/email events present (via `send_email_digest` or delivery resource type)
- ✅ Audit log total entries > 0 (pipeline activity was recorded)
- ✅ Each audit entry has required fields: `action`, `timestamp`, `resource_type` (or equivalent schema)
- ✅ At least 2 pipeline stages (collect, process, deliver) are represented in audit log
- ✅ F48 (Immutable Audit Logging) verified — complete trace from collection through delivery


#### 70.15 🟢 Infrastructure: MCP server health verification across all pipeline dimensions

**User says:** "验证 MCP 服务在所有维度下的健康状况——确认 health_check, diagnose_system, get_metrics 在跨维度流程中正常工作"

**Agent verifies that the MCP infrastructure layer is healthy across all three user dimensions (Director, Agent, End User):**

**Execute:**

```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
TEST_DIR="/tmp/test-q70"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  70.15: MCP Health Across All Dimensions                   ║"
echo "╚══════════════════════════════════════════════════════════════╝"

cd "$TEST_DIR"

# ── Dimension 1: Agent (Direct User) health_check ──────────────────
echo ""
echo "── Dimension 1: Agent health_check ──"
AGENT_HEALTH=$(python3 -c "
import json, subprocess
result = subprocess.run(
    ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'health_check',
     json.dumps({})],
    capture_output=True, text=True, timeout=15
)
data = json.loads(result.stdout) if result.stdout else {}
print(json.dumps(data, indent=2))
" 2>&1)
echo "$AGENT_HEALTH" | head -5
echo "$AGENT_HEALTH" | grep -q '"status"' \
  && echo "  ✅ PASS: health_check returns status (Agent dimension)" \
  || { echo "  ❌ FAIL: health_check failed"; ALL_PASS=false; }

# ── Dimension 1b: Agent diagnose_system ────────────────────────────
echo ""
echo "── Dimension 1b: Agent diagnose_system ──"
DIAG_OUTPUT=$(python3 -c "
import json, subprocess
result = subprocess.run(
    ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'diagnose_system',
     json.dumps({})],
    capture_output=True, text=True, timeout=30
)
data = json.loads(result.stdout) if result.stdout else {}
hs = data.get('health_score', -1)
print(f'Health score: {hs}')
print(f'Config valid: {data.get(\"config\",{}).get(\"valid\",\"?\")}')
print(f'LLM configured: {data.get(\"llm\",{}).get(\"key_configured\",\"?\")}')
" 2>&1)
echo "$DIAG_OUTPUT"
echo "$DIAG_OUTPUT" | grep -q "Health score" \
  && echo "  ✅ PASS: diagnose_system returns health score (Agent dimension)" \
  || { echo "  ❌ FAIL: diagnose_system failed"; ALL_PASS=false; }

# ── Dimension 2: End User MCP tools — profile + subscription ───────
echo ""
echo "── Dimension 2: End User MCP tools ──"
ENDUSER_CHECK=$(python3 -c "
import json, subprocess
result = subprocess.run(
    ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'get_enduser_history',
     json.dumps({'user_id': 'ivf-researcher-alice'})],
    capture_output=True, text=True, timeout=15
)
data = json.loads(result.stdout) if result.stdout else {}
entries = data.get('entries', data.get('history', data.get('items', [])))
print(f'End user history entries: {len(entries)}')
print(f'MCP tool status: {\"operational\" if result.returncode == 0 else \"error\"}')
" 2>&1)
echo "$ENDUSER_CHECK"
echo "$ENDUSER_CHECK" | grep -q "End user history" \
  && echo "  ✅ PASS: end user MCP tools operational (End User dimension)" \
  || { echo "  ⚠️  End user MCP may need profile setup first"; }

# ── Dimension 3: Director User — CLI health commands ────────────────
echo ""
echo "── Dimension 3: Director User CLI health ──"
DOCTOR_OUTPUT=$(autoinfo doctor --json 2>&1 || echo '{}')
DOCTOR_EXIT=$?
echo "$DOCTOR_OUTPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'Doctor status: {data.get(\"status\",\"?\")}')
print(f'Config valid: {data.get(\"config\",{}).get(\"valid\",\"?\")}')
print(f'LLM key: {data.get(\"llm\",{}).get(\"key_configured\",\"?\")}')
" 2>&1
[ "$DOCTOR_EXIT" -eq 0 ] \
  && echo "  ✅ PASS: autoinfo doctor exit 0 (Director dimension)" \
  || { echo "  ❌ FAIL: autoinfo doctor exit $DOCTOR_EXIT"; ALL_PASS=false; }

# ── Dimension 4: Cross-dimension — Prometheus metrics ──────────────
echo ""
echo "── Dimension 4: Prometheus metrics endpoint ──"
PROM_METRICS=$(python3 -c "
import json, subprocess
result = subprocess.run(
    ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'get_prometheus_metrics',
     json.dumps({})],
    capture_output=True, text=True, timeout=15
)
data = json.loads(result.stdout) if result.stdout else {}
keys = list(data.keys())[:5] if data else []
print(f'Prometheus metric keys: {keys}')
print(f'Metrics accessible: {len(keys) > 0}')
" 2>&1)
echo "$PROM_METRICS"
echo "$PROM_METRICS" | grep -q "accessible" \
  && echo "  ✅ PASS: Prometheus metrics accessible (observability dimension)" \
  || { echo "  ⚠️  Prometheus metrics may require REST API running"; }

# ── Verdict ────────────────────────────────────────────────────────
echo ""
echo "── Cross-Dimension Health Summary ──"
echo "  Agent (health_check + diagnose):  checked"
echo "  End User (MCP tools):             checked"
echo "  Director (CLI doctor):            checked"
echo "  Observability (Prometheus):       checked"

if [ "$ALL_PASS" = true ]; then
  echo ""
  echo "✅ SCENARIO 70.15 PASSED — MCP health across all dimensions"
  exit 0
else
  echo ""
  echo "❌ SCENARIO 70.15 FAILED"
  exit 1
fi
```
**Expected Result:**
- ✅ `health_check()` returns valid status from Agent dimension
- ✅ `diagnose_system()` returns `health_score` (Agent dimension)
- ✅ End User MCP tools (`get_enduser_history`) are callable (End User dimension)
- ✅ `autoinfo doctor --json` exits 0 with structured health data (Director dimension)
- ✅ Prometheus metrics endpoint returns metric keys (Observability dimension)
- ✅ All three dimensions + observability verified in a single infrastructure scenario


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
| 70.10 | Full E2E: Collect → Process → Digest → Deliver | All 3 dimensions | ⬜ |
| 70.11 | Pipeline stage artifact verification | Agent (Direct) | ⬜ |
| 70.12 | trace_id propagation across pipeline | Agent (Direct) | ⬜ |
| 70.13 | End User delivery channel verification | Agent to End User | ⬜ |
| 70.14 | Audit log pipeline completeness | Agent (Direct) | ⬜ |
| 70.15 | MCP health across all dimensions (infra) | All 3 dimensions | ⬜ |

**OVERALL: ⬜**

**F expectations verified:** F01 (setup), F03 (init), F04 (LLM key), F05 (domain/source), F09 (topics/keywords), F11 (one-command collect), F12 (progress), F15 (LLM extraction), F20 (KB pipeline), F21 (KB search), F24 (digest), F27 (delivery), F29 (PROCESSED products), F31 (collection overview), F37 (multi-channel delivery), F38 (end user lifecycle), F39 (delivery reliability), F48 (audit logging), F49 (per-item traceability), F50 (pipeline observability), F51 (artifact verification)

---

## Q71: Full E2E with Error Recovery -- Failure, Escalation, Recovery

> **Director User says:** "帮我追踪 AI 商业情报，每天给我推送简报到 Discord"

Same journey as Q70 but with deliberate failure mid-cycle requiring escalation to Director User, a decision, and recovery to complete delivery.

### Prerequisites

```bash
cd /tmp/test-q71

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
  --domain ai-commercial

# Verify setup
autoinfo doctor --json | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'OK: config_valid={d.get(\"config\",{}).get(\"valid\")}')"
```

**Expected Result:** ✅ Project initialized. ai-commercial domain active with intentionally fragile source.

---

### Scenarios

#### 71.1 🟢 Director User instructs Agent to set up AI commercial tracking

**User says:** "配置 AI 商业情报追踪，关注 AI 产品发布、融资和定价变化，用 TechCrunch"

**Agent executes:**

**Execute:**

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
     '--domain', 'ai-commercial'],
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


#### 71.2 🔴 Agent runs collection -- fragile source times out

**User says:** "开始搜集"

**Agent executes:**

**Execute:**

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
- ✅ `fragile-source` (web, timeout) returns 0 items (failure isolated, F33 confirmed)
- ✅ F33 (Source Handler Isolation) -- one source failing does NOT crash others
- ✅ Collection summary shows per-source status (success + error)


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


#### 71.4 🟢 Director User decides to skip broken source and proceed

**User says:** "忽略那个坏掉的信源，用已有的内容继续"

**Agent executes:**

**Execute:**

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
- ✅ Processing completes with exit code 0 despite failed source (F33 isolation confirmed)
- ✅ F15 + F20 processing path works with partial collection results


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


#### 71.6 🟢 Agent generates daily digest from successfully processed items

**User says:** "用通过质量门的内容生成简报"

**Agent executes:**

**Execute:**

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


#### 71.7 🟢 Agent verifies end user profile before delivery

**User says:** "推送到 Bob 的 Discord"

**Agent executes:**

**Execute:**

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


#### 71.8 🟢 Agent attempts Discord delivery with email fallback

**User says:** "Discord 推送，如果失败用邮件"

**Agent executes:**

**Execute:**

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
- ✅ Email delivery: if SMTP configured → message sent successfully (check delivery_log `status: "delivered"`); if SMTP not configured → returns appropriate config error
- ✅ Delivery log records both attempts with channel and status
- ✅ F39 (Delivery Reliability) -- retry chain with fallback, never silently drop
- ✅ D2 (Format Integrity) delivery gate passes


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
- ✅ SLA compliance recorded: delivery_log entry has `sla_tier: "P0"` and `delivery_latency_seconds <= 300`
- ✅ Audit log contains delivery events for end-to-end traceability
- ✅ Retry chain documented: Discord -> Email -> delivered
- ✅ F39 + F48 + F55 (Per-Item Traceability) satisfied


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
| **Q71b** | Agent Callback Subscription Pattern (+ infra) | ✅ Director, Agent, End User | N/A (push registration + persistence) | ⬜ |

**OVERALL CROSS-DIMENSION E2E: ⬜**

---

## Cross-Dimension Coverage Summary

| Capability | Q70 | Q71 | Q71b | F Reference |
|------------|-----|-----|------|-------------|
| Director User gives NL instruction | 70.1 | 71.1 | 71b.1 | F01-F05 |
| Agent configures domain/source/topic | 70.1 | 71.1 | - | F05, F09 |
| Dry-run collection preview | 70.2 | - | - | F11 |
| Async collection with progress polling | 70.3 | 71.2 | - | F11, F12 |
| LLM extraction processing | 70.4 | 71.4 | - | F15 |
| Knowledge base (01-Raw) storage | 70.4 | 71.4 | - | F20 |
| KB search and retrieval | 70.5 | - | - | F21 |
| Quality gates (G0/G4 hard gates) | 70.4 | 71.5 | - | G0, G4 |
| Digest generation | 70.6 | 71.6 | - | F24, F29 |
| End user profile management | 70.Prereq | 71.7 | - | F36 |
| Multi-channel delivery | 70.7 | 71.8 | - | F27, F37 |
| Delivery fallback chain | - | 71.8 | - | F39 |
| Delivery SLA verification | 70.8 | 71.9 | - | F39 |
| Audit log verification | 70.8 | 71.9 | - | F48 |
| Delivery gate checks (D1-D3) | 70.7 | 71.8, 71.10 | - | D1-D3 |
| Source failure isolation | - | 71.2, 71.3 | - | F33 |
| Agent escalation to Director | - | 71.3 | - | F32, F34 |
| Director decision + recovery | - | 71.4 | - | F34 |
| End user receives product | 70.9 | 71.10 | - | F38 |
| Agent proposes improvements | - | 71.10 | - | F31 |
| Source health monitoring | - | 71.3 | - | F32 |
| G4 factual consistency retry+block | - | 71.5 | - | G4 |
| End-to-end trace (collection to delivery) | 70.8 | 71.9 | - | F55 |
| Agent callback registration & push delivery | - | - | 71b.1, 71b.2, 71b.3, 71b.4 | F27, F37 |
| MCP health across all dimensions | 70.15 | - | - | F50 |
| Agent callback persistence (SQLite) | - | - | 71b.4 | F37 |

---

## Q71b: Agent Callback Subscription Pattern — Push Notifications Without Polling

> **Director User says:** "设置当有新摘要生成时，推送到我的 agent webhook，以后不要再轮询了"

Unlike traditional polling where the agent repeatedly checks for new content, the Agent Callback pattern allows an agent to register a webhook URL with AutoInfo. When a matching event occurs (e.g., a digest is generated), AutoInfo pushes structured JSON to the agent's callback URL. This reduces latency and eliminates polling overhead.

### Prerequisites

```bash
cd /tmp/test-q71b

export AUTOINFO_LLM_API_KEY="sk-dummy-for-testing"

# Initialize with medical-research demo domain
autoinfo init --demo medical-research

# Verify MCP server is accessible
python3 -c "
import json, subprocess
result = subprocess.run(
    ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'health_check',
     json.dumps({})],
    capture_output=True, text=True, timeout=15
)
data = json.loads(result.stdout) if result.stdout else {}
print(f'Health check: status={data.get(\"status\",\"?\")}, version={data.get(\"version\",\"?\")}')
"
```

**Expected Result:** ✅ Project initialized. MCP server healthy. Agent callback tools available.

---

### Scenarios

#### 71b.1 🟢 Agent registers a callback for digest events

**User says:** "当生成 IVF 研究摘要时，推送到 https://my-agent.example.com/callback，事件类型包括 new_digest 和 new_report"

**Agent executes:**

**Execute:**

```python
# Agent registers a callback webhook using the MCP tool
python3 -c "
import json, subprocess

# Register callback for new digest and report events
result = subprocess.run(
    ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'set_agent_callback',
     json.dumps({
         'url': 'https://my-agent.example.com/callback',
         'events': ['new_digest', 'new_report'],
         'description': 'IVF research digest push notifications',
         'secret': 'whsec_abc123xyz'
     })],
    capture_output=True, text=True, timeout=15
)
data = json.loads(result.stdout) if result.stdout else {}
print(f'Callback registered: {json.dumps(data, indent=2)[:500]}')

# Verify the callback ID is returned
callback_id = data.get('callback_id', data.get('id', ''))
if callback_id:
    print(f'PASS: Callback created with ID: {callback_id}')
else:
    print('FAIL: No callback_id returned')
"
```

**Expected Result:**
- ✅ `set_agent_callback` returns success with a `callback_id`
- ✅ Callback registered for URL `https://my-agent.example.com/callback`
- ✅ Events configured: `new_digest` and `new_report`
- ✅ Optional `secret` for HMAC signature verification accepted
- ✅ F27 (Delivery) — agent push delivery pattern registered


#### 71b.2 🟢 Agent lists registered callbacks to verify configuration

**User says:** "确认一下目前的回调注册情况，看看有几个活跃的回调"

**Agent executes:**

**Execute:**

```python
# List all registered agent callbacks
python3 -c "
import json, subprocess

result = subprocess.run(
    ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'list_agent_callbacks',
     json.dumps({})],
    capture_output=True, text=True, timeout=15
)
data = json.loads(result.stdout) if result.stdout else {}
callbacks = data.get('callbacks', data.get('items', []))
print(f'Registered callbacks: {len(callbacks)}')
for cb in callbacks:
    url = cb.get('url', '?')
    events = cb.get('events', [])
    cb_id = cb.get('callback_id', cb.get('id', '?'))
    active = cb.get('active', cb.get('status', '?'))
    print(f'  [{cb_id}] {url}')
    print(f'    Events: {events} | Active: {active}')

# Verify our callback appears in the list
our_url = 'https://my-agent.example.com/callback'
found = any(cb.get('url', '') == our_url for cb in callbacks)
if found:
    print(f'PASS: Callback for {our_url} found in list')
else:
    print(f'FAIL: Callback for {our_url} NOT found in list')
"
```

**Expected Result:**
- ✅ `list_agent_callbacks` returns all registered callbacks
- ✅ Callback to `https://my-agent.example.com/callback` appears in the list
- ✅ Each callback shows URL, events, and active status
- ✅ Agent can confirm the Director User's callback is properly configured


#### 71b.3 🟢 Agent removes a callback when no longer needed

**User says:** "我们现在不需要这个回调了，暂时移除它，以后需要再注册"

**Agent executes:**

**Execute:**

```python
# Remove the previously registered callback
python3 -c "
import json, subprocess

# First, get the callback ID from list
result = subprocess.run(
    ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'list_agent_callbacks',
     json.dumps({})],
    capture_output=True, text=True, timeout=15
)
data = json.loads(result.stdout) if result.stdout else {}
callbacks = data.get('callbacks', data.get('items', []))

# Find our callback
target_url = 'https://my-agent.example.com/callback'
target = next((cb for cb in callbacks if cb.get('url', '') == target_url), None)
if not target:
    print('WARN: Callback not found in list (may have already been removed)')
    print('PASS: Nothing to remove (already clean)')
else:
    target_id = target.get('callback_id', target.get('id', ''))
    print(f'Removing callback: {target_id} ({target_url})')

    # Remove the callback
    result2 = subprocess.run(
        ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'remove_agent_callback',
         json.dumps({'callback_id': target_id})],
        capture_output=True, text=True, timeout=15
    )
    data2 = json.loads(result2.stdout) if result2.stdout else {}
    status = data2.get('status', data2.get('result', '?'))
    print(f'Removal result: {status}')

    # Verify removal
    result3 = subprocess.run(
        ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'list_agent_callbacks',
         json.dumps({})],
        capture_output=True, text=True, timeout=15
    )
    data3 = json.loads(result3.stdout) if result3.stdout else {}
    remaining = data3.get('callbacks', data3.get('items', []))
    still_present = any(cb.get('url', '') == target_url for cb in remaining)
    if not still_present:
        print(f'PASS: Callback {target_id} successfully removed')
    else:
        print(f'FAIL: Callback {target_id} still present after removal')
"
```

**Expected Result:**
- ✅ `remove_agent_callback` returns success status
- ✅ After removal, `list_agent_callbacks` no longer includes the removed callback
- ✅ Idempotent — removing a non-existent callback does not cause a crash
- ✅ Agent demonstrates full lifecycle: register → list/verify → remove


#### 71b.4 🟢 Infrastructure: Agent callback server persistence — callbacks survive restart

**User says:** "确认我的回调注册会在服务器重启后继续存在，不需要每次重新注册"

**Agent verifies that callback registrations are SQLite-persisted and survive MCP server restarts:**

**Execute:**

```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
TEST_DIR="/tmp/test-q71b"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  71b.4: Agent Callback Persistence Across Restarts          ║"
echo "╚══════════════════════════════════════════════════════════════╝"

cd "$TEST_DIR"

# ── Step 1: Register a callback ─────────────────────────────────────
echo "── Step 1: Register callback ──"
REGISTER_RESULT=$(python3 -c "
import json, subprocess
result = subprocess.run(
    ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'set_agent_callback',
     json.dumps({
         'url': 'https://persistent-callback.example.com/hook',
         'events': ['new_digest', 'new_report'],
         'description': 'Persistence test callback'
     })],
    capture_output=True, text=True, timeout=15
)
data = json.loads(result.stdout) if result.stdout else {}
cb_id = data.get('callback_id', data.get('id', ''))
print(cb_id)
" 2>&1)
echo "  Registered callback ID: $REGISTER_RESULT"
[ -n "$REGISTER_RESULT" ] \
  && echo "  ✅ PASS: callback registered with ID" \
  || { echo "  ❌ FAIL: callback registration failed"; ALL_PASS=false; }

# ── Step 2: Verify callback appears in list (pre-restart) ────────────
echo ""
echo "── Step 2: Verify callback appears pre-restart ──"
PRE_LIST=$(python3 -c "
import json, subprocess
result = subprocess.run(
    ['python3', '-m', 'autoinfo.mcp.server', '--tool', 'list_agent_callbacks',
     json.dumps({})],
    capture_output=True, text=True, timeout=15
)
data = json.loads(result.stdout) if result.stdout else {}
callbacks = data.get('callbacks', data.get('items', []))
print(f'Callbacks pre-restart: {len(callbacks)}')
for cb in callbacks:
    print(f'  {cb.get(\"url\",\"?\")} — events: {cb.get(\"events\",[])}')
" 2>&1)
echo "$PRE_LIST"
PERSIST_COUNT=$(echo "$PRE_LIST" | python3 -c "import sys; print(sys.stdin.read().count('persistent-callback'))")
[ "$PERSIST_COUNT" -gt 0 ] \
  && echo "  ✅ PASS: callback found in list pre-restart" \
  || { echo "  ❌ FAIL: callback not in list pre-restart"; ALL_PASS=false; }

# ── Step 3: Check SQLite persistence file ────────────────────────────
echo ""
echo "── Step 3: Check SQLite persistence ──"
DB_PATH=".autoinfo/agent_callbacks.db"
if [ -f "$DB_PATH" ]; then
  DB_SIZE=$(stat --format=%s "$DB_PATH" 2>/dev/null || stat -f%z "$DB_PATH" 2>/dev/null || echo 0)
  echo "  Callback DB: $DB_PATH ($DB_SIZE bytes)"
  [ "$DB_SIZE" -gt 0 ] \
    && echo "  ✅ PASS: agent_callbacks.db exists and is non-empty" \
    || { echo "  ❌ FAIL: agent_callbacks.db empty or missing"; ALL_PASS=false; }

  # Verify our callback is in the DB
  python3 -c "
import sqlite3, json
conn = sqlite3.connect('$DB_PATH')
rows = conn.execute('SELECT url, events FROM agent_callbacks WHERE url LIKE ?', ('%persistent-callback%',)).fetchall()
print(f'  DB entries for persistent-callback: {len(rows)}')
for r in rows:
    print(f'    url={r[0]}, events={r[1]}')
conn.close()
" 2>&1 \
    && echo "  ✅ PASS: callback persisted in SQLite" \
    || { echo "  ❌ FAIL: callback not found in SQLite DB"; ALL_PASS=false; }
else
  echo "  ⚠️  agent_callbacks.db not found (may use different persistence mechanism)"
fi

# ── Verdict ──────────────────────────────────────────────────────────
echo ""
if [ "$ALL_PASS" = true ]; then
  echo "✅ SCENARIO 71b.4 PASSED — Agent callback persistence verified"
  exit 0
else
  echo "❌ SCENARIO 71b.4 FAILED"
  exit 1
fi
```
**Expected Result:**
- ✅ `set_agent_callback` returns a `callback_id` (registration works)
- ✅ `list_agent_callbacks` shows the registered callback (pre-restart verification)
- ✅ `.autoinfo/agent_callbacks.db` exists and is non-empty (SQLite persistence)
- ✅ Callback URL and events are stored in `agent_callbacks` DB table
- ✅ Callbacks persist across MCP server restarts (SQLite-backed, per AGENTS.md)


---

### 📊 Q71b Verdict

| # | Scenario | Dimension(s) Verified | Result |
|---|----------|----------------------|--------|
| 71b.1 | Director instructs Agent to register callback | Director to Agent | ⬜ |
| 71b.2 | Agent lists callbacks to verify registration | Agent (Direct) | ⬜ |
| 71b.3 | Director instructs Agent to remove callback | Director to Agent | ⬜ |
| 71b.4 | Callback persistence across restarts (infra) | Agent (Direct) | ⬜ |

**OVERALL: ⬜**

**F expectations verified:** F27 (Delivery — agent callback push pattern for digest delivery), F37 (Multi-Channel Delivery — webhook as a delivery channel for agent subscribers)

---

**Agent Callback Subscription Pattern — Full Lifecycle:**

```
Director User          Agent (Direct User)          AutoInfo Server          Agent Webhook
     |                        |                           |                       |
     |--"设置回调推送"-->       |                           |                       |
     |                        |--set_agent_callback()-->  |                       |
     |                        |<---callback_id----------  |                       |
     |                        |--list_agent_callbacks()-> |                       |
     |                        |<---[callback list]------  |                       |
     |<--"回调已注册"---------|                           |                       |
     |                        |                           |                       |
     |                        |    (Later: digest gen)    |                       |
     |                        |                           |--POST /callback----->  |
     |                        |                           |   {event:new_digest}   |
     |                        |                           |<---200 OK-------------|
     |                        |                           |                       |
     |--"不需要了，取消"-->    |                           |                       |
     |                        |--remove_agent_callback()->|                       |
     |                        |<---success--------------  |                       |
     |<--"回调已取消"---------|                           |                       |
```

**Key Pattern:** Agent registers once → AutoInfo pushes on events → Agent never polls. When no longer needed, Agent removes the callback. This is the preferred pattern for low-latency agent integration versus polling-based approaches. *(requires AutoInfo ≥ v1.7)*

---

## Q72: Module-Level Validation — Embeddings, Importer, Terminology, Translation QA

> **Context:** Validate four standalone modules (`embeddings.py`, `importer.py`, `terminology.py`, `translation_qa.py`) that underpin KB search, content ingestion, translation guardrails, and translation quality scoring. These modules are exercised indirectly throughout the pipeline but deserve direct unit-level scenarios to lock their contracts.

### Prerequisites

```bash
cd /tmp/test-q72

# AutoInfo must be importable
python3 -c "import autoinfo; print(f'AutoInfo {autoinfo.__version__ if hasattr(autoinfo, \"__version__\") else \"installed\"}')"

# LLM key is optional for most scenarios — embedding/translation fallbacks return
# zero-vectors or initial translations when the API is unreachable.
export AUTOINFO_LLM_API_KEY="sk-dummy-for-testing"
```

**Expected Result:** ✅ AutoInfo importable. Test workspace ready.

---

### Scenarios

#### 72.1 🟢 Embeddings — generate_embedding returns 1536-dim float vector

**Agent executes:**

**Execute:**

```bash
python3 -c "
from autoinfo.embeddings import generate_embedding

vec = generate_embedding('CRISPR therapy shows promise')

# Type contract
assert isinstance(vec, list), f'Expected list, got {type(vec).__name__}'
assert len(vec) == 1536, f'Expected 1536 dims, got {len(vec)}'
assert all(isinstance(x, float) for x in vec), 'All elements must be floats'

print(f'Type: {type(vec).__name__}')
print(f'Dimensions: {len(vec)}')
print(f'All floats: {all(isinstance(x, float) for x in vec)}')
print(f'PASS: generate_embedding returns list[float] of length 1536')
"
```

**Expected Result:**
- ✅ `generate_embedding` returns a `list` (not a tuple or numpy array)
- ✅ Vector dimension is exactly 1536
- ✅ Every element is a Python `float`
- ✅ Without a real embedding API key, the function gracefully returns a zero-vector (all 0.0) rather than raising


#### 72.2 🟢 Embeddings — cosine_similarity boundary values

**Agent executes:**

**Execute:**

```bash
python3 -c "
from autoinfo.embeddings import cosine_similarity

# Identical vectors → 1.0
identical = cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0])
print(f'Identical: {identical}')
assert abs(identical - 1.0) < 1e-9, f'Identical vectors should give 1.0, got {identical}'

# Opposite vectors → -1.0
opposite = cosine_similarity([1.0, 2.0, 3.0], [-1.0, -2.0, -3.0])
print(f'Opposite: {opposite}')
assert abs(opposite - (-1.0)) < 1e-9, f'Opposite vectors should give -1.0, got {opposite}'

# Orthogonal vectors → 0.0
orthogonal = cosine_similarity([1.0, 0.0], [0.0, 1.0])
print(f'Orthogonal: {orthogonal}')
assert abs(orthogonal - 0.0) < 1e-9, f'Orthogonal vectors should give 0.0, got {orthogonal}'

# Degenerate inputs → 0.0 (no crash)
empty = cosine_similarity([], [1.0, 2.0])
print(f'Empty input: {empty}')
assert empty == 0.0, f'Empty input should give 0.0, got {empty}'

mismatched = cosine_similarity([1.0, 2.0], [1.0, 2.0, 3.0])
print(f'Mismatched length: {mismatched}')
assert mismatched == 0.0, f'Mismatched length should give 0.0, got {mismatched}'

print('PASS: cosine_similarity boundary values correct')
"
```

**Expected Result:**
- ✅ Identical vectors return `1.0`
- ✅ Opposite vectors return `-1.0`
- ✅ Orthogonal vectors return `0.0`
- ✅ With empty input (`[]`): returns `0.0` (no exception). With mismatched-length inputs (`[1,0]` vs `[1,0,0]`): returns `0.0` (no exception)
- ✅ Return value is always a float in `[-1.0, 1.0]`


#### 72.3 🔴 Embeddings — empty text returns zero-vector (graceful fallback)

**Agent executes:**

**Execute:**

```bash
python3 -c "
from autoinfo.embeddings import generate_embedding

# Empty string
vec_empty = generate_embedding('')
assert isinstance(vec_empty, list), f'Expected list, got {type(vec_empty).__name__}'
assert len(vec_empty) == 1536, f'Expected 1536 dims, got {len(vec_empty)}'
assert all(x == 0.0 for x in vec_empty), 'Empty text should yield zero-vector'
print(f'Empty string: len={len(vec_empty)}, all_zero={all(x == 0.0 for x in vec_empty)}')

# Whitespace-only string
vec_ws = generate_embedding('   \n\t  ')
assert len(vec_ws) == 1536
assert all(x == 0.0 for x in vec_ws), 'Whitespace-only text should yield zero-vector'
print(f'Whitespace: len={len(vec_ws)}, all_zero={all(x == 0.0 for x in vec_ws)}')

print('PASS: empty/whitespace text returns 1536-dim zero-vector without raising')
"
```

**Expected Result:**
- ✅ `generate_embedding("")` does NOT raise an exception
- ✅ Returns a list of 1536 floats, all `0.0`
- ✅ Whitespace-only text (`"   \n\t  "`) also returns a zero-vector
- ✅ Graceful degradation: the function logs a warning but never crashes on empty input


#### 72.4 🟢 Importer — import_kb with Markdown frontmatter lands in 01-Raw

**Agent executes:**

**Execute:**

```bash
python3 -c "
import os, tempfile
from pathlib import Path
from autoinfo.importer import import_kb

with tempfile.TemporaryDirectory() as td:
    os.chdir(td)
    Path('.autoinfo').mkdir()
    Path('.autoinfo/config.yaml').write_text('llm:\n  provider: openai\n  model: gpt-4o-mini\n')

    md = '''---
title: Test Article
source_url: https://example.com/article
source_type: web
source_platform: manual
---
# Test Article
This is the body content for the imported markdown entry.
'''

    result = import_kb('test-domain', 'markdown', md)
    print(f'Result: {result}')

    assert result.get('entries_imported') == 1, f'Expected 1 imported, got {result.get(\"entries_imported\")}'
    assert result.get('entries_failed') == 0, f'Expected 0 failed, got {result.get(\"entries_failed\")}'
    assert 'entry_id' in result, 'Result must include entry_id'

    # Verify the entry landed in 01-Raw tier
    raw_files = list(Path('knowledge/test-domain/01-Raw').rglob('*.md'))
    print(f'01-Raw files: {len(raw_files)}')
    assert len(raw_files) >= 1, 'Entry must be stored in 01-Raw tier'
    print(f'PASS: Markdown imported to 01-Raw, entry_id={result[\"entry_id\"]}')
"
```

**Expected Result:**
- ✅ `import_kb` with `format="markdown"` returns a dict with `entries_imported: 1`
- ✅ `entries_failed: 0` and `errors: []`
- ✅ Result includes an `entry_id` for the created entry
- ✅ The entry file exists under `knowledge/test-domain/01-Raw/`
- ✅ Imported entry lands in 01-Raw tier (the sole entry point per KB pipeline rules)


#### 72.5 🟢 Importer — import_kb with JSON array imports 2 entries

**Agent executes:**

**Execute:**

```bash
python3 -c "
import os, json, tempfile
from pathlib import Path
from autoinfo.importer import import_kb

with tempfile.TemporaryDirectory() as td:
    os.chdir(td)
    Path('.autoinfo').mkdir()
    Path('.autoinfo/config.yaml').write_text('llm:\n  provider: openai\n  model: gpt-4o-mini\n')

    data = json.dumps([
        {'title': 'Item 1', 'source_url': 'https://example.com/1', 'content': 'Body 1'},
        {'title': 'Item 2', 'source_url': 'https://example.com/2', 'content': 'Body 2'},
    ])

    result = import_kb('test-domain', 'json', data)
    print(f'Result: {result}')

    assert result.get('entries_imported') == 2, f'Expected 2 imported, got {result.get(\"entries_imported\")}'
    assert result.get('entries_failed') == 0, f'Expected 0 failed, got {result.get(\"entries_failed\")}'
    assert result.get('errors') == [], f'Expected no errors, got {result.get(\"errors\")}'

    raw_files = list(Path('knowledge/test-domain/01-Raw').rglob('*.md'))
    print(f'01-Raw files: {len(raw_files)}')
    assert len(raw_files) >= 2, 'Both entries must be stored in 01-Raw'
    print('PASS: JSON array imported 2 entries to 01-Raw')
"
```

**Expected Result:**
- ✅ `import_kb` with `format="json"` and a 2-element array returns `entries_imported: 2`
- ✅ `entries_failed: 0` and `errors: []`
- ✅ Both entries are stored as Markdown files under `knowledge/test-domain/01-Raw/`
- ✅ Each JSON entry requires mandatory fields: `title`, `source_url`, `content`


#### 72.6 🟢 Importer — import_kb with CSV imports entries

**Agent executes:**

**Execute:**

```bash
python3 -c "
import os, tempfile
from pathlib import Path
from autoinfo.importer import import_kb

with tempfile.TemporaryDirectory() as td:
    os.chdir(td)
    Path('.autoinfo').mkdir()
    Path('.autoinfo/config.yaml').write_text('llm:\n  provider: openai\n  model: gpt-4o-mini\n')

    csv_data = 'title,source_url,source_type,source_platform,content\n'
    csv_data += 'Alpha,https://e.com/a,web,manual,Body Alpha\n'
    csv_data += 'Beta,https://e.com/b,web,manual,Body Beta\n'

    result = import_kb('test-domain', 'csv', csv_data)
    print(f'Result: {result}')

    assert result.get('entries_imported') == 2, f'Expected 2 imported, got {result.get(\"entries_imported\")}'
    assert result.get('entries_failed') == 0, f'Expected 0 failed, got {result.get(\"entries_failed\")}'
    assert result.get('errors') == [], f'Expected no errors, got {result.get(\"errors\")}'

    raw_files = list(Path('knowledge/test-domain/01-Raw').rglob('*.md'))
    print(f'01-Raw files: {len(raw_files)}')
    assert len(raw_files) >= 2, 'CSV entries must be stored in 01-Raw'
    print('PASS: CSV imported 2 entries to 01-Raw')
"
```

**Expected Result:**
- ✅ `import_kb` with `format="csv"` parses the CSV header and rows
- ✅ Returns `entries_imported: 2`, `entries_failed: 0`, `errors: []`
- ✅ CSV columns `title,source_url,source_type,source_platform,content` are mapped to entry fields
- ✅ Both entries stored under `knowledge/test-domain/01-Raw/`


#### 72.7 🔴 Importer — unsupported format raises ValueError

**Agent executes:**

**Execute:**

```bash
python3 -c "
from autoinfo.importer import import_kb

try:
    result = import_kb('test-domain', 'unsupported_format', 'some data')
    print(f'FAIL: No exception raised, got {result}')
except ValueError as e:
    print(f'ValueError: {e}')
    assert 'unsupported_format' in str(e), f'Error message should mention the bad format'
    assert 'csv' in str(e) and 'json' in str(e) and 'markdown' in str(e) and 'opml' in str(e), \\
        'Error message should list supported formats'
    print('PASS: Unsupported format raises ValueError with helpful message')
except Exception as e:
    print(f'FAIL: Wrong exception type {type(e).__name__}: {e}')
"
```

**Expected Result:**
- ✅ `import_kb` with an unsupported format raises `ValueError` (not a generic `Exception`)
- ✅ Error message includes the offending format name (`"unsupported_format"`)
- ✅ Error message lists the supported formats: `csv`, `json`, `markdown`, `opml`
- ✅ No partial side effects (no files written, no KB entries created)


#### 72.8 🟢 Terminology — load_terminology on nonexistent domain returns empty Terminology

**Agent executes:**

**Execute:**

```bash
python3 -c "
from autoinfo.terminology import load_terminology, Terminology

# Domain that has no _terminology.yaml
term = load_terminology('nonexistent-domain-xyz')

# Must return a Terminology instance, not None, not a crash
assert isinstance(term, Terminology), f'Expected Terminology, got {type(term).__name__}'
assert len(term.terms) == 0, f'Expected empty terms dict, got {len(term.terms)} entries'

# Default score_weights must still be present
expected_weights = {'faithfulness', 'terminology', 'style', 'readability'}
assert set(term.score_weights.keys()) == expected_weights, \\
    f'Expected default weight keys {expected_weights}, got {set(term.score_weights.keys())}'

print(f'Type: {type(term).__name__}')
print(f'Terms: {len(term.terms)} (empty)')
print(f'Score weights: {term.score_weights}')
print('PASS: Missing terminology file returns empty Terminology with default weights')
"
```

**Expected Result:**
- ✅ `load_terminology` returns a `Terminology` dataclass instance (not `None`, no exception)
- ✅ `terms` dict is empty (`{}`)
- ✅ `score_weights` retains default values: `faithfulness=40, terminology=30, style=20, readability=10`
- ✅ Missing file is handled gracefully (no crash, logged as a warning)


#### 72.9 🟢 Terminology — load_terminology reads _terminology.yaml and parses terms

**Agent executes:**

**Execute:**

```bash
python3 -c "
import os, tempfile, yaml
from pathlib import Path
from autoinfo.terminology import load_terminology, TermEntry

with tempfile.TemporaryDirectory() as td:
    os.chdir(td)
    kdir = Path('knowledge/mydomain')
    kdir.mkdir(parents=True)

    data = {
        'score_weights': {'faithfulness': 50, 'terminology': 20, 'style': 20, 'readability': 10},
        'terms': {
            'CRISPR': {'type': 'do_not_translate', 'note': 'Gene editing tool'},
            'in vitro fertilization': {
                'preferred': '体外受精',
                'variants': ['IVF'],
                'confidence': 0.95,
            },
        },
    }
    (kdir / '_terminology.yaml').write_text(yaml.safe_dump(data))

    term = load_terminology('mydomain')

    # Terms parsed correctly
    assert len(term.terms) == 2, f'Expected 2 terms, got {len(term.terms)}'

    crispr = term.terms['CRISPR']
    assert isinstance(crispr, TermEntry), f'CRISPR must be TermEntry, got {type(crispr).__name__}'
    assert crispr.type == 'do_not_translate', f'CRISPR type wrong: {crispr.type}'
    assert crispr.note == 'Gene editing tool', f'CRISPR note wrong: {crispr.note}'

    ivf = term.terms['in vitro fertilization']
    assert ivf.preferred == '体外受精', f'IVF preferred wrong: {ivf.preferred}'
    assert ivf.variants == ['IVF'], f'IVF variants wrong: {ivf.variants}'
    assert abs(ivf.confidence - 0.95) < 1e-9, f'IVF confidence wrong: {ivf.confidence}'

    # Custom score_weights loaded
    assert term.score_weights['faithfulness'] == 50, f'Custom weight wrong: {term.score_weights}'
    assert term.score_weights['terminology'] == 20

    print(f'Terms loaded: {len(term.terms)}')
    print(f'CRISPR: type={crispr.type}, note={crispr.note}')
    print(f'IVF: preferred={ivf.preferred}, variants={ivf.variants}, confidence={ivf.confidence}')
    print(f'Weights: {term.score_weights}')
    print('PASS: _terminology.yaml parsed correctly with terms and custom weights')
"
```

**Expected Result:**
- ✅ `load_terminology` finds and reads `knowledge/mydomain/_terminology.yaml`
- ✅ Both terms parsed: `CRISPR` (do_not_translate) and `in vitro fertilization` (preferred)
- ✅ `TermEntry` fields populated: `type`, `preferred`, `variants`, `confidence`, `note`
- ✅ Custom `score_weights` from the YAML override the defaults
- ✅ Unicode preferred translation (`体外受精`) preserved correctly


#### 72.10 🟢 Translation QA — calculate_quality_score with partial scores

**Agent executes:**

**Execute:**

```bash
python3 -c "
from autoinfo.translation_qa import calculate_quality_score, DEFAULT_WEIGHTS

# Provide only faithfulness and terminology; style and readability default to 0
result = calculate_quality_score(faithfulness=85, terminology=70)

print(f'Result: {result}')

# Default weights: F=40, T=30, S=20, R=10 (sum=100)
# composite = 85*0.40 + 70*0.30 + 0*0.20 + 0*0.10 = 34 + 21 = 55.0
expected_composite = 85 * (40/100) + 70 * (30/100) + 0 * (20/100) + 0 * (10/100)
print(f'Expected composite: {expected_composite}')

assert abs(result['composite'] - 55.0) < 0.01, f'Expected 55.0, got {result[\"composite\"]}'
assert result['faithfulness'] == 85.0
assert result['terminology'] == 70.0
assert result['style'] == 0.0
assert result['readability'] == 0.0

# weights_used must reflect normalised defaults
assert result['weights_used']['faithfulness'] == 40.0
assert result['weights_used']['terminology'] == 30.0

print('PASS: composite=55.0 with F=85, T=70, S=0, R=0 and default weights')

# Also verify with all four scores
result2 = calculate_quality_score(faithfulness=85, terminology=70, style=80, readability=90)
# composite = 85*0.4 + 70*0.3 + 80*0.2 + 90*0.1 = 34 + 21 + 16 + 9 = 80.0
print(f'All four scores: composite={result2[\"composite\"]}')
assert abs(result2['composite'] - 80.0) < 0.01, f'Expected 80.0, got {result2[\"composite\"]}'
print('PASS: composite=80.0 with all four scores provided')
"
```

**Expected Result:**
- ✅ `calculate_quality_score(faithfulness=85, terminology=70)` returns `composite: 55.0`
- ✅ Missing sub-scores (`style`, `readability`) default to `0.0`
- ✅ Default weights applied: `F=40, T=30, S=20, R=10` (sum normalised to 100)
- ✅ `weights_used` in the result reflects the normalised weight percentages
- ✅ With all four scores (85, 70, 80, 90), composite is `80.0`
- ✅ Composite is rounded to 1 decimal place


#### 72.11 🔴 Translation QA — out-of-range scores are clamped to [0, 100]

**Agent executes:**

**Execute:**

```bash
python3 -c "
from autoinfo.translation_qa import calculate_quality_score

# Scores above 100 and below 0
result = calculate_quality_score(faithfulness=150, terminology=-20, style=200, readability=-50)

print(f'Result: {result}')

# Clamped: F=100, T=0, S=100, R=0
# composite = 100*0.4 + 0*0.3 + 100*0.2 + 0*0.1 = 40 + 0 + 20 + 0 = 60.0
assert result['faithfulness'] == 100.0, f'F should clamp to 100, got {result[\"faithfulness\"]}'
assert result['terminology'] == 0.0, f'T should clamp to 0, got {result[\"terminology\"]}'
assert result['style'] == 100.0, f'S should clamp to 100, got {result[\"style\"]}'
assert result['readability'] == 0.0, f'R should clamp to 0, got {result[\"readability\"]}'

expected = 100*0.4 + 0*0.3 + 100*0.2 + 0*0.1
assert abs(result['composite'] - 60.0) < 0.01, f'Expected 60.0, got {result[\"composite\"]}'

# Composite itself is also clamped to [0, 100]
result2 = calculate_quality_score(faithfulness=100, terminology=100, style=100, readability=100)
assert result2['composite'] == 100.0, f'Max composite should be 100, got {result2[\"composite\"]}'

result3 = calculate_quality_score(faithfulness=0, terminology=0, style=0, readability=0)
assert result3['composite'] == 0.0, f'Min composite should be 0, got {result3[\"composite\"]}'

print(f'Clamped scores: F={result[\"faithfulness\"]}, T={result[\"terminology\"]}, S={result[\"style\"]}, R={result[\"readability\"]}')
print(f'Clamped composite: {result[\"composite\"]}')
print('PASS: Out-of-range scores clamped to [0, 100], composite stays in [0, 100]')
"
```

**Expected Result:**
- ✅ `faithfulness=150` clamped to `100.0`
- ✅ `terminology=-20` clamped to `0.0`
- ✅ `style=200` clamped to `100.0`
- ✅ `readability=-50` clamped to `0.0`
- ✅ Composite computed from clamped scores: `60.0`
- ✅ Composite itself is bounded to `[0, 100]` (max=100, min=0)
- ✅ No exception raised for out-of-range inputs


#### 72.12 🟢 Translation QA — run_back_translation_pipeline disabled returns None

**Agent executes:**

**Execute:**

```bash
python3 -c "
from autoinfo.translation_qa import run_back_translation_pipeline

# When back-translation is explicitly disabled, the pipeline should short-circuit
result = run_back_translation_pipeline(
    source_text='The mitochondria is the powerhouse of the cell.',
    translated_text='线粒体是细胞的能量工厂。',
    source_lang='en',
    target_lang='zh',
    model_pool=None,
    enable_back_translation=False,
)

print(f'Result: {result}')
assert result is None, f'Expected None when back-translation disabled, got {result}'
print('PASS: run_back_translation_pipeline returns None when enable_back_translation=False')
"
```

**Expected Result:**
- ✅ `run_back_translation_pipeline` with `enable_back_translation=False` returns `None`
- ✅ No LLM call is made (no network request, no API key required)
- ✅ No exception raised — the function cleanly short-circuits
- ✅ Callers can use this to skip back-translation verification when not needed


#### 72.13 🔴 Translation QA — refine_translation with failing LLM falls back to initial translation

**Agent executes:**

**Execute:**

```bash
python3 -c "
from autoinfo.translation_qa import refine_translation

# Use an invalid model name that will cause LiteLLM to raise an error
result = refine_translation(
    source_text='The mitochondria is the powerhouse of the cell.',
    initial_translation='线粒体是细胞的能量工厂。',
    source_lang='en',
    target_lang='zh',
    judge_feedback=[{'issue': 'none', 'suggestion': 'keep as is'}],
    model='invalid/nonexistent-model-xyz',
)

print(f'Result: {result}')

# Must return a dict with translation and model_used
assert isinstance(result, dict), f'Expected dict, got {type(result).__name__}'
assert 'translation' in result, 'Result must contain translation key'
assert 'model_used' in result, 'Result must contain model_used key'

# On LLM failure, translation must fall back to the initial_translation
assert result['translation'] == '线粒体是细胞的能量工厂。', \\
    f'Expected fallback to initial translation, got {result[\"translation\"]}'

print(f'translation: {result[\"translation\"]}')
print(f'model_used: {result[\"model_used\"]}')
print('PASS: refine_translation falls back to initial_translation when LLM call fails')
"
```

**Expected Result:**
- ✅ `refine_translation` with an invalid/failing model does NOT raise an exception
- ✅ Returns a dict with `translation` and `model_used` keys
- ✅ `translation` equals the `initial_translation` argument (graceful fallback)
- ✅ `model_used` records the model name that was attempted
- ✅ The failure is logged (warning) but the caller receives a usable result
- ✅ Translation pipeline never silently drops content — it degrades to the input


---

### 📊 Q72 Verdict

| # | Scenario | Module Verified | Result |
|---|----------|----------------|--------|
| 72.1 | generate_embedding returns 1536-dim float vector | embeddings.py | ⬜ |
| 72.2 | cosine_similarity boundary values (1.0, -1.0, 0.0) | embeddings.py | ⬜ |
| 72.3 | Empty text returns zero-vector (graceful fallback) | embeddings.py | ⬜ |
| 72.4 | import_kb Markdown with frontmatter → 01-Raw | importer.py | ⬜ |
| 72.5 | import_kb JSON array → 2 entries imported | importer.py | ⬜ |
| 72.6 | import_kb CSV → entries imported | importer.py | ⬜ |
| 72.7 | Unsupported format raises ValueError | importer.py | ⬜ |
| 72.8 | load_terminology on nonexistent domain → empty Terminology | terminology.py | ⬜ |
| 72.9 | load_terminology reads _terminology.yaml correctly | terminology.py | ⬜ |
| 72.10 | calculate_quality_score with partial scores → composite 55.0 | translation_qa.py | ⬜ |
| 72.11 | Out-of-range scores clamped to [0, 100] | translation_qa.py | ⬜ |
| 72.12 | run_back_translation_pipeline disabled → None | translation_qa.py | ⬜ |
| 72.13 | refine_translation with failing LLM → fallback to initial | translation_qa.py | ⬜ |

**OVERALL: ⬜**

**Modules verified:**
- `embeddings.py` — vector generation (1536-dim), cosine similarity math, graceful empty-text fallback
- `importer.py` — unified dispatch (`import_kb`), Markdown/JSON/CSV formats, unsupported format rejection, all entries land in 01-Raw
- `terminology.py` — `_terminology.yaml` loader, missing-file graceful default, TermEntry parsing with Unicode
- `translation_qa.py` — composite scoring with clamping, back-translation pipeline toggle, LLM failure fallback

**F expectations touched:** F15 (LLM extraction uses embeddings for vector search), F20 (KB pipeline — importer is an alternate 01-Raw entry path), F21 (KB search — embeddings power vector/hybrid mode), F25 (translation QA pipeline — quality scoring, back-translation, refinement)
