# Part 1: Core Pipeline Journeys (Q1-Q6)

**Files:** `README.md` ← `part-01-core-pipeline.md`
**Coverage:** Init → Collect → Process → Browse → Status → Doctor

---

## Q1: Can I initialize a project and configure sources?

**User says:** "I want to start tracking medical research. Give me a working project."

### Prerequisites
```bash
cd /tmp && rm -rf test-q1 && mkdir test-q1 && cd test-q1
```

### Scenarios

#### 1.1 🟢 Happy Path — Init with demo domain
```bash
autoinfo init --demo medical-research
```
**Expected Result:**
- ✅ Exit code 0
- ✅ `.autoinfo/config.yaml` created
- ✅ `.autoinfo/sources.yaml` created
- ✅ `knowledge/`, `collections/`, `outputs/` directories created
- ✅ Success message printed with next steps

**Actual Result:** _________ **PASS / FAIL:** _________

#### 1.2 🟢 Config is valid and parseable
```bash
python3 -c "
from autoinfo.config import load_config
cfg = load_config('.autoinfo/config.yaml')
print(f'Project: {cfg.project.name}')
print(f'LLM: {cfg.llm.provider}/{cfg.llm.model}')
print(f'Domains: {[d.name for d in cfg.domains]}')
for d in cfg.domains:
    print(f'  {d.name}: active={d.active}, sources={[s.name for s in d.sources]}, topics={[t.name for t in d.topics]}')
"
```
**Expected Result:**
- ✅ Config parses without error
- ✅ `cfg.project.name` is non-empty
- ✅ `cfg.llm.provider` matches default ("openrouter")
- ✅ `cfg.llm.model` matches default ("deepseek/deepseek-chat")
- ✅ At least one domain active with sources and topics

**Actual Result:** _________ **PASS / FAIL:** _________

#### 1.3 🟢 Init is idempotent
```bash
autoinfo init --demo medical-research
```
**Expected Result:** ✅ Exit code 0. Prints "SKIP" for existing files. No overwrite.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 1.4 🟢 Init without --demo lists available domains
```bash
autoinfo init
```
**Expected Result:** ✅ Prints available demo domains (medical-research, ai-commercial, language-learning). Exit code 0.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 1.5 🟢 Init with multiple demo domains
```bash
cd /tmp && rm -rf test-multi && mkdir test-multi && cd test-multi
autoinfo init --demo medical-research --demo ai-commercial
```
**Expected Result:** ✅ Both domains active. Config shows 2 domains with sources and topics.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 1.6 🔴 Init with unknown domain
```bash
autoinfo init --demo nonexistent-domain
```
**Expected Result:** ❌ Exit code != 0. Error message mentions unknown domain.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 1.7 🔴 Init with --name (named project)
```bash
cd /tmp && rm -rf test-named && mkdir test-named && cd test-named
autoinfo init --name "My Custom Project" --demo medical-research
```
**Expected Result:** ✅ Config has `project.name = "My Custom Project"`. Overrides default name.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q1 Verdict

| Scenario | Result |
|----------|--------|
| 1.1 Happy path init | ⬜ |
| 1.2 Config parseable | ⬜ |
| 1.3 Idempotent | ⬜ |
| 1.4 List domains | ⬜ |
| 1.5 Multi-demo init | ⬜ |
| 1.6 Unknown domain | ⬜ |
| 1.7 Named project | ⬜ |

**OVERALL: ⬜**

---

## Q2: Can I collect from all source types?

**User says:** "I configured my project. Now fetch items from my sources."

### Prerequisites
```bash
cd /tmp && rm -rf test-q2 && mkdir test-q2 && cd test-q2
autoinfo init --demo medical-research
```

### Scenarios

#### 2.1 🟢 Happy Path — Collect from PubMed
```bash
autoinfo collect --domain medical-research --topic "IVF" --limit 3
```
**Expected Result:**
- ✅ Exit code 0
- ✅ Progress shown per source
- ✅ Completion summary with item counts
- ✅ Items cached to `collections/medical-research/pubmed/<date>/<id>.json`
- ✅ Cached JSON has `source_url`, `title`, `content`, `source_type`, `source_platform`, `collected_at`

**Actual Result:** _________ **PASS / FAIL:** _________

#### 2.2 🟢 Dry-run returns estimates without storing
```bash
autoinfo collect --domain medical-research --topic "IVF" --limit 3 --dry-run
```
**Expected Result:**
- ✅ Exit code 0
- ✅ Output shows estimated item counts
- ✅ No files created in `collections/` directory

**Actual Result:** _________ **PASS / FAIL:** _________

#### 2.3 🟢 Collection with source filter
```bash
autoinfo collect --domain medical-research --topic "IVF" --source pubmed --limit 3
```
**Expected Result:** ✅ Only PubMed handler runs. Items collected successfully.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 2.4 🟢 Empty results handled gracefully
```bash
autoinfo collect --domain medical-research --topic "zzzzzznonexistent" --limit 3
```
**Expected Result:** ✅ Exit code 0. Message: "No new items" or similar. Not an error.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 2.5 🟢 RSS feed collection (ai-commercial domain)
```bash
cd /tmp && rm -rf test-rss && mkdir test-rss && cd test-rss
autoinfo init --demo ai-commercial
autoinfo collect --domain ai-commercial --source techcrunch --limit 5
```
**Expected Result:** ✅ RSS items collected with title, link, summary, published date. `source_type: "rss"`.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 2.6 🟢 Collection with JSON output
```bash
autoinfo collect --domain medical-research --topic "IVF" --limit 3 --json
```
**Expected Result:** ✅ Valid JSON output with collection results.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 2.7 🔴 Collection with missing config
```bash
cd /tmp/empty-dir && autoinfo collect --domain medical-research
```
**Expected Result:** ❌ Exit code != 0. "Run 'autoinfo init' first" error message.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q2 Verdict

| Scenario | Result |
|----------|--------|
| 2.1 PubMed collect | ⬜ |
| 2.2 Dry-run | ⬜ |
| 2.3 Source filter | ⬜ |
| 2.4 Empty results | ⬜ |
| 2.5 RSS collect | ⬜ |
| 2.6 JSON output | ⬜ |
| 2.7 Missing config | ⬜ |

**OVERALL: ⬜**

---

## Q3: Can I process collected items (LLM extraction + quality gates + KB storage)?

**User says:** "I collected some papers. Now extract structured summaries and store them."

### Prerequisites
```bash
cd /tmp && rm -rf test-q3 && mkdir test-q3 && cd test-q3
autoinfo init --demo medical-research
autoinfo collect --domain medical-research --topic "IVF" --limit 3
```

### Scenarios

#### 3.1 🟢 Happy Path — Process cached items [REQUIRES LLM KEY]
```bash
autoinfo process --domain medical-research
```
**Expected Result:**
- ✅ Exit code 0
- ✅ Per-item progress shown
- ✅ Summary: "N items → N passed gates → N KB entries created"
- ✅ Markdown files created in `knowledge/medical-research/01-Raw/ivf/`

**Actual Result:** _________ **PASS / FAIL:** _________

#### 3.2 🟢 KB entries have correct YAML frontmatter
```bash
head -20 knowledge/medical-research/01-Raw/ivf/*.md
```
**Expected Result:**
- ✅ YAML frontmatter with: title, domain, tier: 01-Raw, source_url, source_type, source_platform, collected_at, quality_tier, relevance_score
- ✅ Body contains original content + extracted TL;DR + key points

**Actual Result:** _________ **PASS / FAIL:** _________

#### 3.3 🟢 Collect + process in one step (--auto-process)
```bash
cd /tmp && rm -rf test-autoprocess && mkdir test-autoprocess && cd test-autoprocess
autoinfo init --demo medical-research
autoinfo collect --domain medical-research --topic "IVF" --limit 3 --auto-process
```
**Expected Result:**
- ✅ Both phases run
- ✅ Combined summary printed
- ✅ KB entries created (files in `knowledge/.../01-Raw/`)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 3.4 🟢 Processing with empty cache
```bash
cd /tmp && rm -rf test-empty && mkdir test-empty && cd test-empty
autoinfo init --demo medical-research
autoinfo process --domain medical-research
```
**Expected Result:** ✅ Exit code 0. Message: no cached items found.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 3.5 🟢 Process with specific model override [REQUIRES LLM KEY]
```bash
autoinfo process --domain medical-research --model "openrouter/deepseek/deepseek-chat"
```
**Expected Result:** ✅ Process uses specified model. KB entries created.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q3 Verdict

| Scenario | Result |
|----------|--------|
| 3.1 Happy path process | ⬜ |
| 3.2 KB frontmatter | ⬜ |
| 3.3 Auto-process | ⬜ |
| 3.4 Empty cache | ⬜ |
| 3.5 Model override | ⬜ |

**OVERALL: ⬜**

---

## Q4: Can I browse summaries, status, and health?

**User says:** "I processed some papers. Now show me what I have."

### Prerequisites
```bash
cd /tmp && rm -rf test-q4 && mkdir test-q4 && cd test-q4
autoinfo init --demo medical-research
autoinfo collect --domain medical-research --topic "IVF" --limit 3
autoinfo process --domain medical-research 2>/dev/null || echo "(LLM may fail, testing CLI surface only)"
```

### Scenarios

#### 4.1 🟢 Summaries list shows entries with TL;DR
```bash
autoinfo summaries list --domain medical-research
```
**Expected Result:**
- ✅ Exit code 0
- ✅ Shows entries with title, TL;DR (summary), relevance score, date
- ✅ --limit and --offset pagination works

**Actual Result:** _________ **PASS / FAIL:** _________

#### 4.2 🟢 Summaries list with JSON output
```bash
autoinfo summaries list --domain medical-research --json
```
**Expected Result:** ✅ Valid JSON with entries array. Each entry has title, summary, relevance_score, collected_at, tier.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 4.3 🟢 Show single summary
```bash
# Get first entry ID
ENTRY_ID=$(autoinfo summaries list --domain medical-research --json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['entries'][0]['entry_id'] if d.get('entries') else 'none')")
if [ "$ENTRY_ID" != "none" ]; then
    autoinfo summaries show --entry-id "$ENTRY_ID"
fi
```
**Expected Result:** ✅ Shows full entry details: title, content, TL;DR, key points, source metadata.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 4.4 🟢 Flag entry for KB
```bash
ENTRY_ID=$(autoinfo summaries list --domain medical-research --json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['entries'][0]['entry_id'] if d.get('entries') else 'none')")
if [ "$ENTRY_ID" != "none" ]; then
    autoinfo summaries flag --entry-id "$ENTRY_ID" --tags "important,review"
fi
```
**Expected Result:** ✅ Entry flagged. Tags stored in metadata.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 4.5 🟢 Status shows collection stats
```bash
autoinfo status
```
**Expected Result:**
- ✅ Shows items collected per domain
- ✅ Shows total KB entries per domain
- ✅ Shows source health per source

**Actual Result:** _________ **PASS / FAIL:** _________

#### 4.6 🟢 Status with --json
```bash
autoinfo status --json
```
**Expected Result:** ✅ Valid JSON with summary stats.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 4.7 🟢 Doctor checks all systems
```bash
autoinfo doctor
```
**Expected Result:**
- ✅ Checks Python version (≥3.11)
- ✅ Checks config exists and valid
- ✅ Reports LLM key status (configured or not)
- ✅ Reports source count and health
- ✅ No crashes, friendly output

**Actual Result:** _________ **PASS / FAIL:** _________

#### 4.8 🟢 Doctor with JSON output
```bash
autoinfo doctor --json
```
**Expected Result:** ✅ Valid JSON with python/config/llm/sources sections.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q4 Verdict

| Scenario | Result |
|----------|--------|
| 4.1 Summaries list | ⬜ |
| 4.2 Summaries JSON | ⬜ |
| 4.3 Show single summary | ⬜ |
| 4.4 Flag entry | ⬜ |
| 4.5 Status | ⬜ |
| 4.6 Status JSON | ⬜ |
| 4.7 Doctor | ⬜ |
| 4.8 Doctor JSON | ⬜ |

**OVERALL: ⬜**

---

## Q5: Source Management CLI

**User says:** "I want to manage my sources — add new ones, test them, list and remove old ones."

### Prerequisites
```bash
cd /tmp && rm -rf test-q5 && mkdir test-q5 && cd test-q5
autoinfo init --demo medical-research
```

### Scenarios

#### 5.1 🟢 Sources list
```bash
autoinfo sources list
```
**Expected Result:** ✅ Shows all configured sources with name, type, url, domain.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 5.2 🟢 Sources list with --domain filter
```bash
autoinfo sources list --domain medical-research
```
**Expected Result:** ✅ Filters to sources belonging to specified domain.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 5.3 🟢 Test source reachability
```bash
autoinfo sources test --name pubmed
```
**Expected Result:** ✅ Shows reachability result (ok/timeout/error) with latency.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 5.4 🟢 Add new source
```bash
autoinfo sources add --name my-rss --type rss --url https://example.com/feed --domain medical-research --quality-tier 2
```
**Expected Result:** ✅ Source added. Shows confirmation. Listed in `sources list`.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 5.5 🟢 Remove source
```bash
autoinfo sources remove --name my-rss
```
**Expected Result:** ✅ Source removed. Confirmation shown. No longer in `sources list`.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 5.6 🔴 Test nonexistent source
```bash
autoinfo sources test --name nonexistent-source
```
**Expected Result:** ❌ Error message: source not found. Exit code != 0.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 5.7 🔴 Add source with invalid type
```bash
autoinfo sources add --name bad-source --type invalid-type --url https://example.com --domain medical-research
```
**Expected Result:** ❌ Error: invalid source type. Shows available types.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q5 Verdict

| Scenario | Result |
|----------|--------|
| 5.1 Sources list | ⬜ |
| 5.2 Filter by domain | ⬜ |
| 5.3 Test source | ⬜ |
| 5.4 Add source | ⬜ |
| 5.5 Remove source | ⬜ |
| 5.6 Test nonexistent | ⬜ |
| 5.7 Invalid type | ⬜ |

**OVERALL: ⬜**

---

## Q6: Topic Management CLI

**User says:** "I need to manage topics and their keywords."

### Prerequisites
```bash
cd /tmp && rm -rf test-q6 && mkdir test-q6 && cd test-q6
autoinfo init --demo medical-research
```

### Scenarios

#### 6.1 🟢 Topics list
```bash
autoinfo topics list
```
**Expected Result:** ✅ Shows all topics with name, keywords, domain.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 6.2 🟢 Add new topic
```bash
autoinfo topics add --name "Gene Therapy" --keywords "CRISPR,gene editing,AAV" --domain medical-research
```
**Expected Result:** ✅ Topic added. Listed in `topics list`.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 6.3 🟢 Remove topic
```bash
autoinfo topics remove --name "Gene Therapy" --domain medical-research
```
**Expected Result:** ✅ Topic removed. Confirmation shown.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 6.4 🔴 Remove nonexistent topic
```bash
autoinfo topics remove --name "Nonexistent Topic" --domain medical-research
```
**Expected Result:** ❌ Error: topic not found.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q6 Verdict

| Scenario | Result |
|----------|--------|
| 6.1 Topics list | ⬜ |
| 6.2 Add topic | ⬜ |
| 6.3 Remove topic | ⬜ |
| 6.4 Remove nonexistent | ⬜ |

**OVERALL: ⬜**
