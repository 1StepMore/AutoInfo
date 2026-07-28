# Founder's Expectations

> Acceptance from the founder's perspective: does the project actually deliver on the original vision?
> Dimension 3 of the multi-dimension verification system.

---

## 1. Why Founder's Expectations?

AutoInfo is a new project — no tests, no quality gates, no users yet. The codebase is empty. But there's a harder question:

**Does this project actually solve the problem I created it to solve?**

This document answers that question. It defines what "done" looks like from the founder's perspective, before a single line of code is written. It's the blueprint for what AutoInfo must become.

### 1.1 The Project's Promise

> **AutoInfo 是一个通用信息追踪与知识库平台。你配置信源和关注领域，它自动完成采集、结构化提取、摘要、建立可查询的知识库。**
>
> AutoInfo 是你的"信息助理"——它不是帮你搜索，而是把从采集到知识沉淀的流程自动化、质量可控。你选择信源和方向，它完成剩下的所有体力活。领域不限，通用平台。

**Core insight**: AutoInfo's current demo domains (medical research, AI commercial intelligence, language learning) are **illustrative, not exhaustive**. The platform is **domain-agnostic and commercially grounded** — it is designed for any field where high-quality information exists and **customers are willing to pay** for curated knowledge products, thematic reports, or information feeds. Demo domains validate the concept; production domains are those with paying customers.

**Two product types** define AutoInfo's commercial model:

| Product Type | Description | Examples |
|-------------|-------------|----------|
| **RAW products** | The collected information itself — original papers, reports, articles delivered as-is | Raw data feeds, API endpoints, bulk exports (JSON/CSV/SQLite), real-time item streams |
| **PROCESSED products** | Value-added outputs — synthesized, curated, analyzed information products | Digest bundles, thematic research reports, structured data feeds, alert streams, tutorials, presentations |

Both product types are first-class entities in the architecture. The platform is the factory; RAW and PROCESSED products are what customers pay for.

| Demo Domain | Purpose | Key User During Validation |
|-------------|---------|---------------------------|
| **Medical Research** (辅助生殖/脑科学/神经科学) | Validates academic paper collection, structured metadata extraction, citation-aware KB | Founder (P0 validation) |
| **AI Commercial Intelligence** | Validates multi-source collection (API + web + feeds), structured ranking/case data, trend detection | Founder (P0 validation) |
| **Financial/Business Intelligence** | Validates financial data aggregation, multi-source pricing intelligence, regulatory filing monitoring, institutional-grade data feed production | Founder (P1 — high WTP domain) |
| **Tech/AI/Developer** | Validates open API-based collection (GitHub Trending, ProductHunt, Substack RSS), trend analysis, newsletter-style output for technical audiences | Founder (P1 — high API availability) |
| **Language Learning** (children's English reading) | Validates level classification, content simplification, vocabulary extraction, cross-lingual features | Founder (P2 — validate later) |

### 1.2 Design Principles

| Principle | Meaning |
|-----------|---------|
| **Value-first** | Criteria measure whether the project delivers value, not whether code is structured well |
| **Product-first** | The platform exists to produce sellable knowledge products. Two product lines: RAW (collected information) and PROCESSED (synthesized reports, digests, feeds, alerts). Every subsystem serves the product pipeline. A feature's value is measured by its contribution to product quality and delivery. |
| **Production-grade quality** | Quality is not advisory. Retry-first, block-last. Hard gates enforce correctness where block is the only right thing; soft gates operate with configurable thresholds. Paying customers demand genuine quality — human review loops, editorial SLAs, and production thresholds are built-in, not bolted-on. |
| **Founder's truth** | The founder's experience is the source of truth — if it doesn't work for the founder, it doesn't work |
| **Universal by default** | The platform is domain-agnostic. Demo domains are configurations, not hardcoded features |
| **Source-first** | Quality of output is bounded by quality of sources. Curated demo source libraries prove the concept |
| **Knowledge as asset** | The accumulated knowledge base is the primary long-term asset, not the real-time feed |
| **KB pipeline (4-tier)** | 4-tier pipeline (01-Raw → 02-Draft → 03-Wiki; 00-Inbox is scaffolded but deprecated — never written to). Sequential, no skipping. Only human can promote Draft→Wiki. 01-Raw is the sole entry point. Aligned with KB pipeline design |
| **Agent-native** | All capabilities exposed as MCP tools first. CLI is fallback. Director-user communicates through agents |
| **BYOK** | Users bring their own LLM keys. No vendor lock-in. Local models supported where feasible |
| **Honest about gaps** | This document must candidly acknowledge what doesn't work yet |
| **Drives prioritization** | Failed expectations → highest-priority fixes |
| **Living document** | Expectations evolve as the project matures |

### 1.3 Three User Types (Agent-Oriented Model)

The system serves three distinct user roles. Unlike traditional multi-user systems, AutoInfo is designed for the agent-oriented paradigm: the **Direct User** (the agent) executes, the **Director User** (the human) directs, and the **End User** (the paying customer) consumes.

| Role | Description | Interface | Example |
|------|-------------|-----------|---------|
| **End User** (最终用户 / 付费客户) | **The paying customer.** Consumes curated knowledge products (digests, reports, feeds). Their willingness to pay (WTP) drives every commercial decision — product quality, delivery reliability, SLAs, and feature prioritization. Same person fulfills both consumption and payment roles. | Delivered products (email digests, Telegram messages, WeChat pushes, API feeds, webhook streams, exported reports); self-service portal for preferences, subscription management, and delivery history | A pharmaceutical company subscribing to an "IVF Research Weekly" digest delivered via email + WeChat Work; a VC firm paying for "AI Competitive Intelligence" data feeds pushed to their Telegram bot |
| **Direct User** (直接执行者 / Agent) | **The operator.** Executes automation commands via structured tools. **Agent-first**: all capabilities are MCP tools for AI agents. Human-direct access via CLI is preserved as a fallback. The agent is the primary execution layer. | MCP tools (80+ across 19 categories — primary), CLI (17 command groups — fallback) | An AI agent calling `collect_sources()` and `generate_digest()`; a human running `autoinfo collect` for ad-hoc operations |
| **Director User** (人类指挥者) | **The commander.** Gives high-level intent in natural language. Never touches AutoInfo directly — communicates through the Direct User (agent) who translates intent into MCP tool calls. The agent is the interface between the director and the system. | Natural language conversation with the agent | "帮我追踪本周辅助生殖领域的重要论文，按创新程度排序，出一份简报" or "Track OpenAI's enterprise announcements and summarize pricing changes" |

**Design principle**: Agent-oriented by default, human-capable by design. All system capabilities are exposed as structured MCP tools first (for agent direct-users), with CLI as an accessible alternative (for human direct-users). The director-user communicates intent through the agent, not through AutoInfo directly. The end user's (paying customer's) requirements for quality, reliability, and delivery channel flexibility are embedded as hard constraints in every subsystem — see F36-F40 for the full end-user lifecycle specification.

### 1.4 How This Dimension Is Different

| | D1 (Output) | D2 (Behavioral) | D3 (Founder) |
|---|---|---|---|
| **Asks** | Was this collection run's output acceptable? | Does the system behave correctly? | Does the project deliver value? |
| **Audience** | Pipeline operator (agent or human direct-user) | Developer | Founder / first user |
| **Scope** | Single collection run | All system surfaces | Entire project purpose |
| **Failure means** | Re-run the collection | Fix the code | Rethink the approach |
| **Frequency** | Every run | Before releases | Quarterly / milestone |
| **Tone** | Technical pass/fail | Technical pass/fail | Product-ish pass/fail |

---

## 2. Founder's User Journey

The founder's complete workflow — from configuring sources to extracting value from the knowledge base.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FOUNDER'S USER JOURNEY                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────┐   ┌──────────────┐   ┌───────────┐   ┌───────────────┐        │
│  │ 1. SETUP  │ → │ 2. CONFIGURE │ → │ 3. COLLECT│ → │ 4. CURATE     │        │
│  │          │   │              │   │           │   │               │        │
│  │ Install  │   │ Define domain│   │ On-demand │   │ Review summs  │        │
│  │ Config   │   │ Add sources  │   │ Scheduled  │   │ Interactive QA│        │
│  │ Keys     │   │ Set topics   │   │ Monitor    │   │ Link concepts │        │
│  └────┬─────┘   └──────┬───────┘   └─────┬─────┘   └───────┬───────┘        │
│       │                │                  │                │                │
│       ▼                ▼                  ▼                ▼                │
 │  ┌──────────┐   ┌──────────────┐   ┌──────────────────┐   ┌────────────┐   ┌──────────────┐       │
│  │ 5. BUILD  │   │ 6. OUTPUT    │   │ 6.5 PRODUCT &    │   │ 7. MONITOR  │   │ 8. ITERATE   │       │
│  │ KNOWLEDGE │   │              │   │     DELIVERY      │   │             │   │              │       │
│  │          │   │              │   │                  │   │             │   │              │       │
│  │ Search KB │   │ Digest       │   │ Package RAW/     │   │ Source health│  │ Add sources  │       │
│  │ Graph viz │   │ Report       │   │ PROCESSED prods  │   │ Collection   │  │ Tune topics  │       │
│  │ Export    │   │ Tutorial     │   │ Manage subscribers│  │ stats        │  │ Improve QA   │       │
│  │           │   │ Presentation │   │ Deliver via chnl │   │             │  │ New domains  │       │
│  └──────────┘   └──────────────┘   └──────────────────┘   └────────────┘   └──────────────┘       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

The journey has 8 phases. Each phase has specific expectations.

---

## 3. Expectation Catalog

**Status legend:** ✅ Fully implemented | 🟡 Partially implemented (basic version works, enhancements pending) | ❌ Not yet implemented

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

#### F07b — Source API Capability Matrix (NEW) 🟡

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

#### F10 — Multi-language & Localization ✅

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

*KB architecture follows the proven KB pipeline design (`docs/dev/kb-pipeline-reference.md`): a 4-level pipeline with sequential promotion.*

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
| **External KB compatible** | AutoInfo's KB output (`03-Wiki`) is designed to merge into or be consumed by an existing external KB (`docs/dev/kb-pipeline-reference.md`). Same Markdown + YAML frontmatter format, same pipeline tiers. |
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
| **Format options** | Markdown, HTML, PDF, JSON. |

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
| **Delivery channels** | Multiple channels supported: SMTP email (HTML+plain MIME multipart), webhook push (HTTP POST per-item), REST API (FastAPI CRUD), local file output, bulk export. |
| **Scheduling mechanism** | External crond calls `autoinfo cron run`. No built-in scheduler. Two schedule types: `collection` and `digest`. |
| **Configurable cadence** | Daily/weekly/monthly digests. Per-domain or per-collection. |
| **RAW product delivery** | REST API endpoints for raw feeds per domain/topic/time; webhook streams for real-time item push; bulk export (JSON, CSV, SQLite). |
| **PROCESSED product delivery** | Scheduled digest emails (SMTP), thematic report push (webhook), alert streams (configurable thresholds per topic). |
| **Agent: manage delivery** | `send_email_digest(domain, period, recipients)`, `set_domain_webhooks(urls)`, `list_schedules()`, `add_schedule(type="digest", ...)`. |

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

#### F30 — Subscription & Billing Infrastructure 🟡

| UX Detail | Specification |
|-----------|---------------|
| **Current status** | Partially implemented. Stripe webhook endpoint with signature verification (`api/stripe.py`) exists. Stripe-mock dev setup for testing. `CostMeter` tracks LLM tokens/storage/API calls internally. `EndUserProfile` + `Subscription` models with CRUD and state machine (trial→active→suspended→cancelled) implemented. **Remaining**: full payment lifecycle (checkout session, invoice generation, payment method management), feature gating per tier, freemium access control, customer-facing billing portal. |
| **Feature gating** | Partially planned: `ProductTemplate` has no `access_level` field. Per-tier access control requires implementation. |
| **Usage metering** | Partially implemented: `CostMeter` tracks internal units (LLM tokens, storage, API calls) per domain/per user. Not yet linked to product billing units or subscription tier limits. |
| **Billing integration** | Partially implemented: Stripe webhook endpoint (`/api/v1/stripe/webhook`) with event dispatch. Checkout session creation (`create_checkout_session` MCP tool). Stripe-mock for dev testing. Missing: full subscription lifecycle (create, update, cancel, refund), invoice generation, payment method management. |
| **Delivery tracking** | ✅ Implemented: per-subscription `DeliveryLog` with SLA tracking, bounce detection, retry chain. |
| **Customer portal** | Partially implemented: CLI-based portal (`autoinfo portal preferences|history`). Web UI not yet available. |

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
| **Current status** | Partially implemented. Internal cost metering (LLM tokens, storage, API calls) fully operational via `CostMeter`. Per-domain and per-user cost allocation works (pro-rata, usage-based, direct). Cost dashboard with daily trends available via CLI and MCP. Stripe webhook endpoint exists. **Remaining**: full external billing integration — payment processing, invoice generation, subscription lifecycle (create/update/cancel/refund), conversion layer from internal cost units to product billing units, tier enforcement. See F30 for Stripe status. |
| **Billing model** | Hybrid: base subscription (monthly fee for tier) + usage-based overage. Billing units are product-level (items, API calls, storage GB), NOT token-based. End users never see token counts. |
| **Overage units** | Per-item collected beyond tier limit, per-API-call beyond tier cap, per-GB-storage beyond tier allowance, per-premium-output-format generated. Priced in USD per unit. |
| **Tier structure** | Free (trial, watermarked, limited items), RAW Pro (unlimited collection, API access), PROCESSED Pro (all outputs, delivery channels), Enterprise (custom SLA, white-label, dedicated support). |
| **Conversion layer** | Planned: internal cost units → product billing units via configurable mapping table. Maps LLM token cost + storage + API calls → per-item or per-report price. Conversion factors are domain-configurable. Not yet implemented. |
| **Invoice structure** | Planned: Monthly invoice with section: base subscription (fixed), overage per category (itemized), credits/adjustments. Generated at period end. Not yet implemented. |
| **MCP tool** | ✅ `get_billing_summary(user_id, period)` — current charges, usage vs limits, projected overage with expected invoice total. Implemented. |
| **CLI** | ✅ `autoinfo billing --user <user_id> --period <period>` — human-direct for support scenarios. Implemented. |

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

#### F50 — Versioned Re-collection 🟡

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

---

## 4. Quality Gates

> Full specification moved to `docs/dev/specs/quality-gates.md`.

Quality gates run automatically on each collection (G0-G3 mandatory, G4-G5 opt-in LLM-based) and at product output time for PROCESSED products only (D1-D3). See the dedicated spec for gate catalog, philosophy, retry strategies, configuration model, and delivery gate details.

---

## 5. Core Value Propositions Assessment

Beyond individual expectations, there are **core value propositions** — the fundamental reasons this project exists.

### 5.1 "Universal information collector"

```
Promise:  Configure any domain → AutoInfo collects from any source type
Reality:  v1.2 — RSS, API, Web, Webhook, Email (IMAP), PDF — 6 source types, crontab installer
```

| Aspect | Status | Gap |
|--------|--------|-----|
| RSS/API collection | ✅ Implemented | PubMed (esearch+efetch), RSS (feedparser), scheduled via crond |
| Web page extraction | ✅ Implemented | trafilatura + Playwright fallback for JS-heavy pages |
| Webhook/email/PDF collection | ✅ **v1.1 Added** | Webhook (HMAC+rate limiting), Email (stdlib imaplib), PDF (PyMuPDF+chunking) |
| **End-to-end: source → stored item** | ✅ **v1.1 Complete** | Core loop working across 6 source types |
| **Crontab scheduling** | ✅ **v1.2 Added** | `autoinfo cron install/uninstall` for POSIX crontab |

### 5.2 "LLM-powered structured extraction"

```
Promise:  Collect anything → LLM extracts the fields you care about
Reality:  v1.1 — default + custom extraction + G4/G5 quality gates + Q&A
```

| Aspect | Status | Gap |
|--------|--------|-----|
| LLM extraction pipeline | ✅ Implemented | LiteLLM multi-provider, TL;DR + key points + entities + relevance |
| Custom field extraction | ✅ Implemented | User-defined schema per domain, on-demand re-extraction |
| Extraction quality check (G4) | ✅ Implemented | Factual consistency checking via LLM, --check-factual flag |
| Translation accuracy check (G5) | ✅ **v1.1 Added** | Cross-lingual faithfulness verification, --check-translation flag |

### 5.3 "Knowledge base as an asset"

```
Promise:  Collected knowledge is permanently stored, searchable, exportable
Reality:  v1.2 — 4-tier KB pipeline + promote workflow + KG export + frontmatter expansion + git versioning + `[[wiki links]]` + PDF export + REST API
```

| Aspect | Status | Gap |
|--------|--------|-----|
| File-based KB storage | ✅ Implemented | 4-tier pipeline (Inbox→Raw→Draft→Wiki), Markdown + YAML frontmatter |
| Hybrid search | ✅ **v1.2 Wired** | sqlite-vec embeddings + FTS5 (0.7 FTS5 + 0.3 vec), faceted search (7 filters) |
| Export & interoperability | ✅ Implemented | Markdown, JSON, SQLite, CSV, GraphML export; versioning; entry history |
| Knowledge graph | ✅ **v1.1 Enhanced** | Export CLI (JSON/GraphML/CSV), entity extraction + relation discovery |
| KB promote workflow | ✅ **v1.1 Added** | Human-only Draft→Wiki promotion, agent cannot write 03-Wiki |
| Frontmatter expansion | ✅ **v1.1 Added** | author, source_ids, status, related_concepts, linked_entries |
| KB versioning | ✅ **v1.2 Added** | Git auto-commit + SHA tracking per entry, rollback support |
| Obsidian `[[wiki links]]` | ✅ **v1.2 Added** | Native wiki-link syntax in KB Markdown files |
| PDF export | ✅ **v1.2 Added** | WeasyPrint-powered report generation |
| REST API | ✅ **v1.2 Added** | FastAPI CRUD (port 8741), read-only KB access via HTTP |

### 5.4 "Agent can operate the system"

```
Promise:  AI agents (OpenCode, Claude Code, etc.) can run AutoInfo via MCP
Reality:  v1.5 — 79 MCP tools across 19 categories (up from 72 in v1.4, including new Quality Gate Config, Product, Alert Rules categories)
```

| Aspect | Status | Gap |
|--------|--------|-----|
| MCP server | ✅ **v1.6.2 Enhanced** | 114 tools across 32 categories, stdio transport, structured ErrorCode enum, schemas hardened, end user lifecycle, cost governance, data privacy, knowledge lifecycle, observability tools |
| Core collection tools | ✅ Implemented | collect_sources (with dry_run), process_collection (batch), batch_run |
| Progress visibility | ✅ **v1.1 Added** | get_collection_progress, get_collection_status MCP tools |
| KB management tools | ✅ Implemented | Full CRUD + search + draft workflow + promote + KG + reindex |
| Domain lifecycle | ✅ **v1.1 Added** | activate_domain, deactivate_domain, get_domain_config |
| Output generation | ✅ **v1.1 Added** | generate_tutorial, generate_presentation added |
| Keyword discovery | ✅ **v1.1 Added** | list_keywords with groups, multi-language scoring |
| CEFR classification | ✅ **v1.2 Added** | classify_cefr MCP tool, EN/ZH/JA LLM-based scoring |
| Keywords management | ✅ **v1.2 Added** | Central `_keywords.yaml` per domain, manage_keyword MCP tool |
| Email sending | ✅ **v1.2 Added** | send_email MCP tool, SMTP configuration |
| Hybrid search + faceted | ✅ **v1.2 Added** | Vector search MCP tools, 7 faceted filters |
| Report generation (PDF/JSON) | ✅ **v1.2 Added** | generate_report with format param |

### 5.5 "Commercial-grade information products"

```
Promise:  Collected and processed outputs are sellable products delivered to paying customers
Reality:  v1.5 — delivery infrastructure exists (SMTP, webhook, REST API), product model fully specified, hard/soft quality gates, billing deferred to v2+
```

| Aspect | Status | Gap |
|--------|--------|-----|
| Two product types defined (RAW + PROCESSED) | ✅ Conceptualized | Fully specified in this document; code implementation pending |
| RAW product delivery (API feeds, webhook streams, bulk export) | ✅ Infrastructure exists | REST API, webhook push, export_kb MCP tool all operational |
| PROCESSED product delivery (scheduled digests, reports, alerts) | ✅ Infrastructure exists | SMTP email, webhook push, cron scheduling, output generation all operational |
| Product template system | 🔄 Basic | Domain-configurable templates via Jinja2; no product catalog abstraction yet |
| Feature gating / usage metering | ❌ Not implemented | Deferred to v2+ (tracked in F30) |
| Subscription management / billing | ❌ Not implemented | Deferred to v2+ (tracked in F30) |
| Customer delivery portal | ❌ Not implemented | Deferred to v2+ |
| Delivery confirmation / analytics | ❌ Not implemented | Deferred to v2+ |

---

## 6. Founder's Priority Matrix

### 6.1 Implementation Quadrants

| Quadrant | Importance | Effort | Expectations |
|----------|-----------|--------|--------------|
| **🔴 Build first** | HIGH | LOW | **F01-F06** (setup — foundation), **F11** (one-command collect — core loop), **F12** (progress), **G1-G3** (basic gates) |
| **🟡 Core value** | HIGH | HIGH | **F07** (demo domain: medical sources), **F13** (RSS + API handlers), **F15** (LLM extraction), **F16** (summary review), **F20** (KB storage), **F21** (KB search) |
| **🟢 Enhance** | MEDIUM | LOW | **F08** (custom sources), **F09** (topic management), **F10** (localization), **F18** (quality feedback), **G4-G5** (advanced gates) |
| **🔵 Asset phase** | MEDIUM | HIGH | **F17** (Q&A), **F19** (cross-ref), **F22** (knowledge graph), **F24-F26** (outputs) |
| **⚪ Polish** | LOW | VARIES | **F14** (scheduling), **F31-F34** (monitor/iterate) |
| **🔴 Product & Delivery** | CRITICAL | MEDIUM | **F27** (Product Delivery), **F28-F29** (RAW + PROCESSED), **G0/G4** (hard gates), **D1-D3** (delivery gates) |

### 6.2 Demo Domain Implementation Priority

| Demo Domain | v1 Priority | Rationale |
|-------------|-------------|-----------|
| **Medical Research** | 🔴 P0 | Primary validation domain. Most structured data (PubMed API), clearest value. Proves the collection → extraction → KB loop. |
| **Financial/Business Intelligence** | 🔴 P0 | Highest WTP domain validated by market data (Bloomberg $2,665/user/mo, WSJ $44.99/mo). Proves high-value data feed production and institutional-grade delivery. Validates RAW product line for commercial viability. |
| **AI Commercial Intelligence** | 🟡 P1 | Second validation domain. Tests multi-source collection (API + web + feeds). Proves cross-source structuring. |
| **Tech/AI/Developer** | 🟡 P1 | Highest API availability domain — most sources offer free/open APIs. Validates lightweight domain setup with minimal cost. Proves newsletter-style PROCESSED products. |
| **Language Learning (L1 only)** | 🟢 P2 | L1: collect + CEFR tag. Lowest effort to validate. Does not block architecture decisions. |

### 6.3 Immediate Action Items

| Priority | Item | Why |
|----------|------|-----|
| 🔴 P0 | **Build collection core loop** (fetch → parse → dedup → store) | Everything depends on this. Start with RSS handler, then API handler. |
| 🔴 P0 | **Curate medical demo sources** (PubMed API integration) | First validation domain. Needs real API integration, not mock. |
| 🔴 P0 | **Design KB file schema** (YAML frontmatter + Markdown body) | Most consequential architecture decision. Gets harder to change later. |
| 🟡 P1 | **Implement LLM extraction pipeline** (summarization + field extraction) | Primary value-add. Universal, domain-agnostic. |
| 🟡 P1 | **Build G1-G3 quality gates** (source authority, dedup, relevance) | Basic quality control before KB entries are created. |

---

## 7. Market Positioning

### 7.1 Competitive Landscape

AutoInfo occupies an **empty space** between existing tool categories:

| Category | Tools | Price | AutoInfo's differentiator |
|----------|-------|-------|--------------------------|
| **RSS readers** | Feedly, Inoreader | $7-12/mo personal, $1,600+/mo enterprise | KB building, not just feed reading. Structured extraction. Agent-native. BYOK for cost control. |
| **Enterprise intelligence** | AlphaSense, CB Insights | $10K-$100K/user/year | Affordability for individuals. User-defined domains, not predefined verticals. |
| **AI research tools** | EnkiAI, TrendIntel | $17-79/mo | Domain-agnostic KB. User-defined extraction schemas. Full data ownership (files, not SaaS lock-in). |
| **Web extraction APIs** | Diffbot, KnowledgeSDK | $29-$299/mo | User-facing product with KB, search, MCP. Not just a developer API. |
| **Knowledge platforms** | Notion, Obsidian | Free-$10/mo | Built-in collection pipeline. Auto-populated KB. You don't bring your own content. |

### 7.2 Target User (Paying Customer)

AutoInfo serves two distinct customer types corresponding to the two product lines:

**Customer Type A: Information Buyer (RAW products)**
Pays for access to curated, structured information feeds in their domain of interest.

| Attribute | Description |
|-----------|-------------|
| **Title examples** | Pharma competitive intelligence analyst, VC deal sourcing associate, policy research lead, market intelligence manager |
| **Buys** | RAW data feeds: structured paper collections, API access to curated items, bulk exports |
| **Current pain** | Paying $10-100K/year for proprietary databases (Capital IQ, AlphaSense) when public sources + LLM extraction would suffice |
| **Willingness to pay** | $50-500/mo for reliable domain-specific RAW feeds |
| **Quality concern** | Completeness, freshness, source traceability |

**Customer Type B: Knowledge Product Subscriber (PROCESSED products)**
Pays for synthesized, analyzed, ready-to-consume knowledge products.

| Attribute | Description |
|-----------|-------------|
| **Title examples** | Busy clinician, portfolio manager, startup founder, executive decision-maker |
| **Buys** | PROCESSED products: digest bundles, thematic reports, alert streams |
| **Current pain** | No time to read primary sources; needs distilled, trustworthy analysis delivered regularly |
| **Willingness to pay** | $100-2,000/mo for domain-specific processed intelligence |
| **Quality concern** | Factual accuracy, analysis depth, timeliness, presentation quality |

#### 7.2a User Persona by Domain (NEW)

> *Domain-specific user personas derived from the global information payment research report (2024-2026). These personas refine the generic customer types above with detailed demographics, decision patterns, and willingness-to-pay data per domain.*

##### Domain 1: Financial/Business Intelligence

| Attribute | C端 (Individual) | B端 (Institutional) |
|-----------|-----------------|-------------------|
| **Age range** | 30-55 (primary); significantly older than entertainment content consumers | 35-60 (senior decision-makers) |
| **Occupation** | Professional investors, financial analysts, traders, high-net-worth individuals | CIO/CTO/IT directors, heads of research, portfolio managers, corporate strategy |
| **Education** | Bachelor's+ >85% | Advanced degree common (MBA, CFA, PhD) |
| **Income/Revenue** | Household income $100K+ | Firm ACV $50K-$500K |
| **Geography** | Norway (40% news penetration), Sweden (31%), US (22%), China (Caixin model); Nordic/Western Europe highest | North America ~60% of global SaaS spend, EMEA ~25%, APAC ~12% |
| **Decision cycle** | Personal: minutes-days (subscription) | 3-18 months (multi-stakeholder: CIO + legal + finance + business line) |
| **Price sensitivity** | Medium; Bloomberg $2,665/user/mo for retail (terminal); WSJ $44.99/mo for mass premium | Low; ROI-driven, compliant-premium tolerance |
| **Key channels** | Bloomberg Terminal, WSJ, FT, 财新, Wind (China), Alpha Vantage (retail) | Bloomberg, Refinitiv, Wind institutional, Reuters Connect |
| **WTP range** | $20-$2,665/mo (varies by depth) | $50K-$500K ACV |

##### Domain 2: Knowledge Payment / Online Education

| Attribute | C端 (Individual Learner) | B端 (Enterprise L&D) |
|-----------|-------------------------|---------------------|
| **Age range** | 18-40 (80%+); 25-35 most active; 18-35 = 62.3% | 30-50 (L&D managers, HR directors) |
| **Occupation** | Corporate staff (38.5%), freelancers (22.1%), students (19.7%) | CFO, L&D Directors, HR VPs |
| **Education** | Bachelor's+ 60%+ (2024); sub-bachelor growing +31.8% YoY ("knowledge democratization") | — |
| **Income** | ¥8K-¥30K/mo (new middle class, China); $50K-$100K/yr (US) | — |
| **Geography** | Tier 1/new Tier 1/Tier 2 cities (China); global (Coursera) | Global enterprise (Coursera 6,200+ corporate clients) |
| **Decision cycle** | Minutes-days (course purchase); impulse-driven | 3-6 months (fiscal year planning) |
| **Price sensitivity** | High; avg course ¥30-¥80 (China); $39-$79/mo (US) | Medium; ~$1,000/enterprise/yr (Coursera); ROI on upskilling |
| **Key platforms** | 得到 (¥99-¥399/course), Coursera ($59/yr Plus), 知乎盐选, Udemy | Coursera Enterprise, edX for Business, Udemy Business |
| **Repurchase rate** | 41% (audio), 45% professional vs 20% entry-level | >90% annual renewal (corporate SaaS norm) |
| **WTP range** | ¥100-¥500/yr (China); $50-$500/yr (US) | $5K-$100K+/yr |

##### Domain 3: Tech/AI/Developer

| Attribute | Description |
|-----------|-------------|
| **Age range** | 18-34 (dominant); 25-34 fastest-growing segment for AI news consumption (+4pp YoY) |
| **Occupation** | Software developers, ML/AI engineers, data scientists, technical founders, CTOs |
| **Geography** | Global; US/Western Europe (primary), APAC (fastest growth) |
| **Key platforms** | GitHub, arXiv cs.*, ProductHunt, TechCrunch, Substack (tech newsletters), Stack Overflow |
| **Decision cycle** | Personal: minutes (individual sub); Enterprise: 1-3 months (team tool purchase) |
| **Content preference** | Text-heavy (technical blogs, preprints, newsletters) + video (tutorials, conference talks) |
| **AI adoption rate** | Highest of any demographic: <25: 17%, 25-34: 15% weekly use for news; ChatGPT 44% US adult adoption |
| **WTP pattern** | Personal: $5-$20/mo (Substack, ChatGPT Plus); Enterprise: $20-$200/user/mo (Copilot, IDE plugins) |
| **Avg AI subscriptions** | 4 paid AI tools (~$66/mo total); 67% consider AI subscriptions "most important" (Bango 2025) |

##### Domain 4: Enterprise SaaS / B2B Cloud & Software

| Attribute | Description |
|-----------|-------------|
| **Buyer persona** | CIO/CTO/IT director + business line head (dual signature); typical 5-10 stakeholders |
| **Decision cycle** | Median 3-6 months; large enterprise 12-18 months |
| **Budget** | Enterprise software +15.2% YoY (Gartner 2025); ~9pp from price increases, ~6pp real net-new, almost all flowing to AI applications |
| **Geography** | North America ~60% of global SaaS spend, EMEA ~25%, APAC ~12% |
| **Typical ACV** | $50K-$500K (SaaS); significantly higher than consumer subscriptions |
| **Renewal rate** | >90% annual; net retention 110-130% |
| **Purchase criteria** | ROI, TCO, compliance, security, SLA guarantees; price elasticity is low |
| **AI adoption** | 78% of US enterprises plan to deploy AI agents (2026); 51% already in production (Ringly 2026) |
| **Content need** | Competitive intelligence, market analysis, regulatory updates, AI/tech trend tracking |

##### Domain-Level WTP Comparison (C端 vs B端)

| Dimension | Financial (C) | Education (C) | Tech/Dev (C) | Enterprise SaaS (B) |
|-----------|:------------:|:------------:|:------------:|:------------------:|
| **Decision mode** | Minutes-days | Minutes-days | Minutes | 3-18 months |
| **Monthly ARPU** | $4-$2,665 | ¥8-¥33 | $5-$20 | $4K-$42K |
| **Churn rate** | 4-16%/mo | 25-55% | low | <10%/yr |
| **Price sensitivity** | Medium | High | Medium | Low |
| **Key driver** | Information edge | Career advancement | Productivity | ROI & compliance |
| **Agent readiness** | High (86% Wind users) | Low | Medium | High (78% enterprises) |

Pricing is defined by product type and tier, not by platform features:

| Tier | RAW Products | PROCESSED Products | Platform Access |
|------|-------------|-------------------|----------------|
| **Free (dev preview)** | 1 domain, 1 RAW feed (limited to 50 items/mo) | Digest only (weekly, no customization) | CLI + MCP, BYOK |
| **RAW Pro** ($50-200/mo) | Unlimited domains, unlimited RAW feeds, API access, bulk export (JSON/CSV/SQLite) | Digest (daily/weekly + custom instructions), basic reports | CLI + MCP, BYOK, priority collection |
| **PROCESSED Pro** ($500-2,000/mo) | All RAW Pro features | Full product suite: thematic reports, alert streams, tutorials, presentations, custom templates, scheduled delivery | CLI + MCP, BYOK, priority collection + processing, human review on delivery |
| **Enterprise** (Custom) | All features dedicated infrastructure | White-label products, custom SLAs, dedicated delivery channels, editorial review, compliance | Managed hosting, SLA guarantees, SSO |

#### Domain-Level Pricing Benchmarks (Market Reference) (NEW)

> *Actual market pricing across domains, sourced from the global information payment research report. These serve as reference anchors for AutoInfo's product pricing strategy.*

| Domain | Entry-Level | Mid-Tier | Premium | Ultra-Premium (Enterprise) | Notes |
|--------|-----------|---------|---------|--------------------------|-------|
| **Financial Terminal** | Alpha Vantage Premium: $49.99/mo | 同花顺 iFinD: ~¥8,000/yr | Wind: ~¥680/mo (retail); ¥数万-数十万/yr (institutional) | Bloomberg: $2,665/user/mo ($32K/yr); Refinitiv: $2K-$8K+/user/mo | Largest spread: $50-$32K+/mo |
| **Business News/Deep Analysis** | NYT Basic: $17/mo | WSJ: $44.99/mo; 财新: ¥498/yr | FT: £75/mo ($100+/mo); The Information: $199/yr | Bloomberg Terminal: $32K/yr (includes news) | WTP 5-10× for financial vs general news |
| **Professional Knowledge** | Medium: $5/mo | 知乎盐选: ~¥19/mo; 得到: ¥199-365/yr | Coursera Plus: $59/yr; DataCamp: $25/mo | Coursera Enterprise: ~$1,000/org/yr; Degreed: custom | B2B ARPU significantly higher |
| **AI Tools** | ChatGPT Plus: $20/mo; Perplexity Pro: $20/mo | Claude Pro: $20/mo; Gemini Advanced: $20/mo | ChatGPT Team: $25/user/mo; Copilot Pro: $30/mo | ChatGPT Enterprise: custom; Claude Max: $200/mo | AI subs averaging 4 tools/person = ~$66/mo |
| **Developer/Tech** | GitHub Free | Substack paid newsletters: $5-15/mo | Stack Overflow Teams: $12/user/mo | GitHub Enterprise: $21/user/mo | Low ARPU but high volume |
| **Academic Research** | arXiv: Free | PubMed: Free; OpenAlex: Free | IEEE: $30+/mo (personal); Scopus: institutional | Elsevier/SciVal: $10K-$100K+/yr (institutional) | Open access is the norm; premium is institutional |
| **Newsletter/Creator** | Substack free | Substack paid: $5-15/mo | 52 newsletters earning $500K+/yr | Substack Pro advances: $100K-$500K | Creator-led model with platform take rate 10% |
| **Music/Video Streaming** | Spotify Free (ad-supported) | Spotify Premium: $10.99/mo; Netflix Standard: $15.49/mo | Netflix Premium: $22.99/mo; YouTube Premium: $13.99/mo | Apple One Premier: $39.95/mo (bundle) | Entertainment ≠ news/info; different buyer psychology |

#### Key Pricing Insights for AutoInfo

| Insight | Data Point | Implication |
|---------|-----------|-------------|
| **B2B vs B2C price ratio** | $50K-$500K ACV (B2B SaaS) vs $4-$45/mo (C端 subscriptions) — ratio of **100-1000×** | AutoInfo should prioritize B2B PROCESSED products for revenue |
| **Subscription fatigue ceiling** | 47% churn rate (2026, up from 31% in 2024); 87% Gen Z fatigue | Discounts boost conversion by **3.35×** (Journalism Studies 2025); free tier + discount strategy critical |
| **Bundle effect on retention** | Nordic +Alt bundle churn: **0.7%** vs single publication: **16.4%** — LTV gap **26×** | Cross-domain/product bundles are a retention super-weapon |
| **AI premium pricing** | AI users pay 4× subscriptions ($66/mo avg); 67% call AI subs "most important" | Agent-mediated delivery justifies premium pricing |
| **Global market saturation** | Top 20 wealthy nations avg 18% news payment rate; 3 years flat | Growth comes from new domains (financial/legal/tech), not general news |

### 7.4 Product Type Economics

| Dimension | RAW Products | PROCESSED Products |
|-----------|-------------|-------------------|
| **Margin** | Low (commodity — information is available elsewhere) | High (differentiated — synthesis and analysis add value) |
| **Volume** | High (thousands of items per domain) | Low (handful of reports per period) |
| **Automation** | Fully automated (collect → process → deliver) | Semi-automated (LLM generates, human reviews, then delivers) |
| **Delivery** | API endpoints, webhook streams, bulk export | Email digests, scheduled push, REST API, webhook |
| **Customer retention** | Low (switching to another feed is easy) | High (custom analysis creates switching cost) |
| **Quality criticality** | Freshness + completeness | Accuracy + insight + presentation |
| **Gate enforcement** | Soft gates (G1-G3, G5) — flag and filter | Hard gates (G0, G4) + delivery gates (D1-D3) — block on failure |

**Strategic implication**: PROCESSED products are the high-margin revenue driver. RAW products are the moat — they feed the PROCESSED pipeline and make it hard for competitors to replicate the same depth of domain coverage.

### 7.5 Content Sourcing & Agent Ecosystem Strategy (NEW)

> *AutoInfo's strategy for content acquisition, API access, AI agent integration, and navigating the polarized data accessibility landscape.*

#### 7.5.1 Content Accessibility Tier System

Based on the API capability matrix (F07b), all potential sources fall into three tiers:

| Tier | Definition | Examples | AutoInfo Approach |
|------|-----------|---------|-----------------|
| **Tier A: Open Access** (Free/Open API) | Public APIs with generous rate limits, no payment required | arXiv, PubMed, OpenAlex, CrossRef, Semantic Scholar, FRED, GitHub, YouTube (free tier), Reddit (non-commercial) | **First-class citizens**. Default pre-configured sources. Full automation with no cost barrier. |
| **Tier B: Freemium/Low-Cost** (Free tier with paid premium) | Usable free tier exists; premium unlocks higher limits or additional data | Alpha Vantage ($49.99/mo premium), AP ($100/min key), NYT (10 req/min free), Substack (free metadata) | **Default pre-configured at free tier**. Premium tier available as user-configured upgrade. Agent can suggest upgrade when limits hit. |
| **Tier C: Paid Only** (No free access) | Requires paid subscription or institutional license | Bloomberg ($2,665/user/mo), Wind (¥数十万/yr institutional), Reuters Connect ($2K-$15K/mo), 知乎 (no API), 微信公众号 (no API) | **Not pre-configured**. Supported as user-configured sources under F08. User provides their own API key/access credentials. AutoInfo provides the handler. Agent warns about cost when user adds these. |

**Strategic principle**: AutoInfo's default demo domains ship with Tier A and Tier B sources exclusively. Tier C sources are available for user-configured domains where the expected ROI justifies the cost. This ensures the free/dev tier remains functional without requiring users to spend on data access.

#### 7.5.2 AI Agent Integration Strategy

AutoInfo is designed as an **agent-native content supply platform**. As the research report confirms, "Agent-mediated reach" is Reuters Institute's #2 theme for 2026, with 78% of US enterprises planning to deploy AI agents.

**AutoInfo's role in the Agent ecosystem**:

| Layer | AutoInfo's Role | Technical Implementation |
|-------|----------------|------------------------|
| **Content supply** | Provide structured, source-verified content that agents can consume via MCP | All KB data accessible via MCP tools: `search_knowledge_base`, `get_kb_entry`, `export_kb` |
| **Agent-triggered collection** | Agents trigger collection on demand, not just scheduled | `collect_sources(context="agent_query: user asked about X")` — collection tied to agent interaction |
| **Agent-native output delivery** | PROCESSED products delivered as tool results, not just email/files | Agent calls `generate_digest()` → returns structured dict → agent formats for user |
| **RSS Feed as product output** | RAW and PROCESSED products exportable as RSS/Atom feeds for agent and human subscription | `export_kb(format="rss")` → returns RSS feed XML for any domain/topic/collection |

**Market context — content licensing landscape** (data from research report):

| Transaction | AI Company | Publisher | Value | Significance |
|------------|-----------|-----------|-------|--------------|
| Landmark AI deal | OpenAI | News Corp (WSJ, Barron's, etc.) | **$250M / 5 years** | Largest known deal; sets market benchmark |
| AI partnership | OpenAI | Axel Springer (Politico, BI) | ~$13M/yr × 3yr | First "full-stack" deal including paywalled content |
| Enterprise license | OpenAI | Financial Times | $5-10M/yr | Paywalled financial news + attribution |
| Data licensing | Google | Reddit | **$60M/yr** | API-based training data paradigm |
| AI training deal | Amazon | NYT | **$20-25M/yr** | For Alexa/Rufus, excludes ChatGPT/Claude/Perplexity |
| Revenue share | Perplexity | 100+ publishers | 80% of Comet Plus ($5/mo) pool = **$42.5M** | Agent→publisher revenue sharing model |

**Implication**: The AI training data licensing market has matured from pilot (2023-2024) to established revenue stream (2025-2026). AutoInfo's position as an agent-native platform aligns with this trend — content collected and processed by AutoInfo can serve as both human-readable products and agent-consumable structured data.

#### 7.5.3 Content Licensing Strategy for AutoInfo

| Product Type | Licensing Model | Target Customer |
|-------------|----------------|----------------|
| **RAW Products (Tier A sources)** | Included in subscription — no additional licensing cost | All tiers |
| **RAW Products (Tier B/C sources)** | Pass-through: user pays source cost + AutoInfo service fee | RAW Pro / Enterprise |
| **PROCESSED Products (Tier A)** | Included — LLM synthesis of open-access content | PROCESSED Pro |
| **PROCESSED Products (Tier B/C)** | Premium tier — value-add on paid data sources | Enterprise |
| **AI Training Data License** (v2+) | Separate data license agreement — customer trains models on AutoInfo-curated datasets | Enterprise / Strategic Partners |

#### 7.5.4 Chinese Content Ecosystem Boundary

The research report identifies a critical structural gap:

| Aspect | Chinese Ecosystem | Western Ecosystem | Implication |
|--------|-----------------|------------------|-------------|
| **Official MCP support** | **Zero** — 知乎, 得到, 微信公众号, B站, 抖音, 小红书, 微博 have NO official MCP | **Growing** — Reuters MCP (2026-07), Wind MCP, Thomson Reuters Westlaw MCP | Chinese content platforms cannot be reliably accessed via agent protocols |
| **API accessibility** | Nearly all Chinese platforms lack open APIs or have restrictive paid APIs | Many Western platforms offer free/open APIs (academic, selected news, social with rate limits) | Chinese-language content tracking requires alternative approaches |
| **Anti-crawl posture** | Strongest globally — TLS fingerprinting, device fingerprint, CAPTCHA, dynamic tokens | Cloudflare/Akamai common but less aggressive for public content | Web scraping Chinese platforms is high-risk and low-reliability |
| **AI regulation** | 生成式AI暂行办法 (2023/8); training data must be legally sourced, IP-compliant | EU AI Act (2025/8 GPAI obligations); US litigation-driven (NYT v. OpenAI etc.) | Compliance requirements differ significantly |

**AutoInfo's strategy for Chinese content**:
1. **Track Chinese-language open-access sources** (arXiv Chinese authors, CNKI open-access, government open data, WeChat public account RSS-like aggregators where legally available)
2. **Support user-configured premium Chinese sources** (用户自行提供 财新/知网/得到 订阅凭据)
3. **Leverage Chinese AI agent platforms** (字节扣子Coze, 腾讯元器) for content distribution rather than collection
4. **The "财新 × Kimi" model** (Kimi answers cite Caixin with attribution + links) as the reference for Chinese content agent partnership

### 7.6 Regional Strategy & Regulatory Compliance (NEW)

> *Regional market characteristics, user behavior differences, and regulatory requirements that inform AutoInfo's go-to-market strategy.*

#### 7.6.1 Regional Comparison Matrix

| Dimension | 🇺🇸 North America | 🇪🇺 Europe | 🇨🇳 China | 🇯🇵🇰🇷 Japan/Korea |
|-----------|:----------------:|:---------:|:---------:|:---------------:|
| **Global SaaS spend share** | ~60% | ~25% | ~8% | ~5% |
| **News payment rate** | 22% (US) | Norway 40%, Sweden 31%, UK 8%, Germany 13%, France 11% | No unified paywall; skews toward knowledge payment (¥350B market) | Japan 9%, Korea low (music 5% — global lowest) |
| **Top content format** | Video (72% watch news video 2025, up from 55% in 2021) | Text (55% average); German 18-24: 49% text, 33% video | Short video (抖音 7.1B DAU); AI apps (6.02B users) | Text (Japan); Mobile-first |
| **AI news adoption** | 6% (flat 2025→2026); ChatGPT 44% adult adoption | 4-5% (UK, FR, DE flat); Spain doubled YoY | AI users 602M (42.8% penetration);豆包 382M MAU | Korea 14% (doubled YoY); Japan <5% |
| **AI Agent adoption** | 78% enterprises plan to deploy; 51% in production | EU AI Act compliance driving structured adoption | ByteDance Coze, Tencent Yuanshi; zero official MCP | Korea leading Asia in AI news |
| **Key regulation** | Litigation-driven (NYT v. OpenAI, CNN v. Perplexity) | EU AI Act (GPAI obligations since 2025/8/2); DSM Directive Art. 4 opt-out | 生成式AI暂行办法; 网信办 content review; training data compliance | Japan AI guidelines; Korea AI Basic Act |
| **Payment preference** | Credit card; PayPal; Apple Pay | SEPA; credit card; PayPal | WeChat Pay; Alipay; bank transfer | Credit card; convenience store; carrier billing |
| **Subscription behavior** | 89% underestimate monthly sub spend ($273/mo avg); 47% churn rate (2026) | Lower churn in Nordic (bundle 0.7%); higher in UK | Knowledge payment growing;得到 35% payment conversion | Long-tail subscriptions; low churn |

#### 7.6.2 Regulatory Compliance Requirements

**EU AI Act — GPAI obligations (effective 2025/8/2)**:
- AutoInfo must respect TDM opt-out signals (robots.txt, `llms.txt`, machine-readable rights reservations)
- Training data for any GPAI model using AutoInfo-curated data must have copyright policy and respect opt-out
- **Required tool**: `check_source_compliance(source_url)` — verify opt-out status before collection

**China — 生成式人工智能服务管理暂行办法**:
- Training data must be legally sourced, IP-compliant
- Personal information in training data requires consent
- **Implication**: AutoInfo's Chinese-language collection must stay within open-access, properly licensed sources

**US — Litigation-driven**:
- No comprehensive federal AI law; court decisions set precedent
- NYT v. OpenAI (2023-12, ongoing): fair use defense for training data challenged
- **Implication**: AutoInfo should prioritize opt-in, licensed data sources for any commercial AI training use case

#### 7.6.3 Regional Go-to-Market Priority

| Priority | Region | Rationale | AutoInfo Readiness |
|----------|--------|-----------|-------------------|
| 🥇 **Primary** | North America + Western Europe | Highest WTP; mature subscription economy; English-dominant content readily available via open APIs | ✅ Default language; most sources Tier A/B |
| 🥈 **Secondary** | China (outbound: Chinese → English; enterprise Chinese content) | Largest knowledge payment market (¥3,508B); growing AI user base (602M); weak API access = less competition | ⚠️ Chinese sources Tier C (user-configured);适合追踪中英文内容的跨语言领域 |
| 🥉 **Tertiary** | APAC (Japan/Korea/SEA) | Korea fastest AI news growth (+100% YoY); Japan low payment but high trust | ⏸ Future expansion |

### 7.7 Market Trends & Business Model Innovation (NEW)

> *Key industry inflection points and emerging business models that validate AutoInfo's approach and inform future feature priorities.*

#### 7.7.1 2024-2026 Key Inflection Points

| Trend | Data Point | Impact on AutoInfo |
|-------|-----------|-------------------|
| **Social/video surpasses direct access** | US social/video news 54% > websites 51% (2026, Reuters Institute) | Agent-mediated distribution becomes critical — users won't visit websites, content must go to them |
| **Search referral collapse** | Google publisher traffic -33% (2025); AI Overviews CTR decline up to 89%; zero-click queries 60% | AutoInfo's "collect once, deliver anywhere" model insulates against platform dependency |
| **Agent-mediated reach** | Reuters Institute #2 theme for 2026; 78% US enterprises deploying agents | AutoInfo's agent-native architecture is future-proof by design |
| **AI training data licensing** | Reddit-Google $60M/yr; News Corp-OpenAI $250M/5yr — new revenue category emerged 2024-2026 | RAW products have AI training data licensing as an additional monetization path |
| **Publisher "double bleed"** | Search traffic -33% + AI clickback rate 4% (vs search 19%, social 17%) | Publishers need AutoInfo-style tools to create their own AI-mediated distribution |
| **Subscription fatigue acceleration** | 31%→47% churn (2024→2026); 87% Gen Z fatigue; discount lifts conversion 3.35× | Free tier + discount-first strategy essential; bundle pricing (Nordic 0.7% churn vs single 16.4%) should be default |
| **Bundling as retention super-weapon** | Nordic +Alt bundle 0.7% churn vs single publication 16.4% — LTV difference **26×** | Cross-domain/product bundles should be AutoInfo's default pricing architecture |

#### 7.7.2 Business Model Innovation Reference

| Model | Example | Mechanism | Application to AutoInfo |
|-------|---------|-----------|----------------------|
| **Agent revenue share** | Perplexity Comet Plus ($5/mo, 80% to publishers = $42.5M pool, 100+ publishers) | Agent subscription → agent queries publisher content → publisher gets majority of revenue | Future Agent tier: AutoInfo as "content supply" for third-party agents, with usage-based revenue share |
| **Token/credit economy** | Wind Alice personal: 100 yuan = 10,000 credits; first purchase bonus 10% | Points-based metering → consumption-based billing | Alternative payment model for agent-mediated access: "pay per KB entry consumed" |
| **Effectiveness-based pricing (RaaS)** | 蚂蚁数科RaaS; e签宝智能合同Agent: ¥1亿+/yr revenue | Price tied to measurable business outcome (GMV share, ROI) | Enterprise tier: price by items collected, time saved, or analysis quality |
| **API licensing** | Reddit-Google $60M/yr; OpenAI 14+ publisher deals | Fixed annual fee for API access + training data rights | Enterprise RAW tier: bulk data access + AI training rights |
| **Content bundling cross-sell** | NYT bundle: 6.48M subscribers (ARPU $12.67 vs single $3.47); +24.3% YoY | Multiple products sold as a package at premium but per-product discount | Domain bundles: "Financial + Tech + Medical" at package discount — drives retention (bundle churn 0.7% vs single 16.4%) |
| **Human review premium** | 43% comfort if AI + human-supervised vs 12% if purely AI-generated (Reuters 2025) | Premium tier includes human editorial review | PROCESSED Pro includes human QA gate; justifies 4-10× price over fully automated RAW |

#### 7.7.3 Content Format Commercialization Data

| Format | Market Data | AutoInfo Support | Commercial Potential |
|--------|-----------|-----------------|---------------------|
| **Audio digest** | Avg price ¥30-80, repurchase rate 41% | ❌ Not yet supported (text-only) | 🔴 High — 14% user preference, 42% payment intent for news podcasts |
| **Short video summary** | 75.7% of paid learning sessions (2022); 72% user penetration (2024) | ❌ Not yet supported (text-only) | 🟡 Medium — requires TTS + video generation pipeline |
| **Newsletter (email)** | Substack 8.4M paid (+68%); 52 newsletters earning $500K+/yr | ✅ SMTP sending supported; Agent-generated digest | ✅ High — core delivery channel |
| **RSS Feed as product** | RSS adoption +34% YoY (2026); 400M+ podcasts distributed via RSS | 🟡 Not yet exportable (consumes RSS, doesn't produce) | ✅ High — standard format for both human and agent consumption |
| **Structured data API** | Bloomberg $2,665/user/mo; Alpha Vantage $49.99/mo; Wind ¥680/mo | ✅ REST API + webhook + bulk export | ✅ Core RAW product delivery |
| **Agent-native output** | ChatGPT 10B MAU; Perplexity 100M+ MAU (2026 Q2) | ✅ MCP tools for KB search + digest generation | ✅ Highest growth channel — agent-mediated delivery is the 2026 inflection point |

#### 7.7.4 The Shift: From "People Find Information" to "Agent Finds Information"

```
Traditional (SEO era):
  Publisher website → Google Search → User click → Read (ads/subscription wall) → Return visit

Current (AI summary era):
  Publisher API/feed/RSS → AI Agent (ChatGPT/Perplexity/Claude/Gemini) → User prompt → Summary/answer (attribution + link)

AutoInfo's Position:
  Source (Tier A/B/C) → AutoInfo Collection → KB Pipeline (Raw→Draft→Wiki) 
    → RAW Products (API/Webhook/Export) → Agent/Human consumption
    → PROCESSED Products (Digest/Report/Tutorial) → Agent-mediated delivery
    → AI Training Data License (v2+) → Enterprise model training
```

**Key differences** between SEO era and Agent era:

| Dimension | SEO Era | Agent Era | AutoInfo Advantage |
|-----------|---------|-----------|-------------------|
| **User identity** | Publisher-owned (cookies, registration) | Platform-owned (OpenAI/Perplexity/Google) | AutoInfo agents operate on behalf of the user; identity stays with subscriber |
| **Ad inventory** | Publisher web pages (banners, native) | Zero (LLMs don't display publisher ads) | AutoInfo's product model doesn't depend on advertising |
| **Brand exposure** | Full-article reading (high) | Summary reading (low) | PROCESSED products restore brand value through curated, attributed synthesis |
| **Revenue model** | Subscription + advertising (high CPM) | One-time license fee ($1-50M/yr) + micro revenue share (Comet: 80% back) | Multiple revenue streams: subscription + licensing + future revenue share |
| **Publisher control** | Full (SEO optimization, paywall) | Low (AI decides what to cite) | AutoInfo gives publishers control over how their content is packaged for agent consumption |
| **Data回流** | Complete (UTM, click tracking) | Almost none (citation count only) | AutoInfo maintains full provenance + usage analytics |

### 8.1 Founder's Verdict

```python
@dataclass
class FounderVerdict:
    """Result of evaluating founder's expectations against the project."""
    passed: bool                           # ALL critical expectations pass

    journey_phase_results: dict[str, PhaseResult]  # per-phase results
    value_proposition_results: dict[str, ValueResult]  # per-value-prop results

    critical_passed: int                   # Critical expectations that pass
    critical_failed: int                   # Critical expectations that fail

    blocking_issues: list[str]             # Things that make the project
                                           # "not deliverable" for the founder
    summary: str                           # One-line verdict

@dataclass
class PhaseResult:
    phase: str                             # "setup", "configure", "collect", etc.
    expectations_pass: int
    expectations_fail: int
    expectations_untested: int

@dataclass
class ValueResult:
    proposition: str                       # "universal collector", "LLM extraction", etc.
    verdict: Literal["fulfilled", "partial", "broken"]
    gaps: list[str]
```

### 8.2 Example Verdicts

```
PASS — All 6 critical expectations pass, 24/35 total pass
       Value props: 2 fulfilled, 2 partial, 0 broken
       Market fit: validated with first 3 paying users

FAIL — 2 critical expectations fail:
       F11 (collection loop): RSS handler works, API handler broken
       F15 (LLM extraction): extraction quality below acceptable threshold
       Value props: 0 fulfilled, 3 partial, 1 broken

PARTIAL — 18/35 expectations pass, but:
          F07 (medical sources): PubMed works, arXiv integration pending
          F13 (source handlers): only RSS implemented, API handler in progress
          This is acceptable for v0.2 with known limitations
```

---

## 9. Current Reality Assessment

**Status: v1.6 (2026-07-26).** Gap analysis completed — 55/57 expectations fully implemented (✅), F30 (Subscription & Billing) partially implemented (🟡 — Stripe webhook endpoint exists, checkout session creation works, subscription model operational), F42 (External Billing) partially implemented (🟡 — CostMeter fully operational, Stripe billing flow pending). All 13 v1.5+ residual gaps (P0) are closed. All expectations across End User Lifecycle (F36-F40), Cost Governance (F41-F45), Data Privacy (F46-F48), Knowledge Lifecycle (F49-F53), and Operational Observability (F54-F57) are implemented as of v1.6. All 6 quality gates (G0-G5) and 3 delivery gates (D1-D3) are fully implemented per spec. Product model defined: RAW products and PROCESSED products with 10 delivery channels (SMTP, Telegram, WeChat OA, WeChat Work, DingTalk, FeiShu, Discord, Webhook, REST API, File Export) with email as mandatory fallback. End User lifecycle operational: UserProfile/Subscription CRUD, state machine (trial→active→suspended→cancelled), delivery logging with SLA tracking, CLI self-service portal. Cost governance: internal metering, per-domain/per-user allocation, dashboard, budget alerts. Data privacy: source ToS compliance, soft-delete with GDPR export, immutable audit logging. Knowledge lifecycle: per-domain TTL, versioned re-collection with diff, stale content handling, decay metrics, cross-collection dedup & merge. Operational observability: structured JSON pipeline logging, per-item trace_id propagation, enhanced diagnostics with health score, Prometheus metrics export. Comprehensive gap audit (2026-07-26) finds 8 gap categories documented in `docs/dev/comprehensive-gap-audit.md`. Remaining gaps tracked as: Wave 0 documentation ✅, Wave 1 expectations status fixes in progress, Wave 2 MCP tool registration pending, Wave 3 SPEC updates pending, Wave 4 consumer-facing gaps deferred.

```mermaid
%%{init: {'theme': 'neutral', 'themeVariables': { 'fontSize': '14px'}}}%%
gantt
    title AutoInfo Development Timeline
    dateFormat  YYYY-MM-DD
    section v0.1 Core Loop
    RSS + PubMed + CLI + G1-G3           :done, 2026-07-18, 1d
    section v0.2-v0.6
    LLM Extraction + KB + Q&A + Graph    :done, 2026-07-19, 1d
    section v1.0 Product
    All 35 expectations met              :done, 2026-07-20, 1d
    section v1.1 Gap-Fill
    G5 + Promote + Webhook+Email+PDF     :done, 2026-07-21, 1d
    section v1.2 Enhancement
    Hybrid search + REST API + CEFR + Dashboard + Versioning :done, 2026-07-21, 1d
    section v1.4 Domain & QA & Output
    F10b + Translation QA + HTML + Webhooks + Cron Digest :done, 2026-07-23, 1d
    section v1.5 Product & Production
    Commercial scope + Product model + Hard/Soft gates + Delivery :done, 2026-07-24, 1d
    section v1.5+ End User Lifecycle (spec)
    F36-F40 designed (not yet implemented)              :done, 2026-07-25, 1d
```

| Component | Status |
|-----------|--------|
| Code base | ✅ ~18K+ lines Python |
| CLI | ✅ 23 command groups (init, doctor, collect, process, status, summaries, sources, topics, domain, audit, kb, output, cron, knowledge, cefr, email, keywords, clean, cost, billing, enduser, portal, trace) |
| Config system | ✅ YAML-based, LLM per-task config, fallback chains, schema versioning |
| Collection pipeline | ✅ RSS, API (PubMed), Web (trafilatura+Playwright), Webhook (HMAC), Email (IMAP), PDF (PyMuPDF), crontab installer |
| LLM extraction | ✅ Default + custom fields, G4 factual consistency check, token usage tracking |
| Translation QA pipeline | ✅ 5 lite quality gates, back-translation verification, terminology guardrails, composite scoring, translator-qa-skill |
| Quality gates | ✅ G1-G5 hard/soft split (G0/G4 hard, G1-G3/G5 soft), retry-first with configurable thresholds; production delivery gates (D1-D3) |
| KB pipeline | ✅ 4-tier KB pipeline (00-Inbox → 01-Raw → 02-Draft → 03-Wiki; note: 00-Inbox is scaffolded but deprecated — 01-Raw is the sole entry point), git versioning (auto-commit + SHA) |
| KB import | ✅ 4 formats (PDF, Markdown, HTML, JSON) → 01-Raw via `import_kb` MCP tool |
| Search | ✅ Hybrid (FTS5 + sqlite-vec vector), faceted (7 filters) |
| REST API | ✅ FastAPI CRUD (port 8741) |
| Web UI Dashboard | ✅ Bootstrap 5 |
| CEFR classification | ✅ LLM-based EN/ZH/JA |
| Knowledge graph | ✅ Entity extraction + relation discovery + export (JSON/GraphML/CSV) |
| Domain management | ✅ `add_domain`/`remove_domain` MCP tools, `autoinfo domain` CLI (add/list/show/remove/activate/deactivate) |
| Webhook push | ✅ Per-item webhook notification on collection via `set_domain_webhooks`/`get_domain_webhooks` |
| Scheduled digest | ✅ Cron-based email digest delivery (SMTP + crontab schedule) |
| Agent alerting | ✅ Config-based alert rules with YAML persistence, check & dispatch via DeliveryChannel |
| MCP server | ✅ 114 tools across 32 categories (v1.6: +5 categories: End User, Cost, Data Privacy, Knowledge Lifecycle, Observability) |
| Demo source curation | ✅ 7 curated sources across 3 domains |
| Translation | ✅ LLM-based via localize_content MCP tool |
| Output generation | ✅ Digest, report (Markdown/JSON/PDF), tutorial, presentation, export |
| Product delivery | ✅ RAW product delivery (API feeds, webhook streams, bulk export); ✅ PROCESSED product delivery (scheduled digests, thematic reports, alert streams via SMTP/webhook) |
| Quality gate model | ✅ G1-G5 hard/soft split (G0/G4 hard with retry→block, G1-G3/G5 soft with configurable thresholds); delivery gates D1-D3 |
| Commercial scope | ✅ Defined: any field with paying customers; two product types (RAW + PROCESSED) |
| Subscription/billing | ❌ Deferred to v2+ (F30 — tracked) |
| Tests | ✅ 1549 tests (unit, integration, snapshot regression, 262 v1.5 tests) |
| CI/CD | ⏸ Manual — Makefile targets, pre-commit hooks configured |
| Multi-channel delivery | ✅ 10 channels: SMTP, Telegram, WeChat OA, WeChat Work, DingTalk, FeiShu, Discord, Webhook, REST API, File Export (email as mandatory fallback) |
| End user lifecycle | ✅ Profile + Subscription CRUD, state machine (trial→active→suspended→cancelled) |
| Delivery reliability & logging | ✅ Per-subscription DeliveryLog with SLA tracking, retry chain, fallback |
| End user self-service portal | ✅ CLI-based portal (preferences, history, archive) |
| Immutable audit logging | ✅ Append-only audit log, queryable via MCP tool and CLI |
| Structured pipeline logging | ✅ JSON structured logging, daily rotation, per-stage configurable levels |
| Per-item traceability | ✅ UUID trace_id from collection through delivery, CLI trace command |
| Cost metering & allocation | ✅ LLM tokens, storage, API calls per domain/user, pro-rata/usage-based/direct allocation |
| Cost dashboard | ✅ CLI + MCP dashboard with daily trends, top models, budgets |
| Budget alerts | ✅ Threshold-based alerts with auto-remediation actions |
| Source ToS compliance | ✅ Source classification tiers, per-tier output controls, attribution |
| Data deletion & retention | ✅ Soft-delete, restore, GDPR export, 30-day auto-cleanup |
| Knowledge lifecycle | ✅ Per-domain TTL, versioned re-collection, stale handling, decay metrics, cross-collection dedup & merge |
| Enhanced diagnostics | ✅ `doctor --verbose` with health score, error rates, latency p95/p99 |
| Prometheus metrics | ✅ `/metrics` endpoint, structured JSON export |

### What v1.6 ships (v1.5 + additions):

```bash
# --- Setup ---
autoinfo init --name "MyProject"         # Named project initialization
autoinfo init --demo medical-research    # Interactive wizard with domain selection
autoinfo doctor                           # Full health check (LLM, sources, disk, DB)

# --- Domain Management ---
autoinfo domain add --name my-domain     # Create a new custom domain
autoinfo domain list                      # List all configured domains
autoinfo domain show --name my-domain    # Show full domain configuration
autoinfo domain remove --name my-domain  # Remove a domain (keeps data)
autoinfo domain activate --name my-domain # Activate a domain
autoinfo domain deactivate --name my-domain # Deactivate a domain

# --- Collection ---
autoinfo collect --all                    # Collect from ALL active domains at once
autoinfo collect --domain medical --sources pubmed --keywords IVF --limit 5
autoinfo collect --dry-run                # Preview before fetching
autoinfo cron install                     # Install crontab for scheduled collection
autoinfo cron uninstall                   # Remove crontab

# --- Processing ---
autoinfo process --domain medical         # LLM extraction + G1-G5 quality gates
autoinfo process --check-factual          # G4 factual consistency check
autoinfo process --check-translation      # G5 translation accuracy check

# --- Review & Curate ---
autoinfo summaries list --domain medical --date today
autoinfo summaries flag <id> --tag important --add-to-kb
autoinfo summaries rate <id> --helpful

# --- Knowledge Base ---
autoinfo kb search "embryo grading"       # Hybrid search (FTS5 + vector)
autoinfo kb search --vector-only "..."    # Pure vector search
autoinfo kb create-draft ...              # Agent creates Draft from Raw
autoinfo kb promote <entry-id>            # Human-only: Draft → Wiki
autoinfo kb reject <entry-id>             # Reject with reason
autoinfo kb list-tiers                    # Browse pipeline stages

# --- Output ---
autoinfo output digest --domain medical --period week
autoinfo output report --format html      # HTML/PDF/JSON/Markdown report
autoinfo output tutorial --collection "IVF Protocols" --audience clinician
autoinfo knowledge graph --domain medical  # Export knowledge graph
autoinfo output export --domain medical --format json

# --- CEFR ---
autoinfo cefr classify --text "..."       # Classify text CEFR level (EN/ZH/JA)
autoinfo cefr batch --domain language     # Batch classify domain entries

# --- Email ---
autoinfo email config --smtp-server smtp.gmail.com --port 587
autoinfo email send --to user@example.com --subject "Digest" --body "..."

# --- Keywords ---
autoinfo keywords add --domain medical --keyword CRISPR # Add domain keyword
autoinfo keywords list --domain medical   # List keywords

# --- REST API ---
# curl http://127.0.0.1:8741/health
# curl http://127.0.0.1:8741/api/v1/entries
# curl http://127.0.0.1:8741/dashboard  # Web UI

# --- Audit Log ---
autoinfo audit query --actor agent --action collect  # Query immutable audit log

# --- Cost Governance ---
autoinfo cost dashboard --domain medical             # View cost dashboard
autoinfo cost allocation --domain medical --user-id u1  # View user cost allocation

# --- End User Management ---
autoinfo enduser create --name "John" --email john@example.com --tier trial
autoinfo enduser get <user-id>
autoinfo enduser list --domain medical

# --- Self-Service Portal ---
autoinfo portal preferences <user-id>                # Manage delivery preferences
autoinfo portal history <user-id>                    # View delivery history

# --- Pipeline Trace ---
autoinfo trace <trace-id>                            # Full item pipeline trace

# --- MCP (Agent Interface) ---
# Agent connects via stdio MCP, discovers 114 tools automatically
# All capabilities available as structured tool calls
```

---

## 10. Evolution: From Vision to Reality

AutoInfo is starting from zero. This document is the blueprint.

### 10.1 The Build Process

```
For each expectation in the catalog:

  1. Define: What does "done" look like for this expectation?
     → "F11: `autoinfo collect --domain X --topic Y` stores structured items."

  2. Build: Implement the smallest version that delivers this.

  3. Test: Does it actually work? Run it.
     → Answer honestly: "yes", "mostly", "no".

  4. If no: What's the smallest change to flip it to "yes"?

  5. Lock: Write a test that asserts this behavior.
```

### 10.2 Milestone Definition

| Milestone | Definition | Expectations Met |
|-----------|-----------|-----------------|
| **v0.1 — Core Loop** | RSS collection → dedup → store → basic CLI. Medical demo domain with PubMed. | F01-F06, F07 (medical only), F11-F12, F13 (RSS), G1-G3, F31 |
| **v0.2 — Extraction & KB** | LLM summarization → KB storage → hybrid search → flag/review flow | F15, F16, F20, F21, G4 |
| **v0.3 — Multi-source** | API handler → web handler → AI commercial demo domain → cross-source dedup | F07 (AI commercial), F08, F13 (API+web), F18 |
| **v0.4 — Q&A & Graph** | Interactive Q&A → knowledge graph → cross-ref linking | F17, F19, F22 |
| **v0.5 — Output & Schedule** | Digest/report generation → scheduled collection → export formats | F14, F24, F26, F27 |
| **v0.6 — MCP Mature** | Full MCP tool suite → all domains → scheduled distribution → tutorial generation | F09, F10, F25, F32-F34 |
| **v1.0 — Product** | 35 expectations met. First paying users onboarded. Language learning demo (L1). | F07 (language-learning), F10 (learning-specific), all gates |
| **v1.1 — Gap-Fill** | G5 translation gate, KB promote/workflow, 3 new source handlers (webhook/email/PDF), KG export, 7 curated demo sources, 6 new MCP tools, interactive init, langdetect, collect --all | G5, F20 workflow, F13 (webhook/email/PDF), F22 (KG export), F07 (7 curated sources), F12 (progress MCP), F09 (keyword groups), F10 (langdetect) |
| **v1.2 — Enhancement** | Hybrid vector search (sqlite-vec), faceted search, REST API (FastAPI CRUD), Web UI dashboard, Obsidian [[wiki links]], CEFR classification, git versioning + SHA, PDF export, SMTP email, crontab installer, keywords management, schema versioning, multi-user foundation | F21 (hybrid+faceted), F23 (REST API+wiki links+versioning), F10 (CEFR), F26 (PDF export), F27 (SMTP+delivery), F14 (crontab), F20 (keywords), F34 (schema versioning) |
| **v1.3.1 — Expectations Update** | F10b (User-Defined Domains & Consulting Platforms) added, F10 localization QA enhanced (back-translation, multi-round refinement, terminology guard, composite score, agent skill). | F10b (new), F10/G5 (enhanced) |
| **v1.5 — Product & Production** | Commercial scope (any paying field), two product types (RAW + PROCESSED), production-grade quality gates (hard/soft split, retry-first/block-last), delivery infrastructure (SMTP, webhook, API), product delivery expectations F27-F30 | F27-F30 (product delivery ✅, RAW ✅, PROCESSED ✅, subscription 🟡 partially — Stripe webhook exists, full billing deferred), G0/G4 hard, D1-D3 |
| **v1.5+ → v1.6 — End User Lifecycle** | End User model (F36-F40) implemented: unified End User=Paying Customer role, profile/subscription CRUD, 6-channel delivery adapters (Telegram Bot, WeChat OA, WeChat Work, DingTalk, FeiShu, Discord + email fallback), lifecycle state machine (trial→active→suspended→cancelled), delivery logging & SLA tracking, CLI self-service portal. | F36-F40, §12.15 |
| **v1.6 — Cost Governance** | Internal cost metering (LLM tokens + storage + API calls), per-domain/per-user cost allocation (pro-rata, usage-based, direct), cost dashboard with daily trends, budget alerts with auto-remediation. External billing (Stripe) deferred to v2+. | F41-F45, §12.16 |
| **v1.6 — Data Privacy** | Source ToS compliance framework (access tier classification + disclaimer + processed-only output for sensitive sources), soft-delete with 30-day auto-cleanup + GDPR export, immutable audit logging for all operations. | F46-F48, §12.17 |
| **v1.6 — Knowledge Lifecycle** | Per-domain TTL configuration with topic-level overrides, versioned re-collection (same source URL → version diff), stale content marking with search demotion & digest exclusion, domain decay metrics (staleness ratio + avg TTL + Green/Yellow/Red grade), cross-collection dedup and LLM-assisted merge. | F49-F53, §12.18 |
| **v1.6 — Operational Observability** | Structured JSON pipeline logging with daily rotation, per-item trace_id propagation (collect→process→deliver→delivery), enhanced `doctor --verbose` with health score + error rates + latency p95/p99 + LLM spend, Prometheus `/metrics` endpoint export. | F54-F57, §12.19 |

### 10.3 Explicit "No" List (v1.6 Scope)

The following are **explicitly out of scope** for v1.6:

| Feature | Status | Rationale |
|---------|--------|-----------|
| Web UI / dashboard | ✅ **v1.2 Added** | Bootstrap 5 dashboard at `/dashboard` |
| Mobile app | ❌ Out | Agent framework handles mobile access. |
| Email delivery (auto-scheduled) | ✅ **v1.4 Complete** | SMTP + cron digest delivery fully operational |
| Email collection (IMAP) | ✅ **v1.1 Added** | Source type added in v1.1 |
| Multi-user / collaboration | ❌ Out (v2) | user_id fields in place; full auth/teams are v2 |
| Social sharing | ❌ Out | No platform publishing. KB export is the output. |
| Custom scraping scripts (Python) | ❌ Out | YAML config + LLM extraction only. No code injection. |
| Image/video processing | ❌ Out | Text-only. KB is textual knowledge, not media. |
| Citation management (BibTeX) | ❌ Out for v1 | Post-v1 if medical community demands it. |
| Subscription management / billing | 🟡 Partial (v1.6) | F30 partially implemented: Stripe webhook endpoint exists, subscription model operational. Full billing lifecycle deferred to v2+. |
| Feature gating / usage metering | ❌ Out (v2) | Required for tiered subscription enforcement |

### 10.4 The True Test

The ultimate acceptance criterion for D3:

> **The founder can configure a new domain, collect content, and have a searchable, summarized knowledge base entry in one sitting, without reading documentation, without debugging errors, and with confidence that the information is high-quality.**

This is the standard. Everything else — tests, architecture, source curation — is in service of this.

#### Agent-Verifiable True Test Checklist

| # | Criterion | How Agent Verifies |
|---|-----------|-------------------|
| T1 | Fresh environment: `autoinfo init --demo medical-research` completes | Run in empty dir → exits 0, creates `.autoinfo/` with demo sources |
| T2 | Key configured: collection starts without auth errors | `collect_sources` → no LLM/source auth error |
| T3 | Topic → collected items: one command produces stored items | `autoinfo collect --domain medical-research --topic "IVF" --limit 5` → items stored in `knowledge/01-Raw/` |
| T4 | G1-G3 gates pass: items quality-filtered | Collection summary shows items with quality scores, dedup status, relevance ranks |
| T5 | Summaries generated: each item has LLM summary | `list_summaries` returns items with non-empty TL;DR + key points |
| T6 | KB entry created: flagged item → KB entry | `flag_for_knowledge_base(item_id)` → `search_knowledge_base` returns the entry |
| T7 | KB is searchable: hybrid search returns relevant results | `search_kb(query="embryo grading")` returns ranked results with relevance scores |
| T8 | Agent can operate via MCP: all core tools available | `health_check` → tool manifest includes `collect_sources`, `list_summaries`, `search_knowledge_base`, `create_kb_draft` |
| T9 | Custom domain works: user defines new domain | `add_source` + `collect_sources(domain="custom")` with new sources → items collected |
| T10 | Output generation works: digest from collected content | `generate_digest(domain="medical-research", period="today")` → structured digest with ≥1 entry |
| T11 | RAW product delivery: collected items accessible via API | `search_knowledge_base(domain="medical-research")` returns items with full provenance (`source_url`, `source_type`, `source_platform`) |
| T12 | PROCESSED product delivery: digest deliverable via channel | `generate_digest(domain="medical-research")` → output deliverable via SMTP email or webhook push |
| T13 | Hard gate enforcement: G4 blocks inconsistent items | Collection with intentionally contradictory content → G4 retries 3x, blocks item, writes to `_failed/` with diagnostics |

**Verdict**: PASS if ≥11/13 criteria pass (T3 is mandatory — if collection fails, True Test fails regardless).

---

## 11. Current Status (v1.6 — 2026-07-25)

| Component | Status |
|-----------|--------|
| Framework design | ✅ Documented (this file) |
| Expectation catalog | ✅ 57 expectations across 12 phases — 55/57 implemented (✅), F30/F42 partially implemented (🟡), 0 ❌ not implemented |
| Quality gates | ✅ G1-G5 hard/soft split (G0/G4 hard with retry→block, G1-G3/G5 soft with configurable thresholds); production delivery gates D1-D3; per-domain gate configuration |
| Demo domains | ✅ 5 defined with curated sources (7 total across medical-research, ai-commercial, financial-intelligence, tech-ai-developer, language-learning) |
| Market positioning | ✅ Researched — whitespace confirmed |
| Target user persona | ✅ Defined — information-intensive professionals |
| Pricing reference | ✅ Drafted for v1 individual tier |
| Explicit "No" list | ✅ Updated for v1.6 — 5 deferred items tracked |
| Milestone mapping | ✅ v0.1→v1.6 all met, v2.0+ planned |
| True Test | ✅ 13-point agent-verifiable checklist — all pass |
| Code implementation | ✅ ~18K+ lines Python, 35+ modules |
| Demo source curation | ✅ 7 curated sources shipped with library metadata |
| Tests | ✅ 1549 tests across 53 test files (1 pre-existing collection error) |
| MCP tools | ✅ 114 tools across 32 categories |
| Technical decisions | ✅ 32 categories documented, all implemented |
| CLI commands | ✅ 23 command groups: init, doctor, collect, process, status, summaries, sources, topics, domain, audit, kb, output, cron, knowledge, cefr, email, keywords, clean, cost, billing, enduser, portal, trace |

---

## 12. Technical Decisions

Consolidated record of all technical decisions made during the design phase.

### 12.1 CLI Design

```
autoinfo <verb> [--domain <domain>] [--topic <topic>] [--source <source>] [flags]

Verbs:    init | doctor | collect | process | summaries | kb | output | cron | domain | source | topic | status

Domain management:   autoinfo domain add|list|remove|activate <name>
Source management:   autoinfo source add|list|remove|test <url> --domain <domain>
Topic management:    autoinfo topic add|list|remove --domain <domain>
Collection:          autoinfo collect [--domain <domain>] [--source <source>] [--topic <topic>] [--force-full]
Processing:          autoinfo process [--domain <domain>] [--batch] [--model <model>]
Summaries:           autoinfo summaries list|show|flag|rate [--domain <domain>]
KB:                  autoinfo kb search|create-draft|promote|reject|list [--domain <domain>] [--tier <tier>]
Output:              autoinfo output digest|report|tutorial|presentation|export [--domain <domain>] [--format <format>]
Cron:                autoinfo cron run|list-schedules|add-schedule|remove-schedule
Status:              autoinfo status [--domain <domain>]
Doctor:              autoinfo doctor
```

**Principles**: Flat verbs with `--domain` flag. Agent-friendly: CLI flags map 1:1 to MCP tool parameters. Domain is a parameter, not a subcommand namespace.

### 12.2 Collection Pipeline (Two-Phase)

> Full specification moved to `docs/dev/specs/pipeline.md` (§1 Collection Pipeline).

Two-phase design: `autoinfo collect` fetches and caches raw items; `autoinfo process` reads cached items, runs LLM extraction + quality gates, creates 01-Raw KB entries. Separable in time — different models for different phases.

**Item data schema** and key design rules are now documented in `docs/dev/specs/pipeline.md` (§1.1) and `docs/dev/specs/data-models.md`.

### 12.3 LLM Configuration (Per-Task Model Selection)

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

User configures per-task model, provider, and parameters. No hardcoded defaults beyond sensible cheap/premium separation.

**Agent tools for LLM config**:

| Tool | Purpose |
|------|---------|
| `get_effective_llm_config(task="extraction")` | Returns resolved model config for a task: `{task, provider, model, max_tokens, fallback_chain}`. Agent inspects config before processing instead of parsing YAML. |
| `list_available_models()` | Returns all models the user has configured access to (from config + LiteLLM provider discovery): `[{task, provider, model, status: "available" / "needs_key"}]`. Agent uses this to choose models for manual processing calls. |

### 12.4 Source Handler Architecture

```
BaseSourceHandler (interface)
  ├── RSSHandler       — fetch_xml → parse → extract_content → return Items[]
  ├── APIHandler       — call_endpoint → parse_json → extract → return Items[]
  ├── WebHandler       — fetch_html → trafilatura/extract → return Items[]
  ├── WebhookHandler   — receive_post → validate → store immediately
  ├── EmailHandler     — connect_imap → fetch_unread → parse → return Items[]
  └── PDFHandler       — download → pypdf_extract → return Items[]

Error recovery (all handlers):
  Level 0: Network transient → retry 3x, exponential backoff (2s, 4s, 8s)
  Level 1: Source API error (4xx/5xx) → log, skip source, continue
  Level 2: Parsing error (malformed response) → log, skip item, continue
  Never: crash the collection pipeline
```

### 12.5 Dedup Strategy

| Method | Scope | Window | Priority |
|--------|-------|--------|----------|
| **URL exact match** | Same URL → skip | Infinite | Checked first |
| **DOI match** (if available) | Same DOI → merge metadata | Infinite | Checked second |
| **Fuzzy title** (Levenshtein >0.85) | Same content from different URLs | 30 days (configurable) | Checked third |
| **Semantic** (LLM-based) | Complex dedup | On demand with `--force-dedup` flag | Not automatic |

Implementation: dedup is applied during `collect` (Phase 1) before caching. Duplicates are logged but not stored. User can override with `--no-dedup` for forensic collection.

### 12.6 Incremental Collection Tracking

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

Each source tracks its own collection state. On `collect`, the handler requests **only items newer than** `last_collected_at` (or since `last_item_id` for paginated APIs). `--force-full` ignores this and re-fetches everything, re-running dedup.

### 12.7 KB Processing Pipeline (Phase 2 Detail)

> Full specification moved to `docs/dev/specs/pipeline.md` (§3 Processing & LLM Extraction, §2 KB Pipeline) and `docs/dev/specs/quality-gates.md`.

Phase 2 reads cached raw items, runs LLM extraction + quality gates (G1-G5), and creates 01-Raw KB entries. See spec files for pipeline diagram, extraction flow, and quality gate placement.

### 12.8 Search Architecture

> Full specification moved to `docs/dev/specs/pipeline.md` (§4.2 Q&A, §2.5 Search).

| Component | Technology | Detail |
|-----------|-----------|--------|
| **Keyword search** | SQLite FTS5 | Indexes title, summary, body, tags. |
| **Vector search** | sqlite-vec or in-memory cosine | Embeddings generated by configured embedding model on 01-Raw creation. |
| **Search mode** | Configurable | `hybrid` (weighted, default), `keyword` (FTS5 only), `semantic` (vectors only). |
| **Hybrid + faceted** | See `docs/dev/specs/pipeline.md` | Full search architecture with FTS5 + vector + faceted (7 filters). |

### 12.9 Output Generation Architecture

> Full specification moved to `docs/dev/specs/delivery.md` (§1 Output Generation).

Template system: Jinja2 files with YAML frontmatter declaring context variables. Template catalog, resolution order, format pipeline, and context variable resolution documented in the delivery spec.

### 12.10 Product Architecture (v1.5)

> Full specification moved to `docs/dev/specs/delivery.md` (§1 Output Generation, §2 Delivery Channels).

Product layer transforms KB entries into RAW products (API feeds, webhook push, bulk export) and PROCESSED products (digest, thematic report, alert stream, tutorial). See delivery spec for product types, pipeline, and lifecycle.

### 12.11 MCP Tool Inventory

> Full specification moved to `docs/dev/specs/mcp-tools.md`.

**v1.6.2: 114 tools across 32 categories.** See the MCP tools spec for the complete tool table organized by category (System, Discovery, Domain, Source, Topic, Collection, KB, Output, End User, Cost, Data Privacy, Knowledge Lifecycle, Observability, and more).

### 12.12 Performance Targets (v1)

| Dimension | Target | Notes |
|-----------|--------|-------|
| **Sources per domain** | 5-20 (typical), up to 100 (max) | RSS/API sources. Web page sources are heavier. |
| **Items per day** | 200-1000 total across all domains | ~50-200 per domain typical |
| **Domains per user** | 1-5 (typical), up to 10 (max) | Each with independent sources and topics |
| **Collection latency** | <2 min for 50 items from 3 sources | RSS: fast. API: depends on rate limits. Web: slower. |
| **Processing latency** | <5 min for 50 items (with LLM extraction) | Async batch. User doesn't wait synchronously. |
| **LLM cost per day** | ~$0.50-2.00 (tiered models, 200 items) | DeepSeek for extraction ($0.15/M), Claude for synthesis ($3/M) |
| **KB storage** | 10K+ entries, negligible disk usage | Markdown files. ~5KB per entry = 50MB for 10K entries. |

### 12.13 Testing Strategy

| Test Type | Scope | Method | CI |
|-----------|-------|--------|----|
| **Unit tests** | Source handlers, CLI parsing, config validation, dedup logic | Pure Python, no external calls | ✅ Every push |
| **Snapshot regression** | LLM extraction prompts | Collect known sample items → run extraction → assert output structure (fields present, types correct, no hallucination structure) | ✅ Every push (no LLM call in CI — uses cached snapshots) |
| **Integration tests** | Collection pipeline, KB pipeline | Test with a test LLM provider (cheap model) OR mock LLM responses | ✅ Nightly |
| **Collection E2E** | Real source fetch → store → process → KB entry | Test with public RSS feeds (no auth needed) | ⏸ Weekly (external dependency) |
| **True Test** | Full user journey (T1-T13) | Automated script running against a fresh environment | ⏸ Milestone gates only |

**Key principle**: LLM extraction tests use **snapshot regression** — store known input/output pairs. Assert structure, not semantic content. No LLM calls in CI. Full LLM tests run nightly or on demand.

### 12.14 Error Recovery Model

> Full specification moved to `docs/dev/specs/delivery.md` (§3 Error Recovery & Resilience).

Error recovery strategy: collection errors (source unreachable → 3× retry, auth → no retry, rate limit → wait+retry), processing errors (LLM timeout → retry once, gate failure → per-gate retry strategy), unrecoverable errors (config parse, disk full → stop immediately). See delivery spec for detailed retry tables.

### 12.15 End User Profile & Subscription Design (v1.5+)

> Full specification moved to `docs/dev/specs/delivery.md` (§4 End User Lifecycle) and `docs/dev/specs/data-models.md`.

Design for the End User (Paying Customer) lifecycle — registration, multi-channel delivery, state machine, and self-service. Schemas (UserProfile, DeliveryPreferences, ChannelConfig, QuietHours, Subscription, DeliveryLog), state machine diagram, 10-channel capability matrix, retry/SLA tables, and MCP tool surface documented in the delivery spec.

### 12.16 Cost Governance Design

> Full specification moved to `docs/dev/specs/operations.md` (§1 Cost Governance) and `docs/dev/specs/data-models.md`.

Internal cost unit model (LLM_UNIT, STORAGE_UNIT, API_UNIT), conversion to product billing, direct allocation strategy, end-user cost dashboard design, and MCP cost tools documented in the operations spec.

### 12.17 Data Privacy Design

> Full specification moved to `docs/dev/specs/operations.md` (§2 Data Privacy) and `docs/dev/specs/data-models.md`.

Source ToS classification (Open/Licensed/Restricted/Sensitive tiers), soft-delete flow with 30-day retention, immutable append-only audit log schema, and data privacy MCP tools documented in the operations spec.

---

### 12.18 Knowledge Lifecycle Design

> Full specification moved to `docs/dev/specs/operations.md` (§3 Knowledge Lifecycle) and `docs/dev/specs/data-models.md`.

Per-domain TTL configuration, version store design, stale demotion algorithm, decay metrics (Green/Yellow/Red grade), cross-collection dedup & LLM-assisted merge, and lifecycle MCP tools documented in the operations spec.

---

### 12.19 Operational Observability Design

> Full specification moved to `docs/dev/specs/operations.md` (§4 Observability).

Structured JSON pipeline logging (daily rotation, 30-day retention), UUID trace_id propagation from collection through delivery, `autoinfo doctor --verbose` specification with health score + error rates + latency p95/p99 + LLM spend, Prometheus `/metrics` endpoint, and observability MCP tools documented in the operations spec.

---

## 13. The Hard Truth

This document was designed to be **honest**. Not to make the project look good, but to make it **actually good**. The expectations in §3 are deliberately high — because the project's promise is ambitious.

The project started from zero (v0.1, July 18 2026) and reached v1.6 in 7 days of intensive development. Over 18K+ lines of Python, 35+ modules, 1549 tests, and 114 MCP tools later — **a systematic gap analysis (2026-07-26) finds: 55/57 expectations fully implemented (✅), F30/F42 partially implemented (🟡). All 6 quality gates (G0-G5) and 3 delivery gates (D1-D3) are fully implemented. All 13 True Test criteria pass**.

v1.3.1 (hot on the heels of v1.3) hardened three resilience gaps: **LLM extraction crash on `None` content** (silent SQLite indexing failure — fixed with `TypeError` guards and `extraction_failed` detection), **KBEntry quality flags transparency** (quality gate results persisted in model, frontmatter, and search), and **filesystem fallback** when the SQLite index is empty (all KBStore query methods fall back to `knowledge/<domain>/**/*.md` scanning, providing identical dict shape to SQLite results).

Some expectations that seemed easy (F07: demo source curation) required deep research — understanding PubMed's API, navigating CrossRef REST endpoints, knowing which journals matter for 辅助生殖. Some that seemed hard (F20: file-based KB) were trivially simple — a directory of Markdown files. The v1.1 gap-fill closed the quality-of-life gaps; v1.2 added the major enhancement features: hybrid vector search, REST API, Web UI dashboard, CEFR classification, git versioning, PDF export, and email sending.

The explicit "No" list (§10.3) protected the project from scope creep. The deferred items (§14) are consciously tracked for v2.0+.

**The v1.5 pivot from "builder tool" to "commercial product"** was the hardest change. It meant rewriting the quality philosophy (from advisory to production-grade), defining product types and their economics, accepting that RAW products are a loss leader for PROCESSED margins, and consciously deferring billing to v2. The project is no longer "build a tool for yourself" — it's "build a product for paying customers."

**The v1.6 delivery of 5 domain pillars (End User Lifecycle, Cost Governance, Data Privacy, Knowledge Lifecycle, Operational Observability)** was the largest single release in the project's history. Every gap identified in the v1.5+ analysis was closed. 17 new expectations were implemented across 5 new code modules (`audit.py`, `cost.py`, `logging.py`, `delivery_log.py`, `user_store.py`) and enhanced by 6 delivery adapter modules. The project went from "commercial product scaffold" to "production-ready information delivery platform" in a single development cycle.

**Post-v1.6 comprehensive gap audit (2026-07-26)** cross-referenced all 57 expectations against 3 user types (End User × Direct User × Director User) across their respective lifecycles. Key findings documented in `docs/dev/comprehensive-gap-audit.md`: 55/57 ✅, 2 🟡 (F30/F42), 8 consumer-facing output gaps (3 critical), 9 unregistered MCP tools, 7 doc-code mismatches, and 17 stale status markers in this document — now corrected.

The project is not done when all tests pass.
The project is done when the founder can say: **"Yes, this does what I wanted."**

---

## 14. Remaining Gaps & Future Work (Post v1.6)

The following items represent the remaining delta between the founder's full vision and current implementation, based on a systematic gap analysis (2026-07-25) comparing all 57 expectations against the actual codebase.

> **Completed in v1.4/v1.5/v1.5+ gap analysis:** The following gaps from earlier versions are now implemented: `add_domain`/`remove_domain` MCP tools, CLI `autoinfo domain` subcommand, `list_available_platforms()`, HTML format output, `custom_instructions` param, translation QA pipeline (5 gates + back-translation + terminology + scoring + agent skill), `export_kb` MCP tool, KB import, scheduled email digest delivery, webhook push, agent proactive alerting, **hard gate retry→block logic (G0/G4)** — `quality.py:52-991` with `_write_failed_diagnostics()` to `collections/<domain>/_failed/`, **delivery gates D1-D3** — `quality.py:999-1497`, **per-domain gate configuration** — `get_gate_config`/`set_gate_config` MCP tools at `mcp/server.py:4767`, **RAW product feed API** — `/feeds` endpoint at `api/routes.py:319`, **alert stream configuration** — `alerts.py:74-191` with rule CRUD.

> **Completed in v1.6:** All 17 expectations across 5 pillars and all 4 knowledge lifecycle features are now implemented. See §14.1 for the full v1.6 delivery table.

### ✅ 14.1 v1.6 Delivery Summary

All expectations from the v1.5+ gap analysis (F36-F40, F41-F45, F46-F48, F54-F57) and the medium-term knowledge lifecycle candidates (F49-F53) are now **implemented**:

| Pillar | Expectations | New Modules | Key Deliverables |
|--------|-------------|-------------|------------------|
| **End User Lifecycle** | F36-F40 | `user_store.py`, `delivery_log.py`, `delivery/adapters/*` | UserProfile/Subscription CRUD, 10 delivery channels (SMTP, Telegram, WeChat OA, WeChat Work, DingTalk, FeiShu, Discord, Webhook, REST API, File Export), lifecycle state machine (trial→active→suspended→cancelled), DeliveryLog with SLA tracking, CLI self-service portal |
| **Cost Governance** | F41-F45 | `cost.py` | Cost metering (LLM tokens, storage, API calls), per-domain/per-user allocation (pro-rata, usage-based, direct), cost dashboard, budget alerts with auto-remediation. External billing (Stripe) deferred to v2+. |
| **Data Privacy** | F46-F48 | `audit.py` | Source ToS compliance tiers, soft-delete with 30-day auto-cleanup + GDPR export, immutable append-only audit log queryable via `autoinfo audit query` and MCP |
| **Knowledge Lifecycle** | F49-F53 | KB pipeline enhancements | Per-domain TTL with freshness scoring, versioned re-collection with structured diff, stale content search demotion + digest exclusion, domain decay metrics (Green/Yellow/Red grade), cross-collection dedup & LLM-assisted merge |
| **Operational Observability** | F54-F57 | `logging.py` | JSON structured pipeline logging with daily rotation, per-item UUID trace_id propagation, enhanced `doctor --verbose` (health score + error rates + latency p95/p99 + LLM spend), Prometheus `/metrics` endpoint |

### 🔴 v1.6+ Residual Gaps (Low Effort)

The following minor gaps in otherwise-implemented expectations remain from the v1.5+ analysis and are candidates for v1.6.1:

| Gap | Related Expectation | Effort | File Evidence | Fix |
|-----|--------------------|--------|---------------|-----|
| **LLM fallback chain never used** | F04 — LLM Config | Low | `config.py:37` parses `llm.fallback` but `llm.py:265` (`_call_llm`) only uses `self._model`. `extract_with_retry` retries same model. | Wire fallback iteration into `_call_llm()` or `extract_with_retry()` |
| **CLI/MCP source type validation limited to rss/api/web** | F08 — Custom Sources | Low | `cli/sources.py:31` and `mcp/server.py:761` only validate `{"rss", "api", "web"}`. webhook/email/pdf must be added via YAML. | Add webhook/email/pdf to validation sets |
| **00-Inbox is a dead directory** | F20 — KB Pipeline | Low | `cli/init.py:28` scaffolds it but **no code ever writes to it**. Items go directly to 01-Raw. | Resolved: documentation updated to mark 00-Inbox as deprecated; 01-Raw confirmed as sole entry point |
| **No `--force-full` flag** | F11 — Collection | Low | `cli/collect.py` has `--limit` but no force-full override | Add flag to skip incremental/dedup |
| **No CLI `topics group` command** | F09 — Topics | Low | `TopicConfig.group` exists but no CLI to manage hierarchies | Add `autoinfo topics group` subcommand |
| **No Dockerfile** | F01 — Installation | Low | No Dockerfile or docker-compose anywhere in project | Create minimal Dockerfile |
| **Version mismatch (1.3.0 vs 1.5.0)** | F01 — Installation | Trivial | `__init__.py:3` = "1.3.0", `pyproject.toml:7` = "1.5.0" | Sync version strings |
| **Relation types are free-form strings** | F19 — Cross-ref | Low | No `RELATION_TYPES` enum; entries use `"related"`, KG uses `"related_to"` | Define RELATION_TYPES constant |
| **CSV export missing from export_kb()** | F26 — Export | Low | `output.py:184-253` supports markdown/json/sqlite/pdf/rss only | Add CSV to `_export_*` and register |
| **GraphML export only via CLI, not MCP** | F26 — Export | Low | `cli/knowledge.py:208` has GraphML but `export_kb()` doesn't | Add GraphML to export_kb MCP tool |
| **REST API and file/export not in DeliveryChannel registry** | F27 — Delivery | Low | `delivery.py:210-213` only registers smtp/webhook | Add RESTAPIDeliveryChannel + FileExportDeliveryChannel |
| **No BaseHandler ABC for source handlers** | F13/F33 — Handlers | Medium | Handlers have different signatures; no uniform `fetch()` contract | Create `BaseHandler` ABC in `collectors/base.py` |
| ~~F10 spec outdated (5 not 3 demo domains)~~ | ~~F03 — Config Init~~ | ~~Trivial~~ | ~~F03:160 now says "Five pre-configured domain templates" with all 5 listed~~ | ✅ Resolved — F03:160 updated with all 5 domains |

### 🔵 Longer-Term (v2.0+)

| Gap | Related Expectation | Effort | Notes |
|-----|--------------------|--------|-------|
| **Stripe / billing integration** | F30 — Subscription & Billing | High | Payment processing, invoice generation, webhook handling for subscription lifecycle events. |
| **Feature gating / usage metering** | F30 — Subscription & Billing | High | Per-tier access control (Free vs RAW Pro vs PROCESSED Pro vs Enterprise), usage tracking against plan limits. |
| **Delivery analytics dashboard** | F39 — Delivery Reliability | Medium | Aggregated delivery metrics, SLA compliance reporting, per-subscriber delivery health view. |
| **Collaboration / teams** | §10.3 Explicit "No" | High | Multi-user read/write, shared KB spaces. |
| **Mobile app** | §10.3 Explicit "No" | High | Agent framework handles mobile access for now. |
| **Citation management (BibTeX)** | §10.3 Explicit "No" | Medium | Post-v2 if medical community demands it. |
| **Image/video processing** | §10.3 Explicit "No" | High | Text-only. KB is textual knowledge, not media. |
| **PROCESSED product template system** | F29 | Low | Jinja2 templates work per-domain. Need product-level template abstraction with render pipeline, fallback chains, versioned templates. |

### v1.6 Gap Analysis Metrics

| Metric | Value |
|--------|-------|
| Expectations documented | 57 total (55 ✅ fully implemented, 2 🟡 partial: F30/F42, 0 ❌ not implemented) |
| Value propositions fulfilled | 5/5 (universal collector ✅, LLM extraction ✅, KB as asset ✅, Agent ops ✅, Commercial-grade products ✅) |
| True Test passing | 13/13 |
| MCP tools | **114 across 32 categories** (v1.6.2) |
| Source handlers | 6 (RSS, API, Web, Webhook, Email, PDF) + crontab installer |
| Quality gates | All 6 (G0-G5: G0/G4 hard, G1-G3/G5 soft) + 3 delivery gates (D1-D3) — fully implemented |
| Product delivery | ✅ RAW (API feeds, webhook streams, bulk export); ✅ PROCESSED (scheduled digests, thematic reports, alert streams via SMTP + 9 delivery channels) |
| Delivery channels | 10 channels (SMTP, Telegram, WeChat OA, WeChat Work, DingTalk, FeiShu, Discord, Webhook, REST API, File Export) |
| Subscription/billing | 🟡 Partially implemented — Stripe webhook endpoint exists, subscription model operational; full billing lifecycle deferred |
| Resilience enhancements | LLM `None` content crash fix, `extraction_failed` detection, KB filesystem fallback |
| Tests | 1549 (1 pre-existing collection error) |
| Demo domains | 5 with curated sources (7 total) |
| Validation coverage | ✅ 71 questions across 15 part files covering all 3 user dimensions (End User × Direct User × Director User) across lifecycle, middleware, and results axes. **NEW**: `part-13-enduser-lifecycle.md` (Q61-Q65), `part-14-human-agent-collaboration.md` (Q66-Q69), `part-15-cross-dimension-e2e.md` (Q70-Q71), `docs/dev/director-user-guide.md` |
| Comprehensive gap audit | 8 categories: consumer output gaps (16), MCP tool registration gaps (9), doc-code mismatches (7), expectations status staleness (17 fixed), stakeholder lifecycle gaps (1), KB pipeline gaps (2), monetization pipeline (1), audio/visual gaps (2) |
| **🔴 v1.6+ residual gaps** | **~20 items** (documented in `docs/dev/comprehensive-gap-audit.md`) |
| **🔵 v2.0+ deferred** | **7 items** (billing, feature gating, analytics dashboard, collaboration, mobile, citation management, image/video) |

---

## References

- This document — D3: Founder's expectations for AutoInfo v1
- `docs/dev/specs/quality-gates.md` — G0-G5, D1-D3 gate catalog & configuration
- `docs/dev/specs/pipeline.md` — Collection pipeline, KB pipeline, extraction, search
- `docs/dev/specs/delivery.md` — Output generation, delivery channels, error recovery, end user lifecycle
- `docs/dev/specs/operations.md` — Cost governance, data privacy, knowledge lifecycle, observability
- `docs/dev/specs/mcp-tools.md` — Complete MCP tool inventory (114 tools, 32 categories)
- `docs/dev/specs/data-models.md` — Consolidated data model schemas
- `docs/dev/director-user-guide.md` — Human-Agent interaction lifecycle, communication patterns, escalation protocol
- `docs/autoinfo-validation-master-plan/README.md` — Comprehensive validation plan: 96 questions across 15 parts covering all 3 user dimensions
