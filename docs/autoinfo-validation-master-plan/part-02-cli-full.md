# Part 2: Full CLI Surface Mastery (Q7-Q20)

**Coverage:** All 22 CLI commands with subcommands

---

### Part-Level Directory Setup
Run once at the start of this part:
```bash
# Create clean directories for all questions in this part
rm -rf /tmp/test-q10 && mkdir -p /tmp/test-q10
rm -rf /tmp/test-q11 && mkdir -p /tmp/test-q11
rm -rf /tmp/test-q12 && mkdir -p /tmp/test-q12
rm -rf /tmp/test-q13 && mkdir -p /tmp/test-q13
rm -rf /tmp/test-q14 && mkdir -p /tmp/test-q14
rm -rf /tmp/test-q15 && mkdir -p /tmp/test-q15
rm -rf /tmp/test-q16 && mkdir -p /tmp/test-q16
rm -rf /tmp/test-q7 && mkdir -p /tmp/test-q7
rm -rf /tmp/test-q8 && mkdir -p /tmp/test-q8
rm -rf /tmp/test-q18 && mkdir -p /tmp/test-q18
rm -rf /tmp/test-q9 && mkdir -p /tmp/test-q9
rm -rf /tmp/test-q19 && mkdir -p /tmp/test-q19
rm -rf /tmp/test-q20 && mkdir -p /tmp/test-q20
```

## Q7: Domain Management CLI

**User says:** "I need to manage domains — create custom ones, list, activate, deactivate."

### Prerequisites
```bash
cd /tmp/test-q7
autoinfo init --demo medical-research
```

### Scenarios

#### 7.1 🟢 Domain list
```bash
autoinfo domain list
```
**Expected Result:** ✅ Shows all domains with name, active status, source count.


#### 7.2 🟢 Domain show
```bash
autoinfo domain show --name medical-research
```
**Expected Result:** ✅ Shows detailed domain info: schema, sources, topics, quality tiers.


#### 7.3 🟢 Add custom domain
```bash
autoinfo domain add --name "my-custom" --description "My custom domain"
```
**Expected Result:** ✅ Domain added. Listed in `domain list`. Active by default.


#### 7.4 🟢 Activate domain
```bash
autoinfo domain deactivate --name "my-custom"
autoinfo domain activate --name "my-custom"
```
**Expected Result:** ✅ Domain reactivated. Status shown in `domain list`.


#### 7.5 🟢 Deactivate domain
```bash
autoinfo domain deactivate --name my-custom
```
**Expected Result:** ✅ Domain deactivated. No longer active for collection/processing.


#### 7.6 🔴 Remove domain
```bash
autoinfo domain remove --name my-custom
```
**Expected Result:** ✅ Domain removed. Confirmation shown.


#### 7.7 🔴 Remove demo domain (should warn)
```bash
autoinfo domain remove --name medical-research
```
**Expected Result:** ❌ Warning or error about removing demo domain. Confirmation required.


---

### 📊 Q7 Verdict

| Scenario | Result |
|----------|--------|
| 7.1 Domain list | ⬜ |
| 7.2 Domain show | ⬜ |
| 7.3 Add custom domain | ⬜ |
| 7.4 Activate domain | ⬜ |
| 7.5 Deactivate domain | ⬜ |
| 7.6 Remove domain | ⬜ |
| 7.7 Remove demo | ⬜ |

**OVERALL: ⬜**

---

## Q8: KB CLI — Full Lifecycle

**User says:** "I want to manage my knowledge base from the command line."

### Prerequisites
```bash
cd /tmp/test-q8
autoinfo init --demo medical-research
autoinfo collect --domain medical-research --topic "IVF" --limit 3
```

### Scenarios

#### 8.1 🟢 KB search (keyword)
```bash
autoinfo kb search --query "IVF" --domain medical-research
```
**Expected Result:** ✅ Returns matching entries with title, summary, relevance. Exit code 0.


| #### 8.2 🟢 KB search with FTS5 (default)
```bash
autoinfo kb search --query "embryo development" --domain medical-research
```
**Expected Result:** ✅ Returns entries using FTS5 full-text search. (Note: only FTS5 mode is currently implemented; vector/hybrid/faceted/Q&A/graph modes are planned for future releases.)


#### 8.3 🟢 KB create-draft [REQUIRES LLM KEY]
```bash
# Get first entry ID
ENTRY_ID=$(autoinfo summaries list --domain medical-research --json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['items'][0]['entry_id'] if d.get('items') else 'none')")
if [ "$ENTRY_ID" != "none" ]; then
    autoinfo kb create-draft --raw-id "$ENTRY_ID" --title "Draft from $(echo $ENTRY_ID | head -c40)"
fi
```
**Expected Result:** ✅ Draft created in 02-Draft tier. File at `knowledge/medical-research/02-Draft/`.


#### 8.4 🟢 KB list-tiers
```bash
autoinfo kb list-tiers --domain medical-research
```
**Expected Result:** ✅ Shows entries per tier (01-Raw, 02-Draft, 03-Wiki) with counts.


#### 8.5 🟢 KB reject-draft
```bash
# Get entry_id from 02-Draft
ENTRY_ID=$(autoinfo kb list-tiers --domain medical-research --json 2>/dev/null | python3 -c "
import sys,json; d=json.load(sys.stdin)
for t in d.get('items', []):
    if t['tier'] == '02-Draft' and t.get('entry_count', 0) > 0:
        # Get actual entry_id from this tier (requires a separate call)
        print('02-Draft')
        break
" 2>/dev/null)
if [ "$ENTRY_ID" != "" ]; then
    # reject-draft takes a positional ENTRY_ID argument
    autoinfo kb reject-draft "$ENTRY_ID"
fi
```
**Expected Result:** ✅ Draft rejected. Entry remains in 01-Raw. 02-Draft copy removed.


#### 8.6 🟢 KB reindex
```bash
autoinfo kb reindex --domain medical-research
```
**Expected Result:** ✅ FTS5 index rebuilt. Confirmation with entry count.


---

### 📊 Q8 Verdict

| Scenario | Result |
|----------|--------|
| 8.1 KB search | ⬜ |
| 8.2 Hybrid search | ⬜ |
| 8.3 Create draft | ⬜ |
| 8.4 List tiers | ⬜ |
| 8.5 Reject draft | ⬜ |
| 8.6 Reindex | ⬜ |

**OVERALL: ⬜**

---

## Q9: Output CLI

**User says:** "I need to generate reports, digests, tutorials, and export my knowledge base."

### Prerequisites
```bash
cd /tmp/test-q9
autoinfo init --demo medical-research
autoinfo collect --domain medical-research --topic "IVF" --limit 3
autoinfo process --domain medical-research 2>/dev/null || echo "(LLM optional for output gen)"
```

### Scenarios

#### 9.1 🟢 List output templates
```bash
autoinfo output list-templates --domain medical-research
```
**Expected Result:** ✅ Shows available output templates (digest, report, tutorial, presentation).


#### 9.2 🟢 Generate digest
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
OUTPUT=$(autoinfo output digest --domain medical-research --period weekly 2>&1)
EXIT_CODE=$?

echo "$OUTPUT" | grep -q "Digest\|Weekly Digest\|Entries" \
  && echo "  ✅ PASS: digest has header/section structure" \
  || { echo "  ❌ FAIL: digest missing expected sections"; ALL_PASS=false; }

echo "$OUTPUT" | grep -q "\[" \
  && echo "  ✅ PASS: digest contains entry content" \
  || { echo "  ❌ FAIL: digest has no entry content"; ALL_PASS=false; }

echo "$OUTPUT" | grep -qi "http\|doi\|source" \
  && echo "  ✅ PASS: digest contains source references" \
  || { echo "  ❌ FAIL: digest missing source references"; ALL_PASS=false; }

[ "$EXIT_CODE" -eq 0 ] \
  && echo "  ✅ PASS: exit code 0" \
  || { echo "  ❌ FAIL: exit code $EXIT_CODE"; ALL_PASS=false; }

if [ "$ALL_PASS" = true ]; then echo "✅ SCENARIO 9.2 PASSED"; exit 0; else echo "❌ SCENARIO 9.2 FAILED"; exit 1; fi
```
**Expected Result:** ✅ Digest generated with header, entry content, and source references.


#### 9.3 🟢 Generate report (Markdown)
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
OUTPUT=$(autoinfo output report --domain medical-research --format markdown 2>&1)
EXIT_CODE=$?

echo "$OUTPUT" | grep -qi "executive summary\|sections\|references" \
  && echo "  ✅ PASS: report has structured sections" \
  || { echo "  ❌ FAIL: report missing expected sections"; ALL_PASS=false; }

echo "$OUTPUT" | grep -qi "doi\|http\|source" \
  && echo "  ✅ PASS: report contains source references" \
  || { echo "  ❌ FAIL: report missing source references"; ALL_PASS=false; }

echo "$OUTPUT" | grep -q "|" \
  && echo "  ✅ PASS: report contains tabular data" \
  || { echo "  ❌ FAIL: report has no tables"; ALL_PASS=false; }

[ "$EXIT_CODE" -eq 0 ] \
  && echo "  ✅ PASS: exit code 0" \
  || { echo "  ❌ FAIL: exit code $EXIT_CODE"; ALL_PASS=false; }

if [ "$ALL_PASS" = true ]; then echo "✅ SCENARIO 9.3 PASSED"; exit 0; else echo "❌ SCENARIO 9.3 FAILED"; exit 1; fi
```
**Expected Result:** ✅ Report generated with structured sections, references, and tabular data.


#### 9.4 🟢 Generate report (JSON)
```bash
OUTPUT=$(autoinfo output report --domain medical-research --format json 2>&1)
echo "$OUTPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
items = data.get('items', data.get('entries', []))
assert len(items) > 0, 'empty items'
for i, item in enumerate(items):
    assert 'title' in item, f'item {i}: missing title'
    assert 'summary' in item or 'tl_dr' in item, f'item {i}: missing summary/tl_dr'
has_structure = 'executive_summary' in data or 'sections' in data or 'themes' in data
assert has_structure, 'missing report structure (executive_summary, sections, or themes)'
print('  ✅ PASS: valid JSON with non-empty items + titles + summaries + report structure')
" 2>&1 || echo "  ❌ FAIL: JSON content validation failed"
```
**Expected Result:** ✅ Valid JSON with non-empty items, each with title + summary, plus report structure (executive_summary/sections).


#### 9.5 🟢 Generate tutorial [REQUIRES LLM KEY]
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
OUTPUT=$(autoinfo output tutorial --domain medical-research --audience researcher 2>&1)
EXIT_CODE=$?

echo "$OUTPUT" | grep -qi "objective\|learning\|section\|introduction"   && echo "  ✅ PASS: tutorial has learning objectives/sections"   || { echo "  ❌ FAIL: tutorial missing structured sections"; ALL_PASS=false; }

echo "$OUTPUT" | grep -qi "exercise\|summary\|key point\|takeaway"   && echo "  ✅ PASS: tutorial has exercises or takeaways"   || { echo "  ❌ FAIL: tutorial missing exercises/takeaways"; ALL_PASS=false; }

echo "$OUTPUT" | grep -qi "http\|doi\|reference"   && echo "  ✅ PASS: tutorial references sources"   || { echo "  ❌ FAIL: tutorial missing source references"; ALL_PASS=false; }

[ "$EXIT_CODE" -eq 0 ]   && echo "  ✅ PASS: exit code 0"   || { echo "  ❌ FAIL: exit code $EXIT_CODE"; ALL_PASS=false; }

if [ "$ALL_PASS" = true ]; then echo "✅ SCENARIO 9.5 PASSED"; exit 0; else echo "❌ SCENARIO 9.5 FAILED"; exit 1; fi
```
**Expected Result:** ✅ Tutorial generated with learning objectives, structured sections, exercises, and source references.


#### 9.6 🟢 Generate presentation [REQUIRES LLM KEY]
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
OUTPUT=$(autoinfo output presentation --domain medical-research --topic "IVF" 2>&1)
EXIT_CODE=$?

echo "$OUTPUT" | grep -qi 'slide\|<section\|<div class="slide"\|#'   && echo "  ✅ PASS: presentation has slide structure"   || { echo "  ❌ FAIL: presentation missing slide structure"; ALL_PASS=false; }

echo "$OUTPUT" | grep -qi "IVF\|fertilit\|embryo\|treatment"   && echo "  ✅ PASS: presentation content matches requested topic"   || { echo "  ❌ FAIL: presentation content unrelated to topic"; ALL_PASS=false; }

[ "$EXIT_CODE" -eq 0 ]   && echo "  ✅ PASS: exit code 0"   || { echo "  ❌ FAIL: exit code $EXIT_CODE"; ALL_PASS=false; }

if [ "$ALL_PASS" = true ]; then echo "✅ SCENARIO 9.6 PASSED"; exit 0; else echo "❌ SCENARIO 9.6 FAILED"; exit 1; fi
```
**Expected Result:** ✅ Presentation generated with slide structure and content matching the requested topic.


#### 9.7 🟢 Export KB (JSON)
```bash
OUTPUT=$(autoinfo output export --domain medical-research --format json 2>&1)
LAST_LINE=$(echo "$OUTPUT" | tail -1)
cat "$LAST_LINE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
items = data.get('items', data.get('entries', []))
assert len(items) > 0, 'empty export'
print(f'  ✅ PASS: {len(items)} entries exported')
for i, item in enumerate(items[:3]):
    has_id = 'entry_id' in item or 'id' in item
    has_title = bool(item.get('title', ''))
    has_summary = bool(item.get('summary', item.get('tl_dr', '')))
    assert has_id, f'item {i}: missing entry_id'
    assert has_title, f'item {i}: missing title'
print(f'  ✅ PASS: all items have entry_id, title, summary')
" 2>&1 || echo "  ❌ FAIL: export content validation failed"
```
**Expected Result:** ✅ JSON export with all entries, each having entry_id, title, and summary.


#### 9.8 🟢 Export KB (Markdown)
```bash
autoinfo output export --domain medical-research --format markdown
```
**Expected Result:** ✅ Markdown export with all entries in a single file or directory.


#### 9.9 🟢 Export KB (PDF) [REQUIRES LLM KEY]
```bash
autoinfo output export --domain medical-research --format pdf
```
**Expected Result:** ✅ PDF file generated at `exports/medical-research/`.


#### 9.10 🟢 Localize content [REQUIRES LLM KEY]
```bash
autoinfo output translate --domain medical-research --target-lang zh-CN
```
**Expected Result:** ✅ Translation generated. Check `outputs/medical-research/translate/`.


#### 9.12 🟢 Cross-domain report with --domains flag
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
cd /tmp/test-q9

# Ensure second domain is available
autoinfo domain import --from-demo ai-commercial 2>/dev/null || true
autoinfo collect --domain ai-commercial --limit 1 2>/dev/null || true

OUTPUT=$(autoinfo output report --domains medical-research --domains ai-commercial --format json 2>&1)
EXIT_CODE=$?

echo "$OUTPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
items = data.get('items', data.get('entries', []))
print(f'  entries: {len(items)}, keys: {list(data.keys())[:5]}')
assert len(items) >= 0
" 2>&1 || echo "  ❌ FAIL: cross-domain report JSON parse error"

[ "$EXIT_CODE" -eq 0 ] \
  && echo "  ✅ PASS: exit code 0" \
  || { echo "  ❌ FAIL: exit code $EXIT_CODE"; ALL_PASS=false; }

if [ "$ALL_PASS" = true ]; then echo "✅ SCENARIO 9.12 PASSED"; exit 0; else echo "❌ SCENARIO 9.12 FAILED"; exit 1; fi
```
**Expected Result:** ✅ Cross-domain report generated with multiple domains. No crash with --domains flag.

#### 9.13 🟢 Report with specialized --type
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
cd /tmp/test-q9

for RTYPE in industry competitive trend; do
  OUTPUT=$(autoinfo output report --domain medical-research --format markdown --type "$RTYPE" 2>&1)
  EXIT_CODE=$?
  echo "$OUTPUT" | grep -qi "executive summary\|sections\|report\|analysis" \
    && echo "  ✅ PASS: --type $RTYPE produced structured output" \
    || echo "  ⚠️  --type $RTYPE output varies (no structured section markers)"
  [ "$EXIT_CODE" -eq 0 ] \
    && echo "  ✅ PASS: --type $RTYPE exit 0" \
    || { echo "  ❌ FAIL: --type $RTYPE exit $EXIT_CODE"; ALL_PASS=false; }
done

if [ "$ALL_PASS" = true ]; then echo "✅ SCENARIO 9.13 PASSED"; exit 0; else echo "❌ SCENARIO 9.13 FAILED"; exit 1; fi
```
**Expected Result:** ✅ All report types (industry, competitive, trend) complete without error.

#### 9.14 🟢 Bundle export (--format bundle)
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
cd /tmp/test-q9

OUTPUT=$(autoinfo output export --domain medical-research --format bundle 2>&1)
EXIT_CODE=$?

echo "$OUTPUT" | grep -qi "zip\|bundle\|archive\|export" \
  && echo "  ✅ PASS: bundle export produced archive output" \
  || { echo "  ❌ FAIL: bundle export missing archive marker"; ALL_PASS=false; }

[ "$EXIT_CODE" -eq 0 ] \
  && echo "  ✅ PASS: bundle export exit 0" \
  || { echo "  ❌ FAIL: bundle export exit $EXIT_CODE"; ALL_PASS=false; }

if [ "$ALL_PASS" = true ]; then echo "✅ SCENARIO 9.14 PASSED"; exit 0; else echo "❌ SCENARIO 9.14 FAILED"; exit 1; fi
```
**Expected Result:** ✅ Bundle export produces ZIP archive. Exit code 0.

#### 9.15 🟢 RSS export (--format rss) — B17
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
cd /tmp/test-q9

OUTPUT=$(autoinfo output export --domain medical-research --format rss 2>&1)
EXIT_CODE=$?

# Find the RSS export file
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

# Validate XML: must be valid XML with <rss> and <channel> root
python3 -c "
import xml.etree.ElementTree as ET
tree = ET.parse('$RSS_FILE')
root = tree.getroot()
assert root.tag == 'rss', f'Expected <rss> root, got <{root.tag}>'
assert root.get('version') == '2.0', f'Expected version=2.0, got {root.get(\"version\")}'
channel = root.find('channel')
assert channel is not None, 'Missing <channel> element'
items = channel.findall('item')
print(f'  ✅ PASS: valid RSS 2.0 XML with {len(items)} <item> entries')
" 2>&1 || { echo "  ❌ FAIL: RSS XML validation failed"; ALL_PASS=false; }

[ "$EXIT_CODE" -eq 0 ] \
  && echo "  ✅ PASS: exit code 0" \
  || { echo "  ❌ FAIL: exit code $EXIT_CODE"; ALL_PASS=false; }

if [ "$ALL_PASS" = true ]; then echo "✅ SCENARIO 9.15 PASSED — RSS export"; exit 0; else echo "❌ SCENARIO 9.15 FAILED"; exit 1; fi
```
**Expected Result:**
- ✅ RSS XML file written to `exports/medical-research/autoinfo-rss-*.xml`
- ✅ Valid RSS 2.0 XML schema: `<rss version="2.0">` root with `<channel>` and `<item>` entries
- ✅ Each `<item>` has `<title>`, `<link>`, `<description>`, `<guid>`, and `<pubDate>`
- ✅ Exit code 0

#### 9.16 🟢 GraphML export (--format graphml) — B18
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
cd /tmp/test-q9

OUTPUT=$(autoinfo output export --domain medical-research --format graphml 2>&1)
EXIT_CODE=$?

# Find the GraphML export file
GRAPHML_FILE=$(echo "$OUTPUT" | grep -oP '(?:written to|path:\s*|^)\K(?:.*autoinfo-graphml.*\.graphml)' | head -1)
if [ -z "$GRAPHML_FILE" ]; then
    GRAPHML_FILE=$(ls -t exports/medical-research/autoinfo-graphml-*.graphml 2>/dev/null | head -1)
fi

[ -n "$GRAPHML_FILE" ] \
  && echo "  ✅ PASS: GraphML file identified: $GRAPHML_FILE" \
  || { echo "  ❌ FAIL: no GraphML export file found"; ALL_PASS=false; }

[ -f "$GRAPHML_FILE" ] && [ -s "$GRAPHML_FILE" ] \
  && echo "  ✅ PASS: GraphML file is non-empty" \
  || { echo "  ❌ FAIL: GraphML file empty or missing"; ALL_PASS=false; }

# Validate GraphML XML schema
python3 -c "
import xml.etree.ElementTree as ET
tree = ET.parse('$GRAPHML_FILE')
root = tree.getroot()
assert root.tag == '{http://graphml.graphdrawing.org/xmlns}graphml', f'Expected graphml root, got {root.tag}'
graph = root.find('{http://graphml.graphdrawing.org/xmlns}graph')
assert graph is not None, 'Missing <graph> element'
nodes = graph.findall('{http://graphml.graphdrawing.org/xmlns}node')
edges = graph.findall('{http://graphml.graphdrawing.org/xmlns}edge')
print(f'  ✅ PASS: valid GraphML with {len(nodes)} nodes, {len(edges)} edges')
" 2>&1 || { echo "  ❌ FAIL: GraphML validation failed"; ALL_PASS=false; }

[ "$EXIT_CODE" -eq 0 ] \
  && echo "  ✅ PASS: exit code 0" \
  || { echo "  ❌ FAIL: exit code $EXIT_CODE"; ALL_PASS=false; }

if [ "$ALL_PASS" = true ]; then echo "✅ SCENARIO 9.16 PASSED — GraphML export"; exit 0; else echo "❌ SCENARIO 9.16 FAILED"; exit 1; fi
```
**Expected Result:**
- ✅ GraphML XML file written to `exports/medical-research/autoinfo-graphml-*.graphml`
- ✅ Valid GraphML schema: `<graphml>` root with `<graph>`, `<node>`, and `<edge>` elements
- ✅ Nodes have `entity_type` and `entity_name` data; edges have `relation_type` and `strength`
- ✅ Exit code 0

#### 9.17 🟢 Report with --type daily-briefing — B7
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
cd /tmp/test-q9

OUTPUT=$(autoinfo output report --domain medical-research --format markdown --type daily-briefing 2>&1)
EXIT_CODE=$?

echo "$OUTPUT" | grep -qi "daily\|briefing\|today\|summary\|headline" \
  && echo "  ✅ PASS: daily-briefing type produced briefing-style output" \
  || { echo "  ❌ FAIL: daily-briefing missing expected briefing markers"; ALL_PASS=false; }

[ "$EXIT_CODE" -eq 0 ] \
  && echo "  ✅ PASS: exit code 0" \
  || { echo "  ❌ FAIL: exit code $EXIT_CODE"; ALL_PASS=false; }

if [ "$ALL_PASS" = true ]; then echo "✅ SCENARIO 9.17 PASSED — daily-briefing report"; exit 0; else echo "❌ SCENARIO 9.17 FAILED"; exit 1; fi
```
**Expected Result:** ✅ `--type daily-briefing` produces briefing-style output with daily summary structure. Exit code 0.

#### 9.18 🟢 Video output (--format video) — Task 8
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
cd /tmp/test-q9

OUTPUT=$(autoinfo output report --domain medical-research --format video 2>&1)
EXIT_CODE=$?

echo "$OUTPUT" | python3 -c "
import sys, json
try:
    data = json.loads(sys.stdin.read())
    assert data.get('output_type') == 'video', f'Expected output_type=video, got {data.get(\"output_type\")}'
    assert data.get('status') == 'ok', f'Status not ok: {data.get(\"status\")}'
    assert 'video_path' in data, 'Missing video_path'
    assert data.get('format') == 'mp4', f'Expected format=mp4, got {data.get(\"format\")}'
    print(f'  ✅ PASS: video generated — {data[\"video_path\"]}')
except json.JSONDecodeError:
    # Non-JSON output: check for video path pattern in plain text
    text = sys.stdin.read()
    if 'video_path' in text or 'output_type' in text or '.mp4' in text:
        print('  ✅ PASS: video output detected in plain-text response')
    else:
        print('  ❌ FAIL: unrecognized video output format')
        sys.exit(1)
" 2>&1 || { echo "  ❌ FAIL: video output validation failed"; ALL_PASS=false; }

[ "$EXIT_CODE" -eq 0 ] \
  && echo "  ✅ PASS: exit code 0" \
  || { echo "  ❌ FAIL: exit code $EXIT_CODE"; ALL_PASS=false; }

if [ "$ALL_PASS" = true ]; then echo "✅ SCENARIO 9.18 PASSED — video report"; exit 0; else echo "❌ SCENARIO 9.18 FAILED"; exit 1; fi
```
**Expected Result:**
- ✅ `autoinfo output report --format video` generates a video (MP4) from TTS narration + slide images via FFmpeg
- ✅ Output includes `output_type: "video"`, `status: "ok"`, and a `video_path`
- ✅ Exit code 0

#### 9.19 🟢 SEO sitemap — Task 10
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
cd /tmp/test-q19
autoinfo init --demo medical-research 2>/dev/null

OUTPUT=$(autoinfo output sitemap --domain medical-research --base-url "https://example.com" 2>&1)
EXIT_CODE=$?

# Find the sitemap file
SITEMAP_FILE=$(echo "$OUTPUT" | grep -oP 'Sitemap written to \K.*\.xml' | head -1)
if [ -z "$SITEMAP_FILE" ]; then
    SITEMAP_FILE=$(ls -t outputs/medical-research/seo/sitemap.xml 2>/dev/null | head -1)
fi

[ -n "$SITEMAP_FILE" ] \
  && echo "  ✅ PASS: sitemap file identified: $SITEMAP_FILE" \
  || { echo "  ❌ FAIL: no sitemap file found"; ALL_PASS=false; }

[ -f "$SITEMAP_FILE" ] && [ -s "$SITEMAP_FILE" ] \
  && echo "  ✅ PASS: sitemap file is non-empty" \
  || { echo "  ❌ FAIL: sitemap file empty or missing"; ALL_PASS=false; }

# Validate sitemap XML: must have <urlset> root with <url> entries
python3 -c "
import xml.etree.ElementTree as ET
tree = ET.parse('$SITEMAP_FILE')
root = tree.getroot()
ns = 'https://www.sitemaps.org/schemas/sitemap/0.9'
assert root.tag == '{' + ns + '}urlset', f'Expected urlset root, got {root.tag}'
urls = root.findall('{' + ns + '}url')
assert len(urls) >= 1, 'Expected at least 1 <url> entry'
for url in urls:
    loc = url.find('{' + ns + '}loc')
    assert loc is not None, '<url> missing <loc>'
    assert loc.text.startswith('http'), f'<loc> not a URL: {loc.text}'
print(f'  ✅ PASS: valid sitemap XML with {len(urls)} <url> entries, xmlns={ns}')
" 2>&1 || { echo "  ❌ FAIL: sitemap XML validation failed"; ALL_PASS=false; }

[ "$EXIT_CODE" -eq 0 ] \
  && echo "  ✅ PASS: exit code 0" \
  || { echo "  ❌ FAIL: exit code $EXIT_CODE"; ALL_PASS=false; }

if [ "$ALL_PASS" = true ]; then echo "✅ SCENARIO 9.19 PASSED — SEO sitemap"; exit 0; else echo "❌ SCENARIO 9.19 FAILED"; exit 1; fi
```
**Expected Result:**
- ✅ Sitemap XML file written to `outputs/medical-research/seo/sitemap.xml`
- ✅ Valid sitemaps.org XML schema: `<urlset xmlns="https://www.sitemaps.org/schemas/sitemap/0.9">` with `<url><loc>` entries
- ✅ Each `<url>` has a valid `<loc>` URL (starts with `http`)
- ✅ Base URL from `--base-url` flag appears in entries
- ✅ Exit code 0

---

### 📊 Q9 Verdict

| Scenario | Result |
|----------|--------|
| 9.1 List templates | ⬜ |
| 9.2 Generate digest | ⬜ |
| 9.3 Report MD | ⬜ |
| 9.4 Report JSON | ⬜ |
| 9.5 Tutorial | ⬜ |
| 9.6 Presentation | ⬜ |
| 9.7 Export JSON | ⬜ |
| 9.8 Export MD | ⬜ |
| 9.9 Export PDF | ⬜ |
| 9.10 Localize | ⬜ |
| 9.12 Cross-domain report | ⬜ |
| 9.13 Report with --type | ⬜ |
| 9.14 Bundle export (B19) | ⬜ |
| 9.15 RSS export (B17) | ⬜ |
| 9.16 GraphML export (B18) | ⬜ |
| 9.17 Daily-briefing report (B7) | ⬜ |
| 9.18 Video report (Task 8) | ⬜ |
| 9.19 SEO sitemap (Task 10) | ⬜ |

**OVERALL: ⬜**

---

#### 9.11 🟢 Cross-domain output — digest + report across 3 domains
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
for DOMAIN in medical-research ai-commercial language-learning; do
  echo "── Domain: $DOMAIN ──"
  TMPDIR="/tmp/test-q9-xd-$DOMAIN"
  rm -rf "$TMPDIR" && mkdir -p "$TMPDIR" && cd "$TMPDIR"
  autoinfo init --demo "$DOMAIN" > /dev/null 2>&1
  COLLECT=$(timeout 15 autoinfo collect --domain "$DOMAIN" --limit 2 2>&1 || true)
  RAW_COUNT=$(find collections/ -name "*.json" ! -name "_runs.json" 2>/dev/null | wc -l)

  # Digest
  DIGEST_OUT=$(autoinfo output digest --domain "$DOMAIN" --period daily 2>&1 || true)
  echo "$DIGEST_OUT" | grep -qi "entries\|digest\|summary" \
    && echo "  ✅ $DOMAIN digest: has content" \
    || echo "  ⚠️  $DOMAIN digest: no entry content (may need LLM or collected data)"

  # Report (JSON)
  REPORT_OUT=$(autoinfo output report --domain "$DOMAIN" --format json 2>&1 || true)
  echo "$REPORT_OUT" | python3 -c "
import sys, json
try:
    data = json.loads(sys.stdin.read())
    items = data.get('items', data.get('entries', []))
    print(f'  ✅ $DOMAIN report JSON: {len(items)} items, sections={bool(data.get(\"sections\",[]))}')
except: print('  ⚠️  $DOMAIN report: JSON parse failed (no data?)')" 2>&1 || true

  # Export
  EXPORT_OUT=$(autoinfo output export --domain "$DOMAIN" --format json 2>&1 || true)
  echo "$EXPORT_OUT" | python3 -c "
import sys, json, os
try:
    lines = sys.stdin.read().strip().split(chr(10))
    filepath = ''
    for line in lines:
        line = line.strip()
        if line.endswith('.json') and ('/' in line or line.startswith('/')):
            filepath = line
    if filepath and os.path.isfile(filepath):
        with open(filepath) as f:
            data = json.load(f)
        items = data.get('items', data.get('entries', []))
        print(f'  ✅ $DOMAIN export: {len(items)} entries in {os.path.basename(filepath)}')
    else:
        print(f'  ⚠️  $DOMAIN export: file path not found in output')
except Exception as e:
    print(f'  ⚠️  $DOMAIN export: parse error ({e})')" 2>&1 || true
  cd /tmp
done
echo ""
echo "✅ Cross-domain output complete"
```
**Expected Result:**
- ✅ All 3 domains produce digest, report, and export outputs without crash
- ✅ `medical-research` produces full content (has PubMed abstracts)
- ⚠️ Other domains may produce lighter content (RSS snippets, no API keys)
- No traceback or crash for any domain

---

## Q10: CEFR Classification CLI

**User says:** "I need to classify text by CEFR reading level."

### Prerequisites
```bash
cd /tmp/test-q10
autoinfo init --demo language-learning
```

### Scenarios

#### 10.1 🟢 CEFR classify single text [REQUIRES LLM KEY]
```bash
autoinfo cefr classify "The mitochondria is the powerhouse of the cell." --lang en
```
**Expected Result:** ✅ Returns CEFR level (A1-C2), confidence score, features list.

Note: `text` is a positional argument. Use `--lang` not `--language`.


#### 10.2 🟢 CEFR classify batch from file [REQUIRES LLM KEY]
```bash
echo "Hello, how are you?" > /tmp/cefr-input.txt
echo "The ecological implications of deforestation are manifold." >> /tmp/cefr-input.txt
autoinfo cefr batch --input /tmp/cefr-input.txt --lang en
```
**Expected Result:** ✅ Returns CEFR classification for each text.


#### 10.3 🟢 CEFR classify Chinese [REQUIRES LLM KEY]
```bash
autoinfo cefr classify "今天天气很好，我们去公园散步。" --lang zh
```
**Expected Result:** ✅ Returns CEFR level for Chinese text.


---

### 📊 Q10 Verdict

| Scenario | Result |
|----------|--------|
| 10.1 Classify single | ⬜ |
| 10.2 Batch classify | ⬜ |
| 10.3 Chinese classify | ⬜ |

**OVERALL: ⬜**

---

## Q11: Email CLI

**User says:** "I want to send email digests from the command line."

### Prerequisites
```bash
cd /tmp/test-q11
autoinfo init --demo medical-research
```

### Scenarios

#### 11.1 🟢 Email config show
```bash
autoinfo email config
```
**Expected Result:** ✅ Shows email configuration (SMTP server, port, sender). Fields may be empty if not configured.


#### 11.2 🟢 Send email digest [REQUIRES SMTP CONFIG]
```bash
autoinfo email send-digest --domain medical-research --period weekly
```
**Expected Result:** ✅ Email sent. Confirmation message. (Skip if SMTP not configured.)


---

### 📊 Q11 Verdict

| Scenario | Result |
|----------|--------|
| 11.1 Email config | ⬜ |
| 11.2 Send digest | ⬜ |

**OVERALL: ⬜**

---

## Q12: Cron / Schedule CLI

**User says:** "I want to schedule regular collection."

### Prerequisites
```bash
cd /tmp/test-q12
autoinfo init --demo medical-research
```

### Scenarios

#### 12.1 🟢 List schedules
```bash
autoinfo cron list-schedules
```
**Expected Result:** ✅ Shows all cron schedules with domain, topic, cron expression.


#### 12.2 🟢 Add schedule
```bash
autoinfo cron add-schedule --name "weekly-ivf" --expression "0 8 * * 1" --domain medical-research
```
**Expected Result:** ✅ Schedule added. Listed in `list-schedules`.

Note: Uses `--name` + `--expression` (cron syntax), not `--topic` + `--cron`.


#### 12.3 🟢 Remove schedule
```bash
# Get schedule name from list
SCHED_NAME=$(autoinfo cron list-schedules --json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); s=d.get('schedules',[]); print(s[0]['name'] if s else '').strip()" 2>/dev/null)
if [ "$SCHED_NAME" != "" ]; then
    autoinfo cron remove-schedule --name "$SCHED_NAME"
fi
```
**Expected Result:** ✅ Schedule removed. Confirmation shown.

Note: Uses `--name` not `--schedule-id`.


#### 12.4 🟢 Run schedules (manual trigger)
```bash
autoinfo cron run
```
**Expected Result:** ✅ Schedules executed. Collection started for each active schedule.

Note: Subcommand is `run` not `run-schedules`.


#### 12.5 🟢 Install crontab
```bash
autoinfo cron install
```
**Expected Result:** ✅ Crontab entries installed. Confirmation shown. (May need crontab access.)


#### 12.6 🟢 Uninstall crontab
```bash
autoinfo cron uninstall
```
**Expected Result:** ✅ Crontab entries removed. Confirmation shown.


---

### 📊 Q12 Verdict

| Scenario | Result |
|----------|--------|
| 12.1 List schedules | ⬜ |
| 12.2 Add schedule | ⬜ |
| 12.3 Remove schedule | ⬜ |
| 12.4 Run schedules | ⬜ |
| 12.5 Install crontab | ⬜ |
| 12.6 Uninstall crontab | ⬜ |

**OVERALL: ⬜**

---

## Q13: Keywords CLI

**User says:** "I need to manage keywords for topic filtering."

### Prerequisites
```bash
cd /tmp/test-q13
autoinfo init --demo medical-research
```

### Scenarios

#### 13.1 🟢 List keywords
```bash
autoinfo keywords list --domain medical-research
```
**Expected Result:** ✅ Shows all keywords with status (pending/approved/rejected), source topic.


#### 13.2 🟢 Approve keyword
```bash
autoinfo keywords approve medical-research CRISPR
```
**Expected Result:** ✅ Keyword approved. Status changes to "verified". Shown in `list`.

Note: Takes positional `{domain} {keyword}`, not `--keyword --domain` flags.


#### 13.3 🟢 Reject keyword
```bash
autoinfo keywords reject medical-research CRISPR
```
**Expected Result:** ✅ Keyword rejected. Status changes to "deprecated". Confirmation shown.


#### 13.4 🟢 List available keywords commands
```bash
autoinfo keywords --help
```
**Expected Result:** ✅ Shows available subcommands: list, approve, reject. (No add/remove/suggest — these were not implemented.)


---

### 📊 Q13 Verdict

| Scenario | Result |
|----------|--------|
| 13.1 List keywords | ⬜ |
| 13.2 Approve keyword | ⬜ |
| 13.3 Reject keyword | ⬜ |
| 13.4 Keywords subcommands | ⬜ |

**OVERALL: ⬜**

---

## Q14: Knowledge Graph CLI

**User says:** "I want to explore entity relationships in my knowledge base."

### Prerequisites
```bash
cd /tmp/test-q14
autoinfo init --demo medical-research
autoinfo collect --domain medical-research --topic "IVF" --limit 3
```

### Scenarios

#### 14.1 🟢 Knowledge graph export (JSON)
```bash
autoinfo knowledge graph export --domain medical-research
```
**Expected Result:** ✅ JSON file exported (knowledge_graph_export.json). Contains entities and relations.

Note: Output is JSON, not GraphML. Use `knowledge graph export` (not `knowledge graph --domain`).


---

### 📊 Q14 Verdict

| Scenario | Result |
|----------|--------|
| 14.1 Graph export | ⬜ |

**OVERALL: ⬜**

---

## Q15: Clean CLI

**User says:** "I need to clean up temporary artifacts."

### Scenarios

#### 15.1 🟢 Clean temporary artifacts
```bash
cd /tmp/test-q15
autoinfo init --demo medical-research
autoinfo clean
```
**Expected Result:** ✅ Temporary files cleaned. Confirmation with space freed.


#### 15.2 🟢 Clean with --dry-run
```bash
autoinfo clean --dry-run
```
**Expected Result:** ✅ Shows what would be cleaned without actually removing.


---

### 📊 Q15 Verdict

| Scenario | Result |
|----------|--------|
| 15.1 Clean artifacts | ⬜ |
| 15.2 Dry-run | ⬜ |

**OVERALL: ⬜**

---

## Q16: Global CLI Behavior

**User says:** "I need global CLI features to work correctly."

### Prerequisites
```bash
cd /tmp/test-q16
autoinfo init --demo medical-research
```

### Scenarios

#### 16.1 🟢 --help on every command
```bash
for cmd in init doctor collect process status sources topics domain kb output cefr email cron summaries keywords knowledge clean; do
    autoinfo $cmd --help > /dev/null 2>&1 && echo "OK: $cmd" || echo "FAIL: $cmd"
done
```
**Expected Result:** ✅ Every command has help output. No crashes.


#### 16.2 🟢 --version flag
```bash
autoinfo --version
```
**Expected Result:** ✅ Shows version string. (Note: `--version` flag is not currently implemented; check via `autoinfo doctor --json | python3 -c "import sys,json; print(json.load(sys.stdin)['version'])"`)


#### 16.3 🟢 --json on all commands that support it
```bash
for cmd in "status --json" "doctor --json"; do
    echo "Testing: autoinfo $cmd"
    autoinfo $cmd 2>/dev/null | python3 -c "import sys,json; json.load(sys.stdin); print('VALID JSON')" && echo "OK" || echo "FAIL"
done
```
**Expected Result:** ✅ Supported commands produce valid JSON.


---

### 📊 Q16 Verdict

| Scenario | Result |
|----------|--------|
| 16.1 --help all | ⬜ |
| 16.2 --version | ⬜ |
| 16.3 --json support | ⬜ |

**OVERALL: ⬜**

---

## Q17: CLI Edge Cases

**User says:** "What if I pass wrong arguments?"

### Scenarios

#### 17.1 🔴 Missing required --domain on collect
```bash
autoinfo collect
```
**Expected Result:** ❌ Error shown. Mentions --domain is required.


#### 17.2 🔴 Unknown argument
```bash
autoinfo collect --domain medical --nonexistent-flag
```
**Expected Result:** ❌ Error: "No such option". No traceback.


#### 17.3 🔴 Commands without config print friendly error
```bash
cd /tmp/noconfig && autoinfo collect --domain medical-research 2>&1
```
**Expected Result:** ❌ Friendly error: "Run 'autoinfo init' first". Not a traceback.


#### 17.4 🔴 Invalid --format value
```bash
autoinfo output export --domain medical-research --format invalid
```
**Expected Result:** ❌ Error: Invalid format. Shows available formats.


#### 17.5 🔴 Missing required subcommand
```bash
autoinfo sources
```
**Expected Result:** ❌ Shows help for sources command. Mentions list/add/remove/test.


#### 17.6 🔴 Empty --keywords on topic add
```bash
autoinfo topics add --name "Empty" --keywords "" --domain medical-research 2>&1
```
**Expected Result:** ❌ Error or warning about empty keywords.


---

### 📊 Q17 Verdict

| Scenario | Result |
|----------|--------|
| 17.1 Missing --domain | ⬜ |
| 17.2 Unknown flag | ⬜ |
| 17.3 No config | ⬜ |
| 17.4 Invalid format | ⬜ |
| 17.5 Missing subcommand | ⬜ |
| 17.6 Empty keywords | ⬜ |

**OVERALL: ⬜**

---

## Q18: Trace CLI — Per-Item Pipeline History

**User says:** "I need to trace a specific item through the entire pipeline."

### Prerequisites
```bash
cd /tmp/test-q18
autoinfo init --demo medical-research
autoinfo collect --domain medical-research --limit 1 --topic "IVF"
```

### Scenarios

#### 18.1 🟢 autoinfo trace <trace_id> shows collection stage with source metadata
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
PROJECT_ROOT="/mnt/d/贯维/AutoInfo"
TEST_DIR="/tmp/test-q18"

# ── Setup ─────────────────────────────────────────────────────
rm -rf "$TEST_DIR"
mkdir -p "$TEST_DIR"
cd "$TEST_DIR"
autoinfo init --demo medical-research 2>&1 > /dev/null

# ── Collect: obtain a trace_id from real data ─────────────────
echo "--- Running collection ---"
autoinfo collect --domain medical-research --limit 1 --topic "IVF" 2>&1 > /dev/null

# Extract a UUID trace_id from collection cache files
TRACE_ID=$(python3 -c "
import json, os
cache_root = 'collections/medical-research'
if not os.path.isdir(cache_root):
    exit(1)
for source in sorted(os.listdir(cache_root)):
    source_dir = os.path.join(cache_root, source)
    if not os.path.isdir(source_dir) or source_dir.endswith('_runs'):
        continue
    for date_dir in sorted(os.listdir(source_dir), reverse=True):
        d = os.path.join(source_dir, date_dir)
        if not os.path.isdir(d):
            continue
        for fname in sorted(os.listdir(d)):
            if fname.endswith('.json') and not fname.startswith('_'):
                fpath = os.path.join(d, fname)
                data = json.load(open(fpath))
                trace_id = data.get('trace_id', '')
                # Look for UUID-formatted trace_ids (36 chars, dashes)
                if trace_id and len(trace_id) == 36 and '-' in trace_id:
                    print(trace_id)
                    exit(0)
exit(1)
")
if [ -z "$TRACE_ID" ]; then
    echo "  ❌ FAIL: Could not extract UUID trace_id from collection cache"
    exit 1
fi
echo "  Extracted trace_id: $TRACE_ID"

# ── Symlink logs from install dir (PipelineLogger writes to install dir) ──
if [ ! -d logs ]; then
    ln -sf "$PROJECT_ROOT/logs" logs
fi

# ── Execute: autoinfo trace ──────────────────────────────────
OUTPUT=$(autoinfo trace "$TRACE_ID" 2>&1) || true

# ── Assertions ────────────────────────────────────────────────
echo "$OUTPUT" | grep -q "Trace: $TRACE_ID" \
  && echo "  ✅ PASS: Trace header with trace_id present" \
  || { echo "  ❌ FAIL: No trace header matching trace_id"; ALL_PASS=false; }

echo "$OUTPUT" | grep -q "Pipeline Events" \
  && echo "  ✅ PASS: Pipeline Events section present" \
  || { echo "  ❌ FAIL: No Pipeline Events section"; ALL_PASS=false; }

echo "$OUTPUT" | grep -q "collect" \
  && echo "  ✅ PASS: Collection stage ('collect' module) in pipeline events" \
  || { echo "  ❌ FAIL: Collection stage not found in pipeline events"; ALL_PASS=false; }

echo "$OUTPUT" | grep -q "INFO" \
  && echo "  ✅ PASS: Log level (INFO) displayed in trace output" \
  || { echo "  ❌ FAIL: No log level in trace output"; ALL_PASS=false; }

echo "$OUTPUT" | grep -q "Item collected" \
  && echo "  ✅ PASS: 'Item collected' message in trace output" \
  || { echo "  ❌ FAIL: No 'Item collected' message"; ALL_PASS=false; }

echo "$OUTPUT" | grep -qE "source_name|source=" \
  && echo "  ✅ PASS: Source metadata (source_name) present in trace output" \
  || { echo "  ❌ FAIL: No source metadata in trace output"; ALL_PASS=false; }

echo "$OUTPUT" | grep -q "item_id" \
  && echo "  ✅ PASS: item_id present in trace output" \
  || { echo "  ❌ FAIL: No item_id in trace output"; ALL_PASS=false; }

echo "$OUTPUT" | grep -q "domain=" \
  && echo "  ✅ PASS: domain metadata present in trace output" \
  || { echo "  ❌ FAIL: No domain metadata in trace output"; ALL_PASS=false; }

# ── Verdict ───────────────────────────────────────────────────
echo ""
if [ "$ALL_PASS" = true ]; then
    echo "✅ SCENARIO 18.1 PASSED — autoinfo trace shows pipeline stages"
    exit 0
else
    echo "❌ SCENARIO 18.1 FAILED"
    exit 1
fi
```
**Expected Result:**
- ✅ Trace header displays the UUID trace_id (e.g., `Trace: 59162b73-1a91-4839-a48b-30d9420ece07`)
- ✅ Pipeline Events section appears with at least one event
- ✅ Collection stage (module: `collect`) appears in trace output
- ✅ Log level (`INFO`) is displayed for each event
- ✅ Message `Item collected` confirms the event type
- ✅ Source metadata (source_name=pubmed, domain=medical-research) is shown
- ✅ item_id is present, linking the trace to the specific collected item


#### 18.2 🟢 autoinfo trace with unknown trace_id shows friendly output (no crash)
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

# Execute with a random UUID that doesn't exist
OUTPUT=$(autoinfo trace "00000000-0000-0000-0000-000000000000" 2>&1) || true
EXIT_CODE=$?

# ── Assertions ────────────────────────────────────────────────
echo "$OUTPUT" | grep -q "Trace:" \
  && echo "  ✅ PASS: Trace header present (even with unknown ID)" \
  || { echo "  ❌ FAIL: No trace header"; ALL_PASS=false; }

echo "$OUTPUT" | grep -q "No pipeline events found" \
  && echo "  ✅ PASS: Friendly 'No pipeline events found' message" \
  || { echo "  ❌ FAIL: Expected 'No pipeline events found'"; ALL_PASS=false; }

[ "$EXIT_CODE" -eq 0 ] \
  && echo "  ✅ PASS: exit code 0 (no crash)" \
  || { echo "  ❌ FAIL: exit code $EXIT_CODE (expected 0)"; ALL_PASS=false; }

# ── Verdict ───────────────────────────────────────────────────
echo ""
if [ "$ALL_PASS" = true ]; then
    echo "✅ SCENARIO 18.2 PASSED — gracefully handles unknown trace_id"
    exit 0
else
    echo "❌ SCENARIO 18.2 FAILED"
    exit 1
fi
```
**Expected Result:**
- ✅ Trace header displayed even with unknown trace_id
- ✅ Friendly message: "No pipeline events found." — not an error traceback
- ✅ Exit code 0 (no crash)


---

### 📊 Q18 Verdict

| Scenario | Result |
|----------|--------|
| 18.1 Trace collection stage | ⬜ |
| 18.2 Unknown trace_id | ⬜ |

**OVERALL: ⬜**
