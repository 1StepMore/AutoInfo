# Collection delta — 2026-10-27

Raw command output: `collect-medical-research-2026-10-27.log`,
`collect-language-learning-2026-10-27.log`,
`collect-ai-commercial-2026-10-27.log`.
Classifier output: `../source-diagnosis.{csv,md}` + `diagnosis-2026-10-27.log`.

## Items fetched (new / found, `--limit 20`)

| Domain | Source | Result |
|---|---|---|
| medical-research | pubmed | 20 / 20 |
| medical-research | arXiv | 20 / 20 |
| medical-research | semantic-scholar | 0 — HTTP 429, no `AUTOINFO_S2_API_KEY` |
| medical-research | uspto | 0 — PatentsView retired (HTTP 301, migrated to data.uspto.gov) |
| medical-research | CrossRef, Unpaywall, openalex, dblp | 0 returned (no error) |
| language-learning | news-in-levels | 10 / 10 |
| language-learning | commonlit | 15 / 15 |
| language-learning | project-gutenberg | 20 / 20 |
| language-learning | bbc-learning-english | 0 — `[Errno 104] Connection reset by peer` |
| ai-commercial | techcrunch | 20 / 20 |
| ai-commercial | producthunt | 20 / 20 |
| ai-commercial | 36kr | 18 / 20 |
| ai-commercial | Crunchbase | 0 — HTTP 403 Forbidden |
| ai-commercial | LMSYS | 0 — `[Errno 101] Network is unreachable` |

Totals: medical-research 40 new, language-learning 45 new, ai-commercial 58 new
(143 items). No `--dry-run`, no source enabled that config had disabled, no source
added, one attempt per hard-blocked source (budget was two).

## Classifier bucket counts after collection

| Domain | satisfied | degraded | failing | never-attempted |
|---|---|---|---|---|
| medical-research | 2 (pubmed, arXiv) | 0 | 2 (semantic-scholar, uspto) | 3 |
| language-learning | 3 | 0 | 0 | 0 |
| ai-commercial | 3 | 1 (Crunchbase: last run failed, prior items exist) | 0 | 0 |

Every verification domain meets the T11 exit bar (≥2 satisfied, ≥1 non-`_runs.json`
item per satisfied source). The **total satisfied count is unchanged at 9** versus
the T5 baseline: these same sources were already satisfied by the 2026-09-15 /
2026-09-30 collections. What this run adds is fresh raw material for T12, not new
`satisfied` cells — recorded here instead of being presented as an improvement.

`medical-research` keeps two `never-attempted` sources because their configured
topics yield no query the handler can use; they are not failures of this run.
