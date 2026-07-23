# Part 2: Full CLI Surface Mastery (Q7-Q20)

**Coverage:** All 17 CLI commands with subcommands

---

## Q7: Domain Management CLI

**User says:** "I need to manage domains — create custom ones, list, activate, deactivate."

### Prerequisites
```bash
cd /tmp && rm -rf test-q7 && mkdir test-q7 && cd test-q7
autoinfo init --demo medical-research
```

### Scenarios

#### 7.1 🟢 Domain list
```bash
autoinfo domain list
```
**Expected Result:** ✅ Shows all domains with name, active status, source count.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 7.2 🟢 Domain show
```bash
autoinfo domain show --name medical-research
```
**Expected Result:** ✅ Shows detailed domain info: schema, sources, topics, quality tiers.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 7.3 🟢 Add custom domain
```bash
autoinfo domain add --name "my-custom" --description "My custom domain"
```
**Expected Result:** ✅ Domain added. Listed in `domain list`. Active by default.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 7.4 🟢 Activate domain
```bash
autoinfo domain deactivate --name "my-custom"
autoinfo domain activate --name "my-custom"
```
**Expected Result:** ✅ Domain reactivated. Status shown in `domain list`.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 7.5 🟢 Deactivate domain
```bash
autoinfo domain deactivate --name my-custom
```
**Expected Result:** ✅ Domain deactivated. No longer active for collection/processing.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 7.6 🔴 Remove domain
```bash
autoinfo domain remove --name my-custom
```
**Expected Result:** ✅ Domain removed. Confirmation shown.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 7.7 🔴 Remove demo domain (should warn)
```bash
autoinfo domain remove --name medical-research
```
**Expected Result:** ❌ Warning or error about removing demo domain. Confirmation required.

**Actual Result:** _________ **PASS / FAIL:** _________

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
cd /tmp && rm -rf test-q8 && mkdir test-q8 && cd test-q8
autoinfo init --demo medical-research
autoinfo collect --domain medical-research --topic "IVF" --limit 3
```

### Scenarios

#### 8.1 🟢 KB search (keyword)
```bash
autoinfo kb search --query "IVF" --domain medical-research
```
**Expected Result:** ✅ Returns matching entries with title, summary, relevance. Exit code 0.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 8.2 🟢 KB search with hybrid mode
```bash
autoinfo kb search --query "embryo development" --domain medical-research --mode hybrid
```
**Expected Result:** ✅ Returns entries using FTS5+vector hybrid search.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 8.3 🟢 KB create-draft [REQUIRES LLM KEY]
```bash
# Get first entry ID
ENTRY_ID=$(autoinfo summaries list --domain medical-research --json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['entries'][0]['entry_id'] if d.get('entries') else 'none')")
if [ "$ENTRY_ID" != "none" ]; then
    autoinfo kb create-draft --entry-id "$ENTRY_ID"
fi
```
**Expected Result:** ✅ Draft created in 02-Draft tier. File at `knowledge/medical-research/02-Draft/`.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 8.4 🟢 KB list-tiers
```bash
autoinfo kb list-tiers --domain medical-research
```
**Expected Result:** ✅ Shows entries per tier (01-Raw, 02-Draft, 03-Wiki) with counts.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 8.5 🟢 KB reject-draft
```bash
# Get entry_id from 02-Draft
ENTRY_ID=$(autoinfo kb list-tiers --domain medical-research --json 2>/dev/null | python3 -c "
import sys,json; d=json.load(sys.stdin)
for t in d.get('tiers', []):
    if t['tier'] == '02-Draft' and t.get('entries'):
        print(t['entries'][0]['entry_id'])
        break
" 2>/dev/null)
if [ "$ENTRY_ID" != "" ]; then
    autoinfo kb reject-draft --entry-id "$ENTRY_ID"
fi
```
**Expected Result:** ✅ Draft rejected. Entry remains in 01-Raw. 02-Draft copy removed.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 8.6 🟢 KB reindex
```bash
autoinfo kb reindex --domain medical-research
```
**Expected Result:** ✅ FTS5 index rebuilt. Confirmation with entry count.

**Actual Result:** _________ **PASS / FAIL:** _________

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
cd /tmp && rm -rf test-q9 && mkdir test-q9 && cd test-q9
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

**Actual Result:** _________ **PASS / FAIL:** _________

#### 9.2 🟢 Generate digest
```bash
autoinfo output digest --domain medical-research --period week
```
**Expected Result:** ✅ Digest generated. File at `outputs/medical-research/digest/<date>-digest.md`.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 9.3 🟢 Generate report (Markdown)
```bash
autoinfo output report --domain medical-research --format markdown
```
**Expected Result:** ✅ Report generated. File at `outputs/medical-research/report/`.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 9.4 🟢 Generate report (JSON)
```bash
autoinfo output report --domain medical-research --format json
```
**Expected Result:** ✅ Valid JSON report with entries array.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 9.5 🟢 Generate tutorial [REQUIRES LLM KEY]
```bash
autoinfo output tutorial --domain medical-research --topic "IVF"
```
**Expected Result:** ✅ Tutorial generated. Structured educational content.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 9.6 🟢 Generate presentation [REQUIRES LLM KEY]
```bash
autoinfo output presentation --domain medical-research --topic "IVF"
```
**Expected Result:** ✅ Presentation generated (HTML with Reveal.js). File at `outputs/`.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 9.7 🟢 Export KB (JSON)
```bash
autoinfo output export --domain medical-research --format json
```
**Expected Result:** ✅ JSON export written to `exports/medical-research/`. Valid JSON with all entries.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 9.8 🟢 Export KB (Markdown)
```bash
autoinfo output export --domain medical-research --format markdown
```
**Expected Result:** ✅ Markdown export with all entries in a single file or directory.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 9.9 🟢 Export KB (PDF) [REQUIRES LLM KEY]
```bash
autoinfo output export --domain medical-research --format pdf
```
**Expected Result:** ✅ PDF file generated at `exports/medical-research/`.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 9.10 🟢 Localize content [REQUIRES LLM KEY]
```bash
autoinfo output translate --domain medical-research --target-lang zh-CN
```
**Expected Result:** ✅ Translation generated. Check `outputs/medical-research/translate/`.

**Actual Result:** _________ **PASS / FAIL:** _________

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
cd /tmp && rm -rf test-q10 && mkdir test-q10 && cd test-q10
autoinfo init --demo language-learning
```

### Scenarios

#### 10.1 🟢 CEFR classify single text [REQUIRES LLM KEY]
```bash
autoinfo cefr classify --text "The mitochondria is the powerhouse of the cell." --language en
```
**Expected Result:** ✅ Returns CEFR level (A1-C2), confidence score, features list.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 10.2 🟢 CEFR classify batch from file [REQUIRES LLM KEY]
```bash
echo "Hello, how are you?" > /tmp/cefr-input.txt
echo "The ecological implications of deforestation are manifold." >> /tmp/cefr-input.txt
autoinfo cefr batch --input /tmp/cefr-input.txt --language en
```
**Expected Result:** ✅ Returns CEFR classification for each text.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 10.3 🟢 CEFR classify Chinese [REQUIRES LLM KEY]
```bash
autoinfo cefr classify --text "今天天气很好，我们去公园散步。" --language zh
```
**Expected Result:** ✅ Returns CEFR level for Chinese text.

**Actual Result:** _________ **PASS / FAIL:** _________

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
cd /tmp && rm -rf test-q11 && mkdir test-q11 && cd test-q11
autoinfo init --demo medical-research
```

### Scenarios

#### 11.1 🟢 Email config show
```bash
autoinfo email config
```
**Expected Result:** ✅ Shows email configuration (SMTP server, port, sender). Fields may be empty if not configured.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 11.2 🟢 Send email digest [REQUIRES SMTP CONFIG]
```bash
autoinfo email send --to user@example.com --subject "Weekly Digest" --domain medical-research --period week
```
**Expected Result:** ✅ Email sent. Confirmation message. (Skip if SMTP not configured.)

**Actual Result:** _________ **PASS / FAIL:** _________

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
cd /tmp && rm -rf test-q12 && mkdir test-q12 && cd test-q12
autoinfo init --demo medical-research
```

### Scenarios

#### 12.1 🟢 List schedules
```bash
autoinfo cron list-schedules
```
**Expected Result:** ✅ Shows all cron schedules with domain, topic, cron expression.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 12.2 🟢 Add schedule
```bash
autoinfo cron add-schedule --domain medical-research --topic "IVF" --cron "0 8 * * 1"
```
**Expected Result:** ✅ Schedule added. Listed in `list-schedules`.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 12.3 🟢 Remove schedule
```bash
# Get schedule ID from list
SCHED_ID=$(autoinfo cron list-schedules --json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); s=d.get('schedules',[]); print(s[0]['id'] if s else '')" 2>/dev/null)
if [ "$SCHED_ID" != "" ]; then
    autoinfo cron remove-schedule --schedule-id "$SCHED_ID"
fi
```
**Expected Result:** ✅ Schedule removed. Confirmation shown.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 12.4 🟢 Run schedules (manual trigger)
```bash
autoinfo cron run-schedules
```
**Expected Result:** ✅ Schedules executed. Collection started for each active schedule.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 12.5 🟢 Install crontab
```bash
autoinfo cron install
```
**Expected Result:** ✅ Crontab entries installed. Confirmation shown. (May need crontab access.)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 12.6 🟢 Uninstall crontab
```bash
autoinfo cron uninstall
```
**Expected Result:** ✅ Crontab entries removed. Confirmation shown.

**Actual Result:** _________ **PASS / FAIL:** _________

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
cd /tmp && rm -rf test-q13 && mkdir test-q13 && cd test-q13
autoinfo init --demo medical-research
```

### Scenarios

#### 13.1 🟢 List keywords
```bash
autoinfo keywords list --domain medical-research
```
**Expected Result:** ✅ Shows all keywords with status (pending/approved/rejected), source topic.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 13.2 🟢 Add keyword
```bash
autoinfo keywords add --keyword "CRISPR" --domain medical-research --source-topic "IVF"
```
**Expected Result:** ✅ Keyword added. Shown in `list`.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 13.3 🟢 Remove keyword
```bash
autoinfo keywords remove --keyword "CRISPR" --domain medical-research
```
**Expected Result:** ✅ Keyword removed. Confirmation shown.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 13.4 🟢 Suggest keywords [REQUIRES LLM KEY]
```bash
autoinfo keywords suggest --domain medical-research
```
**Expected Result:** ✅ LLM-suggested keywords returned. Shows new keyword candidates.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q13 Verdict

| Scenario | Result |
|----------|--------|
| 13.1 List keywords | ⬜ |
| 13.2 Add keyword | ⬜ |
| 13.3 Remove keyword | ⬜ |
| 13.4 Suggest keywords | ⬜ |

**OVERALL: ⬜**

---

## Q14: Knowledge Graph CLI

**User says:** "I want to explore entity relationships in my knowledge base."

### Prerequisites
```bash
cd /tmp && rm -rf test-q14 && mkdir test-q14 && cd test-q14
autoinfo init --demo medical-research
autoinfo collect --domain medical-research --topic "IVF" --limit 3
```

### Scenarios

#### 14.1 🟢 Knowledge graph export (GraphML)
```bash
autoinfo knowledge graph --domain medical-research
```
**Expected Result:** ✅ GraphML file exported. Contains entities and relations.

**Actual Result:** _________ **PASS / FAIL:** _________

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
cd /tmp && rm -rf test-q15 && mkdir test-q15 && cd test-q15
autoinfo init --demo medical-research
autoinfo clean
```
**Expected Result:** ✅ Temporary files cleaned. Confirmation with space freed.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 15.2 🟢 Clean with --dry-run
```bash
autoinfo clean --dry-run
```
**Expected Result:** ✅ Shows what would be cleaned without actually removing.

**Actual Result:** _________ **PASS / FAIL:** _________

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
cd /tmp && rm -rf test-q16 && mkdir test-q16 && cd test-q16
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

**Actual Result:** _________ **PASS / FAIL:** _________

#### 16.2 🟢 --version flag
```bash
autoinfo --version
```
**Expected Result:** ✅ Shows version string.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 16.3 🟢 --json on all commands that support it
```bash
for cmd in "status --json" "doctor --json"; do
    echo "Testing: autoinfo $cmd"
    autoinfo $cmd 2>/dev/null | python3 -c "import sys,json; json.load(sys.stdin); print('VALID JSON')" && echo "OK" || echo "FAIL"
done
```
**Expected Result:** ✅ Supported commands produce valid JSON.

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

#### 17.2 🔴 Unknown argument
```bash
autoinfo collect --domain medical --nonexistent-flag
```
**Expected Result:** ❌ Error: "No such option". No traceback.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 17.3 🔴 Commands without config print friendly error
```bash
cd /tmp/noconfig && autoinfo collect --domain medical-research 2>&1
```
**Expected Result:** ❌ Friendly error: "Run 'autoinfo init' first". Not a traceback.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 17.4 🔴 Invalid --format value
```bash
autoinfo output export --domain medical-research --format invalid
```
**Expected Result:** ❌ Error: Invalid format. Shows available formats.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 17.5 🔴 Missing required subcommand
```bash
autoinfo sources
```
**Expected Result:** ❌ Shows help for sources command. Mentions list/add/remove/test.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 17.6 🔴 Empty --keywords on topic add
```bash
autoinfo topics add --name "Empty" --keywords "" --domain medical-research 2>&1
```
**Expected Result:** ❌ Error or warning about empty keywords.

**Actual Result:** _________ **PASS / FAIL:** _________

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
