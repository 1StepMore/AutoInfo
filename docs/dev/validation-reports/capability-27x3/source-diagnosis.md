# Source diagnosis — 78 required `domain x source` pairs

Pure-filesystem classification. Regenerate with:

```bash
python3 scripts/source_diagnosis.py
```

## Bucket counts

| bucket | count |
|---|---|
| satisfied | 9 |
| degraded | 5 |
| failing | 3 |
| never-attempted | 59 |
| configured-off | 2 |
| **total** | **78** |

## Rows

| domain | source | configured | enabled | collections_items | last_run_status | last_run_at | last_error | bucket | domain_stable_sources | recommendation | dir_matched |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ai-commercial | techcrunch | True | True | 33 | success | 2026-10-27T07:25:26.397024+00:00 |  | satisfied | 3 | keep | name:techcrunch |
| ai-commercial | producthunt | True | True | 33 | success | 2026-10-27T07:26:02.210687+00:00 |  | satisfied | 3 | keep | name:producthunt |
| ai-commercial | Crunchbase | True | True | 10 | error | 2026-10-27T07:25:28.582452+00:00 | RSS fetch failed for https://news.crunchbase.com/feed/: Client error '403 Forbidden' for url 'https://news.crunchbase.com/feed/' For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/403 | degraded | 3 | fix-collector | name:Crunchbase |
| ai-commercial | 36kr | True | True | 30 | success | 2026-10-27T07:26:00.222305+00:00 |  | satisfied | 3 | keep | name:36kr |
| b2b | producthunt | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| b2b | techcrunch | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| b2b | crunchbase-news | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| b2b | hackernews | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| b2b | saastr | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| financial-intelligence | Alpha Vantage | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| financial-intelligence | FRED | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| financial-intelligence | Finnhub | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| financial-intelligence | SEC EDGAR | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| financial-intelligence | Twelve Data | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| financial-intelligence | World Bank Data | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| financial-intelligence | Quandl/Nasdaq Data Link | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| financial-intelligence | CNBC Investing | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| financial-intelligence | TheStreet | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| financial-intelligence | MarketWatch Markets (DJ) | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| financial-news | cnbc | True | True | 4 | error | 2026-08-15T18:15:27.942428+00:00 | RSS fetch failed for https://www.cnbc.com/id/100003114/device/rss/rss.html: Client error '403 Forbidden' for url 'https://www.cnbc.com/id/100003114/device/rss/rss.html' For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/403 | degraded | 1 | fix-collector | name:cnbc |
| financial-news | seeking-alpha | True | True | 4 | success | 2026-08-12T18:39:13.419781+00:00 |  | satisfied | 1 | keep | name:seeking-alpha |
| financial-news | microsoft-newsroom | True | True | 0 | error | 2026-08-15T18:33:02.596625+00:00 | RSS fetch failed for https://news.microsoft.com/source/feed/: Client error '403 Forbidden' for url 'https://news.microsoft.com/source/feed/' For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/403 | failing | 1 | fix-collector | name:microsoft-newsroom |
| financial-news | WSJ RSS | True | True | 0 |  |  |  | never-attempted | 1 | run-collection |  |
| financial-news | MW RSS | True | True | 0 |  |  |  | never-attempted | 1 | run-collection |  |
| gaming | ign-rss | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| gaming | gamesindustry-biz | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| gaming | gcores-rss | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| gaming | gamespot | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| gaming | pc-gamer | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| gaming | eurogamer | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| general-news | guardian-open-platform | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| general-news | ap-api | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| general-news | zhihu-daily | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| general-news | wechat2rss | True | False | 0 |  |  |  | configured-off | 0 | replace-blocked |  |
| general-news | wired | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| general-news | france24 | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| general-news | npr-news | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| general-news | ars-technica | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| general-news | the-verge | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| general-news | engadget | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| general-news | spacenews | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| language-learning | project-gutenberg | True | True | 33 | success | 2026-10-27T07:24:50.701624+00:00 |  | satisfied | 3 | keep | name:project-gutenberg |
| language-learning | news-in-levels | True | True | 23 | success | 2026-10-27T07:24:45.028299+00:00 |  | satisfied | 3 | keep | name:news-in-levels |
| language-learning | commonlit | True | True | 28 | success | 2026-10-27T07:24:47.728436+00:00 |  | satisfied | 3 | keep | name:commonlit |
| legal-compliance | scotusblog | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| legal-compliance | oyez | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| legal-compliance | gdpr-eu | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| medical-research | pubmed | True | True | 29 | success | 2026-10-27T07:23:42.773249+00:00 |  | satisfied | 2 | keep | name:pubmed |
| medical-research | semantic-scholar | True | True | 0 | error | 2026-10-27T07:23:51.065599+00:00 | Semantic Scholar API rate-limited (HTTP 429) without an API key — set AUTOINFO_S2_API_KEY for a higher rate limit | failing | 2 | fix-collector | name:semantic-scholar |
| medical-research | arXiv | True | True | 21 | success | 2026-10-27T07:23:55.921374+00:00 |  | satisfied | 2 | keep | name:arXiv |
| medical-research | CrossRef | True | True | 0 |  |  |  | never-attempted | 2 | deferred |  |
| medical-research | dblp | True | True | 0 |  |  |  | never-attempted | 2 | deferred |  |
| medical-research | openalex | True | True | 0 |  |  |  | never-attempted | 2 | deferred |  |
| medical-research | uspto | True | True | 0 | error | 2026-10-27T07:23:51.651316+00:00 | PatentsView API retired by USPTO (HTTP 301; migrated to data.uspto.gov) — no keyless patent search API available | failing | 2 | fix-collector | name:uspto |
| online-education | coursera-blog | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| online-education | open-culture | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| online-education | coursera | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| online-education | wanfang | True | False | 0 |  |  |  | configured-off | 0 | replace-blocked |  |
| online-video | variety | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| online-video | hollywood-reporter | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| online-video | netflix-tech-blog | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| online-video | pitchfork | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| online-video | billboard | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| online-video | bilibili-popular | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| online-video | thewrap | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| retail | retail-dive | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| retail | modern-retail | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| retail | shopify-news | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| retail | digiday | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| tech-ai-developer | GitHub Trending | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| tech-ai-developer | HackerNews API | True | True | 11 |  |  |  | degraded | 0 | fix-collector | name:HackerNews API |
| tech-ai-developer | Substack RSS (tech) — Pragmatic Engineer | True | True | 5 |  |  |  | degraded | 0 | fix-collector | name:Substack RSS (tech) — Pragmatic Engineer |
| tech-ai-developer | Stack Exchange | True | True | 16 |  |  |  | degraded | 0 | fix-collector | name:Stack Exchange |
| tech-ai-developer | ProductHunt | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| tech-ai-developer | Reddit | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| tech-ai-developer | Bilibili (B站) | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| tech-ai-developer | HN Algolia API | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| tech-ai-developer | GitHub Blog | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
