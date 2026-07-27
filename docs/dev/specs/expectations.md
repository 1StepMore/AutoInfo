# Expectations Catalog — F01 to F57

> © Extracted from `founder-expectations.md §3` (lines 119-963) on 2026-07-26.
> This file is the source of truth for the founder's expectation catalog. The original
> `founder-expectations.md` retains a stub cross-referencing this file.

> References: F01-F57 as defined in `founder-expectations.md`. See
> [`docs/dev/specs/pipeline.md`](./pipeline.md) for pipeline details,
> [`docs/dev/specs/quality-gates.md`](./quality-gates.md) for gate details,
> [`docs/dev/specs/delivery.md`](./delivery.md) for end user lifecycle,
> [`docs/dev/specs/operations.md`](./operations.md) for cost/privacy/lifecycle/observability,
> [`docs/dev/specs/data-models.md`](./data-models.md) for schemas.

---

## 3. Expectation Catalog

**Status legend:** ✅ Fully implemented | 🔄 Partially implemented (basic version works, enhancements pending) | ❌ Not yet implemented

Each expectation is a statement of what the founder expects the project to do.
Expectations are grouped by journey phase.

> **Note on domains**: References to "medical", "AI commercial", and "language learning" throughout this catalog are **demo domain configurations**. The system is designed to support **any domain** a user defines. Demo domains ship with curated sources and templates to prove value. Users can define their own domains, sources, extraction schemas, and output formats.

### 3.1 Phase 1: Setup

> "I should be able to install and configure AutoInfo in minutes."

#### F01 — Installation ✅

| UX Detail | Specification |
|-----------|---------------|
| **Installation methods** | Multiple paths supported: `pip install autoinfo` (PyPI), `git clone + pip install -e .` (source/dev), or `docker pull` (Docker). README recommends ONE primary path. |
| **Expected dependency handling** | `autoinfo doctor` detects missing system dependencies (LLM API connectivity, database status) and reports them with install guidance. |
| **Expected UX on first install** | Install to first successful command under 5 minutes for a new user who can `pip install`. |
| **Agent perspective** | Agent does not install AutoInfo. Agent connects to a running MCP server (`python -m autoinfo.mcp.server`). The MCP server must be started by the human or systemd. |

#### F02 — First Command ✅

| UX Detail | Specification |
|-----------|---------------|
| **Human: `autoinfo` with no arguments** | Shows standard typer help text listing commands. No splash screen, no branding display. |
| **Agent: MCP server connection** | Agent connects to MCP server via stdio or SSE. Calls `health_check` tool to verify connectivity. Tool manifest is auto-discovered via MCP protocol. |
| **Output format — human** | Plain text help. `--json` flag available globally for machine-readable output. |
| **Output format — agent** | JSON-RPC over stdio. All tools return structured dicts. Tool descriptions are self-documenting via MCP protocol. |
| **Key info visible** | Human: commands, config location, version. Agent: tool list, resource list, server instructions. |

#### F03 — Configuration Initialization ✅

| UX Detail | Specification |
|-----------|---------------|
| **Config file location** | Two-tier: project `.autoinfo/` takes priority; `~/.autoinfo/` is fallback. If neither exists, `init` creates `.autoinfo/` in current directory. |
| **Init process — human** | Interactive wizard: asks user for domains of interest, LLM providers, and default source preferences. Offers to activate one or more demo domain configurations. |
| **Init process — agent** | Agent does not run `init`. Agent expects `.autoinfo/` to already exist with valid config. If missing, MCP tools return appropriate error. |
| **Re-running init** | Idempotent: creates any missing files but never overwrites existing config. To reset fully, delete `.autoinfo/` and re-run init. |
| **What init creates** | Full project skeleton: `config.yaml` + `sources.yaml` (empty, ready to populate) + `domains.yaml` + `topics.yaml` + directory structure (`sources/`, `collections/`, `knowledge/`, `outputs/`). `knowledge/` contains the 4 pipeline tiers: `00-Inbox/` (scaffolded but deprecated — no code writes to it), `01-Raw/`, `02-Draft/`, `03-Wiki/`. If demo domains selected, ships demo source lists. |
| **Demo domains shipped** | Five pre-configured domain templates: `medical-research`, `ai-commercial`, `financial-intelligence`, `tech-ai-developer`, `language-learning`. Each includes curated default sources, suggested topics, and output templates. User can activate any subset. |

#### F04 — LLM Configuration (BYOK) ✅

| UX Detail | Specification |
|-----------|---------------|
| **Multi-provider** | Supports any LLM provider accessible via LiteLLM/OpenRouter: Claude, GPT-4o, DeepSeek, local models (Ollama/vLLM), etc. |
| **Configuration** | `config.yaml` under `llm:` section: provider, model, API key (from env var or file), base URL (for local/self-hosted). |
| **Default provider** | None — user must configure at least one. `init` wizard can help select and test. |
| **Key verification** | `autoinfo doctor` tests LLM connectivity on demand. Collection run gives friendly error if key is invalid. |
| **Fallback chain** | Configurable: `llm.fallback: [claude-sonnet, deepseek-chat]` — if primary fails, try fallback. |
| **Per-task model selection** | Default model for all tasks, with per-task overrides: `llm.tasks.summarization.model: deepseek-chat`, `llm.tasks.extraction.model: claude-sonnet`. |
| **BYOK principle** | User brings their own API keys. No bundled LLM credits. Full cost control. |
| **Minimum friction — human** | Single `export AUTOINFO_LLM_API_KEY="sk-..."` with provider selection. |
| **Minimum friction — agent** | Agent assumes MCP server has key configured. If not, agent reports back to human. |

#### F05 — Domain & Source Configuration ✅

| UX Detail | Specification |
|-----------|---------------|
| **Domain as config** | A domain = a named configuration with: source list, extraction schema (optional), topic list, output templates. Everything in YAML. No code changes needed to add a domain. |
| **Minimum required fields** | At least one domain with at least one active source. |
| **Demo domain: Medical Research** | Default sources: PubMed API (primary), arXiv (q-bio, cs.AI categories), CrossRef (DOI → metadata), Unpaywall (OA full-text lookup). User can add more (journal RSS feeds, preprint servers, custom APIs). |
| **Demo domain: AI Commercial Intelligence** | Default sources: ProductHunt API, Crunchbase (basic), TechCrunch RSS, benchmark leaderboards (LMSYS, Artificial Analysis), thought leader blogs, AI case study repositories. Supports cases, rankings, product launches, funding data as parallel extraction tracks. |
| **Demo domain: Language Learning** | Default sources: Project Gutenberg, BBC Learning English, leveled reader repositories, news-in-levels, public domain children's literature. |
| **Demo domain: Financial/Business Intelligence** | Default sources: Alpha Vantage (stock/crypto/forex, free tier 25 req/day), FRED (US macroeconomics, free), Reuters Connect (enterprise news wire, requires subscription), Yahoo Finance RSS (public feeds), SEC EDGAR RSS (regulatory filings, free), CoinDesk/CoinTelegraph RSS (crypto, free). Supports multi-source pricing intelligence, regulatory filing monitoring, market news aggregation, and institutional-grade data feed production. **Note**: Bloomberg, Wind, Refinitiv, and FT require paid institutional subscriptions and are not included as default sources — they are available as user-configured premium sources under F08. |
| **Demo domain: Tech/AI/Developer** | Default sources: GitHub Trending (REST API + GraphQL, free), ProductHunt API (product launches, free tier), TechCrunch RSS (tech news, free), arXiv cs.AI/cs.CL/cs.LG categories (preprints, free API), Substack RSS (public tech newsletters, free), Hacker News (Firebase API, free), Stack Overflow RSS (Q&A trends, free), Semantic Scholar (AI-enhanced academic search, free API with key). Supports newsletter-style digests, trend analysis, and technology landscape tracking for technical audiences. |
| **Source types supported** | RSS/Atom feeds, REST APIs (JSON), web pages (with extraction rules), webhook push, email (incoming newsletters via IMAP), PDF endpoints. |
| **Universal extraction** | LLM-based flexible schema extraction: user describes what fields they want, LLM extracts them. No per-source coding needed. |
| **Validation** | `autoinfo doctor` validates source configuration. URLs/API endpoints tested for reachability. |
| **Agent: discover demo domains** | `list_demo_domains()` → returns `[{name: "medical-research", description: "...", source_count: 4}]`. |
| **Agent: activate domain** | `activate_domain(name="medical-research")` — loads demo configuration into user's `.autoinfo/`. |
| **Agent: deactivate domain** | `deactivate_domain(name="medical-research")` — removes domain config but preserves collected data. |
| **Agent: read domain config** | `get_domain_config(domain="medical-research")` — returns full domain configuration including sources, topics, extraction schema, and output templates. |
| **Agent: discover domain schema** | `get_domain_schema(domain="medical-research")` → returns `{extract_fields: [{name, type, description, required}], output_templates: ["digest", "report"], topics: [...]}`. Agent reads this to know what extraction fields are available without reading documentation. |

#### F06 — Setup Verification ✅

| UX Detail | Specification |
|-----------|---------------|
| **Human verification** | `autoinfo doctor` — checks Python version, LLM API connectivity, source reachability, database/filesystem status. |
| **Agent verification** | `health_check` MCP tool returns `{status, version, uptime_s, tools_count}`. Basic connectivity check. |
| **Agent self-diagnosis** | `diagnose_system()` MCP tool returns comprehensive health: `{llm: {provider, key_valid, last_test_ms}, sources: [{name, reachable, latency_ms}], disk: {free_mb, total_mb, knowledge_dir_size_mb}, db: {fts5_ok, entry_count}, tools_all_available: bool}`. Agent can self-diagnose without human running `doctor`. |
| **Source check** | `doctor` pings each configured source and reports reachability with latency. Agent-equivalent via `diagnose_system()` sources array. |
| **Missing dep guidance** | For each missing dependency, `doctor` prints install instructions. |

### 3.2 Phase 2: Domain & Topic Configuration

> "I should be able to define what to track, from where, and how to structure it."

#### F07 — Demo Domain Source Libraries ✅

*The system ships with curated source lists for three demo domains, proving value out of the box.*

| UX Detail | Specification |
|-----------|---------------|
| **Medical Research sources** | PubMed API (primary), arXiv (q-bio, cs.AI categories), CrossRef (DOI → metadata), Unpaywall (OA full-text). Each with quality rating, update frequency, access method. |
| **AI Commercial sources** | ProductHunt API (products), Crunchbase basic API (companies/funding), TechCrunch RSS (news), LMSYS/Artificial Analysis (benchmarks), curated case study indices. |
| **Language Learning sources** | Project Gutenberg (classics, public domain), BBC Learning English (leveled news), news-in-levels, commonlit.org (free leveled reading), public domain children's literature. |
| **Source metadata** | Each default source includes: name, URL/API endpoint, domain, content type, update frequency, quality tier (1-4), language, access restrictions. |
| **Quality tiers** | Tier 1: official APIs, peer-reviewed databases. Tier 2: reputable news, curated databases. Tier 3: blogs, community sources. Tier 4: user-defined custom (no quality guarantee). |
| **Agent: list defaults** | `list_demo_sources(domain="medical-research")` → returns `[{name, url, type, quality_tier, frequency}]`. |
| **Agent: activate sources** | `add_source(source_name="pubmed", domain="medical-research")` — activates a demo source. |

#### F07b — Source API Capability Matrix (NEW) ✅

> *Comprehensive API capability matrix for all curated demo domain sources, derived from the global information payment research report (2024-2026).*

This section provides a structured API capability catalog for every pre-configured and commonly available source across all demo domains. It serves as the reference for:
- **Agent decision-making**: which sources to prioritize for a given domain
- **Engineering feasibility**: which sources are freely automatable vs. require paid access
- **Cost estimation**: API pricing, rate limits, and data scope per source

##### Academic & Research Sources

| Source | API Available | Pricing | Rate Limit | Data Scope | Best For | Feasibility Rating |
|--------|-------------|---------|-----------|-----------|----------|-------------------|
| **PubMed (NCBI E-utilities)** | ✅ 9 APIs (esearch, efetch, elink, etc.) | Free, no key required | ≤3 req/s (recommended); IP ban if exceeded | 37M+ citations, titles, abstracts, MeSH terms, author metadata | Medical research, biomedical literature tracking | ⭐⭐⭐⭐⭐ |
| **arXiv** | ✅ REST, OAI-PMH, RSS | Free, no key required | 1 req/3s; 2026 added system-level throttling, 429 on burst | 2.9M+ preprints (8 categories), full PDF links, abstracts | CS/AI/math/physics preprint tracking | ⭐⭐⭐⭐⭐ |
| **CrossRef** | ✅ REST API | Free; polite pool registration for higher limits | Public: 50 req/s; polite: 100+ req/s (2025-12 adjustment) | 180M+ DOI records, titles, authors, reference lists, citation metadata | DOI resolution, citation graph, metadata enrichment | ⭐⭐⭐⭐⭐ |
| **Semantic Scholar** | ✅ Graph API v1.0 | Free (requires x-api-key); research API for academic use only | Rate-limited (higher for authenticated keys) | 200M+ papers, titles, abstracts, citation graph, TLDR summaries | AI-enhanced literature search, citation analysis | ⭐⭐⭐⭐ |
| **OpenAlex** | ✅ REST API | Free, no key required | Generous rate limits | 250M+ scholarly works, authors, institutions, concepts | Open scholarly metadata, broad coverage | ⭐⭐⭐⭐⭐ |
| **PubMed Central (PMC)** | ✅ OA full-text API | Free | Same as PubMed E-utilities | Full-text OA articles, bulk download via FTP | Full-text medical research, NLP datasets | ⭐⭐⭐⭐ |
| **CORE** | ✅ API | Freemium (free tier with limits) | Free tier: limited calls/day | Millions of OA papers aggregated | Central OA paper discovery | ⭐⭐⭐ |
| **Scopus (Elsevier)** | ✅ Scopus API | Paid subscription required (institutional) | Per licensing agreement | 100M+ records, complete citation data, author profiles | Institutional academic research | ⭐⭐ |
| **Web of Science (Clarivate)** | ✅ API | Paid subscription required (institutional) | Per licensing agreement | High-quality journal index, citation data | Citation analysis, research evaluation | ⭐⭐ |
| **IEEE Xplore** | ✅ API | Paid subscription required (institutional or personal) | Per licensing agreement | Engineering, computer science journals/conferences | Engineering research | ⭐⭐ |
| **CNKI (中国知网)** | ❌ No public API | Institutional subscription (~¥160K+/year per university) | Strong anti-crawl (CAPTCHA, IP rate-limit, dynamic token) | 280M+ articles, 10,689 journals (Chinese academic) | Chinese academic research | ⭐ (not automatable) |
| **SSRN (Elsevier)** | ⚠️ Limited (Elsevier integration) | Mostly free (OA papers); some paid | Insufficient data | 563K+ full-text downloads, social sciences/humanities | Social science, law, economics | ⭐⭐ |

##### Financial Data Sources

| Source | API Available | Pricing | Rate Limit | Data Scope | Best For | Feasibility Rating |
|--------|-------------|---------|-----------|-----------|----------|-------------------|
| **Bloomberg Terminal** | ✅ Private BLP API (terminal only) | **$2,665/user/mo** (~$32K/yr); API negotiable | Private protocol, hardware-bound auth | Real-time quotes, history, news, analytics (full-stack) | Institutional finance, real-time market data | ⭐ (prohibitively expensive) |
| **Refinitiv / LSEG Workspace** | ✅ Eikon/Workspace Data API | **$2,000-$8,000+/user/mo** (enterprise pricing) | OAuth license | Real-time + historical quotes, reference data, news | Professional finance, enterprise | ⭐ (prohibitively expensive) |
| **Wind (万得)** | ✅ Local COM/Python SDK | Institutional: tens of thousands RMB/yr; personal: ~¥680/mo (2024 discount) | Account + hardware lock | A-shares, bonds, funds, derivatives, macro, industry (China focus) | China A-share market, Chinese institutional finance | ⭐⭐ (paid, China-specific) |
| **东方财富 Choice** | ✅ Quant API | Institutional (lower entry than Wind) | Signature/token auth | A-shares, HK stocks, US stocks, funds, financial statements | Retail/individual investors in China | ⭐⭐ |
| **同花顺 iFinD** | ✅ SDK + HTTP API | Terminal from ¥8,000+/yr | Login + IP binding | Quotes, financials, news, macro | Retail investors in China | ⭐⭐ |
| **Quandl (Nasdaq Data Link)** | ✅ REST + Python/R packages | Freemium (free datasets + premium by source) | API key rate-limited | EOD, fundamentals, macro, alternative data | Developers, quantitative research | ⭐⭐⭐⭐ |
| **Alpha Vantage** | ✅ REST | Free: 25 req/day (5 req/min); Premium: $49.99-$79.99/mo | Rate-limited (free tier very restrictive) | Stocks, forex, crypto, technical indicators | Personal finance, prototyping, lightweight projects | ⭐⭐⭐ |
| **FRED (Federal Reserve)** | ✅ REST API | **Free** | Generous | US economic time series (millions of series) | US macroeconomic analysis, research | ⭐⭐⭐⭐⭐ |
| **Yahoo Finance** | ❌ No official API (shut down 2017) | — | Blocks automated requests | — (3rd party yfinance library exists, ToS-violating) | Not recommended for production | ⭐ (ToS risk) |
| **CEIC** | ⚠️ API available | High-price institutional subscription | Per contract | Global macroeconomics (200+ countries) | Global macro research | ⭐⭐ |

##### News & Media Sources

| Source | API Available | Pricing | Rate Limit | Data Scope | Best For | Feasibility Rating |
|--------|-------------|---------|-----------|-----------|----------|-------------------|
| **Reuters Connect** | ✅ Enterprise licensing | **$2K-$15K/mo** base; AI training/RAG: six-figure USD/yr | Enterprise contract + OAuth | Full text, images, video, live feeds | Enterprise news monitoring, AI training data | ⭐⭐ |
| **Associated Press (AP)** | ✅ AP Developer Portal | Requires API key (paid); free/subscription tiers | 100 calls/min/key default | Full text, headlines, authors, dates, multimedia | General news, wire content | ⭐⭐⭐ |
| **NYT** | ✅ Developer API | Free key + paid premium | 10 req/min; 1,000 req/h via RapidAPI mirror | Headlines, abstracts, authors, sections (non-full-text, 1980+) | Research, non-commercial analysis | ⭐⭐⭐ |
| **Bloomberg Media** | ❌ No public API | — | — | — | — | ⭐ (not accessible) |
| **Financial Times** | ❌ No public API | Personal sub: £75/mo; no API | Strong anti-crawl behind paywall | Full text (paywalled) | — | ⭐ (not accessible) |
| **新华社** | ❌ No public API | State news agency | — | — | — | ⭐ (not accessible) |
| **财新 (Caixin)** | ❌ No public API | Subscription: ¥498-¥998/yr | Strong anti-crawl | Full text (paywalled, Chinese financial news) | — | ⭐ (not accessible) |
| **WSJ** | ❌ No public API | $44.99/mo | — | — | — | ⭐ (not accessible) |

##### Knowledge & Paid Content Platforms

| Source | API Available | Pricing | Data Scope | Feasibility Rating |
|--------|-------------|---------|-----------|-------------------|
| **Substack** | ✅ Developer API (read-only) | Free (registration + LinkedIn verification) | Public profiles, post metadata; **no paid content** | ⭐⭐⭐⭐ |
| **Medium** | ❌ No public data API | Membership ($5-15/mo) | Public article metadata only (Cloudflare/UA verification) | ⭐⭐ |
| **知乎 (Zhihu)** | ❌ No open API (encrypted since 2025/3) | Salt membership | Public Q&A/column summaries (sliding window + token bucket + TLS fingerprint rate-limiting) | ⭐ (not accessible) |
| **得到 App** | ❌ No official API | Subscription ¥199-¥365/yr | Course/ebook metadata (HTTPS signing + anti-debug) | ⭐ (not accessible) |
| **微信公众号** | ❌ No official API | — | Public article HTML (strong anti-crawl: login/Referer/CSRF required) | ⭐ (not accessible) |
| **Patreon** | ✅ API | Creator subscription | Creator content, membership data | ⭐⭐⭐ |
| **小鹅通** | ✅ Open API | SaaS platform | User/order/course/learning data | ⭐⭐⭐ |

##### Social Media & UGC Sources

| Source | API Available | Pricing | Rate Limit | Data Scope | Feasibility Rating |
|--------|-------------|---------|-----------|-----------|-------------------|
| **X (Twitter)** | ✅ v2 API | Free: 1 post/day write only; Basic: $200/mo (15K reads); Pro: $5,000/mo; Enterprise: $125K-$210K/mo | Token + rate-limit quotas | Tweets, users, trends, search | ⭐⭐ |
| **Reddit** | ✅ OAuth API | Free: 100 req/min (OAuth); Commercial: $0.24/1K calls (pre-approval) | Strict rate-limiting | Posts, comments, subreddit metadata | ⭐⭐⭐⭐ |
| **YouTube Data API v3** | ✅ REST | Free: 10K units/day; Overage: $0.001-$0.01/unit | Quota-based | Videos, channels, comments, captions, analytics | ⭐⭐⭐⭐ |
| **TikTok** | ✅ Display/Login/Research API | Display: commercial; Research: academic (audited) | Device/UA/JS verification, strong anti-crawl | Videos, user metadata (limited) | ⭐⭐ |
| **微博 (Weibo)** | ✅ Open platform | Developer qualification + tiered pricing | Rate-limit + CAPTCHA | Weibo posts, comments, users (partial) | ⭐⭐ |
| **抖音/字节系** | ✅ Open platform | Base: ¥50/10K calls; Premium: ¥100/10K calls (2024/10 pricing) | Signature + token + IP rate-limit | Videos, live-streaming, IM, ecommerce | ⭐⭐ |
| **B站 (Bilibili)** | ✅ Open platform | App review required (free quota available) | Risk control + CAPTCHA | Videos, danmaku, comments, live-streaming | ⭐⭐⭐ |
| **小红书 (Xiaohongshu)** | ✅ Open platform (e-commerce/data only) | Merchant/partner qualification required | Signature + device fingerprint; v2 deprecated 2025/6 | Notes, products | ⭐⭐ |

##### Podcast & Audio Sources

| Source | API Available | Pricing | Data Scope | Feasibility Rating |
|--------|-------------|---------|-----------|-------------------|
| **Spotify** | ✅ Web API + oEmbed | Free (client credentials OAuth); Commercial via partner | Episodes/shows metadata; **no audio stream** | ⭐⭐⭐⭐ |
| **Apple Podcasts** | ✅ iTunes Search API (no auth) | Free | Episodes/shows metadata (1.58M shows globally) | ⭐⭐⭐⭐⭐ |
| **喜马拉雅 (Ximalaya)** | ❌ No public API | — | — | ⭐ (not accessible) |
| **小宇宙 (XYZ Podcast)** | ❌ No official API | — | — | ⭐ (not accessible) |

##### Data Automation Polarity Summary

The research report reveals a clear **polarization** between "engineering-feasible" and "non-engineering-feasible" sources:

| Category | Engineering-Feasible (Free/Open API) | Not Engineering-Feasible (No API or Extremely Expensive) |
|----------|-------------------------------------|--------------------------------------------------------|
| **Academic** | arXiv, PubMed, OpenAlex, CrossRef, Semantic Scholar, PMC, CORE (free tier) | CNKI, Scopus (paid), Web of Science (paid), IEEE (paid), SSRN (limited) |
| **Financial** | Alpha Vantage (free tier), FRED, Quandl (free tier) | Bloomberg, Refinitiv, Wind, FT, CEIC |
| **News** | AP (limited free tier), NYT (research only) | Bloomberg Media, WSJ, 财新, FT, 新华社, 人民日报 |
| **Social/UGC** | Reddit (non-commercial), YouTube, Apple Podcasts | TikTok, 微博, 抖音, 小红书, B站 (paid access) |
| **Chinese Knowledge** | — | 知乎, 得到, 微信公众号, 喜马拉雅, 小宇宙 |

**Strategic implication**: AutoInfo's engineering strategy prioritizes sources with open APIs (academic, selected financial, selected news) for the automated pipeline. High-value but walled sources (Bloomberg, Chinese platforms) are supported as "premium user-configured sources" under F08 — users configure their own paid access, AutoInfo provides the handler. This polarity directly informs domain selection and product pricing. |

*Users add any source, for any domain, without writing code.*

| UX Detail | Specification |
|-----------|---------------|
| **Human: add source** | `autoinfo sources add --name "My Blog" --url https://example.com/rss --type rss --domain custom-domain` |
| **Human: list sources** | `autoinfo sources list` — shows all sources with status, grouped by domain. |
| **Agent: add source** | `add_source(name="My Blog", url="https://...", type="rss", domain="custom-domain")`. **Idempotent**: calling with the same `(url, type, domain)` returns the existing source ID instead of error. Safe for agent retry. |
| **Agent: batch add sources** | `add_sources(sources=[{name, url, type, domain}, ...])` — add multiple sources in one call. Each source validated independently. Non-existent domains return error per source, not global failure. |
| **Source types** | `rss` (RSS/Atom), `api` (REST JSON), `web` (web page, auto-extract), `webhook` (push endpoint), `email` (IMAP inbox), `pdf` (PDF endpoint/directory). |
| **Extraction schema per source** | Optional: user can define `extract_fields: [title, author, date, content, custom_field_1, ...]`. LLM extracts these from each item. If no schema defined, defaults to generic: title, content, date, source. |
| **Source validation** | On add, system tests connectivity and attempts a sample fetch. Reports errors immediately. |
| **Agent: remove source** | `remove_source(source_id="pubmed")` — removes source from domain config. Does not delete already-collected data. |
| **Agent: test source** | `test_source(url="https://...", type="rss")` — fetches a sample, returns content preview, format detection, and suggested extract_fields. |
| **Agent: source warning** | `add_source` returns `{source_id, warnings: ["low quality tier: 3 — content may be unreliable"]}` when quality_tier ≥ 3. Advisory only — agent decides whether to notify human. |

#### F09 — Topic & Keyword Configuration ✅

| UX Detail | Specification |
|-----------|---------------|
| **Domain-scoped topics** | Each domain has its own topic list. Topics within a domain share the domain's source pool. |
| **Human: add topic** | `autoinfo topics add --domain medical-research --name "IVF 2026 breakthroughs" --keywords "IVF, embryo, implantation, in vitro fertilization"` |
| **Human: topic groups** | `autoinfo topics group --domain medical-research --name "IVF Research" --add ivf endometriosis` — hierarchical grouping |
| **Agent: manage topics** | `add_topic(domain="medical-research", name="IVF breakthroughs", keywords=["IVF", "embryo"])`. Remove with `remove_topic(domain="medical-research", topic_id="...")`. |
| **Topic → source mapping** | Each topic can be restricted to specific sources, or use all active sources in its domain. |
| **Multi-language keywords** | Topics support keywords in multiple languages. Useful for cross-lingual domains. |
| **Topic scoring & suggestions** | System can suggest keyword refinements based on initial collection results and LLM analysis. |

#### F10 — Multi-language & Localization 🔄

*Content comes in many languages; the system handles it gracefully. Essential for the language learning demo domain and general usability.*

| UX Detail | Specification |
|-----------|---------------|
| **Source language auto-detection** | Auto-detect language of collected content. Store as metadata. |
| **Translation pipeline** | Built-in LLM-based translation for summarization. User configures source → target language pairs. |
| **Learning-specific localization (demo domain)** | For language-learning domain: level-appropriate simplification, glossaries, reading level classification (CEFR A1-C2, Lexile). |
| **Cross-lingual KB** | Knowledge base entries have multi-language fields: title (original + translated), summary (user's language), keywords (multi-lang). |
| **Use case: medical paper in Chinese** | "帮我翻译这篇摘要到英文" → `localize_content(content, source_lang="zh", target_lang="en")` |
| **Use case: English reading for kids** | "帮我把这篇文章按CEFR B1级别简化，标注生词" → `simplify_for_learning(content, level="B1", gloss_target="zh")` |
| **Agent: translate** | `localize_content(content_id="...", target_lang="en")` — returns translated version. |
| **Translation QA — back-translation verification** | After translation, the system performs back-translation: translate the result back to the source language and compare with the original via LLM. Mismatches are flagged with diff details. Reduces hallucination risk by 60%+ compared to single-pass translation. |
| **Translation QA — multi-round refinement** | If back-translation reveals issues, the system re-transmits with context from the first attempt: "Previous translation had issue X in paragraph Y. Re-translate focusing on Z." Supports up to 3 refinement rounds before falling back to the best attempt. |
| **Translation QA — domain terminology guard** | Per-domain terminology dictionary (maintained in `_keywords.yaml`). Terms like drug names, medical procedures, technical concepts are tagged `do_not_translate` or `preferred_translation`. The LLM prompt includes these guardrails to prevent mistranslation of critical terms. |
| **Translation QA — style & tone consistency** | LLM review verifies that translation maintains the original's tone (formal/academic/colloquial), register, and intent. Style violations are flagged separately from factual inaccuracies. |
| **Translation QA — prompt engineering** | Domain-specific translation prompts optimized through iterative testing. Each domain can define: `translation_prompt_template` (overrides the default), `terminology_glossary_path`, `style_guide`. Prompts are versioned and auditable. |
| **Translation QA — agent skill** | A dedicated translation quality skill (`translator-qa-skill`) that agents load for high-stakes translation workflows. The skill orchestrates: initial translation → back-translation check → terminology audit → style review → human review prompt → final approval. |
| **Translation QA — quality score** | Each translation gets a composite quality score (0-100) combining: faithfulness (G5), terminology accuracy, style consistency, readability. Scores below configurable threshold auto-flag for human review. |

#### F10b — User-Defined Domains & Consulting Platforms ✅

*The platform is domain-agnostic. Users define their own fields of interest and configure the information platforms (data sources) they want to track — no coding required.*

| UX Detail | Specification |
|-----------|---------------|
| **Domain as first-class entity** | A domain = named configuration with: sources, topics, extraction schema, output templates. Defined entirely in YAML. No code changes needed to add a domain. |
| **User-defined domains** | Users create new domains from scratch: `add_domain(name="my-custom-domain", description="...")` — generates a minimal domain skeleton with empty sources/topics, ready to populate via `add_source` and `add_topic`. |
| **Consulting platform concept** | A "consulting platform" is the information source/platform a domain monitors (e.g., PubMed for medical research, TechCrunch for AI commercial, Weibo for social trends). Users define which platforms their domain consults. Platforms map 1:1 to source configurations in the domain. |
| **Multi-platform domain** | A single domain can consult multiple platforms simultaneously. Example: "Medical Research" domain consults PubMed, arXiv, CrossRef, and 3 journal RSS feeds. |
| **Domain lifecycle** | `create` → `activate` / `deactivate` → `archive` (preserves data) → `delete` (destructive). Agent can manage full lifecycle. |
| **Domain schema** | Each domain defines: `extract_fields` (what LLM extracts from items), `output_templates` (digest/report/tutorial/presentation), `search_mode` (keyword/hybrid), `relevance_threshold`. |
| **Agent: create domain** | `add_domain(name="my-domain", description="...")` — creates a new domain with default config. Returns `{domain, sources: [], topics: [], status: "active"}`. Must be idempotent: calling with same name returns existing config. |
| **Agent: list domains** | `list_domains()` — returns `[{name, active, source_count, topic_count, platform_count}]`. |
| **Agent: get schema** | `get_domain_schema(domain="my-domain")` — returns `{extract_fields, output_templates, search_mode, platform_types_supported}`. Agent reads this to understand domain capabilities. |
| **Agent: activate/deactivate** | `activate_domain(name="...")` / `deactivate_domain(name="...")` — toggle domain active state without losing config or data. |
| **Agent: remove domain** | `remove_domain(name="...")` — removes domain config. Preserves already-collected data. |
| **CLI: domain management** | `autoinfo domain add|list|show|remove|activate|deactivate` — human-direct interface for domain lifecycle. |
| **Platform discovery** | `list_available_platforms()` — returns all supported source platform types (RSS, API, Web, Webhook, Email, PDF) with descriptions. Agent uses this to suggest platforms to users during domain creation. |

### 3.3 Phase 3: Information Gathering

> "I should be able to collect information and know what's happening."

#### F11 — One-Command Collection ✅

| UX Detail | Specification |
|-----------|---------------|
| **Human: collect one domain** | `autoinfo collect --domain medical-research` — collects from all active sources in the domain |
| **Human: collect one topic** | `autoinfo collect --domain medical-research --topic "IVF"` — filtered to topic |
| **Human: collect all** | `autoinfo collect --all` — collects from all active domains |
| **Agent: collect** | `collect_sources(domain="medical-research")` — single MCP tool call |
| **Agent: selective** | `collect_sources(domain="medical-research", sources=["pubmed"], keywords=["IVF"], limit=20)` |
| **Collection output** | Each item stored with: source, title, url, content, collected_at, language, domain, topic tags, quality score. |
| **Dedup (G2)** | URL-based dedup + fuzzy title dedup within configurable time window. Same article from multiple sources = one entry. |
| **Dry-run mode** | `collect_sources(..., dry_run=true)` — returns `{estimated_items: {pubmed: 12, arxiv: 5}, total_estimated: 17}` without fetching or storing. Agent previews collection impact before committing. |
| **Empty result handling** | If no new items found, report clearly: "No new items for [domain]. Last collection had [N] items." Not an error. |

#### F12 — Collection Progress Visibility ✅

| UX Detail | Specification |
|-----------|---------------|
| **Human: terminal output** | Per-source progress: source name, items found, items new (after dedup), errors, duration. |
| **Human: no silent gaps** | Between sources, continuous progress output so terminal never goes silent. |
| **Human: completion** | Summary: `✅ 收集完成 — PubMed: 12篇 (8新), arXiv: 5篇 (3新), 共 11 篇新内容` |
| **Agent: progress** | `collect_sources` returns `{collection_id, status: "started", estimated_duration_s: 30}` immediately. Agent divides by 4 for poll interval (e.g., 30s → poll every 7.5s, min 2s). Agent polls `get_collection_progress(collection_id)`. |
| **Agent: per-source detail** | `{source: "pubmed", status: "completed", items_found: 12, items_new: 8, errors: []}` |
| **Agent: processing** | After collection, `process_collection(domain="medical-research", model="deepseek/deepseek-chat")` — runs LLM extraction + quality gates on cached raw items. Separable from collection: collect now, process later. |
| **Agent: completion** | `get_collection_status(collection_id)` returns full collection result with all items. |

#### F13 — Source Type Handlers ✅

*Each supported source type has a dedicated handler. Handlers are pluggable — new source types can be added without changing core pipeline.*

| Source Type | Handler Behavior | Implementation Priority |
|-------------|-----------------|------------------------|
| **RSS/Atom** | Fetch feed XML → parse entries → extract content (full text if available, else summary) → store | 🔴 P0 |
| **REST API (JSON)** | Call endpoint with auth → parse JSON response → extract according to schema → store | 🔴 P0 |
| **Web page** | Fetch HTML → extract main content (trafilatura/readability) → clean → store | 🟡 P1 |
| **Webhook** | Receive POST → validate → store immediately | 🔵 P2 |
| **Email (IMAP)** | Connect to inbox → fetch unread from configured folder(s) → parse → store | 🔵 P2 |
| **PDF endpoint** | Download PDF → extract text (pypdf/LLM) → store | 🟡 P1 |

#### F14 — Scheduled Collection ✅

| UX Detail | Specification |
|-----------|---------------|
| **Scheduling mechanism** | External crond calls `autoinfo cron run` at configured intervals. AutoInfo has no built-in scheduler. |
| **Config format** | `cron.schedules: [{name: "daily-medical", expression: "0 8 * * *", domain: "medical-research", topic: "all"}]` |
| **Per-domain cadence** | Different schedules per domain: daily medical, weekly AI commercial. |
| **Agent: manage schedules** | `add_collection_schedule(expression="0 8 * * *", domain="medical-research")`. Full CRUD via MCP. |
| **On-demand + scheduled** | Both work. On-demand for immediate needs. Scheduled for regular updates. |

#### F15 — LLM-Based Extraction Pipeline ✅

*The core differentiator: LLM extracts structured fields from any collected content, for any domain.*

| UX Detail | Specification |
|-----------|---------------|
| **Universal extraction** | After collection, each item passes through an LLM extraction step. What gets extracted depends on the domain's `extract_fields` config. |
| **Default extraction** | If no custom schema: title, summary (TL;DR), key points (3-5), entities (people, organizations, concepts), relevance score to user's topics. |
| **Custom extraction** | User defines: `extract_fields: [methodology, sample_size, key_findings, limitations]` for medical domain. LLM extracts these from each paper. |
| **Extraction prompt** | Per-domain extraction prompt template. Default prompt is auto-generated from field names and descriptions. User can override. |
| **Extraction quality gate (G4)** | Post-extraction, LLM verifies: does the extracted summary contradict the source? Flags hallucination. |
| **Agent: extract** | `extract_fields(content_id="...", schema=["methodology", "findings"])` — on-demand re-extraction with custom schema. |
| **Agent: inspect extraction** | `get_extraction(content_id="...")` — see what was extracted for any item. |

### 3.4 Phase 4: Curation & Interaction

> "I can review, interact with, and curate the collected information."

#### F16 — Summary Review ✅

| UX Detail | Specification |
|-----------|---------------|
| **Human: browse summaries** | `autoinfo summaries list --domain medical-research --date today` — list all summaries from today, ranked by relevance |
| **Human: read full** | `autoinfo summaries show <summary-id>` — full summary with source link, extracted fields, quality score |
| **Human: flag for KB** | `autoinfo summaries flag <id> --tag important --add-to-kb` — tag for knowledge base inclusion |
| **Agent: list summaries** | `list_summaries(domain="medical-research", date_from="2026-07-01", limit=20)` |
| **Agent: read single summary** | `get_summary(summary_id="...")` — returns full summary detail with extracted fields, quality scores, full content, and source provenance. |
| **Agent: flag for KB** | `flag_for_knowledge_base(summary_id, tags=["ivf", "breakthrough"], importance=5)` |
| **Summary format** | Title (original + translated), source, collected_at, TL;DR, key points (3-5), relevance score, extracted fields. |
| **Batch review (agent-driven)** | Agent can present batch: "Today's medical digest: 15 new papers, 3 flagged as important. Key findings: [...]" |
| **Quality filtering (G3)** | Items below configurable relevance threshold are stored but hidden from default summary view. User can opt to see them. |

#### F17 — Interactive Q&A on Collected Content ✅

| UX Detail | Specification |
|-----------|---------------|
| **Human: ask about content** | "上一篇关于子宫内膜容受性的论文里，用了什么研究方法来测量？" → Agent searches collected content and answers with citations. |
| **Agent: Q&A tool** | `query_collected(query="method for endometrial receptivity measurement", domain="medical-research", content_ids=["..."])` — returns answer with source citations. |
| **Cross-item synthesis** | Answers can synthesize across multiple items: "比较这三篇IVF论文的成功率数据" → structured comparison table. |
| **Source-grounded** | All answers must cite specific collected items. No hallucination: if answer not in collected content, say so. |
| **Scope: Q&A on collection only** | Q&A is limited to already-collected content, not live web search. |
| **Conversation persistence** | Q&A context persists per topic/domain per session. |

#### F18 — Quality Rating & Filtering ✅

| UX Detail | Specification |
|-----------|---------------|
| **Source authority check (G1)** | Each source has a `quality_tier` (1-4). Items from Tier 3+ sources are flagged. User can set minimum tier: "only show Tier 1-2". |
| **Automatic relevance scoring (G3)** | Each item scored against user's topic keywords + LLM-based semantic relevance. Score range 0-100. |
| **User feedback loop** | User can rate items: `autoinfo summaries rate <id> --helpful` / `--not-relevant` → system adjusts topic weights and extraction focus. |
| **Agent: rate item** | `rate_item(item_id, rating=5, feedback="highly relevant to IVF protocol comparison")`. |
| **Auto-filter** | Items below configurable relevance threshold stored but hidden from default view. User can override per collection. |

#### F19 — Cross-reference & Linking ✅

| UX Detail | Specification |
|-----------|---------------|
| **Auto-linking** | System auto-links items sharing keywords, entities, authors, citations (where available), or topics. |
| **Manual linking** | Human or agent can manually link items: "这篇论文是对上一篇提到的技术的临床验证" → `link_items(item_a_id, item_b_id, relation="clinical_validation")`. |
| **Relation types** | `cites`, `cited_by`, `extends`, `contradicts`, `validates`, `implements`, `related`, `translation_of`, `simplified_for`, `custom`. |
| **Cross-domain linking** | Link across domains: "这篇AI论文的方法可以用于医学论文分析" → cross-domain link with rationale. |
| **Agent: query relations** | `get_item_relations(item_id)` → returns linked items with relation types and strength. |

### 3.5 Phase 5: Knowledge Base Building

> "Collected information transforms into a structured, searchable, reusable knowledge asset."

#### F20 — Knowledge Base Storage (4-tier Pipeline) ✅

*KB architecture follows the proven KB pipeline design (`docs/archive/kb-pipeline-reference.md`): a 4-level pipeline with sequential promotion.*

| UX Detail | Specification |
|-----------|---------------|
| **Pipeline model** | 4-level sequential pipeline, **no skipping allowed**:
  ```
  Collected Item → 01-Raw → 02-Draft → 03-Wiki
       ↑              ↑          ↑           ↑
    Auto-ingest    Raw is     Agent can    Only human
    from F11      the ONLY    process &    can promote
                  entry       create       Draft → Wiki.
                  point       Draft.       03-Wiki never
                              No direct     directly written.
                              03-Wiki.
  ```
| **00-Inbox** ⚠️ deprecated | Scaffolded by `init` but **no code ever writes to it**. Items go directly to 01-Raw. Retained as an empty directory skeleton for backward compatibility. Corresponds to KB tier `00-Inbox/`. |
| **01-Raw** (auto, primary) | **Sole entry point** for all collected content. Every collected item (from F11) lands here automatically. **全量保留，不做取舍** — keep everything, filter later. File name = readable topic slug, not source ID. Corresponds to KB tier `01-Raw/`. |
| **02-Draft** (agent-writable) | Agent can create Draft entries from Raw: cleaned, merged, restructured, enriched. But agent **cannot** create Draft directly from outside — only from 01-Raw. User reviews Draft before promotion. Corresponds to KB tier `02-Draft/`. |
| **03-Wiki** (human-only, append-only) | Permanently reviewed knowledge. **No direct writes allowed** (hard rule). Only human can promote Draft→Wiki. Agent never writes to 03-Wiki. **Append-only**: once promoted, entries stay. Agent cannot demote or delete Wiki entries — only human can. Agent may deprecate (tag `status: deprecated`) or annotate entries upon explicit human command. Corresponds to KB tier `03-Wiki/`. |
| **Directory structure** | `knowledge/<domain>/<tier>/<collection>/<YYYY-MM-DD>-<slug>.md`. Example: `knowledge/medical-research/01-Raw/ivf/2026-07-20-endometrial-receptivity.md`. |
| **Entry frontmatter** | `title`, `domain`, `tier` (raw/draft/wiki), `source_url` (必填), `source_type` (paper/article/video/…), `source_platform` (pubmed/arxiv/…), `author`, `collected_at`, `summary`, `source_ids[]`, `tags[]`, `status` (raw/processing/compiled), `priority` (1-5), `language`, `related_concepts[]`, `linked_entries[]`, `custom_fields: {key: value}`. |
| **Generic schema + custom fields** | All entries share base fields. Each domain defines `custom_fields`. Medical: `{doi, authors, journal, methodology, sample_size}`. AI: `{category, pricing, competitors}`. User-defined: anything. |
| **Keywords system** | Central `_keywords.yaml` per domain or global. Managed status: `verified` (human-confirmed), `auto_added` (LLM-extracted candidate), `merged`, `deprecated`. Prevents synonym proliferation. Modeled after external `_keywords.yaml` pattern (554 entries across the KB). |
| **Agent: list keywords** | `list_keywords(domain="medical-research", status="verified")` — returns `[{keyword, status, aliases, created_at}]`. Agent uses known keywords to refine search queries and topic suggestions. |
| **Source metadata mandatory** | Every Raw entry must have complete source provenance (`source_url`, `source_type`, `source_platform`). Future verification and回溯 depend on this. |
| **Auto-ingest to 01-Raw** | Collection pipeline (F11-F15) automatically creates 01-Raw entries. No user action needed for ingestion. |
| **Auto-extraction → Draft candidate** | LLM extraction (F15) + quality gates (G1-G3) produce a Draft candidate from Raw. Agent can present: "3 papers promoted to Draft-ready, review and promote to Wiki?" |
| **Agent: create Draft** | `create_kb_draft(raw_ids=["..."], title="...", summary="...", tags=[...])`. **Cannot** skip Raw. |
| **Agent: list tiers** | `list_kb_tier(domain="medical-research", tier="01-Raw")` — returns entries in a specific pipeline stage. |
| **User: promote Draft→Wiki** | `autoinfo kb promote <entry-id>` — the only way to create Wiki entries. Agent must not call this. |
| **User: reject Draft** | `autoinfo kb reject <entry-id> --reason "needs more sources"` — sends back to Raw or archives. |
| **Agent: reject Draft** | `reject_kb_draft(draft_id="...", reason="needs more sources", action="back_to_raw")` — agent processes rejection on human instruction. Moves Draft back to Raw for revision. |

#### F21 — Knowledge Base Search & Retrieval ✅

| UX Detail | Specification |
|-----------|---------------|
| **Hybrid search** | Keyword (SQLite FTS5) + semantic (vector embeddings via LLM). Configurable weight via `search.mode: hybrid|keyword|semantic`. |
| **Faceted search** | Filter by: domain, tags, date range, source quality tier, content type, language. |
| **Agent: search KB** | `search_knowledge_base(query="endometrial receptivity biomarkers", domain="medical-research", limit=10, offset=0)` — returns paginated results with total count. |
| **Agent: read entry** | `get_kb_entry(entry_id="...")` — returns full entry content (title, all metadata, body, extracted fields, source provenance, linked entries). Required because search results are summaries only. Agent reads full entry to answer deep questions. |
| **Search results** | `[{entry_id, title, summary, relevance_score, matched_tags[], source_count, custom_fields}, total_count]`. |
| **Pagination** | All list/search tools accept `limit` (default: 20, max: 100) and `offset` (default: 0) for cursor-style pagination. Results include `total_count` for agent to determine if more pages exist. |
| **Cross-domain search** | Search across all domains or restrict to specific ones. Default: current domain context. |

#### F22 — Knowledge Graph ✅

| UX Detail | Specification |
|-----------|---------------|
| **Entity extraction** | LLM-based extraction of entities from KB entries: concepts, methods, people, organizations, drugs, technologies, custom per domain. |
| **Relationship mapping** | Auto-discovered + user-defined relationships between entities and entries. |
| **Graph export** | `autoinfo knowledge graph --domain medical-research` — outputs JSON for visualization (D3.js, Gephi). Also GraphML format. |
| **Agent: query graph** | `query_knowledge_graph(entity="IVF", relation="developed_by")` → returns related entities with relationship types and source references. |
| **Incremental building** | Each collection run updates the knowledge graph with new entities and relationships. |

#### F23 — Knowledge Base as Asset ✅

*The accumulated knowledge base has standalone value beyond the collection pipeline.*

| UX Detail | Specification |
|-----------|---------------|
| **Asset principle** | The KB is the primary long-term asset. Real-time feed is temporary; the KB is permanent and grows in value over time. |
| **External KB compatible** | AutoInfo's KB output (`03-Wiki`) is designed to merge into or be consumed by an existing external KB (`docs/archive/kb-pipeline-reference.md`). Same Markdown + YAML frontmatter format, same pipeline tiers. |
| **Obsidian-native** | Markdown files with `[[wiki links]]` are Obsidian-compatible out of the box. User can open `knowledge/` as an Obsidian vault directly. |
| **Entry-level versioning** | Changes tracked per entry (git). Rollback supported. |
| **Shareability** | KB collections exportable: Markdown bundle, JSON, SQLite dump. |
| **Third-party integration** | KB consumable by Obsidian (Markdown + [[links]]), Notion (import), custom apps (JSON API). |
| **REST API (read-only)** | KB queryable via REST API for embedding into other tools. |
| **Monetization potential** | Curated KB collections (e.g., "IVF Research 2026 Weekly Digest") as pre-built assets. Not for v1. |

### 3.6 Phase 6: Output & Asset Creation

> "The knowledge base can produce valuable outputs — reports, tutorials, presentations."

#### F24 — Digest & Report Generation ✅

| UX Detail | Specification |
|-----------|---------------|
| **Human: generate digest** | `autoinfo output digest --domain medical-research --period week` — weekly digest of important findings |
| **Human: custom report** | `autoinfo output report --collection "IVF Protocols 2026" --format markdown` |
| **Agent: generate digest** | `generate_digest(domain="medical-research", period="week", format="markdown")`. |
| **Agent: discover templates** | `list_output_templates(domain="medical-research")` → returns `["digest", "report", "tutorial", "presentation"]`. Agent discovers what outputs a domain supports without trial and error. |
| **Digest structure** | Title, period, domain, summary, key findings (ranked by importance), full entries, trends observed, source list. |
| **Format options** | Markdown, HTML, PDF, JSON. Future: audio (TTS-rendered digest for podcast consumption). |
| **Role-aware content** | Both digest and report accept `target_audience` parameter: `generate_digest(domain, period, target_audience="executive")`. Audience options: `researcher` (technical depth), `clinician` (practical application), `executive` (strategic summary, key takeaways), `student` (educational, foundational). Content depth, terminology, and emphasis adapt to audience. |
| **Audio-ready output** | When `format="audio"`, the system renders digest text through TTS pipeline and outputs MP3 file. Supports podcast-style delivery: intro, section-by-section narration, outro with source credits. Audio format drives new delivery channels (podcast RSS feed, voice messaging via Telegram/WeChat). |

#### F25 — Tutorial & Presentation Generation ✅

| UX Detail | Specification |
|-----------|---------------|
| **Human: generate tutorial** | `autoinfo output tutorial --collection "IVF Protocols 2026" --audience clinician --format markdown` |
| **Human: generate presentation** | `autoinfo output presentation --topic "Latest IVF Research" --slides 10` |
| **Agent: generate tutorial** | `generate_tutorial(collection_id="...", target_audience="clinician")`. |
| **Tutorial structure** | Learning objectives, core content (sourced from KB), key takeaways, further reading (linked KB entries). |
| **Presentation structure** | Title slide, agenda, key finding slides (each sourced from KB), summary, references. Exportable as Markdown (Marp/slides) or PPTX. |
| **Audience adaptation** | Content depth adapts to audience: `researcher` (technical), `clinician` (practical), `executive` (strategic), `student` (educational). |

#### F26 — Export & Interoperability ✅

| UX Detail | Specification |
|-----------|---------------|
| **Export formats** | JSON, Markdown (with YAML frontmatter), CSV, PDF, SQLite dump, GraphML. |
| **Export scope** | Single entry, collection, domain, or full KB. |
| **Import** | Import from supported formats (JSON, Markdown with frontmatter, OPML for source lists). |
| **External tool integration** | Obsidian (Markdown with `[[wiki links]]`), Anki (flashcard export for language learning), JSON API for custom integrations. |
| **Agent: export** | `export_kb(format="obsidian", collection_id="...")` — returns file path or content. |

#### F27 — Product Delivery ✅

| UX Detail | Specification |
|-----------|---------------|
| **Delivery channels** | Multiple channels supported: SMTP email (HTML+plain MIME multipart), webhook push (HTTP POST per-item), REST API (FastAPI CRUD), local file output, bulk export. Future: RSS feed delivery (scheduled feed generation, subscribable by RSS readers and AI agents), agent push (webhook callback to agent endpoint for proactive agent notification). |
| **Scheduling mechanism** | External crond calls `autoinfo cron run`. No built-in scheduler. Two schedule types: `collection` and `digest`. |
| **Configurable cadence** | Daily/weekly/monthly digests. Per-domain or per-collection. |
| **RAW product delivery** | REST API endpoints for raw feeds per domain/topic/time; webhook streams for real-time item push; bulk export (JSON, CSV, SQLite). |
| **PROCESSED product delivery** | Scheduled digest emails (SMTP), thematic report push (webhook), alert streams (configurable thresholds per topic). |
| **Agent: manage delivery** | `send_email_digest(domain, period, recipients)`, `set_domain_webhooks(urls)`, `list_schedules()`, `add_schedule(type="digest", ...)`. |
| **RSS delivery channel** | `export_kb(format="rss")` generates RSS/Atom feed for any domain/topic. Feeds are subscribable by humans (RSS readers, podcast apps) and AI agents (feed polling). Scheduled RSS feed generation via cron: `add_schedule(type="rss", domain="medical")`. Audio-capable RSS feeds (podcast RSS) drive podcast distribution. |
| **Agent push delivery** | Agent registers a webhook callback URL: `set_agent_callback(url, events=["new_digest", "new_report"])`. AutoInfo pushes structured JSON to the callback when a product is generated for a subscribed topic. Enables the "agent subscription" pattern: agent registers interest, AutoInfo pushes product when ready. |
| **Newsletter recipient control** | `send_email_digest` accepts per-recipient configuration: `recipients=[{email, name, format_preference}]`. No per-subscriber segmentation in v1 — all recipients receive same content. Per-recipient targeting deferred to v2. |

#### F28 — RAW Product Generation (NEW) ✅

| UX Detail | Specification |
|-----------|---------------|
| **Definition** | RAW products are the collected information itself — original papers, reports, articles — delivered as-is to paying customers. |
| **RAW feed per domain** | REST API endpoint provides structured access to all collected items per domain/topic/time range. |
| **RAW bulk export** | CLI `autoinfo output export --domain X --format json/csv/sqlite` and MCP `export_kb()` for full data dumps. |
| **RAW real-time stream** | Webhook push (per-item on collection) for live feed consumption. |
| **Source traceability** | Every RAW item includes full provenance: `source_url`, `source_type`, `source_platform`, `collected_at`. |
| **RSS Feed as RAW product** | `export_kb(format="rss", domain="...", topic="...")` — generates RSS/Atom feed XML for any domain/topic/collection. Feed can be subscribed to by humans (RSS readers) or consumed programmatically by AI agents. |
| **Agent: serve RAW product** | `search_knowledge_base()`, `get_kb_entry()`, `export_kb(format="json"|"rss")`, webhook push on collect. |
| **Agent-native RAW delivery** | Agent serves RAW items directly in conversation via MCP tool output. User queries "what's new in medical research" → agent calls `search_knowledge_base()` → returns structured results with source citations. No separate delivery channel needed. |
| **Agent-native JSON format** | `generate_digest(domain, period, format="agent")` returns structured JSON-LD optimized for LLM re-consumption. Schema includes: `@context`, `@type: "KnowledgeDigest"`, `uuid`, `generated_at`, `domain`, `period`, `entries: [{uuid, title, tl_dr, source_url, source_platform, collected_at, relevance_score, confidence_score, entities: [{name, type, relation}], key_points: [str], full_text_summary, citations: [{source, url, accessed_at}]}]`, `trends: [{topic, direction, evidence}]`, `metadata: {entry_count, total_tokens, generation_model, quality_gates: [{name, passed}]}`. This format enables agents to parse, re-synthesize, store in their own KB, or combine with other data sources. |

#### F29 — PROCESSED Product Generation (NEW) ✅

| UX Detail | Specification |
|-----------|---------------|
| **Definition** | PROCESSED products are value-added, synthesized outputs — digests, reports, tutorials, presentations, alert streams. |
| **Digest bundles** | Scheduled (daily/weekly) synthesis of important findings per domain. LLM-generated with source citations. Delivered via SMTP email or webhook. |
| **Thematic reports** | On-demand or scheduled deep-dive reports on specific topics. Structured: executive summary, findings, analysis, references. |
| **Alert streams** | Configurable threshold-based notifications: new items matching topic → push to subscriber via webhook or email. |
| **Custom instructions** | `generate_digest(domain, period, custom_instructions="focus on clinical trials")` — LLM adapts output to subscriber preferences. |
| **Audience adaptation** | Content depth adapts to audience: `researcher` (technical), `clinician` (practical), `executive` (strategic), `student` (educational). |
| **RSS Feed as PROCESSED product** | `export_kb(format="rss", product_type="processed", domain="...")` — generated RSS feed contains LLM-synthesized digest entries rather than raw collected items. Enables agent and human subscription to curated PROCESSED content. |
| **Agent: generate PROCESSED** | `generate_digest()`, `generate_report()`, `generate_tutorial()`, `generate_presentation()`, `localize_content()`. All accept format, audience, custom_instructions params. |
| **Agent-native PROCESSED delivery** | Agent generates PROCESSED products and delivers them directly in conversation via MCP tool output. User says "给我这周的AI商业情报摘要" → agent calls `generate_digest(domain="ai-commercial", period="week")` → returns structured digest as tool result. No separate email client or webhook needed. Agent also proactively pushes: "本周AI商业有新动态，需要我生成简报吗？" |
| **Stored preference integration** | `UserProfile.delivery_preferences` (F36) feeds into PROCESSED generation: preferred format, timezone, quiet hours, max daily digests, channel priority. When generating for a specific end user, `generate_digest(user_id=usr_xxx)` reads preferences from the user profile and applies them automatically — no per-call `custom_instructions` or `format` needed. User preferences serve as defaults; per-call parameters override them. |

#### F30 — Subscription & Billing Infrastructure 🟡

| UX Detail | Specification |
|-----------|---------------|
| **Current status** | Partially implemented. Stripe integration (`create_checkout_session`, `handle_webhook`, subscription status), freemium access gating (`check_access()` in `billing.py`, enforced in `output.py`), and usage metering (CostMeter in `cost.py`) are coded. Stripe webhook REST endpoint and stripe-mock dev setup are pending. |
| **Feature gating** | Partially implemented: `check_access()` enforces free/premium/enterprise tiers in `output.py` for `generate_digest`/`generate_report`. MCP tool layer does not enforce gating (user_id optional). |
| **Usage metering** | Implemented: CostMeter tracks LLM tokens, storage, API calls per domain/user. `get_enduser_usage()` and `get_enduser_invoice()` map internal units to billable line items. |
| **Billing integration** | Partially implemented: Stripe checkout sessions and webhook handling coded in `billing.py`. No Stripe webhook REST endpoint exists. stripe-mock dependency not set up for dev. CostMeter not wired to create actual Stripe invoices/charges. |
| **Delivery tracking** | Implemented: DeliveryLog per subscription with SLA tracking, bounce handling, retry chain. |
| **Customer portal** | CLI-based portal exists (`autoinfo portal preferences|history`). Web-based portal not implemented. |

### 3.7 Phase 7: Monitor

> "I can see what's been collected and how the system is doing."

#### F31 — Collection Overview ✅

| UX Detail | Specification |
|-----------|---------------|
| **Human: status** | `autoinfo status` — summary: items collected today/this week, new KB entries, source health by domain. |
| **Agent: overview** | `get_collection_stats(period="week")` → `{domains: [{name, items_collected, items_new, kb_entries_added, source_health}]}`. |
| **Agent: diff since last run** | `get_collection_diff(domain="medical-research", since_collection_id="...")` → `{new_items: [{id, title, source, collected_at}], total_new: 15, from_collection: "2026-07-19T08:00:00Z", to_collection: "2026-07-20T08:00:00Z"}`. Agent queries "what changed since last time?" in one call instead of comparing lists manually. |
| **Proactive reporting** | Agent periodically summarizes: "本周医学领域收集 45 篇论文，新增 KB 12 条。AI商业领域 23 条案例。" |
| **Status per source** | `healthy`, `degraded` (slow/incomplete), `error` (unreachable), `paused` (user-disabled). |

#### F32 — Source Health Monitoring ✅

| UX Detail | Specification |
|-----------|---------------|
| **Automatic health check** | Each collection run tests source reachability. Degraded sources logged. |
| **Human: source health** | `autoinfo sources health` — all sources with status, last successful fetch, error history, response time. |
| **Agent: source health** | `get_source_health(source_id="pubmed")` → `{status, last_success, error_count, avg_response_time_ms}`. |
| **Alert on failure** | 3 consecutive failures → agent proactively reports. |

### 3.8 Phase 8: Iterate

> "I can improve the system without breaking existing behavior."

#### F33 — Source Handler Isolation ✅

| UX Detail | Specification |
|-----------|---------------|
| **Isolation guarantee** | Each source handler is independent. Adding a new handler doesn't affect existing ones. One source failing doesn't block others. |
| **Handler pattern** | Source handlers implement `BaseSourceHandler` interface. New source type = new class + register. |
| **Failure isolation** | Timeout or error in one source does not crash collection pipeline. Errors logged, source skipped. |

#### F34 — Forward Compatibility ✅

| UX Detail | Specification |
|-----------|---------------|
| **Scope: v1** | New code can read old KB data. KB entry schema (YAML frontmatter + body) is stable. |
| **Readability guarantee** | KB format, collection output format, and config schema are versioned. New versions maintain backward compat. |
| **Breaking changes** | If structural changes necessary: (1) deprecation period with dual-format support, (2) migration tool. |

#### F36 — End User Profile & Subscription Registration ✅

| UX Detail | Specification |
|-----------|---------------|
| **End User identity** | End User = Paying Customer (same person). No distinction between "consumer" and "payer" — the subscriber pays for and consumes the product. |
| **Profile fields** | `user_id`, `name`, `email`, `telegram_id` (optional), `wechat_oa_openid` (optional), `wechat_work_userid` (optional), `dingtalk_userid` (optional), `discord_userid` (optional), `preferred_locale` (zh/en), `timezone`, `created_at`, `updated_at` |
| **Subscription intent fields** | `required_domains: list[str]` — which domains the user subscribes to (mandatory). `optional_platforms: list[str]` — delivery channels the user enables (empty = default channel only). Budget range or tier preference (free vs RAW Pro vs PROCESSED Pro vs Enterprise). |
| **CRUD** | MCP tools: `create_end_user`, `get_end_user`, `update_end_user`, `delete_end_user`, `list_end_users`. CLI equivalents for human direct-users. Bulk import for onboarding. |
| **Validation** | At least one delivery channel must be configured. At least one domain must be subscribed. Email is mandatory (fallback channel). |

#### F37 — Multi-Channel Delivery Configuration ✅

| UX Detail | Specification |
|-----------|---------------|
| **Supported channels** | Email (mandatory), Telegram Bot, WeChat Official Account, WeChat Work, DingTalk, Discord Bot |
| **Channel capability** | Email — Rich HTML, plain text fallback, attachments (PDF digests), threading by subject. Telegram — Markdown message, inline buttons for navigation, file uploads. WeChat OA — Rich article (图文消息), template message. WeChat Work — Markdown message, file upload, interactive card. DingTalk — Markdown message, action card, feed card. Discord Bot — Embed message, file attachment, slash command interaction. |
| **Per-channel opt-in** | End user selects which channels to activate. Each channel has its own configuration (e.g., Telegram chat_id, WeChat OA openid). Agent validates reachability before activation. |
| **Default channel** | Email is always active as the fallback delivery channel. At least one channel must remain active at all times. |
| **Product-to-channel mapping** | Certain products route to specific channels by type: short alerts → Telegram/WeChat Work/DingTalk (instant), daily digests → Email + optional push channel, weekly reports → Email (primary) + optional secondary channel. Configurable per subscription. |
| **Channel capacity limits** | Per-channel rate limits: Telegram (30 msg/s per bot), WeChat OA (unlimited via template), WeChat Work (unlimited), DingTalk (unlimited), Discord (5 msg/s per webhook). Agent queues and batches deliveries respecting each platform's constraints. |

#### F38 — End User Lifecycle State Machine ✅

| UX Detail | Specification |
|-----------|---------------|
| **States** | `trial` → `active` → `suspended` → `cancelled`. Transitions: `trial→active` (payment confirmed), `active→suspended` (payment failed / grace period), `active→cancelled` (explicit cancellation), `suspended→active` (payment resolved), `suspended→cancelled` (grace period expired). |
| **Trial period** | Configurable duration (default: 14 days). Full product access during trial with watermark/attribution on outputs. Direct User (agent) can extend trial per end user. |
| **Grace period** | 7 days after payment failure. Products continue delivery during grace. Alert sent to end user on day 1, 3, 7. After expiry → `cancelled`, all deliveries stop. |
| **State transition hooks** | On `trial→active`: send welcome message via all configured channels. On `active→cancelled`: send goodbye message, offer re-activation link. On `active→suspended`: send payment reminder with link. On `suspended→active`: send confirmation of restored delivery. |
| **Re-activation** | Cancelled users can re-activate within 90 days with full history preserved. After 90 days, profile is archived (data retained per GDPR/privacy policy). |

#### F39 — Delivery Reliability & Logging ✅

| UX Detail | Specification |
|-----------|---------------|
| **Delivery confirmation** | Each delivery attempt records: `subscription_id`, `product_id`, `channel`, `status` (queued/sent/delivered/failed/bounced), `attempted_at`, `confirmed_at`, `error_message`. Email: SMTP delivery receipt. Telegram: API response with message_id. Other channels: webhook callback or API response. |
| **Bounce & failure handling** | Hard bounce (invalid address) → mark channel inactive, alert end user and Direct User. Soft bounce (temporary) → retry 3x with exponential backoff (5min, 15min, 1hr). After 3 consecutive soft bounces → suspend delivery for that channel, attempt fallback channel. |
| **Retry chain** | If primary channel fails: try fallback channel (alternate channel from user's preferences). If all channels fail: queue product for next delivery window, alert Direct User. Never silently drop a product. |
| **Per-subscriber delivery log** | MCP tool `get_delivery_log(subscription_id, period)` — returns delivery history with status per product per channel. Agent can query for troubleshooting. End user can view via portal (F40). |
| **Delivery SLA targets** | P0 (digests, alerts): ≤5min from generation to first delivery attempt. P1 (reports, exports): ≤30min. P2 (bulk): ≤2hr. SLA tracking per subscription, alert agent on repeated SLA misses. |

#### F40 — End User Self-Service Portal ✅

| UX Detail | Specification |
|-----------|---------------|
| **Portal scope** | Web-based self-service: manage profile, update delivery preferences, view subscription status, browse delivery history, download past products, manage billing/payment methods. |
| **Authentication** | Email-based magic link (no password). Link expires in 15 minutes. Session token valid for 7 days. Optional: social login (WeChat OAuth, Telegram OAuth) for push-channel users. |
| **Delivery preference management** | End user can enable/disable channels, update channel IDs (e.g., new Telegram chat_id), change product-to-channel routing preferences, set quiet hours (don't deliver 22:00-08:00 in user's timezone). |
| **Product archive** | All delivered products accessible for 90 days (trial) or subscription duration + 30 days. Searchable by date, domain, product type, channel. Download in original format. |
| **Direct User (agent) overrides** | Agent can update any profile field or subscription state on behalf of the end user (with `updated_by: agent` audit trail). Agent cannot delete an end user — only deactivate. Human Director User can delete. |

### 3.9 Phase 9: Cost Governance

> "I can track and manage the costs of operating AutoInfo, both internally and for end users."

#### F41 — Internal Cost Metering ✅

| UX Detail | Specification |
|-----------|---------------|
| **Cost units tracked** | LLM tokens (input + output per model), storage bytes (KB entries + collections + indexes), API calls (source API calls, LLM API calls). These are internal metering units — NEVER exposed to end users as billing units. |
| **Metering granularity** | Per-domain, per-end-user (if attributable), per-pipeline-stage. LLM costs broken down by task type (extraction, summarization, synthesis, quality check, embedding). |
| **Storage model** | Append-only cost log: `cost_log_id, timestamp, domain, user_id?, stage, cost_unit, quantity, unit_price_estimate, total_cost_estimate`. Written asynchronously to avoid blocking pipeline. |
| **Unit prices** | Pre-populated default prices: DeepSeek Chat $0.15/M input $0.60/M output, Claude Sonnet $3/M input $15/M output, text-embedding-3-small $0.02/M. User can override in config to reflect actual provider pricing. |
| **MCP tool** | `get_cost_report(domain, period, group_by)` — returns aggregated cost breakdown by specified dimension. Agent queries to answer "what did medical research cost me this month?" |
| **CLI** | `autoinfo cost --domain <domain> --period <period> --group-by <dimension>` — human-direct equivalent. |

#### F42 — External Billing Model 🟡

| UX Detail | Specification |
|-----------|---------------|
| **Billing model** | Partially implemented. Hybrid base+overage model specified. CostMeter tracks usage per domain/user. `get_enduser_invoice()` generates invoice-like summaries. Actual Stripe invoice creation and automated charging not connected. |
| **Overage units** | Usage units (items, API calls, storage) tracked in `cost.py`. Not connected to actual overage billing or Stripe metering. |
| **Tier structure** | Free/trial → RAW Pro → PROCESSED Pro → Enterprise tiers specified. `check_access()` enforces in output generation. No subscription tier gating in MCP layer. |
| **Conversion layer** | Partially implemented: CostMeter maps internal costs to product billing units. Conversion factors domain-configurable in `cost.py`. Not wired to Stripe pricing API. |
| **Invoice structure** | Partially implemented: `get_enduser_invoice()` itemizes charges. No automated monthly invoice generation or Stripe Invoice API calls. |
| **MCP tool** | `get_enduser_usage` and `get_enduser_invoice` exist. `get_billing_summary` not implemented. |
| **CLI** | `autoinfo billing` command not implemented. `autoinfo cost dashboard` and `autoinfo cost allocation` provide cost views. |

#### F43 — End-User Cost Dashboard ✅

| UX Detail | Specification |
|-----------|---------------|
| **Dashboard scope** | Per-product itemized cost display within the self-service portal (F40). Shows current period charges, usage vs tier limits, and historical billing. |
| **Default view** | Aggregated: total current charges, next billing date, usage bars (collected items / storage / API calls) against tier limits. No drill-down required for typical users. |
| **Expandable detail** | Click to expand: per-domain charges, per-product-type charges, daily usage timeline. Individual line items for overage (e.g., "450 items over limit @ $0.02 = $9.00"). |
| **Data freshness** | Usage data updated daily (batch). Current-period charges are estimates until period-end invoice is final and binding. |
| **Agent assistance** | Agent can query and explain charges conversationally: "Your medical research digest overage was due to 500 items exceeding your 200-item tier limit." |
| **Cost transparency** | Dashboard always distinguishes between "base fee" (fixed) and "overage" (variable). Never hides overage charges. |

#### F44 — Cost Allocation ✅

| UX Detail | Specification |
|-----------|---------------|
| **Allocation model** | Shared costs (LLM API fees, storage, compute) attributed across domains and end users proportionally. Three configurable strategies: pro-rata (equal split across active domains), usage-based (proportional to consumption per domain), direct (cost definitively tied to specific domain/user). |
| **Per-domain attribution** | LLM extraction costs attributed to domain where item was processed. Shared LLM synthesis (digest generation) allocated across all domains that contributed items. Storage attributed by entry count per domain. |
| **Per-end-user attribution** | Direct costs (items collected for user's subscribed domains) attributed directly to end user. Shared costs (platform overhead, shared synthesis) allocated by subscription tier weight or pro-rata across active users. |
| **Configuration** | `cost_allocation.strategy: usage_based` in global config. Overridable per domain. Allocation method logged in cost audit trail. |
| **MCP tool** | `get_cost_allocation(period)` — returns cost breakdown per domain and per end user with allocation method and rule identifier. |

#### F45 — Budget Alerts & Cost Control ✅

| UX Detail | Specification |
|-----------|---------------|
| **Threshold types** | Absolute spend limit (cost > $X), rate-based (spend/month > $Y), projected overrun (current run-rate extrapolated to period end > $Z). Thresholds per domain, per end user, or global. |
| **Alert channels** | Agent notification (MCP tool return warning with details), email to operator (scheduled, not real-time), dashboard banner in portal. Configurable per threshold rule. |
| **Alert events** | LLM spend approaching monthly budget (80%, 90%, 100% thresholds), storage nearing limit (80%, 90%, 100%), unexpected cost spikes (>2x previous period), end-user overage approaching subscription cap. |
| **Auto-remediation actions** | Configurable per alert: pause collection for domain, switch to cheaper LLM model for non-critical tasks, skip G4 quality check on low-priority items, notify agent with suggested actions. |
| **Configuration** | `cost_alerts:` block in config.yaml. List of alert rules with type, threshold, action, channel. Agent configures via `set_budget_alert` MCP tool. |
| **MCP tool** | `set_budget_alert(domain, threshold_type, value, action)` — configure a budget alert rule. `get_budget_alerts()` — list active alerts with current status. |

### 3.10 Phase 10: Data Privacy

> "I can trust AutoInfo with sensitive or licensed data, knowing it handles sources and user information responsibly."

#### F46 — Source ToS Compliance ✅

| UX Detail | Specification |
|-----------|---------------|
| **Terms disclaimer** | On source creation, agent presents source terms: "PubMed API: research use only, attribution required." User acknowledges before collection begins. Acknowledgment recorded in audit log. |
| **Source classification** | Each source tagged with access tier: **Open** (public data, no restrictions) → full raw content redistributable. **Licensed** (API ToS applies, attribution required) → raw stored internally, only processed output delivered. **Restricted** (paywalled, credential required) → requires user credentials, only aggregated output. **Sensitive** (PII, internal data) → requires data handling acknowledgment, raw content encrypted at rest. |
| **Output control** | Licensed/Restricted/Sensitive sources: only processed output (summaries, structured extracts, aggregated insights) is deliverable to end users. Raw content never leaves internal storage. Enforced at delivery gate D2. |
| **Attribution in outputs** | Generated digests/reports from licensed sources include: "Content derived from [source] under their terms of service." Configurable attribution template per source type. |
| **Compliance checkpoint** | G1 gate extended: source tier classification verified at collection time. If source tier and output tier are incompatible (e.g., trying to deliver raw items from a Licensed source), the pipeline blocks with a clear compliance error. |

#### F47 — Data Deletion & Retention ✅

| UX Detail | Specification |
|-----------|---------------|
| **Soft-delete model** | Delete operations on KB entries mark `status: deleted` with `deleted_at` timestamp and `deleted_reason`. Data NOT physically removed — fully recoverable within retention window. |
| **MCP tools** | `soft_delete_entry(entry_id, reason)` — marks entry as deleted with audit reason. `restore_entry(entry_id)` — recovers entry within retention window. `export_user_data(user_id)` — exports all data for a user (GDPR compliance). |
| **Permanent deletion** | Only `--purge` flag on CLI or explicit Director User action triggers physical deletion. Agent cannot purge. `delete_user_data(user_id, scope)` — available for compliance requests with confirmation step. |
| **30-day auto-cleanup** | Soft-deleted entries older than 30 days auto-purged by scheduled cleanup job (`autoinfo clean --purge-expired`). Configurable retention period per domain. |
| **Retention by subscription tier** | Trial: 14-day post-cancellation retention. Active: full retention for subscription duration + 30 days. Archived: 90-day post-cancellation retention. Purged entries are logged in audit trail with deletion confirmation. |

#### F48 — Audit Logging ✅

| UX Detail | Specification |
|-----------|---------------|
| **Scope** | All agent operations logged: MCP tool calls (actor, tool, parameters, result), pipeline executions (collect/process/deliver per run), configuration changes (domain/source/topic CRUD), user management actions, billing/cost operations. |
| **Log schema** | `audit_log_id, timestamp, actor_type (agent|human|system), actor_id, action, resource_type, resource_id, details (JSON with secrets redacted), result (success|failure|blocked), session_id`. Immutable append-only log. |
| **Agent operations** | Every MCP tool call recorded: tool name, parameters (API keys and tokens redacted), result status, duration. Actor identity from MCP session metadata. |
| **Human operations** | CLI commands logged: command name, arguments (secrets redacted), exit code. Portal actions logged via FastAPI middleware. |
| **Retention** | Audit logs retained 90 days minimum, up to 1 year configurable. Exportable via `query_audit_log()` or CLI `autoinfo audit`. |
| **MCP tool** | `query_audit_log(filters)` — search audit log by actor, action, resource, time range. Returns paginated results with total count. |
| **CLI** | `autoinfo audit --actor <actor> --action <action> --since <date>` — human-direct audit trail browsing with JSON output support. |

### 3.11 Phase 11: Knowledge Lifecycle

> "The knowledge base stays fresh and relevant — old content is gracefully aged, not forgotten."

#### F49 — Per-Domain TTL ✅

| UX Detail | Specification |
|-----------|---------------|
| **TTL definition** | Configurable freshness period per domain: how long a collected item remains "fresh" before being considered "stale." Measured from `collected_at` date. Configurable per topic within domain for finer granularity. |
| **Default TTLs** | Medical research: 180 days (seminal papers remain relevant for months). AI commercial intelligence: 30 days (rapidly evolving landscape). Financial intelligence: 7 days (time-sensitive data). General/default: 90 days. |
| **Configuration** | `ttl_days: 180` in domain config. Optional per-topic override: `topics: [{name: "IVF", ttl_days: 90}]`. |
| **TTL mechanics** | TTL does NOT delete entries. It controls freshness scoring for search ranking and default inclusion in output generation. An entry older than its domain TTL is "stale" but fully accessible via direct lookup or explicit flags. |
| **Expiration behavior** | Stale entries excluded from digest/report generation by default. Agent can explicitly include with `--include-stale` flag. Stale entries remain searchable but demoted (F51). |

#### F50 — Versioned Re-collection ✅

| UX Detail | Specification |
|-----------|---------------|
| **Version model** | Same `source_url` collected again → new version created automatically. Previous version retained with full history. Version tracking via git (already exists for 03-Wiki, extends to 01-Raw). |
| **Version metadata** | Each KB entry tracks: `version: int` (starting at 1), `previous_version_id: UUID?` (link to prior version), `collected_at: datetime`, `updated_at: datetime`. Frontmatter includes all version fields. |
| **Re-collection flow** | Collection pipeline detects existing entry with same `source_url` → creates versioned Raw entry (`knowledge/<domain>/01-Raw/<collection>/<slug>_v2.md`) → links to previous version in frontmatter (`previous_version: <uuid-v1>`). |
| **Version comparison** | MCP tool `compare_versions(entry_id, v1, v2)` — returns structured diff: title changes, summary changes, key point additions/removals. Agent uses to highlight "what changed since last collection." |
| **History pruning** | Retain last N versions per entry (configurable, default: 10). Older versions archived to compressed storage after 90 days. Never automatically deleted without explicit purge. |

#### F51 — Stale Content Handling ✅

| UX Detail | Specification |
|-----------|---------------|
| **Stale marking** | Entries past domain TTL are automatically marked `freshness: stale` with `staleness_date: <date>`. Marked during processing pipeline or on-demand via `refresh_staleness()` MCP tool. |
| **Search demotion** | Stale entries ranked lower in hybrid search. Freshness score contributes 20% to overall relevance ranking. Configurable via `search.freshness_weight: 0.2` in domain config. |
| **Preservation principle** | Stale entries are NEVER deleted. They remain fully accessible via direct entry lookup, explicit search with `--include-stale`, or archived KB view. User or agent must explicitly delete. |
| **Default visibility** | Standard views (digest generation, summary lists, API feeds) exclude stale entries by default. `--include-stale` flag overrides. Admin views display stale entries with visual indicator (e.g., 🟡 stale badge). |
| **Re-fresh on re-collection** | When same source is collected again (F50), the new version supersedes the old. The old entry's staleness status becomes irrelevant — it is superseded rather than stale. |

#### F52 — Domain Decay Metrics ✅

| UX Detail | Specification |
|-----------|---------------|
| **Staleness ratio** | `stale_entries / total_entries` per domain. Measures what fraction of the domain knowledge base is past its TTL. |
| **Avg remaining TTL** | Average days until entries in domain go stale: `sum(ttl_remaining_days) / total_entries`. Negative values indicate entries past their TTL. |
| **Collection freshness** | Days since domain was last collected: `now() - max(collected_at)`. Indicates whether the domain is being actively maintained. |
| **Decay grade** | Composite of staleness ratio + collection freshness: Green (healthy), Yellow (aging), Red (stale). Displayed in `autoinfo status --domains` and MCP `get_collection_stats()`. |
| **Agent alert** | When staleness ratio exceeds configurable threshold (default: 50%), agent proactively suggests re-collection: "Medical research domain is 60% stale. Recommend re-collection." |
| **MCP tool** | `get_domain_decay(domain)` — returns staleness ratio, avg remaining TTL, decay grade, and suggested actions. |

#### F53 — Cross-Collection Dedup & Merge ✅

| UX Detail | Specification |
|-----------|---------------|
| **URL dedup across runs** | Same source URL collected in different runs → detected via exact URL match. Existing entry gets versioned update (F50). |
| **Cross-source similarity detection** | Items from different sources covering same content → detected via: (1) title TF-IDF cosine similarity > 0.85, (2) content sentence-level Jaccard similarity > 0.7. Flagged as potential cross-source duplicates. |
| **LLM-assisted merge** | When cross-source duplicates confirmed, agent can invoke `merge_items(primary_id, secondary_ids, mode)` → LLM consolidates metadata (combines sources, reconciles field differences, preserves both source provenance URLs). |
| **Merge result** | New KB entry with `merged_from: [uuid1, uuid2]`, `sources: [source1, source2]`, consolidated title/summary/key points, combined entity list. Original entries marked `status: superseded` with `superseded_by: new_uuid`. |
| **Trust boundary** | Merged entries are Draft-tier (require human promotion to Wiki). Agent cannot auto-merge into Wiki. Merge decision is logged in audit trail with full rationale. |
| **MCP tools** | `find_similar_items(entry_id, threshold)` — scan KB for similar entries by title + content similarity. `merge_items(primary_id, secondary_ids, mode)` — merge with auto (LLM-driven) or manual (keep primary) mode. |

### 3.12 Phase 12: Operational Observability

> "I can see what the system is doing, trace any item through the pipeline, and diagnose issues efficiently."

#### F54 — Structured Pipeline Logging ✅

| UX Detail | Specification |
|-----------|---------------|
| **Log format** | JSON structured log lines, one per pipeline event. Written to `~/.autoinfo/logs/pipeline-YYYY-MM-DD.json` with daily rotation. |
| **Log schema** | `{"timestamp": ISO8601, "level": "INFO"|"WARN"|"ERROR", "trace_id": "uuid", "stage": "collect"|"process"|"deliver", "domain": "medical", "source": "pubmed", "item_id": "uuid?", "action": "...", "duration_ms": 1234, "status": "success"|"failure", "error": null, "metadata": {...}}` |
| **Stage coverage** | Collect: item fetched from source, dedup result, cache written. Process: extraction start/complete, each quality gate result (pass/fail/retry with reason), KB write confirmation. Deliver: product generation, per-channel dispatch attempt, delivery confirmation or failure. |
| **Log level control** | Configurable per stage: `logging.collect.level: DEBUG`, `logging.process.level: INFO`. Default: INFO. DEBUG includes LLM request/response payloads (prompts, completions). |
| **Viewing** | `autoinfo logs --stage collect --domain medical --since 1h` — tail/filter structured logs with colorized output. `--json` for machine parsing. `--follow` for live tail. |
| **Retention** | 30 days of pipeline logs retained. Older logs automatically archived or deleted (configurable). |

#### F55 — Per-Item Traceability ✅

| UX Detail | Specification |
|-----------|---------------|
| **Trace ID** | UUID generated at collect time for each collected item. Propagated through entire pipeline: collect → cache → extract → quality gates → KB entry → product generation → delivery channel dispatch. |
| **Trace storage** | Append-only trace log: `trace_id, stage, timestamp, status, duration_ms, metadata`. Indexed by trace_id for sub-millisecond lookup. |
| **Trace visualization** | `autoinfo trace <trace_id>` — displays timeline of a single item's journey: when collected from which source, extraction duration, which gates passed or failed, which KB entry was created, which products included it, delivery status per channel. |
| **Error trace** | If item fails at any pipeline stage: trace includes error type, error message, retry attempts and outcomes, final resolution (skipped/blocked/failed). Failed item traces preserved for post-mortem diagnostics. |
| **MCP tool** | `trace_item(trace_id)` — returns full item trace with all stages, statuses, and timestamps. Agent uses for support: "Why wasn't paper X in yesterday's digest?" → trace shows it failed quality gate G3 (low relevance). |

#### F56 — Enhanced Diagnostics ✅

| UX Detail | Specification |
|-----------|---------------|
| **Command** | `autoinfo doctor --verbose` — comprehensive system diagnostics extending the basic health check. |
| **Verbose output** | Recent pipeline runs (last 10 per domain: collection + processing + delivery), error rates per source per stage (trend over 7 days), latency p95/p99 per stage per domain, cost summary (LLM spend per domain this period), KB health (entry count per tier, stale ratio, storage size in MB). |
| **Data sources** | Aggregated from: audit log (F48), pipeline logs (F54), trace store (F55), cost log (F41). |
| **Health score** | Composite health score (0-100) per domain and overall. Factors weighted: source availability (30%), error rate (25%), pipeline latency (20%), staleness ratio (15%), budget status (10%). |
| **MCP tool** | `diagnose_system(verbose=true)` — when `verbose=true`, returns full diagnostic report as structured JSON instead of basic health summary. |
| **Remediation suggestions** | `doctor --verbose` includes actionable suggestions derived from health data: "PubMed API returned 3 errors in 24h — check API key validity or network connectivity." "Medical research domain is 60% stale — consider re-collection (run `autoinfo collect --domain medical`)." |

#### F57 — Metrics Export ✅

| UX Detail | Specification |
|-----------|---------------|
| **Command** | `autoinfo status --metrics` — exports system health and usage indicators as structured JSON to stdout. |
| **Metrics schema** | `{"timestamp": ISO8601, "domains": [{"name": "medical", "items_collected_24h": 42, "items_processed_24h": 38, "kb_total": 1200, "kb_stale": 180, "avg_ttl_remaining_days": 85, "llm_spend_30d": 28.50, "error_rate_7d": 0.02, "p95_collect_latency_ms": 3400, "p95_process_latency_ms": 8500}], "global": {"total_items": 5200, "total_entries": 2800, "active_users": 5, "total_llm_spend_30d": 45.20, "pipeline_health": "healthy"}}` |
| **Prometheus endpoint** | Optional: `http://localhost:8741/metrics` in Prometheus text format. Feature-gated: `metrics.enable_prometheus: true` in config. Standard metric names (`autoinfo_items_collected_total`, `autoinfo_llm_spend_usd`, etc.). |
| **Use cases** | External monitoring (Grafana dashboards), automated cost tracking, SLA reporting to enterprise customers, capacity planning for storage and LLM budget. |
| **MCP tool** | `get_metrics(domain=None)` — returns metrics JSON for agent consumption. Agent uses for proactive reporting: "This month: 5200 items collected across 5 active domains, \$45.20 total LLM spend." |

### 3.13 Notes on Expectation Numbering

The catalog uses the following identifiers: F01-F06 (Phase 1: Setup), F07-F10b (Phase 2: Domain & Topic Config), F11-F15 (Phase 3: Information Gathering), F16-F19 (Phase 4: Curation & Interaction), F20-F23 (Phase 5: Knowledge Base Building), F24-F30 (Phase 6: Output & Asset Creation), F31-F32 (Phase 7: Monitor), F33-F34 (Phase 8: Iterate), F36-F40 (Phase 8.5: Product & Delivery — note: no F35 in source), F41-F45 (Phase 9: Cost Governance), F46-F48 (Phase 10: Data Privacy), F49-F53 (Phase 11: Knowledge Lifecycle), F54-F57 (Phase 12: Operational Observability). Note that F08 (Custom Sources) and F35 are not separately numbered in the source document — F08 appears as the F07b sub-section's continuation (the unheaded table after F07b's preamble concludes with the add-source UX), and F35 is omitted from the source ordering.

---

Associated spec files:

- [`expectations.md`](./expectations.md) — F01-F57 founder expectation catalog (this file)
- [`pipeline.md`](./pipeline.md) — Collection pipeline, KB pipeline, processing & LLM extraction, import, CEFR, cross-collection dedup & merge
- [`quality-gates.md`](./quality-gates.md) — G0-G5 quality gates, D1-D3 delivery gates: catalog, philosophy, retry strategies, configuration
- [`delivery.md`](./delivery.md) — Output generation, delivery channels, error recovery & resilience, end user lifecycle
- [`operations.md`](./operations.md) — Cost governance, data privacy & compliance, knowledge lifecycle (TTL, versioning, decay), observability
- [`mcp-tools.md`](./mcp-tools.md) — Complete MCP tool inventory (114 tools across 32 categories)
- [`data-models.md`](./data-models.md) — Consolidated data model schemas (Item, ExtractionResult, UserProfile, Subscription, DeliveryLog, CostLog, AuditLog, SystemHealth)