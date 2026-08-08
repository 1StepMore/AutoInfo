# AutoInfo Agent-Tester Validation Runbook

> **Result-oriented, full-coverage validator guide.** This runbook teaches a
> validating agent (B2 direct user) how to prove **every** AutoInfo feature
> with **real** MCP, CLI, REST, and LLM calls, and how to surface all raw and
> processed data to the human director so the project is demonstrably real and
> on track. This is **not** a subset, **not** a demo, and **not** a starting
> point. It is the complete coverage runbook.

- **Audience:** the agent-tester (validator) that executes this guide end to end.
- **Author:** maintained alongside `docs/dev/validation-scenario-contract.md`
  (authoring) and `docs/dev/launch-validation-framework.md` (grading).
- **Source of truth:** the actual `src/` code. Every tool name, parameter,
  format enum, and count in this document was verified against source on
  2026-08-05. Where this guide differs from earlier drafts, the source value
  wins and the correction is noted inline.

---

## 1. Purpose, Scope, Definitions

### 1.1 Purpose

Prove, with real calls and real artifacts, that AutoInfo works across its full
surface: **141 MCP tools (35 categories), 28 CLI command groups, 8 REST
endpoints, 13 delivery channels, 30 collector handlers, and every output
format**. Each proof must leave a verifiable artifact on disk, in the SQLite
store, in the audit log, or on a network sink, and that artifact must be shown
to the director.

### 1.2 Scope

Full coverage in nine phases:

| Phase | Area | Rows |
|-------|------|------|
| A | System / config / discovery / error envelope | A1-A4 |
| B | Domain / source / topic / keyword / webhooks | B1-B7 |
| C | Collection pipeline, dedup, cache | C1-C3 |
| D | Processing, LLM extraction, quality gates | D1-D4 |
| E | KB pipeline, lifecycle, graph, search, Q&A | E1-E8 |
| F | Output generation, all formats, schema validation | F1-F9 |
| G | Delivery, scheduling, cron, agent callbacks | G1-G5 |
| H | End-user lifecycle, cost, billing, privacy | H1-H5 |
| I | Governance, observability, REST, validation meta | I1-I6 |

Every row in §4 must be executed. There is no optional row.

### 1.3 Definitions

| Term | Meaning |
|------|---------|
| **Validator** | The executing agent (B2 direct user). Runs every real call, collects every artifact, quotes real data. |
| **Director** | The human (B3 director user) who owns the API keys, reviews evidence, and decides. The validator reports to the director. |
| **Real call** | A genuine network request, LLM inference, subprocess, HTTP request, or database read/write against the live system. Never a mock, fixture, or stubbed response. |
| **Local sink** | A locally hosted capture endpoint (HTTP server, SMTP sink, stripe-mock) that records real network transactions. A local sink is a **real network transaction** with a labeled local destination; it is acceptable evidence, but it must be labeled as a sink in the evidence. |
| **RED** | The honest negative state recorded *before* a fix or configuration: the call fails, the scenario reports `unconfigured`, or the artifact is absent. Recorded first, never skipped. |
| **GREEN** | The verified positive state: the real call succeeds **and** the expected artifact exists on disk / in the DB / in a log / on the sink. GREEN is only GREEN when both conditions hold. |
| **Artifact-to-show** | The concrete file, table row, log line, or captured payload that proves the feature. |
| **unconfigured** | A scenario or tool that could not run because a required key is missing. `unconfigured` is a recorded known-limit. It is **never** a pass. |

---

## 2. Operating Context and the Evidence Contract

### 2.1 The gap this runbook fills

Two validation documents already exist, and neither is a result-oriented
runbook:

| Document | Covers | Gap |
|----------|--------|-----|
| `docs/dev/validation-scenario-contract.md` | How to **author** YAML scenarios (schema, semantics, `requires_env`, `cleanup_steps`) | No end-to-end runbook telling a validator what to call, what to expect, and what to show |
| `docs/dev/launch-validation-framework.md` | How to **grade** a launch (D1-D5 dimensions, SUSPECT table, evidence catalog) | Assumes evidence exists; does not step the validator through producing it feature by feature |

This runbook fills the middle: **the end-user-oriented, full-coverage,
real-call execution guide** that turns "the system has features" into
"every feature has a real, shown artifact".

Supporting references used throughout:

- `AGENTS.md` (project root): operating model, tool catalog, architecture rules
- `README.md`: feature inventory, status table, quantitative baselines
- `docs/dev/required-api-keys.md`: every environment variable, per source and channel
- `docs/dev/mcp-usage-examples.md`: worked MCP workflows
- `docs/dev/validation-scenario-contract.md`: scenario authoring contract
- `docs/dev/launch-validation-framework.md`: D1-D5 grading template
- `docs/dev/cross-dimensional-catalog.md`: keystone product matrix (A1-A7 × B1/B2/B3)
- `docs/dev/enduser-coverage-matrix.md`: end-user feature coverage
- `docs/dev/specs/*.md`: extracted specs (pipeline, delivery, quality-gates, operations, mcp-tools)

### 2.2 The Evidence Contract

Every feature row in §4 is executed against a fixed five-part contract:

```
(surface, real call, expect, actual, artifact-to-show)
```

| Part | Meaning | Rule |
|------|---------|------|
| **surface** | MCP tool, CLI command, or REST endpoint | The call is made through the real surface, never around it |
| **real call** | The exact command / tool invocation | Executed for real; no mocks |
| **expect** | What a correct system returns | Derived from source and documented behavior |
| **actual** | What the system actually returned | Recorded verbatim, even when it differs from expect |
| **artifact-to-show** | The file / DB row / log line / payload that proves it | Must exist on disk / DB / log / sink **and** be surfaced to the director (§7) |

**GREEN requires both halves:**

1. The real call succeeded with the expected shape.
2. The artifact exists **and** was shown (pasted, quoted, or pointed to by
   absolute path) to the director.

A call that succeeds but whose artifact is never surfaced is NOT GREEN.

### 2.3 Baseline honesty rule

Before any key is configured, the system has a known, expected profile. Record
it first:

```
No-keys baseline (expected, 2026-08-05):
  47 scenarios, 225 steps
  37 passed / 0 failed / 10 unconfigured
  env-gated: 9 scenarios need AUTOINFO_LLM_API_KEY
             1 scenario needs FRED_API_KEY + FINNHUB_API_KEY
```

An `unconfigured` result with no key is the honest state. It is recorded, then
re-run after the key is configured. A scenario that reports `unconfigured`
**is never a pass**, and a validator must never skip it, fake it, or grade it
GREEN. This mirrors the grading legend in
`docs/dev/launch-validation-framework.md` §0.

---

## 3. Bootstrap for Real Calls

### 3.1 BYOK LLM setup

The only hard requirement for the LLM-dependent surface is one key. Full
catalog: `docs/dev/required-api-keys.md`.

```bash
# 1. Export the key in the shell that spawns the MCP server / CLI.
export AUTOINFO_LLM_API_KEY="sk-..."

# 2. Record it in config via the MCP tool (stores an env-var REFERENCE
#    ${AUTOINFO_LLM_API_KEY}, never the raw key).
#    MCP: configure_llm(provider="openai", model="<model>",
#                       api_key="${AUTOINFO_LLM_API_KEY}", base_url="<optional>")

# 3. Confirm the effective config:
#    MCP: get_effective_llm_config()
#    CLI: autoinfo doctor --verbose   (reports llm.provider / llm.model)
```

Precedence (highest to lowest): MCP tool parameter > `.autoinfo/config.yaml`
`llm.*` > `AUTOINFO_LLM_API_KEY` env var > defaults (openrouter /
deepseek/deepseek-chat). See `AGENTS.md` "LLM Configuration".

### 3.2 Collector bootstrap matrix

Two tiers. The authoritative map is `SOURCE_KEY_ENV_VARS` in
`src/autoinfo/config.py` (lines 70-82) plus `requires_key()` in the collector
handlers. **21 keyless collectors** (no credential required; optional keys only
raise rate limits), **9 key-gated groups** (real fetch is blocked without the
credential).

| Collector (handler file) | source_type | Key env var | Gated? |
|--------------------------|-------------|-------------|:---:|
| `rss.py` | rss | none | keyless |
| `web.py` | web | none | keyless |
| `web_playwright.py` | web (playwright) | none | keyless |
| `webhook.py` | webhook | none (HMAC secret optional via settings) | keyless |
| `pdf.py` | pdf | none | keyless |
| `dblp.py` | dblp | none | keyless |
| `openalex.py` | openalex | none | keyless |
| `pubmed.py` | api (PubMed) | `AUTOINFO_PUBMED_API_KEY` optional (rate limit only) | keyless |
| `semantic_scholar.py` | api (S2) | `AUTOINFO_S2_API_KEY` optional (rate limit only) | keyless |
| `uspto.py` | api (PatentsView) | `AUTOINFO_USPTO_API_KEY` optional (rate limit only) | keyless |
| `http_api.py` | api (generic) | `AUTOINFO_HTTP_API_KEY` optional (settings can supply) | keyless |
| `hackernews.py` | hackernews | none | keyless |
| `gdelt.py` | gdelt | none | keyless |
| `ssrn.py` | ssrn | none | keyless |
| `sec_edgar.py` | sec_edgar | none | keyless |
| `akshare.py` | akshare | none | keyless |
| `bilibili.py` | bilibili | none | keyless |
| `apple_podcasts.py` | apple_podcasts | none (`requires_key()` returns False) | keyless |
| `yahoo_finance.py` | yahoo_finance | none | keyless |
| `edx_sitemap.py` | edx_sitemap | none | keyless |
| `huggingface.py` | huggingface | none for the HF provider (`requires_key()` returns False); the kaggle provider is gated | keyless |
| `nyt.py` | nyt | `AUTOINFO_NYT_API_KEY` | **key-gated** |
| `ap_api.py` | ap_api | `AUTOINFO_AP_API_KEY` (`requires_key()` True) | **key-gated** |
| `reuters_mcp.py` | reuters_mcp | `AUTOINFO_REUTERS_API_KEY` (`requires_key()` True) | **key-gated** |
| `unpaywall.py` | unpaywall | `AUTOINFO_UNPAYWALL_EMAIL` (`requires_key()` True) | **key-gated** |
| `core.py` (via unpaywall handler) | core | `AUTOINFO_CORE_API_KEY` | **key-gated** |
| `youtube.py` | youtube | `AUTOINFO_YOUTUBE_API_KEY` (`requires_key()` True) | **key-gated** |
| `spotify.py` | spotify | `AUTOINFO_SPOTIFY_CLIENT_ID` + `AUTOINFO_SPOTIFY_CLIENT_SECRET` | **key-gated** |
| `quandl.py` | quandl | `AUTOINFO_QUANDL_API_KEY` | **key-gated** |
| `huggingface.py` (kaggle provider) | kaggle | `KAGGLE_USERNAME` + `KAGGLE_KEY` | **key-gated** |
| `email_imap.py` | email / email_imap | `AUTOINFO_EMAIL_PASSWORD` (or `email.password` in config) | **key-gated** |

**Corrections against earlier drafts (source of truth = `config.py`
`SOURCE_KEY_ENV_VARS`, `src/autoinfo/collectors/*.py`):**

- `email` is an **alias** for the `email_imap` handler. Both share
  `AUTOINFO_EMAIL_PASSWORD` and both appear in `VALID_SOURCE_TYPES`.
- The "9 key-gated groups" merges `unpaywall` + `core` (they share one handler
  file) and `email` + `email_imap` (alias). The config map lists **10 distinct
  key-gated source types**: ap_api, nyt, quandl, reuters_mcp, unpaywall, core,
  youtube, spotify, kaggle, email_imap.
- `pubmed`, `semantic_scholar`, `uspto`, and generic `http_api` keys are
  **optional / rate-limit only**. Do **not** gate on them. The collectors work
  keyless (PubMed 3 req/s vs 10 req/s with key).
- `requires_key()` returns True only for ap_api, reuters_mcp, unpaywall,
  youtube. The other gated types (nyt, spotify, quandl, kaggle, core,
  email_imap) enforce at collect time via their env-var guard, not via
  `requires_key()`. Use `SOURCE_KEY_ENV_VARS` as the single gating map.
- `reddit` is a valid source type and is keyless (the `reddit.py` handler reads
  no credential env vars).

---

## 4. Full-Coverage Validation Matrix

The keystone. Nine phases, one table per phase. Columns:

```
# | Feature | Real-call method | Artifact to show director | LLM key | Scenario(s)
```

Legend for **LLM key**: `no` = callable without a key; `yes` = needs a real
LLM call; `LLM-not-configured` = the tool returns `LLM_NOT_CONFIGURED` until
the key is set (this is itself a proof, see A4).

Legend for **Scenario(s)**: the `src/autoinfo/mcp/scenarios/` file(s) that
exercise the same feature (see Appendix A). `run_validation_scenario` executes
them; the matrix row additionally requires the real call and the artifact.

### Phase A: System, Config, Discovery, Error Envelope

| # | Feature | Real-call method | Artifact to show director | LLM key | Scenario(s) |
|---|---------|------------------|---------------------------|:---:|-------------|
| A1 | System health + phase | MCP `diagnose_system()` **and** CLI `autoinfo doctor --verbose` | The JSON with `health_score` (0-100) + `phase` (`uninitialized` / `llm_unconfigured` / `no_sources` / `ready_to_collect` / `operational`) | no | system-health |
| A2 | BYOK LLM config | MCP `configure_llm(provider, model, api_key, base_url)` then read `.autoinfo/config.yaml` `llm:` block | The config.yaml `llm:` block with the key **redacted as `${AUTOINFO_LLM_API_KEY}`** (never the raw key) | no | projects-config |
| A3 | Discovery inventory | MCP `list_domains()`, `get_domain_schema("<domain>")`, `list_available_models()`, `list_available_platforms()`, `get_tool_count()` (also `get_effective_llm_config()`, `list_output_templates()`) | The JSON responses, including `get_tool_count` returning **141** | no | discovery, output-discovery, system-health, domain-management, error-boundary |
| A4 | Error envelope probe | MCP `run_validation_scenario("error-boundary")` plus a direct probe: call an unknown tool and a missing-domain tool | The `{success:false, error:{code, message, actionable}}` JSON, e.g. `UnknownTool` and `DOMAIN_NOT_FOUND`; also an LLM-required tool (`suggest_keywords`) returning `LLM_NOT_CONFIGURED` while the key is unset | no | error-boundary, llm-gated |

### Phase B: Domain, Source, Topic, Keyword, Webhooks

| # | Feature | Real-call method | Artifact to show director | LLM key | Scenario(s) |
|---|---------|------------------|---------------------------|:---:|-------------|
| B1 | Domain/source/topic CRUD | MCP `add_domain(name, description)`, `add_source(name, url, type, domain, ...)`, `add_topic(domain, name, keywords)`; confirm with `list_sources(domain)` and `list_topics(domain)` | New `domain:` / `source:` / `topic:` blocks in `.autoinfo/config.yaml` plus the list responses | no | domain-management, source-management, topic-management |
| B2 | Keyless collector real fetch | MCP `collect_sources(domain="<d>", topic="<t>", dry_run=false)` against a keyless source (rss, pubmed, hackernews, openalex, dblp, ssrn, sec_edgar, gdelt, etc.) | `collections/<domain>/<source>/*.json` raw cache files with real `source_url`, `source_type`, `source_platform`, plus the collection log line | no | collection, collectors-e2e |
| B3 | Keyed collector with env set | Export the source key (e.g. `AUTOINFO_NYT_API_KEY`), MCP `collect_sources` on that source | `collections/<domain>/<source>/*.json` raw cache from the keyed source | no | sources-a6-keyed |
| B4 | Source reachability + health + rating | MCP `test_source(source_id)`, `get_source_health(source_id)`, `rate_item(item_id, rating)` | The reachability JSON (status/items/error) for each source; rating persisted (visible in later search/ranking output) | no | source-management, collectors-e2e |
| B5 | LLM keyword suggestions | MCP `suggest_keywords(domain, topic, ...)` (real LLM) then `approve_keyword(domain, keyword)` / `reject_keyword(...)`, confirm `list_keywords(domain)` | The suggested-keyword JSON (LLM output) and the updated keyword list showing approve/reject took effect | yes | llm-gated, keyword-management |
| B6 | Topic grouping | MCP `topic_group_add(domain, group_name, topics)` then `list_topics(domain)` | JSON showing the new group and its members | no | topic-management |
| B7 | Domain webhook push | MCP `set_domain_webhooks(domain, webhook_urls=["http://127.0.0.1:8787/hook"])`; run a **local HTTP sink** (e.g. `python -m http.server`-style capture or a small listener) and `collect_sources` | The sink-captured POST body: per-item JSON with source provenance, delivered to the local sink | no | webhooks-alerts |

### Phase C: Collection Pipeline, Dedup, Cache

| # | Feature | Real-call method | Artifact to show director | LLM key | Scenario(s) |
|---|---------|------------------|---------------------------|:---:|-------------|
| C1 | Collection preview + progress + stats | MCP `collect_sources(domain, dry_run=true)` (preview, no writes) then a real run; poll `get_collection_progress(job_id)`; then `get_collection_stats(period)` and `get_collection_diff()` | The dry-run preview JSON, the real-run job JSON, progress updates, and the stats/diff JSON with item counts | no | collection, collection-monitor |
| C2 | Dedup | `collect_sources` the **same URL twice** (or a second source emitting the same URL) and inspect the collection log | The dedup log line (`duplicate` / `skipped`), proving the second fetch was not stored | no | collection, collectors-e2e |
| C3 | Cache cleanup | MCP `clean_cache()` (also `autoinfo clean` CLI) | The cleanup result JSON and a directory listing showing the temp/cache dir emptied | no | collection, projects-config |

### Phase D: Processing, LLM Extraction, Quality Gates

| # | Feature | Real-call method | Artifact to show director | LLM key | Scenario(s) |
|---|---------|------------------|---------------------------|:---:|-------------|
| D1 | Process with extraction | MCP `process_collection(domain, check_factual=true, check_translation=true)` (real LLM), poll `get_processing_progress(job_id)` | `knowledge/<domain>/01-Raw/*.md` files whose frontmatter contains `tl_dr`, `key_points`, `entities`, `summary`, `relevance`, `source_url` | yes | processing, collection |
| D2 | Quality gates G0-G5 + config | MCP `get_gate_config(domain)`, `set_gate_config(domain, gate, action, threshold)` then re-read; inspect processing output for gate outcomes and any `_failed/` item | The gate config JSON before/after, gate outcome lines in the processing log, and any `knowledge/<domain>/_failed/` item (if a gate blocked) | no | quality-gate-config |
| D3 | Custom extraction | MCP `extract_fields(domain, text, fields=[...])` (real LLM) and `get_extraction(entry_id)` | The extracted JSON with the requested fields; the stored extraction for a real entry | yes | kb-extraction, kb-lifecycle |
| D4 | G4 factual + translation QA flags | MCP `process_collection(domain, check_factual=true, check_translation=true)` | Log lines / KB frontmatter showing G4 factual-consistency verification and translation-QA flags on the processed entries | yes | processing, llm-gated |

### Phase E: KB Pipeline, Lifecycle, Graph, Search, Q&A

| # | Feature | Real-call method | Artifact to show director | LLM key | Scenario(s) |
|---|---------|------------------|---------------------------|:---:|-------------|
| E1 | 4-tier pipeline Raw→Draft→Wiki | MCP `list_kb_tier(domain, tier)`; MCP `create_kb_draft(raw_ids=[...], title=..., summary=..., tags=[...])` (Raw→Draft only); human promote via CLI `autoinfo kb promote <draft_id>` | The `knowledge/` tree showing `01-Raw/`, `02-Draft/`, `03-Wiki/` with real entries at each reached tier | no | kb-access, kb-draft |
| E2 | KB import | MCP `import_kb(domain, format, data)` for markdown / pdf / html / json (CLI parity: `autoinfo import-kb --file <f>`) | The new entries landed in `knowledge/<domain>/01-Raw/*.md` with provenance | no | kb-import-export |
| E3 | Versioning | MCP `get_entry_history(entry_id)`, `compare_versions(entry_id, version_a, version_b)`, `restore_entry_version(entry_id, version)` | History/diff JSON showing version deltas, and a restore confirming the content reverted | no | kb-versioning |
| E4 | Knowledge graph | MCP `query_knowledge_graph(domain, entity=...)` and `knowledge_graph_export(domain, format=...)` | The graph query JSON and the exported GraphML file on disk | no | kb-graph |
| E5 | Item relations | MCP `link_items(source_id, target_id, relation)` and `get_item_relations(entry_id)` | The link response and relations JSON | no | kb-graph |
| E6 | Knowledge lifecycle | MCP `mark_stale(entry_id)`, `calculate_freshness_score(domain)`, `get_domain_decay(domain)`, `find_similar_items(entry_id)`, `merge_items(ids, strategy)`, `recommend_content(user_id, ...)`, `simplify_content(content, target_level)` | The staleness/decay JSON, similarity ranking, merge result, recommendation list, and the simplified text (original vs target CEFR) | recommend + simplify: yes; rest: no | kb-lifecycle, output-simplify-recommend |
| E7 | Hybrid/vector/faceted/cross-domain search | MCP `search_knowledge_base(domain, query, mode="hybrid"\|"vector"\|"faceted", filters={...})`; omit `domain` for cross-domain | The ranked JSON results with scores, plus faceted filter counts and cross-domain hits | no | kb-access |
| E8 | Q&A with citations | MCP `query_collected(query)` (real LLM) | The synthesized answer with source citations referencing real 01-Raw entries | yes | kb-extraction |

### Phase F: Output Generation, All Formats, Schema Validation

| # | Feature | Real-call method | Artifact to show director | LLM key | Scenario(s) |
|---|---------|------------------|---------------------------|:---:|-------------|
| F1 | Digest, all 7 formats | MCP `generate_digest(domain, format="markdown"\|"html"\|"json"\|"agent"\|"audio"\|"epub"\|"audiobook")` (7 calls, real LLM) | `outputs/digests/*.md`, `*.html`, `*.json`, agent JSON-LD, MP3, EPUB, audiobook ZIP | yes | output-digest-report, output-ebook |
| F2 | Report, all report types + formats | MCP `generate_report(domain, report_type="industry"\|"competitive"\|"trend"\|"daily-briefing"\|"column"\|"standard", format="markdown"\|"json"\|"html"\|"audio"\|"agent"\|"epub"\|"audiobook")` (7 MCP-valid formats; see Appendix C for the `video` nuance) | `outputs/` report artifacts for each type/format combination exercised | yes | output-digest-report, output-column, output-ebook |
| F3 | Cross-domain report | MCP `generate_cross_domain_report(domains=[...])` | The cross-domain report artifact whose content aggregates multiple domains | yes | output-digest-report |
| F4 | Tutorial | MCP `generate_tutorial(domain, format="markdown"\|"agent")` | `outputs/` tutorial md + agent JSON-LD | yes | output-tutorial-presentation |
| F5 | Presentation | MCP `generate_presentation(domain, format="markdown"\|"html"\|"mkslides"\|"agent")` (4 calls) | `outputs/` presentation md, standalone HTML (Reveal.js CDN), mkslides build, agent JSON-LD | yes | output-tutorial-presentation |
| F6 | Localization | MCP `localize_content(domain, text, target_language)` (real LLM) | The translated text artifact | yes | output-tutorial-presentation |
| F7 | Export, all 12 formats | MCP `export_kb(domain, format="markdown"\|"json"\|"sqlite"\|"csv"\|"pdf"\|"graphml"\|"rss"\|"agent"\|"bundle"\|"sitemap"\|"epub"\|"mobi")` (12 calls; `sitemap` requires `base_url`) | `exports/autoinfo-export-<domain>-<ts>.*` artifacts for every format (bundle = ZIP with PDF+JSON+MD+YAML) | no | kb-import-export |
| F8 | Agent JSON-LD schema validation | Run `jsonschema` against the const-pinned schemas for all 4 agent artifacts: `python3 -m jsonschema -i <digest>.json docs/schemas/knowledge-digest-v1.json` (likewise tutorial / presentation / base-export) | The 4 validated JSON-LD artifacts, each passing its `docs/schemas/*-v1.json` (const-pinned `@context` / `@type`) | no | evidence-only (no dedicated scenario; graded in launch-validation-framework D3) |
| F9 | Audio / audiobook | MCP `generate_digest(domain, format="audio")` and `format="audiobook"` (chaptered MP3 + ZIP with ID3v2.3 CHAP/CTOC) | The MP3 file (playable / size non-zero), the audiobook ZIP, and the chapter metadata | yes | output-ebook |

### Phase G: Delivery, Scheduling, Cron, Agent Callbacks

| # | Feature | Real-call method | Artifact to show director | LLM key | Scenario(s) |
|---|---------|------------------|---------------------------|:---:|-------------|
| G1 | Channel health, 13 channels | MCP `get_channel_health()` | The health JSON covering smtp, webhook, rest_api, file_export, discord, telegram, wechat_work, wechat_oa, dingtalk, feishu, rss, social_publish, push with health + latency | no | delivery-channels |
| G2 | Email digest to local SMTP sink | MCP `email_config(...)` then `generate_digest(domain, format="html")` then `send_email_digest(domain, period)` pointed at a **local SMTP sink**; then MCP `query_delivery_log()` / `get_delivery_log()` | The sink-captured message (headers + html body) and the delivery-log rows for the send | no | delivery-channels |
| G3 | Delivery schedule CRUD | MCP `add_delivery_schedule(domain, cron_expression, output_type, channel, output_format, ...)`, `list_delivery_schedules()`, `remove_delivery_schedule(...)` | The schedule list JSON before/after add and after remove | no | delivery-schedules |
| G4 | Cron schedules + health | MCP `add_schedule(name, cron, command)`, `run_schedules()`, `get_schedule_status()`, `list_schedules()`, `remove_schedule()`; CLI `autoinfo cron install` and `autoinfo cron health` | The schedule status JSON, the heartbeat JSON from `cron health`, and the crontab line (if installed) | no | cron-schedules |
| G5 | Agent push callback | MCP `set_agent_callback(agent_url="http://127.0.0.1:8788/cb", events=[...])`; generate/deliver to trigger; read the callback with a **local HTTP sink** | The sink-captured payload `{event, payload, schema_version: 1, trace_id, product_id}` plus `agent_outbox` rows in `autoinfo.db` | no | agent-callbacks |

### Phase H: End-User Lifecycle, Cost, Billing, Privacy

| # | Feature | Real-call method | Artifact to show director | LLM key | Scenario(s) |
|---|---------|------------------|---------------------------|:---:|-------------|
| H1 | End-user lifecycle | MCP `enduser_create(user_id, name, email, ...)` → `activate_trial(end_user_id, days)` → `get_subscription_status(end_user_id)` → `check_trial_expiry(end_user_id)` → `update_preferences(end_user_id, ...)` / `get_preferences(end_user_id)` → suspend → cancel; CLI `autoinfo enduser list` | The lifecycle JSON at each stage (trial → active → suspended → cancelled) and `get_enduser_history(end_user_id)` | no | enduser-lifecycle, enduser-preferences |
| H2 | End-user delivery | MCP `send_to_enduser(end_user_id, product_id, channel)` then `query_delivery_log(end_user_id)` / `get_delivery_log(end_user_id)` | The delivery-log rows for that end user | no | enduser-lifecycle, delivery-channels |
| H3 | Cost governance | MCP `cost_dashboard(period)`, `cost_allocation(domain)`, `get_billing_summary()`, `get_budget_thresholds()`, `set_budget_thresholds(...)`; then `sqlite3 autoinfo.db "SELECT * FROM cost_log ORDER BY created_at DESC LIMIT 5;"` | The dashboard/allocation JSON and the raw `cost_log` rows (LLM tokens, storage, API calls) | no | cost-budget, products-billing |
| H4 | Checkout (billing) | MCP `create_checkout_session(product_id, end_user_id, mode="subscription"\|"payment", article_id=...)` against **stripe-mock** (`STRIPE_API_BASE` defaults to `http://localhost:12111`, key `sk_test_mock`); label as mock in evidence | The checkout-session JSON returned by stripe-mock | no | products-billing |
| H5 | Data privacy / GDPR | MCP `soft_delete_entry(entry_id, purge=false)` then `restore_entry(entry_id)`; `export_user_data(user_id)` → GDPR export JSON; `delete_user_data(user_id)`; then `soft_delete_entry(entry_id, purge=true)` | The restore confirmation, the GDPR export JSON file, and the purge confirmation; deletion-log / audit rows | no | data-privacy |

### Phase I: Governance, Observability, REST, Validation Meta

| # | Feature | Real-call method | Artifact to show director | LLM key | Scenario(s) |
|---|---------|------------------|---------------------------|:---:|-------------|
| I1 | Audit log | MCP `query_audit_log(actor=..., action=...)` and CLI `autoinfo audit query` | The audit rows (actor / action / tool / resource / trace_id) pulled from `autoinfo.db`, proving dispatch-level audit | no | observability |
| I2 | Per-item trace | MCP `trace_item(trace_id)` and CLI `autoinfo trace <trace_id>` | The full journey for one trace_id: collection → gates → KB → delivery | no | observability |
| I3 | Metrics | MCP `get_metrics()` and `get_prometheus_metrics()`; REST `curl http://localhost:8741/metrics` | The metrics JSON and the Prometheus text exposition from the REST endpoint | no | observability |
| I4 | Alert rules | MCP `add_alert_rule(domain, topic_keywords, relevance_threshold, channel, kind)` → `get_alert_rules()` → trigger a rule → `remove_alert_rule(...)` | The rules YAML file (persisted), the alert list JSON, and the dispatch log line when the rule fired | no | webhooks-alerts |
| I5 | REST API | Start `uvicorn autoinfo.api.server:app --port 8741`; `curl` each endpoint: `GET /health`, `GET /api/v1/entries`, `POST /api/v1/entries`, `GET /api/v1/entries/{id}`, `DELETE /api/v1/entries/{id}`, `GET /api/v1/search`, `GET /dashboard`, `GET /metrics` | The envelope JSON for each endpoint (success + error envelopes) and the dashboard HTML | no | rest-api |
| I6 | Validation meta-coverage | MCP `list_validation_scenarios()`; `run_validation_scenario` for all 47; then `python3 scripts/coverage_audit.py` | The 47-scenario inventory JSON, per-scenario results, and the audit report showing **141/141** covered with zero MISSING | no | meta-validation |

---

## 5. Step-by-Step Walkthrough Template

Run from the project root (`/mnt/d/贯维/AutoInfo`). The venv interpreter is
`.venv/bin/python`; the `autoinfo` console script must be on PATH.

### 5.1 Pre-flight (RED baseline first)

1. **Git cleanliness.** `git status --porcelain` must show no modified source
   files and no runtime artifacts. Runtime dirs (`collections/`, `knowledge/`,
   `outputs/`, `exports/`, `autoinfo.db`, `.autoinfo/`, `logs/`, `.omo/`) are
   gitignored and must **never** be committed. If the tree is dirty, stop and
   report to the director before continuing.
2. **No-keys profile.** With **no** BYOK keys exported, run
   `list_validation_scenarios()` (expect 47) then `run_validation_scenario`
   for all 47. Record the aggregate. Expected: **37 passed / 0 failed / 10
   unconfigured** (see §2.3). This is the RED baseline: honest, recorded,
   never graded as pass.
3. **Configure the key.** `export AUTOINFO_LLM_API_KEY="sk-..."` then MCP
   `configure_llm(...)`. Confirm with `get_effective_llm_config()`.
4. **Re-run the 10 env-gated scenarios to GREEN.** They are: cli-llm,
   kb-extraction, llm-gated, output-column, output-digest-report, output-ebook,
   output-simplify-recommend, output-tutorial-presentation, processing (all
   need `AUTOINFO_LLM_API_KEY`) and sources-a6-keyed (needs `FRED_API_KEY` +
   `FINNHUB_API_KEY`). Each must now report `passed`, not `unconfigured`.
5. **Start the REST server** for http steps: `uvicorn autoinfo.api.server:app
   --port 8741` (needed by the `rest-api` scenario and Phase I).

### 5.2 Per-matrix-row loop

For **every** row in §4 (A1 → I6):

```
RED   → record the honest negative (unconfigured / absent artifact / failing call)
CALL  → make the real call exactly as the row prescribes
GREEN → assert the expected shape AND confirm the artifact exists
SHOW  → surface the artifact to the director (§7); GREEN is not final until shown
CLEAN → run the paired cleanup for every mutating call; verify with list_* + git status
```

Rules inside the loop:

- Execute rows in order A → I where a row depends on earlier state (e.g. D1
  needs C1's collected items; E1 needs D1's processed raws).
- One mutating call, one cleanup. Every `add_*` / `create_*` / `set_*` /
  `soft_delete_entry` has a paired `remove_*` / `delete_*` / `restore_*` /
  `reject_*`, verified by the corresponding `list_*` and a clean
  `git status --porcelain`.
- Prefer idempotent reads for re-verification: `list_*`, `get_*`, `search_*`.
- If a row depends on a key you do not have, record `unconfigured` with the
  env var name, flag it to the director as a BYOK obligation, and move on.
  Never fake the row.

### 5.3 Final sweep

1. Re-run all 47 scenarios with keys configured. All must report `passed`
   (expect 0 failed, 0 unconfigured).
2. Run `python3 scripts/coverage_audit.py`. Report the result: **141/141
   covered, zero MISSING**.
3. Cleanup sweep: re-run every scenario's `cleanup_steps` result (they run
   automatically), remove any leftover test domain/source/topic/end-user, and
   confirm `git status --porcelain` shows only the intended deliverable.
4. Produce the director summary table (§7.3) mapping phase → artifact path →
   verdict, and hand the run report skeleton to the director per
   `docs/dev/launch-validation-framework.md` §6.

---

## 6. Evidence Rules

### 6.1 RED→GREEN discipline

- **Honest negative first.** For every row, the RED state is recorded before
  the GREEN state. A row that jumps straight to GREEN with no recorded negative
  (when a negative existed) is suspect.
- **Never fake-pass.** A call that fails is recorded as failed with the actual
  error. An `unconfigured` result is recorded as `unconfigured`. Neither is
  ever rewritten as a pass.
- **Never silently skip.** Every row in §4 runs. If it cannot run for a missing
  key, that is a recorded `unconfigured` row with the env var named, surfaced
  to the director.
- **unconfigured is not GREEN.** Green requires a real success plus an
  artifact. A row that ends at `unconfigured` is not complete.

### 6.2 Real-surface rule

Evidence is only evidence if it came from a real surface:

| Surface | Acceptable evidence |
|---------|---------------------|
| MCP (stdio) | `{success, data}` envelope JSON from a live tool call |
| CLI | subprocess exit code + stdout/stderr from a real command |
| REST | real HTTP status + body from `uvicorn` on port 8741 |
| LLM | real LiteLLM completion output (extraction, judge, generation) |
| Network | real fetch from a real source; local sinks (HTTP/SMTP/stripe-mock) **labeled as sinks** |
| Storage | actual files under `collections/`, `knowledge/`, `outputs/`, `exports/`; real rows in `autoinfo.db`; real log lines in `logs/` |

Not evidence: unit-test output, mocked stores, seeded fixtures, sample data
copied into runtime paths, or claims without an artifact. This mirrors the
"Real-surface evidence rule" and "No-mock rule" in
`docs/dev/launch-validation-framework.md` §0.

### 6.3 Cleanup rule

- Every mutating call has a paired cleanup call (scenarios already encode this
  via `cleanup_steps`, see `docs/dev/validation-scenario-contract.md`).
- After each phase, verify with the corresponding `list_*` and
  `git status --porcelain` that nothing leaked.
- Never commit runtime artifacts. The validator leaves the working tree as
  clean as it found it, plus the documentation deliverable.

---

## 7. Director Surfacing Protocol

> **UNMISSABLE INSTRUCTION: The validating agent MUST show the director all
> raw data and all processed data. Quote real content, not summaries.**
>
> After every phase, paste to the director: (1) the actual raw JSON from
> `collections/<domain>/<source>/*.json`, (2) the KB markdown file content at
> each tier reached under `knowledge/`, (3) the generated output artifacts
> under `outputs/` and `exports/`, (4) `sqlite3 autoinfo.db` query output for
> the audit, cost, delivery-log, and agent_outbox tables, and (5) the
> email/audio artifacts (sink-captured message body, MP3 file info). The
> director must see the project's real data flowing through the real pipeline.
> A summary of what you did is not evidence; the raw bytes are.

### 7.1 What to show, per artifact class

| Artifact class | Where it lives | Show |
|----------------|----------------|------|
| Raw collection cache | `collections/<domain>/<source>/*.json` | The full JSON of 1-3 items: `source_url`, `source_type`, `source_platform`, title, content excerpt |
| 4-tier KB | `knowledge/<domain>/01-Raw/`, `02-Draft/`, `03-Wiki/` | The frontmatter + body of a real entry per reached tier |
| Generated outputs | `outputs/` (digests, reports, tutorials, presentations), `exports/` (all 12 formats) | File paths, file sizes, first page / head of the artifact, JSON-LD `@type` |
| SQLite evidence | `autoinfo.db` | `sqlite3 autoinfo.db "..."` output for `audit_log`, `cost_log`, `delivery_log`, `agent_outbox`, `kb_entry` (or the real table names) |
| Email / audio artifacts | local SMTP sink capture, `outputs/**/*.mp3`, audiobook ZIP | The captured message headers + body; MP3 size/duration; ZIP contents |
| Network proof | local HTTP sink capture | The received POST/PUT payloads (webhook, agent callback) |

### 7.2 Per-phase "Evidence to show" checklist

| Phase | Minimum evidence shown to director |
|-------|-------------------------------------|
| A | `diagnose_system` JSON (health_score + phase), `get_tool_count` = 141, redacted config llm block, error-envelope JSON |
| B | config.yaml new blocks, `collections/` raw JSON from a real fetch, sink-captured webhook payload |
| C | dry-run vs real collection JSON, dedup log line, stats/diff JSON |
| D | `01-Raw` frontmatter (tl_dr/key_points/entities/summary/relevance/source_url), gate outcomes, extraction JSON |
| E | KB tier tree (01-Raw/02-Draft/03-Wiki), import entries, version diff, GraphML file, search ranking JSON, Q&A answer with citations |
| F | One artifact per format (7 digests, report types, tutorial, presentation, 12 exports), 4 validated JSON-LD, MP3 + audiobook ZIP |
| G | `get_channel_health` 13-channel JSON, sink-captured email, schedule list JSON, cron health heartbeat, agent-callback payload with trace_id |
| H | lifecycle stage JSONs, delivery-log rows, cost_log rows, stripe-mock checkout JSON (labeled mock), GDPR export JSON, restore + purge confirmations |
| I | audit rows, trace journey, Prometheus metrics text, alert dispatch log, REST curl outputs, coverage_audit 141/141 |

### 7.3 Final director summary table

Deliver this table to the director at the end of the walkthrough:

| Phase | Artifact path(s) | Verdict |
|-------|------------------|---------|
| A System/config/discovery | `...` | PASS / FAIL / unconfigured |
| B Domain/source/topic/keyword | `...` | |
| C Collection/dedup/cache | `...` | |
| D Processing/extraction/gates | `...` | |
| E KB pipeline/lifecycle/search | `...` | |
| F Output all formats | `...` | |
| G Delivery/scheduling/cron/callbacks | `...` | |
| H End-user/cost/billing/privacy | `...` | |
| I Governance/observability/REST/meta | `...` | |

Plus the two hard meta-results:

- Scenario suite: **47/47 passed** (0 failed, 0 unconfigured) with keys set.
- `scripts/coverage_audit.py`: **141/141 MCP tools covered, zero MISSING**.

---

## 8. QA Checklist (Pre-Handoff)

Before handing off to the director, verify all of the following:

- [ ] Every row in §4 (A1 through I6) was executed with a real call. No row skipped.
- [ ] RED was recorded before GREEN for every row.
- [ ] Every GREEN has a real artifact on disk / DB / log / sink, and that artifact was shown to the director (pasted or absolute path).
- [ ] No `unconfigured` row was graded as a pass; each missing key was surfaced as a BYOK obligation.
- [ ] All 47 scenarios re-run GREEN with keys configured (0 failed, 0 unconfigured).
- [ ] `python3 scripts/coverage_audit.py` reports 141/141 with zero MISSING.
- [ ] All 8 REST endpoints exercised via `curl` against `uvicorn autoinfo.api.server:app --port 8741`.
- [ ] All mutating calls have paired cleanup, verified by `list_*` and `git status --porcelain`.
- [ ] Runtime artifacts (`collections/`, `knowledge/`, `outputs/`, `exports/`, `autoinfo.db`, `.autoinfo/`, `logs/`, `.omo/`) are NOT committed and the working tree is clean.
- [ ] Local sinks (HTTP / SMTP / stripe-mock) are labeled as sinks in the evidence.
- [ ] Agent JSON-LD artifacts validate against `docs/schemas/*-v1.json` (4 artifacts).
- [ ] Director summary table (§7.3) filled with real paths and verdicts.
- [ ] English, tables, and relative `docs/dev/*.md` links follow repo conventions.

---

## Appendix A: 47-Scenario Inventory

Ground truth: `src/autoinfo/mcp/scenarios/` (47 YAML files, 225 steps total,
10 env-gated). Executed via MCP `list_validation_scenarios` /
`run_validation_scenario` (schemas verified at `src/autoinfo/mcp/server.py`
lines 5802-5831 and 10042-10073; engine `src/autoinfo/mcp/validation.py`).

| # | Scenario (file) | Category | requires_env | Steps | Cleanup |
|---|-----------------|----------|--------------|:---:|:---:|
| 1 | system-health | system | | 3 | 0 |
| 2 | discovery | discovery | | 5 | 0 |
| 3 | domain-management | domain | | 6 | 0 |
| 4 | source-management | source | | 9 | 0 |
| 5 | topic-management | topic | | 5 | 0 |
| 6 | keyword-management | topic | | 6 | 0 |
| 7 | collection | collection | | 5 | 0 |
| 8 | collectors-e2e | collection | | 4 | 0 |
| 9 | collection-monitor | collection | | 4 | 0 |
| 10 | processing | collection | `AUTOINFO_LLM_API_KEY` | 2 | 0 |
| 11 | cron-schedules | collection | | 5 | 0 |
| 12 | kb-access | kb | | 3 | 0 |
| 13 | kb-draft | kb | | 6 | 1 |
| 14 | kb-versioning | kb | | 3 | 0 |
| 15 | kb-graph | kb | | 6 | 1 |
| 16 | kb-import-export | kb | | 3 | 1 |
| 17 | kb-lifecycle | lifecycle | | 8 | 1 |
| 18 | kb-extraction | extraction | `AUTOINFO_LLM_API_KEY` | 2 | 0 |
| 19 | output-discovery | output | | 3 | 0 |
| 20 | output-digest-report | output | `AUTOINFO_LLM_API_KEY` | 3 | 0 |
| 21 | output-ebook | output | `AUTOINFO_LLM_API_KEY` | 4 | 0 |
| 22 | output-tutorial-presentation | output | `AUTOINFO_LLM_API_KEY` | 3 | 0 |
| 23 | output-simplify-recommend | output | `AUTOINFO_LLM_API_KEY` | 2 | 0 |
| 24 | output-column | output | `AUTOINFO_LLM_API_KEY` | 2 | 0 |
| 25 | delivery-channels | delivery | | 6 | 0 |
| 26 | delivery-schedules | delivery | | 4 | 0 |
| 27 | enduser-lifecycle | enduser | | 8 | 0 |
| 28 | enduser-preferences | enduser | | 7 | 0 |
| 29 | cost-budget | cost | | 5 | 0 |
| 30 | products-billing | cost | | 8 | 0 |
| 31 | data-privacy | privacy | | 6 | 1 |
| 32 | observability | observability | | 4 | 0 |
| 33 | agent-callbacks | system | | 4 | 0 |
| 34 | webhooks-alerts | system | | 8 | 0 |
| 35 | quality-gate-config | quality | | 4 | 0 |
| 36 | projects-config | system | | 8 | 0 |
| 37 | llm-gated | llm | `AUTOINFO_LLM_API_KEY` | 3 | 0 |
| 38 | cli-core | cli | | 3 | 0 |
| 39 | cli-content | cli | | 7 | 0 |
| 40 | cli-ops | cli | | 10 | 0 |
| 41 | cli-extra | cli | | 3 | 0 |
| 42 | cli-llm | cli | `AUTOINFO_LLM_API_KEY` | 2 | 0 |
| 43 | rest-api | http | | 8 | 0 |
| 44 | error-boundary | errors | | 3 | 0 |
| 45 | sources-gap-closure | source | | 6 | 0 |
| 46 | sources-a6-keyed | source | `FRED_API_KEY`, `FINNHUB_API_KEY` | 4 | 0 |
| 47 | meta-validation | system | | 2 | 0 |

**Totals:** 47 scenarios, 225 main steps, 10 env-gated (9 need
`AUTOINFO_LLM_API_KEY`, 1 needs `FRED_API_KEY` + `FINNHUB_API_KEY`).
No-key baseline profile: **37 passed / 0 failed / 10 unconfigured** (matches
`docs/dev/validation-scenario-contract.md` and
`docs/dev/launch-validation-framework.md`).

## Appendix B: Collector → Source Type → Key Env → Keyless Matrix

Source of truth: `VALID_SOURCE_TYPES` (29 types) and `SOURCE_KEY_ENV_VARS` in
`src/autoinfo/config.py`; handlers in `src/autoinfo/collectors/` (30 handler
files). See the full table in §3.2. Summary:

| Tier | Source types | Behavior |
|------|--------------|----------|
| **Keyless (21)** | rss, web, web_playwright (web), webhook, pdf, dblp, openalex, api/pubmed, api/s2, api/uspto, api/http_api, hackernews, gdelt, ssrn, sec_edgar, akshare, bilibili, apple_podcasts, yahoo_finance, edx_sitemap, huggingface (HF provider) | Real fetch with no credential; optional keys (pubmed/s2/uspto/http_api) only raise rate limits |
| **Key-gated (9 groups, 10 distinct types)** | nyt, ap_api, reuters_mcp, unpaywall, core, youtube, spotify (id+secret), quandl, kaggle (username+key), email/email_imap | Real fetch blocked without the credential; gating map = `SOURCE_KEY_ENV_VARS` |

Key env vars (full names in `docs/dev/required-api-keys.md`):
`AUTOINFO_NYT_API_KEY`, `AUTOINFO_AP_API_KEY`, `AUTOINFO_REUTERS_API_KEY`,
`AUTOINFO_YOUTUBE_API_KEY`, `AUTOINFO_UNPAYWALL_EMAIL`,
`AUTOINFO_CORE_API_KEY`, `AUTOINFO_SPOTIFY_CLIENT_ID` +
`AUTOINFO_SPOTIFY_CLIENT_SECRET`, `AUTOINFO_QUANDL_API_KEY`,
`KAGGLE_USERNAME` + `KAGGLE_KEY`, `AUTOINFO_EMAIL_PASSWORD`.
Optional rate-limit keys: `AUTOINFO_PUBMED_API_KEY`, `AUTOINFO_S2_API_KEY`,
`AUTOINFO_USPTO_API_KEY`, `AUTOINFO_HTTP_API_KEY`.

## Appendix C: Output Format Matrix

Source of truth: `src/autoinfo/output/__init__.py` (verified at the format
validation lines 329, 2515, 2980, 4474, 4769) and the MCP tool schemas in
`src/autoinfo/mcp/server.py`. Product templates: `PRODUCT_TEMPLATES`
(`src/autoinfo/output/__init__.py` line 2070): 8 templates: digest, report,
tutorial, presentation, premium-briefing, column, magazine-digest,
enterprise-briefing.

| Generator | Formats (count) | Formats | Artifacts |
|-----------|:---:|---------|-----------|
| `generate_digest` | 7 | markdown, html, json, agent, audio, epub, audiobook | `.md`, `.html`, `.json`, JSON-LD (`@type: KnowledgeDigest`), MP3, EPUB, audiobook ZIP (chaptered MP3, ID3v2.3 CHAP/CTOC) |
| `generate_report` | 8 (function) / 7 (MCP schema enum) | markdown, json, html, audio, agent, video, epub, audiobook | report artifacts; `report_type`: standard, industry, competitive, trend, daily-briefing, column |
| `generate_tutorial` | 2 | markdown, agent | `.md`, JSON-LD (`@type: KnowledgeTutorial`) |
| `generate_presentation` | 4 | markdown, html, mkslides, agent | Reveal.js markdown, standalone HTML (CDN), mkslides build, JSON-LD (`@type: KnowledgePresentation`) |
| `export_kb` | 12 | markdown, json, sqlite, csv, pdf, graphml, rss, agent, bundle, sitemap, epub, mobi | `exports/autoinfo-export-<domain>-<ts>.*`; bundle = ZIP (PDF+JSON+MD+YAML); sitemap requires `base_url`; JSON-LD (`@type: KnowledgeBaseExport`) |

**Corrections against earlier drafts:**

- The report generator function accepts **8** formats including `video`
  (`src/autoinfo/output/__init__.py` line 2980), but the MCP schema enum for
  `generate_report` lists **7** (`src/autoinfo/mcp/server.py` lines 7906-7965,
  missing `video`). Both facts are recorded; the function is the source of
  truth for execution, the MCP enum is the source of truth for the tool
  surface. The same note exists in `docs/dev/launch-validation-framework.md`
  §1.
- `export_kb` validates 12 formats; the MCP schema enum confirms all 12
  including `sitemap` and `mobi`.
- JSON-LD schemas live in `docs/schemas/`: `knowledge-digest-v1.json`,
  `knowledge-tutorial-v1.json`, `knowledge-presentation-v1.json`,
  `knowledge-base-export-v1.json` (const-pinned `@context` / `@type`).

---

## Related Documents

- `AGENTS.md` (root): operating model, 141-tool catalog, architecture rules
- `README.md` (root): feature inventory, status table, CLI/MCP tables
- `docs/dev/required-api-keys.md`: every environment variable (31 `AUTOINFO_*` + provider keys)
- `docs/dev/validation-scenario-contract.md`: scenario authoring contract
- `docs/dev/launch-validation-framework.md`: D1-D5 grading template and evidence catalog
- `docs/dev/mcp-usage-examples.md`: worked MCP workflows
- `docs/dev/cross-dimensional-catalog.md`: keystone product matrix (A1-A7 × B1/B2/B3)
- `docs/dev/enduser-coverage-matrix.md`: end-user feature coverage matrix
- `docs/dev/specs/mcp-tools.md`, `docs/dev/specs/pipeline.md`,
  `docs/dev/specs/delivery.md`, `docs/dev/specs/quality-gates.md`,
  `docs/dev/specs/operations.md`: extracted specs
- `docs/schemas/*-v1.json`: JSON-LD validation schemas
