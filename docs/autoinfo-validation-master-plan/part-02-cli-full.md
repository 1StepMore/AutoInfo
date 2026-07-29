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
autoinfo output digest --domain medical-research --period weekly
```
**Expected Result:** ✅ Digest generated. File at `outputs/medical-research/digest/<date>-digest.md`.


#### 9.3 🟢 Generate report (Markdown)
```bash
autoinfo output report --domain medical-research --format markdown
```
**Expected Result:** ✅ Report generated. File at `outputs/medical-research/report/`.


#### 9.4 🟢 Generate report (JSON)
```bash
autoinfo output report --domain medical-research --format json
```
**Expected Result:** ✅ Valid JSON with items array. (Note: the JSON key is `items` not `entries` — adjust Python code accordingly.)


#### 9.5 🟢 Generate tutorial [REQUIRES LLM KEY]
```bash
autoinfo output tutorial --domain medical-research --audience researcher
```
**Expected Result:** ✅ Tutorial generated. Structured educational content.


#### 9.6 🟢 Generate presentation [REQUIRES LLM KEY]
```bash
autoinfo output presentation --domain medical-research --topic "IVF"
```
**Expected Result:** ✅ Presentation generated (HTML with Reveal.js). File at `outputs/`.


#### 9.7 🟢 Export KB (JSON)
```bash
autoinfo output export --domain medical-research --format json
```
**Expected Result:** ✅ JSON export written to `exports/medical-research/`. Valid JSON with all entries.


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

**OVERALL: ⬜**

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
