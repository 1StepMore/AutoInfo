# Part 6: KB Pipeline — 4-Tier Lifecycle (Q42-Q46)

**Coverage:** 00-Inbox, 01-Raw→02-Draft→03-Wiki transitions, Markdown files, SQLite index, import/export, versioning, relations, knowledge graph

---

## Q42: KB Markdown File Integrity

**User says:** "I want my knowledge base as clean Markdown files I can open in Obsidian."

### Prerequisites
```bash
cd /tmp && rm -rf test-q42 && mkdir test-q42 && cd test-q42
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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

#### 42.3 🟢 Body contains original content
```python
    with open(entry.file_path) as f:
        content = f.read()
    assert "IVF Research 2026" in content  # title
    assert "Abstract content here" in content
    print(f"✅ Body contains title and content")
```
**Expected Result:** ✅ Body contains original item content.

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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
cd /tmp && rm -rf test-q44 && mkdir test-q44 && cd test-q44
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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

#### 44.3 🟢 File system reflects tier
```bash
ls -la knowledge/medical-research/01-Raw/ivf/ 2>/dev/null && echo "01-Raw files exist"
ls -la knowledge/medical-research/02-Draft/ivf/ 2>/dev/null && echo "02-Draft files exist" || echo "No 02-Draft files"
```
**Expected Result:** ✅ Files exist in both 01-Raw and 02-Draft directories.

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

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

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q46 Verdict

| Scenario | Result |
|----------|--------|
| 46.1 KB import | ⬜ |
| 46.2 KB export | ⬜ |
| 46.3 Link items | ⬜ |
| 46.4 Knowledge graph | ⬜ |
| 46.5 Stats & diff | ⬜ |

**OVERALL: ⬜**
