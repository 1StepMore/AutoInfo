# New Demo Domain Guide

> Step-by-step instructions for adding a new demo domain to AutoInfo.
> Covers source research, extraction schema definition, configuration creation,
> and validation.
>
> **Target audience**: AutoInfo developers and domain curators.
> **Prerequisites**: AutoInfo installed (`pip install -e ".[dev]"`), working
> MCP server or CLI access.

---

## Table of Contents

1. [Overview](#overview)
2. [Step 1: Research Sources](#step-1-research-sources)
3. [Step 2: Define Extraction Schema](#step-2-define-extraction-schema)
4. [Step 3: Create Domain Config](#step-3-create-domain-config)
5. [Step 4: Create Source Configs](#step-4-create-source-configs)
6. [Step 5: Define Topics](#step-5-define-topics)
7. [Step 6: Validate the Domain](#step-6-validate-the-domain)
8. [Example Source Candidates](#example-source-candidates)
9. [New Domain Blueprint: 4 Demo Candidates](#new-domain-blueprint-4-demo-candidates)
10. [Troubleshooting](#troubleshooting)
11. [Reference: Existing Domain Patterns](#reference-existing-domain-patterns)

---

## Overview

AutoInfo domains are configured via YAML files and consist of:

- **Domain metadata** — name, description (human-readable)
- **Curated sources** — RSS feeds, API endpoints, web targets, specialized collectors
- **Topic structure** — thematic groupings with keyword lists for filtering
- **Extraction schema** — field mappings per source type (title, content, authors, dates)
- **Output templates** — digest, report formats (inherited from domain type)

### Domain hierarchy

```
src/autoinfo/data/domains/
├── <domain-name>/
│   ├── sources.yaml    # Domain config + sources + topics (single file pattern)
│   ├── topics.yaml     # Optional: separate topics file (for complex domains)
│   └── templates/      # Optional: custom output templates
└── ...
```

### Available source types

| Type | Handler | Use Case |
|------|---------|----------|
| `rss` | RSSHandler | Blogs, news sites, any RSS/Atom feed |
| `api` | HttpApiHandler/REST | REST APIs with JSON responses |
| `web` | WebScraperHandler | Static web pages (trafilatura) |
| `web_playwright` | PlaywrightHandler | JS-rendered pages |
| `email` | EmailHandler | IMAP mailbox ingestion |
| `pdf` | PDFHandler | PDF document parsing |
| `webhook` | WebhookHandler | Push-based ingestion |
| `reddit` | RedditHandler | Reddit subreddit monitoring |
| `youtube` | YouTubeHandler | YouTube channel/search tracking |
| `bilibili` | BilibiliHandler | Bilibili (B站) video search |
| `spotify` | SpotifyHandler | Podcast/show episodes |
| `apple_podcasts` | ApplePodcastsHandler | Apple Podcasts search |
| `dblp` | DBLPHandler | Computer science bibliography |
| `openalex` | OpenAlexHandler | Open scholarly research |
| `nyt` | NYTHandler | New York Times API |
| `pubmed` | PubMedHandler | PubMed E-utilities |
| `semantic_scholar` | SemanticScholarHandler | Semantic Scholar API |
| `uspto` | USPTOHandler | US patent data |
| `ap_api` | APAPIHandler | Associated Press API (paid) |
| `reuters_mcp` | ReutersMCPHandler | Reuters (paid, MCP-based) |
| `quandl` | QuandlHandler | Financial/economic data |

---

## Step 1: Research Sources

For each new domain, identify **3–5 reliable, publicly accessible sources**:

1. **Search for RSS feeds** — Append `/feed`, `/rss`, `feed.xml` to known sites
2. **Check API availability** — Prioritize free-tier APIs over scraping (rate limits matter)
3. **Verify feed stability** — Use `webfetch` or `autoinfo sources test` to confirm the feed returns structured content
4. **Document metadata** — For each source, record:
   - Name (slug-friendly, e.g., `variety-rss`)
   - Type (`rss`, `api`, `web`, or specialized type from table above)
   - URL / endpoint
   - API key requirements (`none`, `optional`, `required`)
   - Rate limits (requests per minute/second)
   - Quality tier (1 = authoritative, 2 = secondary, 3 = supplementary)
   - Content coverage / topics covered

### Source verification checklist

| Check | Command / Method |
|-------|-----------------|
| RSS feed parses | `python -c "import feedparser; print(feedparser.parse('URL').bozo)"` |
| API returns data | `curl -I URL` + inspect response body |
| No paywall | Browse a few items in the feed |
| Content structure clear | Check for title, description, publication date, categories |
| Rate limit documented | Read API docs or `robots.txt` |

---

## Step 2: Define Extraction Schema

Map the expected content fields for each source type. Fields vary by source:

### Common fields (all sources)

```yaml
field_mapping:
  id: "id"              # Unique identifier (DOI, GUID, slug)
  title: "title"        # Required — article/video/document title
  content: "content"    # Body text or abstract
  source_url: "link"    # Original URL
  published_date: "published"  # Publication date (ISO-8601 preferred)
```

### RSS-specific fields

```yaml
# For WordPress/Medium RSS feeds
field_mapping:
  id: "id"
  title: "title"
  content: "content"      # content:encoded or summary
  source_url: "link"
  published_date: "published"
  authors: "author"       # dc:creator element
  categories: "tags"      # category elements
```

### API-specific fields (JSON)

```yaml
# For REST APIs with JSON response
settings:
  query_param: "q"          # URL query parameter name
  json_path: "response.items"  # JSONPath to items array
  field_mapping:
    id: "id"
    title: "title"
    content: "description"
    source_url: "url"
```

### Per-domain extraction schema suggestions

| Domain | Key Fields | Optional Fields |
|--------|-----------|-----------------|
| Online Video/OTT | title, content (description), source_url, published_date, categories | platform (Netflix/Amazon/Hulu), genre, cast, rating |
| Financial News | title, content, source_url, published_date, ticker_symbols | analyst_rating, price_target, sector |
| Online Education | title, content (summary), source_url, published_date, author | platform (Coursera/Udemy), skill_level, duration |
| Legal/Compliance | title, content, source_url, published_date, author, court | case_number, statute, regulation, jurisdiction |

---

## Step 3: Create Domain Config

### Via CLI

```bash
autoinfo domain add --name "online-video-ott" \
  --description "Online video, OTT platforms, and streaming industry news"
```

### Via YAML (recommended for demos)

Create `src/autoinfo/data/domains/<domain-name>/sources.yaml` following the
pattern in [§ Reference: Existing Domain Patterns](#reference-existing-domain-patterns).

### Config structure

```yaml
# AutoInfo demo domain: <domain-name>
# <Brief description>
name: <domain-name>
description: "<Human-readable description>"

sources:
  - name: <source-name>
    type: <source-type>
    url: <endpoint-url>
    quality_tier: <1|2|3>
    frequency: <daily|hourly|weekly>
    access: <free|api_key>
    rate_limit: <number>
    enabled: true
    settings:
      # Source-specific settings
    field_mapping:
      # Extraction field mapping

topics:
  - name: "<Topic Name>"
    keywords:
      - keyword1
      - keyword2
```

### Required fields per source type

| Field | Required | Description |
|-------|----------|-------------|
| `name` | ✅ | Unique slug for the source |
| `type` | ✅ | One of the types from [§ Overview](#overview) |
| `url` | ✅ | Base URL for the source |
| `quality_tier` | ✅ | 1 (authoritative), 2 (secondary), 3 (supplementary) |
| `access` | ✅ | `free`, `api_key`, `paid` |
| `rate_limit` | ✅ | Max requests per second/minute |
| `enabled` | ✅ | Set to `true` for active sources |
| `frequency` | ✅ | Collection cadence hint |

### Optional fields

| Field | Purpose |
|-------|---------|
| `requires_key` | When `access: api_key`, set `true` |
| `api_key_optional` | For sources with tiered access (e.g., PubMed) |
| `settings.query_param` | API query parameter name |
| `settings.json_path` | JSONPath to extract items from API response |
| `field_mapping` | Maps source response fields to KB fields |
| `topics` | Source-level topic association |
| `fallback_rss` | RSS fallback URL for API sources |

---

## Step 4: Create Source Configs

For each source in your domain, create a source entry in `sources.yaml`.

### Pattern: Simple RSS source

```yaml
- name: variety-rss
  type: rss
  url: https://variety.com/feed/
  quality_tier: 2
  frequency: hourly
  access: free
  rate_limit: 10
  enabled: true
```

### Pattern: API source with field mapping

```yaml
- name: some-api
  type: api
  url: https://api.example.com/v1/items
  quality_tier: 1
  frequency: daily
  access: api_key
  requires_key: true
  rate_limit: 10
  settings:
    query_param: q
    json_path: results.items
    field_mapping:
      id: uuid
      title: headline
      content: body_text
      source_url: canonical_url
      published_date: date_published
```

### Pattern: Specialized collector (YouTube, Reddit, etc.)

```yaml
- name: youtube-streaming-news
  type: youtube
  url: https://www.googleapis.com/youtube/v3
  quality_tier: 2
  frequency: daily
  access: api_key
  requires_key: true
  rate_limit: 100
  enabled: true
  settings:
    query: "streaming news OTT"
    region: US
```

---

## Step 5: Define Topics

Topics group content into thematic buckets and drive keyword-based filtering.

### Topic structure

```yaml
topics:
  - name: "Industry News"
    keywords:
      - streaming
      - OTT
      - video on demand
      - cord cutting
      - SVOD
      - AVOD
  - name: "Platform Launches"
    keywords:
      - Netflix
      - Disney+
      - Max
      - Paramount+
      - new release
      - streaming premiere
```

### Tips for good topic definitions

- **3–8 keywords per topic** — too few misses content, too many are noisy
- **Use domain-specific terminology** — e.g., "SVOD" for streaming, "10-K" for finance
- **Include both broad and specific terms** — "stock market" + "S&P 500" + "earnings"
- **Avoid overly generic keywords** — "news" or "update" match everything

---

## Step 6: Validate the Domain

### 1. Test source connectivity

```bash
autoinfo sources test --domain <domain-name> --source <source-name>
```

Expected output: `✓ <source-name> — 5 items fetched (200 OK)`

### 2. Run a trial collection

```bash
autoinfo collect --domain <domain-name> --limit 10
autoinfo status
```

### 3. Process and review

```bash
autoinfo process --domain <domain-name>
autoinfo summaries list --domain <domain-name>
```

### 4. Check extraction quality

```bash
# Verify KB entries were created
autoinfo kb search --domain <domain-name> --query "*"
# Check for quality gate failures
autoinfo status --domain <domain-name> --verbose
```

### 5. Verify via MCP

```bash
# Python snippet using MCP tools
python -c "
from autoinfo.mcp.client import MCPClient
c = MCPClient()
print(c.list_domains())
print(c.list_sources(domain='<domain-name>'))
"
```

---

## Example Source Candidates

> **Note on verification**: URLs below have been tested for RSS validity and
> accessibility. Some commercial API sources (marked "requires key") need user
> registration. All RSS feeds are free and publicly accessible at time of writing.
>
> To verify a source yourself:
> ```bash
> python -c "import feedparser; f=feedparser.parse('FEED_URL'); print(len(f.entries), 'entries'); print('bozo:', f.bozo)"
> ```

### D2: Online Video / OTT (Streaming Industry)

| Source Name | Type | URL | Auth | Rate Limit | Tier | Notes |
|------------|------|-----|------|-----------|------|-------|
| Variety RSS | `rss` | `https://variety.com/feed/` | None | 10 req/s | 2 | WordPress RSS; film, TV, streaming industry news. ✅ Verified |
| Hollywood Reporter RSS | `rss` | `https://www.hollywoodreporter.com/feed/` | None | 10 req/s | 2 | Entertainment business, streaming deals. ✅ Verified |
| Netflix Tech Blog | `rss` | `https://netflixtechblog.com/feed` | None | 10 req/s | 2 | Medium RSS; OTT platform engineering. ✅ Verified |
| The Verge — Streaming | `rss` | `https://www.theverge.com/rss/streaming/index.xml` | None | 10 req/s | 2 | Atom feed; consumer streaming news. ✅ Verified |
| YouTube (via YouTubeHandler) | `youtube` | `https://www.googleapis.com/youtube/v3` | API key | 100 req/d | 2 | Track OTT/streaming channels. Requires Google API key. |

**Extraction schema hints**:
- `platform` (Netflix, Disney+, Amazon, etc.)
- `content_type` (series, film, documentary, live event)
- `genre` (drama, comedy, reality, sports)
- `streaming_exclusive` (boolean)

### D3: Financial News / Markets

| Source Name | Type | URL | Auth | Rate Limit | Tier | Notes |
|------------|------|-----|------|-----------|------|-------|
| CNBC RSS | `rss` | `https://www.cnbc.com/id/100003114/device/rss/rss.html` | None | 10 req/s | 1 | US top news & analysis, market coverage. ✅ Verified |
| MarketWatch Top Stories | `rss` | `https://feeds.content.dowjones.io/public/rss/mw_topstories` | None | 10 req/s | 1 | Business/financial news. ✅ Verified |
| SEC EDGAR (filings) | `rss` | `https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=10-K&output=atom` | None | 10 req/s | 1 | Corporate filings (Atom feed). Already used in `financial-intelligence` domain. |
| FRED API | `api` | `https://api.stlouisfed.org/fred/` | API key | 120 req/min | 1 | Economic indicators (GDP, inflation, unemployment). Already used in `financial-intelligence` domain. |
| Alpha Vantage | `api` | `https://www.alphavantage.co/query` | API key | 5 req/min | 1 | Stock market data, forex, crypto. Already used in `financial-intelligence` domain. |

**Extraction schema hints**:
- `ticker_symbols` (list of mentioned stock tickers)
- `sector` (tech, healthcare, energy, finance)
- `market_event_type` (earnings, merger, IPO, dividend)
- `analyst_rating` (buy, sell, hold)
- `economic_indicator` (GDP, CPI, unemployment rate)

### D6: Online Education / EdTech

| Source Name | Type | URL | Auth | Rate Limit | Tier | Notes |
|------------|------|-----|------|-----------|------|-------|
| Coursera Blog | `rss` | `https://blog.coursera.org/feed/` | None | 10 req/s | 1 | Official Coursera blog; online learning, partnerships, AI in education. ✅ Verified |
| Open Culture | `rss` | `https://www.openculture.com/feed` | None | 10 req/s | 2 | Free educational media, courses, and culture. ✅ Verified |
| EdTech Magazine | `rss` | `https://edtechmagazine.com/rss.xml` | None | 10 req/s | 2 | Education technology news (alternative). |
| Project Gutenberg | `rss` | `https://www.gutenberg.org/cache/epub/feeds/today.rss` | None | 5 req/s | 1 | Public domain books. Already used in `language-learning` domain. |
| Udemy Blog | `rss` | `https://blog.udemy.com/feed/` | None | 10 req/s | 2 | Online course marketplace updates. |

**Extraction schema hints**:
- `platform` (Coursera, Udemy, edX, Khan Academy)
- `skill_level` (beginner, intermediate, advanced)
- `subject_area` (computer science, business, arts, humanities)
- `credential_type` (certificate, specialization, degree, MOOC)
- `duration_hours` (estimated time to complete)

### D8: Legal / Compliance

| Source Name | Type | URL | Auth | Rate Limit | Tier | Notes |
|------------|------|-----|------|-----------|------|-------|
| SCOTUSblog | `rss` | `https://www.scotusblog.com/feed/` | None | 10 req/s | 1 | US Supreme Court analysis and news. ✅ Verified |
| Harvard Law — Corp Gov Forum | `rss` | `https://corpgov.law.harvard.edu/feed/` | None | 10 req/s | 1 | Corporate governance, SEC, compliance. ✅ Verified |
| Law.com | `rss` | `https://www.law.com/feed/` | None | 10 req/s | 2 | Legal industry news and analysis. |
| SEC EDGAR (compliance) | `rss` | `https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&output=atom` | None | 10 req/s | 1 | Current reports (material events). Already used in `financial-intelligence` domain. |
| IAPP Privacy Tracker | `web` | `https://iapp.org/news/topics/privacy/` | None | 5 req/min | 1 | International privacy regulation news. (No public RSS; use web scraping.) |

**Extraction schema hints**:
- `jurisdiction` (US federal, US state, EU, UK, APAC)
- `practice_area` (corporate, privacy, securities, IP, litigation)
- `regulatory_body` (SEC, FTC, DOJ, FCA, ESMA, EDPB)
- `case_number` (for court decisions)
- `statute_reference` (DGCL, GDPR, CCPA, SOX, etc.)

---

## New Domain Blueprint: 4 Demo Candidates

The following blueprints provide ready-to-use `sources.yaml` configurations for
four new demo domains. Each follows the existing pattern established by the 5
current demo domains.

### Blueprint: Online Video / OTT (`online-video-ott`)

```yaml
# AutoInfo demo domain: Online Video / OTT
# Tracks streaming industry news, OTT platform developments, and video content trends
name: online-video-ott
description: "Online video, OTT platforms, and streaming industry intelligence"

sources:
  - name: variety
    type: rss
    url: https://variety.com/feed/
    quality_tier: 2
    frequency: hourly
    access: free
    rate_limit: 10

  - name: hollywood-reporter
    type: rss
    url: https://www.hollywoodreporter.com/feed/
    quality_tier: 2
    frequency: hourly
    access: free
    rate_limit: 10

  - name: netflix-tech-blog
    type: rss
    url: https://netflixtechblog.com/feed
    quality_tier: 2
    frequency: daily
    access: free
    rate_limit: 10

  - name: verge-streaming
    type: rss
    url: https://www.theverge.com/rss/streaming/index.xml
    quality_tier: 2
    frequency: hourly
    access: free
    rate_limit: 10

  - name: youtube-streaming
    type: youtube
    url: https://www.googleapis.com/youtube/v3
    quality_tier: 3
    frequency: daily
    access: api_key
    requires_key: true
    rate_limit: 100
    enabled: false

topics:
  - name: "Streaming Platforms"
    keywords:
      - Netflix
      - Disney+
      - Max
      - Paramount+
      - Peacock
      - Amazon Prime
      - Apple TV+
      - Hulu
  - name: "Industry Trends"
    keywords:
      - streaming
      - OTT
      - cord cutting
      - SVOD
      - AVOD
      - FAST
      - video on demand
  - name: "Content & Production"
    keywords:
      - original series
      - premiere
      - streaming exclusive
      - content deal
      - production
      - licensing
```

### Blueprint: Financial News (`financial-news`)

```yaml
# AutoInfo demo domain: Financial News
# Tracks market news, economic indicators, and corporate events
name: financial-news
description: "Financial news and market intelligence — market data, economic indicators, corporate filings"

sources:
  - name: cnbc
    type: rss
    url: https://www.cnbc.com/id/100003114/device/rss/rss.html
    quality_tier: 1
    frequency: hourly
    access: free
    rate_limit: 10

  - name: marketwatch
    type: rss
    url: https://feeds.content.dowjones.io/public/rss/mw_topstories
    quality_tier: 1
    frequency: hourly
    access: free
    rate_limit: 10

  - name: sec-edgar
    type: rss
    url: https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=10-K&output=atom
    quality_tier: 1
    frequency: daily
    access: free
    rate_limit: 10

topics:
  - name: "Market Trends"
    keywords:
      - stock market
      - S&P 500
      - treasury yields
      - market rally
      - bear market
      - volatility
  - name: "Earnings Reports"
    keywords:
      - earnings
      - quarterly results
      - revenue
      - EPS
      - guidance
      - fiscal
  - name: "Economic Indicators"
    keywords:
      - GDP
      - inflation
      - CPI
      - interest rates
      - Federal Reserve
      - unemployment
```

### Blueprint: Online Education (`online-education`)

```yaml
# AutoInfo demo domain: Online Education
# Tracks online learning platforms, EdTech developments, and educational content
name: online-education
description: "Online education intelligence — learning platforms, EdTech trends, educational content"

sources:
  - name: coursera-blog
    type: rss
    url: https://blog.coursera.org/feed/
    quality_tier: 1
    frequency: daily
    access: free
    rate_limit: 10

  - name: open-culture
    type: rss
    url: https://www.openculture.com/feed
    quality_tier: 2
    frequency: daily
    access: free
    rate_limit: 10

  - name: udemy-blog
    type: rss
    url: https://blog.udemy.com/feed/
    quality_tier: 2
    frequency: daily
    access: free
    rate_limit: 10

  - name: project-gutenberg
    type: rss
    url: https://www.gutenberg.org/cache/epub/feeds/today.rss
    quality_tier: 1
    frequency: daily
    access: free
    rate_limit: 5

topics:
  - name: "Platform News"
    keywords:
      - Coursera
      - Udemy
      - edX
      - Khan Academy
      - online learning
      - MOOC
  - name: "EdTech Trends"
    keywords:
      - education technology
      - AI in education
      - adaptive learning
      - personalized learning
      - lifelong learning
  - name: "Skills Development"
    keywords:
      - upskilling
      - reskilling
      - certification
      - professional development
      - career skills
      - credential
```

### Blueprint: Legal / Compliance (`legal-compliance`)

```yaml
# AutoInfo demo domain: Legal / Compliance
# Tracks regulatory developments, compliance requirements, and legal industry news
name: legal-compliance
description: "Legal and compliance intelligence — regulatory updates, court decisions, compliance requirements"

sources:
  - name: scotusblog
    type: rss
    url: https://www.scotusblog.com/feed/
    quality_tier: 1
    frequency: daily
    access: free
    rate_limit: 10

  - name: harvard-corp-gov
    type: rss
    url: https://corpgov.law.harvard.edu/feed/
    quality_tier: 1
    frequency: daily
    access: free
    rate_limit: 10

  - name: sec-edgar-8k
    type: rss
    url: https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&output=atom
    quality_tier: 1
    frequency: daily
    access: free
    rate_limit: 10

  - name: iapp-privacy
    type: web
    url: https://iapp.org/news/topics/privacy/
    quality_tier: 1
    frequency: daily
    access: free
    rate_limit: 5
    settings:
      scrape_selector: "article.news-item"

topics:
  - name: "Regulatory Compliance"
    keywords:
      - SEC
      - regulation
      - compliance
      - FTC
      - corporate governance
      - disclosure
  - name: "Privacy & Data Protection"
    keywords:
      - GDPR
      - CCPA
      - privacy
      - data protection
      - data breach
      - consent
  - name: "Litigation & Enforcement"
    keywords:
      - Supreme Court
      - litigation
      - enforcement
      - ruling
      - penalty
      - settlement
  - name: "Corporate Law"
    keywords:
      - Delaware
      - fiduciary duty
      - shareholder
      - board of directors
      - M&A
      - merger
```

---

## Troubleshooting

### Common issues

| Issue | Likely Cause | Solution |
|-------|-------------|----------|
| Feed returns 0 entries | Feed URL is wrong or blocked | Test with `curl -I <url>`, check HTTP status code |
| `bozo = 1` in feedparser | Malformed XML | Check feed with validator.w3.org/feed |
| Feed has content but no items parsed | Non-standard format | Use `web` type instead of `rss`, add custom parser |
| API returns 403 | Missing/invalid API key | Configure key via `autoinfo configure` or env var |
| API rate limited | Exceeding rate limit | Reduce `rate_limit` in source config, add delays |
| Source times out | Slow server or network | Increase timeout setting, reduce frequency |
| No summaries after processing | Extraction schema mismatch | Check `field_mapping` matches API response structure |
| Quality gate blocks items | G0/G4 failure | Run `autoinfo doctor` for system health, check LLM config |

### Debugging commands

```bash
# Test a single source in isolation
autoinfo sources test --domain <domain> --source <name> --verbose

# Check raw feed output
python -c "import feedparser; f=feedparser.parse('FEED_URL'); print(f.entries[0].keys())"

# Check API response directly
curl -s "API_URL" | python -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d, indent=2)[:2000])"

# View failed items
ls collections/_failed/ 2>/dev/null

# View processing logs
autoinfo doctor --verbose | grep -i "quality gate"
```

### Blocked sources

If a source is paywalled, requires paid subscription, or is otherwise
inaccessible, document it in a `blocked-sources.md` file instead of
including it in the domain config:

```markdown
# Blocked Sources

| Source | Reason | Alternative |
|--------|--------|-------------|
| Bloomberg Terminal | Paid subscription required ($2k+/yr) | Yahoo Finance, MarketWatch |
| WSJ RSS | Paywalled | CNBC, Reuters |
| EdSurge | Feed returned transport error | Open Culture, Coursera Blog |
| Class Central | 403 Forbidden | Coursera Blog, Udemy Blog |
```

---

## Reference: Existing Domain Patterns

### 1. Medical Research (`medical-research`)

**File**: `src/autoinfo/data/domains/medical-research/sources.yaml`

**Pattern highlights**:
- Mix of `api` (PubMed, Semantic Scholar) and `rss` (arXiv) sources
- Uses `field_mapping` for CrossRef API
- Quality tier 1 for authoritative sources
- Topics focus on specific research areas (IVF, Neuroplasticity) with domain keywords

### 2. AI Commercial Intelligence (`ai-commercial`)

**File**: `src/autoinfo/data/domains/ai-commercial/sources.yaml`

**Pattern highlights**:
- All RSS sources (TechCrunch, ProductHunt, Crunchbase, 36kr)
- Simplified config (no `field_mapping` for most RSS sources)
- Topics cover startup funding and product launches
- 36kr source has Chinese-language content with explicit field mapping

### 3. Financial Intelligence (`financial-intelligence`)

**File**: `src/autoinfo/data/domains/financial-intelligence/sources.yaml`

**Pattern highlights**:
- Heavy use of `api` sources (Alpha Vantage, FRED, Twelve Data)
- Multiple sources require API keys (`requires_key: true`)
- Uses `json_path` and `query_param` for API parsing
- `field_mapping` maps API fields to KB schema (e.g., `id: symbol`, `title: name`)
- Topics segmented by use case (Market Trends, Economic Indicators, Corporate Filings)

### 4. Tech / AI / Developer (`tech-ai-developer`)

**File**: `src/autoinfo/data/domains/tech-ai-developer/sources.yaml`

**Pattern highlights**:
- Mix of `api` (GitHub, HackerNews, Stack Exchange) and specialized collectors (Reddit, Bilibili)
- Some sources disabled by default (`enabled: false`) — user opts in
- Rate limits vary widely (10 req/d GitHub unauthenticated, 300 req/d Stack Exchange)
- Settings include subreddit lists and search queries
- Topics cover AI/ML, Developer Tools, and Tech Industry

### 5. Language Learning (`language-learning`)

**File**: `src/autoinfo/data/domains/language-learning/sources.yaml`

**Pattern highlights**:
- Simple domain with 3 RSS sources
- Minimal API configuration
- Topics structured by language skill (Vocabulary, Reading Comprehension, Listening)
- Accessible, free-tier content appropriate for educational use

### Common patterns across all domains

1. `name` matches the directory slug
2. `description` is a short, human-readable line
3. Sources live directly under `sources:` key
4. Topics live directly under `topics:` key
5. Every source has `name`, `type`, `url`, and `rate_limit`
6. Specialized collectors (youtube, reddit, etc.) are usually `enabled: false` by default
7. API-key sources document the key requirement explicitly

---

## Appendix: Quick Command Reference

```bash
# Domain lifecycle
autoinfo domain add --name <domain> --description "<desc>"
autoinfo domain list
autoinfo domain show --name <domain>
autoinfo domain import --from-demo <domain>    # Bootstrap from existing domain
autoinfo domain activate --name <domain>
autoinfo domain deactivate --name <domain>

# Source lifecycle
autoinfo sources add --domain <domain> --name <src> --type rss --url <feed>
autoinfo sources list --domain <domain>
autoinfo sources test --domain <domain> --source <src>
autoinfo sources remove --domain <domain> --name <src>

# Topic lifecycle
autoinfo topics add --domain <domain> --name "<Topic>" --keywords kw1,kw2
autoinfo topics list --domain <domain>

# Collection & processing
autoinfo collect --domain <domain> --limit 10
autoinfo process --domain <domain>
autoinfo summaries list --domain <domain>

# Validation
autoinfo doctor
autoinfo status --domain <domain> --verbose
autoinfo kb search --domain <domain> --query "*"
```
