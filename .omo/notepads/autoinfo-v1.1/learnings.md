# Learnings — autoinfo-v1.1

## 2026-07-21: Init — KB subdirs + interactive wizard

### What was done
- Added `knowledge/00-Inbox`, `knowledge/02-Draft`, `knowledge/03-Wiki` to `_REQUIRED_SUBDIRS`
- Extracted `_run_init()` shared helper from init() body (avoids code duplication between `--demo` and `--interactive` paths)
- Added `--interactive`/`-i` flag (default `True`) with wizard: domain selection by number, LLM provider prompt, optional API key
- Existing `--demo` behavior unchanged (takes precedence over interactive)
- Interactive flow: `autoinfo init` now starts the wizard; `autoinfo init --no-interactive` lists domains (old behavior)

## 2026-07-21: G5 Translation Accuracy quality gate

### What was done
- Implemented `G5TranslationAccuracy` class in `src/autoinfo/quality.py` (pattern-matching `G4FactualConsistency` exactly)
- Added `--check-translation` flag to `autoinfo process` CLI
- Added `check_translation: bool = False` parameter to `run_processing()` in `src/autoinfo/process.py`
- G5 reads translation from `extraction.custom_fields["translation"]`; skips trivially if not present
- Created `tests/test_quality_g5.py` with unit tests (faithful/unfaithful/malformed/empty/unavailable LLM) and pipeline integration tests
- Added CLI tests in `tests/test_process.py` for `--check-translation` flag

### Key decisions
- G5 follows exact same pattern as G4 (SYSTEM_PROMPT, `__init__(model)`, `check(item, extraction) -> QualityResult`, `_get_litellm()`)
- Translation is read from `extraction.custom_fields["translation"]` — same pattern as G4 reading `extraction.tl_dr`
- G5 is optional/advisory like G4 — never blocks items
- `check_translation` flag wired as independent parameter (not through run_quality_gates context), same as `check_factual`

### Test pattern
- G5 unit tests mock `_get_litellm()` to return controlled responses, same as G4 tests
- Pipeline integration tests mock `G5TranslationAccuracy` class and verify it's called / skipped / failure-handled correctly

## 2026-07-21: Init — KB subdirs + interactive wizard

### What was done
- Added `knowledge/00-Inbox`, `knowledge/02-Draft`, `knowledge/03-Wiki` to `_REQUIRED_SUBDIRS`
- Extracted `_run_init()` shared helper from init() body (avoids code duplication between `--demo` and `--interactive` paths)
- Added `--interactive`/`-i` flag (default `True`) with wizard: domain selection by number, LLM provider prompt, optional API key
- Existing `--demo` behavior unchanged (takes precedence over interactive)
- Interactive flow: `autoinfo init` now starts the wizard; `autoinfo init --no-interactive` lists domains (old behavior)

### Key decisions
- `--interactive` defaults to `True` so `autoinfo init` (no flags) enters the wizard — simpler UX
- `os.environ["AUTOINFO_LLM_API_KEY"]` set in-process only; no config file write for the key
- `_run_init()` contains the shared init logic; `init()` handles CLI concerns (parsing, validation, prompting)
- Interactive wizard uses `typer.prompt()` — works with CliRunner's `input=` parameter for tests

### Test pattern
- Init dir-creation test patches `Path.cwd` with `tmp_path`, then asserts all `_REQUIRED_SUBDIRS` dirs exist
- Interactive test passes `input="1\nopenrouter\nsk-test-123\n"` to CliRunner to simulate user typing

## 2026-07-21: Expand KB frontmatter fields — author, source_ids, status, related_concepts, linked_entries

### What was done
- Added 5 new optional fields to `KBEntry` dataclass in `models.py`: `author: str = ""`, `source_ids: list[str] = field(default_factory=list)`, `status: str = "active"`, `related_concepts: list[str] = field(default_factory=list)`, `linked_entries: list[str] = field(default_factory=list)`
- Expanded `_build_frontmatter()` in `kb.py` to include these fields in YAML frontmatter **only for Draft+ tiers** (01-Raw stays unchanged for backwards compatibility)
- Updated `create_kb_draft()` to populate `source_ids` from the `raw_ids` parameter and set `status="active"`
- Added `custom_fields` TEXT column to SQLite `entries` table (safe ALTER TABLE migration, same pattern as `importance`)
- Updated `SQLiteIndex.index_entry()` to serialize the 5 fields into `custom_fields` JSON column
- Updated `promote_kb_draft()` and `reject_kb_draft()` to carry forward fields via `custom_fields` JSON from the draft entry
- Updated `reindex_knowledge_base()` to parse expanded fields from frontmatter (with safe defaults if absent)
- Wrote 6 tests: frontmatter YAML has all new fields, SQLite custom_fields storage, 01-Raw excludes fields, survive promotion, backwards compatibility with legacy entries, survive reject

### Key decisions
- Fields stored in `custom_fields` JSON column in SQLite (no schema migration for individual columns — single TEXT column with safe ALTER TABLE)
- Frontmatter tier guard (`if entry.tier != "01-Raw"`) ensures 01-Raw files remain lean and backwards-compatible
- `reject_kb_draft()` modifies existing frontmatter in-place (no rebuild via `_build_frontmatter()`), so expanded fields persist in the file even after demotion to 01-Raw — this is intentional
- Backwards compatibility: all `.get()` calls use empty/false defaults; `custom_fields` column missing or `'{}'` treated as empty

### Test pattern
- Create Draft via `create_kb_draft()`, parse YAML frontmatter, assert all 5 keys present with correct defaults
- Direct SQLite INSERT without `custom_fields` column to simulate legacy entries, then verify `load` works via `KBEntry(**filtered_dict)` with filtered SQLite meta dict

## 2026-07-21: Language auto-detection for Item.language

### What was done
- Added `langdetect>=1.0.9` dependency to `pyproject.toml` (pure Python, ~50KB, no ML models)
- Changed `Item.language` default from `"en"` to `""` in `models.py` (auto-detect replaces hardcoded default)
- Changed `KBEntry.language` default from `"en"` to `""` for consistency
- Implemented `detect_language(text: str) -> str` in `process.py`:
  - Uses `langdetect.detect_langs()` for confidence-aware detection
  - Returns `"unknown"` for text < 20 chars, confidence < 0.8, or `LangDetectException`
  - Graceful `ImportError` fallback returns `"unknown"` when not installed
- Wired `detect_language()` into `run_processing()` — called before `store_entry()`, sets `item.language`
- Added `language` TEXT column to SQLite `entries` table (safe ALTER TABLE migration)
- Updated `SQLiteIndex.index_entry()` to persist `language` in SQLite
- Updated `create_kb_draft()`, `promote_kb_draft()`, `reject_kb_draft()` to carry forward `language`
- Updated `reindex_knowledge_base()` to parse `language` from frontmatter
- `_build_frontmatter()` already included `language: entry.language` — no change needed

### Key decisions
- Used `detect_langs()` (not `detect()`) to access confidence scores — low-confidence results return `"unknown"`
- Language detection is NON-BLOCKING — failures produce `"unknown"`, never raise exceptions
- `langdetect` import is inside the function body — `ImportError` caught gracefully, no hard dependency
- Language stored both in YAML frontmatter and SQLite `language` column for fast filtering
- Carried forward through all KB pipeline transitions (Raw → Draft → Wiki)

### Test pattern
- Mock `detect_langs()` to return controlled `Language` objects (`.lang`, `.prob`)
- Short text test (< 20 chars) reaches `"unknown"` without even calling `detect_langs`
- Chinese test accepts both `"zh-cn"` and `"zh"` (langdetect may return either)

## 2026-07-21: --all / -A flag for `autoinfo collect`

### What was done
- Added `--all` / `-A` flag to `autoinfo collect` command in `cli/collect.py`
- When `--all` is True: iterates all active domains from config, calls `run_collection()` for each
- When `--all` is True AND `--domain` is provided: raises error "Cannot use --all with --domain"
- When neither `--all` nor `--domain` provided: raises error asking user to provide one
- `--topic`, `--limit`, `--source`, `--dry-run`, `--auto-process`, `--json` all work with `--all`
- Results aggregated into a summary dict with `total_domains`, `total_found`, `total_new`, `total_duration_s`
- Existing single-domain `--domain` behavior completely unchanged

## 2026-07-21: MCP tools batch — collection progress, domain lifecycle, keywords, tutorial/presentation, test_source enhancements

### What was done
- Added module-level `_collection_state` in-memory dict tracking active collection runs keyed by domain
- Added `_handle_get_collection_progress(domain)` — returns current state for domain or all domains (running/completed/idle with progress_pct, items_collected, errors)
- Added `_handle_get_collection_status(domain)` — returns last collection results with duration_s, items_per_source, error_count
- Updated `_handle_collect_sources()` to write start/completion state to `_collection_state`
- Added `_handle_activate_domain(name)` / `_handle_deactivate_domain(name)` — toggles `domain.active`, saves config
- Added `_handle_get_domain_config(name)` — returns full domain config (sources, topics, extract_fields, search_mode)
- Added `_handle_list_keywords(domain, topic=None)` — returns keywords with topic grouping, multi-language support, scoring info
- Added `_handle_generate_tutorial(domain, topic, format)` — thin wrapper around `autoinfo.output.generate_tutorial`
- Added `_handle_generate_presentation(domain, topic, slides)` — thin wrapper around `autoinfo.output.generate_presentation`
- Updated `_handle_test_source()` to return `suggested_extract_fields` (pubmed → pmid/doi/authors/journal, rss → title/pub_date/description, web → description/author/published_date, default → title/description)
- Updated `_handle_add_source()` to add quality warning when tier >= 3 (both creation and dedup paths)
- Added `_suggest_extract_fields(source_type)` helper
- Added `group: str = ""` and `relevance_threshold: int = 30` fields to `TopicConfig` dataclass in config.py
- Updated `_dict_to_config` and both `config_to_dict` functions to parse/serialize the new fields
- Updated `G3RelevanceScoring.check()` to accept `list[str] | dict[str, list[str]]` for multi-language keywords (dict flattens all language keyword lists into one flat list for matching)
- Added `autoinfo topics keywords --domain X --topic Y` CLI subcommand
- Registered 8 new MCP tools in `list_tools()` and `call_tool()` dispatch

### Key decisions
- `_collection_state` is in-memory only (not persisted) per v1.1 design
- Multi-language keywords: dict `{"en": ["IVF"], "zh": ["试管婴儿"]}` is flattened to a single keyword list for lexical matching — no language-specific scoring
- Backwards compatibility: `list[str]` keywords still work — `isinstance` check in `G3RelevanceScoring`
- `generate_tutorial`/`generate_presentation` are thin wrappers only — no reimplementation
- Quality tier warning is advisory only — does NOT block tier 3+ source creation
- Dedup quality warning: the idempotency return path also checks quality_tier >= 3
- `config_to_dict` has a bug with duplicate function definitions — second definition shadows the first. Both were updated for safety.

### Test pattern
- Collection progress: Set `_collection_state` dict directly, assert handler returns correct shape
- Domain lifecycle: Write temp config, patch `_config_path`, call handler, verify response
- List keywords: Write temp config with group and relevance_threshold, verify returned data
- Tutorial/Presentation: Mock `autoinfo.output.generate_*`, verify wrapper passes correct params
- Test source: Mock `httpx.get`/`httpx.head`, verify `suggested_extract_fields` by source type
- Quality warning: Pre-populate config with tier 4 source, add_source dedup triggers warning
- G3 multi-language: Mock Item with Chinese text, pass `dict[str, list[str]]` keywords, assert matches from both languages

### Key decisions
- `--domain` changed from required (`...`) to optional (`None`) default to allow `--all` without `--domain`
- Validation is explicit: must provide exactly one of `--domain` or `--all`
- Config loading for domain list happens inside the `--all` branch using `get_config_path()` + `load_config()` — same pattern as `run_collection()` internals
- Auto-process runs per-domain when `--auto-process` is combined with `--all`

### Test pattern
- Conflict test: invoke CLI with both `--all --domain medical-research`, assert exit_code 1 and error message
- Multi-domain test: patch `Path.cwd` + write temp config with 2 active domains, mock `run_collection` side_effect returns domain-specific results, assert call_count=2 and correct params passed

## 2026-07-21: Add 7 curated demo sources to 3 demo domains

### What was done
- **medical-research**: Added arXiv (RSS, bio feed), CrossRef (API, works endpoint), Unpaywall (API, v2 endpoint) — all quality_tier 2, api_key_optional where applicable
- **ai-commercial**: Added Crunchbase (RSS news feed), LMSYS (RSS lmarena.ai feed) — both quality_tier 2
- **language-learning**: Added news-in-levels (RSS), commonlit (RSS blog feed) — both quality_tier 2
- All existing sources preserved unchanged in each file
- Wrote `tests/test_demo_sources.py` — parametrized tests covering: old sources preserved, new sources added, required fields present, total source count per domain (12 tests total)

### Key decisions
- No changes to source handler implementations — all new sources use existing RSS (`type: rss`) or API (`type: api`) handlers
- Sources that typically require API keys (CrossRef, Unpaywall) have `api_key_optional: true` — collection won't fail without a key
- RSS sources use `enabled: true` field instead of `frequency`/`access` — the newer pattern from ai-commercial and language-learning configs

### Test pattern
- `test_demo_sources.py` uses `yaml.safe_load` to load each domain's `sources.yaml` directly (no mocking needed — pure config validation)
- Parametrized at class level with `(domain, old, new)` tuples — each test method runs 3 times (once per domain)
- Tests are fast (~0.5s) and need no fixtures beyond the YAML file on disk

## 2026-07-21: Knowledge graph export CLI command

### What was done
- Added `list_entities(domain)` and `list_relations(domain)` to `SQLiteIndex` — return all entities/relations optionally filtered by domain (for full KG dump, not search-based like `query_knowledge_graph`)
- Added `export_knowledge_graph(domain)` to `KBStore` — orchestrates entity/relation listing, returns `{domain, exported_at, entities, relations}`
- Created `src/autoinfo/cli/knowledge.py` — new CLI module with 3-level nesting: `autoinfo knowledge graph export`
  - `knowledge_app` registered at top level as `knowledge`
  - `graph_app` nested under `knowledge` as `graph`
  - `export` command under `graph`
- Supports 3 export formats: `json` (default), `graphml` (basic XML with nodes/edges), `csv` (2 files: entities.csv + relations.csv)
- `--domain` is required, `--format` defaults to `json`, `--output` defaults to `knowledge_graph_export.<format>`
- GraphML uses `xml.etree.ElementTree` from stdlib (no extra dependency)
- CSV writes two files with `_entities.csv` and `_relations.csv` suffixes on the output stem
- Wrote 15 tests: 6 for KBStore export, 9 for CLI (help discovery, JSON export file structure, domain filter isolation, GraphML XML validity, CSV 2-file output, invalid format error)

### Key decisions
- `list_entities()` does a simple `SELECT ... FROM entities WHERE domain = ?` — no entity search, no pagination (assumes reasonable KG size for v1.1)
- `list_relations()` JOINs entities table to resolve `entity_a`/`entity_b` IDs to names — exported relations include `entity_a_name`/`entity_b_name`
- GraphML uses `xml.etree.ElementTree` (stdlib) over `lxml` to avoid a new dependency
- CSV format produces 2 files (entities + relations) rather than a single merged CSV — cleaner schema per file
- CLI uses existing typer patterns consistently: `typer.Option(..., "--flag", help="...")`, `typer.echo`, `typer.Exit(code=1)` on errors
- Registered via `app.add_typer(knowledge.knowledge_app, name="knowledge")` in `cli/__init__.py`

### Test pattern
- KBStore unit tests: create a `KBStore` with `tmp_path`, call `store.store_entities()` for multiple domains, then `export_knowledge_graph()` and assert structure/content/filtering
- CLI tests: use `CliRunner` with `os.chdir(tmp_path)` since `KBStore()` uses `Path("knowledge")` by default and writes to CWD; `json.loads` the output file and verify structure
- Domain filter test: seed 2 domains with distinct entities, export with `--domain domain-a`, verify only domain-a entities in output

## 2026-07-21: Webhook source handler (push-based ingestion)

### What was done
- Created `src/autoinfo/collectors/webhook.py` — `WebhookHandler` class with `handle(payload, config=None) -> Item`
- Validates 3 required fields (`title`, `content`, `source_url`) — raises `ValueError` if missing
- Optional HMAC-SHA256 signature verification (`secret` in config, `signature` in payload or config)
  - Supports both raw hex and `sha256=` prefixed signatures (GitHub webhook format)
  - Uses `hmac.compare_digest()` for timing-safe comparison
- Optional in-memory sliding-window rate limiting (`max_requests_per_minute` in config)
  - Stored per-handler-instance in `_request_timestamps: deque[float]`
  - Window is 60 seconds, prunes expired timestamps on each call
- Registered `WebhookHandler` in `collectors/__init__.py` exports
- Added `webhook` source type dispatch in `collect.py`:
  - `_build_handler()` returns `WebhookHandler` for `stype == "webhook"`
  - `_fetch_items()` detects push-based handlers (has `handle` but no `fetch`) and returns `[]` with an info log
- No `SourceConfig` schema changes needed (`type` is already a free string field)
- Created `tests/test_webhook_handler.py` with 18 tests across 4 test classes

### Key decisions
- No external dependencies — stdlib only (`hashlib`, `hmac`, `json`, `collections.deque`, `time`)
- `handle()` method signature follows a push-based pattern (payload dict in, Item out), distinct from the pull-based `fetch(url)` pattern used by RSS/Web handlers
- HMAC serialises the payload with `json.dumps(payload, sort_keys=True, separators=(",", ":"))` — sorted keys ensure deterministic signing regardless of Python dict ordering
- Signature can come from either `payload["signature"]` or `config["signature"]`, matching real-world usage where webhook middleware may parse the `X-Hub-Signature-256` header and pass it through config
- Rate limiting is per-handler-instance (not global) — each source config gets its own counter
- `_fetch_items` uses duck typing (`hasattr(handler, "handle") and not hasattr(handler, "fetch")`) rather than an explicit import, avoiding potential circular dependencies

### Test pattern
- Direct unit tests (no VCR, no network, no mocking needed — pure computation)
- HMAC tests build signatures with the same algorithm used in production (`hmac.new(secret, body, hashlib.sha256).hexdigest()`)
- Tampered payload test: sign original, modify payload, verify HMAC rejects
- `sha256=` prefix test: ensures `removeprefix` handles GitHub-style webhook headers
- Rate limit test clears `_request_timestamps` directly to simulate window expiry (fast, no `time.sleep`)

## 2026-07-21: Email (IMAP) source handler

### What was done
- Created `src/autoinfo/collectors/email_imap.py` — `EmailHandler` class with `collect(config: dict) -> list[Item]` using stdlib `imaplib.IMAP4_SSL`
- Config fields: `host` (required), `port` (default 993), `username` (required), `password` (required), `mailbox` (default "INBOX"), `since_date` (optional ISO date)
- Fetches UNSEEN emails; extracts subject → title, body (text/plain preferred over text/html) → content, from → source_platform ("email:<address>")
- Body extraction walks multipart messages, skips attachments (detected via Content-Disposition), strips HTML tags with regex
- RFC 2047 header decoding via `email.header.decode_header`
- IMAP date format: user provides ISO `YYYY-MM-DD` for `since_date`, handler converts to IMAP `DD-Mon-YYYY` format
- Item ID: `sha256(host:mailbox:uid)[:16]` — deterministic per message
- Extended `SourceConfig` with `settings: dict[str, Any]` field to carry extra config (host, port, username, mailbox) through YAML roundtrip
- Updated `_dict_to_config` to capture non-core source keys into `settings`
- Updated both `config_to_dict` functions to spread `settings` back into source dicts
- Registered `EmailHandler` in `_build_handler()` for `stype in ("email", "email_imap")`
- Added `collect()` dispatch in `_fetch_items()` — constructs config dict from `source_config.settings` + `AUTOINFO_EMAIL_PASSWORD` env var fallback
- Created `tests/test_email_imap_handler.py` with 20 tests across 6 test classes

### Key decisions
- stdlib only (`imaplib`, `email` modules) — no external dependencies
- `collect(config: dict)` method signature differs from `fetch(url)` used by RSS/Web — a dict is necessary because IMAP needs multiple connection parameters (host, port, credentials, mailbox)
- Password resolved in this priority: `settings["password"]` (from YAML, may contain `${VAR}` resolved at load time) → `AUTOINFO_EMAIL_PASSWORD` env var
- `host` can come from either `source_config.url` (convention for YAML simplicity) or `settings["host"]` (explicit field)
- `_fetch_items` checks `hasattr(handler, "collect")` to dispatch to email handler, following same duck-typing pattern used for webhook (`handle`) and RSS (`fetch`)
- HTML stripping is simple regex-based (no external HTML parser) — sufficient for email body extraction where we want plain text
- Graceful degradation: connection failure, login failure, mailbox select failure, individual message parse errors all return empty list / skip message — never raises

### Test pattern
- Mock `imaplib.IMAP4_SSL` with `unittest.mock.patch` — no network calls
- `_make_mock_imap()` helper builds a `MagicMock` with controlled `login`, `select`, `search`, `fetch` responses
- `_build_raw_email()` helper constructs RFC822 messages as bytes
- Config validation tests check each required field independently (host, username, password, empty config)
- Connection failure tests cover: connection refused, auth failure, mailbox not found, timeout
- Email parsing tests cover: single/multiple emails, HTML stripping, from-address extraction, RFC 2047 decoding, deterministic IDs

## 2026-07-21: PDF source handler

### What was done
- Created `src/autoinfo/collectors/pdf.py` — `PDFHandler` class with `extract(source, config)` and `fetch(url)` methods
- Accepts file paths (str/Path) or URLs (http/https); URLs are downloaded via httpx to a temp file before extraction
- Uses PyMuPDF (`import fitz`) for text extraction — all pages joined with newlines → `Item.content`
- Extracts PDF metadata (title, author, subject, keywords) → `Item.raw_data`
- Chunking: PDFs >10 pages split into multiple Items (one per 10-page chunk)
- Title from PDF metadata or filename fallback; chunk titles include page range
- 50MB download cap; `ImportError` when PyMuPDF not installed
- Added `pdf = ["PyMuPDF>=1.23.0"]` optional dependency in `pyproject.toml`
- Registered in `collectors/__init__.py` and `collect.py` dispatch (`_build_handler`)
- 15 tests: text extraction, metadata parsing, URL download + parse (all mocked)

### Key decisions
- Module-level lazy import: `try: import fitz / except ImportError: fitz = None` — allows patching `autoinfo.collectors.pdf.fitz.open` in tests and clear `ImportError` at call time via `_check_deps()`
- `fetch()` delegates to `extract()` for the `collect.py` dispatch pattern (`_fetch_items` uses `hasattr(handler, "fetch")`)
- Chunk ID format: `{base_id}-chunk{idx:03d}` (e.g., `abc123-chunk000`) — deterministic, stable across runs
- Temp file cleanup: `try/finally` with `unlink(missing_ok=True)` ensures no temp file leaks
- Download size check before writing to temp file (avoids filling disk with oversized PDFs)

### Test pattern
- `_build_mock_doc()` helper creates a `MagicMock` Document with configurable `page_count`, `metadata`, and per-page `get_text` return values
- `patch("autoinfo.collectors.pdf.fitz.open")` intercepts the module-level `fitz` — works because fitz is a module attribute, not a local import inside the function
- File-based tests use `tmp_path` to create real empty files (passes `Path.exists()` check) while mocking fitz to avoid needing real PDFs
- URL tests patch both `httpx.get` and `autoinfo.collectors.pdf.fitz.open`
