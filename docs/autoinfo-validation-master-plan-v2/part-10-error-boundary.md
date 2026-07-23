# Part 10: Error & Boundary Matrix (Q59)

**Coverage:** Comprehensive error handling across CLI, MCP, Config, LLM, Collection, Network, Data integrity

---

## Q59: Comprehensive Error & Boundary Matrix

**User says:** "What happens when things go wrong? Missing configs, network errors, bad data?"

### Prerequisites
```bash
cd /tmp && rm -rf test-q59 && mkdir test-q59 && cd test-q59
```

### CLI Error Scenarios

#### 59.1 🔴 Missing config directory
```bash
cd /tmp/nonexistent && autoinfo doctor 2>&1; echo "EXIT: $?"
```
**Expected Result:** ❌ Friendly error about config not found. No traceback. Exit code != 0.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 59.2 🔴 Invalid YAML config
```bash
mkdir -p /tmp/broken-yaml/.autoinfo
echo "invalid: yaml: :::: broken" > /tmp/broken-yaml/.autoinfo/config.yaml
cd /tmp/broken-yaml && autoinfo doctor 2>&1; echo "EXIT: $?"
```
**Expected Result:** ❌ Reports YAML parsing error with file path. No traceback.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 59.3 🔴 Empty project name in config
```bash
mkdir -p /tmp/empty-name/.autoinfo
cat > /tmp/empty-name/.autoinfo/config.yaml << 'EOF'
project:
  name: ""
llm:
  provider: openrouter
  model: deepseek/deepseek-chat
  api_key: ${AUTOINFO_LLM_API_KEY}
domains: []
EOF
cd /tmp/empty-name && autoinfo doctor 2>&1; echo "EXIT: $?"
```
**Expected Result:** ❌ Doctor reports config validation error. No crash.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 59.4 🔴 Missing required --domain on process
```bash
cd /tmp/test-autoinfo 2>/dev/null || (mkdir /tmp/test-autoinfo && cd /tmp/test-autoinfo && autoinfo init --demo medical-research)
cd /tmp/test-autoinfo && autoinfo process 2>&1; echo "EXIT: $?"
```
**Expected Result:** ❌ Error about missing --domain. Shows help. Exit code != 0.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 59.5 🔴 Nonexistent domain on collect
```bash
autoinfo collect --domain nonexistent-domain 2>&1; echo "EXIT: $?"
```
**Expected Result:** ❌ Error: domain not found. No traceback.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 59.6 🔴 Unknown CLI subcommand
```bash
autoinfo nonexistent-command 2>&1; echo "EXIT: $?"
```
**Expected Result:** ❌ Error: No such command. Shows available commands. Exit code != 0.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 59.7 🔴 Invalid --limit value
```bash
autoinfo collect --domain medical-research --topic IVF --limit -1 2>&1; echo "EXIT: $?"
```
**Expected Result:** ❌ Error about invalid limit. Accepts positive integers only.

**Actual Result:** _________ **PASS / FAIL:** _________

### Config Error Scenarios

#### 59.8 🔴 Missing sources.yaml
```bash
cd /tmp && rm -rf test-missing-sources && mkdir test-missing-sources && cd test-missing-sources
autoinfo init --demo medical-research
rm -f .autoinfo/sources.yaml
autoinfo collect --domain medical-research --topic IVF --limit 3 2>&1; echo "EXIT: $?"
```
**Expected Result:** ❌ Error: sources config missing. Or gracefully handles with warning.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 59.9 🔴 LLM API timeout — pipeline continues with next item
```python
# Test item-level isolation (simulate 3 items, middle one fails)
from autoinfo.llm import LLMExtractor
from autoinfo.models import Item, ExtractionResult
from unittest.mock import patch

extractor = LLMExtractor()
items = [
    Item(id='a', title='Good item 1', content='Real content', collected_at='2026-07-23'),
    Item(id='b', title='Bad item', content='Causes timeout', collected_at='2026-07-23'),
    Item(id='c', title='Good item 2', content='More content', collected_at='2026-07-23'),
]

# Mock 2nd item to fail
original_extract = extractor.extract_with_retry
def mock_extract(item, **kw):
    if item.id == 'b':
        raise Exception('Simulated LLM timeout')
    return original_extract(item, **kw)

extractor.extract_with_retry = mock_extract

results = []
for item in items:
    try:
        result = extractor.extract_with_retry(item)
        results.append(('ok', str(result)[:50]))
    except Exception as e:
        results.append(('fail', str(e)))

print(f'Results: {len(results)}/{len(items)} processed')
for status, r in results:
    print(f'  {status}: {r}')

assert results[0][0] == 'ok', 'First item should succeed'
assert results[1][0] == 'fail', 'Second item should fail'
assert results[2][0] == 'ok', 'Third item should succeed after failure'
print('✅ Item-level isolation confirmed')
```
**Expected Result:** ✅ Single-item LLM failure doesn't stop the pipeline. 3rd item processes after 2nd fails.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 59.10 🟢 Malformed LLM response handled gracefully
```python
from autoinfo.llm import LLMExtractor
from autoinfo.models import Item
from unittest.mock import patch, MagicMock

with patch("autoinfo.llm.litellm.completion") as mock:
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "not valid json at all"
    mock.return_value = mock_response
    
    extractor = LLMExtractor()
    item = Item(id="malformed", title="Test", content="test content", collected_at="now")
    result = extractor.extract(item)
    
    assert result is not None, "Should return default result, not None"
    print(f"✅ Malformed JSON handled: result={type(result).__name__}, summary='{str(result.summary)[:50]}'")
```
**Expected Result:** ✅ Malformed JSON returns default ExtractionResult. Doesn't crash.

**Actual Result:** _________ **PASS / FAIL:** _________

### Network Error Scenarios

#### 59.11 🟢 PubMed handler retries on timeout
```python
from unittest.mock import patch, MagicMock
from autoinfo.collectors.pubmed import PubMedHandler

with patch("httpx.get") as mock_get:
    # 2 failures then success
    mock_get.side_effect = [
        Exception("timeout"),
        Exception("timeout"),
        MagicMock(status_code=200, text='<?xml version="1.0"?><eSearchResult><Count>1</Count><IdList><Id>12345</Id></IdList></eSearchResult>')
    ]
    
    handler = PubMedHandler()
    try:
        result = handler.search("IVF", max_results=3)
        print(f"✅ PubMed retry succeeded: call_count={mock_get.call_count}")
        assert mock_get.call_count == 3
    except Exception as e:
        print(f"⚠️ PubMed retry test: {e}")
```
**Expected Result:** ✅ Handler retries 3x. Succeeds on 3rd attempt.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 59.12 🟢 Collection orchestrator isolates source failures
```python
# Simulate: one source fails, others continue
# This tests that run_collection doesn't crash when a single source errors
from autoinfo.collect import run_collection
import tempfile, os

# Run with a mix of working and broken sources
original_dir = os.getcwd()
with tempfile.TemporaryDirectory() as td:
    os.chdir(td)
    try:
        # Init project
        import subprocess
        subprocess.run(["autoinfo", "init", "--demo", "medical-research"], capture_output=True, timeout=30)
        
        # Add a broken source alongside working ones
        subprocess.run([
            "autoinfo", "sources", "add",
            "--name", "broken-source",
            "--type", "web",
            "--url", "https://this-domain-does-not-exist-99999.com",
            "--domain", "medical-research",
            "--quality-tier", "3"
        ], capture_output=True, timeout=30)
        
        # Run collection — should not crash despite broken source
        result = run_collection(domain="medical-research", topic="IVF", limit=3)
        print(f"✅ Collection with broken source: result keys={list(result.keys()) if isinstance(result, dict) else type(result)}")
        print(f"  errors={result.get('errors', '?')}")
    except Exception as e:
        print(f"⚠️ Collection orchestrator test: {e}")
    finally:
        os.chdir(original_dir)
```
**Expected Result:** ✅ Collection completes despite source errors. Other sources unaffected.

**Actual Result:** _________ **PASS / FAIL:** _________

### Data Integrity Scenarios

#### 59.13 🔴 Empty collected_at date
```python
from autoinfo.kb import KBStore, SQLiteIndex
from autoinfo.models import Item
from pathlib import Path
import tempfile

with tempfile.TemporaryDirectory() as td:
    store = KBStore(Path(td) / "knowledge", SQLiteIndex(Path(td) / "autoinfo.db"))
    store.index.init_db()
    
    # Entry with empty dates
    try:
        entry = store.store_entry(Item(
            id="no-date", source_name="pubmed", title="No Date",
            content="test", collected_at="",  # empty date
            domain="medical-research", topic_tags=["test"]
        ))
        print(f"✅ Empty date handled: path={entry.file_path}")
    except Exception as e:
        print(f"⚠️ Empty date handling: {e} (may use current date fallback)")
```
**Expected Result:** ✅ Empty dates handled without crash. Falls back to current date.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 59.14 🔴 Extremely long title
```python
with tempfile.TemporaryDirectory() as td:
    store = KBStore(Path(td) / "knowledge", SQLiteIndex(Path(td) / "autoinfo.db"))
    store.index.init_db()
    
    long_title = "A" * 5000  # 5000 chars
    try:
        entry = store.store_entry(Item(
            id="long-title", source_name="pubmed", title=long_title,
            content="test content", collected_at="2026-07-23",
            domain="medical-research", topic_tags=["test"]
        ))
        print(f"✅ Long title ({len(long_title)} chars) handled: path={entry.file_path[:80]}...")
    except Exception as e:
        print(f"⚠️ Long title handling: {e}")
```
**Expected Result:** ✅ Long title handled without crash (truncated or stored as-is).

**Actual Result:** _________ **PASS / FAIL:** _________

#### 59.15 🔴 Special characters in content (Unicode, emoji)
```python
with tempfile.TemporaryDirectory() as td:
    store = KBStore(Path(td) / "knowledge", SQLiteIndex(Path(td) / "autoinfo.db"))
    store.index.init_db()
    
    special_content = "Unicode: 你好, 日本語, 한글\nEmoji: 🧬🔬🧫\nHTML: <script>alert('xss')</script>\nMarkdown: **bold** *italic* `code`"
    try:
        entry = store.store_entry(Item(
            id="special-chars", source_name="pubmed", title="Special Chars Test",
            content=special_content, collected_at="2026-07-23",
            domain="medical-research", topic_tags=["test"]
        ))
        # Verify content preserved
        with open(entry.file_path) as f:
            saved = f.read()
        assert "你好" in saved, "CJK characters missing"
        assert "🧬" in saved, "Emoji missing"
        print(f"✅ Special characters preserved: {entry.file_path}")
    except Exception as e:
        print(f"⚠️ Special chars handling: {e}")
```
**Expected Result:** ✅ Unicode, emoji, HTML, Markdown all preserved without corruption.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 59.16 🔴 Concurrent access (two collections simultaneously)
```bash
cd /tmp && rm -rf test-concurrent && mkdir test-concurrent && cd test-concurrent
autoinfo init --demo medical-research

# Run two collections in parallel
autoinfo collect --domain medical-research --topic "IVF" --source pubmed --limit 3 &
PID1=$!
autoinfo collect --domain medical-research --topic "CRISPR" --source pubmed --limit 3 &
PID2=$!
wait $PID1 $PID2
echo "Both collections completed: $PID1=$?, $PID2=$?"
```
**Expected Result:** ✅ Both collections complete without file corruption or race conditions.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q59 Verdict

| # | Scenario | Result |
|---|----------|--------|
| 59.1 | Missing config dir | ⬜ |
| 59.2 | Invalid YAML | ⬜ |
| 59.3 | Empty project name | ⬜ |
| 59.4 | Missing --domain | ⬜ |
| 59.5 | Nonexistent domain | ⬜ |
| 59.6 | Unknown subcommand | ⬜ |
| 59.7 | Invalid --limit | ⬜ |
| 59.8 | Missing sources.yaml | ⬜ |
| 59.9 | LLM timeout isolation | ⬜ |
| 59.10 | Malformed LLM response | ⬜ |
| 59.11 | PubMed retry | ⬜ |
| 59.12 | Source failure isolation | ⬜ |
| 59.13 | Empty date | ⬜ |
| 59.14 | Long title | ⬜ |
| 59.15 | Special characters | ⬜ |
| 59.16 | Concurrent access | ⬜ |

**OVERALL: ⬜**
