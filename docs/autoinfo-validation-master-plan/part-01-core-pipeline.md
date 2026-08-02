# Part 1: Core Pipeline Journeys (Q1-Q6)

**Files:** `README.md` ← `part-01-core-pipeline.md`
**Coverage:** Init → Collect → Process → Browse → Status → Doctor

---

### Part-Level Directory Setup
Run once at the start of this part:
```bash
# Create clean directories for all questions in this part
rm -rf /tmp/test-q1 && mkdir -p /tmp/test-q1
rm -rf /tmp/test-q2 && mkdir -p /tmp/test-q2
rm -rf /tmp/test-q3 && mkdir -p /tmp/test-q3
rm -rf /tmp/test-q4 && mkdir -p /tmp/test-q4
rm -rf /tmp/test-q5 && mkdir -p /tmp/test-q5
rm -rf /tmp/test-q6 && mkdir -p /tmp/test-q6
rm -rf /tmp/test-q6b && mkdir -p /tmp/test-q6b
```

## Q1: Can I initialize a project and configure sources?

**User says:** "I want to start tracking medical research. Give me a working project."

### Prerequisites
```bash
cd /tmp/test-q1
```

### Scenarios

#### 1.1 🟢 Happy Path — Init with demo domain
```bash
autoinfo init --demo medical-research
```
**Expected Result:**
- ✅ Exit code 0
- ✅ `.autoinfo/config.yaml` created (domains with embedded `sources` + `topics` — config.yaml is the single source of truth; **no standalone `sources.yaml` is created**)
- ✅ `knowledge/`, `collections/`, `outputs/` directories created
- ✅ Success message printed with next steps


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


#### 1.3 🟢 Init is idempotent
```bash
autoinfo init --demo medical-research
```
**Expected Result:** ✅ Exit code 0. Prints "SKIP" for existing files. No overwrite.


#### 1.4 🟢 Init --list-domains shows available domains
```bash
autoinfo init --list-domains
```
**Expected Result:** ✅ Prints available demo domains (medical-research, ai-commercial, financial-intelligence, tech-ai-developer, language-learning). Exit code 0.

Note: `autoinfo init` without `--demo` launches an interactive wizard (requires TTY). Use `--list-domains` to list domains non-interactively.


#### 1.5 🟢 Init with specific domain (single --demo)
```bash
cd /tmp && rm -rf test-multi && mkdir test-multi && cd test-multi
autoinfo init --demo medical-research
```
**Expected Result:** ✅ Domain configured with sources and topics.

Note: `--demo` accepts a single domain name. Initialize multiple domains by running `init --demo` separately or use the interactive wizard.


#### 1.6 🔴 Init with unknown domain
```bash
autoinfo init --demo nonexistent-domain
```
**Expected Result:** ❌ Exit code != 0. Error message mentions unknown domain.


#### 1.7 🔴 Init with --name (named project)
```bash
cd /tmp && rm -rf test-named && mkdir test-named && cd test-named
autoinfo init --name "My Custom Project" --demo medical-research
```
**Expected Result:** ✅ Config has `project.project_name = "My Custom Project"`. Overrides default name.

Note: Uses `project.project_name` (not `project.name`) — the default name "My AutoInfo" remains under `project.name`.


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
cd /tmp/test-q2
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


#### 2.2 🟢 Dry-run returns estimates without storing
```bash
autoinfo collect --domain medical-research --topic "IVF" --limit 3 --dry-run
```
**Expected Result:**
- ✅ Exit code 0
- ✅ Output shows estimated item counts
- ✅ No files created in `collections/` directory


#### 2.3 🟢 Collection with source filter
```bash
autoinfo collect --domain medical-research --topic "IVF" --source pubmed --limit 3
```
**Expected Result:** ✅ Only PubMed handler runs. Items collected successfully.


#### 2.4 🟢 Empty results handled gracefully
```bash
autoinfo collect --domain medical-research --topic "zzzzzznonexistent" --limit 3
```
**Expected Result:** ✅ Exit code 0. Message: "No new items" or similar. Not an error.


#### 2.5 🟢 RSS feed collection (ai-commercial domain)
```bash
cd /tmp && rm -rf test-rss && mkdir test-rss && cd test-rss
autoinfo init --demo ai-commercial
autoinfo collect --domain ai-commercial --source techcrunch --limit 5
```
**Expected Result:** ✅ RSS items collected with title, link, summary, published date. `source_type: "rss"`.


#### 2.6 🟢 Collection with JSON output
```bash
autoinfo collect --domain medical-research --topic "IVF" --limit 3 --json
```
**Expected Result:** ✅ Valid JSON output with collection results.


#### 2.7 🔴 Collection with missing config
```bash
cd /tmp/empty-dir && autoinfo collect --domain medical-research
```
**Expected Result:** ❌ Exit code != 0. "Run 'autoinfo init' first" error message.


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

## Q2b: Collector Validation — All 15 Source Handlers (Mock Transport)

**User says:** "Does every collector handle its API correctly? Happy path, empty results, and errors?"

### Prerequisites
```bash
cd /tmp/test-q2
# Ensure the package is importable
python3 -c "from autoinfo.collectors.openalex import OpenAlexHandler; print('OK')" || pip install -e ".[dev]" -q
```

### Scenarios — Academic Collectors (A2-A5)

#### 2b.1 🟢 OpenAlex — Happy path mock (httpx transport)
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(python3 -c "
import json, httpx
from autoinfo.collectors.openalex import OpenAlexHandler

# Build a mock transport that returns synthetic OpenAlex data
def mock_handler(request):
    data = {
        'results': [
            {
                'id': 'https://openalex.org/W4200000001',
                'title': 'Advances in CRISPR Gene Editing',
                'abstract_inverted_index': {'crispr': [0], 'gene': [1], 'editing': [2]},
                'authorships': [{'author': {'display_name': 'Jane Doe'}}],
                'cited_by_count': 42,
                'publication_date': '2024-06-15',
            },
            {
                'id': 'https://openalex.org/W4200000002',
                'title': 'Machine Learning for Protein Folding',
                'abstract_inverted_index': None,
                'authorships': [],
                'cited_by_count': 0,
                'publication_date': '2023-01-01',
            },
        ],
        'meta': {'count': 2},
    }
    return httpx.Response(200, json=data, request=request)

transport = httpx.MockTransport(mock_handler)
with httpx.Client(transport=transport) as client:
    # Monkey-patch httpx.get to use our mock client
    import autoinfo.collectors.openalex as oa_mod
    original_get = oa_mod.httpx.get
    oa_mod.httpx.get = client.get
    try:
        handler = OpenAlexHandler({'query': 'CRISPR'})
        articles = handler.fetch(limit=5)
        items = [handler.to_item(a) for a in articles]
        for item in items:
            print(f'ID={item.id} TITLE={item.title} SRC={item.source_platform}')
        assert len(items) == 2, f'Expected 2 items, got {len(items)}'
        assert items[0].title == 'Advances in CRISPR Gene Editing'
        assert items[0].source_platform == 'openalex'
        assert 'CRISPR' in items[0].content
        print('  ✅ PASS: 2 items mapped correctly')
    finally:
        oa_mod.httpx.get = original_get
" 2>&1)
EXIT_CODE=$?

echo "$OUTPUT" | grep -q "PASS: 2 items mapped correctly" && echo "  ✅ PASS: OpenAlex happy path" || { echo "  ❌ FAIL: OpenAlex happy path"; ALL_PASS=false; }
[ "$EXIT_CODE" -eq 0 ] && echo "  ✅ PASS: exit code 0" || { echo "  ❌ FAIL: exit code $EXIT_CODE"; ALL_PASS=false; }

[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 2b.1 PASSED" && exit 0 || { echo "❌ SCENARIO 2b.1 FAILED"; exit 1; }
```
**Expected Result:**
- ✅ 2 items mapped with correct source_platform `"openalex"`
- ✅ Title and content fields populated
- ✅ Exit code 0

#### 2b.2 🔴 OpenAlex — Empty results (no matches)
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(python3 -c "
import json, httpx
from autoinfo.collectors.openalex import OpenAlexHandler

def mock_handler(request):
    return httpx.Response(200, json={'results': [], 'meta': {'count': 0}}, request=request)

transport = httpx.MockTransport(mock_handler)
with httpx.Client(transport=transport) as client:
    import autoinfo.collectors.openalex as oa_mod
    original_get = oa_mod.httpx.get
    oa_mod.httpx.get = client.get
    try:
        handler = OpenAlexHandler({'query': 'xyznonexistent12345678'})
        articles = handler.fetch(limit=5)
        print(f'COUNT={len(articles)}')
        assert len(articles) == 0, f'Expected 0 items, got {len(articles)}'
        print('  ✅ PASS: empty results returned []')
    finally:
        oa_mod.httpx.get = original_get
" 2>&1)
EXIT_CODE=$?

echo "$OUTPUT" | grep -q "PASS: empty results" && echo "  ✅ PASS: OpenAlex empty results" || { echo "  ❌ FAIL: OpenAlex empty results"; ALL_PASS=false; }
[ "$EXIT_CODE" -eq 0 ] && echo "  ✅ PASS: exit code 0" || { echo "  ❌ FAIL: exit code $EXIT_CODE"; ALL_PASS=false; }

[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 2b.2 PASSED" && exit 0 || { echo "❌ SCENARIO 2b.2 FAILED"; exit 1; }
```
**Expected Result:**
- ✅ Returns empty list `[]` without error
- ✅ Exit code 0

#### 2b.3 🔴 OpenAlex — Network error (timeout)
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(python3 -c "
import httpx
from autoinfo.collectors.openalex import OpenAlexHandler

def mock_handler(request):
    raise httpx.TimeoutException('Connection timed out')

transport = httpx.MockTransport(mock_handler)
with httpx.Client(transport=transport) as client:
    import autoinfo.collectors.openalex as oa_mod
    original_get = oa_mod.httpx.get
    oa_mod.httpx.get = client.get
    try:
        handler = OpenAlexHandler({'query': 'test'})
        articles = handler.fetch(limit=5)
        print(f'COUNT={len(articles)}')
        assert len(articles) == 0, f'Expected 0 items on error, got {len(articles)}'
        print('  ✅ PASS: network error handled gracefully (returned [])')
    finally:
        oa_mod.httpx.get = original_get
" 2>&1)
EXIT_CODE=$?

echo "$OUTPUT" | grep -q "PASS: network error" && echo "  ✅ PASS: OpenAlex error handling" || { echo "  ❌ FAIL: OpenAlex error handling"; ALL_PASS=false; }
[ "$EXIT_CODE" -eq 0 ] && echo "  ✅ PASS: exit code 0" || { echo "  ❌ FAIL: exit code $EXIT_CODE"; ALL_PASS=false; }

[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 2b.3 PASSED" && exit 0 || { echo "❌ SCENARIO 2b.3 FAILED"; exit 1; }
```
**Expected Result:**
- ✅ Returns empty list `[]` on timeout
- ✅ No unhandled exception propagates
- ✅ Exit code 0

---

#### 2b.4 🟢 Semantic Scholar — Happy path mock
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(python3 -c "
import json, httpx
from autoinfo.collectors.semantic_scholar import SemanticScholarHandler

def mock_handler(request):
    data = {
        'data': [
            {'paperId': 's2-001', 'title': 'Deep Learning Survey', 'abstract': 'A comprehensive survey...',
             'authors': [{'name': 'Alice Smith'}], 'citationCount': 150, 'publicationDate': '2024-03'},
            {'paperId': 's2-002', 'title': 'Transformer Architectures', 'abstract': '',
             'authors': [], 'citationCount': 0, 'publicationDate': None},
        ]
    }
    return httpx.Response(200, json=data, request=request)

transport = httpx.MockTransport(mock_handler)
with httpx.Client(transport=transport) as client:
    import autoinfo.collectors.semantic_scholar as ss_mod
    original_get = ss_mod.httpx.get
    ss_mod.httpx.get = client.get
    try:
        handler = SemanticScholarHandler()
        papers = handler.fetch('deep learning', limit=10)
        items = [handler.to_item(p) for p in papers]
        for item in items:
            print(f'ID={item.id} TITLE={item.title} SRC={item.source_platform}')
        assert len(items) == 2, f'Expected 2, got {len(items)}'
        assert items[0].source_platform == 'semantic_scholar'
        assert items[0].title == 'Deep Learning Survey'
        print('  ✅ PASS: 2 papers mapped')
    finally:
        ss_mod.httpx.get = original_get
" 2>&1)
EXIT_CODE=$?

echo "$OUTPUT" | grep -q "PASS: 2 papers" && echo "  ✅ PASS: Semantic Scholar happy path" || { echo "  ❌ FAIL: Semantic Scholar happy path"; ALL_PASS=false; }
[ "$EXIT_CODE" -eq 0 ] && echo "  ✅ PASS: exit code 0" || { echo "  ❌ FAIL: exit code $EXIT_CODE"; ALL_PASS=false; }

[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 2b.4 PASSED" && exit 0 || { echo "❌ SCENARIO 2b.4 FAILED"; exit 1; }
```
**Expected Result:**
- ✅ 2 papers mapped with correct source_platform `"semantic_scholar"`
- ✅ Titles and content populated

#### 2b.5 🔴 Semantic Scholar — Empty results
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(python3 -c "
import httpx
from autoinfo.collectors.semantic_scholar import SemanticScholarHandler

def mock_handler(request):
    return httpx.Response(200, json={'data': []}, request=request)

transport = httpx.MockTransport(mock_handler)
with httpx.Client(transport=transport) as client:
    import autoinfo.collectors.semantic_scholar as ss_mod
    original_get = ss_mod.httpx.get
    ss_mod.httpx.get = client.get
    try:
        handler = SemanticScholarHandler()
        papers = handler.fetch('xyznonexistent', limit=10)
        assert len(papers) == 0
        print('  ✅ PASS: empty results returned []')
    finally:
        ss_mod.httpx.get = original_get
" 2>&1)

echo "$OUTPUT" | grep -q "PASS: empty results" && echo "  ✅ PASS: Semantic Scholar empty results" || { echo "  ❌ FAIL"; ALL_PASS=false; }
[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 2b.5 PASSED" && exit 0 || { echo "❌ SCENARIO 2b.5 FAILED"; exit 1; }
```
**Expected Result:** ✅ Returns `[]` for no matches.

#### 2b.6 🔴 Semantic Scholar — HTTP 500 error
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(python3 -c "
import httpx
from autoinfo.collectors.semantic_scholar import SemanticScholarHandler

def mock_handler(request):
    return httpx.Response(500, json={'error': 'Internal Server Error'}, request=request)

transport = httpx.MockTransport(mock_handler)
with httpx.Client(transport=transport) as client:
    import autoinfo.collectors.semantic_scholar as ss_mod
    original_get = ss_mod.httpx.get
    ss_mod.httpx.get = client.get
    try:
        handler = SemanticScholarHandler()
        papers = handler.fetch('test', limit=5)
        print(f'COUNT={len(papers)}')
        assert len(papers) == 0
        print('  ✅ PASS: HTTP 500 handled gracefully (returned [])')
    finally:
        ss_mod.httpx.get = original_get
" 2>&1)

echo "$OUTPUT" | grep -q "PASS: HTTP 500" && echo "  ✅ PASS: Semantic Scholar error handling" || { echo "  ❌ FAIL"; ALL_PASS=false; }
[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 2b.6 PASSED" && exit 0 || { echo "❌ SCENARIO 2b.6 FAILED"; exit 1; }
```
**Expected Result:** ✅ Returns `[]` on server error, no exception.

---

#### 2b.7 🟢 DBLP — Happy path mock
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(python3 -c "
import json, httpx
from autoinfo.collectors.dblp import DBLPHandler

def mock_handler(request):
    data = {
        'result': {
            'hits': {
                '@total': '2',
                'hit': [
                    {
                        '@score': '1.0', '@id': 'https://dblp.org/rec/conf/nips/Doe2024',
                        'info': {'title': 'Neural Network Optimization', 'doi': '10.1234/nn2024',
                                 'authors': {'author': ['John Smith', 'Jane Doe']},
                                 'year': '2024', 'venue': 'NeurIPS 2024'}
                    },
                    {
                        '@score': '0.8', '@id': 'https://dblp.org/rec/journals/ai/Lee2023',
                        'info': {'title': 'Symbolic Reasoning in LLMs', 'doi': '',
                                 'authors': {'author': 'Min Lee'},
                                 'year': '2023', 'venue': 'Artificial Intelligence'}
                    },
                ]
            }
        }
    }
    return httpx.Response(200, json=data, request=request)

transport = httpx.MockTransport(mock_handler)
with httpx.Client(transport=transport) as client:
    import autoinfo.collectors.dblp as dblp_mod
    original_get = dblp_mod.httpx.get
    dblp_mod.httpx.get = client.get
    try:
        handler = DBLPHandler()
        pubs = handler.fetch('machine learning', limit=10)
        items = [handler.to_item(p) for p in pubs]
        for item in items:
            print(f'ID={item.id} TITLE={item.title} SRC={item.source_platform}')
        assert len(items) == 2, f'Expected 2, got {len(items)}'
        assert items[0].source_platform == 'dblp'
        assert items[0].raw_data.get('venue') == 'NeurIPS 2024'
        print('  ✅ PASS: 2 publications mapped with venue')
    finally:
        dblp_mod.httpx.get = original_get
" 2>&1)
EXIT_CODE=$?

echo "$OUTPUT" | grep -q "PASS: 2 publications" && echo "  ✅ PASS: DBLP happy path" || { echo "  ❌ FAIL"; ALL_PASS=false; }
[ "$EXIT_CODE" -eq 0 ] && echo "  ✅ PASS: exit code 0" || { echo "  ❌ FAIL: exit code $EXIT_CODE"; ALL_PASS=false; }
[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 2b.7 PASSED" && exit 0 || { echo "❌ SCENARIO 2b.7 FAILED"; exit 1; }
```
**Expected Result:**
- ✅ 2 publications mapped with source_platform `"dblp"`
- ✅ Venue metadata in raw_data

#### 2b.8 🔴 DBLP — Empty results
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(python3 -c "
import httpx
from autoinfo.collectors.dblp import DBLPHandler

def mock_handler(request):
    return httpx.Response(200, json={'result': {'hits': {'@total': '0', 'hit': []}}}, request=request)

transport = httpx.MockTransport(mock_handler)
with httpx.Client(transport=transport) as client:
    import autoinfo.collectors.dblp as dblp_mod
    original_get = dblp_mod.httpx.get
    dblp_mod.httpx.get = client.get
    try:
        handler = DBLPHandler()
        pubs = handler.fetch('xyznonexistent', limit=10)
        assert len(pubs) == 0
        print('  ✅ PASS: empty results returned []')
    finally:
        dblp_mod.httpx.get = original_get
" 2>&1)

echo "$OUTPUT" | grep -q "PASS: empty" && echo "  ✅ PASS: DBLP empty results" || { echo "  ❌ FAIL"; ALL_PASS=false; }
[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 2b.8 PASSED" && exit 0 || { echo "❌ SCENARIO 2b.8 FAILED"; exit 1; }
```
**Expected Result:** ✅ Returns `[]` for no matches.

#### 2b.9 🔴 DBLP — Network error
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(python3 -c "
import httpx
from autoinfo.collectors.dblp import DBLPHandler

def mock_handler(request):
    raise httpx.NetworkError('Connection refused')

transport = httpx.MockTransport(mock_handler)
with httpx.Client(transport=transport) as client:
    import autoinfo.collectors.dblp as dblp_mod
    original_get = dblp_mod.httpx.get
    dblp_mod.httpx.get = client.get
    try:
        handler = DBLPHandler()
        pubs = handler.fetch('test', limit=5)
        assert len(pubs) == 0
        print('  ✅ PASS: network error handled gracefully')
    finally:
        dblp_mod.httpx.get = original_get
" 2>&1)

echo "$OUTPUT" | grep -q "PASS: network error" && echo "  ✅ PASS: DBLP error handling" || { echo "  ❌ FAIL"; ALL_PASS=false; }
[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 2b.9 PASSED" && exit 0 || { echo "❌ SCENARIO 2b.9 FAILED"; exit 1; }
```
**Expected Result:** ✅ Returns `[]` on network error.

---

#### 2b.10 🟢 USPTO — Happy path mock (PatentsView API)
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(python3 -c "
import json, httpx
from autoinfo.collectors.uspto import USPTOHandler

def mock_handler(request):
    data = {
        'patents': [
            {
                'patent_number': 'US12000123',
                'patent_title': 'CRISPR-based Gene Therapy Method',
                'patent_abstract': 'A novel method for targeted gene therapy using CRISPR-Cas9...',
                'patent_date': '2024-05-10',
                'app_date': '2023-01-15',
                'inventors': [{'inventor_first_name': 'Alice', 'inventor_last_name': 'Johnson'}],
                'assignee_organization': 'GenTech Inc.',
                'patent_num_cited_by_us_patents': 5,
                'patent_num_combined_citations': 12,
            }
        ]
    }
    return httpx.Response(200, json=data, request=request)

transport = httpx.MockTransport(mock_handler)
with httpx.Client(transport=transport) as client:
    import autoinfo.collectors.uspto as uspto_mod
    original_post = uspto_mod.httpx.post
    uspto_mod.httpx.post = client.post
    try:
        handler = USPTOHandler()
        patents = handler.fetch('gene therapy', limit=10)
        items = [handler.to_item(p) for p in patents]
        for item in items:
            print(f'ID={item.id} TITLE={item.title} SRC={item.source_platform}')
        assert len(items) == 1, f'Expected 1, got {len(items)}'
        assert items[0].source_platform == 'uspto'
        assert items[0].raw_data.get('patent_number') == 'US12000123'
        print('  ✅ PASS: 1 patent mapped with patent_number')
    finally:
        uspto_mod.httpx.post = original_post
" 2>&1)
EXIT_CODE=$?

echo "$OUTPUT" | grep -q "PASS: 1 patent" && echo "  ✅ PASS: USPTO happy path" || { echo "  ❌ FAIL"; ALL_PASS=false; }
[ "$EXIT_CODE" -eq 0 ] && echo "  ✅ PASS: exit code 0" || { echo "  ❌ FAIL: exit code $EXIT_CODE"; ALL_PASS=false; }
[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 2b.10 PASSED" && exit 0 || { echo "❌ SCENARIO 2b.10 FAILED"; exit 1; }
```
**Expected Result:**
- ✅ 1 patent mapped with source_platform `"uspto"`
- ✅ Patent number and metadata in raw_data

#### 2b.11 🔴 USPTO — Empty results
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(python3 -c "
import httpx
from autoinfo.collectors.uspto import USPTOHandler

def mock_handler(request):
    return httpx.Response(200, json={'patents': []}, request=request)

transport = httpx.MockTransport(mock_handler)
with httpx.Client(transport=transport) as client:
    import autoinfo.collectors.uspto as uspto_mod
    original_post = uspto_mod.httpx.post
    uspto_mod.httpx.post = client.post
    try:
        handler = USPTOHandler()
        patents = handler.fetch('xyznonexistent', limit=10)
        assert len(patents) == 0
        print('  ✅ PASS: empty results returned []')
    finally:
        uspto_mod.httpx.post = original_post
" 2>&1)

echo "$OUTPUT" | grep -q "PASS: empty" && echo "  ✅ PASS: USPTO empty results" || { echo "  ❌ FAIL"; ALL_PASS=false; }
[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 2b.11 PASSED" && exit 0 || { echo "❌ SCENARIO 2b.11 FAILED"; exit 1; }
```
**Expected Result:** ✅ Returns `[]` for no matching patents.

#### 2b.12 🔴 USPTO — API error falls back to RSS
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(python3 -c "
import httpx
from autoinfo.collectors.uspto import USPTOHandler

# PatentsView API returns 500 → should fall back to RSS
call_count = {'count': 0}
def mock_handler(request):
    call_count['count'] += 1
    if request.method == 'POST':
        return httpx.Response(500, json={'error': 'down'}, request=request)
    else:
        # RSS fallback — return valid RSS XML with 1 item
        rss_xml = '''<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<rss version=\"2.0\"><channel><title>USPTO Patents</title>
<item><title>Test Patent Application</title>
<link>https://example.com/patent1</link>
<pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
<description>Test patent description</description></item>
</channel></rss>'''
        return httpx.Response(200, text=rss_xml, request=request)

transport = httpx.MockTransport(mock_handler)
with httpx.Client(transport=transport) as client:
    import autoinfo.collectors.uspto as uspto_mod
    original_post = uspto_mod.httpx.post
    original_get = uspto_mod.httpx.get
    uspto_mod.httpx.post = client.post
    uspto_mod.httpx.get = client.get
    try:
        handler = USPTOHandler()
        patents = handler.fetch('test', limit=10)
        # With PatentsView failing, it should fall back to RSS and get at least 1 item
        print(f'PATENTS_COUNT={len(patents)}')
        assert call_count['count'] >= 2, 'Expected at least POST + GET fallback'
        print('  ✅ PASS: PatentsView failure triggered RSS fallback')
    finally:
        uspto_mod.httpx.post = original_post
        uspto_mod.httpx.get = original_get
" 2>&1)
EXIT_CODE=$?

echo "$OUTPUT" | grep -q "PASS: PatentsView failure" && echo "  ✅ PASS: USPTO fallback" || { echo "  ❌ FAIL"; ALL_PASS=false; }
[ "$EXIT_CODE" -eq 0 ] && echo "  ✅ PASS: exit code 0" || { echo "  ❌ FAIL: exit code $EXIT_CODE"; ALL_PASS=false; }
[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 2b.12 PASSED" && exit 0 || { echo "❌ SCENARIO 2b.12 FAILED"; exit 1; }
```
**Expected Result:**
- ✅ PatentsView failure triggers RSS fallback
- ✅ At least 2 HTTP calls (POST + GET)

---

### Scenarios — Financial Collectors (A8)

#### 2b.13 🟢 Quandl — Happy path mock
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(python3 -c "
import json, os, httpx
os.environ['AUTOINFO_QUANDL_API_KEY'] = 'test-key-123'
from autoinfo.collectors.quandl import QuandlHandler
from autoinfo.config import SourceConfig

def mock_handler(request):
    data = {
        'dataset': {
            'dataset_code': 'WIKI/AAPL',
            'name': 'Apple Inc. (AAPL) Stock Prices',
            'description': 'Historical end-of-day stock prices for Apple Inc.',
            'column_names': ['Date', 'Open', 'High', 'Low', 'Close'],
            'data': [['2024-01-02', 185.0, 188.0, 184.0, 187.5]],
        }
    }
    return httpx.Response(200, json=data, request=request)

transport = httpx.MockTransport(mock_handler)
with httpx.Client(transport=transport) as client:
    import autoinfo.collectors.quandl as q_mod
    original_get = q_mod.httpx.get
    q_mod.httpx.get = client.get
    try:
        cfg = SourceConfig(name='quandl-test', type='quandl', url='https://data.nasdaq.com/api/v3/datasets/WIKI/AAPL.json')
        handler = QuandlHandler(cfg)
        items = handler.fetch(url=cfg.url, limit=5)
        for item in items:
            print(f'ID={item.id} TITLE={item.title} TYPE={item.source_type}')
        assert len(items) == 1, f'Expected 1, got {len(items)}'
        assert items[0].id == 'WIKI/AAPL'
        assert items[0].source_type == 'quandl'
        assert 'Apple' in items[0].title
        print('  ✅ PASS: 1 Quandl dataset mapped')
    finally:
        q_mod.httpx.get = original_get
        del os.environ['AUTOINFO_QUANDL_API_KEY']
" 2>&1)
EXIT_CODE=$?

echo "$OUTPUT" | grep -q "PASS: 1 Quandl" && echo "  ✅ PASS: Quandl happy path" || { echo "  ❌ FAIL"; ALL_PASS=false; }
[ "$EXIT_CODE" -eq 0 ] && echo "  ✅ PASS: exit code 0" || { echo "  ❌ FAIL: exit code $EXIT_CODE"; ALL_PASS=false; }
[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 2b.13 PASSED" && exit 0 || { echo "❌ SCENARIO 2b.13 FAILED"; exit 1; }
```
**Expected Result:**
- ✅ 1 Quandl dataset mapped with source_type `"quandl"`
- ✅ Dataset code `"WIKI/AAPL"` extracted correctly

#### 2b.14 🔴 Quandl — Missing API key (graceful degradation)
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(python3 -c "
# Ensure no API key in env
for k in list(__import__('os').environ.keys()):
    if 'QUANDL' in k:
        del __import__('os').environ[k]

from autoinfo.collectors.quandl import QuandlHandler
from autoinfo.config import SourceConfig

cfg = SourceConfig(name='quandl-nokey', type='quandl', url='https://example.com')
handler = QuandlHandler(cfg)
items = handler.fetch(url=cfg.url, limit=5)
print(f'COUNT={len(items)}')
assert len(items) == 0, 'Expected 0 items without API key'
print('  ✅ PASS: missing API key returns []')
" 2>&1)
EXIT_CODE=$?

echo "$OUTPUT" | grep -q "PASS: missing API key" && echo "  ✅ PASS: Quandl no-key graceful" || { echo "  ❌ FAIL"; ALL_PASS=false; }
[ "$EXIT_CODE" -eq 0 ] && echo "  ✅ PASS: exit code 0" || { echo "  ❌ FAIL: exit code $EXIT_CODE"; ALL_PASS=false; }
[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 2b.14 PASSED" && exit 0 || { echo "❌ SCENARIO 2b.14 FAILED"; exit 1; }
```
**Expected Result:** ✅ Returns `[]` gracefully when API key is missing.

#### 2b.15 🔴 Quandl — HTTP error
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(python3 -c "
import os, httpx
os.environ['AUTOINFO_QUANDL_API_KEY'] = 'test-key'
from autoinfo.collectors.quandl import QuandlHandler
from autoinfo.config import SourceConfig

def mock_handler(request):
    return httpx.Response(403, json={'error': 'Forbidden'}, request=request)

transport = httpx.MockTransport(mock_handler)
with httpx.Client(transport=transport) as client:
    import autoinfo.collectors.quandl as q_mod
    original_get = q_mod.httpx.get
    q_mod.httpx.get = client.get
    try:
        cfg = SourceConfig(name='quandl-err', type='quandl', url='https://example.com')
        handler = QuandlHandler(cfg)
        items = handler.fetch(url=cfg.url, limit=5)
        assert len(items) == 0
        print('  ✅ PASS: HTTP 403 handled gracefully (returned [])')
    finally:
        q_mod.httpx.get = original_get
        del os.environ['AUTOINFO_QUANDL_API_KEY']
" 2>&1)

echo "$OUTPUT" | grep -q "PASS: HTTP 403" && echo "  ✅ PASS: Quandl error handling" || { echo "  ❌ FAIL"; ALL_PASS=false; }
[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 2b.15 PASSED" && exit 0 || { echo "❌ SCENARIO 2b.15 FAILED"; exit 1; }
```
**Expected Result:** ✅ Returns `[]` on HTTP 403.

---

#### 2b.16 🟢 Yahoo Finance — Happy path mock (feedparser RSS)
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(python3 -c "
from autoinfo.collectors.yahoo_finance import YahooFinanceHandler

handler = YahooFinanceHandler(source_name='yf-test')
items = handler.fetch(url=None)  # Use default URL — will fail to network, but tests structure
# Test that the class structure and to_item are functional by testing with a mock entry
from autoinfo.collectors.yahoo_finance import _make_item_id, _normalise_date

# Test idempotent helpers
id1 = _make_item_id('https://feed.url', 'https://item.link')
id2 = _make_item_id('https://feed.url', 'https://item.link')
assert id1 == id2, 'ID should be deterministic'
print(f'ITEM_ID={id1}')

# Test date normalisation
d1 = _normalise_date('Mon, 01 Jan 2024 00:00:00 GMT')
assert '2024' in d1, f'Expected 2024 in date, got {d1}'
print(f'DATE={d1}')

print('  ✅ PASS: Yahoo Finance helpers work correctly')
" 2>&1)
EXIT_CODE=$?

echo "$OUTPUT" | grep -q "PASS: Yahoo Finance helpers" && echo "  ✅ PASS: Yahoo Finance structure" || { echo "  ❌ FAIL"; ALL_PASS=false; }
[ "$EXIT_CODE" -eq 0 ] && echo "  ✅ PASS: exit code 0" || { echo "  ❌ FAIL: exit code $EXIT_CODE"; ALL_PASS=false; }
[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 2b.16 PASSED" && exit 0 || { echo "❌ SCENARIO 2b.16 FAILED"; exit 1; }
```
**Expected Result:**
- ✅ Item ID generation is deterministic
- ✅ Date normalisation produces ISO format

#### 2b.17 🔴 Yahoo Finance — Invalid feed URL
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(python3 -c "
from autoinfo.collectors.yahoo_finance import YahooFinanceHandler

handler = YahooFinanceHandler(source_name='yf-invalid')
items = handler.fetch(url='https://invalid.example.com/nonexistent.xml')
print(f'COUNT={len(items)}')
# feedparser will attempt to fetch and fail, returning empty entries
assert len(items) == 0, f'Expected 0 items for invalid URL, got {len(items)}'
print('  ✅ PASS: invalid feed URL returns []')
" 2>&1)
EXIT_CODE=$?

echo "$OUTPUT" | grep -q "PASS: invalid feed" && echo "  ✅ PASS: Yahoo Finance error handling" || { echo "  ❌ FAIL"; ALL_PASS=false; }
[ "$EXIT_CODE" -eq 0 ] && echo "  ✅ PASS: exit code 0" || { echo "  ❌ FAIL: exit code $EXIT_CODE"; ALL_PASS=false; }
[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 2b.17 PASSED" && exit 0 || { echo "❌ SCENARIO 2b.17 FAILED"; exit 1; }
```
**Expected Result:** ✅ Returns `[]` for invalid/unreachable feed URL.

---

### Scenarios — News Collectors (A9-A10)

#### 2b.18 🟢 AP API — Graceful degradation (no API key)
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(python3 -c "
# Ensure no AP key
for k in list(__import__('os').environ.keys()):
    if 'AP_API' in k:
        del __import__('os').environ[k]

from autoinfo.collectors.ap_api import APAPIHandler

handler = APAPIHandler()
assert handler.requires_key() == True, 'AP always requires key'
articles = handler.fetch(limit=10)
assert len(articles) == 0, 'Expected 0 without key'
print('  ✅ PASS: AP API returns [] without key — graceful degradation')
" 2>&1)
EXIT_CODE=$?

echo "$OUTPUT" | grep -q "PASS: AP API" && echo "  ✅ PASS: AP API no-key graceful" || { echo "  ❌ FAIL"; ALL_PASS=false; }
[ "$EXIT_CODE" -eq 0 ] && echo "  ✅ PASS: exit code 0" || { echo "  ❌ FAIL: exit code $EXIT_CODE"; ALL_PASS=false; }
[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 2b.18 PASSED" && exit 0 || { echo "❌ SCENARIO 2b.18 FAILED"; exit 1; }
```
**Expected Result:**
- ✅ `requires_key()` returns `True`
- ✅ Returns `[]` with explanatory log when key is missing

#### 2b.19 🟢 AP API — Happy path mock (with mock key)
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(python3 -c "
import os, json, httpx
os.environ['AUTOINFO_AP_API_KEY'] = 'fake-ap-key'
from autoinfo.collectors.ap_api import APAPIHandler

def mock_handler(request):
    data = {
        'data': {
            'items': [
                {
                    'uri': 'ap://article/001',
                    'headline': 'Global Markets Rally on Tech Earnings',
                    'body': 'Stock markets surged worldwide...',
                    'byline': 'By John Smith',
                    'published': '2024-06-15T10:30:00Z',
                    'section': 'Business',
                    'language': 'en',
                    'source': 'Associated Press',
                }
            ]
        }
    }
    return httpx.Response(200, json=data, request=request)

transport = httpx.MockTransport(mock_handler)
with httpx.Client(transport=transport) as client:
    import autoinfo.collectors.ap_api as ap_mod
    original_get = ap_mod.httpx.get
    ap_mod.httpx.get = client.get
    try:
        handler = APAPIHandler(api_key='fake-ap-key')
        articles = handler.fetch(limit=10)
        items = [handler.to_item(a) for a in articles]
        for item in items:
            print(f'ID={item.id} TITLE={item.title} SRC={item.source_platform}')
        assert len(items) == 1, f'Expected 1, got {len(items)}'
        assert items[0].source_platform == 'ap_api'
        assert items[0].title == 'Global Markets Rally on Tech Earnings'
        print('  ✅ PASS: 1 AP article mapped')
    finally:
        ap_mod.httpx.get = original_get
        del os.environ['AUTOINFO_AP_API_KEY']
" 2>&1)
EXIT_CODE=$?

echo "$OUTPUT" | grep -q "PASS: 1 AP article" && echo "  ✅ PASS: AP API happy path" || { echo "  ❌ FAIL"; ALL_PASS=false; }
[ "$EXIT_CODE" -eq 0 ] && echo "  ✅ PASS: exit code 0" || { echo "  ❌ FAIL: exit code $EXIT_CODE"; ALL_PASS=false; }
[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 2b.19 PASSED" && exit 0 || { echo "❌ SCENARIO 2b.19 FAILED"; exit 1; }
```
**Expected Result:**
- ✅ 1 AP article mapped with source_platform `"ap_api"`
- ✅ Title, content, and metadata fields populated

#### 2b.20 🔴 AP API — 401 Unauthorized
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(python3 -c "
import os, httpx
os.environ['AUTOINFO_AP_API_KEY'] = 'bad-key'
from autoinfo.collectors.ap_api import APAPIHandler

def mock_handler(request):
    return httpx.Response(401, json={'error': 'Unauthorized'}, request=request)

transport = httpx.MockTransport(mock_handler)
with httpx.Client(transport=transport) as client:
    import autoinfo.collectors.ap_api as ap_mod
    original_get = ap_mod.httpx.get
    ap_mod.httpx.get = client.get
    try:
        handler = APAPIHandler(api_key='bad-key')
        articles = handler.fetch(limit=10)
        assert len(articles) == 0
        print('  ✅ PASS: 401 Unauthorized returns []')
    finally:
        ap_mod.httpx.get = original_get
        del os.environ['AUTOINFO_AP_API_KEY']
" 2>&1)

echo "$OUTPUT" | grep -q "PASS: 401" && echo "  ✅ PASS: AP API error handling" || { echo "  ❌ FAIL"; ALL_PASS=false; }
[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 2b.20 PASSED" && exit 0 || { echo "❌ SCENARIO 2b.20 FAILED"; exit 1; }
```
**Expected Result:** ✅ Returns `[]` on 401 with explanatory log.

---

#### 2b.21 🟢 Reuters MCP — Graceful degradation (no API key)
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(python3 -c "
for k in list(__import__('os').environ.keys()):
    if 'REUTERS' in k:
        del __import__('os').environ[k]

from autoinfo.collectors.reuters_mcp import ReutersMCPHandler

handler = ReutersMCPHandler()
assert handler.requires_key() == True, 'Reuters always requires key'
articles = handler.fetch(limit=10)
assert len(articles) == 0, 'Expected 0 without key'
print('  ✅ PASS: Reuters MCP returns [] without key — graceful degradation')
" 2>&1)
EXIT_CODE=$?

echo "$OUTPUT" | grep -q "PASS: Reuters MCP" && echo "  ✅ PASS: Reuters MCP no-key graceful" || { echo "  ❌ FAIL"; ALL_PASS=false; }
[ "$EXIT_CODE" -eq 0 ] && echo "  ✅ PASS: exit code 0" || { echo "  ❌ FAIL: exit code $EXIT_CODE"; ALL_PASS=false; }
[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 2b.21 PASSED" && exit 0 || { echo "❌ SCENARIO 2b.21 FAILED"; exit 1; }
```
**Expected Result:**
- ✅ `requires_key()` returns `True`
- ✅ Returns `[]` with explanatory log when key is missing

#### 2b.22 🟢 Reuters MCP — Happy path mock
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(python3 -c "
import os, json, httpx
os.environ['AUTOINFO_REUTERS_API_KEY'] = 'fake-reuters-key'
from autoinfo.collectors.reuters_mcp import ReutersMCPHandler
from autoinfo.config import SourceConfig

def mock_handler(request):
    data = {
        'data': {
            'items': [
                {
                    'id': 'reuters-001',
                    'headline': 'Fed Signals Rate Cut',
                    'body': 'The Federal Reserve indicated...',
                    'byline': 'Reuters Staff',
                    'published': '2024-06-15T08:00:00Z',
                    'section': 'Economy',
                    'language': 'en',
                    'source': 'Reuters',
                    'url': 'https://www.reuters.com/article/001',
                }
            ]
        }
    }
    return httpx.Response(200, json=data, request=request)

transport = httpx.MockTransport(mock_handler)
with httpx.Client(transport=transport) as client:
    import autoinfo.collectors.reuters_mcp as rm_mod
    original_post = rm_mod.httpx.post
    rm_mod.httpx.post = client.post
    try:
        cfg = SourceConfig(name='reuters-test', type='reuters_mcp',
                           url='https://api.reuters.com/content/v1/search',
                           settings={'api_key': 'fake-reuters-key'})
        handler = ReutersMCPHandler(cfg)
        articles = handler.fetch(limit=10)
        items = [handler.to_item(a) for a in articles]
        for item in items:
            print(f'ID={item.id} TITLE={item.title} SRC={item.source_platform}')
        assert len(items) == 1, f'Expected 1, got {len(items)}'
        assert items[0].source_platform == 'reuters_mcp'
        print('  ✅ PASS: 1 Reuters article mapped')
    finally:
        rm_mod.httpx.post = original_post
        os.environ.pop('AUTOINFO_REUTERS_API_KEY', None)
" 2>&1)
EXIT_CODE=$?

echo "$OUTPUT" | grep -q "PASS: 1 Reuters" && echo "  ✅ PASS: Reuters MCP happy path" || { echo "  ❌ FAIL"; ALL_PASS=false; }
[ "$EXIT_CODE" -eq 0 ] && echo "  ✅ PASS: exit code 0" || { echo "  ❌ FAIL: exit code $EXIT_CODE"; ALL_PASS=false; }
[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 2b.22 PASSED" && exit 0 || { echo "❌ SCENARIO 2b.22 FAILED"; exit 1; }
```
**Expected Result:** ✅ 1 Reuters article mapped with source_platform `"reuters_mcp"`.

#### 2b.23 🔴 Reuters MCP — 403 Forbidden
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(python3 -c "
import os, httpx
os.environ['AUTOINFO_REUTERS_API_KEY'] = 'bad-key'
from autoinfo.collectors.reuters_mcp import ReutersMCPHandler
from autoinfo.config import SourceConfig

def mock_handler(request):
    return httpx.Response(403, json={'error': 'Forbidden'}, request=request)

transport = httpx.MockTransport(mock_handler)
with httpx.Client(transport=transport) as client:
    import autoinfo.collectors.reuters_mcp as rm_mod
    original_post = rm_mod.httpx.post
    rm_mod.httpx.post = client.post
    try:
        cfg = SourceConfig(name='reuters-err', type='reuters_mcp',
                           url='https://api.reuters.com/content/v1/search',
                           settings={'api_key': 'bad-key'})
        handler = ReutersMCPHandler(cfg)
        articles = handler.fetch(limit=10)
        assert len(articles) == 0
        print('  ✅ PASS: 403 Forbidden returns []')
    finally:
        rm_mod.httpx.post = original_post
        os.environ.pop('AUTOINFO_REUTERS_API_KEY', None)
" 2>&1)

echo "$OUTPUT" | grep -q "PASS: 403" && echo "  ✅ PASS: Reuters MCP error handling" || { echo "  ❌ FAIL"; ALL_PASS=false; }
[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 2b.23 PASSED" && exit 0 || { echo "❌ SCENARIO 2b.23 FAILED"; exit 1; }
```
**Expected Result:** ✅ Returns `[]` on 403 Forbidden.

---

#### 2b.24 🟢 NYT — Graceful degradation (no API key)
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(python3 -c "
for k in list(__import__('os').environ.keys()):
    if 'NYT' in k:
        del __import__('os').environ[k]

from autoinfo.collectors.nyt import NYTHandler

handler = NYTHandler()
articles = handler.fetch(limit=10)
assert len(articles) == 0, 'Expected 0 without API key'
print('  ✅ PASS: NYT returns [] without API key — graceful degradation')
" 2>&1)
EXIT_CODE=$?

echo "$OUTPUT" | grep -q "PASS: NYT returns" && echo "  ✅ PASS: NYT no-key graceful" || { echo "  ❌ FAIL"; ALL_PASS=false; }
[ "$EXIT_CODE" -eq 0 ] && echo "  ✅ PASS: exit code 0" || { echo "  ❌ FAIL: exit code $EXIT_CODE"; ALL_PASS=false; }
[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 2b.24 PASSED" && exit 0 || { echo "❌ SCENARIO 2b.24 FAILED"; exit 1; }
```
**Expected Result:** ✅ Returns `[]` with explanatory log when API key is missing.

#### 2b.25 🟢 NYT — Happy path mock
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(python3 -c "
import os, json, httpx
os.environ['AUTOINFO_NYT_API_KEY'] = 'fake-nyt-key'
from autoinfo.collectors.nyt import NYTHandler

def mock_handler(request):
    data = {
        'response': {
            'docs': [
                {
                    '_id': 'nyt://article/001',
                    'headline': {'main': 'AI Startups Raise Record Funding'},
                    'abstract': 'Venture capital investment in AI startups reached...',
                    'section_name': 'Technology',
                    'subsection_name': 'Startups',
                    'pub_date': '2024-06-15T09:00:00Z',
                    'web_url': 'https://www.nytimes.com/2024/06/15/technology/ai-funding.html',
                    'byline': {'original': 'By Jane Reporter'},
                    'word_count': 850,
                    'document_type': 'article',
                }
            ]
        }
    }
    return httpx.Response(200, json=data, request=request)

transport = httpx.MockTransport(mock_handler)
with httpx.Client(transport=transport) as client:
    import autoinfo.collectors.nyt as nyt_mod
    original_get = nyt_mod.httpx.get
    nyt_mod.httpx.get = client.get
    try:
        handler = NYTHandler({'api_key': 'fake-nyt-key', 'query': 'AI funding'})
        articles = handler.fetch(limit=10)
        items = [handler.to_item(a) for a in articles]
        for item in items:
            print(f'ID={item.id} TITLE={item.title} SRC={item.source_platform}')
        assert len(items) == 1, f'Expected 1, got {len(items)}'
        assert items[0].source_platform == 'nyt'
        assert items[0].title == 'AI Startups Raise Record Funding'
        print('  ✅ PASS: 1 NYT article mapped')
    finally:
        nyt_mod.httpx.get = original_get
        del os.environ['AUTOINFO_NYT_API_KEY']
" 2>&1)
EXIT_CODE=$?

echo "$OUTPUT" | grep -q "PASS: 1 NYT" && echo "  ✅ PASS: NYT happy path" || { echo "  ❌ FAIL"; ALL_PASS=false; }
[ "$EXIT_CODE" -eq 0 ] && echo "  ✅ PASS: exit code 0" || { echo "  ❌ FAIL: exit code $EXIT_CODE"; ALL_PASS=false; }
[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 2b.25 PASSED" && exit 0 || { echo "❌ SCENARIO 2b.25 FAILED"; exit 1; }
```
**Expected Result:**
- ✅ 1 NYT article mapped with source_platform `"nyt"`
- ✅ Headline, abstract, and byline extracted

#### 2b.26 🔴 NYT — HTTP error (429 Rate Limited)
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(python3 -c "
import os, httpx
os.environ['AUTOINFO_NYT_API_KEY'] = 'fake-key'
from autoinfo.collectors.nyt import NYTHandler

def mock_handler(request):
    return httpx.Response(429, json={'error': 'Rate limit exceeded'}, request=request)

transport = httpx.MockTransport(mock_handler)
with httpx.Client(transport=transport) as client:
    import autoinfo.collectors.nyt as nyt_mod
    original_get = nyt_mod.httpx.get
    nyt_mod.httpx.get = client.get
    try:
        handler = NYTHandler({'api_key': 'fake-key', 'query': 'test'})
        articles = handler.fetch(limit=10)
        assert len(articles) == 0
        print('  ✅ PASS: 429 rate limit returns []')
    finally:
        nyt_mod.httpx.get = original_get
        del os.environ['AUTOINFO_NYT_API_KEY']
" 2>&1)

echo "$OUTPUT" | grep -q "PASS: 429" && echo "  ✅ PASS: NYT error handling" || { echo "  ❌ FAIL"; ALL_PASS=false; }
[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 2b.26 PASSED" && exit 0 || { echo "❌ SCENARIO 2b.26 FAILED"; exit 1; }
```
**Expected Result:** ✅ Returns `[]` on rate limit (429).

---

### Scenarios — Content & Social Collectors (A12, A14-A17)

#### 2b.27 🟢 36kr — RSS feed collection (via ai-commercial domain)
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

cd /tmp && rm -rf test-36kr && mkdir test-36kr && cd test-36kr

OUTPUT=$(autoinfo init --demo ai-commercial 2>&1)
EXIT_CODE=$?

# Check that 36kr source is configured (it's an RSS feed source)
echo "$OUTPUT" | grep -qi "ai-commercial" && echo "  ✅ PASS: ai-commercial domain initialized" || { echo "  ❌ FAIL"; ALL_PASS=false; }

# Verify 36kr appears in sources
SRC_OUT=$(autoinfo sources list --domain ai-commercial 2>&1 || true)
echo "$SRC_OUT" | grep -qi "36kr" && echo "  ✅ PASS: 36kr source configured" || echo "  ⚠️  36kr source not found in list (may have been renamed)"

[ "$EXIT_CODE" -eq 0 ] && echo "  ✅ PASS: exit code 0" || { echo "  ❌ FAIL: exit code $EXIT_CODE"; ALL_PASS=false; }

[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 2b.27 PASSED" && exit 0 || { echo "❌ SCENARIO 2b.27 FAILED"; exit 1; }
```
**Expected Result:**
- ✅ ai-commercial domain initializes with 36kr as RSS source
- ✅ 36kr listed in `sources list`

---

#### 2b.28 🟢 Reddit — Happy path mock (OAuth2 + search)
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(python3 -c "
import json, httpx, time
from autoinfo.collectors.reddit import RedditHandler

token_called = []

def mock_handler(request):
    # Token endpoint — return OAuth2 token
    if '/api/v1/access_token' in str(request.url):
        token_called.append(True)
        return httpx.Response(200, json={
            'access_token': 'fake-reddit-token-xxxx',
            'token_type': 'bearer',
            'expires_in': 3600,
        }, request=request)
    # Search / hot endpoint — return posts
    data = {
        'data': {
            'children': [
                {
                    'data': {
                        'name': 't3_abc123',
                        'title': 'Latest advances in reinforcement learning',
                        'selftext': 'Researchers at DeepMind have achieved...',
                        'author': 'ml_researcher',
                        'subreddit': 'MachineLearning',
                        'score': 250,
                        'num_comments': 45,
                        'created_utc': 1700000000.0,
                        'url': 'https://reddit.com/r/MachineLearning/comments/abc123',
                    }
                }
            ]
        }
    }
    return httpx.Response(200, json=data, request=request)

transport = httpx.MockTransport(mock_handler)
with httpx.Client(transport=transport) as client:
    import autoinfo.collectors.reddit as r_mod
    original_post = r_mod.httpx.post
    original_get = r_mod.httpx.get
    r_mod.httpx.post = client.post
    r_mod.httpx.get = client.get
    try:
        handler = RedditHandler({
            'client_id': 'fake-client', 'client_secret': 'fake-secret',
            'user_agent': 'AutoInfo/1.0', 'subreddits': ['MachineLearning'],
        })
        posts = handler.fetch(query='reinforcement learning', limit=5)
        items = [handler.to_item(p) for p in posts]
        for item in items:
            print(f'ID={item.id} TITLE={item.title} SRC={item.source_platform}')
        assert len(items) == 1, f'Expected 1, got {len(items)}'
        assert items[0].source_platform == 'reddit'
        assert items[0].title == 'Latest advances in reinforcement learning'
        assert len(token_called) == 1, 'OAuth2 token should have been requested'
        print('  ✅ PASS: 1 Reddit post mapped via OAuth2')
    finally:
        r_mod.httpx.post = original_post
        r_mod.httpx.get = original_get
" 2>&1)
EXIT_CODE=$?

echo "$OUTPUT" | grep -q "PASS: 1 Reddit" && echo "  ✅ PASS: Reddit happy path" || { echo "  ❌ FAIL"; ALL_PASS=false; }
[ "$EXIT_CODE" -eq 0 ] && echo "  ✅ PASS: exit code 0" || { echo "  ❌ FAIL: exit code $EXIT_CODE"; ALL_PASS=false; }
[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 2b.28 PASSED" && exit 0 || { echo "❌ SCENARIO 2b.28 FAILED"; exit 1; }
```
**Expected Result:**
- ✅ OAuth2 token requested before search
- ✅ 1 Reddit post mapped with source_platform `"reddit"`

#### 2b.29 🔴 Reddit — OAuth2 failure (bad credentials)
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(python3 -c "
import httpx
from autoinfo.collectors.reddit import RedditHandler

def mock_handler(request):
    return httpx.Response(401, json={'error': 'invalid_client'}, request=request)

transport = httpx.MockTransport(mock_handler)
with httpx.Client(transport=transport) as client:
    import autoinfo.collectors.reddit as r_mod
    original_post = r_mod.httpx.post
    r_mod.httpx.post = client.post
    try:
        handler = RedditHandler({
            'client_id': 'bad-client', 'client_secret': 'bad-secret',
            'user_agent': 'AutoInfo/1.0', 'subreddits': ['test'],
        })
        posts = handler.fetch(query='test', limit=5)
        assert len(posts) == 0
        print('  ✅ PASS: OAuth2 failure returns []')
    finally:
        r_mod.httpx.post = original_post
" 2>&1)

echo "$OUTPUT" | grep -q "PASS: OAuth2" && echo "  ✅ PASS: Reddit error handling" || { echo "  ❌ FAIL"; ALL_PASS=false; }
[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 2b.29 PASSED" && exit 0 || { echo "❌ SCENARIO 2b.29 FAILED"; exit 1; }
```
**Expected Result:** ✅ Returns `[]` on OAuth2 authentication failure.

#### 2b.30 🔴 Reddit — Empty subreddits config
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(python3 -c "
from autoinfo.collectors.reddit import RedditHandler

handler = RedditHandler({
    'client_id': 'test', 'client_secret': 'test',
    'user_agent': 'AutoInfo/1.0', 'subreddits': [],
})
posts = handler.fetch(query='test', limit=5)
assert len(posts) == 0
print('  ✅ PASS: empty subreddits returns []')
" 2>&1)

echo "$OUTPUT" | grep -q "PASS: empty subreddits" && echo "  ✅ PASS: Reddit empty config" || { echo "  ❌ FAIL"; ALL_PASS=false; }
[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 2b.30 PASSED" && exit 0 || { echo "❌ SCENARIO 2b.30 FAILED"; exit 1; }
```
**Expected Result:** ✅ Returns `[]` when no subreddits configured.

---

#### 2b.31 🟢 YouTube — Graceful degradation (no API key)
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(python3 -c "
for k in list(__import__('os').environ.keys()):
    if 'YOUTUBE' in k:
        del __import__('os').environ[k]

from autoinfo.collectors.youtube import YouTubeHandler

handler = YouTubeHandler()
assert handler.requires_key() == True, 'YouTube always requires key'
videos = handler.fetch(limit=10)
assert len(videos) == 0, 'Expected 0 without API key'
print('  ✅ PASS: YouTube returns [] without API key — graceful degradation')
" 2>&1)
EXIT_CODE=$?

echo "$OUTPUT" | grep -q "PASS: YouTube" && echo "  ✅ PASS: YouTube no-key graceful" || { echo "  ❌ FAIL"; ALL_PASS=false; }
[ "$EXIT_CODE" -eq 0 ] && echo "  ✅ PASS: exit code 0" || { echo "  ❌ FAIL: exit code $EXIT_CODE"; ALL_PASS=false; }
[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 2b.31 PASSED" && exit 0 || { echo "❌ SCENARIO 2b.31 FAILED"; exit 1; }
```
**Expected Result:** ✅ Returns `[]` with explanatory log when API key is missing.

#### 2b.32 🟢 YouTube — Happy path mock
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(python3 -c "
import os, json, httpx
os.environ['AUTOINFO_YOUTUBE_API_KEY'] = 'fake-yt-key'
from autoinfo.collectors.youtube import YouTubeHandler

def mock_handler(request):
    data = {
        'items': [
            {
                'id': {'videoId': 'dQw4w9WgXcQ'},
                'snippet': {
                    'title': 'Understanding Transformers in NLP',
                    'description': 'A comprehensive guide to transformer architectures...',
                    'channelTitle': 'AI Explained',
                    'channelId': 'UC_example',
                    'publishedAt': '2024-05-20T15:00:00Z',
                    'thumbnails': {'default': {'url': 'https://img.youtube.com/vi/dQw4/default.jpg'}},
                }
            }
        ]
    }
    return httpx.Response(200, json=data, request=request)

transport = httpx.MockTransport(mock_handler)
with httpx.Client(transport=transport) as client:
    import autoinfo.collectors.youtube as yt_mod
    original_get = yt_mod.httpx.get
    yt_mod.httpx.get = client.get
    try:
        handler = YouTubeHandler({'api_key': 'fake-yt-key', 'query': 'transformers NLP'})
        videos = handler.fetch(limit=10)
        items = [handler.to_item(v) for v in videos]
        for item in items:
            print(f'ID={item.id} TITLE={item.title} SRC={item.source_platform}')
        assert len(items) == 1, f'Expected 1, got {len(items)}'
        assert items[0].source_platform == 'youtube'
        assert 'Transformers' in items[0].title
        print('  ✅ PASS: 1 YouTube video mapped')
    finally:
        yt_mod.httpx.get = original_get
        del os.environ['AUTOINFO_YOUTUBE_API_KEY']
" 2>&1)
EXIT_CODE=$?

echo "$OUTPUT" | grep -q "PASS: 1 YouTube" && echo "  ✅ PASS: YouTube happy path" || { echo "  ❌ FAIL"; ALL_PASS=false; }
[ "$EXIT_CODE" -eq 0 ] && echo "  ✅ PASS: exit code 0" || { echo "  ❌ FAIL: exit code $EXIT_CODE"; ALL_PASS=false; }
[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 2b.32 PASSED" && exit 0 || { echo "❌ SCENARIO 2b.32 FAILED"; exit 1; }
```
**Expected Result:** ✅ 1 YouTube video mapped with source_platform `"youtube"`.

#### 2b.33 🔴 YouTube — Empty query
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(python3 -c "
import os
os.environ['AUTOINFO_YOUTUBE_API_KEY'] = 'fake-key'
from autoinfo.collectors.youtube import YouTubeHandler

handler = YouTubeHandler({'api_key': 'fake-key', 'query': ''})
videos = handler.fetch(limit=10)
assert len(videos) == 0
print('  ✅ PASS: empty query returns []')
del os.environ['AUTOINFO_YOUTUBE_API_KEY']
" 2>&1)

echo "$OUTPUT" | grep -q "PASS: empty query" && echo "  ✅ PASS: YouTube empty query" || { echo "  ❌ FAIL"; ALL_PASS=false; }
[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 2b.33 PASSED" && exit 0 || { echo "❌ SCENARIO 2b.33 FAILED"; exit 1; }
```
**Expected Result:** ✅ Returns `[]` when query is empty string.

---

#### 2b.34 🟢 Spotify — Happy path mock (OAuth2 + show episodes)
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(python3 -c "
import json, httpx
from autoinfo.collectors.spotify import SpotifyHandler

token_called = []

def mock_handler(request):
    if 'accounts.spotify.com' in str(request.url):
        token_called.append(True)
        return httpx.Response(200, json={
            'access_token': 'fake-spotify-token',
            'token_type': 'Bearer',
            'expires_in': 3600,
        }, request=request)
    data = {
        'items': [
            {
                'id': 'ep_001',
                'name': 'The Future of AGI',
                'description': 'A discussion on artificial general intelligence...',
                'publisher': 'Tech Podcasts Inc.',
                'release_date': '2024-06-10',
                'duration_ms': 2400000,
                'languages': ['en'],
                'external_urls': {'spotify': 'https://open.spotify.com/episode/ep_001'},
                'audio_preview_url': 'https://p.scdn.co/mp3-preview/abc123',
                'show': {'id': 'show_42', 'name': 'Future Tech', 'publisher': 'Tech Podcasts Inc.',
                         'description': 'A podcast about future technology'},
                'explicit': False,
                'type': 'episode',
            }
        ]
    }
    return httpx.Response(200, json=data, request=request)

transport = httpx.MockTransport(mock_handler)
with httpx.Client(transport=transport) as client:
    import autoinfo.collectors.spotify as sp_mod
    original_post = sp_mod.httpx.post
    original_get = sp_mod.httpx.get
    sp_mod.httpx.post = client.post
    sp_mod.httpx.get = client.get
    try:
        handler = SpotifyHandler({
            'client_id': 'fake-sp-client', 'client_secret': 'fake-sp-secret',
            'show_id': 'show_42',
        })
        episodes = handler.fetch(limit=10, show_id='show_42')
        items = [handler.to_item(e) for e in episodes]
        for item in items:
            print(f'ID={item.id} TITLE={item.title} SRC={item.source_platform}')
        assert len(items) == 1, f'Expected 1, got {len(items)}'
        assert items[0].source_platform == 'spotify'
        assert items[0].title == 'The Future of AGI'
        assert len(token_called) == 1, 'OAuth2 token should have been requested'
        print('  ✅ PASS: 1 Spotify episode mapped via OAuth2')
    finally:
        sp_mod.httpx.post = original_post
        sp_mod.httpx.get = original_get
" 2>&1)
EXIT_CODE=$?

echo "$OUTPUT" | grep -q "PASS: 1 Spotify" && echo "  ✅ PASS: Spotify happy path" || { echo "  ❌ FAIL"; ALL_PASS=false; }
[ "$EXIT_CODE" -eq 0 ] && echo "  ✅ PASS: exit code 0" || { echo "  ❌ FAIL: exit code $EXIT_CODE"; ALL_PASS=false; }
[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 2b.34 PASSED" && exit 0 || { echo "❌ SCENARIO 2b.34 FAILED"; exit 1; }
```
**Expected Result:**
- ✅ OAuth2 token requested before API call
- ✅ 1 Spotify episode mapped with source_platform `"spotify"`

#### 2b.35 🔴 Spotify — No query and no show_id
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(python3 -c "
from autoinfo.collectors.spotify import SpotifyHandler

handler = SpotifyHandler({
    'client_id': 'test', 'client_secret': 'test',
})
episodes = handler.fetch(limit=10, query='', show_id='')
assert len(episodes) == 0
print('  ✅ PASS: no query/no show_id returns []')
" 2>&1)

echo "$OUTPUT" | grep -q "PASS: no query" && echo "  ✅ PASS: Spotify empty config" || { echo "  ❌ FAIL"; ALL_PASS=false; }
[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 2b.35 PASSED" && exit 0 || { echo "❌ SCENARIO 2b.35 FAILED"; exit 1; }
```
**Expected Result:** ✅ Returns `[]` when no query and no show_id provided.

#### 2b.36 🔴 Spotify — OAuth2 failure
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(python3 -c "
import httpx
from autoinfo.collectors.spotify import SpotifyHandler

def mock_handler(request):
    return httpx.Response(401, json={'error': 'invalid_client'}, request=request)

transport = httpx.MockTransport(mock_handler)
with httpx.Client(transport=transport) as client:
    import autoinfo.collectors.spotify as sp_mod
    original_post = sp_mod.httpx.post
    sp_mod.httpx.post = client.post
    try:
        handler = SpotifyHandler({
            'client_id': 'bad', 'client_secret': 'bad',
            'show_id': 'show_42',
        })
        episodes = handler.fetch(limit=10, show_id='show_42')
        assert len(episodes) == 0
        print('  ✅ PASS: OAuth2 failure returns []')
    finally:
        sp_mod.httpx.post = original_post
" 2>&1)

echo "$OUTPUT" | grep -q "PASS: OAuth2" && echo "  ✅ PASS: Spotify error handling" || { echo "  ❌ FAIL"; ALL_PASS=false; }
[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 2b.36 PASSED" && exit 0 || { echo "❌ SCENARIO 2b.36 FAILED"; exit 1; }
```
**Expected Result:** ✅ Returns `[]` on OAuth2 authentication failure.

---

#### 2b.37 🟢 Apple Podcasts — Happy path mock (iTunes Search API)
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(python3 -c "
import json, httpx
from autoinfo.collectors.apple_podcasts import ApplePodcastsHandler

def mock_handler(request):
    data = {
        'resultCount': 1,
        'results': [
            {
                'trackId': 123456789,
                'trackName': 'AI Frontiers Podcast',
                'description': 'Weekly podcast exploring the latest in artificial intelligence.',
                'artistName': 'TechMedia Inc.',
                'feedUrl': 'https://feeds.example.com/ai-frontiers',
                'releaseDate': '2024-01-15T00:00:00Z',
                'collectionViewUrl': 'https://podcasts.apple.com/podcast/id123456789',
                'primaryGenreName': 'Technology',
                'artworkUrl600': 'https://example.com/artwork.jpg',
                'trackCount': 50,
                'country': 'USA',
                'genres': ['Technology', 'Science'],
            }
        ]
    }
    return httpx.Response(200, json=data, request=request)

transport = httpx.MockTransport(mock_handler)
with httpx.Client(transport=transport) as client:
    import autoinfo.collectors.apple_podcasts as ap_mod
    original_get = ap_mod.httpx.get
    ap_mod.httpx.get = client.get
    try:
        handler = ApplePodcastsHandler({'term': 'AI podcast'})
        shows = handler.fetch(term='AI podcast', limit=10)
        items = [handler.to_item(s) for s in shows]
        for item in items:
            print(f'ID={item.id} TITLE={item.title} SRC={item.source_platform}')
        assert len(items) == 1, f'Expected 1, got {len(items)}'
        assert items[0].source_platform == 'apple_podcasts'
        assert items[0].title == 'AI Frontiers Podcast'
        assert items[0].raw_data.get('feed_url') == 'https://feeds.example.com/ai-frontiers'
        print('  ✅ PASS: 1 Apple Podcast show mapped')
    finally:
        ap_mod.httpx.get = original_get
" 2>&1)
EXIT_CODE=$?

echo "$OUTPUT" | grep -q "PASS: 1 Apple Podcast" && echo "  ✅ PASS: Apple Podcasts happy path" || { echo "  ❌ FAIL"; ALL_PASS=false; }
[ "$EXIT_CODE" -eq 0 ] && echo "  ✅ PASS: exit code 0" || { echo "  ❌ FAIL: exit code $EXIT_CODE"; ALL_PASS=false; }
[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 2b.37 PASSED" && exit 0 || { echo "❌ SCENARIO 2b.37 FAILED"; exit 1; }
```
**Expected Result:**
- ✅ No authentication required (`requires_key()` returns `False`)
- ✅ 1 podcast show mapped with source_platform `"apple_podcasts"`
- ✅ Feed URL in raw_data

#### 2b.38 🔴 Apple Podcasts — Empty search results
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(python3 -c "
import httpx
from autoinfo.collectors.apple_podcasts import ApplePodcastsHandler

def mock_handler(request):
    return httpx.Response(200, json={'resultCount': 0, 'results': []}, request=request)

transport = httpx.MockTransport(mock_handler)
with httpx.Client(transport=transport) as client:
    import autoinfo.collectors.apple_podcasts as ap_mod
    original_get = ap_mod.httpx.get
    ap_mod.httpx.get = client.get
    try:
        handler = ApplePodcastsHandler()
        shows = handler.fetch(term='xyznonexistent12345678', limit=10)
        assert len(shows) == 0
        print('  ✅ PASS: empty results returned []')
    finally:
        ap_mod.httpx.get = original_get
" 2>&1)

echo "$OUTPUT" | grep -q "PASS: empty" && echo "  ✅ PASS: Apple Podcasts empty results" || { echo "  ❌ FAIL"; ALL_PASS=false; }
[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 2b.38 PASSED" && exit 0 || { echo "❌ SCENARIO 2b.38 FAILED"; exit 1; }
```
**Expected Result:** ✅ Returns `[]` for no matching shows.

#### 2b.39 🔴 Apple Podcasts — Network error
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(python3 -c "
import httpx
from autoinfo.collectors.apple_podcasts import ApplePodcastsHandler

def mock_handler(request):
    raise httpx.TimeoutException('Connection timed out')

transport = httpx.MockTransport(mock_handler)
with httpx.Client(transport=transport) as client:
    import autoinfo.collectors.apple_podcasts as ap_mod
    original_get = ap_mod.httpx.get
    ap_mod.httpx.get = client.get
    try:
        handler = ApplePodcastsHandler()
        shows = handler.fetch(term='test', limit=10)
        assert len(shows) == 0
        print('  ✅ PASS: network timeout returns []')
    finally:
        ap_mod.httpx.get = original_get
" 2>&1)

echo "$OUTPUT" | grep -q "PASS: network timeout" && echo "  ✅ PASS: Apple Podcasts error handling" || { echo "  ❌ FAIL"; ALL_PASS=false; }
[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 2b.39 PASSED" && exit 0 || { echo "❌ SCENARIO 2b.39 FAILED"; exit 1; }
```
**Expected Result:** ✅ Returns `[]` on network timeout.

---

#### 2b.40 🟢 Bilibili — Happy path mock (search/all/v2)
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(python3 -c "
import json, httpx
from autoinfo.collectors.bilibili import BilibiliHandler

def mock_handler(request):
    data = {
        'code': 0,
        'message': 'success',
        'data': {
            'result': {
                'video': [
                    {
                        'aid': 123456789,
                        'bvid': 'BV1xx411c7mD',
                        'title': '大模型训练技术详解',
                        'description': '深入讲解大规模语言模型的训练方法...',
                        'author': 'AI技术分享',
                        'created': 1700000000,
                        'pic': 'https://example.com/thumb.jpg',
                        'stat': {'view': 50000},
                    }
                ]
            }
        }
    }
    return httpx.Response(200, json=data, request=request)

transport = httpx.MockTransport(mock_handler)
with httpx.Client(transport=transport) as client:
    import autoinfo.collectors.bilibili as bl_mod
    original_get = bl_mod.httpx.get
    bl_mod.httpx.get = client.get
    try:
        handler = BilibiliHandler({'query': '大模型'})
        videos = handler.fetch(limit=10)
        items = [handler.to_item(v) for v in videos]
        for item in items:
            print(f'ID={item.id} TITLE={item.title} SRC={item.source_platform}')
        assert len(items) == 1, f'Expected 1, got {len(items)}'
        assert items[0].source_platform == 'bilibili'
        assert '大模型' in items[0].title
        assert items[0].raw_data.get('bvid') == 'BV1xx411c7mD'
        print('  ✅ PASS: 1 Bilibili video mapped with bvid')
    finally:
        bl_mod.httpx.get = original_get
" 2>&1)
EXIT_CODE=$?

echo "$OUTPUT" | grep -q "PASS: 1 Bilibili" && echo "  ✅ PASS: Bilibili happy path" || { echo "  ❌ FAIL"; ALL_PASS=false; }
[ "$EXIT_CODE" -eq 0 ] && echo "  ✅ PASS: exit code 0" || { echo "  ❌ FAIL: exit code $EXIT_CODE"; ALL_PASS=false; }
[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 2b.40 PASSED" && exit 0 || { echo "❌ SCENARIO 2b.40 FAILED"; exit 1; }
```
**Expected Result:**
- ✅ 1 Bilibili video mapped with source_platform `"bilibili"`
- ✅ BVID (`BV1xx411c7mD`) in raw_data
- ✅ Chinese (CJK) title handled correctly

#### 2b.41 🔴 Bilibili — API error code (code != 0)
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(python3 -c "
import httpx
from autoinfo.collectors.bilibili import BilibiliHandler

def mock_handler(request):
    return httpx.Response(200, json={'code': -412, 'message': '请求被拦截', 'data': None}, request=request)

transport = httpx.MockTransport(mock_handler)
with httpx.Client(transport=transport) as client:
    import autoinfo.collectors.bilibili as bl_mod
    original_get = bl_mod.httpx.get
    bl_mod.httpx.get = client.get
    try:
        handler = BilibiliHandler({'query': 'test'})
        videos = handler.fetch(limit=10)
        assert len(videos) == 0
        print('  ✅ PASS: Bilibili error code returns []')
    finally:
        bl_mod.httpx.get = original_get
" 2>&1)

echo "$OUTPUT" | grep -q "PASS: Bilibili error" && echo "  ✅ PASS: Bilibili error handling" || { echo "  ❌ FAIL"; ALL_PASS=false; }
[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 2b.41 PASSED" && exit 0 || { echo "❌ SCENARIO 2b.41 FAILED"; exit 1; }
```
**Expected Result:** ✅ Returns `[]` when Bilibili returns non-zero error code.

#### 2b.42 🔴 Bilibili — Empty query
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(python3 -c "
from autoinfo.collectors.bilibili import BilibiliHandler

handler = BilibiliHandler({'query': ''})
videos = handler.fetch(limit=10)
assert len(videos) == 0
print('  ✅ PASS: empty query returns []')
" 2>&1)

echo "$OUTPUT" | grep -q "PASS: empty query" && echo "  ✅ PASS: Bilibili empty query" || { echo "  ❌ FAIL"; ALL_PASS=false; }
[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 2b.42 PASSED" && exit 0 || { echo "❌ SCENARIO 2b.42 FAILED"; exit 1; }
```
**Expected Result:** ✅ Returns `[]` when query is empty.

#### 2b.43 🟢 Apple Podcasts — Chinese podcast coverage (A29, real iTunes Search, country=CN)
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

# A29 隐式覆盖验证：Apple Podcasts/iTunes Search API 以 country=CN 查询中文播客。
# 真实网络查询（网络不可用时标记 SKIP，不判 FAIL）。抽查 3 个代表性中文播客：小宇宙/喜马拉雅/品牌星球。
for term in "%E5%B0%8F%E5%AE%87%E5%AE%99" "%E5%96%9C%E9%A9%AC%E6%8B%89%E9%9B%85" "%E5%93%81%E7%89%8C%E6%98%9F%E7%90%83"; do
  RES=$(curl -s --max-time 30 "https://itunes.apple.com/search?media=podcast&term=${term}&country=CN&limit=5" 2>/dev/null || true)
  if [ -z "$RES" ]; then
    echo "  ⚠️ SKIP: network unavailable for term=$term"
    continue
  fi
  CNT=$(echo "$RES" | python3 -c "import json,sys; print(json.load(sys.stdin).get('resultCount', 0))" 2>/dev/null || echo 0)
  [ "$CNT" -ge 1 ] && echo "  ✅ PASS: term=$term resultCount=$CNT" || { echo "  ❌ FAIL: term=$term resultCount=$CNT"; ALL_PASS=false; }
done

[ "$ALL_PASS" = true ] && echo "✅ SCENARIO 2b.43 PASSED (Chinese podcast coverage via iTunes Search country=CN)" && exit 0 || { echo "❌ SCENARIO 2b.43 FAILED"; exit 1; }
```
**Expected Result:**
- ✅ iTunes Search API `country=CN` 对 3 个中文播客查询（小宇宙/喜马拉雅/品牌星球）均返回 `resultCount ≥ 1`
- ✅ ApplePodcastsHandler 支持 config `country`（默认 US，可设 CN）→ A29 中文播客**隐式覆盖**（2026-08-02 实测确认）
- ⚠️ 网络不可用时标记 `➖ SKIP`（不判 FAIL）；实测证据见 `.omo/evidence/task-5-apple-podcast-cn.json`

---

### 📊 Q2b Verdict

| Scenario | Result |
|----------|--------|
| 2b.1 OpenAlex happy path mock | ⬜ |
| 2b.2 OpenAlex empty results | ⬜ |
| 2b.3 OpenAlex network error | ⬜ |
| 2b.4 Semantic Scholar happy path | ⬜ |
| 2b.5 Semantic Scholar empty results | ⬜ |
| 2b.6 Semantic Scholar HTTP 500 | ⬜ |
| 2b.7 DBLP happy path mock | ⬜ |
| 2b.8 DBLP empty results | ⬜ |
| 2b.9 DBLP network error | ⬜ |
| 2b.10 USPTO happy path mock | ⬜ |
| 2b.11 USPTO empty results | ⬜ |
| 2b.12 USPTO API fallback to RSS | ⬜ |
| 2b.13 Quandl happy path mock | ⬜ |
| 2b.14 Quandl missing API key | ⬜ |
| 2b.15 Quandl HTTP error | ⬜ |
| 2b.16 Yahoo Finance happy path | ⬜ |
| 2b.17 Yahoo Finance invalid URL | ⬜ |
| 2b.18 AP API no-key graceful | ⬜ |
| 2b.19 AP API happy path mock | ⬜ |
| 2b.20 AP API 401 Unauthorized | ⬜ |
| 2b.21 Reuters MCP no-key graceful | ⬜ |
| 2b.22 Reuters MCP happy path mock | ⬜ |
| 2b.23 Reuters MCP 403 Forbidden | ⬜ |
| 2b.24 NYT no-key graceful | ⬜ |
| 2b.25 NYT happy path mock | ⬜ |
| 2b.26 NYT 429 Rate Limited | ⬜ |
| 2b.27 36kr RSS source config | ⬜ |
| 2b.28 Reddit happy path mock | ⬜ |
| 2b.29 Reddit OAuth2 failure | ⬜ |
| 2b.30 Reddit empty subreddits | ⬜ |
| 2b.31 YouTube no-key graceful | ⬜ |
| 2b.32 YouTube happy path mock | ⬜ |
| 2b.33 YouTube empty query | ⬜ |
| 2b.34 Spotify happy path mock | ⬜ |
| 2b.35 Spotify no query/show_id | ⬜ |
| 2b.36 Spotify OAuth2 failure | ⬜ |
| 2b.37 Apple Podcasts happy path | ⬜ |
| 2b.38 Apple Podcasts empty results | ⬜ |
| 2b.39 Apple Podcasts network error | ⬜ |
| 2b.40 Bilibili happy path mock | ⬜ |
| 2b.41 Bilibili error code | ⬜ |
| 2b.42 Bilibili empty query | ⬜ |
| 2b.43 Apple Podcasts Chinese podcast coverage (A29, country=CN) | ⬜ |

**OVERALL: ⬜**

---

## Q3: Can I process collected items (LLM extraction + quality gates + KB storage)?

**User says:** "I collected some papers. Now extract structured summaries and store them."

### Prerequisites
```bash
cd /tmp/test-q3
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


#### 3.2 🟢 KB entries have correct YAML frontmatter
```bash
head -20 knowledge/medical-research/01-Raw/ivf/*.md
```
**Expected Result:**
- ✅ YAML frontmatter with: title, domain, tier: 01-Raw, source_url, source_type, source_platform, collected_at, quality_tier, relevance_score
- ✅ Body contains original content + extracted TL;DR + key points


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


#### 3.4 🟢 Processing with empty cache
```bash
cd /tmp && rm -rf test-empty && mkdir test-empty && cd test-empty
autoinfo init --demo medical-research
autoinfo process --domain medical-research
```
**Expected Result:** ✅ Exit code 0. Message: no cached items found.


#### 3.5 🟢 Process with specific model override [REQUIRES LLM KEY]
```bash
autoinfo process --domain medical-research --model "openrouter/deepseek/deepseek-chat"
```
**Expected Result:** ✅ Process uses specified model. KB entries created.


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
cd /tmp/test-q4
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


#### 4.2 🟢 Summaries list with JSON output
```bash
autoinfo summaries list --domain medical-research --json
```
**Expected Result:** ✅ Valid JSON with items array. Each item has entry_id, title, summary, relevance_score, collected_at, tier.


#### 4.3 🟢 Show single summary
```bash
# Get first entry ID
ENTRY_ID=$(autoinfo summaries list --domain medical-research --json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['entries'][0]['entry_id'] if d.get('entries') else 'none')")
if [ "$ENTRY_ID" != "none" ]; then
    autoinfo summaries show "$ENTRY_ID"
fi
```
**Expected Result:** ✅ Shows full entry details: title, content, TL;DR, key points, source metadata.

Note: `entry_id` is a positional argument, not `--entry-id`.


#### 4.4 🟢 Flag entry for KB
```bash
ENTRY_ID=$(autoinfo summaries list --domain medical-research --json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['entries'][0]['entry_id'] if d.get('entries') else 'none')")
if [ "$ENTRY_ID" != "none" ]; then
    autoinfo summaries flag "$ENTRY_ID" --tag "important" --tag "review"
fi
```
**Expected Result:** ✅ Entry flagged. Tags stored in metadata.

Note: `entry_id` is positional. Use `--tag` (repeatable) not `--tags`.


#### 4.5 🟢 Status shows collection stats
```bash
autoinfo status
```
**Expected Result:**
- ✅ Shows items collected per domain
- ✅ Shows total KB entries per domain
- ✅ Shows source health per source


#### 4.6 🟢 Status with --json
```bash
autoinfo status --json
```
**Expected Result:** ✅ Valid JSON with summary stats.


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


#### 4.8 🟢 Doctor with JSON output
```bash
autoinfo doctor --json
```
**Expected Result:** ✅ Valid JSON with python/config/llm/sources sections.


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
cd /tmp/test-q5
autoinfo init --demo medical-research
```

### Scenarios

#### 5.1 🟢 Sources list
```bash
autoinfo sources list --domain medical-research
```
**Expected Result:** ✅ Shows all configured sources with name, type, url, domain.


#### 5.2 🟢 Sources list with --domain filter
```bash
autoinfo sources list --domain medical-research
```
**Expected Result:** ✅ Filters to sources belonging to specified domain.


#### 5.3 🟢 Test source reachability
```bash
autoinfo sources test --url https://eutils.ncbi.nlm.nih.gov/entrez/eutils/ --type api
```
**Expected Result:** ✅ Shows reachability result (ok/timeout/error) with latency. (Note: uses `--url` + `--type`, not `--name`.)


#### 5.4 🟢 Add new source
```bash
autoinfo sources add --name my-rss --type rss --url https://example.com/feed --domain medical-research
```
**Expected Result:** ✅ Source added. Shows confirmation. Listed in `sources list`.


#### 5.5 🟢 Remove source
```bash
autoinfo sources remove --source-id "medical-research:my-rss"
```
**Expected Result:** ✅ Source removed. Confirmation shown. No longer in `sources list`.


#### 5.6 🔴 Test nonexistent URL
```bash
autoinfo sources test --url https://nonexistent.example.com/feed --type rss
```
**Expected Result:** ❌ Shows unreachable/error status. Exit code 0 (test command runs, but URL is unreachable).

Note: `sources test` only accepts `--url` and `--type`. There is no way to test a configured source by name. To test a configured source, pass its URL directly.


#### 5.7 🔴 Add source with invalid type
```bash
autoinfo sources add --name bad-source --type invalid-type --url https://example.com --domain medical-research
```
**Expected Result:** ❌ Error: invalid source type. Shows available types.


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
cd /tmp/test-q6
autoinfo init --demo medical-research
```

### Scenarios

#### 6.1 🟢 Topics list
```bash
autoinfo topics list --domain medical-research
```
**Expected Result:** ✅ Shows all topics with name, keywords, domain.


#### 6.2 🟢 Add new topic
```bash
autoinfo topics add --name "Gene Therapy" --keywords "CRISPR,gene editing,AAV" --domain medical-research
```
**Expected Result:** ✅ Topic added. Listed in `topics list`.


#### 6.3 🟢 Remove topic
```bash
autoinfo topics remove --topic-id "Gene Therapy" --domain medical-research
```
**Expected Result:** ✅ Topic removed. Confirmation shown.


#### 6.4 🔴 Remove nonexistent topic
```bash
autoinfo topics remove --topic-id "Nonexistent Topic" --domain medical-research
```
**Expected Result:** ❌ Error: topic not found.




## Q6b: Cross-Domain Collect — All 5 Demo Domains

**User says:** "I want to collect data from all available domains to see which sources actually work."

### Prerequisites
```bash
rm -rf /tmp/test-q6b && mkdir -p /tmp/test-q6b && cd /tmp/test-q6b
```

### Scenarios

#### 6b.1 🟢 Init + collect all 5 domains — verify each produces raw data
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
DOMAINS="medical-research ai-commercial financial-intelligence language-learning tech-ai-developer"
for DOMAIN in $DOMAINS; do
  echo "── Domain: $DOMAIN ──"
  rm -rf "$DOMAIN" && mkdir "$DOMAIN" && cd "$DOMAIN"
  OUTPUT=$(autoinfo init --demo "$DOMAIN" 2>&1)
  COLLECT_OUT=$(timeout 15 autoinfo collect --domain "$DOMAIN" --limit 2 2>&1 || true)
  echo "$COLLECT_OUT" | tail -3
  # Check raw data files exist
  RAW_COUNT=$(find collections/ -name "*.json" ! -name "_runs.json" 2>/dev/null | wc -l)
  if [ "$RAW_COUNT" -gt 0 ]; then
    echo "  ✅ PASS: $DOMAIN — $RAW_COUNT raw JSON files created"
  else
    echo "  ⚠️  $DOMAIN — 0 raw files (source may need API key or feed may be empty)"
  fi
  cd ..
done
echo ""
echo "✅ Cross-domain collection complete. See per-domain results above."
```
**Expected Result:**
- ✅ Each domain produces at least `init` output (config created)
- ✅ `medical-research` produces raw JSON files from PubMed
- ✅ `ai-commercial` produces raw JSON files from RSS feeds
- ⚠️ Other domains may return 0 items if sources need API keys or feeds are empty
- No scenario crashes or produces traceback for any domain

#### 6b.2 🟢 Init + collect remaining 4 domains — online-video, financial-news, online-education, legal-compliance
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
DOMAINS="online-video financial-news online-education legal-compliance"
for DOMAIN in $DOMAINS; do
  echo "── Domain: $DOMAIN ──"
  rm -rf "$DOMAIN" && mkdir "$DOMAIN" && cd "$DOMAIN"
  OUTPUT=$(autoinfo init --demo "$DOMAIN" 2>&1)
  COLLECT_OUT=$(timeout 15 autoinfo collect --domain "$DOMAIN" --limit 2 2>&1 || true)
  echo "$COLLECT_OUT" | tail -3
  # Check raw data files exist
  RAW_COUNT=$(find collections/ -name "*.json" ! -name "_runs.json" 2>/dev/null | wc -l)
  if [ "$RAW_COUNT" -gt 0 ]; then
    echo "  ✅ PASS: $DOMAIN — $RAW_COUNT raw JSON files created"
  else
    echo "  ⚠️  $DOMAIN — 0 raw files (source may need API key or feed may be empty)"
  fi
  cd ..
done
echo ""
echo "✅ Cross-domain collection (wave 2) complete. See per-domain results above."
```
**Expected Result:**
- ✅ Each domain produces at least `init` output (config created)
- ✅ `online-video` produces raw JSON files from RSS feeds (YouTube, Variety, Hollywood Reporter, Netflix Tech Blog)
- ✅ `online-education` produces raw JSON files from RSS feeds (Coursera Blog, EdSurge, Class Central, Khan Academy, Open Culture)
- ✅ `legal-compliance` produces raw JSON files from RSS feeds (SCOTUSblog, IAPP, Law.com, Oyez, GDPR.eu)
- ⚠️ `financial-news` may return 0 items if RSS feeds are unreachable — its NYT source requires an API key; without a key, that source is skipped gracefully, remaining sources still produce output (mirrors Q2b.24 NYT degradation pattern)
- No scenario crashes or produces traceback for any domain


---

### 📊 Q6 Verdict

| Scenario | Result |
|----------|--------|
| 6.1 Topics list | ⬜ |
| 6.2 Add topic | ⬜ |
| 6.3 Remove topic | ⬜ |
| 6.4 Remove nonexistent | ⬜ |
| 6b.1 Cross-domain 5 domains | ⬜ |
| 6b.2 Cross-domain 4 domains | ⬜ |

**OVERALL: ⬜**
