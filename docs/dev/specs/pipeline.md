<!-- agent: pipeline-internals -->
# Collection & Processing Pipeline

> Extracted from `founder-expectations.md §§12.2-12.8, 12.12, 12.18`. References: F5-F9 (Collection), F10-F14 (Processing/Extraction), F15 (LLM Config).
> **B2 lifecycle:** `docs/dev/specs/user-lifecycle-definition.md` §3 (B2 Direct User Lifecycle). Pipeline execution occurs in the B2.4 Operate stage. See §9 for the full B2 lifecycle mapping.
> **Keystone matrix:** [`docs/dev/cross-dimensional-catalog.md`](../cross-dimensional-catalog.md) — the A1 (Collection) and A2 (Extraction) columns define what this pipeline stage must produce. CD entries cross-reference specific gaps.

---

## 1. Collection Pipeline (§12.2)

### 1.1 Item Dataclass Schema

> **Format scope note**: The pipeline collects **text content**. Video and audio sources (Spotify, YouTube, Bilibili, Apple Podcasts) are supported as metadata collectors — they ship titles, descriptions, and metadata, not media content. For full media format pipeline gaps, see [`cross-dimensional-catalog.md`](../cross-dimensional-catalog.md) (the keystone product matrix).

Every collected source item is represented as an `Item`:

```python
@dataclass
class Item:
    """A single collected item from any source."""
    id: str
    source_name: str
    source_type: str                  # one of VALID_SOURCE_TYPES (29 types, single source of truth in src/autoinfo/config.py)
    source_url: str
    title: str
    content: str                      # main body text
    content_type: str = "text"
    source_platform: str = ""         # e.g. "pubmed", "arxiv", "hn"
    collected_at: str = ""            # ISO-8601 timestamp (string, not datetime)
    language: str = ""
    domain: str = ""
    topic_tags: list[str] = field(default_factory=list)   # matched topic names
    quality_tier: int = 1             # 1-4, propagated from source config at collect time (G1 input)
    raw_data: dict[str, Any] = field(default_factory=dict)  # source-specific (DOI, PMID, URL)
    version: int = 1
    previous_version: int = 0
    supersedes: str = ""
    trace_id: str = ""                # UUID assigned at collection, carried through delivery
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
Phase 1 — Fetch:     autoinfo collect --domain X   (MCP: collect_sources(domain=X))
  → Source handlers fetch items in parallel
  → Raw JSON cached to collections/
  → Dedup (URL → PMID/DOI → fuzzy title)
  → Collection log written (per-item trace_id, timestamps, source)

Phase 2 — Process:   autoinfo process --domain X [--model deepseek-chat]   (MCP: process_collection(domain=X))
  → Reads cached raw items (from collection cache, not KB)
  → LLM extraction (configurable model per task)
  → Quality gates (G0-G5)
  → Creates 01-Raw KB entries (one per validated item)
```

> **Agent reference**: All pipeline operations are available as MCP tools. See [mcp-tools.md](./mcp-tools.md) for the full catalog.

### 1.4 Source Handler Implementations

> **Single source of truth**: the `VALID_SOURCE_TYPES` frozenset in `src/autoinfo/config.py` (29 types) is the canonical source-type registry. Adding a type requires updating BOTH the set and `_build_handler` in `src/autoinfo/collectors/__init__.py` — enforced by the parity test in `tests/test_source_dispatch.py`. The 30 handler modules below live in `src/autoinfo/collectors/`.

| Source | Implementation | Key behavior |
|--------|---------------|--------------|
| **PubMed** | NCBI E-Utilities (`esearch.fcgi` + `efetch.fcgi`) | Supports PMID list, query string, date range. Respects NCBI rate limits (3 req/s). |
| **arXiv** | arXiv API (`export.arxiv.org/api/query`) | Atom feed parsing, date range, category filters. |
| **Semantic Scholar** | Semantic Scholar Graph API | Paper metadata, citation counts, DOI lookup. |
| **CrossRef** | CrossRef REST API (`api.crossref.org`) | DOI metadata, works query, reference lists. |
| **DBLP** | DBLP XML API (`dblp.org/search`) | Computer science bibliography, author/publication search. |
| **OpenAlex** | OpenAlex REST API | Works, authors, institutions, concepts. |
| **USPTO** | PatentsView API | Patent metadata, assignee, classification. |
| **NYT** | NYT Article Search API | Article metadata, query, date range. |
| **RSS/Atom** | `feedparser` | Standard feed parsing. Proxied via Playwright for JS-rendered feeds. |
| **Web** | `trafilatura` (primary) + Playwright fallback (JS-rendered, separate `web_playwright.py` handler) | Extracts article body, ignores boilerplate. |
| **Webhook** | HMAC-signed inbound push | Per-domain webhook receiver, signature verification. |
| **Email** | IMAP IDLE + polling | Configurable folders. New emails trigger collection. |
| **PDF** | PyMuPDF (`fitz`) | Text extraction. Layout-aware reading order. Configurable timeout (default 120s). |
| **Reddit** | Reddit API | Subreddit monitoring, post/comment collection. |
| **Spotify** | Spotify Web API | Podcast episodes, show metadata. |
| **YouTube** | YouTube Data API v3 | Channel videos, search, transcript retrieval. |
| **Bilibili** | Bilibili API | Video metadata, danmaku, channel monitoring. |
| **Apple Podcasts** | Apple Podcasts Connect API | Episode metadata, feed URL lookup. |
| **AP API** | Associated Press API (paid) | Newswire content, licensing tiers. |
| **Reuters MCP** | Reuters MCP server (paid) | News feed via MCP protocol, licensing required. |
| **SSRN** | SSRN API | Social science preprints, working papers. |
| **GDELT** | GDELT DOC 2.0 API | Global event tracking, news monitoring at scale. |
| **HackerNews** | Hacker News Firebase API | Two-step fetch: item metadata then content. |
| **HuggingFace/Kaggle** | HuggingFace Hub + Kaggle APIs | Dataset/model metadata, competition data. |
| **Unpaywall/CORE** | Unpaywall + CORE APIs | Open-access paper lookup, full-text retrieval. |
| **Yahoo Finance** | Yahoo Finance API | Market data, quotes, historical prices. |
| **HTTP API** | Generic HTTP/REST adapter | Configurable endpoint, auth, pagination. Covers Quandl and other generic REST sources. |
| **AKShare** | AKShare open library | Chinese + global market data via AKShare (no key) — **M2 (2026-08-05)** |
| **SEC EDGAR** | SEC EDGAR full-text + filings | Ticker→CIK→filings via EDGAR APIs, UA + 10 req/s (no key) — **M2 (2026-08-05)** |
| **edX sitemap** | edX course sitemap | Sitemap crawl gated by robots.txt RFC 9309 (no key) — **M2 (2026-08-05)** |

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

### 1.6 Fetch Depth & Fulltext Fetching

Each source carries a `fetch_depth` setting (`SourceConfig.fetch_depth`, default `"abstract"`, values `"abstract"` / `"fulltext"`). The dispatch layer threads it into collection: `collect.py` injects the per-source `fetch_depth` into the handler `config` before invoking it, so handlers that read `fetch_depth` switch their fetch behavior while handlers that ignore it are unaffected (the key is inert). `autoinfo domain import` / CLI source management preserve and round-trip the setting.

When `fetch_depth == "fulltext"`, the following collectors fetch the full article body instead of metadata/abstract only:

| Collector | Fulltext source | Cap / fallback |
|-----------|-----------------|----------------|
| **unpaywall** | Open-access full text via Unpaywall/CORE (OA PDF/HTML → extracted text) | 8000-char cap (`FULLTEXT_CONTENT_CAP`); falls back to abstract if no OA full text is available |
| **rss** | The entry's link target (fetches + extracts the linked article) | 8000-char cap (`FULLTEXT_MAX_CHARS`); falls back to the feed description |
| **youtube** | Video transcript retrieval | Falls back to description when no captions/transcript are available |
| **gdelt** | The linked news article | 8000-char cap (`FULLTEXT_CONTENT_CAP`); falls back to GDELT-provided metadata |

The fulltext content is used for deeper extraction (G4 factual checks, custom fields) while the abstract-level path stays cheap for high-volume sources.

---

## 2. KB Pipeline (§12.4, 12.7) (executes in B2.4 Operate stage)

### 2.1 Four-Tier Architecture

```
    01-Raw         02-Draft       03-Wiki
      ↑               ↑              ↑
  Sole entry      Agent can       Agent promotes
  point for all   process Raw     Draft → Wiki via
  collected       and create      promote_kb_draft
  content         Draft           (no human gate —
                                  KB is a production database)
```

| Tier | Purpose | Written by | Edited by | Durability |
|------|---------|-----------|-----------|------------|
| **01-Raw** | Immutable source record | Agent (from collected items) | Agent (re-collection only) | Append-only per collection |
| **02-Draft** | LLM-processed summary | Agent (from 01-Raw) | Agent (re-extract from same Raw) | Replaceable (re-processing) |
| **03-Wiki** | Reviewed, permanent knowledge | Agent (promote from Draft, no human gate) | Agent only (append-only) | Immutable (append-only) |

### 2.2 Storage

All tiers are stored as flat Markdown files with YAML frontmatter in `knowledge/{domain}/{tier}/`:

```markdown
---
entry_id: "raw_abc123"
source_url: "https://pubmed.ncbi.nlm.nih.gov/12345"
source_type: "pubmed"
source_platform: "pubmed"
collected_at: "2026-07-26T10:00:00"
tags: ["IVF breakthroughs"]
relevance_score: 85
trace_id: "trc_abc123"
---

## Title of the Article

Body content extracted from source...
```

### 2.3 File Path Convention

```
knowledge/{domain}/{tier}/{topic}/{YYYY-MM-DD}-{slug}.md
```

Where `slug` is a sanitized version of the article title (lowercase, hyphens, max 80 chars). This enables natural browsing by date.

### 2.4 Git Backing

The entire `knowledge/` directory is a git repository (separate from the AutoInfo source repo). Every KB write is a git commit:

```bash
git add knowledge/{domain}/{tier}/{topic}/{YYYY-MM-DD}-{slug}.md
git commit -m "[{tier}] {domain}: {article title}"
```

This provides full history, diff between versions, and recovery. No explicit "versioning" system needed — git handles it.

### 2.5 Version Tracking

Re-collection creates a new `Item` with an incremented `version` (and `previous_version` linking the prior version); KB entries carry `version` / `previous_version` / `supersedes` in their frontmatter. When re-processing produces a new version, the old entry is preserved (git retains history) and the new entry gets a new path (new slug with `-v2` suffix). There is no content-hash field in the model — versioning is tracked via the explicit version fields and git history.

### 2.6 Product Analysis Metadata

Differentiated product generation (premium-briefing / enterprise-briefing / magazine-digest — see delivery.md §1.1) persists its per-product LLM analysis onto the source KB entries via `KBStore.update_entry_metadata` (no new store, no new tool). The analysis lives in the entry's existing `custom_fields` dict under the reserved key:

```yaml
custom_fields:
  product_analysis:            # written by _persist_product_analysis_to_kb during product generation
    product: "premium-briefing"
    implications: ["So-what per key_findings entry ..."]     # list[str], index-aligned with key_findings
    risks: ["..."]                                            # list[str], index-aligned
    action_required: ["..."]                                  # list[str], index-aligned (premium/enterprise)
    key_metrics: [{"metric": "...", "value": "...", "source": "..."}]  # enterprise only
```

The persisted analysis is **searchable**: `search_knowledge_base(filter_custom_fields={"product_analysis.action_required": ""})` returns entries whose product analysis prescribes an action (presence match), and `{"product_analysis.product": "premium-briefing"}` narrows to a specific product (exact match). See mcp-tools.md for the `filter_custom_fields` semantics (dot-path into `custom_fields`, `""` = presence, non-empty = exact match, path-injection validated).

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
    """Structured extraction output from LLM processing."""
    item_id: str
    title: str = ""
    tl_dr: str = ""                    # One-sentence summary
    key_points: list[str] = field(default_factory=list)  # 3-5 bullet points
    entities: list[dict[str, Any]] = field(default_factory=list)  # Extracted entities — list of dicts (not dict-of-lists)
    relevance_score: float = 0.0       # populated by G3
    custom_fields: dict[str, Any] = field(default_factory=dict)   # Domain-specific fields
    usage: dict[str, Any] = field(default_factory=dict)  # LLM token usage metadata
```

#### Report Thematic Grouping (issue #311)

Report generation groups KB entries into 3–5 themes via an LLM. The grouping
prompts (main + strict-retry) require each theme to carry a SHORT SEMANTIC
title — a concise noun phrase (2-6 words) naming the theme, never a raw
keyword list, concatenated entry titles, or separator-dumped keywords.
After batches are merged, `_merge_theme_groups` first merges themes that
normalize to the same string, then runs a near-duplicate pass: pairs whose
normalized token sets have Jaccard similarity >= 0.6 with one set a subset
of the other are merged (longest original title kept, entries deduplicated
by `entry_id`), so report section headings are unique semantic titles.

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

**Note**: As of the current implementation, the config system supports per-task model configuration and fallback chains. When the primary model fails (timeout, rate limit, server error), AutoInfo iterates through the configured `llm.fallback` chain. Each fallback is tried once before escalating to the next. See §3.3 for the full LLM configuration hierarchy.

---

### 3.5 LLM Concurrency, Rate Limiting & Retry (2026-08-13 llm-concurrency-remediation wave)

Every LLM call route through `llm.call_with_fallback` (llm.py) and inherits the same concurrency controls; gate semantics (G0-G5 thresholds/actions/retry-block) are **unchanged** — limiter and backoff wrap the calls, they do not alter gate outcomes.

**Per-provider shared rate limiting** — `_PROVIDER_SEMAPHORES` (llm.py) holds one `threading.Semaphore` per `(provider, base_url)`; `AUTOINFO_LLM_MAX_CONCURRENCY` env override (default 4, clamped ≥1) bounds in-flight requests per provider. Enforced across **every** fan-out path: process workers, post-extraction gates, cefr_batch, output grouping, MCP `asyncio.to_thread` handlers, and the fallback chain itself (each chain entry walks under the same limiter). There is no single global process-wide lock.

**429/5xx jittered backoff** — HTTP 429 and 5xx are retried inside `call_with_fallback` with jittered exponential backoff: at most 3 total attempts (2 retries), base 1.0s, factor 2, cap 8s, jitter ±25%. Non-retryable 4xx (400/403/404) surface immediately, never retried; after the final attempt the last error surfaces.

**Per-task model routing** — `_resolve_task_llm_config` (config.py) resolves the model per task and feeds `call_with_fallback(task=)` → `_build_config_with_model` (process.py, which disables task routing for explicit model overrides). Extraction/classification tasks use the task-config model, else the base model. Judgment calls (G4 factual, G5 translation, llm_judge) resolve config-first (issue #195): `llm.judgment_model` (shipped default `openai/deepseek-v4-flash` in default_config.yaml) → `llm.model` → a loud `JudgmentModelNotConfiguredError` — never a code-constant guess (the #127 ghost-model failure mode), so judgment never drifts with runtime task config and an unconfigured deployment fails loudly.

**Processing parallelism** — `AUTOINFO_PROCESS_WORKERS` (default 5, env-clamped 1..16; cap raised 8→16 probe-gated: 0 rate limits at workers 1/4/8/16 × 12 with bounded p95, see `scripts/test_llm_concurrency.py`) bounds the per-item extraction thread pool. Post-extraction gates G3/G4/G5/CEFR run concurrently per item under `AUTOINFO_SUBTASK_CAP` (default 4); canonical gate order, G3 retry loop, G4 hard-gate 3× retry and the G0-G5 report order are preserved. The CEFR classification LLM call runs **outside** `_STORAGE_LOCK` (only its storage writes take the lock).

**MCP & output parallelism** — `AUTOINFO_CEFR_BATCH_WORKERS` (default 8, never more than the text count) bounds `cefr_batch` fan-out with order preserved and per-item errors; 14 sync LLM handlers (suggest_keywords, classify_cefr, cefr_batch, extract_fields, generate_digest, generate_report, generate_cross_domain_report, generate_tutorial, generate_presentation, localize_content, query_collected, recommend_content, simplify_content, promote_kb_draft) are offloaded via `asyncio.to_thread`; `_group_by_theme` batch loop is parallelized (max 4 workers, batch size `_GROUPING_BATCH_SIZE`=8 unchanged, results collected by index so order is preserved, exec-summary calls remain serial).

**Probe** — `scripts/test_llm_concurrency.py` accepts `--workers N` / `--total N` and reports `p95` (95th percentile of per-call durations) and `rate_limit_count`; no-args keeps the serial baseline + (1,3,5) sequence.

---

### 3.6 Processing Cursor: Monotonic Item-Id Ledger (issue #637, v1.21.3)

The resume cursor lives in `autoinfo.db` (`_get_progress_db_path()`, the same SQLite file that backs the KB index), and `_init_progress_table` creates two tables with distinct jobs:

| Table | Columns | Role |
|-------|---------|------|
| `processing_items` | `domain`, `item_id`, `processed_at`; PRIMARY KEY `(domain, item_id)` | **Authoritative** item-id ledger |
| `processing_progress` | `domain`, `last_processed_index`, `total_items` | **Legacy** position cursor, retained as a public contract |

**Why the cursor is monotone** — the cursor anchor is the stable `Item.id`, not a position plus a snapshot count. `_read_processed_ids(domain)` returns the ledger's id set and the pending list is computed as `[it for it in cached_items if it.id not in processed_ids]`; an id is pending exactly once until it is marked, so a nightly collection that grows (or shrinks) the cache no longer resets the cursor to zero and re-processes the whole backlog — the failure mode that position-based tracking had before #637 (parent issue #596 / BACKLOG B7).

**Per-item durability** — `_mark_processed` runs as soon as each item's processing settles (`INSERT OR IGNORE`, so re-marking is idempotent) with an ISO-8601 UTC `processed_at`. Items whose log status is `"error"` are deliberately **not** marked, so a failed item is retried on the next run instead of being silently sunk. A run killed by an external timeout therefore keeps every item it already finished.

**`resume_from` and `batch_size`** — `run_processing(..., batch_size=0, resume_from=None)` derives two booleans: `persist_cursor = batch_size > 0 or resume_from in ("auto", "start")` and `use_cursor = batch_size > 0 or resume_from == "auto"`. The modes are:

- `resume_from=None` (default) — legacy behaviour: the cursor is consulted only when `batch_size > 0`.
- `resume_from="auto"` — consult the ledger and process the pending remainder even when `batch_size` is 0 (this is what `scripts/nightly_process.py` always passes).
- `resume_from="start"` — `_reset_progress(domain)` deletes the `processing_progress` row **and** every `processing_items` row for the domain, then reprocesses from the beginning.

When the cursor is in use, `effective_batch = batch_size if batch_size > 0 else len(pending)`, and `remaining_count` / `is_complete` are computed from the pending set rather than from the cache total.

**One-shot migration** — a pre-#637 domain has a legacy position cursor but an empty ledger. When `_read_processed_ids` returns nothing and `last_processed_index > 0`, the first `legacy_index` cached items are seeded into the ledger via `_mark_processed` ("the first N items in cache order were processed"), after which the domain continues on the id path. At the end of any run with `persist_cursor`, `_write_progress(domain, new_index, total_items)` still updates the legacy row so `get_processing_progress()` keeps returning `{total_items, processed_count, remaining_count, is_complete}` unchanged.

### 3.7 Time Window & Ordering: `--since-days` / `--newest-first` (issue #655, v1.21.4)

`load_cached_items(domain, base_path="collections", *, since_days=0, newest_first=False)` gained both parameters, and both are **no-ops at their defaults** so existing callers keep the cache's directory-walk order. The loader only resolves timestamps when `since_days > 0 or newest_first` (`need_timestamps`), so an unparameterised call does no extra work.

**Timestamp resolution** — `_resolve_cache_timestamp(item, date_dir)` parses `item.collected_at` with `datetime.fromisoformat` (a naive value is assumed UTC), and falls back to the parent cache directory name via `date.fromisoformat(date_dir.name)` at midnight UTC — items live under `collections/<domain>/<source>/<date>/`. If neither works the item's time is `None`.

**Window** — `since_days > 0` computes `cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)` and drops items with a resolved timestamp older than the cutoff. Items whose time **cannot be determined are kept**, never silently dropped (only a debug log line is written). `since_days=0` applies no window.

**Ordering** — `newest_first=True` sorts with `_newest_first_key = (ts is None, -ts.timestamp() if ts is not None else 0.0, item.id)`: newest first, undated items last, ties broken by item id. `newest_first=False` preserves the sorted directory walk, i.e. the prior oldest-first behaviour.

**Threading** — `run_processing(..., since_days=0, newest_first=False)` forwards both straight to `load_cached_items`, and the CLI exposes them as `--since-days N` (default 0) and `--newest-first` (default off). `scripts/nightly_process.py` forwards both to the `autoinfo process` subprocess and additionally passes `since_days` to `count_cached_items`, which narrows the backlog count **by path parsing only** — a date-named parent directory older than the cutoff is skipped and a non-date directory never filters a file out; cache files are never opened.

### 3.8 Nightly Process Stage: Hard Budget & Fair-Share Batching (issue #635, v1.18.0)

The nightly batch used to run `collect` → `nightly_gap.py`; `scripts/nightly_process.py` inserts the LLM-bound process stage between them but only for domains that actually have a backlog: `backlog = count_cached_items(...) - read_processed_count(...)`, and a domain is due only when `backlog >= --min-backlog`. `read_processed_count` prefers `SELECT COUNT(*) FROM processing_items` (the #637 ledger, unaffected by cache-total changes) and falls back to `last_processed_index` from `processing_progress` for pre-#637 projects.

**Hard run budget** — `--max-seconds` (default 2400) is a hard wall-clock budget for the whole run, so the lane returns inside the systemd window instead of eating the next stage's time; `--max-seconds 0` disables it for manual/backlog runs. `--timeout` (default 7200) caps a single domain, `--seconds-per-item` (default 40, measured on the 2026-10-21 backlog) converts an allowance into an item count, and `--batch-size 0` means "derive it from the budget".

**Fair share across due domains** — for each due domain, with `remaining_due = due_count - assigned + 1`:

- `consumed` is elapsed wall time on a real run, or the sum of projected allowances on `--dry-run` (a dry run cannot observe durations);
- `remaining = max_seconds - consumed`; if `remaining <= 0` the domain is marked `skipped_budget` and never started;
- otherwise `allowance = remaining / remaining_due`. If `allowance < seconds_per_item` and more than one domain is still due, the domain is deferred as `skipped_budget` (a smaller due set may still fit); when it is the last due domain it gets the whole `remaining` instead, and is skipped only if even that is below `seconds_per_item`.

**Derived batch and subprocess** — `_derive_batch_size` returns `max(1, min(backlog, int(allowance // seconds_per_item)))`, or 0 ("all") when the budget is disabled. The per-domain subprocess timeout is `max(1, int(min(--timeout, allowance)))`, and the invocation is `autoinfo process --domain <d> --resume-from auto`, appending `--batch-size`, `--since-days` and `--newest-first` only when set. A subprocess killed by the timeout returns exit code 124; `--dry-run` reports `would_run` with the projected `budget_s` and `batch_size` instead of executing.

**Reporting** — per-domain rows carry `cached_items`, `processed_count`, `backlog`, `action`, `budget_s`, `batch_size`, `exit_code` and `duration_s`; the summary counts `selected`, `executed`, `failed`, `skipped` and `skipped_budget`, and sets `budget_exhausted` when the budget is enabled and at least one domain was skipped for budget. Output is machine-readable JSON (`--json-out`) plus a Markdown table (`--md-out`, also printed), and exit codes are 0 (all selected domains succeeded or nothing was due), 1 (at least one failure), 2 (usage/environment error).

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

Uses FTS5 full-text search across `knowledge/{domain}/02-Draft/` to find relevant entries, then calls LLM to synthesize an answer with inline citations. The LLM prompt constrains the model to answer **only** from the retrieved entries — no external knowledge.

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

All imports create 01-Raw entries identical to collected items (same `source_url` — uses a synthetic URL `import://{filename}`, same `source_type` — `import`, subject to the same URL-based dedup rules).

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

---

## 9. B2 Lifecycle Integration

> **Root spec:** `docs/dev/specs/user-lifecycle-definition.md` §3 (B2 Direct User Lifecycle)
> **F-expectations:** F05-F06 (B2.1 Discover, B2.2 Connect), F05/F08-F10b/F14 (B2.3 Configure), F11-F15 (B2.4 Operate), F31/F32/F52 (B2.5 Monitor), F69 (B2.6 Report)
> **Delivery spec:** `docs/dev/specs/delivery.md` for delivery-stage mapping

This section maps each B2 lifecycle stage (from the root spec) to the pipeline sections that implement it. The pipeline is the operational backbone of B2's execution.

### 9.1 B2.1 Discover

**B2 discovers available AutoInfo capabilities.**

| Capability | Pipeline Section | MCP Tool(s) |
|-----------|-----------------|-------------|
| MCP tool discovery | N/A (MCP protocol) | Protocol-level `tools/list` — auto-discovery |
| Domain listing | — | `list_domains()` |
| Available sources | §1 (Collection Pipeline) | `list_available_platforms()` |
| Available models | §3 (LLM Config) | `list_available_models()` |
| Output templates | §1.1 (Product Types) | `list_output_templates()` |

### 9.2 B2.2 Connect

**B2 establishes session and verifies system health.**

| Capability | Pipeline Section | MCP Tool(s) |
|-----------|-----------------|-------------|
| System health check | — | `health_check()`, `diagnose_system()` |
| MCP session establishment | N/A (transport layer) | stdio connection (SSE is future work) — no pipeline involvement |
| LLM connectivity | §3.1 (LLM Configuration) | `diagnose_system()` checks LLM key |

### 9.3 B2.3 Configure

**B2 configures sources, topics, extraction schemas, and schedules. Done once (or when domains change), not per-cycle.**

| Capability | Pipeline Section | MCP Tool(s) |
|-----------|-----------------|-------------|
| Domain activation | §1.1 (Domain as config) | `activate_domain()`, `add_domain()` |
| Source registration | §1.4 (Source Handler Architecture) | `add_source()`, `add_sources()` |
| Topic configuration | §1.2 (Topic → Keyword matching) | `add_topic()` |
| Schedule setup | §1.6 (Cron scheduling) | `add_schedule()` |
| Gate configuration | Quality gates spec | `set_gate_config()` |

### 9.4 B2.4 Operate

**This is the core pipeline execution — the primary B2 activity. Repeated on every schedule tick.**

| Pipeline Phase | B2 Action | Pipeline Section |
|---------------|-----------|-----------------|
| **Collect** | `collect_sources(domain, topic)` → fetch items from all configured sources | §1 (Two-Phase Collection) |
| **Process** | `process_collection(domain)` → LLM extraction + quality gates | §2 (KB Pipeline), §3 (LLM Extraction) |
| **Store** | Create KB entries (Raw → Draft pipeline) | §2 (KB Pipeline: 01-Raw→02-Draft) |
| **Generate** | `generate_digest()` / `generate_report()` etc. | delivery.md §1 (Output Generation) |
| **Deliver** | `send_email_digest()` / delivery via channels | delivery.md §2 (Delivery Channels) |

B2.4 Operate reads the B1 subscription configs to determine:
- Which domains to collect (from B1's `domains`)
- How frequently to run (from B1's `frequency`)
- What to generate (from B1's `content_preference`)
- Where to deliver (from B1's `channels`)
- Which products to generate (from B1's tier → product mapping)

Generated products cite their sources: digest/report/tutorial bodies carry
inline citations to the real KB entry `source_url`s they synthesize (e.g.
`(Source: https://…/12345678/)`), so every claim is traceable back to a
collected item (issue #312 tutorial citations).

### 9.5 B2.5 Monitor

**B2 monitors pipeline execution health. This is ongoing.**

| Monitoring Action | Data Source | Pipeline Section |
|------------------|-------------|-----------------|
| Collection progress | `get_collection_progress()` | §1.7 (Async Collection) |
| Processing progress | `get_processing_progress()` | §2 (KB Processing) |
| Source health | `get_source_health()` | §1.4 (Source Handler) |
| KB freshness decay | `calculate_freshness_score()` | operations.md §3 (Knowledge Lifecycle) |
| Delivery SLA compliance | `query_delivery_log()` | delivery.md §4 (Delivery Reliability) |
| LLM cost tracking | `cost_dashboard()` | operations.md §1 (Cost Governance) |
| System diagnostics | `diagnose_system()` | operations.md §4 (Observability) |

### 9.6 B2.6 Report

> **F-expectation:** F69 — Not yet implemented. See `docs/dev/specs/expectations.md` Phase 15.

**B2 generates structured execution reports for B3 (Director).**

| Report Content | Data Source | Format |
|---------------|-------------|--------|
| What was collected (items per domain, dedup stats) | Collection log + G1-G3 gate results | JSON + summary |
| What was delivered (products per B1, channel status) | DeliveryLog (delivery.md §4) | JSON + summary |
| Errors encountered (source failures, gate blocks, delivery failures) | Trace log + audit log | JSON + summary |
| Cost summary (LLM tokens, storage, API calls) | CostLog (operations.md §1) | JSON |
| Anomaly flags (source health degraded, budget threshold breached, cron missed) | Alert rules + health check | JSON + alert |

**Report delivery**: Reports are pushed to B3 via dashboard (see operations.md §7.2) or stored for B3 query.

> **Implementation gap**: No structured reporting mechanism exists. B2 can query all the data sources listed above individually, but no consolidated report format or periodic generation exists. This is a gap tracked by F69.
