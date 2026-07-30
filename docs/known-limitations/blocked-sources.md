# Blocked High-Value Information Sources

## Overview

AutoInfo aims for universal information access. Some high-value sources cannot be
integrated due to cost, platform policy, or technical limitations. This document
catalogs those sources and identifies potential alternatives — whether within
AutoInfo, via other free/open platforms, or through complementary tools.

**Already integrated and provided as comparison**: AutoInfo includes free/open
sources like PubMed, arXiv, Alpha Vantage, FRED, SEC EDGAR, GitHub Trending,
HackerNews, Project Gutenberg, and RSS feeds. These demonstrate what's possible
when a source has a public API, RSS feed, or permissive scraping policy.

---

## Sources

### Financial Data & Terminal Services

#### Bloomberg Terminal
- **Type**: Proprietary terminal / API
- **Blocking Reason**: Cost: ~$2,000/user/month. Closed ecosystem with no public API.
- **Alternative**: Alpha Vantage (free tier), FRED (free), SEC EDGAR (free), Twelve Data (free tier), World Bank Data (free) — all integrated in AutoInfo's financial-intelligence domain.
- **Feasibility**: Unlikely. Cost structure is incompatible with AutoInfo's BYOK model. Only viable if Bloomberg launches an affordable developer API tier.

#### Reuters Eikon / LSEG Workspace
- **Type**: Proprietary terminal / API
- **Blocking Reason**: Cost: ~$1,500/user/month. Enterprise-only licensing.
- **Alternative**: Alpha Vantage + World Bank Data (integrated). For news, RSS feeds from financial publishers may partially substitute.
- **Feasibility**: Unlikely. Same cost barrier as Bloomberg. LSEG Data & Analytics has no publicly documented affordable API tier.

#### Capital IQ / S&P Global Market Intelligence
- **Type**: Proprietary platform / API
- **Blocking Reason**: Cost: enterprise (undisclosed, typically 5–6 figures/year). No individual/developer tier.
- **Alternative**: SEC EDGAR (integrated) for filings, FRED (integrated) for economic data.
- **Feasibility**: Unlikely without S&P launching a self-serve developer program.

#### Dow Jones / Factiva
- **Type**: Proprietary news database / API
- **Blocking Reason**: Cost: enterprise (undisclosed). Requires institutional subscription.
- **Alternative**: RSS feeds from individual publishers (e.g., Reuters RSS, MarketWatch RSS), Google News RSS. AutoInfo's RSS collector can aggregate from multiple news sources.
- **Feasibility**: Unlikely. Enterprise-only licensing with no public API documentation.

---

### News & Media (Paywalled)

#### Wall Street Journal (WSJ)
- **Type**: Web (subscription paywall)
- **Blocking Reason**: Hard paywall. No public API. Anti-scraping measures in ToS.
- **Alternative**: Free financial news via Yahoo Finance RSS, MarketWatch RSS, CNBC.com (free articles). WSJ headlines are available via RSS but full-text requires subscription.
- **Feasibility**: Likely — if WSJ launches a content licensing API for developers. Otherwise, AutoInfo can ingest WSJ RSS headlines (public) but not full-text articles.

#### Financial Times (FT)
- **Type**: Web (subscription paywall)
- **Blocking Reason**: Metered/hard paywall. No public content API.
- **Alternative**: Free financial news via Reuters RSS, Bloomberg.com (free articles), MarketWatch RSS.
- **Feasibility**: Unlikely. FT's business model is subscription-first. Headlines-only RSS is public; full-text requires institutional license.

#### The Economist
- **Type**: Web (subscription paywall)
- **Blocking Reason**: Hard paywall. No public API. Limited free articles per month.
- **Alternative**: World Bank Data (integrated) for economic data. VOA News RSS for international affairs (free).
- **Feasibility**: Unlikely. No developer API available.

#### CNBC Pro
- **Type**: Web (subscription paywall)
- **Blocking Reason**: Premium tier paywall (~$30/month). No API for Pro content.
- **Alternative**: CNBC.com free articles via RSS, Yahoo Finance RSS, MarketWatch RSS.
- **Feasibility**: Likely — if CNBC opens a Pro API. Currently, free CNBC content is accessible via RSS.

---

### Academic & Research

#### Nature / Science / Cell
- **Type**: Web (subscription paywall)
- **Blocking Reason**: Institutional subscription required. No public API. Individual article costs $30–$50.
- **Alternative**: PubMed (integrated, free) indexes 36M+ biomedical abstracts including Nature/Science/Cell papers. Many authors post preprints on bioRxiv/medRxiv (free, RSS-accessible). arXiv (integrated, free) covers physics, math, CS, and related fields.
- **Feasibility**: Partially likely. Abstracts are free on journal websites — AutoInfo could scrape abstracts with proper attribution, but full-text requires institutional access. Note: abstracts are already discoverable via PubMed.

#### IEEE Xplore / ACM Digital Library
- **Type**: Digital library (subscription paywall)
- **Blocking Reason**: Institutional subscription required. Pay-per-article otherwise (~$33/article IEEE, ~$15/article ACM).
- **Alternative**: arXiv (integrated, free) — most CS/EE papers appear as preprints. Semantic Scholar (free API) indexes and links to open-access versions. Google Scholar for discovery.
- **Feasibility**: Partially likely for abstracts only. Full-text requires institutional license. arXiv preprints cover a large overlap for CS/EE.

---

### Social Media & Platforms

#### Twitter / X API v2
- **Type**: REST API
- **Blocking Reason**: Cost: Basic tier $100/month (10K posts), Pro tier $5,000/month (1M posts). Free tier limited to 1,500 posts/month (write-only; read access restricted). API terms restrict bulk data collection and redistribution.
- **Alternative**: RSS feeds from accounts that cross-post (many journalists and researchers mirror to RSS-enabled blogs or newsletters). Reddit API (free tier still usable) for community discussion. HackerNews API (integrated, free) for tech discussion.
- **Feasibility**: Under review. Pro tier ($5,000/month) is cost-prohibitive for most users. Basic tier ($100/month) may become viable for enterprise AutoInfo deployments if ROI can be demonstrated. Blocked indefinitely for free-tier users.

#### LinkedIn API
- **Type**: REST API (OAuth 2.0)
- **Blocking Reason**: Restricted. LinkedIn's API access requires approved use cases (recruiting, marketing, sales). General content search and knowledge extraction are NOT approved use cases. No public feed/content search endpoint.
- **Alternative**: Company blogs and RSS feeds for corporate news. Crunchbase API (integrated in ai-commercial domain) for company data. AngelList/WellFound for startup data.
- **Feasibility**: Unlikely. LinkedIn's API strategy is product-integration focused, not open-access. Content search is explicitly excluded from approved use cases.

#### Facebook / Instagram Graph API
- **Type**: REST API (OAuth 2.0)
- **Blocking Reason**: Read-only for approved use cases (Page management, Instagram business). No general content search. No public feed access. Instagram Basic Display API deprecated in 2024.
- **Alternative**: Public RSS feeds from organizations that also post on Facebook/Instagram. Many businesses maintain blogs or press pages with RSS.
- **Feasibility**: Very unlikely. Meta's API strategy is tightly restricted to business integrations. No path to general content access.

#### TikTok API
- **Type**: REST API (OAuth 2.0)
- **Blocking Reason**: Restricted. TikTok's Research API requires academic/research institution affiliation and approved application. TikTok for Developers API is for content creation/management, not consumption. Region-locked in some countries.
- **Alternative**: For trend monitoring: Google Trends API (free tier). For creator content: YouTube RSS feeds (public, free) for creators who cross-post.
- **Feasibility**: Very unlikely. Research API is narrowly scoped and not designed for general knowledge tracking.

---

### Legal & Regulatory

#### Westlaw / Thomson Reuters
- **Type**: Proprietary platform / API
- **Blocking Reason**: Cost: enterprise (typically 5-figures/year per seat). No public API. Tightly controlled legal database.
- **Alternative**: CourtListener (free, RECAP archive) for US federal court documents. GovInfo.gov (free) for US legislation and regulations. EUR-Lex (free) for EU law.
- **Feasibility**: Unlikely. Westlaw's business model is built on exclusivity. No path to affordable access.

#### LexisNexis
- **Type**: Proprietary platform / API
- **Blocking Reason**: Cost: enterprise (typically 5-figures/year per seat). No public API for general search.
- **Alternative**: Same as Westlaw: CourtListener, GovInfo.gov, EUR-Lex. Some state-level court systems provide free docket access.
- **Feasibility**: Unlikely. LexisNexis developer portal exists but is focused on risk/fraud APIs, not legal content search.

---

### Comparison: Free Sources Already Integrated

These sources demonstrate what AutoInfo can achieve when APIs are open and accessible:

| Source | Type | Domain | Note |
|--------|------|--------|------|
| **PubMed** | REST API (E-utilities) | medical-research | 36M+ biomedical abstracts. Free, no key required. |
| **arXiv** | REST API + RSS | medical-research, tech-ai-developer | 2.4M+ preprints. Free, bulk access supported. |
| **CrossRef** | REST API | medical-research | DOI metadata. Free, no key required. |
| **Alpha Vantage** | REST API | financial-intelligence | Stock/forex/crypto data. Free tier: 25 req/day. |
| **FRED** | REST API | financial-intelligence | 823K+ US economic series. Free, key required. |
| **SEC EDGAR** | REST API (xbrl) | financial-intelligence | All public company filings. Free, no key. |
| **HackerNews** | Firebase API | tech-ai-developer | Tech community discussion. Free, no key. |
| **GitHub Trending** | Web scraping | tech-ai-developer | Developer project discovery. Public pages. |

---

## Summary

| Source | Reason | Alternative | Feasibility |
|--------|--------|-------------|-------------|
| Bloomberg Terminal | Cost: $2,000/user/mo | Alpha Vantage, FRED, SEC EDGAR (integrated) | Unlikely |
| Reuters Eikon | Cost: $1,500/user/mo | Alpha Vantage, World Bank Data (integrated) | Unlikely |
| Capital IQ / S&P Global | Cost: enterprise | SEC EDGAR, FRED (integrated) | Unlikely |
| Twitter / X API v2 | Cost: $100–$5,000/mo, policy | RSS from cross-posting accounts, HackerNews | Under review |
| LinkedIn API | Policy: restricted use cases | Crunchbase (integrated), company RSS | Unlikely |
| Facebook/Instagram Graph API | Policy: no content search | Organization RSS, press pages | Very unlikely |
| TikTok API | Policy: restricted, region-locked | YouTube RSS for cross-posters | Very unlikely |
| WeChat Official Account API | Platform: China-only, restricted | General RSS for organizations with blogs | Unlikely |
| Westlaw | Cost: enterprise | CourtListener, GovInfo.gov (free) | Unlikely |
| LexisNexis | Cost: enterprise | CourtListener, EUR-Lex (free) | Unlikely |
| Dow Jones / Factiva | Cost: enterprise | Publisher RSS feeds (free) | Unlikely |
| CNBC Pro | Cost: ~$30/mo paywall | CNBC free RSS, Yahoo Finance RSS | Likely |
| Wall Street Journal | Cost: subscription paywall | Yahoo Finance RSS, MarketWatch RSS | Likely |
| Financial Times | Cost: subscription paywall | Reuters RSS, MarketWatch RSS | Unlikely |
| The Economist | Cost: subscription paywall | VOA News RSS, World Bank Data | Unlikely |
| Nature / Science / Cell | Cost: subscription/institutional | PubMed, arXiv (integrated, free) | Partially likely (abstracts) |
| IEEE / ACM Digital Libraries | Cost: subscription/institutional | arXiv, Semantic Scholar (free) | Partially likely (abstracts) |

---

## How to Contribute

When evaluating a new source for integration, check:

1. **API availability** — Does the source have a documented public API?
2. **Cost structure** — Is there a free tier or affordable developer plan?
3. **Terms of Service** — Does the ToS permit automated collection and knowledge-base storage?
4. **RSS/Atom feed** — Even without an API, many sources offer RSS feeds.

If a source is blocked, document it here with the blocking reason, any alternative sources already integrated in AutoInfo, and a feasibility assessment.

---

*Last updated: 2026-07-30. This is a living document — sources change their API policies and pricing over time.*
