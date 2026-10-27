# Source diagnosis — 78 required `domain × source` pairs

Every pair in `docs/dev/specs/end-user-matrix.yaml` → `required_sources`,
classified from on-disk config and `collections/` only (no network calls).

Regenerate:

```bash
.venv/bin/python scripts/source_diagnosis.py --output docs/dev/validation-reports/capability-27x3/
```

## Bucket summary

| bucket | rows | meaning |
|---|---|---|
| satisfied | 9 | items > 0 and the last recorded run succeeded |
| degraded | 5 | items > 0 but the last recorded run did not succeed (or no run log exists) |
| failing | 3 | collection directory exists, 0 items |
| never-attempted | 59 | configured and enabled, but no collection directory |
| configured-off | 2 | `enabled: false` in the domain config |
| **total** | **78** | |

Decisions: `deferred` 3, `fix-collector` 8, `keep` 9, `replace-blocked` 2, `run-collection` 56.

## Verification domains

| domain | satisfied | draft/Wiki material available |
|---|---|---|
| medical-research | 2 | yes |
| language-learning | 3 | yes |
| ai-commercial | 3 | yes |

## Decision rule

- `satisfied` → `keep`.
- `degraded` / `failing` → `fix-collector`: the source is configured and
  reachable enough to have produced or attempted work, so the collector or
  its credentials are the defect.
- `never-attempted` in a domain with < 2 satisfied sources → `run-collection`;
  with ≥ 2 → `deferred` (the domain already has sufficient raw material, and
  the row states that stable-source count).
- `configured-off` in a domain with < 2 satisfied sources → `replace-blocked`;
  with ≥ 2 → `deferred`.

## Known blockers (verbatim from the domain configs)

**`general-news` / `wechat2rss`** — the feed URL is a template and its id was never filled:

```yaml
url: https://wechat2rss.xlab.app/feed/{id}.xml
enabled: false
feed_id: <replace-me>
```

Config comment: `settings.feed_id` 一直是占位符 `<replace-me>`，从未填过真实公众号 id，实测该模板返回 404。

**`online-education` / `wanfang`** — licensed API, key declined by the owner:

```yaml
url: https://api.wanfangdata.com.cn/openwanfang/getQuery
enabled: false
requires_key: true
tos_classification: licensed
```

Config comment: wanfang requires_key + tos_classification=licensed，owner 2026-09-30 决定本阶段不配密钥，故禁用。

## Full table

`domain_stable_sources` is the number of satisfied sources in that domain;
`dir_matched` records which config identity (`name:`/`id:`) resolved to the
collection directory, blank when no directory exists.

| domain | source | configured | enabled | items | last_run_status | last_run_at | last_error | bucket | domain_stable_sources | recommendation | dir_matched |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ai-commercial | techcrunch | True | True | 13 | success | 2026-09-02T03:04:34.278600+00:00 |  | satisfied | 3 | keep | name:techcrunch |
| ai-commercial | producthunt | True | True | 13 | success | 2026-09-02T03:05:07.945445+00:00 |  | satisfied | 3 | keep | name:producthunt |
| ai-commercial | Crunchbase | True | True | 10 | error | 2026-09-02T03:04:35.359174+00:00 | RSS fetch failed for https://news.crunchbase.com/feed/: Client error '403 Forbidden' for u | degraded | 3 | fix-collector | name:Crunchbase |
| ai-commercial | 36kr | True | True | 12 | success | 2026-09-02T03:05:06.432886+00:00 |  | satisfied | 3 | keep | name:36kr |
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
| financial-news | cnbc | True | True | 4 | error | 2026-08-15T18:15:27.942428+00:00 | RSS fetch failed for https://www.cnbc.com/id/100003114/device/rss/rss.html: Client error ' | degraded | 1 | fix-collector | name:cnbc |
| financial-news | seeking-alpha | True | True | 4 | success | 2026-08-12T18:39:13.419781+00:00 |  | satisfied | 1 | keep | name:seeking-alpha |
| financial-news | microsoft-newsroom | True | True | 0 | error | 2026-08-15T18:33:02.596625+00:00 | RSS fetch failed for https://news.microsoft.com/source/feed/: Client error '403 Forbidden' | failing | 1 | fix-collector | name:microsoft-newsroom |
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
| language-learning | project-gutenberg | True | True | 13 | success | 2026-09-15T13:33:55.016490+00:00 |  | satisfied | 3 | keep | name:project-gutenberg |
| language-learning | news-in-levels | True | True | 13 | success | 2026-09-15T13:33:46.516840+00:00 |  | satisfied | 3 | keep | name:news-in-levels |
| language-learning | commonlit | True | True | 13 | success | 2026-09-15T13:33:51.058213+00:00 |  | satisfied | 3 | keep | name:commonlit |
| legal-compliance | scotusblog | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| legal-compliance | oyez | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| legal-compliance | gdpr-eu | True | True | 0 |  |  |  | never-attempted | 0 | run-collection |  |
| medical-research | pubmed | True | True | 9 | success | 2026-09-30T09:18:14.419995+00:00 |  | satisfied | 2 | keep | name:pubmed |
| medical-research | semantic-scholar | True | True | 0 | error | 2026-09-30T09:18:21.905995+00:00 | Semantic Scholar API rate-limited (HTTP 429) without an API key — set AUTOINFO_S2_API_KEY  | failing | 2 | fix-collector | name:semantic-scholar |
| medical-research | arXiv | True | True | 1 | success | 2026-09-30T09:18:25.973925+00:00 |  | satisfied | 2 | keep | name:arXiv |
| medical-research | CrossRef | True | True | 0 |  |  |  | never-attempted | 2 | deferred |  |
| medical-research | dblp | True | True | 0 |  |  |  | never-attempted | 2 | deferred |  |
| medical-research | openalex | True | True | 0 |  |  |  | never-attempted | 2 | deferred |  |
| medical-research | uspto | True | True | 0 | error | 2026-09-30T09:18:22.807867+00:00 | PatentsView API retired by USPTO (HTTP 301; migrated to data.uspto.gov) — no keyless paten | failing | 2 | fix-collector | name:uspto |
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
