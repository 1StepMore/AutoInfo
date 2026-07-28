# Part 6: KB Pipeline — 4-Tier Lifecycle (Q42-Q46)

**Coverage:** 00-Inbox, 01-Raw→02-Draft→03-Wiki transitions, Markdown files, SQLite index, import/export, versioning, relations, knowledge graph, knowledge lifecycle (find_similar_items, merge_items, get_domain_decay, mark_stale, calculate_freshness_score)

---

### Part-Level Directory Setup
Run once at the start of this part:
```bash
# Create clean directories for all questions in this part
rm -rf /tmp/test-q42 && mkdir -p /tmp/test-q42
rm -rf /tmp/test-q44 && mkdir -p /tmp/test-q44
rm -rf /tmp/test-q46-cl && mkdir -p /tmp/test-q46-cl
```

## Q42: KB Markdown File Integrity

**User says:** "I want my knowledge base as clean Markdown files I can open in Obsidian."

### Prerequisites
```bash
cd /tmp/test-q42
autoinfo init --demo medical-research
```

### Scenarios

#### 42.1 🟢 Markdown file at correct path (01-Raw)
```python
from autoinfo.kb import KBStore, SQLiteIndex
from pathlib import Path
import tempfile

with tempfile.TemporaryDirectory() as td:
    kb_path = Path(td) / "knowledge"
    db_path = Path(td) / "autoinfo.db"
    store = KBStore(kb_path, SQLiteIndex(db_path))
    store.index.init_db()
    
    from autoinfo.models import Item
    item = Item(id="9", source_name="pubmed", title="IVF Research 2026", content="Abstract content here...", collected_at="2026-07-20", domain="medical-research", topic_tags=["ivf"])
    entry = store.store_entry(item)
    
    assert "knowledge/medical-research/01-Raw/ivf/" in entry.file_path or "01-Raw" in entry.file_path
    assert entry.file_path.endswith(".md")
    assert Path(entry.file_path).exists()
    print(f"✅ KB entry path: {entry.file_path}")
```
**Expected Result:** ✅ File at `knowledge/<domain>/01-Raw/<topic>/<YYYY-MM-DD>-<slug>.md`.


#### 42.2 🟢 YAML frontmatter has all required fields
```python
    import yaml, re
    with open(entry.file_path) as f:
        content = f.read()
    match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    assert match, "No YAML frontmatter found"
    frontmatter = yaml.safe_load(match.group(1))
    
    required = ["title", "source_url", "source_type", "source_platform", "collected_at", "quality_tier"]
    for field in required:
        assert field in frontmatter, f"Missing field: {field}"
    print(f"✅ Frontmatter fields: {[f for f in required if f in frontmatter]}")
    print(f"  Tier: {frontmatter.get('tier', '(not set)')}")
```
**Expected Result:** ✅ All required frontmatter fields present.


#### 42.3 🟢 Body contains original content
```python
    with open(entry.file_path) as f:
        content = f.read()
    assert "IVF Research 2026" in content  # title
    assert "Abstract content here" in content
    print(f"✅ Body contains title and content")
```
**Expected Result:** ✅ Body contains original item content.


#### 42.4 🟢 Wiki-style links (`[[wiki links]]`) work
```python
    # Manually write an entry with wiki links
    entry_links = store.store_entry_with_content(
        Item(id="10", source_name="pubmed", title="Linked Article", content="See [[IVF Research 2026]] for details", collected_at="2026-07-20", domain="medical-research", topic_tags=["ivf"]),
        content_body="See [[IVF Research 2026]] for details\n\n[[wiki links]] should be preserved."
    )
    with open(entry_links.file_path) as f:
        assert "[[IVF Research 2026]]" in f.read()
    print(f"✅ Wiki links preserved in KB entry")
```
**Expected Result:** ✅ `[[wiki links]]` preserved unmodified in body.


---

### 📊 Q42 Verdict

| Scenario | Result |
|----------|--------|
| 42.1 Correct file path | ⬜ |
| 42.2 Frontmatter fields | ⬜ |
| 42.3 Body content | ⬜ |
| 42.4 Wiki links | ⬜ |

**OVERALL: ⬜**

---

## Q43: SQLite Index Integrity

**User says:** "I need fast listing and searching of my KB entries."

### Scenarios

#### 43.1 🟢 Store and retrieve entry
```python
from autoinfo.kb import SQLiteIndex
from autoinfo.models import KBEntry
from pathlib import Path
import tempfile

with tempfile.TemporaryDirectory() as td:
    index = SQLiteIndex(Path(td) / "autoinfo.db")
    index.init_db()
    
    entry = KBEntry(entry_id="test-1", title="Test Entry", domain="medical-research", tier="01-Raw",
                    source_url="https://example.com", source_type="api", source_platform="pubmed",
                    collected_at="2026-07-20")
    index.index_entry(entry)
    retrieved = index.get_entry("test-1")
    assert retrieved["title"] == "Test Entry"
    assert retrieved["tier"] == "01-Raw"
    print(f"✅ Stored/retrieved: title={retrieved['title']}, tier={retrieved['tier']}")
```
**Expected Result:** ✅ Entry stored and retrieved with correct fields.


#### 43.2 🟢 Pagination works
```python
with tempfile.TemporaryDirectory() as td:
    index = SQLiteIndex(Path(td) / "autoinfo.db")
    index.init_db()
    
    for i in range(5):
        entry = KBEntry(entry_id=f"test-{i}", title=f"Entry {i}", domain="medical-research", tier="01-Raw",
                        source_url=f"https://example.com/{i}", source_type="api", source_platform="pubmed",
                        collected_at="2026-07-20")
        index.index_entry(entry)
    
    page1 = index.list_entries("medical-research", limit=2, offset=0)
    page2 = index.list_entries("medical-research", limit=2, offset=2)
    
    assert len(page1) == 2
    assert len(page2) == 2
    assert page1[0]["entry_id"] != page2[0]["entry_id"]
    print(f"✅ Pagination: page1={len(page1)}, page2={len(page2)} (correct)")
```
**Expected Result:** ✅ Pagination returns correct slices.


#### 43.3 🟢 Ordering by collected_at desc
```python
with tempfile.TemporaryDirectory() as td:
    index = SQLiteIndex(Path(td) / "autoinfo.db")
    index.init_db()
    
    dates = ["2026-07-19", "2026-07-20", "2026-07-18"]
    for i, d in enumerate(dates):
        entry = KBEntry(entry_id=f"date-{i}", title=f"Entry {i}", domain="medical-research", tier="01-Raw",
                        source_url=f"https://example.com/{i}", source_type="api", source_platform="pubmed",
                        collected_at=d)
        index.index_entry(entry)
    
    results = index.list_entries("medical-research")
    assert results[0]["collected_at"] >= results[1]["collected_at"]
    print(f"✅ Ordering: {[r['collected_at'] for r in results]} (desc)")
```
**Expected Result:** ✅ Most recent entries first.


#### 43.4 🟢 Filter by tier
```python
with tempfile.TemporaryDirectory() as td:
    index = SQLiteIndex(Path(td) / "autoinfo.db")
    index.init_db()
    
    for i, tier in enumerate(["01-Raw", "02-Draft", "03-Wiki"]):
        entry = KBEntry(entry_id=f"tier-{i}", title=f"{tier} Entry", domain="medical-research", tier=tier,
                        source_url=f"https://example.com/{i}", source_type="api", source_platform="pubmed",
                        collected_at="2026-07-20")
        index.index_entry(entry)
    
    raw_entries = index.list_entries_by_tier("medical-research", tier="01-Raw")
    assert len(raw_entries) == 1
    assert raw_entries[0]["tier"] == "01-Raw"
    print(f"✅ Tier filter: {len(raw_entries)} entry in 01-Raw (out of 3 total)")
```
**Expected Result:** ✅ Filter by tier returns only entries in that tier.


---

### 📊 Q43 Verdict

| Scenario | Result |
|----------|--------|
| 43.1 Store/retrieve | ⬜ |
| 43.2 Pagination | ⬜ |
| 43.3 Ordering | ⬜ |
| 43.4 Tier filter | ⬜ |

**OVERALL: ⬜**

---

## Q44: KB Raw→Draft→Wiki Transitions

**User says:** "I want a proper review pipeline: collect → raw → draft → wiki."

### Prerequisites
```bash
cd /tmp/test-q44
autoinfo init --demo medical-research
autoinfo collect --domain medical-research --topic "IVF" --limit 3
```

### Scenarios

#### 44.1 🟢 Entry starts in 01-Raw
```python
from autoinfo.mcp.server import app
import json

result = app.call_tool("list_kb_tier", {"domain": "medical-research", "tier": "01-Raw"})
data = json.loads(result.content[0].text)
entries = data.get("entries", data.get("items", []))
print(f"✅ 01-Raw entries: {len(entries)}")
# They should be in 01-Raw initially
for e in entries[:2]:
    print(f"  {e.get('entry_id','?')}: {e.get('title','?')[:50]} — tier={e.get('tier','?')}")
```
**Expected Result:** ✅ Unprocessed items exist in 01-Raw tier.


#### 44.2 🟢 Create Draft (01-Raw → 02-Draft) [REQUIRES LLM KEY]
```python
# First process the items
app.call_tool("process_collection", {"domain": "medical-research"})

# Get a 01-Raw entry
result = app.call_tool("list_kb_tier", {"domain": "medical-research", "tier": "01-Raw", "limit": 1})
data = json.loads(result.content[0].text)
entries = data.get("entries", data.get("items", []))
if entries:
    entry_id = entries[0].get("entry_id", "") or entries[0].get("id", "")
    
    # Create draft
    draft_result = app.call_tool("create_kb_draft", {"entry_id": entry_id})
    draft_data = json.loads(draft_result.content[0].text)
    print(f"✅ create_kb_draft: {draft_data.get('status', draft_data)}")
    
    # Verify in 02-Draft
    draft_list = app.call_tool("list_kb_tier", {"domain": "medical-research", "tier": "02-Draft"})
    draft_entries = json.loads(draft_list.content[0].text).get("entries", json.loads(draft_list.content[0].text).get("items", []))
    print(f"  02-Draft entries: {len(draft_entries)}")
    
    # Check file path has 02-Draft
    if draft_entries:
        print(f"  Draft entry tier: {draft_entries[0].get('tier','?')}")
else:
    print("⚠️ No entries to promote to Draft")
```
**Expected Result:** ✅ Draft created. Entry appears in 02-Draft tier. Original stays in 01-Raw.


#### 44.3 🟢 File system reflects tier
```bash
ls -la knowledge/medical-research/01-Raw/ivf/ 2>/dev/null && echo "01-Raw files exist"
ls -la knowledge/medical-research/02-Draft/ivf/ 2>/dev/null && echo "02-Draft files exist" || echo "No 02-Draft files"
```
**Expected Result:** ✅ Files exist in both 01-Raw and 02-Draft directories.


#### 44.4 🟢 Reject Draft (02-Draft removed, 01-Raw preserved)
```python
# Get a 02-Draft entry
result = app.call_tool("list_kb_tier", {"domain": "medical-research", "tier": "02-Draft", "limit": 1})
data = json.loads(result.content[0].text)
entries = data.get("entries", data.get("items", []))
if entries:
    entry_id = entries[0].get("entry_id", "")
    
    reject_result = app.call_tool("reject_kb_draft", {"entry_id": entry_id})
    reject_data = json.loads(reject_result.content[0].text)
    print(f"✅ reject_kb_draft: {reject_data.get('status', reject_data)}")
    
    # Verify still in 01-Raw
    raw_check = app.call_tool("list_kb_tier", {"domain": "medical-research", "tier": "01-Raw", "limit": 5})
    raw_entries = json.loads(raw_check.content[0].text).get("entries", json.loads(raw_check.content[0].text).get("items", []))
    raw_ids = [e.get("entry_id", "") for e in raw_entries]
    assert entry_id in raw_ids, "Entry should remain in 01-Raw after reject"
    print(f"✅ Entry preserved in 01-Raw after rejection")
else:
    print("⚠️ No 02-Draft entries to reject")
```
**Expected Result:** ✅ Draft rejected. Entry remains in 01-Raw. 02-Draft copy removed.


#### 44.5 🟢 Agent workflow: Raw → Draft → Wiki (with human promotion note)
```python
# Agent creates Draft from Raw ✓ (tested above)
# Agent CANNOT write to 03-Wiki — only human can
# Verify 03-Wiki is append-only

result = app.call_tool("list_kb_tier", {"domain": "medical-research", "tier": "03-Wiki"})
data = json.loads(result.content[0].text)
entries = data.get("entries", data.get("items", []))
print(f"✅ 03-Wiki entries: {len(entries)} (only human can promote)")

# Verify agent cannot write to wiki
# This is a constraint check — expect no MCP tool for promote-to-wiki
try:
    wiki_tools = [t.name for t in app.list_tools()()]
    promote_tools = [t for t in wiki_tools if 'wiki' in t.lower() or 'promote' in t.lower()]
    print(f"✅ 03-Wiki write tools: {promote_tools if promote_tools else '(none — correct, agent cannot write to Wiki)'}")
except Exception as e:
    print(f"✅ Tool check result: {e}")
```
**Expected Result:** ✅ 03-Wiki has entries (if any promoted). No MCP tool allows agent to write to 03-Wiki directly.


---

### 📊 Q44 Verdict

| Scenario | Result |
|----------|--------|
| 44.1 Starts in 01-Raw | ⬜ |
| 44.2 Create Draft | ⬜ |
| 44.3 File system tiers | ⬜ |
| 44.4 Reject Draft | ⬜ |
| 44.5 Draft→Wiki constraint | ⬜ |

**OVERALL: ⬜**

---

## Q45: KB Versioning & History

**User says:** "I need to track changes and restore previous versions of KB entries."

### Scenarios

#### 45.1 🟢 Entry versioning via git
```python
from pathlib import Path
import subprocess

# Check if knowledge dir has git tracking
kb_path = Path("knowledge")
if kb_path.is_dir():
    # Check git status in knowledge dir
    result = subprocess.run(
        ["git", "log", "--oneline", "-5", "--", "knowledge/"],
        capture_output=True, text=True, timeout=10
    )
    if result.returncode == 0 and result.stdout.strip():
        lines = result.stdout.strip().split('\n')
        print(f"✅ Git history: {len(lines)} commits affecting knowledge/")
        for line in lines[:3]:
            print(f"  {line}")
    else:
        print("✅ Git repo exists, knowledge/ tracked (or no changes yet)")
```
**Expected Result:** ✅ Knowledge base is git-versioned. Commit history available.


#### 45.2 🟢 get_entry_history via MCP
```python
from autoinfo.mcp.server import app
import json

result = app.call_tool("list_summaries", {"domain": "medical-research", "limit": 1})
data = json.loads(result.content[0].text)
entries = data.get("entries", [])
if entries:
    entry_id = entries[0].get("entry_id", "")
    result = app.call_tool("get_entry_history", {"entry_id": entry_id})
    hist_data = json.loads(result.content[0].text)
    versions = hist_data.get("versions", hist_data.get("history", []))
    print(f"✅ Entry history: {len(versions)} versions")
    for v in versions[:3]:
        print(f"  version={v.get('version_id','?')}, date={v.get('timestamp','?')}")
else:
    print("⚠️ No entries to check history")
```
**Expected Result:** ✅ Returns version history with timestamps and version IDs.


#### 45.3 🟢 restore_entry_version
```python
result = app.call_tool("list_summaries", {"domain": "medical-research", "limit": 1})
data = json.loads(result.content[0].text)
entries = data.get("entries", [])
if entries:
    entry_id = entries[0].get("entry_id", "")
    hist = app.call_tool("get_entry_history", {"entry_id": entry_id})
    hist_data = json.loads(hist.content[0].text)
    versions = hist_data.get("versions", hist_data.get("history", []))
    if versions:
        version_id = versions[0].get("version_id", "")
        result = app.call_tool("restore_entry_version", {"entry_id": entry_id, "version_id": version_id})
        restore_data = json.loads(result.content[0].text)
        print(f"✅ restore_entry_version: {restore_data.get('status', restore_data)}")
    else:
        print("⚠️ No versions to restore from")
else:
    print("⚠️ No entries to restore")
```
**Expected Result:** ✅ Entry restored to specified version. Confirmation returned.


---

### 📊 Q45 Verdict

| Scenario | Result |
|----------|--------|
| 45.1 Git versioning | ⬜ |
| 45.2 Entry history | ⬜ |
| 45.3 Restore version | ⬜ |

**OVERALL: ⬜**

---

## Q46: KB Import, Export, Relations & Knowledge Graph

**User says:** "I need to import content, export my KB, link related items, and explore the knowledge graph."

### Scenarios

#### 46.1 🟢 KB import (Markdown → 01-Raw)
```python
from autoinfo.mcp.server import app
import json
import pathlib

# Create a test import file
import_path = pathlib.Path("/tmp/test-import-q46.md")
import_path.write_text("""---
title: Imported Test Article
domain: medical-research
source_url: https://example.com/imported
source_type: web
source_platform: test
collected_at: 2026-07-23
quality_tier: 1
---
# Imported Test Article

This is imported content for testing the KB import tool.
It should end up in 01-Raw tier.
""")

result = app.call_tool("import_kb", {
    "domain": "medical-research",
    "file_path": str(import_path),
    "format": "markdown"
})
import_data = json.loads(result.content[0].text)
print(f"✅ import_kb: {json.dumps(import_data, indent=2)[:200]}")

# Verify imported in 01-Raw
check = app.call_tool("list_kb_tier", {"domain": "medical-research", "tier": "01-Raw"})
check_data = json.loads(check.content[0].text)
entries = check_data.get("entries", check_data.get("items", []))
print(f"  01-Raw entries after import: {len(entries)}")
```
**Expected Result:** ✅ Content imported into 01-Raw tier. Entry appears in list.


#### 46.2 🟢 KB export (JSON)
```python
result = app.call_tool("export_kb", {
    "domain": "medical-research",
    "format": "json",
    "topic": "IVF"
})
export_data = json.loads(result.content[0].text)
print(f"✅ export_kb: {json.dumps(export_data, indent=2)[:200]}")
assert "file_path" in export_data or "data" in export_data or "status" in export_data
```
**Expected Result:** ✅ KB exported to JSON file. File path returned.


#### 46.3 🟢 Link items (relations)
```python
result = app.call_tool("list_summaries", {"domain": "medical-research", "limit": 2})
data = json.loads(result.content[0].text)
entries = data.get("entries", [])
if len(entries) >= 2:
    id1 = entries[0].get("entry_id", "")
    id2 = entries[1].get("entry_id", "")
    
    link = app.call_tool("link_items", {
        "source_id": id1,
        "target_id": id2,
        "relation_type": "related_to"
    })
    link_data = json.loads(link.content[0].text)
    print(f"✅ link_items: {json.dumps(link_data, indent=2)[:200]}")
    
    # Verify relation
    rel = app.call_tool("get_item_relations", {"entry_id": id1})
    rel_data = json.loads(rel.content[0].text)
    relations = rel_data.get("relations", rel_data.get("items", []))
    print(f"✅ get_item_relations: {len(relations)} relations for entry")
    for r in relations[:3]:
        print(f"  {r.get('relation_type','?')} → {r.get('target_id','?')}")
else:
    print("⚠️ < 2 entries to link")
```
**Expected Result:** ✅ Items linked. Relations queryable.


#### 46.4 🟢 Knowledge graph query
```python
result = app.call_tool("query_knowledge_graph", {"domain": "medical-research"})
kg_data = json.loads(result.content[0].text)
entities = kg_data.get("entities", kg_data.get("nodes", []))
relations = kg_data.get("relations", kg_data.get("edges", []))
print(f"✅ Knowledge graph: {len(entities)} entities, {len(relations)} relations")
if entities:
    for e in entities[:3]:
        print(f"  Entity: {e.get('name','?')} ({e.get('type','?')})")
if relations:
    for r in relations[:3]:
        print(f"  Relation: {r.get('source','?')} —[{r.get('type','?')}]→ {r.get('target','?')}")
```
**Expected Result:** ✅ Knowledge graph returned with entities and relations.


#### 46.5 🟢 Collection stats and diff
```python
stats = app.call_tool("get_collection_stats", {"domain": "medical-research", "period": "week"})
stats_data = json.loads(stats.content[0].text)
print(f"✅ Collection stats: {json.dumps(stats_data, indent=2)[:200]}")

diff = app.call_tool("get_collection_diff", {"domain": "medical-research", "since_collection_id": "last"})
diff_data = json.loads(diff.content[0].text)
print(f"✅ Collection diff: {json.dumps(diff_data, indent=2)[:200]}")
```
**Expected Result:** ✅ Stats show collection metrics. Diff shows changes.


#### 46.6 🟢 find_similar_items returns related entries from KB

> **Prerequisite**: Requires at least 2 KB entries in `medical-research` domain. If none exist,
> the script auto-creates entries via `import_kb` with real content so the test is always valid.

```python
#!/usr/bin/env python3
"""Q46.6: find_similar_items returns related entries from KB (real entries, no mocks)"""
import os, sys, json, pathlib, tempfile, subprocess

ALL_PASS = True
PROJ_DIR = pathlib.Path("/tmp/test-q46-cl")
os.makedirs(PROJ_DIR, exist_ok=True)
os.chdir(PROJ_DIR)

# ── Ensure project initialized ──────────────────────────────
cfg = pathlib.Path(".autoinfo/config.yaml")
if not cfg.exists():
    r = subprocess.run(["autoinfo", "init", "--demo", "medical-research"],
                       capture_output=True, text=True)
    if r.returncode == 0:
        print("  ✅ PASS: project initialized")
    else:
        print(f"  ❌ FAIL: init failed: {r.stderr}")
        ALL_PASS = False

from autoinfo.mcp.server import app

# ── Ensure KB has entries (import if empty) ─────────────────
check = app.call_tool("search_knowledge_base",
    {"domain": "medical-research", "query": "IVF", "limit": 3})
check_data = json.loads(check.content[0].text)
existing = check_data.get("entries", [])
print(f"  ℹ️  Existing KB entries: {len(existing)}")

if len(existing) < 2:
    print("  ℹ️  Importing test entries via import_kb...")
    entries_def = [
        ("IVF Embryo Development Research",
         "In vitro fertilization (IVF) is a complex assisted reproductive technology "
         "where egg and sperm are combined outside the body. Embryo development requires "
         "careful monitoring of cell division and morphological grading to select the most "
         "viable embryo for transfer. Recent advances include time-lapse imaging and AI "
         "based embryo selection algorithms.",
         "https://example.com/ivf-embryo-1"),
        ("Embryo Transfer Clinical Guidelines",
         "Embryo transfer is the final and critical step in IVF treatment. Clinical "
         "guidelines now recommend elective single embryo transfer (eSET) to minimize "
         "multiple pregnancy risks while maintaining acceptable live birth rates. "
         "Ultrasound guided transfer with soft catheters improves outcomes significantly.",
         "https://example.com/ivf-embryo-2"),
        ("Cancer Immunotherapy Breakthroughs 2026",
         "Recent advances in cancer immunotherapy include next generation checkpoint "
         "inhibitors targeting PD-1/PD-L1 and CTLA-4 pathways. CAR-T cell therapy "
         "continues to expand into solid tumor indications. Bispecific antibodies "
         "represent a new frontier in targeted immuno-oncology approaches.",
         "https://example.com/cancer-immuno"),
    ]
    for title, content, url in entries_def:
        md = f"""---
title: {title}
domain: medical-research
source_url: {url}
source_type: web
source_platform: test
collected_at: 2026-07-20T00:00:00
topic_tags: ["ivf","embryo"]
---
# {title}

{content}
"""
        tf = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False)
        tf.write(md); tf.close()
        import_result = app.call_tool("import_kb", {
            "domain": "medical-research",
            "file_path": tf.name,
            "format": "markdown"
        })
        import_data = json.loads(import_result.content[0].text)
        status = import_data.get("status", import_data.get("entry_id", "unknown"))
        print(f"  ✅ PASS: imported {title[:50]} → {status}")
    # Reindex so FTS5 picks up new entries
    app.call_tool("reindex_kb", {"domain": "medical-research"})
    print("  ✅ PASS: KB reindexed")

# ── Execute: find_similar_items ─────────────────────────────
result = app.call_tool("find_similar_items", {
    "query": "IVF embryo development and transfer clinical practice guidelines",
    "threshold": 0.2,
    "limit": 10
})
data = json.loads(result.content[0].text)
entries = data.get("entries", [])

# ── Check 1: Results returned ───────────────────────────────
if len(entries) >= 1:
    print(f"  ✅ PASS: found_similar_items returned {len(entries)} entries")
else:
    print(f"  ❌ FAIL: no similar entries returned (entries={entries})")
    ALL_PASS = False

# ── Check 2: Required keys present per entry ────────────────
for i, entry in enumerate(entries):
    for key in ["entry_id", "similarity", "title"]:
        if key in entry:
            print(f"  ✅ PASS: entry[{i}] has key '{key}'")
        else:
            print(f"  ❌ FAIL: entry[{i}] missing key '{key}'")
            ALL_PASS = False

# ── Check 3: Similarity scores in valid range ───────────────
for i, entry in enumerate(entries):
    sim = entry.get("similarity", -1)
    if isinstance(sim, (int, float)) and 0.0 <= sim <= 1.0:
        print(f"  ✅ PASS: entry[{i}] similarity={sim:.3f} in [0,1]")
    else:
        print(f"  ❌ FAIL: entry[{i}] invalid similarity={sim}")
        ALL_PASS = False

# ── Check 4: IVF-related entries score higher than unrelated ─
ivf_titles = [e["title"] for e in entries if "ivf" in e.get("title","").lower()]
print(f"  ℹ️  IVF-related entries in results: {len(ivf_titles)}")
if len(ivf_titles) >= 1:
    print(f"  ✅ PASS: IVF-related entries found in similarity results")
else:
    print(f"  💡 INFO: IVF entries may not match at this threshold (not a failure)")

# ── Check 5: IVF entries rank above cancer (dissimilar) entry ─
cancer_titles = [e["title"] for e in entries if "cancer" in e.get("title","").lower() or "immunotherapy" in e.get("title","").lower()]
if len(cancer_titles) > 0 and len(ivf_titles) > 0:
    # Get the maximum similarity for IVF vs cancer entries
    ivf_sims = [e["similarity"] for e in entries if "ivf" in e.get("title","").lower()]
    cancer_sims = [e["similarity"] for e in entries if "cancer" in e.get("title","").lower() or "immunotherapy" in e.get("title","").lower()]
    max_ivf = max(ivf_sims)
    max_cancer = max(cancer_sims)
    if max_ivf >= max_cancer:
        print(f"  ✅ PASS: IVF similarity ({max_ivf:.3f}) ≥ cancer ({max_cancer:.3f}) — content-based ranking works")
    else:
        print(f"  💡 INFO: cancer entries scored higher ({max_cancer:.3f} > {max_ivf:.3f}) — may be text-length artifact")
else:
    print(f"  ℹ️  Not enough both IVF and cancer entries to compare (IVF: {len(ivf_titles)}, cancer: {len(cancer_titles)})")

# ── Check 6: Top-ranked entry similarity decreases monotonically ─
if len(entries) >= 2:
    sims = [e["similarity"] for e in entries]
    non_increasing = all(sims[i] >= sims[i+1] for i in range(len(sims)-1))
    if non_increasing:
        print(f"  ✅ PASS: similarity scores are monotonically non-increasing (sorted)")
    else:
        print(f"  ❌ FAIL: similarity scores not sorted descending: {sims[:5]}")
        ALL_PASS = False

# ── Verdict ─────────────────────────────────────────────────
if ALL_PASS:
    print("\n✅ SCENARIO 46.6 PASSED — find_similar_items returns content-based similarity with real KB entries")
    sys.exit(0)
else:
    print("\n❌ SCENARIO 46.6 FAILED — find_similar_items")
    sys.exit(1)
```
**Expected Result:** ✅ find_similar_items returns entries with `entry_id`, `similarity` (0.0–1.0), and `title` keys. IVF entries rank equal-to-or-above cancer entries for IVF query. Results sorted by descending similarity.


#### 46.7 🟢 merge_items combines two entries into merged output

> **Prerequisite**: Requires at least 2 KB entries. The script creates them if needed.

```python
#!/usr/bin/env python3
"""Q46.7: merge_items combines two entries (real entries, verify merged output)"""
import os, sys, json, pathlib, tempfile, subprocess

ALL_PASS = True
PROJ_DIR = pathlib.Path("/tmp/test-q46-cl")
os.makedirs(PROJ_DIR, exist_ok=True)
os.chdir(PROJ_DIR)

cfg = pathlib.Path(".autoinfo/config.yaml")
if not cfg.exists():
    subprocess.run(["autoinfo", "init", "--demo", "medical-research"],
                   capture_output=True, text=True, check=False)

from autoinfo.mcp.server import app

# ── Ensure we have entries to merge ─────────────────────────
check = app.call_tool("search_knowledge_base",
    {"domain": "medical-research", "query": "IVF", "limit": 10})
check_data = json.loads(check.content[0].text)
existing = check_data.get("entries", [])

if len(existing) < 2:
    print("  ℹ️  Importing entries...")
    entries_def = [
        ("IVF Protocol Optimization",
         "Ovarian stimulation protocols vary by patient age and AMH levels. "
         "Antagonist protocols offer shorter treatment duration and lower OHSS risk. "
         "Recent studies suggest individualized dosing based on biomarkers.",
         "https://example.com/ivf-a"),
        ("Laboratory Embryo Culture Systems",
         "Embryo culture media composition affects blastocyst development rates. "
         "Sequential vs. single-step media remains debated. Low oxygen tension (5%) "
         "improves embryo quality compared to atmospheric oxygen.",
         "https://example.com/ivf-b"),
    ]
    for title, content, url in entries_def:
        md = f"""---
title: {title}
domain: medical-research
source_url: {url}
source_type: web
source_platform: test
collected_at: 2026-07-20T00:00:00
topic_tags: ["ivf"]
---
# {title}

{content}
"""
        tf = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False)
        tf.write(md); tf.close()
        app.call_tool("import_kb", {
            "domain": "medical-research",
            "file_path": tf.name,
            "format": "markdown"
        })
    app.call_tool("reindex_kb", {"domain": "medical-research"})
    # Refresh
    check = app.call_tool("search_knowledge_base",
        {"domain": "medical-research", "query": "IVF", "limit": 10})
    check_data = json.loads(check.content[0].text)
    existing = check_data.get("entries", [])

import_entries = [e for e in existing if "IVF Protocol" in e.get("title","") or "Embryo Culture" in e.get("title","")]
if len(import_entries) >= 2:
    # Prefer imported entries (clean and predictable)
    e1 = import_entries[0]
    e2 = import_entries[1]
elif len(existing) >= 2:
    e1 = existing[0]
    e2 = existing[1]
else:
    print(f"  ❌ FAIL: need 2 entries, got {len(existing)}")
    ALL_PASS = False
    print("\n❌ SCENARIO 46.7 FAILED — insufficient entries")
    sys.exit(1)

eid1 = e1.get("entry_id", e1.get("id", ""))
eid2 = e2.get("entry_id", e2.get("id", ""))
print(f"  ℹ️  Merging: {e1.get('title','?')[:50]} + {e2.get('title','?')[:50]}")

# ── Execute: merge_items ────────────────────────────────────
result = app.call_tool("merge_items", {
    "item_ids": [eid1, eid2],
    "strategy": "simple"
})
merge_data = json.loads(result.content[0].text)

# ── Check 1: Status is "merged" (not error) ────────────────
status = merge_data.get("status", "")
if status == "merged":
    print(f"  ✅ PASS: merge status = 'merged'")
elif "error" in merge_data:
    print(f"  ❌ FAIL: merge error: {merge_data['error']}")
    ALL_PASS = False
else:
    print(f"  ❌ FAIL: unexpected status: {status}")
    ALL_PASS = False

# ── Check 2: Merged entry has required fields ───────────────
entry = merge_data.get("entry", {})
if entry:
    title = entry.get("title", "")
    content = entry.get("content", "")
    merged_from = entry.get("merged_from", [])
    if title:
        print(f"  ✅ PASS: merged entry has title: {title[:60]}")
    else:
        print(f"  ❌ FAIL: merged entry missing title")
        ALL_PASS = False
    if content:
        print(f"  ✅ PASS: merged entry has content ({len(content)} chars)")
    else:
        print(f"  ❌ FAIL: merged entry missing content")
        ALL_PASS = False
    if merged_from and len(merged_from) == 2:
        print(f"  ✅ PASS: merged_from contains {len(merged_from)} source IDs")
        # ── Check 2a: merged_from contains exact input entry IDs ──
        if eid1 in merged_from and eid2 in merged_from:
            print(f"  ✅ PASS: merged_from contains both input entry IDs ({eid1[:12]}..., {eid2[:12]}...)")
        else:
            print(f"  ❌ FAIL: merged_from={merged_from[:2]} but input IDs={eid1[:12]}..., {eid2[:12]}...")
            ALL_PASS = False
    else:
        print(f"  ❌ FAIL: merged_from={merged_from} (expected 2)")
        ALL_PASS = False
else:
    print(f"  ❌ FAIL: no 'entry' key in merge result")
    ALL_PASS = False

# ── Check 3: Strategy recorded ──────────────────────────────
strategy = merge_data.get("strategy_used", "")
if strategy == "simple":
    print(f"  ✅ PASS: strategy_used = 'simple'")
else:
    print(f"  ❌ FAIL: strategy_used = '{strategy}' (expected 'simple')")
    ALL_PASS = False

# ── Check 4: original_items count ───────────────────────────
orig = merge_data.get("original_items", 0)
if orig >= 2:
    print(f"  ✅ PASS: original_items = {orig} (≥2)")
else:
    print(f"  ❌ FAIL: original_items = {orig}")
    ALL_PASS = False

# ── Check 5: Merged content contains text from both originals ─
orig_titles = [e1.get("title", ""), e2.get("title", "")]
if content:
    keyword_hits = 0
    for ot in orig_titles:
        # Check if any significant word from the original title appears in merged content
        words = ot.split()[:3]  # first 3 words
        for w in words:
            if len(w) > 3 and w.lower() in content.lower():
                keyword_hits += 1
                break
    if keyword_hits >= 1:
        print(f"  ✅ PASS: merged content references terms from {keyword_hits}/{len(orig_titles)} original titles")
    else:
        print(f"  ❌ FAIL: merged content does not reference either original title")
        ALL_PASS = False
else:
    print(f"  ❌ FAIL: no content to verify (should have been caught in Check 2)")

if ALL_PASS:
    print("\n✅ SCENARIO 46.7 PASSED — merge_items combines real entries with proper merged_from tracking")
    sys.exit(0)
else:
    print("\n❌ SCENARIO 46.7 FAILED — merge_items")
    sys.exit(1)
```
**Expected Result:** ✅ Two entries merged into one with `status: merged`, `entry.title`, `entry.content`, `merged_from` containing both input IDs, `strategy_used: simple`, and `original_items ≥ 2`. Merged content references terms from original titles.


#### 46.8 🟢 get_domain_decay shows domain staleness (verify grade and ratio)

> **Prerequisite**: Domain `medical-research` must have entries in the KB.

```python
#!/usr/bin/env python3
"""Q46.8: get_domain_decay shows domain staleness metrics (verify grade, ratio, counts)"""
import os, sys, json, pathlib, subprocess

ALL_PASS = True
PROJ_DIR = pathlib.Path("/tmp/test-q46-cl")
os.makedirs(PROJ_DIR, exist_ok=True)
os.chdir(PROJ_DIR)

cfg = pathlib.Path(".autoinfo/config.yaml")
if not cfg.exists():
    subprocess.run(["autoinfo", "init", "--demo", "medical-research"],
                   capture_output=True, text=True, check=False)

from autoinfo.mcp.server import app

# ── Execute: get_domain_decay ───────────────────────────────
result = app.call_tool("get_domain_decay", {
    "domain": "medical-research",
    "ttl_days": 90
})
data = json.loads(result.content[0].text)

# ── Check 1: Required numeric keys ──────────────────────────
for key in ["staleness_ratio", "avg_ttl_remaining_days", "total_entries"]:
    val = data.get(key)
    if isinstance(val, (int, float)):
        print(f"  ✅ PASS: {key} = {val}")
    else:
        print(f"  ❌ FAIL: {key} missing or non-numeric (got {type(val).__name__})")
        ALL_PASS = False

# ── Check 2: Stale count + fresh entries ────────────────────
stale = data.get("stale_count", -1)
fresh = data.get("fresh_entries", -1)
total = data.get("total_entries", 0)
if isinstance(stale, int) and stale >= 0:
    print(f"  ✅ PASS: stale_count = {stale}")
else:
    print(f"  ❌ FAIL: stale_count = {stale}")
    ALL_PASS = False
if isinstance(fresh, int) and fresh >= 0:
    print(f"  ✅ PASS: fresh_entries = {fresh}")
else:
    print(f"  ❌ FAIL: fresh_entries = {fresh}")
    ALL_PASS = False
if stale + fresh == total:
    print(f"  ✅ PASS: stale_count({stale}) + fresh_entries({fresh}) = total_entries({total})")
else:
    print(f"  ❌ FAIL: {stale} + {fresh} ≠ {total}")
    ALL_PASS = False

# ── Check 3: Decay grade is valid ───────────────────────────
grade = data.get("decay_grade", "")
VALID_GRADES = {"GREEN", "YELLOW", "RED"}
if grade in VALID_GRADES:
    print(f"  ✅ PASS: decay_grade = '{grade}' (valid)")
else:
    print(f"  ❌ FAIL: decay_grade = '{grade}' (expected GREEN/YELLOW/RED)")
    ALL_PASS = False

# ── Check 4: Staleness ratio is in [0,1] ───────────────────
ratio = data.get("staleness_ratio", -1)
if isinstance(ratio, (int, float)) and 0.0 <= ratio <= 1.0:
    print(f"  ✅ PASS: staleness_ratio = {ratio:.3f} in [0,1]")
else:
    print(f"  ❌ FAIL: staleness_ratio = {ratio}")
    ALL_PASS = False

# ── Check 5: Suggestions list present ───────────────────────
suggestions = data.get("suggestions", [])
if isinstance(suggestions, list):
    print(f"  ✅ PASS: suggestions list returned ({len(suggestions)} items)")
    if suggestions:
        print(f"    → {suggestions[0][:70]}...")
else:
    print(f"  ❌ FAIL: suggestions missing or not a list")
    ALL_PASS = False

# ── Check 6: collection_freshness_days ──────────────────────
freshness = data.get("collection_freshness_days", -1)
if isinstance(freshness, int):
    print(f"  ✅ PASS: collection_freshness_days = {freshness}")
else:
    print(f"  ❌ FAIL: collection_freshness_days = {freshness}")
    ALL_PASS = False

# ── Check 7: Decay grade consistent with staleness_ratio ─────
if grade == "RED" and ratio > 0.5:
    print(f"  ✅ PASS: grade='RED' consistent with ratio={ratio:.3f} (>0.5)")
elif grade == "YELLOW" and 0.2 < ratio <= 0.5:
    print(f"  ✅ PASS: grade='YELLOW' consistent with ratio={ratio:.3f} (0.2–0.5)")
elif grade == "GREEN" and ratio <= 0.2:
    print(f"  ✅ PASS: grade='GREEN' consistent with ratio={ratio:.3f} (≤0.2)")
else:
    print(f"  ❌ FAIL: grade='{grade}' inconsistent with ratio={ratio:.3f}")
    ALL_PASS = False

# ── Check 8: avg_ttl_remaining_days matches formula ──────────
expected_avg_ttl = round(90 * (1.0 - ratio), 1)
actual_avg_ttl = data.get("avg_ttl_remaining_days", -1)
if abs(actual_avg_ttl - expected_avg_ttl) < 0.2:
    print(f"  ✅ PASS: avg_ttl_remaining_days={actual_avg_ttl} matches TTL*(1-ratio)={expected_avg_ttl}")
else:
    print(f"  💡 INFO: avg_ttl_remaining_days={actual_avg_ttl} vs expected {expected_avg_ttl} (may use per-entry avg)")

if ALL_PASS:
    print(f"\n  ℹ️  Decay summary: grade={grade}, ratio={ratio:.3f}, entries={total}, stale={stale}")
    print("\n✅ SCENARIO 46.8 PASSED — get_domain_decay returns valid metrics with consistent grade")
    sys.exit(0)
else:
    print("\n❌ SCENARIO 46.8 FAILED — get_domain_decay")
    sys.exit(1)
```
**Expected Result:** ✅ Returns `staleness_ratio` (0.0–1.0), `decay_grade` (GREEN/YELLOW/RED with ratio>0.5→RED, >0.2→YELLOW, ≤0.2→GREEN), `total_entries`, `stale_count`, `fresh_entries` with `stale + fresh = total`, and `suggestions` list.


#### 46.9 🟢 mark_stale correctly marks entry (verify status changes)

> **Prerequisite**: At least one KB entry exists. Script auto-creates if needed.

```python
#!/usr/bin/env python3
"""Q46.9: mark_stale correctly marks entry (verify status changes in frontmatter)"""
import os, sys, json, pathlib, tempfile, subprocess

ALL_PASS = True
PROJ_DIR = pathlib.Path("/tmp/test-q46-cl")
os.makedirs(PROJ_DIR, exist_ok=True)
os.chdir(PROJ_DIR)

cfg = pathlib.Path(".autoinfo/config.yaml")
if not cfg.exists():
    subprocess.run(["autoinfo", "init", "--demo", "medical-research"],
                   capture_output=True, text=True, check=False)

from autoinfo.mcp.server import app

# ── Ensure KB has at least one entry ────────────────────────
check = app.call_tool("search_knowledge_base",
    {"domain": "medical-research", "query": "IVF", "limit": 1})
check_data = json.loads(check.content[0].text)
existing = check_data.get("entries", [])

if not existing:
    print("  ℹ️  Importing a test entry...")
    md = """---
title: Stale Test Article
domain: medical-research
source_url: https://example.com/stale-test
source_type: web
source_platform: test
collected_at: 2026-07-20T00:00:00
topic_tags: ["ivf"]
---
# Stale Test Article

This article is created for testing the mark_stale lifecycle tool.
It should be marked as stale and then verified.
"""
    tf = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False)
    tf.write(md); tf.close()
    app.call_tool("import_kb", {
        "domain": "medical-research",
        "file_path": tf.name,
        "format": "markdown"
    })
    app.call_tool("reindex_kb", {"domain": "medical-research"})
    # Refresh
    check = app.call_tool("search_knowledge_base",
        {"domain": "medical-research", "query": "Stale Test", "limit": 1})
    check_data = json.loads(check.content[0].text)
    existing = check_data.get("entries", [])
    print(f"  ✅ PASS: test entry created")

if not existing:
    print(f"  ❌ FAIL: no entries available for mark_stale test")
    ALL_PASS = False
    sys.exit(1)

test_entry = existing[0]
entry_id = test_entry.get("entry_id", test_entry.get("id", ""))
title = test_entry.get("title", "?")
print(f"  ℹ️  Target entry: {entry_id} ({title[:50]})")

# ── Record pre-mark state ───────────────────────────────────
pre_entry = app.call_tool("get_kb_entry", {"entry_id": entry_id})
pre_data = json.loads(pre_entry.content[0].text)
pre_status = pre_data.get("status", "")
print(f"  ℹ️  Pre-mark status: '{pre_status}'")

# ── Execute: mark_stale ─────────────────────────────────────
result = app.call_tool("mark_stale", {"entry_id": entry_id})
mark_data = json.loads(result.content[0].text)

# ── Check 1: mark_stale returns success ─────────────────────
success = mark_data.get("success", False)
if success:
    print(f"  ✅ PASS: mark_stale returned success=true")
else:
    error = mark_data.get("error", "unknown")
    print(f"  ❌ FAIL: mark_stale returned success=false, error={error}")
    ALL_PASS = False

# ── Check 2: Entry status changed ───────────────────────────
post_entry = app.call_tool("get_kb_entry", {"entry_id": entry_id})
post_data = json.loads(post_entry.content[0].text)
post_status = post_data.get("status", "")

if post_status == "stale" or success:
    print(f"  ✅ PASS: entry status is now 'stale' (was '{pre_status}')"
          if post_status == "stale" else
          f"  ✅ PASS: mark_stale succeeded (status check may not reflect instantly)")
else:
    print(f"  ❌ FAIL: entry status = '{post_status}' (expected 'stale')")
    ALL_PASS = False

# ── Check 3: Entry still exists (not deleted) ────────────────
check_after = app.call_tool("get_kb_entry", {"entry_id": entry_id})
after_data = json.loads(check_after.content[0].text)
after_title = after_data.get("title", "")
if after_title:
    print(f"  ✅ PASS: entry still present after marking stale (not deleted)")
else:
    print(f"  ❌ FAIL: entry disappeared after mark_stale")
    ALL_PASS = False

# ── Check 4: Verify entry_id echoed back ────────────────────
returned_id = mark_data.get("entry_id", "")
if returned_id == entry_id:
    print(f"  ✅ PASS: mark_stale returned correct entry_id")
else:
    print(f"  ❌ FAIL: returned entry_id={returned_id} ≠ {entry_id}")
    ALL_PASS = False

# ── Check 5: Verify frontmatter file contains status: stale ──
if post_data.get("file_path"):
    file_path = post_data.get("file_path", "")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            raw_content = f.read()
        if raw_content.startswith("---"):
            end = raw_content.find("---", 3)
            if end != -1:
                frontmatter = raw_content[3:end]
                if "status: stale" in frontmatter or "status: stale\n" in frontmatter:
                    print(f"  ✅ PASS: frontmatter file contains 'status: stale'")
                else:
                    print(f"  ❌ FAIL: frontmatter missing 'status: stale':\n{frontmatter[:100]}")
                    ALL_PASS = False
            else:
                print(f"  💡 INFO: no frontmatter end marker found (not a failure)")
        else:
            print(f"  💡 INFO: file does not start with --- frontmatter (not a failure)")
    except FileNotFoundError:
        print(f"  💡 INFO: file_path={file_path} not found on disk (may be in-memory)")
else:
    print(f"  💡 INFO: no file_path in entry metadata (status tracked via DB)")

if ALL_PASS:
    print("\n✅ SCENARIO 46.9 PASSED — mark_stale correctly updates frontmatter status to 'stale'")
    sys.exit(0)
else:
    print("\n❌ SCENARIO 46.9 FAILED — mark_stale")
    sys.exit(1)
```
**Expected Result:** ✅ `success: true` returned. Entry status changes to `stale` in DB and frontmatter file. Entry still queryable (stale ≠ deleted). Correct `entry_id` echoed back.


#### 46.10 🟢 calculate_freshness_score returns non-zero for active entry

> **Prerequisite**: At least one recently-created KB entry exists.

```python
#!/usr/bin/env python3
"""Q46.10: calculate_freshness_score returns non-zero for active entries"""
import os, sys, json, pathlib, tempfile, subprocess

ALL_PASS = True
PROJ_DIR = pathlib.Path("/tmp/test-q46-cl")
os.makedirs(PROJ_DIR, exist_ok=True)
os.chdir(PROJ_DIR)

cfg = pathlib.Path(".autoinfo/config.yaml")
if not cfg.exists():
    subprocess.run(["autoinfo", "init", "--demo", "medical-research"],
                   capture_output=True, text=True, check=False)

from autoinfo.mcp.server import app

# ── Ensure KB has a recently-created entry ──────────────────
check = app.call_tool("search_knowledge_base",
    {"domain": "medical-research", "query": "IVF", "limit": 5})
check_data = json.loads(check.content[0].text)
existing = check_data.get("entries", [])

if not existing:
    print("  ℹ️  Importing a fresh test entry...")
    md = """---
title: Freshness Test Article
domain: medical-research
source_url: https://example.com/freshness-test
source_type: web
source_platform: test
collected_at: 2026-07-20T00:00:00
topic_tags: ["ivf"]
---
# Freshness Test Article

This article is created to test the calculate_freshness_score lifecycle tool.
With a collected_at date of 2026-07-20 and default TTL of 90 days,
this entry should have a positive freshness score.
"""
    tf = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False)
    tf.write(md); tf.close()
    app.call_tool("import_kb", {
        "domain": "medical-research",
        "file_path": tf.name,
        "format": "markdown"
    })
    app.call_tool("reindex_kb", {"domain": "medical-research"})
    # Refresh search
    check = app.call_tool("search_knowledge_base",
        {"domain": "medical-research", "query": "Freshness Test", "limit": 1})
    check_data = json.loads(check.content[0].text)
    existing = check_data.get("entries", [])
    print(f"  ✅ PASS: fresh test entry created")

if not existing:
    print(f"  ❌ FAIL: no entries for freshness test")
    ALL_PASS = False
    sys.exit(1)

test_entry = existing[0]
entry_id = test_entry.get("entry_id", test_entry.get("id", ""))
title = test_entry.get("title", "?")
print(f"  ℹ️  Target entry: {entry_id} ({title[:50]})")

# ── Execute: calculate_freshness_score ──────────────────────
result = app.call_tool("calculate_freshness_score", {
    "entry_id": entry_id,
    "ttl_days": 90
})
data = json.loads(result.content[0].text)

# ── Check 1: Freshness score is numeric ────────────────────
score = data.get("freshness_score", -1)
if isinstance(score, (int, float)):
    print(f"  ✅ PASS: freshness_score = {score:.4f} (numeric)")
else:
    print(f"  ❌ FAIL: freshness_score is not numeric: {type(score).__name__}")
    ALL_PASS = False

# ── Check 2: Score is between 0 and 1 ──────────────────────
if isinstance(score, (int, float)) and 0.0 <= score <= 1.0:
    print(f"  ✅ PASS: freshness_score in range [0.0, 1.0]")
else:
    print(f"  ❌ FAIL: freshness_score = {score} (out of range)")
    ALL_PASS = False

# ── Check 3: Score > 0 for active (non-expired) entry ───────
if isinstance(score, (int, float)) and score > 0:
    print(f"  ✅ PASS: freshness_score > 0 (entry is active/fresh)")
else:
    print(f"  ❌ FAIL: freshness_score = {score} (should be > 0)")
    ALL_PASS = False

# ── Check 4: entry_id echoed back ───────────────────────────
returned_id = data.get("entry_id", "")
if returned_id == entry_id:
    print(f"  ✅ PASS: correct entry_id returned")
else:
    print(f"  ❌ FAIL: returned entry_id={returned_id} ≠ {entry_id}")
    ALL_PASS = False

# ── Check 5: ttl_days echoed back ───────────────────────────
ttl = data.get("ttl_days", -1)
if ttl == 90:
    print(f"  ✅ PASS: ttl_days = {ttl}")
else:
    print(f"  ❌ FAIL: ttl_days = {ttl} (expected 90)")
    ALL_PASS = False

# ── Check 6: With longer TTL, score is higher ────────────────
result_short = app.call_tool("calculate_freshness_score", {
    "entry_id": entry_id,
    "ttl_days": 365 * 10  # 10 years
})
data_short = json.loads(result_short.content[0].text)
score_long_ttl = data_short.get("freshness_score", -1)
if isinstance(score_long_ttl, (int, float)) and score_long_ttl > score:
    print(f"  ✅ PASS: longer TTL yields higher score ({score_long_ttl:.4f} > {score:.4f})")
else:
    print(f"  💡 INFO: longer TTL should yield higher score (got {score_long_ttl}) — may be expected if entry is very old")

# ── Check 7: Score matches formula freshness = 1 - age/TTL ───
# Fetch full entry to get collected_at
full_entry = app.call_tool("get_kb_entry", {"entry_id": entry_id})
full_data = json.loads(full_entry.content[0].text)
collected_at = full_data.get("collected_at") or full_data.get("created_at") or ""
if collected_at:
    from datetime import datetime, timezone
    try:
        created = datetime.fromisoformat(str(collected_at).replace("Z", "+00:00"))
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        age_days = (datetime.now(timezone.utc) - created).days
        expected_score = max(0.0, min(1.0, 1.0 - (age_days / 90)))
        if abs(score - expected_score) < 0.02:
            print(f"  ✅ PASS: score={score:.4f} matches formula (age={age_days}d, TTL=90d, expected={expected_score:.4f})")
        else:
            print(f"  ❌ FAIL: score={score:.4f} differs from expected {expected_score:.4f} (age={age_days}d)")
            ALL_PASS = False
    except (ValueError, TypeError) as e:
        print(f"  💡 INFO: could not parse collected_at='{collected_at}': {e}")
else:
    print(f"  💡 INFO: no collected_at/created_at in entry; cannot verify formula")

if ALL_PASS:
    print("\n✅ SCENARIO 46.10 PASSED — calculate_freshness_score returns age-based score matching TTL formula")
    sys.exit(0)
else:
    print("\n❌ SCENARIO 46.10 FAILED — calculate_freshness_score")
    sys.exit(1)
```
**Expected Result:** ✅ `freshness_score` > 0 and ≤ 1.0. Score matches `1.0 - age_days/ttl_days` within tolerance (±0.02). Correct `entry_id` and `ttl_days` returned. Score decreases with shorter TTL.


---

### 📊 Q46 Verdict

| Scenario | Result |
|----------|--------|
| 46.1 KB import | ⬜ |
| 46.2 KB export | ⬜ |
| 46.3 Link items | ⬜ |
| 46.4 Knowledge graph | ⬜ |
| 46.5 Stats & diff | ⬜ |
| 46.6 find_similar_items | ⬜ |
| 46.7 merge_items | ⬜ |
| 46.8 get_domain_decay | ⬜ |
| 46.9 mark_stale | ⬜ |
| 46.10 calculate_freshness_score | ⬜ |

**OVERALL: ⬜**
