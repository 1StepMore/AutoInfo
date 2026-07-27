# Collection & Processing Pipeline

> Extracted from `founder-expectations.md §§12.2-12.8, 12.12, 12.18`. References: F5-F9 (Collection), F10-F14 (Processing/Extraction), F15 (LLM Config).

---

## 1. Collection Pipeline (§12.2)

### 1.1 Item Dataclass Schema

Every collected source item is represented as an `Item`:

```python
@dataclass
class Item:
    """A single collected item before KB storage."""
    source_url: str
    source_type: str                  # "pubmed" | "rss" | "web" | "email" | "pdf"
    source_platform: str              # e.g. "pubmed", "arxiv", "hn"
    title: str
    content: str                      # main body text
    content_hash: str                 # SHA256(content) — dedup key
    author: str | None = None
    published: datetime | None = None
    collected_at: datetime = field(default_factory=datetime.now)
    raw_metadata: dict = field(default_factory=dict)  # source-specific (DOI, PMID, URL)
    topics: list[str] = field(default_factory=list)   # matched topic names
    relevance_score: float = 0.0      # populated by G3
    quality_flags: list[str] = field(default_factory=list)
```

### 1.2 Design Rules

| Rule | Rationale |
|------|-----------|
| **Raw→Processing separation in time** | Fetch task is network-bound; processing task is LLM-bound. If one fails, the other's cached output is preserved. Operator can re-process cached items with a different model without re-fetching. |
| **Dedup at multiple levels** | URL exact match (fastest) → PMID/DOI canonical match → fuzzy title similarity within window. Each level is cheaper than the next. |
| **DRY run with preview** | `collect_sources(domain=X, dry_run=True)` shows what items would be collected without writing anything. Essential for source configuration debugging. |
| **Per-item trace_id from collection through delivery** | UUID assigned at Item construction, carried through to KB entry and final product. Used in `trace_item` MCP tool and `autoinfo trace` CLI. |
| **Items are immutable after creation** | Once an Item is written to a collection cache, it is never mutated. Re-processing reads the cached Item; any re-collection creates a new Item with a new `collected_at` timestamp. This ensures reproducibility. |

### 1.3 Two-Phase Flow

```
Phase 1 — Fetch:     autoinfo collect --domain X
  → Source handlers fetch items in parallel
  → Raw JSON cached to collections/
  → Dedup (URL → PMID/DOI → fuzzy title)
  → Collection log written (per-item trace_id, timestamps, source)

Phase 2 — Process:   autoinfo process --domain X [--model deepseek-chat]
  → Reads cached raw items (from collection cache, not KB)
  → LLM extraction (configurable model per task)
  → Quality gates (G0-G5)
  → Creates 01-Raw KB entries (one per validated item)
```

### 1.4 Source Handler Implementations

| Source | Implementation | Key behavior |
|--------|---------------|--------------|
| **PubMed** | NCBI E-Utilities (`esearch.fcgi` + `efetch.fcgi`) | Supports PMID list, query string, date range. Respects NCBI rate limits (3 req/s). |
| **RSS/Atom** | `feedparser` | Standard feed parsing. Proxied via Playwright for JS-rendered feeds. |
| **Web** | `trafilatura` (primary) + Playwright fallback (JS-rendered) | Extracts article body, ignores boilerplate. |
| **Email** | IMAP IDLE + polling | Configurable folders. New emails trigger collection. |
| **PDF** | PyMuPDF (`fitz`) | Text extraction. Layout-aware reading order. |

### 1.5 Incremental Collection Tracking

Each source tracks its own collection state in a per-source JSON file:

```yaml
# collections/<domain>/<source>/_runs.json
{
  "source_name": "pubmed",
  "last_collected_at": "2026-07-20T08:00:00Z",
  "last_item_id": "39817291",
  "total_runs": 42,
  "total_items_collected": 892,
  "total_errors": 3,
  "last_error": null,
  "status": "healthy"
}
```

On `collect`, the handler requests **only items newer than** `last_collected_at` (or since `last_item_id` for paginated APIs). `--force-full` ignores this and re-fetches everything, re-running dedup.

---

## 2. KB Pipeline (§12.4, 12.7)

### 2.1 Four-Tier Architecture

```
    01-Raw         02-Draft       03-Wiki
      ↑               ↑              ↑
  Sole entry      Agent can       Only human
  point for all   process Raw     can promote
  collected       and create      Draft → Wiki
  content         Draft           (Wiki = permanently reviewed)
```

| Tier | Purpose | Written by | Edited by | Durability |
|------|---------|-----------|-----------|------------|
| **01-Raw** | Immutable source record | Agent (from collected items) | Agent (re-collection only) | Append-only per collection |
| **02-Draft** | LLM-processed summary | Agent (from 01-Raw) | Agent (re-extract from same Raw) | Replaceable (re-processing) |
| **03-Wiki** | Reviewed, permanent knowledge | Human (promote from Draft) | Human only | Immutable (append-only) |

### 2.2 Storage

All tiers are stored as flat Markdown files with YAML frontmatter in `kb/{domain}/{tier}/`:

```markdown
---
id: "raw_abc123"
source_url: "https://pubmed.ncbi.nlm.nih.gov/12345"
source_type: "pubmed"
source_platform: "pubmed"
collected_at: "2026-07-26T10:00:00"
topics: ["IVF breakthroughs"]
relevance_score: 85
trace_id: "trc_abc123"
---

## Title of the Article

Body content extracted from source...
```

### 2.3 File Path Convention

```
kb/{domain}/{tier}/{yyyy}/{mm}/{dd}/{slug}.md
```

Where `slug` is a sanitized version of the article title (lowercase, hyphens, max 80 chars). This enables natural browsing by date.

### 2.4 Git Backing

The entire `kb/` directory is a git repository (separate from the AutoInfo source repo). Every KB write is a git commit:

```bash
git add kb/{domain}/{tier}/{yyyy}/{mm}/{dd}/{slug}.md
git commit -m "[{tier}] {domain}: {article title}"
```

This provides full history, diff between versions, and recovery. No explicit "versioning" system needed — git handles it.

### 2.5 SHA Tracking

Each KB entry's YAML frontmatter includes `content_sha: <sha256(content + metadata)>`. When re-processing produces a different SHA, the old entry is preserved (git retains history) and the new entry gets a new path (new slug with `-v2` suffix).

---

## 3. Processing & LLM Extraction (§12.6)

### 3.1 Extraction Pipeline

For each 01-Raw entry being processed:

```
Raw entry
  ↓
1. Build prompt from domain schema (custom_fields + system instruction + KB context)
2. Call LLM (configurable model per task; fallback chain supported)
3. Parse structured output (JSON for custom_fields, TL;DR, key_points, entities)
4. Run G4 factual consistency check (if --check-factual)
5. Run G5 translation accuracy check (if --check-translation)
6. Build 02-Draft entry from extraction result
```

### 3.2 Structured Extraction Fields

Per-domain schema defines `custom_fields`:

```yaml
# domain config
extraction:
  custom_fields:
    - name: key_findings
      type: list[str]
      description: "Key findings from the article"
    - name: methodology
      type: str
      description: "Research methodology used"
```

Each extraction run produces:

```python
@dataclass
class ExtractionResult:
    tl_dr: str                         # One-sentence summary
    key_points: list[str]             # 3-5 bullet points
    entities: dict[str, list[str]]    # Extracted entities by type
    custom_fields: dict               # Domain-specific fields
    quality_score: float = 0.0        # 0-100, from G4/G5
    facts: list[str] = field(default_factory=list)    # verifiable claims (for G4)
    translation: str | None = None    # Translated text (if language != source)
```

### 3.3 LLM Configuration

LLM usage follows a hierarchical config:

```
Per-domain task config (model override for extraction, G4, G5, etc.)
  ↕ falls through
Domain-level LLM config (provider, model, base_url, api_key)
  ↕ falls through
Global config.yaml [llm] section
  ↕ falls through
Environment variables (AUTOINFO_LLM_API_KEY, etc.)
  ↕ falls through
Defaults (openrouter / deepseek/deepseek-chat / AUTOINFO_LLM_API_KEY)
```

Each task (extraction, g4_factual_check, g5_translation_check, relevance_scoring) can specify:
- `model` — model name
- `provider` — `openrouter`, `openai`, or any LiteLLM-supported provider
- `base_url` — custom endpoint URL
- `api_key` — key (or env var reference)
- `temperature`, `max_tokens` — generation params

**Key rule**: The operator picks the model. No automatic model selection. Defaults are sensible (deepseek-chat for extraction, Claude for factual consistency checks), but always overridable.

#### Full LLM Configuration Example

```yaml
# ~/.autoinfo/config.yaml
llm:
  default_provider: openrouter
  default_model: deepseek/deepseek-chat      # cheap default for bulk work

  tasks:
    extraction:                               # F15: field extraction from raw items
      provider: openrouter
      model: deepseek/deepseek-chat           # cheap — bulk volume
      max_tokens: 2000

    summarization:                            # F15: TL;DR + key points
      provider: openrouter
      model: anthropic/claude-sonnet-4        # premium — quality matters
      max_tokens: 1000

    translation:                              # F10: cross-lingual
      provider: openrouter
      model: anthropic/claude-sonnet-4

    synthesis:                                # F24-F25: digest/report generation
      provider: openrouter
      model: anthropic/claude-sonnet-4
      max_tokens: 4000

    quality_check:                            # G4-G5: factual consistency check
      provider: openrouter
      model: deepseek/deepseek-chat

    embedding:
      provider: openrouter
      model: openai/text-embedding-3-small    # or any embedding model

  fallback:
    - provider: openrouter
      model: anthropic/claude-sonnet-4
    - provider: local                         # ollama/vllm if configured
      model: qwen2.5:72b
```

#### LLM Config Agent Tools

| Tool | Purpose |
|------|---------|
| `get_effective_llm_config(task="extraction")` | Returns resolved model config for a task: `{task, provider, model, max_tokens, fallback_chain}`. Agent inspects config before processing instead of parsing YAML. |
| `list_available_models()` | Returns all models the user has configured access to (from config + LiteLLM provider discovery): `[{task, provider, model, status: "available" / "needs_key"}]`. Agent uses this to choose models for manual processing calls. |

---

#### 3.4 LLM Fallback Chain

```yaml
llm:
  fallback:
    - provider: openrouter
      model: anthropic/claude-sonnet-4
    - provider: local
      model: qwen2.5:72b
```

When the primary model fails (timeout, rate limit, server error), AutoInfo iterates through the fallback chain. Each fallback is tried once before escalating to the next.

**Note**: As of v1.6, the fallback chain is parsed from config but the primary extraction path (`_call_llm`) retries the same model rather than iterating through fallbacks. This is a known low-effort gap — see §14.1 of `founder-expectations.md` for the fix plan.

---

## 4. Custom Extraction & Q&A (§12.5, 12.8)

### 4.1 Custom Extraction

Two MCP tools for ad-hoc extraction:

| Tool | Description |
|------|-------------|
| `extract_fields(domain, text, fields)` | One-shot LLM extraction of arbitrary fields from provided text (no KB write). Used for quick tests or manual article processing. |
| `get_extraction(entry_id, fields)` | Re-extract specific fields from an existing KB entry without full re-processing. Cached — if fields were previously extracted, return cached result. |

### 4.2 Q&A

```
query_collected(domain, query) → Answer with sources
```

Uses FTS5 full-text search across `kb/{domain}/02-Draft/` to find relevant entries, then calls LLM to synthesize an answer with inline citations. The LLM prompt constrains the model to answer **only** from the retrieved entries — no external knowledge.

---

## 5. CEFR Classification (§12.13)

Used by the `language-learning` demo domain. CEFR levels (A1-C2) are classified via LLM with per-language prompts.

| Language | Supported levels | Confidence output |
|----------|-----------------|-------------------|
| EN | A1-C2 | level + confidence 0-1 + feature tags |
| ZH | A1-C2 | level + confidence 0-1 + feature tags |
| JA | A1-C2 | level + confidence 0-1 + feature tags |

Output structure:

```json
{
  "level": "B2",
  "confidence": 0.87,
  "features": ["academic vocabulary", "complex sentence structure", "passive voice"]
}
```

---

## 6. Import Pipeline (§12.12)

`import_kb` ingests external documents into 01-Raw:

| Format | Handler | Notes |
|--------|---------|-------|
| PDF | PyMuPDF | Layout-aware text extraction |
| Markdown | Direct read | Frontmatter parsed if present |
| HTML | trafilatura | Body extraction, boilerplate removal |
| JSON | Structured parse | Must match Item schema fields |

All imports create 01-Raw entries identical to collected items (same `source_url` — uses a synthetic URL `import://{filename}`, same `source_type` — `import`, same `content_sha` dedup).

---

## 7. Cross-Collection Dedup & Merge (§12.18)

**Problem**: The same article may appear from different sources (e.g., PubMed + RSS + email alert).

**Approach**: Multi-level dedup:

| Level | Method | Scope | Cost |
|-------|--------|-------|------|
| 1 | URL exact match | All items in collection cache | O(1) hash lookup |
| 2 | PMID/DOI/arXiv ID match | All KB tiers + collection cache | O(1) index lookup |
| 3 | Fuzzy title similarity (Levenshtein, window=100 chars, threshold=0.85) | Items within configurable window (default 30 days) | O(n) in window |
| 4 | Cross-source similarity (LLM-based semantic check) | Items flagged at level 3 as potential duplicates | 1 LLM call per candidate pair |

**Merge rule**: When duplicate detected at levels 1-3, the newer item is skipped (logged as duplicate). When detected at level 4, an LLM decides whether to merge (append source URLs, combine metadata) or keep separate.

---

## 8. Performance Targets

| Dimension | Target | Notes |
|-----------|--------|-------|
| **Sources per domain** | 5-20 (typical), up to 100 (max) | RSS/API sources. Web page sources are heavier. |
| **Items per day** | 200-1000 total across all domains | ~50-200 per domain typical |
| **Domains per user** | 1-5 (typical), up to 10 (max) | Each with independent sources and topics |
| **Collection latency** | <2 min for 50 items from 3 sources | RSS: fast. API: depends on rate limits. Web: slower. |
| **Processing latency** | <5 min for 50 items (with LLM extraction) | Async batch. User doesn't wait synchronously. |
| **LLM cost per day** | ~$0.50-2.00 (tiered models, 200 items) | DeepSeek for extraction ($0.15/M), Claude for synthesis ($3/M) |
| **KB storage** | 10K+ entries, negligible disk usage | Markdown files. ~5KB per entry = 50MB for 10K entries. |
